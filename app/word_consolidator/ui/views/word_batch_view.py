"""app.word_consolidator.ui.views.word_batch_view

Vista principal para el procesamiento por lote de documentos Word hacia matrices M1–M5 (Fase 28.2).
Fachada desacoplada que valida carpetas de entrada/salida, parametriza el período,
monitorea el worker asíncrono y presenta los resultados institucionales.
"""

from pathlib import Path
import queue
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional, Union

import customtkinter as ctk

from app.application.dto.batch_dtos import BatchArchivoResultadoDTO, BatchResultadoDTO
from app.word_consolidator.models import PeriodoConsolidacion
from app.word_consolidator.ui.services.word_batch_service import (
    WordBatchAppService,
    WordBatchPreflightStatus,
)
from app.word_consolidator.ui.views.period_selection_view import (
    PeriodSelectionView,
)
from app.word_consolidator.ui.views.progress_view import ProgressView
from app.word_consolidator.ui.views.result_view import (
    _abrir_archivo_so,
    _abrir_carpeta_so,
)
from app.word_consolidator.ui.workers.word_batch_worker import (
    ETAPAS_WORD_BATCH,
    WordBatchEvent,
    WordBatchEventType,
    WordBatchWorker,
)


class WordBatchProcessingView(ctk.CTkFrame):
    """Componente visual que orquesta el flujo completo de Word → Matrices M1–M5."""

    def __init__(
        self,
        master: Any,
        on_volver_menu: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_volver_menu = on_volver_menu

        self.carpeta_origen: Optional[Path] = None
        self.carpeta_salida: Path = WordBatchAppService.resolver_directorio_salida_predeterminado()
        self.periodo_actual: Optional[PeriodoConsolidacion] = None
        self.preflight_status: Optional[WordBatchPreflightStatus] = None

        self.worker: Optional[WordBatchWorker] = None
        self.event_queue: queue.Queue = queue.Queue()
        self._polling_id: Optional[str] = None
        self.resultado_batch: Optional[BatchResultadoDTO] = None

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
        header.grid_columnconfigure(1, weight=0)

        title_lbl = ctk.CTkLabel(
            header,
            text="BLUEFIELDS INDIAN & CARIBBEAN UNIVERSITY — BICU",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="white",
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, padx=20, pady=(12, 2), sticky="w")

        sub_lbl = ctk.CTkLabel(
            header,
            text="Módulo 1: Procesamiento de Informes Word → Matrices Oficiales M1–M5",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#E0E0E0", "#B0BEC5"),
            anchor="w",
        )
        sub_lbl.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        if self.on_volver_menu:
            btn_volver = ctk.CTkButton(
                header,
                text="← Menú Principal",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#1A2634",
                hover_color="#07263D",
                width=130,
                height=32,
                corner_radius=5,
                command=self.on_volver_menu,
            )
            btn_volver.grid(row=0, column=1, rowspan=2, padx=15, pady=10, sticky="e")

        # ---------------------------------------------------------------------
        # 2. PESTAÑAS DE FLUJO OPERATIVO
        # ---------------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        self.tab_config = self.tabview.add("1. Carpeta y Parámetros")
        self.tab_exec = self.tabview.add("2. Validación y Ejecución")
        self.tab_result = self.tabview.add("3. Resultados y Auditoría")

        self.tab_config.grid_columnconfigure(0, weight=1)
        self.tab_config.grid_rowconfigure(0, weight=1)
        self.tab_exec.grid_columnconfigure(0, weight=1)
        self.tab_exec.grid_rowconfigure(0, weight=1)
        self.tab_result.grid_columnconfigure(0, weight=1)
        self.tab_result.grid_rowconfigure(0, weight=1)

        # ---------------------------------------------------------------------
        # PESTAÑA 1: CARPETA Y PARÁMETROS
        # ---------------------------------------------------------------------
        scroll_config = ctk.CTkScrollableFrame(self.tab_config, fg_color="transparent")
        scroll_config.grid(row=0, column=0, sticky="nsew")
        scroll_config.grid_columnconfigure(0, weight=1)

        # Sección 1: Selección de Carpeta Origen
        grp_origen = ctk.CTkFrame(scroll_config, fg_color=("gray92", "gray17"), corner_radius=6)
        grp_origen.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))
        grp_origen.grid_columnconfigure(1, weight=1)

        lbl_orig_title = ctk.CTkLabel(
            grp_origen,
            text="1. CARPETA DE DOCUMENTOS WORD (.DOCX):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
        )
        lbl_orig_title.grid(row=0, column=0, columnspan=3, padx=14, pady=(10, 4), sticky="w")

        lbl_orig_desc = ctk.CTkLabel(
            grp_origen,
            text="Seleccione la carpeta que contiene los informes de actividades Word institucionales.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
            anchor="w",
        )
        lbl_orig_desc.grid(row=1, column=0, columnspan=3, padx=14, pady=(0, 8), sticky="w")

        self.lbl_path_origen = ctk.CTkLabel(
            grp_origen,
            text="[ No seleccionada — Seleccione una carpeta ]",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_path_origen.grid(row=2, column=0, columnspan=2, padx=14, pady=6, sticky="ew")

        btn_examinar = ctk.CTkButton(
            grp_origen,
            text="Examinar Carpeta...",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=160,
            height=32,
            corner_radius=5,
            command=self._on_seleccionar_carpeta_origen,
        )
        btn_examinar.grid(row=2, column=2, padx=14, pady=6, sticky="e")

        self.lbl_resumen_descubrimiento = ctk.CTkLabel(
            grp_origen,
            text="Documentos encontrados: 0  |  Temporales excluidos (~$*): 0  |  Listos: 0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="gray",
            anchor="w",
        )
        self.lbl_resumen_descubrimiento.grid(row=3, column=0, columnspan=3, padx=14, pady=(0, 10), sticky="w")

        # Sección 2: Configuración de Período Institucional (Reutilizado)
        self.period_view = PeriodSelectionView(
            scroll_config,
            on_periodo_changed=self._on_periodo_cambiado,
        )
        self.period_view.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Sección 3: Carpeta de Salida
        grp_salida = ctk.CTkFrame(scroll_config, fg_color=("gray92", "gray17"), corner_radius=6)
        grp_salida.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 15))
        grp_salida.grid_columnconfigure(1, weight=1)

        lbl_salida_title = ctk.CTkLabel(
            grp_salida,
            text="3. CARPETA DE SALIDA PARA MATRICES M1–M5:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
        )
        lbl_salida_title.grid(row=0, column=0, columnspan=3, padx=14, pady=(10, 4), sticky="w")

        self.lbl_path_salida = ctk.CTkLabel(
            grp_salida,
            text=str(self.carpeta_salida),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            anchor="w",
        )
        self.lbl_path_salida.grid(row=1, column=0, columnspan=2, padx=14, pady=6, sticky="ew")

        btn_salida = ctk.CTkButton(
            grp_salida,
            text="Cambiar Carpeta...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            width=160,
            height=30,
            corner_radius=5,
            command=self._on_cambiar_carpeta_salida,
        )
        btn_salida.grid(row=1, column=2, padx=14, pady=6, sticky="e")

        btn_ir_val = ctk.CTkButton(
            scroll_config,
            text="Continuar a Validación y Ejecución  ➔",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=36,
            corner_radius=5,
            command=self._on_click_continuar_a_validacion,
        )
        btn_ir_val.grid(row=3, column=0, sticky="e", padx=10, pady=(0, 15))

        # ---------------------------------------------------------------------
        # PESTAÑA 2: VALIDACIÓN Y EJECUCIÓN
        # ---------------------------------------------------------------------
        scroll_exec = ctk.CTkScrollableFrame(self.tab_exec, fg_color="transparent")
        scroll_exec.grid(row=0, column=0, sticky="nsew")
        scroll_exec.grid_columnconfigure(0, weight=1)

        # Tarjeta Pre-Vuelo
        self.card_preflight = ctk.CTkFrame(scroll_exec, fg_color=("gray92", "gray17"), corner_radius=6)
        self.card_preflight.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 10))
        self.card_preflight.grid_columnconfigure(1, weight=1)

        lbl_pf_title = ctk.CTkLabel(
            self.card_preflight,
            text="RESUMEN DE VALIDACIÓN PREVIA (PREFLIGHT)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
        )
        lbl_pf_title.grid(row=0, column=0, columnspan=2, padx=14, pady=(10, 6), sticky="w")

        self.lbl_pf_origen = ctk.CTkLabel(
            self.card_preflight,
            text="• Carpeta Origen: Pendiente de selección",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_pf_origen.grid(row=1, column=0, columnspan=2, padx=14, pady=2, sticky="w")

        self.lbl_pf_candidatos = ctk.CTkLabel(
            self.card_preflight,
            text="• Documentos listos para procesar: 0",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_pf_candidatos.grid(row=2, column=0, columnspan=2, padx=14, pady=2, sticky="w")

        self.lbl_pf_periodo = ctk.CTkLabel(
            self.card_preflight,
            text="• Período institucional: Pendiente",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_pf_periodo.grid(row=3, column=0, columnspan=2, padx=14, pady=2, sticky="w")

        self.lbl_pf_salida = ctk.CTkLabel(
            self.card_preflight,
            text=f"• Destino: {self.carpeta_salida}",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_pf_salida.grid(row=4, column=0, columnspan=2, padx=14, pady=2, sticky="w")

        self.lbl_pf_estado = ctk.CTkLabel(
            self.card_preflight,
            text="Estado: Seleccione una carpeta con documentos Word para habilitar la ejecución.",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#FFA726",
            anchor="w",
        )
        self.lbl_pf_estado.grid(row=5, column=0, columnspan=2, padx=14, pady=(6, 12), sticky="w")

        # Control de Simulación (Dry-Run)
        self.chk_dry_run = ctk.CTkCheckBox(
            scroll_exec,
            text="Modo Simulación (Dry-Run: valida y calcula sin escribir en SQLite ni exportar archivos)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.chk_dry_run.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        # Botón de Procesamiento Convencional
        self.btn_procesar = ctk.CTkButton(
            scroll_exec,
            text="Procesar documentos",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=38,
            corner_radius=5,
            command=self._on_iniciar_procesamiento,
        )
        self.btn_procesar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 15))

        # Monitor de Progreso Reutilizado
        self.progress_view = ProgressView(
            scroll_exec,
            etapas=ETAPAS_WORD_BATCH,
            titulo="PROGRESO DE PROCESAMIENTO POR LOTE",
        )
        self.progress_view.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

        # ---------------------------------------------------------------------
        # PESTAÑA 3: RESULTADOS Y AUDITORÍA
        # ---------------------------------------------------------------------
        scroll_result = ctk.CTkScrollableFrame(self.tab_result, fg_color="transparent")
        scroll_result.grid(row=0, column=0, sticky="nsew")
        scroll_result.grid_columnconfigure(0, weight=1)

        # Encabezado de Resultados
        self.lbl_res_header = ctk.CTkLabel(
            scroll_result,
            text="PROCESAMIENTO COMPLETADO",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#2E7D32",
            anchor="w",
        )
        self.lbl_res_header.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        self.lbl_res_periodo = ctk.CTkLabel(
            scroll_result,
            text="Período: —  |  Lote: —",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_res_periodo.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

        # Tarjetas Ejecutivas (4 columnas)
        metrics_frame = ctk.CTkFrame(scroll_result, fg_color="transparent")
        metrics_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        for i in range(4):
            metrics_frame.grid_columnconfigure(i, weight=1)

        # Card 1: Documentos
        c_doc = ctk.CTkFrame(metrics_frame, fg_color=("gray92", "gray17"), corner_radius=6)
        c_doc.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(c_doc, text="Documentos", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="gray").pack(pady=(8, 0))
        self.val_docs = ctk.CTkLabel(c_doc, text="0", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"))
        self.val_docs.pack(pady=(0, 2))
        self.lbl_docs_sub = ctk.CTkLabel(c_doc, text="Aceptados: 0 | Rechazados: 0", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="gray")
        self.lbl_docs_sub.pack(pady=(0, 8))

        # Card 2: Actividades Creadas
        c_act = ctk.CTkFrame(metrics_frame, fg_color=("gray92", "gray17"), corner_radius=6)
        c_act.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(c_act, text="Actividades en SQLite", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="gray").pack(pady=(8, 0))
        self.val_actividades = ctk.CTkLabel(c_act, text="0", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"))
        self.val_actividades.pack(pady=(0, 2))
        self.lbl_act_sub = ctk.CTkLabel(c_act, text="Persistidas como SSOT", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="gray")
        self.lbl_act_sub.pack(pady=(0, 8))

        # Card 3: Evidencias Registradas
        c_evid = ctk.CTkFrame(metrics_frame, fg_color=("gray92", "gray17"), corner_radius=6)
        c_evid.grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(c_evid, text="Evidencias Custodiadas", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="gray").pack(pady=(8, 0))
        self.val_evidencias = ctk.CTkLabel(c_evid, text="0", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"))
        self.val_evidencias.pack(pady=(0, 2))
        self.lbl_evid_sub = ctk.CTkLabel(c_evid, text="Fotos y listas vinculadas", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="gray")
        self.lbl_evid_sub.pack(pady=(0, 8))

        # Card 4: Matrices M1–M5
        c_mat = ctk.CTkFrame(metrics_frame, fg_color=("gray92", "gray17"), corner_radius=6)
        c_mat.grid(row=0, column=3, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(c_mat, text="Matrices M1–M5", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="gray").pack(pady=(8, 0))
        self.val_matrices = ctk.CTkLabel(c_mat, text="0", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"))
        self.val_matrices.pack(pady=(0, 2))
        self.lbl_mat_sub = ctk.CTkLabel(c_mat, text="M1 generada con éxito", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="gray")
        self.lbl_mat_sub.pack(pady=(0, 8))

        # Aviso Institucional Obligatorio sobre M2–M5 Vacías
        aviso_m2_m5 = ctk.CTkFrame(scroll_result, fg_color=("gray88", "gray18"), corner_radius=6)
        aviso_m2_m5.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        aviso_m2_m5.grid_columnconfigure(0, weight=1)

        lbl_aviso_m2_m5 = ctk.CTkLabel(
            aviso_m2_m5,
            text=(
                "INFORMACIÓN INSTITUCIONAL SOBRE MATRICES NOMINALES (M2–M5):\n"
                "Los documentos procesados contienen información agregada y evidencia de asistencia, pero no datos nominales "
                "estructurados suficientes para generar nuevos registros individuales en M2–M5. Las actividades fueron "
                "registradas fielmente y consolidadas en la Matriz M1 General."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            justify="left",
            anchor="w",
            text_color=("gray30", "gray80"),
        )
        lbl_aviso_m2_m5.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        # Tabla de Detalle por Archivo
        tbl_container = ctk.CTkFrame(scroll_result, fg_color=("gray92", "gray17"), corner_radius=6)
        tbl_container.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))
        tbl_container.grid_columnconfigure(0, weight=1)

        lbl_tbl_title = ctk.CTkLabel(
            tbl_container,
            text="DETALLE DE ARCHIVOS PROCESADOS",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor="w",
        )
        lbl_tbl_title.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        self.table_scroll = ctk.CTkScrollableFrame(tbl_container, height=160, fg_color="transparent")
        self.table_scroll.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.table_scroll.grid_columnconfigure(0, weight=2)
        self.table_scroll.grid_columnconfigure(1, weight=1)
        self.table_scroll.grid_columnconfigure(2, weight=3)

        # Botonera de Acciones Finales
        btn_bar = ctk.CTkFrame(scroll_result, fg_color="transparent")
        btn_bar.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 15))

        self.btn_abrir_carpeta = ctk.CTkButton(
            btn_bar,
            text="Abrir Carpeta de Resultados",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=36,
            corner_radius=5,
            command=self._on_abrir_carpeta_resultados,
        )
        self.btn_abrir_carpeta.pack(side="left", padx=(0, 8), expand=True, fill="x")

        self.btn_abrir_m1 = ctk.CTkButton(
            btn_bar,
            text="Abrir Matriz M1 General",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=36,
            corner_radius=5,
            command=self._on_abrir_m1,
        )
        self.btn_abrir_m1.pack(side="left", padx=(0, 8), expand=True, fill="x")

        self.btn_ver_manifest = ctk.CTkButton(
            btn_bar,
            text="Ver Manifiesto",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=36,
            corner_radius=5,
            command=self._on_ver_manifest,
        )
        self.btn_ver_manifest.pack(side="left", padx=(0, 8), expand=True, fill="x")

        self.btn_nuevo_lote = ctk.CTkButton(
            btn_bar,
            text="Procesar Otro Lote",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#555555",
            hover_color="#333333",
            height=36,
            corner_radius=5,
            command=self._on_nuevo_lote,
        )
        self.btn_nuevo_lote.pack(side="left", expand=True, fill="x")

        # Sincronización inicial
        self._sincronizar_preflight()

    # -------------------------------------------------------------------------
    # MÉTODOS OPERATIVOS Y CALLBACKS
    # -------------------------------------------------------------------------
    def _on_seleccionar_carpeta_origen(self) -> None:
        """Abre el diálogo para seleccionar la carpeta de documentos Word."""
        carpeta = filedialog.askdirectory(
            title="Seleccionar Carpeta con Documentos Word (.docx)",
            mustexist=True,
        )
        if carpeta:
            self.carpeta_origen = Path(carpeta)
            self.lbl_path_origen.configure(
                text=str(self.carpeta_origen),
                text_color=("black", "white"),
            )
            self._sincronizar_preflight()

    def _on_cambiar_carpeta_salida(self) -> None:
        """Abre el diálogo para modificar la carpeta de salida."""
        carpeta = filedialog.askdirectory(
            title="Seleccionar Carpeta de Destino para Matrices M1–M5",
            mustexist=False,
        )
        if carpeta:
            self.carpeta_salida = Path(carpeta)
            self.lbl_path_salida.configure(text=str(self.carpeta_salida))
            self.lbl_pf_salida.configure(text=f"• Destino: {self.carpeta_salida}")

    def _on_periodo_cambiado(self, periodo: Optional[PeriodoConsolidacion]) -> None:
        """Notificación de cambio en la configuración del período."""
        self.periodo_actual = periodo
        if hasattr(self, "lbl_pf_origen"):
            self._sincronizar_preflight()

    def _sincronizar_preflight(self) -> WordBatchPreflightStatus:
        """Evalúa el estado pre-vuelo y actualiza los indicadores visuales."""
        if not hasattr(self, "lbl_pf_origen"):
            return WordBatchPreflightStatus()

        if not self.carpeta_origen:
            status = WordBatchPreflightStatus(
                listo_para_procesar=False,
                carpeta_origen_valida=False,
                errores_bloqueantes=["Seleccione una carpeta de origen con documentos Word."],
            )
        else:
            status = WordBatchAppService.analizar_carpeta_origen(self.carpeta_origen)

        self.preflight_status = status

        # Actualizar etiquetas en pestaña 1
        if status.carpeta_origen_valida:
            self.lbl_resumen_descubrimiento.configure(
                text=(
                    f"Documentos encontrados: {status.total_archivos_encontrados}  |  "
                    f"Temporales excluidos (~$*): {status.total_temporales_excluidos}  |  "
                    f"Listos: {status.total_candidatos}"
                ),
                text_color=("black", "white"),
            )
        else:
            self.lbl_resumen_descubrimiento.configure(
                text="Documentos encontrados: 0  |  Temporales excluidos (~$*): 0  |  Listos: 0",
                text_color="gray",
            )

        # Actualizar tarjeta en pestaña 2
        orig_txt = str(self.carpeta_origen) if self.carpeta_origen else "Pendiente de selección"
        self.lbl_pf_origen.configure(text=f"• Carpeta Origen: {orig_txt}")
        self.lbl_pf_candidatos.configure(text=f"• Documentos listos para procesar: {status.total_candidatos}")

        periodo_txt = self.periodo_actual.etiqueta if self.periodo_actual else "Período por defecto (Año actual)"
        self.lbl_pf_periodo.configure(text=f"• Período institucional: {periodo_txt}")

        if status.listo_para_procesar:
            self.lbl_pf_estado.configure(
                text="Estado: Validación previa completada. Listo para procesar.",
                text_color="#2E7D32",
            )
            self.btn_procesar.configure(state="normal")
        else:
            err_msg = status.errores_bloqueantes[0] if status.errores_bloqueantes else "Requisitos incompletos."
            self.lbl_pf_estado.configure(
                text=f"Estado: NO SE PUEDE PROCESAR — {err_msg}",
                text_color="#C62828",
            )
            self.btn_procesar.configure(state="disabled")

        return status

    def _on_click_continuar_a_validacion(self) -> None:
        """Avanza a la pestaña de validación si la carpeta es válida."""
        status = self._sincronizar_preflight()
        if not status.carpeta_origen_valida:
            messagebox.showwarning(
                "Carpeta Requerida",
                "Debe seleccionar una carpeta válida con documentos Word antes de continuar.",
            )
            return
        self.tabview.set("2. Validación y Ejecución")

    def _on_iniciar_procesamiento(self) -> None:
        """Lanza el worker asíncrono en segundo plano."""
        status = self._sincronizar_preflight()
        if not status.listo_para_procesar or not self.carpeta_origen:
            messagebox.showwarning(
                "Validación Incompleta",
                "Verifique que la carpeta de origen contenga documentos válidos antes de procesar.",
            )
            return

        # Bloquear controles concurrentes
        self.btn_procesar.configure(state="disabled")
        self.progress_view.reiniciar()

        # Limpiar cola anterior
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except Exception:
                break

        dry_run = bool(self.chk_dry_run.get())

        self.worker = WordBatchWorker(
            carpeta_origen=self.carpeta_origen,
            carpeta_salida=self.carpeta_salida,
            event_queue=self.event_queue,
            dry_run=dry_run,
        )
        self.worker.start()

        # Iniciar polling no bloqueante en el hilo principal
        self._programar_polling_cola()

    def _programar_polling_cola(self) -> None:
        """Revisa periódicamente la cola de eventos en el hilo de UI."""
        self._procesar_eventos_pendientes()
        if self.worker and self.worker.is_alive():
            self._polling_id = self.after(50, self._programar_polling_cola)
        else:
            self._procesar_eventos_pendientes()

    def _procesar_eventos_pendientes(self) -> None:
        """Consume los eventos de la cola y actualiza la UI."""
        while not self.event_queue.empty():
            try:
                evento: WordBatchEvent = self.event_queue.get_nowait()
            except Exception:
                break

            tipo = evento.event_type

            if tipo == WordBatchEventType.STAGE_STARTED:
                if evento.step_index and evento.step_name:
                    self.progress_view.etapa_iniciada(evento.step_index, evento.step_name)

            elif tipo == WordBatchEventType.STAGE_COMPLETED:
                if evento.step_index and evento.step_name:
                    self.progress_view.etapa_completada(evento.step_index, evento.step_name)

            elif tipo == WordBatchEventType.FILE_STARTED:
                if evento.file_name:
                    self.progress_view.subtitle_lbl.configure(
                        text=f"Procesando: {evento.file_name}...",
                        text_color=("#0B3C5D", "#4FC3F7"),
                    )

            elif tipo == WordBatchEventType.WARNING:
                if evento.message:
                    self.progress_view.agregar_advertencia(evento.message)

            elif tipo == WordBatchEventType.BATCH_FAILED:
                self.btn_procesar.configure(state="normal")
                info = evento.error_info
                if info:
                    messagebox.showerror(info.titulo, info.mensaje_completo())
                else:
                    messagebox.showerror(
                        "Error en Procesamiento",
                        evento.message or "Ocurrió un error inesperado al procesar el lote.",
                    )

            elif tipo == WordBatchEventType.BATCH_COMPLETED:
                self.btn_procesar.configure(state="normal")
                self.progress_view.finalizar_exitoso(
                    mensaje="✓ Procesamiento por lote completado. Matrices oficiales generadas."
                )
                if evento.result:
                    self.resultado_batch = evento.result
                    self._mostrar_resultado(evento.result)
                    self.tabview.set("3. Resultados y Auditoría")

    def _mostrar_resultado(self, res: BatchResultadoDTO) -> None:
        """Carga y visualiza los resultados del lote en la pestaña 3."""
        periodo_str = self.periodo_actual.etiqueta if self.periodo_actual else "Año actual"
        self.lbl_res_periodo.configure(
            text=f"Período: {periodo_str}  |  Lote ID: {res.batch_id[:8]}..."
        )

        total_con_obs = res.archivos_con_advertencias
        total_rechazados = res.archivos_rechazados
        total_duplicados = len(res.actividades_con_posible_duplicado)

        if res.archivos_fallidos > 0:
            self.lbl_res_header.configure(text="PROCESAMIENTO COMPLETADO CON ERRORES", text_color="#C62828")
        elif total_con_obs > 0 or total_rechazados > 0:
            self.lbl_res_header.configure(text="PROCESAMIENTO COMPLETADO CON OBSERVACIONES", text_color="#ED6C02")
        else:
            self.lbl_res_header.configure(text="PROCESAMIENTO COMPLETADO EXITOSAMENTE", text_color="#2E7D32")

        # Tarjetas
        self.val_docs.configure(text=str(res.archivos_encontrados))
        self.lbl_docs_sub.configure(
            text=f"Aceptados: {res.archivos_aceptados} | Rechazados: {res.archivos_rechazados} | Duplicados: {total_duplicados}"
        )

        self.val_actividades.configure(text=str(len(res.actividades_creadas)))
        self.val_evidencias.configure(text=str(res.evidencias_registradas_total))

        m1_generada = "matriz_1" in res.matrices_generadas or any("M1" in str(v) for v in res.matrices_generadas.values())
        if m1_generada:
            self.val_matrices.configure(text=f"{len(res.matrices_generadas)} de 5", text_color="#2E7D32")
            self.lbl_mat_sub.configure(text="M1 generada con éxito")
        else:
            self.val_matrices.configure(text="0 de 5", text_color="gray")
            self.lbl_mat_sub.configure(text="Sin exportar (Dry-Run)")

        # Cargar tabla de archivos procesados
        for w in self.table_scroll.winfo_children():
            w.destroy()

        # Cabecera de la tabla
        h_f = ctk.CTkLabel(self.table_scroll, text="Archivo", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w")
        h_f.grid(row=0, column=0, padx=6, pady=2, sticky="w")
        h_e = ctk.CTkLabel(self.table_scroll, text="Estado", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w")
        h_e.grid(row=0, column=1, padx=6, pady=2, sticky="w")
        h_d = ctk.CTkLabel(self.table_scroll, text="Detalle / Observación", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w")
        h_d.grid(row=0, column=2, padx=6, pady=2, sticky="w")

        for idx, f_dto in enumerate(res.resultados_por_archivo, start=1):
            lbl_nom = ctk.CTkLabel(
                self.table_scroll,
                text=f_dto.nombre_archivo,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                anchor="w",
            )
            lbl_nom.grid(row=idx, column=0, padx=6, pady=2, sticky="w")

            estado_txt = f_dto.estado
            estado_col = "#2E7D32" if estado_txt == "ACEPTADO" else "#ED6C02" if estado_txt in ("CON_ADVERTENCIAS", "RECHAZADO") else "#C62828"

            if f_dto.posible_duplicado_advertido:
                estado_txt = "OMITIDO — DUPLICADO"
                estado_col = "#757575"

            lbl_est = ctk.CTkLabel(
                self.table_scroll,
                text=estado_txt,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=estado_col,
                anchor="w",
            )
            lbl_est.grid(row=idx, column=1, padx=6, pady=2, sticky="w")

            # Detalle
            if f_dto.motivo_rechazo:
                det = f"Rechazado: {f_dto.motivo_rechazo}"
            elif f_dto.posible_duplicado_advertido:
                det = "Documento ya registrado previamente en la base de datos (GAP-3)."
            elif f_dto.advertencias:
                det = f_dto.advertencias[0]
            elif f_dto.id_actividad:
                det = f"Actividad registrada ({f_dto.id_actividad[:8]}...) — Incorporada en M1"
            else:
                det = "Procesado correctamente."

            lbl_det = ctk.CTkLabel(
                self.table_scroll,
                text=det,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                anchor="w",
                wraplength=450,
                justify="left",
            )
            lbl_det.grid(row=idx, column=2, padx=6, pady=2, sticky="w")

    def _on_abrir_carpeta_resultados(self) -> None:
        """Abre la carpeta de salida en el explorador de archivos."""
        target = self.carpeta_salida
        if self.resultado_batch and self.resultado_batch.carpeta_batch_salida:
            p = Path(self.resultado_batch.carpeta_batch_salida)
            if p.exists():
                target = p
        _abrir_carpeta_so(target)

    def _on_abrir_m1(self) -> None:
        """Abre el archivo Excel de la Matriz M1 General."""
        if not self.resultado_batch:
            return
        m1_path = self.resultado_batch.matrices_generadas.get("matriz_1")
        if not m1_path:
            # Buscar cualquier archivo que contenga M1
            for path_str in self.resultado_batch.matrices_generadas.values():
                if "M1" in Path(path_str).name:
                    m1_path = path_str
                    break

        if m1_path and Path(m1_path).exists():
            _abrir_archivo_so(m1_path)
        else:
            messagebox.showinfo("Archivo no disponible", "La Matriz M1 no se encuentra disponible en disco.")

    def _on_ver_manifest(self) -> None:
        """Abre el manifiesto JSON en el visor predeterminado."""
        if self.resultado_batch and self.resultado_batch.manifest_path:
            p = Path(self.resultado_batch.manifest_path)
            if p.exists():
                _abrir_archivo_so(p)
                return
        messagebox.showinfo("Manifiesto no disponible", "El manifiesto JSON no se encuentra disponible.")

    def _on_nuevo_lote(self) -> None:
        """Restablece los controles para procesar otro lote."""
        self.progress_view.reiniciar()
        self.tabview.set("1. Carpeta y Parámetros")
        self._sincronizar_preflight()
