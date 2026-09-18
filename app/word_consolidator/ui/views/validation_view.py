"""
app.word_consolidator.ui.views.validation_view

Vista para la validación previa (Preflight Check), configuración de carpeta de salida
y lanzamiento de la consolidación institucional (Fase 14.9).
"""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

from app.word_consolidator.models import PeriodoConsolidacion
from app.word_consolidator.ui.services.application_service import (
    ConsolidationAppService,
    PreflightStatus,
)


class ValidationView(ctk.CTkFrame):
    """
    Componente visual que resume la aptitud operativa del sistema antes de procesar.
    """

    def __init__(
        self,
        master: Any,
        on_ejecutar_click: Optional[Callable[[], None]] = None,
        on_validar_click: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ):
        super().__init__(master, **kwargs)
        self.on_ejecutar_click = on_ejecutar_click
        self.on_validar_click = on_validar_click

        self.carpeta_salida: Path = ConsolidationAppService.resolver_directorio_salida_predeterminado()
        self.matrices_actuales: Dict[str, Path] = {}
        self.periodo_actual: Optional[PeriodoConsolidacion] = None
        self.preflight_status: Optional[PreflightStatus] = None
        self._en_ejecucion = False

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Encabezado
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="3. VALIDACIÓN PREVIA Y DIRECTORIO DE SALIDA",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        title_lbl.pack(anchor="w")

        desc_lbl = ctk.CTkLabel(
            header_frame,
            text="Verifique la consistencia de las matrices y configure el directorio donde se guardará el informe Word y su auditoría.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        desc_lbl.pack(anchor="w", pady=(2, 0))

        # Panel de Carpeta de Salida
        out_frame = ctk.CTkFrame(self)
        out_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=6)
        out_frame.grid_columnconfigure(1, weight=1)

        lbl_out = ctk.CTkLabel(
            out_frame,
            text="Carpeta de Salida:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=130,
            anchor="w",
        )
        lbl_out.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        self.lbl_path_salida = ctk.CTkLabel(
            out_frame,
            text=str(self.carpeta_salida),
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.lbl_path_salida.grid(row=0, column=1, padx=6, pady=8, sticky="ew")

        self.btn_cambiar_salida = ctk.CTkButton(
            out_frame,
            text="Cambiar Carpeta...",
            width=140,
            height=28,
            font=ctk.CTkFont(size=11),
            command=self._on_cambiar_carpeta_salida,
        )
        self.btn_cambiar_salida.grid(row=0, column=2, padx=10, pady=8)

        # Botón de validación estructural explícita
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.grid(row=2, column=0, sticky="ew", padx=15, pady=4)

        self.btn_validar = ctk.CTkButton(
            btn_box,
            text="🔍 VALIDAR MATRICES Y ESTADO OPERATIVO",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_click_validar,
            width=280,
            height=32,
            fg_color="#0B3C5D",
            hover_color="#07263D",
        )
        self.btn_validar.pack(side="left")

        # Tarjeta de Resumen Pre-Vuelo
        self.card_preflight = ctk.CTkFrame(self, fg_color=("gray90", "gray18"))
        self.card_preflight.grid(row=3, column=0, sticky="ew", padx=15, pady=8)
        self.card_preflight.grid_columnconfigure(1, weight=1)

        # Matrices
        self.lbl_chk_matrices = ctk.CTkLabel(
            self.card_preflight,
            text="[   ] MATRICES:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=140,
            anchor="w",
        )
        self.lbl_chk_matrices.grid(row=0, column=0, padx=12, pady=4, sticky="w")

        self.lbl_det_matrices = ctk.CTkLabel(
            self.card_preflight,
            text="0 de 5 matrices seleccionadas",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_det_matrices.grid(row=0, column=1, padx=6, pady=4, sticky="w")

        # Período
        self.lbl_chk_periodo = ctk.CTkLabel(
            self.card_preflight,
            text="[   ] PERÍODO:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=140,
            anchor="w",
        )
        self.lbl_chk_periodo.grid(row=1, column=0, padx=12, pady=4, sticky="w")

        self.lbl_det_periodo = ctk.CTkLabel(
            self.card_preflight,
            text="Pendiente de configuración",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_det_periodo.grid(row=1, column=1, padx=6, pady=4, sticky="w")

        # Salida
        self.lbl_chk_salida = ctk.CTkLabel(
            self.card_preflight,
            text="[ ✓ ] SALIDA:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#4CAF50",
            width=140,
            anchor="w",
        )
        self.lbl_chk_salida.grid(row=2, column=0, padx=12, pady=4, sticky="w")

        self.lbl_det_salida = ctk.CTkLabel(
            self.card_preflight,
            text="Carpeta verificada con permisos de escritura",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.lbl_det_salida.grid(row=2, column=1, padx=6, pady=4, sticky="w")

        # Estado global de aptitud
        self.lbl_estado_aptitud = ctk.CTkLabel(
            self.card_preflight,
            text="ESTADO: PENDIENTE DE VALIDACIÓN",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#E57373",
            anchor="w",
        )
        self.lbl_estado_aptitud.grid(row=3, column=0, columnspan=2, padx=12, pady=(6, 10), sticky="w")

        # Opciones de Generación (Checkboxes)
        self.gen_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.gen_frame.grid(row=4, column=0, sticky="ew", padx=15, pady=(5, 5))
        
        self.chk_var_tecnico = tk.BooleanVar(value=True)
        self.chk_tecnico = ctk.CTkCheckBox(
            self.gen_frame,
            text="Generar Informe Técnico de Auditoría (Detallado)",
            variable=self.chk_var_tecnico,
            font=ctk.CTkFont(size=12),
            command=self._on_opciones_generacion_cambiadas,
        )
        self.chk_tecnico.pack(anchor="w", pady=(0, 5))
        
        self.chk_var_institucional = tk.BooleanVar(value=True)
        self.chk_institucional = ctk.CTkCheckBox(
            self.gen_frame,
            text="Generar Informe Institucional Ejecutivo (Resumido)",
            variable=self.chk_var_institucional,
            font=ctk.CTkFont(size=12),
            command=self._on_opciones_generacion_cambiadas,
        )
        self.chk_institucional.pack(anchor="w")

        # Botón Institucional de Ejecución
        exec_frame = ctk.CTkFrame(self, fg_color="transparent")
        exec_frame.grid(row=5, column=0, sticky="ew", padx=15, pady=(5, 12))

        self.btn_ejecutar = ctk.CTkButton(
            exec_frame,
            text="▶ EJECUTAR CONSOLIDACIÓN INSTITUCIONAL",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            command=self._on_click_ejecutar,
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            state="disabled",
        )
        self.btn_ejecutar.pack(fill="x")

    def _on_cambiar_carpeta_salida(self) -> None:
        """Abre el diálogo para seleccionar una nueva carpeta de destino."""
        carpeta = filedialog.askdirectory(
            title="Seleccionar Carpeta para Guardar Consolidados BICU",
            initialdir=str(self.carpeta_salida),
        )
        if carpeta:
            self.carpeta_salida = Path(carpeta)
            self.lbl_path_salida.configure(text=str(self.carpeta_salida))
            self.actualizar_estado(self.matrices_actuales, self.periodo_actual)

    def _on_click_validar(self) -> None:
        """Acción al presionar Validar Matrices."""
        if self.on_validar_click:
            self.on_validar_click()
        self.actualizar_estado(self.matrices_actuales, self.periodo_actual)

    def _on_click_ejecutar(self) -> None:
        """Acción al presionar Ejecutar Consolidación."""
        if self._en_ejecucion:
            return
        if self.on_ejecutar_click:
            self.on_ejecutar_click()

    def _on_opciones_generacion_cambiadas(self) -> None:
        """Manejador reactivo al alternar los checkboxes de selección de informes (Fase 16.7-B)."""
        self.actualizar_estado(self.matrices_actuales, self.periodo_actual)

    def actualizar_estado(
        self,
        matrices: Dict[str, Path],
        periodo: Optional[PeriodoConsolidacion],
    ) -> PreflightStatus:
        """Evalúa las condiciones y actualiza la tarjeta de pre-vuelo y el botón de ejecución."""
        self.matrices_actuales = matrices
        self.periodo_actual = periodo
        gen_tec, gen_inst = self.obtener_banderas_generacion()

        status = ConsolidationAppService.validar_preflight(
            matrices=matrices,
            periodo=periodo,
            carpeta_salida=self.carpeta_salida,
            generar_tecnico=gen_tec,
            generar_institucional=gen_inst,
        )
        self.preflight_status = status

        # 1. Matrices
        if status.matrices_completas:
            self.lbl_chk_matrices.configure(text="[ ✓ ] MATRICES:", text_color="#4CAF50")
            self.lbl_det_matrices.configure(
                text="5 de 5 matrices oficiales identificadas y válidas",
                text_color=("black", "white"),
            )
        else:
            self.lbl_chk_matrices.configure(text="[   ] MATRICES:", text_color="#E57373")
            faltantes = sorted(list(set(["M1", "M2", "M3", "M4", "M5"]) - set(matrices.keys())))
            faltan_str = f"Faltan: {', '.join(faltantes)}" if faltantes else "Incompletas"
            self.lbl_det_matrices.configure(
                text=f"{status.total_matrices_validas} de 5 válidas ({faltan_str})",
                text_color="#E57373",
            )

        # 2. Período
        if status.periodo_valido and periodo:
            self.lbl_chk_periodo.configure(text="[ ✓ ] PERÍODO:", text_color="#4CAF50")
            self.lbl_det_periodo.configure(
                text=periodo.etiqueta,
                text_color=("black", "white"),
            )
        else:
            self.lbl_chk_periodo.configure(text="[   ] PERÍODO:", text_color="#E57373")
            self.lbl_det_periodo.configure(
                text="No configurado o con parámetros inválidos",
                text_color="#E57373",
            )

        # 3. Carpeta de salida
        if status.carpeta_salida_valida:
            self.lbl_chk_salida.configure(text="[ ✓ ] SALIDA:", text_color="#4CAF50")
            self.lbl_det_salida.configure(
                text=f"Carpeta lista: {self.carpeta_salida.name}",
                text_color=("black", "white"),
            )
        else:
            self.lbl_chk_salida.configure(text="[ X ] SALIDA:", text_color="#E57373")
            self.lbl_det_salida.configure(
                text="Sin permisos de escritura en la carpeta",
                text_color="#E57373",
            )

        # 4. Estado general y habilitación del botón
        if status.listo_para_procesar and not self._en_ejecucion:
            self.lbl_estado_aptitud.configure(
                text="ESTADO: LISTO PARA PROCESAR",
                text_color="#4CAF50",
            )
            self.btn_ejecutar.configure(state="normal")
        else:
            if self._en_ejecucion:
                self.lbl_estado_aptitud.configure(
                    text="ESTADO: EJECUCIÓN EN PROGRESO...",
                    text_color="#2196F3",
                )
            elif not status.matrices_completas or not status.periodo_valido or not status.carpeta_salida_valida:
                self.lbl_estado_aptitud.configure(
                    text="ESTADO: REQUISITOS INCOMPLETOS PARA PROCESAR",
                    text_color="#E57373",
                )
            elif not (gen_tec or gen_inst):
                self.lbl_estado_aptitud.configure(
                    text="ESTADO: NO LISTO — SELECCIONE AL MENOS UN INFORME",
                    text_color="#E57373",
                )
            else:
                self.lbl_estado_aptitud.configure(
                    text="ESTADO: REQUISITOS INCOMPLETOS PARA PROCESAR",
                    text_color="#E57373",
                )
            self.btn_ejecutar.configure(state="disabled")

        return status

    def set_ejecucion_activa(self, activa: bool) -> None:
        """Bloquea o desbloquea controles durante la ejecución activa."""
        self._en_ejecucion = activa
        if activa:
            self.btn_ejecutar.configure(state="disabled")
            self.btn_validar.configure(state="disabled")
            self.btn_cambiar_salida.configure(state="disabled")
            self.chk_tecnico.configure(state="disabled")
            self.chk_institucional.configure(state="disabled")
            self.lbl_estado_aptitud.configure(
                text="ESTADO: EJECUCIÓN EN PROGRESO...",
                text_color="#2196F3",
            )
        else:
            self.btn_validar.configure(state="normal")
            self.btn_cambiar_salida.configure(state="normal")
            self.chk_tecnico.configure(state="normal")
            self.chk_institucional.configure(state="normal")
            self.actualizar_estado(self.matrices_actuales, self.periodo_actual)

    def obtener_carpeta_salida(self) -> Path:
        """Retorna la carpeta de salida actual."""
        return self.carpeta_salida

    def obtener_banderas_generacion(self) -> tuple[bool, bool]:
        """Retorna (generar_tecnico, generar_institucional)."""
        return self.chk_var_tecnico.get(), self.chk_var_institucional.get()
