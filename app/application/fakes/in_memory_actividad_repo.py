"""Implementación Fake en memoria de IActividadRepository para pruebas de Application.

Almacena entidades en memoria sin dependencias de base de datos física ni SQLite.
"""

from copy import deepcopy
from datetime import date
from typing import Dict, List, Optional, Union

from app.core.models.activity import Activity
from app.core.ports.actividad_repository import IActividadRepository


class InMemoryActividadRepository(IActividadRepository):
    """Repositorio fake en memoria para el agregado Actividad."""

    def __init__(self, datos_iniciales: Optional[Dict[str, Activity]] = None) -> None:
        self._actividades: Dict[str, Activity] = deepcopy(datos_iniciales) if datos_iniciales else {}

    def save(self, actividad: Activity) -> None:
        """Inserta o actualiza una actividad en memoria."""
        self._actividades[actividad.id_actividad] = deepcopy(actividad)

    def get_by_id(self, id_actividad: str) -> Optional[Activity]:
        """Recupera una actividad por su UUID."""
        actividad = self._actividades.get(id_actividad)
        return deepcopy(actividad) if actividad is not None else None

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
                # Si no tiene fecha, solo se incluye si no hay filtro estricto o no aplica
                pass
        return resultados

    def count(self) -> int:
        """Retorna la cantidad total de actividades almacenadas."""
        return len(self._actividades)
