"""Suite de Pruebas Automatizadas para Indicadores Institucionales BICU.

Fase 29.19.1–29.19.2 — Auditoría e Implementación Controlada de Indicadores.

Cubre exhaustivamente:
  - IND-01: Cero datos (universo vacío, divisiones por cero controladas).
  - IND-02: Una actividad planificada y ejecutada (1:1).
  - IND-03: Múltiples actividades.
  - IND-04: Plan sin ejecución.
  - IND-05: Ejecución sin planificación (emergente).
  - IND-06: Una planificación con múltiples ejecuciones (multisesión 1:N).
  - IND-07: Participación repetida (asistencias brutas vs personas únicas).
  - IND-08: Persona única identificable.
  - IND-09: Persona sin identificador formal (aislamiento controlado).
  - IND-10: Sexo NULL (no imputación, categoría No Especificado).
  - IND-11: Sede y dimensiones nulas/específicas.
  - IND-12: Idempotencia y no duplicación por hash.
  - IND-13: Vínculo ACTIVE (computa en cobertura y trazabilidad).
  - IND-14: Vínculo REVOKED (excluido de cobertura).
  - IND-15: Vínculo SUPERSEDED (excluido de cobertura).
  - IND-16: Exclusión de M5 histórico (es_historico_preexistente = 0).
  - IND-17: Período sin datos.
  - IND-18: Filtrado dimensional ortogonal (sede, programa).
  - IND-19: Conservación de fuentes (solo lectura verificada).
  - IND-20: Reproducibilidad determinista estricta.
  - Pruebas matemáticas de precisión, paridad de género y metas de participación.
"""

import sqlite3
import uuid
from typing import Tuple

import pytest

from app.infrastructure.persistence.migrations import MigrationRunner
from app.indicators.application.service import IndicatorCalculationService
from app.indicators.domain.catalog import IndicatorCatalog, INDICATOR_CATALOG
from app.indicators.domain.contracts import (
    IndicatorCategory,
    IndicatorId,
    IndicatorQuery,
)
from app.indicators.infrastructure.sqlite_reader import SQLiteIndicatorReader


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
def service(db_conn: sqlite3.Connection) -> IndicatorCalculationService:
    """Instancia del servicio determinista conectado al lector SQLite."""
    reader = SQLiteIndicatorReader(db_conn)
    return IndicatorCalculationService(reader)


def _seed_plan(
    conn: sqlite3.Connection,
    planning_id: str = "PLAN-2025-001",
    name: str = "Taller de Emprendimiento",
    sede: str = "BILWI",
    programa: str = "INNOVACION",
    eje: str = "11.41.67",
    tipo: str = "TALLER",
    fecha: str = "2025-03-15",
    meta_total: int = 50,
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
            "Coordinación Innovación", eje, programa, tipo,
            fecha, meta_total // 2, meta_total - (meta_total // 2),
        ),
    )
    conn.commit()
    return internal_id


def _seed_exec(
    conn: sqlite3.Connection,
    name: str = "Taller de Emprendimiento Real",
    sede: str = "BILWI",
    programa: str = "INNOVACION",
    eje: str = "11.41.67",
    tipo: str = "TALLER",
    fecha: str = "2025-03-15",
    estado: str = "EJECUTADA",
    es_emergente: int = 0,
    hash_val: str = "",
) -> str:
    """Inserta una actividad ejecutada en la tabla actividad."""
    act_id = str(uuid.uuid4())
    final_hash = hash_val or f"hash_{act_id}_{name}"
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
            "DGI", "Coordinador Real", estado, es_emergente,
            final_hash,
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
            link_id, str(plan_internal_id), exec_id, "Auditor Institucional",
            "Trazabilidad formal certificada", num_sesion, status,
        ),
    )
    conn.commit()
    return link_id


