"""app.application.use_cases.exportacion.exportar_matrices_periodo

Caso de uso: ExportarMatricesPeriodoUseCase.
Orquesta la consolidación y exportación de las 5 matrices oficiales M1–M5 para un conjunto de actividades
correspondientes a un período determinado (semana, mes o lista de actividades).

Principios arquitectónicos:
- Clean Architecture: Cero importaciones de sqlite3, openpyxl, xlsxwriter o python-docx.
- Consolida actividades de forma agregada para Matriz 1 (Consolidado de Actividades).
- Unifica listas nominales para M2 (Estudiantes), M3 (Académicos/Admin), M4 (Colaboradores) y M5 (Beneficiados).
- Gobierna la política OPEN-02 a través de ExportACL y PoliticaExportacionRevision.
- Asegura la exclusión estricta de registros BLOQUEADOS y COLA_REVISION.
"""

from pathlib import Path
from typing import Dict, List, Optional

from app.audit.audit_logger import get_logger
from app.exporters.base_exporter import calcular_sha256
from app.application.commands.pipeline_commands import (
    EjecutarPipelineActividadCommand,
    ExportarMatricesPeriodoCommand,
)
from app.application.dto.export_dtos import ExportacionPreparadaDTO, ExportarMatricesResultDTO
from app.application.export_acl.export_acl import ExportACL, ExportDataset
from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)
from app.core.models.activity import Activity
from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.unit_of_work import IUnitOfWork
from app.routing.enums import MatrizDestino
from app.routing.models import ResultadoRouting, ResumenMatriz
from app.statistics.statistics_engine import StatisticsEngine

logger = get_logger(__name__)


