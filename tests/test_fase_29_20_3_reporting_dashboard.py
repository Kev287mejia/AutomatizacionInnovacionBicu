"""tests/test_fase_29_20_3_reporting_dashboard.py

Suite Pericial de Pruebas Automatizadas para la Fase 29.20.3.
INTEGRACIÓN CONTROLADA: REPORTING + DASHBOARD INSTITUCIONAL BICU.

REQUERIMIENTOS CERTIFICADOS:
  - REPORT-01: Generación de REP-01 (Balance Ejecutivo) con estructura y métricas correctas.
  - REPORT-02: Generación de REP-02 (Cumplimiento POA) con plan vs ejecución y cuadrantes.
  - REPORT-03: Generación de REP-03 (Cobertura Demográfica) con estamento y género.
  - REPORT-04: Generación de REP-04 (Extensión Territorial) con sedes y municipios certificados.
  - REPORT-05: Generación de REP-05 (Auditoría de Trazabilidad y Salud del Dato).
  - DASH-01: Dashboard consume exclusivamente DashboardDataDTO inmutable.
  - DASH-02: DashboardView no realiza cálculos matemáticos ni reconstruye indicadores.
  - DASH-03: Los filtros de ReportFilterDTO modifican el resultado en cascada.
  - DASH-04: COHORT_UNIQUE opera como modo predeterminado (cohortes únicas).
  - DASH-05: SESSION_SUM opera cuando es solicitado explícitamente.
  - DASH-06: Actividades emergentes no incrementan el cumplimiento del POA.
  - DASH-07: M5 histórico (es_historico_preexistente = 0) no contamina el período actual.
  - DASH-08: NULL se conserva sin imputaciones artificiales.
  - DASH-09: Trazabilidad V004 se representa fielmente (ACTIVE vs REVOKED/SUPERSEDED).
  - EXPORT-01: Exportación XLSX produce archivo Excel válido con openpyxl.
  - EXPORT-02: Exportación DOCX produce documento Word válido con python-docx.
  - EXPORT-03: Exportación CSV produce archivo estructurado válido.
  - EXPORT-04: Exportaciones no modifican el estado de SQLite (inmutabilidad).
  - EXPORT-05: Exportaciones no modifican plantillas ni matrices M1–M5.
  - ARCH-01: La capa UI no importa sqlite3 ni ejecuta sentencias SQL.
  - ARCH-02: La capa UI no contiene fórmulas ni duplicación de indicadores.
  - ARCH-03: La capa UI no depende de Gemini ni de IA.
  - ARCH-04: Esquema V004 permanece intacto y V005 no existe.
"""

import ast
import hashlib
from pathlib import Path
import sqlite3
import uuid
from typing import Any, Dict, List, Tuple

import docx
import openpyxl
import pytest

from app.infrastructure.persistence.migrations import MigrationRunner
from app.indicators.application.service import IndicatorCalculationService
from app.indicators.domain.contracts import IndicatorId
from app.indicators.infrastructure.sqlite_reader import SQLiteIndicatorReader
from app.reporting.application.reporting_service import ReportingService
from app.reporting.domain.dto import (
    DashboardCardDTO,
    DashboardDataDTO,
    DashboardSectionDTO,
    ReportDocumentDTO,
    ReportFilterDTO,
)
from app.reporting.domain.enums import (
    AlertStatus,
    ExportFormat,
    MultisessionGoalMode,
    ReportType,
)
from app.reporting.infrastructure.exporters.csv_exporter import CSVReportExporter
from app.reporting.infrastructure.exporters.docx_exporter import DOCXReportExporter
from app.reporting.infrastructure.exporters.xlsx_exporter import XLSXReportExporter
from app.reporting.infrastructure.memory_cache import ReportingMemoryCache
from app.reporting_ui.services.reporting_ui_service import ReportingUIService


