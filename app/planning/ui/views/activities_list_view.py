"""
app.planning.ui.views.activities_list_view

Vista de Exploración y Filtrado de Actividades Planificadas (POA) — BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from app.planning.domain.dtos import PlannedActivitySummaryDTO, PlanningIngestionReportDTO
from app.planning.ui.services.planning_ui_service import PlanningUIError, PlanningUIService

SEDES_BICU = [
    "Todas",
    "Bluefields",
    "Bilwi",
    "Las Minas",
    "Nueva Guinea",
    "Waspam",
    "Paiwas",
    "El Rama",
    "Bonanza",
    "Rosita",
    "Siuna",
]

ESTADOS_DISENO = [
    "Todos",
    "SIN_DISENO",
    "DRAFT",
    "GENERATED",
    "APPROVED",
]


class IngestionReportDialog(ctk.CTkToplevel):
    """Ventana modal institucional que presenta el resumen de la ingestión de matriz POA."""

    def __init__(self, master: Any, report: PlanningIngestionReportDTO, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.report = report

        self.title("BICU — Resumen de Ingestión de Matriz POA")
        self.geometry("680x520")
        self.minsize(580, 420)
        self.grab_set()

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 1. Banner
        has_errors = bool(self.report.errors)
        has_rejections = self.report.rows_rejected > 0
        if has_errors:
            banner_bg = ("#C62828", "#B71C1C")
            banner_title = "⚠️ ATENCIÓN — OBSERVACIONES ESTRUCTURALES EN LA FUENTE POA"
            banner_sub = "No se pudieron procesar las actividades debido a inconsistencias en el archivo."
        elif has_rejections:
            banner_bg = ("#E65100", "#BF360C")
            banner_title = "⚠️ INGESTIÓN PARCIAL DE ACTIVIDADES POA"
            banner_sub = "Algunas actividades fueron aceptadas pero otras se rechazaron por falta de datos obligatorios."
        else:
            banner_bg = ("#2E7D32", "#1B5E20")
            banner_title = "✓ INGESTIÓN COMPLETADA EXITOSAMENTE"
            banner_sub = "Las actividades del Plan Operativo Anual (POA) fueron incorporadas a la base institucional."

        banner = ctk.CTkFrame(self, fg_color=banner_bg[0], corner_radius=0)
        banner.grid(row=0, column=0, sticky="ew")
        banner.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            banner,
            text=banner_title,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="white",
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=(10, 2), sticky="w")

        ctk.CTkLabel(
            banner,
            text=banner_sub,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#E0E0E0",
            anchor="w",
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        # 2. Métricas y Metadatos de la Fuente
        summary_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray18"), corner_radius=6)
        summary_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 6))
        summary_frame.grid_columnconfigure(0, weight=1)
        summary_frame.grid_columnconfigure(1, weight=1)
        summary_frame.grid_columnconfigure(2, weight=1)

        source_name = Path(self.report.source_file).name if self.report.source_file else "Desconocido"
        sheet_info = f"Hoja: {self.report.sheet_name}" if self.report.sheet_name else "Hoja automática"
        ctk.CTkLabel(
            summary_frame,
            text=f"Fuente: {source_name}  |  {sheet_info}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(8, 4), sticky="w")

        # Fila métricas
        m1_text = f"Filas examinadas: {self.report.total_rows_examined}\nAceptadas (creadas): {len(self.report.created_activity_ids)}"
        m2_text = f"Actualizadas in-place: {len(self.report.updated_activity_ids)}\nRechazadas: {self.report.rows_rejected}"
        m3_text = f"Duplicados / R-08: {len(self.report.duplicates_detected)}\nAdvertencias: {len(self.report.warnings)}"

        ctk.CTkLabel(summary_frame, text=m1_text, font=ctk.CTkFont(family="Segoe UI", size=11), justify="left", anchor="w").grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")
        ctk.CTkLabel(summary_frame, text=m2_text, font=ctk.CTkFont(family="Segoe UI", size=11), justify="left", anchor="w").grid(row=1, column=1, padx=12, pady=(0, 8), sticky="w")
        ctk.CTkLabel(summary_frame, text=m3_text, font=ctk.CTkFont(family="Segoe UI", size=11), justify="left", anchor="w").grid(row=1, column=2, padx=12, pady=(0, 8), sticky="w")

        # 3. Detalle scrollable de observaciones
        scroll_details = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll_details.grid(row=2, column=0, sticky="nsew", padx=16, pady=6)
        scroll_details.grid_columnconfigure(0, weight=1)

        row_idx = 0

        # Errores estructurales
        if self.report.errors:
            lbl_err_title = ctk.CTkLabel(
                scroll_details,
                text="Errores Estructurales de la Fuente:",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=("#C62828", "#EF5350"),
                anchor="w",
            )
            lbl_err_title.grid(row=row_idx, column=0, sticky="w", pady=(4, 2))
            row_idx += 1
            for err in self.report.errors:
                ctk.CTkLabel(
                    scroll_details,
                    text=f"• {err}",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=("#C62828", "#EF5350"),
                    wraplength=600,
                    justify="left",
                    anchor="w",
                ).grid(row=row_idx, column=0, sticky="w", padx=12, pady=1)
                row_idx += 1

        # Filas rechazadas con motivos
        if self.report.rejection_reasons:
            lbl_rej_title = ctk.CTkLabel(
                scroll_details,
                text="Filas Rechazadas (Datos Obligatorios o Inválidos):",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=("#D84315", "#FF7043"),
                anchor="w",
            )
            lbl_rej_title.grid(row=row_idx, column=0, sticky="w", pady=(8, 2))
            row_idx += 1
            for r_num, reason in self.report.rejection_reasons:
                ctk.CTkLabel(
                    scroll_details,
                    text=f"• {reason}",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    wraplength=600,
                    justify="left",
                    anchor="w",
                ).grid(row=row_idx, column=0, sticky="w", padx=12, pady=1)
                row_idx += 1

        # Duplicados / R-08
        if self.report.duplicates_detected:
            lbl_dup_title = ctk.CTkLabel(
                scroll_details,
                text="Notas de Deduplicación y Protección R-08:",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=("#0B3C5D", "#4FC3F7"),
                anchor="w",
            )
            lbl_dup_title.grid(row=row_idx, column=0, sticky="w", pady=(8, 2))
            row_idx += 1
            for dup in self.report.duplicates_detected:
                ctk.CTkLabel(
                    scroll_details,
                    text=f"• {dup}",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    wraplength=600,
                    justify="left",
                    anchor="w",
                ).grid(row=row_idx, column=0, sticky="w", padx=12, pady=1)
                row_idx += 1

        # Advertencias
        if self.report.warnings:
            lbl_warn_title = ctk.CTkLabel(
                scroll_details,
                text="Advertencias de Lectura:",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=("#F57F17", "#FFEE58"),
                anchor="w",
            )
            lbl_warn_title.grid(row=row_idx, column=0, sticky="w", pady=(8, 2))
            row_idx += 1
            for w in self.report.warnings:
                ctk.CTkLabel(
                    scroll_details,
                    text=f"• {w}",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    wraplength=600,
                    justify="left",
                    anchor="w",
                ).grid(row=row_idx, column=0, sticky="w", padx=12, pady=1)
                row_idx += 1

        if not self.report.errors and not self.report.rejection_reasons and not self.report.duplicates_detected and not self.report.warnings:
            ctk.CTkLabel(
                scroll_details,
                text="Todas las actividades examinadas fueron validadas y persistidas correctamente sin observaciones.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=("#2E7D32", "#81C784"),
                anchor="w",
            ).grid(row=row_idx, column=0, sticky="w", padx=4, pady=12)

        # 4. Botón de cierre
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=10)
        ctk.CTkButton(
            bottom_frame,
            text="Aceptar y Cerrar",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            width=140,
            height=32,
            corner_radius=4,
            command=self.destroy,
        ).pack(side="right")


class PlannedActivitiesListView(ctk.CTkFrame):
    """Componente visual para explorar y filtrar actividades del POA institucional."""

    def __init__(
        self,
        master: Any,
        service: PlanningUIService,
        on_select_activity: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.service = service
        self.on_select_activity = on_select_activity

        self._init_ui()
        self.refrescar_actividades()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # 1. PANEL DE BÚSQUEDA Y FILTROS
        # ---------------------------------------------------------------------
        filter_panel = ctk.CTkFrame(self, fg_color=("gray95", "gray20"), corner_radius=6)
        filter_panel.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        filter_panel.grid_columnconfigure(1, weight=1)

        # Fila 1: Búsqueda textual
        lbl_search = ctk.CTkLabel(
            filter_panel,
            text="Buscar:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        lbl_search.grid(row=0, column=0, padx=(12, 6), pady=10, sticky="w")

        self.txt_search = ctk.CTkEntry(
            filter_panel,
            placeholder_text="Escriba el nombre de la actividad o código institucional (POA)...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=32,
        )
        self.txt_search.grid(row=0, column=1, padx=6, pady=10, sticky="ew")
        self.txt_search.bind("<Return>", lambda _: self.refrescar_actividades())

        # Fila 2: Filtros desplegables y botones
        subfilter_frame = ctk.CTkFrame(filter_panel, fg_color="transparent")
        subfilter_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))

        lbl_sede = ctk.CTkLabel(
            subfilter_frame,
            text="Sede:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        lbl_sede.pack(side="left", padx=(0, 6))

        self.opt_sede = ctk.CTkOptionMenu(
            subfilter_frame,
            values=SEDES_BICU,
            width=130,
            height=30,
            command=lambda _: self.refrescar_actividades(),
        )
        self.opt_sede.set("Todas")
        self.opt_sede.pack(side="left", padx=(0, 16))

        lbl_estado = ctk.CTkLabel(
            subfilter_frame,
            text="Estado Diseño:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        lbl_estado.pack(side="left", padx=(0, 6))

        self.opt_estado = ctk.CTkOptionMenu(
            subfilter_frame,
            values=ESTADOS_DISENO,
            width=140,
            height=30,
            command=lambda _: self.refrescar_actividades(),
        )
        self.opt_estado.set("Todos")
        self.opt_estado.pack(side="left", padx=(0, 16))

        btn_buscar = ctk.CTkButton(
            subfilter_frame,
            text="Buscar / Filtrar",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            width=120,
            height=30,
            command=self.refrescar_actividades,
        )
        btn_buscar.pack(side="left", padx=(0, 8))

        btn_limpiar = ctk.CTkButton(
            subfilter_frame,
            text="Limpiar",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=("gray75", "gray35"),
            text_color=("black", "white"),
            hover_color=("gray65", "gray45"),
            width=80,
            height=30,
            command=self._limpiar_filtros,
        )
        btn_limpiar.pack(side="left")

        btn_cargar_poa = ctk.CTkButton(
            subfilter_frame,
            text="📥 Cargar Matriz POA (.xlsx)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            height=30,
            command=self._on_click_cargar_poa,
        )
        btn_cargar_poa.pack(side="right")

        # ---------------------------------------------------------------------
        # 2. LISTA DE ACTIVIDADES (SCROLLABLE)
        # ---------------------------------------------------------------------
        self.list_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_container.grid(row=1, column=0, sticky="nsew", padx=16, pady=6)
        self.list_container.grid_columnconfigure(0, weight=1)

        # ---------------------------------------------------------------------
        # 3. BARRA DE ESTADO / TOTALES
        # ---------------------------------------------------------------------
        status_bar = ctk.CTkFrame(self, fg_color="transparent", height=24)
        status_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 8))

        self.lbl_totals = ctk.CTkLabel(
            status_bar,
            text="Cargando actividades...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        self.lbl_totals.pack(side="left")

    def _on_click_cargar_poa(self) -> None:
        """Abre el selector de archivos Excel para incorporar actividades POA."""
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar Matriz POA Institucional (Excel)",
            filetypes=[("Matriz POA institucional", "*.xlsx")],
        )
        if not file_path:
            return  # Cancelación limpia sin efectos secundarios

        try:
            report = self.service.ingest_planning_matrix(file_path)
            self._mostrar_reporte_ingestion(report)
            self.refrescar_actividades()
        except PlanningUIError as e:
            messagebox.showerror(
                "Error al Cargar Matriz POA",
                e.message,
                parent=self,
            )

    def _mostrar_reporte_ingestion(self, report: PlanningIngestionReportDTO) -> None:
        """Muestra el diálogo modal institucional con el resumen pericial de la ingestión."""
        try:
            dlg = IngestionReportDialog(self, report=report)
            dlg.wait_window()
        except Exception:
            # Fallback seguro
            msg = (
                f"Matriz POA procesada:\n"
                f"• Filas examinadas: {report.total_rows_examined}\n"
                f"• Aceptadas (creadas): {len(report.created_activity_ids)}\n"
                f"• Actualizadas in-place: {len(report.updated_activity_ids)}\n"
                f"• Rechazadas: {report.rows_rejected}"
            )
            messagebox.showinfo("Resumen de Ingestión POA", msg, parent=self)

    def _limpiar_filtros(self) -> None:
        self.txt_search.delete(0, tk.END)
        self.opt_sede.set("Todas")
        self.opt_estado.set("Todos")
        self.refrescar_actividades()

    def refrescar_actividades(self) -> None:
        """Consulta el backend mediante PlanningUIService y repuebla la lista visual."""
        # Limpiar contenedor de filas
        for widget in self.list_container.winfo_children():
            widget.destroy()

        sede = self.opt_sede.get()
        estado = self.opt_estado.get()
        busqueda = self.txt_search.get()

        try:
            actividades = self.service.list_activities(
                sede=sede,
                status=estado,
                search_term=busqueda,
            )
        except PlanningUIError as e:
            messagebox.showerror("Error al Consultar Actividades", e.message)
            self.lbl_totals.configure(text="Error al consultar actividades.")
            return

        self.lbl_totals.configure(text=f"Total actividades registradas en el POA: {len(actividades)}")

        if not actividades:
            lbl_empty = ctk.CTkLabel(
                self.list_container,
                text="No se encontraron actividades planificadas con los criterios seleccionados.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color="gray",
                anchor="center",
            )
            lbl_empty.grid(row=0, column=0, pady=40)
            return

        for idx, act in enumerate(actividades):
            self._render_activity_card(idx, act)

    def _render_activity_card(self, row_idx: int, act: PlannedActivitySummaryDTO) -> None:
        card = ctk.CTkFrame(
            self.list_container,
            fg_color=("gray92", "gray17"),
            corner_radius=6,
            border_width=1,
            border_color=("gray80", "gray25"),
        )
        card.grid(row=row_idx, column=0, sticky="ew", pady=4, padx=2)
        card.grid_columnconfigure(1, weight=1)

        # Columna 0: Badge de Código Institucional
        lbl_code = ctk.CTkLabel(
            card,
            text=act.planning_id,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
            width=180,
        )
        lbl_code.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

        # Columna 1: Nombre de Actividad y Metadatos
        lbl_name = ctk.CTkLabel(
            card,
            text=act.activity_name,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
            wraplength=450,
            justify="left",
        )
        lbl_name.grid(row=0, column=1, padx=8, pady=(10, 2), sticky="w")

        info_text = f"Sede: {act.sede}  |  Área: {act.area_responsable}  |  Meta: {act.total_participants} protagonistas"
        lbl_info = ctk.CTkLabel(
            card,
            text=info_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        lbl_info.grid(row=1, column=1, padx=8, pady=(0, 10), sticky="w")

        # Columna 2: Estado del Diseño (Badge visual)
        badge_color, badge_text = self._get_status_badge_info(act.design_status)
        lbl_status = ctk.CTkLabel(
            card,
            text=badge_text,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=badge_color[0],
            text_color=badge_color[1],
            corner_radius=4,
            width=120,
            height=24,
        )
        lbl_status.grid(row=0, column=2, rowspan=2, padx=12, pady=10)

        # Columna 3: Botón de Acción
        btn_accion = ctk.CTkButton(
            card,
            text="Ver Ficha ➔",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            width=110,
            height=30,
            corner_radius=4,
            command=lambda ref=act.planning_id: self._on_click_select(ref),
        )
        btn_accion.grid(row=0, column=3, rowspan=2, padx=(0, 12), pady=10)

    def _get_status_badge_info(self, status: str) -> tuple[tuple[str, str], str]:
        """Retorna ((bg_color, fg_color), label_text) según el estado institucional."""
        if status == "APPROVED":
            return (("#2E7D32", "white"), "APROBADO")
        elif status == "DRAFT":
            return (("#E65100", "white"), "EN BORRADOR")
        elif status == "GENERATED":
            return (("#1565C0", "white"), "GENERADO")
        else:
            return (("gray70", "gray20"), "SIN DISEÑO")

    def _on_click_select(self, planning_id: str) -> None:
        if self.on_select_activity:
            self.on_select_activity(planning_id)
