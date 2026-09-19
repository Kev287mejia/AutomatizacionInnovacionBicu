"""app.application.use_cases.exportacion.exportar_matrices_actividad

Caso de uso: ExportarMatricesActividadUseCase.
Orquesta la exportación integral de las 5 matrices oficiales M1–M5 para una actividad institucional individual.

Principios arquitectónicos:
- Clean Architecture: NO importa sqlite3, NO importa openpyxl, NO contiene consultas SQL.
- Utiliza ProcesarPipelineActividadUseCase para asegurar la secuencia:
  ACTIVIDAD -> CALIDAD -> ROUTING -> PREPARACIÓN EXPORT ACL.
- Gobierna la política OPEN-02 mediante PoliticaExportacionRevision.
- Garantiza que registros BLOQUEADOS y COLA_REVISION queden estrictamente excluidos de las matrices.
- Bloque 1 (Stop Gate Activo): Prepara y certifica el dataset en memoria (ExportDataset) garantizando
  cero mutación de las fuentes primarias y cero corrupción de disco previo a la autorización del Bloque 2.
"""

from typing import Optional
from pathlib import Path

from app.audit.audit_logger import get_logger
from app.exporters.base_exporter import calcular_sha256
from app.application.commands.pipeline_commands import (
    EjecutarPipelineActividadCommand,
    ExportarMatricesActividadCommand,
)
from app.application.dto.export_dtos import ExportarMatricesResultDTO
from app.application.export_acl.export_acl import ExportACL, ExportDataset
from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.unit_of_work import IUnitOfWork

logger = get_logger(__name__)


class ExportarMatricesActividadUseCase:
    """Caso de uso de aplicación para exportar las matrices M1–M5 de una actividad."""

    def __init__(
        self,
        actividad_repo: Optional[IActividadRepository] = None,
        persona_repo: Optional[IPersonaRepository] = None,
        participacion_repo: Optional[IParticipacionRepository] = None,
        discrepancia_repo: Optional[IDiscrepanciaRepository] = None,
        uow: Optional[IUnitOfWork] = None,
        pipeline_use_case: Optional[ProcesarPipelineActividadUseCase] = None,
    ) -> None:
        self._actividad_repo = actividad_repo
        self._persona_repo = persona_repo
        self._participacion_repo = participacion_repo
        self._discrepancia_repo = discrepancia_repo
        self._uow = uow
        self._pipeline_use_case = pipeline_use_case or ProcesarPipelineActividadUseCase(
            actividad_repo=actividad_repo,
            persona_repo=persona_repo,
            participacion_repo=participacion_repo,
            discrepancia_repo=discrepancia_repo,
            uow=uow,
        )

    def execute(
        self,
        command: ExportarMatricesActividadCommand,
        uow: Optional[IUnitOfWork] = None,
    ) -> ExportarMatricesResultDTO:
        """Ejecuta la preparación y orquestación de exportación para la actividad indicada.

        Args:
            command: Comando con el ID de la actividad, carpeta de salida y política de revisión.
            uow: Unidad de trabajo opcional.

        Returns:
            ExportarMatricesResultDTO con los resultados del proceso.
        """
        logger.info(
            f"ExportarMatricesActividad: Procesando actividad '{command.id_actividad}' con política {command.politica_revision.value} "
            f"(dry_run={command.dry_run})."
        )

        # 1. Coordinar a través del pipeline integral
        pipeline_cmd = EjecutarPipelineActividadCommand(
            id_actividad=command.id_actividad,
            dry_run=command.dry_run,
            politica_revision=command.politica_revision,
            persistir_discrepancias=not command.dry_run,
        )
        pipeline_res = self._pipeline_use_case.execute(command=pipeline_cmd, uow=uow)

        # 2. Obtener el ExportDataset preparado por ExportACL
        dataset = self._pipeline_use_case.ultimo_dataset
        if dataset is None:
            raise ValueError(f"No se pudo preparar el dataset de exportación para actividad '{command.id_actividad}'.")

        # 3. Ejecutar la exportación física (o simulación PREVIEW) vía ExportACL
        modo_str = "PREVIEW" if command.dry_run else "EXPORT"
        carpeta_tpl = Path(command.carpeta_templates) if command.carpeta_templates else None
        carpeta_fix = Path(command.carpeta_fixtures) if command.carpeta_fixtures else None

        manifiesto = ExportACL.exportar_matrices_fisicas(
            dataset=dataset,
            carpeta_salida=Path(command.carpeta_salida),
            modo=modo_str,
            carpeta_templates=carpeta_tpl,
            carpeta_fixtures=carpeta_fix,
            permitir_fixtures_test_only=command.permitir_fixtures_test_only,
        )

        archivos_generados = {
            id_m: res.ruta_salida for id_m, res in manifiesto.matrices.items()
        }
        hashes_sha256 = {}
        for id_m, ruta_str in archivos_generados.items():
            p = Path(ruta_str)
            if p.exists():
                hashes_sha256[id_m] = calcular_sha256(p)

        total_filas = {
            id_m: res.total_filas_escritas for id_m, res in manifiesto.matrices.items()
        }

        return ExportarMatricesResultDTO(
            id_actividad=command.id_actividad,
            modo=modo_str,
            carpeta_salida=command.carpeta_salida,
            archivos_generados=archivos_generados if not command.dry_run else {},
            hashes_sha256_salida=hashes_sha256 if not command.dry_run else {},
            total_filas_exportadas_por_matriz=total_filas,
            manifiesto_ruta=manifiesto.ruta_manifiesto if not command.dry_run else None,
            exito=manifiesto.invariante_filas_valida and manifiesto.invariante_conservacion_valida,
            mensaje=(
                f"Exportación de 5 matrices completada exitosamente en modo {modo_str}. "
                f"Total nominal exportado: {manifiesto.total_filas_detalle_escritas}."
            ),
        )
