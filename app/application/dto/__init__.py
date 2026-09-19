"""Subpaquete de Data Transfer Objects (DTOs) de la capa de Aplicación - Sistema BICU."""

from app.application.dto.input_dtos import (
    FilaParticipanteIngestaDTO,
    PartidaPresupuestariaDTO,
    DetalleActividadInformeDTO,
)
from app.application.dto.output_dtos import (
    IngestaListaAsistenciaResultDTO,
    ActividadResumenDTO,
    ActividadDetalleDTO,
    PersonaResumenDTO,
    PersonaDetalleDTO,
    ParticipacionDetalleDTO,
    EvidenciaVinculadaDTO,
    DiscrepanciaDetalleDTO,
    InformeSemanalCompletoDTO,
    PlanificacionAsignadaDTO,
    DisenoMetodologicoAsignadoDTO,
    InformeActividadRegistradoDTO,
)
from app.application.dto.quality_dtos import (
    ValidationFindingDTO,
    QualityAssessmentDTO,
)
from app.application.dto.export_dtos import (
    PoliticaExportacionRevision,
    ExportacionPreparadaDTO,
    PipelineActividadResultDTO,
    ExportarMatricesResultDTO,
)
from app.application.dto.word_extraction_dtos import (
    TipoDocumentoWord,
    TipoEvidenciaWord,
    FichaTecnicaDTO,
    MatrizCuantitativaDTO,
    EvidenciaDetectadaDTO,
    EvidenciasAnexosDTO,
    NarrativaSeccionesDTO,
    DiagnosticoExtraccionDTO,
    WordActivityExtractionResultDTO,
    IngestaActividadWordResultDTO,
)
from app.application.dto.batch_dtos import (
    BatchArchivoResultadoDTO,
    BatchResultadoDTO,
    PipelineDesdeWordResultDTO,
)

__all__ = [
    "FilaParticipanteIngestaDTO",
    "PartidaPresupuestariaDTO",
    "DetalleActividadInformeDTO",
    "IngestaListaAsistenciaResultDTO",
    "ActividadResumenDTO",
    "ActividadDetalleDTO",
    "PersonaResumenDTO",
    "PersonaDetalleDTO",
    "ParticipacionDetalleDTO",
    "EvidenciaVinculadaDTO",
    "DiscrepanciaDetalleDTO",
    "InformeSemanalCompletoDTO",
    "PlanificacionAsignadaDTO",
    "DisenoMetodologicoAsignadoDTO",
    "InformeActividadRegistradoDTO",
    "ValidationFindingDTO",
    "QualityAssessmentDTO",
    "PoliticaExportacionRevision",
    "ExportacionPreparadaDTO",
    "PipelineActividadResultDTO",
    "ExportarMatricesResultDTO",
    "TipoDocumentoWord",
    "TipoEvidenciaWord",
    "FichaTecnicaDTO",
    "MatrizCuantitativaDTO",
    "EvidenciaDetectadaDTO",
    "EvidenciasAnexosDTO",
    "NarrativaSeccionesDTO",
    "DiagnosticoExtraccionDTO",
    "WordActivityExtractionResultDTO",
    "IngestaActividadWordResultDTO",
    # Batch
    "BatchArchivoResultadoDTO",
    "BatchResultadoDTO",
    "PipelineDesdeWordResultDTO",
]
