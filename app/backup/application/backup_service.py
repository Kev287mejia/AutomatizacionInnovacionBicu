"""app.backup.application.backup_service

Servicio institucional de generación de respaldo consistente de la base de datos BICU.

Fase 29.24.1 — Consolidación Operativa.

REGLA FUNDAMENTAL:
    El respaldo se genera exclusivamente mediante la SQLite Online Backup API
    (sqlite3.Connection.backup). Nunca mediante copia directa de archivos en
    una base activa en modo WAL (Write-Ahead Logging).

FORMATO .bicu.bak:
    Archivo ZIP estándar (zipfile.ZIP_DEFLATED) con estructura interna:
        database.sqlite     — Copia consistente generada vía Online Backup API.
        manifest.json       — Metadatos de auditoría, conteos, versiones, hash.
        signature.sha256    — Hash SHA-256 de database.sqlite para verificación rápida.

INVARIANTES:
    - No modifica la base de datos activa (solo lectura).
    - No modifica matrices patrimoniales (M1–M5).
    - No almacena secretos, credenciales ni claves API.
    - No incluye rutas personales ni datos sensibles del entorno.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import sys
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.backup.domain.models import (
    BackupManifest,
    BackupResult,
)

logger = logging.getLogger("bicu.backup.service")

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

BACKUP_FORMAT_VERSION = "1.0"
SQLITE_HEADER_MAGIC = b"SQLite format 3\x00"
BACKUP_EXTENSION = ".bicu.bak"
SYSTEM_VERSION = "1.1.0"

# Versión máxima de esquema soportada por esta versión del software
MAX_SUPPORTED_SCHEMA_VERSION = 4

# Tablas mínimas obligatorias que debe contener cualquier backup válido
REQUIRED_TABLES_V001 = {
    "schema_version",
    "actividad",
    "planificacion",
    "partida_presupuestaria",
    "diseno_metodologico",
    "persona",
    "perfil_estudiante",
    "perfil_personal",
    "perfil_colaborador",
    "perfil_beneficiario",
    "participacion",
    "evidencia",
    "actividad_evidencia",
    "informe_actividad",
    "informe_semanal",
    "detalle_informe_semanal",
    "discrepancia",
    "salida_institucional",
    "auditoria_evento",
}


class BackupService:
    """Servicio de respaldo institucional SQLite para BICU.

    Genera archivos .bicu.bak autocontenidos, validables y restaurables
    sin dependencia del entorno de desarrollo.

    Uso:
        svc = BackupService(db_path=Path(".../bicu_sistema.db"))
        result = svc.create_backup(destination_dir=Path("..."), system_version="1.1.0")
        if result.success:
            print(f"Backup: {result.backup_path}")
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        system_version: str = SYSTEM_VERSION,
    ) -> None:
        """Inicializa el servicio de backup.

        Args:
            db_path: Ruta a la base de datos activa. Si es None, se utiliza
                     la ruta institucional predeterminada (%LOCALAPPDATA%/BICU_Sistema/data).
            system_version: Versión del software a registrar en el manifiesto.
        """
        if db_path is None:
            from app.infrastructure.persistence.config import get_default_database_path
            db_path = get_default_database_path()
        self._db_path = Path(db_path)
        self._system_version = system_version

    # ------------------------------------------------------------------
    # CREACIÓN DE BACKUP
    # ------------------------------------------------------------------

    def create_backup(
        self,
        destination_dir: Path,
        system_version: Optional[str] = None,
    ) -> BackupResult:
        """Genera un respaldo consistente de la base de datos activa.

        Flujo interno:
            1. Validar que la base activa exista y sea accesible.
            2. Crear copia consistente vía SQLite Online Backup API en tmpdir.
            3. Calcular SHA-256 de la copia temporal.
            4. Recopilar metadatos: tablas, conteos, schema_version.
            5. Construir manifiesto JSON.
            6. Empaquetar en ZIP (.bicu.bak): database.sqlite + manifest.json + signature.sha256.
            7. Verificar el ZIP generado (post-backup integrity check).
            8. Retornar BackupResult.

        Args:
            destination_dir: Directorio de destino para el archivo .bicu.bak.
            system_version: Versión del sistema (override del constructor).

        Returns:
            BackupResult con resultado completo.
        """
        start_ts = time.perf_counter()
        eff_version = system_version or self._system_version
        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        if not self._db_path.exists():
            return BackupResult(
                success=False,
                backup_path=None,
                backup_filename="",
                manifest=None,
                error_message=f"La base de datos activa no existe: {self._db_path}",
                duration_seconds=time.perf_counter() - start_ts,
            )

        with tempfile.TemporaryDirectory(prefix="bicu_backup_") as tmpdir:
            tmp_sqlite = Path(tmpdir) / "database.sqlite"

            # --- PASO 1: Copia consistente vía Online Backup API ---
            try:
                self._online_backup(self._db_path, tmp_sqlite)
            except Exception as exc:
                logger.error("Error en SQLite Online Backup API: %s", exc, exc_info=True)
                return BackupResult(
                    success=False,
                    backup_path=None,
                    backup_filename="",
                    manifest=None,
                    error_message=f"Error generando copia consistente de SQLite: {exc}",
                    duration_seconds=time.perf_counter() - start_ts,
                )

            # --- PASO 2: Calcular SHA-256 del sqlite copiado ---
            try:
                db_sha256 = self._sha256_file(tmp_sqlite)
                db_size = tmp_sqlite.stat().st_size
            except Exception as exc:
                return BackupResult(
                    success=False,
                    backup_path=None,
                    backup_filename="",
                    manifest=None,
                    error_message=f"Error calculando hash del backup SQLite: {exc}",
                    duration_seconds=time.perf_counter() - start_ts,
                )

            # --- PASO 3: Recopilar metadatos de la copia ---
            try:
                table_names, table_row_counts, schema_version, migrations_applied = (
                    self._collect_metadata(tmp_sqlite)
                )
            except Exception as exc:
                logger.error("Error recopilando metadatos del backup: %s", exc, exc_info=True)
                return BackupResult(
                    success=False,
                    backup_path=None,
                    backup_filename="",
                    manifest=None,
                    error_message=f"Error recopilando metadatos del backup: {exc}",
                    duration_seconds=time.perf_counter() - start_ts,
                )

            # --- PASO 4: Construir el manifiesto ---
            backup_id = str(uuid.uuid4())
            now_utc = datetime.now(timezone.utc)
            now_local = datetime.now()

            manifest = BackupManifest(
                backup_id=backup_id,
                backup_format_version=BACKUP_FORMAT_VERSION,
                created_at_utc=now_utc.isoformat(),
                created_at_local=now_local.strftime("%Y-%m-%d %H:%M:%S"),
                system_version=eff_version,
                schema_version=schema_version,
                database_sha256=db_sha256,
                database_size_bytes=db_size,
                table_names=sorted(table_names),
                table_row_counts=table_row_counts,
                schema_migrations_applied=sorted(migrations_applied),
                python_version=sys.version.split()[0],
                platform=sys.platform,
            )

            # --- PASO 5: Construir nombre del archivo ---
            hash6 = db_sha256[:6]
            timestamp_str = now_utc.strftime("%Y%m%d_%H%M%S")
            filename = (
                f"BICU_BACKUP_v{eff_version}_schV{schema_version:03d}"
                f"_{timestamp_str}_{hash6}{BACKUP_EXTENSION}"
            )
            backup_path = destination_dir / filename

            # --- PASO 6: Empaquetar en ZIP ---
            try:
                signature_content = f"SHA256:{db_sha256}\n"
                with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(tmp_sqlite, "database.sqlite")
                    zf.writestr("manifest.json", json.dumps(manifest.to_dict(), indent=2))
                    zf.writestr("signature.sha256", signature_content)
            except Exception as exc:
                logger.error("Error empaquetando backup ZIP: %s", exc, exc_info=True)
                # Intentar limpiar archivo parcial
                if backup_path.exists():
                    try:
                        backup_path.unlink()
                    except Exception:
                        pass
                return BackupResult(
                    success=False,
                    backup_path=None,
                    backup_filename=filename,
                    manifest=None,
                    error_message=f"Error generando archivo .bicu.bak: {exc}",
                    duration_seconds=time.perf_counter() - start_ts,
                )

        # --- PASO 7: Post-verificación del ZIP generado ---
        # La post-verificación estructural NO incluye check de compatibilidad de
        # versión de esquema porque generar un backup de una BD con esquema futuro
        # es una operación válida. La compatibilidad se verifica SOLO en el flujo
        # de restauración (validate_backup llamado con check_schema_compat=True).
        ok, msg = self.validate_backup(backup_path, check_schema_compat=False)
        if not ok:
            logger.error("Post-verificación de backup falló: %s", msg)
            try:
                backup_path.unlink(missing_ok=True)
            except Exception:
                pass
            return BackupResult(
                success=False,
                backup_path=None,
                backup_filename=filename,
                manifest=None,
                error_message=f"Post-verificación del backup falló: {msg}",
                duration_seconds=time.perf_counter() - start_ts,
            )

        logger.info(
            "Backup institucional generado exitosamente: %s (schema v%d, %d tablas, SHA256: %s)",
            filename, schema_version, len(table_names), db_sha256[:12] + "...",
        )

        return BackupResult(
            success=True,
            backup_path=backup_path,
            backup_filename=filename,
            manifest=manifest,
            error_message=None,
            duration_seconds=time.perf_counter() - start_ts,
        )

    # ------------------------------------------------------------------
    # VALIDACIÓN DE BACKUP
    # ------------------------------------------------------------------

    def validate_backup(
        self,
        backup_path: Path,
        check_schema_compat: bool = True,
    ) -> Tuple[bool, str]:
        """Valida un archivo .bicu.bak en múltiples niveles.

        Niveles de validación:
            1. Existencia del archivo.
            2. Integridad del ZIP.
            3. Presencia de database.sqlite, manifest.json y signature.sha256.
            4. SHA-256 del database.sqlite vs. manifest y signature.
            5. Cabecera SQLite (16 bytes mágicos).
            6. PRAGMA integrity_check.
            7. PRAGMA foreign_key_check.
            8. Presencia de schema_version y tablas mínimas.
            9. Compatibilidad de versión de esquema (solo si check_schema_compat=True).

        Args:
            backup_path: Ruta al archivo .bicu.bak.
            check_schema_compat: Si True (predeterminado), verifica que el esquema
                del backup sea compatible con esta versión del software.
                Usar False en la post-verificación de create_backup, ya que
                generar un backup de una BD con esquema futuro es válido.

        Returns:
            Tupla (es_válido, mensaje).
        """
        backup_path = Path(backup_path)

        # 1. Existencia
        if not backup_path.exists():
            return False, f"El archivo no existe: {backup_path}"

        # 2 y 3. Integridad ZIP y contenido mínimo
        try:
            if not zipfile.is_zipfile(backup_path):
                return False, "El archivo no es un ZIP válido."
        except Exception as exc:
            return False, f"Error al verificar el ZIP: {exc}"

        with tempfile.TemporaryDirectory(prefix="bicu_validate_") as tmpdir:
            tmp = Path(tmpdir)
            try:
                with zipfile.ZipFile(backup_path, "r") as zf:
                    names = set(zf.namelist())
                    if "database.sqlite" not in names:
                        return False, "El backup no contiene 'database.sqlite'."
                    if "manifest.json" not in names:
                        return False, "El backup no contiene 'manifest.json'."
                    if "signature.sha256" not in names:
                        return False, "El backup no contiene 'signature.sha256'."
                    zf.extractall(tmp)
            except zipfile.BadZipFile as exc:
                return False, f"ZIP corrupto: {exc}"
            except Exception as exc:
                return False, f"Error extrayendo el backup: {exc}"

            db_file = tmp / "database.sqlite"
            manifest_file = tmp / "manifest.json"
            sig_file = tmp / "signature.sha256"

            # 4. Hash SHA-256
            try:
                actual_hash = self._sha256_file(db_file)
            except Exception as exc:
                return False, f"Error calculando hash: {exc}"

            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                manifest = BackupManifest.from_dict(manifest_data)
            except Exception as exc:
                return False, f"manifest.json inválido: {exc}"

            try:
                sig_content = sig_file.read_text(encoding="utf-8").strip()
                # Formato: "SHA256:<hash>"
                if ":" in sig_content:
                    sig_hash = sig_content.split(":", 1)[1].strip()
                else:
                    sig_hash = sig_content
            except Exception as exc:
                return False, f"signature.sha256 inválido: {exc}"

            if actual_hash != manifest.database_sha256:
                return (
                    False,
                    f"Hash SHA-256 no coincide con el manifiesto. "
                    f"Esperado: {manifest.database_sha256[:12]}... "
                    f"Real: {actual_hash[:12]}...",
                )

            if actual_hash != sig_hash:
                return (
                    False,
                    f"Hash SHA-256 no coincide con signature.sha256. "
                    f"Archivo puede haber sido alterado.",
                )

            # 5. Cabecera SQLite
            try:
                header = db_file.read_bytes()[:16]
                if header != SQLITE_HEADER_MAGIC:
                    return False, "El archivo database.sqlite no tiene cabecera SQLite válida."
            except Exception as exc:
                return False, f"Error leyendo cabecera SQLite: {exc}"

            # 6. integrity_check y 7. foreign_key_check
            try:
                conn = sqlite3.connect(str(db_file))
                try:
                    conn.execute("PRAGMA foreign_keys = ON;")

                    cur = conn.execute("PRAGMA integrity_check;")
                    ic_result = cur.fetchone()
                    if ic_result is None or ic_result[0] != "ok":
                        return (
                            False,
                            f"PRAGMA integrity_check falló: {ic_result}",
                        )

                    cur = conn.execute("PRAGMA foreign_key_check;")
                    fk_violations = cur.fetchall()
                    if fk_violations:
                        return (
                            False,
                            f"PRAGMA foreign_key_check encontró {len(fk_violations)} violación(es).",
                        )

                    # 8. Tablas mínimas
                    cur = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
                    )
                    tables_in_backup = {row[0] for row in cur.fetchall()}
                    missing = REQUIRED_TABLES_V001 - tables_in_backup
                    if missing:
                        return (
                            False,
                            f"Tablas obligatorias faltantes en el backup: {sorted(missing)}",
                        )

                    # 9. Compatibilidad de versión de esquema (solo si se solicitó)
                    if check_schema_compat and "schema_version" in tables_in_backup:
                        cur = conn.execute(
                            "SELECT MAX(version) FROM schema_version;"
                        )
                        row = cur.fetchone()
                        if row and row[0] is not None:
                            sv = int(row[0])
                            if sv > MAX_SUPPORTED_SCHEMA_VERSION:
                                return (
                                    False,
                                    f"El backup requiere esquema v{sv}, pero esta versión del "
                                    f"software soporta hasta v{MAX_SUPPORTED_SCHEMA_VERSION}. "
                                    f"Actualice el software antes de restaurar.",
                                )
                finally:
                    conn.close()
            except sqlite3.Error as exc:
                return False, f"Error de SQLite al validar el backup: {exc}"

        return True, "Backup válido y verificado correctamente."

    # ------------------------------------------------------------------
    # HELPERS INTERNOS
    # ------------------------------------------------------------------

    @staticmethod
    def _online_backup(source_path: Path, dest_path: Path) -> None:
        """Realiza una copia consistente de SQLite usando la Online Backup API.

        Esta API garantiza que la copia incluya todas las transacciones WAL
        pendientes y produce un archivo autocontenido, estable y sin locks
        sobre la base original.

        Args:
            source_path: Ruta a la base de datos SQLite activa.
            dest_path: Ruta de destino para la copia consistente.
        """
        source_conn = sqlite3.connect(str(source_path))
        dest_conn = sqlite3.connect(str(dest_path))
        try:
            # Checkpoint pasivo para intentar volcar páginas WAL a la base principal
            source_conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
            # Backup incremental en páginas de 200 (apropiado para bases < 100 MB)
            source_conn.backup(dest_conn, pages=200, sleep=0.005)
        finally:
            dest_conn.close()
            source_conn.close()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Calcula el hash SHA-256 de un archivo en bloques de 64 KB."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _collect_metadata(
        db_path: Path,
    ) -> Tuple[List[str], Dict[str, int], int, List[int]]:
        """Recopila metadatos de la base de datos copiada.

        Returns:
            Tupla: (table_names, table_row_counts, schema_version, migrations_applied)
        """
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            table_names = [row[0] for row in cur.fetchall()]

            row_counts: Dict[str, int] = {}
            for t in table_names:
                if not t.startswith("sqlite_"):
                    try:
                        cnt = conn.execute(f"SELECT COUNT(*) FROM \"{t}\";").fetchone()[0]
                        row_counts[t] = int(cnt)
                    except Exception:
                        row_counts[t] = -1

            # schema_version
            schema_ver = 0
            migrations: List[int] = []
            if "schema_version" in table_names:
                try:
                    cur = conn.execute("SELECT version FROM schema_version ORDER BY version;")
                    migrations = [int(row[0]) for row in cur.fetchall()]
                    schema_ver = max(migrations) if migrations else 0
                except Exception:
                    pass

            return table_names, row_counts, schema_ver, migrations
        finally:
            conn.close()
