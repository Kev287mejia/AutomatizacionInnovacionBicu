"""
app.word_consolidator.document

Submódulo de modelos documentales intermedios y capa de transformación
para la generación del Informe Consolidado Institucional (Fase 14.6).
Totalmente desacoplado de python-docx, tablas Word y estilos visuales.
"""

from app.word_consolidator.document.models import (
    DocumentoConsolidado,
    PortadaDocumental,
    ResumenEjecutivoDocumental,
    MatrizGeneralDocumental,
    FilaActividadDocumental,
    FichaActividadDocumental,
    DemografiaDocumental,
    EstamentosDocumental,
    TerritorioDocumental,
    AuditoriaDocumental,
    ConclusionDocumental,
    AnexosDocumentales,
    DistribucionSexoDocumental,
    MetricasRecurrenciaDocumental,
    ConteoEstamentoDocumental,
    ItemCarreraDocumental,
    ItemSedeDocumental,
    ItemTerritorioDocumental,
    ItemMunicipioDocumental,
    ItemDiscrepanciaDocumental,
    ItemComparativaDimension,
    FilaEstamentoDetalle,
    ComparativaTotalesActividad,
    TotalesComparativosDocumentales,
    TrazabilidadFuenteDocumental,
)
from app.word_consolidator.document.transformer import DocumentTransformer

# Modelos del Producto B: Informe Semanal Institucional BICU
from app.word_consolidator.document.institutional_models import (
    ActividadInstitucional,
    ConteoSexoInstitucional,
    DiscrepanciaActividadInstitucional,
    DiscrepanciaEstamento,
    EstadoEvidenciaEnum,
    InformeSemanalInstitucional,
    ItemEvidenciaInstitucional,
    ProtagonistaEstamentoInstitucional,
    SeccionEvidenciasActividad,
    TipoEstamentoInstitucional,
    TipoEvidenciaEnum,
    TrazabilidadActividad,
)
from app.word_consolidator.document.institutional_transformer import (
    InstitutionalReportTransformer,
)

__all__ = [
    "DocumentoConsolidado",
    "PortadaDocumental",
    "ResumenEjecutivoDocumental",
    "MatrizGeneralDocumental",
    "FilaActividadDocumental",
    "FichaActividadDocumental",
    "DemografiaDocumental",
    "EstamentosDocumental",
    "TerritorioDocumental",
    "AuditoriaDocumental",
    "ConclusionDocumental",
    "AnexosDocumentales",
    "DistribucionSexoDocumental",
    "MetricasRecurrenciaDocumental",
    "ConteoEstamentoDocumental",
    "ItemCarreraDocumental",
    "ItemSedeDocumental",
    "ItemTerritorioDocumental",
    "ItemMunicipioDocumental",
    "ItemDiscrepanciaDocumental",
    "ItemComparativaDimension",
    "FilaEstamentoDetalle",
    "ComparativaTotalesActividad",
    "TotalesComparativosDocumentales",
    "TrazabilidadFuenteDocumental",
    "DocumentTransformer",
    # Producto B
    "InformeSemanalInstitucional",
    "ActividadInstitucional",
    "ProtagonistaEstamentoInstitucional",
    "ConteoSexoInstitucional",
    "DiscrepanciaActividadInstitucional",
    "DiscrepanciaEstamento",
    "SeccionEvidenciasActividad",
    "ItemEvidenciaInstitucional",
    "TrazabilidadActividad",
    "TipoEstamentoInstitucional",
    "TipoEvidenciaEnum",
    "EstadoEvidenciaEnum",
    "InstitutionalReportTransformer",
]
