"""Implementación Fake en memoria de IEvidenciaRepository para pruebas de Application.

Almacena metadatos de evidencias y relaciones N:M con actividades en memoria.
"""

from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from app.core.models.evidence import Evidencia
from app.core.ports.evidencia_repository import IEvidenciaRepository


class InMemoryEvidenciaRepository(IEvidenciaRepository):
    """Repositorio fake en memoria para el agregado Evidencia."""

    def __init__(self, datos_iniciales: Optional[Dict[str, Evidencia]] = None) -> None:
        self._evidencias: Dict[str, Evidencia] = deepcopy(datos_iniciales) if datos_iniciales else {}
        # Lista de vínculos: cada elemento es un dict con id_actividad, id_evidencia, orden, seccion
        self._vinculos: List[Dict[str, object]] = []

    def save(self, evidencia: Evidencia) -> None:
        """Inserta o actualiza una evidencia en memoria."""
        self._evidencias[evidencia.id_evidencia] = deepcopy(evidencia)

    def get_by_id(self, id_evidencia: str) -> Optional[Evidencia]:
        """Recupera una evidencia por su UUID."""
        evi = self._evidencias.get(id_evidencia)
        return deepcopy(evi) if evi is not None else None

    def get_by_hash(self, hash_sha256: str) -> Optional[Evidencia]:
        """Recupera una evidencia por su hash SHA-256."""
        if not hash_sha256 or not hash_sha256.strip():
            return None
        h_buscado = hash_sha256.strip().lower()
        for evi in self._evidencias.values():
            if evi.hash_sha256 and evi.hash_sha256.strip().lower() == h_buscado:
                return deepcopy(evi)
        return None

    def link_actividad(
        self,
        id_actividad: str,
        id_evidencia: str,
        orden: int = 1,
        seccion: str = "GALERIA",
    ) -> None:
        """Asocia una evidencia a una actividad (actualiza orden/sección si ya existe)."""
        for v in self._vinculos:
            if v["id_actividad"] == id_actividad and v["id_evidencia"] == id_evidencia:
                v["orden"] = orden
                v["seccion"] = seccion
                return

        self._vinculos.append({
            "id_actividad": id_actividad,
            "id_evidencia": id_evidencia,
            "orden": orden,
            "seccion": seccion,
        })

    def unlink_actividad(self, id_actividad: str, id_evidencia: str) -> None:
        """Desvincula una evidencia de una actividad."""
        self._vinculos = [
            v for v in self._vinculos
            if not (v["id_actividad"] == id_actividad and v["id_evidencia"] == id_evidencia)
        ]

    def get_by_actividad(
        self, id_actividad: str
    ) -> List[Tuple[Evidencia, int, str]]:
        """Recupera la lista de (Evidencia, orden, seccion) vinculadas a una actividad."""
        vinculos_act = [
            v for v in self._vinculos if v["id_actividad"] == id_actividad
        ]
        # Ordenar por orden_presentacion ascendente
        vinculos_act.sort(key=lambda x: int(x["orden"]))

        resultados: List[Tuple[Evidencia, int, str]] = []
        for v in vinculos_act:
            evi = self._evidencias.get(str(v["id_evidencia"]))
            if evi is not None:
                resultados.append((deepcopy(evi), int(v["orden"]), str(v["seccion"])))

        return resultados
