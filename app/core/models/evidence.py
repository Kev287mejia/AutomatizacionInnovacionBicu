"""app.core.models.evidence

Modelo interno de Evidencia (Evidence) para activos digitales institucionales.
Modela fotografías, listas firmadas, actas y enlaces web con custodia criptográfica SHA-256.

Decisión de persistencia (Fase 24):
- Metadatos + hash SHA-256 en base de datos.
- Archivos binarios pesados en sistema de archivos local.
"""

from datetime import date
from enum import Enum
from typing import Optional, Union
import uuid
from pydantic import BaseModel, Field


class TipoEvidencia(str, Enum):
    """Tipos de evidencia institucional admitidos."""
    FOTOGRAFIA = "FOTOGRAFIA"
    LISTA_FIRMADA = "LISTA_FIRMADA"
    ACTA_RECEPCION = "ACTA_RECEPCION"
    ENLACE_WEB = "ENLACE_WEB"
    DOCUMENTO_ADJUNTO = "DOCUMENTO_ADJUNTO"


class Evidencia(BaseModel):
    """Modelo de dominio representativo de un activo digital de evidencia."""

    id_evidencia: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único interno generado automáticamente (UUIDv4)."
    )
    tipo_evidencia: TipoEvidencia = Field(
        default=TipoEvidencia.FOTOGRAFIA,
        description="Tipo de evidencia institucional."
    )
    titulo: str = Field(
        ...,
        description="Título descriptivo breve de la evidencia."
    )
    descripcion_pie: Optional[str] = Field(
        default=None,
        description="Pie de foto o descripción contextual para informes Word."
    )
    ruta_archivo_relativa: Optional[str] = Field(
        default=None,
        description="Ruta relativa dentro de la bóveda de almacenamiento local."
    )
    url_externa: Optional[str] = Field(
        default=None,
        description="URL o enlace web si la evidencia es un recurso en línea."
    )
    hash_sha256: Optional[str] = Field(
        default=None,
        description="Hash criptográfico SHA-256 del archivo binario para custodia e inalterabilidad."
    )
    tamano_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamaño en bytes del archivo digital."
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="Tipo MIME del recurso (ej. image/jpeg, application/pdf)."
    )
    fecha_captura: Optional[Union[date, str]] = Field(
        default=None,
        description="Fecha en que se capturó o emitió la evidencia."
    )

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ActividadEvidenciaVinculo(BaseModel):
    """Asociación N:M entre una Actividad y una Evidencia."""

    id_actividad_evidencia: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único de la relación asociativa."
    )
    id_actividad: str = Field(
        ...,
        description="Identificador de la actividad asociada."
    )
    id_evidencia: str = Field(
        ...,
        description="Identificador de la evidencia vinculada."
    )
    orden_presentacion: int = Field(
        default=1,
        ge=1,
        description="Orden de visualización en el informe de actividad."
    )
    seccion_informe: str = Field(
        default="GALERIA",
        description="Sección de destino en el informe Word ('FICHA_TECNICA', 'GALERIA', 'ANEXO')."
    )

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }
