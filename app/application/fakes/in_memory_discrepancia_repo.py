"""Implementación Fake en memoria de IDiscrepanciaRepository para pruebas de Application.

Consagra el principio pericial DETECTAR ≠ CORREGIR (RN-C07):
- Almacena discrepancias sin alterar valores fuente.
- registrar_revision() asienta la justificación pericial sin corregir ni mutar Fuente A/B.
- No implementa lógica de corrección automática.
"""

from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional

from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.models.discrepancy import Discrepancia, EstadoDiscrepancia
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository


class InMemoryDiscrepanciaRepository(IDiscrepanciaRepository):
    """Repositorio fake en memoria para el agregado Discrepancia."""

    def __init__(self, datos_iniciales: Optional[Dict[str, Discrepancia]] = None) -> None:
        self._discrepancias: Dict[str, Discrepancia] = deepcopy(datos_iniciales) if datos_iniciales else {}

    def save(self, discrepancia: Discrepancia) -> None:
        """Inserta o actualiza una discrepancia en memoria."""
        self._discrepancias[discrepancia.id_discrepancia] = deepcopy(discrepancia)

    def save_batch(self, discrepancias: List[Discrepancia]) -> None:
        """Inserta o actualiza un lote de discrepancias."""
        for d in discrepancias:
            self.save(d)

    def get_by_id(self, id_discrepancia: str) -> Optional[Discrepancia]:
        """Recupera una discrepancia por su UUID."""
        d = self._discrepancias.get(id_discrepancia)
        return deepcopy(d) if d is not None else None

    def list_by_actividad(self, id_actividad: str) -> List[Discrepancia]:
        """Recupera discrepancias registradas en una actividad."""
        return [
            deepcopy(d) for d in self._discrepancias.values()
            if d.id_actividad == id_actividad
        ]

    def list_pendientes(
        self, severidad: Optional[str] = None
    ) -> List[Discrepancia]:
        """Recupera discrepancias activas pendientes de revisión humana."""
        estados_pendientes = {
            EstadoDiscrepancia.REQUIERE_REVISION.value,
            EstadoDiscrepancia.EN_REVISION.value,
            "REQUIERE_REVISION",
            "EN_REVISION",
        }
        sev_buscada = severidad.strip().upper() if severidad else None

        resultados = []
        for d in self._discrepancias.values():
            estado_val = d.estado.value if hasattr(d.estado, "value") else str(d.estado)
            if estado_val in estados_pendientes:
                if sev_buscada is None:
                    resultados.append(deepcopy(d))
                else:
                    sev_val = d.severidad.value if hasattr(d.severidad, "value") else str(d.severidad)
                    if sev_val == sev_buscada:
                        resultados.append(deepcopy(d))
        return resultados

    def registrar_revision(
        self,
        id_discrepancia: str,
        nuevo_estado: str,
        justificacion: str,
        usuario_revisor: str,
    ) -> None:
        """Asienta la resolución o aclaración humana de la discrepancia.

        Preserva rigurosamente intactos los valores de fuente_a_valor, fuente_b_valor y delta_valor.
        """
        discrepancia = self._discrepancias.get(id_discrepancia)
        if discrepancia is None:
            raise EntityNotFoundError("Discrepancia", id_discrepancia)

        # Asignar campos de revisión sin alterar fuentes originales
        discrepancia.estado = EstadoDiscrepancia(nuevo_estado) if nuevo_estado in EstadoDiscrepancia.__members__ else nuevo_estado  # type: ignore
        discrepancia.justificacion_aclaratoria = justificacion
        discrepancia.usuario_revisor = usuario_revisor
        discrepancia.fecha_revision = datetime.now().isoformat()