def _seed_participant(
    conn: sqlite3.Connection,
    exec_id: str,
    nombre: str = "Persona Test",
    cedula: str = None,
    sexo: str = "F",
    estamento: str = "ESTUDIANTE",
    condicion: str = "PRESENTE",
    es_historico: int = 0,
) -> Tuple[str, str]:
    """Inserta una persona y su participación en la actividad."""
    p_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO persona (
            id_persona_interno, cedula, nombre_completo, sexo
        ) VALUES (?, ?, ?, ?);
        """,
        (p_id, cedula, nombre, sexo),
    )
    part_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO participacion (
            id_participacion, id_actividad, id_persona,
            estamento_declarado, condicion_asistencia, es_historico_preexistente
        ) VALUES (?, ?, ?, ?, ?, ?);
        """,
        (part_id, exec_id, p_id, estamento, condicion, es_historico),
    )
    conn.commit()
    return p_id, part_id


# ---------------------------------------------------------------------------
# TESTS DE CATÁLOGO Y CONTRATOS
# ---------------------------------------------------------------------------

class TestCatalogAndContracts:
    """Verifica que el catálogo oficial contenga todos los indicadores aprobados."""

    def test_catalogo_contiene_15_indicadores(self):
        assert len(INDICATOR_CATALOG) >= 15
        assert IndicatorId.IND_ACT_01 in INDICATOR_CATALOG
        assert IndicatorId.IND_ACT_02 in INDICATOR_CATALOG
        assert IndicatorId.IND_CUMP_01 in INDICATOR_CATALOG
        assert IndicatorId.IND_PART_01 in INDICATOR_CATALOG
        assert IndicatorId.IND_TRAZ_01 in INDICATOR_CATALOG

    def test_todos_los_indicadores_tienen_contrato_completo(self):
        for ind_id, defn in INDICATOR_CATALOG.items():
            assert defn.indicator_id == ind_id
            assert defn.name and len(defn.name) > 5
            assert defn.definition and len(defn.definition) > 10
            assert defn.purpose and len(defn.purpose) > 10
            assert defn.source and len(defn.source) > 5
            assert defn.formula and len(defn.formula) > 3
            assert defn.unit in ("actividades", "%", "participaciones", "personas únicas", "% y Razón")
            assert defn.periodicity
            assert len(defn.dimensions) > 0
            assert defn.null_policy
            assert defn.duplicate_policy
            assert defn.limitations
            assert defn.allowed_interpretation
            assert defn.forbidden_interpretation


# ---------------------------------------------------------------------------
# TESTS IND-01 A IND-20
# ---------------------------------------------------------------------------

