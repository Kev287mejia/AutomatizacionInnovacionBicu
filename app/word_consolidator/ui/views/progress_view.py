"""
app.word_consolidator.ui.views.progress_view

Vista de progreso determinístico por etapas reales del pipeline (Fase 14.9).
Muestra las 9 etapas reales del procesamiento institucional sin porcentajes falsos ni barras simuladas.
"""

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from app.word_consolidator.ui.workers.consolidation_worker import ETAPAS_PIPELINE


class ProgressView(ctk.CTkFrame):
    """
    Componente visual que refleja fielmente las etapas del pipeline en tiempo real.
    """

    def __init__(
        self,
        master: Any,
        etapas: Optional[List[Dict[str, Any]]] = None,
        titulo: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(master, **kwargs)
        self.etapas: List[Dict[str, Any]] = etapas if etapas is not None else ETAPAS_PIPELINE
        self.titulo_texto: str = titulo or "PROGRESO DE CONSOLIDACIÓN INSTITUCIONAL"
        self.stage_widgets: Dict[int, Dict[str, Any]] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Encabezado
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        self.title_lbl = ctk.CTkLabel(
            header_frame,
            text=self.titulo_texto,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self.title_lbl.pack(anchor="w")

        self.subtitle_lbl = ctk.CTkLabel(
            header_frame,
            text="Esperando inicio de consolidación...",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        self.subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # Panel contenedor de las etapas
        self.stages_container = ctk.CTkFrame(self)
        self.stages_container.grid(row=1, column=0, sticky="ew", padx=15, pady=8)
        self.stages_container.grid_columnconfigure(1, weight=1)

        total_etapas = len(self.etapas)
        for item in self.etapas:
            idx = item["index"]
            name = item["name"]

            row_frame = ctk.CTkFrame(self.stages_container, fg_color=("gray92", "gray20"))
            row_frame.grid(row=idx - 1, column=0, columnspan=2, sticky="ew", padx=8, pady=3)
            row_frame.grid_columnconfigure(1, weight=1)

            icon_lbl = ctk.CTkLabel(
                row_frame,
                text="[   ]",
                font=ctk.CTkFont(size=12, weight="bold"),
                width=45,
                text_color="gray",
            )
            icon_lbl.grid(row=0, column=0, padx=(8, 4), pady=4)

            name_lbl = ctk.CTkLabel(
                row_frame,
                text=f"Etapa {idx}/{total_etapas}: {name}",
                font=ctk.CTkFont(size=12),
                text_color="gray",
                anchor="w",
            )
            name_lbl.grid(row=0, column=1, padx=4, pady=4, sticky="w")

            status_lbl = ctk.CTkLabel(
                row_frame,
                text="Pendiente",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                width=100,
                anchor="e",
            )
            status_lbl.grid(row=0, column=2, padx=(4, 10), pady=4)

            self.stage_widgets[idx] = {
                "frame": row_frame,
                "icon": icon_lbl,
                "name": name_lbl,
                "status": status_lbl,
            }

        # Sub-panel para avisos o advertencias durante el proceso
        self.warning_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray18"))
        self.warning_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(4, 10))
        self.warning_frame.grid_columnconfigure(0, weight=1)

        self.lbl_warning = ctk.CTkLabel(
            self.warning_frame,
            text="Observaciones: El pipeline opera en modo estrictamente determinístico y no destructivo.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        )
        self.lbl_warning.grid(row=0, column=0, padx=10, pady=6, sticky="w")

    def reiniciar(self) -> None:
        """Restablece visualmente todas las etapas al estado pendiente."""
        self.subtitle_lbl.configure(
            text="Iniciando ejecución institucional...",
            text_color=("black", "white"),
        )
        for item in self.etapas:
            idx = item["index"]
            if idx in self.stage_widgets:
                w = self.stage_widgets[idx]
                w["icon"].configure(text="[   ]", text_color="gray")
                w["name"].configure(text_color="gray")
                w["status"].configure(text="Pendiente", text_color="gray")
        self.lbl_warning.configure(
            text="Observaciones: Procesando en segundo plano...",
            text_color="gray",
        )

    def etapa_iniciada(self, step_index: int, step_name: str) -> None:
        """Marca una etapa como en ejecución activa."""
        self.subtitle_lbl.configure(
            text=f"Ejecutando: {step_name}...",
            text_color=("#0B3C5D", "#4FC3F7"),
        )
        if step_index in self.stage_widgets:
            w = self.stage_widgets[step_index]
            w["icon"].configure(text="[ ● ]", text_color="#2196F3")
            w["name"].configure(text_color=("black", "white"))
            w["status"].configure(text="En progreso...", text_color="#2196F3")

    def etapa_completada(self, step_index: int, step_name: str) -> None:
        """Marca una etapa como completada con éxito."""
        if step_index in self.stage_widgets:
            w = self.stage_widgets[step_index]
            w["icon"].configure(text="[ ✓ ]", text_color="#4CAF50")
            w["name"].configure(text_color=("black", "white"))
            w["status"].configure(text="Finalizada", text_color="#4CAF50")

    def etapa_fallida(self, step_index: int, step_name: str, error_msg: str) -> None:
        """Marca una etapa como fallida."""
        self.subtitle_lbl.configure(
            text=f"Error en Etapa {step_index}: {step_name}",
            text_color="#E57373",
        )
        if step_index in self.stage_widgets:
            w = self.stage_widgets[step_index]
            w["icon"].configure(text="[ ✕ ]", text_color="#E57373")
            w["name"].configure(text_color="#E57373")
            w["status"].configure(text="Error", text_color="#E57373")
        self.lbl_warning.configure(
            text=f"Detalle: {error_msg[:120]}...",
            text_color="#E57373",
        )

    def agregar_advertencia(self, mensaje: str) -> None:
        """Muestra una advertencia institucional no bloqueante."""
        self.lbl_warning.configure(
            text=f"Aviso: {mensaje}",
            text_color="#FFA726",
        )

    def finalizar_exitoso(self, mensaje: Optional[str] = None) -> None:
        """Marca el conjunto de etapas como culminado con éxito."""
        self.subtitle_lbl.configure(
            text=mensaje or "✓ Proceso completado exitosamente.",
            text_color="#4CAF50",
        )
        for item in self.etapas:
            idx = item["index"]
            if idx in self.stage_widgets:
                w = self.stage_widgets[idx]
                w["icon"].configure(text="[ ✓ ]", text_color="#4CAF50")
                w["name"].configure(text_color=("black", "white"))
                w["status"].configure(text="Finalizada", text_color="#4CAF50")
