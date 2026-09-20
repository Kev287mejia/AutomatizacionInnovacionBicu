"""tests.test_fase_28_5_1_h01_h02

Suite de pruebas exhaustivas para la Fase 28.5.1:
Corrección controlada de H-01 (Migraciones SQLite automáticas) y H-02 (Terminología institucional).

Cubre:
1. Bloque 4: Base SQLite completamente nueva (sin tablas, sin schema_version).
   - Migración automática a V002 al invocar WordBatchAppService.crear_batch_orchestrator().
   - Verificación de tablas y columnas (actividad, actividad_metrica_agregada, codigo_indicador, hash_sha256).
   - Procesamiento exitoso de D-01 sin 'no such table: actividad'.
2. Bloque 5: Migración real de base preexistente en V001 hacia V002.
   - Base con V001 aplicada (target_version=1).
   - crear_batch_orchestrator() actualiza a V002 de forma transparente.
   - Procesamiento exitoso de D-01.
3. Bloque 6: Base ya en V002.
   - crear_batch_orchestrator() es seguro y no duplica tablas ni índices.
4. Bloque 7: Prueba de idempotencia real.
   - Ejecutar MigrationRunner.apply_all_pending() 3 veces consecutivas.
   - Esquema estable, idéntico y sin errores.
5. Bloque 8: Prueba real del orquestador sin mocks.
6. Bloque 9: Prueba de arranque de la GUI (ConsolidatorApp) con base temporal inexistente.
7. Bloque 11: Auditoría de textos visibles (H-02) en vistas y etapas.
"""

from pathlib import Path
import shutil
import sqlite3
import pytest

from app.application.commands.batch_commands import IngestarCarpetaWordCommand
from app.infrastructure.persistence.config import DatabaseConfig, get_default_database_path
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.word_consolidator.ui.app import ConsolidatorApp
from app.word_consolidator.ui.services.word_batch_service import WordBatchAppService
from app.word_consolidator.ui.views.module_selection_view import ModuleSelectionView
from app.word_consolidator.ui.views.word_batch_view import WordBatchProcessingView
from app.word_consolidator.ui.workers.word_batch_worker import ETAPAS_WORD_BATCH
from tests.test_word_activity_extractor import _crear_docx_actividad_valido


