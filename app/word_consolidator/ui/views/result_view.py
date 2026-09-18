"""
app.word_consolidator.ui.views.result_view

Vista de resultados finales y auditoría institucional de discrepancias (Fase 14.9).
Presenta el resumen ejecutivo, métricas volumétricas, tabla no técnica de discrepancias,
aviso institucional formal y botones de acceso directo al informe Word y auditoría.
"""

import json
import os
from pathlib import Path
import subprocess
from tkinter import messagebox
from typing import Any, Callable, Dict, List, Optional, Union

import customtkinter as ctk

from app.word_consolidator.pipeline import PipelineExecutionResult


def _abrir_archivo_so(ruta: Union[str, Path, None]) -> bool:
    """Abre un archivo con el programa predeterminado del sistema operativo (Windows/Linux/Mac)."""
    if not ruta or not str(ruta).strip():
        return False
    p = Path(ruta)
    if not p.exists():
        return False
    if not p.is_file():
        return False
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(p.resolve()))  # type: ignore
            return True
        else:
            subprocess.Popen(["xdg-open", str(p.resolve())])
            return True
    except Exception:
        try:
            subprocess.Popen(["start", "", str(p.resolve())], shell=True)
            return True
        except Exception:
            return False


def _abrir_carpeta_so(carpeta: Union[str, Path], archivo_seleccionado: Optional[Union[str, Path]] = None) -> bool:
    """Abre el explorador de archivos en la carpeta o seleccionando el archivo especificado."""
    p_dir = Path(carpeta)
    if not p_dir.exists():
        return False
    try:
        if archivo_seleccionado and Path(archivo_seleccionado).exists():
            subprocess.Popen(f'explorer /select,"{Path(archivo_seleccionado).resolve()}"')
            return True
        elif hasattr(os, "startfile"):
            os.startfile(str(p_dir.resolve()))  # type: ignore
            return True
        else:
            subprocess.Popen(["xdg-open", str(p_dir.resolve())])
            return True
    except Exception:
        try:
            subprocess.Popen(["explorer", str(p_dir.resolve())])
            return True
        except Exception:
            return False


