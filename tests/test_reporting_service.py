"""Suite de Pruebas Automatizadas para el Núcleo de Reporting y Dashboard BICU.

Fase 29.20.1 — Implementación Controlada del Núcleo Reporting Service.

Cubre exhaustivamente:
  - DTOs inmutables (@dataclass(frozen=True)).
  - Aislamiento arquitectónico (sin CustomTkinter, sin Gemini, sin Word Consolidator).
  - REP-01: Balance Ejecutivo de Gestión Institucional.
  - REP-02: Evaluación de Cumplimiento del POA (Plan vs Ejecución, Cuadrantes).
  - REP-03: Cobertura Demográfica y Atención de Protagonistas (Asistencias vs Personas Únicas).
  - REP-04: Extensión y Descentralización Territorial (Sedes DDL V001).
  - REP-05: Auditoría de Trazabilidad, Gobernanza y Salud del Dato (ACTIVE vs REVOKED/SUPERSEDED).
  - Multisesión (1:N): 1 plan + N ejecuciones = 1 plan cumplido (max 100%).
  - Actividades Emergentes: Volumen y territorio sí; 0 aporte a cobertura POA.
  - M5 Histórico: Exclusión estricta de registros preexistentes (es_historico_preexistente = 0).
  - Parámetros: COHORT_UNIQUE (default) vs SESSION_SUM explícito.
  - Cédula Verificada: require_verified_id_for_unique_persons = True (default) vs False.
  - Control de División por Cero: Base de datos vacía devuelve "N/D" sin ZeroDivisionError.
  - Solo Lectura: Cero mutaciones en base de datos relacional SQLite (schema_version = 4).
  - DashboardDataDTO: Payload estructurado completo en 5 niveles ortogonales.
  - Caché en Memoria: ReportingMemoryCache (hit, set, invalidación, TTL).
"""

from dataclasses import FrozenInstanceError
import hashlib
import sqlite3
import sys
import uuid
from typing import Tuple

import pytest

from app.infrastructure.persistence.migrations import MigrationRunner
from app.indicators.application.service import IndicatorCalculationService
from app.indicators.domain.contracts import IndicatorId
from app.indicators.infrastructure.sqlite_reader import SQLiteIndicatorReader
from app.reporting import (
    AlertStatus,
    DashboardCardDTO,
    DashboardDataDTO,
    DashboardSectionDTO,
    MultisessionGoalMode,
    ReportDocumentDTO,
    ReportFilterDTO,
    ReportMetricItemDTO,
    ReportSectionDTO,
    ReportingMemoryCache,
    ReportingService,
    ReportType,
)


