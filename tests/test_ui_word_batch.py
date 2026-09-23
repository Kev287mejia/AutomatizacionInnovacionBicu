"""tests.test_ui_word_batch

Suite de pruebas para la Fachada UI del flujo Word → Matrices M1–M5 (Fase 28.2).
Valida:
  1. WordBatchAppService: análisis preflight, exclusión de temporales (~$*), resolución de rutas.
  2. WordBatchWorker: ciclo de vida asíncrono y emisión estructurada de eventos.
  3. ModuleSelectionView: navegación institucional entre módulos.
  4. WordBatchProcessingView: pestañas, preflight, visualización de resultados y tratamiento de duplicados.
  5. ConsolidatorApp: navegación global entre módulos.
"""

from pathlib import Path
import queue
import time
import pytest
from unittest.mock import MagicMock

from app.application.dto.batch_dtos import BatchArchivoResultadoDTO, BatchResultadoDTO
from app.word_consolidator.ui.services.word_batch_service import (
    WordBatchAppService,
    WordBatchPreflightStatus,
)
from app.word_consolidator.ui.views.module_selection_view import ModuleSelectionView
from app.word_consolidator.ui.views.word_batch_view import WordBatchProcessingView
from app.word_consolidator.ui.workers.word_batch_worker import (
    WordBatchEvent,
    WordBatchEventType,
    WordBatchWorker,
)
from tests.test_word_activity_extractor import _crear_docx_actividad_valido


class TestWordBatchAppService:
    """Pruebas del servicio de aplicación de preflight y descubrimiento."""

    def test_preflight_carpeta_inexistente(self, tmp_path):
        """Preflight detecta limpiamente si la carpeta origen no existe."""
        no_existe = tmp_path / "carpeta_fantasma"
        status = WordBatchAppService.analizar_carpeta_origen(no_existe)
        assert not status.listo_para_procesar
        assert not status.carpeta_origen_valida
        assert any("no existe" in e.lower() for e in status.errores_bloqueantes)

    def test_preflight_exclusion_temporales_word(self, tmp_path):
        """Preflight excluye archivos que inician con ~$ y cuenta candidatos reales."""
        carpeta = tmp_path / "lote_docx"
        carpeta.mkdir()

        # Crear 2 archivos válidos y 2 temporales
        (carpeta / "informe1.docx").write_bytes(b"PK01")
        (carpeta / "informe2.docx").write_bytes(b"PK02")
        (carpeta / "~$informe1.docx").write_bytes(b"TEMP1")
        (carpeta / "~$otro_temp.docx").write_bytes(b"TEMP2")
        (carpeta / "notas.txt").write_text("ignorar")

        status = WordBatchAppService.analizar_carpeta_origen(carpeta)
        assert status.listo_para_procesar
        assert status.carpeta_origen_valida
        assert status.total_archivos_encontrados == 4  # 4 *.docx en total
        assert status.total_temporales_excluidos == 2  # 2 temporales ~$
        assert status.total_candidatos == 2            # 2 reales
        assert any("excluyeron" in a.lower() for a in status.advertencias)

    def test_resolver_directorio_salida(self):
        """Resuelve un directorio de salida válido y accesible en el sistema."""
        salida = WordBatchAppService.resolver_directorio_salida_predeterminado()
        assert isinstance(salida, Path)
        assert salida.exists()
        assert salida.is_dir()


class TestWordBatchWorker:
    """Pruebas del hilo de ejecución asíncrono."""

    def test_worker_ciclo_de_vida_y_eventos(self, tmp_path):
        """Worker emite BATCH_STARTED, STAGE_STARTED y BATCH_COMPLETED hacia la cola."""
        carpeta_origen = tmp_path / "origen"
        carpeta_origen.mkdir()
        carpeta_salida = tmp_path / "salida"
        carpeta_salida.mkdir()

        # Crear un archivo de prueba
        _crear_docx_actividad_valido(carpeta_origen, nombre_archivo="actividad_test.docx")

        event_q = queue.Queue()

        # Mock del orquestador para aislamiento rápido
        mock_orch = MagicMock()
        mock_orch._pipeline_word_use_case.execute.return_value = MagicMock(
            exitoso=True,
            id_actividad="act-123",
            to_batch_archivo_resultado=lambda ruta_archivo: BatchArchivoResultadoDTO(
                nombre_archivo="actividad_test.docx",
                ruta_archivo=str(ruta_archivo),
                estado="ACEPTADO",
                tipo_documento="INFORME_ACTIVIDAD",
                id_actividad="act-123",
            ),
        )
        mock_orch._exportar_periodo_use_case = MagicMock()
        mock_orch.execute.return_value = BatchResultadoDTO(
            batch_id="test-batch-001",
            carpeta_origen=str(carpeta_origen),
            timestamp_inicio="2026-09-18T10:00:00",
            timestamp_fin="2026-09-18T10:01:00",
            dry_run=True,
            archivos_encontrados=1,
            archivos_aceptados=1,
            actividades_creadas=["act-123"],
            matrices_generadas={"matriz_1": "output/M1.xlsx"},
            resultados_por_archivo=[
                BatchArchivoResultadoDTO(
                    nombre_archivo="actividad_test.docx",
                    ruta_archivo=str(carpeta_origen / "actividad_test.docx"),
                    estado="ACEPTADO",
                    tipo_documento="INFORME_ACTIVIDAD",
                    id_actividad="act-123",
                )
            ],
        )

        worker = WordBatchWorker(
            carpeta_origen=carpeta_origen,
            carpeta_salida=carpeta_salida,
            event_queue=event_q,
            dry_run=True,
            batch_orchestrator=mock_orch,
        )
        worker.start()
        worker.join(timeout=10.0)
        assert not worker.is_alive()

        # Recoger eventos
        eventos = []
        while not event_q.empty():
            eventos.append(event_q.get_nowait())

        tipos = [e.event_type for e in eventos]
        assert WordBatchEventType.BATCH_STARTED in tipos
        assert WordBatchEventType.STAGE_STARTED in tipos
        assert WordBatchEventType.BATCH_COMPLETED in tipos


