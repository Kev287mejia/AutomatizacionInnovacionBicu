"""
tests.test_word_consolidator.test_ui_worker

Pruebas unitarias y de concurrencia para ConsolidationWorker y eventos de cola (Fase 14.9).
Valida:
1. Emisión estructurada de eventos (STARTED, STEP_STARTED, STEP_COMPLETED, COMPLETED, ERROR).
2. Ejecución asíncrona sin bloqueo del hilo principal.
3. Manejo de excepciones y traducción automática de errores durante el ciclo del hilo.
"""

from pathlib import Path
import queue
import time
import pytest

from app.word_consolidator.models import PeriodoConsolidacion, TipoPeriodo
from app.word_consolidator.pipeline import PipelineExecutionResult
from app.word_consolidator.ui.workers.consolidation_worker import (
    ConsolidationEvent,
    ConsolidationEventType,
    ConsolidationWorker,
    ETAPAS_PIPELINE,
)

OUTPUT_DIR = Path("output")


@pytest.fixture
def rutas_matrices_oficiales_output():
    """Retorna las rutas a las matrices con la corrida real de Septiembre 2026."""
    return {
        "M1": OUTPUT_DIR / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": OUTPUT_DIR / "Matriz_2_Estudiantes.xlsx",
        "M3": OUTPUT_DIR / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": OUTPUT_DIR / "Matriz_4_Colaboradores.xlsx",
        "M5": OUTPUT_DIR / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }



class TestConsolidationWorker:
    """Suite de pruebas para ConsolidationWorker."""

    def test_01_definicion_de_etapas(self):
        assert len(ETAPAS_PIPELINE) == 9
        assert ETAPAS_PIPELINE[0]["index"] == 1
        assert "identificacion" in ETAPAS_PIPELINE[0]["id"]
        assert ETAPAS_PIPELINE[-1]["index"] == 9
        assert "auditoria" in ETAPAS_PIPELINE[-1]["id"]

    def test_02_emision_manual_de_eventos(self):
        q = queue.Queue()
        dummy_periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 — Semana 1",
        )
        worker = ConsolidationWorker(
            fuentes={},
            periodo=dummy_periodo,
            salida_dir=Path("output"),
            event_queue=q,
        )
        assert worker.daemon is True

        worker.emitir(ConsolidationEventType.STARTED, message="Inicio de prueba")
        worker.emitir(ConsolidationEventType.STEP_STARTED, step_index=1, step_name="Paso 1")
        worker.emitir(ConsolidationEventType.STEP_COMPLETED, step_index=1, step_name="Paso 1")
        worker.emitir(ConsolidationEventType.WARNING, message="Aviso no bloqueante")

        eventos = []
        while not q.empty():
            eventos.append(q.get_nowait())

        assert len(eventos) == 4
        assert eventos[0].event_type == ConsolidationEventType.STARTED
        assert eventos[1].event_type == ConsolidationEventType.STEP_STARTED
        assert eventos[1].step_index == 1
        assert eventos[2].event_type == ConsolidationEventType.STEP_COMPLETED
        assert eventos[3].event_type == ConsolidationEventType.WARNING

    def test_03_ejecucion_error_matrices_faltantes(self, tmp_path):
        q = queue.Queue()
        dummy_periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 — Semana 1",
        )
        # Pasar fuentes vacías para forzar MatricesFaltantesError
        worker = ConsolidationWorker(
            fuentes={},
            periodo=dummy_periodo,
            salida_dir=tmp_path,
            event_queue=q,
        )
        worker.start()
        worker.join(timeout=10.0)
        assert not worker.is_alive()

        eventos = []
        while not q.empty():
            eventos.append(q.get_nowait())

        tipos = [e.event_type for e in eventos]
        assert ConsolidationEventType.STARTED in tipos
        assert ConsolidationEventType.STEP_FAILED in tipos
        assert ConsolidationEventType.ERROR in tipos

        evento_error = [e for e in eventos if e.event_type == ConsolidationEventType.ERROR][0]
        assert evento_error.error_info is not None
        assert evento_error.error_info.titulo == "Matrices Oficiales Incompletas"
        assert evento_error.error_info.es_bloqueante is True

    def test_04_ejecucion_exitosa_caso_real(self, rutas_matrices_oficiales_output, tmp_path):
        """Valida que el worker complete las 9 etapas reales con las matrices oficiales."""
        import gc
        gc.collect()

        q = queue.Queue()
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 - Semana 1",
        )

        worker = ConsolidationWorker(
            fuentes=rutas_matrices_oficiales_output,
            periodo=periodo,
            salida_dir=tmp_path,
            event_queue=q,
        )
        worker.start()
        worker.join(timeout=60.0)
        assert not worker.is_alive()

        eventos = []
        while not q.empty():
            eventos.append(q.get_nowait())

        tipos = [e.event_type for e in eventos]
        assert ConsolidationEventType.STARTED in tipos
        assert ConsolidationEventType.COMPLETED in tipos
        assert ConsolidationEventType.ERROR not in tipos

        # Verificar que se emitieron etapas de inicio y fin
        steps_started = [e.step_index for e in eventos if e.event_type == ConsolidationEventType.STEP_STARTED]
        steps_completed = [e.step_index for e in eventos if e.event_type == ConsolidationEventType.STEP_COMPLETED]
        assert 1 in steps_started
        assert 9 in steps_completed

        # Verificar resultado en COMPLETED
        evento_completed = [e for e in eventos if e.event_type == ConsolidationEventType.COMPLETED][0]
        res: PipelineExecutionResult = evento_completed.result
        assert res is not None
        assert res.total_actividades == 1
        assert res.total_personas_unicas == 18
        assert res.total_participaciones == 18
        assert Path(res.ruta_docx).exists()
        assert Path(res.ruta_reporte_json).exists()
        assert Path(res.ruta_reporte_md).exists()
