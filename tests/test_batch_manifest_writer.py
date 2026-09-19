"""tests.test_batch_manifest_writer

Suite de pruebas para el Subbloque 3.4:
BatchManifestWriter (Trazabilidad y auditoría externa en manifest.json).

Cobertura:
- M-01: Construcción de payload con todos los campos obligatorios de la Decisión P-04.
- M-02: Serialización y escritura física de manifest.json válido en disco.
- M-03: Modo dry_run=True no escribe en disco por diseño estricto (cero escrituras).
- M-04: Trazabilidad heurística GAP-3 incluida con nota pericial explícita.
- M-05: Integración con IngestarCarpetaWordUseCase: genera manifest físico en salida.
- M-06: Aislamiento arquitectónico (AST): no importa sqlite3, docx ni openpyxl.
"""

import ast
import json
from pathlib import Path
from typing import Generator
import pytest

from app.application.commands.batch_commands import IngestarCarpetaWordCommand
from app.application.dto.batch_dtos import (
    BatchArchivoResultadoDTO,
    BatchResultadoDTO,
)
from app.application.use_cases.batch.batch_manifest_writer import (
    BatchManifestWriter,
)
from app.application.use_cases.batch.ingestar_carpeta_word import (
    IngestarCarpetaWordUseCase,
)
from app.application.use_cases.batch.procesar_pipeline_desde_word import (
    ProcesarPipelineDesdeWordUseCase,
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
from tests.test_word_activity_extractor import _crear_docx_actividad_valido


@pytest.fixture
def sqlite_test_env(tmp_path) -> Generator[SQLiteUnitOfWork, None, None]:
    db_file = tmp_path / "test_manifest.db"
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
def dummy_batch_resultado() -> BatchResultadoDTO:
    """Fixture de un BatchResultadoDTO con datos representativos."""
    archivo_01 = BatchArchivoResultadoDTO(
        nombre_archivo="Actividad_01.docx",
        ruta_archivo="/datos/Actividad_01.docx",
        estado="ACEPTADO",
        tipo_documento="INFORME_ACTIVIDAD",
        id_actividad="uuid-act-01",
        evidencias_registradas=2,
        calidad_estado="CONFORME",
        total_hallazgos_calidad=0,
        total_participaciones_enrutadas=0,
    )
    archivo_02 = BatchArchivoResultadoDTO(
        nombre_archivo="Actividad_02.docx",
        ruta_archivo="/datos/Actividad_02.docx",
        estado="CON_ADVERTENCIAS",
        tipo_documento="INFORME_ACTIVIDAD",
        id_actividad="uuid-act-02",
        evidencias_registradas=1,
        advertencias=["[GAP-3] Posible coincidencia de nombre."],
        calidad_estado="CON_OBSERVACIONES",
        total_hallazgos_calidad=1,
        total_participaciones_enrutadas=0,
        posible_duplicado_advertido=True,
    )
    return BatchResultadoDTO(
        batch_id="batch-uuid-test-12345",
        carpeta_origen="/datos/word_docs",
        patron_glob="*.docx",
        timestamp_inicio="2026-09-18T20:00:00",
        timestamp_fin="2026-09-18T20:02:00",
        dry_run=False,
        archivos_encontrados=2,
        archivos_aceptados=1,
        archivos_rechazados=0,
        archivos_con_advertencias=1,
        archivos_fallidos=0,
        actividades_creadas=["uuid-act-01", "uuid-act-02"],
        evidencias_registradas_total=3,
        actividades_con_posible_duplicado=["uuid-act-02"],
        matrices_generadas={"matriz_1": "/out/M1.xlsx"},
        hashes_matrices={"matriz_1": "abcdef1234567890"},
        manifest_path=None,
        invariante_ok=True,
        errores_criticos=[],
        advertencias_lote=["[GAP-3] Posible coincidencia de nombre."],
        resultados_por_archivo=[archivo_01, archivo_02],
    )


class TestBatchManifestWriter:

    def test_m01_construccion_payload_completo(self, dummy_batch_resultado):
        """M-01: El payload contiene todos los campos exigidos por la Decisión P-04."""
        payload = BatchManifestWriter.construir_payload(dummy_batch_resultado)

        assert "metadata_lote" in payload
        assert payload["metadata_lote"]["batch_id"] == "batch-uuid-test-12345"
        assert payload["metadata_lote"]["invariante_ok"] is True

        assert "balance_archivos" in payload
        assert payload["balance_archivos"]["encontrados"] == 2
        assert payload["balance_archivos"]["aceptados"] == 1
        assert payload["balance_archivos"]["con_advertencias"] == 1

        assert "entidades_generadas" in payload
        assert payload["entidades_generadas"]["total_actividades"] == 2
        assert len(payload["entidades_generadas"]["actividades_ids"]) == 2

        assert "calidad" in payload
        assert "routing" in payload
        assert payload["routing"]["total_participaciones_nominales"] == 0

        assert "exportacion" in payload
        assert "matrices_generadas" in payload["exportacion"]

        assert "gap3_trazabilidad_duplicados" in payload
        assert payload["gap3_trazabilidad_duplicados"]["actividades_con_posible_duplicado_count"] == 1

        assert "archivos_detalle" in payload
        assert len(payload["archivos_detalle"]) == 2

    def test_m02_escritura_fisica_json_valido(self, dummy_batch_resultado, tmp_path):
        """M-02: Se escribe físicamente un archivo JSON válido en el directorio destino."""
        out_dir = tmp_path / "output_manifest"
        manifest_file = BatchManifestWriter.escribir(dummy_batch_resultado, out_dir)

        assert manifest_file is not None
        assert manifest_file.exists()
        assert manifest_file.name == "manifest.json"

        # Validar que es JSON parseable
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["metadata_lote"]["batch_id"] == "batch-uuid-test-12345"
        assert len(data["archivos_detalle"]) == 2

    def test_m03_dry_run_no_escribe_en_disco(self, dummy_batch_resultado, tmp_path):
        """M-03: Con dry_run=True no se escribe en disco salvo permiso explícito."""
        dummy_batch_resultado.dry_run = True
        out_dir = tmp_path / "out_dry"

        res = BatchManifestWriter.escribir(dummy_batch_resultado, out_dir)

        assert res is None
        assert not (out_dir / "manifest.json").exists()

    def test_m04_gap3_trazabilidad_explicita(self, dummy_batch_resultado):
        """M-04: La nota pericial de GAP-3 aclara la limitación del schema v001."""
        payload = BatchManifestWriter.construir_payload(dummy_batch_resultado)
        gap3 = payload["gap3_trazabilidad_duplicados"]

        assert "v001" in gap3["nota_pericial"]
        assert "heurística" in gap3["nota_pericial"].lower()
        assert gap3["actividades_con_posible_duplicado_count"] == 1

    def test_m05_integracion_batch_use_case_genera_manifest(self, tmp_path, sqlite_test_env):
        """M-05: IngestarCarpetaWordUseCase genera manifest físico cuando no es dry_run."""
        carpeta_lote = tmp_path / "lote_manifest_test"
        carpeta_lote.mkdir()
        _crear_docx_actividad_valido(carpeta_lote, nombre_archivo="Actividad_Manifest.docx")

        extractor = WordActivityExtractor()
        ingesta_uc = IngestarActividadDesdeWordUseCase(extractor=extractor, uow=sqlite_test_env)
        pipe_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        pipe_word_uc = ProcesarPipelineDesdeWordUseCase(
            ingesta_use_case=ingesta_uc,
            pipeline_use_case=pipe_uc,
            uow=sqlite_test_env,
        )

        batch_uc = IngestarCarpetaWordUseCase(
            pipeline_word_use_case=pipe_word_uc,
            exportar_periodo_use_case=None,
            uow=sqlite_test_env,
        )

        carpeta_salida = tmp_path / "salida_manifest_test"
        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_lote,
            carpeta_salida=carpeta_salida,
            dry_run=False,
        )

        resultado = batch_uc.execute(cmd)

        assert resultado.manifest_path is not None
        p_manifest = Path(resultado.manifest_path)
        assert p_manifest.exists()
        assert p_manifest.name == "manifest.json"

        # Subcarpeta por batch_id (P-07)
        assert p_manifest.parent.name == resultado.batch_id

    def test_m06_aislamiento_arquitectonico_ast(self):
        """M-06: batch_manifest_writer.py no importa sqlite3, docx ni openpyxl."""
        archivo = Path("app/application/use_cases/batch/batch_manifest_writer.py")
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))

        modulos_prohibidos = {"sqlite3", "docx", "openpyxl"}
        modulos_importados = set()

        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    modulos_importados.add(alias.name.split(".")[0])
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                modulos_importados.add(nodo.module.split(".")[0])

        interseccion = modulos_prohibidos & modulos_importados
        assert not interseccion, f"Clean Architecture violada con {interseccion}"
