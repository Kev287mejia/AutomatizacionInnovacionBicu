"""Contratos y Modelos de Dominio para Indicadores Institucionales BICU.

Fase 29.19.1–29.19.2 — Auditoría e Implementación Controlada de Indicadores.

PRINCIPIOS RECTORES:
  1. DATOS ≠ INDICADORES ≠ INTERPRETACIONES
  2. PLANIFICADO ≠ EJECUTADO
  3. CERO MODIFICACIÓN DE FUENTES (Solo Lectura)
  4. INDEPENDIENTE DE IA, UI Y WORD CONSOLIDATOR
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class IndicatorCategory(str, Enum):
    """Categorías ortogonales de indicadores institucionales."""
    ACTIVIDAD = "ACTIVIDAD"
    CUMPLIMIENTO = "CUMPLIMIENTO"
    PARTICIPACION = "PARTICIPACION"
    TERRITORIAL = "TERRITORIAL"
    TEMPORALIDAD = "TEMPORALIDAD"
    DIVERSIDAD = "DIVERSIDAD"
    TRAZABILIDAD = "TRAZABILIDAD"
    CALIDAD = "CALIDAD"


class IndicatorId:
    """Catálogo canónico de identificadores de indicadores."""
    IND_ACT_01 = "IND-ACT-01"   # Total Actividades Planificadas
    IND_ACT_02 = "IND-ACT-02"   # Total Actividades Ejecutadas
    IND_ACT_03 = "IND-ACT-03"   # Total Actividades Emergentes
    IND_ACT_04 = "IND-ACT-04"   # Tasa de Formalización Metodológica
    IND_CUMP_01 = "IND-CUMP-01" # Cobertura de Ejecución de Actividades Planificadas
    IND_CUMP_02 = "IND-CUMP-02" # Eficacia Global de Metas de Participación
    IND_PART_01 = "IND-PART-01" # Total Participaciones Registradas (Asistencias Brutas)
    IND_PART_02 = "IND-PART-02" # Total Personas Únicas Alcanzadas
    IND_PART_03 = "IND-PART-03" # Tasa de Recurrencia de Participantes
    IND_PART_04 = "IND-PART-04" # Distribución de Participación por Sexo (Índice de Paridad)
    IND_PART_05 = "IND-PART-05" # Distribución de Participación por Estamento
    IND_TERR_01 = "IND-TERR-01" # Distribución Territorial de Actividades por Sede
    IND_TRAZ_01 = "IND-TRAZ-01" # Índice de Trazabilidad Planificación-Ejecución
    IND_TRAZ_02 = "IND-TRAZ-02" # Tasa de Discrepancia Documental (M1 vs M2-M5)
    IND_TRAZ_03 = "IND-TRAZ-03" # Tasa de Disponibilidad de Cédula Oficial


@dataclass(frozen=True)
class IndicatorDefinition:
    """Contrato canónico inmutable de un indicador institucional.
    
    Cumple rigurosamente la estructura de 16 campos aprobada en Fase 29.19 §8 y §12.
    """
    indicator_id: str
    name: str
    category: IndicatorCategory
    definition: str
    purpose: str
    source: str
    numerator: str
    denominator: Optional[str]
    formula: str
    unit: str
    periodicity: str
    dimensions: List[str]
    null_policy: str
    duplicate_policy: str
    limitations: str
    allowed_interpretation: str
    forbidden_interpretation: str


@dataclass(frozen=True)
class IndicatorQuery:
    """Criterios de consulta dimensional y parámetros técnicos de cálculo.
    
    Permite parametrizar decisiones pendientes sin asumir reglas institucionales arbitrarias.
    """
    indicator_ids: Optional[List[str]] = None
    start_date: Optional[str] = None       # ISO 8601 YYYY-MM-DD
    end_date: Optional[str] = None         # ISO 8601 YYYY-MM-DD
    sede: Optional[str] = None             # Sede institucional (filtro espacial)
    programa: Optional[str] = None         # Programa académico / extensión
    eje_estrategico: Optional[str] = None  # Eje institucional C1
    tipo_evento: Optional[str] = None      # Tipo de evento C4

    # Parámetros para Decisiones Institucionales Pendientes (Fase 29.19 §24)
    # DEC-INST-01: Ventana de corte para actividades vencidas
    evaluation_cutoff_date: Optional[str] = None

    # DEC-INST-02: Modo de metas en procesos multisesión (COHORT_UNIQUE vs SESSION_SUM)
    multisession_goal_mode: str = "COHORT_UNIQUE"

    # DEC-INST-04: Prevalencia ante discrepancias M1 vs Nominales
    discrepancy_prevalence: str = "NOMINAL_AUDITED"

    # DEC-INST-05: Requisito estricto de identificación para personas únicas
    require_verified_id_for_unique_persons: bool = True


@dataclass(frozen=True)
class IndicatorResult:
    """Resultado numérico determinista e inmutable de un cálculo de indicador."""
    indicator_id: str
    name: str
    category: IndicatorCategory
    value: Optional[float]
    unit: str
    numerator_value: Optional[float] = None
    denominator_value: Optional[float] = None
    universe_total: Optional[int] = None
    breakdown: Dict[str, Any] = field(default_factory=dict)
    is_determinable: bool = True
    notes: List[str] = field(default_factory=list)
    parameters_applied: Dict[str, Any] = field(default_factory=dict)
    calculation_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(frozen=True)
class IndicatorReport:
    """Contenedor agregado de resultados de múltiples indicadores."""
    query: IndicatorQuery
    results: Dict[str, IndicatorResult]
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_calculated: int = 0
    invariants_verified: bool = True
