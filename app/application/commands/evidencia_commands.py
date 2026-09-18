"""Commands para el contexto de Evidencias y Custodia Digital - Sistema BICU.

Representan intenciones de registro, vinculación y desvinculación de activos digitales.
"""

from datetime import date
from typing import Optional, Union
from pydantic import BaseModel, Field

from app.core.models.evidence import TipoEvidencia


class RegistrarEvidenciaDigitalCommand(BaseModel):
    """Comando de intención para asentar los metadatos de un activo digital en el sistema."""

    tipo_evidencia: Union[TipoEvidencia, str] = Field(
        default=TipoEvidencia.FOTOGRAFIA,
        description="Tipo de evidencia institucional."
    )
    titulo: str = Field(
        ...,
        description="Título o encabezado descriptivo breve."
    )
    descripcion_pie: Optional[str] = Field(
        default=None,
        description="Pie descriptivo o texto de contexto."
    )
    ruta_archivo_relativa: Optional[str] = Field(
        default=None,
        description="Ubicación relativa en el almacenamiento de evidencias."
    )
    url_externa: Optional[str] = Field(
        default=None,
        description="Enlace web si es recurso externo."
    )
    hash_sha256: Optional[str] = Field(
        default=None,
        description="Hash criptográfico SHA-256 para custodia e inalterabilidad."
    )
    tamano_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Tamaño en bytes del archivo."
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="Tipo MIME del recurso."
    )
    fecha_captura: Optional[Union[date, str]] = Field(
        default=None,
        description="Fecha de captura o emisión."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class VincularEvidenciaActividadCommand(BaseModel):
    """Comando de intención para vincular una evidencia digital a una actividad (N:M)."""

    id_actividad: str = Field(..., description="UUID de la actividad receptora.")
    id_evidencia: str = Field(..., description="UUID de la evidencia a vincular.")
    orden_presentacion: int = Field(
        default=1,
        ge=1,
        description="Orden o posición de maquetación en el informe Word."
    )
    seccion_informe: str = Field(
        default="GALERIA",
        description="Sección del informe de destino ('FICHA_TECNICA', 'GALERIA', 'ANEXO')."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class DesvincularEvidenciaActividadCommand(BaseModel):
    """Comando de intención para remover el vínculo entre una evidencia y una actividad."""

    id_actividad: str = Field(..., description="UUID de la actividad.")
    id_evidencia: str = Field(..., description="UUID de la evidencia a desvincular.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
