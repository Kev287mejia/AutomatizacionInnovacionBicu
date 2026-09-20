"""app.application.use_cases.batch.procesar_pipeline_desde_word

Caso de uso de aplicación que orquesta el flujo encadenado para un documento Word individual:
    DOCX institucional
          ↓
    IngestarActividadDesdeWordUseCase (atómico, por archivo)
          ↓
    ProcesarPipelineActividadUseCase (Quality Q-01..Q-20 + Routing + ExportPrep)
          ↓
    PipelineDesdeWordResultDTO

Reglas arquitectónicas:
- Application Layer: NO importa sqlite3, python-docx ni openpyxl.
- Decisión P-01: NO realiza exportación física individual (XLSX). La exportación física
  se realiza de forma consolidada al final del lote mediante ExportarMatricesPeriodoUseCase.
- Decisión P-02: 0 participantes nominales es el comportamiento esperado en actividades
  extraídas de Word; NO se crean participantes ficticios.
- Decisión P-03: GAP-3 de posible duplicado emite advertencia heurística pero NO bloquea.
- Transaccionalidad: Cada archivo es una unidad transaccional independiente (éxito parcial en lote).
- Dry-run: Cuando dry_run=True, utiliza almacenamiento en memoria (InMemoryUnitOfWork)
  garantizando cero mutaciones persistentes en SQLite.
"""

from pathlib import Path
from typing import List, Optional, Union

from app.application.commands.pipeline_commands import EjecutarPipelineActividadCommand
from app.application.dto.batch_dtos import PipelineDesdeWordResultDTO
from app.application.dto.export_dtos import PoliticaExportacionRevision
from app.application.fakes.in_memory_uow import InMemoryUnitOfWork
from app.application.use_cases.ingestar_actividad_desde_word import (
    IngestarActividadDesdeWordUseCase,
)
from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)
from app.audit.audit_logger import get_logger
from app.core.ports.unit_of_work import IUnitOfWork

logger = get_logger(__name__)


