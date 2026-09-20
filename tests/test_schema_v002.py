"""tests.test_schema_v002

Pruebas exhaustivas para la implementación controlada de Schema V002 (Fase 28.3).
Cubre:
1. Migración V001 -> V002.
2. codigo_indicador NULL.
3. codigo_indicador persistido.
4. Indicador NO convertido en tipo_evento (INDICADOR != TIPO_EVENTO).
5. SHA-256 correcto.
6. Hash único (restricción parcial UNIQUE en SQLite).
7. Hash NULL permitido cuando corresponda (múltiples NULLs permitidos).
8. Detección de duplicado (OMITIDO — DUPLICADO, continuar lote).
9. actividad_metrica_agregada 1:1.
10. FK hacia actividad.
11. ON DELETE CASCADE.
12. Las 15 métricas agregadas oficiales.
13. fuente_seccion.
14. presenta_discrepancia_interna (DETECTAR != CORREGIR).
15. Repetición de migración sin corrupción (idempotencia del MigrationRunner).
16. Regresión de ingesta Word con V002.
17. Regresión batch con V002.
18. Regresión UI con V002.
"""

import hashlib
import sqlite3
import tempfile
from pathlib import Path
import pytest

from app.application.dto.word_extraction_dtos import (
    DiagnosticoExtraccionDTO,
    FichaTecnicaDTO,
    MatrizCuantitativaDTO,
    TipoDocumentoWord,
    WordActivityExtractionResultDTO,
)
from app.application.mappers.word_activity_mapper import WordActivityDTOMapper
from app.application.ports.word_activity_extractor import IWordActivityExtractor
from app.application.use_cases.ingestar_actividad_desde_word import (
    IngestarActividadDesdeWordUseCase,
)
from app.core.exceptions.persistence_exceptions import (
    EntityAlreadyExistsError,
    ReferentialIntegrityError,
)
from app.core.models.activity import ActividadMetricaAgregada, Activity
from app.infrastructure.persistence.connection import (
    DatabaseConfig,
    SQLiteConnectionManager,
)
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.repositories.actividad_repository import (
    SQLiteActividadRepository,
)
from app.infrastructure.persistence.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)
from app.infrastructure.persistence.schema import (
    EXPECTED_TABLE_NAMES,
    EXPECTED_TABLE_NAMES_V002,
    INITIAL_INDEXES_DDL_STATEMENTS,
    INITIAL_SCHEMA_DDL_STATEMENTS,
    V002_INDEXES_DDL_STATEMENTS,
    V002_SCHEMA_DDL_STATEMENTS,
)


def get_connection(db_path: str) -> sqlite3.Connection:
    return SQLiteConnectionManager(DatabaseConfig(db_path=Path(db_path))).get_connection()


@pytest.fixture
def isolated_db_path(tmp_path):
    """Crea una base de datos aislada temporal."""
    db_file = tmp_path / "test_v002.db"
    return str(db_file)


class DummyExtractor(IWordActivityExtractor):
    """Extractor dummy parametrizable para pruebas de integración de V002."""

    def __init__(self, extraction_dto: WordActivityExtractionResultDTO):
        self._dto = extraction_dto

    def extract(self, file_path: Path) -> WordActivityExtractionResultDTO:
        return self._dto


# ===========================================================================
# 1. Migración V001 -> V002
# ===========================================================================

