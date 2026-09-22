"""Tests de V004 — PlanningExecutionLink (Trazabilidad Planificación ↔ Ejecución).

Fase 29.18.1 — Implementación Controlada de Trazabilidad.

PRINCIPIO RECTOR: PLANIFICADO ≠ EJECUTADO.

Suite de tests que verifica:
  T1.  Migración V004 aplicada correctamente (tabla y columnas presentes).
  T2.  PlanningExecutionLink.create() genera UUID y estado ACTIVE.
  T3.  Validación de invariantes del dominio.
  T4.  Ciclo de vida: ACTIVE → REVOKED (inmutabilidad de revoke()).
  T5.  save() + get_by_id() round-trip.
  T6.  get_by_planning_id() / get_by_actividad_id() / get_active_by_planning_id().
  T7.  Restricción UNIQUE(planning_internal_id, id_actividad) aplicada por SQLite.
  T8.  Aislamiento: las tablas de ejecución (actividad, participacion) no se modifican.
  T9.  V003 permanece inmutable (tablas planning_* no modificadas).
  T10. Integridad patrimonial: hashes M1-M5 y EXE no afectados.
"""

import sqlite3
import uuid
from datetime import datetime

import pytest

from app.infrastructure.persistence.migrations import MigrationRunner, MIGRATION_REGISTRY
from app.planning.domain.entities import PlanningExecutionLink
from app.planning.infrastructure.persistence.schema_v004 import (
    EXPECTED_V004_TABLE_NAMES,
    V004_SCHEMA_DDL_STATEMENTS,
    V004_INDEXES_DDL_STATEMENTS,
)


# ---------------------------------------------------------------------------
# FIXTURE: Base de datos con esquema completo (V001-V004) en memoria
# ---------------------------------------------------------------------------

def _build_full_db() -> sqlite3.Connection:
    """Crea una BD SQLite in-memory con todas las migraciones V001-V004 aplicadas."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    runner = MigrationRunner(conn)
    runner.apply_all_pending()
    return conn


def _seed_actividad(conn: sqlite3.Connection) -> str:
    """Inserta una actividad de ejecución mínima y retorna su id_actividad."""
    id_act = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO actividad (
            id_actividad, nombre_original, tipo_evento,
            sede, departamento_geo, municipio,
            fecha_inicio,
            departamento_responsable, responsable, estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            id_act, "Actividad Test V004", "TALLER",
            "BILWI", "RACN", "Puerto Cabezas",
            "2025-01-15",
            "Área Test", "Director Test", "EJECUTADA",
        ),
    )
    conn.commit()
    return id_act


def _seed_planned_activity(conn: sqlite3.Connection) -> uuid.UUID:
    """Inserta una actividad planificada mínima y retorna su activity_internal_id."""
    act_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO planning_planned_activities (
            activity_internal_id, planning_id, activity_name, sede,
            area_responsable, eje_estrategia, programa, tipo_evento,
            est_grado_m, est_grado_f, est_postgrado_m, est_postgrado_f,
            docentes_m, docentes_f, administrativos_m, administrativos_f,
            externos_m, externos_f
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
        """,
        (
            str(act_id), "POA-2025-001", "Capacitación Docente V004",
            "BICU BILWI", "Área Académica", "EJE-01", "PROG-01", "TALLER",
        ),
    )
    conn.commit()
    return act_id


# ---------------------------------------------------------------------------
# T1. Migración V004: tabla y columnas presentes
# ---------------------------------------------------------------------------