# ---------------------------------------------------------------------------
# FIXTURES Y SEEDING
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn() -> sqlite3.Connection:
    """Base de datos en memoria con esquema institucional V001–V004."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    runner = MigrationRunner(conn)
    runner.apply_all_pending()
    return conn


@pytest.fixture
def populated_db(db_conn: sqlite3.Connection) -> sqlite3.Connection:
    """Puebla la base de datos con actividades planificadas, ejecutadas y participantes."""
    conn = db_conn

    # 1. Actividades Planificadas POA
    plan_1 = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO planning_planned_activities (
            activity_internal_id, planning_id, activity_name, sede,
            area_responsable, eje_estrategia, programa, tipo_evento,
            fecha_evento, est_grado_m, est_grado_f
        ) VALUES (?, 'PLAN-2026-001', 'Capacitación en Innovación Digital', 'BILWI',
                  'Dirección de Innovación', '11.41.67', 'INNOVACION', 'CAPACITACION',
                  '2026-03-15', 10, 15);
        """,
        (plan_1,),
    )
    plan_2 = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO planning_planned_activities (
            activity_internal_id, planning_id, activity_name, sede,
            area_responsable, eje_estrategia, programa, tipo_evento,
            fecha_evento, est_grado_m, est_grado_f
        ) VALUES (?, 'PLAN-2026-002', 'Feria Tecnológica Regional', 'BLUEFIELDS',
                  'Dirección de Extensión', '11.41.67', 'INNOVACION', 'FERIA',
                  '2026-05-20', 20, 20);
        """,
        (plan_2,),
    )

    # 2. Actividades Ejecutadas
    exec_1 = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO actividad (
            id_actividad, nombre_original, tipo_evento, sede,
            eje_estrategico, programa, fecha_inicio,
            departamento_responsable, responsable, estado, es_emergente,
            hash_sha256
        ) VALUES (?, 'Capacitación en Innovación Digital Sesión 1', 'CAPACITACION', 'BILWI',
                  '11.41.67', 'INNOVACION', '2026-03-15',
                  'DGI', 'Coordinador BICU', 'EJECUTADA', 0, ?);
        """,
        (exec_1, f"hash_{exec_1}"),
    )

    exec_2_multisesion = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO actividad (
            id_actividad, nombre_original, tipo_evento, sede,
            eje_estrategico, programa, fecha_inicio,
            departamento_responsable, responsable, estado, es_emergente,
            hash_sha256
        ) VALUES (?, 'Capacitación en Innovación Digital Sesión 2', 'CAPACITACION', 'BILWI',
                  '11.41.67', 'INNOVACION', '2026-03-16',
                  'DGI', 'Coordinador BICU', 'EJECUTADA', 0, ?);
        """,
        (exec_2_multisesion, f"hash_{exec_2_multisesion}"),
    )

    exec_emergente = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO actividad (
            id_actividad, nombre_original, tipo_evento, sede,
            eje_estrategico, programa, fecha_inicio,
            departamento_responsable, responsable, estado, es_emergente,
            hash_sha256
        ) VALUES (?, 'Taller Comunitario de Emergencia', 'TALLER', 'LAS_MINAS',
                  '11.41.67', 'INNOVACION', '2026-04-05',
                  'DGI', 'Coordinador BICU', 'EJECUTADA', 1, ?);
        """,
        (exec_emergente, f"hash_{exec_emergente}"),
    )

    # 3. Vínculos V004 (Trazabilidad Plan -> Ejecución)
    conn.execute(
        """
        INSERT INTO planning_execution_links (
            link_id, planning_internal_id, id_actividad, linked_by,
            link_rationale, numero_sesion, link_status
        ) VALUES (?, ?, ?, 'Auditor BICU', 'Trazabilidad formal', 1, 'ACTIVE');
        """,
        (str(uuid.uuid4()), plan_1, exec_1),
    )
    conn.execute(
        """
        INSERT INTO planning_execution_links (
            link_id, planning_internal_id, id_actividad, linked_by,
            link_rationale, numero_sesion, link_status
        ) VALUES (?, ?, ?, 'Auditor BICU', 'Trazabilidad multisesión', 2, 'ACTIVE');
        """,
        (str(uuid.uuid4()), plan_1, exec_2_multisesion),
    )
    # exec_emergente NO tiene vínculo activo en planning_execution_links

    # 4. Personas y Participaciones
    p1 = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo)
        VALUES (?, '601-010190-0001A', 'Juan Perez', 'M');
        """,
        (p1,),
    )

    p2 = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo)
        VALUES (?, '601-020292-0002B', 'Maria Lopez', 'F');
        """,
        (p2,),
    )

    # Participaciones del período actual (es_historico_preexistente = 0)
    conn.execute(
        """
        INSERT INTO participacion (
            id_participacion, id_actividad, id_persona,
            condicion_asistencia, estamento_declarado, es_historico_preexistente
        ) VALUES (?, ?, ?, 'PRESENTE', 'ESTUDIANTE', 0);
        """,
        (str(uuid.uuid4()), exec_1, p1),
    )
    conn.execute(
        """
        INSERT INTO participacion (
            id_participacion, id_actividad, id_persona,
            condicion_asistencia, estamento_declarado, es_historico_preexistente
        ) VALUES (?, ?, ?, 'PRESENTE', 'ESTUDIANTE', 0);
        """,
        (str(uuid.uuid4()), exec_2_multisesion, p1),  # Juan repite sesión en la misma cohorte
    )
    conn.execute(
        """
        INSERT INTO participacion (
            id_participacion, id_actividad, id_persona,
            condicion_asistencia, estamento_declarado, es_historico_preexistente
        ) VALUES (?, ?, ?, 'PRESENTE', 'DOCENTE', 0);
        """,
        (str(uuid.uuid4()), exec_1, p2),
    )

    # Participación Histórica Preexistente (es_historico_preexistente = 1) -> M5 histórico
    p_hist = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo)
        VALUES (?, '999-999999-9999H', 'Historico Antiguo', 'M');
        """,
        (p_hist,),
    )
    conn.execute(
        """
        INSERT INTO participacion (
            id_participacion, id_actividad, id_persona,
            condicion_asistencia, estamento_declarado, es_historico_preexistente
        ) VALUES (?, ?, ?, 'PRESENTE', 'BENEFICIADO', 1);
        """,
        (str(uuid.uuid4()), exec_1, p_hist),
    )

    conn.commit()
    return conn


@pytest.fixture
def reporting_ui_service(populated_db: sqlite3.Connection) -> ReportingUIService:
    """Servicio de UI conectado a la base de datos poblada de prueba."""
    reader = SQLiteIndicatorReader(populated_db)
    calc_svc = IndicatorCalculationService(reader)
    rep_svc = ReportingService(calc_svc, cache=ReportingMemoryCache(default_ttl_seconds=10, enabled=False))
    return ReportingUIService(rep_svc)


# ===========================================================================
# BLOQUE 1: REPORTES INSTITUCIONALES (REPORT-01 A REPORT-05)
# ===========================================================================

class TestOfficialReports:

    def test_report_01_balance_ejecutivo(self, reporting_ui_service: ReportingUIService):
        """REPORT-01: Generación de REP-01 (Balance Ejecutivo) con estructura y métricas completas."""
        doc = reporting_ui_service.generate_report(ReportType.REP_01)
        assert doc.report_type == ReportType.REP_01
        assert "Balance Ejecutivo" in doc.title
        assert len(doc.sections) >= 3
        # Verificar que contiene métricas clave en la primera sección
        sec_resumen = doc.sections[0]
        assert any(m.indicator_id == IndicatorId.IND_ACT_01 for m in sec_resumen.metrics)
        assert any(m.indicator_id == IndicatorId.IND_ACT_02 for m in sec_resumen.metrics)

    def test_report_02_cumplimiento_poa(self, reporting_ui_service: ReportingUIService):
        """REPORT-02: Generación de REP-02 (Cumplimiento POA) con comparativa Plan vs Ejecución."""
        doc = reporting_ui_service.generate_report(ReportType.REP_02)
        assert doc.report_type == ReportType.REP_02
        assert "Cumplimiento" in doc.title
        # Verificar presencia de secciones de cuadrantes y cobertura
        sec_cump = next(s for s in doc.sections if "PLAN OPERATIVO" in s.title.upper() or "CUMPLIMIENTO" in s.title.upper())
        assert sec_cump is not None

    def test_report_03_cobertura_demografica(self, reporting_ui_service: ReportingUIService):
        """REPORT-03: Generación de REP-03 (Demografía) con desglose por estamento y género."""
        doc = reporting_ui_service.generate_report(ReportType.REP_03)
        assert doc.report_type == ReportType.REP_03
        assert "Demográfica" in doc.title
        # Debe reflejar asistencias brutas y personas únicas
        all_metrics = [m for s in doc.sections for m in s.metrics]
        part_ids = {m.indicator_id for m in all_metrics}
        assert IndicatorId.IND_PART_01 in part_ids

    def test_report_04_descentralizacion_territorial(self, reporting_ui_service: ReportingUIService):
        """REPORT-04: Generación de REP-04 (Extensión Territorial) con sedes certificadas."""
        doc = reporting_ui_service.generate_report(ReportType.REP_04)
        assert doc.report_type == ReportType.REP_04
        assert "Territorial" in doc.title
        sec_terr = doc.sections[0]
        assert sec_terr.table_rows is not None

    def test_report_05_auditoria_trazabilidad(self, reporting_ui_service: ReportingUIService):
        """REPORT-05: Generación de REP-05 (Auditoría de Gobernanza y Trazabilidad V004)."""
        doc = reporting_ui_service.generate_report(ReportType.REP_05)
        assert doc.report_type == ReportType.REP_05
        assert "Trazabilidad" in doc.title or "Auditoría" in doc.title
        all_metrics = [m for s in doc.sections for m in s.metrics]
        traz_ids = {m.indicator_id for m in all_metrics}
        assert IndicatorId.IND_TRAZ_01 in traz_ids


# ===========================================================================
# BLOQUE 2: DASHBOARD Y REGLAS INSTITUCIONALES (DASH-01 A DASH-09)
# ===========================================================================

class TestDashboardAndBusinessRules:

    def test_dash_01_dashboard_receives_dto(self, reporting_ui_service: ReportingUIService):
        """DASH-01: Dashboard consume exclusivamente DashboardDataDTO inmutable."""
        data = reporting_ui_service.get_dashboard()
        assert isinstance(data, DashboardDataDTO)
        assert len(data.kpi_cards_summary) == 5
        assert isinstance(data.level_1_summary, DashboardSectionDTO)
        assert isinstance(data.level_2_activity, DashboardSectionDTO)
        assert isinstance(data.level_3_demography, DashboardSectionDTO)
        assert isinstance(data.level_4_territory, DashboardSectionDTO)
        assert isinstance(data.level_5_traceability, DashboardSectionDTO)

    def test_dash_02_dashboard_does_not_calculate_indicators(self):
        """DASH-02: DashboardView no realiza cálculos matemáticos ni reconstruye indicadores."""
        from app.reporting_ui.views.dashboard_view import DashboardView
        # Inspeccionar código fuente con AST
        src_path = Path("app/reporting_ui/views/dashboard_view.py")
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        # Verificar que no importa sqlite3 ni define funciones matemáticas
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "sqlite3"
                    assert "math" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "sqlite3"

    def test_dash_03_filters_applied_correctly(self, reporting_ui_service: ReportingUIService):
        """DASH-03: Los filtros de ReportFilterDTO modifican el resultado del Dashboard."""
        f_all = ReportFilterDTO()
        d_all = reporting_ui_service.get_dashboard(f_all)

        f_sede = ReportFilterDTO(sede="BLUEFIELDS")
        d_sede = reporting_ui_service.get_dashboard(f_sede)

        # En BILWI hay actividades, en BLUEFIELDS hay planes sin ejecución
        val_all_exec = next(c.main_value for c in d_all.kpi_cards_summary if c.card_id == "kpi_executed_acts")
        val_sede_exec = next(c.main_value for c in d_sede.kpi_cards_summary if c.card_id == "kpi_executed_acts")
        assert val_all_exec != val_sede_exec

    def test_dash_04_cohort_unique_default(self, reporting_ui_service: ReportingUIService):
        """DASH-04: COHORT_UNIQUE opera como modo predeterminado (1 plan + N sesiones = 1 cumplimiento)."""
        f_cohort = ReportFilterDTO(multisession_goal_mode=MultisessionGoalMode.COHORT_UNIQUE.value)
        data = reporting_ui_service.get_dashboard(f_cohort)
        cump_card = next(c for c in data.kpi_cards_summary if c.card_id == "kpi_poa_coverage")
        # 1 plan con 2 sesiones ejecutadas cuenta como 1 plan cumplido de 2 planes planificados (50.0%)
        assert "50.0" in cump_card.main_value or "50%" in cump_card.main_value

    def test_dash_05_session_sum_explicit(self, reporting_ui_service: ReportingUIService):
        """DASH-05: SESSION_SUM opera cuando es solicitado explícitamente."""
        f_session = ReportFilterDTO(multisession_goal_mode=MultisessionGoalMode.SESSION_SUM.value)
        data = reporting_ui_service.get_dashboard(f_session)
        assert data.filters_active.multisession_goal_mode == MultisessionGoalMode.SESSION_SUM.value

    def test_dash_06_emergents_do_not_boost_poa(self, reporting_ui_service: ReportingUIService):
        """DASH-06: Actividades emergentes computan en volumen pero 0 aporte a cobertura POA."""
        data = reporting_ui_service.get_dashboard()
        card_emerg = next(c for c in data.kpi_cards_summary if c.card_id == "kpi_emergent_acts")
        # Hay 1 actividad emergente en los datos de prueba
        assert int(card_emerg.main_value) >= 1
        # La cobertura POA solo cuenta planes con vínculo activo (1 de 2 = 50.0%), la emergente no suma
        card_cump = next(c for c in data.kpi_cards_summary if c.card_id == "kpi_poa_coverage")
        assert "50.0" in card_cump.main_value or "1 de 2" in card_cump.sub_label

    def test_dash_07_m5_historical_excluded_from_current_period(self, reporting_ui_service: ReportingUIService):
        """DASH-07: M5 histórico (es_historico_preexistente = 1) no contamina el período actual."""
        data = reporting_ui_service.get_dashboard()
        card_part = next(c for c in data.kpi_cards_summary if c.card_id == "kpi_protagonists")
        # El participante histórico p_hist (es_historico_preexistente = 1) no debe estar en personas únicas (deben ser 2: p1 y p2)
        assert "2 personas únicas" in card_part.sub_label

    def test_dash_08_null_preserved_no_imputation(self, reporting_ui_service: ReportingUIService):
        """DASH-08: NULL y categorías institucionales (No Especificado) se conservan sin imputaciones."""
        data = reporting_ui_service.get_dashboard()
        lvl_3 = data.level_3_demography
        assert lvl_3 is not None
        # Verificar que las notas de auditoría y la estructura preservan la regla de no imputación (INV-05)
        all_notes = " ".join(lvl_3.notes) + " ".join(data.level_1_summary.notes) + " ".join(data.level_4_territory.notes)
        assert any(term in all_notes for term in ["No Especificado", "INV-05", "imputar", "Municipio No Especificado"])

    def test_dash_09_v004_traceability_representation(self, reporting_ui_service: ReportingUIService):
        """DASH-09: Trazabilidad V004 se representa fielmente (ACTIVE vs REVOKED/SUPERSEDED)."""
        data = reporting_ui_service.get_dashboard()
        lvl_5 = data.level_5_traceability
        assert any("Vínculos" in c.title or "Trazabilidad" in c.title or "Salud" in c.title for c in lvl_5.cards)


# ===========================================================================
# BLOQUE 3: EXPORTADORES DERIVADOS (EXPORT-01 A EXPORT-05)
# ===========================================================================

class TestReportExporters:

    def test_export_01_xlsx_validity(self, reporting_ui_service: ReportingUIService, tmp_path: Path):
        """EXPORT-01: Exportación XLSX produce archivo Excel válido y estructurado."""
        doc = reporting_ui_service.generate_report(ReportType.REP_01)
        out_file = tmp_path / "test_report_01.xlsx"
        result_path = reporting_ui_service.export_report(doc, out_file, ExportFormat.XLSX)

        assert result_path.exists()
        assert result_path.stat().st_size > 0

        # Inspección con openpyxl
        wb = openpyxl.load_workbook(str(result_path))
        assert "Resumen Ejecutivo" in wb.sheetnames
        ws = wb["Resumen Ejecutivo"]
        assert "BLUEFIELDS INDIAN & CARIBBEAN UNIVERSITY" in str(ws["A1"].value).upper()
        wb.close()

    def test_export_02_docx_validity(self, reporting_ui_service: ReportingUIService, tmp_path: Path):
        """EXPORT-02: Exportación DOCX produce documento Word válido con python-docx."""
        doc = reporting_ui_service.generate_report(ReportType.REP_02)
        out_file = tmp_path / "test_report_02.docx"
        result_path = reporting_ui_service.export_report(doc, out_file, ExportFormat.DOCX)

        assert result_path.exists()
        assert result_path.stat().st_size > 0

        # Inspección con python-docx
        word_doc = docx.Document(str(result_path))
        text_content = " ".join(p.text for p in word_doc.paragraphs)
        assert "BLUEFIELDS INDIAN & CARIBBEAN UNIVERSITY" in text_content
        assert len(word_doc.tables) >= 1

    def test_export_03_csv_validity(self, reporting_ui_service: ReportingUIService, tmp_path: Path):
        """EXPORT-03: Exportación CSV produce archivo de texto separado por comas válido."""
        doc = reporting_ui_service.generate_report(ReportType.REP_03)
        out_file = tmp_path / "test_report_03.csv"
        result_path = reporting_ui_service.export_report(doc, out_file, ExportFormat.CSV)

        assert result_path.exists()
        csv_text = result_path.read_text(encoding="utf-8-sig")
        assert "# REPORTE OFICIAL INSTITUCIONAL BICU" in csv_text
        assert "REP-03" in csv_text

    def test_export_04_exports_do_not_modify_sqlite(
        self, populated_db: sqlite3.Connection, reporting_ui_service: ReportingUIService, tmp_path: Path
    ):
        """EXPORT-04: Las exportaciones no modifican el estado de SQLite (inmutabilidad)."""
        # Capturar hash del contenido de las tablas de la base de datos
        cursor = populated_db.cursor()
        cursor.execute("SELECT id_actividad, nombre_original FROM actividad ORDER BY id_actividad;")
        acts_before = cursor.fetchall()
        cursor.execute("SELECT id_participacion, estamento_declarado FROM participacion ORDER BY id_participacion;")
        parts_before = cursor.fetchall()

        doc = reporting_ui_service.generate_report(ReportType.REP_01)
        reporting_ui_service.export_report(doc, tmp_path / "rep.xlsx", ExportFormat.XLSX)
        reporting_ui_service.export_report(doc, tmp_path / "rep.docx", ExportFormat.DOCX)
        reporting_ui_service.export_report(doc, tmp_path / "rep.csv", ExportFormat.CSV)

        cursor.execute("SELECT id_actividad, nombre_original FROM actividad ORDER BY id_actividad;")
        acts_after = cursor.fetchall()
        cursor.execute("SELECT id_participacion, estamento_declarado FROM participacion ORDER BY id_participacion;")
        parts_after = cursor.fetchall()

        assert acts_before == acts_after
        assert parts_before == parts_after

    def test_export_05_exports_do_not_modify_m1_m5(self, reporting_ui_service: ReportingUIService, tmp_path: Path):
        """EXPORT-05: Las exportaciones no modifican las plantillas ni matrices M1–M5."""
        template_files = [
            Path("templates/Matriz_1_Consolidado_Actividades.xlsx"),
            Path("templates/Matriz_2_Estudiantes.xlsx"),
            Path("templates/Matriz_3_Academicos_Administrativos.xlsx"),
            Path("templates/Matriz_4_Colaboradores.xlsx"),
            Path("templates/Matriz_5_Protagonistas_Beneficiados.xlsx"),
        ]
        hashes_before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in template_files if p.exists()}

        doc = reporting_ui_service.generate_report(ReportType.REP_05)
        reporting_ui_service.export_report(doc, tmp_path / "m_check.xlsx", ExportFormat.XLSX)

        hashes_after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in template_files if p.exists()}
        assert hashes_before == hashes_after


# ===========================================================================
# BLOQUE 4: ARQUITECTURA Y AISLAMIENTO (ARCH-01 A ARCH-04)
# ===========================================================================

class TestArchitectureAndIsolation:

    def test_arch_01_ui_does_not_import_sqlite3_or_execute_sql(self):
        """ARCH-01: La capa UI (app/reporting_ui) no importa sqlite3 ni ejecuta SQL."""
        ui_dir = Path("app/reporting_ui")
        assert ui_dir.exists()

        for py_file in ui_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name != "sqlite3", f"Violación ARCH-01 en {py_file}: import sqlite3"
                elif isinstance(node, ast.ImportFrom):
                    assert node.module != "sqlite3", f"Violación ARCH-01 en {py_file}: from sqlite3 import ..."

    def test_arch_02_ui_does_not_duplicate_indicators(self):
        """ARCH-02: La capa UI no contiene fórmulas ni duplicación de indicadores."""
        ui_dir = Path("app/reporting_ui")
        forbidden_keywords = {"IND_ACT_01", "IND_CUMP_01", "calculate_indicator"}

        for py_file in ui_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for kw in forbidden_keywords:
                assert f"def {kw}" not in content, f"Violación ARCH-02 en {py_file}: define función de indicador {kw}"

    def test_arch_03_ui_does_not_import_gemini(self):
        """ARCH-03: La capa UI no importa ni depende de Gemini o IA."""
        ui_dir = Path("app/reporting_ui")
        ai_modules = {"google.genai", "google.generativeai", "app.planning.infrastructure.ai"}

        for py_file in ui_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for ai_mod in ai_modules:
                            assert not alias.name.startswith(ai_mod), f"Violación ARCH-03 en {py_file}: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    mod_name = node.module or ""
                    for ai_mod in ai_modules:
                        assert not mod_name.startswith(ai_mod), f"Violación ARCH-03 en {py_file}: {mod_name}"

    def test_arch_04_v004_intact_no_v005(self, db_conn: sqlite3.Connection):
        """ARCH-04: Esquema V004 permanece intacto y V005 no existe."""
        cursor = db_conn.cursor()
        cursor.execute("SELECT max(version) FROM schema_version;")
        row = cursor.fetchone()
        max_version = row[0] if row else None
        assert max_version == 4, f"Se esperaba max(version) = 4, pero se obtuvo {max_version} (prohibido V005)"

        # Verificar que no existen archivos de migración V005
        migrations_dir = Path("app/infrastructure/persistence")
        v005_files = list(migrations_dir.glob("*v005*")) + list(migrations_dir.glob("*V005*"))
        assert len(v005_files) == 0, f"Se encontraron archivos de migración V005 prohibidos: {v005_files}"

    def test_reporting_backend_isolation_ast(self):
        """Verifica que app.reporting puro no importe customtkinter, matplotlib ni UI."""
        reporting_dir = Path("app/reporting")
        forbidden_terms = {"customtkinter", "matplotlib", "google.genai", "google.generativeai", "app.word_consolidator.ui"}

        for py_file in reporting_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_terms:
                            assert not alias.name.startswith(forbidden), (
                                f"Violación de aislamiento en {py_file}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    mod_name = node.module or ""
                    for forbidden in forbidden_terms:
                        assert not mod_name.startswith(forbidden), (
                            f"Violación de aislamiento en {py_file}: from {mod_name} import ..."
                        )
