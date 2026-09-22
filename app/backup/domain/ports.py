"""app.backup.domain.ports

Puerto abstracto para el servicio de respaldo institucional BICU.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.backup.domain.models import BackupResult, RestoreResult


class IBackupService(ABC):
    """Contrato abstracto para el servicio de backup y restauración institucional."""

    @abstractmethod
    def create_backup(
        self,
        destination_dir: Path,
        system_version: str = "unknown",
    ) -> BackupResult:
        """Genera un respaldo consistente de la base de datos activa.

        Args:
            destination_dir: Directorio donde se almacenará el archivo .bicu.bak.
            system_version: Versión del sistema incluida en el manifiesto.

        Returns:
            BackupResult con el resultado de la operación.
        """

    @abstractmethod
    def validate_backup(self, backup_path: Path) -> tuple[bool, str]:
        """Valida la integridad de un archivo de respaldo.

        Args:
            backup_path: Ruta al archivo .bicu.bak a validar.

        Returns:
            Tupla (es_válido, mensaje_descriptivo).
        """

    @abstractmethod
    def restore_backup(
        self,
        backup_path: Path,
        confirmed_by_user: bool = False,
    ) -> RestoreResult:
        """Restaura la base de datos desde un archivo de respaldo.

        La restauración requiere confirmación explícita del usuario
        (confirmed_by_user=True). Si no se confirma, retorna ABORTED.

        Args:
            backup_path: Ruta al archivo .bicu.bak a restaurar.
            confirmed_by_user: True si el operador confirmó la operación.

        Returns:
            RestoreResult con el resultado de la operación.
        """