class TestCoreIndicatorsSuite:
    """Pruebas funcionales de los casos canónicos IND-01 a IND-20."""

    def test_ind_01_cero_datos(self, service: IndicatorCalculationService):
        """IND-01: Base de datos vacía. Conteos en 0, tasas en None (sin división por cero)."""
        report = service.calculate_all()
        assert report.results[IndicatorId.IND_ACT_01].value == 0.0
        assert report.results[IndicatorId.IND_ACT_02].value == 0.0
        assert report.results[IndicatorId.IND_PART_01].value == 0.0
        assert report.results[IndicatorId.IND_CUMP_01].value is None  # División por cero protegida
        assert report.results[IndicatorId.IND_TRAZ_01].value is None

    def test_ind_02_una_actividad(self, db_conn, service):
        """IND-02: 1 plan y 1 ejecución con vínculo ACTIVE (1:1). Cobertura y trazabilidad 100%."""
        plan_id = _seed_plan(db_conn)
        exec_id = _seed_exec(db_conn)
        _seed_link(db_conn, plan_id, exec_id, status="ACTIVE")

        res_act1 = service.calculate_indicator(IndicatorId.IND_ACT_01)
        res_act2 = service.calculate_indicator(IndicatorId.IND_ACT_02)
        res_cump = service.calculate_indicator(IndicatorId.IND_CUMP_01)
        res_traz = service.calculate_indicator(IndicatorId.IND_TRAZ_01)

        assert res_act1.value == 1.0
        assert res_act2.value == 1.0
        assert res_cump.value == 100.0
        assert res_traz.value == 100.0

    def test_ind_03_multiples_actividades(self, db_conn, service):
        """IND-03: Múltiples actividades en distintos estados y sedes."""
        p1 = _seed_plan(db_conn, planning_id="P1", sede="BILWI")
        p2 = _seed_plan(db_conn, planning_id="P2", sede="BLUEFIELDS")
        p3 = _seed_plan(db_conn, planning_id="P3", sede="BILWI")

        e1 = _seed_exec(db_conn, sede="BILWI")
        e2 = _seed_exec(db_conn, sede="BLUEFIELDS")

        _seed_link(db_conn, p1, e1, status="ACTIVE")
        _seed_link(db_conn, p2, e2, status="ACTIVE")

        res_act1 = service.calculate_indicator(IndicatorId.IND_ACT_01)
        res_act2 = service.calculate_indicator(IndicatorId.IND_ACT_02)
        res_cump = service.calculate_indicator(IndicatorId.IND_CUMP_01)

        assert res_act1.value == 3.0
        assert res_act2.value == 2.0
        assert res_cump.value == round((2.0 / 3.0) * 100.0, 2)  # 66.67%

    def test_ind_04_plan_sin_ejecucion(self, db_conn, service):
        """IND-04: Planificación sin ninguna ejecución vinculada."""
        _seed_plan(db_conn, planning_id="P-PENDIENTE")

        res_act1 = service.calculate_indicator(IndicatorId.IND_ACT_01)
        res_act2 = service.calculate_indicator(IndicatorId.IND_ACT_02)
        res_cump = service.calculate_indicator(IndicatorId.IND_CUMP_01)

        assert res_act1.value == 1.0
        assert res_act2.value == 0.0
        assert res_cump.value == 0.0

    def test_ind_05_ejecucion_sin_planificacion_emergente(self, db_conn, service):
        """IND-05: Ejecución emergente sin planificación previa."""
        _seed_exec(db_conn, name="Feria Emergente Comunitaria", es_emergente=1)

        res_act1 = service.calculate_indicator(IndicatorId.IND_ACT_01)
        res_act2 = service.calculate_indicator(IndicatorId.IND_ACT_02)
        res_act3 = service.calculate_indicator(IndicatorId.IND_ACT_03)
        res_traz = service.calculate_indicator(IndicatorId.IND_TRAZ_01)

        assert res_act1.value == 0.0
        assert res_act2.value == 1.0
        assert res_act3.value == 1.0
        assert res_traz.value == 0.0

    def test_ind_06_una_planificacion_con_multiples_ejecuciones_multisesion(self, db_conn, service):
        """IND-06: Multisesión (1 plan -> 3 sesiones). El plan cuenta como 1, NO como 300%."""
        p_id = _seed_plan(db_conn, planning_id="TALLER-CICLO-01")
        s1 = _seed_exec(db_conn, name="Sesión 1")
        s2 = _seed_exec(db_conn, name="Sesión 2")
        s3 = _seed_exec(db_conn, name="Sesión 3")

        _seed_link(db_conn, p_id, s1, status="ACTIVE", num_sesion=1)
        _seed_link(db_conn, p_id, s2, status="ACTIVE", num_sesion=2)
        _seed_link(db_conn, p_id, s3, status="ACTIVE", num_sesion=3)

        res_act1 = service.calculate_indicator(IndicatorId.IND_ACT_01)
        res_act2 = service.calculate_indicator(IndicatorId.IND_ACT_02)
        res_cump = service.calculate_indicator(IndicatorId.IND_CUMP_01)

        assert res_act1.value == 1.0  # 1 actividad planificada
        assert res_act2.value == 3.0  # 3 sesiones ejecutadas
        assert res_cump.value == 100.0  # 1 plan cumplido / 1 plan total = 100% (¡NO 300%!)

    def test_ind_07_participacion_repetida_asistencias_vs_personas_unicas(self, db_conn, service):
        """IND-07: 1 persona asiste a 3 actividades distintas. 3 asistencias brutas, 1 persona única."""
        e1 = _seed_exec(db_conn, name="Act 1")
        e2 = _seed_exec(db_conn, name="Act 2")
        e3 = _seed_exec(db_conn, name="Act 3")

        # Misma persona en 3 eventos
        p_id = str(uuid.uuid4())
        db_conn.execute(
            "INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo) VALUES (?, ?, ?, ?);",
            (p_id, "601-120395-0001A", "Estudiante Frecuente", "F"),
        )
        for act in (e1, e2, e3):
            db_conn.execute(
                """
                INSERT INTO participacion (
                    id_participacion, id_actividad, id_persona,
                    estamento_declarado, condicion_asistencia, es_historico_preexistente
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (str(uuid.uuid4()), act, p_id, "ESTUDIANTE", "PRESENTE", 0),
            )
        db_conn.commit()

        res_part1 = service.calculate_indicator(IndicatorId.IND_PART_01)
        res_part2 = service.calculate_indicator(IndicatorId.IND_PART_02)
        res_rec = service.calculate_indicator(IndicatorId.IND_PART_03)

        assert res_part1.value == 3.0  # 3 asistencias brutas
        assert res_part2.value == 1.0  # 1 persona única
        assert res_rec.value == 100.0  # 100% de las personas son recurrentes

    def test_ind_08_persona_unica_identificable(self, db_conn, service):
        """IND-08: Personas con cédula o número institucional válido cuentan como únicas."""
        e1 = _seed_exec(db_conn)
        _seed_participant(db_conn, e1, nombre="Ana", cedula="601-010190-0001A")
        _seed_participant(db_conn, e1, nombre="Carlos", cedula="601-020290-0002B")

        res_part2 = service.calculate_indicator(IndicatorId.IND_PART_02)
        assert res_part2.value == 2.0

    def test_ind_09_persona_sin_identificador(self, db_conn, service):
        """IND-09: Personas sin cédula se aíslan cuando require_verified_id=True."""
        e1 = _seed_exec(db_conn)
        _seed_participant(db_conn, e1, nombre="Comunitario Sin Cédula", cedula=None)
        _seed_participant(db_conn, e1, nombre="Docente Con Cédula", cedula="601-121280-0001X")

        res_strict = service.calculate_indicator(
            IndicatorId.IND_PART_02,
            IndicatorQuery(require_verified_id_for_unique_persons=True),
        )
        assert res_strict.value == 1.0
        assert any("sin cédula/ID formal" in n for n in res_strict.notes)

        res_lax = service.calculate_indicator(
            IndicatorId.IND_PART_02,
            IndicatorQuery(require_verified_id_for_unique_persons=False),
        )
        assert res_lax.value == 2.0

    def test_ind_10_sexo_null(self, db_conn, service):
        """IND-10: Participante con sexo nulo o inválido NO es imputado a M o F."""
        class MockReaderWithNullSex(SQLiteIndicatorReader):
            def get_participations(self, query):
                return [
                    {"sexo": "F", "id_participacion": "1"},
                    {"sexo": "M", "id_participacion": "2"},
                    {"sexo": None, "id_participacion": "3"},
                    {"sexo": "", "id_participacion": "4"},
                ]

        mock_service = IndicatorCalculationService(MockReaderWithNullSex(db_conn))
        res_sexo = mock_service.calculate_indicator(IndicatorId.IND_PART_04)
        bd = res_sexo.breakdown

        assert bd["total_femenino"] == 1
        assert bd["total_masculino"] == 1
        assert bd["total_no_especificado"] == 2
        assert bd["porcentaje_femenino"] == 50.0
        assert bd["porcentaje_masculino"] == 50.0
        assert bd["indice_paridad"] == 1.0
        assert any("no especificado" in n.lower() for n in res_sexo.notes)

    def test_ind_11_sede_desconocida_o_especifica(self, db_conn, service):
        """IND-11: Desglose territorial agrupa correctamente por sede."""
        _seed_exec(db_conn, sede="BILWI")
        _seed_exec(db_conn, sede="BILWI")
        _seed_exec(db_conn, sede="BLUEFIELDS")

        res_terr = service.calculate_indicator(IndicatorId.IND_TERR_01)
        bd = res_terr.breakdown

        assert bd["BILWI"]["conteo"] == 2
        assert bd["BILWI"]["porcentaje"] == 66.67
        assert bd["BLUEFIELDS"]["conteo"] == 1
        assert bd["BLUEFIELDS"]["porcentaje"] == 33.33

    def test_ind_12_duplicado_reprocesamiento_idempotencia(self, db_conn, service):
        """IND-12: El mismo hash_sha256 en actividad es bloqueado por SQLite (idempotencia)."""
        _seed_exec(db_conn, name="Actividad Unica", hash_val="hash_repetido_123")
        with pytest.raises(sqlite3.IntegrityError):
            _seed_exec(db_conn, name="Actividad Duplicada", hash_val="hash_repetido_123")

        res_act2 = service.calculate_indicator(IndicatorId.IND_ACT_02)
        assert res_act2.value == 1.0

    def test_ind_13_vinculo_active(self, db_conn, service):
        """IND-13: Vínculo ACTIVE computa en trazabilidad y cobertura."""
        p = _seed_plan(db_conn)
        e = _seed_exec(db_conn)
        _seed_link(db_conn, p, e, status="ACTIVE")

        res_cump = service.calculate_indicator(IndicatorId.IND_CUMP_01)
        res_traz = service.calculate_indicator(IndicatorId.IND_TRAZ_01)

        assert res_cump.value == 100.0
        assert res_traz.value == 100.0

    def test_ind_14_vinculo_revoked(self, db_conn, service):
        """IND-14: Vínculo REVOKED se excluye estrictamente de cobertura y trazabilidad."""
        p = _seed_plan(db_conn)
        e = _seed_exec(db_conn)
        _seed_link(db_conn, p, e, status="REVOKED")

        res_cump = service.calculate_indicator(IndicatorId.IND_CUMP_01)
        res_traz = service.calculate_indicator(IndicatorId.IND_TRAZ_01)

        assert res_cump.value == 0.0
        assert res_traz.value == 0.0

    def test_ind_15_vinculo_superseded(self, db_conn, service):
        """IND-15: Vínculo SUPERSEDED no cuenta como activo."""
        p = _seed_plan(db_conn)
        e = _seed_exec(db_conn)
        _seed_link(db_conn, p, e, status="SUPERSEDED")

        res_cump = service.calculate_indicator(IndicatorId.IND_CUMP_01)
        assert res_cump.value == 0.0

    def test_ind_16_m5_historico_exclusion(self, db_conn, service):
        """IND-16: Filas con es_historico_preexistente=1 se excluyen de los indicadores del período."""
        e = _seed_exec(db_conn)
        _seed_participant(db_conn, e, nombre="Beneficiario Histórico", cedula="601-111111-0001H", es_historico=1)
        _seed_participant(db_conn, e, nombre="Beneficiario Actual", cedula="601-222222-0001A", es_historico=0)

        res_part1 = service.calculate_indicator(IndicatorId.IND_PART_01)
        res_part2 = service.calculate_indicator(IndicatorId.IND_PART_02)

        assert res_part1.value == 1.0  # Solo el actual
        assert res_part2.value == 1.0

    def test_ind_17_periodo_sin_datos(self, db_conn, service):
        """IND-17: Filtro temporal sobre rango vacío retorna 0 o None para tasas."""
        _seed_exec(db_conn, fecha="2025-01-15")

        q_vacio = IndicatorQuery(start_date="2025-06-01", end_date="2025-06-30")
        res_act = service.calculate_indicator(IndicatorId.IND_ACT_02, q_vacio)
        res_traz = service.calculate_indicator(IndicatorId.IND_TRAZ_01, q_vacio)

        assert res_act.value == 0.0
        assert res_traz.value is None

    def test_ind_18_filtro_por_dimension(self, db_conn, service):
        """IND-18: Filtrado dimensional aísla los recintos solicitados."""
        _seed_exec(db_conn, sede="BILWI")
        _seed_exec(db_conn, sede="BLUEFIELDS")

        q_bilwi = IndicatorQuery(sede="BILWI")
        res_bilwi = service.calculate_indicator(IndicatorId.IND_ACT_02, q_bilwi)
        assert res_bilwi.value == 1.0

    def test_ind_19_conservacion_de_fuentes_solo_lectura(self, db_conn, service):
        """IND-19: La ejecución de indicadores no altera el estado de la base de datos."""
        _seed_plan(db_conn)
        _seed_exec(db_conn)

        # Capturar conteos antes
        cur = db_conn.cursor()
        c_plan_pre = cur.execute("SELECT COUNT(*) FROM planning_planned_activities;").fetchone()[0]
        c_act_pre = cur.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]

        # Ejecutar todos los indicadores
        service.calculate_all()

        # Capturar conteos después
        c_plan_post = cur.execute("SELECT COUNT(*) FROM planning_planned_activities;").fetchone()[0]
        c_act_post = cur.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]

        assert c_plan_pre == c_plan_post == 1
        assert c_act_pre == c_act_post == 1

    def test_ind_20_reproducibilidad_determinista(self, db_conn, service):
        """IND-20: Dos ejecuciones sucesivas idénticas retornan exactamente el mismo reporte."""
        p = _seed_plan(db_conn)
        e = _seed_exec(db_conn)
        _seed_link(db_conn, p, e, status="ACTIVE")
        _seed_participant(db_conn, e, nombre="Participante A", cedula="601-000000-0001A")

        rep1 = service.calculate_all()
        rep2 = service.calculate_all()

        assert rep1.total_calculated == rep2.total_calculated
        for k in rep1.results:
            assert rep1.results[k].value == rep2.results[k].value
            assert rep1.results[k].numerator_value == rep2.results[k].numerator_value
            assert rep1.results[k].denominator_value == rep2.results[k].denominator_value


class TestDiscrepancyAndQualityIndicators:
    """Pruebas para los indicadores de discrepancia documental y calidad."""

    def test_ind_traz_02_discrepancias(self, db_conn, service):
        """Verifica la tasa de discrepancias activas M1 vs M2-M5."""
        e1 = _seed_exec(db_conn, name="Act 1")
        e2 = _seed_exec(db_conn, name="Act 2")

        # Discrepancia activa en Act 1
        db_conn.execute(
            """
            INSERT INTO discrepancia (
                id_discrepancia, id_actividad, tipo_discrepancia, severidad,
                fuente_a_nombre, fuente_a_valor, fuente_b_nombre, fuente_b_valor,
                estado, fecha_deteccion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                str(uuid.uuid4()), e1, "M1_VS_NOMINALES", "WARNING",
                "M1", "50", "Nominal", "40",
                "REQUIERE_REVISION", "2025-03-20",
            ),
        )
        db_conn.commit()

        res_disc = service.calculate_indicator(IndicatorId.IND_TRAZ_02)
        assert res_disc.numerator_value == 1.0
        assert res_disc.denominator_value == 2.0
        assert res_disc.value == 50.0

    def test_ind_traz_03_disponibilidad_cedula(self, db_conn, service):
        """Verifica la tasa de disponibilidad de cédula oficial."""
        e = _seed_exec(db_conn)
        _seed_participant(db_conn, e, nombre="Con Cédula", cedula="601-111111-0001A")
        _seed_participant(db_conn, e, nombre="Sin Cédula", cedula="")

        res_ced = service.calculate_indicator(IndicatorId.IND_TRAZ_03)
        assert res_ced.numerator_value == 1.0
        assert res_ced.denominator_value == 2.0
        assert res_ced.value == 50.0


