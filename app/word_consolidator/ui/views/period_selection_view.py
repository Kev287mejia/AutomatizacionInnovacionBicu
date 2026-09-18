"""
app.word_consolidator.ui.views.period_selection_view

Vista para la configuración del período institucional a consolidar (Fase 14.9).
Permite seleccionar: Semana, Mes, Trimestre, Semestre, Año o Personalizado.
Genera el objeto inmutable PeriodoConsolidacion sin inferir fechas ni alterar las reglas del dominio.
"""

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from app.word_consolidator.models import PeriodoConsolidacion, TipoPeriodo
from app.word_consolidator.ui.services.application_service import (
    ConsolidationAppService,
    MESES_ESPANOL,
)

TIPOS_MAP: Dict[str, TipoPeriodo] = {
    "Semana": TipoPeriodo.SEMANA,
    "Mes": TipoPeriodo.MES,
    "Trimestre": TipoPeriodo.TRIMESTRE,
    "Semestre": TipoPeriodo.SEMESTRE,
    "Año": TipoPeriodo.ANIO,
    "Personalizado": TipoPeriodo.PERSONALIZADO,
}

MESES_LISTA = [
    "1 — Enero", "2 — Febrero", "3 — Marzo", "4 — Abril",
    "5 — Mayo", "6 — Junio", "7 — Julio", "8 — Agosto",
    "9 — Septiembre", "10 — Octubre", "11 — Noviembre", "12 — Diciembre"
]


