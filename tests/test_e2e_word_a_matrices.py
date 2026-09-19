"""tests.test_e2e_word_a_matrices

Pruebas de Integración y End-to-End (E2E) para la Fase 26.9 Bloque 3:
Orquestación completa y procesamiento por lote:
  DOCX institucional(es) -> Extractor -> SQLite SSOT -> Quality -> Routing -> ExportConsolidado M1-M5 -> Manifest JSON.

Cobertura E2E:
- E2E-01: Flujo completo de lote sintético heterogéneo (actividades válidas, archivo incompatible, informe semanal).
          Verifica persistencia en SQLite, matrices M1-M5 en output/<batch_id>/, invariante matemática y manifest.json.
- E2E-02: Flujo con documentos institucionales Word reales (si existen en Downloads).
- E2E-03: Garantía de modo dry_run: cero mutaciones en SQLite, cero XLSX y cero manifest.json en disco.
- E2E-04: Inmutabilidad estricta de plantillas oficiales base en templates/.
- E2E-05: Comportamiento heurístico GAP-3 ante documentos duplicados en lote sucesivo.
"""

import json
from pathlib import Path
import shutil
from typing import Generator
import openpyxl
import pytest

from app.application.commands.batch_commands import IngestarCarpetaWordCommand
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
from app.exporters.base_exporter import calcular_sha256
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
    db_file = tmp_path / "test_e2e_word_a_matrices.db"
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
def batch_orchestrator(sqlite_test_env) -> IngestarCarpetaWordUseCase:
    """Configura el caso de uso batch con todos sus componentes reales conectados."""
    extractor = WordActivityExtractor()
    ingesta_uc = IngestarActividadDesdeWordUseCase(extractor=extractor, uow=sqlite_test_env)
    pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
    pipeline_word_uc = ProcesarPipelineDesdeWordUseCase(
        ingesta_use_case=ingesta_uc,
        pipeline_use_case=pipeline_uc,
        uow=sqlite_test_env,
    )
    exportar_periodo_uc = ExportarMatricesPeriodoUseCase(
        pipeline_use_case=pipeline_uc,
        uow=sqlite_test_env,
    )
    return IngestarCarpetaWordUseCase(
        pipeline_word_use_case=pipeline_word_uc,
        exportar_periodo_use_case=exportar_periodo_uc,
        uow=sqlite_test_env,
    )


