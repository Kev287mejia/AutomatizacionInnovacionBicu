"""Caso de uso CU-ACT-03: AsignarDisenoMetodologico.

Orquesta la asignación de diseño pedagógico y metodológico a una actividad.
La relación es opcional (0..1 : 1). No inventa reglas de obligatoriedad que no estén
definidas formalmente en la capa de Dominio.
"""

from app.application.commands.actividad_commands import AsignarDisenoMetodologicoCommand
from app.application.dto.output_dtos import DisenoMetodologicoAsignadoDTO
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.ports.actividad_repository import IActividadRepository


class AsignarDisenoMetodologicoUseCase:
    """Caso de uso para asociar diseño metodológico a una actividad."""

    def __init__(self, actividad_repo: IActividadRepository) -> None:
        """Inicializa el caso de uso con el repositorio de actividades.

        Args:
            actividad_repo: Puerto de persistencia del agregado Actividad.
        """
        self._actividad_repo = actividad_repo

    def execute(
        self, command: AsignarDisenoMetodologicoCommand
    ) -> DisenoMetodologicoAsignadoDTO:
        """Ejecuta la asignación del diseño metodológico a la actividad.

        Args:
            command: Comando con los datos didácticos y pedagógicos.

        Returns:
            DisenoMetodologicoAsignadoDTO con los datos confirmados.

        Raises:
            EntityNotFoundError: Si la actividad especificada no existe en el repositorio.
        """
        if not self._actividad_repo.exists(command.id_actividad):
            raise EntityNotFoundError("Actividad", command.id_actividad)

        return DisenoMetodologicoAsignadoDTO(
            id_actividad=command.id_actividad,
            objetivo_general=command.objetivo_general,
            horas_duracion=command.horas_duracion,
            facilitadores=command.facilitadores,
        )
