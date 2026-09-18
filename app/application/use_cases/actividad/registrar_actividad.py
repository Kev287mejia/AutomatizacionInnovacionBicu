"""Caso de uso CU-ACT-01: RegistrarActividad.

Orquesta el registro de una nueva actividad institucional en el SSOT.
"""

from app.application.commands.actividad_commands import RegistrarActividadCommand
from app.application.dto.output_dtos import ActividadDetalleDTO
from app.core.models.activity import Activity
from app.core.ports.actividad_repository import IActividadRepository


class RegistrarActividadUseCase:
    """Caso de uso para registrar una nueva actividad en el sistema."""

    def __init__(self, actividad_repo: IActividadRepository) -> None:
        """Inicializa el caso de uso con el repositorio de actividades.

        Args:
            actividad_repo: Puerto de persistencia del agregado Actividad.
        """
        self._actividad_repo = actividad_repo

    def execute(self, command: RegistrarActividadCommand) -> ActividadDetalleDTO:
        """Ejecuta el registro de la actividad en el SSOT.

        Args:
            command: Comando con los datos de la actividad a registrar.

        Returns:
            ActividadDetalleDTO con la información persistida.
        """
        actividad = Activity(
            nombre_actividad_original=command.nombre_actividad_original,
            nombre_actividad_oficial=command.nombre_actividad_oficial,
            fecha_evento=command.fecha_evento,
            sede=command.sede,
            departamento=command.departamento,
            municipio_evento=command.municipio_evento,
            programa=command.programa,
            ambito=command.ambito,
            tipo_evento=command.tipo_evento,
            eje_linea_estrategica=command.eje_linea_estrategica,
            informacion_adicional=command.informacion_adicional,
            fuente_origen=command.fuente_origen,
        )

        self._actividad_repo.save(actividad)

        return ActividadDetalleDTO(
            id_actividad=actividad.id_actividad,
            nombre_actividad_original=actividad.nombre_actividad_original,
            nombre_actividad_oficial=actividad.nombre_actividad_oficial,
            fecha_evento=str(actividad.fecha_evento) if actividad.fecha_evento else None,
            sede=actividad.sede,
            departamento=actividad.departamento,
            municipio_evento=actividad.municipio_evento,
            programa=actividad.programa,
            ambito=actividad.ambito,
            tipo_evento=actividad.tipo_evento,
            eje_linea_estrategica=actividad.eje_linea_estrategica,
            informacion_adicional=actividad.informacion_adicional,
            fuente_origen=actividad.fuente_origen,
        )
