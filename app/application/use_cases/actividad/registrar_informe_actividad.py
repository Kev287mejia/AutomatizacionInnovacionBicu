"""Caso de uso CU-ACT-04: RegistrarInformeActividad.

Orquesta el asentamiento y custodia institucional de la emisión del informe Word individual
de una actividad. Valida la existencia de la actividad vinculada y preserva el hash SHA-256.
"""

from app.application.commands.actividad_commands import RegistrarInformeActividadCommand
from app.application.dto.output_dtos import InformeActividadRegistradoDTO
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.ports.actividad_repository import IActividadRepository


class RegistrarInformeActividadUseCase:
    """Caso de uso para registrar el informe individual emitido de una actividad."""

    def __init__(self, actividad_repo: IActividadRepository) -> None:
        """Inicializa el caso de uso con el repositorio de actividades.

        Args:
            actividad_repo: Puerto de persistencia de Actividad.
        """
        self._actividad_repo = actividad_repo

    def execute(
        self, command: RegistrarInformeActividadCommand
    ) -> InformeActividadRegistradoDTO:
        """Ejecuta el registro del informe individual asegurando la referencia a la actividad.

        Args:
            command: Comando con la ruta, hash SHA-256 y total reportado.

        Returns:
            InformeActividadRegistradoDTO con los datos asentados.

        Raises:
            EntityNotFoundError: Si la actividad asociada no existe.
        """
        if not self._actividad_repo.exists(command.id_actividad):
            raise EntityNotFoundError("Actividad", command.id_actividad)

        return InformeActividadRegistradoDTO(
            id_actividad=command.id_actividad,
            ruta_archivo_word=command.ruta_archivo_word,
            hash_sha256=command.hash_sha256,
            total_participantes_declarados=command.total_participantes_declarados,
        )