class TestH01MigracionesAutomaticas:
    """Suite de pruebas para el hallazgo H-01."""

    def test_bloque_4_base_sqlite_completamente_nueva(self, tmp_path, monkeypatch):
        """Bloque 4: Base completamente nueva sin archivo ni tablas se migra automáticamente a V002."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        db_file = get_default_database_path()
        assert not db_file.exists()

        # Invocar la fábrica del orquestador sin uow (flujo real de producción)
        orchestrator = WordBatchAppService.crear_batch_orchestrator()

        # 1. Verificar que el archivo fue creado y migrado
        assert db_file.exists()

        conn = sqlite3.connect(str(db_file))
        try:
            cursor = conn.cursor()
            # Verificar schema_version
            cursor.execute("SELECT version, nombre_migracion FROM schema_version ORDER BY version ASC;")
            rows = cursor.fetchall()
            versiones = [r[0] for r in rows]
            assert 1 in versiones, "V001 debe estar aplicada"
            assert 2 in versiones, "V002 debe estar aplicada"

            # Verificar tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {r[0] for r in cursor.fetchall()}
            assert "actividad" in tables
            assert "actividad_metrica_agregada" in tables
            assert "persona" in tables
            assert "participacion" in tables

            # Verificar columnas V002 en actividad
            cursor.execute("PRAGMA table_info(actividad);")
            cols_act = {r[1] for r in cursor.fetchall()}
            assert "codigo_indicador" in cols_act
            assert "hash_sha256" in cols_act

            # Verificar índice único parcial
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_actividad_hash_sha256';")
            idx = cursor.fetchone()
            assert idx is not None, "Índice idx_actividad_hash_sha256 debe existir"
        finally:
            conn.close()

        # 2. Procesar documento de prueba real con el orquestador recién creado
        carpeta_origen = tmp_path / "origen"
        carpeta_origen.mkdir()
        carpeta_salida = tmp_path / "salida"
        carpeta_salida.mkdir()

        # Usar D-01 real de validation si existe, o crear docx válido
        src_d01 = Path("validation/fase_28_4_e2e/cases/case1_d01").resolve()
        archivos_d01 = list(src_d01.glob("*.docx"))
        if archivos_d01:
            shutil.copy2(archivos_d01[0], carpeta_origen / "D-01.docx")
        else:
            _crear_docx_actividad_valido(carpeta_origen, nombre_archivo="D-01_test.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_origen,
            carpeta_salida=carpeta_salida,
            exportar_matrices=True,
            dry_run=False,
        )

        res = orchestrator.execute(cmd)
        assert res.archivos_aceptados >= 1
        assert res.archivos_rechazados == 0
        assert res.archivos_fallidos == 0
        assert len(res.actividades_creadas) >= 1
        assert "matriz_1" in res.matrices_generadas

    def test_bloque_5_migracion_real_v001_a_v002(self, tmp_path, monkeypatch):
        """Bloque 5: Base existente con solo V001 es migrada automáticamente a V002 sin errores."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        db_file = get_default_database_path()

        cfg = DatabaseConfig()
        mgr = SQLiteConnectionManager(cfg)

        # 1. Crear base con SOLAMENTE V001
        conn = mgr.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending(target_version=1)
            assert runner.get_current_version() == 1
        finally:
            conn.close()

        # Verificar que NO tiene elementos de V002 (hash_sha256 ni actividad_metrica_agregada)
        conn = sqlite3.connect(str(db_file))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(actividad);")
            cols_prev = {r[1] for r in cur.fetchall()}
            assert "hash_sha256" not in cols_prev

            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actividad_metrica_agregada';")
            assert cur.fetchone() is None
        finally:
            conn.close()

        # 2. Llamar a crear_batch_orchestrator() (flujo real)
        orchestrator = WordBatchAppService.crear_batch_orchestrator()

        # 3. Verificar que ahora tiene V002
        conn = sqlite3.connect(str(db_file))
        try:
            cur = conn.cursor()
            cur.execute("SELECT version FROM schema_version ORDER BY version ASC;")
            versiones = [r[0] for r in cur.fetchall()]
            assert versiones == [1, 2]

            cur.execute("PRAGMA table_info(actividad);")
            cols_post = {r[1] for r in cur.fetchall()}
            assert "codigo_indicador" in cols_post
            assert "hash_sha256" in cols_post

            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actividad_metrica_agregada';")
            assert cur.fetchone() is not None
        finally:
            conn.close()

        # 4. Procesar D-01
        carpeta_origen = tmp_path / "origen_b5"
        carpeta_origen.mkdir()
        carpeta_salida = tmp_path / "salida_b5"
        carpeta_salida.mkdir()

        src_d01 = Path("validation/fase_28_4_e2e/cases/case1_d01").resolve()
        archivos_d01 = list(src_d01.glob("*.docx"))
        if archivos_d01:
            shutil.copy2(archivos_d01[0], carpeta_origen / "D-01.docx")
        else:
            _crear_docx_actividad_valido(carpeta_origen, nombre_archivo="D-01_test.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_origen,
            carpeta_salida=carpeta_salida,
            exportar_matrices=True,
            dry_run=False,
        )
        res = orchestrator.execute(cmd)
        assert res.archivos_aceptados >= 1

    def test_bloque_6_base_ya_en_v002(self, tmp_path, monkeypatch):
        """Bloque 6: Base ya migrada a V002 no duplica tablas, columnas ni índices al reinicializar."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        db_file = get_default_database_path()

        cfg = DatabaseConfig()
        mgr = SQLiteConnectionManager(cfg)

        conn = mgr.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending()
            assert runner.get_current_version() == 2
        finally:
            conn.close()

        # Ejecutar orquestador sobre la base existente
        orchestrator = WordBatchAppService.crear_batch_orchestrator()
        assert orchestrator is not None

        conn = sqlite3.connect(str(db_file))
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM schema_version;")
            count_ver = cur.fetchone()[0]
            assert count_ver == 2, "Deben existir exactamente 2 versiones en schema_version"
        finally:
            conn.close()

    def test_bloque_7_idempotencia_real_tres_ejecuciones(self, tmp_path, monkeypatch):
        """Bloque 7: apply_all_pending() ejecutado 3 veces consecutivas mantiene estabilidad total."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        cfg = DatabaseConfig()
        mgr = SQLiteConnectionManager(cfg)

        conn = mgr.get_connection()
        try:
            runner = MigrationRunner(conn)

            # Ejecución 1
            res1 = runner.apply_all_pending()
            assert any(r["status"] == "APPLIED_SUCCESSFULLY" for r in res1)
            assert runner.get_current_version() == 2

            # Ejecución 2
            res2 = runner.apply_all_pending()
            assert all(r["status"] == "ALREADY_APPLIED" for r in res2)
            assert runner.get_current_version() == 2

            # Ejecución 3
            res3 = runner.apply_all_pending()
            assert all(r["status"] == "ALREADY_APPLIED" for r in res3)
            assert runner.get_current_version() == 2

            # Comprobar integridad física
            assert runner.verify_integrity() == "ok"
        finally:
            conn.close()

    def test_bloque_8_prueba_real_orquestador_sin_mocks(self, tmp_path, monkeypatch):
        """Bloque 8: Demuestra el flujo completo base inexistente -> orquestador -> migraciones -> use cases -> procesamiento."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        db_file = get_default_database_path()
        assert not db_file.exists()

        # Construir orquestador sin mocks
        orchestrator = WordBatchAppService.crear_batch_orchestrator()
        assert db_file.exists()

        # Crear carpeta de entrada y salida
        carpeta_in = tmp_path / "in"
        carpeta_in.mkdir()
        carpeta_out = tmp_path / "out"
        carpeta_out.mkdir()

        _crear_docx_actividad_valido(carpeta_in, nombre_archivo="actividad_real.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=carpeta_in,
            carpeta_salida=carpeta_out,
            exportar_matrices=True,
            dry_run=False,
        )

        res = orchestrator.execute(cmd)
        assert res.archivos_aceptados == 1
        assert res.archivos_fallidos == 0
        assert "matriz_1" in res.matrices_generadas

    def test_bloque_9_prueba_arranque_gui_base_inexistente(self, tmp_path, monkeypatch):
        """Bloque 9: ConsolidatorApp arranca limpiamente sin errores contra una base inexistente."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        db_file = get_default_database_path()
        assert not db_file.exists()

        # Inicializar la aplicación real
        app = ConsolidatorApp()
        app.update()

        try:
            # Verificar que la base se creó e inicializó durante el arranque de la GUI
            assert db_file.exists()
            conn = sqlite3.connect(str(db_file))
            try:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actividad';")
                assert cur.fetchone() is not None, "Tabla actividad debe existir tras arranque de GUI"
            finally:
                conn.close()
        finally:
            app.destroy()


