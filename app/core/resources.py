"""app.core.resources

Módulo centralizado de resolución de recursos institucionales.
Garantiza la localización determinista de plantillas, activos y configuración
tanto en modo desarrollo (código fuente) como en modo empaquetado (PyInstaller onedir/onefile),
independientemente del Current Working Directory (CWD).
"""

import os
import sys
from pathlib import Path
from typing import Optional, Union

# Raíz del proyecto calculada a partir de la ubicación de este archivo:
# app/core/resources.py -> app/core -> app -> PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

PLANTILLAS_OFICIALES = (
    "Matriz_1_Consolidado_Actividades.xlsx",
    "Matriz_2_Estudiantes.xlsx",
    "Matriz_3_Academicos_Administrativos.xlsx",
    "Matriz_4_Colaboradores.xlsx",
    "Matriz_5_Protagonistas_Beneficiados.xlsx",
)


def _contiene_plantillas(directorio: Path) -> bool:
    """Comprueba si un directorio existe y contiene al menos una plantilla oficial .xlsx."""
    if not directorio.is_dir():
        return False
    return any(directorio.glob("*.xlsx"))


def resolver_ruta_recurso(nombre_recurso: str) -> Path:
    """Resuelve la ruta absoluta a un recurso empaquetado o de desarrollo.

    Jerarquía:
    1. Entorno empaquetado (PyInstaller):
       - sys._MEIPASS / nombre_recurso
       - Path(sys.executable).parent / "_internal" / nombre_recurso
       - Path(sys.executable).parent / nombre_recurso
    2. Entorno desarrollo:
       - PROJECT_ROOT / nombre_recurso
       - Path.cwd() / nombre_recurso
    3. Fallback:
       - Path(nombre_recurso)
    """
    # 1. Modo empaquetado PyInstaller
    if hasattr(sys, "_MEIPASS"):
        p_meipass = Path(sys._MEIPASS) / nombre_recurso
        if p_meipass.exists():
            return p_meipass

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        p_internal = exe_dir / "_internal" / nombre_recurso
        if p_internal.exists():
            return p_internal
        p_exe = exe_dir / nombre_recurso
        if p_exe.exists():
            return p_exe

    # 2. Modo desarrollo
    p_dev = PROJECT_ROOT / nombre_recurso
    if p_dev.exists():
        return p_dev

    p_cwd = Path.cwd() / nombre_recurso
    if p_cwd.exists():
        return p_cwd

    return Path(nombre_recurso)


def resolver_ruta_templates(
    carpeta_templates: Optional[Union[str, Path]] = None,
) -> Path:
    """Resuelve la ruta absoluta al directorio de plantillas oficiales M1–M5.

    Jerarquía de resolución determinista e independiente del CWD:

    Caso A — Ruta explícita:
        Si el consumidor suministra una ruta explícita distinta de:
        None, "", "templates", Path("templates"),
        se respeta estrictamente dicha ruta (para fixtures, testing o personalización).

    Caso B — Desarrollo:
        Cuando se ejecuta desde código fuente, localiza PROJECT_ROOT / "templates"
        independientemente del directorio de trabajo actual.

    Caso C — PyInstaller (Empaquetado):
        Cuando la aplicación está empaquetada, busca en las ubicaciones
        internas válidas que contengan las plantillas oficiales:
        - sys._MEIPASS / "templates"
        - Path(sys.executable).parent / "_internal" / "templates"
        - Path(sys.executable).parent / "templates"

    Args:
        carpeta_templates: Ruta opcional proporcionada por el llamador.

    Returns:
        Path resuelto al directorio de plantillas.
    """
    # Caso A: Ruta explícita personalizada
    if carpeta_templates is not None:
        str_val = str(carpeta_templates).strip()
        # Si NO es un valor por defecto o genérico, respetar la ruta explícita del llamador
        if str_val not in ("", "templates", "templates/", "templates\\"):
            p_explicita = Path(carpeta_templates)
            return p_explicita

        # Si es el valor por defecto relativo "templates", verificar si existe en CWD y tiene plantillas
        p_cwd = Path("templates")
        if _contiene_plantillas(p_cwd):
            return p_cwd.resolve()

    # Caso C: Modo empaquetado (PyInstaller)
    if hasattr(sys, "_MEIPASS"):
        p_meipass = Path(sys._MEIPASS) / "templates"
        if _contiene_plantillas(p_meipass):
            return p_meipass

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        p_internal = exe_dir / "_internal" / "templates"
        if _contiene_plantillas(p_internal):
            return p_internal
        p_exe_tpl = exe_dir / "templates"
        if _contiene_plantillas(p_exe_tpl):
            return p_exe_tpl

    # Caso B: Modo desarrollo (código fuente)
    p_dev = PROJECT_ROOT / "templates"
    if _contiene_plantillas(p_dev):
        return p_dev

    # Fallback relativo a CWD
    p_cwd_fallback = Path.cwd() / "templates"
    if _contiene_plantillas(p_cwd_fallback):
        return p_cwd_fallback

    # Fallback final estándar
    return Path("templates")