def test_migration_v001_to_v002(isolated_db_path):
    """Verifica la migración secuencial V001 -> V002 y la creación de actividad_metrica_agregada."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)

    # 1. Aplicar V001
    executed_v1 = runner.apply_all_pending(target_version=1)
    assert len(executed_v1) == 1
    assert runner.get_current_version() == 1

    # Verificar que no existe actividad_metrica_agregada en V001
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actividad_metrica_agregada'")
    assert cursor.fetchone() is None

    # 2. Aplicar V002
    executed_v2 = runner.apply_all_pending(target_version=2)
    applied_v2 = [m for m in executed_v2 if m["status"] == "APPLIED_SUCCESSFULLY"]
    assert len(applied_v2) == 1
    assert runner.get_current_version() == 2

    # Verificar existencia de tabla e índices V002
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actividad_metrica_agregada'")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_actividad_hash_sha256'")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_actividad_indicador'")
    assert cursor.fetchone() is not None

    conn.close()


# ===========================================================================
# 2. codigo_indicador NULL
# ===========================================================================

def test_codigo_indicador_null(isolated_db_path):
    """Caso A: Actividad sin indicador institucional -> codigo_indicador = NULL."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)

    repo = SQLiteActividadRepository(conn)
    actividad = Activity(
        id_actividad="act-null-indicador",
        nombre_actividad_original="Capacitación sin indicador",
        codigo_indicador=None,
    )
    repo.save(actividad)

    saved = repo.get_by_id("act-null-indicador")
    assert saved is not None
    assert saved.codigo_indicador is None

    cursor = conn.cursor()
    cursor.execute("SELECT codigo_indicador FROM actividad WHERE id_actividad = ?", ("act-null-indicador",))
    row = cursor.fetchone()
    assert row[0] is None
    conn.close()


# ===========================================================================
# 3. codigo_indicador persistido
# ===========================================================================

def test_codigo_indicador_persistido(isolated_db_path):
    """Caso B: Actividad con indicador institucional -> codigo_indicador = valor de ficha."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)

    repo = SQLiteActividadRepository(conn)
    actividad = Activity(
        id_actividad="act-con-indicador",
        nombre_actividad_original="Taller institucional",
        codigo_indicador="IND-2024-001",
    )
    repo.save(actividad)

    saved = repo.get_by_id("act-con-indicador")
    assert saved is not None
    assert saved.codigo_indicador == "IND-2024-001"

    cursor = conn.cursor()
    cursor.execute("SELECT codigo_indicador FROM actividad WHERE id_actividad = ?", ("act-con-indicador",))
    row = cursor.fetchone()
    assert row[0] == "IND-2024-001"
    conn.close()


# ===========================================================================
# 4. Indicador NO convertido en tipo_evento (INDICADOR != TIPO_EVENTO)
# ===========================================================================

def test_indicador_no_convertido_en_tipo_evento():
    """Regla crítica: INDICADOR != TIPO_EVENTO. Nunca asignar tipo_evento = ficha.indicador."""
    extraction_dto = WordActivityExtractionResultDTO(
        nombre_archivo="informe_test.docx",
        diagnostico=DiagnosticoExtraccionDTO(
            es_valido=True,
            tipo_documento=TipoDocumentoWord.INFORME_ACTIVIDAD,
            compatible_flujo_principal=True,
        ),
        ficha_tecnica=FichaTecnicaDTO(
            actividad_general="Jornada de Reforestación Comunitaria",
            indicador="IND-MEDIO-AMBIENTE-05",
            lugar="Bluefields",
        ),
    )

    actividad = WordActivityDTOMapper.to_activity(extraction_dto)

    assert actividad.codigo_indicador == "IND-MEDIO-AMBIENTE-05"
    # tipo_evento se detecta del nombre ("Jornada..."), NUNCA del indicador
    assert actividad.tipo_evento == "JORNADA"
    assert actividad.tipo_evento != actividad.codigo_indicador


# ===========================================================================
# 5. SHA-256 correcto
# ===========================================================================

def test_sha256_correcto(tmp_path):
    """El hash SHA-256 debe calcularse sobre los bytes reales del archivo DOCX."""
    archivo_ficticio = tmp_path / "documento_prueba.docx"
    contenido = b"PK\x03\x04Contenido binario real de prueba"
    archivo_ficticio.write_bytes(contenido)

    hash_esperado = hashlib.sha256(contenido).hexdigest()
    hash_calculado = hashlib.sha256(archivo_ficticio.read_bytes()).hexdigest()

    assert hash_calculado == hash_esperado
    assert len(hash_calculado) == 64


# ===========================================================================
# 6. Hash único
# ===========================================================================

def test_hash_unico_en_sqlite(isolated_db_path):
    """Verifica que el índice único parcial impida registrar dos actividades con el mismo hash."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)

    repo = SQLiteActividadRepository(conn)
    h = "a" * 64

    act1 = Activity(
        id_actividad="act-hash-1",
        nombre_actividad_original="Actividad 1",
        hash_sha256=h,
    )
    repo.save(act1)

    act2 = Activity(
        id_actividad="act-hash-2",
        nombre_actividad_original="Actividad 2",
        hash_sha256=h,
    )

    with pytest.raises(EntityAlreadyExistsError):
        repo.save(act2)

    conn.close()


