"""app.backup.application.restore_service

Servicio institucional de restauración controlada de la base de datos BICU.

Fase 29.24.1 — Consolidación Operativa.

FLUJO CANÓNICO DE RESTAURACIÓN:
    1. Verificar precondiciones (backup existe, no es OneDrive, BD activa accesible).
    2. Extraer y validar el backup en directorio temporal (hash, SQLite, schema).
    3. Detener si no hay confirmación explícita del operador (ABORTED).
    4. Crear snapshot preventivo de la base activa (safety backup).
    5. Reemplazar la base activa con la copia extraída (operación atómica).
    6. Verificar la base restaurada (integrity_check, pragma, schema_version).
    7. Retornar RestoreResult con estado final.

INVARIANTES ABSOLUTOS:
    - Nunca se reemplaza la base activa sin haber generado el safety backup.
    - El safety backup se genera aunque la base activa parezca corrupta.
    - Si el replace falla, se intenta recuperar desde el safety backup.
    - No se modifica ninguna matriz patrimonial (M1-M5) durante el proceso.
    - No se modifica ningún registro histórico pre-existente.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from app.backup.domain.models import (
    BackupManifest,
    RestoreResult,
    RestoreStage,
)
from app.backup.application.backup_service import BackupService

logger = logging.getLogger("bicu.restore.service")

# Número máximo de intentos de reemplazo atómico
_MAX_REPLACE_RETRIES = 3

# Tiempo de espera entre reintentos de reemplazo (segundos)
_REPLACE_RETRY_SLEEP = 0.25


class RestoreService:
    """Servicio de restauración controlada de la base de datos institucional BICU.

    Este servicio es la única entidad autorizada para reemplazar la base activa
    en un flujo de restauración. Requiere confirmación explícita del operador.

    Uso:
        svc = RestoreService(db_path=Path(".../bicu_sistema.db"))
        result = svc.restore_backup(
            backup_path=Path(".../BICU_BACKUP_...bicu.bak"),
            confirmed_by_user=True,
        )
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
    ) -> None:
        """Inicializa el servicio de restauración.

        Args:
            db_path: Ruta a la base de datos activa. Si es None, se usa la ruta
                     institucional predeterminada.
        """
        if db_path is None:
            from app.infrastructure.persistence.config import get_default_database_path
            db_path = get_default_database_path()
        self._db_path = Path(db_path)
        self._backup_service = BackupService(db_path=self._db_path)

    # ------------------------------------------------------------------
    # PUNTO DE ENTRADA PRINCIPAL
    # ------------------------------------------------------------------

    def restore_backup(
        self,
        backup_path: Path,
        confirmed_by_user: bool = False,
    ) -> RestoreResult:
        """Restaura la base de datos desde un archivo .bicu.bak.

        Args:
            backup_path: Ruta al archivo .bicu.bak a restaurar.
            confirmed_by_user: True si el operador confirmó la operación.
                               Si False, retorna RestoreResult(stage=ABORTED).

        Returns:
            RestoreResult con estado, ruta al safety backup y mensajes de error.
        """
        start_ts = time.perf_counter()
        backup_path = Path(backup_path)

        # --- ETAPA 0: Verificar confirmación ---
        if not confirmed_by_user:
            logger.warning(
                "Restauración abortada: no se recibió confirmación explícita del operador."
            )
            return RestoreResult(
                success=False,
                final_stage=RestoreStage.ABORTED,
                safety_backup_path=None,
                error_message=(
                    "La restauración fue abortada porque el operador no confirmó la operación. "
                    "La base de datos activa NO fue modificada."
                ),
                schema_version_after=None,
                duration_seconds=time.perf_counter() - start_ts,
            )

        # --- ETAPA 1: Precondiciones ---
        logger.info("Iniciando proceso de restauración: %s", backup_path.name)

        if not backup_path.exists():
            return RestoreResult(
                success=False,
                final_stage=RestoreStage.FAILED,
                safety_backup_path=None,
                error_message=f"El archivo de backup no existe: {backup_path}",
                schema_version_after=None,
                duration_seconds=time.perf_counter() - start_ts,
            )

        # Verificar OneDrive antes de operar
        from app.infrastructure.persistence.config import is_onedrive_path
        if is_onedrive_path(self._db_path):
            return RestoreResult(
                success=False,
                final_stage=RestoreStage.FAILED,
                safety_backup_path=None,
                error_message=(
                    "La ruta de la base de datos activa está dentro de OneDrive. "
                    "La restauración no puede realizarse en esta configuración."
                ),
                schema_version_after=None,
                duration_seconds=time.perf_counter() - start_ts,
            )

        with tempfile.TemporaryDirectory(prefix="bicu_restore_") as tmpdir:
            tmp = Path(tmpdir)

            # --- ETAPA 2: Extraer backup ---
            try:
                logger.info("Extrayendo backup en directorio temporal...")
                with zipfile.ZipFile(backup_path, "r") as zf:
                    zf.extractall(tmp)
            except Exception as exc:
                logger.error("Error extrayendo backup: %s", exc, exc_info=True)
                return RestoreResult(
                    success=False,
                    final_stage=RestoreStage.EXTRACTING,
                    safety_backup_path=None,
                    error_message=f"Error extrayendo el backup: {exc}",
                    schema_version_after=None,
                    duration_seconds=time.perf_counter() - start_ts,
                )

            extracted_db = tmp / "database.sqlite"
            manifest_file = tmp / "manifest.json"

            if not extracted_db.exists():
                return RestoreResult(
                    success=False,
                    final_stage=RestoreStage.EXTRACTING,
                    safety_backup_path=None,
                    error_message="El backup no contiene 'database.sqlite'.",
                    schema_version_after=None,
                    duration_seconds=time.perf_counter() - start_ts,
                )

            # --- ETAPA 3: Validar hash ---
            try:
                manifest = BackupManifest.from_dict(
                    json.loads(manifest_file.read_text(encoding="utf-8"))
                )
            except Exception as exc:
                return RestoreResult(
                    success=False,
                    final_stage=RestoreStage.VALIDATING_HASH,
                    safety_backup_path=None,
                    error_message=f"manifest.json inválido: {exc}",
                    schema_version_after=None,
                    duration_seconds=time.perf_counter() - start_ts,
                )

            actual_hash = BackupService._sha256_file(extracted_db)
            if actual_hash != manifest.database_sha256:
                return RestoreResult(
                    success=False,
                    final_stage=RestoreStage.VALIDATING_HASH,
                    safety_backup_path=None,
                    error_message=(
                        f"Hash SHA-256 no coincide: "
                        f"esperado {manifest.database_sha256[:12]}..., "
                        f"encontrado {actual_hash[:12]}..."
                    ),
                    schema_version_after=None,
                    duration_seconds=time.perf_counter() - start_ts,
                )

            # --- ETAPA 4: Validar SQLite integrity ---
            ok_sqlite, msg_sqlite = self._check_sqlite_integrity(extracted_db)
            if not ok_sqlite:
                return RestoreResult(
                    success=False,
                    final_stage=RestoreStage.VALIDATING_SQLITE,
                    safety_backup_path=None,
                    error_message=f"Integridad SQLite del backup inválida: {msg_sqlite}",
                    schema_version_after=None,
                    duration_seconds=time.perf_counter() - start_ts,
                )

            # --- ETAPA 5: Validar compatibilidad de esquema ---
            schema_ver_backup = manifest.schema_version
            from app.backup.application.backup_service import MAX_SUPPORTED_SCHEMA_VERSION
            if schema_ver_backup > MAX_SUPPORTED_SCHEMA_VERSION:
                return RestoreResult(
                    success=False,
                    final_stage=RestoreStage.VALIDATING_SCHEMA,
                    safety_backup_path=None,
                    error_message=(
                        f"El backup requiere esquema v{schema_ver_backup}, "
                        f"esta versión del software soporta hasta v{MAX_SUPPORTED_SCHEMA_VERSION}. "
                        f"Actualice el software antes de restaurar."
                    ),
                    schema_version_after=None,
                    duration_seconds=time.perf_counter() - start_ts,
                )

            # --- ETAPA 6: Snapshot preventivo (SAFETY BACKUP) ---
            safety_backup_path: Optional[Path] = None
            if self._db_path.exists():
                logger.info("Generando snapshot preventivo de la base activa...")
                safety_dir = self._db_path.parent / "safety_snapshots"
                safety_result = self._backup_service.create_backup(
                    destination_dir=safety_dir,
                    system_version="safety-snapshot",
                )
                if not safety_result.success:
                    logger.error(
                        "No se pudo generar el snapshot preventivo: %s",
                        safety_result.error_message,
                    )
                    return RestoreResult(
                        success=False,
                        final_stage=RestoreStage.CREATING_SAFETY_BACKUP,
                        safety_backup_path=None,
                        error_message=(
                            f"No se pudo generar el snapshot preventivo de la base activa: "
                            f"{safety_result.error_message}. "
                            f"La restauración fue cancelada para proteger los datos."
                        ),
                        schema_version_after=None,
                        duration_seconds=time.perf_counter() - start_ts,
                    )
                safety_backup_path = safety_result.backup_path
                logger.info("Snapshot preventivo creado: %s", safety_backup_path)

            # --- ETAPA 7: Reemplazo atómico ---
            logger.info("Iniciando reemplazo atómico de la base de datos...")

            # Crear directorio de la base activa si no existe
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

            replace_ok, replace_err = self._atomic_replace(
                source=extracted_db,
                destination=self._db_path,
            )

            if not replace_ok:
                logger.error("Error en reemplazo atómico: %s", replace_err)

                # Intentar recuperación desde safety backup
                if safety_backup_path is not None:
                    logger.warning(
                        "Intentando recuperación desde snapshot preventivo: %s",
                        safety_backup_path,
                    )
                    self._attempt_recovery_from_safety(safety_backup_path)

                return RestoreResult(
                    success=False,
                    final_stage=RestoreStage.REPLACING_DATABASE,
                    safety_backup_path=safety_backup_path,
                    error_message=(
                        f"Error reemplazando la base de datos: {replace_err}. "
                        f"El snapshot preventivo está disponible en: {safety_backup_path}"
                    ),
                    schema_version_after=None,
                    duration_seconds=time.perf_counter() - start_ts,
                )

        # --- ETAPA 8: Post-verificación de la base restaurada ---
        # (ya fuera del tempdir — usamos la base que está ahora en su lugar)
        try:
            schema_version_after = self._get_schema_version(self._db_path)
        except Exception as exc:
            logger.warning("No se pudo leer schema_version tras restauración: %s", exc)
            schema_version_after = None

        ok_post, msg_post = self._check_sqlite_integrity(self._db_path)
        if not ok_post:
            logger.error("Post-verificación de la base restaurada falló: %s", msg_post)
            return RestoreResult(
                success=False,
                final_stage=RestoreStage.POST_VERIFICATION,
                safety_backup_path=safety_backup_path,
                error_message=(
                    f"La base restaurada no pasó la verificación post-restauración: {msg_post}. "
                    f"El snapshot preventivo está disponible en: {safety_backup_path}"
                ),
                schema_version_after=schema_version_after,
                duration_seconds=time.perf_counter() - start_ts,
            )

        logger.info(
            "Restauración completada exitosamente. Schema v%s, snapshot en: %s",
            schema_version_after,
            safety_backup_path,
        )

        return RestoreResult(
            success=True,
            final_stage=RestoreStage.COMPLETED,
            safety_backup_path=safety_backup_path,
            error_message=None,
            schema_version_after=schema_version_after,
            duration_seconds=time.perf_counter() - start_ts,
        )

    # ------------------------------------------------------------------
    # HELPERS INTERNOS
    # ------------------------------------------------------------------

    @staticmethod
    def _check_sqlite_integrity(db_path: Path) -> Tuple[bool, str]:
        """Ejecuta PRAGMA integrity_check y foreign_key_check sobre una BD."""
        try:
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("PRAGMA foreign_keys = ON;")
                ic = conn.execute("PRAGMA integrity_check;").fetchone()
                if ic is None or ic[0] != "ok":
                    return False, f"integrity_check: {ic}"
                fk = conn.execute("PRAGMA foreign_key_check;").fetchall()
                if fk:
                    return False, f"foreign_key_check: {len(fk)} violación(es)"
                return True, "ok"
            finally:
                conn.close()
        except sqlite3.Error as exc:
            return False, str(exc)

    @staticmethod
    def _get_schema_version(db_path: Path) -> Optional[int]:
        """Lee la versión máxima de esquema de la base de datos."""
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_version;").fetchone()
            return int(row[0]) if row and row[0] is not None else None
        finally:
            conn.close()

    @staticmethod
    def _atomic_replace(source: Path, destination: Path) -> Tuple[bool, str]:
        """Reemplaza destination con source de forma atómica usando rename.

        En Windows no existe rename atómico entre filesystems distintos.
        Se usa un archivo temporal en el mismo directorio que destination
        para minimizar la ventana de riesgo.

        Retries: hasta _MAX_REPLACE_RETRIES intentos con sleep entre ellos.
        """
        dest_dir = destination.parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, _MAX_REPLACE_RETRIES + 1):
            try:
                # Copiar source a un tmp en el mismo directorio que el destino
                tmp_dest = destination.with_suffix(".restore_tmp")
                shutil.copy2(str(source), str(tmp_dest))

                # Reemplazar atomicamente (os.replace es atómico en el mismo volumen)
                os.replace(str(tmp_dest), str(destination))

                # Limpiar archivos WAL y SHM de la base anterior si existen.
                # Los archivos WAL/SHM de SQLite tienen nombres como "active.db-wal"
                # y "active.db-shm" — NO son extensiones Python estándar (no comienzan con '.').
                # Por eso se construyen como parent / (name + ext).
                for ext in ("-wal", "-shm"):
                    stale = destination.parent / (destination.name + ext)
                    if stale.exists():
                        try:
                            stale.unlink()
                            logger.info("Archivo residual eliminado: %s", stale)
                        except Exception as exc:
                            logger.warning("No se pudo eliminar %s: %s", stale, exc)

                return True, "ok"

            except PermissionError as exc:
                logger.warning(
                    "PermissionError en intento %d de reemplazo: %s", attempt, exc
                )
                if attempt < _MAX_REPLACE_RETRIES:
                    time.sleep(_REPLACE_RETRY_SLEEP)
                else:
                    return (
                        False,
                        f"PermissionError tras {_MAX_REPLACE_RETRIES} intentos: {exc}",
                    )
            except Exception as exc:
                return False, str(exc)

        return False, "Número máximo de reintentos de reemplazo alcanzado."

    def _attempt_recovery_from_safety(self, safety_path: Path) -> None:
        """Intenta recuperar la base activa desde el safety backup.

        Este método es un best-effort: si falla, registra el error pero no
        propaga excepciones (ya estamos en un flujo de error crítico).
        """
        try:
            with tempfile.TemporaryDirectory(prefix="bicu_recovery_") as tmpdir:
                with zipfile.ZipFile(safety_path, "r") as zf:
                    zf.extractall(tmpdir)
                recovered_db = Path(tmpdir) / "database.sqlite"
                if recovered_db.exists():
                    ok, err = self._atomic_replace(recovered_db, self._db_path)
                    if ok:
                        logger.info("Recuperación desde safety backup exitosa.")
                    else:
                        logger.error(
                            "Recuperación desde safety backup FALLÓ: %s. "
                            "Intervención manual requerida en: %s",
                            err, safety_path,
                        )
                else:
                    logger.error(
                        "El safety backup no contiene database.sqlite. "
                        "Intervención manual requerida: %s",
                        safety_path,
                    )
        except Exception as exc:
            logger.error(
                "Excepción durante intento de recuperación: %s. "
                "Safety backup disponible en: %s",
                exc, safety_path, exc_info=True,
            )
