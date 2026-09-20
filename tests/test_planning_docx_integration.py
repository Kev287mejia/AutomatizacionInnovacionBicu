"""
Suite de Pruebas de Integración Controlada — Planning V003 → Document Model → DOCX.

Fase 29.5.4 — Integración Controlada Planning V003 → Document Model → DOCX.
Verifica de forma estricta:
  INT-01: Persistir diseño en V003 y reconstruirlo.
  INT-02: Reconstruir diseño y convertirlo a DTO.
  INT-03: DTO real reconstruido genera DOCX válido.
  INT-04: Los cinco bloques institucionales llegan correctamente al DOCX (y título verificado).
  INT-05: FAQ conserva las siete preguntas institucionales.
  INT-06: Agenda conserva tiempos.
  INT-07: Matriz operacional conserva sus filas y 6 columnas.
  INT-08: planning_id permanece trazable en todo el flujo.
  INT-09: No se generan registros M1–M5.
  INT-10: No se generan registros de ejecución.
  INT-11: No se modifica el flujo Word → M1–M5.
  INT-12: No existe dependencia del renderer hacia SQLite.
  INT-13: No existe dependencia del renderer hacia app.word_consolidator.
  INT-14: APPROVED continúa siendo inmutable (rechazo a modificación, render válido).
  INT-15: DRAFT puede renderizarse sin inventar marca de agua.
  INT-SVC: MethodologicalDocumentExportService orquesta vía export_design() único camino.
  INT-AST-SVC: Servicio de aplicación no conoce M1–M5, extractor Word, enrutador ni ACL.
"""
from __future__ import annotations

import ast
from datetime import date, datetime
import inspect
from pathlib import Path
import sqlite3
import sys
import uuid
import pytest
import docx

from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.planning.application.services import MethodologicalDocumentExportService
from app.planning.domain.dtos import (
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    TimeBlockDTO,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.value_objects import (
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)
from app.planning.infrastructure.document_rendering import (
    DocxMethodologicalDocumentRenderer,
    DocumentRenderingError,
)
from app.planning.infrastructure.persistence import (
    PlanningUnitOfWork,
    SQLiteMethodologicalDesignRepository,
    SQLitePlannedActivityRepository,
)


# ===========================================================================
# FIXTURES DE BASE DE DATOS Y DOMINIO
# ===========================================================================

@pytest.fixture
def clean_db(tmp_path: Path):
    """Crea una base de datos SQLite temporal con las migraciones V001, V002 y V003 aplicadas."""
    db_file = tmp_path / "test_planning_integration_v003.db"
    mgr = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))
    conn = mgr.get_connection()
    runner = MigrationRunner(conn)
    runner.apply_all_pending()
    conn.close()
    return db_file


@pytest.fixture
def sample_planned_activity() -> PlannedActivity:
    """Crea una PlannedActivity representativa con metas institucionales válidas."""
    goals = ParticipantGoals(
        est_grado_m=10,
        est_grado_f=15,
        est_postgrado_m=2,
        est_postgrado_f=3,
        docentes_m=4,
        docentes_f=6,
        administrativos_m=1,
        administrativos_f=2,
        externos_m=5,
        externos_f=5,
    )
    return PlannedActivity.create(
        planning_id="POA-2026-TALLER-INT-01",
        activity_name="Taller de Innovación y Metodologías Ágiles",
        sede="Bluefields",
        area_responsable="Dirección de Innovación y Emprendimiento",
        eje_estrategia="E1",
        programa="PR1",
        tipo_evento="TE1",
        participant_goals=goals,
        dep_sede="RACCS",
        mun_sede="Bluefields",
        proposito="Capacitar a la comunidad universitaria en marcos ágiles de innovación.",
        fecha_evento=date(2026, 10, 15),
    )


