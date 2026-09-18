"""Puerto de persistencia para el agregado Discrepancia (Calidad y Auditoría).

Define la interfaz abstracta IDiscrepanciaRepository desacoplada
de cualquier tecnología física de base de datos.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.models.discrepancy import Discrepancia


class IDiscrepanciaRepository(ABC):
    """Puerto de repositorio para la gestión pericial de discrepancias bajo DETECTAR ≠ CORREGIR.

    Reglas institucionales de diseño (RN-C07):
    - Principio de No Mutación: El repositorio almacena divergencias detectadas sin alterar
      los valores originales de Fuente A ni Fuente B.
    - Prohibición de Corrección Automática: El repositorio no decide qué fuente prevalece
      ni corrige inconsistencias de forma unilateral.
    """

    @abstractmethod
    def save(self, discrepancia: Discrepancia) -> None:
        """Inserta o actualiza un registro de discrepancia.

        Args:
            discrepancia: Entidad Discrepancia a persistir.
        """
        ...

    @abstractmethod
    def save_batch(self, discrepancias: List[Discrepancia]) -> None:
        """Inserta o actualiza un lote de discrepancias detectadas.

        Args:
            discrepancias: Lista de entidades Discrepancia a persistir.
        """
        ...

    @abstractmethod
    def get_by_id(self, id_discrepancia: str) -> Optional[Discrepancia]:
        """Recupera una discrepancia por su identificador único (UUID).

        Args:
            id_discrepancia: Identificador UUID de la discrepancia.

        Returns:
            Instancia de Discrepancia si existe, None en caso contrario.
        """
        ...

    @abstractmethod
    def list_by_actividad(self, id_actividad: str) -> List[Discrepancia]:
        """Recupera la totalidad de discrepancias detectadas en una actividad.

        Args:
            id_actividad: Identificador UUID de la actividad.

        Returns:
            Lista de discrepancias asociadas a la actividad.
        """
        ...

    @abstractmethod
    def list_pendientes(
        self, severidad: Optional[str] = None
    ) -> List[Discrepancia]:
        """Recupera discrepancias activas no resueltas (estados REQUIERE_REVISION o EN_REVISION).

        Args:
            severidad: Filtro opcional por severidad ('INFO', 'WARNING', 'ERROR').

        Returns:
            Lista de discrepancias pendientes de revisión humana.
        """
        ...

    @abstractmethod
    def registrar_revision(
        self,
        id_discrepancia: str,
        nuevo_estado: str,
        justificacion: str,
        usuario_revisor: str,
    ) -> None:
        """Registra formalmente la aclaración o resolución humana de una discrepancia.

        Preserva inalterados los valores fuente originales y solo asienta la nota de auditoría.

        Args:
            id_discrepancia: Identificador de la discrepancia.
            nuevo_estado: Nuevo estado ('ACLARADO', 'CONCORDANTE', etc.).
            justificacion: Justificación o explicación institucional del revisor.
            usuario_revisor: Identificador del funcionario revisor.
        """
        ...