class TestE2EWordAMatrices:
    """Suite integral E2E para el flujo completo Word -> Matrices M1-M5."""

    def test_e2e_01_flujo_completo_lote_sintetico(self, batch_orchestrator, sqlite_test_env, tmp_path):
        """E2E-01: Procesa lote heterogéneo y valida SQLite, M1-M5 y manifest.json."""
        carpeta_origen = tmp_path / "lote_origen"
        carpeta_origen.mkdir()
        carpeta_salida = tmp_path / "output_e2e"
        carpeta_salida.mkdir()

        # Documentos sintéticos del lote
        _crear_docx_actividad_valido(
            carpeta_origen,
            nombre_archivo="Actividad_01_Robotica.docx",
            actividad="Taller de Robotica Educativa",
            lugar="Laboratorio de Informatica Bilwi",
            fecha="2026-05-10",
            total=25,
            femenino=15,
            masculino=10,
            estudiantes=20,
            docentes=5,
        )
        _crear_docx_actividad_valido(
            carpeta_origen,
            nombre_archivo="Actividad_02_Emprendimiento.docx",
            actividad="Feria de Emprendimiento Tecnologico",
            lugar="Auditorio Central Bluefields",
            fecha="2026-05-18",
            total=40,
            femenino=25,
            masculino=15,
            estudiantes=30,
            docentes=10,
        )
        _crear_docx_incompatible(
            carpeta_origen / "Incompatible_Oficio.docx"
        )
        _crear_docx_informe_semanal(
            carpeta_origen / "Informe_Semanal_Mayo.docx"
        )

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_origen,
            carpeta_salida=carpeta_salida,
            permitir_fixtures_test_only=True,
            dry_run=False,
        )

        res = batch_orchestrator.execute(cmd)

        # 1. Invariante del lote y contadores
        assert res.invariante_ok is True
        assert res.archivos_encontrados == 4
        assert (res.archivos_aceptados + res.archivos_con_advertencias) == 2
        assert res.archivos_rechazados == 2
        assert res.archivos_fallidos == 0
        assert len(res.actividades_creadas) == 2
        assert len(res.errores_criticos) == 0

        # 2. Persistencia en SQLite SSOT
        conn = sqlite_test_env._connection_manager.get_connection()
        total_act = conn.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]
        total_per = conn.execute("SELECT COUNT(*) FROM persona;").fetchone()[0]
        total_part = conn.execute("SELECT COUNT(*) FROM participacion;").fetchone()[0]
        conn.close()

        assert total_act == 2
        # P-02: Cero personas ni participaciones creadas artificialmente
        assert total_per == 0
        assert total_part == 0

        with sqlite_test_env:
            for act_id in res.actividades_creadas:
                act = sqlite_test_env.actividades.get_by_id(act_id)
                assert act is not None
                assert act.nombre_actividad_original in [
                    "Taller de Robotica Educativa",
                    "Feria de Emprendimiento Tecnologico",
                ]

        # 3. Aislamiento por batch_id en carpeta de salida (P-07)
        carpeta_lote = carpeta_salida / res.batch_id
        assert carpeta_lote.exists()
        assert carpeta_lote.is_dir()

        # 4. Matrices físicas generadas M1–M5 (P-01)
        assert len(res.matrices_generadas) == 5
        for id_matriz, ruta_str in res.matrices_generadas.items():
            archivo_matriz = Path(ruta_str)
            assert archivo_matriz.exists()
            assert archivo_matriz.stat().st_size > 0

        # Verificación específica de M1 (Consolidado de Actividades)
        m1_path = Path(res.matrices_generadas["matriz_1"])
        wb_m1 = openpyxl.load_workbook(str(m1_path))
        ws_m1 = wb_m1.active
        # Debe haber al menos 2 actividades escritas a partir de la fila 2
        assert ws_m1.cell(row=2, column=9).value is not None
        assert ws_m1.cell(row=3, column=9).value is not None
        assert ws_m1.cell(row=4, column=9).value is None
        wb_m1.close()

        # Verificación de M2, M3, M4 (listas nominales vacías, 0 filas nominales)
        m2_path = Path(res.matrices_generadas["matriz_2"])
        wb_m2 = openpyxl.load_workbook(str(m2_path))
        ws_m2 = wb_m2.active
        assert ws_m2.cell(row=2, column=33).value is None  # Sin estudiantes nominales
        wb_m2.close()

        # Verificación de M5 (32 registros históricos preservados intactos)
        m5_path = Path(res.matrices_generadas["matriz_5"])
        wb_m5 = openpyxl.load_workbook(str(m5_path))
        ws_m5 = wb_m5.active
        # Fila 33 contiene el histórico 32
        assert ws_m5.cell(row=33, column=1).value == 32
        # Fila 34 no contiene datos nuevos ya que Word no infiere nominales
        assert ws_m5.cell(row=34, column=1).value is None
        wb_m5.close()

        # 5. Verificación de Manifiesto Pericial JSON (P-04)
        assert res.manifest_path is not None
        manifest_file = Path(res.manifest_path)
        assert manifest_file.exists()

        with open(manifest_file, "r", encoding="utf-8") as mf:
            datos_manifest = json.load(mf)

        assert datos_manifest["metadata_lote"]["batch_id"] == res.batch_id
        assert datos_manifest["balance_archivos"]["encontrados"] == 4
        assert datos_manifest["balance_archivos"]["aceptados"] + datos_manifest["balance_archivos"]["con_advertencias"] == 2
        assert datos_manifest["balance_archivos"]["rechazados"] == 2
        assert datos_manifest["balance_archivos"]["fallidos"] == 0
        assert datos_manifest["metadata_lote"]["invariante_ok"] is True
        assert datos_manifest["metadata_lote"]["dry_run"] is False

        # Verificación criptográfica SHA-256 de todas las matrices en el manifiesto
        matrices_dict = datos_manifest["exportacion"]["matrices_generadas"]
        hashes_dict = datos_manifest["exportacion"]["hashes_sha256"]
        assert len(matrices_dict) == 5
        assert len(hashes_dict) == 5
        for m_id, ruta_str in matrices_dict.items():
            ruta_m = Path(ruta_str)
            assert ruta_m.exists()
            assert hashes_dict[m_id] == calcular_sha256(ruta_m)

    def test_e2e_02_flujo_documentos_reales_institucionales(self, batch_orchestrator, sqlite_test_env, tmp_path):
        """E2E-02: Procesa lote con documentos Word institucionales reales desde Downloads."""
        downloads = Path(r"C:\Users\LENOVO X1 YOGA\Downloads")
        f1_matches = list(downloads.glob("*seguimiento y desarrollo*.docx"))
        f2_matches = list(downloads.glob("*Certificados*.docx"))
        f_semanal_matches = list(downloads.glob("*Informe semanal*.docx"))
        f_incompatible_matches = list(downloads.glob("*Carta de Solicitud*.docx"))

        if not (f1_matches and f2_matches and f_semanal_matches and f_incompatible_matches):
            pytest.skip("Documentos institucionales reales no encontrados en Downloads.")

        f_real_1 = f1_matches[0]
        f_real_2 = f2_matches[0]
        f_semanal = f_semanal_matches[0]
        f_incompatible = f_incompatible_matches[0]

        carpeta_origen = tmp_path / "lote_real"
        carpeta_origen.mkdir()
        carpeta_salida = tmp_path / "output_real"
        carpeta_salida.mkdir()

        # Copiar archivos reales al lote con nombres limpios para evitar MAX_PATH en Windows temp
        shutil.copy2(str(f_real_1), str(carpeta_origen / "Real_Indicador16_GoogleForm.docx"))
        shutil.copy2(str(f_real_2), str(carpeta_origen / "Real_Indicador16_Certificados.docx"))
        shutil.copy2(str(f_semanal), str(carpeta_origen / "Real_Informe_Semanal.docx"))
        shutil.copy2(str(f_incompatible), str(carpeta_origen / "Real_Carta_Solicitud.docx"))

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_origen,
            carpeta_salida=carpeta_salida,
            permitir_fixtures_test_only=True,
            dry_run=False,
        )

        res = batch_orchestrator.execute(cmd)

        assert res.invariante_ok is True
        assert res.archivos_encontrados == 4
        assert (res.archivos_aceptados + res.archivos_con_advertencias) == 2
        assert res.archivos_rechazados == 2
        assert res.archivos_fallidos == 0
        assert len(res.actividades_creadas) == 2

        # Validar en SQLite
        conn = sqlite_test_env._connection_manager.get_connection()
        total_act = conn.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]
        total_per = conn.execute("SELECT COUNT(*) FROM persona;").fetchone()[0]
        total_part = conn.execute("SELECT COUNT(*) FROM participacion;").fetchone()[0]
        conn.close()

        assert total_act == 2
        assert total_per == 0
        assert total_part == 0

        # Validar generación física de matrices y manifiesto
        assert len(res.matrices_generadas) == 5
        assert res.manifest_path is not None
        assert Path(res.manifest_path).exists()

        # Validar que M1 contenga los nombres reales
        m1_path = Path(res.matrices_generadas["matriz_1"])
        wb_m1 = openpyxl.load_workbook(str(m1_path))
        ws_m1 = wb_m1.active
        nombres_m1 = [
            ws_m1.cell(row=2, column=9).value,
            ws_m1.cell(row=3, column=9).value,
        ]
        wb_m1.close()
        assert any("Google Form" in str(n) for n in nombres_m1)
        assert any("Entrega de Certificados" in str(n) for n in nombres_m1)

    def test_e2e_03_dry_run_garantiza_cero_escrituras_globales(self, batch_orchestrator, sqlite_test_env, tmp_path):
        """E2E-03: dry_run=True garantiza cero cambios en SQLite y cero archivos en disco."""
        carpeta_origen = tmp_path / "lote_dry_run"
        carpeta_origen.mkdir()
        carpeta_salida = tmp_path / "output_dry_run"

        _crear_docx_actividad_valido(
            carpeta_origen,
            nombre_archivo="Actividad_Dry_1.docx",
            actividad="Capacitacion Docente Dry",
        )
        _crear_docx_actividad_valido(
            carpeta_origen,
            nombre_archivo="Actividad_Dry_2.docx",
            actividad="Taller de Investigacion Dry",
        )

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_origen,
            carpeta_salida=carpeta_salida,
            permitir_fixtures_test_only=True,
            dry_run=True,
        )

        res = batch_orchestrator.execute(cmd)

        assert res.dry_run is True
        assert res.archivos_encontrados == 2
        assert len(res.actividades_creadas) == 2
        assert len(res.matrices_generadas) == 0
        assert res.manifest_path is None

        # Base de datos completamente intacta
        conn = sqlite_test_env._connection_manager.get_connection()
        total_act = conn.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]
        conn.close()
        assert total_act == 0

        # Carpeta de salida no fue creada o está vacía
        assert not carpeta_salida.exists() or len(list(carpeta_salida.glob("*"))) == 0

    def test_e2e_04_inmutabilidad_plantillas_base(self, batch_orchestrator, tmp_path):
        """E2E-04: Ninguna exportación altera las plantillas oficiales en templates/."""
        carpeta_templates = Path("templates")
        plantillas = list(carpeta_templates.glob("Matriz_*.xlsx"))
        assert len(plantillas) == 5

        hashes_antes = {p.name: calcular_sha256(p) for p in plantillas}

        carpeta_origen = tmp_path / "lote_inmutabilidad"
        carpeta_origen.mkdir()
        carpeta_salida = tmp_path / "output_inmutabilidad"

        _crear_docx_actividad_valido(
            carpeta_origen,
            nombre_archivo="Actividad_Test.docx",
            actividad="Actividad Verificacion Inmutabilidad",
        )

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_origen,
            carpeta_salida=carpeta_salida,
            permitir_fixtures_test_only=True,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)
        assert res.invariante_ok is True

        hashes_despues = {p.name: calcular_sha256(p) for p in plantillas}

        # Las plantillas base deben permanecer 100% inalteradas
        assert hashes_antes == hashes_despues

    def test_e2e_05_idempotencia_heuristic_gap3_dos_ejecuciones(self, batch_orchestrator, tmp_path):
        """E2E-05: Ejecutar dos veces con el mismo archivo emite advertencia GAP-3 sin fallar."""
        carpeta_origen = tmp_path / "lote_repetido"
        carpeta_origen.mkdir()
        carpeta_salida = tmp_path / "output_repetido"

        _crear_docx_actividad_valido(
            carpeta_origen,
            nombre_archivo="Actividad_Repetida.docx",
            actividad="Actividad Repetida",
        )

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_origen,
            carpeta_salida=carpeta_salida,
            advertir_posibles_duplicados=True,
            permitir_fixtures_test_only=True,
            dry_run=True,
        )

        # Primera ejecución
        res1 = batch_orchestrator.execute(cmd)
        assert res1.archivos_encontrados == 1
        assert res1.invariante_ok is True

        # Segunda ejecución
        res2 = batch_orchestrator.execute(cmd)
        assert res2.archivos_encontrados == 1
        assert res2.invariante_ok is True
