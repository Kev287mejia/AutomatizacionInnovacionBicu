"""Caso de uso: EnrutarParticipacionesActividadUseCase.

Orquesta la clasificación y persistencia institucional de todas las asistencias
registradas para una actividad específica hacia sus matrices oficiales (M2..M5)
o cubetas de control (COLA_REVISION, BLOQUEADOS).

Reglas fundamentales de orquestación:
- Application Layer únicamente orquesta: NO implementa reglas de negocio ni lógica heurística de routing.
- Delega la evaluación de reglas a Domain (ParticipantRouter).
- Traduce decisiones mediante RoutingACL (excluyendo formalmente a M1).
- Transaccionalidad garantizada: actualiza participaciones dentro de una transacción atómica (commit o rollback).
- Invariante de conservación estricta:
  total_entrada == M2 + M3 + M4 + M5 + COLA_REVISION + BLOQUEADOS
"""

from typing import List, Optional
from app.audit.audit_logger import get_logger
from app.application.commands.participacion_commands import EnrutarParticipacionesCommand
from app.application.dto.output_dtos import EnrutarParticipacionesResultDTO
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.unit_of_work import IUnitOfWork
from app.routing.acl import RoutingACL
from app.routing.participant_router import ParticipantRouter
from app.routing.models import ResultadoRouting

logger = get_logger(__name__)


