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


class ActividadMetricaAgregada(BaseModel):
    """Métricas cuantitativas agregadas provenientes de la Tabla 2 del informe Word.

    REGLA FUNDAMENTAL DE DATOS AGREGADOS:
    La información agregada de Tabla 2:
    - NO CREA PERSONA
    - NO CREA PARTICIPATION
    - NO CREA CÉDULA
    - NO CREA ESTUDIANTE
    - NO CREA DOCENTE
    - NO CREA ADMINISTRATIVO
    - NO CREA PROTAGONISTA
    Únicamente debe almacenarse como actividad_metrica_agregada.
    """
    id_actividad: str = Field(
        ...,
        description="UUID de la actividad institucional vinculada (relación 1:1)."
    )
    total_participantes: Optional[int] = Field(default=None, description="Total global de participantes.")
    total_femenino: Optional[int] = Field(default=None, description="Total participantes sexo femenino.")
    total_masculino: Optional[int] = Field(default=None, description="Total participantes sexo masculino.")
    total_estudiantes: Optional[int] = Field(default=None, description="Total estamento estudiantes.")
    total_docentes: Optional[int] = Field(default=None, description="Total estamento docentes.")
    total_administrativos: Optional[int] = Field(default=None, description="Total estamento personal administrativo.")
    total_otros: Optional[int] = Field(default=None, description="Total estamento otros.")
    total_mestizo: Optional[int] = Field(default=None, description="Total etnia Mestizo.")
    total_creole: Optional[int] = Field(default=None, description="Total etnia Creole.")
    total_miskitu: Optional[int] = Field(default=None, description="Total etnia Miskitu.")
    total_mayangna: Optional[int] = Field(default=None, description="Total etnia Mayangna.")
    total_ulwa: Optional[int] = Field(default=None, description="Total etnia Ulwa.")
    total_rama: Optional[int] = Field(default=None, description="Total etnia Rama.")
    total_garifuna: Optional[int] = Field(default=None, description="Total etnia Garífuna.")
    total_otra_etnia: Optional[int] = Field(default=None, description="Total otras etnias.")
    fuente_seccion: str = Field(
        default="TABLA_2_MATRIZ_CUANTITATIVA",
        description="Sección del documento origen de donde proceden las métricas."
    )
    presenta_discrepancia_interna: bool = Field(
        default=False,
        description="Refleja si el propio documento presenta inconsistencia interna entre sus cifras agregadas."
    )

    model_config = {
        "validate_assignment": True,
    }


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
    codigo_indicador: Optional[str] = Field(
        default=None,
        description="Código de indicador institucional extraído de la ficha técnica (GAP-2). No es tipo_evento."
    )
    hash_sha256: Optional[str] = Field(
        default=None,
        description="Hash criptográfico SHA-256 del archivo DOCX de origen para idempotencia (GAP-3)."
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
    metrica_agregada: Optional[ActividadMetricaAgregada] = Field(
        default=None,
        description="Métricas cuantitativas agregadas provenientes de Tabla 2 (GAP-1)."
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

