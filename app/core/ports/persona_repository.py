"""Puerto de persistencia para el agregado Persona (SSOT Bio-Demográfica).

Define la interfaz abstracta IPersonaRepository desacoplada
de cualquier tecnología física de base de datos.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.models.person import Person


class IPersonaRepository(ABC):
    """Puerto de repositorio para gestionar el ciclo de vida y búsqueda de Persona.

    Reglas institucionales de diseño:
    - Identidad técnica subrogada: `id_persona_interno` (UUID).
    - Cédula nullable: Múltiples personas pueden carecer de cédula (cedula = NULL / None)
      sin que ello constituya colisión de identidad (Regla RN-C04).
    - No invención: Queda estrictamente prohibido inventar o asumir identificadores.
    - Neutralidad de resolución: El repositorio almacena y consulta identidades;
      la lógica de unificación pertenece al servicio de dominio `IdentityResolver`.
    """

    @abstractmethod
    def save(self, persona: Person) -> None:
        """Inserta o actualiza una entidad Persona y sus perfiles asociados.

        Args:
            persona: Entidad Person a persistir.
        """
        ...

    @abstractmethod
    def get_by_id(self, id_persona_interno: str) -> Optional[Person]:
        """Recupera una persona por su identificador único interno (UUID).

        Args:
            id_persona_interno: Identificador UUID único de la persona.

        Returns:
            Instancia de Person si existe, None en caso contrario.
        """
        ...

    @abstractmethod
    def get_by_cedula(self, cedula: str) -> Optional[Person]:
        """Recupera una persona por su cédula oficial nicaragüense (Nivel 1 de confianza).

        Args:
            cedula: Cédula oficial en formato institucional. Si es vacía o None, retorna None.

        Returns:
            Instancia de Person si existe, None en caso contrario.
        """
        ...

    @abstractmethod
    def get_by_numero_institucional(self, numero: str) -> Optional[Person]:
        """Recupera una persona por su carné estudiantil o número de empleado (Nivel 2).

        Args:
            numero: Identificador institucional unívoco.

        Returns:
            Instancia de Person si existe, None en caso contrario.
        """
        ...

    @abstractmethod
    def search_by_nombre(self, nombre_query: str, limite: int = 10) -> List[Person]:
        """Busca personas cuyo nombre coincida o contenga la cadena provista.

        Utilizado primordialmente por el servicio de resolución de identidades (Nivel 4).

        Args:
            nombre_query: Cadena textual a buscar.
            limite: Cantidad máxima de candidatos a retornar.

        Returns:
            Lista de personas candidatas.
        """
        ...

    @abstractmethod
    def exists(self, id_persona_interno: str) -> bool:
        """Comprueba si existe una persona registrada con el ID interno provisto.

        Args:
            id_persona_interno: Identificador UUID interno a consultar.

        Returns:
            True si existe, False en caso contrario.
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Retorna la cantidad total de personas registradas en el SSOT.

        Returns:
            Cantidad entera de personas.
        """
        ...
