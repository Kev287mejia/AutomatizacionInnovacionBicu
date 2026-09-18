"""
app.word_consolidator.ui.app

Aplicación de escritorio principal del Consolidador Word Institucional BICU (Fase 14.9).
Configura DPI awareness de forma segura en Windows, establece estilos y temas institucionales,
e inicializa la ventana principal de CustomTkinter.
"""

import ctypes
import os
import sys
from typing import Optional

import customtkinter as ctk

from app.word_consolidator.ui.views.main_window import MainWindow


def configurar_dpi_awareness() -> None:
    """
    Configura el escalado de alta densidad de píxeles (DPI) en Windows de forma segura.
    Evita que los textos y controles se vean borrosos en monitores 4K o pantallas modernas.
    Maneja excepciones defensivamente para no fallar en otros entornos.
    """
    if sys.platform == "win32":
        try:
            # Opción 1: Windows 8.1+ (Per-Monitor DPI Aware)
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore
        except Exception:
            try:
                # Opción 2: Windows Vista / 7+ (System DPI Aware)
                ctypes.windll.user32.SetProcessDPIAware()  # type: ignore
            except Exception:
                pass



def obtener_ruta_icono() -> Optional[str]:
    """
    Resuelve de forma robusta la ruta al icono oficial de BICU.
    Funciona tanto en desarrollo local como dentro del paquete PyInstaller onedir (_MEIPASS).
    """
    from pathlib import Path

    # 1. En entorno empaquetado por PyInstaller
    if hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / "assets" / "bicu_logo.ico"
        if p.exists():
            return str(p)

    # 2. En entorno de desarrollo (raíz del proyecto)
    root = Path(__file__).resolve().parent.parent.parent.parent
    p_dev = root / "assets" / "bicu_logo.ico"
    if p_dev.exists():
        return str(p_dev)

    # 3. Fallback relativo al directorio de ejecución
    p_cwd = Path.cwd() / "assets" / "bicu_logo.ico"
    if p_cwd.exists():
        return str(p_cwd)

    return None


class ConsolidatorApp(ctk.CTk):
    """
    Ventana raíz de la aplicación de escritorio CustomTkinter para BICU.
    """

    def __init__(self, **kwargs):
        # Configurar DPI antes de inicializar la ventana
        configurar_dpi_awareness()

        # Configuración estética institucional
        ctk.set_appearance_mode("System")  # Adaptable a Light/Dark de Windows
        ctk.set_default_color_theme("blue")  # Paleta azul institucional

        super().__init__(**kwargs)

        self.title("BICU — Consolidador Institucional de Asistencias (Excel → Word)")
        self.geometry("980x700")
        self.minsize(800, 520)

        # Configurar icono oficial institucional de BICU
        icono = obtener_ruta_icono()
        if icono and sys.platform == "win32":
            try:
                self.iconbitmap(icono)
                # Refuerzo para garantizar persistencia ante inicialización asíncrona de Tk
                self.after(200, lambda: self._aplicar_icono_seguro(icono))
            except Exception:
                pass

        # Configurar grid de la ventana raíz
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Instanciar vista principal
        self.main_window = MainWindow(self)
        self.main_window.grid(row=0, column=0, sticky="nsew")

    def _aplicar_icono_seguro(self, icono: str) -> None:
        """Aplica el icono verificando que la ventana siga viva."""
        try:
            if self.winfo_exists():
                self.iconbitmap(icono)
        except Exception:
            pass


def main() -> None:
    """Punto de inicio para ejecutar la aplicación."""
    app = ConsolidatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
