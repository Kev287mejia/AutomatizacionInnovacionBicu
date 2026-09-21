"""
app.planning.ui.views.design_editor_view

Editor de los Cinco Bloques del Diseño Metodológico — BICU.
Fase 29.11 — Implementación Controlada de la UI de Planificación Institucional.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, List, Optional
import uuid

import customtkinter as ctk

from app.planning.domain.dtos import (
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    TimeBlockDTO,
    UpdateMethodologicalDesignCommand,
    ValidationReportDTO,
)
from app.planning.ui.services.planning_ui_service import PlanningUIError, PlanningUIService
from app.planning.ui.views.approval_dialog import ApprovalDialog
from app.planning.ui.views.validation_dialog import ValidationDialog


class MethodologicalDesignEditorView(ctk.CTkFrame):
    """Editor completo de los 5 bloques metodológicos con validación y aprobación integrada."""

    def __init__(
        self,
        master: Any,
        service: PlanningUIService,
        planning_id: str,
        on_volver_detalle: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.service = service
        self.planning_id = planning_id
        self.on_volver_detalle = on_volver_detalle

        self.design_dto: Optional[MethodologicalDesignDTO] = None
        self.is_dirty: bool = False

        # Listas dinámicas en memoria para Agenda y Matriz Operativa
        self.agenda_items: List[TimeBlockDTO] = []
        self.matrix_items: List[OperationalActivityDTO] = []

        self._init_ui()
        self.cargar_diseno()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO SUPERIOR DEL EDITOR
        # ---------------------------------------------------------------------
        self.header_card = ctk.CTkFrame(self, fg_color=("gray95", "gray20"), corner_radius=6)
        self.header_card.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        self.header_card.grid_columnconfigure(1, weight=1)

        btn_volver = ctk.CTkButton(
            self.header_card,
            text="← Volver a la Ficha",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=("gray75", "gray35"),
            text_color=("black", "white"),
            hover_color=("gray65", "gray45"),
            width=130,
            height=30,
            command=self._on_click_volver,
        )
        btn_volver.grid(row=0, column=0, padx=12, pady=10, sticky="w")

        self.lbl_header_title = ctk.CTkLabel(
            self.header_card,
            text="Editor de Diseño Metodológico",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
            wraplength=600,
            justify="left",
        )
        self.lbl_header_title.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.lbl_status_badge = ctk.CTkLabel(
            self.header_card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=4,
            width=120,
            height=26,
        )
        self.lbl_status_badge.grid(row=0, column=2, padx=14, pady=10, sticky="e")

        # ---------------------------------------------------------------------
        # 2. PESTAÑAS DE LOS CINCO BLOQUES (Tabview)
        # ---------------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=16, pady=6)

        self.tab_b1 = self.tabview.add("1. Introducción y Enfoque")
        self.tab_b2 = self.tabview.add("2. Objetivos")
        self.tab_b3 = self.tabview.add("3. Preguntas Frecuentes (FAQ)")
        self.tab_b4 = self.tabview.add("4. Programa / Agenda")
        self.tab_b5 = self.tabview.add("5. Matriz Operativa")

        self._setup_bloque_1()
        self._setup_bloque_2()
        self._setup_bloque_3()
        self._setup_bloque_4()
        self._setup_bloque_5()

        # ---------------------------------------------------------------------
        # 3. BARRA INFERIOR DE ACCIONES
        # ---------------------------------------------------------------------
        self.bottom_bar = ctk.CTkFrame(self, fg_color=("gray95", "gray20"), corner_radius=6)
        self.bottom_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 12))
        self.bottom_bar.grid_columnconfigure(0, weight=1)

        self.lbl_save_status = ctk.CTkLabel(
            self.bottom_bar,
            text="Listo para editar.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        self.lbl_save_status.pack(side="left", padx=16, pady=8)

        self.action_buttons_frame = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        self.action_buttons_frame.pack(side="right", padx=12, pady=8)

    # -------------------------------------------------------------------------
    # CONFIGURACIÓN DE PESTAÑAS (BLOQUES 1 A 5)
    # -------------------------------------------------------------------------
    def _setup_bloque_1(self) -> None:
        """Bloque 1: Introducción y Enfoque Metodológico."""
        self.tab_b1.grid_columnconfigure(0, weight=1)
        self.tab_b1.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self.tab_b1, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        scroll.grid_columnconfigure(0, weight=1)

        lbl_intro = ctk.CTkLabel(
            scroll,
            text="Contexto y Vinculación Institucional (Introducción):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            anchor="w",
        )
        lbl_intro.pack(fill="x", pady=(8, 4))

        self.txt_intro = ctk.CTkTextbox(scroll, height=140, font=ctk.CTkFont(family="Segoe UI", size=11))
        self.txt_intro.pack(fill="x", pady=(0, 14))
        self.txt_intro.bind("<<Modified>>", self._on_field_modified)

        lbl_enfoque = ctk.CTkLabel(
            scroll,
            text="Enfoque Metodológico Institucional:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            anchor="w",
        )
        lbl_enfoque.pack(fill="x", pady=(4, 4))

        self.txt_enfoque = ctk.CTkTextbox(scroll, height=110, font=ctk.CTkFont(family="Segoe UI", size=11))
        self.txt_enfoque.pack(fill="x", pady=(0, 8))
        self.txt_enfoque.bind("<<Modified>>", self._on_field_modified)

    def _setup_bloque_2(self) -> None:
        """Bloque 2: Exactamente dos (2) objetivos específicos (R-07)."""
        self.tab_b2.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self.tab_b2, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure(0, weight=1)

        info_lbl = ctk.CTkLabel(
            scroll,
            text="📌 REGLA R-07: La actividad debe definir exactamente dos (2) objetivos específicos.",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        info_lbl.pack(fill="x", pady=(8, 12))

        lbl_obj1 = ctk.CTkLabel(
            scroll,
            text="Objetivo Específico 1:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            anchor="w",
        )
        lbl_obj1.pack(fill="x", pady=(4, 2))

        self.txt_obj1 = ctk.CTkTextbox(scroll, height=75, font=ctk.CTkFont(family="Segoe UI", size=11))
        self.txt_obj1.pack(fill="x", pady=(0, 14))
        self.txt_obj1.bind("<<Modified>>", self._on_field_modified)

        lbl_obj2 = ctk.CTkLabel(
            scroll,
            text="Objetivo Específico 2:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            anchor="w",
        )
        lbl_obj2.pack(fill="x", pady=(4, 2))

        self.txt_obj2 = ctk.CTkTextbox(scroll, height=75, font=ctk.CTkFont(family="Segoe UI", size=11))
        self.txt_obj2.pack(fill="x", pady=(0, 8))
        self.txt_obj2.bind("<<Modified>>", self._on_field_modified)

    def _setup_bloque_3(self) -> None:
        """Bloque 3: Preguntas Frecuentes (FAQ - 7 preguntas institucionales)."""
        scroll = ctk.CTkScrollableFrame(self.tab_b3, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure(0, weight=1)

        self.faq_entries = {}
        questions = [
            ("q1_que_es", "1. ¿En qué es esta actividad? (Sugerencia del POA):"),
            ("q2_para_que", "2. ¿Para qué se realiza? (Propósito / Justificación):"),
            ("q3_sesiones", "3. ¿Cuántas sesiones? (Default: Sesión única):"),
            ("q4_protagonistas", "4. ¿Cuánto son los protagonistas? (Metas POA):"),
            ("q5_facilitador", "5. ¿Quién va facilitar? (Área o facilitadores):"),
            ("q6_materiales", "6. ¿Qué materiales se requieren? (Obligatorio):"),
            ("q7_duracion", "7. ¿Cuánto tiempo dura? (Sincronizado con Agenda):"),
        ]

        for q_key, q_label in questions:
            lbl = ctk.CTkLabel(
                scroll,
                text=q_label,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                anchor="w",
            )
            lbl.pack(fill="x", pady=(6, 2))

            ent = ctk.CTkEntry(scroll, height=32, font=ctk.CTkFont(family="Segoe UI", size=11))
            ent.pack(fill="x", pady=(0, 6))
            ent.bind("<KeyRelease>", self._on_field_modified)
            self.faq_entries[q_key] = ent

    def _setup_bloque_4(self) -> None:
        """Bloque 4: Programa / Agenda de la actividad (Tabla 2)."""
        self.tab_b4.grid_columnconfigure(0, weight=1)
        self.tab_b4.grid_rowconfigure(1, weight=1)

        # Fila superior: Indicador de duración y controles de adición
        ctrl_frame = ctk.CTkFrame(self.tab_b4, fg_color=("gray95", "gray20"), corner_radius=6)
        ctrl_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        ctrl_frame.grid_columnconfigure(1, weight=1)

        lbl_add_act = ctk.CTkLabel(
            ctrl_frame,
            text="Fase / Actividad:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        )
        lbl_add_act.grid(row=0, column=0, padx=(10, 4), pady=10, sticky="w")

        self.txt_new_agenda_label = ctk.CTkEntry(
            ctrl_frame,
            placeholder_text="Ej: Bienvenida e Introducción...",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self.txt_new_agenda_label.grid(row=0, column=1, padx=4, pady=10, sticky="ew")

        lbl_add_min = ctk.CTkLabel(
            ctrl_frame,
            text="Minutos:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        )
        lbl_add_min.grid(row=0, column=2, padx=(10, 4), pady=10, sticky="w")

        self.txt_new_agenda_min = ctk.CTkEntry(
            ctrl_frame,
            placeholder_text="Min.",
            width=65,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self.txt_new_agenda_min.grid(row=0, column=3, padx=4, pady=10)

        self.btn_add_agenda = ctk.CTkButton(
            ctrl_frame,
            text="+ Agregar a Agenda",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            width=140,
            height=30,
            command=self._on_add_agenda_item,
        )
        self.btn_add_agenda.grid(row=0, column=4, padx=(8, 10), pady=10)

        # Fila central: Lista de bloques de tiempo
        self.scroll_agenda = ctk.CTkScrollableFrame(self.tab_b4, fg_color="transparent")
        self.scroll_agenda.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self.scroll_agenda.grid_columnconfigure(1, weight=1)

        # Fila inferior: Total de minutos
        self.lbl_agenda_total = ctk.CTkLabel(
            self.tab_b4,
            text="Duración Total de la Agenda: 0 minutos",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        self.lbl_agenda_total.grid(row=2, column=0, sticky="w", padx=12, pady=6)

    def _setup_bloque_5(self) -> None:
        """Bloque 5: Matriz de Planificación Operativa (Tabla 3)."""
        self.tab_b5.grid_columnconfigure(0, weight=1)
        self.tab_b5.grid_rowconfigure(1, weight=1)

        # Fila superior: Asistente para clonar desde agenda
        assist_frame = ctk.CTkFrame(self.tab_b5, fg_color=("gray95", "gray20"), corner_radius=6)
        assist_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        assist_frame.grid_columnconfigure(0, weight=1)

        lbl_info_r06 = ctk.CTkLabel(
            assist_frame,
            text="📌 REGLA R-06: La Matriz Operativa debe corresponder exactamente con la Agenda en cantidad y minutos.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        lbl_info_r06.pack(side="left", padx=12, pady=8)

        self.btn_sync_matrix = ctk.CTkButton(
            assist_frame,
            text="Sincronizar Fases desde Agenda  ➔",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=28,
            command=self._on_sync_matrix_from_agenda,
        )
        self.btn_sync_matrix.pack(side="right", padx=12, pady=8)

        # Fila central: Lista de actividades operativas
        self.scroll_matrix = ctk.CTkScrollableFrame(self.tab_b5, fg_color="transparent")
        self.scroll_matrix.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self.scroll_matrix.grid_columnconfigure(0, weight=1)

    # -------------------------------------------------------------------------
    # CARGA Y POBLADO DE DATOS
    # -------------------------------------------------------------------------
    def cargar_diseno(self) -> None:
        """Recupera el diseño metodológico desde el backend y puebla los campos."""
        try:
            act_detail = self.service.get_activity_detail(self.planning_id)
            if not act_detail:
                messagebox.showerror("Error", f"No se encontró la actividad '{self.planning_id}'.")
                return

            if act_detail.design_status == "SIN_DISENO" or not act_detail.design_id:
                messagebox.showinfo(
                    "Sin Diseño",
                    "Esta actividad aún no cuenta con un borrador de diseño metodológico.",
                )
                return

            # Para cargar el DTO completo usamos validate o creamos un comando de lectura
            # MethodologicalDesignService.get_activity_detail da el estado general, y
            # create_design_draft() es idempotente: retorna el DTO del borrador existente
            self.design_dto = self.service.create_design_draft(
                activity_ref=self.planning_id,
                created_by="consulta_ui",
            )
            self._populate_editor(self.design_dto, act_detail.design_status)
        except PlanningUIError as e:
            messagebox.showerror("Error al Cargar Diseño", e.message)

    def _populate_editor(self, dto: MethodologicalDesignDTO, status: str) -> None:
        is_approved = (status == "APPROVED")

        # Encabezado
        self.lbl_header_title.configure(text=f"Diseño: {dto.document_title} ({self.planning_id})")
        badge_color = ("#2E7D32", "white") if is_approved else (("#E65100", "white") if status == "DRAFT" else ("#1565C0", "white"))
        badge_label = "APROBADO (R-08)" if is_approved else ("EN BORRADOR" if status == "DRAFT" else status)
        self.lbl_status_badge.configure(text=badge_label, fg_color=badge_color[0], text_color=badge_color[1])

        # Bloque 1: Introducción
        self._set_text(self.txt_intro, dto.introduction)
        self._set_text(self.txt_enfoque, dto.methodological_approach)

        # Bloque 2: Objetivos
        self._set_text(self.txt_obj1, dto.objective_1)
        self._set_text(self.txt_obj2, dto.objective_2)

        # Bloque 3: FAQ
        faq = dto.faq
        if faq:
            self._set_entry(self.faq_entries.get("q1_que_es"), faq.q1_que_es)
            self._set_entry(self.faq_entries.get("q2_para_que"), faq.q2_para_que)
            self._set_entry(self.faq_entries.get("q3_sesiones"), faq.q3_sesiones)
            self._set_entry(self.faq_entries.get("q4_protagonistas"), faq.q4_protagonistas)
            self._set_entry(self.faq_entries.get("q5_facilitador"), faq.q5_facilitador)
            self._set_entry(self.faq_entries.get("q6_materiales"), faq.q6_materiales)
            self._set_entry(self.faq_entries.get("q7_duracion"), faq.q7_duracion)

        # Bloque 4: Agenda
        self.agenda_items = list(dto.agenda)
        self._render_agenda_items()

        # Bloque 5: Matriz Operativa
        self.matrix_items = list(dto.operational_matrix)
        self._render_matrix_items()

        # Configurar botones y permisos según estado
        self._update_action_buttons(is_approved)

        # Reiniciar bandera de cambios
        self.is_dirty = False
        self.lbl_save_status.configure(text="Diseño cargado correctamente.")

    def _update_action_buttons(self, is_approved: bool) -> None:
        for w in self.action_buttons_frame.winfo_children():
            w.destroy()

        if is_approved:
            # En modo aprobado: inhabilitar inputs y mostrar solo exportación
            self._disable_all_inputs()

            btn_docx = ctk.CTkButton(
                self.action_buttons_frame,
                text="Generar Documento Word (.docx)  ➔",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color="#2E7D32",
                hover_color="#1B5E20",
                height=34,
                command=self._on_click_export_docx,
            )
            btn_docx.pack(side="right")
        else:
            btn_guardar = ctk.CTkButton(
                self.action_buttons_frame,
                text="Guardar Borrador",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#0B3C5D",
                hover_color="#07263D",
                width=130,
                height=34,
                command=self._on_click_guardar_borrador,
            )
            btn_guardar.pack(side="left", padx=4)

            btn_validar = ctk.CTkButton(
                self.action_buttons_frame,
                text="Validar Diseño",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color=("gray60", "gray40"),
                hover_color=("gray50", "gray30"),
                width=120,
                height=34,
                command=self._on_click_validar,
            )
            btn_validar.pack(side="left", padx=4)

            btn_aprobar = ctk.CTkButton(
                self.action_buttons_frame,
                text="Aprobar Diseño  ➔",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color="#2E7D32",
                hover_color="#1B5E20",
                width=140,
                height=34,
                command=self._on_click_aprobar,
            )
            btn_aprobar.pack(side="left", padx=4)

    def _disable_all_inputs(self) -> None:
        """Inhabilita todos los campos de entrada si el diseño está APPROVED."""
        self.txt_intro.configure(state="disabled")
        self.txt_enfoque.configure(state="disabled")
        self.txt_obj1.configure(state="disabled")
        self.txt_obj2.configure(state="disabled")
        for ent in self.faq_entries.values():
            ent.configure(state="disabled")
        self.txt_new_agenda_label.configure(state="disabled")
        self.txt_new_agenda_min.configure(state="disabled")
        self.btn_add_agenda.configure(state="disabled")
        self.btn_sync_matrix.configure(state="disabled")

    # -------------------------------------------------------------------------
    # GESTIÓN DE AGENDA Y MATRIZ
    # -------------------------------------------------------------------------
    def _on_add_agenda_item(self) -> None:
        label = self.txt_new_agenda_label.get().strip()
        min_str = self.txt_new_agenda_min.get().strip()

        if not label:
            messagebox.showwarning("Campo Vacío", "Debe ingresar el nombre de la fase o actividad.")
            return

        try:
            minutes = int(min_str)
            if minutes <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("Minutos Inválidos", "La duración debe ser un número entero mayor a 0.")
            return

        seq = len(self.agenda_items) + 1
        self.agenda_items.append(TimeBlockDTO(sequence=seq, label=label, minutes=minutes))

        self.txt_new_agenda_label.delete(0, tk.END)
        self.txt_new_agenda_min.delete(0, tk.END)

        self._render_agenda_items()
        self.is_dirty = True
        self.lbl_save_status.configure(text="Cambios pendientes de guardar.")

    def _on_delete_agenda_item(self, idx: int) -> None:
        if 0 <= idx < len(self.agenda_items):
            self.agenda_items.pop(idx)
            # Reindexar secuencia
            self.agenda_items = [
                TimeBlockDTO(sequence=i + 1, label=it.label, minutes=it.minutes)
                for i, it in enumerate(self.agenda_items)
            ]
            self._render_agenda_items()
            self.is_dirty = True
            self.lbl_save_status.configure(text="Cambios pendientes de guardar.")

    def _render_agenda_items(self) -> None:
        for w in self.scroll_agenda.winfo_children():
            w.destroy()

        total = sum(it.minutes for it in self.agenda_items)
        self.lbl_agenda_total.configure(text=f"Duración Total de la Agenda: {total} minutos")

        # Actualizar automáticamente q7 en FAQ
        if "q7_duracion" in self.faq_entries:
            self._set_entry(self.faq_entries["q7_duracion"], f"{total} minutos")

        for idx, item in enumerate(self.agenda_items):
            row = ctk.CTkFrame(self.scroll_agenda, fg_color=("gray92", "gray17"), corner_radius=4)
            row.grid(row=idx, column=0, sticky="ew", pady=2, padx=2)
            row.grid_columnconfigure(1, weight=1)

            lbl_num = ctk.CTkLabel(row, text=f"{item.sequence}.", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), width=30)
            lbl_num.grid(row=0, column=0, padx=6, pady=6)

            lbl_lbl = ctk.CTkLabel(row, text=item.label, font=ctk.CTkFont(family="Segoe UI", size=11), anchor="w")
            lbl_lbl.grid(row=0, column=1, padx=6, pady=6, sticky="w")

            lbl_m = ctk.CTkLabel(row, text=f"{item.minutes} min", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), width=70)
            lbl_m.grid(row=0, column=2, padx=6, pady=6)

            if not (self.design_dto and self.design_dto.approved_by):
                btn_del = ctk.CTkButton(
                    row,
                    text="✕",
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    fg_color=("#C62828", "#B71C1C"),
                    hover_color="#8E0000",
                    width=28,
                    height=24,
                    command=lambda i=idx: self._on_delete_agenda_item(i),
                )
                btn_del.grid(row=0, column=3, padx=6, pady=6)

    def _on_sync_matrix_from_agenda(self) -> None:
        """Clona las filas y minutos de la agenda hacia la matriz operativa para satisfacer R-06."""
        if not self.agenda_items:
            messagebox.showwarning(
                "Agenda Vacía",
                "Primero agregue bloques de tiempo a la Agenda (Pestaña 4) antes de sincronizar.",
            )
            return

        new_matrix = []
        for it in self.agenda_items:
            # Preservar descripciones previas si ya existían para este paso
            prev_step = next((m for m in self.matrix_items if m.step_number == it.sequence), None)
            goal = prev_step.operative_goal if prev_step else ""
            proc = prev_step.procedure if prev_step else ""
            mat = prev_step.materials if prev_step else ""

            new_matrix.append(
                OperationalActivityDTO(
                    step_number=it.sequence,
                    phase_label=it.label,
                    operative_goal=goal,
                    procedure=proc,
                    materials=mat,
                    minutes=it.minutes,
                )
            )

        self.matrix_items = new_matrix
        self._render_matrix_items()
        self.is_dirty = True
        self.lbl_save_status.configure(text="Matriz sincronizada con la Agenda. Guarde los cambios.")
        messagebox.showinfo(
            "Sincronización Exitosa",
            "Se actualizaron las actividades y minutos de la Matriz Operativa según la Agenda.\n"
            "Ahora puede completar los objetivos, procedimientos y materiales de cada sesión.",
        )

    def _render_matrix_items(self) -> None:
        for w in self.scroll_matrix.winfo_children():
            w.destroy()

        if not self.matrix_items:
            lbl_empty = ctk.CTkLabel(
                self.scroll_matrix,
                text="La matriz operativa está vacía. Use el botón 'Sincronizar Fases desde Agenda' arriba.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="gray",
            )
            lbl_empty.pack(pady=20)
            return

        for idx, item in enumerate(self.matrix_items):
            card = ctk.CTkFrame(self.scroll_matrix, fg_color=("gray92", "gray17"), corner_radius=6)
            card.pack(fill="x", pady=4, padx=2)
            card.grid_columnconfigure(1, weight=1)

            # Encabezado del paso
            step_header = f"Paso {item.step_number}: {item.phase_label} ({item.minutes} minutos)"
            lbl_h = ctk.CTkLabel(
                card,
                text=step_header,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=("#0B3C5D", "#4FC3F7"),
                anchor="w",
            )
            lbl_h.grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 4), sticky="w")

            # Campos editables de la fila
            fields = [
                ("Objetivo Operativo:", item.operative_goal, "goal"),
                ("Procedimiento Metodológico:", item.procedure, "procedure"),
                ("Materiales y Recursos:", item.materials, "materials"),
            ]

            for f_idx, (f_label, f_val, f_type) in enumerate(fields, start=1):
                lbl_f = ctk.CTkLabel(
                    card,
                    text=f_label,
                    font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                    anchor="w",
                    width=160,
                )
                lbl_f.grid(row=f_idx, column=0, padx=10, pady=2, sticky="w")

                ent_f = ctk.CTkEntry(card, height=28, font=ctk.CTkFont(family="Segoe UI", size=11))
                ent_f.grid(row=f_idx, column=1, padx=10, pady=2, sticky="ew")
                ent_f.insert(0, f_val)
                ent_f.bind("<KeyRelease>", lambda _, i=idx, t=f_type: self._on_matrix_field_change(i, t))

                if self.design_dto and self.design_dto.approved_by:
                    ent_f.configure(state="disabled")

    def _on_matrix_field_change(self, idx: int, field_type: str) -> None:
        self.is_dirty = True
        self.lbl_save_status.configure(text="Cambios pendientes de guardar.")

    def _collect_matrix_items_from_ui(self) -> List[OperationalActivityDTO]:
        """Extrae el contenido de los entries de la matriz operativa."""
        collected = []
        children = self.scroll_matrix.winfo_children()
        for idx, card in enumerate(children):
            if not isinstance(card, ctk.CTkFrame) or idx >= len(self.matrix_items):
                continue
            orig = self.matrix_items[idx]
            # Extraer entries en filas 1, 2, 3
            entries = [w for w in card.winfo_children() if isinstance(w, ctk.CTkEntry)]
            goal = entries[0].get().strip() if len(entries) > 0 else orig.operative_goal
            proc = entries[1].get().strip() if len(entries) > 1 else orig.procedure
            mats = entries[2].get().strip() if len(entries) > 2 else orig.materials

            collected.append(
                OperationalActivityDTO(
                    step_number=orig.step_number,
                    phase_label=orig.phase_label,
                    operative_goal=goal,
                    procedure=proc,
                    materials=mats,
                    minutes=orig.minutes,
                )
            )
        return collected or self.matrix_items

    # -------------------------------------------------------------------------
    # ACCIONES: GUARDAR, VALIDAR, APROBAR, EXPORTAR
    # -------------------------------------------------------------------------
    def _build_update_command(self) -> UpdateMethodologicalDesignCommand:
        if not self.design_dto:
            raise ValueError("No hay diseño metodológico cargado.")

        intro = self.txt_intro.get("1.0", tk.END).strip()
        enfoque = self.txt_enfoque.get("1.0", tk.END).strip()
        obj1 = self.txt_obj1.get("1.0", tk.END).strip()
        obj2 = self.txt_obj2.get("1.0", tk.END).strip()

        faq_dto = FAQTableDTO(
            q1_que_es=self.faq_entries["q1_que_es"].get().strip(),
            q2_para_que=self.faq_entries["q2_para_que"].get().strip(),
            q3_sesiones=self.faq_entries["q3_sesiones"].get().strip(),
            q4_protagonistas=self.faq_entries["q4_protagonistas"].get().strip(),
            q5_facilitador=self.faq_entries["q5_facilitador"].get().strip(),
            q6_materiales=self.faq_entries["q6_materiales"].get().strip(),
            q7_duracion=self.faq_entries["q7_duracion"].get().strip(),
        )

        matrix = self._collect_matrix_items_from_ui()

        return UpdateMethodologicalDesignCommand(
            design_id=self.design_dto.design_id,
            introduction_text=intro,
            methodological_approach=enfoque,
            objectives=(obj1, obj2),
            faq=faq_dto,
            agenda=tuple(self.agenda_items),
            operational_matrix=tuple(matrix),
        )

    def _on_click_guardar_borrador(self) -> None:
        try:
            cmd = self._build_update_command()
            updated = self.service.update_design_draft(cmd)
            self.design_dto = updated
            self.is_dirty = False
            self.lbl_save_status.configure(text="✓ Borrador guardado exitosamente en la base de datos.")
            messagebox.showinfo("Borrador Guardado", "El diseño metodológico se ha guardado correctamente como borrador.")
        except PlanningUIError as e:
            messagebox.showerror("Error al Guardar Borrador", e.message)

    def _on_click_validar(self) -> None:
        if not self.design_dto:
            return

        # Guardar primero para que el validador examine los datos actuales
        if self.is_dirty:
            try:
                cmd = self._build_update_command()
                self.design_dto = self.service.update_design_draft(cmd)
                self.is_dirty = False
            except PlanningUIError as e:
                messagebox.showerror("Error al Guardar antes de Validar", e.message)
                return

        try:
            report = self.service.validate_design(self.design_dto.design_id)
            ValidationDialog(
                self,
                report=report,
                on_proceder_aprobacion=self._on_click_aprobar,
            )
        except PlanningUIError as e:
            messagebox.showerror("Error de Validación", e.message)

    def _on_click_aprobar(self) -> None:
        if not self.design_dto:
            return

        # Ejecutar validación pre-vuelo antes de abrir diálogo de aprobación
        try:
            if self.is_dirty:
                cmd = self._build_update_command()
                self.design_dto = self.service.update_design_draft(cmd)
                self.is_dirty = False

            report = self.service.validate_design(self.design_dto.design_id)
            if not report.is_valid:
                ValidationDialog(self, report=report)
                return
        except PlanningUIError as e:
            messagebox.showerror("Error de Validación", e.message)
            return

        ApprovalDialog(
            self,
            activity_name=self.design_dto.document_title,
            planning_id=self.planning_id,
            on_confirm_approval=self._ejecutar_aprobacion_formal,
        )

    def _ejecutar_aprobacion_formal(self, approver_name: str) -> None:
        if not self.design_dto:
            return
        try:
            approved_dto = self.service.approve_design(
                design_id=self.design_dto.design_id,
                approved_by=approver_name,
            )
            self.design_dto = approved_dto
            self.is_dirty = False
            self._populate_editor(approved_dto, "APPROVED")
            messagebox.showinfo(
                "Aprobación Formal Exitosa",
                f"El diseño metodológico ha sido APROBADO formalmente por {approver_name}.\n\n"
                "Conforme a la regla institucional R-08, el diseño ha quedado sellado e inmutable.\n"
                "Ahora puede generar el documento oficial en formato Word (.docx).",
            )
        except PlanningUIError as e:
            messagebox.showerror("Error al Aprobar Diseño", e.message)

    def _on_click_export_docx(self) -> None:
        if not self.design_dto:
            return

        default_name = f"Diseno_Metodologico_{self.planning_id}.docx"
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar Diseño Metodológico Oficial en Word",
            initialfile=default_name,
            defaultextension=".docx",
            filetypes=[("Documento de Microsoft Word", "*.docx")],
        )
        if not file_path:
            return

        try:
            out_file = self.service.export_docx(
                design_id=self.design_dto.design_id,
                output_path=file_path,
            )
            messagebox.showinfo(
                "Documento Word Generado",
                f"El documento oficial se generó exitosamente en:\n{out_file}",
            )
        except PlanningUIError as e:
            messagebox.showerror("Error al Generar Documento", e.message)

    # -------------------------------------------------------------------------
    # HELPERS Y CONTROL DE DIRTY FLAG
    # -------------------------------------------------------------------------
    def _on_field_modified(self, *_) -> None:
        self.is_dirty = True
        self.lbl_save_status.configure(text="Cambios pendientes de guardar.")
        # Limpiar flag de Tkinter Textbox si aplica
        try:
            self.txt_intro.edit_modified(False)
            self.txt_enfoque.edit_modified(False)
            self.txt_obj1.edit_modified(False)
            self.txt_obj2.edit_modified(False)
        except Exception:
            pass

    def _on_click_volver(self) -> None:
        if self.is_dirty:
            resp = messagebox.askyesnocancel(
                "Cambios sin Guardar",
                "Tiene modificaciones sin guardar en este borrador.\n\n"
                "¿Desea guardar los cambios antes de salir?\n"
                "• Sí: Guarda y sale.\n"
                "• No: Descarta los cambios y sale.\n"
                "• Cancelar: Permanece en el editor.",
                parent=self,
            )
            if resp is True:
                try:
                    self._on_click_guardar_borrador()
                except Exception:
                    return
            elif resp is None:
                return

        if self.on_volver_detalle:
            self.on_volver_detalle()

    @staticmethod
    def _set_text(textbox: ctk.CTkTextbox, text: Optional[str]) -> None:
        textbox.configure(state="normal")
        textbox.delete("1.0", tk.END)
        if text:
            textbox.insert("1.0", text)

    @staticmethod
    def _set_entry(entry: Optional[ctk.CTkEntry], text: Optional[str]) -> None:
        if entry:
            entry.configure(state="normal")
            entry.delete(0, tk.END)
            if text:
                entry.insert(0, text)
