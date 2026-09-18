"""Caso de uso CU-ACT-02: AsignarPlanificacion.

Orquesta la asignación de metas operativas y desglose presupuestario a una actividad.
La relación es opcional (0..1 : 1) respetando que actividades emergentes pueden carecer de planificación.
"""

from app.application.commands.actividad_commands import AsignarPlanificacionCommand
from app.application.dto.output_dtos import PlanificacionAsignadaDTO
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.ports.actividad_repository import IActividadRepository


class AsignarPlanificacionUseCase:
    """Caso de uso para asociar planificación y presupuesto a una actividad."""

    def __init__(self, actividad_repo: IActividadRepository) -> None:
        """Inicializa el caso de uso con el repositorio de actividades.

        Args:
            actividad_repo: Puerto de persistencia del agregado Actividad.
        """
        self._actividad_repo = actividad_repo

    def execute(self, command: AsignarPlanificacionCommand) -> PlanificacionAsignadaDTO:
        """Ejecuta la asignación de planificación a la actividad especificada.

        Args:
            command: Comando con las metas y partidas presupuestarias.

        Returns:
            PlanificacionAsignadaDTO con los valores asignados y el presupuesto acumulado.

        Raises:
            EntityNotFoundError: Si la actividad especificada no existe en el repositorio.
        """
        if not self._actividad_repo.exists(command.id_actividad):
            raise EntityNotFoundError("Actividad", command.id_actividad)

        total_presupuesto = round(
            sum(p.subtotal for p in command.partidas_presupuestarias), 2
        )

        return PlanificacionAsignadaDTO(
            id_actividad=command.id_actividad,
            anio=command.anio,
            mes=command.mes,
            semana=command.semana,
            meta_participantes=command.meta_participantes,
            total_presupuesto=total_presupuesto,
            cantidad_partidas=len(command.partidas_presupuestarias),
        )
