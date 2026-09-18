"""
app.core.models.validation_result

Modelo interno para registrar hallazgos de validación y auditoría (ValidationResult).
Soporta los 4 niveles del sistema: ERROR, WARNING, INFO, REVISION.
"""

from datetime import datetime
from typing import Optional, Union
import uuid
from pydantic import BaseModel, Field, field_validator
from app.core.constants.participant_types import NivelValidacion


class ValidationResult(BaseModel):
    """
    Representa una advertencia, error o información de auditoría
    detectada durante cualquier fase del procesamiento.
    """
    id_resultado: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único del resultado de validación."
    )
    id_referencia: Optional[str] = Field(
        default=None,
        description="ID del objeto evaluado (id_actividad, id_persona o id_participacion)."
    )
    nivel: Union[NivelValidacion, str] = Field(
        ...,
        description="Nivel de severidad del hallazgo: ERROR, WARNING, INFO o REVISION."
    )
    codigo: str = Field(
        ...,
        description="Código estandarizado del hallazgo (ej: VAL_CEDULA_VACIA, ROUTING_DESCONOCIDO)."
    )
    mensaje: str = Field(
        ...,
        description="Descripción clara y legible para el usuario o revisor del problema detectado."
    )
    fuente_origen: Optional[str] = Field(
        default=None,
        description="Nombre del archivo o lista donde se originó el dato evaluado."
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Momento exacto en que se generó la validación."
    )

    @field_validator("nivel")
    @classmethod
    def normalizar_nivel(cls, valor: Union[NivelValidacion, str]) -> NivelValidacion:
        """Convierte y valida a la enumeración NivelValidacion."""
        if isinstance(valor, NivelValidacion):
            return valor
        if isinstance(valor, str):
            limpio = valor.strip().upper()
            try:
                return NivelValidacion(limpio)
            except ValueError:
                raise ValueError(
                    f"Nivel de validación '{valor}' inválido. "
                    f"Opciones válidas: {[e.value for e in NivelValidacion]}"
                )
        raise ValueError("El nivel de validación es obligatorio.")

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }
