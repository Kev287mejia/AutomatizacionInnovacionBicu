"""Implementación Fake en memoria de IActividadRepository para pruebas de Application.

Almacena entidades en memoria sin dependencias de base de datos física ni SQLite.
"""

from copy import deepcopy
from datetime import date
from typing import Dict, List, Optional, Union

from app.core.models.activity import ActividadMetricaAgregada, Activity
from app.core.ports.actividad_repository import IActividadRepository


class InMemoryActividadRepository(IActividadRepository):
    """Repositorio fake en memoria para el agregado Actividad."""

    def __init__(self, datos_iniciales: Optional[Dict[str, Activity]] = None) -> None:
        self._actividades: Dict[str, Activity] = deepcopy(datos_iniciales) if datos_iniciales else {}
        self._metricas_agregadas: Dict[str, ActividadMetricaAgregada] = {}

    def save(self, actividad: Activity) -> None:
        """Inserta o actualiza una actividad en memoria."""
        self._actividades[actividad.id_actividad] = deepcopy(actividad)
        if actividad.metrica_agregada:
            self._metricas_agregadas[actividad.id_actividad] = deepcopy(actividad.metrica_agregada)

    def get_by_id(self, id_actividad: str) -> Optional[Activity]:
        """Recupera una actividad por su UUID."""
        actividad = self._actividades.get(id_actividad)
        if actividad is None:
            return None
        act = deepcopy(actividad)
        act.metrica_agregada = self.get_metrica_agregada(id_actividad)
        return act

    def get_by_hash(self, hash_sha256: str) -> Optional[Activity]:
        """Recupera una actividad por el hash SHA-256 de su documento Word fuente."""
        if not hash_sha256:
            return None
        h_norm = hash_sha256.strip().lower()
        for act in self._actividades.values():
            if act.hash_sha256 and act.hash_sha256.strip().lower() == h_norm:
                return self.get_by_id(act.id_actividad)
        return None

    def exists(self, id_actividad: str) -> bool:
        """Comprueba si existe la actividad con el ID provisto."""
        return id_actividad in self._actividades

    def list_by_periodo(
        self,
        fecha_inicio: Union[date, str],
        fecha_fin: Union[date, str],
        sede: Optional[str] = None,
    ) -> List[Activity]:
        """Consulta actividades dentro del rango de fechas provisto."""
        f_ini_str = str(fecha_inicio)
        f_fin_str = str(fecha_fin)

        resultados = []
        for act in self._actividades.values():
            if act.fecha_evento is not None:
                f_act_str = str(act.fecha_evento)
                if f_ini_str <= f_act_str <= f_fin_str:
                    if sede is None or (act.sede and act.sede.strip().upper() == sede.strip().upper()):
                        resultados.append(deepcopy(act))
            else:
                pass
        return resultados

    def count(self) -> int:
        """Retorna la cantidad total de actividades almacenadas."""
        return len(self._actividades)

    def save_metrica_agregada(self, metrica: ActividadMetricaAgregada) -> None:
        """Inserta o actualiza las métricas cuantitativas agregadas de Tabla 2."""
        self._metricas_agregadas[metrica.id_actividad] = deepcopy(metrica)

    def get_metrica_agregada(self, id_actividad: str) -> Optional[ActividadMetricaAgregada]:
        """Recupera las métricas cuantitativas agregadas de una actividad."""
        metrica = self._metricas_agregadas.get(id_actividad)
        return deepcopy(metrica) if metrica is not None else None

