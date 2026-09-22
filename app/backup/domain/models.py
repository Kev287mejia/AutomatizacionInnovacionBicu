"""app.backup.domain.models

Modelos de dominio puros para el sistema de respaldo y restauración institucional BICU.

Fase 29.24.1 — Consolidación Operativa.

Principios de diseño:
    - Inmutabilidad: todos los modelos son dataclasses frozen.
    - Sin dependencias de infraestructura: solo tipos de la biblioteca estándar.
    - Representación explícita de todos los estados posibles.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# ENUMERACIONES DE ESTADO
# ---------------------------------------------------------------------------


class PreflightStatus(str, Enum):
    """Estado resultante de la verificación previa al inicio de la aplicación."""

    READY = "READY"
    """La aplicación puede iniciar normalmente."""

    WARNING = "WARNING"
    """Condición no crítica detectada; el operador debe ser informado."""

    FATAL = "FATAL"
    """La aplicación no debe iniciar operaciones institucionales."""


class RestoreStage(str, Enum):
    """Etapa alcanzada durante el proceso de restauración."""

    NOT_STARTED = "NOT_STARTED"
    EXTRACTING = "EXTRACTING"
    VALIDATING_HASH = "VALIDATING_HASH"
    VALIDATING_SQLITE = "VALIDATING_SQLITE"
    VALIDATING_SCHEMA = "VALIDATING_SCHEMA"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CREATING_SAFETY_BACKUP = "CREATING_SAFETY_BACKUP"
    REPLACING_DATABASE = "REPLACING_DATABASE"
    POST_VERIFICATION = "POST_VERIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


# ---------------------------------------------------------------------------
# MANIFEST DE RESPALDO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackupManifest:
    """Manifiesto técnico de un archivo de respaldo institucional BICU.

    Contiene toda la información necesaria para validar la compatibilidad,
    integridad y contenido de un respaldo. No almacena secretos ni credenciales.
    """

    # Identificación del respaldo
    backup_id: str
    """Identificador único del respaldo (UUID v4)."""

    backup_format_version: str
    """Versión del formato de empaquetado del backup. Actualmente '1.0'."""

    # Contexto de generación
    created_at_utc: str
    """Fecha y hora UTC de generación en formato ISO 8601."""

    created_at_local: str
    """Fecha y hora local de generación (informativa, no para comparación)."""

    # Versiones del sistema
    system_version: str
    """Versión del software BICU que generó el respaldo."""

    schema_version: int
    """Versión del esquema SQLite en el momento de generación."""

    # Integridad criptográfica
    database_sha256: str
    """Hash SHA-256 del archivo database.sqlite contenido en el respaldo."""

    database_size_bytes: int
    """Tamaño en bytes del archivo database.sqlite extraído."""

    # Contenido estructural
    table_names: List[str]
    """Lista ordenada de nombres de tablas presentes en la base de datos respaldada."""

    table_row_counts: Dict[str, int]
    """Conteos de filas por tabla en el momento de generación del backup."""

    # Metadatos de schema_version registrados
    schema_migrations_applied: List[int]
    """Lista de versiones de migración aplicadas (ej. [1, 2, 3, 4])."""

    # Información técnica no sensible del entorno
    python_version: str
    """Versión de Python en la plataforma de generación (ej. '3.14.5')."""

    platform: str
    """Plataforma del sistema operativo (ej. 'win32')."""

    def to_dict(self) -> dict:
        """Serializa el manifiesto a un diccionario JSON-compatible."""
        return {
            "backup_id": self.backup_id,
            "backup_format_version": self.backup_format_version,
            "created_at_utc": self.created_at_utc,
            "created_at_local": self.created_at_local,
            "system_version": self.system_version,
            "schema_version": self.schema_version,
            "database_sha256": self.database_sha256,
            "database_size_bytes": self.database_size_bytes,
            "table_names": sorted(self.table_names),
            "table_row_counts": self.table_row_counts,
            "schema_migrations_applied": self.schema_migrations_applied,
            "python_version": self.python_version,
            "platform": self.platform,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BackupManifest":
        """Deserializa el manifiesto desde un diccionario JSON."""
        return cls(
            backup_id=str(data["backup_id"]),
            backup_format_version=str(data.get("backup_format_version", "1.0")),
            created_at_utc=str(data["created_at_utc"]),
            created_at_local=str(data.get("created_at_local", "")),
            system_version=str(data.get("system_version", "unknown")),
            schema_version=int(data["schema_version"]),
            database_sha256=str(data["database_sha256"]),
            database_size_bytes=int(data["database_size_bytes"]),
            table_names=list(data.get("table_names", [])),
            table_row_counts=dict(data.get("table_row_counts", {})),
            schema_migrations_applied=list(data.get("schema_migrations_applied", [])),
            python_version=str(data.get("python_version", "unknown")),
            platform=str(data.get("platform", "unknown")),
        )


# ---------------------------------------------------------------------------
# RESULTADO DE BACKUP
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackupResult:
    """Resultado de la operación de generación de respaldo."""

    success: bool
    """True si el backup fue generado y verificado correctamente."""

    backup_path: Optional[Path]
    """Ruta absoluta al archivo .bicu.bak generado. None si falló."""

    backup_filename: str
    """Nombre del archivo de respaldo (sin directorio)."""

    manifest: Optional[BackupManifest]
    """Manifiesto del backup generado. None si falló."""

    error_message: Optional[str]
    """Descripción del error si success=False. None si success=True."""

    duration_seconds: float
    """Duración total de la operación en segundos."""

    @property
    def backup_sha256(self) -> Optional[str]:
        """Hash SHA-256 del archivo .bicu.bak completo (no del SQLite interno)."""
        if self.backup_path is None or not self.backup_path.exists():
            return None
        h = hashlib.sha256()
        with open(self.backup_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()


# ---------------------------------------------------------------------------
# RESULTADO DE RESTAURACIÓN
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RestoreResult:
    """Resultado de la operación de restauración de un backup."""

    success: bool
    """True si la restauración completó correctamente."""

    final_stage: RestoreStage
    """Etapa alcanzada al finalizar (éxito o fallo)."""

    safety_backup_path: Optional[Path]
    """Ruta al snapshot preventivo creado antes del reemplazo. None si no se creó."""

    error_message: Optional[str]
    """Descripción del error si success=False. None si success=True."""

    schema_version_after: Optional[int]
    """Versión de esquema verificada tras la restauración."""

    duration_seconds: float
    """Duración total de la operación en segundos."""


# ---------------------------------------------------------------------------
# RESULTADO DE PRE-FLIGHT
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreflightCheck:
    """Resultado de una verificación individual dentro del preflight."""

    name: str
    """Nombre descriptivo de la verificación."""

    status: PreflightStatus
    """Estado resultante de esta verificación."""

    message: str
    """Mensaje descriptivo para el operador."""

    detail: Optional[str] = None
    """Detalle técnico opcional para logs (puede omitirse en la UI)."""


@dataclass(frozen=True)
class PreflightReport:
    """Informe consolidado del preflight institucional.

    El estado global es el más severo entre todos los checks individuales.
    """

    checks: List[PreflightCheck]
    """Lista de todas las verificaciones realizadas."""

    overall_status: PreflightStatus
    """Estado global derivado del check más severo."""

    checked_at_utc: str
    """Marca temporal UTC de cuando se realizó el preflight."""

    @property
    def is_ready(self) -> bool:
        return self.overall_status == PreflightStatus.READY

    @property
    def has_warnings(self) -> bool:
        return self.overall_status == PreflightStatus.WARNING

    @property
    def is_fatal(self) -> bool:
        return self.overall_status == PreflightStatus.FATAL

    @property
    def fatal_checks(self) -> List[PreflightCheck]:
        return [c for c in self.checks if c.status == PreflightStatus.FATAL]

    @property
    def warning_checks(self) -> List[PreflightCheck]:
        return [c for c in self.checks if c.status == PreflightStatus.WARNING]

    def summary_lines(self) -> List[str]:
        """Genera líneas de resumen legibles para el operador."""
        lines = [f"Estado global: {self.overall_status.value}"]
        for check in self.checks:
            icon = {"READY": "✓", "WARNING": "⚠", "FATAL": "✗"}.get(
                check.status.value, "?"
            )
            lines.append(f"  {icon} [{check.status.value}] {check.name}: {check.message}")
        return lines
