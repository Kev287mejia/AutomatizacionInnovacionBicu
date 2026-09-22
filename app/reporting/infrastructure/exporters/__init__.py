"""app.reporting.infrastructure.exporters

Módulo de exportadores documentales derivados para Reporting Institucional BICU.
Fase 29.20.3 — Integración de Reporting + Dashboard Institucional.

PRINCIPIOS:
  - Formatos autorizados MVP: XLSX (openpyxl), DOCX (python-docx), CSV (estándar csv).
  - Cero mutación: los archivos exportados son salidas derivadas.
  - Cero modificación de SQLite, M1-M5, Planning ni V004.
  - No se utiliza motor PDF.
"""

from app.reporting.infrastructure.exporters.xlsx_exporter import XLSXReportExporter
from app.reporting.infrastructure.exporters.docx_exporter import DOCXReportExporter
from app.reporting.infrastructure.exporters.csv_exporter import CSVReportExporter

__all__ = [
    "XLSXReportExporter",
    "DOCXReportExporter",
    "CSVReportExporter",
]
