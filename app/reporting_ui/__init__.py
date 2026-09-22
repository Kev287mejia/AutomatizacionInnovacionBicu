"""app.reporting_ui

Capa de Interfaz de Usuario para Reporting y Dashboard Institucional BICU.
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS ARQUITECTÓNICOS:
  - Aislamiento estricto: reside en app.reporting_ui para no contaminar app.reporting con CustomTkinter.
  - Cero importación de sqlite3 o ejecución directa de SQL.
  - Cero acceso directo o modificación de las matrices patrimoniales M1–M5.
  - Cero duplicación de cálculos matemáticos o reglas de indicadores.
  - Flujo: CustomTkinter -> ReportingUIService -> ReportingService -> Indicators -> DB.
"""

__all__ = []
