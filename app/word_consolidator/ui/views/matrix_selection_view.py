"""
app.word_consolidator.ui.views.matrix_selection_view

Vista para la selección e identificación estructural de las 5 matrices oficiales BICU.
Permite seleccionar los 5 archivos Excel en cualquier orden (individualmente, selección múltiple o carpeta)
sin importar sus nombres de archivo (p. ej. 'Documento de Kevds3(1).xlsx', 'archivo.xlsx').
Identifica automáticamente cuál corresponde a M1, M2, M3, M4 y M5 mediante su estructura interna.
"""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from app.word_consolidator.ui.services.application_service import (
    ConsolidationAppService,
    MatrixValidationItem,
)
from app.word_consolidator.ui.services.error_translator import (
    NOMBRES_OFICIALES_MATRICES,
)


class MatrixSelectionView(ctk.CTkFrame):
    """
    Componente visual para la selección desacoplada y clasificación estructural de las 5 matrices oficiales.
    """

    def __init__(
        self,
        master: Any,
        on_matrices_changed: Optional[Callable[[Dict[str, Path]], None]] = None,
        **kwargs: Any,
    ):
        super().__init__(master, **kwargs)
        self.on_matrices_changed = on_matrices_changed
        self.archivos_seleccionados: List[Optional[Path]] = [None] * 5
        self.matrices_identificadas: Dict[str, Path] = {}
        self.detalles_matrices: Dict[str, MatrixValidationItem] = {}
        self.ultimo_analisis: Optional[Dict[str, Any]] = None

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO Y EXPLICACIÓN
        # ---------------------------------------------------------------------
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="1. SELECCIÓN DE MATRICES OFICIALES (M1 — M5)",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        desc_lbl = ctk.CTkLabel(
            header_frame,
            text=(
                "Seleccione los cinco archivos Excel en cualquier orden. El sistema identificará "
                "automáticamente cuál corresponde a M1, M2, M3, M4 y M5 analizando su estructura interna."
            ),
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
            wraplength=850,
            justify="left",
        )
        desc_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # ---------------------------------------------------------------------
        # 2. BARRA DE ACCIONES RÁPIDAS
        # ---------------------------------------------------------------------
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=8)

        self.btn_archivos = ctk.CTkButton(
            btn_bar,
            text="📂 Seleccionar los 5 Archivos Excel...",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_seleccionar_archivos_multiples,
            width=240,
            height=32,
        )
        self.btn_archivos.pack(side="left", padx=(0, 10))

        self.btn_carpeta = ctk.CTkButton(
            btn_bar,
            text="📁 Seleccionar Carpeta",
            font=ctk.CTkFont(size=12),
            command=self._on_seleccionar_carpeta,
            width=170,
            height=32,
        )
        self.btn_carpeta.pack(side="left", padx=(0, 10))

        self.btn_limpiar = ctk.CTkButton(
            btn_bar,
            text="Limpiar Selección",
            font=ctk.CTkFont(size=12),
            fg_color="#555555",
            hover_color="#333333",
            command=self.limpiar,
            width=140,
            height=32,
        )
        self.btn_limpiar.pack(side="left")

        # ---------------------------------------------------------------------
        # 3. SLOTS DE ENTRADA GENÉRICOS (Archivo 1 a Archivo 5)
        # ---------------------------------------------------------------------
        self.input_group = ctk.CTkFrame(self, fg_color=("gray95", "gray17"))
        self.input_group.grid(row=2, column=0, sticky="ew", padx=15, pady=6)
        self.input_group.grid_columnconfigure(1, weight=1)

        input_title = ctk.CTkLabel(
            self.input_group,
            text="Archivos Seleccionados (Cualquier Orden):",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        input_title.grid(row=0, column=0, columnspan=3, padx=12, pady=(8, 4), sticky="w")

        self.slot_widgets: List[Dict[str, Any]] = []

        for i in range(5):
            lbl_num = ctk.CTkLabel(
                self.input_group,
                text=f"Archivo {i + 1}:",
                font=ctk.CTkFont(size=12, weight="bold"),
                width=80,
                anchor="w",
            )
            lbl_num.grid(row=i + 1, column=0, padx=(12, 4), pady=3, sticky="w")

            file_box = ctk.CTkLabel(
                self.input_group,
                text="[ No seleccionado ]",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w",
            )
            file_box.grid(row=i + 1, column=1, padx=6, pady=3, sticky="ew")

            btn_exam = ctk.CTkButton(
                self.input_group,
                text="Examinar...",
                width=90,
                height=26,
                font=ctk.CTkFont(size=11),
                command=lambda idx=i: self._on_examinar_archivo_individual(idx),
            )
            btn_exam.grid(row=i + 1, column=2, padx=(4, 12), pady=3)

            self.slot_widgets.append({
                "label_num": lbl_num,
                "label_file": file_box,
                "btn_exam": btn_exam,
            })

        # Botón de Identificación Estructural
        btn_identificar_frame = ctk.CTkFrame(self.input_group, fg_color="transparent")
        btn_identificar_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=12, pady=(8, 10))
        btn_identificar_frame.grid_columnconfigure(0, weight=1)

        self.btn_identificar = ctk.CTkButton(
            btn_identificar_frame,
            text="🔍 IDENTIFICAR MATRICES POR ESTRUCTURA",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=34,
            fg_color="#0B3C5D",
            hover_color="#07263D",
            command=lambda: self.identificar_matrices(mostrar_alertas=True),
        )
        self.btn_identificar.grid(row=0, column=0, sticky="ew")

        # ---------------------------------------------------------------------
        # 4. TARJETAS DE MATRICES IDENTIFICADAS (M1 a M5)
        # ---------------------------------------------------------------------
        self.result_group = ctk.CTkFrame(self, fg_color=("gray95", "gray17"))
        self.result_group.grid(row=3, column=0, sticky="ew", padx=15, pady=6)
        self.result_group.grid_columnconfigure(0, weight=1)

        res_title = ctk.CTkLabel(
            self.result_group,
            text="MATRICES IDENTIFICADAS (Estructura Interna Verificada):",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        res_title.grid(row=0, column=0, padx=12, pady=(8, 4), sticky="w")

        self.matrix_cards: Dict[str, Dict[str, Any]] = {}
        codigos = ["M1", "M2", "M3", "M4", "M5"]

        for idx, cod in enumerate(codigos):
            card_frame = ctk.CTkFrame(self.result_group, fg_color=("gray90", "gray22"))
            card_frame.grid(row=idx + 1, column=0, sticky="ew", padx=10, pady=3)
            card_frame.grid_columnconfigure(2, weight=1)

            icon_lbl = ctk.CTkLabel(
                card_frame,
                text="[   ]",
                font=ctk.CTkFont(size=13, weight="bold"),
                width=35,
                text_color="gray",
            )
            icon_lbl.grid(row=0, column=0, padx=(8, 4), pady=5)

            nombre_oficial = NOMBRES_OFICIALES_MATRICES.get(cod, cod)
            nom_lbl = ctk.CTkLabel(
                card_frame,
                text=nombre_oficial,
                font=ctk.CTkFont(size=12, weight="bold"),
                width=270,
                anchor="w",
            )
            nom_lbl.grid(row=0, column=1, padx=4, pady=5, sticky="w")

            detail_lbl = ctk.CTkLabel(
                card_frame,
                text="No identificada (Falta archivo correspondiente)",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w",
            )
            detail_lbl.grid(row=0, column=2, padx=6, pady=5, sticky="ew")

            self.matrix_cards[cod] = {
                "frame": card_frame,
                "icon": icon_lbl,
                "nombre": nom_lbl,
                "detalle": detail_lbl,
            }

        # ---------------------------------------------------------------------
        # 5. ESTADO GLOBAL Y BANNER DE OBSERVACIONES
        # ---------------------------------------------------------------------
        self.status_lbl = ctk.CTkLabel(
            self,
            text="Estado: 0 de 5 matrices identificadas.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#E57373",
            anchor="w",
        )
        self.status_lbl.grid(row=4, column=0, sticky="w", padx=15, pady=(5, 4))

        self.error_banner = ctk.CTkFrame(self, fg_color=("#FFEBEE", "#3E2723"), corner_radius=6)
        self.error_banner.grid_columnconfigure(0, weight=1)
        self.error_banner_title = ctk.CTkLabel(
            self.error_banner,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#C62828",
            anchor="w",
        )
        self.error_banner_title.grid(row=0, column=0, padx=12, pady=(6, 2), sticky="w")

        self.error_banner_msg = ctk.CTkLabel(
            self.error_banner,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#B71C1C",
            anchor="w",
            justify="left",
        )
        self.error_banner_msg.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="w")

    # -------------------------------------------------------------------------
    # GESTIÓN DE ENTRADAS DE ARCHIVO
    # -------------------------------------------------------------------------
    def _on_seleccionar_archivos_multiples(self) -> None:
        """Abre el diálogo para seleccionar múltiples archivos Excel a la vez."""
        archivos = filedialog.askopenfilenames(
            title="Seleccionar 5 Matrices Excel BICU (Cualquier Orden)",
            filetypes=[("Archivos Excel", "*.xlsx *.xlsm"), ("Todos los archivos", "*.*")],
        )
        if not archivos:
            return

        self.limpiar()
        for idx, a in enumerate(archivos[:5]):
            self.archivos_seleccionados[idx] = Path(a)

        self._actualizar_etiquetas_slots()
        self.identificar_matrices(mostrar_alertas=False)

    def _on_seleccionar_carpeta(self) -> None:
        """Abre el diálogo para seleccionar una carpeta con las 5 matrices."""
        carpeta = filedialog.askdirectory(title="Seleccionar Carpeta con Matrices BICU")
        if not carpeta:
            return

        p = Path(carpeta)
        archivos = [
            f for f in sorted(p.iterdir())
            if f.is_file() and f.suffix.lower() in (".xlsx", ".xlsm") and not f.name.startswith("~$")
        ]

        self.limpiar()
        for idx, a in enumerate(archivos[:5]):
            self.archivos_seleccionados[idx] = a

        self._actualizar_etiquetas_slots()
        self.identificar_matrices(mostrar_alertas=False)

    def _on_examinar_archivo_individual(self, idx: int) -> None:
        """Permite seleccionar un archivo específico para el slot idx (0..4)."""
        archivo = filedialog.askopenfilename(
            title=f"Seleccionar Archivo {idx + 1}",
            filetypes=[("Archivos Excel", "*.xlsx *.xlsm"), ("Todos los archivos", "*.*")],
        )
        if not archivo:
            return

        self.archivos_seleccionados[idx] = Path(archivo)
        self._actualizar_etiquetas_slots()
        self.identificar_matrices(mostrar_alertas=False)

    def _actualizar_etiquetas_slots(self) -> None:
        """Actualiza el texto de los 5 slots de entrada."""
        for i in range(5):
            p = self.archivos_seleccionados[i]
            w = self.slot_widgets[i]
            if p:
                w["label_file"].configure(text=p.name, text_color=("black", "white"))
            else:
                w["label_file"].configure(text="[ No seleccionado ]", text_color="gray")

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN ESTRUCTURAL Y REORGANIZACIÓN DETERMINÍSTICA
    # -------------------------------------------------------------------------
    def identificar_matrices(self, mostrar_alertas: bool = False) -> Dict[str, Path]:
        """
        Ejecuta la identificación estructural mediante MatrixIdentifier.
        Reorganiza los archivos sin importar el orden ni el nombre y actualiza las tarjetas.
        """
        rutas_validas = [p for p in self.archivos_seleccionados if p is not None]

        if not rutas_validas:
            self._mostrar_estado_vacio()
            if mostrar_alertas:
                messagebox.showinfo(
                    "Identificación de Matrices",
                    "Seleccione al menos un archivo Excel para iniciar la identificación estructural.",
                )
            return {}

        analisis = ConsolidationAppService.analizar_conjunto_archivos(rutas_validas)
        self.ultimo_analisis = analisis
        self.matrices_identificadas = analisis["matrices"]
        self.detalles_matrices = analisis["detalles"]

        # Actualizar visualmente las tarjetas M1 a M5
        total_ok = 0
        for cod in ["M1", "M2", "M3", "M4", "M5"]:
            item = self.detalles_matrices.get(cod)
            card = self.matrix_cards[cod]
            if item and item.es_valido:
                total_ok += 1
                card["icon"].configure(text="✓", text_color="#4CAF50")
                if cod == "M5":
                    detalle_txt = f"{item.nombre_archivo}  —  Estructura reconocida ({item.total_columnas} cols — 32 históricos)"
                else:
                    detalle_txt = f"{item.nombre_archivo}  —  Estructura reconocida ({item.total_columnas} columnas)"
                card["detalle"].configure(
                    text=detalle_txt,
                    text_color=("black", "white"),
                )
            else:
                if cod in analisis.get("duplicados", {}):
                    card["icon"].configure(text="✕", text_color="#E57373")
                    card["detalle"].configure(
                        text=f"MATRIZ DUPLICADA ({len(analisis['duplicados'][cod])} archivos coinciden)",
                        text_color="#E57373",
                    )
                else:
                    card["icon"].configure(text="[   ]", text_color="gray")
                    card["detalle"].configure(
                        text="No identificada (Falta archivo correspondiente)",
                        text_color="gray",
                    )

        # Actualizar etiqueta de estado global
        if total_ok == 5:
            self.status_lbl.configure(
                text="✓ 5 de 5 matrices identificadas y verificadas estructuralmente.",
                text_color="#4CAF50",
            )
            self._ocultar_banner_error()
        else:
            if analisis.get("duplicados"):
                self.status_lbl.configure(
                    text="Estado: Conflicto detectado (Matriz duplicada).",
                    text_color="#E57373",
                )
            else:
                faltan = analisis.get("faltantes", [])
                faltan_str = ", ".join(faltan) if faltan else "Ninguna"
                self.status_lbl.configure(
                    text=f"Estado: {total_ok} de 5 matrices identificadas. Faltan: {faltan_str}",
                    text_color="#E57373",
                )

        # Procesar resumen de errores
        error_res = analisis.get("error_resumen")
        if error_res:
            self._mostrar_banner_error(error_res["titulo"], error_res["mensaje"])
            if mostrar_alertas:
                messagebox.showerror(error_res["titulo"], error_res["mensaje"])
        else:
            self._ocultar_banner_error()

        if self.on_matrices_changed:
            self.on_matrices_changed(self.matrices_identificadas)

        return dict(self.matrices_identificadas)

    def _mostrar_banner_error(self, titulo: str, mensaje: str) -> None:
        """Muestra el banner de advertencia/error institucional."""
        self.error_banner_title.configure(text=f"⚠️ {titulo.upper()}")
        self.error_banner_msg.configure(text=mensaje)
        self.error_banner.grid(row=5, column=0, sticky="ew", padx=15, pady=(4, 10))

    def _ocultar_banner_error(self) -> None:
        """Oculta el banner de advertencia/error."""
        self.error_banner.grid_forget()

    def _mostrar_estado_vacio(self) -> None:
        """Restablece los textos a estado sin selección."""
        for cod in ["M1", "M2", "M3", "M4", "M5"]:
            card = self.matrix_cards[cod]
            card["icon"].configure(text="[   ]", text_color="gray")
            card["detalle"].configure(
                text="No identificada (Falta archivo correspondiente)",
                text_color="gray",
            )
        self.status_lbl.configure(
            text="Estado: 0 de 5 matrices identificadas.",
            text_color="#E57373",
        )
        self._ocultar_banner_error()

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS DE INTERFAZ
    # -------------------------------------------------------------------------
    def cargar_matrices_directas(self, fuentes: Dict[str, Path]) -> None:
        """
        Carga matrices programáticamente (compatibilidad con suites de prueba y presets).
        Asigna a los slots y ejecuta la identificación estructural.
        """
        self.limpiar()
        rutas = list(fuentes.values())
        for idx, r in enumerate(rutas[:5]):
            self.archivos_seleccionados[idx] = Path(r)

        self._actualizar_etiquetas_slots()
        self.identificar_matrices(mostrar_alertas=False)

    def limpiar(self) -> None:
        """Restablece completamente la selección de archivos y el estado."""
        self.archivos_seleccionados = [None] * 5
        self.matrices_identificadas.clear()
        self.detalles_matrices.clear()
        self.ultimo_analisis = None
        self._actualizar_etiquetas_slots()
        self._mostrar_estado_vacio()

        if self.on_matrices_changed:
            self.on_matrices_changed({})

    def obtener_matrices(self) -> Dict[str, Path]:
        """Retorna el diccionario de matrices identificadas válidas (M1..M5)."""
        return dict(self.matrices_identificadas)

