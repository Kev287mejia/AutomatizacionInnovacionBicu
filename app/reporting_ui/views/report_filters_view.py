"""app.reporting_ui.views.report_filters_view

Componente visual de filtros y parámetros institucionales BICU.
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS:
  - Manejo estricto de ReportFilterDTO inmutable.
  - Modos de meta explícitos y visibles: COHORT_UNIQUE (default) vs SESSION_SUM.
  - Cero persistencia directa: emite filtros mediante callbacks hacia la vista integradora.
"""

from typing import Any, Callable, Optional

import customtkinter as ctk

from app.reporting.domain.dto import ReportFilterDTO
from app.reporting.domain.enums import MultisessionGoalMode


class ReportFiltersView(ctk.CTkFrame):
    """Panel de configuración de filtros dimensionales y metodológicos."""

    def __init__(
        self,
        master: Any,
        on_apply_filters: Optional[Callable[[ReportFilterDTO], None]] = None,
        initial_filters: Optional[ReportFilterDTO] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_apply_filters = on_apply_filters
        self._current_filters = initial_filters or ReportFilterDTO()

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self, fg_color=("gray95", "gray17"), corner_radius=6, border_width=1, border_color=("gray80", "gray25"))
        card.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, weight=1)

        # Título del panel
        title_lbl = ctk.CTkLabel(
            card,
            text="FILTROS DIMENSIONALES Y METODOLOGÍA DE CÁLCULO",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, columnspan=3, padx=16, pady=(12, 8), sticky="w")

        # -----------------------------------------------------------------
        # Fila 1: Filtros Temporales y Territoriales
        # -----------------------------------------------------------------
        # Año de Período
        col1 = ctk.CTkFrame(card, fg_color="transparent")
        col1.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")
        ctk.CTkLabel(col1, text="Año de Período:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w").pack(fill="x")
        self.entry_year = ctk.CTkEntry(col1, height=30, placeholder_text="Ej. 2026 (o vacío para todos)")
        if self._current_filters.period_year:
            self.entry_year.insert(0, str(self._current_filters.period_year))
        self.entry_year.pack(fill="x", pady=(2, 0))

        # Sede
        col2 = ctk.CTkFrame(card, fg_color="transparent")
        col2.grid(row=1, column=1, padx=12, pady=6, sticky="nsew")
        ctk.CTkLabel(col2, text="Sede Institucional:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w").pack(fill="x")
        self.combo_sede = ctk.CTkComboBox(
            col2,
            height=30,
            values=["TODAS", "BILWI", "BLUEFIELDS", "LAS_MINAS", "NUEVA_GUINEA"],
        )
        self.combo_sede.set(self._current_filters.sede or "TODAS")
        self.combo_sede.pack(fill="x", pady=(2, 0))

        # Rango de Fechas
        col3 = ctk.CTkFrame(card, fg_color="transparent")
        col3.grid(row=1, column=2, padx=12, pady=6, sticky="nsew")
        ctk.CTkLabel(col3, text="Rango de Fechas (YYYY-MM-DD):", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w").pack(fill="x")
        dates_frame = ctk.CTkFrame(col3, fg_color="transparent")
        dates_frame.pack(fill="x", pady=(2, 0))
        dates_frame.grid_columnconfigure(0, weight=1)
        dates_frame.grid_columnconfigure(1, weight=1)
        self.entry_start = ctk.CTkEntry(dates_frame, height=30, placeholder_text="Inicio")
        if self._current_filters.start_date:
            self.entry_start.insert(0, self._current_filters.start_date)
        self.entry_start.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.entry_end = ctk.CTkEntry(dates_frame, height=30, placeholder_text="Fin")
        if self._current_filters.end_date:
            self.entry_end.insert(0, self._current_filters.end_date)
        self.entry_end.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # -----------------------------------------------------------------
        # Fila 2: Parámetros Metodológicos Institucionales
        # -----------------------------------------------------------------
        method_frame = ctk.CTkFrame(card, fg_color=("gray90", "gray22"), corner_radius=4)
        method_frame.grid(row=2, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="ew")
        method_frame.grid_columnconfigure(0, weight=1)
        method_frame.grid_columnconfigure(1, weight=1)

        # Selector de Modo Multisesión
        mode_box = ctk.CTkFrame(method_frame, fg_color="transparent")
        mode_box.grid(row=0, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkLabel(mode_box, text="Modo de Cómputo de Metas Multisesión (1:N):", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w").pack(anchor="w")

        self.var_mode = ctk.StringVar(value=self._current_filters.multisession_goal_mode)
        self.seg_mode = ctk.CTkSegmentedButton(
            mode_box,
            values=[MultisessionGoalMode.COHORT_UNIQUE.value, MultisessionGoalMode.SESSION_SUM.value],
            variable=self.var_mode,
            command=self._on_mode_change,
        )
        self.seg_mode.pack(anchor="w", pady=(4, 2))

        self.lbl_mode_explanation = ctk.CTkLabel(
            mode_box,
            text=self._get_mode_explanation(self._current_filters.multisession_goal_mode),
            font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        self.lbl_mode_explanation.pack(anchor="w")

        # Toggle de Cédula Verificada para Personas Únicas
        chk_box = ctk.CTkFrame(method_frame, fg_color="transparent")
        chk_box.grid(row=0, column=1, padx=12, pady=8, sticky="e")

        self.var_require_id = ctk.BooleanVar(value=self._current_filters.require_verified_id_for_unique_persons)
        self.chk_require_id = ctk.CTkCheckBox(
            chk_box,
            text="Exigir Identificación Verificada para Personas Únicas",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            variable=self.var_require_id,
        )
        self.chk_require_id.pack(anchor="e", pady=(8, 2))
        ctk.CTkLabel(
            chk_box,
            text="Registros sin cédula válida computan como asistencias, no personas únicas.",
            font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
            text_color=("gray40", "gray70"),
            anchor="e",
        ).pack(anchor="e")

        # -----------------------------------------------------------------
        # Fila 3: Botones de Acción
        # -----------------------------------------------------------------
        action_frame = ctk.CTkFrame(card, fg_color="transparent")
        action_frame.grid(row=3, column=0, columnspan=3, padx=12, pady=(10, 12), sticky="e")

        btn_reset = ctk.CTkButton(
            action_frame,
            text="Restablecer",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            text_color=("black", "white"),
            width=110,
            height=32,
            command=self._on_reset,
        )
        btn_reset.pack(side="left", padx=(0, 8))

        btn_apply = ctk.CTkButton(
            action_frame,
            text="Aplicar Filtros al Dashboard y Reportes",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            width=260,
            height=32,
            command=self._on_apply,
        )
        btn_apply.pack(side="left")

    def _get_mode_explanation(self, mode: str) -> str:
        if mode == MultisessionGoalMode.COHORT_UNIQUE.value:
            return "Modo Predeterminado: 1 plan con N sesiones cuenta como 1 cumplimiento (cohortes únicas)."
        return "Modo Explícito: Suma acumulada de participaciones brutas de cada sesión realizada."

    def _on_mode_change(self, mode: str) -> None:
        self.lbl_mode_explanation.configure(text=self._get_mode_explanation(mode))

    def _on_reset(self) -> None:
        self.entry_year.delete(0, "end")
        self.combo_sede.set("TODAS")
        self.entry_start.delete(0, "end")
        self.entry_end.delete(0, "end")
        self.var_mode.set(MultisessionGoalMode.COHORT_UNIQUE.value)
        self.var_require_id.set(True)
        self._on_mode_change(MultisessionGoalMode.COHORT_UNIQUE.value)
        self._on_apply()

    def _on_apply(self) -> None:
        year_str = self.entry_year.get().strip()
        period_year = int(year_str) if year_str.isdigit() else None
        sede_val = self.combo_sede.get().strip()
        sede = None if sede_val == "TODAS" else sede_val
        start_date = self.entry_start.get().strip() or None
        end_date = self.entry_end.get().strip() or None

        self._current_filters = ReportFilterDTO(
            period_year=period_year,
            start_date=start_date,
            end_date=end_date,
            sede=sede,
            multisession_goal_mode=self.var_mode.get(),
            require_verified_id_for_unique_persons=self.var_require_id.get(),
        )

        if self.on_apply_filters:
            self.on_apply_filters(self._current_filters)

    def get_current_filters(self) -> ReportFilterDTO:
        return self._current_filters
