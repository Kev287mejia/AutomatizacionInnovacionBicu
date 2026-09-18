"""Implementación Fake en memoria de IInformeSemanalRepository para pruebas de Application.

Almacena informes semanales consolidados y sus secuencias de detalle en memoria.
"""

from copy import deepcopy
from typing import Dict, List, Optional

from app.core.models.weekly_report import DetalleInformeSemanal, InformeSemanal
from app.core.ports.informe_semanal_repository import IInformeSemanalRepository


class InMemoryInformeSemanalRepository(IInformeSemanalRepository):
    """Repositorio fake en memoria para el agregado Informe Semanal Consolidado."""

    def __init__(self, datos_iniciales: Optional[Dict[str, InformeSemanal]] = None) -> None:
        self._informes: Dict[str, InformeSemanal] = deepcopy(datos_iniciales) if datos_iniciales else {}
        self._detalles: Dict[str, List[DetalleInformeSemanal]] = {}

    def save(
        self,
        informe: InformeSemanal,
        detalles: Optional[List[DetalleInformeSemanal]] = None,
    ) -> None:
        """Inserta o actualiza un informe semanal y opcionalmente sus detalles."""
        self._informes[informe.id_informe_semanal] = deepcopy(informe)
        if detalles is not None:
            self._detalles[informe.id_informe_semanal] = deepcopy(detalles)
        elif informe.detalles is not None:
            self._detalles[informe.id_informe_semanal] = deepcopy(informe.detalles)

    def get_by_id(self, id_informe_semanal: str) -> Optional[InformeSemanal]:
        """Recupera un informe semanal por su UUID."""
        inf = self._informes.get(id_informe_semanal)
        if inf is None:
            return None
        res = deepcopy(inf)
        if id_informe_semanal in self._detalles:
            res.detalles = deepcopy(self._detalles[id_informe_semanal])
        return res

    def get_by_periodo(
        self, anio: int, mes: int, numero_semana: int, sede: str
    ) -> Optional[InformeSemanal]:
        """Recupera un informe semanal por año, mes, semana y sede exactos."""
        sede_buscada = sede.strip().upper()
        for inf in self._informes.values():
            if (
                inf.anio == anio
                and inf.mes == mes
                and inf.numero_semana == numero_semana
                and inf.sede_recinto.strip().upper() == sede_buscada
            ):
                return self.get_by_id(inf.id_informe_semanal)
        return None

    def list_all(self) -> List[InformeSemanal]:
        """Retorna todos los informes semanales registrados."""
        return [self.get_by_id(inf_id) for inf_id in self._informes]  # type: ignore

    def get_detalles(
        self, id_informe_semanal: str
    ) -> List[DetalleInformeSemanal]:
        """Recupera la secuencia de detalles ordenada por orden_secuencia."""
        detalles = self._detalles.get(id_informe_semanal, [])
        detalles_ordenados = sorted(detalles, key=lambda d: d.orden_secuencia)
        return deepcopy(detalles_ordenados)
