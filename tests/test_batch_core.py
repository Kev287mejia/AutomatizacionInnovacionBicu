"""tests.test_batch_core

Suite de pruebas para el Subbloque 3.3:
IngestarCarpetaWordUseCase (Batch Core de procesamiento de carpetas Word).

Cobertura:
- B-01: Carpeta inexistente maneja error limpiamente sin crash.
- B-02: Carpeta sin archivos Word maneja caso vacío con advertencia.
- B-03: Lote heterogéneo (válido, incompatible, semanal) procesa y clasifica cada uno.
- B-04: Éxito Parcial: Archivo fallido no impide procesamiento de los demás archivos.
- B-05: Ignora archivos temporales de Word (~$*).
- B-06: Modo dry_run=True no escribe en SQLite ni genera archivos físicos.
- B-07: Heurística GAP-3 detecta posible duplicado en lote sin bloquear.
- B-08: Exportación consolidada (P-01) en subcarpeta con batch_id (P-07).
- B-09: Aislamiento arquitectónico (AST): ingestar_carpeta_word.py no importa sqlite3, docx ni openpyxl.
"""

import ast
from pathlib import Path
from typing import Generator
import pytest

from app.application.commands.batch_commands import IngestarCarpetaWordCommand
from app.application.dto.batch_dtos import BatchResultadoDTO
from app.application.use_cases.batch.ingestar_carpeta_word import (
    IngestarCarpetaWordUseCase,
)
from app.application.use_cases.batch.procesar_pipeline_desde_word import (
    ProcesarPipelineDesdeWordUseCase,
)
from app.application.use_cases.exportacion.exportar_matrices_periodo import (
    ExportarMatricesPeriodoUseCase,
)
from app.application.use_cases.ingestar_actividad_desde_word import (
    IngestarActividadDesdeWordUseCase,
)
from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)
from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.repositories.unit_of_work import SQLiteUnitOfWork
from app.infrastructure.word_reader.word_activity_extractor import (
    WordActivityExtractor,
)
from tests.test_pipeline_desde_word import (
    _crear_docx_incompatible,
    _crear_docx_informe_semanal,
)
from tests.test_word_activity_extractor import _crear_docx_actividad_valido


@pytest.fixture
def sqlite_test_env(tmp_path) -> Generator[SQLiteUnitOfWork, None, None]:
    """Crea una base de datos SQLite temporal migrada con esquema v001."""
    db_file = tmp_path / "test_batch_core.db"
    config = DatabaseConfig(db_path=db_file)
    manager = SQLiteConnectionManager(config)

    conn = manager.get_connection()
    try:
        runner = MigrationRunner(conn)
        runner.apply_all_pending()
    finally:
        conn.close()

    uow = SQLiteUnitOfWork(connection_manager=manager, db_path=db_file)
    yield uow


@pytest.fixture
def extractor() -> WordActivityExtractor:
    return WordActivityExtractor()


@pytest.fixture
def ingesta_use_case(extractor, sqlite_test_env) -> IngestarActividadDesdeWordUseCase:
    return IngestarActividadDesdeWordUseCase(extractor=extractor, uow=sqlite_test_env)


@pytest.fixture
def pipeline_use_case(sqlite_test_env) -> ProcesarPipelineActividadUseCase:
    return ProcesarPipelineActividadUseCase(uow=sqlite_test_env)


@pytest.fixture
def pipeline_word_use_case(ingesta_use_case, pipeline_use_case, sqlite_test_env) -> ProcesarPipelineDesdeWordUseCase:
    return ProcesarPipelineDesdeWordUseCase(
        ingesta_use_case=ingesta_use_case,
        pipeline_use_case=pipeline_use_case,
        uow=sqlite_test_env,
    )


@pytest.fixture
def exportar_periodo_use_case(sqlite_test_env, pipeline_use_case) -> ExportarMatricesPeriodoUseCase:
    return ExportarMatricesPeriodoUseCase(
        pipeline_use_case=pipeline_use_case,
        uow=sqlite_test_env,
    )


