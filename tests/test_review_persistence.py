"""tests.test_review_persistence

Pruebas de persistencia, atomicidad y auditoría para la Cola de Revisión (Fase 29.22.1).
Valida:
- Aislamiento e inviolabilidad de los 32 registros históricos M5.
- Transaccionalidad atómica (COMMIT / ROLLBACK).
- Inserción mandatoria en auditoria_evento con tipo_operacion = 'DISCREPANCY_RESOLVE'.
- Actualización unívoca de participacion (matriz_destino, requiere_revision = 0).
"""

from pathlib import Path
import tempfile
import pytest

from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.repositories.actividad_repository import SQLiteActividadRepository
from app.infrastructure.persistence.repositories.participacion_repository import SQLiteParticipacionRepository
from app.infrastructure.persistence.repositories.persona_repository import SQLitePersonaRepository
from app.review.domain.enums import EstamentoInstitucional, ReviewDecisionType
from app.review.domain.exceptions import HistoricalDataProtectionError, InvalidDecisionError
from app.review.domain.models import ReviewDecision
from app.review.infrastructure.sqlite_review_repository import SQLiteReviewQueueRepository


@pytest.fixture
def temp_review_db():
    """Crea una base de datos SQLite temporal con el esquema oficial V004."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_review.db"
        config = DatabaseConfig(db_path=db_path)
        mgr = SQLiteConnectionManager(config)
        conn = mgr.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending()
        finally:
            conn.close()

        active_conn = mgr.get_connection()
        yield active_conn
        active_conn.close()


def seed_test_data(conn):
    """Inserta datos de prueba: actividad, personas y participaciones (normales e históricas)."""
    act_repo = SQLiteActividadRepository(conn)
    per_repo = SQLitePersonaRepository(conn)
    part_repo = SQLiteParticipacionRepository(conn)

    # 1. Actividad de prueba
    act = Activity(
        id_actividad="act-rev-01",
        nombre_actividad_original="Taller de Emprendimiento e Innovación",
        fecha_inicio_texto="2026-03-15",
        lugar="BICU Bluefields",
    )
    act_repo.save(act)

    # 2. Persona normal no resuelta
    p1 = Person(
        id_persona_interno="per-rev-01",
        nombre_completo="CARLOS ALBERTO GOMEZ",
        nombres="CARLOS ALBERTO",
        apellidos="GOMEZ",
        cedula=None,  # RN-C04 NULL preservado
        sexo_original="M",
        sexo_normalizado="M",
    )
    per_repo.save(p1)

    # 3. Persona candidata existente para matching
    p2 = Person(
        id_persona_interno="per-rev-02",
        nombre_completo="CARLOS GOMEZ MARTINEZ",
        nombres="CARLOS",
        apellidos="GOMEZ MARTINEZ",
        cedula="601-150385-0001A",
        sexo_original="M",
        sexo_normalizado="M",
    )
    per_repo.save(p2)

    # 4. Persona histórica M5 (patrimonial protegida)
    p_hist = Person(
        id_persona_interno="per-hist-01",
        nombre_completo="PROTAGONISTA HISTORICO M5",
        nombres="PROTAGONISTA",
        apellidos="HISTORICO M5",
        cedula="601-010190-0002B",
        sexo_original="F",
        sexo_normalizado="F",
    )
    per_repo.save(p_hist)

    # 5. Participación pendiente en COLA_REVISION
    part_rev = Participation(
        id_participacion="part-rev-01",
        id_actividad="act-rev-01",
        id_persona="per-rev-01",
        categoria_participacion="DESCONOCIDO",
        matriz_destino="COLA_REVISION",
        requiere_revision=True,
        motivo_revision="Estamento no determinable institucionalmente",
        es_historico_preexistente=0,
    )
    part_repo.save(part_rev)

    # 6. Participación histórica M5 (INV-03 protegida)
    part_hist = Participation(
        id_participacion="part-hist-01",
        id_actividad="act-rev-01",
        id_persona="per-hist-01",
        categoria_participacion="BENEFICIADO",
        matriz_destino="M5",
        requiere_revision=False,
        motivo_revision=None,
        es_historico_preexistente=1,
    )
    part_repo.save(part_hist)


def test_list_pending_cases_excluye_historico_m5(temp_review_db):
    """Valida que los registros históricos nunca aparezcan en la bandeja de revisión."""
    seed_test_data(temp_review_db)
    repo = SQLiteReviewQueueRepository(temp_review_db)

    casos = repo.list_pending_cases()
    assert len(casos) == 1
    assert casos[0].id_caso == "part-rev-01"
    assert casos[0].nombre_persona == "CARLOS ALBERTO GOMEZ"

    # Verificar que el histórico M5 no está en la lista
    ids_en_cola = [c.id_caso for c in casos]
    assert "part-hist-01" not in ids_en_cola


def test_get_case_detail_bloquea_registro_historico(temp_review_db):
    """Valida que consultar un registro histórico lance HistoricalDataProtectionError."""
    seed_test_data(temp_review_db)
    repo = SQLiteReviewQueueRepository(temp_review_db)

    with pytest.raises(HistoricalDataProtectionError):
        repo.get_case_detail("part-hist-01")


def test_resolucion_estamento_atomica_y_auditoria(temp_review_db):
    """Valida que confirmar estamento actualice la participación y registre auditoría DISCREPANCY_RESOLVE."""
    seed_test_data(temp_review_db)
    repo = SQLiteReviewQueueRepository(temp_review_db)

    decision = ReviewDecision(
        tipo_decision=ReviewDecisionType.CONFIRMAR_ESTAMENTO,
        nuevo_estamento=EstamentoInstitucional.ESTUDIANTE,
        justificacion="Evidencia de matrícula I Semestre 2026 constatada",
        usuario_operador="operador_bicu",
        fecha_resolucion="2026-09-22T10:30:00",
    )

    resultado = repo.execute_atomic_resolution("part-rev-01", decision)
    assert resultado.exito is True
    assert resultado.matriz_destino == "M2"
    assert resultado.nuevo_estado == "RESUELTO"
    assert resultado.id_auditoria is not None

    # Verificar en base de datos la actualización de participacion
    cursor = temp_review_db.cursor()
    cursor.execute(
        "SELECT estamento_declarado, matriz_destino, requiere_revision FROM participacion WHERE id_participacion = ?;",
        ("part-rev-01",),
    )
    row = cursor.fetchone()
    assert row["estamento_declarado"] == "ESTUDIANTE"
    assert row["matriz_destino"] == "M2"
    assert row["requiere_revision"] == 0

    # Verificar registro inmutable en auditoria_evento
    cursor.execute(
        "SELECT * FROM auditoria_evento WHERE id_auditoria = ?;",
        (resultado.id_auditoria,),
    )
    aud = cursor.fetchone()
    assert aud is not None
    assert aud["tipo_operacion"] == "DISCREPANCY_RESOLVE"
    assert aud["usuario_operador"] == "operador_bicu"
    assert aud["tabla_afectada"] == "participacion"
    assert aud["id_registro_afectado"] == "part-rev-01"
    assert "ESTUDIANTE" in aud["snapshot_nuevo_json"]


def test_resolucion_identidad_nueva_cedula_valida(temp_review_db):
    """Valida que confirmar identidad con cédula válida actualice a la persona y asiente la resolución."""
    seed_test_data(temp_review_db)
    repo = SQLiteReviewQueueRepository(temp_review_db)

    decision = ReviewDecision(
        tipo_decision=ReviewDecisionType.CONFIRMAR_IDENTIDAD,
        nueva_cedula="601-100495-0003K",
        justificacion="Cédula verificada con fotocopia física",
        usuario_operador="operador_bicu",
        fecha_resolucion="2026-09-22T10:45:00",
    )

    resultado = repo.execute_atomic_resolution("part-rev-01", decision)
    assert resultado.exito is True

    cursor = temp_review_db.cursor()
    cursor.execute("SELECT cedula, estado_identidad FROM persona WHERE id_persona_interno = 'per-rev-01';")
    per_row = cursor.fetchone()
    assert per_row["cedula"] == "601-100495-0003K"
    assert per_row["estado_identidad"] == "IDENTIDAD_CONFIRMADA"


def test_resolucion_falla_si_cedula_invalida(temp_review_db):
    """Valida que una cédula inválida cause rollback y no modifique nada."""
    seed_test_data(temp_review_db)
    repo = SQLiteReviewQueueRepository(temp_review_db)

    decision = ReviewDecision(
        tipo_decision=ReviewDecisionType.CONFIRMAR_IDENTIDAD,
        nueva_cedula="1234-INVALIDA",
        justificacion="Intento con formato incorrecto",
        usuario_operador="operador_bicu",
        fecha_resolucion="2026-09-22T10:50:00",
    )

    with pytest.raises(InvalidDecisionError):
        repo.execute_atomic_resolution("part-rev-01", decision)

    # Verificar que participacion y persona permanecen intactas (ROLLBACK)
    cursor = temp_review_db.cursor()
    cursor.execute("SELECT cedula FROM persona WHERE id_persona_interno = 'per-rev-01';")
    assert cursor.fetchone()["cedula"] is None

    cursor.execute("SELECT requiere_revision FROM participacion WHERE id_participacion = 'part-rev-01';")
    assert cursor.fetchone()["requiere_revision"] == 1


def test_resolucion_no_resoluble_conserva_registro(temp_review_db):
    """Valida que MARCAR_NO_RESOLUBLE preserve la participación en COLA_REVISION con su justificación."""
    seed_test_data(temp_review_db)
    repo = SQLiteReviewQueueRepository(temp_review_db)

    decision = ReviewDecision(
        tipo_decision=ReviewDecisionType.MARCAR_NO_RESOLUBLE,
        justificacion="Imposible contactar con el participante para obtener evidencia",
        usuario_operador="operador_bicu",
        fecha_resolucion="2026-09-22T11:00:00",
    )

    resultado = repo.execute_atomic_resolution("part-rev-01", decision)
    assert resultado.exito is True
    assert resultado.nuevo_estado == "NO_RESOLUBLE"

    cursor = temp_review_db.cursor()
    cursor.execute("SELECT matriz_destino, motivo_revision FROM participacion WHERE id_participacion = 'part-rev-01';")
    row = cursor.fetchone()
    assert row["matriz_destino"] == "COLA_REVISION"
    assert "NO_RESOLUBLE" in row["motivo_revision"]


def test_listar_historial_resoluciones(temp_review_db):
    """Valida la lectura del historial forense de resoluciones desde auditoria_evento."""
    seed_test_data(temp_review_db)
    repo = SQLiteReviewQueueRepository(temp_review_db)

    decision = ReviewDecision(
        tipo_decision=ReviewDecisionType.CONFIRMAR_ESTAMENTO,
        nuevo_estamento=EstamentoInstitucional.DOCENTE,
        justificacion="Constancia de docencia horaria presentada",
        usuario_operador="operador_bicu",
        fecha_resolucion="2026-09-22T11:15:00",
    )
    repo.execute_atomic_resolution("part-rev-01", decision)

    historial = repo.list_history()
    assert len(historial) == 1
    assert historial[0].usuario_operador == "operador_bicu"
    assert historial[0].id_registro_afectado == "part-rev-01"
    assert "Constancia de docencia" in historial[0].motivo_modificacion
