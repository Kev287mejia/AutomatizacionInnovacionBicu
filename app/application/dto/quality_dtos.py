"""app.application.dto.quality_dtos

DTOs para la capa de Aplicación del contexto de Calidad Institucional BICU.
Transportan resultados de evaluación pericial sin exponer entidades de dominio ni acoplarse a persistencia.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ValidationFindingDTO(BaseModel):
    """DTO de transporte para un hallazgo pericial individual."""
    id_hallazgo: str = Field(..., description="UUID del hallazgo.")
    codigo_regla: str = Field(..., description="Código de regla (ej. Q-01..Q-20).")
    severidad: str = Field(..., description="Severidad técnica ('INFO', 'WARNING', 'ERROR', 'CRITICAL').")
    id_referencia: Optional[str] = Field(default=None, description="ID de la entidad evaluada.")
    entidad_afectada: str = Field(..., description="Tipo de entidad: 'ACTIVIDAD', 'PERSONA', 'PARTICIPACION', 'INFORME'.")
    campo_origen: Optional[str] = Field(default=None, description="Campo fuente donde se detectó el hallazgo.")
    valor_detectado: Optional[str] = Field(default=None, description="Valor literal asentado en origen.")
    valor_esperado: Optional[str] = Field(default=None, description="Valor esperado o formato canónico.")
    mensaje_humano: str = Field(..., description="Descripción pericial del hallazgo.")
    fuente_archivo: Optional[str] = Field(default=None, description="Archivo de procedencia.")
    requiere_discrepancia_persistente: bool = Field(default=False, description="True si genera fila en tabla discrepancia.")
    timestamp: str = Field(..., description="Momento de detección en formato ISO.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class QualityAssessmentDTO(BaseModel):
    """DTO de transporte para el resultado holístico de la evaluación de calidad de una actividad."""
    id_evaluacion: str = Field(..., description="UUID de la corrida de evaluación.")
    id_actividad: str = Field(..., description="UUID de la actividad evaluada.")
    timestamp_evaluacion: str = Field(..., description="Momento de la evaluación en ISO.")

    # Métricas Globales
    total_actividades_evaluadas: int = Field(default=0, ge=0)
    total_personas_evaluadas: int = Field(default=0, ge=0)
    total_participaciones_evaluadas: int = Field(default=0, ge=0)
    total_reglas_ejecutadas: int = Field(default=0, ge=0)

    # Resumen por Severidad (Las 4 severidades autorizadas)
    total_criticos: int = Field(default=0, ge=0)
    total_errores: int = Field(default=0, ge=0)
    total_advertencias: int = Field(default=0, ge=0)
    total_revisiones: int = Field(default=0, ge=0)
    total_informativos: int = Field(default=0, ge=0)

    # Clasificación Operativa
    total_aptas: int = Field(default=0, ge=0)
    total_en_revision: int = Field(default=0, ge=0)
    total_cola_revision: int = Field(default=0, ge=0)
    total_bloqueadas: int = Field(default=0, ge=0)

    hallazgos: List[ValidationFindingDTO] = Field(default_factory=list, description="Lista de hallazgos periciales.")
    estado_general_calidad: str = Field(..., description="Estado general ('CONFORME', 'CON_OBSERVACIONES', 'REQUIERE_ACCION', 'BLOQUEADO').")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
