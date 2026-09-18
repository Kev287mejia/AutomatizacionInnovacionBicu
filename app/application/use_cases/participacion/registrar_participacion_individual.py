"""Caso de uso CU-PAR-01: RegistrarParticipacionIndividual.

Orquesta el asentamiento de una asistencia individual vinculando una persona a una actividad.
Reglas fundamentales:
- Application no decide ruteo institucional (M2..M5) ni prevalencia de beneficiario (RN-C03).
- No ejecuta matching ni deduplicación.
- Valida la existencia referencial de actividad y persona si se proveen los repositorios.
"""

from typing import Optional

from app.application.commands.participacion_commands import (
    RegistrarParticipacionIndividualCommand,
)
from app.application.dto.output_dtos import ParticipacionDetalleDTO
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.models.participation import Participation
from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.persona_repository import IPersonaRepository


class RegistrarParticipacionIndividualUseCase:
    """Caso de uso para registrar una participación individual."""

    def __init__(
        self,
        participacion_repo: IParticipacionRepository,
        actividad_repo: Optional[IActividadRepository] = None,
        persona_repo: Optional[IPersonaRepository] = None,
    ) -> None:
        """Inicializa el caso de uso con repositorios específicos.

        Args:
            participacion_repo: Puerto de persistencia de Participación.
            actividad_repo: Puerto de persistencia opcional para validar existencia de Actividad.
            persona_repo: Puerto de persistencia opcional para validar existencia de Persona.
        """
        self._participacion_repo = participacion_repo
        self._actividad_repo = actividad_repo
        self._persona_repo = persona_repo

    def execute(
        self, command: RegistrarParticipacionIndividualCommand
    ) -> ParticipacionDetalleDTO:
        """Ejecuta el registro de la participación sin aplicar lógica de routing institucional.

        Args:
            command: Comando con los datos de asistencia y categoría.

        Returns:
            ParticipacionDetalleDTO con el registro asentado.

        Raises:
            EntityNotFoundError: Si la actividad o persona vinculada no existe en el repositorio.
        """
        if self._actividad_repo is not None and not self._actividad_repo.exists(
            command.id_actividad
        ):
            raise EntityNotFoundError("Actividad", command.id_actividad)

        persona = None
        if self._persona_repo is not None:
            persona = self._persona_repo.get_by_id(command.id_persona)
            if persona is None:
                raise EntityNotFoundError("Persona", command.id_persona)

        participacion = Participation(
            id_actividad=command.id_actividad,
            id_persona=command.id_persona,
            categoria_participacion=command.categoria_participacion,
            nivel_confianza_identidad=command.nivel_confianza_identidad,
            fuente_origen=command.fuente_origen,
            observaciones=command.observaciones,
        )

        self._participacion_repo.save(participacion)

        cat_str = (
            participacion.categoria_participacion.value
            if hasattr(participacion.categoria_participacion, "value")
            else str(participacion.categoria_participacion)
        )

        return ParticipacionDetalleDTO(
            id_participacion=participacion.id_participacion,
            id_actividad=participacion.id_actividad,
            id_persona=participacion.id_persona,
            nombre_completo=persona.nombre_completo if persona else "N/D",
            cedula=persona.cedula if persona else None,
            categoria=cat_str,
            matriz_destino=getattr(participacion, "matriz_destino", None),
            requiere_revision=participacion.requiere_revision,
            motivo_revision=participacion.motivo_revision,
        )