class PeriodSelectionView(ctk.CTkFrame):
    """
    Componente visual interactivo para la parametrización del período institucional.
    """

    def __init__(
        self,
        master: Any,
        on_periodo_changed: Optional[Callable[[Optional[PeriodoConsolidacion]], None]] = None,
        **kwargs: Any,
    ):
        super().__init__(master, **kwargs)
        self.on_periodo_changed = on_periodo_changed
        self.periodo_actual: Optional[PeriodoConsolidacion] = None

        self._init_ui()
        self._actualizar_controles()
        self._construir_periodo_desde_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Encabezado
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="2. PERÍODO INSTITUCIONAL A CONSOLIDAR",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        title_lbl.pack(anchor="w")

        desc_lbl = ctk.CTkLabel(
            header_frame,
            text="Especifique el corte temporal institucional. El sistema aplicará la regla estricta de fechas sin inferencias.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        desc_lbl.pack(anchor="w", pady=(2, 0))

        # Panel de controles
        self.ctrl_frame = ctk.CTkFrame(self)
        self.ctrl_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=8)
        self.ctrl_frame.grid_columnconfigure(1, weight=1)

        # 1. Tipo de período
        lbl_tipo = ctk.CTkLabel(
            self.ctrl_frame,
            text="Tipo de Período:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=130,
            anchor="w",
        )
        lbl_tipo.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        self.cb_tipo = ctk.CTkComboBox(
            self.ctrl_frame,
            values=["Semana", "Mes", "Trimestre", "Semestre", "Año", "Personalizado"],
            command=self._on_tipo_changed,
            width=200,
            font=ctk.CTkFont(size=12),
        )
        self.cb_tipo.set("Semana")
        self.cb_tipo.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        # 2. Año institucional
        lbl_anio = ctk.CTkLabel(
            self.ctrl_frame,
            text="Año Institucional:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=130,
            anchor="w",
        )
        lbl_anio.grid(row=1, column=0, padx=12, pady=6, sticky="w")

        anios = [str(a) for a in range(2024, 2031)]
        self.cb_anio = ctk.CTkComboBox(
            self.ctrl_frame,
            values=anios,
            command=lambda _: self._construir_periodo_desde_ui(),
            width=120,
            font=ctk.CTkFont(size=12),
        )
        self.cb_anio.set("2026")
        self.cb_anio.grid(row=1, column=1, padx=8, pady=6, sticky="w")

        # Sub-panel para controles dinámicos
        self.dynamic_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        self.dynamic_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=4)
        self.dynamic_frame.grid_columnconfigure(1, weight=1)

        # Mes
        self.lbl_mes = ctk.CTkLabel(
            self.dynamic_frame,
            text="Mes:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=130,
            anchor="w",
        )
        self.cb_mes = ctk.CTkComboBox(
            self.dynamic_frame,
            values=MESES_LISTA,
            command=lambda _: self._construir_periodo_desde_ui(),
            width=200,
            font=ctk.CTkFont(size=12),
        )
        self.cb_mes.set("9 — Septiembre")

        # Semana
        self.lbl_semana = ctk.CTkLabel(
            self.dynamic_frame,
            text="Semana:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=130,
            anchor="w",
        )
        self.cb_semana = ctk.CTkComboBox(
            self.dynamic_frame,
            values=["Semana 1", "Semana 2", "Semana 3", "Semana 4", "Semana 5"],
            command=lambda _: self._construir_periodo_desde_ui(),
            width=140,
            font=ctk.CTkFont(size=12),
        )
        self.cb_semana.set("Semana 1")

        # Trimestre
        self.lbl_trimestre = ctk.CTkLabel(
            self.dynamic_frame,
            text="Trimestre:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=130,
            anchor="w",
        )
        self.cb_trimestre = ctk.CTkComboBox(
            self.dynamic_frame,
            values=[
                "Trimestre I (Enero - Marzo)",
                "Trimestre II (Abril - Junio)",
                "Trimestre III (Julio - Septiembre)",
                "Trimestre IV (Octubre - Diciembre)",
            ],
            command=lambda _: self._construir_periodo_desde_ui(),
            width=260,
            font=ctk.CTkFont(size=12),
        )
        self.cb_trimestre.set("Trimestre III (Julio - Septiembre)")

        # Semestre
        self.lbl_semestre = ctk.CTkLabel(
            self.dynamic_frame,
            text="Semestre:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=130,
            anchor="w",
        )
        self.cb_semestre = ctk.CTkComboBox(
            self.dynamic_frame,
            values=[
                "Semestre I (Enero - Junio)",
                "Semestre II (Julio - Diciembre)",
            ],
            command=lambda _: self._construir_periodo_desde_ui(),
            width=240,
            font=ctk.CTkFont(size=12),
        )
        self.cb_semestre.set("Semestre II (Julio - Diciembre)")

        # Personalizado (Fechas)
        self.lbl_desde = ctk.CTkLabel(
            self.dynamic_frame,
            text="Fecha Desde (AAAA-MM-DD):",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=190,
            anchor="w",
        )
        self.ent_desde = ctk.CTkEntry(
            self.dynamic_frame,
            placeholder_text="2026-09-01",
            width=130,
            font=ctk.CTkFont(size=12),
        )
        self.ent_desde.insert(0, "2026-09-01")
        self.ent_desde.bind("<KeyRelease>", lambda _: self._construir_periodo_desde_ui())

        self.lbl_hasta = ctk.CTkLabel(
            self.dynamic_frame,
            text="Fecha Hasta (AAAA-MM-DD):",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=190,
            anchor="w",
        )
        self.ent_hasta = ctk.CTkEntry(
            self.dynamic_frame,
            placeholder_text="2026-09-07",
            width=130,
            font=ctk.CTkFont(size=12),
        )
        self.ent_hasta.insert(0, "2026-09-07")
        self.ent_hasta.bind("<KeyRelease>", lambda _: self._construir_periodo_desde_ui())

        # Previsualización de la denominación oficial
        preview_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray22"))
        preview_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(4, 10))
        preview_frame.grid_columnconfigure(1, weight=1)

        lbl_prev_title = ctk.CTkLabel(
            preview_frame,
            text="Denominación Oficial:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        lbl_prev_title.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.lbl_preview = ctk.CTkLabel(
            preview_frame,
            text="Septiembre 2026 — Semana 1",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        self.lbl_preview.grid(row=0, column=1, padx=6, pady=8, sticky="w")

    def _on_tipo_changed(self, _: str) -> None:
        """Callback al cambiar el tipo de período."""
        self._actualizar_controles()
        self._construir_periodo_desde_ui()

    def _actualizar_controles(self) -> None:
        """Muestra u oculta widgets según el tipo de período seleccionado."""
        # Limpiar dynamic_frame
        for widget in self.dynamic_frame.winfo_children():
            widget.grid_forget()

        tipo_str = self.cb_tipo.get()

        if tipo_str == "Semana":
            self.lbl_mes.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
            self.cb_mes.grid(row=0, column=1, padx=4, pady=4, sticky="w")
            self.lbl_semana.grid(row=1, column=0, padx=(0, 8), pady=4, sticky="w")
            self.cb_semana.grid(row=1, column=1, padx=4, pady=4, sticky="w")

        elif tipo_str == "Mes":
            self.lbl_mes.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
            self.cb_mes.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        elif tipo_str == "Trimestre":
            self.lbl_trimestre.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
            self.cb_trimestre.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        elif tipo_str == "Semestre":
            self.lbl_semestre.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
            self.cb_semestre.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        elif tipo_str == "Año":
            # Únicamente se requiere el año (ya visible arriba)
            pass

        elif tipo_str == "Personalizado":
            self.lbl_desde.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
            self.ent_desde.grid(row=0, column=1, padx=4, pady=4, sticky="w")
            self.lbl_hasta.grid(row=1, column=0, padx=(0, 8), pady=4, sticky="w")
            self.ent_hasta.grid(row=1, column=1, padx=4, pady=4, sticky="w")

    def _construir_periodo_desde_ui(self) -> None:
        """Construye y valida el objeto PeriodoConsolidacion a partir de los controles activos."""
        try:
            tipo_str = self.cb_tipo.get()
            tipo = TIPOS_MAP[tipo_str]
            anio = int(self.cb_anio.get())

            mes: Optional[int] = None
            semana: Optional[int] = None
            trimestre: Optional[int] = None
            semestre: Optional[int] = None
            f_ini: Optional[date] = None
            f_fin: Optional[date] = None

            if tipo == TipoPeriodo.SEMANA:
                mes_str = self.cb_mes.get()
                mes = int(mes_str.split("—")[0].strip())
                sem_str = self.cb_semana.get()
                semana = int(sem_str.replace("Semana", "").strip())

            elif tipo == TipoPeriodo.MES:
                mes_str = self.cb_mes.get()
                mes = int(mes_str.split("—")[0].strip())

            elif tipo == TipoPeriodo.TRIMESTRE:
                tri_str = self.cb_trimestre.get()
                if "Trimestre I" in tri_str:
                    trimestre = 1
                elif "Trimestre II" in tri_str:
                    trimestre = 2
                elif "Trimestre III" in tri_str:
                    trimestre = 3
                else:
                    trimestre = 4

            elif tipo == TipoPeriodo.SEMESTRE:
                sem_str = self.cb_semestre.get()
                semestre = 1 if "Semestre I" in sem_str else 2

            elif tipo == TipoPeriodo.PERSONALIZADO:
                s_desde = self.ent_desde.get().strip()
                s_hasta = self.ent_hasta.get().strip()
                if s_desde and s_hasta:
                    f_ini = datetime.strptime(s_desde, "%Y-%m-%d").date()
                    f_fin = datetime.strptime(s_hasta, "%Y-%m-%d").date()

            periodo = ConsolidationAppService.construir_periodo(
                tipo=tipo,
                anio=anio,
                mes=mes,
                semana=semana,
                trimestre=trimestre,
                semestre=semestre,
                fecha_inicio=f_ini,
                fecha_fin=f_fin,
            )
            self.periodo_actual = periodo
            self.lbl_preview.configure(
                text=periodo.etiqueta,
                text_color=("#0B3C5D", "#4FC3F7"),
            )
            if self.on_periodo_changed:
                self.on_periodo_changed(periodo)

        except Exception as ex:
            self.periodo_actual = None
            self.lbl_preview.configure(
                text=f"Parámetros incompletos o inválidos ({ex})",
                text_color="#E57373",
            )
            if self.on_periodo_changed:
                self.on_periodo_changed(None)

    def configurar_periodo_directo(self, periodo: PeriodoConsolidacion) -> None:
        """Permite inyectar un período preconfigurado."""
        self.periodo_actual = periodo
        # Sincronizar UI
        for k, v in TIPOS_MAP.items():
            if v == periodo.tipo_periodo:
                self.cb_tipo.set(k)
                break
        self.cb_anio.set(str(periodo.anio))
        if periodo.mes:
            for item in MESES_LISTA:
                if item.startswith(f"{periodo.mes} "):
                    self.cb_mes.set(item)
                    break
        if periodo.semana:
            self.cb_semana.set(f"Semana {periodo.semana}")

        self._actualizar_controles()
        self.lbl_preview.configure(
            text=periodo.etiqueta,
            text_color=("#0B3C5D", "#4FC3F7"),
        )
        if self.on_periodo_changed:
            self.on_periodo_changed(periodo)

    def obtener_periodo(self) -> Optional[PeriodoConsolidacion]:
        """Retorna el período institucional configurado."""
        return self.periodo_actual
