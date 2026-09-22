"""
app.planning.ui.views.ai_proposal_review_dialog

Diálogo Modal de Revisión Humana para Propuestas de Asistencia IA — BICU.
Fase 29.15 — Integración de Asistencia IA en la UI Institucional.

Permite al responsable institucional examinar comparativamente el contenido
actual del diseño frente a la propuesta generada por el núcleo de asistencia IA.
Garantiza el principio rector: la IA propone, el ser humano revisa, decide y valida.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Any, Callable, Optional

import customtkinter as ctk

from app.planning.domain.dtos import AIProposalDTO


class AIProposalReviewDialog(ctk.CTkToplevel):
    """Ventana modal de revisión humana de propuestas de asistencia de IA."""

    def __init__(
        self,
        master: Any,
        proposal: AIProposalDTO,
        current_content: str,
        field_label: str,
        on_accept: Callable[[AIProposalDTO, str], None],
        on_reject: Callable[[AIProposalDTO, str, str], None],
        on_cancel: Optional[Callable[[], None]] = None,
        default_reviewer: str = "Responsable Institucional",
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.proposal = proposal
        self.current_content = current_content
        self.field_label = field_label
        self.on_accept = on_accept
        self.on_reject = on_reject
        self.on_cancel = on_cancel
        self.default_reviewer = default_reviewer

        self.title("BICU — Revisión de Propuesta de Asistencia IA")
        self.geometry("700x620")
        self.minsize(620, 520)
        self.grab_set()  # Comportamiento modal estricto

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO INSTITUCIONAL
        # ---------------------------------------------------------------------
        banner = ctk.CTkFrame(self, fg_color=("#0B3C5D", "#1A2634"), corner_radius=0)
        banner.grid(row=0, column=0, sticky="ew")
        banner.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            banner,
            text="REVISIÓN INSTITUCIONAL DE PROPUESTA DE ASISTENCIA IA",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="white",
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        confidence_pct = int(self.proposal.confidence * 100)
        sub_lbl = ctk.CTkLabel(
            banner,
            text=(
                f"Campo asistido: {self.field_label} | "
                f"Asistencia Local (Mock determinístico) | "
                f"Confianza: {confidence_pct}%"
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#E0E0E0", "#B0BEC5"),
            anchor="w",
        )
        sub_lbl.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # ---------------------------------------------------------------------
        # 2. ADVERTENCIA DE CONTROL HUMANO (PRINCIPIO RECTOR)
        # ---------------------------------------------------------------------
        info_card = ctk.CTkFrame(
            self,
            fg_color=("#E3F2FD", "#1E293B"),
            corner_radius=6,
            border_width=1,
            border_color=("#90CAF9", "#334155"),
        )
        info_card.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 6))
        info_card.grid_columnconfigure(0, weight=1)

        lbl_info = ctk.CTkLabel(
            info_card,
            text=(
                "ℹ️ Esta propuesta fue generada como un borrador de apoyo para consideración humana. "
                "La decisión de incorporarla al diseño corresponde exclusivamente al responsable institucional. "
                "Al aceptar, el diseño permanecerá en estado BORRADOR (DRAFT)."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#0D47A1", "#90CAF9"),
            anchor="w",
            wraplength=640,
            justify="left",
        )
        lbl_info.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        # ---------------------------------------------------------------------
        # 3. CUERPO COMPARATIVO: TEXTO ACTUAL VS PROPUESTA IA
        # ---------------------------------------------------------------------
        body_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body_scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=6)
        body_scroll.grid_columnconfigure(0, weight=1)

        # Sección: Texto Actual
        lbl_current = ctk.CTkLabel(
            body_scroll,
            text="TEXTO ACTUAL EN EL DISEÑO:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        lbl_current.pack(fill="x", pady=(4, 2))

        self.txt_current = ctk.CTkTextbox(
            body_scroll,
            height=100,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=("gray95", "gray18"),
        )
        self.txt_current.pack(fill="x", pady=(0, 10))
        self.txt_current.insert("1.0", self.current_content or "(Campo actualmente vacío)")
        self.txt_current.configure(state="disabled")

        # Sección: Propuesta de IA
        lbl_proposed = ctk.CTkLabel(
            body_scroll,
            text="PROPUESTA SUGERIDA POR ASISTENCIA IA:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#2E7D32", "#81C784"),
            anchor="w",
        )
        lbl_proposed.pack(fill="x", pady=(4, 2))

        self.txt_proposed = ctk.CTkTextbox(
            body_scroll,
            height=140,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=("gray95", "gray18"),
        )
        self.txt_proposed.pack(fill="x", pady=(0, 10))
        self.txt_proposed.insert("1.0", self.proposal.proposed_content)
        self.txt_proposed.configure(state="disabled")

        # Sección: Revisor
        lbl_rev = ctk.CTkLabel(
            body_scroll,
            text="Funcionario Revisor / Responsable:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            anchor="w",
        )
        lbl_rev.pack(fill="x", pady=(4, 2))

        self.ent_reviewer = ctk.CTkEntry(
            body_scroll,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self.ent_reviewer.pack(fill="x", pady=(0, 6))
        self.ent_reviewer.insert(0, self.default_reviewer)

        # ---------------------------------------------------------------------
        # 4. BARRA INFERIOR DE ACCIONES (ACEPTAR / RECHAZAR / CANCELAR)
        # ---------------------------------------------------------------------
        bottom_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray20"), corner_radius=6)
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 12))
        bottom_frame.grid_columnconfigure(0, weight=1)

        btn_cancel = ctk.CTkButton(
            bottom_frame,
            text="Cancelar",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=("gray75", "gray35"),
            text_color=("black", "white"),
            hover_color=("gray65", "gray45"),
            width=100,
            height=32,
            command=self._on_click_cancel,
        )
        btn_cancel.pack(side="left", padx=12, pady=10)

        btn_reject = ctk.CTkButton(
            bottom_frame,
            text="✕ Rechazar Propuesta",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=("#C62828", "#B71C1C"),
            hover_color="#8E0000",
            width=160,
            height=32,
            command=self._on_click_reject,
        )
        btn_reject.pack(side="right", padx=(6, 12), pady=10)

        btn_accept = ctk.CTkButton(
            bottom_frame,
            text="✓ Aceptar Propuesta",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            width=160,
            height=32,
            command=self._on_click_accept,
        )
        btn_accept.pack(side="right", padx=6, pady=10)

    def _on_click_accept(self) -> None:
        reviewer = self.ent_reviewer.get().strip()
        if not reviewer:
            messagebox.showwarning(
                "Revisor Requerido",
                "Debe indicar el nombre del funcionario que revisa y acepta esta propuesta.",
                parent=self,
            )
            return

        try:
            self.on_accept(self.proposal, reviewer)
            self.destroy()
        except Exception as e:
            messagebox.showerror(
                "Error al Aceptar Propuesta",
                f"No fue posible aplicar la propuesta: {e}",
                parent=self,
            )

    def _on_click_reject(self) -> None:
        reviewer = self.ent_reviewer.get().strip()
        if not reviewer:
            messagebox.showwarning(
                "Revisor Requerido",
                "Debe indicar el nombre del funcionario que revisa y rechaza esta propuesta.",
                parent=self,
            )
            return

        reason = simpledialog.askstring(
            "Motivo de Rechazo Institucional",
            "Ingrese el motivo del rechazo (obligatorio para fines de auditoría institucional):",
            parent=self,
        )

        if reason is None:
            # Usuario canceló el cuadro de diálogo
            return

        clean_reason = reason.strip()
        if not clean_reason:
            messagebox.showwarning(
                "Motivo Obligatorio",
                "El motivo del rechazo es obligatorio y no puede estar vacío.",
                parent=self,
            )
            return

        try:
            self.on_reject(self.proposal, reviewer, clean_reason)
            self.destroy()
        except Exception as e:
            messagebox.showerror(
                "Error al Rechazar Propuesta",
                f"No fue posible registrar el rechazo: {e}",
                parent=self,
            )

    def _on_click_cancel(self) -> None:
        if self.on_cancel:
            self.on_cancel()
        self.destroy()
