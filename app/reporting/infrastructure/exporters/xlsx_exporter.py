"""app.reporting.infrastructure.exporters.xlsx_exporter

Exportador de Reportes Institucionales BICU en formato Excel (.xlsx).
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS:
  - Generación de archivos derivados limpios utilizando openpyxl.
  - Cero modificación de plantillas maestras o matrices M1–M5.
  - Estilos visuales institucionales (#0B3C5D / #1A2634).
  - Estructuración transparente de secciones, tablas de datos y notas de auditoría.
"""

from pathlib import Path
from typing import Union

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.reporting.domain.dto import ReportDocumentDTO


class XLSXReportExporter:
    """Genera libros Excel profesionales derivados a partir de ReportDocumentDTO."""

    @staticmethod
    def export(document: ReportDocumentDTO, output_path: Union[str, Path]) -> Path:
        """Exporta el documento a la ruta especificada en formato .xlsx."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        wb = openpyxl.Workbook()
        # Eliminar hoja por defecto al configurar las propias
        ws_resumen = wb.active
        ws_resumen.title = "Resumen Ejecutivo"

        # Paleta institucional BICU
        fill_header = PatternFill(start_color="0B3C5D", end_color="0B3C5D", fill_type="solid")
        fill_sub = PatternFill(start_color="1A2634", end_color="1A2634", fill_type="solid")
        fill_section = PatternFill(start_color="2A4D69", end_color="2A4D69", fill_type="solid")
        fill_metric_head = PatternFill(start_color="4B86B4", end_color="4B86B4", fill_type="solid")
        fill_table_head = PatternFill(start_color="E7EFF6", end_color="E7EFF6", fill_type="solid")

        font_title = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
        font_sub = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        font_section = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        font_bold = Font(name="Segoe UI", size=10, bold=True)
        font_regular = Font(name="Segoe UI", size=10)
        font_muted = Font(name="Segoe UI", size=9, italic=True, color="555555")

        thin_side = Side(border_style="thin", color="CCCCCC")
        border_box = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        # -----------------------------------------------------------------
        # 1. ENCABEZADO INSTITUCIONAL
        # -----------------------------------------------------------------
        ws_resumen.merge_cells("A1:F1")
        c_title = ws_resumen["A1"]
        c_title.value = f"{document.institution_name} — REPORTE OFICIAL"
        c_title.fill = fill_header
        c_title.font = font_title
        c_title.alignment = Alignment(horizontal="center", vertical="center")
        ws_resumen.row_dimensions[1].height = 28

        ws_resumen.merge_cells("A2:F2")
        c_sub = ws_resumen["A2"]
        c_sub.value = f"{document.report_type.value}: {document.title}"
        c_sub.fill = fill_sub
        c_sub.font = font_sub
        c_sub.alignment = Alignment(horizontal="center", vertical="center")
        ws_resumen.row_dimensions[2].height = 22

        if document.subtitle:
            ws_resumen.merge_cells("A3:F3")
            c_desc = ws_resumen["A3"]
            c_desc.value = document.subtitle
            c_desc.font = font_muted
            c_desc.alignment = Alignment(horizontal="center", vertical="center")
            ws_resumen.row_dimensions[3].height = 18

        # Metadatos del informe
        curr_row = 5
        ws_resumen.cell(row=curr_row, column=1, value="Metadato").font = font_bold
        ws_resumen.cell(row=curr_row, column=2, value="Valor").font = font_bold
        curr_row += 1

        meta_items = [
            ("ID del Reporte", document.report_id),
            ("Tipo Institucional", document.report_type.value),
            ("Fecha de Emisión", document.generated_at),
            ("Emitido Por", document.generated_by),
            ("Año del Período", str(document.filters_applied.period_year or "Todos")),
            ("Rango de Fechas", f"{document.filters_applied.start_date or 'Inicio'} a {document.filters_applied.end_date or 'Fin'}"),
            ("Sede Filtrada", document.filters_applied.sede or "Todas las Sedes"),
            ("Modo Multisesión", document.filters_applied.multisession_goal_mode),
            ("Sello Criptográfico (SHA-256)", document.cryptographic_seal or "No computado"),
        ]

        for k, v in meta_items:
            c1 = ws_resumen.cell(row=curr_row, column=1, value=k)
            c2 = ws_resumen.cell(row=curr_row, column=2, value=str(v))
            c1.font = font_bold
            c2.font = font_regular
            c1.border = border_box
            c2.border = border_box
            curr_row += 1

        curr_row += 2

        # -----------------------------------------------------------------
        # 2. SECCIONES Y TABLAS DEL DOCUMENTO
        # -----------------------------------------------------------------
        for sec in document.sections:
            ws_resumen.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=6)
            c_sec = ws_resumen.cell(row=curr_row, column=1, value=f"{sec.section_id}: {sec.title}")
            c_sec.fill = fill_section
            c_sec.font = font_section
            c_sec.alignment = Alignment(horizontal="left", vertical="center")
            ws_resumen.row_dimensions[curr_row].height = 20
            curr_row += 1

            if sec.description:
                ws_resumen.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=6)
                c_sdesc = ws_resumen.cell(row=curr_row, column=1, value=sec.description)
                c_sdesc.font = font_muted
                curr_row += 1

            # Métricas de la sección si existen
            if sec.metrics:
                m_headers = ["ID Indicador", "Métrica / Concepto", "Valor", "Unidad", "Relación (Num/Den)", "Nivel de Alerta"]
                for col_idx, h in enumerate(m_headers, start=1):
                    cell = ws_resumen.cell(row=curr_row, column=col_idx, value=h)
                    cell.fill = fill_metric_head
                    cell.font = font_section
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = border_box
                curr_row += 1

                for m in sec.metrics:
                    r_num_den = f"{m.numerator_display or '-'} / {m.denominator_display or '-'}"
                    m_row = [m.indicator_id, m.label, m.value_display, m.unit, r_num_den, m.alert_level]
                    for col_idx, val in enumerate(m_row, start=1):
                        cell = ws_resumen.cell(row=curr_row, column=col_idx, value=val)
                        cell.font = font_regular
                        cell.border = border_box
                        if col_idx in (1, 3, 4, 5, 6):
                            cell.alignment = Alignment(horizontal="center")
                    curr_row += 1
                curr_row += 1

            # Tablas de datos si existen
            if sec.table_headers and sec.table_rows:
                for col_idx, h in enumerate(sec.table_headers, start=1):
                    cell = ws_resumen.cell(row=curr_row, column=col_idx, value=str(h))
                    cell.fill = fill_table_head
                    cell.font = font_bold
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = border_box
                curr_row += 1

                for row_data in sec.table_rows:
                    for col_idx, val in enumerate(row_data, start=1):
                        cell = ws_resumen.cell(row=curr_row, column=col_idx, value=str(val) if val is not None else "N/D")
                        cell.font = font_regular
                        cell.border = border_box
                    curr_row += 1
                curr_row += 1

            # Notas de auditoría si existen
            if sec.audit_notes:
                for note in sec.audit_notes:
                    ws_resumen.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=6)
                    c_note = ws_resumen.cell(row=curr_row, column=1, value=f"• Nota Pericial: {note}")
                    c_note.font = font_muted
                    curr_row += 1
                curr_row += 1

            curr_row += 1

        # Ajuste de ancho de columnas
        for col in ws_resumen.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if len(val_str) > max_len and not cell.coordinate in ws_resumen.merged_cells:
                    max_len = len(val_str)
            ws_resumen.column_dimensions[col_letter].width = max(max_len + 4, 15)

        wb.save(str(out))
        return out
