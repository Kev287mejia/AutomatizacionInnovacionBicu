"""app.application.use_cases.calidad.evaluar_calidad_actividad

Caso de uso: EvaluarCalidadActividadUseCase.
Orquesta la evaluación pericial exhaustiva de calidad sobre una actividad institucional,
sus participantes y fuentes contrastadas bajo el principio inviolable DETECTAR ≠ CORREGIR (RN-C07).

CONTRATO DRY_RUN VS PERSISTENCIA:
- dry_run = True: Evaluación puramente diagnóstica en memoria. CERO operaciones de escritura (INSERT/UPDATE).
  Si existe Unit of Work, asegura rollback y nunca ejecuta commit.
- dry_run = False y persistir_discrepancias = True: Persiste discrepancias detectadas en 'discrepancia'
  y actualiza marcas operativas en 'participacion' atómicamente.
- dry_run = False y persistir_discrepancias = False: Actualiza marcas operativas en 'participacion'
  sin insertar filas en la tabla 'discrepancia'.
"""

import uuid
from typing import Dict, List, Optional

from app.audit.audit_logger import get_logger
from app.application.commands.calidad_commands import EvaluarCalidadActividadCommand
from app.application.dto.quality_dtos import (
    QualityAssessmentDTO,
    ValidationFindingDTO,
)
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.models.discrepancy import (
    Discrepancia,
    EstadoDiscrepancia,
    SeveridadDiscrepancia,
    TipoDiscrepancia,
)
from app.core.models.participation import Participation
from app.core.models.person import Person
from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.unit_of_work import IUnitOfWork
from app.quality.models import QualityAssessment, QualityContext, ValidationFinding
from app.quality.validator import QualityValidator

logger = get_logger(__name__)


