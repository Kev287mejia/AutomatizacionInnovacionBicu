"""
app.planning.ui.views.validation_dialog

Diálogo de Validación Institucional del Diseño Metodológico — BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import customtkinter as ctk

from app.planning.domain.dtos import ValidationReportDTO, ValidationResultDTO


class ValidationDialog(ctk.CTkToplevel):
    """Ventana modal que presenta el reporte de validación institucional de forma clara y amigable."""

    def __init__(
        self,
        master: Any,
        report: ValidationReportDTO,
        on_proceder_aprobacion: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.report = report
        self.on_proceder_aprobacion = on_proceder_aprobacion

        self.title("BICU — Validación Institucional del Diseño Metodológico")
        self.geometry("640x520")
        self.minsize(550, 420)
        self.grab_set()  # Modal

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO DE ESTADO GENERAL
        # ---------------------------------------------------------------------
        if self.report.is_valid:
            banner_color = ("#2E7D32", "#1B5E20")
            banner_title = "✓ DISEÑO VÁLIDO PARA APROBACIÓN INSTITUCIONAL"
            banner_desc = (
                "El diseño metodológico cumple satisfactoriamente con todas las "
                "reglas institucionales y los cinco bloques obligatorios de BICU."
            )
        else:
            banner_color = ("#C62828", "#B71C1C")
            banner_title = "⚠️ EXISTEN OBSERVACIONES BLOQUEANTES"
            banner_desc = (
                f"Se detectaron {len(self.report.errors)} observación(es) que deben corregirse "
                "antes de poder aprobar y exportar el documento oficial."
            )

        header_frame = ctk.CTkFrame(self, fg_color=banner_color[0], corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        lbl_header_title = ctk.CTkLabel(
            header_frame,
            text=banner_title,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="white",
            anchor="w",
        )
        lbl_header_title.grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        lbl_header_desc = ctk.CTkLabel(
            header_frame,
            text=banner_desc,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#F5F5F5",
            anchor="w",
            wraplength=580,
            justify="left",
        )
        lbl_header_desc.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # ---------------------------------------------------------------------
        # 2. LISTA DE OBSERVACIONES (SCROLLABLE)
        # ---------------------------------------------------------------------
        scroll_list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll_list.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        scroll_list.grid_columnconfigure(0, weight=1)

        # Mostrar errores
        for idx, err in enumerate(self.report.errors):
            self._render_result_item(scroll_list, idx, err, is_error=True)

        # Mostrar advertencias
        start_warn_idx = len(self.report.errors)
        for idx, warn in enumerate(self.report.warnings, start=start_warn_idx):
            self._render_result_item(scroll_list, idx, warn, is_error=False)

        if not self.report.errors and not self.report.warnings:
            lbl_clean = ctk.CTkLabel(
                scroll_list,
                text="No hay errores ni advertencias. Todo se encuentra en orden.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="gray",
                anchor="center",
            )
            lbl_clean.pack(pady=40)

        # ---------------------------------------------------------------------
        # 3. BARRA DE ACCIÓN INFERIOR
        # ---------------------------------------------------------------------
        action_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        action_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        action_frame.grid_columnconfigure(0, weight=1)

        btn_cerrar = ctk.CTkButton(
            action_frame,
            text="Cerrar",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=("gray75", "gray35"),
            text_color=("black", "white"),
            hover_color=("gray65", "gray45"),
            width=100,
            height=32,
            command=self.destroy,
        )
        btn_cerrar.pack(side="right", padx=(8, 0))

        if self.report.is_valid and self.on_proceder_aprobacion:
            btn_aprobar = ctk.CTkButton(
                action_frame,
                text="Proceder a Aprobación Formal  ➔",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color="#2E7D32",
                hover_color="#1B5E20",
                height=32,
                command=self._on_click_proceder,
            )
            btn_aprobar.pack(side="right")

    def _render_result_item(
        self,
        parent: Any,
        idx: int,
        item: ValidationResultDTO,
        is_error: bool,
    ) -> None:
        item_frame = ctk.CTkFrame(
            parent,
            fg_color=("gray95", "gray20"),
            corner_radius=4,
            border_width=1,
            border_color="#C62828" if is_error else "#F57C00",
        )
        item_frame.grid(row=idx, column=0, sticky="ew", pady=4, padx=2)
        item_frame.grid_columnconfigure(1, weight=1)

        badge_text = "ERROR" if is_error else "ADVERTENCIA"
        badge_bg = "#C62828" if is_error else "#F57C00"

        badge = ctk.CTkLabel(
            item_frame,
            text=badge_text,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=badge_bg,
            text_color="white",
            corner_radius=3,
            width=85,
            height=20,
        )
        badge.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="nw")

        lbl_msg = ctk.CTkLabel(
            item_frame,
            text=item.message,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
            wraplength=460,
            justify="left",
        )
        lbl_msg.grid(row=0, column=1, padx=6, pady=(8, 4), sticky="w")

        if item.field:
            lbl_field = ctk.CTkLabel(
                item_frame,
                text=f"Campo afectado: {item.field}",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=("gray40", "gray70"),
                anchor="w",
            )
            lbl_field.grid(row=1, column=1, padx=6, pady=(0, 6), sticky="w")

    def _on_click_proceder(self) -> None:
        self.destroy()
        if self.on_proceder_aprobacion:
            self.on_proceder_aprobacion()
