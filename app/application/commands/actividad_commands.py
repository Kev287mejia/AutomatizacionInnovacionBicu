"""Commands para el contexto de Actividades - Sistema BICU.

Representan intenciones de mutación sobre actividades, planificación, diseño metodológico
e informes individuales. No ejecutan lógica ni acceden a persistencia.
"""

from datetime import date
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.application.dto.input_dtos import PartidaPresupuestariaDTO


class RegistrarActividadCommand(BaseModel):
    """Comando de intención para registrar una nueva actividad en el SSOT."""

    nombre_actividad_original: str = Field(
        ...,
        description="Nombre textual extraído de la fuente de origen."
    )
    nombre_actividad_oficial: Optional[str] = Field(
        default=None,
        description="Nombre oficial o estandarizado."
    )
    fecha_evento: Optional[Union[date, str]] = Field(
        default=None,
        description="Fecha de realización de la actividad."
    )
    sede: Optional[str] = Field(
        default=None,
        description="Sede o recinto institucional."
    )
    departamento: Optional[str] = Field(
        default=None,
        description="Departamento geográfico."
    )
    municipio_evento: Optional[str] = Field(
        default=None,
        description="Municipio del evento."
    )
    programa: Optional[str] = Field(
        default=None,
        description="Programa institucional responsable."
    )
    ambito: Optional[str] = Field(
        default=None,
        description="Ámbito territorial."
    )
    tipo_evento: Optional[str] = Field(
        default=None,
        description="Tipo de evento institucional."
    )
    eje_linea_estrategica: Optional[str] = Field(
        default=None,
        description="Línea estratégica institucional."
    )
    informacion_adicional: Optional[str] = Field(
        default=None,
        description="Notas o datos complementarios."
    )
    fuente_origen: Optional[str] = Field(
        default=None,
        description="Archivo o documento de origen."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class AsignarPlanificacionCommand(BaseModel):
    """Comando de intención para asignar metas y presupuesto a una actividad."""

    id_actividad: str = Field(
        ...,
        description="UUID de la actividad a la cual se asigna la planificación."
    )
    anio: int = Field(
        ...,
        ge=2020,
        le=2050,
        description="Año operativo."
    )
    mes: int = Field(
        ...,
        ge=1,
        le=12,
        description="Mes operativo (1..12)."
    )
    semana: int = Field(
        ...,
        ge=1,
        le=5,
        description="Semana operativa (1..5)."
    )
    meta_participantes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Meta proyectada de participantes."
    )
    partidas_presupuestarias: List[PartidaPresupuestariaDTO] = Field(
        default_factory=list,
        description="Partidas o rubros presupuestarios asociados."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class AsignarDisenoMetodologicoCommand(BaseModel):
    """Comando de intención para asociar diseño pedagógico y metodológico a una actividad."""

    id_actividad: str = Field(
        ...,
        description="UUID de la actividad formativa."
    )
    objetivo_general: str = Field(
        ...,
        description="Objetivo general de la actividad."
    )
    objetivos_especificos: Optional[str] = Field(
        default=None,
        description="Objetivos específicos."
    )
    contenidos_tematicos: Optional[str] = Field(
        default=None,
        description="Temario o contenidos desarrollados."
    )
    metodologia: Optional[str] = Field(
        default=None,
        description="Metodología didáctica implementada."
    )
    horas_duracion: Optional[int] = Field(
        default=None,
        ge=0,
        description="Duración en horas reloj."
    )
    materiales_insumos: Optional[str] = Field(
        default=None,
        description="Recursos o insumos requeridos."
    )
    facilitadores: Optional[str] = Field(
        default=None,
        description="Nombres de los facilitadores o instructores."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class RegistrarInformeActividadCommand(BaseModel):
    """Comando de intención para asentar la emisión del informe Word individual de una actividad."""

    id_actividad: str = Field(
        ...,
        description="UUID de la actividad correspondiente."
    )
    ruta_archivo_word: str = Field(
        ...,
        description="Ruta de almacenamiento del documento individual generado."
    )
    hash_sha256: str = Field(
        ...,
        description="Hash criptográfico SHA-256 de custodia del documento emitido."
    )
    total_participantes_declarados: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total de asistentes reportado en la carátula o ficha técnica del informe."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