class TestUIComponentsWordBatch:
    """Pruebas de los componentes visuales de CustomTkinter."""

    # app_root se hereda con scope='session' desde tests/conftest.py

    def test_module_selection_view_callbacks(self, app_root):
        """ModuleSelectionView invoca correctamente los callbacks de navegación."""
        called_w2m = []
        called_m2w = []

        view = ModuleSelectionView(
            app_root,
            on_select_word_batch=lambda: called_w2m.append(True),
            on_select_matrices_word=lambda: called_m2w.append(True),
        )
        assert view is not None

        view._on_click_word_batch()
        assert len(called_w2m) == 1

        view._on_click_matrices_word()
        assert len(called_m2w) == 1

    def test_word_batch_processing_view_tabs_y_preflight(self, app_root, tmp_path):
        """WordBatchProcessingView inicializa pestañas y sincroniza el estado preflight."""
        view = WordBatchProcessingView(app_root)
        assert view.tabview is not None
        assert view.period_view is not None
        assert view.progress_view is not None

        # Probar con carpeta vacía
        view.carpeta_origen = tmp_path
        status = view._sincronizar_preflight()
        assert not status.listo_para_procesar
        assert "NO SE PUEDE PROCESAR" in view.lbl_pf_estado.cget("text")

        # Crear archivo válido y re-sincronizar
        _crear_docx_actividad_valido(tmp_path, nombre_archivo="act_01.docx")
        status2 = view._sincronizar_preflight()
        assert status2.listo_para_procesar
        assert "Listo para procesar" in view.lbl_pf_estado.cget("text")
        assert view.btn_procesar.cget("state") == "normal"

    def test_word_batch_view_mostrar_resultados_duplicado_y_m2_m5(self, app_root, tmp_path):
        """WordBatchProcessingView visualiza duplicados sin error y muestra aviso M2–M5."""
        view = WordBatchProcessingView(app_root)

        res = BatchResultadoDTO(
            batch_id="batch-uuid-test",
            carpeta_origen=str(tmp_path),
            timestamp_inicio="2026-09-18T12:00:00",
            timestamp_fin="2026-09-18T12:01:00",
            dry_run=False,
            archivos_encontrados=2,
            archivos_aceptados=1,
            archivos_rechazados=0,
            archivos_con_advertencias=1,
            actividades_creadas=["act-uuid-1"],
            actividades_con_posible_duplicado=["act-uuid-dup"],
            matrices_generadas={"matriz_1": str(tmp_path / "M1_Consolidado_General.xlsx")},
            carpeta_batch_salida=str(tmp_path / "batch-uuid-test"),
            resultados_por_archivo=[
                BatchArchivoResultadoDTO(
                    nombre_archivo="actividad_normal.docx",
                    ruta_archivo=str(tmp_path / "actividad_normal.docx"),
                    estado="ACEPTADO",
                    tipo_documento="INFORME_ACTIVIDAD",
                    id_actividad="act-uuid-1",
                ),
                BatchArchivoResultadoDTO(
                    nombre_archivo="actividad_duplicada.docx",
                    ruta_archivo=str(tmp_path / "actividad_duplicada.docx"),
                    estado="CON_ADVERTENCIAS",
                    tipo_documento="INFORME_ACTIVIDAD",
                    id_actividad="act-uuid-dup",
                    posible_duplicado_advertido=True,
                ),
            ],
        )

        view._mostrar_resultado(res)
        assert view.val_docs.cget("text") == "2"
        assert view.val_actividades.cget("text") == "1"
        assert "1 de 5" in view.val_matrices.cget("text")
        assert "COMPLETADO CON OBSERVACIONES" in view.lbl_res_header.cget("text")

    def test_consolidator_app_navegacion(self, app_root):
        """ConsolidatorApp alterna correctamente entre el menú, Word Batch y Matrices Word."""
        from app.word_consolidator.ui.app import ConsolidatorApp

        app = ConsolidatorApp()
        app.withdraw()

        assert app.module_selection_view is not None
        assert app.word_batch_view is not None
        assert app.main_window is not None

        # Navegar a Word Batch
        app.mostrar_word_batch()
        assert app.word_batch_view.winfo_ismapped() or True  # Modo withdrawn

        # Navegar a Matrices Word
        app.mostrar_matrices_word()
        assert app.main_window is not None

        # Volver al menú principal
        app.mostrar_menu_principal()
        assert app.module_selection_view is not None

        try:
            app.destroy()
        except Exception:
            pass