class ProcesarPipelineDesdeWordUseCase:
    """Orquestador de aplicación para encadenar Ingesta y Pipeline de un archivo Word."""

    def __init__(
        self,
        ingesta_use_case: IngestarActividadDesdeWordUseCase,
        pipeline_use_case: ProcesarPipelineActividadUseCase,
        uow: Optional[IUnitOfWork] = None,
    ) -> None:
        """Inicializa el caso de uso con sus dependencias de aplicación.

        Args:
            ingesta_use_case: Caso de uso de ingesta atómica de Word hacia SQLite.
            pipeline_use_case: Caso de uso del pipeline institucional (Quality + Routing + Prep).
            uow: Unidad de trabajo transaccional (opcional, utiliza el de ingesta si no se provee).
        """
        self._ingesta_use_case = ingesta_use_case
        self._pipeline_use_case = pipeline_use_case
        self._uow = uow or getattr(ingesta_use_case, "_uow", None)

    def execute(
        self,
        file_path: Union[str, Path],
        dry_run: bool = False,
        politica_revision: PoliticaExportacionRevision = PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
        posible_duplicado_advertido: bool = False,
        advertencias_adicionales: Optional[List[str]] = None,
    ) -> PipelineDesdeWordResultDTO:
        """Ejecuta el flujo encadenado de ingesta y pipeline para un archivo DOCX.

        Args:
            file_path: Ruta al archivo DOCX a procesar.
            dry_run: Si True, no realiza escrituras persistentes en SQLite.
            politica_revision: Política OPEN-02 para el pipeline de exportación.
            posible_duplicado_advertido: True si la heurística GAP-3 detectó coincidencia de nombre.
            advertencias_adicionales: Advertencias externas previas a incorporar en el resultado.

        Returns:
            PipelineDesdeWordResultDTO con el diagnóstico completo del archivo.
        """
        path = Path(file_path)
        nombre_archivo = path.name
        advertencias_acumuladas: List[str] = list(advertencias_adicionales or [])
        errores_acumulados: List[str] = []

        if posible_duplicado_advertido:
            advertencias_acumuladas.append(
                f"[GAP-3] Advertencia heurística: El archivo '{nombre_archivo}' ya fue visto "
                "en el lote o en SQLite. No es garantía de identidad documental; el procesamiento continúa."
            )

        logger.info(
            f"Procesando pipeline para DOCX '{nombre_archivo}' (dry_run={dry_run})."
        )

        # ------------------------------------------------------------------
        # PASO 1: Ingesta atómica hacia SQLite (o memoria si dry_run)
        # ------------------------------------------------------------------
        uow_activo: Optional[IUnitOfWork] = self._uow
        if dry_run:
            uow_activo = InMemoryUnitOfWork()
            ingesta_runner = IngestarActividadDesdeWordUseCase(
                extractor=self._ingesta_use_case._extractor,
                uow=uow_activo,
            )
        else:
            ingesta_runner = self._ingesta_use_case

        try:
            ingesta_res = ingesta_runner.execute(path)
        except Exception as exc:
            logger.error(f"Excepción inesperada durante ingesta de '{nombre_archivo}': {exc}")
            errores_acumulados.append(f"Excepción en ingesta: {exc}")
            return PipelineDesdeWordResultDTO(
                nombre_archivo=nombre_archivo,
                exitoso=False,
                id_actividad=None,
                tipo_documento=None,
                ingesta_exitosa=False,
                evidencias_registradas=0,
                motivo_rechazo=f"Excepción técnica en ingesta: {exc}",
                pipeline_ejecutado=False,
                calidad_estado=None,
                total_hallazgos=0,
                total_participaciones=0,
                advertencias=advertencias_acumuladas,
                errores=errores_acumulados,
                posible_duplicado_advertido=posible_duplicado_advertido,
            )

        # Acumular advertencias y errores de la ingesta
        advertencias_acumuladas.extend(ingesta_res.advertencias)
        errores_acumulados.extend(ingesta_res.errores)

        tipo_doc_str: Optional[str] = None
        if ingesta_res.tipo_documento is not None:
            tipo_doc_str = (
                ingesta_res.tipo_documento.value
                if hasattr(ingesta_res.tipo_documento, "value")
                else str(ingesta_res.tipo_documento)
            )

        # Si fue omitido por duplicado (GAP-3)
        if getattr(ingesta_res, "posible_duplicado", False):
            logger.info(
                f"Documento '{nombre_archivo}' omitido por duplicado (GAP-3). El lote continúa."
            )
            return PipelineDesdeWordResultDTO(
                nombre_archivo=nombre_archivo,
                exitoso=True,
                id_actividad=None,
                tipo_documento=tipo_doc_str,
                ingesta_exitosa=True,
                evidencias_registradas=0,
                motivo_rechazo=None,
                pipeline_ejecutado=False,
                calidad_estado=None,
                total_hallazgos=0,
                total_participaciones=0,
                advertencias=advertencias_acumuladas,
                errores=errores_acumulados,
                posible_duplicado_advertido=True,
            )

        # Si la ingesta no fue exitosa (documento rechazado o incompatible)
        if not ingesta_res.exitoso or not ingesta_res.id_actividad:
            logger.info(
                f"Documento '{nombre_archivo}' rechazado en ingesta: {ingesta_res.motivo_rechazo}"
            )
            return PipelineDesdeWordResultDTO(
                nombre_archivo=nombre_archivo,
                exitoso=False,
                id_actividad=None,
                tipo_documento=tipo_doc_str,
                ingesta_exitosa=False,
                evidencias_registradas=0,
                motivo_rechazo=ingesta_res.motivo_rechazo,
                pipeline_ejecutado=False,
                calidad_estado=None,
                total_hallazgos=0,
                total_participaciones=0,
                advertencias=advertencias_acumuladas,
                errores=errores_acumulados,
                posible_duplicado_advertido=posible_duplicado_advertido,
            )

        id_actividad = ingesta_res.id_actividad
        evidencias_count = ingesta_res.evidencias_registradas_count

        # ------------------------------------------------------------------
        # PASO 2: Ejecución del Pipeline Institucional (Quality + Routing + Prep)
        # ------------------------------------------------------------------
        cmd_pipeline = EjecutarPipelineActividadCommand(
            id_actividad=id_actividad,
            dry_run=dry_run,
            persistir_discrepancias=(not dry_run),
            politica_revision=politica_revision,
            fuente_archivo_informe=nombre_archivo,
        )

        try:
            pipeline_res = self._pipeline_use_case.execute(
                cmd_pipeline,
                uow=uow_activo,
            )
        except Exception as exc:
            logger.error(f"Excepción en pipeline institucional para '{nombre_archivo}': {exc}")
            errores_acumulados.append(f"Excepción en pipeline institucional: {exc}")
            return PipelineDesdeWordResultDTO(
                nombre_archivo=nombre_archivo,
                exitoso=False,
                id_actividad=id_actividad,
                tipo_documento=tipo_doc_str,
                ingesta_exitosa=True,
                evidencias_registradas=evidencias_count,
                motivo_rechazo=None,
                pipeline_ejecutado=False,
                calidad_estado=None,
                total_hallazgos=0,
                total_participaciones=0,
                advertencias=advertencias_acumuladas,
                errores=errores_acumulados,
                posible_duplicado_advertido=posible_duplicado_advertido,
            )

        # Extraer métricas de Quality y Routing
        calidad_estado: Optional[str] = None
        total_hallazgos = 0
        if pipeline_res.calidad:
            calidad_estado = pipeline_res.calidad.estado_general_calidad
            total_hallazgos = len(pipeline_res.calidad.hallazgos)

            # Acumular advertencias y errores desde los hallazgos de calidad
            for h in pipeline_res.calidad.hallazgos:
                if h.severidad in ("WARNING", "REVISION", "INFO"):
                    advertencias_acumuladas.append(f"[{h.codigo_regla}] {h.mensaje_humano}")
                elif h.severidad in ("ERROR", "CRITICAL"):
                    errores_acumulados.append(f"[{h.codigo_regla}] {h.mensaje_humano}")

        total_participaciones = pipeline_res.total_participaciones_ingreso

        # Determinar éxito global del procesamiento del archivo
        # En flujo institucional: CONFORME y CON_OBSERVACIONES son estados procesables / exportables.
        # Si estado es BLOQUEADO o existen errores técnicos, exitoso_global es False.
        es_bloqueado = (calidad_estado == "BLOQUEADO")
        exitoso_global = (not es_bloqueado) and (len(errores_acumulados) == 0)

        return PipelineDesdeWordResultDTO(
            nombre_archivo=nombre_archivo,
            exitoso=exitoso_global,
            id_actividad=id_actividad,
            tipo_documento=tipo_doc_str,
            ingesta_exitosa=True,
            evidencias_registradas=evidencias_count,
            motivo_rechazo=None,
            pipeline_ejecutado=True,
            calidad_estado=calidad_estado,
            total_hallazgos=total_hallazgos,
            total_participaciones=total_participaciones,
            advertencias=advertencias_acumuladas,
            errores=errores_acumulados,
            posible_duplicado_advertido=posible_duplicado_advertido,
        )