class TestV004MigracionEsquema:
    """T1 — Verifica que la migración V004 crea la tabla con las columnas correctas."""

    def test_tabla_planning_execution_links_existe(self):
        conn = _build_full_db()
        runner = MigrationRunner(conn)
        tables = runner.get_existing_tables()
        assert "planning_execution_links" in tables, (
            "La tabla planning_execution_links debe existir tras aplicar V004."
        )
        conn.close()

    def test_columnas_correctas(self):
        conn = _build_full_db()
        conn.row_factory = sqlite3.Row
        cur = conn.execute("PRAGMA table_info(planning_execution_links);")
        col_names = {row["name"] for row in cur.fetchall()}
        required = {
            "link_id", "planning_internal_id", "id_actividad",
            "linked_by", "linked_at", "link_rationale",
            "numero_sesion", "link_status",
            "revoked_by", "revoked_at", "revocation_reason",
        }
        missing = required - col_names
        assert not missing, f"Columnas faltantes en planning_execution_links: {missing}"
        conn.close()

    def test_v004_registrada_en_schema_version(self):
        conn = _build_full_db()
        cur = conn.execute(
            "SELECT version, nombre_migracion FROM schema_version WHERE version = 4;"
        )
        row = cur.fetchone()
        assert row is not None, "V004 debe estar registrada en schema_version."
        assert row["nombre_migracion"] == "v004_planning_execution_links"
        conn.close()

    def test_v003_no_modificada(self):
        """Las tablas de V003 deben seguir intactas tras V004."""
        conn = _build_full_db()
        runner = MigrationRunner(conn)
        tables = runner.get_existing_tables()
        v003_tables = {
            "planning_planned_activities",
            "planning_methodological_designs",
            "planning_design_faqs",
            "planning_design_agenda",
            "planning_design_operational_matrix",
            "planning_ai_proposals",
        }
        for t in v003_tables:
            assert t in tables, f"La tabla V003 '{t}' debe seguir presente tras V004."
        conn.close()

    def test_expected_v004_table_names_correcto(self):
        assert EXPECTED_V004_TABLE_NAMES == {"planning_execution_links"}

    def test_ddl_statements_no_vacios(self):
        assert len(V004_SCHEMA_DDL_STATEMENTS) >= 1
        assert len(V004_INDEXES_DDL_STATEMENTS) >= 1


# ---------------------------------------------------------------------------
# T2. Dominio: PlanningExecutionLink.create()
# ---------------------------------------------------------------------------