class EnrutarParticipacionesActividadUseCase:
    """Orquestador de aplicación para el routing institucional de participaciones."""

    def __init__(
        self,
        participacion_repo: Optional[IParticipacionRepository] = None,
        actividad_repo: Optional[IActividadRepository] = None,
        persona_repo: Optional[IPersonaRepository] = None,
        uow: Optional[IUnitOfWork] = None,
    ) -> None:
        """Inicializa el caso de uso con repositorios o Unit of Work.

        Args:
            participacion_repo: Puerto de persistencia de participaciones.
            actividad_repo: Puerto de persistencia de actividades.
            persona_repo: Puerto de persistencia de personas.
            uow: Unidad de trabajo transaccional opcional.
        """
        self._participacion_repo = participacion_repo
        self._actividad_repo = actividad_repo
        self._persona_repo = persona_repo
        self._uow = uow

    def execute(self, command: EnrutarParticipacionesCommand) -> EnrutarParticipacionesResultDTO:
        """Ejecuta el enrutamiento de las participaciones de la actividad indicada.

        Args:
            command: Comando con el ID de la actividad y la bandera opcional de simulación (dry_run).

        Returns:
            EnrutarParticipacionesResultDTO con la distribución oficial e invariante verificada.

        Raises:
            EntityNotFoundError: Si la actividad no existe en el sistema.
            ValueError: Si no se configuran repositorios válidos o se viola la invariante.
        """
        # Si disponemos de UnitOfWork, coordinar la transacción atómica
        active_uow = self._uow
        if active_uow is not None:
            with active_uow:
                result = self._execute_core(
                    command=command,
                    act_repo=active_uow.actividades,
                    per_repo=active_uow.personas,
                    part_repo=active_uow.participaciones,
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
                "Debe proporcionarse una instancia de IUnitOfWork o todos los repositorios requeridos."
            )

        # Ejecución contra repositorios individuales
        return self._execute_core(
            command=command,
            act_repo=self._actividad_repo,
            per_repo=self._persona_repo,
            part_repo=self._participacion_repo,
        )

    def _execute_core(
        self,
        command: EnrutarParticipacionesCommand,
        act_repo: IActividadRepository,
        per_repo: IPersonaRepository,
        part_repo: IParticipacionRepository,
    ) -> EnrutarParticipacionesResultDTO:
        """Lógica central de orquestación del routing."""
        # 1. Validar existencia de la actividad
        actividad = act_repo.get_by_id(command.id_actividad)
        if actividad is None:
            raise EntityNotFoundError("Actividad", command.id_actividad)

        # 2. Obtener participaciones de la actividad
        participaciones: List[Participation] = part_repo.get_by_actividad(command.id_actividad)
        total_entrada = len(participaciones)

        if total_entrada == 0:
            logger.info(f"Actividad '{command.id_actividad}' no posee participaciones para enrutar.")
            return EnrutarParticipacionesResultDTO(
                id_actividad=command.id_actividad,
                total_participaciones=0,
                total_m2_estudiantes=0,
                total_m3_academicos_admin=0,
                total_m4_colaboradores=0,
                total_m5_beneficiados=0,
                total_cola_revision=0,
                total_bloqueados=0,
                invariante_conservacion_valida=True,
            )

        # 3. Obtener personas vinculadas
        persona_ids = {p.id_persona for p in participaciones}
        personas: List[Person] = []
        for pid in persona_ids:
            persona = per_repo.get_by_id(pid)
            if persona is not None:
                personas.append(persona)

        # 4. Invocar ParticipantRouter (Reglas de dominio puras)
        resultado: ResultadoRouting = ParticipantRouter.enrutar(
            actividades=[actividad],
            personas=personas,
            participaciones=participaciones,
        )

        # 5. Aplicar decisiones mediante RoutingACL
        # Actualizar matriz_destino en las participaciones
        participaciones_a_guardar: List[Participation] = []

        for reg in (
            resultado.estudiantes
            + resultado.academicos_administrativos
            + resultado.colaboradores
            + resultado.beneficiados
            + resultado.cola_revision
            + resultado.bloqueados
        ):
            part = reg.participacion
            # Traducir código oficial mediante ACL
            codigo_relacional = RoutingACL.to_persistence(reg)

            # Para bloqueados, el código es None pero estado_operativo es BLOQUEADO
            if reg.estado_operativo == "BLOQUEADO":
                part.matriz_destino = None
                part.requiere_revision = True
                if not part.motivo_revision:
                    part.motivo_revision = reg.motivo_enrutamiento
            else:
                part.matriz_destino = codigo_relacional

            participaciones_a_guardar.append(part)

        # 6. Persistir cambios en lote si no es simulación (dry_run)
        if not command.dry_run:
            part_repo.save_batch(participaciones_a_guardar)

        # 7. Verificar formalmente la invariante de conservación institucional
        m2_count = len(resultado.estudiantes)
        m3_count = len(resultado.academicos_administrativos)
        m4_count = len(resultado.colaboradores)
        m5_count = len(resultado.beneficiados)
        cola_count = len(resultado.cola_revision)
        bloq_count = len(resultado.bloqueados)

        suma_salidas = m2_count + m3_count + m4_count + m5_count + cola_count + bloq_count
        invariante_ok = (total_entrada == suma_salidas) and resultado.invariante_valida

        if not invariante_ok:
            msg = (
                f"FALLO DE INVARIANTE EN CASO DE USO: entrada={total_entrada} != "
                f"salidas={suma_salidas} (M2={m2_count}, M3={m3_count}, M4={m4_count}, "
                f"M5={m5_count}, Cola={cola_count}, Bloqueados={bloq_count})"
            )
            logger.error(msg)
            raise ValueError(msg)

        logger.info(
            f"Routing exitoso para actividad '{command.id_actividad}': {total_entrada} participaciones "
            f"(M2={m2_count}, M3={m3_count}, M4={m4_count}, M5={m5_count}, Cola={cola_count}, Bloq={bloq_count})."
        )

        # 8. Construir y retornar DTO de resultado
        return EnrutarParticipacionesResultDTO(
            id_actividad=command.id_actividad,
            total_participaciones=total_entrada,
            total_m2_estudiantes=m2_count,
            total_m3_academicos_admin=m3_count,
            total_m4_colaboradores=m4_count,
            total_m5_beneficiados=m5_count,
            total_cola_revision=cola_count,
            total_bloqueados=bloq_count,
            invariante_conservacion_valida=invariante_ok,
        )
