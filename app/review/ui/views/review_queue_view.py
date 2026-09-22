"""app.review.ui.views.review_queue_view

Vista institucional de Gestión y Resolución de la Cola de Revisión (COLA_REVISION).
Fase 29.22.1 — Implementación Controlada de Cola de Revisión.

PRINCIPIOS ARQUITECTÓNICOS INNEGOCIABLES:
- DETECTAR ≠ CORREGIR: Toda resolución requiere acción humana explícita.
- EVIDENCIA ≠ SUPOSICIÓN: Prohibido fabricar datos o autocompletar cédulas sin evidencia.
- Cero acceso a SQLite: Prohibido importar sqlite3 o ejecutar sentencias SQL.
- Interacción exclusiva a través de ReviewQueueApplicationService y DTOs inmutables.
- Lenguaje visual institucional uniforme con el resto del sistema BICU.
"""

from tkinter import messagebox
from typing import Any, Callable, List, Optional

import customtkinter as ctk

from app.review.application.dto import (
    ReviewCaseDetailDTO,
    ReviewCaseSummaryDTO,
    ReviewHistoryItemDTO,
)
from app.review.application.service import ReviewQueueApplicationService
from app.review.domain.enums import EstamentoInstitucional


class ReviewQueueView(ctk.CTkFrame):
    """Contenedor maestro institucional para la gestión y resolución de COLA_REVISION."""

    def __init__(
        self,
        master: Any,
        service: ReviewQueueApplicationService,
        on_volver_menu: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.service = service
        self.on_volver_menu = on_volver_menu

        self._casos_actuales: List[ReviewCaseSummaryDTO] = []
        self._caso_seleccionado: Optional[ReviewCaseDetailDTO] = None

        self._init_ui()
        self.recargar_bandeja()

    def _init_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------------------
        # 1. ENCABEZADO INSTITUCIONAL (#0B3C5D / #1A2634)
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
            text="GESTIÓN Y RESOLUCIÓN PERICIAL DE COLA DE REVISIÓN (COLA_REVISION)",
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
        # 2. PESTAÑAS PRINCIPALES (Tabview)
        # ---------------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        self.tab_bandeja = self.tabview.add("1. Bandeja de Casos Pendientes")
        self.tab_detalle = self.tabview.add("2. Detalle y Resolución")
        self.tab_historial = self.tabview.add("3. Historial de Decisiones Auditadas")

        self.tab_bandeja.grid_columnconfigure(0, weight=1)
        self.tab_bandeja.grid_rowconfigure(1, weight=1)

        self.tab_detalle.grid_columnconfigure(0, weight=1)
        self.tab_detalle.grid_rowconfigure(0, weight=1)

        self.tab_historial.grid_columnconfigure(0, weight=1)
        self.tab_historial.grid_rowconfigure(1, weight=1)

        self._build_tab_bandeja()
        self._build_tab_detalle()
        self._build_tab_historial()

    # -------------------------------------------------------------------------
    # PESTAÑA 1: BANDEJA DE CASOS PENDIENTES
    # -------------------------------------------------------------------------
    def _build_tab_bandeja(self) -> None:
        # Barra superior de controles
        top_bar = ctk.CTkFrame(self.tab_bandeja, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 10))
        top_bar.grid_columnconfigure(1, weight=1)

        lbl_total = ctk.CTkLabel(
            top_bar,
            text="Casos que requieren intervención humana:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        )
        lbl_total.grid(row=0, column=0, padx=5, sticky="w")

        self.lbl_contador = ctk.CTkLabel(
            top_bar,
            text="0 pendientes",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=("#D32F2F", "#EF5350"),
        )
        self.lbl_contador.grid(row=0, column=1, padx=5, sticky="w")

        btn_refrescar = ctk.CTkButton(
            top_bar,
            text="Actualizar Bandeja",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=130,
            height=30,
            command=self.recargar_bandeja,
        )
        btn_refrescar.grid(row=0, column=2, padx=5, sticky="e")

        # Contenedor con scroll para la lista de casos
        self.scroll_bandeja = ctk.CTkScrollableFrame(
            self.tab_bandeja, fg_color=("gray95", "gray14"), corner_radius=6
        )
        self.scroll_bandeja.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scroll_bandeja.grid_columnconfigure(0, weight=1)

    # -------------------------------------------------------------------------
    # PESTAÑA 2: DETALLE Y RESOLUCIÓN
    # -------------------------------------------------------------------------
    def _build_tab_detalle(self) -> None:
        self.scroll_detalle = ctk.CTkScrollableFrame(
            self.tab_detalle, fg_color="transparent"
        )
        self.scroll_detalle.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll_detalle.grid_columnconfigure(0, weight=1)

        # Mensaje si no hay caso seleccionado
        self.lbl_sin_seleccion = ctk.CTkLabel(
            self.scroll_detalle,
            text="Seleccione un caso en la Bandeja de Casos Pendientes para inspeccionar evidencia y resolver.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="gray",
        )
        self.lbl_sin_seleccion.pack(pady=40)

        # Contenedor del caso activo (se muestra al seleccionar)
        self.frame_caso_activo = ctk.CTkFrame(self.scroll_detalle, fg_color="transparent")
        self.frame_caso_activo.grid_columnconfigure(0, weight=1)

        # 1. Tarjeta de Evidencia y Contexto
        card_evidencia = ctk.CTkFrame(self.frame_caso_activo, corner_radius=6)
        card_evidencia.pack(fill="x", pady=(0, 12))
        card_evidencia.grid_columnconfigure(1, weight=1)

        lbl_tit_ev = ctk.CTkLabel(
            card_evidencia,
            text="EVIDENCIA Y CONTEXTO REGISTRADO",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        lbl_tit_ev.grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 8), sticky="w")

        self.lbl_det_nombre = ctk.CTkLabel(card_evidencia, text="", font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        self.lbl_det_nombre.grid(row=1, column=0, columnspan=2, padx=16, pady=2, sticky="w")

        self.lbl_det_cedula = ctk.CTkLabel(card_evidencia, text="", font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_det_cedula.grid(row=2, column=0, columnspan=2, padx=16, pady=2, sticky="w")

        self.lbl_det_actividad = ctk.CTkLabel(card_evidencia, text="", font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_det_actividad.grid(row=3, column=0, columnspan=2, padx=16, pady=2, sticky="w")

        self.lbl_det_motivo = ctk.CTkLabel(card_evidencia, text="", font=ctk.CTkFont(size=12), text_color=("#D32F2F", "#EF5350"), anchor="w")
        self.lbl_det_motivo.grid(row=4, column=0, columnspan=2, padx=16, pady=(2, 12), sticky="w")

        # 2. Tarjeta de Resolución Pericial Humana
        card_resolucion = ctk.CTkFrame(self.frame_caso_activo, corner_radius=6)
        card_resolucion.pack(fill="x", pady=(0, 12))
        card_resolucion.grid_columnconfigure(1, weight=1)

        lbl_tit_res = ctk.CTkLabel(
            card_resolucion,
            text="DECISIÓN PERICIAL EXPLÍCITA (RESOLUCIÓN)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("#0B3C5D", "#4FC3F7"),
            anchor="w",
        )
        lbl_tit_res.grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 10), sticky="w")

        # Tipo de acción
        lbl_accion = ctk.CTkLabel(card_resolucion, text="Acción:", font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        lbl_accion.grid(row=1, column=0, padx=16, pady=6, sticky="w")

        self.combo_accion = ctk.CTkComboBox(
            card_resolucion,
            values=[
                "Confirmar Estamento Oficial",
                "Confirmar Identidad (Cédula Oficial)",
                "Declarar NO RESOLUBLE",
            ],
            width=300,
            command=self._on_cambio_accion,
        )
        self.combo_accion.grid(row=1, column=1, padx=16, pady=6, sticky="w")

        # Parámetro Estamento
        self.lbl_param_estamento = ctk.CTkLabel(card_resolucion, text="Estamento Oficial:", font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_param_estamento.grid(row=2, column=0, padx=16, pady=6, sticky="w")

        self.combo_estamento = ctk.CTkComboBox(
            card_resolucion,
            values=[e.value for e in EstamentoInstitucional],
            width=300,
        )
        self.combo_estamento.grid(row=2, column=1, padx=16, pady=6, sticky="w")

        # Parámetro Cédula
        self.lbl_param_cedula = ctk.CTkLabel(card_resolucion, text="Nueva Cédula Oficial:", font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_param_cedula.grid(row=3, column=0, padx=16, pady=6, sticky="w")

        self.entry_cedula = ctk.CTkEntry(card_resolucion, width=300, placeholder_text="XXX-XXXXXX-XXXXL")
        self.entry_cedula.grid(row=3, column=1, padx=16, pady=6, sticky="w")

        # Justificación obligatoria
        lbl_just = ctk.CTkLabel(card_resolucion, text="Justificación Pericial (*):", font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        lbl_just.grid(row=4, column=0, padx=16, pady=6, sticky="w")

        self.entry_justificacion = ctk.CTkEntry(
            card_resolucion, width=450, placeholder_text="Documente el sustento formal de la decisión (obligatorio)"
        )
        self.entry_justificacion.grid(row=4, column=1, padx=16, pady=6, sticky="w")

        # Operador
        lbl_operador = ctk.CTkLabel(card_resolucion, text="Operador Responsable (*):", font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        lbl_operador.grid(row=5, column=0, padx=16, pady=6, sticky="w")

        self.entry_operador = ctk.CTkEntry(card_resolucion, width=300)
        self.entry_operador.insert(0, "operador_bicu")
        self.entry_operador.grid(row=5, column=1, padx=16, pady=6, sticky="w")

        # Botón Resolver
        self.btn_ejecutar_resolucion = ctk.CTkButton(
            card_resolucion,
            text="Confirmar y Asentar Resolución Pericial",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0B3C5D",
            hover_color="#07263D",
            height=34,
            command=self._ejecutar_resolucion,
        )
        self.btn_ejecutar_resolucion.grid(row=6, column=0, columnspan=2, padx=16, pady=(16, 16), sticky="ew")

        self._on_cambio_accion(self.combo_accion.get())

    # -------------------------------------------------------------------------
    # PESTAÑA 3: HISTORIAL DE DECISIONES AUDITADAS
    # -------------------------------------------------------------------------
    def _build_tab_historial(self) -> None:
        top_bar = ctk.CTkFrame(self.tab_historial, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 10))
        top_bar.grid_columnconfigure(0, weight=1)

        lbl_hist = ctk.CTkLabel(
            top_bar,
            text="Trazabilidad forense de resoluciones periciales (auditoria_evento):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        )
        lbl_hist.grid(row=0, column=0, padx=5, sticky="w")

        btn_act_hist = ctk.CTkButton(
            top_bar,
            text="Actualizar Historial",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=130,
            height=30,
            command=self.recargar_historial,
        )
        btn_act_hist.grid(row=0, column=1, padx=5, sticky="e")

        self.scroll_historial = ctk.CTkScrollableFrame(
            self.tab_historial, fg_color=("gray95", "gray14"), corner_radius=6
        )
        self.scroll_historial.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scroll_historial.grid_columnconfigure(0, weight=1)

    # -------------------------------------------------------------------------
    # MÉTODOS DE CONTROL Y RECARGA
    # -------------------------------------------------------------------------
    def recargar_bandeja(self) -> None:
        """Consulta y actualiza la lista de casos pendientes desde el servicio."""
        # Limpiar contenedor visual
        for w in self.scroll_bandeja.winfo_children():
            w.destroy()

        try:
            self._casos_actuales = self.service.listar_casos_pendientes()
        except Exception as e:
            messagebox.showerror("Error al consultar cola", f"No fue posible consultar la cola de revisión:\n{e}")
            self._casos_actuales = []

        total = len(self._casos_actuales)
        self.lbl_contador.configure(text=f"{total} casos pendientes")

        if total == 0:
            lbl_vacio = ctk.CTkLabel(
                self.scroll_bandeja,
                text="No existen casos pendientes en la Cola de Revisión. Todos los registros están clasificados.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color="gray",
            )
            lbl_vacio.pack(pady=40)
            return

        for caso in self._casos_actuales:
            self._render_tarjeta_caso(caso)

    def _render_tarjeta_caso(self, caso: ReviewCaseSummaryDTO) -> None:
        """Renderiza una tarjeta individual de caso en la bandeja."""
        card = ctk.CTkFrame(self.scroll_bandeja, corner_radius=6, border_width=1, border_color=("gray80", "gray25"))
        card.pack(fill="x", padx=6, pady=4)
        card.grid_columnconfigure(1, weight=1)

        # Indicador de estado/tipo
        badge_tipo = ctk.CTkLabel(
            card,
            text=f"[{caso.tipo_caso}]",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=("#D32F2F", "#EF5350"),
            anchor="w",
        )
        badge_tipo.grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

        lbl_nombre = ctk.CTkLabel(
            card,
            text=caso.nombre_persona,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            anchor="w",
        )
        lbl_nombre.grid(row=1, column=0, columnspan=2, padx=12, pady=1, sticky="w")

        cedula_str = f"Cédula: {caso.cedula_persona}" if caso.cedula_persona else "Cédula: [SIN REGISTRO]"
        lbl_act = ctk.CTkLabel(
            card,
            text=f"Actividad: {caso.nombre_actividad}  |  {cedula_str}  |  Estamento reportado: {caso.estamento_actual}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        lbl_act.grid(row=2, column=0, columnspan=2, padx=12, pady=1, sticky="w")

        lbl_motivo = ctk.CTkLabel(
            card,
            text=f"Motivo: {caso.motivo_revision}",
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color=("#C62828", "#FF8A80"),
            anchor="w",
        )
        lbl_motivo.grid(row=3, column=0, padx=12, pady=(1, 8), sticky="w")

        btn_revisar = ctk.CTkButton(
            card,
            text="Revisar Caso ➔",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            width=110,
            height=28,
            command=lambda cid=caso.id_caso: self.seleccionar_caso(cid),
        )
        btn_revisar.grid(row=3, column=1, padx=12, pady=(1, 8), sticky="e")

    def seleccionar_caso(self, id_caso: str) -> None:
        """Carga el detalle del caso y cambia a la pestaña de Detalle y Resolución."""
        try:
            detalle = self.service.obtener_detalle_caso(id_caso)
            if not detalle:
                messagebox.showwarning("Caso no encontrado", f"No fue posible encontrar el caso '{id_caso}'.")
                return
            self._caso_seleccionado = detalle
            self._mostrar_caso_activo()
            self.tabview.set("2. Detalle y Resolución")
        except Exception as e:
            messagebox.showerror("Error al cargar caso", f"Error al recuperar detalle del caso:\n{e}")

    def _mostrar_caso_activo(self) -> None:
        """Actualiza los campos visuales de la pestaña de detalle con el caso seleccionado."""
        if not self._caso_seleccionado:
            return

        self.lbl_sin_seleccion.pack_forget()
        self.frame_caso_activo.pack(fill="x", expand=True)

        d = self._caso_seleccionado
        self.lbl_det_nombre.configure(text=f"Participante: {d.nombre_persona} (ID: {d.id_persona})")
        ced_txt = d.cedula_persona if d.cedula_persona else "[SIN CÉDULA — RN-C04 NULL]"
        self.lbl_det_cedula.configure(text=f"Identificación: {ced_txt}  |  Sexo: {d.sexo_persona or 'N/D'}")
        self.lbl_det_actividad.configure(text=f"Actividad: {d.nombre_actividad}  |  Fecha: {d.fecha_actividad or 'N/D'}")
        self.lbl_det_motivo.configure(text=f"Discrepancia detectada: {d.motivo_revision}  [{d.tipo_caso}]")

        self.entry_justificacion.delete(0, "end")
        self.entry_cedula.delete(0, "end")

    def _on_cambio_accion(self, valor: str) -> None:
        """Muestra u oculta controles según la acción seleccionada."""
        if "Estamento" in valor:
            self.lbl_param_estamento.grid()
            self.combo_estamento.grid()
            self.lbl_param_cedula.grid_remove()
            self.entry_cedula.grid_remove()
        elif "Identidad" in valor:
            self.lbl_param_estamento.grid_remove()
            self.combo_estamento.grid_remove()
            self.lbl_param_cedula.grid()
            self.entry_cedula.grid()
        else:  # NO RESOLUBLE
            self.lbl_param_estamento.grid_remove()
            self.combo_estamento.grid_remove()
            self.lbl_param_cedula.grid_remove()
            self.entry_cedula.grid_remove()

    def _ejecutar_resolucion(self) -> None:
        """Ejecuta la resolución pericial a través del servicio de aplicación."""
        if not self._caso_seleccionado:
            messagebox.showwarning("Sin caso", "No hay ningún caso seleccionado para resolver.")
            return

        accion = self.combo_accion.get()
        justificacion = self.entry_justificacion.get().strip()
        operador = self.entry_operador.get().strip()

        if not justificacion:
            messagebox.showwarning("Justificación requerida", "Debe proporcionar una justificación pericial formal.")
            return

        if not operador:
            messagebox.showwarning("Operador requerido", "Debe registrar el nombre del operador que asienta la decisión.")
            return

        confirma = messagebox.askyesno(
            "Confirmación Pericial",
            f"¿Desea asentar la siguiente resolución de forma definitiva y auditable?\n\n"
            f"Acción: {accion}\n"
            f"Participante: {self._caso_seleccionado.nombre_persona}\n"
            f"Operador: {operador}\n\n"
            "Esta operación es transaccional y registrará un evento DISCREPANCY_RESOLVE inmutable.",
        )
        if not confirma:
            return

        try:
            cid = self._caso_seleccionado.id_caso
            if "Estamento" in accion:
                estamento_sel = self.combo_estamento.get()
                res = self.service.resolver_estamento(
                    id_participacion=cid,
                    nuevo_estamento=estamento_sel,
                    justificacion=justificacion,
                    usuario=operador,
                )
            elif "Identidad" in accion:
                cedula_val = self.entry_cedula.get().strip()
                if not cedula_val:
                    messagebox.showwarning("Cédula requerida", "Debe introducir una cédula oficial para confirmar identidad.")
                    return
                res = self.service.resolver_identidad(
                    id_participacion=cid,
                    nueva_cedula=cedula_val,
                    justificacion=justificacion,
                    usuario=operador,
                )
            else:
                res = self.service.marcar_no_resoluble(
                    id_participacion=cid,
                    motivo=justificacion,
                    usuario=operador,
                )

            if res.exito:
                messagebox.showinfo(
                    "Resolución Asentada",
                    f"{res.mensaje}\n\n"
                    f"Matriz Destino: {res.matriz_destino}\n"
                    f"ID Auditoría: {res.id_auditoria[:12]}...",
                )
                self._caso_seleccionado = None
                self.frame_caso_activo.pack_forget()
                self.lbl_sin_seleccion.pack(pady=40)
                self.recargar_bandeja()
                self.recargar_historial()
                self.tabview.set("1. Bandeja de Casos Pendientes")
            else:
                messagebox.showerror("Error en resolución", res.mensaje)

        except Exception as e:
            messagebox.showerror("Fallo en resolución", f"No fue posible asentar la resolución pericial:\n{e}")

    def recargar_historial(self) -> None:
        """Carga y muestra el historial de auditoría desde el servicio."""
        for w in self.scroll_historial.winfo_children():
            w.destroy()

        try:
            historial = self.service.listar_historial_resoluciones()
        except Exception as e:
            messagebox.showerror("Error de historial", f"Error al consultar auditoría:\n{e}")
            historial = []

        if not historial:
            lbl_vacio = ctk.CTkLabel(
                self.scroll_historial,
                text="No hay registros de resolución pericial asentados en auditoria_evento.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color="gray",
            )
            lbl_vacio.pack(pady=40)
            return

        for h in historial:
            card = ctk.CTkFrame(self.scroll_historial, corner_radius=6)
            card.pack(fill="x", padx=6, pady=4)

            lbl_enc = ctk.CTkLabel(
                card,
                text=f"{h.fecha_hora[:19]}  |  Operador: {h.usuario_operador}  |  Caso: {h.id_registro_afectado}",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=("#0B3C5D", "#4FC3F7"),
                anchor="w",
            )
            lbl_enc.pack(padx=12, pady=(8, 2), anchor="w")

            lbl_cambios = ctk.CTkLabel(
                card,
                text=f"Cambios: {h.cambios_resumen}",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                anchor="w",
            )
            lbl_cambios.pack(padx=12, pady=1, anchor="w")

            lbl_just = ctk.CTkLabel(
                card,
                text=f"Justificación: {h.motivo_modificacion}",
                font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
                text_color=("gray40", "gray70"),
                anchor="w",
            )
            lbl_just.pack(padx=12, pady=(1, 8), anchor="w")
