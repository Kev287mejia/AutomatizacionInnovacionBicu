"""app.core.models.discrepancy

Modelo interno de Discrepancia (Discrepancy) institucional.
Gobernado bajo el principio inviolable DETECTAR ≠ CORREGIR (Regla RN-C07).

Conserva intactos los valores de fuentes divergentes, exponiendo formalmente
el delta numérico o discrepancia cualitativa para resolución humana auditada.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional, Union
import uuid
from pydantic import BaseModel, Field


class TipoDiscrepancia(str, Enum):
    """Tipos de discrepancias detectables entre fuentes institucionales."""
    PLAN_VS_REAL = "PLAN_VS_REAL"
    RESUMEN_VS_NOMINAL = "RESUMEN_VS_NOMINAL"
    M1_VS_NOMINALES = "M1_VS_NOMINALES"
    FECHA_DISCORDANTE = "FECHA_DISCORDANTE"
    OTRO = "OTRO"


class SeveridadDiscrepancia(str, Enum):
    """Nivel de severidad técnica e institucional del hallazgo."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class EstadoDiscrepancia(str, Enum):
    """Estados del ciclo de vida pericial de una discrepancia."""
    REQUIERE_REVISION = "REQUIERE_REVISION"
    EN_REVISION = "EN_REVISION"
    ACLARADO = "ACLARADO"
    CONCORDANTE = "CONCORDANTE"


class Discrepancia(BaseModel):
    """Modelo representativo de una divergencia detectada entre fuentes institucionales."""

    id_discrepancia: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único generado automáticamente (UUIDv4)."
    )
    id_actividad: str = Field(
        ...,
        description="Identificador de la actividad donde se detectó la discrepancia."
    )
    tipo_discrepancia: TipoDiscrepancia = Field(
        default=TipoDiscrepancia.PLAN_VS_REAL,
        description="Categoría estructural del hallazgo."
    )
    severidad: SeveridadDiscrepancia = Field(
        default=SeveridadDiscrepancia.WARNING,
        description="Nivel de impacto técnico."
    )
    fuente_a_nombre: str = Field(
        ...,
        description="Nombre descriptivo de la Fuente A (ej. 'Planificacion.meta_participantes')."
    )
    fuente_a_valor: str = Field(
        ...,
        description="Valor literal asentado en la Fuente A."
    )
    fuente_b_nombre: str = Field(
        ...,
        description="Nombre descriptivo de la Fuente B (ej. 'Asistencias.total_presentes')."
    )
    fuente_b_valor: str = Field(
        ...,
        description="Valor literal asentado en la Fuente B."
    )
    delta_valor: Optional[str] = Field(
        default=None,
        description="Diferencia matemática o explicación de divergencia cualitativa."
    )
    estado: EstadoDiscrepancia = Field(
        default=EstadoDiscrepancia.REQUIERE_REVISION,
        description="Estado actual del hallazgo en la bandeja de auditoría."
    )
    justificacion_aclaratoria: Optional[str] = Field(
        default=None,
        description="Nota humana aclaratoria sin mutar los valores originales."
    )
    usuario_revisor: Optional[str] = Field(
        default=None,
        description="Identificador del funcionario que revisó o aclaró la discrepancia."
    )
    fecha_deteccion: Union[datetime, date, str] = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Sello temporal de detección automática."
    )
    fecha_revision: Optional[Union[datetime, date, str]] = Field(
        default=None,
        description="Sello temporal de resolución o aclaración humana."
    )

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }
