"""tests.test_review_historical_protection

Pruebas estrictas de preservación e inviolabilidad patrimonial (Fase 29.22.1).
Valida:
- Los 32 registros históricos de M5 (es_historico_preexistente = 1):
  1. NUNCA aparecen en COLA_REVISION.
  2. NUNCA pueden ser consultados para revisión pericial.
  3. NUNCA pueden ser resueltos por el módulo de revisión.
  4. NUNCA son alterados ni destruidos en SQLite ni en las matrices.
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
from app.review.application.service import ReviewQueueApplicationService
from app.review.domain.enums import EstamentoInstitucional, ReviewDecisionType
from app.review.domain.exceptions import HistoricalDataProtectionError
from app.review.domain.models import ReviewDecision
from app.review.infrastructure.sqlite_review_repository import SQLiteReviewQueueRepository


@pytest.fixture
def db_con_32_historicos():
    """Genera una base de datos de pruebas poblada con exactamente 32 registros históricos M5."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_hist_protection.db"
        config = DatabaseConfig(db_path=db_path)
        mgr = SQLiteConnectionManager(config)
        conn = mgr.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending()
        finally:
            conn.close()

        active_conn = mgr.get_connection()
        act_repo = SQLiteActividadRepository(active_conn)
        per_repo = SQLitePersonaRepository(active_conn)
        part_repo = SQLiteParticipacionRepository(active_conn)

        # 1. Actividad histórica institucional
        act = Activity(
            id_actividad="act-historica-m5",
            nombre_actividad_original="Registro Histórico Patrimonial M5",
            fecha_inicio_texto="2025-01-01",
            lugar="Bluefields",
        )
        act_repo.save(act)

        # 2. Insertar exactamente 32 personas y participaciones históricas
        for i in range(1, 33):
            pid = f"per-hist-{i:03d}"
            part_id = f"part-hist-{i:03d}"

            p = Person(
                id_persona_interno=pid,
                nombre_completo=f"PROTAGONISTA HISTORICO {i:02d}",
                nombres=f"PROTAGONISTA {i:02d}",
                apellidos="HISTORICO",
                cedula=f"601-010190-{i:04d}A",
                sexo_original="F" if i % 2 == 0 else "M",
                sexo_normalizado="F" if i % 2 == 0 else "M",
            )
            per_repo.save(p)

            # Invariable: es_historico_preexistente = 1
            part = Participation(
                id_participacion=part_id,
                id_actividad="act-historica-m5",
                id_persona=pid,
                categoria_participacion="BENEFICIADO",
                matriz_destino="M5",
                requiere_revision=False,
                motivo_revision=None,
                es_historico_preexistente=1,
            )
            part_repo.save(part)

        # 3. Insertar 1 participación operativa que SÍ está en COLA_REVISION
        p_op = Person(
            id_persona_interno="per-operativa-01",
            nombre_completo="PARTICIPANTE OPERATIVO DUDOSO",
            nombres="PARTICIPANTE",
            apellidos="OPERATIVO",
            cedula=None,
            sexo_original="M",
            sexo_normalizado="M",
        )
        per_repo.save(p_op)

        part_op = Participation(
            id_participacion="part-operativa-01",
            id_actividad="act-historica-m5",
            id_persona="per-operativa-01",
            categoria_participacion="DESCONOCIDO",
            matriz_destino="COLA_REVISION",
            requiere_revision=True,
            motivo_revision="Estamento no determinable",
            es_historico_preexistente=0,
        )
        part_repo.save(part_op)

        yield active_conn
        active_conn.close()


def test_32_historicos_m5_nunca_aparecen_en_cola_revision(db_con_32_historicos):
    """Verifica que de los 33 registros en base de datos, solo el operativo aparece en la cola."""
    repo = SQLiteReviewQueueRepository(db_con_32_historicos)
    service = ReviewQueueApplicationService(repo)

    casos = service.listar_casos_pendientes()
    assert len(casos) == 1
    assert casos[0].id_caso == "part-operativa-01"

    # Verificar exhaustivamente que NINGUNO de los 32 históricos aparece
    ids_en_bandeja = {c.id_caso for c in casos}
    for i in range(1, 33):
        hist_id = f"part-hist-{i:03d}"
        assert hist_id not in ids_en_bandeja, f"El registro histórico {hist_id} apareció indebidamente en la cola."


def test_32_historicos_m5_bloqueados_en_detalle(db_con_32_historicos):
    """Verifica que solicitar detalle de cualquier histórico M5 lance HistoricalDataProtectionError."""
    repo = SQLiteReviewQueueRepository(db_con_32_historicos)
    service = ReviewQueueApplicationService(repo)

    for i in (1, 15, 32):
        hist_id = f"part-hist-{i:03d}"
        with pytest.raises(HistoricalDataProtectionError):
            service.obtener_detalle_caso(hist_id)


def test_32_historicos_m5_bloqueados_en_resolucion(db_con_32_historicos):
    """Verifica que intentar resolver cualquier histórico M5 sea rechazado inmediatamente."""
    repo = SQLiteReviewQueueRepository(db_con_32_historicos)
    service = ReviewQueueApplicationService(repo)

    for i in (1, 16, 32):
        hist_id = f"part-hist-{i:03d}"
        with pytest.raises(HistoricalDataProtectionError):
            service.resolver_estamento(
                id_participacion=hist_id,
                nuevo_estamento="ESTUDIANTE",
                justificacion="Intento prohibido de resolución sobre histórico",
                usuario="operador_malicioso",
            )


def test_32_historicos_m5_permanecen_exactamente_intactos_tras_resolucion_operativa(db_con_32_historicos):
    """Verifica que resolver el registro operativo no altera en lo más mínimo los 32 históricos."""
    repo = SQLiteReviewQueueRepository(db_con_32_historicos)
    service = ReviewQueueApplicationService(repo)

    # Estado previo de los 32 históricos
    cursor = db_con_32_historicos.cursor()
    cursor.execute("SELECT COUNT(*) FROM participacion WHERE es_historico_preexistente = 1;")
    assert cursor.fetchone()[0] == 32

    cursor.execute(
        "SELECT id_participacion, estamento_declarado, matriz_destino, requiere_revision FROM participacion WHERE es_historico_preexistente = 1 ORDER BY id_participacion;"
    )
    historicos_antes = cursor.fetchall()

    # Resolver el caso operativo
    res = service.resolver_estamento(
        id_participacion="part-operativa-01",
        nuevo_estamento="BENEFICIADO",
        justificacion="Acreditado como beneficiario comunitario",
        usuario="operador_bicu",
    )
    assert res.exito is True
    assert res.matriz_destino == "M5"

    # Verificar que los 32 históricos siguen siendo exactamente 32 y con los mismos valores celda por celda
    cursor.execute("SELECT COUNT(*) FROM participacion WHERE es_historico_preexistente = 1;")
    assert cursor.fetchone()[0] == 32

    cursor.execute(
        "SELECT id_participacion, estamento_declarado, matriz_destino, requiere_revision FROM participacion WHERE es_historico_preexistente = 1 ORDER BY id_participacion;"
    )
    historicos_despues = cursor.fetchall()

    for r_antes, r_despues in zip(historicos_antes, historicos_despues):
        assert r_antes["id_participacion"] == r_despues["id_participacion"]
        assert r_antes["estamento_declarado"] == r_despues["estamento_declarado"]
        assert r_antes["matriz_destino"] == r_despues["matriz_destino"]
        assert r_antes["requiere_revision"] == r_despues["requiere_revision"]