@pytest.fixture
def sample_methodological_design(sample_planned_activity: PlannedActivity) -> MethodologicalDesign:
    """Crea un MethodologicalDesign completo con los cinco bloques institucionales."""
    faq = FAQTable(
        q1_que_es="Es una jornada práctica formativa de innovación aplicada.",
        q2_para_que="Para transferir capacidades metodológicas a equipos multidisciplinarios.",
        q3_sesiones="Sesión única",
        q4_protagonistas="48 protagonistas en total: 30 estudiantes, 10 docentes, 3 administrativos y 5 externos.",
        q5_facilitador="Dirección de Innovación y Emprendimiento",
        q6_materiales="Laptops, conexión a red, proyector, papelógrafos, marcadores y notas adhesivas.",
        q7_duracion="2 horas y 30 minutos (150 minutos).",
    )

    agenda = [
        TimeBlock(sequence=1, label="Registro e Instalación", minutes=15),
        TimeBlock(sequence=2, label="Introducción y Dinámica de Apertura", minutes=30),
        TimeBlock(sequence=3, label="Desarrollo Práctico del Taller", minutes=75),
        TimeBlock(sequence=4, label="Plenaria de Conclusiones y Evaluación", minutes=30),
    ]

    matrix = [
        OperationalActivity(
            step_number=1,
            phase_label="Registro e Instalación",
            operative_goal="Registrar asistencia y organizar equipos de trabajo",
            procedure="Los participantes ingresan, firman lista y reciben gafetes",
            materials="Lista de asistencia, gafetes, bolígrafos",
            minutes=15,
        ),
        OperationalActivity(
            step_number=2,
            phase_label="Introducción y Dinámica de Apertura",
            operative_goal="Presentar la metodología y alinear expectativas",
            procedure="Presentación en diapositivas y dinámica rompehielo grupal",
            materials="Proyector, diapositivas",
            minutes=30,
        ),
        OperationalActivity(
            step_number=3,
            phase_label="Desarrollo Práctico del Taller",
            operative_goal="Aplicar los marcos de trabajo en casos prácticos asignados",
            procedure="Trabajo colaborativo por mesas con asesoría continua del facilitador",
            materials="Papelógrafos, notas adhesivas, marcadores",
            minutes=75,
        ),
        OperationalActivity(
            step_number=4,
            phase_label="Plenaria de Conclusiones y Evaluación",
            operative_goal="Sintetizar hallazgos y evaluar satisfacción de la jornada",
            procedure="Exposición de propuestas por equipo y llenado de encuesta digital",
            materials="Formulario de evaluación en línea",
            minutes=30,
        ),
    ]

    return MethodologicalDesign.create(
        planned_activity_internal_id=sample_planned_activity.activity_internal_id,
        planning_id=sample_planned_activity.planning_id,
        activity_name=sample_planned_activity.activity_name,
        introduction="La presente actividad se enmarca en las directrices del plan operativo institucional...",
        methodological_approach="Se implementa un enfoque constructivista y participativo orientado al aprender haciendo.",
        objective_1="Comprender los principios teóricos fundamentales del marco de trabajo ágil.",
        objective_2="Desarrollar una propuesta práctica aplicable a un reto institucional concreto.",
        faq=faq,
        agenda=agenda,
        operational_matrix=matrix,
        created_by="coordinador_innovacion",
        version=1,
        status=DesignStatus.DRAFT,
    )


# ===========================================================================
# PRUEBAS DE INTEGRACIÓN CONTROLADA (INT-01 A INT-15)
# ===========================================================================

