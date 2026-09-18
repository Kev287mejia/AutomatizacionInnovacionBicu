"""
tests.test_word_consolidator.test_ui_components

Pruebas unitarias para componentes gráficos CustomTkinter (Fase 14.9).
Valida el ciclo de vida de los widgets, transiciones de estado, sincronización
y presentación de datos sin requerir interacción de pantalla humana.
"""

from pathlib import Path
import pytest
import customtkinter as ctk

from app.word_consolidator.models import PeriodoConsolidacion, TipoPeriodo
from app.word_consolidator.pipeline import PipelineExecutionResult
from app.word_consolidator.ui.views.main_window import MainWindow
from app.word_consolidator.ui.views.matrix_selection_view import MatrixSelectionView
from app.word_consolidator.ui.views.period_selection_view import PeriodSelectionView
from app.word_consolidator.ui.views.progress_view import ProgressView
from app.word_consolidator.ui.views.result_view import ResultView
from app.word_consolidator.ui.views.validation_view import ValidationView

OUTPUT_DIR = Path("output")


# app_root se hereda con scope='session' desde tests/conftest.py


@pytest.fixture
def rutas_oficiales():
    return {
        "M1": OUTPUT_DIR / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": OUTPUT_DIR / "Matriz_2_Estudiantes.xlsx",
        "M3": OUTPUT_DIR / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": OUTPUT_DIR / "Matriz_4_Colaboradores.xlsx",
        "M5": OUTPUT_DIR / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }


class TestUIComponents:
    """Suite de pruebas de componentes de interfaz."""

    def test_01_matrix_selection_view_flujo(self, app_root, rutas_oficiales):
        view = MatrixSelectionView(app_root)
        assert len(view.obtener_matrices()) == 0

        # Cargar matrices oficiales
        view.cargar_matrices_directas(rutas_oficiales)
        m = view.obtener_matrices()
        assert len(m) == 5
        assert set(m.keys()) == {"M1", "M2", "M3", "M4", "M5"}
        assert "5 de 5 matrices identificadas" in view.status_lbl.cget("text")

        # Limpiar
        view.limpiar()
        assert len(view.obtener_matrices()) == 0
        assert "0 de 5 matrices" in view.status_lbl.cget("text")

    def test_02_period_selection_view_flujo(self, app_root):
        view = PeriodSelectionView(app_root)
        p = view.obtener_periodo()
        assert p is not None
        assert p.tipo_periodo == TipoPeriodo.SEMANA
        assert p.anio == 2026
        assert p.mes == 9
        assert p.semana == 1
        assert "Septiembre 2026 — Semana 1" in p.etiqueta

        # Inyectar período tipo MES
        p_mes = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026",
        )
        view.configurar_periodo_directo(p_mes)
        assert view.obtener_periodo().tipo_periodo == TipoPeriodo.MES

    def test_03_validation_view_estados(self, app_root, rutas_oficiales, tmp_path):
        view = ValidationView(app_root)
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 — Semana 1",
        )

        # 1. Sin matrices: bloqueado
        status1 = view.actualizar_estado({}, periodo)
        assert status1.listo_para_procesar is False
        assert view.btn_ejecutar.cget("state") == "disabled"

        # 2. Con 5 matrices válidas: habilitado
        status2 = view.actualizar_estado(rutas_oficiales, periodo)
        assert status2.listo_para_procesar is True
        assert view.btn_ejecutar.cget("state") == "normal"

        # 3. Durante ejecución: bloqueado
        view.set_ejecucion_activa(True)
        assert view.btn_ejecutar.cget("state") == "disabled"
        assert view.btn_validar.cget("state") == "disabled"

        # 4. Final de ejecución: restaurado
        view.set_ejecucion_activa(False)
        assert view.btn_ejecutar.cget("state") == "normal"
        assert view.btn_validar.cget("state") == "normal"

    def test_04_progress_view_etapas(self, app_root):
        view = ProgressView(app_root)

        # Inicio
        view.etapa_iniciada(1, "Identificando matrices")
        assert view.stage_widgets[1]["status"].cget("text") == "En progreso..."

        # Completar
        view.etapa_completada(1, "Identificando matrices")
        assert view.stage_widgets[1]["status"].cget("text") == "Finalizada"

        # Advertencia
        view.agregar_advertencia("Dato incompleto detectado")
        assert "Dato incompleto" in view.lbl_warning.cget("text")

        # Fallo
        view.etapa_fallida(2, "Hashes", "Error de lectura")
        assert view.stage_widgets[2]["status"].cget("text") == "Error"

        # Reiniciar
        view.reiniciar()
        assert view.stage_widgets[1]["status"].cget("text") == "Pendiente"
        assert view.stage_widgets[2]["status"].cget("text") == "Pendiente"

    def test_05_result_view_presentacion(self, app_root):
        view = ResultView(app_root)

        res = PipelineExecutionResult(
            execution_id="test-1234",
            timestamp="2026-09-13T12:00:00",
            periodo="Septiembre 2026 — Semana 1",
            tipo_periodo="SEMANA",
            estado_final="EXITOSO_CON_DISCREPANCIAS_REGISTRADAS",
            total_actividades=1,
            total_participaciones=18,
            total_personas_unicas=18,
            total_discrepancias=2,
            ruta_docx=str(OUTPUT_DIR / "test_salida.docx"),
            sha256_docx="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            tamanio_docx_bytes=45000,
        )

        view.mostrar_resultado(res)
        assert view.val_actividades.cget("text") == "1"
        assert view.val_participaciones.cget("text") == "18"
        assert view.val_personas.cget("text") == "18"
        assert view.val_discrepancias.cget("text") == "2"
        assert "Septiembre 2026 — Semana 1" in view.periodo_lbl.cget("text")

    def test_06_main_window_integracion(self, app_root):
        window = MainWindow(app_root)
        assert window.tabview is not None
        assert window.matrix_view is not None
        assert window.period_view is not None
        assert window.validation_view is not None
        assert window.progress_view is not None
        assert window.result_view is not None

    def test_07_main_window_iniciar_ejecucion_prepara_worker(self, app_root, rutas_oficiales):
        window = MainWindow(app_root)
        window.matrix_view.cargar_matrices_directas(rutas_oficiales)
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 — Semana 1",
        )
        window.period_view.configurar_periodo_directo(periodo)
        window._sincronizar_preflight()

        # Verificar que el botón de ejecutar está habilitado
        assert window.validation_view.btn_ejecutar.cget("state") == "normal"

        # Simular inicio de ejecución sin bloquear
        window._on_iniciar_ejecucion()
        assert window.worker is not None
        assert window.worker.is_alive()
        assert window.worker.informes_narrativos is not None
        assert "caso_real_sept_2026" in window.worker.informes_narrativos

        # Esperar que el worker termine
        window.worker.join(timeout=60.0)
        assert not window.worker.is_alive()

        # Procesar los eventos en MainWindow
        window._procesar_eventos_pendientes()
        assert window.result_view.resultado_actual is not None
        assert window.result_view.resultado_actual.total_discrepancias == 3
        assert window.result_view.resultado_actual.total_personas_unicas == 18

        # Limpieza explícita en el hilo principal para evitar deadlocks de Tk en hilos secundarios
        try:
            window.destroy()
        except Exception:
            pass
        import gc
        gc.collect()

