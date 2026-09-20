"""app.word_consolidator.ui.workers.word_batch_worker

Hilo de ejecución asíncrono para el procesamiento de lotes Word institucionales (Fase 28.2).
Ejecuta IngestarCarpetaWordUseCase en segundo plano sin congelar la UI.
Emite eventos estructurados por etapas hacia una cola segura (queue.Queue).
"""

from enum import Enum
from pathlib import Path
import queue
import threading
from typing import Any, Dict, List, Optional, Union

from app.application.commands.batch_commands import IngestarCarpetaWordCommand
from app.application.dto.batch_dtos import BatchResultadoDTO
from app.application.use_cases.batch.ingestar_carpeta_word import (
    IngestarCarpetaWordUseCase,
)
from app.word_consolidator.ui.services.error_translator import (
    ErrorInstitucionalInfo,
    ErrorTranslator,
)
from app.word_consolidator.ui.services.word_batch_service import (
    WordBatchAppService,
)


class WordBatchEventType(str, Enum):
    """Tipos de eventos emitidos durante el ciclo de vida del procesamiento por lote."""
    BATCH_STARTED = "BATCH_STARTED"
    STAGE_STARTED = "STAGE_STARTED"
    STAGE_COMPLETED = "STAGE_COMPLETED"
    FILE_STARTED = "FILE_STARTED"
    FILE_COMPLETED = "FILE_COMPLETED"
    WARNING = "WARNING"
    BATCH_COMPLETED = "BATCH_COMPLETED"
    BATCH_FAILED = "BATCH_FAILED"


ETAPAS_WORD_BATCH: List[Dict[str, Any]] = [
    {"index": 1, "id": "descubrimiento", "name": "Descubrimiento de documentos Word (.docx)"},
    {"index": 2, "id": "ingesta", "name": "Ingesta atómica hacia SQLite SSOT"},
    {"index": 3, "id": "calidad", "name": "Validación de reglas de calidad Q-01..Q-20"},
    {"index": 4, "id": "enrutamiento", "name": "Enrutamiento institucional de participaciones"},
    {"index": 5, "id": "exportacion", "name": "Exportación consolidada de matrices M1–M5"},
    {"index": 6, "id": "manifiesto", "name": "Generación de manifiesto criptográfico JSON"},
]