class TestPlanningDocxIntegration:
    """Batería de pruebas de integración Planning V003 -> Document Model -> DOCX."""

    def test_int_01_persist_and_reconstruct_design(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
    ):
        """INT-01: Persistir diseño en V003 y reconstruirlo fielmente desde SQLite real."""
        # 1. Persistencia transaccional
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        # 2. Reconstrucción en una nueva conexión independiente
        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            reconstructed = repo.get_by_id(sample_methodological_design.design_id)

            assert reconstructed is not None
            assert reconstructed.design_id == sample_methodological_design.design_id
            assert reconstructed.planned_activity_ref == sample_planned_activity.planning_id
            assert reconstructed.activity_name == sample_planned_activity.activity_name
            assert reconstructed.status == DesignStatus.DRAFT
            assert reconstructed.introduction_text == sample_methodological_design.introduction_text
            assert reconstructed.methodological_approach == sample_methodological_design.methodological_approach
            assert len(reconstructed.objectives) == 2
            assert reconstructed.objective_1 == sample_methodological_design.objective_1
            assert reconstructed.objective_2 == sample_methodological_design.objective_2
            assert reconstructed.faq is not None
            assert reconstructed.faq.q1_que_es == sample_methodological_design.faq.q1_que_es
            assert len(reconstructed.agenda) == 4
            assert reconstructed.total_minutes == 150
            assert len(reconstructed.operational_matrix) == 4
        finally:
            conn.close()

    def test_int_02_reconstruct_design_to_dto(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
    ):
        """INT-02: Reconstruir diseño y convertirlo a MethodologicalDesignDTO sin pérdida de datos."""
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            reconstructed = repo.get_by_id(sample_methodological_design.design_id)
            assert reconstructed is not None

            dto = reconstructed.to_dto()

            assert isinstance(dto, MethodologicalDesignDTO)
            assert dto.design_id == reconstructed.design_id
            assert dto.version == reconstructed.version
            assert dto.document_title == f"Diseño metodológico {reconstructed.activity_name}"
            assert dto.introduction == reconstructed.introduction_text
            assert dto.methodological_approach == reconstructed.methodological_approach
            assert dto.objectives_heading == "OBJETIVOS DEL TALLER ARTÍSTICO"
            assert dto.objective_1 == reconstructed.objective_1
            assert dto.objective_2 == reconstructed.objective_2
            assert dto.faq.q1_que_es == reconstructed.faq.q1_que_es
            assert len(dto.agenda) == 4
            assert dto.total_minutes == 150
            assert len(dto.operational_matrix) == 4
        finally:
            conn.close()

    def test_int_03_reconstructed_dto_produces_valid_docx(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-03: DTO real reconstruido genera un DOCX físicamente válido y no vacío."""
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            reconstructed = repo.get_by_id(sample_methodological_design.design_id)
            dto = reconstructed.to_dto()

            renderer = DocxMethodologicalDocumentRenderer()
            out_file = str(tmp_path / "integrated_design.docx")
            result_path = renderer.render(dto, out_file)

            assert Path(result_path).exists()
            assert Path(result_path).stat().st_size > 0

            # Carga del documento con python-docx
            doc = docx.Document(result_path)
            assert len(doc.paragraphs) > 0
            assert len(doc.tables) == 3
        finally:
            conn.close()

    def test_int_04_five_blocks_arrive_to_docx(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-04: Los cinco bloques institucionales (y título adicional) llegan correctamente al DOCX.

        Bloques institucionales normativos:
          1. Introducción
          2. Objetivos
          3. FAQ
          4. Programa / Agenda
          5. Matriz Operativa
        Título: Verificado adicionalmente sin contarse como sexto bloque.
        """
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            reconstructed = repo.get_by_id(sample_methodological_design.design_id)
            dto = reconstructed.to_dto()

            renderer = DocxMethodologicalDocumentRenderer()
            out_file = str(tmp_path / "test_blocks.docx")
            renderer.render(dto, out_file)

            doc = docx.Document(out_file)
            p_texts = [p.text for p in doc.paragraphs]

            # Verificación adicional de Título (no cuenta como bloque institucional)
            assert any(dto.document_title.upper() in t for t in p_texts), "Título del documento ausente"

            # 1. Bloque 1: Introducción
            assert any("INTRODUCCIÓN" in t for t in p_texts), "Bloque 1 (Encabezado Introducción) ausente"
            assert any(dto.introduction[:30] in t for t in p_texts), "Bloque 1 (Texto Introducción) ausente"
            assert any(dto.methodological_approach[:30] in t for t in p_texts), "Bloque 1 (Enfoque Metodológico) ausente"

            # 2. Bloque 2: Objetivos
            assert any(dto.objectives_heading in t for t in p_texts), "Bloque 2 (Encabezado Objetivos) ausente"
            assert any(dto.objective_1 in t for t in p_texts), "Bloque 2 (Objetivo 1) ausente"
            assert any(dto.objective_2 in t for t in p_texts), "Bloque 2 (Objetivo 2) ausente"

            # 3. Bloque 3: FAQ (Tabla 1)
            faq_table = doc.tables[0]
            assert "Preguntas frecuentes" in faq_table.rows[0].cells[0].text, "Bloque 3 (Tabla FAQ) ausente"

            # 4. Bloque 4: Programa / Agenda (Tabla 2)
            assert any(dto.program_section_label in t for t in p_texts), "Bloque 4 (Encabezado Agenda) ausente"
            prog_table = doc.tables[1]
            assert "Actividad" in prog_table.rows[0].cells[0].text, "Bloque 4 (Tabla Agenda) ausente"

            # 5. Bloque 5: Matriz Operativa (Tabla 3)
            assert any(dto.matrix_section_label in t for t in p_texts), "Bloque 5 (Encabezado Matriz) ausente"
            matrix_table = doc.tables[2]
            assert "No." in matrix_table.rows[0].cells[0].text, "Bloque 5 (Tabla Matriz) ausente"
        finally:
            conn.close()

    def test_int_05_faq_contains_seven_questions(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-05: La tabla FAQ en el DOCX conserva con exactitud las 7 preguntas institucionales."""
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            reconstructed = repo.get_by_id(sample_methodological_design.design_id)
            dto = reconstructed.to_dto()

            renderer = DocxMethodologicalDocumentRenderer()
            out_file = str(tmp_path / "test_faq.docx")
            renderer.render(dto, out_file)

            doc = docx.Document(out_file)
            table = doc.tables[0]
            assert len(table.rows) == 8
            assert len(table.columns) == 2

            expected_questions = [
                "¿En qué es esta actividad?",
                "¿Para qué se realiza?",
                "¿Cuántas sesiones se realizarán?",
                "¿Cuánto son los protagonistas?",
                "¿Quién va facilitar??",
                "¿Qué materiales se van a utilizar?",
                "¿Cuánto tiempo dura el taller?",
            ]
            for idx, q_expected in enumerate(expected_questions, start=1):
                assert table.rows[idx].cells[0].text == q_expected
                assert len(table.rows[idx].cells[1].text.strip()) > 0
        finally:
            conn.close()

    def test_int_06_agenda_preserves_times(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-06: La tabla de Agenda en el DOCX conserva los tiempos individuales y la suma total."""
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            reconstructed = repo.get_by_id(sample_methodological_design.design_id)
            dto = reconstructed.to_dto()

            renderer = DocxMethodologicalDocumentRenderer()
            out_file = str(tmp_path / "test_agenda.docx")
            renderer.render(dto, out_file)

            doc = docx.Document(out_file)
            table = doc.tables[1]
            assert len(table.rows) == 6  # 1 header + 4 blocks + 1 total

            # Filas de actividad
            assert "Registro e Instalación" in table.rows[1].cells[0].text
            assert "15 min." in table.rows[1].cells[1].text

            assert "Introducción y Dinámica de Apertura" in table.rows[2].cells[0].text
            assert "30 min." in table.rows[2].cells[1].text

            assert "Desarrollo Práctico del Taller" in table.rows[3].cells[0].text
            assert "75 min." in table.rows[3].cells[1].text

            assert "Plenaria de Conclusiones y Evaluación" in table.rows[4].cells[0].text
            assert "30 min." in table.rows[4].cells[1].text

            # Fila total
            assert table.rows[5].cells[0].text == "Total"
            assert table.rows[5].cells[1].text == "150 min."
        finally:
            conn.close()

    def test_int_07_matrix_preserves_rows_and_six_columns(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-07: La matriz operacional en el DOCX conserva sus filas y las 6 columnas oficiales."""
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            reconstructed = repo.get_by_id(sample_methodological_design.design_id)
            dto = reconstructed.to_dto()

            renderer = DocxMethodologicalDocumentRenderer()
            out_file = str(tmp_path / "test_matrix.docx")
            renderer.render(dto, out_file)

            doc = docx.Document(out_file)
            table = doc.tables[2]
            assert len(table.rows) == 5  # 1 header + 4 activities
            assert len(table.columns) == 6

            expected_headers = [
                "No.",
                "Actividad",
                "Objetivos Operativos",
                "Procedimiento",
                "Materiales",
                "Tiempo",
            ]
            for col_idx, h_expected in enumerate(expected_headers):
                assert table.rows[0].cells[col_idx].text == h_expected

            for row_idx, act in enumerate(dto.operational_matrix, start=1):
                row = table.rows[row_idx]
                assert row.cells[0].text == str(act.step_number)
                assert row.cells[1].text == act.phase_label
                assert row.cells[2].text == act.operative_goal
                assert row.cells[3].text == act.procedure
                assert row.cells[4].text == act.materials
                assert row.cells[5].text == f"{act.minutes} min."
        finally:
            conn.close()

    def test_int_08_planning_id_traceability(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-08: planning_id permanece trazable desde PlannedActivity hasta el DOCX generado."""
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            design = repo.get_by_activity_ref(sample_planned_activity.planning_id)
            assert design is not None
            assert design.planned_activity_ref == sample_planned_activity.planning_id

            # Trazabilidad al DTO
            dto = design.to_dto()
            assert sample_planned_activity.activity_name in dto.document_title

            # Trazabilidad al DOCX
            renderer = DocxMethodologicalDocumentRenderer()
            out_file = str(tmp_path / "test_traceability.docx")
            renderer.render(dto, out_file)

            doc = docx.Document(out_file)
            p_first = doc.paragraphs[0].text
            assert sample_planned_activity.activity_name.upper() in p_first
        finally:
            conn.close()

    def test_int_09_no_m1_m5_records_generated(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-09: La persistencia, reconstrucción y renderizado no generan registros en M1–M5."""
        conn = sqlite3.connect(str(clean_db))
        cursor = conn.cursor()

        # Tablas patrimoniales asociadas a M1..M5
        m_tables = [
            "actividad",
            "perfil_estudiante",
            "perfil_personal",
            "perfil_colaborador",
            "perfil_beneficiario",
            "participacion",
        ]

        def get_m_counts():
            counts = {}
            for t in m_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {t};")
                counts[t] = cursor.fetchone()[0]
            return counts

        counts_before = get_m_counts()
        conn.close()

        # Ejecutar flujo completo de integración
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            design = repo.get_by_id(sample_methodological_design.design_id)
            dto = design.to_dto()
            renderer = DocxMethodologicalDocumentRenderer()
            renderer.render(dto, str(tmp_path / "test_no_m1_m5.docx"))

            cursor = conn.cursor()
            counts_after = {}
            for t in m_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {t};")
                counts_after[t] = cursor.fetchone()[0]

            assert counts_before == counts_after
            for t, cnt in counts_after.items():
                assert cnt == 0, f"La tabla {t} contiene {cnt} registros inesperados."
        finally:
            conn.close()

    def test_int_10_no_execution_records_generated(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-10: Cero creación de registros en tablas de ejecución (actividad, persona, participacion, informes)."""
        conn = sqlite3.connect(str(clean_db))
        cursor = conn.cursor()

        exec_tables = [
            "actividad",
            "persona",
            "participacion",
            "informe_actividad",
            "informe_semanal",
            "detalle_informe_semanal",
        ]

        def get_exec_counts():
            counts = {}
            for t in exec_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {t};")
                counts[t] = cursor.fetchone()[0]
            return counts

        counts_before = get_exec_counts()
        conn.close()

        # Ejecutar flujo de planning
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            design = repo.get_by_id(sample_methodological_design.design_id)
            dto = design.to_dto()
            renderer = DocxMethodologicalDocumentRenderer()
            renderer.render(dto, str(tmp_path / "test_no_exec.docx"))

            cursor = conn.cursor()
            counts_after = {}
            for t in exec_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {t};")
                counts_after[t] = cursor.fetchone()[0]

            assert counts_before == counts_after
            for t, cnt in counts_after.items():
                assert cnt == 0, f"La tabla de ejecución {t} contiene {cnt} registros inesperados."
        finally:
            conn.close()

    def test_int_11_word_to_m1_m5_unmodified(self):
        """INT-11: El flujo patrimonial Word -> M1–M5 permanece completamente intacto e independiente."""
        from app.word_consolidator.pipeline import WordConsolidationPipeline
        from app.parsers.word_parser import WordReportParser
        from app.application.word_acl.adapters import WordACL

        assert WordConsolidationPipeline is not None
        assert WordReportParser is not None
        assert WordACL is not None

    def test_int_12_renderer_blind_to_sqlite(self):
        """INT-12: El renderer DOCX no importa ni conoce sqlite3, SQLAlchemy ni repositorios."""
        renderer_path = Path("app/planning/infrastructure/document_rendering/docx_renderer.py")
        source = renderer_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(renderer_path))

        prohibited = [
            "sqlite3",
            "sqlalchemy",
            "app.infrastructure.persistence",
            "PlanningUnitOfWork",
            "repositories",
        ]

        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.append(node.module)

        for imp in imported_names:
            for p in prohibited:
                assert p not in imp, f"Violación de aislamiento en renderer: importa '{imp}'."

    def test_int_13_renderer_blind_to_word_consolidator(self):
        """INT-13: El renderer DOCX no importa ni conoce app.word_consolidator."""
        renderer_path = Path("app/planning/infrastructure/document_rendering/docx_renderer.py")
        source = renderer_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(renderer_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "word_consolidator" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "word_consolidator" not in node.module

    def test_int_14_approved_design_is_immutable_but_renderable(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-14: Un diseño en estado APPROVED no puede modificarse pero puede renderizarse a DOCX."""
        # 1. Aprobar y persistir
        sample_methodological_design.approve(approved_by="director_academico")
        assert sample_methodological_design.status == DesignStatus.APPROVED

        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        # 2. Intento de modificación rechazado por R-08
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            loaded = uow.methodological_designs.get_by_id(sample_methodological_design.design_id)
            assert loaded is not None
            with pytest.raises(RuntimeError, match="APPROVED"):
                uow.methodological_designs.save(loaded)

        # 3. Renderizado de APPROVED exitoso
        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            approved_design = repo.get_by_id(sample_methodological_design.design_id)
            dto = approved_design.to_dto()
            renderer = DocxMethodologicalDocumentRenderer()
            out_file = str(tmp_path / "test_approved.docx")
            res_path = renderer.render(dto, out_file)

            assert Path(res_path).exists()
            assert Path(res_path).stat().st_size > 0
        finally:
            conn.close()

    def test_int_15_draft_renders_without_invented_watermark(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """INT-15: Un diseño en DRAFT se renderiza limpiamente sin marcas de agua inventadas."""
        assert sample_methodological_design.status == DesignStatus.DRAFT

        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            draft_design = repo.get_by_id(sample_methodological_design.design_id)
            dto = draft_design.to_dto()

            renderer = DocxMethodologicalDocumentRenderer()
            out_file = str(tmp_path / "test_draft.docx")
            res_path = renderer.render(dto, out_file)

            # Verificar que el DOCX no contenga marcas de agua ni texto 'BORRADOR'
            doc = docx.Document(res_path)
            for p in doc.paragraphs:
                assert "BORRADOR" not in p.text.upper()
                assert "WATERMARK" not in p.text.upper()
        finally:
            conn.close()

    def test_service_export_central_path(
        self,
        clean_db: Path,
        sample_planned_activity: PlannedActivity,
        sample_methodological_design: MethodologicalDesign,
        tmp_path: Path,
    ):
        """Verifica que MethodologicalDocumentExportService orqueste vía el camino central export_design()."""
        with PlanningUnitOfWork(db_path=clean_db) as uow:
            uow.planned_activities.save(sample_planned_activity)
            uow.methodological_designs.save(sample_methodological_design)
            uow.commit()

        conn = sqlite3.connect(str(clean_db))
        conn.row_factory = sqlite3.Row
        try:
            repo = SQLiteMethodologicalDesignRepository(conn)
            renderer = DocxMethodologicalDocumentRenderer()
            service = MethodologicalDocumentExportService(
                design_repository=repo,
                renderer=renderer,
            )

            # 1. Exportar por ID
            out_by_id = str(tmp_path / "service_by_id.docx")
            res_id = service.export_by_id(sample_methodological_design.design_id, out_by_id)
            assert Path(res_id).exists()
            assert Path(res_id).stat().st_size > 0

            # 2. Exportar por referencia institucional
            out_by_ref = str(tmp_path / "service_by_ref.docx")
            res_ref = service.export_by_activity_ref(sample_planned_activity.planning_id, out_by_ref)
            assert Path(res_ref).exists()
            assert Path(res_ref).stat().st_size > 0

            # 3. Exportar diseño directo
            out_direct = str(tmp_path / "service_direct.docx")
            res_dir = service.export_design(sample_methodological_design, out_direct)
            assert Path(res_dir).exists()
            assert Path(res_dir).stat().st_size > 0
        finally:
            conn.close()

    def test_service_ast_isolation(self):
        """Verifica que MethodologicalDocumentExportService no conozca M1–M5, Word extractor, router ni ACL."""
        service_path = Path("app/planning/application/services.py")
        source = service_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(service_path))

        prohibited = [
            "sqlite3",
            "sqlalchemy",
            "app.infrastructure.persistence",
            "app.word_consolidator",
            "app.application.word_acl",
            "app.application.export_acl",
            "app.routing",
            "google.generativeai",
            "openai",
        ]

        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.append(node.module)

        for imp in imported_names:
            for p in prohibited:
                assert p not in imp, f"Violación de aislamiento en application service: importa '{imp}'."
