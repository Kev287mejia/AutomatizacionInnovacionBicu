"""app.reporting.infrastructure.exporters.csv_exporter

Exportador de Reportes Institucionales BICU en formato estructurado CSV.
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS:
  - Generación de archivos derivados de texto estructurado utilizando biblioteca estándar csv.
  - Cero modificación de base de datos o matrices patrimoniales.
  - Formato UTF-8 compatible con Excel y herramientas de análisis institucional.
"""

import csv
from pathlib import Path
from typing import Union

from app.reporting.domain.dto import ReportDocumentDTO


class CSVReportExporter:
    """Genera archivos CSV estructurados derivados a partir de ReportDocumentDTO."""

    @staticmethod
    def export(document: ReportDocumentDTO, output_path: Union[str, Path]) -> Path:
        """Exporta el informe a la ruta especificada en formato .csv."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with open(out, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # -------------------------------------------------------------
            # 1. METADATOS DEL ENCABEZADO
            # -------------------------------------------------------------
            writer.writerow(["# REPORTE OFICIAL INSTITUCIONAL BICU"])
            writer.writerow(["# Institucion", document.institution_name])
            writer.writerow(["# Tipo Reporte", document.report_type.value])
            writer.writerow(["# Titulo", document.title])
            if document.subtitle:
                writer.writerow(["# Subtitulo", document.subtitle])
            writer.writerow(["# ID Reporte", document.report_id])
            writer.writerow(["# Fecha Generacion", document.generated_at])
            writer.writerow(["# Generado Por", document.generated_by])
            writer.writerow(["# Periodo Anual", str(document.filters_applied.period_year or "Todos")])
            writer.writerow(["# Rango Fechas", f"{document.filters_applied.start_date or 'Inicio'} a {document.filters_applied.end_date or 'Fin'}"])
            writer.writerow(["# Sede", document.filters_applied.sede or "Todas"])
            writer.writerow(["# Modo Multisesion", document.filters_applied.multisession_goal_mode])
            writer.writerow(["# Sello Criptografico", document.cryptographic_seal or "No computado"])
            writer.writerow([])

            # -------------------------------------------------------------
            # 2. SECCIONES Y TABLAS
            # -------------------------------------------------------------
            for sec in document.sections:
                writer.writerow([f"## SECCION: {sec.section_id} - {sec.title}"])
                if sec.description:
                    writer.writerow([f"# Descripcion: {sec.description}"])

                # Métricas
                if sec.metrics:
                    writer.writerow(["### METRICAS CLAVE"])
                    writer.writerow(["ID_Indicador", "Concepto", "Valor_Display", "Unidad", "Numerador", "Denominador", "Nivel_Alerta"])
                    for m in sec.metrics:
                        writer.writerow([
                            m.indicator_id,
                            m.label,
                            m.value_display,
                            m.unit,
                            m.numerator_display or "",
                            m.denominator_display or "",
                            m.alert_level,
                        ])
                    writer.writerow([])

                # Tablas de datos
                if sec.table_headers and sec.table_rows:
                    writer.writerow(["### TABLA DE DATOS"])
                    writer.writerow(sec.table_headers)
                    for row in sec.table_rows:
                        writer.writerow([str(v) if v is not None else "" for v in row])
                    writer.writerow([])

                # Notas de auditoría
                if sec.audit_notes:
                    writer.writerow(["### NOTAS DE AUDITORIA"])
                    for note in sec.audit_notes:
                        writer.writerow([f"* {note}"])
                    writer.writerow([])

                writer.writerow([])

        return out