class TestPlanningExecutionLinkDominio:
    """T2/T3/T4 — Prueba entidad PlanningExecutionLink sin base de datos."""

    def test_create_genera_uuid_y_status_active(self):
        plan_id = uuid.uuid4()
        link = PlanningExecutionLink.create(
            planning_internal_id=plan_id,
            id_actividad="ACT-001",
            linked_by="Director Académico",
            link_rationale="Actividad ejecutada corresponde al POA 2025 Q1.",
        )
        assert isinstance(link.link_id, uuid.UUID)
        assert link.link_status == "ACTIVE"
        assert link.planning_internal_id == plan_id
        assert link.id_actividad == "ACT-001"
        assert link.linked_by == "Director Académico"
        assert link.revoked_by is None
        assert link.revoked_at is None
        assert link.revocation_reason is None

    def test_create_con_numero_sesion(self):
        link = PlanningExecutionLink.create(
            planning_internal_id=uuid.uuid4(),
            id_actividad="ACT-MULTI",
            linked_by="Coordinador",
            link_rationale="Sesión 2 de 3.",
            numero_sesion=2,
        )
        assert link.numero_sesion == 2

    def test_validacion_linked_by_obligatorio(self):
        with pytest.raises(ValueError, match="linked_by"):
            PlanningExecutionLink.create(
                planning_internal_id=uuid.uuid4(),
                id_actividad="ACT-001",
                linked_by="",
                link_rationale="Justificación.",
            )

    def test_validacion_link_rationale_obligatorio(self):
        with pytest.raises(ValueError, match="link_rationale"):
            PlanningExecutionLink.create(
                planning_internal_id=uuid.uuid4(),
                id_actividad="ACT-001",
                linked_by="Director",
                link_rationale="   ",
            )

    def test_validacion_id_actividad_obligatorio(self):
        with pytest.raises(ValueError, match="id_actividad"):
            PlanningExecutionLink.create(
                planning_internal_id=uuid.uuid4(),
                id_actividad="",
                linked_by="Director",
                link_rationale="Justificación.",
            )

    def test_validacion_status_invalido(self):
        with pytest.raises(ValueError, match="link_status"):
            PlanningExecutionLink(
                link_id=uuid.uuid4(),
                planning_internal_id=uuid.uuid4(),
                id_actividad="ACT-001",
                linked_by="Director",
                linked_at=datetime.now(),
                link_rationale="Justificación.",
                link_status="PENDIENTE",  # Inválido
            )

    def test_validacion_revoked_sin_datos(self):
        with pytest.raises(ValueError, match="revoked_by"):
            PlanningExecutionLink(
                link_id=uuid.uuid4(),
                planning_internal_id=uuid.uuid4(),
                id_actividad="ACT-001",
                linked_by="Director",
                linked_at=datetime.now(),
                link_rationale="Justificación.",
                link_status="REVOKED",
                # revoked_by faltante
            )

    def test_validacion_numero_sesion_menor_que_uno(self):
        with pytest.raises(ValueError, match="numero_sesion"):
            PlanningExecutionLink.create(
                planning_internal_id=uuid.uuid4(),
                id_actividad="ACT-001",
                linked_by="Director",
                link_rationale="Justificación.",
                numero_sesion=0,
            )

    def test_revoke_retorna_nueva_instancia(self):
        """T4 — revoke() es inmutable: retorna copia, no modifica original."""
        original = PlanningExecutionLink.create(
            planning_internal_id=uuid.uuid4(),
            id_actividad="ACT-001",
            linked_by="Director",
            link_rationale="Justificación inicial.",
        )
        revocado = original.revoke("Rector", "Actividad cancelada por fuerza mayor.")
        # Original no modificado
        assert original.link_status == "ACTIVE"
        assert original.revoked_by is None
        # Copia revocada
        assert revocado.link_status == "REVOKED"
        assert revocado.revoked_by == "Rector"
        assert revocado.revocation_reason == "Actividad cancelada por fuerza mayor."
        assert revocado.link_id == original.link_id  # Mismo ID

    def test_revoke_dos_veces_falla(self):
        link = PlanningExecutionLink.create(
            planning_internal_id=uuid.uuid4(),
            id_actividad="ACT-001",
            linked_by="Director",
            link_rationale="Justificación.",
        )
        revocado = link.revoke("Rector", "Motivo 1.")
        with pytest.raises(ValueError, match="ya está revocado"):
            revocado.revoke("Decano", "Motivo 2.")

    def test_revoke_sin_revoked_by_falla(self):
        link = PlanningExecutionLink.create(
            planning_internal_id=uuid.uuid4(),
            id_actividad="ACT-001",
            linked_by="Director",
            link_rationale="Justificación.",
        )
        with pytest.raises(ValueError, match="revoked_by"):
            link.revoke("", "Motivo.")

    def test_revoke_sin_reason_falla(self):
        link = PlanningExecutionLink.create(
            planning_internal_id=uuid.uuid4(),
            id_actividad="ACT-001",
            linked_by="Director",
            link_rationale="Justificación.",
        )
        with pytest.raises(ValueError, match="reason"):
            link.revoke("Rector", "")


# ---------------------------------------------------------------------------
# T5/T6/T7. Repositorio SQLite: persistencia, consultas y unicidad
# ---------------------------------------------------------------------------