class WordBatchEvent:
    """Evento estructurado emitido por el hilo de trabajo hacia la interfaz gráfica."""

    def __init__(
        self,
        event_type: WordBatchEventType,
        step_index: Optional[int] = None,
        step_name: Optional[str] = None,
        message: Optional[str] = None,
        file_name: Optional[str] = None,
        file_index: Optional[int] = None,
        total_files: Optional[int] = None,
        result: Optional[BatchResultadoDTO] = None,
        error_info: Optional[ErrorInstitucionalInfo] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.step_index = step_index
        self.step_name = step_name
        self.message = message
        self.file_name = file_name
        self.file_index = file_index
        self.total_files = total_files
        self.result = result
        self.error_info = error_info
        self.data = data or {}

    def __repr__(self) -> str:
        return f"<WordBatchEvent type={self.event_type} step={self.step_index} msg='{self.message}'>"


class WordBatchWorker(threading.Thread):
    """Hilo de trabajo independiente para ejecutar el procesamiento de lotes Word.

    Garantiza que la interfaz gráfica permanezca receptiva durante operaciones pesadas de I/O.
    """

    def __init__(
        self,
        carpeta_origen: Union[str, Path],
        carpeta_salida: Union[str, Path],
        event_queue: queue.Queue,
        dry_run: bool = False,
        patron_glob: str = "*.docx",
        batch_orchestrator: Optional[IngestarCarpetaWordUseCase] = None,
    ):
        super().__init__(name="WordBatchWorkerThread", daemon=True)
        self.carpeta_origen = Path(carpeta_origen)
        self.carpeta_salida = Path(carpeta_salida)
        self.event_queue = event_queue
        self.dry_run = dry_run
        self.patron_glob = patron_glob
        self.batch_orchestrator = batch_orchestrator

    def emitir(
        self,
        tipo: WordBatchEventType,
        step_index: Optional[int] = None,
        step_name: Optional[str] = None,
        message: Optional[str] = None,
        file_name: Optional[str] = None,
        file_index: Optional[int] = None,
        total_files: Optional[int] = None,
        result: Optional[BatchResultadoDTO] = None,
        error_info: Optional[ErrorInstitucionalInfo] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Coloca un evento en la cola de mensajes de forma segura."""
        evento = WordBatchEvent(
            event_type=tipo,
            step_index=step_index,
            step_name=step_name,
            message=message,
            file_name=file_name,
            file_index=file_index,
            total_files=total_files,
            result=result,
            error_info=error_info,
            data=data,
        )
        self.event_queue.put(evento)

    def run(self) -> None:
        """Punto de entrada del hilo de trabajo."""
        self.emitir(
            WordBatchEventType.BATCH_STARTED,
            message=f"Iniciando procesamiento de lote en '{self.carpeta_origen.name}'",
        )

        try:
            orchestrator = self.batch_orchestrator
            if orchestrator is None:
                orchestrator = WordBatchAppService.crear_batch_orchestrator()

            # Etapa 1: Descubrimiento
            self.emitir(
                WordBatchEventType.STAGE_STARTED,
                step_index=1,
                step_name=ETAPAS_WORD_BATCH[0]["name"],
            )

            # Envolver la ejecución de archivos para emitir progreso fino
            orig_pipeline_execute = orchestrator._pipeline_word_use_case.execute
            file_counter = 0

            def wrapped_pipeline_execute(*args: Any, **kwargs: Any) -> Any:
                nonlocal file_counter
                file_counter += 1
                file_path = kwargs.get("file_path") or (args[0] if args else None)
                fname = Path(file_path).name if file_path else f"Archivo {file_counter}"

                # En primer archivo, marcar etapa 1 completa y pasar a 2, 3, 4
                if file_counter == 1:
                    self.emitir(
                        WordBatchEventType.STAGE_COMPLETED,
                        step_index=1,
                        step_name=ETAPAS_WORD_BATCH[0]["name"],
                    )
                    self.emitir(
                        WordBatchEventType.STAGE_STARTED,
                        step_index=2,
                        step_name=ETAPAS_WORD_BATCH[1]["name"],
                    )
                    self.emitir(
                        WordBatchEventType.STAGE_STARTED,
                        step_index=3,
                        step_name=ETAPAS_WORD_BATCH[2]["name"],
                    )
                    self.emitir(
                        WordBatchEventType.STAGE_STARTED,
                        step_index=4,
                        step_name=ETAPAS_WORD_BATCH[3]["name"],
                    )

                self.emitir(
                    WordBatchEventType.FILE_STARTED,
                    file_name=fname,
                    file_index=file_counter,
                    message=f"Procesando: {fname}...",
                )

                pipe_res = orig_pipeline_execute(*args, **kwargs)

                status_desc = "ACEPTADO" if pipe_res.exitoso else "RECHAZADO"
                self.emitir(
                    WordBatchEventType.FILE_COMPLETED,
                    file_name=fname,
                    file_index=file_counter,
                    message=f"Completado: {fname} ({status_desc})",
                )
                return pipe_res

            orchestrator._pipeline_word_use_case.execute = wrapped_pipeline_execute

            # Envolver exportación de período
            if orchestrator._exportar_periodo_use_case is not None:
                orig_export_execute = orchestrator._exportar_periodo_use_case.execute

                def wrapped_export_execute(*args: Any, **kwargs: Any) -> Any:
                    self.emitir(
                        WordBatchEventType.STAGE_COMPLETED,
                        step_index=2,
                        step_name=ETAPAS_WORD_BATCH[1]["name"],
                    )
                    self.emitir(
                        WordBatchEventType.STAGE_COMPLETED,
                        step_index=3,
                        step_name=ETAPAS_WORD_BATCH[2]["name"],
                    )
                    self.emitir(
                        WordBatchEventType.STAGE_COMPLETED,
                        step_index=4,
                        step_name=ETAPAS_WORD_BATCH[3]["name"],
                    )
                    self.emitir(
                        WordBatchEventType.STAGE_STARTED,
                        step_index=5,
                        step_name=ETAPAS_WORD_BATCH[4]["name"],
                    )
                    res = orig_export_execute(*args, **kwargs)
                    self.emitir(
                        WordBatchEventType.STAGE_COMPLETED,
                        step_index=5,
                        step_name=ETAPAS_WORD_BATCH[4]["name"],
                    )
                    self.emitir(
                        WordBatchEventType.STAGE_STARTED,
                        step_index=6,
                        step_name=ETAPAS_WORD_BATCH[5]["name"],
                    )
                    return res

                orchestrator._exportar_periodo_use_case.execute = wrapped_export_execute

            # Construir y ejecutar el comando
            cmd = IngestarCarpetaWordCommand(
                carpeta_origen=self.carpeta_origen,
                patron_glob=self.patron_glob,
                recursivo=False,
                exportar_matrices=True,
                carpeta_salida=self.carpeta_salida,
                dry_run=self.dry_run,
                advertir_posibles_duplicados=True,
            )

            batch_res = orchestrator.execute(cmd)

            # Marcar etapa 6 como completada
            self.emitir(
                WordBatchEventType.STAGE_COMPLETED,
                step_index=6,
                step_name=ETAPAS_WORD_BATCH[5]["name"],
            )

            self.emitir(
                WordBatchEventType.BATCH_COMPLETED,
                result=batch_res,
                message="Procesamiento por lote completado exitosamente.",
            )

        except Exception as exc:
            error_info = ErrorTranslator.traducir(exc)
            self.emitir(
                WordBatchEventType.BATCH_FAILED,
                error_info=error_info,
                message=str(exc),
            )
