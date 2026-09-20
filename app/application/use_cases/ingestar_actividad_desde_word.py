"""app.application.use_cases.ingestar_actividad_desde_word

Caso de uso para la ingesta y persistencia estructurada de actividades institucionales Word (.docx) hacia SQLite.

OBJETIVO:
    Transformar el DTO producido por IWordActivityExtractor en entidades persistentes
    del sistema institucional dentro de un ámbito transaccional atómico (IUnitOfWork).

REGLAS ABSOLUTAS DE AISLAMIENTO:
    1. Clean Architecture: La capa Application no importa docx, sqlite3 ni openpyxl.
    2. CERO participantes nominales: La Matriz Cuantitativa (Tabla 2) representa cifras agregadas.
       No se crean objetos Person ni filas de asistencia en participacion.
    3. DETECTAR != CORREGIR: Toda inconsistencia o discrepancia se reporta en advertencias,
       nunca se altera la información ni se inventan datos.
    4. CERO ejecución de Quality, Routing o Exportación M1-M5 en este caso de uso.
    5. Transaccionalidad atómica: La persistencia de la actividad y sus evidencias vinculadas
       se ejecuta con semántica All-or-Nothing (rollback automático ante excepciones).
"""

from pathlib import Path
from typing import Optional, Union

from app.application.dto.word_extraction_dtos import (
    IngestaActividadWordResultDTO,
    TipoDocumentoWord,
)
from app.application.mappers.word_activity_mapper import WordActivityDTOMapper
from app.application.ports.word_activity_extractor import IWordActivityExtractor
from app.audit.audit_logger import get_logger
from app.core.exceptions.persistence_exceptions import EntityAlreadyExistsError
from app.core.ports.unit_of_work import IUnitOfWork

logger = get_logger(__name__)