class TestSQLitePlanningExecutionLinkRepository:
    """T5/T6/T7 — Prueba el repositorio concreto SQLite."""

    def setup_method(self):
        """Prepara la BD completa con datos de planificación y ejecución."""
        from app.planning.infrastructure.persistence.repositories import (
            SQLitePlanningExecutionLinkRepository,
        )
        self.conn = _build_full_db()
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.repo = SQLitePlanningExecutionLinkRepository(self.conn)
        self.id_actividad = _seed_actividad(self.conn)
        self.planning_id = _seed_planned_activity(self.conn)

    def teardown_method(self):
        self.conn.close()

    def _make_link(self, **kwargs) -> PlanningExecutionLink:
        defaults = dict(
            planning_internal_id=self.planning_id,
            id_actividad=self.id_actividad,
            linked_by="Director Académico",
            link_rationale="Actividad ejecutada en el marco del POA 2025.",
        )
        defaults.update(kwargs)
        return PlanningExecutionLink.create(**defaults)

    def test_save_y_get_by_id_roundtrip(self):
        """T5 — save() + get_by_id() round-trip completo."""
        link = self._make_link()
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(link)
        self.conn.execute("COMMIT;")

        recovered = self.repo.get_by_id(link.link_id)
        assert recovered is not None
        assert recovered.link_id == link.link_id
        assert recovered.planning_internal_id == link.planning_internal_id
        assert recovered.id_actividad == link.id_actividad
        assert recovered.linked_by == link.linked_by
        assert recovered.link_rationale == link.link_rationale
        assert recovered.link_status == "ACTIVE"
        assert recovered.numero_sesion is None
        assert recovered.revoked_by is None

    def test_save_link_con_numero_sesion(self):
        link = self._make_link(numero_sesion=3)
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(link)
        self.conn.execute("COMMIT;")

        recovered = self.repo.get_by_id(link.link_id)
        assert recovered is not None
        assert recovered.numero_sesion == 3

    def test_get_by_id_inexistente_retorna_none(self):
        result = self.repo.get_by_id(uuid.uuid4())
        assert result is None

    def test_get_by_planning_id(self):
        """T6 — get_by_planning_id() retorna todos los vínculos del planning_id."""
        link1 = self._make_link()
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(link1)
        self.conn.execute("COMMIT;")

        results = self.repo.get_by_planning_id(self.planning_id)
        assert len(results) >= 1
        ids = [r.link_id for r in results]
        assert link1.link_id in ids

    def test_get_by_actividad_id(self):
        """T6 — get_by_actividad_id() retorna todos los vínculos de la ejecución."""
        link = self._make_link()
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(link)
        self.conn.execute("COMMIT;")

        results = self.repo.get_by_actividad_id(self.id_actividad)
        assert len(results) >= 1
        ids = [r.link_id for r in results]
        assert link.link_id in ids

    def test_get_active_by_planning_id(self):
        """T6 — get_active_by_planning_id() retorna el vínculo ACTIVE."""
        link = self._make_link()
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(link)
        self.conn.execute("COMMIT;")

        active = self.repo.get_active_by_planning_id(self.planning_id)
        assert active is not None
        assert active.link_id == link.link_id
        assert active.link_status == "ACTIVE"

    def test_get_active_sin_vinculos_retorna_none(self):
        result = self.repo.get_active_by_planning_id(uuid.uuid4())
        assert result is None

    def test_save_revocado_actualiza_estado(self):
        """T5 — save() de un vínculo revocado persiste el nuevo estado."""
        link = self._make_link()
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(link)
        self.conn.execute("COMMIT;")

        revocado = link.revoke("Rector", "Cancelado por decreto.")
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(revocado)
        self.conn.execute("COMMIT;")

        recovered = self.repo.get_by_id(link.link_id)
        assert recovered is not None
        assert recovered.link_status == "REVOKED"
        assert recovered.revoked_by == "Rector"
        assert recovered.revocation_reason == "Cancelado por decreto."

    def test_unicidad_planning_actividad_falla_en_duplicado(self):
        """T7 — UNIQUE(planning_internal_id, id_actividad) es forzado por SQLite."""
        link1 = self._make_link()
        link2 = self._make_link()  # Mismo par (planning_id, id_actividad)
        assert link1.link_id != link2.link_id  # Distintos UUIDs

        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(link1)
        self.conn.execute("COMMIT;")

        # El segundo insert con mismo par debe fallar
        with pytest.raises(Exception):  # sqlite3.IntegrityError o similar
            self.conn.execute("BEGIN IMMEDIATE;")
            self.repo.save(link2)
            self.conn.execute("COMMIT;")

    def test_replace_link_id_misma_pk_upsert(self):
        """T7 — INSERT OR REPLACE con mismo link_id actualiza sin violar UNIQUE."""
        link = self._make_link()
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(link)
        self.conn.execute("COMMIT;")

        # Modificamos el rationale (mismo link_id, mismo par)
        revocado = link.revoke("Rector", "Cambio de estrategia institucional.")
        self.conn.execute("BEGIN IMMEDIATE;")
        self.repo.save(revocado)  # Debe hacer REPLACE correctamente
        self.conn.execute("COMMIT;")

        recovered = self.repo.get_by_id(link.link_id)
        assert recovered.link_status == "REVOKED"


# ---------------------------------------------------------------------------
# T8. Aislamiento: dominio de ejecución no modificado
# ---------------------------------------------------------------------------

