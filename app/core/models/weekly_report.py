"""app.core.models.weekly_report

Modelo interno de Informe Semanal Consolidado (Weekly Report) de recinto.
Representa el documento periódico de agregación de actividades para emitir
Product A (Informe Técnico Horizontal) y Product B (Informe Ejecutivo Vertical).
"""

from datetime import date, datetime
from typing import Optional, Union, List
import uuid
from pydantic import BaseModel, Field


class DetalleInformeSemanal(BaseModel):
    """Elemento ordinal de asociación entre un informe semanal y una actividad incluida."""

    id_detalle: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único del ítem de detalle."
    )
    id_informe_semanal: str = Field(
        ...,
        description="Identificador del informe semanal contenedor."
    )
    id_actividad: str = Field(
        ...,
        description="Identificador de la actividad incorporada al consolidado."
    )
    orden_secuencia: int = Field(
        default=1,
        ge=1,
        description="Posición u orden en la secuencia de presentación de actividades."
    )
    incluir_product_a: bool = Field(
        default=True,
        description="Indica si la actividad debe incluirse en Product A (Técnico Horizontal)."
    )
    incluir_product_b: bool = Field(
        default=True,
        description="Indica si la actividad debe incluirse en Product B (Ejecutivo Vertical)."
    )

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class InformeSemanal(BaseModel):
    """Modelo de dominio representativo de un informe semanal consolidado de recinto."""

    id_informe_semanal: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único interno generado automáticamente (UUIDv4)."
    )
    anio: int = Field(
        ...,
        ge=2020,
        le=2050,
        description="Año calendario de ejecución."
    )
    mes: int = Field(
        ...,
        ge=1,
        le=12,
        description="Mes calendario (1..12)."
    )
    numero_semana: int = Field(
        ...,
        ge=1,
        le=5,
        description="Número correlativo de semana operativa del mes (1..5)."
    )
    etiqueta_periodo: str = Field(
        ...,
        description="Denominación legible oficial del período (ej. 'Semana 3 - Septiembre 2026')."
    )
    departamento_responsable: str = Field(
        ...,
        description="Área institucional responsable del consolidado."
    )
    sede_recinto: str = Field(
        ...,
        description="Sede o recinto institucional emisor."
    )
    ruta_product_a: Optional[str] = Field(
        default=None,
        description="Ruta de almacenamiento del documento Word Product A generado."
    )
    hash_sha256_product_a: Optional[str] = Field(
        default=None,
        description="Hash SHA-256 de custodia del archivo Product A emitido."
    )
    ruta_product_b: Optional[str] = Field(
        default=None,
        description="Ruta de almacenamiento del documento Word Product B generado."
    )
    hash_sha256_product_b: Optional[str] = Field(
        default=None,
        description="Hash SHA-256 de custodia del archivo Product B emitido."
    )
    fecha_generacion: Union[datetime, date, str] = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Fecha y hora formal de emisión del informe."
    )
    detalles: Optional[List[DetalleInformeSemanal]] = Field(
        default=None,
        description="Colección opcional de actividades ordenadas que componen el informe."
    )

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }
