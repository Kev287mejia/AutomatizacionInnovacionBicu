"""
app.word_consolidator

Paquete institucional para la generación del Documento Word Consolidado (Fase 14).
Implementa lectura no destructiva de las 5 matrices oficiales, detección de discrepancias,
agregaciones multidimensionales y maquetación de informes en formato DOCX landscape.
"""

from app.word_consolidator.models import (
    TipoPeriodo,
    PeriodoConsolidacion,
    DiscrepanciaItem,
    EstadoDiscrepancia,
    RegistroFuenteArchivo,
    MetadatosInstitucionales,
    DesgloseEstamentoWord,
    FilaActividadWord,
    ReporteAuditoriaWord,
    ContextoConsolidadoDocx,
    FilaLeidaM1,
    FilaLeidaNominal,
    ConjuntoMatricesLeidas,
    ResultadoFiltradoPeriodo,
    InformeDiscrepanciasActividad,
    ResultadoAuditoriaDiscrepancias,
)
from app.word_consolidator.engine.discrepancy_detector import DiscrepancyDetector
from app.word_consolidator.document import (
    DocumentoConsolidado,
    DocumentTransformer,
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
)
from app.word_consolidator.docx_generator import (
    DocxGenerator,
    DocxRenderer,
)
from app.word_consolidator.pipeline import (
    MatrixIdentifier,
    WordConsolidationPipeline,
    PipelineExecutionResult,
    MatrixPipelineError,
    MatricesFaltantesError,
    MatrizDuplicadaError,
    EstructuraMatrizInvalidaError,
    ArchivoMatrizInvalidoError,
    ErrorIntegridadArchivo,
)

__all__ = [
    "TipoPeriodo",
    "PeriodoConsolidacion",
    "DiscrepanciaItem",
    "EstadoDiscrepancia",
    "RegistroFuenteArchivo",
    "MetadatosInstitucionales",
    "DesgloseEstamentoWord",
    "FilaActividadWord",
    "ReporteAuditoriaWord",
    "ContextoConsolidadoDocx",
    "FilaLeidaM1",
    "FilaLeidaNominal",
    "ConjuntoMatricesLeidas",
    "ResultadoFiltradoPeriodo",
    "InformeDiscrepanciasActividad",
    "ResultadoAuditoriaDiscrepancias",
    "DiscrepancyDetector",
    "DocumentoConsolidado",
    "DocumentTransformer",
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
    "DocxGenerator",
    "DocxRenderer",
    "MatrixIdentifier",
    "WordConsolidationPipeline",
    "PipelineExecutionResult",
    "MatrixPipelineError",
    "MatricesFaltantesError",
    "MatrizDuplicadaError",
    "EstructuraMatrizInvalidaError",
    "ArchivoMatrizInvalidoError",
    "ErrorIntegridadArchivo",
]


