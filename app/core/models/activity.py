"""
app.core.models.activity

Modelo interno de Actividad (Activity).
Representa una actividad o evento institucional de Vinculación / Innovación y Emprendimiento.

Reglas institucionales:
- C-06: El consolidado tiene UNA FILA POR ACTIVIDAD.
- C-13: El id_actividad es generado internamente por el sistema (UUID).
        El nombre textual de la actividad NO es el identificador único.
- C-15: Si un dato no existe en la fuente, se conserva como None (Regla de no invención).
"""

from datetime import date
from typing import Optional, Union
import uuid
from pydantic import BaseModel, Field, field_validator


class Activity(BaseModel):
    """
    Modelo representativo de una Actividad o Evento.
    Fuente única de verdad (SSOT) para los datos a nivel de actividad.
    """
    id_actividad: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único interno generado automáticamente por el sistema."
    )
    nombre_actividad_original: str = Field(
        ...,
        description="Nombre textual extraído directamente de la fuente de origen sin alteraciones."
    )
    nombre_actividad_oficial: Optional[str] = Field(
        default=None,
        description="Nombre estandarizado u oficial tras normalización o confirmación del usuario."
    )
    fecha_evento: Optional[Union[date, str]] = Field(
        default=None,
        description="Fecha en que se realizó la actividad o evento."
    )
    sede: Optional[str] = Field(
        default=None,
        description="Sede, recinto o campus institucional donde se desarrolló la actividad."
    )
    departamento: Optional[str] = Field(
        default=None,
        description="Departamento geográfico donde tuvo lugar la actividad."
    )
    municipio_evento: Optional[str] = Field(
        default=None,
        description="Municipio específico donde se realizó el evento."
    )
    programa: Optional[str] = Field(
        default=None,
        description="Programa institucional responsable o asociado a la actividad."
    )
    ambito: Optional[str] = Field(
        default=None,
        description="Ámbito de la actividad (ej. Nacional, Local, etc.)."
    )
    tipo_evento: Optional[str] = Field(
        default=None,
        description="Tipo de evento (Taller, Conferencia, Hackatón, etc.)."
    )
    eje_linea_estrategica: Optional[str] = Field(
        default=None,
        description="Eje o línea estratégica institucional a la que tributa la actividad."
    )
    informacion_adicional: Optional[str] = Field(
        default=None,
        description="Observaciones, notas o detalles complementarios de la actividad."
    )
    fuente_origen: Optional[str] = Field(
        default=None,
        description="Nombre o ruta del archivo de donde fue extraída la información de la actividad."
    )

    @field_validator("nombre_actividad_original")
    @classmethod
    def validar_nombre_no_vacio(cls, valor: str) -> str:
        """Asegura que el nombre original de la actividad no sea una cadena vacía."""
        if not valor or not valor.strip():
            raise ValueError("El nombre de la actividad original no puede estar vacío.")
        return valor.strip()

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }
