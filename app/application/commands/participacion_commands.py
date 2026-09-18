"""Commands para el contexto de Participación e Ingesta - Sistema BICU.

Representan intenciones de asociar personas a actividades (asistencia individual)
o procesar masivamente listas externas de asistencia.
"""

from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.core.constants.participant_types import CategoriaParticipacion
from app.application.dto.input_dtos import FilaParticipanteIngestaDTO


class RegistrarParticipacionIndividualCommand(BaseModel):
    """Comando de intención para asentar la asistencia de una persona a una actividad."""

    id_actividad: str = Field(
        ...,
        description="UUID de la actividad institucional."
    )
    id_persona: str = Field(
        ...,
        description="UUID de la persona participante."
    )
    categoria_participacion: Union[CategoriaParticipacion, str] = Field(
        ...,
        description="Categoría o rol asumido en ESTA actividad (ESTUDIANTE, DOCENTE, BENEFICIADO, etc.)."
    )
    nivel_confianza_identidad: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Nivel de certeza de identidad (1: Cédula, 2: Carné, 3: Otro ID, 4: Candidato)."
    )
    fuente_origen: Optional[str] = Field(
        default=None,
        description="Documento o lista de asistencia origen."
    )
    observaciones: Optional[str] = Field(
        default=None,
        description="Notas complementarias de la participación."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class IngestarListaAsistenciaCommand(BaseModel):
    """Comando de intención para orquestar la ingesta en lote de una lista de asistencia externa."""

    id_actividad: str = Field(
        ...,
        description="UUID de la actividad receptora de las asistencias."
    )
    fuente_archivo: str = Field(
        ...,
        description="Ruta o nombre del archivo de lista de asistencia procesado."
    )
    filas_participantes: List[FilaParticipanteIngestaDTO] = Field(
        ...,
        min_length=1,
        description="Colección de filas crudas extraídas de la lista."
    )

    model_config = {
        "frozen": True,
    }


class EnrutarParticipacionesCommand(BaseModel):
    """Comando de intención para ejecutar el routing institucional de participaciones de una actividad."""

    id_actividad: str = Field(
        ...,
        description="UUID de la actividad cuyas participaciones serán enrutadas."
    )
    dry_run: bool = Field(
        default=False,
        description="Si es True, calcula el routing en memoria y retorna el resumen sin persistir cambios."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