class ResultView(ctk.CTkFrame):
    """
    Componente visual que presenta los resultados finales del pipeline y el módulo de discrepancias.
    """

    def __init__(
        self,
        master: Any,
        on_nueva_consolidacion: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ):
        super().__init__(master, **kwargs)
        self.on_nueva_consolidacion = on_nueva_consolidacion
        self.resultado_actual: Optional[PipelineExecutionResult] = None

        self._init_ui()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Encabezado
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        self.title_lbl = ctk.CTkLabel(
            header_frame,
            text="CONSOLIDACIÓN COMPLETADA",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#4CAF50",
            anchor="w",
        )
        self.title_lbl.pack(anchor="w")

        self.periodo_lbl = ctk.CTkLabel(
            header_frame,
            text="Período: —",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        self.periodo_lbl.pack(anchor="w", pady=(2, 0))

        # Tarjetas de Métricas Ejecutivas (4 columnas)
        metrics_frame = ctk.CTkFrame(self)
        metrics_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=8)
        for i in range(4):
            metrics_frame.grid_columnconfigure(i, weight=1)

        # 1. Actividades
        card_act = ctk.CTkFrame(metrics_frame, fg_color=("gray90", "gray18"))
        card_act.grid(row=0, column=0, padx=4, pady=6, sticky="ew")
        ctk.CTkLabel(card_act, text="Actividades", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(6, 0))
        self.val_actividades = ctk.CTkLabel(card_act, text="0", font=ctk.CTkFont(size=18, weight="bold"))
        self.val_actividades.pack(pady=(0, 6))

        # 2. Participaciones Brutas
        card_part = ctk.CTkFrame(metrics_frame, fg_color=("gray90", "gray18"))
        card_part.grid(row=0, column=1, padx=4, pady=6, sticky="ew")
        ctk.CTkLabel(card_part, text="Participaciones", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(6, 0))
        self.val_participaciones = ctk.CTkLabel(card_part, text="0", font=ctk.CTkFont(size=18, weight="bold"))
        self.val_participaciones.pack(pady=(0, 6))

        # 3. Personas Únicas
        card_pers = ctk.CTkFrame(metrics_frame, fg_color=("gray90", "gray18"))
        card_pers.grid(row=0, column=2, padx=4, pady=6, sticky="ew")
        ctk.CTkLabel(card_pers, text="Personas Únicas", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(6, 0))
        self.val_personas = ctk.CTkLabel(card_pers, text="0", font=ctk.CTkFont(size=18, weight="bold"))
        self.val_personas.pack(pady=(0, 6))

        # 4. Discrepancias Activas
        card_disc = ctk.CTkFrame(metrics_frame, fg_color=("gray90", "gray18"))
        card_disc.grid(row=0, column=3, padx=4, pady=6, sticky="ew")
        ctk.CTkLabel(card_disc, text="Discrepancias", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(6, 0))
        self.val_discrepancias = ctk.CTkLabel(card_disc, text="0", font=ctk.CTkFont(size=18, weight="bold"))
        self.val_discrepancias.pack(pady=(0, 6))

        # Panel de Discrepancias Institucionales
        self.disc_container = ctk.CTkFrame(self)
        self.disc_container.grid(row=2, column=0, sticky="ew", padx=15, pady=6)
        self.disc_container.grid_columnconfigure(0, weight=1)

        self.lbl_disc_header = ctk.CTkLabel(
            self.disc_container,
            text="RESULTADO DE VALIDACIÓN DE FUENTES",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self.lbl_disc_header.grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

        self.lbl_disc_summary = ctk.CTkLabel(
            self.disc_container,
            text="Concordantes: 0  |  Requieren revisión: 0",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        self.lbl_disc_summary.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="w")

        # Tabla / Cuadrícula de discrepancias
        self.table_scroll = ctk.CTkScrollableFrame(self.disc_container, height=130)
        self.table_scroll.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        self.table_scroll.grid_columnconfigure(1, weight=1)

        # Aviso Institucional Obligatorio
        aviso_frame = ctk.CTkFrame(self.disc_container, fg_color=("gray85", "gray15"))
        aviso_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(6, 10))
        aviso_frame.grid_columnconfigure(0, weight=1)

        self.lbl_aviso_institucional = ctk.CTkLabel(
            aviso_frame,
            text=(
                "ℹ️ AVISO INSTITUCIONAL:\n"
                "El sistema registra fielmente las cifras de cada fuente sin alterarlas ni forzar su reconciliación "
                "automática. La aclaración de estas diferencias corresponde a las instancias académicas y administrativas "
                "responsables de la actividad."
            ),
            font=ctk.CTkFont(size=11, slant="italic"),
            justify="left",
            anchor="w",
        )
        self.lbl_aviso_institucional.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        # Archivos generados
        files_frame = ctk.CTkFrame(self, fg_color=("gray92", "gray20"))
        files_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=6)
        files_frame.grid_columnconfigure(0, weight=1)

        lbl_f_title = ctk.CTkLabel(
            files_frame,
            text="Archivos Institucionales Generados:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        lbl_f_title.grid(row=0, column=0, padx=12, pady=(8, 4), sticky="w")

        # Tarjeta Producto A (Informe Técnico)
        card_tec = ctk.CTkFrame(files_frame, fg_color=("gray86", "gray17"), corner_radius=6)
        card_tec.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        card_tec.grid_columnconfigure(0, weight=1)
        card_tec.grid_columnconfigure(1, weight=0)

        f_tec_info = ctk.CTkFrame(card_tec, fg_color="transparent")
        f_tec_info.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        lbl_tec_title = ctk.CTkLabel(
            f_tec_info,
            text="📄 INFORME TÉCNICO DE AUDITORÍA",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        lbl_tec_title.pack(anchor="w")

        self.lbl_status_tecnico = ctk.CTkLabel(
            f_tec_info,
            text="Pendiente",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        )
        self.lbl_status_tecnico.pack(anchor="w", pady=(2, 0))

        self.lbl_detalles_tecnico = ctk.CTkLabel(
            f_tec_info,
            text="• Esperando procesamiento",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.lbl_detalles_tecnico.pack(anchor="w", pady=(2, 0))
        self.lbl_f_docx = self.lbl_detalles_tecnico

        self.btn_abrir_tecnico = ctk.CTkButton(
            card_tec,
            text="📄 ABRIR INFORME TÉCNICO",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=34,
            width=220,
            command=self._on_abrir_tecnico,
            state="disabled",
        )
        self.btn_abrir_tecnico.grid(row=0, column=1, padx=12, pady=8, sticky="e")

        # Tarjeta Producto B (Informe Institucional)
        card_inst = ctk.CTkFrame(files_frame, fg_color=("gray86", "gray17"), corner_radius=6)
        card_inst.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        card_inst.grid_columnconfigure(0, weight=1)
        card_inst.grid_columnconfigure(1, weight=0)

        f_inst_info = ctk.CTkFrame(card_inst, fg_color="transparent")
        f_inst_info.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        lbl_inst_title = ctk.CTkLabel(
            f_inst_info,
            text="🏛️ INFORME INSTITUCIONAL EJECUTIVO",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        lbl_inst_title.pack(anchor="w")

        self.lbl_status_institucional = ctk.CTkLabel(
            f_inst_info,
            text="Pendiente",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        )
        self.lbl_status_institucional.pack(anchor="w", pady=(2, 0))

        self.lbl_detalles_institucional = ctk.CTkLabel(
            f_inst_info,
            text="• Esperando procesamiento",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.lbl_detalles_institucional.pack(anchor="w", pady=(2, 0))
        self.lbl_f_docx_inst = self.lbl_detalles_institucional

        self.btn_abrir_institucional = ctk.CTkButton(
            card_inst,
            text="🏛️ ABRIR INFORME INSTITUCIONAL",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=34,
            width=220,
            command=self._on_abrir_institucional,
            state="disabled",
        )
        self.btn_abrir_institucional.grid(row=0, column=1, padx=12, pady=8, sticky="e")

        # Auditoría E2E
        self.lbl_f_audit = ctk.CTkLabel(
            files_frame,
            text="• Auditoría E2E (.json / .md): Pendiente",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.lbl_f_audit.grid(row=3, column=0, padx=14, pady=(4, 8), sticky="w")

        # Botonera de Acciones Finales
        btn_action_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_action_bar.grid(row=4, column=0, sticky="ew", padx=15, pady=(8, 14))

        self.btn_abrir_carpeta = ctk.CTkButton(
            btn_action_bar,
            text="📁 ABRIR CARPETA DE RESULTADOS",
            font=ctk.CTkFont(size=12),
            height=38,
            command=self._on_abrir_carpeta,
        )
        self.btn_abrir_carpeta.pack(side="left", padx=(0, 8), expand=True, fill="x")

        self.btn_ver_auditoria = ctk.CTkButton(
            btn_action_bar,
            text="📋 VER AUDITORÍA E2E",
            font=ctk.CTkFont(size=12),
            height=38,
            command=self._on_ver_auditoria,
        )
        self.btn_ver_auditoria.pack(side="left", padx=(0, 8), expand=True, fill="x")

        self.btn_nueva_cons = ctk.CTkButton(
            btn_action_bar,
            text="🔄 NUEVA CONSOLIDACIÓN",
            font=ctk.CTkFont(size=12),
            fg_color="#555555",
            hover_color="#333333",
            height=38,
            command=self._on_nueva_consolidacion,
        )
        self.btn_nueva_cons.pack(side="left", expand=True, fill="x")

    def mostrar_resultado(self, res: PipelineExecutionResult) -> None:
        """Carga y visualiza los datos del resultado de ejecución."""
        self.resultado_actual = res

        self.periodo_lbl.configure(text=f"Período Institucional: {res.periodo}")
        self.val_actividades.configure(text=str(res.total_actividades))
        self.val_participaciones.configure(text=str(res.total_participaciones))
        self.val_personas.configure(text=str(res.total_personas_unicas))
        self.val_discrepancias.configure(
            text=str(res.total_discrepancias),
            text_color="#FFA726" if res.total_discrepancias > 0 else "#4CAF50",
        )

        # ---------------------------------------------------------------------
        # Producto A: Informe Técnico
        # ---------------------------------------------------------------------
        status_a = res.status_tecnico
        if status_a == "SUCCESS":
            if res.ruta_docx and Path(res.ruta_docx).is_file():
                p_a = Path(res.ruta_docx)
                tamanio = res.tamanio_docx_bytes or (p_a.stat().st_size if p_a.exists() else 0)
                self.lbl_status_tecnico.configure(text="✓ GENERADO", text_color="#4CAF50")
                self.lbl_detalles_tecnico.configure(
                    text=f"Archivo: {p_a.name} ({tamanio:,} bytes)",
                    text_color=("black", "white"),
                )
                self.btn_abrir_tecnico.configure(state="normal")
            else:
                self.lbl_status_tecnico.configure(text="✗ ERROR EN GENERACIÓN", text_color="#E57373")
                self.lbl_detalles_tecnico.configure(
                    text="Archivo no disponible en disco.",
                    text_color="#E57373",
                )
                self.btn_abrir_tecnico.configure(state="disabled")
        elif status_a == "FAILED":
            self.lbl_status_tecnico.configure(text="✗ ERROR EN GENERACIÓN", text_color="#E57373")
            msg_err = res.error_tecnico or "Error durante la generación del informe técnico."
            self.lbl_detalles_tecnico.configure(
                text=f"Detalle: {msg_err}",
                text_color="#E57373",
            )
            self.btn_abrir_tecnico.configure(state="disabled")
        else:  # NOT_REQUESTED
            self.lbl_status_tecnico.configure(text="⚠ NO SOLICITADO", text_color=("gray50", "gray60"))
            self.lbl_detalles_tecnico.configure(
                text="No se solicitó la generación de este documento.",
                text_color=("gray50", "gray60"),
            )
            self.btn_abrir_tecnico.configure(state="disabled")

        # ---------------------------------------------------------------------
        # Producto B: Informe Institucional
        # ---------------------------------------------------------------------
        status_b = res.status_institucional
        if status_b == "SUCCESS":
            if res.ruta_docx_institucional and Path(res.ruta_docx_institucional).is_file():
                p_b = Path(res.ruta_docx_institucional)
                tamanio = res.tamanio_docx_institucional_bytes or (p_b.stat().st_size if p_b.exists() else 0)
                self.lbl_status_institucional.configure(text="✓ GENERADO", text_color="#4CAF50")
                self.lbl_detalles_institucional.configure(
                    text=f"Archivo: {p_b.name} ({tamanio:,} bytes)",
                    text_color=("black", "white"),
                )
                self.btn_abrir_institucional.configure(state="normal")
            else:
                self.lbl_status_institucional.configure(text="✗ ERROR EN GENERACIÓN", text_color="#E57373")
                self.lbl_detalles_institucional.configure(
                    text="Archivo no disponible en disco.",
                    text_color="#E57373",
                )
                self.btn_abrir_institucional.configure(state="disabled")
        elif status_b == "FAILED":
            self.lbl_status_institucional.configure(text="✗ ERROR EN GENERACIÓN", text_color="#E57373")
            msg_err = res.error_institucional or "Error durante la generación del informe institucional."
            self.lbl_detalles_institucional.configure(
                text=f"Detalle: {msg_err}",
                text_color="#E57373",
            )
            self.btn_abrir_institucional.configure(state="disabled")
        else:  # NOT_REQUESTED
            self.lbl_status_institucional.configure(text="⚠ NO SOLICITADO", text_color=("gray50", "gray60"))
            self.lbl_detalles_institucional.configure(
                text="No se solicitó la generación de este documento.",
                text_color=("gray50", "gray60"),
            )
            self.btn_abrir_institucional.configure(state="disabled")

        audit_md = Path(res.ruta_reporte_md).name if res.ruta_reporte_md else "No generado"
        audit_json = Path(res.ruta_reporte_json).name if res.ruta_reporte_json else "No generado"
        self.lbl_f_audit.configure(
            text=f"• Auditoría E2E: {audit_md} y {audit_json}"
        )

        # Cargar discrepancias desde el archivo JSON de auditoría si está disponible
        discrepancias: List[Dict[str, Any]] = []
        if res.ruta_reporte_json and Path(res.ruta_reporte_json).exists():
            try:
                with open(res.ruta_reporte_json, "r", encoding="utf-8") as fj:
                    data = json.load(fj)
                    discrepancias = data.get("discrepancias", [])
            except Exception:
                discrepancias = []

        # Limpiar tabla de discrepancias
        for w in self.table_scroll.winfo_children():
            w.destroy()

        concordantes = sum(1 for d in discrepancias if d.get("estado") == "CONCORDANTE")
        activas = sum(1 for d in discrepancias if d.get("estado") != "CONCORDANTE")

        self.lbl_disc_summary.configure(
            text=f"Concordantes: {concordantes}  |  Requieren revisión: {activas}"
        )

        if not discrepancias:
            lbl_vacio = ctk.CTkLabel(
                self.table_scroll,
                text="✓ No se registraron discrepancias entre las fuentes. Concordancia institucional plena.",
                font=ctk.CTkFont(size=12),
                text_color="#4CAF50",
            )
            lbl_vacio.pack(pady=10)
        else:
            # Encabezado de tabla
            header_row = ctk.CTkFrame(self.table_scroll, fg_color=("gray85", "gray25"))
            header_row.pack(fill="x", pady=(0, 4))
            header_row.grid_columnconfigure(0, weight=2)
            header_row.grid_columnconfigure(1, weight=1)
            header_row.grid_columnconfigure(2, weight=1)
            header_row.grid_columnconfigure(3, weight=1)
            header_row.grid_columnconfigure(4, weight=1)

            ctk.CTkLabel(header_row, text="Dimensión / Estamento", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, padx=6, pady=4, sticky="w")
            ctk.CTkLabel(header_row, text="Fuente Declarada", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, padx=4, pady=4)
            ctk.CTkLabel(header_row, text="Suma Nominal", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=2, padx=4, pady=4)
            ctk.CTkLabel(header_row, text="Diferencia", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=3, padx=4, pady=4)
            ctk.CTkLabel(header_row, text="Estado", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=4, padx=6, pady=4)

            for d in discrepancias:
                row_f = ctk.CTkFrame(self.table_scroll, fg_color=("gray92", "gray20"))
                row_f.pack(fill="x", pady=2)
                row_f.grid_columnconfigure(0, weight=2)
                row_f.grid_columnconfigure(1, weight=1)
                row_f.grid_columnconfigure(2, weight=1)
                row_f.grid_columnconfigure(3, weight=1)
                row_f.grid_columnconfigure(4, weight=1)

                estamento = d.get("estamento", "General")
                val_a = d.get("valor_fuente_a", 0)
                val_b = d.get("valor_fuente_b", 0)
                delta = d.get("delta", 0)
                delta_str = f"+{delta}" if delta > 0 else str(delta)
                estado = d.get("estado", "CONCORDANTE")
                color_estado = "#4CAF50" if estado == "CONCORDANTE" else "#FFA726"

                ctk.CTkLabel(row_f, text=estamento, font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=6, pady=3, sticky="w")
                ctk.CTkLabel(row_f, text=str(val_a), font=ctk.CTkFont(size=11)).grid(row=0, column=1, padx=4, pady=3)
                ctk.CTkLabel(row_f, text=str(val_b), font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=4, pady=3)
                ctk.CTkLabel(row_f, text=delta_str, font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=3, padx=4, pady=3)
                ctk.CTkLabel(row_f, text=estado, font=ctk.CTkFont(size=11, weight="bold"), text_color=color_estado).grid(row=0, column=4, padx=6, pady=3)

    def _on_abrir_tecnico(self) -> None:
        """Abre exclusivamente el Informe Técnico (Producto A)."""
        if not self.resultado_actual:
            return
        ruta = self.resultado_actual.ruta_docx
        if not ruta or not str(ruta).strip():
            messagebox.showwarning(
                "Archivo No Disponible",
                "El informe solicitado no se encuentra disponible en disco.",
            )
            return

        p = Path(ruta)
        if not p.exists() or not p.is_file():
            messagebox.showwarning(
                "Archivo No Disponible",
                "El informe solicitado no se encuentra disponible en disco.",
            )
            return

        ok = _abrir_archivo_so(p)
        if not ok:
            messagebox.showerror(
                "Error al Abrir Documento",
                "No fue posible abrir el informe con la aplicación predeterminada.",
            )

    def _on_abrir_institucional(self) -> None:
        """Abre exclusivamente el Informe Institucional (Producto B)."""
        if not self.resultado_actual:
            return
        ruta = self.resultado_actual.ruta_docx_institucional
        if not ruta or not str(ruta).strip():
            messagebox.showwarning(
                "Archivo No Disponible",
                "El informe solicitado no se encuentra disponible en disco.",
            )
            return

        p = Path(ruta)
        if not p.exists() or not p.is_file():
            messagebox.showwarning(
                "Archivo No Disponible",
                "El informe solicitado no se encuentra disponible en disco.",
            )
            return

        ok = _abrir_archivo_so(p)
        if not ok:
            messagebox.showerror(
                "Error al Abrir Documento",
                "No fue posible abrir el informe con la aplicación predeterminada.",
            )

    def _on_abrir_docx(self) -> None:
        """Compatibilidad: delega apertura a los métodos específicos según el estado."""
        if self.resultado_actual:
            if self.resultado_actual.status_tecnico == "SUCCESS":
                self._on_abrir_tecnico()
            if self.resultado_actual.status_institucional == "SUCCESS":
                self._on_abrir_institucional()

    def _on_abrir_carpeta(self) -> None:
        """Abre la carpeta de resultados en el explorador de archivos."""
        if self.resultado_actual:
            ruta = (
                self.resultado_actual.ruta_docx
                or self.resultado_actual.ruta_docx_institucional
                or self.resultado_actual.ruta_reporte_md
                or self.resultado_actual.ruta_reporte_json
            )
            if ruta:
                p = Path(ruta)
                _abrir_carpeta_so(p.parent, archivo_seleccionado=p if p.exists() else None)

    def _on_ver_auditoria(self) -> None:
        """Abre el reporte de auditoría (.md o .json)."""
        if self.resultado_actual:
            if self.resultado_actual.ruta_reporte_md and Path(self.resultado_actual.ruta_reporte_md).exists():
                _abrir_archivo_so(self.resultado_actual.ruta_reporte_md)
            elif self.resultado_actual.ruta_reporte_json and Path(self.resultado_actual.ruta_reporte_json).exists():
                _abrir_archivo_so(self.resultado_actual.ruta_reporte_json)

    def _on_nueva_consolidacion(self) -> None:
        """Notifica al controlador principal para reiniciar el ciclo."""
        if self.on_nueva_consolidacion:
            self.on_nueva_consolidacion()