class IngestarActividadDesdeWordUseCase:
    """Caso de uso de Aplicación que orquesta la ingesta de un Word de actividad hacia SQLite."""

    def __init__(
        self,
        extractor: IWordActivityExtractor,
        uow: IUnitOfWork,
    ) -> None:
        """Inicializa el caso de uso con el extractor y el puerto transaccional.

        Args:
            extractor: Puerto de extracción estructurada IWordActivityExtractor.
            uow: Frontera transaccional desacoplada IUnitOfWork.
        """
        self._extractor = extractor
        self._uow = uow

    def execute(self, file_path: Union[str, Path]) -> IngestaActividadWordResultDTO:
        """Ejecuta el flujo de ingesta transaccional para un archivo Word.

        Args:
            file_path: Ruta al archivo .docx a procesar.

        Returns:
            IngestaActividadWordResultDTO con el diagnóstico y resultado del proceso.
        """
        path = Path(file_path)
        nombre_archivo = path.name

        # 1. Extracción física desacoplada a través del puerto
        extraction_dto = self._extractor.extract(path)

        # 2. Validación de compatibilidad con el flujo principal
        diag = extraction_dto.diagnostico

        if not diag.es_valido:
            logger.warning(
                f"Documento no procesable '{nombre_archivo}': {diag.errores}"
            )
            return IngestaActividadWordResultDTO(
                exitoso=False,
                id_actividad=None,
                nombre_archivo=nombre_archivo,
                ruta_archivo=str(path),
                tipo_documento=diag.tipo_documento,
                compatible_flujo_principal=False,
                total_participantes_declarado=None,
                evidencias_registradas_count=0,
                motivo_rechazo=f"Documento no válido para ingesta: {'; '.join(diag.errores)}",
                advertencias=diag.advertencias,
                errores=diag.errores,
                extraction_dto=extraction_dto,
            )

        if diag.tipo_documento == TipoDocumentoWord.INFORME_SEMANAL:
            logger.info(
                f"Documento '{nombre_archivo}' reconocido como INFORME_SEMANAL. "
                "No corresponde a un informe individual de actividad."
            )
            return IngestaActividadWordResultDTO(
                exitoso=False,
                id_actividad=None,
                nombre_archivo=nombre_archivo,
                ruta_archivo=str(path),
                tipo_documento=diag.tipo_documento,
                compatible_flujo_principal=False,
                total_participantes_declarado=None,
                evidencias_registradas_count=0,
                motivo_rechazo="El archivo corresponde a un Informe Semanal Consolidado, no a una actividad individual.",
                advertencias=diag.advertencias,
                errores=[],
                extraction_dto=extraction_dto,
            )

        if diag.tipo_documento != TipoDocumentoWord.INFORME_ACTIVIDAD or not diag.compatible_flujo_principal:
            logger.warning(
                f"Documento '{nombre_archivo}' clasificado como NO_COMPATIBLE."
            )
            return IngestaActividadWordResultDTO(
                exitoso=False,
                id_actividad=None,
                nombre_archivo=nombre_archivo,
                ruta_archivo=str(path),
                tipo_documento=diag.tipo_documento,
                compatible_flujo_principal=False,
                total_participantes_declarado=None,
                evidencias_registradas_count=0,
                motivo_rechazo="El documento no contiene la Ficha Técnica (Tabla 1) ni la estructura requerida.",
                advertencias=diag.advertencias,
                errores=diag.errores,
                extraction_dto=extraction_dto,
            )

        if not extraction_dto.ficha_tecnica or not extraction_dto.ficha_tecnica.actividad_general:
            return IngestaActividadWordResultDTO(
                exitoso=False,
                id_actividad=None,
                nombre_archivo=nombre_archivo,
                ruta_archivo=str(path),
                tipo_documento=diag.tipo_documento,
                compatible_flujo_principal=False,
                total_participantes_declarado=None,
                evidencias_registradas_count=0,
                motivo_rechazo="La Ficha Técnica no contiene el nombre de la Actividad General.",
                advertencias=diag.advertencias,
                errores=["Campo obligatorio 'Actividad General' ausente o vacío."],
                extraction_dto=extraction_dto,
            )

        # 3. Mapeo a entidades de dominio compatibles
        try:
            actividad = WordActivityDTOMapper.to_activity(extraction_dto)
            evidencias_data = WordActivityDTOMapper.to_evidencias(
                extraction_dto, actividad.id_actividad
            )
        except Exception as e:
            logger.error(f"Error al mapear DTO a dominio para '{nombre_archivo}': {e}")
            return IngestaActividadWordResultDTO(
                exitoso=False,
                id_actividad=None,
                nombre_archivo=nombre_archivo,
                ruta_archivo=str(path),
                tipo_documento=diag.tipo_documento,
                compatible_flujo_principal=False,
                total_participantes_declarado=None,
                evidencias_registradas_count=0,
                motivo_rechazo=f"Error de mapeo institucional: {e}",
                advertencias=diag.advertencias,
                errores=[str(e)],
                extraction_dto=extraction_dto,
            )

        # 4. Frontera Transaccional Atómica (Unit of Work)
        evidencias_guardadas = 0
        try:
            with self._uow:
                # 4.1. GAP-3: Idempotencia documental mediante SHA-256 (pre-verificación dentro de UoW)
                if extraction_dto.hash_sha256:
                    actividad_existente = self._uow.actividades.get_by_hash(extraction_dto.hash_sha256)
                    if actividad_existente is not None:
                        logger.warning(
                            f"Documento duplicado omitido por hash SHA-256 para '{nombre_archivo}'. "
                            f"Actividad previamente registrada: {actividad_existente.id_actividad}. OMITIDO — DUPLICADO."
                        )
                        return IngestaActividadWordResultDTO(
                            exitoso=True,
                            id_actividad=None,
                            nombre_archivo=nombre_archivo,
                            ruta_archivo=str(path),
                            tipo_documento=diag.tipo_documento,
                            compatible_flujo_principal=True,
                            total_participantes_declarado=None,
                            evidencias_registradas_count=0,
                            motivo_rechazo=None,
                            advertencias=[
                                f"OMITIDO — DUPLICADO: Documento '{nombre_archivo}' con hash SHA-256 idéntico "
                                f"a una actividad ya registrada ({actividad_existente.id_actividad})."
                            ] + diag.advertencias,
                            errores=[],
                            extraction_dto=extraction_dto,
                            posible_duplicado=True,
                        )

                # Guardar la entidad Actividad en SQLite (incluye métricas agregadas)
                self._uow.actividades.save(actividad)

                # Registrar y vincular evidencias detectadas compatibles
                for evidencia, orden, seccion in evidencias_data:
                    self._uow.evidencias.save(evidencia)
                    self._uow.evidencias.link_actividad(
                        id_actividad=actividad.id_actividad,
                        id_evidencia=evidencia.id_evidencia,
                        orden=orden,
                        seccion=seccion,
                    )
                    evidencias_guardadas += 1

                # Confirmar atómicamente la transacción
                self._uow.commit()

        except EntityAlreadyExistsError as exc:
            # GAP-3 & Concurrencia (Bloque 8): Manejo controlado de unicidad por hash SHA-256
            logger.warning(
                f"Conflicto de integridad por hash duplicado en '{nombre_archivo}': {exc}. OMITIDO — DUPLICADO."
            )
            return IngestaActividadWordResultDTO(
                exitoso=True,
                id_actividad=None,
                nombre_archivo=nombre_archivo,
                ruta_archivo=str(path),
                tipo_documento=diag.tipo_documento,
                compatible_flujo_principal=True,
                total_participantes_declarado=None,
                evidencias_registradas_count=0,
                motivo_rechazo=None,
                advertencias=[
                    f"OMITIDO — DUPLICADO: Documento '{nombre_archivo}' omitido por restricción UNIQUE de hash SHA-256."
                ] + diag.advertencias,
                errores=[],
                extraction_dto=extraction_dto,
                posible_duplicado=True,
            )
        except Exception as exc:
            logger.error(f"Fallo transaccional durante persistencia de '{nombre_archivo}': {exc}")
            # El context manager ejecuta automáticamente rollback()
            return IngestaActividadWordResultDTO(
                exitoso=False,
                id_actividad=None,
                nombre_archivo=nombre_archivo,
                ruta_archivo=str(path),
                tipo_documento=diag.tipo_documento,
                compatible_flujo_principal=False,
                total_participantes_declarado=None,
                evidencias_registradas_count=0,
                motivo_rechazo=f"Error durante la transacción en SQLite: {exc}",
                advertencias=diag.advertencias,
                errores=diag.errores + [str(exc)],
                extraction_dto=extraction_dto,
            )

        # 5. Obtener total cuantitativo declarado (para información en DTO, NO nominales)
        total_declarado: Optional[int] = None
        if extraction_dto.matriz_cuantitativa and extraction_dto.matriz_cuantitativa.total is not None:
            total_declarado = extraction_dto.matriz_cuantitativa.total
        elif extraction_dto.ficha_tecnica and extraction_dto.ficha_tecnica.total_participantes_declarado is not None:
            total_declarado = extraction_dto.ficha_tecnica.total_participantes_declarado

        logger.info(
            f"Actividad '{actividad.nombre_actividad_original}' persistida con éxito en SQLite "
            f"(id_actividad={actividad.id_actividad}, evidencias={evidencias_guardadas})."
        )

        return IngestaActividadWordResultDTO(
            exitoso=True,
            id_actividad=actividad.id_actividad,
            nombre_archivo=nombre_archivo,
            ruta_archivo=str(path),
            tipo_documento=diag.tipo_documento,
            compatible_flujo_principal=True,
            total_participantes_declarado=total_declarado,
            evidencias_registradas_count=evidencias_guardadas,
            motivo_rechazo=None,
            advertencias=diag.advertencias,
            errores=[],
            extraction_dto=extraction_dto,
        )
