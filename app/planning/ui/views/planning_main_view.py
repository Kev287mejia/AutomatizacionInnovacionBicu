"""
app.planning.ui.views.planning_main_view

Contenedor Principal e Integrador de Navegación del Módulo 3 — Planificación Institucional BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from app.planning.ui.services.planning_ui_service import PlanningUIError, PlanningUIService
from app.planning.ui.views.activities_list_view import PlannedActivitiesListView
from app.planning.ui.views.activity_detail_view import PlannedActivityDetailView
from app.planning.ui.views.design_editor_view import MethodologicalDesignEditorView


class PlanningMainView(ctk.CTkFrame):
    """Vista raíz del Módulo 3 que coordina la navegación entre Lista, Detalle y Editor."""

    def __init__(
        self,
        master: Any,
        on_volver_menu: Optional[Callable[[], None]] = None,
        service: Optional[PlanningUIService] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_volver_menu = on_volver_menu
        self.service = service or PlanningUIService()

        self._active_planning_id: Optional[str] = None
        self._current_subview: Optional[ctk.CTkFrame] = None

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO INSTITUCIONAL
        # ---------------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color=("#0B3C5D", "#1A2634"), corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title_lbl = ctk.CTkLabel(
            header,
            text="BLUEFIELDS INDIAN & CARIBBEAN UNIVERSITY — BICU",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="white",
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, padx=20, pady=(12, 2), sticky="w")

        sub_lbl = ctk.CTkLabel(
            header,
            text="Módulo 3: Planificación y Diseño Metodológico de Actividades Institucionales",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#E0E0E0", "#B0BEC5"),
            anchor="w",
        )
        sub_lbl.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        if self.on_volver_menu:
            btn_volver = ctk.CTkButton(
                header,
                text="← Menú Principal",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#1A2634",
                hover_color="#07263D",
                width=130,
                height=32,
                corner_radius=5,
                command=self.on_volver_menu,
            )
            btn_volver.grid(row=0, column=1, rowspan=2, padx=15, pady=10, sticky="e")

        # ---------------------------------------------------------------------
        # 2. CONTENEDOR DE SUBVISTAS INTERCAMBIABLES
        # ---------------------------------------------------------------------
        self.subview_container = ctk.CTkFrame(self, fg_color="transparent")
        self.subview_container.grid(row=1, column=0, sticky="nsew")
        self.subview_container.grid_columnconfigure(0, weight=1)
        self.subview_container.grid_rowconfigure(0, weight=1)

    def _switch_subview(self, new_subview: ctk.CTkFrame) -> None:
        """Oculta la subvista actual y posiciona la nueva en el contenedor."""
        if self._current_subview:
            self._current_subview.destroy()
        self._current_subview = new_subview
        self._current_subview.grid(row=0, column=0, sticky="nsew")

    # -------------------------------------------------------------------------
    # RUTAS DE NAVEGACIÓN
    # -------------------------------------------------------------------------
    def mostrar_lista_actividades(self) -> None:
        """Navega a la Vista 1: Lista de Actividades Planificadas."""
        view = PlannedActivitiesListView(
            self.subview_container,
            service=self.service,
            on_select_activity=self.mostrar_detalle_actividad,
        )
        self._switch_subview(view)

    def mostrar_detalle_actividad(self, planning_id: str) -> None:
        """Navega a la Vista 2: Detalle de Actividad Planificada."""
        self._active_planning_id = planning_id
        view = PlannedActivityDetailView(
            self.subview_container,
            service=self.service,
            planning_id=planning_id,
            on_volver_lista=self.mostrar_lista_actividades,
            on_editar_diseno=self.mostrar_editor_diseno,
            on_exportar_docx=self._exportar_docx_directo,
        )
        self._switch_subview(view)

    def mostrar_editor_diseno(self, planning_id: str) -> None:
        """Navega a la Vista 3: Editor de Diseño Metodológico."""
        self._active_planning_id = planning_id
        view = MethodologicalDesignEditorView(
            self.subview_container,
            service=self.service,
            planning_id=planning_id,
            on_volver_detalle=lambda: self.mostrar_detalle_actividad(planning_id),
        )
        self._switch_subview(view)

    def _exportar_docx_directo(self, planning_id: str) -> None:
        """Exporta directamente a DOCX desde la vista de detalle para diseños aprobados."""
        try:
            detail = self.service.get_activity_detail(planning_id)
            if not detail or not detail.design_id:
                messagebox.showerror("Error", "No se encontró diseño metodológico para esta actividad.")
                return

            default_name = f"Diseno_Metodologico_{planning_id}.docx"
            file_path = filedialog.asksaveasfilename(
                parent=self,
                title="Guardar Diseño Metodológico Oficial en Word",
                initialfile=default_name,
                defaultextension=".docx",
                filetypes=[("Documento de Microsoft Word", "*.docx")],
            )
            if not file_path:
                return

            out_file = self.service.export_docx(
                design_id=detail.design_id,
                output_path=file_path,
            )
            messagebox.showinfo(
                "Documento Word Generado",
                f"El documento oficial se generó exitosamente en:\n{out_file}",
            )
        except PlanningUIError as e:
            messagebox.showerror("Error al Exportar Documento", e.message)