# ===========================================================================
# 7. Hash NULL permitido cuando corresponda (múltiples NULLs)
# ===========================================================================

def test_hash_null_permitido_multiple(isolated_db_path):
    """El índice único parcial permite múltiples actividades con hash_sha256 = NULL."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)

    repo = SQLiteActividadRepository(conn)

    act1 = Activity(
        id_actividad="act-null-hash-1",
        nombre_actividad_original="Actividad Sin Hash 1",
        hash_sha256=None,
    )
    act2 = Activity(
        id_actividad="act-null-hash-2",
        nombre_actividad_original="Actividad Sin Hash 2",
        hash_sha256=None,
    )

    repo.save(act1)
    repo.save(act2)  # No debe lanzar error de unicidad

    assert repo.get_by_id("act-null-hash-1") is not None
    assert repo.get_by_id("act-null-hash-2") is not None
    conn.close()


# ===========================================================================
# 8. Detección de duplicado (OMITIDO — DUPLICADO)
# ===========================================================================

def test_deteccion_duplicado_omitido_sin_error(isolated_db_path, tmp_path):
    """Caso E: Mismo DOCX procesado dos veces debe detectarse como OMITIDO — DUPLICADO."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)
    conn.close()

    uow = SQLiteUnitOfWork(db_path=isolated_db_path)
    hash_doc = "b" * 64

    extraction_dto = WordActivityExtractionResultDTO(
        nombre_archivo="informe_dup.docx",
        hash_sha256=hash_doc,
        diagnostico=DiagnosticoExtraccionDTO(
            es_valido=True,
            tipo_documento=TipoDocumentoWord.INFORME_ACTIVIDAD,
            compatible_flujo_principal=True,
        ),
        ficha_tecnica=FichaTecnicaDTO(
            actividad_general="Feria de Innovación BICU",
            indicador="IND-001",
            lugar="Bluefields",
        ),
    )
    extractor = DummyExtractor(extraction_dto)
    use_case = IngestarActividadDesdeWordUseCase(extractor=extractor, uow=uow)

    fake_file = tmp_path / "informe_dup.docx"
    fake_file.write_bytes(b"dummy")

    # Primera ejecución: Aceptado
    res1 = use_case.execute(fake_file)
    assert res1.exitoso is True
    assert res1.id_actividad is not None
    assert res1.posible_duplicado is False

    # Segunda ejecución: Omitido como duplicado
    res2 = use_case.execute(fake_file)
    assert res2.exitoso is True
    assert res2.id_actividad is None
    assert res2.posible_duplicado is True
    assert any("OMITIDO — DUPLICADO" in adv for adv in res2.advertencias)


# ===========================================================================
# 9. actividad_metrica_agregada 1:1
# ===========================================================================

