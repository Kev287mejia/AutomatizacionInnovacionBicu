"""
tests.conftest

Configuración global de entorno para la suite de pruebas pytest.
Optimiza límites de descriptores de archivos de C runtime en Windows para suites extensas (>500 tests con I/O intensivo de Excel y Word).
Provee fixture session-scoped para la ventana raíz de CustomTkinter, evitando múltiples ciclos de inicialización/destrucción de Tcl/Tk.
"""

import os
import sys
import gc
import pytest

if sys.platform == "win32":
    # 1. Configurar variables de entorno canónicas para Tcl/Tk
    tcl_dir = os.path.join(sys.base_prefix, "tcl", "tcl8.6")
    tk_dir = os.path.join(sys.base_prefix, "tcl", "tk8.6")
    if os.path.isdir(tcl_dir):
        os.environ.setdefault("TCL_LIBRARY", tcl_dir)
    if os.path.isdir(tk_dir):
        os.environ.setdefault("TK_LIBRARY", tk_dir)

    # 2. Ampliar el límite de descriptores stdio en ucrtbase.dll y msvcrt.dll a 2048 (máximo)
    try:
        import ctypes
        for dll_name in ("ucrtbase.dll", "msvcrt.dll"):
            try:
                dll = ctypes.CDLL(dll_name)
                if hasattr(dll, "_setmaxstdio"):
                    dll._setmaxstdio(2048)
            except Exception:
                pass
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def app_root():
    """Ventana raíz de CustomTkinter persistente para toda la sesión de pruebas."""
    import customtkinter as ctk
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass
    gc.collect()


def pytest_runtest_teardown(item, nextitem):
    """Recolector periódico defensivo para liberar descriptores de archivos Excel/Word en Windows."""
    gc.collect()
