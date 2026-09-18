"""
app.templates_analysis

Módulo para la inspección física (Fase 8A) e ingeniería de mapeo (Fase 8B)
de plantillas oficiales de Excel.
"""

from app.templates_analysis.models import (
    TipoMapeoColumna,
    EstadoMapeo,
    CeldaProtegida,
    RangoCombinado,
    ColumnaDetectada,
    ZonaEscribible,
    EsquemaPlantilla,
    ItemMappingManifesto,
    MappingManifesto,
    ReporteInspeccionPlantillas,
)

__all__ = [
    "TipoMapeoColumna",
    "EstadoMapeo",
    "CeldaProtegida",
    "RangoCombinado",
    "ColumnaDetectada",
    "ZonaEscribible",
    "EsquemaPlantilla",
    "ItemMappingManifesto",
    "MappingManifesto",
    "ReporteInspeccionPlantillas",
]