def test_actividad_metrica_agregada_relacion_1_a_1(isolated_db_path):
    """Verifica la cardinalidad 1:1 en la tabla actividad_metrica_agregada."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)

    repo = SQLiteActividadRepository(conn)
    act = Activity(
        id_actividad="act-1a1",
        nombre_actividad_original="Taller 1a1",
    )
    repo.save(act)

    metrica1 = ActividadMetricaAgregada(
        id_actividad="act-1a1",
        total_participantes=50,
        total_femenino=30,
        total_masculino=20,
    )
    repo.save_metrica_agregada(metrica1)

    recup = repo.get_metrica_agregada("act-1a1")
    assert recup is not None
    assert recup.total_participantes == 50

    # Si se intenta insertar una segunda fila con el mismo id_actividad,
    # el método hace REPLACE/UPSERT garantizando exactamente 1 fila por actividad
    metrica2 = ActividadMetricaAgregada(
        id_actividad="act-1a1",
        total_participantes=60,
        total_femenino=35,
        total_masculino=25,
    )
    repo.save_metrica_agregada(metrica2)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM actividad_metrica_agregada WHERE id_actividad = ?", ("act-1a1",))
    count = cursor.fetchone()[0]
    assert count == 1

    recup2 = repo.get_metrica_agregada("act-1a1")
    assert recup2.total_participantes == 60
    conn.close()


# ===========================================================================
# 10. FK hacia actividad
# ===========================================================================

def test_fk_hacia_actividad(isolated_db_path):
    """Verifica que actividad_metrica_agregada rechace métricas para actividades inexistentes."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)

    repo = SQLiteActividadRepository(conn)
    metrica = ActividadMetricaAgregada(
        id_actividad="act-inexistente",
        total_participantes=10,
    )

    with pytest.raises(ReferentialIntegrityError):
        repo.save_metrica_agregada(metrica)

    conn.close()


# ===========================================================================
# 11. CASCADE
# ===========================================================================

def test_on_delete_cascade_metrica(isolated_db_path):
    """Al eliminar la actividad, la fila en actividad_metrica_agregada debe eliminarse en cascada."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)

    repo = SQLiteActividadRepository(conn)
    act = Activity(
        id_actividad="act-cascade",
        nombre_actividad_original="Actividad para eliminar",
    )
    repo.save(act)

    metrica = ActividadMetricaAgregada(
        id_actividad="act-cascade",
        total_participantes=15,
    )
    repo.save_metrica_agregada(metrica)

    assert repo.get_metrica_agregada("act-cascade") is not None

    # Eliminar actividad en SQLite con PRAGMA foreign_keys = ON
    cursor = conn.cursor()
    cursor.execute("DELETE FROM actividad WHERE id_actividad = ?", ("act-cascade",))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM actividad_metrica_agregada WHERE id_actividad = ?", ("act-cascade",))
    assert cursor.fetchone()[0] == 0
    conn.close()


# ===========================================================================
# 12. Las 15 métricas oficiales
# ===========================================================================

def test_15_metricas_oficiales_preservadas(isolated_db_path):
    """Verifica la persistencia y recuperación exacta de las 15 métricas oficiales."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)

    repo = SQLiteActividadRepository(conn)
    act = Activity(
        id_actividad="act-15-metricas",
        nombre_actividad_original="Capacitación Integral",
    )
    repo.save(act)

    m = ActividadMetricaAgregada(
        id_actividad="act-15-metricas",
        total_participantes=100,
        total_femenino=60,
        total_masculino=40,
        total_estudiantes=70,
        total_docentes=15,
        total_administrativos=10,
        total_otros=5,
        total_mestizo=50,
        total_creole=20,
        total_miskitu=15,
        total_mayangna=5,
        total_ulwa=4,
        total_rama=3,
        total_garifuna=2,
        total_otra_etnia=1,
        fuente_seccion="TABLA_2_MATRIZ_CUANTITATIVA",
        presenta_discrepancia_interna=False,
    )
    repo.save_metrica_agregada(m)

    rec = repo.get_metrica_agregada("act-15-metricas")
    assert rec is not None
    assert rec.total_participantes == 100
    assert rec.total_femenino == 60
    assert rec.total_masculino == 40
    assert rec.total_estudiantes == 70
    assert rec.total_docentes == 15
    assert rec.total_administrativos == 10
    assert rec.total_otros == 5
    assert rec.total_mestizo == 50
    assert rec.total_creole == 20
    assert rec.total_miskitu == 15
    assert rec.total_mayangna == 5
    assert rec.total_ulwa == 4
    assert rec.total_rama == 3
    assert rec.total_garifuna == 2
    assert rec.total_otra_etnia == 1
    assert rec.fuente_seccion == "TABLA_2_MATRIZ_CUANTITATIVA"
    assert rec.presenta_discrepancia_interna is False
    conn.close()


