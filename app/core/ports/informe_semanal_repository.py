"""Puerto de persistencia para el agregado Informe Semanal Consolidado.

Define la interfaz abstracta IInformeSemanalRepository desacoplada
de cualquier tecnología física de base de datos.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.models.weekly_report import InformeSemanal, DetalleInformeSemanal


class IInformeSemanalRepository(ABC):
    """Puerto de repositorio para gestionar informes semanales consolidados de recinto."""

    @abstractmethod
    def save(
        self,
        informe: InformeSemanal,
        detalles: Optional[List[DetalleInformeSemanal]] = None,
    ) -> None:
        """Inserta o actualiza un informe semanal y opcionalmente su lista de actividades incluidas.

        Args:
            informe: Entidad InformeSemanal a persistir.
            detalles: Lista opcional de elementos DetalleInformeSemanal asociados.
        """
        ...

    @abstractmethod
    def get_by_id(self, id_informe_semanal: str) -> Optional[InformeSemanal]:
        """Recupera un informe semanal por su identificador único (UUID).

        Args:
            id_informe_semanal: Identificador UUID del informe semanal.

        Returns:
            Instancia de InformeSemanal si existe, None en caso contrario.
        """
        ...

    @abstractmethod
    def get_by_periodo(
        self, anio: int, mes: int, numero_semana: int, sede: str
    ) -> Optional[InformeSemanal]:
        """Recupera el informe semanal existente correspondiente a un período y recinto exactos.

        Args:
            anio: Año calendario.
            mes: Mes del año (1..12).
            numero_semana: Semana del mes (1..5).
            sede: Sede o recinto institucional emisor.

        Returns:
            Instancia de InformeSemanal si ya fue registrado, None en caso contrario.
        """
        ...

    @abstractmethod
    def list_all(self) -> List[InformeSemanal]:
        """Retorna el catálogo histórico de todos los informes semanales generados.

        Returns:
            Lista de informes semanales.
        """
        ...

    @abstractmethod
    def get_detalles(
        self, id_informe_semanal: str
    ) -> List[DetalleInformeSemanal]:
        """Recupera la secuencia ordenada de actividades incluidas en un informe semanal.

        Args:
            id_informe_semanal: Identificador del informe semanal.

        Returns:
            Lista de detalles ordenados por `orden_secuencia`.
        """
        ...
