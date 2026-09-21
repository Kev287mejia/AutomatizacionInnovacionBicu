"""
app.planning.ui.views.activities_list_view

Vista de Exploración y Filtrado de Actividades Planificadas (POA) — BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from app.planning.domain.dtos import PlannedActivitySummaryDTO
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
