"""app.reporting.domain.enums

Catálogos y Enumeraciones para la Capa de Reporting y Dashboard Institucional BICU.
Fase 29.20.1 — Implementación Controlada del Núcleo Reporting Service.

PRINCIPIOS:
  - Cero ambigüedades en tipos de reportes institucionales (REP-01 a REP-05).
  - Tipos de alerta para estados de KPI y salud del dato.
  - Modos de meta de multisesión estrictamente parametrizados.
"""

from enum import Enum


class ReportType(str, Enum):
    """Catálogo canónico de reportes institucionales BICU aprobados en Fase 29.20."""
    REP_01 = "REP-01"  # Balance Ejecutivo de Gestión Institucional
    REP_02 = "REP-02"  # Evaluación de Cumplimiento del POA (Plan vs Ejecución)
    REP_03 = "REP-03"  # Cobertura Demográfica y Atención de Protagonistas
    REP_04 = "REP-04"  # Extensión y Descentralización Territorial
    REP_05 = "REP-05"  # Auditoría de Trazabilidad, Gobernanza y Salud del Dato


class AlertStatus(str, Enum):
    """Estados visuales y periciales de alerta para tarjetas KPI y secciones."""
    GREEN = "GREEN"      # Cumplimiento adecuado, dentro de umbral óptimo
    YELLOW = "YELLOW"    # Alerta preventiva / discrepancia activa / atención
    RED = "RED"          # Incumplimiento crítico / falla en calidad del dato
    NEUTRAL = "NEUTRAL"  # Métrica informativa pura / sin evaluación de umbral


class ExportFormat(str, Enum):
    """Formatos de exportación documental autorizados para Reporting."""
    XLSX = "XLSX"  # Excel (mediante openpyxl existente - MVP)
    DOCX = "DOCX"  # Word (mediante python-docx existente - MVP)
    CSV = "CSV"    # CSV estructurado (librería estándar - MVP)
    PDF = "PDF"    # PDF (clasificado como FUTURO / post-MVP)


class MultisessionGoalMode(str, Enum):
    """Modos oficiales de cómputo de metas para eventos multisesión (IND-CUMP-02)."""
    COHORT_UNIQUE = "COHORT_UNIQUE"  # Personas únicas alcanzadas (Default certificado)
    SESSION_SUM = "SESSION_SUM"      # Esfuerzo acumulado de participaciones brutas
