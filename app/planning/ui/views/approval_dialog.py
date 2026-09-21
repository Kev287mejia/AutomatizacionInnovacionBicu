"""
app.planning.ui.views.approval_dialog

Diálogo Modal de Aprobación Formal del Diseño Metodológico (Regla R-08) — BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk


class ApprovalDialog(ctk.CTkToplevel):
    """Ventana modal de confirmación formal para sellar un diseño metodológico (R-08)."""

    def __init__(
        self,
        master: Any,
        activity_name: str,
        planning_id: str,
        on_confirm_approval: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.activity_name = activity_name
        self.planning_id = planning_id
        self.on_confirm_approval = on_confirm_approval

        self.title("BICU — Aprobación Formal del Diseño Metodológico")
        self.geometry("560x380")
        self.minsize(500, 340)
        self.resizable(False, False)
        self.grab_set()  # Modal

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO DE ADVERTENCIA INSTITUCIONAL
        # ---------------------------------------------------------------------
        banner = ctk.CTkFrame(self, fg_color="#0B3C5D", corner_radius=0)
        banner.grid(row=0, column=0, sticky="ew")
        banner.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            banner,
            text="APROBACIÓN FORMAL E INMUTABILIDAD INSTITUCIONAL",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="white",
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        sub_lbl = ctk.CTkLabel(
            banner,
            text=f"Actividad: {self.activity_name} ({self.planning_id})",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#E0E0E0",
            anchor="w",
        )
        sub_lbl.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # ---------------------------------------------------------------------
        # 2. CUERPO: ADVERTENCIA R-08 Y FORMULARIO DE APROBADOR
        # ---------------------------------------------------------------------
        body_frame = ctk.CTkFrame(self, fg_color="transparent")
        body_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=14)
        body_frame.grid_columnconfigure(0, weight=1)

        # Tarjeta de Alerta R-08
        warning_card = ctk.CTkFrame(
            body_frame,
            fg_color=("#FFF3E0", "#3E2723"),
            corner_radius=6,
            border_width=1,
            border_color=("#FFE0B2", "#5D4037"),
        )
        warning_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        warning_card.grid_columnconfigure(0, weight=1)

        warn_text = (
            "⚠️ REGLA R-08 — INMUTABILIDAD ESTRICTA:\n"
            "Al confirmar la aprobación formal, este diseño metodológico quedará sellado "
            "de forma definitiva. No podrá volver a ser editado, modificado ni reabierto. "
            "A partir de este momento, únicamente podrá ser generado como documento oficial Word (.docx)."
        )
        lbl_warn = ctk.CTkLabel(
            warning_card,
            text=warn_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#BF360C", "#FFCCBC"),
            anchor="w",
            wraplength=490,
            justify="left",
        )
        lbl_warn.grid(row=0, column=0, padx=14, pady=12, sticky="w")

        # Entrada del nombre de aprobador
        lbl_prompt = ctk.CTkLabel(
            body_frame,
            text="Nombre y cargo del aprobador institucional (obligatorio):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            anchor="w",
        )
        lbl_prompt.grid(row=1, column=0, sticky="w", pady=(0, 4))

        self.txt_approver = ctk.CTkEntry(
            body_frame,
            placeholder_text="Ej: Dra. Kenia Mejia — Directora de Innovación y Emprendimiento",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34,
        )
        self.txt_approver.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.txt_approver.focus()

        # ---------------------------------------------------------------------
        # 3. BOTONES DE ACCIÓN
        # ---------------------------------------------------------------------
        btn_container = ctk.CTkFrame(self, fg_color="transparent")
        btn_container.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))

        btn_cancelar = ctk.CTkButton(
            btn_container,
            text="Cancelar",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=("gray75", "gray35"),
            text_color=("black", "white"),
            hover_color=("gray65", "gray45"),
            width=110,
            height=34,
            command=self.destroy,
        )
        btn_cancelar.pack(side="right", padx=(8, 0))

        btn_confirmar = ctk.CTkButton(
            btn_container,
            text="Confirmar y Aprobar Formalmente",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            height=34,
            command=self._on_click_confirmar,
        )
        btn_confirmar.pack(side="right")

    def _on_click_confirmar(self) -> None:
        approver = self.txt_approver.get().strip()
        if not approver:
            messagebox.showwarning(
                "Aprobador Requerido",
                "Debe ingresar el nombre y cargo del aprobador institucional para continuar.",
                parent=self,
            )
            return

        self.destroy()
        self.on_confirm_approval(approver)