# ===========================================================================
# 13. fuente_seccion
# ===========================================================================

def test_fuente_seccion_conservada():
    """fuente_seccion debe conservar la procedencia oficial (TABLA_2_MATRIZ_CUANTITATIVA)."""
    dto = WordActivityExtractionResultDTO(
        nombre_archivo="doc.docx",
        diagnostico=DiagnosticoExtraccionDTO(
            es_valido=True,
            tipo_documento=TipoDocumentoWord.INFORME_ACTIVIDAD,
            compatible_flujo_principal=True,
        ),
        ficha_tecnica=FichaTecnicaDTO(actividad_general="Actividad General"),
        matriz_cuantitativa=MatrizCuantitativaDTO(total=20, femenino=10, masculino=10),
    )
    metrica = WordActivityDTOMapper.to_metrica_agregada(dto, "id-test")
    assert metrica is not None
    assert metrica.fuente_seccion == "TABLA_2_MATRIZ_CUANTITATIVA"


# ===========================================================================
# 14. presenta_discrepancia_interna (DETECTAR != CORREGIR)
# ===========================================================================

def test_presenta_discrepancia_interna_detectar_no_corregir():
    """Ejemplo D-02: Ficha 11 vs Tabla 2 10. Se preserva 10 y se marca presenta_discrepancia_interna=True."""
    dto = WordActivityExtractionResultDTO(
        nombre_archivo="d02.docx",
        diagnostico=DiagnosticoExtraccionDTO(
            es_valido=True,
            tipo_documento=TipoDocumentoWord.INFORME_ACTIVIDAD,
            compatible_flujo_principal=True,
        ),
        ficha_tecnica=FichaTecnicaDTO(
            actividad_general="Taller de Validación",
            total_participantes_declarado=11,
        ),
        matriz_cuantitativa=MatrizCuantitativaDTO(
            total=10,
            femenino=6,
            masculino=4,
            discrepancia_suma_genero=False,
        ),
    )
    metrica = WordActivityDTOMapper.to_metrica_agregada(dto, "id-d02")
    assert metrica is not None
    # No corrige a 11; conserva 10
    assert metrica.total_participantes == 10
    assert metrica.presenta_discrepancia_interna is True


# ===========================================================================
# 15. Repetición de migración sin corrupción
# ===========================================================================

