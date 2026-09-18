"""Implementación Fake en memoria de IParticipacionRepository para pruebas de Application.

Almacena participaciones en memoria sin ejecutar reglas de negocio, routing institucional (M2..M5)
ni prevalencia de roles. Cumple estrictamente el contrato del puerto abstracto.
"""

from copy import deepcopy
from typing import Dict, List, Optional

from app.core.models.participation import Participation
from app.core.ports.participacion_repository import IParticipacionRepository


class InMemoryParticipacionRepository(IParticipacionRepository):
    """Repositorio fake en memoria para la entidad asociativa Participación."""

    def __init__(self, datos_iniciales: Optional[Dict[str, Participation]] = None) -> None:
        self._participaciones: Dict[str, Participation] = deepcopy(datos_iniciales) if datos_iniciales else {}
        self._matriz_map: Dict[str, str] = {}

    def save(self, participacion: Participation) -> None:
        """Inserta o actualiza una participación en memoria."""
        self._participaciones[participacion.id_participacion] = deepcopy(participacion)
        # Si el objeto recibido trae matriz_destino como atributo dinámico, preservarla sin deducirla
        matriz = getattr(participacion, "matriz_destino", None)
        if matriz:
            self._matriz_map[participacion.id_participacion] = str(matriz).strip().upper()

    def save_batch(self, participaciones: List[Participation]) -> None:
        """Inserta o actualiza un lote de participaciones."""
        for p in participaciones:
            self.save(p)

    def get_by_id(self, id_participacion: str) -> Optional[Participation]:
        """Recupera una participación por su UUID."""
        p = self._participaciones.get(id_participacion)
        return deepcopy(p) if p is not None else None

    def get_by_actividad(self, id_actividad: str) -> List[Participation]:
        """Recupera participaciones asociadas a una actividad."""
        return [
            deepcopy(p) for p in self._participaciones.values()
            if p.id_actividad == id_actividad
        ]

    def get_by_persona(self, id_persona: str) -> List[Participation]:
        """Recupera participaciones asociadas a una persona."""
        return [
            deepcopy(p) for p in self._participaciones.values()
            if p.id_persona == id_persona
        ]

    def get_by_actividad_and_persona(
        self, id_actividad: str, id_persona: str
    ) -> Optional[Participation]:
        """Recupera la participación exacta entre una actividad y una persona."""
        for p in self._participaciones.values():
            if p.id_actividad == id_actividad and p.id_persona == id_persona:
                return deepcopy(p)
        return None

    def list_by_matriz_destino(
        self, matriz_destino: str, id_actividad: Optional[str] = None
    ) -> List[Participation]:
        """Filtra participaciones según la matriz asignada previamente (sin inferir routing)."""
        matriz_buscada = matriz_destino.strip().upper()
        resultados = []
        for p in self._participaciones.values():
            p_matriz = self._matriz_map.get(p.id_participacion) or getattr(p, "matriz_destino", None)
            if p_matriz and str(p_matriz).strip().upper() == matriz_buscada:
                if id_actividad is None or p.id_actividad == id_actividad:
                    resultados.append(deepcopy(p))
        return resultados

    def list_requieren_revision(
        self, id_actividad: Optional[str] = None
    ) -> List[Participation]:
        """Recupera participaciones con bandera de revisión activa."""
        resultados = []
        for p in self._participaciones.values():
            if p.requiere_revision:
                if id_actividad is None or p.id_actividad == id_actividad:
                    resultados.append(deepcopy(p))
        return resultados

    def count_by_actividad(self, id_actividad: str) -> int:
        """Retorna el conteo total de participaciones para una actividad."""
        return sum(1 for p in self._participaciones.values() if p.id_actividad == id_actividad)
