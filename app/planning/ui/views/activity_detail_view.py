"""
app.planning.ui.views.activity_detail_view

Ficha de Detalle de Actividad Planificada (POA) — BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Any, Callable, Optional

import customtkinter as ctk

from app.planning.domain.dtos import PlannedActivityDetailDTO
from app.planning.ui.services.planning_ui_service import PlanningUIError, PlanningUIService


class PlannedActivityDetailView(ctk.CTkFrame):
    """Ficha de solo lectura con la información institucional de la actividad y acciones de diseño."""

    def __init__(
        self,
        master: Any,
        service: PlanningUIService,
        planning_id: str,
        on_volver_lista: Optional[Callable[[], None]] = None,
        on_editar_diseno: Optional[Callable[[str], None]] = None,
        on_exportar_docx: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.service = service
        self.planning_id = planning_id
        self.on_volver_lista = on_volver_lista
        self.on_editar_diseno = on_editar_diseno
        self.on_exportar_docx = on_exportar_docx

        self.activity_detail: Optional[PlannedActivityDetailDTO] = None

        self._init_ui()
        self.cargar_detalle()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO DE LA ACTIVIDAD
        # ---------------------------------------------------------------------
        self.header_card = ctk.CTkFrame(self, fg_color=("gray95", "gray20"), corner_radius=6)
        self.header_card.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        self.header_card.grid_columnconfigure(0, weight=1)
        self.header_card.grid_columnconfigure(1, weight=0)

        self.lbl_title = ctk.CTkLabel(
            self.header_card,
            text="Cargando información de la actividad...",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            anchor="w",
            wraplength=700,
            justify="left",
        )
        self.lbl_title.grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        self.lbl_subtitle = ctk.CTkLabel(
            self.header_card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        self.lbl_subtitle.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        self.lbl_status_badge = ctk.CTkLabel(
            self.header_card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=4,
            width=130,
            height=28,
        )
        self.lbl_status_badge.grid(row=0, column=1, rowspan=2, padx=16, pady=12, sticky="e")

        # ---------------------------------------------------------------------
        # 2. CUERPO: TARJETAS DE DATOS INSTITUCIONALES Y METAS
        # ---------------------------------------------------------------------
        self.scroll_body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_body.grid(row=1, column=0, sticky="nsew", padx=16, pady=6)
        self.scroll_body.grid_columnconfigure(0, weight=3)
        self.scroll_body.grid_columnconfigure(1, weight=2)

        # Panel Izquierdo: Información General del POA
        self.panel_poa = ctk.CTkFrame(
            self.scroll_body,
            fg_color=("gray92", "gray17"),
            corner_radius=6,
            border_width=1,
            border_color=("gray80", "gray25"),
        )
        self.panel_poa.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
        self.panel_poa.grid_columnconfigure(1, weight=1)

        poa_title = ctk.CTkLabel(
            self.panel_poa,
            text="DATOS INSTITUCIONALES DEL POA",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        poa_title.grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 10), sticky="w")

        self.poa_fields_container = ctk.CTkFrame(self.panel_poa, fg_color="transparent")
        self.poa_fields_container.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))
        self.poa_fields_container.grid_columnconfigure(1, weight=1)

        # Panel Derecho: Metas Cuantitativas de Participantes
        self.panel_goals = ctk.CTkFrame(
            self.scroll_body,
            fg_color=("gray92", "gray17"),
            corner_radius=6,
            border_width=1,
            border_color=("gray80", "gray25"),
        )
        self.panel_goals.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)
        self.panel_goals.grid_columnconfigure(1, weight=1)

        goals_title = ctk.CTkLabel(
            self.panel_goals,
            text="METAS DE PARTICIPANTES (PROTAGONISTAS)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        goals_title.grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 10), sticky="w")

        self.goals_fields_container = ctk.CTkFrame(self.panel_goals, fg_color="transparent")
        self.goals_fields_container.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))
        self.goals_fields_container.grid_columnconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # 3. BARRA INFERIOR DE NAVEGACIÓN Y ACCIONES
        # ---------------------------------------------------------------------
        self.action_bar = ctk.CTkFrame(self, fg_color=("gray95", "gray20"), corner_radius=6)
        self.action_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 12))
        self.action_bar.grid_columnconfigure(0, weight=1)
        self.action_bar.grid_columnconfigure(1, weight=0)

        self.btn_volver = ctk.CTkButton(
            self.action_bar,
            text="← Volver al Listado",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=("gray75", "gray35"),
            text_color=("black", "white"),
            hover_color=("gray65", "gray45"),
            width=140,
            height=34,
            corner_radius=4,
            command=self._on_click_volver,
        )
        self.btn_volver.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        self.btn_action_container = ctk.CTkFrame(self.action_bar, fg_color="transparent")
        self.btn_action_container.grid(row=0, column=1, padx=14, pady=10, sticky="e")

    def cargar_detalle(self) -> None:
        """Carga la ficha técnica de la actividad desde el backend."""
        try:
            act = self.service.get_activity_detail(self.planning_id)
            if not act:
                messagebox.showerror(
                    "Actividad No Encontrada",
                    f"No fue posible localizar la actividad con referencia '{self.planning_id}'.",
                )
                if self.on_volver_lista:
                    self.on_volver_lista()
                return

            self.activity_detail = act
            self._populate_view(act)
        except PlanningUIError as e:
            messagebox.showerror("Error al Cargar Detalle", e.message)

    def _populate_view(self, act: PlannedActivityDetailDTO) -> None:
        # Encabezado
        self.lbl_title.configure(text=act.activity_name)
        self.lbl_subtitle.configure(text=f"Código Institucional: {act.planning_id}  |  Sede: {act.sede}")

        badge_color, badge_text = self._get_status_badge_info(act.design_status)
        self.lbl_status_badge.configure(
            text=badge_text,
            fg_color=badge_color[0],
            text_color=badge_color[1],
        )

        # Limpiar contenedores
        for w in self.poa_fields_container.winfo_children():
            w.destroy()
        for w in self.goals_fields_container.winfo_children():
            w.destroy()

        # Rellenar POA
        poa_rows = [
            ("Sede:", act.sede),
            ("Municipio / Depto:", f"{act.mun_sede or '—'}, {act.dep_sede or '—'}"),
            ("Área Responsable:", act.area_responsable),
            ("Departamento Resp.:", act.departamento_responsable or "—"),
            ("Eje Estratégico (C1):", act.eje_estrategia),
            ("Programa (C2):", act.programa),
            ("Tipo de Evento (C4):", act.tipo_evento),
            ("Propósito:", act.proposito or "Sin propósito especificado en POA"),
            ("Fecha Programada:", str(act.fecha_evento) if act.fecha_evento else "Por definir"),
            ("Código Presupuestario:", act.codigo_presupuestario or "—"),
            ("Convenio / Cooperantes:", act.convenio or act.entidades_cooperantes or "—"),
        ]

        for r_idx, (label, val) in enumerate(poa_rows):
            lbl_k = ctk.CTkLabel(
                self.poa_fields_container,
                text=label,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=("gray30", "gray75"),
                anchor="nw",
                width=150,
            )
            lbl_k.grid(row=r_idx, column=0, sticky="nw", padx=(0, 6), pady=3)

            lbl_v = ctk.CTkLabel(
                self.poa_fields_container,
                text=val,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                anchor="nw",
                wraplength=380,
                justify="left",
            )
            lbl_v.grid(row=r_idx, column=1, sticky="w", pady=3)

        # Rellenar Metas de Participantes
        goals = act.participant_goals
        if goals:
            goal_rows = [
                ("Estudiantes de Grado:", f"{goals.est_grado_total} (M: {goals.est_grado_m}, F: {goals.est_grado_f})"),
                ("Estudiantes de Postgrado:", f"{goals.est_postgrado_total} (M: {goals.est_postgrado_m}, F: {goals.est_postgrado_f})"),
                ("Docentes:", f"{goals.docentes_total} (M: {goals.docentes_m}, F: {goals.docentes_f})"),
                ("Administrativos:", f"{goals.administrativos_total} (M: {goals.administrativos_m}, F: {goals.administrativos_f})"),
                ("Externos:", f"{goals.externos_total} (M: {goals.externos_m}, F: {goals.externos_f})"),
                ("TOTAL PROTAGONISTAS:", f"{goals.total()}"),
            ]
        else:
            goal_rows = [("Total Protagonistas:", "0")]

        for r_idx, (label, val) in enumerate(goal_rows):
            is_total = "TOTAL" in label
            font_w = "bold" if is_total else "normal"
            color_v = ("#0B3C5D", "#4FC3F7") if is_total else ("gray20", "gray90")

            lbl_gk = ctk.CTkLabel(
                self.goals_fields_container,
                text=label,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=("gray30", "gray75"),
                anchor="nw",
                width=170,
            )
            lbl_gk.grid(row=r_idx, column=0, sticky="nw", padx=(0, 6), pady=4)

            lbl_gv = ctk.CTkLabel(
                self.goals_fields_container,
                text=val,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight=font_w),
                text_color=color_v,
                anchor="nw",
            )
            lbl_gv.grid(row=r_idx, column=1, sticky="w", pady=4)

        # Actualizar botones de acción según estado
        self._update_action_buttons(act)

    def _update_action_buttons(self, act: PlannedActivityDetailDTO) -> None:
        for w in self.btn_action_container.winfo_children():
            w.destroy()

        status = act.design_status

        if status == "SIN_DISENO":
            btn_crear = ctk.CTkButton(
                self.btn_action_container,
                text="Crear Diseño Metodológico  ➔",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color="#0B3C5D",
                hover_color="#07263D",
                height=34,
                corner_radius=4,
                command=self._on_click_crear_diseno,
            )
            btn_crear.pack(side="left", padx=4)

        elif status == "DRAFT":
            btn_editar = ctk.CTkButton(
                self.btn_action_container,
                text="Continuar Edición del Diseño  ➔",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color="#0B3C5D",
                hover_color="#07263D",
                height=34,
                corner_radius=4,
                command=self._on_click_editar_diseno,
            )
            btn_editar.pack(side="left", padx=4)

        elif status in ("APPROVED", "GENERATED"):
            btn_ver = ctk.CTkButton(
                self.btn_action_container,
                text="Ver Diseño (Solo Lectura)  ➔",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color=("gray60", "gray40"),
                hover_color=("gray50", "gray30"),
                height=34,
                corner_radius=4,
                command=self._on_click_editar_diseno,
            )
            btn_ver.pack(side="left", padx=4)

            btn_docx = ctk.CTkButton(
                self.btn_action_container,
                text="Generar Documento Word (.docx)  ➔",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color="#2E7D32",
                hover_color="#1B5E20",
                height=34,
                corner_radius=4,
                command=self._on_click_exportar_docx,
            )
            btn_docx.pack(side="left", padx=4)

    def _get_status_badge_info(self, status: str) -> tuple[tuple[str, str], str]:
        if status == "APPROVED":
            return (("#2E7D32", "white"), "APROBADO")
        elif status == "DRAFT":
            return (("#E65100", "white"), "EN BORRADOR")
        elif status == "GENERATED":
            return (("#1565C0", "white"), "GENERADO")
        else:
            return (("gray70", "gray20"), "SIN DISEÑO")

    def _on_click_crear_diseno(self) -> None:
        creador = simpledialog.askstring(
            "Crear Diseño Metodológico",
            "Ingrese el nombre o cargo del responsable de la planificación:",
            parent=self,
        )
        if not creador or not creador.strip():
            return

        try:
            self.service.create_design_draft(
                activity_ref=self.planning_id,
                created_by=creador.strip(),
            )
            if self.on_editar_diseno:
                self.on_editar_diseno(self.planning_id)
        except PlanningUIError as e:
            messagebox.showerror("Error al Crear Borrador", e.message)

    def _on_click_editar_diseno(self) -> None:
        if self.on_editar_diseno:
            self.on_editar_diseno(self.planning_id)

    def _on_click_exportar_docx(self) -> None:
        if self.on_exportar_docx:
            self.on_exportar_docx(self.planning_id)

    def _on_click_volver(self) -> None:
        if self.on_volver_lista:
            self.on_volver_lista()
