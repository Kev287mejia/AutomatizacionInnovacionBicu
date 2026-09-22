"""app.review.application.dto

Data Transfer Objects (DTO) inmutables para desacoplar el dominio y la persistencia
de la capa de presentación / UI de la Cola de Revisión.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ReviewCaseSummaryDTO:
    """Resumen de un caso de revisión para visualización en bandeja operativa."""

    id_caso: str
    id_actividad: str
    nombre_actividad: str
    id_persona: str
    nombre_persona: str
    estamento_actual: str
    tipo_caso: str
    motivo_revision: str
    estado: str
    cedula_persona: Optional[str] = None
    archivo_fuente: Optional[str] = None
    fecha_deteccion: Optional[str] = None


@dataclass(frozen=True)
class CandidateMatchDTO:
    """Candidato sugerido para resolución de identidad (EVIDENCIA ≠ SUPOSICIÓN)."""

    id_persona: str
    nombre_completo: str
    cedula: Optional[str]
    estamento_principal: str
    confianza: float
    criterio_coincidencia: str


@dataclass(frozen=True)
class ReviewCaseDetailDTO:
    """Detalle pericial exhaustivo de un caso de revisión con evidencia contextual."""

    id_caso: str
    id_actividad: str
    nombre_actividad: str
    id_persona: str
    nombre_persona: str
    estamento_actual: str
    tipo_caso: str
    motivo_revision: str
    estado: str
    cedula_persona: Optional[str] = None
    sexo_persona: Optional[str] = None
    carrera_o_cargo: Optional[str] = None
    entidad_externa: Optional[str] = None
    archivo_fuente: Optional[str] = None
    fila_fuente: Optional[int] = None
    fecha_actividad: Optional[str] = None
    lugar_actividad: Optional[str] = None
    usuario_resolutor: Optional[str] = None
    fecha_resolucion: Optional[str] = None
    observaciones: Optional[str] = None
    candidatos_sugeridos: List[CandidateMatchDTO] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewResolutionResultDTO:
    """Resultado formal de la resolución transaccional de un caso."""

    id_caso: str
    exito: bool
    mensaje: str
    nuevo_estado: str
    matriz_destino: Optional[str] = None
    id_auditoria: Optional[str] = None


@dataclass(frozen=True)
class ReviewHistoryItemDTO:
    """Registro inmutable de auditoría forense para el historial de decisiones periciales."""

    id_auditoria: str
    fecha_hora: str
    usuario_operador: str
    id_registro_afectado: str
    motivo_modificacion: str
    cambios_resumen: str
    snapshot_previo: Dict[str, Any] = field(default_factory=dict)
    snapshot_nuevo: Dict[str, Any] = field(default_factory=dict)
