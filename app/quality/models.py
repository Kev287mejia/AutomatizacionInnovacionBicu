"""app.quality.models

Modelos de Dominio y Value Objects para el Motor de Calidad Institucional BICU.
Gobernado bajo el principio inviolable DETECTAR ≠ CORREGIR (Regla RN-C07).

Define:
- ValidationFinding: Hallazgo atómico inmutable de calidad con trazabilidad forense.
- QualityAssessment: Value Object de resultado consolidado de evaluación en memoria.
- QualityContext: Contenedor desacoplado de entidades y metadatos evaluados.
- IValidationRule: Interfaz Strategy para reglas desacopladas Q-01 a Q-20.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator

from app.core.models.activity import Activity
from app.core.models.participation import Participation
from app.core.models.person import Person


class SeveridadCalidad(str, Enum):
    """Niveles oficiales de severidad técnica e institucional.
    
    REGLA: 'REVISION' NO es una severidad; es un estado o acción pericial.
    Solo existen 4 severidades oficiales.
    """
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EstadoGeneralCalidad(str, Enum):
    """Estado sintético global de aptitud institucional resultante de la evaluación."""
    CONFORME = "CONFORME"
    CON_OBSERVACIONES = "CON_OBSERVACIONES"
    REQUIERE_ACCION = "REQUIERE_ACCION"
    BLOQUEADO = "BLOQUEADO"


class ValidationFinding(BaseModel):
    """Hallazgo atómico de calidad generado por una regla del motor pericial.
    
    Responde formalmente las 9 preguntas de auditoría forense sin mutar datos.
    """
    id_hallazgo: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único del hallazgo (UUIDv4)."
    )
    codigo_regla: str = Field(
        ...,
        description="Código estandarizado de la regla (ej. Q-01, VAL_CEDULA_VACIA)."
    )
    severidad: str = Field(
        ...,
        description="Nivel de severidad técnica: 'INFO', 'WARNING', 'ERROR' o 'CRITICAL'."
    )
    id_referencia: Optional[str] = Field(
        default=None,
        description="Identificador de la entidad evaluada (id_actividad, id_persona, id_participacion)."
    )
    entidad_afectada: str = Field(
        ...,
        description="Tipo de entidad evaluada: 'ACTIVIDAD', 'PERSONA', 'PARTICIPACION', 'INFORME'."
    )
    campo_origen: Optional[str] = Field(
        default=None,
        description="Nombre del campo o atributo donde se detectó el hallazgo."
    )
    valor_detectado: Optional[str] = Field(
        default=None,
        description="Valor literal crudo detectado en la fuente de origen."
    )
    valor_esperado: Optional[str] = Field(
        default=None,
        description="Valor canónico, catálogo o expectativa de integridad referencial."
    )
    mensaje_humano: str = Field(
        ...,
        description="Descripción clara, legible y pericial del problema detectado."
    )
    fuente_archivo: Optional[str] = Field(
        default=None,
        description="Nombre o ruta relativa del documento origen del dato."
    )
    requiere_discrepancia_persistente: bool = Field(
        default=False,
        description="Indica si este hallazgo debe materializarse como fila en la tabla 'discrepancia'."
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Momento exacto en que se detectó la anomalía."
    )

    @field_validator("severidad")
    @classmethod
    def validar_severidad(cls, v: str) -> str:
        """Asegura que la severidad pertenezca estrictamente a los 4 niveles autorizados."""
        norm = v.strip().upper() if isinstance(v, str) else ""
        if norm not in SeveridadCalidad.__members__:
            raise ValueError(
                f"Severidad '{v}' inválida. Las únicas severidades autorizadas son: "
                f"{list(SeveridadCalidad.__members__.keys())}. 'REVISION' no es una severidad."
            )
        return norm

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class QualityAssessment(BaseModel):
    """Value Object de resultado de evaluación de calidad en memoria.
    
    ARQUITECTURA:
    - Es inmutable y se genera puramente en memoria tras la evaluación.
    - NO es una entidad persistente ni un Aggregate persistido en SQLite.
    - NO posee tabla ni repositorio en persistencia.
    """
    id_evaluacion: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único de la corrida de evaluación."
    )
    id_actividad: str = Field(
        ...,
        description="Identificador UUID de la actividad evaluada."
    )
    timestamp_evaluacion: datetime = Field(
        default_factory=datetime.now,
        description="Sello temporal de la evaluación."
    )
    # Métricas Globales
    total_actividades_evaluadas: int = Field(default=0, ge=0)
    total_personas_evaluadas: int = Field(default=0, ge=0)
    total_participaciones_evaluadas: int = Field(default=0, ge=0)
    total_reglas_ejecutadas: int = Field(default=0, ge=0)

    # Resumen por Severidad (Las 4 severidades oficiales)
    total_criticos: int = Field(default=0, ge=0)       # CRITICAL
    total_errores: int = Field(default=0, ge=0)        # ERROR
    total_advertencias: int = Field(default=0, ge=0)   # WARNING
    total_revisiones: int = Field(default=0, ge=0)     # Participaciones con requiere_revision
    total_informativos: int = Field(default=0, ge=0)   # INFO

    # Clasificación Operativa de Participaciones
    total_aptas: int = Field(default=0, ge=0)          # Sin observaciones bloqueantes ni de revisión
    total_en_revision: int = Field(default=0, ge=0)    # Enrutadas a M2..M5 pero con observación documental
    total_cola_revision: int = Field(default=0, ge=0)  # Categoría DESCONOCIDO
    total_bloqueadas: int = Field(default=0, ge=0)     # Aisladas con matriz_destino = None

    hallazgos: List[ValidationFinding] = Field(
        default_factory=list,
        description="Colección de hallazgos periciales individuales."
    )
    estado_general_calidad: EstadoGeneralCalidad = Field(
        default=EstadoGeneralCalidad.CONFORME,
        description="Estado general de aptitud institucional resultante."
    )

    model_config = {
        "frozen": True,
    }


class QualityContext(BaseModel):
    """Contexto de entrada para la ejecución de las reglas del motor de calidad."""
    actividad: Optional[Activity] = None
    personas: List[Person] = Field(default_factory=list)
    participaciones: List[Participation] = Field(default_factory=list)

    # Metadatos documentales y de planificación
    meta_planificada: Optional[int] = None
    total_asistentes_declarados_informe: Optional[int] = None
    titulo_informe: Optional[str] = None
    fecha_informe: Optional[str] = None
    fecha_asistencia_declarada: Optional[str] = None
    fuente_archivo_asistencia: Optional[str] = None
    fuente_archivo_informe: Optional[str] = None

    # Catálogos opcionales para reglas desacopladas
    catalogo_carreras: Optional[List[str]] = None
    catalogo_etnias: Optional[List[str]] = None
    mapeos_sexo: Optional[Dict[str, Dict[str, str]]] = None

    model_config = {
        "arbitrary_types_allowed": True,
    }


class IValidationRule(ABC):
    """Interfaz abstracta Strategy para una regla del motor de calidad."""
    codigo_regla: str
    nombre_regla: str
    dimension: str
    severidad_por_defecto: str

    @abstractmethod
    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        """Ejecuta la evaluación de la regla sobre el contexto proporcionado.
        
        Garantía: No debe mutar ninguna entidad recibida.
        """
        ...
