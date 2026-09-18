"""Mecanismo de Migraciones Versionadas de Esquema - Sistema Institucional BICU.

Fase 25 (Etapa 25.2): Schema, SCHEMA_VERSION y Migración Inicial.
Proporciona el ejecutor determinista y transaccional de migraciones DDL,
registrando cada cambio en la tabla técnica schema_version con hash SHA-256
y verificación pericial de integridad.
"""

import time
import hashlib
import sqlite3
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict, Any, Set

from app.infrastructure.persistence.schema import (
    SCHEMA_VERSION_TABLE_DDL,
    INITIAL_SCHEMA_DDL_STATEMENTS,
    INITIAL_INDEXES_DDL_STATEMENTS,
    EXPECTED_TABLE_NAMES,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Migration:
    """Definición inmutable de una migración de esquema versionada."""

    version: int
    name: str
    statements: List[str]

    def compute_hash(self) -> str:
        """Calcula el hash SHA-256 inmutable de las sentencias DDL de la migración."""
        hasher = hashlib.sha256()
        for stmt in self.statements:
            hasher.update(stmt.strip().encode("utf-8"))
        return hasher.hexdigest()


# ---------------------------------------------------------------------------
# REGISTRO GLOBAL DE MIGRACIONES
# ---------------------------------------------------------------------------
MIGRATION_V001 = Migration(
    version=1,
    name="v001_initial_schema_18_tables",
    statements=INITIAL_SCHEMA_DDL_STATEMENTS + INITIAL_INDEXES_DDL_STATEMENTS,
)

MIGRATION_REGISTRY: List[Migration] = [
    MIGRATION_V001,
]


class MigrationRunner:
    """Ejecutor transaccional y determinista de migraciones DDL."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def ensure_schema_version_table(self) -> None:
        """Crea la tabla técnica schema_version si no existe."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(SCHEMA_VERSION_TABLE_DDL)
        finally:
            cursor.close()

    def get_applied_versions(self) -> Dict[int, Dict[str, Any]]:
        """Obtiene el historial de versiones de esquema aplicadas en la base de datos."""
        self.ensure_schema_version_table()
        cursor = self.conn.cursor()
        applied = {}
        try:
            cursor.execute(
                "SELECT version, nombre_migracion, hash_script, fecha_aplicacion, tiempo_ejecucion_ms "
                "FROM schema_version ORDER BY version ASC;"
            )
            for row in cursor.fetchall():
                applied[int(row[0])] = {
                    "version": int(row[0]),
                    "nombre_migracion": str(row[1]),
                    "hash_script": str(row[2]),
                    "fecha_aplicacion": str(row[3]),
                    "tiempo_ejecucion_ms": int(row[4]),
                }
        finally:
            cursor.close()
        return applied

    def get_current_version(self) -> int:
        """Retorna el número de versión actual aplicada (0 si ninguna)."""
        applied = self.get_applied_versions()
        return max(applied.keys()) if applied else 0

    def apply_migration(self, migration: Migration) -> Dict[str, Any]:
        """Aplica una migración específica dentro de una transacción segura.

        Si la migración ya fue aplicada previamente, no la re-ejecuta (idempotente).
        Si falla cualquier sentencia, ejecuta ROLLBACK automático.
        """
        self.ensure_schema_version_table()
        applied = self.get_applied_versions()

        if migration.version in applied:
            logger.info(f"Migración {migration.version} ({migration.name}) ya aplicada. Omitiendo.")
            return {
                "version": migration.version,
                "name": migration.name,
                "status": "ALREADY_APPLIED",
                "execution_ms": applied[migration.version]["tiempo_ejecucion_ms"],
            }

        start_time = time.perf_counter()
        migration_hash = migration.compute_hash()
        now_iso = datetime.now(timezone.utc).isoformat()

        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE;")
            # Ejecutar cada sentencia DDL de la migración
            for stmt in migration.statements:
                clean_stmt = stmt.strip()
                if clean_stmt:
                    cursor.execute(clean_stmt)

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # Registrar en la tabla schema_version
            cursor.execute(
                "INSERT INTO schema_version (version, nombre_migracion, hash_script, fecha_aplicacion, tiempo_ejecucion_ms) "
                "VALUES (?, ?, ?, ?, ?);",
                (migration.version, migration.name, migration_hash, now_iso, elapsed_ms),
            )
            cursor.execute("COMMIT;")
        except Exception as e:
            cursor.execute("ROLLBACK;")
            logger.error(f"Error crítico al aplicar migración {migration.version} ({migration.name}): {e}")
            raise
        finally:
            cursor.close()

        return {
            "version": migration.version,
            "name": migration.name,
            "status": "APPLIED_SUCCESSFULLY",
            "hash": migration_hash,
            "applied_at": now_iso,
            "execution_ms": elapsed_ms,
        }

    def apply_all_pending(self) -> List[Dict[str, Any]]:
        """Aplica todas las migraciones registradas que aún no hayan sido ejecutadas."""
        results = []
        for migration in MIGRATION_REGISTRY:
            result = self.apply_migration(migration)
            results.append(result)
        return results

    def verify_integrity(self) -> str:
        """Ejecuta PRAGMA integrity_check sobre la base de datos y retorna el resultado."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("PRAGMA integrity_check;")
            row = cursor.fetchone()
            return str(row[0]) if row else "failed"
        finally:
            cursor.close()

    def get_existing_tables(self) -> Set[str]:
        """Obtiene el conjunto de tablas existentes en la base de datos (excluyendo sqlite_*)."""
        cursor = self.conn.cursor()
        tables = set()
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            for row in cursor.fetchall():
                tables.add(str(row[0]).lower())
        finally:
            cursor.close()
        return tables