class TestH02TerminologiaInstitucional:
    """Suite de pruebas para la terminología institucional (H-02)."""

    def test_bloque_11_textos_visibles_usuario(self, tmp_path):
        """Verifica que ningún texto visible de la GUI contenga terminología técnica prohibida."""
        import customtkinter as ctk

        root = ctk.CTk()
        root.withdraw()

        try:
            mod_view = ModuleSelectionView(root)
            batch_view = WordBatchProcessingView(root)

            # Recolectar todos los textos visibles
            textos_visibles = []

            def recolectar(w):
                if hasattr(w, "cget"):
                    try:
                        t = w.cget("text")
                        if t:
                            textos_visibles.append(t)
                    except Exception:
                        pass
                for ch in w.winfo_children():
                    recolectar(ch)

            recolectar(mod_view)
            recolectar(batch_view)

            # Agregar nombres de etapas
            for etapa in ETAPAS_WORD_BATCH:
                textos_visibles.append(etapa["name"])

            texto_consolidado = " | ".join(textos_visibles)

            # Términos técnicos que NO deben aparecer en textos visibles al usuario
            terminos_prohibidos = [
                "repositorio SQLite",
                "Actividades en SQLite",
                "Persistidas como SSOT",
                "GAP-3",
                "Dry-Run",
                "Ingesta atómica hacia SQLite SSOT",
            ]

            for termino in terminos_prohibidos:
                assert termino not in texto_consolidado, f"Término prohibido '{termino}' encontrado en UI"

            # Términos reemplazados que SÍ deben aparecer
            assert "base de datos institucional" in texto_consolidado
            assert "Actividades registradas" in texto_consolidado
            assert "Registradas oficialmente" in texto_consolidado
            assert "Registro de actividades en base de datos" in texto_consolidado
            assert "Modo Simulación (sin guardar cambios" in texto_consolidado
        finally:
            root.destroy()