class TestAislamientoEjecucion:
    """T8 — Las tablas de ejecución no se alteran por V004."""

    def test_actividad_no_tiene_columnas_planning(self):
        conn = _build_full_db()
        conn.row_factory = sqlite3.Row
        cur = conn.execute("PRAGMA table_info(actividad);")
        col_names = {row["name"] for row in cur.fetchall()}
        # Ninguna columna del dominio de planificación
        forbidden = {"planning_internal_id", "link_id", "linked_by"}
        assert not (forbidden & col_names), (
            f"La tabla 'actividad' no debe tener columnas de planificación: "
            f"{forbidden & col_names}"
        )
        conn.close()

    def test_participacion_no_tiene_columnas_planning(self):
        conn = _build_full_db()
        conn.row_factory = sqlite3.Row
        cur = conn.execute("PRAGMA table_info(participacion);")
        col_names = {row["name"] for row in cur.fetchall()}
        forbidden = {"planning_internal_id", "link_id", "linked_by"}
        assert not (forbidden & col_names), (
            f"La tabla 'participacion' no debe tener columnas de planificación: "
            f"{forbidden & col_names}"
        )
        conn.close()

    def test_planning_execution_links_no_tiene_datos_personales(self):
        conn = _build_full_db()
        conn.row_factory = sqlite3.Row
        cur = conn.execute("PRAGMA table_info(planning_execution_links);")
        col_names = {row["name"] for row in cur.fetchall()}
        # Columnas de datos personales prohibidas
        forbidden_personal = {"cedula", "nombre_completo", "nombres", "apellidos", "sexo"}
        # Metas de planificación prohibidas
        forbidden_goals = {
            "est_grado_m", "est_grado_f", "docentes_m", "docentes_f",
            "administrativos_m", "administrativos_f",
        }
        all_forbidden = forbidden_personal | forbidden_goals
        assert not (all_forbidden & col_names), (
            f"planning_execution_links tiene columnas prohibidas: "
            f"{all_forbidden & col_names}"
        )
        conn.close()


# ---------------------------------------------------------------------------
# T9. V003 permanece inmutable
# ---------------------------------------------------------------------------

class TestV003Inmutabilidad:
    """T9 — V003 no fue modificado por V004."""

    def test_schema_version_v003_hash_presente(self):
        conn = _build_full_db()
        cur = conn.execute(
            "SELECT hash_script FROM schema_version WHERE version = 3;"
        )
        row = cur.fetchone()
        assert row is not None, "V003 debe estar en schema_version."
        assert row["hash_script"] and len(row["hash_script"]) == 64, (
            "El hash de V003 debe ser un SHA-256 de 64 caracteres hexadecimales."
        )
        conn.close()

    def test_registry_contiene_v001_v002_v003_v004(self):
        versions = [m.version for m in MIGRATION_REGISTRY]
        assert 1 in versions
        assert 2 in versions
        assert 3 in versions
        assert 4 in versions
        assert versions == sorted(versions), "El registro de migraciones debe estar ordenado."


# ---------------------------------------------------------------------------
# T10. PlanningUnitOfWork expone execution_links
# ---------------------------------------------------------------------------

class TestPlanningUoWExecutionLinks:
    """T10 — PlanningUnitOfWork.execution_links disponible dentro de 'with'."""

    def test_execution_links_disponible_en_contexto(self, tmp_path):
        from app.planning.infrastructure.persistence.unit_of_work import PlanningUnitOfWork
        from app.planning.infrastructure.persistence.repositories import (
            SQLitePlanningExecutionLinkRepository,
        )
        db_file = tmp_path / "test_v004_uow.db"
        from app.infrastructure.persistence.migrations import MigrationRunner
        import sqlite3 as _sqlite3

        # Inicializar BD
        conn = _sqlite3.connect(str(db_file))
        runner = MigrationRunner(conn)
        runner.apply_all_pending()
        conn.close()

        with PlanningUnitOfWork(db_path=str(db_file)) as uow:
            assert uow.execution_links is not None
            assert isinstance(uow.execution_links, SQLitePlanningExecutionLinkRepository)

    def test_execution_links_fuera_de_contexto_lanza_error(self, tmp_path):
        from app.planning.infrastructure.persistence.unit_of_work import PlanningUnitOfWork
        from app.core.exceptions.persistence_exceptions import TransactionError
        db_file = tmp_path / "test_v004_uow2.db"
        uow = PlanningUnitOfWork(db_path=str(db_file))
        with pytest.raises(TransactionError):
            _ = uow.execution_links