class EvaluarCalidadActividadUseCase:
    """Orquestador de aplicación para la evaluación pericial de calidad de una actividad."""

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

    def execute(
        self,
        command: EvaluarCalidadActividadCommand,
        uow: Optional[IUnitOfWork] = None,
    ) -> QualityAssessmentDTO:
        """Ejecuta la evaluación de calidad coordinando la frontera transaccional."""
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
        command: EvaluarCalidadActividadCommand,
        act_repo: IActividadRepository,
        per_repo: IPersonaRepository,
        part_repo: IParticipacionRepository,
        disc_repo: Optional[IDiscrepanciaRepository],
    ) -> QualityAssessmentDTO:
        """Lógica central de ejecución de la evaluación."""
        # 1. Validar existencia de la actividad receptora
        actividad = act_repo.get_by_id(command.id_actividad)
        if actividad is None:
            raise EntityNotFoundError("Actividad", command.id_actividad)

        # 2. Cargar participaciones vinculadas a la actividad
        participaciones: List[Participation] = part_repo.get_by_actividad(command.id_actividad)

        # 3. Cargar personas asociadas a esas participaciones
        ids_personas = {part.id_persona for part in participaciones}
        personas: List[Person] = []
        for pid in ids_personas:
            p = per_repo.get_by_id(pid)
            if p is not None:
                personas.append(p)

        # 4. Construir contexto de calidad
        ctx = QualityContext(
            actividad=actividad,
            personas=personas,
            participaciones=participaciones,
            fuente_archivo_asistencia=command.fuente_archivo_asistencia or actividad.fuente_origen,
            fuente_archivo_informe=command.fuente_archivo_informe,
        )

        # 5. Ejecutar Domain Service puro
        validator = QualityValidator()
        assessment: QualityAssessment = validator.evaluar_contexto(ctx)

        # 6. Gobernanza de persistencia según banderas del contrato
        if not command.dry_run:
            # 6.1 Persistir discrepancias formales si está habilitado
            if command.persistir_discrepancias and disc_repo is not None:
                discrepancias_a_guardar: List[Discrepancia] = []
                for h in assessment.hallazgos:
                    if h.requiere_discrepancia_persistente:
                        # Mapeo a tipo físico SQLite (respetando CHECK)
                        if h.codigo_regla == "Q-17":
                            tipo_disc = TipoDiscrepancia.FECHA_DISCORDANTE
                        elif h.codigo_regla == "Q-18":
                            tipo_disc = TipoDiscrepancia.PLAN_VS_REAL
                        elif h.codigo_regla == "Q-19":
                            tipo_disc = TipoDiscrepancia.RESUMEN_VS_NOMINAL
                        else:
                            tipo_disc = TipoDiscrepancia.OTRO

                        # Severidad compatible SQLite ('INFO', 'WARNING', 'ERROR')
                        sev_disc = (
                            SeveridadDiscrepancia.ERROR
                            if h.severidad in ("ERROR", "CRITICAL")
                            else SeveridadDiscrepancia.INFO
                            if h.severidad == "INFO"
                            else SeveridadDiscrepancia.WARNING
                        )

                        # Empaquetar contexto de procedencia para GAP-DISC-01
                        fuente_a_nom = f"{h.fuente_archivo or 'Fuente'}.{h.entidad_afectada}"
                        if h.id_referencia:
                            fuente_a_nom = f"{fuente_a_nom}[{h.id_referencia}]"
                        if h.campo_origen:
                            fuente_a_nom = f"{fuente_a_nom}.{h.campo_origen}"

                        disc = Discrepancia(
                            id_actividad=command.id_actividad,
                            tipo_discrepancia=tipo_disc,
                            severidad=sev_disc,
                            fuente_a_nombre=fuente_a_nom,
                            fuente_a_valor=str(h.valor_detectado if h.valor_detectado is not None else "None"),
                            fuente_b_nombre=f"SSOT.{h.entidad_afectada}.referencia",
                            fuente_b_valor=str(h.valor_esperado if h.valor_esperado is not None else "None"),
                            delta_valor=h.mensaje_humano,
                            estado=EstadoDiscrepancia.REQUIERE_REVISION,
                        )
                        discrepancias_a_guardar.append(disc)

                if discrepancias_a_guardar:
                    disc_repo.save_batch(discrepancias_a_guardar)

            # 6.2 Actualizar únicamente las marcas operativas autorizadas en Participation
            REGLAS_REVISION_OPERATIVA = {
                "Q-02", "Q-03", "Q-08", "Q-09", "Q-10", "Q-12", "Q-13", "Q-15", "Q-20"
            }
            mapa_hallazgos_part: Dict[str, List[ValidationFinding]] = {}
            for h in assessment.hallazgos:
                if h.id_referencia:
                    mapa_hallazgos_part.setdefault(h.id_referencia, []).append(h)

            parts_actualizadas: List[Participation] = []
            for part in participaciones:
                h_part = mapa_hallazgos_part.get(part.id_participacion, [])
                h_per = mapa_hallazgos_part.get(part.id_persona, [])
                h_tot = h_part + h_per

                necesita_revision = any(h.codigo_regla in REGLAS_REVISION_OPERATIVA for h in h_tot)
                es_error = any(h.severidad in ("ERROR", "CRITICAL") for h in h_tot)

                cambio = False
                if necesita_revision or es_error:
                    if not part.requiere_revision:
                        part.requiere_revision = True
                        cambio = True

                    motivos_nuevos = [h.mensaje_humano for h in h_tot]
                    motivo_previo = part.motivo_revision or ""
                    for m in motivos_nuevos:
                        if m not in motivo_previo:
                            motivo_previo = f"{motivo_previo} | {m}" if motivo_previo else m
                            cambio = True
                    part.motivo_revision = motivo_previo

                # Para Q-13, agregar observación de evidencia sin sobrescribir
                for h in h_tot:
                    if h.codigo_regla == "Q-13":
                        evidencia_obs = f"[Aparición repetida detectada: {h.mensaje_humano}]"
                        obs_prev = part.observaciones or ""
                        if evidencia_obs not in obs_prev:
                            part.observaciones = f"{obs_prev}; {evidencia_obs}" if obs_prev else evidencia_obs
                            cambio = True

                if cambio:
                    parts_actualizadas.append(part)

            if parts_actualizadas:
                part_repo.save_batch(parts_actualizadas)

        # 7. Proyectar y retornar el DTO consolidado
        return self._to_dto(assessment)

    @staticmethod
    def _to_dto(assessment: QualityAssessment) -> QualityAssessmentDTO:
        """Convierte el Value Object QualityAssessment al DTO de transporte."""
        hallazgos_dto = [
            ValidationFindingDTO(
                id_hallazgo=h.id_hallazgo,
                codigo_regla=h.codigo_regla,
                severidad=h.severidad,
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
        ]

        return QualityAssessmentDTO(
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
            hallazgos=hallazgos_dto,
            estado_general_calidad=assessment.estado_general_calidad.value,
        )
