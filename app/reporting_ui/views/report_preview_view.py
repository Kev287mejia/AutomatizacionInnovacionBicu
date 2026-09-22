"""app.reporting_ui.views.report_preview_view

Componente visual de previsualización y exportación documental institucional BICU.
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS:
  - Recibe un ReportDocumentDTO inmutable para inspección previa a la exportación.
  - Ofrece botones de exportación a XLSX, DOCX y CSV.
  - No modifica la base de datos ni las matrices oficiales M1–M5.
"""

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from app.reporting.domain.dto import ReportDocumentDTO
from app.reporting.domain.enums import ExportFormat


class ReportPreviewView(ctk.CTkFrame):
    """Panel de previsualización del informe generado y exportación a disco."""

    def __init__(
        self,
        master: Any,
        on_export_requested: Optional[Callable[[ReportDocumentDTO, Path, ExportFormat], Path]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_export_requested = on_export_requested
        self._current_doc: Optional[ReportDocumentDTO] = None

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -----------------------------------------------------------------
        # 1. BARRA SUPERIOR: METADATOS Y ACCIONES DE EXPORTACIÓN
        # -----------------------------------------------------------------
        self.top_bar = ctk.CTkFrame(self, fg_color=("#0B3C5D", "#1A2634"), corner_radius=6)
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 8))
        self.top_bar.grid_columnconfigure(0, weight=1)
        self.top_bar.grid_columnconfigure(1, weight=0)

        self.lbl_title = ctk.CTkLabel(
            self.top_bar,
            text="VISTA PREVIA DEL REPORTE INSTITUCIONAL",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="white",
            anchor="w",
        )
        self.lbl_title.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        # Botones de exportación
        btn_group = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        btn_group.grid(row=0, column=1, padx=14, pady=8, sticky="e")

        self.btn_xlsx = ctk.CTkButton(
            btn_group,
            text="Exportar XLSX",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            width=110,
            height=30,
            command=lambda: self._export_as(ExportFormat.XLSX),
        )
        self.btn_xlsx.pack(side="left", padx=4)

        self.btn_docx = ctk.CTkButton(
            btn_group,
            text="Exportar DOCX",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1565C0",
            hover_color="#0D47A1",
            width=110,
            height=30,
            command=lambda: self._export_as(ExportFormat.DOCX),
        )
        self.btn_docx.pack(side="left", padx=4)

        self.btn_csv = ctk.CTkButton(
            btn_group,
            text="Exportar CSV",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#546E7A",
            hover_color="#37474F",
            width=110,
            height=30,
            command=lambda: self._export_as(ExportFormat.CSV),
        )
        self.btn_csv.pack(side="left", padx=4)

        # -----------------------------------------------------------------
        # 2. CUERPO DESPLAZABLE: DETALLE DEL REPORTE
        # -----------------------------------------------------------------
        self.scroll_body = ctk.CTkScrollableFrame(self, fg_color=("gray95", "gray17"), corner_radius=6)
        self.scroll_body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scroll_body.grid_columnconfigure(0, weight=1)

        self.placeholder_lbl = ctk.CTkLabel(
            self.scroll_body,
            text="Seleccione un reporte institucional de la lista para previsualizarlo y exportarlo.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
        )
        self.placeholder_lbl.pack(pady=40)

    def display_report(self, document: ReportDocumentDTO) -> None:
        """Pinta la estructura del reporte en el área de vista previa."""
        self._current_doc = document
        for widget in self.scroll_body.winfo_children():
            widget.destroy()

        self.lbl_title.configure(text=f"{document.report_type.value}: {document.title}")

        # Tarjeta de Encabezado y Metadatos
        head_card = ctk.CTkFrame(self.scroll_body, fg_color=("white", "gray20"), corner_radius=6, border_width=1, border_color=("gray85", "gray30"))
        head_card.pack(fill="x", padx=10, pady=8)
        head_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            head_card,
            text=f"{document.institution_name} — REPORTE INSTITUCIONAL",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            head_card,
            text=f"{document.report_type.value}: {document.title}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 4))

        if document.subtitle:
            ctk.CTkLabel(
                head_card,
                text=document.subtitle,
                font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
                text_color=("gray40", "gray70"),
                anchor="w",
            ).pack(fill="x", padx=14, pady=(0, 6))

        # Metadatos en línea
        f = document.filters_applied
        meta_txt = (
            f"ID: {document.report_id}  |  Emisión: {document.generated_at}  |  "
            f"Período: {f.period_year or 'Todos'}  |  Sede: {f.sede or 'Todas'}  |  "
            f"Modo: {f.multisession_goal_mode}"
        )
        ctk.CTkLabel(
            head_card,
            text=meta_txt,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=("gray50", "gray60"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        # Secciones
        for sec in document.sections:
            sec_card = ctk.CTkFrame(self.scroll_body, fg_color=("white", "gray20"), corner_radius=6, border_width=1, border_color=("gray85", "gray30"))
            sec_card.pack(fill="x", padx=10, pady=6)

            # Título de sección
            s_head = ctk.CTkFrame(sec_card, fg_color=("#E7EFF6", "#1B2A38"), corner_radius=4)
            s_head.pack(fill="x", padx=6, pady=6)
            ctk.CTkLabel(
                s_head,
                text=f"{sec.section_id}: {sec.title}",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=("#0B3C5D", "#90CAF9"),
                anchor="w",
            ).pack(fill="x", padx=10, pady=4)

            if sec.description:
                ctk.CTkLabel(
                    sec_card,
                    text=sec.description,
                    font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
                    text_color=("gray40", "gray70"),
                    anchor="w",
                ).pack(fill="x", padx=12, pady=(2, 6))

            # Métricas
            if sec.metrics:
                m_frame = ctk.CTkFrame(sec_card, fg_color="transparent")
                m_frame.pack(fill="x", padx=12, pady=4)
                for m in sec.metrics:
                    m_row = ctk.CTkFrame(m_frame, fg_color=("gray95", "gray23"), corner_radius=4)
                    m_row.pack(fill="x", pady=2)
                    m_row.grid_columnconfigure(1, weight=1)

                    ctk.CTkLabel(m_row, text=f"{m.indicator_id}:", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), width=120, anchor="w").grid(row=0, column=0, padx=8, pady=4, sticky="w")
                    ctk.CTkLabel(m_row, text=m.label, font=ctk.CTkFont(family="Segoe UI", size=10), anchor="w").grid(row=0, column=1, padx=4, pady=4, sticky="w")
                    ctk.CTkLabel(m_row, text=f"{m.value_display} {m.unit}", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=("#0B3C5D", "#4FC3F7"), width=130, anchor="e").grid(row=0, column=2, padx=8, pady=4, sticky="e")

            # Tablas
            if sec.table_headers and sec.table_rows:
                tbl_frame = ctk.CTkFrame(sec_card, fg_color=("gray95", "gray22"), corner_radius=4)
                tbl_frame.pack(fill="x", padx=12, pady=6)
                for idx, h in enumerate(sec.table_headers):
                    tbl_frame.grid_columnconfigure(idx, weight=1)
                    ctk.CTkLabel(
                        tbl_frame,
                        text=str(h),
                        font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                        fg_color=("#0B3C5D", "#1A2634"),
                        text_color="white",
                        height=24,
                    ).grid(row=0, column=idx, sticky="ew", padx=1, pady=1)

                for r_idx, r_vals in enumerate(sec.table_rows[:20], start=1):  # Preview de hasta 20 filas
                    bg = ("white", "gray20") if r_idx % 2 == 1 else ("gray96", "gray23")
                    for c_idx, val in enumerate(r_vals):
                        ctk.CTkLabel(
                            tbl_frame,
                            text=str(val) if val is not None else "N/D",
                            font=ctk.CTkFont(family="Segoe UI", size=9),
                            fg_color=bg,
                            height=20,
                            anchor="w" if c_idx == 0 else "center",
                        ).grid(row=r_idx, column=c_idx, sticky="ew", padx=1, pady=1)

            # Notas de auditoría
            if sec.audit_notes:
                for note in sec.audit_notes:
                    ctk.CTkLabel(
                        sec_card,
                        text=f"• Nota Pericial: {note}",
                        font=ctk.CTkFont(family="Segoe UI", size=9, slant="italic"),
                        text_color=("gray50", "gray60"),
                        anchor="w",
                    ).pack(fill="x", padx=12, pady=1)

    def _export_as(self, fmt: ExportFormat) -> None:
        if not self._current_doc:
            messagebox.showwarning("Exportación", "No hay ningún reporte generado para exportar.")
            return

        extensions = {
            ExportFormat.XLSX: (".xlsx", "Libro de Excel (*.xlsx)"),
            ExportFormat.DOCX: (".docx", "Documento de Word (*.docx)"),
            ExportFormat.CSV: (".csv", "Archivo CSV (*.csv)"),
        }
        ext, desc = extensions[fmt]
        def_filename = f"{self._current_doc.report_type.value}_{self._current_doc.report_id[:8]}{ext}"

        filepath = filedialog.asksaveasfilename(
            title=f"Guardar {self._current_doc.report_type.value} como {fmt.value}",
            defaultextension=ext,
            initialfile=def_filename,
            filetypes=[(desc, f"*{ext}")],
        )
        if not filepath:
            return

        target = Path(filepath)
        try:
            if self.on_export_requested:
                saved_path = self.on_export_requested(self._current_doc, target, fmt)
                messagebox.showinfo(
                    "Exportación Exitosa",
                    f"El reporte {self._current_doc.report_type.value} ha sido exportado exitosamente a:\n\n{saved_path}",
                )
        except Exception as ex:
            messagebox.showerror("Error de Exportación", f"No se pudo completar la exportación del reporte:\n{ex}")
