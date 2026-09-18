"""
app.word_consolidator.ui.workers.consolidation_worker

Hilo de ejecución asíncrono para la consolidación institucional BICU (Fase 14.9).
Ejecuta el orquestador WordConsolidationPipeline en segundo plano sin congelar la UI.
Emite eventos de progreso determinísticos por etapas hacia una cola segura (queue.Queue).
"""

from enum import Enum
from functools import wraps
from pathlib import Path
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union

from app.word_consolidator.models import MetadatosInstitucionales, PeriodoConsolidacion
from app.word_consolidator.pipeline import (
    PipelineExecutionResult,
    WordConsolidationPipeline,
)
from app.word_consolidator.ui.services.error_translator import (
    ErrorInstitucionalInfo,
    ErrorTranslator,
)


class ConsolidationEventType(str, Enum):
    """Tipos de eventos emitidos durante el ciclo de vida de la consolidación."""
    STARTED = "STARTED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"
    WARNING = "WARNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


ETAPAS_PIPELINE: List[Dict[str, Any]] = [
    {"index": 1, "id": "identificacion", "name": "Identificando matrices oficiales M1–M5"},
    {"index": 2, "id": "hashes_iniciales", "name": "Verificando hashes criptográficos SHA-256 iniciales"},
    {"index": 3, "id": "lectura", "name": "Leyendo matrices Excel de forma no destructiva"},
    {"index": 4, "id": "filtrado", "name": "Filtrando período temporal estricto (cero inferencias)"},
    {"index": 5, "id": "consolidacion", "name": "Consolidando participantes y resolviendo identidades"},
    {"index": 6, "id": "discrepancias", "name": "Evaluando protocolo de discrepancias institucionales"},
    {"index": 7, "id": "transformacion", "name": "Construyendo Modelo Documental Intermedio"},
    {"index": 8, "id": "renderizado", "name": "Generando documento Word institucional (.docx)"},
    {"index": 9, "id": "auditoria", "name": "Verificando inmutabilidad y generando auditoría E2E"},
]


