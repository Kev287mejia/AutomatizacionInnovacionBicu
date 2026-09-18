"""
app.word_consolidator.ui.views.main_window

Ventana principal integradora de la aplicación de escritorio BICU (Fase 14.9).
Coordina la navegación por pestañas/etapas, la comunicación asíncrona con el worker
y el flujo de usuario desde la selección de matrices hasta la apertura del informe Word.
"""

from pathlib import Path
import queue
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict, Optional

import customtkinter as ctk

from app.word_consolidator.models import PeriodoConsolidacion
from app.word_consolidator.pipeline import PipelineExecutionResult
from app.word_consolidator.ui.services.application_service import (
    ConsolidationAppService,
)
from app.word_consolidator.ui.views.matrix_selection_view import (
    MatrixSelectionView,
)
from app.word_consolidator.ui.views.period_selection_view import (
    PeriodSelectionView,
)
from app.word_consolidator.ui.views.progress_view import ProgressView
from app.word_consolidator.ui.views.result_view import ResultView
from app.word_consolidator.ui.views.validation_view import ValidationView
from app.word_consolidator.ui.workers.consolidation_worker import (
    ConsolidationEvent,
    ConsolidationEventType,
    ConsolidationWorker,
)


class MainWindow(ctk.CTkFrame):
    """
    Contenedor principal e integrador de flujo de la interfaz institucional BICU.
    """

    def __init__(self, master: Any, **kwargs: Any):
        super().__init__(master, **kwargs)
        self.worker: Optional[ConsolidationWorker] = None
        self.event_queue: queue.Queue = queue.Queue()
        self._polling_id: Optional[str] = None

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # ENCABEZADO INSTITUCIONAL
        # ---------------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color=("#0B3C5D", "#1A2634"), corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header,
            text="BLUEFIELDS INDIAN & CARIBBEAN UNIVERSITY — BICU",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white",
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, padx=20, pady=(12, 2), sticky="w")

        sub_lbl = ctk.CTkLabel(
            header,
            text="Sistema Automatizado de Consolidación de Asistencias → Informe Word Institucional",
            font=ctk.CTkFont(size=12),
            text_color=("#E0E0E0", "#B0BEC5"),
            anchor="w",
        )
        sub_lbl.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        # ---------------------------------------------------------------------
        # PESTAÑAS DE FLUJO OPERATIVO (Tabview)
        # ---------------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        self.tab_config = self.tabview.add("1. Matrices y Período")
        self.tab_exec = self.tabview.add("2. Validación y Ejecución")
        self.tab_result = self.tabview.add("3. Resultados y Auditoría")

        self.tab_config.grid_columnconfigure(0, weight=1)
        self.tab_config.grid_rowconfigure(0, weight=1)
        self.tab_exec.grid_columnconfigure(0, weight=1)
        self.tab_exec.grid_rowconfigure(0, weight=1)
        self.tab_result.grid_columnconfigure(0, weight=1)
        self.tab_result.grid_rowconfigure(0, weight=1)

        # Pestaña 1: Matrices y Período (con ScrollableFrame para rueda de ratón / touchpad)
        self.scroll_config = ctk.CTkScrollableFrame(self.tab_config, fg_color="transparent")
        self.scroll_config.grid(row=0, column=0, sticky="nsew")
        self.scroll_config.grid_columnconfigure(0, weight=1)

        self.matrix_view = MatrixSelectionView(
            self.scroll_config,
            on_matrices_changed=self._on_matrices_o_periodo_cambiados,
        )
        self.matrix_view.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))

        self.period_view = PeriodSelectionView(
            self.scroll_config,
            on_periodo_changed=self._on_matrices_o_periodo_cambiados,
        )
        self.period_view.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Botón de paso a la pestaña de validación
        btn_ir_val = ctk.CTkButton(
            self.scroll_config,
            text="Continuar a Validación y Ejecución  ➔",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
            command=self._on_click_continuar_a_validacion,
        )
        btn_ir_val.grid(row=2, column=0, sticky="e", padx=10, pady=(0, 15))

        # Pestaña 2: Validación y Progreso (con ScrollableFrame)
        self.scroll_exec = ctk.CTkScrollableFrame(self.tab_exec, fg_color="transparent")
        self.scroll_exec.grid(row=0, column=0, sticky="nsew")
        self.scroll_exec.grid_columnconfigure(0, weight=1)

        self.validation_view = ValidationView(
            self.scroll_exec,
            on_ejecutar_click=self._on_iniciar_ejecucion,
            on_validar_click=self._on_validar_exploratorio,
        )
        self.validation_view.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))

        self.progress_view = ProgressView(self.scroll_exec)
        self.progress_view.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Pestaña 3: Resultados (con ScrollableFrame)
        self.scroll_result = ctk.CTkScrollableFrame(self.tab_result, fg_color="transparent")
        self.scroll_result.grid(row=0, column=0, sticky="nsew")
        self.scroll_result.grid_columnconfigure(0, weight=1)
        self.scroll_result.grid_rowconfigure(0, weight=1)

        self.result_view = ResultView(
            self.scroll_result,
            on_nueva_consolidacion=self._on_nueva_consolidacion,
        )
        self.result_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # ---------------------------------------------------------------------
        # PIE DE PÁGINA INSTITUCIONAL (Footer)
        # ---------------------------------------------------------------------
        footer_frame = ctk.CTkFrame(self, fg_color="transparent", height=20)
        footer_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 6))

        footer_lbl = ctk.CTkLabel(
            footer_frame,
            text="Made With Love By: Kevin Mejía Montalván",
            font=ctk.CTkFont(size=11),
            text_color=("#666666", "#999999"),
            anchor="center",
        )
        footer_lbl.pack(fill="x")

        # Sincronización inicial
        self._sincronizar_preflight()

    def _on_click_continuar_a_validacion(self) -> None:
        """Verifica que las 5 matrices estén identificadas antes de avanzar a la pestaña 2."""
        matrices = self.matrix_view.obtener_matrices()
        if len(matrices) != 5:
            analisis = getattr(self.matrix_view, "ultimo_analisis", None)
            if analisis and analisis.get("error_resumen"):
                res = analisis["error_resumen"]
                messagebox.showerror(res["titulo"], res["mensaje"])
            else:
                messagebox.showwarning(
                    "Matrices Incompletas",
                    "Debe identificar las 5 matrices oficiales de BICU antes de continuar a la validación y ejecución.",
                )
            return
        self.tabview.set("2. Validación y Ejecución")

    def _on_matrices_o_periodo_cambiados(self, *_: Any) -> None:
        """Callback al alterar la selección de matrices o parámetros temporales."""
        self._sincronizar_preflight()

    def _on_validar_exploratorio(self) -> None:
        """Ejecuta validación exploratoria sin iniciar consolidación."""
        status = self._sincronizar_preflight()
        if status.errores_bloqueantes:
            err_text = "\n• ".join(status.errores_bloqueantes)
            messagebox.showwarning(
                "Validación de Matrices",
                f"Se detectaron las siguientes observaciones:\n\n• {err_text}",
            )
        else:
            messagebox.showinfo(
                "Validación de Matrices",
                "✓ Las 5 matrices oficiales y los parámetros son válidos y están listos para consolidar.",
            )

    def _sincronizar_preflight(self) -> Any:
        """Sincroniza el estado de validación en la vista de validación."""
        if not getattr(self, "matrix_view", None) or not getattr(self, "period_view", None) or not getattr(self, "validation_view", None):
            return None
        matrices = self.matrix_view.obtener_matrices()
        periodo = self.period_view.obtener_periodo()
        return self.validation_view.actualizar_estado(matrices, periodo)

    def _on_iniciar_ejecucion(self) -> None:
        """Inicia el pipeline en el hilo de trabajo secundario."""
        matrices = self.matrix_view.obtener_matrices()
        periodo = self.period_view.obtener_periodo()
        salida_dir = self.validation_view.obtener_carpeta_salida()

        if len(matrices) != 5 or not periodo:
            messagebox.showwarning(
                "Requisitos Incompletos",
                "Asegúrese de contar con las 5 matrices identificadas y un período configurado antes de ejecutar.",
            )
            return

        # Bloquear controles y preparar visualización
        self.validation_view.set_ejecucion_activa(True)
        self.progress_view.reiniciar()

        # Limpiar cola de eventos anterior
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except Exception:
                break

        # Obtener banderas de generación
        gen_tec, gen_inst = self.validation_view.obtener_banderas_generacion()
        if not (gen_tec or gen_inst):
            messagebox.showwarning(
                "Selección Requerida",
                "Seleccione al menos un informe para generar (Informe Técnico o Informe Institucional).",
            )
            return

        # Obtener informes narrativos institucionales si existen para evaluar discrepancias
        carpeta_matrices = next(iter(matrices.values())).parent if matrices else None
        informes_narrativos = ConsolidationAppService.obtener_informes_narrativos_institucionales(
            periodo=periodo,
            carpeta_matrices=carpeta_matrices,
        )

        # Obtener metadatos institucionales oficiales predeterminados
        metadatos = ConsolidationAppService.obtener_metadatos_institucionales_predeterminados()

        # Instanciar y lanzar el worker en segundo plano
        self.worker = ConsolidationWorker(
            fuentes=matrices,
            periodo=periodo,
            salida_dir=salida_dir,
            event_queue=self.event_queue,
            metadatos=metadatos,
            informes_narrativos=informes_narrativos,
            generar_tecnico=gen_tec,
            generar_institucional=gen_inst,
        )
        self.worker.start()

        # Iniciar ciclo de polling no bloqueante en el bucle principal de Tkinter
        self._programar_polling_cola()

    def _programar_polling_cola(self) -> None:
        """Programa la revisión periódica de la cola de eventos en el hilo principal."""
        self._procesar_eventos_pendientes()
        if self.worker and self.worker.is_alive():
            self._polling_id = self.after(50, self._programar_polling_cola)
        else:
            # Procesar últimos eventos remanentes
            self._procesar_eventos_pendientes()

    def _procesar_eventos_pendientes(self) -> None:
        """Extrae y procesa los eventos disponibles en la cola de mensajes."""
        while not self.event_queue.empty():
            try:
                evento: ConsolidationEvent = self.event_queue.get_nowait()
            except Exception:
                break

            tipo = evento.event_type

            if tipo == ConsolidationEventType.STEP_STARTED:
                if evento.step_index and evento.step_name:
                    self.progress_view.etapa_iniciada(evento.step_index, evento.step_name)

            elif tipo == ConsolidationEventType.STEP_COMPLETED:
                if evento.step_index and evento.step_name:
                    self.progress_view.etapa_completada(evento.step_index, evento.step_name)

            elif tipo == ConsolidationEventType.WARNING:
                if evento.message:
                    self.progress_view.agregar_advertencia(evento.message)

            elif tipo == ConsolidationEventType.STEP_FAILED:
                if evento.step_index and evento.step_name:
                    self.progress_view.etapa_fallida(
                        evento.step_index,
                        evento.step_name,
                        evento.message or "Fallo de ejecución",
                    )

            elif tipo == ConsolidationEventType.ERROR:
                self.validation_view.set_ejecucion_activa(False)
                info = evento.error_info
                if info:
                    messagebox.showerror(info.titulo, info.mensaje_completo())
                else:
                    messagebox.showerror("Error en Consolidación", evento.message or "Error inesperado")

            elif tipo == ConsolidationEventType.COMPLETED:
                self.progress_view.finalizar_exitoso()
                self.validation_view.set_ejecucion_activa(False)
                if evento.result:
                    self.result_view.mostrar_resultado(evento.result)
                    # Cambiar automáticamente a la pestaña de resultados
                    self.tabview.set("3. Resultados y Auditoría")

    def _on_nueva_consolidacion(self) -> None:
        """Restablece el flujo para una nueva consolidación."""
        self.progress_view.reiniciar()
        self.tabview.set("1. Matrices y Período")
        self._sincronizar_preflight()
