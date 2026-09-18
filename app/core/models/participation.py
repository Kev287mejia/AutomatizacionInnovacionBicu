"""
app.core.models.participation

Modelo interno de Participación (Participation).
Representa el vínculo entre una Persona (Person) y una Actividad (Activity).

Reglas institucionales:
- C-03: El routing a las matrices depende de la 'categoria_participacion'
        registrada para ESTA participación, NO de la profesión o rol histórico de la persona.
- C-10: Cada participación es una asistencia registrada que SE CONSERVA siempre.
- C-11: Una misma persona puede participar válidamente en múltiples actividades.
"""

from typing import Optional, Union
import uuid
from pydantic import BaseModel, Field, field_validator
from app.core.constants.participant_types import CategoriaParticipacion, NivelConfianzaIdentidad


class Participation(BaseModel):
    """
    Modelo de Participación / Asistencia.
    Núcleo del routing hacia las 5 matrices oficiales.
    """
    id_participacion: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único de la asistencia/participación generado automáticamente."
    )
    id_actividad: str = Field(
        ...,
        description="Identificador de la actividad en la que se participó (FK a Activity)."
    )
    id_persona: str = Field(
        ...,
        description="Identificador de la persona participante (FK a Person)."
    )
    categoria_participacion: Union[CategoriaParticipacion, str] = Field(
        ...,
        description="Categoría del protagonista para ESTA actividad (ESTUDIANTE, DOCENTE, BENEFICIADO, etc.)."
    )
    nivel_confianza_identidad: int = Field(
        default=NivelConfianzaIdentidad.NIVEL_1_CEDULA.value,
        description="Nivel de certeza de la identidad (1: Cédula, 2: Carné, 3: Otro ID, 4: Candidato)."
    )
    fuente_origen: Optional[str] = Field(
        default=None,
        description="Archivo o lista de asistencia origen de este registro."
    )
    observaciones: Optional[str] = Field(
        default=None,
        description="Notas adicionales registradas en la lista de asistencia."
    )
    requiere_revision: bool = Field(
        default=False,
        description="Indica si esta participación tiene datos dudosos que requieren confirmación humana."
    )
    motivo_revision: Optional[str] = Field(
        default=None,
        description="Explicación detallada del porqué requiere revisión humana."
    )

    es_beneficiado_rol: bool = Field(
        default=False,
        description="Indica si el participante actúa contextualmente como beneficiario directo."
    )
    matriz_destino: Optional[str] = Field(
        default=None,
        description="Código de matriz institucional asignado tras el routing (M2..M5, COLA_REVISION) o None pre-routing."
    )

    @field_validator("categoria_participacion")
    @classmethod
    def normalizar_categoria(cls, valor: Union[CategoriaParticipacion, str]) -> CategoriaParticipacion:
        """Convierte y valida strings a la enumeración oficial CategoriaParticipacion."""
        if isinstance(valor, CategoriaParticipacion):
            return valor
        if isinstance(valor, str):
            limpio = valor.strip().upper()
            if limpio in ("BENEFICIARIO", "PROTAGONISTA", "COMUNIDAD", "EMPRENDEDOR"):
                return CategoriaParticipacion.BENEFICIADO
            try:
                return CategoriaParticipacion(limpio)
            except ValueError:
                return CategoriaParticipacion.DESCONOCIDO
        return CategoriaParticipacion.DESCONOCIDO

    @field_validator("nivel_confianza_identidad")
    @classmethod
    def validar_nivel_confianza(cls, valor: int) -> int:
        """Asegura que el nivel de confianza esté entre 1 y 4."""
        if valor not in (1, 2, 3, 4):
            raise ValueError(f"Nivel de confianza inválido: {valor}. Debe ser 1, 2, 3 o 4.")
        return valor

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }
