"""app.review.domain.enums

Enumeraciones oficiales y catálogo cerrado del dominio de Cola de Revisión.
Gobernado bajo el principio inviolable DETECTAR ≠ CORREGIR y EVIDENCIA ≠ SUPOSICIÓN.
"""

from enum import Enum


class ReviewCaseStatus(str, Enum):
    """Estados del ciclo de vida de un caso de revisión institucional."""

    PENDIENTE = "PENDIENTE"
    EN_REVISION = "EN_REVISION"
    RESUELTO = "RESUELTO"
    NO_RESOLUBLE = "NO_RESOLUBLE"


class ReviewCaseType(str, Enum):
    """Tipos de discrepancia deterministas identificados en el enrutamiento."""

    ESTAMENTO_NO_RESUELTO = "ESTAMENTO_NO_RESUELTO"
    IDENTIDAD_NO_RESUELTA = "IDENTIDAD_NO_RESUELTA"
    CONFLICTO_CEDULA = "CONFLICTO_CEDULA"
    DATOS_INCONSISTENTES = "DATOS_INCONSISTENTES"


class ReviewDecisionType(str, Enum):
    """Decisiones explícitas autorizadas para el operador humano."""

    CONFIRMAR_ESTAMENTO = "CONFIRMAR_ESTAMENTO"
    CONFIRMAR_IDENTIDAD = "CONFIRMAR_IDENTIDAD"
    MARCAR_NO_RESOLUBLE = "MARCAR_NO_RESOLUBLE"


class EstamentoInstitucional(str, Enum):
    """Catálogo cerrado institucional y su enrutamiento unívoco a matrices oficiales.

    Mapeo institucional estricto:
    - ESTUDIANTE     -> M2
    - DOCENTE        -> M3
    - ADMINISTRATIVO -> M3
    - COLABORADOR    -> M4
    - BENEFICIADO    -> M5
    """

    ESTUDIANTE = "ESTUDIANTE"
    DOCENTE = "DOCENTE"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    COLABORADOR = "COLABORADOR"
    BENEFICIADO = "BENEFICIADO"

    @property
    def matriz_destino(self) -> str:
        """Determina la matriz oficial correspondiente según el catálogo BICU."""
        mapping = {
            EstamentoInstitucional.ESTUDIANTE: "M2",
            EstamentoInstitucional.DOCENTE: "M3",
            EstamentoInstitucional.ADMINISTRATIVO: "M3",
            EstamentoInstitucional.COLABORADOR: "M4",
            EstamentoInstitucional.BENEFICIADO: "M5",
        }
        return mapping[self]
