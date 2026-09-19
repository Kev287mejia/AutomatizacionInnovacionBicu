"""app.application.use_cases.pipeline.procesar_pipeline_actividad

Caso de uso: ProcesarPipelineActividadUseCase.
Orquestador de aplicación para coordinar el pipeline institucional completo:
  ACTIVIDAD / PERSISTENCIA
            ↓
          CALIDAD (Q-01..Q-20, DETECTAR ≠ CORREGIR)
            ↓
          ROUTING (M2..M5, COLA_REVISION, BLOQUEADOS)
            ↓
          PREPARACIÓN DE EXPORTACIÓN (ExportACL + OPEN-02)

Reglas arquitectónicas fundamentales:
- Application Layer coordina: NO implementa lógica de negocio ni altera datos fuente.
- Reutiliza QualityValidator (app.quality) sin duplicar reglas Q-01..Q-20.
- Reutiliza ParticipantRouter y RoutingACL (app.routing) sin duplicar decisiones de clasificación.
- Preserva la regla RN-C07: DETECTAR ≠ CORREGIR (no muta nombres, cédulas, sexos, carreras ni fechas).
- Asegura la invariante matemática: Entrada = M2 + M3 + M4 + M5 + COLA_REVISION + BLOQUEADOS.
- Conecta Quality con Routing: hallazgos ERROR/CRITICAL aíslan en BLOQUEADOS; advertencias/revisiones marcan EN_REVISION.
- Entrega el resultado depurado a ExportACL para aplicar la política OPEN-02.
- Soporta transaccionalidad atómica y modo dry_run (cero mutaciones persistentes).
"""

from datetime import datetime
from typing import Dict, List, Optional
import uuid

from app.audit.audit_logger import get_logger
from app.application.commands.pipeline_commands import EjecutarPipelineActividadCommand
from app.application.dto.export_dtos import (
    ExportacionPreparadaDTO,
    PipelineActividadResultDTO,
    PoliticaExportacionRevision,
)
from app.application.dto.output_dtos import EnrutarParticipacionesResultDTO
from app.application.dto.quality_dtos import (
    QualityAssessmentDTO,
    ValidationFindingDTO,
)
from app.application.export_acl.export_acl import ExportACL, ExportDataset
from app.core.constants.participant_types import NivelValidacion
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.models.activity import Activity
from app.core.models.discrepancy import (
    Discrepancia,
    EstadoDiscrepancia,
    SeveridadDiscrepancia,
    TipoDiscrepancia,
)
from app.core.models.participation import Participation
from app.core.models.person import Person
from app.core.models.validation_result import ValidationResult
from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.unit_of_work import IUnitOfWork
from app.quality.models import (
    QualityAssessment,
    QualityContext,
    SeveridadCalidad,
    ValidationFinding,
)
from app.quality.validator import QualityValidator
from app.routing.acl import RoutingACL
from app.routing.models import ResultadoRouting
from app.routing.participant_router import ParticipantRouter

logger = get_logger(__name__)


