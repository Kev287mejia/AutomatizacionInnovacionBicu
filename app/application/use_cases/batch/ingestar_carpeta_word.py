"""app.application.use_cases.batch.ingestar_carpeta_word

Caso de uso central de aplicación para el procesamiento por lote (batch) de carpetas
que contienen documentos Word (.docx) de actividades institucionales BICU.

Flujo gobernado:
  1. Descubrimiento de archivos por patrón glob en carpeta_origen (omitiendo temporales de Word ~$*).
  2. Heurística GAP-3 de detección de duplicados simples en lote (advertir sin bloquear).
  3. Procesamiento atómico individual mediante ProcesarPipelineDesdeWordUseCase (éxito parcial).
  4. Agregación de métricas, balances y resultados por archivo.
  5. Decisión P-01: Exportación física consolidada al final del lote mediante ExportarMatricesPeriodoUseCase.
  6. Decisión P-07: Aislamiento por ejecución en subcarpeta con batch_id.
  7. Retorno inmutable de BatchResultadoDTO.

Reglas arquitectónicas:
- Application Layer: NO importa sqlite3, python-docx ni openpyxl.
- Atomicidad: Falla en archivo X no bloquea el procesamiento de archivos Y o Z.
- Preserva invariante matemática: Entrada = Aceptados + Rechazados + Advertencias + Fallidos.
- Dry-run: Cero mutaciones persistentes en SQLite y cero exportaciones físicas cuando dry_run=True.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import uuid

from app.application.commands.batch_commands import IngestarCarpetaWordCommand
from app.application.commands.pipeline_commands import ExportarMatricesPeriodoCommand
from app.application.dto.batch_dtos import (
    BatchArchivoResultadoDTO,
    BatchResultadoDTO,
)
from app.application.use_cases.batch.procesar_pipeline_desde_word import (
    ProcesarPipelineDesdeWordUseCase,
)
from app.application.use_cases.batch.batch_manifest_writer import (
    BatchManifestWriter,
)
from app.application.use_cases.exportacion.exportar_matrices_periodo import (
    ExportarMatricesPeriodoUseCase,
)
from app.audit.audit_logger import get_logger
from app.core.ports.unit_of_work import IUnitOfWork

logger = get_logger(__name__)


class IngestarCarpetaWordUseCase:
    """Caso de uso de aplicación para procesar por lote una carpeta de documentos Word."""

    def __init__(
        self,
        pipeline_word_use_case: ProcesarPipelineDesdeWordUseCase,
        exportar_periodo_use_case: Optional[ExportarMatricesPeriodoUseCase] = None,
        uow: Optional[IUnitOfWork] = None,
    ) -> None:
        """Inicializa el caso de uso batch.

        Args:
            pipeline_word_use_case: Caso de uso para procesar individualmente cada DOCX.
            exportar_periodo_use_case: Caso de uso para exportación consolidada de matrices M1–M5.
            uow: Unidad de trabajo transaccional (opcional).
        """
        self._pipeline_word_use_case = pipeline_word_use_case
        self._exportar_periodo_use_case = exportar_periodo_use_case
        self._uow = uow

    def execute(self, command: IngestarCarpetaWordCommand) -> BatchResultadoDTO:
        """Ejecuta el procesamiento integral del lote de documentos Word.

        Args:
            command: IngestarCarpetaWordCommand con parámetros de configuración del lote.

        Returns:
            BatchResultadoDTO con el diagnóstico completo del lote y matrices exportadas.
        """
        batch_id = str(uuid.uuid4())
        timestamp_inicio = datetime.now().isoformat()
        carpeta_origen = Path(command.carpeta_origen)

        logger.info(
            f"Iniciando procesamiento por lote batch_id={batch_id} en carpeta '{carpeta_origen}' "
            f"(patron='{command.patron_glob}', dry_run={command.dry_run})."
        )

        errores_criticos: List[str] = []
        advertencias_lote: List[str] = []

        # ------------------------------------------------------------------
        # PASO 1: Validación de existencia y descubrimiento de archivos
        # ------------------------------------------------------------------
        if not carpeta_origen.exists() or not carpeta_origen.is_dir():
            msg_error = f"La carpeta origen '{carpeta_origen}' no existe o no es un directorio accesible."
            logger.error(msg_error)
            errores_criticos.append(msg_error)
            return BatchResultadoDTO(
                batch_id=batch_id,
                carpeta_origen=str(carpeta_origen),
                patron_glob=command.patron_glob,
                timestamp_inicio=timestamp_inicio,
                timestamp_fin=datetime.now().isoformat(),
                dry_run=command.dry_run,
                archivos_encontrados=0,
                archivos_aceptados=0,
                archivos_rechazados=0,
                archivos_con_advertencias=0,
                archivos_fallidos=0,
                actividades_creadas=[],
                evidencias_registradas_total=0,
                actividades_con_posible_duplicado=[],
                matrices_generadas={},
                hashes_matrices={},
                manifest_path=None,
                invariante_ok=False,
                errores_criticos=errores_criticos,
                advertencias_lote=advertencias_lote,
                resultados_por_archivo=[],
            )

        # Buscar archivos descartando temporales de Word (prefijo ~$)
        todos_los_archivos = sorted(list(carpeta_origen.glob(command.patron_glob)))
        archivos_candidatos = [
            f for f in todos_los_archivos if not f.name.startswith("~$")
        ]
        total_encontrados = len(archivos_candidatos)

        if total_encontrados == 0:
            msg_adv = f"No se encontraron archivos coincidentes con '{command.patron_glob}' en '{carpeta_origen}'."
            logger.warning(msg_adv)
            advertencias_lote.append(msg_adv)
            return BatchResultadoDTO(
                batch_id=batch_id,
                carpeta_origen=str(carpeta_origen.resolve()),
                patron_glob=command.patron_glob,
                timestamp_inicio=timestamp_inicio,
                timestamp_fin=datetime.now().isoformat(),
                dry_run=command.dry_run,
                archivos_encontrados=0,
                archivos_aceptados=0,
                archivos_rechazados=0,
                archivos_con_advertencias=0,
                archivos_fallidos=0,
                actividades_creadas=[],
                evidencias_registradas_total=0,
                actividades_con_posible_duplicado=[],
                matrices_generadas={},
                hashes_matrices={},
                manifest_path=None,
                invariante_ok=True,
                errores_criticos=[],
                advertencias_lote=advertencias_lote,
                resultados_por_archivo=[],
            )

        # ------------------------------------------------------------------
        # PASO 2: Iteración por archivo con aislamiento de fallos (Éxito Parcial)
        # ------------------------------------------------------------------
        resultados_por_archivo: List[BatchArchivoResultadoDTO] = []
        nombres_vistos: Set[str] = set()
        actividades_creadas: List[str] = []
        actividades_con_posible_duplicado: List[str] = []
        evidencias_totales = 0

        archivos_aceptados = 0
        archivos_rechazados = 0
        archivos_con_advertencias = 0
        archivos_fallidos = 0

        for archivo_path in archivos_candidatos:
            nombre = archivo_path.name
            es_posible_duplicado = False

            # Heurística GAP-3 de posible duplicado por nombre de archivo
            if command.advertir_posibles_duplicados:
                if nombre in nombres_vistos:
                    es_posible_duplicado = True
                    logger.warning(
                        f"[GAP-3] Posible duplicado detectado en lote para archivo '{nombre}'."
                    )
                else:
                    nombres_vistos.add(nombre)

            try:
                pipe_res = self._pipeline_word_use_case.execute(
                    file_path=archivo_path,
                    dry_run=command.dry_run,
                    politica_revision=command.politica_revision,
                    posible_duplicado_advertido=es_posible_duplicado,
                )
                archivo_dto = pipe_res.to_batch_archivo_resultado(
                    ruta_archivo=str(archivo_path.resolve())
                )
            except Exception as exc:
                logger.error(
                    f"Fallo técnico irrecuperable al procesar '{nombre}': {exc}"
                )
                archivo_dto = BatchArchivoResultadoDTO(
                    nombre_archivo=nombre,
                    ruta_archivo=str(archivo_path.resolve()),
                    estado="FALLIDO",
                    tipo_documento=None,
                    id_actividad=None,
                    motivo_rechazo=None,
                    evidencias_registradas=0,
                    advertencias=[],
                    errores=[f"Excepción no capturada: {exc}"],
                    calidad_estado=None,
                    total_hallazgos_calidad=0,
                    total_participaciones_enrutadas=0,
                    posible_duplicado_advertido=es_posible_duplicado,
                )

            resultados_por_archivo.append(archivo_dto)

            # Clasificación de contadores según el estado resultante
            if archivo_dto.estado == "ACEPTADO":
                archivos_aceptados += 1
            elif archivo_dto.estado == "CON_ADVERTENCIAS":
                archivos_con_advertencias += 1
            elif archivo_dto.estado == "RECHAZADO":
                archivos_rechazados += 1
            elif archivo_dto.estado == "FALLIDO":
                archivos_fallidos += 1

            if archivo_dto.id_actividad:
                actividades_creadas.append(archivo_dto.id_actividad)

            evidencias_totales += archivo_dto.evidencias_registradas

            if archivo_dto.posible_duplicado_advertido:
                actividades_con_posible_duplicado.append(
                    archivo_dto.id_actividad or nombre
                )

        if actividades_con_posible_duplicado:
            advertencias_lote.append(
                f"[GAP-3] Se detectaron {len(actividades_con_posible_duplicado)} archivos con nombres coincidentes. "
                "Advertencia heurística, no garantía de identidad documental."
            )

        # ------------------------------------------------------------------
        # PASO 3: Decisión P-01 & P-07: Exportación Consolidada al Final del Lote
        # ------------------------------------------------------------------
        matrices_generadas: Dict[str, str] = {}
        hashes_matrices: Dict[str, str] = {}

        if (
            not command.dry_run
            and len(actividades_creadas) > 0
            and self._exportar_periodo_use_case is not None
        ):
            # P-07: Subcarpeta aislada por batch_id
            carpeta_salida_base = Path(command.carpeta_salida)
            carpeta_salida_lote = carpeta_salida_base / batch_id
            carpeta_salida_lote.mkdir(parents=True, exist_ok=True)

            logger.info(
                f"Ejecutando exportación consolidada para {len(actividades_creadas)} actividades "
                f"en destino '{carpeta_salida_lote}'."
            )

            cmd_export = ExportarMatricesPeriodoCommand(
                anio=datetime.now().year,
                ids_actividades=actividades_creadas,
                carpeta_salida=str(carpeta_salida_lote),
                politica_revision=command.politica_revision,
                dry_run=False,
                permitir_fixtures_test_only=command.permitir_fixtures_test_only,
                carpeta_templates=command.carpeta_templates,
                carpeta_fixtures=command.carpeta_fixtures,
            )

            try:
                export_res = self._exportar_periodo_use_case.execute(
                    command=cmd_export,
                    uow=self._uow,
                )
                matrices_generadas = export_res.archivos_generados
                hashes_matrices = export_res.hashes_sha256_salida

                if not export_res.exito:
                    msg_exp_err = f"Exportación consolidada finalizó con incidencias: {export_res.mensaje}"
                    logger.warning(msg_exp_err)
                    advertencias_lote.append(msg_exp_err)
            except Exception as exc:
                msg_exp_crit = f"Fallo técnico durante exportación consolidada de matrices: {exc}"
                logger.error(msg_exp_crit)
                errores_criticos.append(msg_exp_crit)

        # Invariante del lote: Sin fallos técnicos no controlados
        invariante_ok = (archivos_fallidos == 0) and (len(errores_criticos) == 0)
        timestamp_fin = datetime.now().isoformat()

        # ------------------------------------------------------------------
        # PASO 4: Escritura de Manifiesto Pericial Externo (P-04)
        # ------------------------------------------------------------------
        manifest_ruta_str: Optional[str] = None
        if not command.dry_run:
            carpeta_salida_base = Path(command.carpeta_salida)
            carpeta_salida_lote = carpeta_salida_base / batch_id
            carpeta_salida_lote.mkdir(parents=True, exist_ok=True)

            dto_para_manifest = BatchResultadoDTO(
                batch_id=batch_id,
                carpeta_origen=str(carpeta_origen.resolve()),
                patron_glob=command.patron_glob,
                timestamp_inicio=timestamp_inicio,
                timestamp_fin=timestamp_fin,
                dry_run=command.dry_run,
                archivos_encontrados=total_encontrados,
                archivos_aceptados=archivos_aceptados,
                archivos_rechazados=archivos_rechazados,
                archivos_con_advertencias=archivos_con_advertencias,
                archivos_fallidos=archivos_fallidos,
                actividades_creadas=actividades_creadas,
                evidencias_registradas_total=evidencias_totales,
                actividades_con_posible_duplicado=actividades_con_posible_duplicado,
                matrices_generadas=matrices_generadas,
                hashes_matrices=hashes_matrices,
                manifest_path=None,
                invariante_ok=invariante_ok,
                errores_criticos=errores_criticos,
                advertencias_lote=advertencias_lote,
                resultados_por_archivo=resultados_por_archivo,
            )

            escrito = BatchManifestWriter.escribir(
                resultado=dto_para_manifest,
                ruta_directorio_salida=carpeta_salida_lote,
            )
            if escrito:
                manifest_ruta_str = str(escrito)

        logger.info(
            f"Procesamiento por lote completado batch_id={batch_id}: Encontrados={total_encontrados}, "
            f"Aceptados={archivos_aceptados}, ConAdvertencias={archivos_con_advertencias}, "
            f"Rechazados={archivos_rechazados}, Fallidos={archivos_fallidos}."
        )

        return BatchResultadoDTO(
            batch_id=batch_id,
            carpeta_origen=str(carpeta_origen.resolve()),
            patron_glob=command.patron_glob,
            timestamp_inicio=timestamp_inicio,
            timestamp_fin=timestamp_fin,
            dry_run=command.dry_run,
            archivos_encontrados=total_encontrados,
            archivos_aceptados=archivos_aceptados,
            archivos_rechazados=archivos_rechazados,
            archivos_con_advertencias=archivos_con_advertencias,
            archivos_fallidos=archivos_fallidos,
            actividades_creadas=actividades_creadas,
            evidencias_registradas_total=evidencias_totales,
            actividades_con_posible_duplicado=actividades_con_posible_duplicado,
            matrices_generadas=matrices_generadas,
            hashes_matrices=hashes_matrices,
            manifest_path=manifest_ruta_str,
            invariante_ok=invariante_ok,
            errores_criticos=errores_criticos,
            advertencias_lote=advertencias_lote,
            resultados_por_archivo=resultados_por_archivo,
        )