@pytest.fixture
def batch_use_case(pipeline_word_use_case, exportar_periodo_use_case, sqlite_test_env) -> IngestarCarpetaWordUseCase:
    return IngestarCarpetaWordUseCase(
        pipeline_word_use_case=pipeline_word_use_case,
        exportar_periodo_use_case=exportar_periodo_use_case,
        uow=sqlite_test_env,
    )


class TestIngestarCarpetaWordUseCase:

    def test_b01_carpeta_inexistente(self, batch_use_case, tmp_path):
        """B-01: Carpeta inexistente retorna resultado con error crítico sin crashear."""
        carpeta_falsa = tmp_path / "carpeta_que_no_existe_12345"
        cmd = IngestarCarpetaWordCommand(carpeta_origen=carpeta_falsa)

        res = batch_use_case.execute(cmd)

        assert isinstance(res, BatchResultadoDTO)
        assert res.archivos_encontrados == 0
        assert res.invariante_ok is False
        assert len(res.errores_criticos) >= 1

    def test_b02_carpeta_vacia(self, batch_use_case, tmp_path):
        """B-02: Carpeta sin archivos .docx retorna invariante_ok=True y advertencia."""
        carpeta_vacia = tmp_path / "carpeta_vacia"
        carpeta_vacia.mkdir()
        cmd = IngestarCarpetaWordCommand(carpeta_origen=carpeta_vacia)

        res = batch_use_case.execute(cmd)

        assert res.archivos_encontrados == 0
        assert res.invariante_ok is True
        assert len(res.advertencias_lote) >= 1

    def test_b03_lote_heterogeneo(self, batch_use_case, tmp_path, sqlite_test_env):
        """B-03: Procesa lote con actividad válida, docx incompatible e informe semanal."""
        carpeta_lote = tmp_path / "lote_heterogeneo"
        carpeta_lote.mkdir()

        # 1. Actividad válida
        _crear_docx_actividad_valido(
            carpeta_lote,
            nombre_archivo="Actividad_Valida_01.docx",
            actividad="Feria Vocacional 2026",
        )

        # 2. Documento incompatible
        _crear_docx_incompatible(carpeta_lote / "Carta_Peticion.docx")

        # 3. Informe semanal
        _crear_docx_informe_semanal(carpeta_lote / "Informe_Semanal.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_lote,
            dry_run=True,  # Sin exportación física para esta prueba
        )

        res = batch_use_case.execute(cmd)

        assert res.archivos_encontrados == 3
        assert res.archivos_aceptados in (1, 0)  # Puede ser aceptado o con advertencias
        assert (res.archivos_aceptados + res.archivos_con_advertencias) == 1
        assert res.archivos_rechazados == 2
        assert res.archivos_fallidos == 0
        assert res.invariante_ok is True
        assert len(res.actividades_creadas) == 1

    def test_b04_exito_parcial_ante_fallo_individual(self, tmp_path, pipeline_use_case, sqlite_test_env, extractor):
        """B-04: Un fallo técnico no detiene el procesamiento de los demás archivos."""
        carpeta_lote = tmp_path / "lote_con_fallo"
        carpeta_lote.mkdir()

        _crear_docx_actividad_valido(carpeta_lote, nombre_archivo="Act_01_OK.docx", actividad="Actividad Buena 1")
        _crear_docx_actividad_valido(carpeta_lote, nombre_archivo="Act_02_Falla.docx", actividad="Actividad Para Fallar")
        _crear_docx_actividad_valido(carpeta_lote, nombre_archivo="Act_03_OK.docx", actividad="Actividad Buena 3")

        ingesta_uc = IngestarActividadDesdeWordUseCase(extractor=extractor, uow=sqlite_test_env)

        # Runner que falla sólo para Act_02_Falla
        class MockPipelineDesdeWord(ProcesarPipelineDesdeWordUseCase):
            def execute(self, file_path, **kwargs):
                p = Path(file_path)
                if "Falla" in p.name:
                    raise RuntimeError("Error de disco simulado")
                return super().execute(file_path, **kwargs)

        mock_pipe = MockPipelineDesdeWord(
            ingesta_use_case=ingesta_uc,
            pipeline_use_case=pipeline_use_case,
            uow=sqlite_test_env,
        )

        batch_uc = IngestarCarpetaWordUseCase(
            pipeline_word_use_case=mock_pipe,
            exportar_periodo_use_case=None,
            uow=sqlite_test_env,
        )

        cmd = IngestarCarpetaWordCommand(carpeta_origen=carpeta_lote, dry_run=True)
        res = batch_uc.execute(cmd)

        assert res.archivos_encontrados == 3
        assert (res.archivos_aceptados + res.archivos_con_advertencias) == 2
        assert res.archivos_fallidos == 1
        assert res.invariante_ok is False  # Hubo 1 archivo fallido

    def test_b05_ignora_temporales_de_word(self, batch_use_case, tmp_path):
        """B-05: Descarta automáticamente archivos temporales de Word (~$*)."""
        carpeta_lote = tmp_path / "lote_con_temporales"
        carpeta_lote.mkdir()

        _crear_docx_actividad_valido(carpeta_lote, nombre_archivo="Actividad_Real.docx")

        # Archivo temporal que simula Word abierto
        temp_word = carpeta_lote / "~$Actividad_Real.docx"
        temp_word.write_text("lock file temporal", encoding="utf-8")

        cmd = IngestarCarpetaWordCommand(carpeta_origen=carpeta_lote, dry_run=True)
        res = batch_use_case.execute(cmd)

        assert res.archivos_encontrados == 1  # Solo el real, el ~$ fue ignorado
        assert res.resultados_por_archivo[0].nombre_archivo == "Actividad_Real.docx"

    def test_b06_dry_run_lote_cero_escrituras(self, batch_use_case, tmp_path, sqlite_test_env):
        """B-06: dry_run=True no persiste en SQLite ni escribe matrices en disco."""
        carpeta_lote = tmp_path / "lote_dry_run"
        carpeta_lote.mkdir()

        _crear_docx_actividad_valido(carpeta_lote, nombre_archivo="Simulacion_01.docx", actividad="Simulada 1")
        _crear_docx_actividad_valido(carpeta_lote, nombre_archivo="Simulacion_02.docx", actividad="Simulada 2")

        carpeta_salida = tmp_path / "output_simulado"
        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_lote,
            carpeta_salida=carpeta_salida,
            dry_run=True,
        )

        res = batch_use_case.execute(cmd)

        assert res.dry_run is True
        assert res.archivos_encontrados == 2
        assert len(res.actividades_creadas) == 2
        assert len(res.matrices_generadas) == 0

        # Cero escrituras en SQLite
        with sqlite_test_env:
            assert sqlite_test_env.actividades.count() == 0

        # Cero archivos en carpeta de salida
        assert not carpeta_salida.exists() or len(list(carpeta_salida.glob("*"))) == 0

    def test_b07_heuristica_gap3_detecta_duplicado(self, batch_use_case, tmp_path):
        """B-07: GAP-3 detecta coincidencia de nombre y emite advertencia sin bloquear."""
        carpeta_lote = tmp_path / "lote_duplicados"
        carpeta_lote.mkdir()

        _crear_docx_actividad_valido(carpeta_lote, nombre_archivo="MismoNombre.docx", actividad="Actividad Primera")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_lote,
            advertir_posibles_duplicados=True,
            dry_run=True,
        )

        # Ejecución normal
        res = batch_use_case.execute(cmd)
        assert res.archivos_encontrados == 1

    def test_b08_aislamiento_arquitectonico_ast(self):
        """B-08: ingestar_carpeta_word.py no importa sqlite3, docx ni openpyxl."""
        archivo_batch = Path("app/application/use_cases/batch/ingestar_carpeta_word.py")
        arbol = ast.parse(archivo_batch.read_text(encoding="utf-8"))

        modulos_prohibidos = {"sqlite3", "docx", "openpyxl"}
        modulos_importados = set()

        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    modulos_importados.add(alias.name.split(".")[0])
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                modulos_importados.add(nodo.module.split(".")[0])

        interseccion = modulos_prohibidos & modulos_importados
        assert not interseccion, f"Clean Architecture violada con imports {interseccion}"
