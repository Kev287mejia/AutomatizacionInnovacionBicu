"""Anti-Corruption Layer (ACL) para el Bounded Context de Routing - Sistema BICU.

Traduce de manera bidireccional y controlada entre los conceptos puros del dominio
de routing (MatrizDestino) y los códigos relacionales de persistencia en SQLite
(participacion.matriz_destino).

Reglas institucionales de diseño:
- R-ACL-01: Mapeo estricto de matrices nominales de participantes (M2, M3, M4, M5).
- R-ACL-02: Mapeo de cubeta de control COLA_REVISION.
- R-ACL-03: BLOQUEADOS no posee código relacional; se traduce a None y se acompaña
            de estado_operativo='BLOQUEADO'.
- R-ACL-04: M1 (CONSOLIDADO) queda formalmente EXCLUIDO de este ACL, ya que representa
            una agregación a nivel de Actividad y no un destino nominal de participantes.
"""

from typing import Optional, Union
from app.routing.enums import MatrizDestino
from app.routing.models import EnrutamientoRegistro


class RoutingACL:
    """Traductor entre el dominio de Routing y la capa de Persistencia / Relacional."""

    # Mapeo oficial Domain -> Código SQLite
    _DOMAIN_TO_RELATIONAL = {
        MatrizDestino.ESTUDIANTES: "M2",
        MatrizDestino.ACADEMICOS_ADMINISTRATIVOS: "M3",
        MatrizDestino.COLABORADORES: "M4",
        MatrizDestino.BENEFICIADOS: "M5",
        MatrizDestino.COLA_REVISION: "COLA_REVISION",
    }

    # Mapeo inverso Código SQLite -> Domain
    _RELATIONAL_TO_DOMAIN = {
        "M2": MatrizDestino.ESTUDIANTES,
        "M3": MatrizDestino.ACADEMICOS_ADMINISTRATIVOS,
        "M4": MatrizDestino.COLABORADORES,
        "M5": MatrizDestino.BENEFICIADOS,
        "COLA_REVISION": MatrizDestino.COLA_REVISION,
    }

    # Catálogo explícito de códigos relacionales válidos en participacion.matriz_destino
    VALID_RELATIONAL_CODES = frozenset({"M2", "M3", "M4", "M5", "COLA_REVISION"})

    @classmethod
    def to_relational_code(cls, matriz_destino: Union[MatrizDestino, str]) -> Optional[str]:
        """Traduce una MatrizDestino de dominio al código de matriz persistible en SQLite.

        Args:
            matriz_destino: Enumeración o string del destino de dominio.

        Returns:
            Código 'M2', 'M3', 'M4', 'M5', 'COLA_REVISION' o None para BLOQUEADOS.

        Raises:
            ValueError: Si se intenta traducir M1/CONSOLIDADO o un destino no reconocido.
        """
        if isinstance(matriz_destino, str):
            norm = matriz_destino.strip().upper()
            if norm in ("CONSOLIDADO", "M1"):
                raise ValueError(
                    "M1 / CONSOLIDADO no es un destino de routing nominal de participantes "
                    "y está excluido de RoutingACL (Regla R-ACL-04)."
                )
            try:
                dest_enum = MatrizDestino(norm)
            except ValueError:
                # Si ya es un código relacional válido, retornarlo
                if norm in cls.VALID_RELATIONAL_CODES:
                    return norm
                raise ValueError(f"Destino de routing no reconocido o inválido: '{matriz_destino}'.")
        else:
            dest_enum = matriz_destino

        if dest_enum == MatrizDestino.CONSOLIDADO:
            raise ValueError(
                "CONSOLIDADO (M1) no es un destino de routing nominal de participantes "
                "y está excluido de RoutingACL (Regla R-ACL-04)."
            )

        if dest_enum == MatrizDestino.BLOQUEADOS:
            # BLOQUEADOS no tiene código relacional; se almacena None (NULL pre/post-routing para aislados)
            return None

        codigo = cls._DOMAIN_TO_RELATIONAL.get(dest_enum)
        if codigo is None:
            raise ValueError(f"No existe mapeo relacional para el destino de dominio: {dest_enum}.")
        return codigo

    @classmethod
    def to_persistence(cls, decision: EnrutamientoRegistro) -> Optional[str]:
        """Extrae el código relacional para persistencia a partir de una decisión de routing.

        Si la decisión corresponde a un registro BLOQUEADO, retorna None sin inventar código.
        """
        if decision.estado_operativo == "BLOQUEADO" or decision.matriz_destino == MatrizDestino.BLOQUEADOS:
            return None
        return cls.to_relational_code(decision.matriz_destino)

    @classmethod
    def to_domain(cls, relational_code: Optional[str]) -> Optional[MatrizDestino]:
        """Traduce un código relacional persistido en SQLite de vuelta al enum MatrizDestino.

        Args:
            relational_code: 'M2', 'M3', 'M4', 'M5', 'COLA_REVISION', o None (pre-routing / bloqueado).

        Returns:
            Instancia correspondiente de MatrizDestino, o None si el valor relacional es None/vacío.
        """
        if relational_code is None or not relational_code.strip():
            return None
        norm = relational_code.strip().upper()
        if norm in ("CONSOLIDADO", "M1"):
            raise ValueError(
                "M1 / CONSOLIDADO no es un destino de routing nominal de participantes (Regla R-ACL-04)."
            )
        dest = cls._RELATIONAL_TO_DOMAIN.get(norm)
        if dest is None:
            raise ValueError(f"Código relacional '{relational_code}' no pertenece al catálogo válido de routing.")
        return dest
