"""app.backup

Módulo institucional de respaldo y restauración de datos — Sistema BICU.

Fase 29.24.1: Implementación de Consolidación Operativa.

Arquitectura:
    UI / CLI
       ↓
    application.backup_service.BackupService
    application.restore_service.RestoreService
    application.preflight.ReleasePreflightChecker
       ↓
    domain.models (BackupManifest, BackupResult, RestoreResult, PreflightReport)
    domain.ports (IBackupService)

Principios:
    - Cero modificación de datos institucionales durante la generación de un backup.
    - Backup basado en SQLite Online Backup API (nunca shutil.copy en caliente).
    - Restore con snapshot preventivo antes de tocar la base activa.
    - Preflight no destructivo — solo lectura, sin correcciones silenciosas.
    - Cero secrets, credenciales o rutas personales en archivos de backup.
"""

from app.backup.domain.models import (
    BackupManifest,
    BackupResult,
    RestoreResult,
    RestoreStage,
    PreflightReport,
    PreflightStatus,
    PreflightCheck,
)
from app.backup.application.backup_service import BackupService
from app.backup.application.restore_service import RestoreService
from app.backup.application.preflight import ReleasePreflightChecker

__all__ = [
    "BackupManifest",
    "BackupResult",
    "RestoreResult",
    "RestoreStage",
    "PreflightReport",
    "PreflightStatus",
    "PreflightCheck",
    "BackupService",
    "RestoreService",
    "ReleasePreflightChecker",
]
