"""Puerto de persistencia para la entidad asociativa Participación.

Define la interfaz abstracta IParticipacionRepository desacoplada
de cualquier tecnología física de base de datos.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.models.participation import Participation


class IParticipacionRepository(ABC):
    """Puerto de repositorio para gestionar asistencias y participaciones de personas en actividades.

    Reglas institucionales de diseño:
    - Neutralidad de ruteo: El repositorio persiste y consulta las participaciones;
      NO decide de forma autónoma el ruteo hacia matrices ni ejecuta las reglas de negocio
      (la prevalencia de rol RN-C03 es responsabilidad exclusiva de la capa de dominio).
    - Preservación histórica: Respeta la condición de registros históricos preexistentes (RN-C06).
    """

    @abstractmethod
    def save(self, participacion: Participation) -> None:
        """Inserta o actualiza un registro individual de participación.

        Args:
            participacion: Entidad Participation a persistir.
        """
        ...

    @abstractmethod
    def save_batch(self, participaciones: List[Participation]) -> None:
        """Inserta o actualiza un lote de participaciones (útil para listas masivas de asistencia).

        Args:
            participaciones: Lista de entidades Participation a persistir.
        """
        ...

    @abstractmethod
    def get_by_id(self, id_participacion: str) -> Optional[Participation]:
        """Recupera una participación por su identificador único (UUID).

        Args:
            id_participacion: Identificador UUID de la participación.

        Returns:
            Instancia de Participation si existe, None en caso contrario.
        """
        ...

    @abstractmethod
    def get_by_actividad(self, id_actividad: str) -> List[Participation]:
        """Recupera la totalidad de participaciones vinculadas a una actividad.

        Args:
            id_actividad: Identificador UUID de la actividad.

        Returns:
            Lista de participaciones asociadas a la actividad.
        """
        ...

    @abstractmethod
    def get_by_persona(self, id_persona: str) -> List[Participation]:
        """Recupera la trayectoria de participaciones registradas para una persona.

        Args:
            id_persona: Identificador UUID interno de la persona.

        Returns:
            Lista de participaciones de dicha persona.
        """
        ...

    @abstractmethod
    def get_by_actividad_and_persona(
        self, id_actividad: str, id_persona: str
    ) -> Optional[Participation]:
        """Recupera el registro de participación específico entre una actividad y una persona.

        Args:
            id_actividad: Identificador de la actividad.
            id_persona: Identificador interno de la persona.

        Returns:
            Instancia de Participation si existe la relación, None en caso contrario.
        """
        ...

    @abstractmethod
    def list_by_matriz_destino(
        self, matriz_destino: str, id_actividad: Optional[str] = None
    ) -> List[Participation]:
        """Filtra participaciones por su etiqueta de matriz de destino (M2, M3, M4, M5).

        Args:
            matriz_destino: Código oficial de matriz de destino.
            id_actividad: Filtro opcional por actividad específica.

        Returns:
            Lista de participaciones clasificadas para dicha matriz.
        """
        ...

    @abstractmethod
    def list_requieren_revision(
        self, id_actividad: Optional[str] = None
    ) -> List[Participation]:
        """Recupera participaciones que poseen la bandera de revisión humana activada.

        Args:
            id_actividad: Filtro opcional por actividad.

        Returns:
            Lista de participaciones que demandan validación o aclaración.
        """
        ...

    @abstractmethod
    def count_by_actividad(self, id_actividad: str) -> int:
        """Retorna el conteo total de participaciones para una actividad.

        Args:
            id_actividad: Identificador de la actividad.

        Returns:
            Cantidad entera de participantes registrados.
        """
        ...