class TestMathematicalPrecisionAndFormulas:
    """Pruebas rigurosas de precisión numérica, redondeo y parámetros de decisión."""

    def test_ind_cump_02_modos_multisesion(self, db_conn, service):
        """Verifica IND-CUMP-02 en modos COHORT_UNIQUE vs SESSION_SUM (DEC-INST-02)."""
        p = _seed_plan(db_conn, meta_total=100)
        s1 = _seed_exec(db_conn, name="Sesion 1")
        s2 = _seed_exec(db_conn, name="Sesion 2")
        _seed_link(db_conn, p, s1, status="ACTIVE", num_sesion=1)
        _seed_link(db_conn, p, s2, status="ACTIVE", num_sesion=2)

        # Misma persona asiste a ambas sesiones
        p_id = str(uuid.uuid4())
        db_conn.execute(
            "INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo) VALUES (?, ?, ?, ?);",
            (p_id, "601-999999-0001Z", "Persona Repetida", "F"),
        )
        for act in (s1, s2):
            db_conn.execute(
                """
                INSERT INTO participacion (
                    id_participacion, id_actividad, id_persona,
                    estamento_declarado, condicion_asistencia, es_historico_preexistente
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (str(uuid.uuid4()), act, p_id, "ESTUDIANTE", "PRESENTE", 0),
            )
        db_conn.commit()

        # En modo COHORT_UNIQUE: 1 persona única / meta 100 = 1.0%
        res_cohort = service.calculate_indicator(
            IndicatorId.IND_CUMP_02,
            IndicatorQuery(multisession_goal_mode="COHORT_UNIQUE"),
        )
        assert res_cohort.numerator_value == 1.0
        assert res_cohort.denominator_value == 100.0
        assert res_cohort.value == 1.0

        # En modo SESSION_SUM: 2 asistencias / meta 100 = 2.0%
        res_sum = service.calculate_indicator(
            IndicatorId.IND_CUMP_02,
            IndicatorQuery(multisession_goal_mode="SESSION_SUM"),
        )
        assert res_sum.numerator_value == 2.0
        assert res_sum.denominator_value == 100.0
        assert res_sum.value == 2.0

    def test_ind_act_04_solo_approved_computa(self, db_conn, service):
        """Verifica que en IND-ACT-04 solo diseños en APPROVED computen en el numerador."""
        p1 = _seed_plan(db_conn, planning_id="P-DRAFT")
        p2 = _seed_plan(db_conn, planning_id="P-APPROVED")
        p3 = _seed_plan(db_conn, planning_id="P-REJECTED")

        # Insertar diseños en diferentes estados
        db_conn.execute(
            """
            INSERT INTO planning_methodological_designs (
                design_id, planned_activity_internal_id, planned_activity_ref,
                status, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (str(uuid.uuid4()), str(p1), "P-DRAFT", "DRAFT", "User 1", "2025-01-01"),
        )
        db_conn.execute(
            """
            INSERT INTO planning_methodological_designs (
                design_id, planned_activity_internal_id, planned_activity_ref,
                status, created_by, created_at, approved_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (str(uuid.uuid4()), str(p2), "P-APPROVED", "APPROVED", "User 2", "2025-01-01", "Director"),
        )
        db_conn.execute(
            """
            INSERT INTO planning_methodological_designs (
                design_id, planned_activity_internal_id, planned_activity_ref,
                status, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (str(uuid.uuid4()), str(p3), "P-REJECTED", "REJECTED", "User 3", "2025-01-01"),
        )
        db_conn.commit()

        res = service.calculate_indicator(IndicatorId.IND_ACT_04)
        assert res.numerator_value == 1.0  # Solo p2
        assert res.denominator_value == 3.0
        assert res.value == round((1.0 / 3.0) * 100.0, 2)  # 33.33%


class TestImmutabilityAndNoV005:
    """Verificación formal de que no existe V005 y los esquemas V001–V004 son inmutables."""

    def test_no_existe_migracion_v005(self):
        """Verifica que el registro de migraciones solo contenga V001 a V004."""
        from app.infrastructure.persistence.migrations import MIGRATION_REGISTRY
        versions = [m.version for m in MIGRATION_REGISTRY]
        assert 5 not in versions, "PROHIBICIÓN VIOLADA: Existe una migración V005 en el registro."
        assert max(versions) == 4

    def test_schema_version_maximo_es_v004(self, db_conn):
        """Verifica que la base de datos aplique hasta V004 y ninguna tabla V005."""
        cur = db_conn.cursor()
        rows = cur.execute("SELECT version FROM schema_version ORDER BY version ASC;").fetchall()
        applied_versions = [r[0] for r in rows]
        assert applied_versions == [1, 2, 3, 4]

    def test_indicadores_no_alteran_esquema(self, db_conn, service):
        """Verifica que tras calcular todos los indicadores el esquema permanezca intacto."""
        cur = db_conn.cursor()
        tables_pre = {
            r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        }

        # Ejecutar todos los indicadores
        service.calculate_all()

        tables_post = {
            r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        }

        assert tables_pre == tables_post, "El cálculo de indicadores alteró las tablas de la base de datos."

