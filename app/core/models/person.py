"""
app.core.models.person

Modelo interno de Persona (Person).
Representa a cualquier individuo que participa en las actividades institucionales.

Reglas institucionales:
- C-08: Mapeo de sexo específico por fuente (sexo_original, sexo_fuente, sexo_normalizado).
- C-09: Jerarquía de identidad de 4 niveles (cédula, número único, otro ID, candidato).
- C-10: Regla de no invención: Si un dato no existe, se mantiene en None.
- C-12: Carreras divididas en tres niveles (carrera_original, carrera_normalizada, carrera_oficial).
"""

from datetime import date
from typing import Optional, Union
import uuid
from pydantic import BaseModel, Field, field_validator


class Person(BaseModel):
    """
    Modelo de Persona. Fuente única de verdad para datos personales de protagonistas.
    """
    id_persona_interno: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único generado internamente por el sistema."
    )
    nombre_completo: str = Field(
        ...,
        description="Nombre completo del participante tal como figura en la fuente o unificado."
    )
    nombres: Optional[str] = Field(
        default=None,
        description="Primer y segundo nombre del participante."
    )
    apellidos: Optional[str] = Field(
        default=None,
        description="Apellidos del participante."
    )
    # Jerarquía de identificación (Regla C-09)
    cedula: Optional[str] = Field(
        default=None,
        description="Cédula oficial de identidad (Nivel 1 de confianza)."
    )
    numero_unico: Optional[str] = Field(
        default=None,
        description="Número de carné o número único institucional (Nivel 2 de confianza)."
    )
    otro_id_institucional: Optional[str] = Field(
        default=None,
        description="Otro identificador oficial institucional verificado (Nivel 3 de confianza)."
    )
    # Sexo por fuente (Regla C-08)
    sexo_original: Optional[str] = Field(
        default=None,
        description="Valor textual de sexo extraído directamente de la fuente (sin alterar)."
    )
    sexo_fuente: Optional[str] = Field(
        default=None,
        description="Identificador de la fuente de donde se extrajo el dato de sexo."
    )
    sexo_normalizado: Optional[str] = Field(
        default=None,
        description="Sexo normalizado (ej. MASCULINO, FEMENINO) según el catálogo de esa fuente."
    )
    # Fechas y demografía
    fecha_nacimiento: Optional[Union[date, str]] = Field(
        default=None,
        description="Fecha de nacimiento (solo si la fuente la proporciona explícitamente)."
    )
    edad: Optional[int] = Field(
        default=None,
        description="Edad en años cumplidos."
    )
    etnia: Optional[str] = Field(
        default=None,
        description="Pertenencia étnica o pueblo originario declarado."
    )
    telefono: Optional[str] = Field(
        default=None,
        description="Número de teléfono o celular de contacto."
    )
    departamento_persona: Optional[str] = Field(
        default=None,
        description="Departamento de residencia u origen del participante."
    )
    municipio_persona: Optional[str] = Field(
        default=None,
        description="Municipio de residencia u origen del participante."
    )
    discapacidad: Optional[str] = Field(
        default=None,
        description="Condición de discapacidad reportada."
    )
    # Carreras (Regla C-12)
    carrera_original: Optional[str] = Field(
        default=None,
        description="Nombre de la carrera exacto tal como figura en la lista de origen."
    )
    carrera_normalizada: Optional[str] = Field(
        default=None,
        description="Nombre de carrera con limpieza básica de formato."
    )
    carrera_oficial: Optional[str] = Field(
        default=None,
        description="Nombre estandarizado correspondiente al catálogo oficial institucional."
    )
    fuente_origen: Optional[str] = Field(
        default=None,
        description="Documento o lista de donde se extrajo el registro."
    )

    @field_validator("nombre_completo")
    @classmethod
    def validar_nombre_no_vacio(cls, valor: str) -> str:
        """Asegura que el nombre completo de la persona no sea una cadena vacía."""
        if not valor or not valor.strip():
            raise ValueError("El nombre completo de la persona no puede estar vacío.")
        return valor.strip()

    @field_validator("edad")
    @classmethod
    def validar_edad_rango(cls, valor: Optional[int]) -> Optional[int]:
        """Si se proporciona edad, valida que sea un número razonable."""
        if valor is not None and (valor < 0 or valor > 125):
            raise ValueError(f"Edad fuera de rango biológico plausible: {valor}")
        return valor

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }
