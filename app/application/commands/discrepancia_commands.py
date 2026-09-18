"""Commands para el contexto de Calidad, Auditoría y Discrepancias - Sistema BICU.

Consagran el principio pericial DETECTAR ≠ CORREGIR (Regla RN-C07).
Las intenciones registran o aclaran hallazgos sin mutar los datos fuente originales.
"""

from typing import Optional, Union
from pydantic import BaseModel, Field

from app.core.models.discrepancy import (
    TipoDiscrepancia,
    SeveridadDiscrepancia,
    EstadoDiscrepancia,
)


class RegistrarDiscrepanciaCommand(BaseModel):
    """Comando de intención para asentar una divergencia detectada entre fuentes institucionales."""

    id_actividad: str = Field(
        ...,
        description="UUID de la actividad asociada al hallazgo."
    )
    tipo_discrepancia: Union[TipoDiscrepancia, str] = Field(
        default=TipoDiscrepancia.PLAN_VS_REAL,
        description="Categoría estructural de la discrepancia."
    )
    severidad: Union[SeveridadDiscrepancia, str] = Field(
        default=SeveridadDiscrepancia.WARNING,
        description="Severidad técnica (INFO, WARNING, ERROR)."
    )
    fuente_a_nombre: str = Field(
        ...,
        description="Denominación de la Fuente A (ej. 'Planificacion.meta_participantes')."
    )
    fuente_a_valor: str = Field(
        ...,
        description="Valor literal extraído de la Fuente A."
    )
    fuente_b_nombre: str = Field(
        ...,
        description="Denominación de la Fuente B (ej. 'Asistencias.total_presentes')."
    )
    fuente_b_valor: str = Field(
        ...,
        description="Valor literal extraído de la Fuente B."
    )
    delta_valor: Optional[str] = Field(
        default=None,
        description="Diferencia matemática o explicación de la contradicción."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ResolverRevisionDiscrepanciaCommand(BaseModel):
    """Comando de intención para asentar la justificación pericial de revisión humana."""

    id_discrepancia: str = Field(
        ...,
        description="UUID de la discrepancia en revisión."
    )
    nuevo_estado: Union[EstadoDiscrepancia, str] = Field(
        default=EstadoDiscrepancia.ACLARADO,
        description="Nuevo estado pericial asignado (ej. 'ACLARADO', 'CONCORDANTE')."
    )
    justificacion_aclaratoria: str = Field(
        ...,
        min_length=1,
        description="Justificación detallada del auditor (obligatoria)."
    )
    usuario_revisor: str = Field(
        ...,
        min_length=1,
        description="Identificador del funcionario responsable de la resolución."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
