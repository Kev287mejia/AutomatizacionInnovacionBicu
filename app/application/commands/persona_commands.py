"""Commands para el contexto de Personas e Identidades - Sistema BICU.

Representa intenciones de incorporación o actualización bio-demográfica.
Consagra la regla RN-C04 (cédula nullable y no invención).
"""

from datetime import date
from typing import Optional, Union
from pydantic import BaseModel, Field


class RegistrarPersonaCommand(BaseModel):
    """Comando de intención para incorporar un individuo al SSOT bio-demográfico."""

    nombre_completo: str = Field(
        ...,
        description="Nombre completo tal como figura en la fuente de origen."
    )
    nombres: Optional[str] = Field(
        default=None,
        description="Nombres de pila si están desglosados."
    )
    apellidos: Optional[str] = Field(
        default=None,
        description="Apellidos del participante."
    )
    cedula: Optional[str] = Field(
        default=None,
        description="Cédula oficial (nullable; si no existe, permanece estrictamente en None)."
    )
    numero_unico: Optional[str] = Field(
        default=None,
        description="Carné institucional o número de empleado."
    )
    otro_id_institucional: Optional[str] = Field(
        default=None,
        description="Identificador secundario oficial."
    )
    sexo_original: Optional[str] = Field(
        default=None,
        description="Dato de sexo extraído de la fuente."
    )
    sexo_fuente: Optional[str] = Field(
        default=None,
        description="Identificador de la fuente origen del dato de sexo."
    )
    sexo_normalizado: Optional[str] = Field(
        default=None,
        description="Sexo estandarizado (ej. MASCULINO, FEMENINO)."
    )
    fecha_nacimiento: Optional[Union[date, str]] = Field(
        default=None,
        description="Fecha de nacimiento si está disponible."
    )
    edad: Optional[int] = Field(
        default=None,
        ge=0,
        le=125,
        description="Edad en años."
    )
    etnia: Optional[str] = Field(
        default=None,
        description="Pueblo originario o pertenencia étnica."
    )
    telefono: Optional[str] = Field(
        default=None,
        description="Número de contacto."
    )
    departamento_persona: Optional[str] = Field(
        default=None,
        description="Departamento de origen o residencia."
    )
    municipio_persona: Optional[str] = Field(
        default=None,
        description="Municipio de origen o residencia."
    )
    discapacidad: Optional[str] = Field(
        default=None,
        description="Condición de discapacidad declarada."
    )
    carrera_original: Optional[str] = Field(
        default=None,
        description="Carrera tal como figura en la lista de origen."
    )
    fuente_origen: Optional[str] = Field(
        default=None,
        description="Documento o lista de donde se extrajo el registro."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
