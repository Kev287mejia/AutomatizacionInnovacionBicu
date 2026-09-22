"""app.reporting_ui.views.dashboard_view

Vista de Dashboard Institucional BICU de 5 Niveles.
Fase 29.20.3 — Integración Controlada de Reporting + Dashboard.

PRINCIPIOS:
  - Consumo exclusivo e inmutable de DashboardDataDTO.
  - Cero consultas a SQLite, cero acceso a M1-M5 y cero lógica matemática en la vista.
  - Componentes visuales organizados por los 5 niveles aprobados:
      NIVEL 1: Resumen Ejecutivo
      NIVEL 2: Actividades y Cumplimiento
      NIVEL 3: Participación y Demografía
      NIVEL 4: Cobertura Territorial
      NIVEL 5: Trazabilidad y Salud del Dato
"""

from typing import Any, List, Optional

import customtkinter as ctk

from app.reporting.domain.dto import DashboardCardDTO, DashboardDataDTO
from app.reporting.domain.enums import AlertStatus


class DashboardView(ctk.CTkScrollableFrame):
    """Panel interactivo de visualización institucional de 5 niveles."""

    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._current_data: Optional[DashboardDataDTO] = None

    def render(self, data: DashboardDataDTO) -> None:
        """Renderiza todo el Dashboard a partir del DTO inmutable recibido."""
        self._current_data = data

        # Limpiar widgets previos
        for widget in self.winfo_children():
            widget.destroy()

        # -----------------------------------------------------------------
        # ENCABEZADO Y BARRA DE ESTADO DEL PERÍODO
        # -----------------------------------------------------------------
        status_banner = ctk.CTkFrame(self, fg_color=("#E0EBF5", "#1B2A38"), corner_radius=6)
        status_banner.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 12))
        status_banner.grid_columnconfigure(0, weight=1)

        f = data.filters_active
        periodo_txt = f"Período: {f.period_year or 'Histórico Completo'}"
        fechas_txt = f"Rango: {f.start_date or 'Inicio'} a {f.end_date or 'Actual'}"
        sede_txt = f"Sede: {f.sede or 'Todas las Sedes'}"
        modo_txt = f"Modo Multisesión: {f.multisession_goal_mode}"

        info_lbl = ctk.CTkLabel(
            status_banner,
            text=f"ESTADO INSTITUCIONAL ACTUALIZADO  |  {periodo_txt}  |  {fechas_txt}  |  {sede_txt}  |  {modo_txt}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        info_lbl.grid(row=0, column=0, padx=16, pady=8, sticky="w")

        # Alertas de Salud del Dato si existen
        if data.system_health_alerts:
            alert_box = ctk.CTkFrame(self, fg_color=("#FFF3E0", "#3E2723"), corner_radius=6)
            alert_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
            for alert_text in data.system_health_alerts:
                ctk.CTkLabel(
                    alert_box,
                    text=f"⚠ ALERTA DE GOBERNANZA: {alert_text}",
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    text_color=("#E65100", "#FFB74D"),
                    anchor="w",
                ).pack(fill="x", padx=16, pady=4)

        current_row = 2

        # -----------------------------------------------------------------
        # NIVEL 1 — RESUMEN EJECUTIVO
        # -----------------------------------------------------------------
        current_row = self._render_level_1(current_row, data)

        # -----------------------------------------------------------------
        # NIVEL 2 — ACTIVIDADES Y CUMPLIMIENTO
        # -----------------------------------------------------------------
        current_row = self._render_level_2(current_row, data)

        # -----------------------------------------------------------------
        # NIVEL 3 — PARTICIPACIÓN Y DEMOGRAFÍA
        # -----------------------------------------------------------------
        current_row = self._render_level_3(current_row, data)

        # -----------------------------------------------------------------
        # NIVEL 4 — COBERTURA TERRITORIAL
        # -----------------------------------------------------------------
        current_row = self._render_level_4(current_row, data)

        # -----------------------------------------------------------------
        # NIVEL 5 — TRAZABILIDAD Y SALUD DEL DATO
        # -----------------------------------------------------------------
        current_row = self._render_level_5(current_row, data)

    # =====================================================================
    # RENDERIZADORES MODULARES POR NIVEL
    # =====================================================================

    def _render_level_1(self, start_row: int, data: DashboardDataDTO) -> int:
        sec = data.level_1_summary
        container = self._create_section_container(start_row, "NIVEL 1 — RESUMEN EJECUTIVO Y ESTADO GENERAL")

        # Tarjetas KPI superiores
        cards_grid = ctk.CTkFrame(container, fg_color="transparent")
        cards_grid.pack(fill="x", padx=12, pady=8)

        cols = len(sec.cards)
        for i in range(cols):
            cards_grid.grid_columnconfigure(i, weight=1)

        for idx, card in enumerate(sec.cards):
            self._render_kpi_card(cards_grid, card, row=0, col=idx)

        # Tabla resumen si está presente
        if sec.table_rows:
            self._render_data_table(container, sec.table_headers, sec.table_rows)

        self._render_notes(container, sec.notes)
        return start_row + 1

    def _render_level_2(self, start_row: int, data: DashboardDataDTO) -> int:
        sec = data.level_2_activity
        container = self._create_section_container(start_row, "NIVEL 2 — ACTIVIDADES Y CUMPLIMIENTO POA (PLAN VS EJECUCIÓN)")

        # Tarjetas de nivel 2
        cards_grid = ctk.CTkFrame(container, fg_color="transparent")
        cards_grid.pack(fill="x", padx=12, pady=8)
        for i in range(len(sec.cards)):
            cards_grid.grid_columnconfigure(i, weight=1)

        for idx, card in enumerate(sec.cards):
            self._render_kpi_card(cards_grid, card, row=0, col=idx)

        # Visualizador de gráficos/barras normalizados desde ChartDatasetDTO
        for chart in sec.charts:
            chart_box = ctk.CTkFrame(container, fg_color=("gray90", "gray20"), corner_radius=6)
            chart_box.pack(fill="x", padx=12, pady=6)
            ctk.CTkLabel(
                chart_box,
                text=chart.title,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                anchor="w",
            ).pack(fill="x", padx=12, pady=(8, 4))

            # Renderizado de barras mediante widgets nativos de CustomTkinter (CERO matplotlib)
            max_v = max(chart.values) if chart.values and max(chart.values) > 0 else 1.0
            for lbl, val in zip(chart.labels, chart.values):
                r_box = ctk.CTkFrame(chart_box, fg_color="transparent")
                r_box.pack(fill="x", padx=12, pady=3)
                r_box.grid_columnconfigure(1, weight=1)

                ctk.CTkLabel(r_box, text=f"{lbl}:", font=ctk.CTkFont(family="Segoe UI", size=10), width=180, anchor="w").grid(row=0, column=0, sticky="w")
                bar = ctk.CTkProgressBar(r_box, height=14, corner_radius=3, fg_color=("gray80", "gray30"), progress_color="#0B3C5D")
                bar.grid(row=0, column=1, sticky="ew", padx=8)
                bar.set(min(val / max_v, 1.0))
                ctk.CTkLabel(r_box, text=str(val), font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), width=60, anchor="e").grid(row=0, column=2, sticky="e")

        if sec.table_rows:
            self._render_data_table(container, sec.table_headers, sec.table_rows)

        self._render_notes(container, sec.notes)
        return start_row + 1

    def _render_level_3(self, start_row: int, data: DashboardDataDTO) -> int:
        sec = data.level_3_demography
        container = self._create_section_container(start_row, "NIVEL 3 — PARTICIPACIÓN Y DEMOGRAFÍA DE PROTAGONISTAS")

        cards_grid = ctk.CTkFrame(container, fg_color="transparent")
        cards_grid.pack(fill="x", padx=12, pady=8)
        for i in range(len(sec.cards)):
            cards_grid.grid_columnconfigure(i, weight=1)

        for idx, card in enumerate(sec.cards):
            self._render_kpi_card(cards_grid, card, row=0, col=idx)

        # Tablas de distribución demográfica (estudiantes, docentes, externos, beneficiarios, No Especificado)
        if sec.table_rows:
            self._render_data_table(container, sec.table_headers, sec.table_rows)

        self._render_notes(container, sec.notes)
        return start_row + 1

    def _render_level_4(self, start_row: int, data: DashboardDataDTO) -> int:
        sec = data.level_4_territory
        container = self._create_section_container(start_row, "NIVEL 4 — COBERTURA TERRITORIAL (SEDES Y MUNICIPIOS COSTA CARIBE)")

        cards_grid = ctk.CTkFrame(container, fg_color="transparent")
        cards_grid.pack(fill="x", padx=12, pady=8)
        for i in range(len(sec.cards)):
            cards_grid.grid_columnconfigure(i, weight=1)

        for idx, card in enumerate(sec.cards):
            self._render_kpi_card(cards_grid, card, row=0, col=idx)

        if sec.table_rows:
            self._render_data_table(container, sec.table_headers, sec.table_rows)

        self._render_notes(container, sec.notes)
        return start_row + 1

    def _render_level_5(self, start_row: int, data: DashboardDataDTO) -> int:
        sec = data.level_5_traceability
        container = self._create_section_container(start_row, "NIVEL 5 — AUDITORÍA DE TRAZABILIDAD, GOBERNANZA Y SALUD DEL DATO")

        cards_grid = ctk.CTkFrame(container, fg_color="transparent")
        cards_grid.pack(fill="x", padx=12, pady=8)
        for i in range(len(sec.cards)):
            cards_grid.grid_columnconfigure(i, weight=1)

        for idx, card in enumerate(sec.cards):
            self._render_kpi_card(cards_grid, card, row=0, col=idx)

        if sec.table_rows:
            self._render_data_table(container, sec.table_headers, sec.table_rows)

        self._render_notes(container, sec.notes)
        return start_row + 1

    # =====================================================================
    # COMPONENTES AUXILIARES DE RENDERIZADO VISUAL
    # =====================================================================

    def _create_section_container(self, row: int, title: str) -> ctk.CTkFrame:
        wrapper = ctk.CTkFrame(self, fg_color=("gray95", "gray17"), corner_radius=6, border_width=1, border_color=("gray85", "gray25"))
        wrapper.grid(row=row, column=0, sticky="ew", padx=10, pady=8)
        wrapper.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(wrapper, fg_color=("#0B3C5D", "#1A2634"), corner_radius=4)
        header.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="white",
            anchor="w",
        ).pack(fill="x", padx=12, pady=6)

        return wrapper

    def _render_kpi_card(self, parent: Any, card: DashboardCardDTO, row: int, col: int) -> None:
        # Colores de alerta según AlertStatus
        alert_colors = {
            AlertStatus.GREEN: ("#E8F5E9", "#1B5E20"),
            AlertStatus.YELLOW: ("#FFF9C4", "#F57F17"),
            AlertStatus.RED: ("#FFEBEE", "#B71C1C"),
            AlertStatus.NEUTRAL: ("gray90", "gray22"),
        }
        badge_bg, badge_fg = alert_colors.get(card.alert_status, ("gray90", "gray22"))

        card_frame = ctk.CTkFrame(parent, fg_color=("white", "gray20"), corner_radius=6, border_width=1, border_color=("gray80", "gray30"))
        card_frame.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        card_frame.grid_columnconfigure(0, weight=1)

        # Título y badge
        top_bar = ctk.CTkFrame(card_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkLabel(
            top_bar,
            text=card.title,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=("gray30", "gray80"),
            anchor="w",
            wraplength=130,
            justify="left",
        ).pack(side="left", fill="x", expand=True)

        badge = ctk.CTkLabel(
            top_bar,
            text=card.alert_status.value,
            font=ctk.CTkFont(family="Segoe UI", size=8, weight="bold"),
            fg_color=badge_bg,
            text_color=badge_fg,
            corner_radius=4,
            width=50,
            height=18,
        )
        badge.pack(side="right")

        # Valor Principal
        ctk.CTkLabel(
            card_frame,
            text=card.main_value,
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="center",
        ).pack(fill="x", padx=8, pady=(4, 0))

        # Unidad y subtítulo
        ctk.CTkLabel(
            card_frame,
            text=card.unit_label,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=("gray50", "gray60"),
            anchor="center",
        ).pack(fill="x", padx=8)

        if card.sub_label:
            ctk.CTkLabel(
                card_frame,
                text=card.sub_label,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=("gray40", "gray70"),
                anchor="center",
                wraplength=140,
            ).pack(fill="x", padx=8, pady=(2, 8))

    def _render_data_table(self, parent: Any, headers: List[str], rows: List[List[Any]]) -> None:
        table_frame = ctk.CTkFrame(parent, fg_color=("white", "gray18"), corner_radius=4, border_width=1, border_color=("gray85", "gray28"))
        table_frame.pack(fill="x", padx=12, pady=6)

        for col_idx in range(len(headers)):
            table_frame.grid_columnconfigure(col_idx, weight=1)

        # Encabezados
        for col_idx, h_text in enumerate(headers):
            cell = ctk.CTkLabel(
                table_frame,
                text=str(h_text),
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=("#E7EFF6", "#1A2634"),
                text_color=("#0B3C5D", "#90CAF9"),
                anchor="center",
                height=26,
            )
            cell.grid(row=0, column=col_idx, sticky="ew", padx=1, pady=1)

        # Filas
        for row_idx, r_data in enumerate(rows, start=1):
            bg = ("white", "gray20") if row_idx % 2 == 1 else ("gray96", "gray23")
            for col_idx, val in enumerate(r_data):
                val_str = str(val) if val is not None else "N/D"
                cell = ctk.CTkLabel(
                    table_frame,
                    text=val_str,
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    fg_color=bg,
                    anchor="w" if col_idx == 0 else "center",
                    height=24,
                )
                cell.grid(row=row_idx, column=col_idx, sticky="ew", padx=1, pady=1)

    def _render_notes(self, parent: Any, notes: List[str]) -> None:
        if not notes:
            return
        notes_box = ctk.CTkFrame(parent, fg_color="transparent")
        notes_box.pack(fill="x", padx=12, pady=(4, 8))
        for note in notes:
            ctk.CTkLabel(
                notes_box,
                text=f"• {note}",
                font=ctk.CTkFont(family="Segoe UI", size=9, slant="italic"),
                text_color=("gray50", "gray60"),
                anchor="w",
            ).pack(fill="x", pady=1)
