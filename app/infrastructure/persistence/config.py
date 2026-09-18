"""Configuración de Persistencia SQLite - Sistema Institucional BICU.

Fase 25 (Etapa 25.1): Infraestructura SQLite y Gobernanza de Ubicación.
Define la configuración estandarizada de SQLite con modo WAL, llaves foráneas
activadas y aislamiento estricto de la base de datos respecto a clientes
de sincronización en la nube (Microsoft OneDrive).
"""

import os
import sys
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


class DatabaseSecurityError(ValueError):
    """Excepción lanzada cuando se detecta una configuración de ruta insegura."""
    pass


def get_default_database_directory() -> Path:
    """Obtiene el directorio local seguro para la base de datos activa.

    Regla de Ubicación Institucional:
    La base de datos activa DEBE ubicarse en el almacenamiento local del sistema
    operativo (%LOCALAPPDATA% en Windows o ~/.local/share en Unix/Linux) para
    evitar colisiones de bloqueo con sincronizadores cloud (OneDrive, Dropbox).
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base_dir = Path(local_app_data)
        else:
            base_dir = Path.home() / "AppData" / "Local"
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            base_dir = Path(xdg_data)
        else:
            base_dir = Path.home() / ".local" / "share"

    target_dir = base_dir / "BICU_Sistema" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def get_default_database_path() -> Path:
    """Devuelve la ruta absoluta predeterminada para el archivo SQLite activo.

    Ruta estándar: %LOCALAPPDATA%\\BICU_Sistema\\data\\bicu_sistema.db
    """
    return get_default_database_directory() / "bicu_sistema.db"


def is_onedrive_path(path: Union[str, Path]) -> bool:
    """Comprueba si una ruta determinada se encuentra dentro de Microsoft OneDrive.

    Esta verificación previene colisiones de bloqueo catastróficas entre
    SQLite WAL y el motor de sincronización de archivos de OneDrive en Windows.
    """
    path_resolved = Path(path).resolve()
    path_str_lower = str(path_resolved).lower()

    # Comprobar si "onedrive" aparece como componente o texto en la ruta
    if "onedrive" in path_str_lower:
        return True

    # Comprobar variables de entorno estándar de OneDrive en Windows
    onedrive_vars = ["OneDrive", "OneDriveConsumer", "OneDriveCommercial"]
    for var in onedrive_vars:
        env_val = os.environ.get(var)
        if env_val:
            try:
                env_path = Path(env_val).resolve()
                if path_resolved == env_path or env_path in path_resolved.parents:
                    return True
            except (ValueError, OSError):
                continue

    return False


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuración inmutable de conexión y pragmas de SQLite.

    Atributos:
        db_path: Ruta al archivo de base de datos SQLite.
        journal_mode: Modo de journal. Predeterminado 'WAL' (Write-Ahead Logging).
        foreign_keys: Activar integridad referencial estricta. Predeterminado True.
        busy_timeout_ms: Tiempo de espera ante bloqueos en milisegundos. Predeterminado 5000 ms.
        synchronous: Nivel de sincronización de disco. En WAL, 'NORMAL' es seguro y performante.
        cache_size: Tamaño de caché de páginas (-2000 equivale a ~2 MB de RAM).
        allow_onedrive: Bandera explícita para pruebas o escenarios forzados (por defecto False).
    """

    db_path: Path = field(default_factory=get_default_database_path)
    journal_mode: str = "WAL"
    foreign_keys: bool = True
    busy_timeout_ms: int = 5000
    synchronous: str = "NORMAL"
    cache_size: int = -2000
    allow_onedrive: bool = False

    def __post_init__(self) -> None:
        """Valida que la configuración cumpla con las directrices de seguridad."""
        # Convertir a Path si se pasa string
        if not isinstance(self.db_path, Path):
            object.__setattr__(self, "db_path", Path(self.db_path))

        # Validación estricta de OneDrive para bases de datos en archivo (ignora :memory:)
        if str(self.db_path) != ":memory:" and not self.allow_onedrive:
            if is_onedrive_path(self.db_path):
                raise DatabaseSecurityError(
                    f"VIOLACIÓN DE SEGURIDAD OPERACIONAL: La base de datos activa no debe residir "
                    f"dentro de Microsoft OneDrive ({self.db_path}). Esto causa colisiones críticas "
                    f"de bloqueo en modo WAL. Use la ruta local segura %LOCALAPPDATA%\\BICU_Sistema\\data."
                )

        # Validar opciones de journal_mode
        valid_journals = {"WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"}
        if self.journal_mode.upper() not in valid_journals:
            raise ValueError(f"journal_mode inválido: {self.journal_mode}")

        # Validar synchronous
        valid_sync = {"OFF", "NORMAL", "FULL", "EXTRA"}
        if self.synchronous.upper() not in valid_sync:
            raise ValueError(f"synchronous inválido: {self.synchronous}")
