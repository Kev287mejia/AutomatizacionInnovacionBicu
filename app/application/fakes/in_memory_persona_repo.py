"""Implementación Fake en memoria de IPersonaRepository para pruebas de Application.

Simula el comportamiento de persistencia del SSOT bio-demográfico:
- Cédula nullable: Múltiples personas con cédula None coexisten sin error (RN-C04).
- Unicidad de cédula no nula: Lanza EntityAlreadyExistsError si dos personas distintas tienen la misma cédula.
- No ejecuta algoritmos de matching ni deduplicación automática de negocio.
"""

from copy import deepcopy
from typing import Dict, List, Optional

from app.core.exceptions.persistence_exceptions import EntityAlreadyExistsError
from app.core.models.person import Person
from app.core.ports.persona_repository import IPersonaRepository


class InMemoryPersonaRepository(IPersonaRepository):
    """Repositorio fake en memoria para el agregado Persona."""

    def __init__(self, datos_iniciales: Optional[Dict[str, Person]] = None) -> None:
        self._personas: Dict[str, Person] = deepcopy(datos_iniciales) if datos_iniciales else {}

    def save(self, persona: Person) -> None:
        """Inserta o actualiza una persona.

        Simula la restricción relacional UNIQUE sobre cédula no nula.
        """
        # Si la persona tiene cédula no vacía, validar que no pertenezca a otra persona registrada
        if persona.cedula and persona.cedula.strip():
            cedula_limpia = persona.cedula.strip().upper()
            for existente in self._personas.values():
                if existente.id_persona_interno != persona.id_persona_interno:
                    if existente.cedula and existente.cedula.strip().upper() == cedula_limpia:
                        raise EntityAlreadyExistsError(
                            "Persona", "cedula", persona.cedula
                        )

        self._personas[persona.id_persona_interno] = deepcopy(persona)

    def get_by_id(self, id_persona_interno: str) -> Optional[Person]:
        """Recupera una persona por su UUID interno."""
        persona = self._personas.get(id_persona_interno)
        return deepcopy(persona) if persona is not None else None

    def get_by_cedula(self, cedula: str) -> Optional[Person]:
        """Recupera una persona por su cédula oficial."""
        if not cedula or not cedula.strip():
            return None
        cedula_buscada = cedula.strip().upper()
        for persona in self._personas.values():
            if persona.cedula and persona.cedula.strip().upper() == cedula_buscada:
                return deepcopy(persona)
        return None

    def get_by_numero_institucional(self, numero: str) -> Optional[Person]:
        """Recupera una persona por su carné o código institucional."""
        if not numero or not numero.strip():
            return None
        num_buscado = numero.strip().upper()
        for persona in self._personas.values():
            if persona.numero_unico and persona.numero_unico.strip().upper() == num_buscado:
                return deepcopy(persona)
        return None

    def search_by_nombre(self, nombre_query: str, limite: int = 10) -> List[Person]:
        """Busca personas cuyo nombre contenga la cadena buscada."""
        if not nombre_query or not nombre_query.strip():
            return []
        q = nombre_query.strip().lower()
        coincidencias = []
        for persona in self._personas.values():
            if q in persona.nombre_completo.lower():
                coincidencias.append(deepcopy(persona))
                if len(coincidencias) >= limite:
                    break
        return coincidencias

    def exists(self, id_persona_interno: str) -> bool:
        """Comprueba si existe una persona por su ID interno."""
        return id_persona_interno in self._personas

    def count(self) -> int:
        """Retorna la cantidad total de personas almacenadas."""
        return len(self._personas)
