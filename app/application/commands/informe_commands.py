"""Commands para el contexto de Informes Semanales Consolidados - Sistema BICU.

Representan intenciones de creación del contenedor de consolidación y asociación de actividades
para la emisión de Product A y Product B.
"""

from typing import List
from pydantic import BaseModel, Field

from app.application.dto.input_dtos import DetalleActividadInformeDTO


class CrearInformeSemanalCommand(BaseModel):
    """Comando de intención para crear el contenedor oficial de consolidado semanal de recinto."""

    anio: int = Field(
        ...,
        ge=2020,
        le=2050,
        description="Año de ejecución del consolidado."
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
        description="Número correlativo de semana operativa (1..5)."
    )
    etiqueta_periodo: str = Field(
        ...,
        description="Denominación formal del período (ej. 'Semana 3 - Septiembre 2026')."
    )
    departamento_responsable: str = Field(
        ...,
        description="Área institucional responsable del consolidado."
    )
    sede_recinto: str = Field(
        ...,
        description="Sede o recinto emisor del consolidado."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class AsociarActividadesInformeSemanalCommand(BaseModel):
    """Comando de intención para incorporar y ordenar actividades en un informe semanal."""

    id_informe_semanal: str = Field(
        ...,
        description="UUID del informe semanal contenedor."
    )
    detalles: List[DetalleActividadInformeDTO] = Field(
        ...,
        description="Lista de ítems de actividades ordenadas con sus banderas Product A/B."
    )

    model_config = {
        "frozen": True,
    }