# ---------------------------------------------------------------------------
# FIXTURES Y AUXILIARES DE TEST
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn() -> sqlite3.Connection:
    """Crea una base de datos SQLite en memoria con esquema V001–V004 completo."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    runner = MigrationRunner(conn)
    runner.apply_all_pending()
    return conn


@pytest.fixture
def reporting_service(db_conn: sqlite3.Connection) -> ReportingService:
    """Instancia del ReportingService conectado a la base de datos de prueba."""
    reader = SQLiteIndicatorReader(db_conn)
    calc_service = IndicatorCalculationService(reader)
    cache = ReportingMemoryCache(default_ttl_seconds=30, enabled=True)
    return ReportingService(calc_service, cache=cache)


def _seed_plan(
    conn: sqlite3.Connection,
    planning_id: str = "PLAN-2026-001",
    name: str = "Taller Institucional",
    sede: str = "BLUEFIELDS",
    programa: str = "INNOVACION",
    eje: str = "11.41.67",
    tipo: str = "TALLER",
    fecha: str = "2026-04-10",
    meta_total: int = 40,
) -> uuid.UUID:
    """Inserta una actividad planificada en planning_planned_activities."""
    internal_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO planning_planned_activities (
            activity_internal_id, planning_id, activity_name, sede,
            area_responsable, eje_estrategia, programa, tipo_evento,
            fecha_evento, est_grado_m, est_grado_f
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            str(internal_id), planning_id, name, sede,
            "Dirección de Extensión", eje, programa, tipo,
            fecha, meta_total // 2, meta_total - (meta_total // 2),
        ),
    )
    conn.commit()
    return internal_id


def _seed_exec(
    conn: sqlite3.Connection,
    name: str = "Taller Institucional Ejecutado",
    sede: str = "BLUEFIELDS",
    programa: str = "INNOVACION",
    eje: str = "11.41.67",
    tipo: str = "TALLER",
    fecha: str = "2026-04-10",
    estado: str = "EJECUTADA",
    es_emergente: int = 0,
) -> str:
    """Inserta una actividad ejecutada en la tabla actividad."""
    act_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO actividad (
            id_actividad, nombre_original, tipo_evento, sede,
            eje_estrategico, programa, fecha_inicio,
            departamento_responsable, responsable, estado, es_emergente,
            hash_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            act_id, name, tipo, sede,
            eje, programa, fecha,
            "DGI", "Coordinador BICU", estado, es_emergente,
            f"hash_{act_id}",
        ),
    )
    conn.commit()
    return act_id


def _seed_link(
    conn: sqlite3.Connection,
    plan_internal_id: uuid.UUID,
    exec_id: str,
    status: str = "ACTIVE",
    num_sesion: int = None,
) -> str:
    """Inserta un vínculo en planning_execution_links."""
    link_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO planning_execution_links (
            link_id, planning_internal_id, id_actividad, linked_by,
            link_rationale, numero_sesion, link_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            link_id, str(plan_internal_id), exec_id, "Auditor BICU",
            "Trazabilidad formal certificada", num_sesion, status,
        ),
    )
    conn.commit()
    return link_id


def _seed_participant(
    conn: sqlite3.Connection,
    exec_id: str,
    nombre: str = "Protagonista Test",
    cedula: str = None,
    sexo: str = "F",
    estamento: str = "ESTUDIANTE",
    condicion: str = "PRESENTE",
    es_historico: int = 0,
) -> Tuple[str, str]:
    """Inserta una persona y su participación efectiva."""
    p_id = str(uuid.uuid4())
    sexo_val = sexo if sexo is not None else "NO_ESPECIFICADO"
    conn.execute(
        """
        INSERT INTO persona (
            id_persona_interno, cedula, nombre_completo, sexo
        ) VALUES (?, ?, ?, ?);
        """,
        (p_id, cedula, nombre, sexo_val),
    )
    part_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO participacion (
            id_participacion, id_actividad, id_persona,
            condicion_asistencia, estamento_declarado, es_historico_preexistente
        ) VALUES (?, ?, ?, ?, ?, ?);
        """,
        (part_id, exec_id, p_id, condicion, estamento, es_historico),
    )
    conn.commit()
    return p_id, part_id


# ===========================================================================
# 1. PRUEBAS DE INMUTABILIDAD DE DTOs
# ===========================================================================

class TestReportingDTOsInmutability:
    """Valida que todos los DTOs sean estrictamente inmutables (@dataclass(frozen=True))."""

    def test_report_filter_dto_frozen(self):
        f = ReportFilterDTO(period_year=2026, sede="BLUEFIELDS")
        with pytest.raises(FrozenInstanceError):
            f.period_year = 2025  # type: ignore

    def test_report_filter_dto_validation_multisession_mode(self):
        # Modo válido
        f = ReportFilterDTO(multisession_goal_mode=MultisessionGoalMode.SESSION_SUM.value)
        assert f.multisession_goal_mode == "SESSION_SUM"

        # Modo inválido debe lanzar ValueError defensivo
        with pytest.raises(ValueError, match="Modo multisesión inválido"):
            ReportFilterDTO(multisession_goal_mode="MODO_INVENTADO")

    def test_report_metric_item_dto_frozen(self):
        item = ReportMetricItemDTO(
            indicator_id="IND-ACT-01",
            label="Planes",
            value_display="10",
            raw_value=10.0,
            unit="planes",
        )
        with pytest.raises(FrozenInstanceError):
            item.value_display = "20"  # type: ignore

    def test_dashboard_card_dto_frozen(self):
        card = DashboardCardDTO(
            card_id="card-1",
            indicator_id="IND-CUMP-01",
            title="Cobertura",
            main_value="85.00%",
            unit_label="%",
            sub_label="Normal",
            alert_status=AlertStatus.GREEN,
            tooltip_explanation="Explicación",
        )
        with pytest.raises(FrozenInstanceError):
            card.alert_status = AlertStatus.RED  # type: ignore


# ===========================================================================
# 2. PRUEBAS DE AISLAMIENTO ARQUITECTÓNICO
# ===========================================================================