class ConsolidationEvent:
    """Evento estructurado emitido por el hilo de trabajo hacia la interfaz gráfica."""

    def __init__(
        self,
        event_type: ConsolidationEventType,
        step_index: Optional[int] = None,
        step_name: Optional[str] = None,
        message: Optional[str] = None,
        result: Optional[PipelineExecutionResult] = None,
        error_info: Optional[ErrorInstitucionalInfo] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.step_index = step_index
        self.step_name = step_name
        self.message = message
        self.result = result
        self.error_info = error_info
        self.data = data or {}

    def __repr__(self) -> str:
        return f"<ConsolidationEvent type={self.event_type} step={self.step_index} msg='{self.message}'>"


class ConsolidationWorker(threading.Thread):
    """
    Hilo de trabajo independiente para ejecutar la consolidación.
    Garantiza que la interfaz gráfica nunca se bloquee durante operaciones pesadas de I/O.
    """

    def __init__(
        self,
        fuentes: Dict[str, Path],
        periodo: PeriodoConsolidacion,
        salida_dir: Path,
        event_queue: queue.Queue,
        metadatos: Optional[MetadatosInstitucionales] = None,
        informes_narrativos: Optional[Dict[str, Dict[str, Any]]] = None,
        ruta_docx_salida: Optional[Path] = None,
        generar_tecnico: bool = True,
        generar_institucional: bool = True,
    ):
        super().__init__(name="ConsolidationWorkerThread", daemon=True)
        self.fuentes = fuentes
        self.periodo = periodo
        self.salida_dir = salida_dir
        self.event_queue = event_queue
        self.metadatos = metadatos if metadatos is not None else MetadatosInstitucionales()
        self.informes_narrativos = informes_narrativos
        self.ruta_docx_salida = ruta_docx_salida
        self.generar_tecnico = generar_tecnico
        self.generar_institucional = generar_institucional
        self._cancel_requested = False

    def emitir(
        self,
        tipo: ConsolidationEventType,
        step_index: Optional[int] = None,
        step_name: Optional[str] = None,
        message: Optional[str] = None,
        result: Optional[PipelineExecutionResult] = None,
        error_info: Optional[ErrorInstitucionalInfo] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Coloca un evento en la cola de mensajes de forma segura."""
        evento = ConsolidationEvent(
            event_type=tipo,
            step_index=step_index,
            step_name=step_name,
            message=message,
            result=result,
            error_info=error_info,
            data=data,
        )
        self.event_queue.put(evento)

    def run(self) -> None:
        """Punto de entrada del hilo de ejecución."""
        self.emitir(
            ConsolidationEventType.STARTED,
            message=f"Iniciando consolidación para {self.periodo.etiqueta}",
        )

        etapa_actual = 1

        try:
            pipeline = WordConsolidationPipeline(output_dir=self.salida_dir)

            # Instrumentar el pipeline existente con emisión de etapas sin modificar pipeline.py
            orig_resolver_fuentes = pipeline._resolver_fuentes
            orig_filtrar_fechas = pipeline._filtrar_fechas_estricto
            orig_guardar_auditoria = pipeline._guardar_reporte_auditoria

            # Importar módulos de dominio para envolver llamadas de etapas
            from app.word_consolidator.readers.matrix_reader import MatrixReader
            from app.word_consolidator.engine.consolidation_engine import ConsolidationEngine
            from app.word_consolidator.engine.discrepancy_detector import DiscrepancyDetector
            from app.word_consolidator.document.orchestrator import DocumentOutputOrchestrator

            orig_leer_matrices = MatrixReader.leer_conjunto_matrices
            orig_consolidar = ConsolidationEngine.consolidar
            orig_evaluar_auditoria = DiscrepancyDetector.evaluar_consolidacion
            orig_orchestrate = DocumentOutputOrchestrator.orchestrate_generation

            # Wrappers para registrar y emitir eventos de progreso reales
            def wrapped_resolver_fuentes(*args: Any, **kwargs: Any) -> Any:
                nonlocal etapa_actual
                etapa_actual = 1
                self.emitir(ConsolidationEventType.STEP_STARTED, 1, ETAPAS_PIPELINE[0]["name"])
                res = orig_resolver_fuentes(*args, **kwargs)
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 1, ETAPAS_PIPELINE[0]["name"])
                # Inmediatamente tras resolver fuentes, pipeline calcula hashes iniciales
                etapa_actual = 2
                self.emitir(ConsolidationEventType.STEP_STARTED, 2, ETAPAS_PIPELINE[1]["name"])
                return res

            def wrapped_leer_matrices(*args: Any, **kwargs: Any) -> Any:
                nonlocal etapa_actual
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 2, ETAPAS_PIPELINE[1]["name"])
                etapa_actual = 3
                self.emitir(ConsolidationEventType.STEP_STARTED, 3, ETAPAS_PIPELINE[2]["name"])
                res = orig_leer_matrices(*args, **kwargs)
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 3, ETAPAS_PIPELINE[2]["name"])
                return res

            def wrapped_filtrar_fechas(*args: Any, **kwargs: Any) -> Any:
                nonlocal etapa_actual
                etapa_actual = 4
                self.emitir(ConsolidationEventType.STEP_STARTED, 4, ETAPAS_PIPELINE[3]["name"])
                res = orig_filtrar_fechas(*args, **kwargs)
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 4, ETAPAS_PIPELINE[3]["name"])
                return res

            def wrapped_consolidar(*args: Any, **kwargs: Any) -> Any:
                nonlocal etapa_actual
                etapa_actual = 5
                self.emitir(ConsolidationEventType.STEP_STARTED, 5, ETAPAS_PIPELINE[4]["name"])
                res = orig_consolidar(*args, **kwargs)
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 5, ETAPAS_PIPELINE[4]["name"])
                return res

            def wrapped_evaluar_auditoria(*args: Any, **kwargs: Any) -> Any:
                nonlocal etapa_actual
                etapa_actual = 6
                self.emitir(ConsolidationEventType.STEP_STARTED, 6, ETAPAS_PIPELINE[5]["name"])
                res = orig_evaluar_auditoria(*args, **kwargs)
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 6, ETAPAS_PIPELINE[5]["name"])
                return res

            def wrapped_orchestrate(*args: Any, **kwargs: Any) -> Any:
                nonlocal etapa_actual
                etapa_actual = 7
                self.emitir(ConsolidationEventType.STEP_STARTED, 7, ETAPAS_PIPELINE[6]["name"])
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 7, ETAPAS_PIPELINE[6]["name"])
                etapa_actual = 8
                self.emitir(ConsolidationEventType.STEP_STARTED, 8, "Generando documentos Word (Técnico e Institucional)")
                res = orig_orchestrate(*args, **kwargs)
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 8, "Generando documentos Word (Técnico e Institucional)")
                return res

            def wrapped_guardar_auditoria(*args: Any, **kwargs: Any) -> Any:
                nonlocal etapa_actual
                etapa_actual = 9
                self.emitir(ConsolidationEventType.STEP_STARTED, 9, ETAPAS_PIPELINE[8]["name"])
                res = orig_guardar_auditoria(*args, **kwargs)
                self.emitir(ConsolidationEventType.STEP_COMPLETED, 9, ETAPAS_PIPELINE[8]["name"])
                return res

            # Aplicar temporalmente los hooks al orquestador
            pipeline._resolver_fuentes = wrapped_resolver_fuentes  # type: ignore
            pipeline._filtrar_fechas_estricto = wrapped_filtrar_fechas  # type: ignore
            pipeline._guardar_reporte_auditoria = wrapped_guardar_auditoria  # type: ignore

            MatrixReader.leer_conjunto_matrices = staticmethod(wrapped_leer_matrices)  # type: ignore
            ConsolidationEngine.consolidar = staticmethod(wrapped_consolidar)  # type: ignore
            DiscrepancyDetector.evaluar_consolidacion = staticmethod(wrapped_evaluar_auditoria)  # type: ignore
            DocumentOutputOrchestrator.orchestrate_generation = staticmethod(wrapped_orchestrate)  # type: ignore

            try:
                resultado = pipeline.ejecutar(
                    fuentes=self.fuentes,
                    periodo=self.periodo,
                    metadatos=self.metadatos,
                    informes_narrativos=self.informes_narrativos,
                    ruta_docx_salida=self.ruta_docx_salida,
                    salida_dir=self.salida_dir,
                    generar_tecnico=self.generar_tecnico,
                    generar_institucional=self.generar_institucional,
                )
            finally:
                # Restaurar siempre las funciones originales
                pipeline._resolver_fuentes = orig_resolver_fuentes  # type: ignore
                pipeline._filtrar_fechas_estricto = orig_filtrar_fechas  # type: ignore
                pipeline._guardar_reporte_auditoria = orig_guardar_auditoria  # type: ignore

                MatrixReader.leer_conjunto_matrices = orig_leer_matrices  # type: ignore
                ConsolidationEngine.consolidar = orig_consolidar  # type: ignore
                DiscrepancyDetector.evaluar_consolidacion = orig_evaluar_auditoria  # type: ignore
                DocumentOutputOrchestrator.orchestrate_generation = orig_orchestrate  # type: ignore

            # Emitir advertencias si existen
            if resultado.warnings:
                for w in resultado.warnings:
                    self.emitir(ConsolidationEventType.WARNING, message=w)

            # Notificar finalización exitosa
            self.emitir(
                ConsolidationEventType.COMPLETED,
                message="Consolidación institucional completada exitosamente.",
                result=resultado,
            )

        except Exception as ex:
            error_info = ErrorTranslator.traducir(ex)
            self.emitir(
                ConsolidationEventType.STEP_FAILED,
                step_index=etapa_actual,
                step_name=ETAPAS_PIPELINE[etapa_actual - 1]["name"] if 1 <= etapa_actual <= len(ETAPAS_PIPELINE) else "Proceso",
                message=str(ex),
            )
            self.emitir(
                ConsolidationEventType.ERROR,
                message=error_info.mensaje_principal,
                error_info=error_info,
            )
