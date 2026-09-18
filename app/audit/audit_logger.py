"""
app/audit/audit_logger.py

Sistema de logging y auditoría del proyecto.

Responsabilidades:
- Configurar el logger central del sistema usando settings.yaml.
- Proveer una función get_logger() para que cualquier módulo
  obtenga su propio logger con nombre descriptivo.
- Escribir simultáneamente a consola y a archivo de log rotativo.

Uso:
    from app.audit.audit_logger import get_logger
    logger = get_logger(__name__)
    logger.info("Mensaje informativo")
    logger.warning("Advertencia")
    logger.error("Error crítico")
"""

import logging
import logging.handlers
import os
import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Ruta base del proyecto (dos niveles arriba de este archivo: app/audit/ -> /)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"

# ---------------------------------------------------------------------------
# Bandera para no configurar el logging raíz más de una vez
# ---------------------------------------------------------------------------
_configurado = False


def _cargar_settings() -> dict:
    """
    Carga el archivo settings.yaml.
    Si no existe o hay un error, devuelve valores por defecto seguros.
    """
    defaults = {
        "logging": {
            "nivel": "DEBUG",
            "archivo": "logs/sistema.log",
            "formato": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "fecha_formato": "%Y-%m-%d %H:%M:%S",
            "max_bytes": 5242880,
            "backup_count": 3,
        }
    }
    if not SETTINGS_PATH.exists():
        return defaults
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if data else defaults
    except Exception:
        return defaults


def configurar_logging() -> None:
    """
    Configura el sistema de logging del proyecto.
    - Handler de archivo rotativo en logs/sistema.log
    - Handler de consola (stdout)
    - Se ejecuta una sola vez aunque se llame varias veces.
    """
    global _configurado
    if _configurado:
        return

    settings = _cargar_settings()
    cfg = settings.get("logging", {})

    nivel_str = cfg.get("nivel", "DEBUG").upper()
    nivel = getattr(logging, nivel_str, logging.DEBUG)
    formato = cfg.get("formato", "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    fecha_fmt = cfg.get("fecha_formato", "%Y-%m-%d %H:%M:%S")
    archivo_log = cfg.get("archivo", "logs/sistema.log")
    max_bytes = cfg.get("max_bytes", 5_242_880)
    backup_count = cfg.get("backup_count", 3)

    # Resolver ruta del archivo de log relativa al proyecto
    ruta_log = BASE_DIR / archivo_log
    ruta_log.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(fmt=formato, datefmt=fecha_fmt)

    # --- Handler de archivo rotativo ---
    file_handler = logging.handlers.RotatingFileHandler(
        filename=ruta_log,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(nivel)
    file_handler.setFormatter(formatter)

    # --- Handler de consola ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(nivel)
    console_handler.setFormatter(formatter)

    # --- Logger raíz ---
    root_logger = logging.getLogger()
    root_logger.setLevel(nivel)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _configurado = True

    # Primera línea en el log
    root_logger.info("=" * 70)
    root_logger.info("Sistema de Automatización Estadístico de Asistencias iniciado.")
    root_logger.info(f"Archivo de log: {ruta_log}")
    root_logger.info("=" * 70)


def get_logger(nombre: str) -> logging.Logger:
    """
    Devuelve un logger con el nombre indicado.
    Configura el sistema de logging si todavía no se hizo.

    Args:
        nombre: Normalmente se pasa __name__ desde el módulo que lo llama.
                Ejemplo: get_logger(__name__)

    Returns:
        logging.Logger listo para usar.
    """
    configurar_logging()
    return logging.getLogger(nombre)
