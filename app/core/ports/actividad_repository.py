"""Puerto de persistencia para el agregado Actividad.

Define la interfaz abstracta IActividadRepository desacoplada
de cualquier tecnología física de base de datos.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional, Union

from app.core.models.activity import Activity


class IActividadRepository(ABC):
    """Puerto de repositorio para gestionar el ciclo de vida del agregado Actividad."""

    @abstractmethod
    def save(self, actividad: Activity) -> None:
        """Inserta o actualiza una entidad Actividad.

        Args:
            actividad: Entidad Actividad a persistir.
        """
        ...

    @abstractmethod
    def get_by_id(self, id_actividad: str) -> Optional[Activity]:
        """Recupera una actividad por su identificador único (UUID).

        Args:
            id_actividad: Identificador único de la actividad.

        Returns:
            Instancia de Activity si existe, None en caso contrario.
        """
        ...

    @abstractmethod
    def exists(self, id_actividad: str) -> bool:
        """Comprueba si existe una actividad registrada con el ID especificado.

        Args:
            id_actividad: Identificador único a consultar.

        Returns:
            True si la actividad existe, False en caso contrario.
        """
        ...

    @abstractmethod
    def list_by_periodo(
        self,
        fecha_inicio: Union[date, str],
        fecha_fin: Union[date, str],
        sede: Optional[str] = None
    ) -> List[Activity]:
        """Consulta actividades ejecutadas en un rango de fechas, opcionalmente filtradas por sede.

        Args:
            fecha_inicio: Fecha inicial del período (inclusive).
            fecha_fin: Fecha final del período (inclusive).
            sede: Filtro opcional por sede/recinto institucional.

        Returns:
            Lista de actividades coincidentes.
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Retorna el número total de actividades registradas.

        Returns:
            Cantidad entera de actividades.
        """
        ...