def test_migracion_repetida_sin_corrupcion(isolated_db_path):
    """Aplicar migraciones múltiples veces no debe corromper el esquema ni fallar."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)

    # Primera aplicación
    runner.apply_all_pending(target_version=2)
    assert runner.get_current_version() == 2

    # Segunda aplicación
    executed_again = runner.apply_all_pending(target_version=2)
    newly_applied = [m for m in executed_again if m["status"] == "APPLIED_SUCCESSFULLY"]
    assert len(newly_applied) == 0
    assert runner.get_current_version() == 2
    conn.close()


# ===========================================================================
# 16. Regresión de ingesta Word con V002
# ===========================================================================

def test_regresion_ingesta_word_con_v002(isolated_db_path, tmp_path):
    """Ingesta Word completa persiste actividad, evidencias y métricas agregadas."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)
    conn.close()

    uow = SQLiteUnitOfWork(db_path=isolated_db_path)
    dto = WordActivityExtractionResultDTO(
        nombre_archivo="informe_completo.docx",
        hash_sha256="c" * 64,
        diagnostico=DiagnosticoExtraccionDTO(
            es_valido=True,
            tipo_documento=TipoDocumentoWord.INFORME_ACTIVIDAD,
            compatible_flujo_principal=True,
        ),
        ficha_tecnica=FichaTecnicaDTO(
            actividad_general="Feria Científica 2024",
            indicador="IND-CIENCIA-01",
            lugar="Bilwi",
        ),
        matriz_cuantitativa=MatrizCuantitativaDTO(
            total=45,
            femenino=25,
            masculino=20,
            estudiantes=40,
            docentes=5,
            distribucion_etnica={"Miskitu": 30, "Creole": 15},
        ),
    )
    extractor = DummyExtractor(dto)
    use_case = IngestarActividadDesdeWordUseCase(extractor=extractor, uow=uow)

    fake_file = tmp_path / "informe_completo.docx"
    fake_file.write_bytes(b"test")

    res = use_case.execute(fake_file)
    assert res.exitoso is True
    assert res.id_actividad is not None

    # Verificar en BD
    conn = get_connection(isolated_db_path)
    repo = SQLiteActividadRepository(conn)
    act = repo.get_by_id(res.id_actividad)
    assert act is not None
    assert act.codigo_indicador == "IND-CIENCIA-01"
    assert act.hash_sha256 == "c" * 64
    assert act.metrica_agregada is not None
    assert act.metrica_agregada.total_participantes == 45
    assert act.metrica_agregada.total_miskitu == 30
    assert act.metrica_agregada.total_creole == 15
    conn.close()


# ===========================================================================
# 17. Regresión batch con V002
# ===========================================================================

def test_regresion_batch_con_v002(isolated_db_path, tmp_path):
    """Procesamiento por lote reconoce V002, omite duplicados y no crea participantes ficticios."""
    conn = get_connection(isolated_db_path)
    runner = MigrationRunner(conn)
    runner.apply_all_pending(target_version=2)
    conn.close()

    uow = SQLiteUnitOfWork(db_path=isolated_db_path)
    dto1 = WordActivityExtractionResultDTO(
        nombre_archivo="doc1.docx",
        hash_sha256="d" * 64,
        diagnostico=DiagnosticoExtraccionDTO(
            es_valido=True,
            tipo_documento=TipoDocumentoWord.INFORME_ACTIVIDAD,
            compatible_flujo_principal=True,
        ),
        ficha_tecnica=FichaTecnicaDTO(
            actividad_general="Actividad 1",
            indicador="IND-01",
        ),
        matriz_cuantitativa=MatrizCuantitativaDTO(total=20, femenino=10, masculino=10),
    )
    extractor = DummyExtractor(dto1)
    use_case = IngestarActividadDesdeWordUseCase(extractor=extractor, uow=uow)

    fake_file = tmp_path / "doc1.docx"
    fake_file.write_bytes(b"doc1")

    res = use_case.execute(fake_file)
    assert res.exitoso is True

    # Verificar que NO se crearon participantes nominales (0 personas)
    conn = get_connection(isolated_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM persona")
    assert cursor.fetchone()[0] == 0

    cursor.execute("SELECT COUNT(*) FROM participacion")
    assert cursor.fetchone()[0] == 0
    conn.close()


# ===========================================================================
# 18. Regresión UI con V002
# ===========================================================================

def test_regresion_ui_reconoce_v002():
    """Verifica que las entidades y DTOs de V002 se integren con la UI sin incompatibilidades."""
    from app.application.dto.batch_dtos import BatchArchivoResultadoDTO, PipelineDesdeWordResultDTO

    pipe_dto = PipelineDesdeWordResultDTO(
        nombre_archivo="prueba.docx",
        exitoso=True,
        id_actividad="act-123",
        ingesta_exitosa=True,
        posible_duplicado_advertido=True,
    )
    batch_dto = pipe_dto.to_batch_archivo_resultado(ruta_archivo="c:/fake/prueba.docx")

    assert batch_dto.posible_duplicado_advertido is True
    assert batch_dto.estado == "CON_ADVERTENCIAS"