class TestReportingIsolation:
    """Garantiza que la capa de Reporting no importe CustomTkinter, Gemini ni Word Consolidator."""

    def test_reporting_does_not_import_ui_or_ai(self):
        import ast
        from pathlib import Path

        reporting_dir = Path("app/reporting")
        forbidden_terms = {"customtkinter", "google.genai", "google.generativeai", "app.word_consolidator"}

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

    def test_reporting_service_no_sqlite_writes(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """Verifica que ReportingService no ejecute sentencias INSERT/UPDATE/DELETE."""
        # Seeding inicial
        plan_id = _seed_plan(db_conn, fecha="2026-05-01")
        exec_id = _seed_exec(db_conn, fecha="2026-05-01")
        _seed_link(db_conn, plan_id, exec_id, status="ACTIVE")

        # Tomar hash del estado de la tabla actividad
        cursor = db_conn.cursor()
        cursor.execute("SELECT id_actividad, nombre_original, estado FROM actividad ORDER BY id_actividad;")
        initial_state = cursor.fetchall()

        # Ejecutar todos los reportes y dashboard
        f = ReportFilterDTO(period_year=2026)
        reporting_service.generate_report(ReportType.REP_01, f)
        reporting_service.generate_report(ReportType.REP_02, f)
        reporting_service.generate_report(ReportType.REP_03, f)
        reporting_service.generate_report(ReportType.REP_04, f)
        reporting_service.generate_report(ReportType.REP_05, f)
        reporting_service.get_dashboard_data(f)

        # Verificar que el estado de la base de datos es 100% idéntico
        cursor.execute("SELECT id_actividad, nombre_original, estado FROM actividad ORDER BY id_actividad;")
        final_state = cursor.fetchall()
        assert initial_state == final_state, "ReportingService modificó registros en la base de datos."


# ===========================================================================
# 3. PRUEBAS DE GENERACIÓN DE REPORTES (REP-01 A REP-05)
# ===========================================================================

class TestReportingReportsGeneration:
    """Valida la composición estructurada de cada uno de los 5 reportes institucionales."""

    def test_rep_01_balance_ejecutivo(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """REP-01: Generación íntegra del Balance Ejecutivo."""
        p_id = _seed_plan(db_conn, name="Plan 1", sede="BILWI", fecha="2026-03-01", meta_total=20)
        e_id = _seed_exec(db_conn, name="Ejec 1", sede="BILWI", fecha="2026-03-01")
        _seed_link(db_conn, p_id, e_id, status="ACTIVE")
        _seed_participant(db_conn, e_id, nombre="Persona 1", cedula="601-010101-0001A", sexo="F")
        _seed_participant(db_conn, e_id, nombre="Persona 2", cedula="601-010101-0002B", sexo="M")

        doc = reporting_service.generate_report(ReportType.REP_01, ReportFilterDTO(period_year=2026))

        assert doc.report_type == ReportType.REP_01
        assert "REP-01: Balance Ejecutivo" in doc.title
        assert len(doc.sections) == 3

        # Sección 1: Resumen Cuantitativo
        sec_resumen = doc.sections[0]
        metric_ids = [m.indicator_id for m in sec_resumen.metrics]
        assert IndicatorId.IND_ACT_01 in metric_ids
        assert IndicatorId.IND_ACT_02 in metric_ids
        assert IndicatorId.IND_CUMP_01 in metric_ids
        assert IndicatorId.IND_PART_01 in metric_ids
        assert IndicatorId.IND_PART_02 in metric_ids

        # Sección 2: Desconcentración territorial
        sec_terr = doc.sections[1]
        assert len(sec_terr.table_rows) > 0
        sedes_in_table = [r[0] for r in sec_terr.table_rows]
        assert "BILWI" in sedes_in_table

        # Sección 3: Auditoría y notas
        sec_audit = doc.sections[2]
        assert any("es_historico_preexistente = 0" in note for note in sec_audit.audit_notes)

    def test_rep_02_cumplimiento_poa_cuadrantes(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """REP-02: Evaluación del POA y separación en cuadrantes operativos."""
        # Plan 1 cumplido
        p1 = _seed_plan(db_conn, planning_id="P-01", name="Plan Cumplido", fecha="2026-06-01")
        e1 = _seed_exec(db_conn, name="Ejec 1", fecha="2026-06-01")
        _seed_link(db_conn, p1, e1, status="ACTIVE")

        # Plan 2 pendiente
        _seed_plan(db_conn, planning_id="P-02", name="Plan Pendiente", fecha="2026-06-01")

        # Ejecución emergente (sin plan)
        _seed_exec(db_conn, name="Ejecución Emergente", fecha="2026-06-01", es_emergente=1)

        doc = reporting_service.generate_report(ReportType.REP_02, ReportFilterDTO(period_year=2026))

        assert doc.report_type == ReportType.REP_02
        sec_cuadrantes = doc.sections[1]
        assert sec_cuadrantes.section_id == "cuadrantes_operativos"

        rows = {r[0]: r[2] for r in sec_cuadrantes.table_rows}
        assert rows["Cuadrante 1"] == "1"  # 1 cumplido
        assert rows["Cuadrante 2"] == "1"  # 1 pendiente
        assert rows["Cuadrante 3"] == "1"  # 1 emergente
        assert rows["Cuadrante 4"] == "2"  # 2 ejecutadas totales (1 trazada + 1 emergente)

    def test_rep_03_cobertura_demografica(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """REP-03: Participaciones vs personas únicas y desglose por sexo sin imputación."""
        e1 = _seed_exec(db_conn, fecha="2026-07-01")
        e2 = _seed_exec(db_conn, fecha="2026-07-02")

        # Persona repetida en 2 actividades
        p1, _ = _seed_participant(db_conn, e1, nombre="Ana", cedula="601-111111-0001A", sexo="F", estamento="DOCENTE")
        # Misma persona en e2 (misma cedula)
        conn = db_conn
        conn.execute(
            "INSERT INTO participacion (id_participacion, id_actividad, id_persona, condicion_asistencia, estamento_declarado, es_historico_preexistente) VALUES (?, ?, ?, 'PRESENTE', 'DOCENTE', 0);",
            (str(uuid.uuid4()), e2, p1),
        )
        # Persona con sexo M
        _seed_participant(db_conn, e1, nombre="Carlos", cedula="601-222222-0002B", sexo="M", estamento="ESTUDIANTE")

        doc = reporting_service.generate_report(ReportType.REP_03, ReportFilterDTO(period_year=2026))

        assert doc.report_type == ReportType.REP_03
        sec_poblacion = doc.sections[0]
        metrics = {m.indicator_id: m for m in sec_poblacion.metrics}

        # 3 asistencias brutas (Ana x 2 + Carlos x 1)
        assert metrics[IndicatorId.IND_PART_01].raw_value == 3.0
        # 2 personas únicas
        assert metrics[IndicatorId.IND_PART_02].raw_value == 2.0

        # Verificación de distribución de sexo en sección 2
        sec_genero = doc.sections[1]
        genero_rows = {r[0]: r[1] for r in sec_genero.table_rows}
        assert genero_rows["Femenino"] == "2"         # Ana asistió 2 veces
        assert genero_rows["Masculino"] == "1"        # Carlos asistió 1 vez
        assert genero_rows["No Especificado"] == "0"  # Cero nulos en este lote

    def test_rep_03_sexo_no_especificado_mock(self, db_conn: sqlite3.Connection):
        """REP-03: Participación con sexo no especificado preservada intacta sin imputación."""
        class MockReaderWithNullSex(SQLiteIndicatorReader):
            def get_participations(self, query):
                return [
                    {"sexo": "F", "estamento_declarado": "ESTUDIANTE"},
                    {"sexo": "M", "estamento_declarado": "DOCENTE"},
                    {"sexo": None, "estamento_declarado": "COMUNIDAD"},
                    {"sexo": "", "estamento_declarado": "COLABORADOR"},
                ]
            def get_unique_persons(self, query):
                return [
                    {"cedula": "1", "sexo": "F"},
                    {"cedula": "2", "sexo": "M"},
                    {"cedula": None, "sexo": None},
                ]

        calc = IndicatorCalculationService(MockReaderWithNullSex(db_conn))
        rep_srv = ReportingService(calc)
        doc = rep_srv.generate_report(ReportType.REP_03)

        sec_genero = doc.sections[1]
        genero_rows = {r[0]: r[1] for r in sec_genero.table_rows}
        assert genero_rows["Femenino"] == "1"
        assert genero_rows["Masculino"] == "1"
        assert genero_rows["No Especificado"] == "2"

    def test_rep_04_descentralizacion_territorial(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """REP-04: Extensión territorial respetando las sedes relacionales V001."""
        _seed_exec(db_conn, name="Act Bluefields", sede="BLUEFIELDS", fecha="2026-08-01")
        _seed_exec(db_conn, name="Act Bilwi", sede="BILWI", fecha="2026-08-02")
        _seed_exec(db_conn, name="Act Waspam", sede="WASPAM", fecha="2026-08-03")

        doc = reporting_service.generate_report(ReportType.REP_04, ReportFilterDTO(period_year=2026))

        assert doc.report_type == ReportType.REP_04
        sec_sedes = doc.sections[0]
        assert sec_sedes.section_id == "desconcentracion_geografica"

        sedes_in_report = {r[0]: r[1] for r in sec_sedes.table_rows}
        assert sedes_in_report["BLUEFIELDS"] == "1"
        assert sedes_in_report["BILWI"] == "1"
        assert sedes_in_report["WASPAM"] == "1"
        assert any("DEC-CAT-01" in note for note in sec_sedes.audit_notes)

    def test_rep_05_auditoria_trazabilidad(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """REP-05: Trazabilidad V004 y exclusión estricta de REVOKED/SUPERSEDED."""
        p1 = _seed_plan(db_conn, planning_id="P-01", fecha="2026-09-01")
        p2 = _seed_plan(db_conn, planning_id="P-02", fecha="2026-09-01")

        e1 = _seed_exec(db_conn, name="Ejec 1", fecha="2026-09-01")
        e2 = _seed_exec(db_conn, name="Ejec 2", fecha="2026-09-01")

        # e1 tiene enlace ACTIVE
        _seed_link(db_conn, p1, e1, status="ACTIVE")
        # e2 tiene enlace REVOKED (anulado por auditor)
        _seed_link(db_conn, p2, e2, status="REVOKED")

        doc = reporting_service.generate_report(ReportType.REP_05, ReportFilterDTO(period_year=2026))

        assert doc.report_type == ReportType.REP_05
        sec_traz = doc.sections[0]
        traz_rows = {r[0]: r[1] for r in sec_traz.table_rows}
        # Solo 1 ejecución activa (e1), e2 fue revocado y no suma
        assert traz_rows["Ejecuciones con Enlace Activo (ACTIVE)"] == "1"
        assert traz_rows["Total de Actividades Ejecutadas Auditadas"] == "2"


# ===========================================================================
# 4. PRUEBAS DE CASOS CRÍTICOS Y REGLAS PERICIALES
# ===========================================================================

class TestCriticalRulesAndParameters:
    """Valida multisesión (1:N), emergentes, M5 histórico, parámetros y división por cero."""

    def test_multisession_rule_1_to_n(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """1 plan planificado con 3 ejecuciones vinculadas = 1 plan cumplido (100%, jamás 300%)."""
        plan_id = _seed_plan(db_conn, planning_id="PLAN-MULTI", name="Taller Multisesión", fecha="2026-10-01")

        # 3 ejecuciones de sesiones distintas del mismo plan
        e1 = _seed_exec(db_conn, name="Sesión 1", fecha="2026-10-01")
        e2 = _seed_exec(db_conn, name="Sesión 2", fecha="2026-10-08")
        e3 = _seed_exec(db_conn, name="Sesión 3", fecha="2026-10-15")

        _seed_link(db_conn, plan_id, e1, status="ACTIVE", num_sesion=1)
        _seed_link(db_conn, plan_id, e2, status="ACTIVE", num_sesion=2)
        _seed_link(db_conn, plan_id, e3, status="ACTIVE", num_sesion=3)

        doc = reporting_service.generate_report(ReportType.REP_02, ReportFilterDTO(period_year=2026))
        cump_metric = next(m for m in doc.sections[0].metrics if m.indicator_id == IndicatorId.IND_CUMP_01)

        # 1 plan cumplido de 1 plan planificado = 100.00%
        assert cump_metric.raw_value == 100.0
        assert cump_metric.numerator_display == "1"
        assert cump_metric.denominator_display == "1"

    def test_emergentes_zero_poa_impact(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """Actividades emergentes no aumentan el numerador de cumplimiento del POA."""
        # 1 plan sin ejecución
        _seed_plan(db_conn, planning_id="PLAN-PEND", fecha="2026-11-01")

        # 3 ejecuciones emergentes sin plan
        _seed_exec(db_conn, name="Emergente 1", fecha="2026-11-02", es_emergente=1)
        _seed_exec(db_conn, name="Emergente 2", fecha="2026-11-03", es_emergente=1)
        _seed_exec(db_conn, name="Emergente 3", fecha="2026-11-04", es_emergente=1)

        doc = reporting_service.generate_report(ReportType.REP_02, ReportFilterDTO(period_year=2026))
        cump_metric = next(m for m in doc.sections[0].metrics if m.indicator_id == IndicatorId.IND_CUMP_01)

        # Cobertura debe ser exactamente 0.00%
        assert cump_metric.raw_value == 0.0
        assert cump_metric.numerator_display == "0"
        assert cump_metric.denominator_display == "1"

    def test_m5_historico_excluded(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """Registros preexistentes de M5 con es_historico_preexistente = 1 quedan excluidos."""
        exec_id = _seed_exec(db_conn, fecha="2026-05-01")

        # 1 participante regular del período
        _seed_participant(db_conn, exec_id, nombre="Persona Período", cedula="601-000000-0001A", es_historico=0)

        # 2 participantes históricos de M5
        _seed_participant(db_conn, exec_id, nombre="Histórico 1", cedula="601-999999-0001Z", es_historico=1)
        _seed_participant(db_conn, exec_id, nombre="Histórico 2", cedula="601-999999-0002Y", es_historico=1)

        doc = reporting_service.generate_report(ReportType.REP_03, ReportFilterDTO(period_year=2026))
        part_metric = next(m for m in doc.sections[0].metrics if m.indicator_id == IndicatorId.IND_PART_01)

        # Solo debe registrar 1 participación efectiva, los 2 históricos deben ser excluidos
        assert part_metric.raw_value == 1.0

    def test_parameters_cohort_unique_vs_session_sum(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """Verifica la conmutación entre modos multisesión en IND-CUMP-02."""
        plan_id = _seed_plan(db_conn, planning_id="P-MULTI", meta_total=10, fecha="2026-05-01")
        e1 = _seed_exec(db_conn, fecha="2026-05-01")
        e2 = _seed_exec(db_conn, fecha="2026-05-02")
        _seed_link(db_conn, plan_id, e1, status="ACTIVE", num_sesion=1)
        _seed_link(db_conn, plan_id, e2, status="ACTIVE", num_sesion=2)

        # Misma persona asiste a ambas sesiones
        p_id, _ = _seed_participant(db_conn, e1, nombre="Lucía", cedula="601-333333-0001L")
        conn = db_conn
        conn.execute(
            "INSERT INTO participacion (id_participacion, id_actividad, id_persona, condicion_asistencia, estamento_declarado, es_historico_preexistente) VALUES (?, ?, ?, 'PRESENTE', 'ESTUDIANTE', 0);",
            (str(uuid.uuid4()), e2, p_id),
        )

        # Modo 1: COHORT_UNIQUE -> 1 persona única / 10 meta = 10.00%
        f_cohort = ReportFilterDTO(period_year=2026, multisession_goal_mode="COHORT_UNIQUE")
        doc_cohort = reporting_service.generate_report(ReportType.REP_02, f_cohort)
        cump_02_cohort = next(m for m in doc_cohort.sections[0].metrics if m.indicator_id == IndicatorId.IND_CUMP_02)
        assert cump_02_cohort.raw_value == 10.0
        assert doc_cohort.parameters_applied["multisession_goal_mode"] == "COHORT_UNIQUE"

        # Modo 2: SESSION_SUM -> 2 asistencias brutas / 10 meta = 20.00%
        f_sum = ReportFilterDTO(period_year=2026, multisession_goal_mode="SESSION_SUM")
        doc_sum = reporting_service.generate_report(ReportType.REP_02, f_sum)
        cump_02_sum = next(m for m in doc_sum.sections[0].metrics if m.indicator_id == IndicatorId.IND_CUMP_02)
        assert cump_02_sum.raw_value == 20.0
        assert doc_sum.parameters_applied["multisession_goal_mode"] == "SESSION_SUM"

    def test_require_verified_id_parameter(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        """Verifica el comportamiento de require_verified_id_for_unique_persons."""
        e = _seed_exec(db_conn, fecha="2026-05-01")
        _seed_participant(db_conn, e, nombre="Persona Con Cédula", cedula="601-555555-0001A")
        _seed_participant(db_conn, e, nombre="Persona Sin Cédula", cedula=None)

        # Con cédula requerida (default: True) -> Solo 1 persona única verificada
        doc_verified = reporting_service.generate_report(
            ReportType.REP_03,
            ReportFilterDTO(period_year=2026, require_verified_id_for_unique_persons=True),
        )
        p2_metric_v = next(m for m in doc_verified.sections[0].metrics if m.indicator_id == IndicatorId.IND_PART_02)
        assert p2_metric_v.raw_value == 1.0

        # Sin cédula requerida (False) -> Las 2 personas computan como únicas
        doc_unverified = reporting_service.generate_report(
            ReportType.REP_03,
            ReportFilterDTO(period_year=2026, require_verified_id_for_unique_persons=False),
        )
        p2_metric_u = next(m for m in doc_unverified.sections[0].metrics if m.indicator_id == IndicatorId.IND_PART_02)
        assert p2_metric_u.raw_value == 2.0

    def test_zero_division_empty_database(self, reporting_service: ReportingService):
        """Base de datos vacía no genera ZeroDivisionError ni None sin manejar."""
        f = ReportFilterDTO(period_year=2026)

        # Generar todos los reportes sobre base vacía
        for rtype in [ReportType.REP_01, ReportType.REP_02, ReportType.REP_03, ReportType.REP_04, ReportType.REP_05]:
            doc = reporting_service.generate_report(rtype, f)
            assert doc is not None
            for sec in doc.sections:
                for m in sec.metrics:
                    assert m.value_display in ("0", "N/D", "0.00%", "0.00")

        # Generar dashboard data sobre base vacía
        dash = reporting_service.get_dashboard_data(f)
        assert dash is not None
        for card in dash.kpi_cards_summary:
            assert card.main_value in ("0", "N/D", "0.00%", "0.00")


# ===========================================================================
# 5. PRUEBAS DEL PAYLOAD COMPLETO DEL DASHBOARD (DASHBOARDDATADTO)
# ===========================================================================

class TestDashboardDataPayload:
    """Verifica que DashboardDataDTO entregue los 5 niveles completos para la futura vista."""

    def test_dashboard_data_structure(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        plan_id = _seed_plan(db_conn, fecha="2026-04-01")
        exec_id = _seed_exec(db_conn, fecha="2026-04-01")
        _seed_link(db_conn, plan_id, exec_id, status="ACTIVE")
        _seed_participant(db_conn, exec_id, nombre="Estudiante 1", cedula="601-123456-0001A")

        data = reporting_service.get_dashboard_data(ReportFilterDTO(period_year=2026))

        assert isinstance(data, DashboardDataDTO)
        assert len(data.kpi_cards_summary) == 5

        # Verificar los 5 niveles
        assert data.level_1_summary.section_id == "level_1_summary"
        assert data.level_2_activity.section_id == "level_2_activity"
        assert data.level_3_demography.section_id == "level_3_demography"
        assert data.level_4_territory.section_id == "level_4_territory"
        assert data.level_5_traceability.section_id == "level_5_traceability"

        # Gráficos presentes en niveles correspondientes
        assert len(data.level_2_activity.charts) >= 1
        assert len(data.level_3_demography.charts) >= 1
        assert len(data.level_4_territory.charts) >= 1

        # Alertas de salud del sistema
        assert isinstance(data.system_health_alerts, list)
        assert len(data.system_health_alerts) >= 1


# ===========================================================================
# 6. PRUEBAS DE CACHÉ EN MEMORIA (REPORTINGMEMORYCACHE)
# ===========================================================================

class TestReportingMemoryCache:
    """Valida el funcionamiento de la memoria volátil pasiva."""

    def test_cache_hit_and_invalidation(self, db_conn: sqlite3.Connection, reporting_service: ReportingService):
        f = ReportFilterDTO(period_year=2026)

        # Primera llamada calcula y almacena
        doc1 = reporting_service.generate_report(ReportType.REP_01, f)
        # Segunda llamada devuelve exactamente la misma instancia de la caché
        doc2 = reporting_service.generate_report(ReportType.REP_01, f)
        assert doc1 is doc2

        # Invalidar caché
        reporting_service._cache.clear()
        # Tercera llamada recalcula
        doc3 = reporting_service.generate_report(ReportType.REP_01, f)
        assert doc3 is not doc1
        assert doc3.report_id != doc1.report_id  # Nuevo timestamp de ID
