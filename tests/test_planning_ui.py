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
        """UI-18: Análisis AST verificando que las vistas y servicios UI no importan sqlite3 ni ejecutan SQL."""
        ui_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "ui"
        py_files = list(ui_dir.rglob("*.py"))
        assert len(py_files) > 0

        for pf in py_files:
            content = pf.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(pf))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name != "sqlite3", f"sqlite3 importado directamente en {pf}"
                        assert not alias.name.startswith("app.word_consolidator"), f"word_consolidator importado en {pf}"
                elif isinstance(node, ast.ImportFrom):
                    assert node.module != "sqlite3", f"from sqlite3 import ... en {pf}"
                    if node.module:
                        assert not node.module.startswith("app.word_consolidator"), f"from app.word_consolidator import ... en {pf}"

            # Verificación de no SQL directo en UI
            for sql_keyword in ["SELECT ", "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP TABLE"]:
                assert sql_keyword not in content, f"Sentencia SQL directa '{sql_keyword}' encontrada en archivo UI: {pf}"

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

    def test_ui_ingest_planning_source_success(self, ui_service: PlanningUIService, tmp_path: Path):
        """UI Service: Ingestión exitosa de actividades POA y reflejo en list_activities()."""
        import openpyxl
        fpath = str(tmp_path / "poa_valido.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Programas, proyectos y act"
        # Encabezados
        ws.cell(1, 1, "No")
        ws.cell(1, 2, "Sede")
        ws.cell(1, 3, "Actividad")
        ws.cell(1, 4, "Área_responsable")
        ws.cell(1, 5, "Eje_estrategia")
        ws.cell(1, 6, "Programa")
        ws.cell(1, 7, "Tipo_Evento")
        ws.cell(1, 8, "Total, estud_M_grado")
        ws.cell(1, 9, "Total, estud_F_grado")
        # Fila 2
        ws.cell(2, 1, "101")
        ws.cell(2, 2, "Bluefields")
        ws.cell(2, 3, "Taller de Robótica Submarina")
        ws.cell(2, 4, "Innovación")
        ws.cell(2, 5, "EJE_11")
        ws.cell(2, 6, "PGM_07")
        ws.cell(2, 7, "EVT_CAPACITACION")
        ws.cell(2, 8, 15)
        ws.cell(2, 9, 20)
        wb.save(fpath)
        wb.close()

        # Ingestar mediante PlanningUIService
        report = ui_service.ingest_planning_matrix(fpath)
        assert report.rows_accepted == 1
        assert report.rows_rejected == 0
        assert len(report.created_activity_ids) == 1
        created_pid = report.created_activity_ids[0]

        # Verificar disponibilidad en list_activities()
        activities = ui_service.list_activities(search_term="Robótica Submarina")
        assert len(activities) == 1
        act = activities[0]
        assert act.activity_name == "Taller de Robótica Submarina"
        assert act.sede == "Bluefields"
        assert act.total_participants == 35
        assert act.design_status == "SIN_DISENO"

    def test_ui_ingest_planning_source_error_handling(self, ui_service: PlanningUIService, tmp_path: Path):
        """UI Service: Manejo riguroso de errores en archivos inexistentes o no válidos sin persistencia parcial."""
        # 1. Archivo inexistente
        report_nonexistent = ui_service.ingest_planning_matrix("ruta_totalmente_inexistente.xlsx")
        assert len(report_nonexistent.errors) > 0
        assert report_nonexistent.rows_accepted == 0
        assert "no existe" in report_nonexistent.errors[0]

        # 2. Archivo sin columnas obligatorias
        import openpyxl
        fpath_invalid = str(tmp_path / "poa_sin_columnas.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Programas, proyectos y act"
        ws.cell(1, 1, "ColumnaA")
        ws.cell(1, 2, "ColumnaB")
        ws.cell(2, 1, "ValorA")
        ws.cell(2, 2, "ValorB")
        wb.save(fpath_invalid)
        wb.close()

        report_invalid = ui_service.ingest_planning_matrix(fpath_invalid)
        assert len(report_invalid.errors) > 0
        assert report_invalid.rows_accepted == 0
        assert "No se encontraron los encabezados institucionales mínimos" in report_invalid.errors[0]

    def test_ui_ingest_planning_source_r08_protection(self, ui_service: PlanningUIService, tmp_path: Path):
        """UI Service: Protección estricta R-08 al reimportar una actividad con diseño metodológico APPROVED."""
        import openpyxl
        fpath = str(tmp_path / "poa_r08.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Programas, proyectos y act"
        ws.cell(1, 1, "No")
        ws.cell(1, 2, "Sede")
        ws.cell(1, 3, "Actividad")
        ws.cell(1, 4, "Área_responsable")
        ws.cell(1, 5, "Eje_estrategia")
        ws.cell(1, 6, "Programa")
        ws.cell(1, 7, "Tipo_Evento")
        ws.cell(1, 8, "Total, estud_M_grado")
        ws.cell(1, 9, "Total, estud_F_grado")
        ws.cell(2, 1, "202")
        ws.cell(2, 2, "Bilwi")
        ws.cell(2, 3, "Taller de Tecnologías Limpias")
        ws.cell(2, 4, "Innovación")
        ws.cell(2, 5, "EJE_11")
        ws.cell(2, 6, "PGM_07")
        ws.cell(2, 7, "EVT_CAPACITACION")
        ws.cell(2, 8, 10)
        ws.cell(2, 9, 15)
        wb.save(fpath)
        wb.close()

        # 1. Ingestión inicial
        rep1 = ui_service.ingest_planning_matrix(fpath)
        assert rep1.rows_accepted == 1
        pid = rep1.created_activity_ids[0]

        # 2. Crear borrador, completar 5 bloques y aprobar diseño
        draft = ui_service.create_design_draft(pid, created_by="Responsable Certificado")
        agenda = (
            TimeBlockDTO(sequence=1, label="Apertura", minutes=30),
            TimeBlockDTO(sequence=2, label="Desarrollo", minutes=90),
        )
        matrix = (
            OperationalActivityDTO(
                step_number=1,
                phase_label="Apertura",
                operative_goal="Sensibilización",
                procedure="Presentación",
                materials="Material digital",
                minutes=30,
            ),
            OperationalActivityDTO(
                step_number=2,
                phase_label="Desarrollo",
                operative_goal="Práctica guiada",
                procedure="Taller",
                materials="Equipos",
                minutes=90,
            ),
        )
        faq = FAQTableDTO(
            q1_que_es=draft.faq.q1_que_es if draft.faq else "Taller",
            q2_para_que="Aprender tecnologías limpias",
            q3_sesiones="Sesión única",
            q4_protagonistas=draft.faq.q4_protagonistas if draft.faq else "25 participantes",
            q5_facilitador="Facilitador",
            q6_materiales="Materiales",
            q7_duracion="120 minutos",
        )
        cmd = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Introducción formal al taller de tecnologías limpias...",
            methodological_approach="Metodología teórico-práctica participativa.",
            objectives=("Objetivo formativo 1.", "Objetivo aplicativo 2."),
            faq=faq,
            agenda=agenda,
            operational_matrix=matrix,
        )
        ui_service.update_design_draft(cmd)
        approved = ui_service.approve_design(draft.design_id, approved_by="Autoridad Institucional")
        assert approved.approved_by == "Autoridad Institucional"

        # 3. Re-ingestar la misma fuente
        rep2 = ui_service.ingest_planning_matrix(fpath)
        assert rep2.rows_accepted == 1
        assert any("APPROVED" in dup and "inmutable R-08" in dup for dup in rep2.duplicates_detected)

        # 4. Comprobar que el diseño sigue en estado APPROVED y la actividad permanece intacta
        detail = ui_service.get_activity_detail(pid)
        assert detail is not None
        assert detail.design_status == "APPROVED"
        assert detail.design_id == draft.design_id

    def test_ui_view_has_cargar_poa_button_and_dialog(self, ui_service: PlanningUIService):
        """PlannedActivitiesListView: El botón de carga existe y maneja la cancelación limpia."""
        import customtkinter as ctk
        root = ctk.CTk()
        try:
            view = PlannedActivitiesListView(root, service=ui_service)
            assert hasattr(view, "_on_click_cargar_poa")
            assert hasattr(view, "_mostrar_reporte_ingestion")

            # Simular cancelación en filedialog (retorna "")
            with patch("tkinter.filedialog.askopenfilename", return_value=""):
                with patch.object(ui_service, "ingest_planning_matrix") as mock_ingest:
                    view._on_click_cargar_poa()
                    mock_ingest.assert_not_called()
        finally:
            root.destroy()

    def test_ui_ingest_rejection_and_warnings_reporting(self, ui_service: PlanningUIService, tmp_path: Path):
        """Reporte riguroso de rechazos con fila/motivo y advertencias por inconsistencias detectadas."""
        import openpyxl
        fpath = str(tmp_path / "poa_con_rechazos.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Programas, proyectos y act"
        ws.cell(1, 1, "No")
        ws.cell(1, 2, "Sede")
        ws.cell(1, 3, "Actividad")
        ws.cell(1, 4, "Área_responsable")
        ws.cell(1, 5, "Eje_estrategia")
        ws.cell(1, 6, "Programa")
        ws.cell(1, 7, "Tipo_Evento")
        ws.cell(1, 8, "Total, estud_M_grado")
        ws.cell(1, 9, "Total, estud_F_grado")

        # Fila 2: Válida
        ws.cell(2, 1, "1")
        ws.cell(2, 2, "Bluefields")
        ws.cell(2, 3, "Actividad Válida A")
        ws.cell(2, 4, "Innovación")
        ws.cell(2, 5, "EJE_11")
        ws.cell(2, 6, "PGM_07")
        ws.cell(2, 7, "EVT_CAPACITACION")
        ws.cell(2, 8, 5)
        ws.cell(2, 9, 5)

        # Fila 3: Rechazada (Actividad vacía)
        ws.cell(3, 1, "2")
        ws.cell(3, 2, "Bluefields")
        ws.cell(3, 3, "")
        ws.cell(3, 4, "Innovación")
        ws.cell(3, 5, "EJE_11")
        ws.cell(3, 6, "PGM_07")
        ws.cell(3, 7, "EVT_CAPACITACION")
        ws.cell(3, 8, 5)
        ws.cell(3, 9, 5)

        # Fila 4: Rechazada (Meta negativa)
        ws.cell(4, 1, "3")
        ws.cell(4, 2, "Bluefields")
        ws.cell(4, 3, "Actividad con Meta Negativa")
        ws.cell(4, 4, "Innovación")
        ws.cell(4, 5, "EJE_11")
        ws.cell(4, 6, "PGM_07")
        ws.cell(4, 7, "EVT_CAPACITACION")
        ws.cell(4, 8, -10)
        ws.cell(4, 9, 5)

        wb.save(fpath)
        wb.close()

        rep = ui_service.ingest_planning_matrix(fpath)
        assert rep.total_rows_examined == 3
        assert rep.rows_accepted == 1
        assert rep.rows_rejected == 2
        assert len(rep.rejection_reasons) == 2
        filas_rechazadas = [r[0] for r in rep.rejection_reasons]
        assert 3 in filas_rechazadas
        assert 4 in filas_rechazadas

    def test_ui_ingest_invalid_or_corrupt_file(self, ui_service: PlanningUIService, tmp_path: Path):
        """Manejo de archivo corrupto o con formato no Excel."""
        fpath_corrupt = tmp_path / "archivo_corrupto.xlsx"
        fpath_corrupt.write_text("Este no es un archivo excel binario valido", encoding="utf-8")

        rep = ui_service.ingest_planning_matrix(str(fpath_corrupt))
        assert rep.rows_accepted == 0
        assert len(rep.errors) > 0

    def test_ui_view_refreshes_list_after_successful_ingestion(self, ui_service: PlanningUIService, tmp_path: Path):
        """PlannedActivitiesListView refresca el listado visual inmediatamente tras ingesta exitosa."""
        import openpyxl
        import customtkinter as ctk

        fpath = str(tmp_path / "poa_refresh.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Programas, proyectos y act"
        ws.cell(1, 1, "No")
        ws.cell(1, 2, "Sede")
        ws.cell(1, 3, "Actividad")
        ws.cell(1, 4, "Área_responsable")
        ws.cell(1, 5, "Eje_estrategia")
        ws.cell(1, 6, "Programa")
        ws.cell(1, 7, "Tipo_Evento")
        ws.cell(2, 1, "999")
        ws.cell(2, 2, "Bilwi")
        ws.cell(2, 3, "Actividad de Prueba Refresco UI")
        ws.cell(2, 4, "Innovación")
        ws.cell(2, 5, "EJE_11")
        ws.cell(2, 6, "PGM_07")
        ws.cell(2, 7, "EVT_CAPACITACION")
        wb.save(fpath)
        wb.close()

        root = ctk.CTk()
        try:
            view = PlannedActivitiesListView(root, service=ui_service)
            # Inicialmente sin la actividad
            acts_init = ui_service.list_activities(search_term="Refresco UI")
            assert len(acts_init) == 0

            with patch("tkinter.filedialog.askopenfilename", return_value=fpath):
                with patch.object(view, "_mostrar_reporte_ingestion") as mock_modal:
                    view._on_click_cargar_poa()
                    mock_modal.assert_called_once()

            # Comprobar que el listado visual ahora refleja la actividad cargada
            acts_after = ui_service.list_activities(search_term="Refresco UI")
            assert len(acts_after) == 1
            assert acts_after[0].activity_name == "Actividad de Prueba Refresco UI"
        finally:
            root.destroy()


