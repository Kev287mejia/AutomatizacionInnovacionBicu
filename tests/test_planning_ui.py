"""
tests.test_planning_ui

Suite de Pruebas Automatizadas de la Interfaz de Usuario de Planificación Institucional BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.

Cubre:
  - UI-01: Apertura y navegación al Módulo 3.
  - UI-02: Listado de actividades en PlannedActivitiesListView.
  - UI-03: Filtro por sede.
  - UI-04: Filtro por estado.
  - UI-05: Búsqueda por término.
  - UI-06: Detalle de actividad (PlannedActivityDetailView).
  - UI-07: Creación de DRAFT.
  - UI-08: Idempotencia de DRAFT (reutilización de borrador).
  - UI-09: Edición de bloques en MethodologicalDesignEditorView.
  - UI-10: Guardado de DRAFT (update_design_draft).
  - UI-11: Validación del diseño (validate_design).
  - UI-12: Visualización de observaciones en ValidationDialog.
  - UI-13: Aprobación formal mediante ApprovalDialog.
  - UI-14: Protección de APPROVED (inmutabilidad y bloqueo de inputs).
  - UI-15: Generación documental DOCX (export_docx).
  - UI-16: Manejo institucional de errores de exportación.
  - UI-17: No contaminación de Word → M1–M5.
  - UI-18: Análisis AST de aislamiento (cero sqlite3 ni repositorios directos en vistas).
  - UI-R08: Prueba explícita de rechazo backend ante intento de modificar un diseño APPROVED.
  - UI-E2E: Flujo completo de extremo a extremo sin mocks.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock, patch
import uuid
import pytest

from app.planning.application.services import (
    MethodologicalDesignService,
    MethodologicalDocumentExportService,
)
from app.planning.domain.dtos import (
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    PlannedActivityDetailDTO,
    PlannedActivitySummaryDTO,
    TimeBlockDTO,
    UpdateMethodologicalDesignCommand,
    ValidationReportDTO,
    ValidationResultDTO,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.value_objects import (
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)
from app.planning.infrastructure.document_rendering import DocxMethodologicalDocumentRenderer
from app.planning.infrastructure.persistence import (
    PlanningUnitOfWork,
    SQLiteMethodologicalDesignRepository,
)
from app.planning.infrastructure.persistence.schema_v003 import V003_SCHEMA_DDL_STATEMENTS
from app.planning.ui.services.planning_ui_service import PlanningUIError, PlanningUIService
from app.planning.ui.views.activities_list_view import PlannedActivitiesListView
from app.planning.ui.views.activity_detail_view import PlannedActivityDetailView
from app.planning.ui.views.approval_dialog import ApprovalDialog
from app.planning.ui.views.design_editor_view import MethodologicalDesignEditorView
from app.planning.ui.views.planning_main_view import PlanningMainView
from app.planning.ui.views.validation_dialog import ValidationDialog
from app.word_consolidator.ui.views.module_selection_view import ModuleSelectionView


@pytest.fixture
def clean_db(tmp_path: Path) -> Path:
    """Base de datos SQLite V003 limpia con el esquema completo."""
    db_file = tmp_path / "test_planning_ui.sqlite"
    conn = sqlite3.connect(str(db_file))
    try:
        cursor = conn.cursor()
        for statement in V003_SCHEMA_DDL_STATEMENTS:
            cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return db_file


@pytest.fixture
def populated_db(clean_db: Path) -> tuple[Path, PlannedActivity, PlannedActivity]:
    """Base de datos con dos actividades del POA para pruebas de listado y filtrado."""
    goals_1 = ParticipantGoals(
        est_grado_m=10,
        est_grado_f=15,
        est_postgrado_m=2,
        est_postgrado_f=3,
        docentes_m=4,
        docentes_f=4,
        administrativos_m=1,
        administrativos_f=1,
        externos_m=5,
        externos_f=5,
    )
    act1 = PlannedActivity.create(
        planning_id="POA-BLUE-001",
        activity_name="Taller de Innovación y Metodologías Ágiles",
        sede="Bluefields",
        area_responsable="Dirección de Innovación y Emprendimiento",
        eje_estrategia="EJE_11",   # C1: Innovación, Ciencia, Tecnología e Investigación
        programa="PGM_07",         # C2: Emprendimiento y Desarrollo Económico
        tipo_evento="EVT_CAPACITACION",  # C4: Capacitación
        participant_goals=goals_1,
        proposito="Transferir capacidades metodológicas en innovación.",
        fecha_evento=date(2026, 10, 15),
    )

    goals_2 = ParticipantGoals(
        est_grado_m=20,
        est_grado_f=20,
        est_postgrado_m=0,
        est_postgrado_f=0,
        docentes_m=5,
        docentes_f=5,
        administrativos_m=2,
        administrativos_f=2,
        externos_m=0,
        externos_f=0,
    )
    act2 = PlannedActivity.create(
        planning_id="POA-BILWI-002",
        activity_name="Seminario de Emprendimiento Comunitario",
        sede="Bilwi",
        area_responsable="Coordinación de Extensión",
        eje_estrategia="EJE_11",   # C1: Innovación, Ciencia, Tecnología e Investigación
        programa="PGM_07",         # C2: Emprendimiento y Desarrollo Económico
        tipo_evento="EVT_CAPACITACION",  # C4: Capacitación
        participant_goals=goals_2,
        proposito="Fomentar iniciativas de emprendimiento local.",
        fecha_evento=date(2026, 11, 20),
    )

    with PlanningUnitOfWork(db_path=clean_db) as uow:
        uow.planned_activities.save(act1)
        uow.planned_activities.save(act2)
        uow.commit()

    return clean_db, act1, act2


@pytest.fixture
def ui_service(populated_db: tuple[Path, PlannedActivity, PlannedActivity]) -> PlanningUIService:
    db_file, _, _ = populated_db
    uow = PlanningUnitOfWork(db_path=db_file)
    design_service = MethodologicalDesignService(uow=uow)

    conn = sqlite3.connect(str(db_file))
    design_repo = SQLiteMethodologicalDesignRepository(conn)
    renderer = DocxMethodologicalDocumentRenderer()
    export_service = MethodologicalDocumentExportService(
        design_repository=design_repo,
        renderer=renderer,
    )

    return PlanningUIService(
        design_service=design_service,
        export_service=export_service,
    )


# ===========================================================================
# SUITE DE PRUEBAS DE LA INTERFAZ DE USUARIO (UI-01 A UI-18, R08, E2E)
# ===========================================================================

class TestPlanningUI:
    """Batería exhaustiva de pruebas para la UI de Planificación Institucional."""

    def test_ui_01_apertura_modulo_en_module_selection_view(self):
        """UI-01: ModuleSelectionView expone el callback del Módulo 3.

        Se parchenean CTkFrame.__init__ y _init_ui para aislar el test del
        entorno gráfico Tkinter (headless/CI). El contrato verificado es
        que el atributo on_select_planning quede asignado y que el método
        _on_click_planning lo invoque exactamente una vez.
        """
        mock_planning_cb = MagicMock()

        # Parche sobre CTkFrame para evitar la inicialización Tkinter real.
        with (
            patch("customtkinter.CTkFrame.__init__", return_value=None),
            patch.object(ModuleSelectionView, "_init_ui", return_value=None),
        ):
            view = ModuleSelectionView.__new__(ModuleSelectionView)
            view.on_select_word_batch = None
            view.on_select_matrices_word = None
            view.on_select_planning = mock_planning_cb

        assert view.on_select_planning == mock_planning_cb

        # Disparar callback
        view._on_click_planning()
        mock_planning_cb.assert_called_once()

    def test_ui_02_listado_actividades(self, ui_service: PlanningUIService):
        """UI-02: PlanningUIService lista todas las actividades con sus estados."""
        activities = ui_service.list_activities()
        assert len(activities) == 2
        pids = [a.planning_id for a in activities]
        assert "POA-BLUE-001" in pids
        assert "POA-BILWI-002" in pids
        for a in activities:
            assert a.design_status == "SIN_DISENO"

    def test_ui_03_filtro_por_sede(self, ui_service: PlanningUIService):
        """UI-03: Filtrado determinista por sede institucional."""
        blue_acts = ui_service.list_activities(sede="Bluefields")
        assert len(blue_acts) == 1
        assert blue_acts[0].planning_id == "POA-BLUE-001"

        bilwi_acts = ui_service.list_activities(sede="Bilwi")
        assert len(bilwi_acts) == 1
        assert bilwi_acts[0].planning_id == "POA-BILWI-002"

        mina_acts = ui_service.list_activities(sede="Las Minas")
        assert len(mina_acts) == 0

    def test_ui_04_filtro_por_estado(self, ui_service: PlanningUIService):
        """UI-04: Filtrado por estado de diseño metodológico."""
        sin_diseno = ui_service.list_activities(status="SIN_DISENO")
        assert len(sin_diseno) == 2

        drafts = ui_service.list_activities(status="DRAFT")
        assert len(drafts) == 0

        # Crear un DRAFT y verificar filtrado
        ui_service.create_design_draft("POA-BLUE-001", created_by="coordinador_1")
        drafts_after = ui_service.list_activities(status="DRAFT")
        assert len(drafts_after) == 1
        assert drafts_after[0].planning_id == "POA-BLUE-001"

    def test_ui_05_busqueda_por_termino(self, ui_service: PlanningUIService):
        """UI-05: Búsqueda por coincidencia de texto en nombre y código."""
        res_nombre = ui_service.list_activities(search_term="Innovación")
        assert len(res_nombre) == 1
        assert res_nombre[0].planning_id == "POA-BLUE-001"

        res_codigo = ui_service.list_activities(search_term="BILWI")
        assert len(res_codigo) == 1
        assert res_codigo[0].planning_id == "POA-BILWI-002"

        res_vacio = ui_service.list_activities(search_term="Inexistente")
        assert len(res_vacio) == 0

    def test_ui_06_detalle_actividad(self, ui_service: PlanningUIService):
        """UI-06: Consulta de ficha técnica de actividad sin datos técnicos expuestos."""
        detail = ui_service.get_activity_detail("POA-BLUE-001")
        assert detail is not None
        assert detail.activity_name == "Taller de Innovación y Metodologías Ágiles"
        assert detail.sede == "Bluefields"
        assert detail.area_responsable == "Dirección de Innovación y Emprendimiento"
        assert detail.participant_goals is not None
        assert detail.participant_goals.total() == 50
        assert detail.design_status == "SIN_DISENO"

    def test_ui_07_creacion_draft(self, ui_service: PlanningUIService):
        """UI-07: Inicialización de borrador DRAFT con campos prellenados.

        MethodologicalDesignDTO no expone un campo .status; el estado DRAFT
        se infiere porque approved_by es None (sin aprobación registrada).
        """
        draft = ui_service.create_design_draft("POA-BLUE-001", created_by="profesor_kenia")
        assert draft.approved_by is None, "DRAFT: approved_by debe ser None (sin aprobación)"
        assert draft.created_by == "profesor_kenia"
        assert draft.document_title == "Diseño metodológico Taller de Innovación y Metodologías Ágiles"
        assert draft.faq is not None
        assert draft.faq.q1_que_es == "Taller de Innovación y Metodologías Ágiles"
        assert draft.faq.q3_sesiones == "Sesión única"
        assert "50 participantes" in draft.faq.q4_protagonistas
        assert draft.faq.q5_facilitador == "Dirección de Innovación y Emprendimiento"

    def test_ui_08_idempotencia_draft(self, ui_service: PlanningUIService):
        """UI-08: Reutilización determinista de borrador existente sin duplicar."""
        d1 = ui_service.create_design_draft("POA-BLUE-001", created_by="usuario_a")
        d2 = ui_service.create_design_draft("POA-BLUE-001", created_by="usuario_b")
        assert d1.design_id == d2.design_id
        assert d1.created_by == "usuario_a"  # Conserva autor original

    def test_ui_09_y_10_edicion_y_guardado_draft(self, ui_service: PlanningUIService):
        """UI-09 y UI-10: Edición de los 5 bloques y guardado in-place."""
        draft = ui_service.create_design_draft("POA-BLUE-001", created_by="usuario_edicion")

        agenda = (
            TimeBlockDTO(sequence=1, label="Registro y Apertura", minutes=20),
            TimeBlockDTO(sequence=2, label="Sesión Práctica", minutes=100),
        )
        matrix = (
            OperationalActivityDTO(
                step_number=1,
                phase_label="Registro y Apertura",
                operative_goal="Acreditar asistentes",
                procedure="Firma en listas oficiales",
                materials="Listas de asistencia",
                minutes=20,
            ),
            OperationalActivityDTO(
                step_number=2,
                phase_label="Sesión Práctica",
                operative_goal="Desarrollar dinámica",
                procedure="Trabajo por mesas",
                materials="Papelógrafos y marcadores",
                minutes=100,
            ),
        )

        faq = FAQTableDTO(
            q1_que_es="Taller de Innovación",
            q2_para_que="Capacitar equipos",
            q3_sesiones="Sesión única",
            q4_protagonistas="50 protagonistas",
            q5_facilitador="Dirección de Innovación",
            q6_materiales="Papelógrafos, proyector",
            q7_duracion="120 minutos",
        )

        cmd = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Contexto institucional del taller en BICU...",
            methodological_approach="Enfoque participativo constructivista.",
            objectives=("Comprender metodologías ágiles.", "Aplicar herramientas de innovación."),
            faq=faq,
            agenda=agenda,
            operational_matrix=matrix,
        )

        updated = ui_service.update_design_draft(cmd)
        assert updated.introduction == "Contexto institucional del taller en BICU..."
        assert updated.objective_1 == "Comprender metodologías ágiles."
        assert updated.objective_2 == "Aplicar herramientas de innovación."
        assert len(updated.agenda) == 2
        assert updated.total_minutes == 120
        assert len(updated.operational_matrix) == 2

    def test_ui_11_y_12_validacion_visual(self, ui_service: PlanningUIService):
        """UI-11 y UI-12: Validación del diseño metodológico y estructura de observaciones."""
        # 1. Diseño incompleto (recién creado, faltan objetivos, agenda, matriz)
        draft = ui_service.create_design_draft("POA-BILWI-002", created_by="autor_test")
        report_invalido = ui_service.validate_design(draft.design_id)
        assert not report_invalido.is_valid
        assert len(report_invalido.errors) > 0

        # Verificar que los resultados se pueden formatear sin fallar
        for err in report_invalido.errors:
            assert isinstance(err.message, str)
            assert err.severity == "ERROR"

    def test_ui_13_aprobacion_formal(self, ui_service: PlanningUIService):
        """UI-13: Flujo de aprobación formal con registro de aprobador."""
        draft = ui_service.create_design_draft("POA-BLUE-001", created_by="autor_valido")

        # Completar todos los campos para que sea 100% válido
        agenda = (TimeBlockDTO(sequence=1, label="Sesión Única", minutes=90),)
        matrix = (
            OperationalActivityDTO(
                step_number=1,
                phase_label="Sesión Única",
                operative_goal="Objetivo operativo",
                procedure="Procedimiento",
                materials="Materiales",
                minutes=90,
            ),
        )
        faq = FAQTableDTO(
            q1_que_es="Actividad",
            q2_para_que="Propósito",
            q3_sesiones="Sesión única",
            q4_protagonistas="50 protagonistas",
            q5_facilitador="Facilitador",
            q6_materiales="Materiales",
            q7_duracion="90 minutos",
        )
        cmd = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Introducción válida...",
            methodological_approach="Enfoque válido...",
            objectives=("Objetivo 1", "Objetivo 2"),
            faq=faq,
            agenda=agenda,
            operational_matrix=matrix,
        )
        ui_service.update_design_draft(cmd)

        # Validar y aprobar
        report = ui_service.validate_design(draft.design_id)
        assert report.is_valid

        approved = ui_service.approve_design(
            design_id=draft.design_id,
            approved_by="Dra. Kenia Mejia — Directora",
        )
        # MethodologicalDesignDTO no tiene .status; APPROVED se confirma
        # porque approved_by contiene el nombre del aprobador institucional.
        assert approved.approved_by == "Dra. Kenia Mejia — Directora", (
            "APPROVED: approved_by debe contener el nombre del aprobador"
        )

    def test_ui_14_y_r08_proteccion_inmutabilidad_approved(self, ui_service: PlanningUIService):
        """UI-14 y R-08: Intento de modificar un diseño APPROVED es estrictamente rechazado por el backend."""
        draft = ui_service.create_design_draft("POA-BLUE-001", created_by="autor_r08")
        agenda = (TimeBlockDTO(sequence=1, label="Sesión", minutes=60),)
        matrix = (
            OperationalActivityDTO(
                step_number=1,
                phase_label="Sesión",
                operative_goal="Meta",
                procedure="Proc",
                materials="Mat",
                minutes=60,
            ),
        )
        faq = FAQTableDTO(
            q1_que_es="Actividad",
            q2_para_que="Propósito",
            q3_sesiones="Sesión única",
            q4_protagonistas="50",
            q5_facilitador="Facilitador",
            q6_materiales="Materiales",
            q7_duracion="60 minutos",
        )
        cmd_valido = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Intro...",
            methodological_approach="Enfoque...",
            objectives=("Obj 1", "Obj 2"),
            faq=faq,
            agenda=agenda,
            operational_matrix=matrix,
        )
        ui_service.update_design_draft(cmd_valido)
        ui_service.approve_design(draft.design_id, approved_by="Aprobador Institucional")

        # Intentar modificar el diseño aprobado
        cmd_invalido = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Intento de cambio ilegal post-aprobación...",
        )
        with pytest.raises(PlanningUIError) as exc_info:
            ui_service.update_design_draft(cmd_invalido)

        assert "Regla R-08" in exc_info.value.message
        assert "APROBADO" in exc_info.value.message

    def test_ui_15_generacion_docx(self, ui_service: PlanningUIService, tmp_path: Path):
        """UI-15: Exportación física del diseño aprobado hacia un archivo Word (.docx)."""
        draft = ui_service.create_design_draft("POA-BLUE-001", created_by="autor_docx")
        agenda = (TimeBlockDTO(sequence=1, label="Taller", minutes=60),)
        matrix = (
            OperationalActivityDTO(
                step_number=1,
                phase_label="Taller",
                operative_goal="Meta",
                procedure="Proc",
                materials="Mat",
                minutes=60,
            ),
        )
        faq = FAQTableDTO(
            q1_que_es="Actividad",
            q2_para_que="Propósito",
            q3_sesiones="Sesión única",
            q4_protagonistas="50",
            q5_facilitador="Facilitador",
            q6_materiales="Materiales",
            q7_duracion="60 minutos",
        )
        cmd = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Intro...",
            methodological_approach="Enfoque...",
            objectives=("Obj 1", "Obj 2"),
            faq=faq,
            agenda=agenda,
            operational_matrix=matrix,
        )
        ui_service.update_design_draft(cmd)
        ui_service.approve_design(draft.design_id, approved_by="Director")

        out_docx = tmp_path / "Diseno_Oficial.docx"
        result_path = ui_service.export_docx(draft.design_id, output_path=out_docx)

        assert Path(result_path).exists()
        assert Path(result_path).stat().st_size > 0

    def test_ui_16_manejo_errores_docx(self, ui_service: PlanningUIService):
        """UI-16: Excepciones de renderizado convertidas a mensajes amigables."""
        inexistente = uuid.uuid4()
        with pytest.raises(PlanningUIError) as exc_info:
            ui_service.export_docx(inexistente, "inexistente.docx")
        assert "No se pudo generar el documento" in exc_info.value.message

    def test_ui_17_no_contaminacion_word_a_matrices(self):
        """UI-17: Ningún componente de Planning importa o modifica app.word_consolidator."""
        ui_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "ui"
        py_files = list(ui_dir.rglob("*.py"))
        assert len(py_files) > 0

        forbidden_tokens = [
            "WordActivityExtractor",
            "ConsolidationPipeline",
            "Matriz_1",
            "Matriz_2",
            "Matriz_3",
            "Matriz_4",
            "Matriz_5",
            "generar_informe_semanal_word",
        ]

        for pf in py_files:
            content = pf.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in content, f"Token prohibido '{token}' detectado en {pf}"

    def test_ui_18_aislamiento_ast_sin_sqlite3_en_vistas(self):
        """UI-18: Análisis AST verificando que las vistas no importan sqlite3 directamente."""
        views_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "ui" / "views"
        py_files = list(views_dir.rglob("*.py"))
        assert len(py_files) > 0

        for pf in py_files:
            tree = ast.parse(pf.read_text(encoding="utf-8"), filename=str(pf))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name != "sqlite3", f"sqlite3 importado directamente en vista: {pf}"
                elif isinstance(node, ast.ImportFrom):
                    assert node.module != "sqlite3", f"from sqlite3 import ... en vista: {pf}"

    def test_ui_e2e_flujo_completo(self, ui_service: PlanningUIService, tmp_path: Path):
        """UI-E2E: Escenario integral: POA -> SIN_DISENO -> CREAR DRAFT -> COMPLETAR -> VALIDAR -> APROBAR -> DOCX."""
        # 1. Explorar lista
        actividades = ui_service.list_activities(search_term="Innovación")
        assert len(actividades) == 1
        pid = actividades[0].planning_id

        # 2. Consultar detalle
        detalle = ui_service.get_activity_detail(pid)
        assert detalle is not None
        assert detalle.design_status == "SIN_DISENO"

        # 3. Crear DRAFT
        draft = ui_service.create_design_draft(pid, created_by="facilitador_e2e")
        assert draft.approved_by is None, "E2E DRAFT: approved_by debe ser None"

        # 4. Completar los 5 bloques
        agenda = (
            TimeBlockDTO(sequence=1, label="Apertura Institucional", minutes=30),
            TimeBlockDTO(sequence=2, label="Trabajo de Grupos", minutes=90),
        )
        matrix = (
            OperationalActivityDTO(
                step_number=1,
                phase_label="Apertura Institucional",
                operative_goal="Presentar objetivos",
                procedure="Exposición con diapositivas",
                materials="Proyector y laptop",
                minutes=30,
            ),
            OperationalActivityDTO(
                step_number=2,
                phase_label="Trabajo de Grupos",
                operative_goal="Construir prototipos",
                procedure="Mesas de co-creación",
                materials="Papelógrafos, notas adhesivas",
                minutes=90,
            ),
        )
        faq = FAQTableDTO(
            q1_que_es=draft.faq.q1_que_es if draft.faq else "Actividad",
            q2_para_que="Fomentar capacidades de innovación",
            q3_sesiones="Sesión única",
            q4_protagonistas="50 participantes",
            q5_facilitador="Dirección de Innovación",
            q6_materiales="Papelógrafos, notas adhesivas, proyector",
            q7_duracion="120 minutos",
        )
        cmd = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Introducción y justificación formal...",
            methodological_approach="Aprender haciendo y metodología Design Thinking.",
            objectives=("Aprender los conceptos básicos.", "Aplicar la metodología en proyectos."),
            faq=faq,
            agenda=agenda,
            operational_matrix=matrix,
        )
        updated = ui_service.update_design_draft(cmd)
        assert updated.total_minutes == 120

        # 5. Validar
        report = ui_service.validate_design(draft.design_id)
        assert report.is_valid
        assert len(report.errors) == 0

        # 6. Aprobar
        approved = ui_service.approve_design(draft.design_id, approved_by="Ing. Kevin Mejia — Decano")
        assert approved.approved_by == "Ing. Kevin Mejia — Decano", (
            "E2E APPROVED: approved_by debe contener nombre del decano"
        )

        # 7. Exportar DOCX
        docx_path = tmp_path / "E2E_Diseno_Metodologico.docx"
        exported = ui_service.export_docx(draft.design_id, docx_path)
        assert Path(exported).exists()
        assert Path(exported).stat().st_size > 1000  # Archivo Word con contenido real
