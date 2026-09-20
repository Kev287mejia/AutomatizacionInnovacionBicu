"""app.word_consolidator.ui.views.module_selection_view

Vista de selección inicial de módulos del Sistema Institucional BICU (Fase 28.2).
Permite elegir entre:
  1. Módulo 1: Word → Matrices M1–M5.
  2. Módulo 2: Matrices M1–M5 → Informes Word (flujo patrimonial).
"""

from typing import Any, Callable, Optional
import customtkinter as ctk


class ModuleSelectionView(ctk.CTkFrame):
    """Componente visual para la selección de procesos institucionales."""

    def __init__(
        self,
        master: Any,
        on_select_word_batch: Optional[Callable[[], None]] = None,
        on_select_matrices_word: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_select_word_batch = on_select_word_batch
        self.on_select_matrices_word = on_select_matrices_word

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

        title_lbl = ctk.CTkLabel(
            header,
            text="BLUEFIELDS INDIAN & CARIBBEAN UNIVERSITY — BICU",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="white",
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, padx=24, pady=(14, 2), sticky="w")

        sub_lbl = ctk.CTkLabel(
            header,
            text="Sistema de Gestión Institucional de Asistencias y Actividades",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#E0E0E0", "#B0BEC5"),
            anchor="w",
        )
        sub_lbl.grid(row=1, column=0, padx=24, pady=(0, 14), sticky="w")

        # ---------------------------------------------------------------------
        # 2. CUERPO CENTRAL: SELECCIÓN DE PROCESO
        # ---------------------------------------------------------------------
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=1, column=0, sticky="nsew", padx=30, pady=25)
        center_frame.grid_columnconfigure(0, weight=1)

        prompt_title = ctk.CTkLabel(
            center_frame,
            text="SELECCIÓN DE PROCESO INSTITUCIONAL",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            anchor="center",
        )
        prompt_title.grid(row=0, column=0, pady=(10, 4))

        prompt_desc = ctk.CTkLabel(
            center_frame,
            text="Seleccione el flujo de procesamiento que desea ejecutar en esta sesión:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
            anchor="center",
        )
        prompt_desc.grid(row=1, column=0, pady=(0, 25))

        cards_container = ctk.CTkFrame(center_frame, fg_color="transparent")
        cards_container.grid(row=2, column=0, sticky="ew")
        cards_container.grid_columnconfigure(0, weight=1)
        cards_container.grid_columnconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # Tarjeta 1: WORD → MATRICES
        # ---------------------------------------------------------------------
        card_w2m = ctk.CTkFrame(
            cards_container,
            fg_color=("gray92", "gray17"),
            corner_radius=6,
            border_width=1,
            border_color=("gray80", "gray25"),
        )
        card_w2m.grid(row=0, column=0, padx=(0, 12), pady=10, sticky="nsew")
        card_w2m.grid_columnconfigure(0, weight=1)

        w2m_badge = ctk.CTkLabel(
            card_w2m,
            text="MÓDULO 1",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        w2m_badge.grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        w2m_title = ctk.CTkLabel(
            card_w2m,
            text="PROCESAR INFORMES WORD → MATRICES M1–M5",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
            wraplength=380,
            justify="left",
        )
        w2m_title.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        w2m_desc = ctk.CTkLabel(
            card_w2m,
            text=(
                "Extrae actividades institucionales desde documentos Word (.docx), "
                "valida reglas de calidad Q-01 a Q-20, registra los datos en la base de datos "
                "institucional y genera las matrices consolidadas oficiales M1 a M5."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray40", "gray70"),
            anchor="w",
            wraplength=380,
            justify="left",
        )
        w2m_desc.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="w")

        btn_w2m = ctk.CTkButton(
            card_w2m,
            text="Iniciar Procesamiento Word  ➔",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=36,
            corner_radius=5,
            command=self._on_click_word_batch,
        )
        btn_w2m.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")

        # ---------------------------------------------------------------------
        # Tarjeta 2: MATRICES → INFORMES WORD (PATRIMONIAL)
        # ---------------------------------------------------------------------
        card_m2w = ctk.CTkFrame(
            cards_container,
            fg_color=("gray92", "gray17"),
            corner_radius=6,
            border_width=1,
            border_color=("gray80", "gray25"),
        )
        card_m2w.grid(row=0, column=1, padx=(12, 0), pady=10, sticky="nsew")
        card_m2w.grid_columnconfigure(0, weight=1)

        m2w_badge = ctk.CTkLabel(
            card_m2w,
            text="MÓDULO 2 (CONSOLIDADOR)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        m2w_badge.grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        m2w_title = ctk.CTkLabel(
            card_m2w,
            text="CONSOLIDAR MATRICES EXCEL → INFORMES WORD",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
            wraplength=380,
            justify="left",
        )
        m2w_title.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        m2w_desc = ctk.CTkLabel(
            card_m2w,
            text=(
                "Consolida las cinco matrices oficiales de asistencias (M1 a M5) "
                "y genera el Informe Técnico de Auditoría y el Informe Institucional "
                "Ejecutivo en formato Word (.docx)."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray40", "gray70"),
            anchor="w",
            wraplength=380,
            justify="left",
        )
        m2w_desc.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="w")

        btn_m2w = ctk.CTkButton(
            card_m2w,
            text="Iniciar Consolidación de Matrices  ➔",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=36,
            corner_radius=5,
            command=self._on_click_matrices_word,
        )
        btn_m2w.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")

        # ---------------------------------------------------------------------
        # 3. PIE DE PÁGINA INSTITUCIONAL
        # ---------------------------------------------------------------------
        footer_frame = ctk.CTkFrame(self, fg_color="transparent", height=24)
        footer_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))

        footer_lbl = ctk.CTkLabel(
            footer_frame,
            text="Bluefields Indian & Caribbean University — Dirección de Innovación y Emprendimiento",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray50", "gray60"),
            anchor="center",
        )
        footer_lbl.pack(fill="x")

    def _on_click_word_batch(self) -> None:
        if self.on_select_word_batch:
            self.on_select_word_batch()

    def _on_click_matrices_word(self) -> None:
        if self.on_select_matrices_word:
            self.on_select_matrices_word()