class ProcesarPipelineActividadUseCase:
    """Orquestador de aplicación para coordinar el flujo integral de una actividad."""

    def __init__(
        self,
        actividad_repo: Optional[IActividadRepository] = None,
        persona_repo: Optional[IPersonaRepository] = None,
        participacion_repo: Optional[IParticipacionRepository] = None,
        discrepancia_repo: Optional[IDiscrepanciaRepository] = None,
        uow: Optional[IUnitOfWork] = None,
    ) -> None:
        self._actividad_repo = actividad_repo
        self._persona_repo = persona_repo
        self._participacion_repo = participacion_repo
        self._discrepancia_repo = discrepancia_repo
        self._uow = uow
        self._ultimo_dataset: Optional[ExportDataset] = None

    @property
    def ultimo_dataset(self) -> Optional[ExportDataset]:
        """Retorna el último ExportDataset preparado durante la ejecución del pipeline."""
        return self._ultimo_dataset

    def execute(
        self,
        command: EjecutarPipelineActividadCommand,
        uow: Optional[IUnitOfWork] = None,
    ) -> PipelineActividadResultDTO:
        """Ejecuta el pipeline institucional completo con control transaccional."""
        active_uow = uow or self._uow

        if active_uow is not None:
            if getattr(active_uow, "_in_transaction", False):
                return self._execute_core(
                    command=command,
                    act_repo=active_uow.actividades,
                    per_repo=active_uow.personas,
                    part_repo=active_uow.participaciones,
                    disc_repo=active_uow.discrepancias,
                )

            with active_uow:
                result = self._execute_core(
                    command=command,
                    act_repo=active_uow.actividades,
                    per_repo=active_uow.personas,
                    part_repo=active_uow.participaciones,
                    disc_repo=active_uow.discrepancias,
                )
                if not command.dry_run:
                    active_uow.commit()
                else:
                    active_uow.rollback()
            return result

        if (
            self._actividad_repo is None
            or self._persona_repo is None
            or self._participacion_repo is None
        ):
            raise ValueError(
                "Debe proporcionarse una instancia de IUnitOfWork o los repositorios requeridos."
            )

        return self._execute_core(
            command=command,
            act_repo=self._actividad_repo,
            per_repo=self._persona_repo,
            part_repo=self._participacion_repo,
            disc_repo=self._discrepancia_repo,
        )

    def _execute_core(
        self,
        command: EjecutarPipelineActividadCommand,
        act_repo: IActividadRepository,
        per_repo: IPersonaRepository,
        part_repo: IParticipacionRepository,
        disc_repo: Optional[IDiscrepanciaRepository],
    ) -> PipelineActividadResultDTO:
        """Lógica de coordinación paso a paso sin intervenir en las reglas de dominio."""
        fecha_inicio_iso = datetime.now().isoformat()
        logger.info(f"Pipeline: Iniciando procesamiento para actividad '{command.id_actividad}' (dry_run={command.dry_run}).")

        # ------------------------------------------------------------------
        # PASO 1 & 2: OBTENER Y VERIFICAR ACTIVIDAD
        # ------------------------------------------------------------------
        actividad: Optional[Activity] = act_repo.get_by_id(command.id_actividad)
        if actividad is None:
            raise EntityNotFoundError("Actividad", command.id_actividad)

        # ------------------------------------------------------------------
        # PASO 3: OBTENER PARTICIPACIONES Y PERSONAS VINCULADAS
        # ------------------------------------------------------------------
        participaciones: List[Participation] = part_repo.get_by_actividad(command.id_actividad)
        total_ingreso = len(participaciones)

        ids_personas = {p.id_persona for p in participaciones}
        personas: List[Person] = []
        for pid in ids_personas:
            persona = per_repo.get_by_id(pid)
            if persona is not None:
                personas.append(persona)

        # ------------------------------------------------------------------
        # PASO 4: EVALUACIÓN PERICIAL DE CALIDAD (Q-01..Q-20)
        # ------------------------------------------------------------------
        calidad_ctx = QualityContext(
            actividad=actividad,
            personas=personas,
            participaciones=participaciones,
            fuente_archivo_asistencia=command.fuente_archivo_asistencia or actividad.fuente_origen,
            fuente_archivo_informe=command.fuente_archivo_informe,
        )
        validator = QualityValidator()
        assessment: QualityAssessment = validator.evaluar_contexto(calidad_ctx)

        # ------------------------------------------------------------------
        # PASO 5: REGISTRAR / PRESERVAR FINDINGS Y DISCREPANCIAS
        # ------------------------------------------------------------------
        if not command.dry_run:
            part_map = {p.id_participacion: p for p in participaciones}
            modificadas = False

            # Indexar hallazgos de participación
            for finding in assessment.hallazgos:
                if finding.entidad_afectada == "PARTICIPACION" and finding.id_referencia in part_map:
                    part = part_map[finding.id_referencia]
                    if finding.severidad in (SeveridadCalidad.WARNING, SeveridadCalidad.ERROR, SeveridadCalidad.CRITICAL):
                        part.requiere_revision = True
                        if not part.motivo_revision:
                            part.motivo_revision = f"[{finding.codigo_regla}] {finding.mensaje_humano}"
                        elif finding.codigo_regla not in part.motivo_revision:
                            part.motivo_revision = f"{part.motivo_revision}; [{finding.codigo_regla}]"
                        modificadas = True

            if modificadas:
                part_validas_para_guardar = [
                    p for p in part_map.values() if per_repo.get_by_id(p.id_persona) is not None
                ]
                if part_validas_para_guardar:
                    part_repo.save_batch(part_validas_para_guardar)

            # Persistir discrepancias formales si está habilitado
            if command.persistir_discrepancias and disc_repo is not None:
                for finding in assessment.hallazgos:
                    if finding.requiere_discrepancia_persistente:
                        # Mapear a entidad Discrepancia
                        tipo_disc = TipoDiscrepancia.OTRO
                        if finding.codigo_regla == "Q-17":
                            tipo_disc = TipoDiscrepancia.FECHA_DISCORDANTE
                        elif finding.codigo_regla == "Q-18":
                            tipo_disc = TipoDiscrepancia.PLAN_VS_REAL
                        elif finding.codigo_regla == "Q-19":
                            tipo_disc = TipoDiscrepancia.RESUMEN_VS_NOMINAL

                        sev_disc = SeveridadDiscrepancia.WARNING
                        if finding.severidad in (SeveridadCalidad.ERROR, "ERROR"):
                            sev_disc = SeveridadDiscrepancia.ERROR

                        discrepancia = Discrepancia(
                            id_discrepancia=str(uuid.uuid4()),
                            id_actividad=command.id_actividad,
                            tipo_discrepancia=tipo_disc,
                            severidad=sev_disc,
                            fuente_a_nombre=finding.fuente_archivo or "CALIDAD_SSOT",
                            fuente_a_valor=finding.valor_detectado or "N/D",
                            fuente_b_nombre="EXPECTATIVA_OFICIAL",
                            fuente_b_valor=finding.valor_esperado or "N/D",
                            delta_valor=None,
                            estado_discrepancia=EstadoDiscrepancia.REQUIERE_REVISION,
                            justificacion_aclaratoria=finding.mensaje_humano,
                            usuario_revisor=None,
                        )
                        disc_repo.save(discrepancia)

        # ------------------------------------------------------------------
        # PASO 6: ADAPTAR HALLAZGOS Y EJECUTAR ROUTING INSTITUCIONAL
        # ------------------------------------------------------------------
        validaciones_adaptadas: List[ValidationResult] = []
        for finding in assessment.hallazgos:
            if finding.severidad in (SeveridadCalidad.ERROR, SeveridadCalidad.CRITICAL, "ERROR", "CRITICAL"):
                nivel_val = NivelValidacion.ERROR
            elif finding.severidad in (SeveridadCalidad.WARNING, "WARNING"):
                nivel_val = NivelValidacion.WARNING
            elif finding.severidad in (SeveridadCalidad.INFO, "INFO"):
                nivel_val = NivelValidacion.INFO
            else:
                nivel_val = NivelValidacion.REVISION

            validaciones_adaptadas.append(
                ValidationResult(
                    id_referencia=finding.id_referencia,
                    nivel=nivel_val,
                    codigo=finding.codigo_regla,
                    mensaje=finding.mensaje_humano,
                    fuente_origen=finding.fuente_archivo or actividad.fuente_origen,
                )
            )

        resultado_routing: ResultadoRouting = ParticipantRouter.enrutar(
            actividades=[actividad],
            personas=personas,
            participaciones=participaciones,
            validaciones=validaciones_adaptadas,
        )

        # ------------------------------------------------------------------
        # PASO 7: PERSISTIR DECISIONES DE ROUTING Y VERIFICAR INVARIANTE
        # ------------------------------------------------------------------
        participaciones_a_guardar: List[Participation] = []
        for reg in (
            resultado_routing.estudiantes
            + resultado_routing.academicos_administrativos
            + resultado_routing.colaboradores
            + resultado_routing.beneficiados
            + resultado_routing.cola_revision
            + resultado_routing.bloqueados
        ):
            part = reg.participacion
            codigo_relacional = RoutingACL.to_persistence(reg)

            if reg.estado_operativo == "BLOQUEADO":
                part.matriz_destino = None
                part.requiere_revision = True
                if not part.motivo_revision:
                    part.motivo_revision = reg.motivo_enrutamiento
            else:
                part.matriz_destino = codigo_relacional

            # Solo persistir si la persona asociada existe en SQLite (evita colapso por clave huérfana)
            if per_repo.get_by_id(part.id_persona) is not None:
                participaciones_a_guardar.append(part)
            else:
                logger.warning(
                    f"Pipeline: Participación '{part.id_participacion}' con clave foránea huérfana "
                    f"id_persona='{part.id_persona}' aislada en BLOQUEADOS; omitiendo escritura en SQLite "
                    f"para preservar integridad referencial relacional."
                )

        if not command.dry_run and participaciones_a_guardar:
            part_repo.save_batch(participaciones_a_guardar)

        # Verificación estricta de invariante
        m2_c = len(resultado_routing.estudiantes)
        m3_c = len(resultado_routing.academicos_administrativos)
        m4_c = len(resultado_routing.colaboradores)
        m5_c = len(resultado_routing.beneficiados)
        cola_c = len(resultado_routing.cola_revision)
        bloq_c = len(resultado_routing.bloqueados)
        suma_salidas = m2_c + m3_c + m4_c + m5_c + cola_c + bloq_c

        invariante_ok = (total_ingreso == suma_salidas) and resultado_routing.invariante_valida
        if not invariante_ok:
            msg = (
                f"FALLO DE INVARIANTE EN PIPELINE: Entrada={total_ingreso} != Salidas={suma_salidas} "
                f"(M2={m2_c}, M3={m3_c}, M4={m4_c}, M5={m5_c}, Cola={cola_c}, Bloq={bloq_c})"
            )
            logger.error(msg)
            raise ValueError(msg)

        # ------------------------------------------------------------------
        # PASO 8 & 9: PREPARACIÓN DE EXPORTACIÓN MEDIANTE EXPORT ACL
        # ------------------------------------------------------------------
        export_dataset: ExportDataset = ExportACL.adaptar_y_preparar(
            actividades=[actividad],
            personas=personas,
            participaciones=participaciones,
            resultado_routing=resultado_routing,
            politica_revision=command.politica_revision,
        )
        self._ultimo_dataset = export_dataset

        # Proyecciones DTO de salida
        calidad_dto = QualityAssessmentDTO(
            id_evaluacion=assessment.id_evaluacion,
            id_actividad=assessment.id_actividad,
            timestamp_evaluacion=assessment.timestamp_evaluacion.isoformat(),
            total_actividades_evaluadas=assessment.total_actividades_evaluadas,
            total_personas_evaluadas=assessment.total_personas_evaluadas,
            total_participaciones_evaluadas=assessment.total_participaciones_evaluadas,
            total_reglas_ejecutadas=assessment.total_reglas_ejecutadas,
            total_criticos=assessment.total_criticos,
            total_errores=assessment.total_errores,
            total_advertencias=assessment.total_advertencias,
            total_revisiones=assessment.total_revisiones,
            total_informativos=assessment.total_informativos,
            total_aptas=assessment.total_aptas,
            total_en_revision=assessment.total_en_revision,
            total_cola_revision=assessment.total_cola_revision,
            total_bloqueadas=assessment.total_bloqueadas,
            hallazgos=[
                ValidationFindingDTO(
                    id_hallazgo=h.id_hallazgo,
                    codigo_regla=h.codigo_regla,
                    severidad=h.severidad if isinstance(h.severidad, str) else h.severidad.value,
                    id_referencia=h.id_referencia,
                    entidad_afectada=h.entidad_afectada,
                    campo_origen=h.campo_origen,
                    valor_detectado=h.valor_detectado,
                    valor_esperado=h.valor_esperado,
                    mensaje_humano=h.mensaje_humano,
                    fuente_archivo=h.fuente_archivo,
                    requiere_discrepancia_persistente=h.requiere_discrepancia_persistente,
                    timestamp=h.timestamp.isoformat(),
                )
                for h in assessment.hallazgos
            ],
            estado_general_calidad=assessment.estado_general_calidad.value,
        )

        routing_dto = EnrutarParticipacionesResultDTO(
            id_actividad=command.id_actividad,
            total_participaciones=total_ingreso,
            total_m2_estudiantes=m2_c,
            total_m3_academicos_admin=m3_c,
            total_m4_colaboradores=m4_c,
            total_m5_beneficiados=m5_c,
            total_cola_revision=cola_c,
            total_bloqueados=bloq_c,
            invariante_conservacion_valida=invariante_ok,
        )

        # Conteo operativo global
        aptas_c = (
            sum(1 for r in resultado_routing.estudiantes if r.estado_operativo == "APTO")
            + sum(1 for r in resultado_routing.academicos_administrativos if r.estado_operativo == "APTO")
            + sum(1 for r in resultado_routing.colaboradores if r.estado_operativo == "APTO")
            + sum(1 for r in resultado_routing.beneficiados if r.estado_operativo == "APTO")
        )
        en_rev_c = (
            sum(1 for r in resultado_routing.estudiantes if r.estado_operativo == "EN_REVISION")
            + sum(1 for r in resultado_routing.academicos_administrativos if r.estado_operativo == "EN_REVISION")
            + sum(1 for r in resultado_routing.colaboradores if r.estado_operativo == "EN_REVISION")
            + sum(1 for r in resultado_routing.beneficiados if r.estado_operativo == "EN_REVISION")
            + cola_c
        )

        logger.info(
            f"Pipeline completado exitosamente para actividad '{command.id_actividad}'. "
            f"Total={total_ingreso}, Aptas={aptas_c}, EnRevision={en_rev_c}, Bloqueadas={bloq_c}. "
            f"Exportables preparadas={export_dataset.dto.total_exportables_nominales}."
        )

        return PipelineActividadResultDTO(
            id_actividad=command.id_actividad,
            nombre_actividad=actividad.nombre_actividad_oficial or actividad.nombre_actividad_original,
            fecha_ejecucion_iso=fecha_inicio_iso,
            dry_run=command.dry_run,
            calidad=calidad_dto,
            routing=routing_dto,
            exportacion_preparada=export_dataset.dto,
            total_participaciones_ingreso=total_ingreso,
            total_aptas=aptas_c,
            total_en_revision=en_rev_c,
            total_bloqueadas=bloq_c,
            invariante_conservacion_valida=invariante_ok,
        )