class ExportarMatricesPeriodoUseCase:
    """Caso de uso de aplicación para exportar las matrices M1–M5 de un período institucional."""

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
        command: ExportarMatricesPeriodoCommand,
        uow: Optional[IUnitOfWork] = None,
    ) -> ExportarMatricesResultDTO:
        """Ejecuta la consolidación y preparación de exportación para el período."""
        active_uow = uow or self._uow

        if active_uow is not None:
            if getattr(active_uow, "_in_transaction", False):
                return self._execute_core(command=command, act_repo=active_uow.actividades, uow=active_uow)
            with active_uow:
                return self._execute_core(command=command, act_repo=active_uow.actividades, uow=active_uow)

        if self._actividad_repo is None:
            raise ValueError("Se requiere repositorio de actividades o IUnitOfWork.")

        return self._execute_core(command=command, act_repo=self._actividad_repo, uow=None)

    def _execute_core(
        self,
        command: ExportarMatricesPeriodoCommand,
        act_repo: IActividadRepository,
        uow: Optional[IUnitOfWork],
    ) -> ExportarMatricesResultDTO:
        """Lógica central de consolidación para el período especificado."""
        logger.info(
            f"ExportarMatricesPeriodo: Iniciando consolidación período anio={command.anio}, "
            f"mes={command.mes}, semana={command.semana} (dry_run={command.dry_run})."
        )

        # 1. Obtener actividades del período
        actividades: List[Activity] = []
        if command.ids_actividades:
            for act_id in command.ids_actividades:
                act = act_repo.get_by_id(act_id)
                if act is not None:
                    actividades.append(act)
        else:
            if command.mes is not None:
                f_inicio = f"{command.anio}-{command.mes:02d}-01"
                f_fin = f"{command.anio}-{command.mes:02d}-31"
            else:
                f_inicio = f"{command.anio}-01-01"
                f_fin = f"{command.anio}-12-31"

            actividades = act_repo.list_by_periodo(
                fecha_inicio=f_inicio,
                fecha_fin=f_fin,
                sede=command.sede_recinto,
            )

        periodo_id = f"PERIODO_{command.anio}_{command.mes or 'ANUAL'}"

        if not actividades:
            logger.warning("No se encontraron actividades que coincidan con el período especificado.")
            return ExportarMatricesResultDTO(
                id_actividad=periodo_id,
                modo="PREVIEW" if command.dry_run else "EXPORT",
                carpeta_salida=command.carpeta_salida,
                archivos_generados={},
                hashes_sha256_salida={},
                total_filas_exportadas_por_matriz={
                    "matriz_1": 0, "matriz_2": 0, "matriz_3": 0, "matriz_4": 0, "matriz_5": 0,
                },
                manifiesto_ruta=None,
                exito=True,
                mensaje="Período sin actividades. 0 registros a procesar.",
            )

        # 2. Procesar cada actividad mediante el pipeline para obtener datasets individuales
        estudiantes = []
        academicos_admin = []
        colaboradores = []
        beneficiados = []
        cola_revision = []
        bloqueados = []
        cuarentena = []
        personas_dict = {}
        participaciones_totales = []

        for act in actividades:
            pipe_cmd = EjecutarPipelineActividadCommand(
                id_actividad=act.id_actividad,
                dry_run=command.dry_run,
                politica_revision=command.politica_revision,
                persistir_discrepancias=not command.dry_run,
            )
            pipe_res = self._pipeline_use_case.execute(command=pipe_cmd, uow=uow)
            dataset = self._pipeline_use_case.ultimo_dataset
            if dataset is not None:
                estudiantes.extend(dataset.resultado_routing_exportable.estudiantes)
                academicos_admin.extend(dataset.resultado_routing_exportable.academicos_administrativos)
                colaboradores.extend(dataset.resultado_routing_exportable.colaboradores)
                beneficiados.extend(dataset.resultado_routing_exportable.beneficiados)
                cola_revision.extend(dataset.registros_cola_revision)
                bloqueados.extend(dataset.registros_bloqueados)
                cuarentena.extend(dataset.registros_cuarentena)
                for p in dataset.personas:
                    personas_dict[p.id_persona_interno] = p
                participaciones_totales.extend(dataset.participaciones_originales)

        total_exportables_nominales = len(estudiantes) + len(academicos_admin) + len(colaboradores) + len(beneficiados)

        # 3. Routing consolidado para el período
        resumenes_periodo = {
            "M2": ResumenMatriz(
                matriz=MatrizDestino.ESTUDIANTES,
                total_participaciones=len(estudiantes),
                total_aptos=sum(1 for r in estudiantes if r.estado_operativo == "APTO"),
                total_en_revision=sum(1 for r in estudiantes if r.estado_operativo == "EN_REVISION"),
                total_femenino=sum(1 for r in estudiantes if r.persona.sexo_normalizado == "FEMENINO"),
                total_masculino=sum(1 for r in estudiantes if r.persona.sexo_normalizado == "MASCULINO"),
            ),
            "M3": ResumenMatriz(
                matriz=MatrizDestino.ACADEMICOS_ADMINISTRATIVOS,
                total_participaciones=len(academicos_admin),
                total_aptos=sum(1 for r in academicos_admin if r.estado_operativo == "APTO"),
                total_en_revision=sum(1 for r in academicos_admin if r.estado_operativo == "EN_REVISION"),
                total_femenino=sum(1 for r in academicos_admin if r.persona.sexo_normalizado == "FEMENINO"),
                total_masculino=sum(1 for r in academicos_admin if r.persona.sexo_normalizado == "MASCULINO"),
            ),
            "M4": ResumenMatriz(
                matriz=MatrizDestino.COLABORADORES,
                total_participaciones=len(colaboradores),
                total_aptos=sum(1 for r in colaboradores if r.estado_operativo == "APTO"),
                total_en_revision=sum(1 for r in colaboradores if r.estado_operativo == "EN_REVISION"),
                total_femenino=sum(1 for r in colaboradores if r.persona.sexo_normalizado == "FEMENINO"),
                total_masculino=sum(1 for r in colaboradores if r.persona.sexo_normalizado == "MASCULINO"),
            ),
            "M5": ResumenMatriz(
                matriz=MatrizDestino.BENEFICIADOS,
                total_participaciones=len(beneficiados),
                total_aptos=sum(1 for r in beneficiados if r.estado_operativo == "APTO"),
                total_en_revision=sum(1 for r in beneficiados if r.estado_operativo == "EN_REVISION"),
                total_femenino=sum(1 for r in beneficiados if r.persona.sexo_normalizado == "FEMENINO"),
                total_masculino=sum(1 for r in beneficiados if r.persona.sexo_normalizado == "MASCULINO"),
            ),
        }

        routing_periodo = ResultadoRouting(
            estudiantes=estudiantes,
            academicos_administrativos=academicos_admin,
            colaboradores=colaboradores,
            beneficiados=beneficiados,
            cola_revision=[],
            bloqueados=[],
            actividades=actividades,
            total_entrada=total_exportables_nominales,
            total_clasificadas=total_exportables_nominales,
            invariante_valida=True,
            resumenes=resumenes_periodo,
        )

        # 4. Estadísticas consolidadas para M1
        part_exportables_ids = {
            r.participacion.id_participacion
            for r in (estudiantes + academicos_admin + colaboradores + beneficiados)
        }
        part_para_stats = [
            p for p in participaciones_totales if p.id_participacion in part_exportables_ids
        ]
        personas_list = list(personas_dict.values())

        stats_periodo = StatisticsEngine.calcular(
            resultado_routing=routing_periodo,
            actividades=actividades,
            personas=personas_list,
            participaciones=part_para_stats,
        )

        # 5. Dataset consolidado de exportación para el período
        dto_periodo = ExportacionPreparadaDTO(
            id_actividad=periodo_id,
            politica_revision=command.politica_revision,
            total_m1_actividades=len(actividades),
            total_m2_estudiantes=len(estudiantes),
            total_m3_academicos_admin=len(academicos_admin),
            total_m4_colaboradores=len(colaboradores),
            total_m5_beneficiados=len(beneficiados),
            total_exportables_nominales=total_exportables_nominales,
            total_cuarentena=len(cuarentena),
            total_cola_revision_excluidos=len(cola_revision),
            total_bloqueados_excluidos=len(bloqueados),
            invariante_verificada=True,
        )

        dataset_periodo = ExportDataset(
            actividades=actividades,
            personas=personas_list,
            participaciones_originales=participaciones_totales,
            resultado_routing_exportable=routing_periodo,
            resultado_routing_original=routing_periodo,
            estadistica_global=stats_periodo,
            registros_cuarentena=cuarentena,
            registros_bloqueados=bloqueados,
            registros_cola_revision=cola_revision,
            politica_aplicada=command.politica_revision,
            dto=dto_periodo,
        )

        # 6. Ejecutar exportación física o simulación PREVIEW
        modo_str = "PREVIEW" if command.dry_run else "EXPORT"
        carpeta_tpl = Path(command.carpeta_templates) if command.carpeta_templates else None
        carpeta_fix = Path(command.carpeta_fixtures) if command.carpeta_fixtures else None

        manifiesto = ExportACL.exportar_matrices_fisicas(
            dataset=dataset_periodo,
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
            id_actividad=periodo_id,
            modo=modo_str,
            carpeta_salida=command.carpeta_salida,
            archivos_generados=archivos_generados if not command.dry_run else {},
            hashes_sha256_salida=hashes_sha256 if not command.dry_run else {},
            total_filas_exportadas_por_matriz=total_filas,
            manifiesto_ruta=manifiesto.ruta_manifiesto if not command.dry_run else None,
            exito=manifiesto.invariante_filas_valida and manifiesto.invariante_conservacion_valida,
            mensaje=(
                f"Exportación de período consolidada exitosamente en modo {modo_str}. "
                f"Actividades en M1={len(actividades)}, Total nominal exportado: {manifiesto.total_filas_detalle_escritas}."
            ),
        )
