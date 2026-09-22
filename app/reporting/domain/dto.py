"""app.reporting.domain.dto

Objetos de Transferencia de Datos (DTOs) Inmutables para Reporting y Dashboard BICU.
Fase 29.20.1 — Implementación Controlada del Núcleo Reporting Service.

PRINCIPIOS:
  - Inmutabilidad estricta (@dataclass(frozen=True)).
  - Desacoplamiento de SQLite, CustomTkinter, Gemini y Word Consolidator.
  - Cero lógica matemática dentro de los DTOs.
  - Serializables y fáciles de probar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.reporting.domain.enums import AlertStatus, MultisessionGoalMode, ReportType


@dataclass(frozen=True)
class ReportFilterDTO:
    """Parámetros de filtrado dimensional aplicados a la generación de reportes y dashboard.
    
    Alineado estrictamente con la matriz de filtros certificada en Fase 29.20.0-C.
    """
    period_year: Optional[int] = None
    start_date: Optional[str] = None          # ISO 8601 YYYY-MM-DD
    end_date: Optional[str] = None            # ISO 8601 YYYY-MM-DD
    sede: Optional[str] = None                # Sede institucional (DDL V001)
    municipio: Optional[str] = None
    departamento: Optional[str] = None
    programa: Optional[str] = None
    eje_estrategia: Optional[str] = None
    tipo_evento: Optional[str] = None
    estado_planificacion: Optional[str] = None
    estado_ejecucion: Optional[str] = None
    trazabilidad: Optional[str] = None
    # Parámetros institucionales auditados
    multisession_goal_mode: str = MultisessionGoalMode.COHORT_UNIQUE.value
    require_verified_id_for_unique_persons: bool = True

    def __post_init__(self) -> None:
        # Validación defensiva de modo multisesión
        valid_modes = {MultisessionGoalMode.COHORT_UNIQUE.value, MultisessionGoalMode.SESSION_SUM.value}
        if self.multisession_goal_mode not in valid_modes:
            raise ValueError(
                f"Modo multisesión inválido: '{self.multisession_goal_mode}'. "
                f"Valores permitidos: {sorted(list(valid_modes))}."
            )


@dataclass(frozen=True)
class ReportMetricItemDTO:
    """Proyección atómica de un indicador institucional en una sección de reporte."""
    indicator_id: str
    label: str
    value_display: str                        # Ej. '85.50%', '1,420', 'N/D'
    raw_value: Optional[float]
    unit: str
    numerator_display: Optional[str] = None
    denominator_display: Optional[str] = None
    interpretation_note: Optional[str] = None
    alert_level: str = "NORMAL"               # 'NORMAL', 'WARNING', 'CRITICAL', 'INFO'


@dataclass(frozen=True)
class ReportSectionDTO:
    """Sección estructurada de un informe institucional consolidado."""
    section_id: str
    title: str
    description: str
    metrics: List[ReportMetricItemDTO] = field(default_factory=list)
    table_headers: List[str] = field(default_factory=list)
    table_rows: List[List[Any]] = field(default_factory=list)
    audit_notes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReportDocumentDTO:
    """Documento completo consolidado emitido por el ReportingService."""
    report_id: str
    report_type: ReportType
    title: str
    subtitle: str
    institution_name: str                     # 'Bluefields Indian & Caribbean University (BICU)'
    generated_at: str                         # ISO 8601
    generated_by: str
    filters_applied: ReportFilterDTO
    sections: List[ReportSectionDTO] = field(default_factory=list)
    parameters_applied: Dict[str, Any] = field(default_factory=dict)
    cryptographic_seal: Optional[str] = None  # SHA-256 opcional para trazabilidad pericial


@dataclass(frozen=True)
class DashboardCardDTO:
    """Tarjeta resumen (KPI Card) para renderizado visual en Dashboard."""
    card_id: str
    indicator_id: str
    title: str
    main_value: str                           # '87.50%', '25', 'N/D'
    unit_label: str                           # 'actividades', 'participaciones', '%'
    sub_label: str                            # '17 de 20 planes vinculados'
    alert_status: AlertStatus
    tooltip_explanation: str
    multisession_mode_applied: Optional[str] = None
    raw_value: Optional[float] = None


@dataclass(frozen=True)
class ChartDatasetDTO:
    """Estructura de datos normalizada para alimentar componentes visuales (gráficos/barras)."""
    chart_type: str                           # 'BAR', 'PIE', 'LINE', 'STACKED_BAR'
    title: str
    labels: List[str] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    extra_series: Dict[str, List[float]] = field(default_factory=dict)


@dataclass(frozen=True)
class DashboardSectionDTO:
    """Nivel o sección modular dentro del Dashboard interactivo."""
    section_id: str
    title: str
    cards: List[DashboardCardDTO] = field(default_factory=list)
    charts: List[ChartDatasetDTO] = field(default_factory=list)
    table_headers: List[str] = field(default_factory=list)
    table_rows: List[List[Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class DashboardDataDTO:
    """Payload completo e inmutable proyectado hacia el Dashboard visual (5 niveles)."""
    timestamp: str
    filters_active: ReportFilterDTO
    kpi_cards_summary: List[DashboardCardDTO]
    level_1_summary: DashboardSectionDTO
    level_2_activity: DashboardSectionDTO
    level_3_demography: DashboardSectionDTO
    level_4_territory: DashboardSectionDTO
    level_5_traceability: DashboardSectionDTO
    system_health_alerts: List[str] = field(default_factory=list)
    parameters_applied: Dict[str, Any] = field(default_factory=dict)
