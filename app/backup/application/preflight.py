"""app.backup.application.preflight

Verificador de pre-vuelo institucional del sistema BICU.

Fase 29.24.1 — Consolidación Operativa.

El preflight es una verificación NON-DESTRUCTIVA ejecutada antes de que la
aplicación inicie operaciones. Detecta condiciones que podrían comprometer
la integridad institucional de los datos sin aplicar correcciones silenciosas.

VERIFICACIONES IMPLEMENTADAS (en orden de ejecución):
    1. RUTA DE BASE DE DATOS
       - La base activa no está en OneDrive.
       - La base activa está en el directorio local institucional.

    2. BASE DE DATOS
       - El archivo de BD existe y es accesible.
       - La cabecera SQLite es válida (16 bytes mágicos).
       - PRAGMA integrity_check pasa.
       - PRAGMA foreign_key_check pasa.

    3. ESQUEMA
       - La tabla schema_version existe.
       - La versión de esquema es soportada por esta versión del software.
       - No hay migraciones pendientes (o se registra como WARNING).

    4. REGISTROS PATRIMONIALES
       - Los 32 registros históricos de Matriz_5 están protegidos.

    5. ENTORNO
       - Python >= 3.9.
       - Módulo sqlite3 disponible con versión de SQLite >= 3.35 (para INSERT OR IGNORE seguro).

POLÍTICA DE SEVERIDAD:
    - READY: Todo OK.
    - WARNING: Condición no crítica (ej. sin migraciones pendientes, Python compatible pero antiguo).
    - FATAL: La aplicación no debe iniciar operaciones institucionales.

USO:
    checker = ReleasePreflightChecker()
    report = checker.run_all()
    if report.is_fatal:
        for line in report.summary_lines():
            print(line)
        sys.exit(1)
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.backup.domain.models import (
    PreflightCheck,
    PreflightReport,
    PreflightStatus,
)

logger = logging.getLogger("bicu.preflight")

# Versión mínima de SQLite para funcionalidades requeridas
SQLITE_MIN_VERSION = (3, 35, 0)

# Versión mínima de Python soportada
PYTHON_MIN_VERSION = (3, 9)

# Versión máxima de esquema soportada (sincronizada con backup_service.py)
MAX_SUPPORTED_SCHEMA_VERSION = 4

# Número esperado de registros históricos de Matriz_5
M5_HISTORICO_EXPECTED_COUNT = 32


class ReleasePreflightChecker:
    """Verificador de pre-vuelo institucional — solo lectura, sin correcciones.

    Ejecuta una batería de verificaciones antes del inicio de operaciones
    y devuelve un informe estructurado que la UI puede presentar al operador.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Inicializa el preflight con la ruta de la base de datos activa.

        Args:
            db_path: Ruta a la BD activa. Si es None, usa la ruta institucional.
        """
        if db_path is None:
            from app.infrastructure.persistence.config import get_default_database_path
            db_path = get_default_database_path()
        self._db_path = Path(db_path)

    def run_all(self) -> PreflightReport:
        """Ejecuta todas las verificaciones de pre-vuelo.

        Siempre ejecuta todas las verificaciones incluso si alguna falla,
        para dar al operador la imagen completa del estado del sistema.

        Returns:
            PreflightReport con todos los checks y el estado global.
        """
        checks: List[PreflightCheck] = []

        # Grupo 1: Ruta de base de datos
        checks.append(self._check_not_onedrive())
        checks.append(self._check_local_path())

        # Grupo 2: Acceso y estructura de la BD
        db_accessible = checks[-1].status != PreflightStatus.FATAL
        # Solo verificar SQLite si la ruta es local y accesible
        if self._db_path.exists():
            checks.append(self._check_sqlite_header())
            checks.append(self._check_integrity())
            checks.append(self._check_foreign_keys())

            # Grupo 3: Esquema
            checks.append(self._check_schema_version_table())
            checks.append(self._check_schema_version_compatible())
            checks.append(self._check_no_pending_migrations())

            # Grupo 4: Registros patrimoniales
            checks.append(self._check_m5_historical_records())
        else:
            checks.append(PreflightCheck(
                name="Base de datos",
                status=PreflightStatus.WARNING,
                message=(
                    "La base de datos no existe aún en la ruta configurada. "
                    "Se creará automáticamente al iniciar la aplicación."
                ),
            ))

        # Grupo 5: Entorno
        checks.append(self._check_python_version())
        checks.append(self._check_sqlite_module_version())

        # Determinar estado global (el más severo)
        all_statuses = [c.status for c in checks]
        if PreflightStatus.FATAL in all_statuses:
            overall = PreflightStatus.FATAL
        elif PreflightStatus.WARNING in all_statuses:
            overall = PreflightStatus.WARNING
        else:
            overall = PreflightStatus.READY

        return PreflightReport(
            checks=checks,
            overall_status=overall,
            checked_at_utc=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # GRUPO 1: RUTA
    # ------------------------------------------------------------------

    def _check_not_onedrive(self) -> PreflightCheck:
        name = "Aislamiento OneDrive"
        try:
            from app.infrastructure.persistence.config import is_onedrive_path
            if is_onedrive_path(self._db_path):
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.FATAL,
                    message=(
                        "La base de datos activa se encuentra dentro de OneDrive. "
                        "Esto es incompatible con SQLite WAL y puede corromper los datos."
                    ),
                    detail=str(self._db_path),
                )
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=f"No se pudo verificar la ruta OneDrive: {exc}",
            )
        return PreflightCheck(
            name=name,
            status=PreflightStatus.READY,
            message="La base de datos no está en OneDrive.",
        )

    def _check_local_path(self) -> PreflightCheck:
        name = "Ruta local institucional"
        try:
            from app.infrastructure.persistence.config import get_default_database_path
            expected = get_default_database_path()
            if self._db_path.resolve() == expected.resolve():
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.READY,
                    message=f"Base de datos en ruta institucional correcta.",
                    detail=str(self._db_path),
                )
            else:
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.WARNING,
                    message=(
                        f"La base de datos no está en la ruta institucional predeterminada. "
                        f"Ruta configurada: {self._db_path}. "
                        f"Ruta institucional: {expected}"
                    ),
                )
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=f"No se pudo verificar la ruta institucional: {exc}",
            )

    # ------------------------------------------------------------------
    # GRUPO 2: SQLITE
    # ------------------------------------------------------------------

    def _check_sqlite_header(self) -> PreflightCheck:
        name = "Cabecera SQLite"
        SQLITE_MAGIC = b"SQLite format 3\x00"
        try:
            with open(self._db_path, "rb") as f:
                header = f.read(16)
            if header == SQLITE_MAGIC:
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.READY,
                    message="Cabecera SQLite válida.",
                )
            else:
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.FATAL,
                    message=(
                        "El archivo de base de datos no tiene una cabecera SQLite válida. "
                        "Puede estar corrupto o ser de formato diferente."
                    ),
                    detail=f"Header: {header.hex()}",
                )
        except PermissionError:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.FATAL,
                message="Sin permiso de lectura sobre el archivo de base de datos.",
            )
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.FATAL,
                message=f"Error leyendo cabecera del archivo: {exc}",
            )

    def _check_integrity(self) -> PreflightCheck:
        name = "Integridad SQLite (integrity_check)"
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=8.0)
            try:
                result = conn.execute("PRAGMA integrity_check;").fetchone()
                if result and result[0] == "ok":
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.READY,
                        message="PRAGMA integrity_check: ok.",
                    )
                else:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.FATAL,
                        message=f"PRAGMA integrity_check falló: {result}",
                    )
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.WARNING,
                    message=f"Base de datos bloqueada temporalmente (puede estar en uso): {exc}",
                )
            return PreflightCheck(
                name=name,
                status=PreflightStatus.FATAL,
                message=f"Error de SQLite al verificar integridad: {exc}",
            )
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.FATAL,
                message=f"Error verificando integridad: {exc}",
            )

    def _check_foreign_keys(self) -> PreflightCheck:
        name = "Integridad referencial (foreign_key_check)"
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=8.0)
            try:
                conn.execute("PRAGMA foreign_keys = ON;")
                violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
                if not violations:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.READY,
                        message="PRAGMA foreign_key_check: sin violaciones.",
                    )
                else:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.WARNING,
                        message=f"PRAGMA foreign_key_check detectó {len(violations)} violación(es) referencial(es).",
                        detail=str(violations[:5]),
                    )
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.WARNING,
                    message=f"Base de datos bloqueada temporalmente al verificar FK: {exc}",
                )
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=f"Error de SQLite verificando FK: {exc}",
            )
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=f"Error verificando FK: {exc}",
            )

    # ------------------------------------------------------------------
    # GRUPO 3: ESQUEMA
    # ------------------------------------------------------------------

    def _check_schema_version_table(self) -> PreflightCheck:
        name = "Tabla schema_version"
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=8.0)
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';"
                ).fetchone()
                if row:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.READY,
                        message="La tabla schema_version existe.",
                    )
                else:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.FATAL,
                        message=(
                            "La tabla schema_version no existe. "
                            "La base de datos puede estar incompleta o sin inicializar."
                        ),
                    )
            finally:
                conn.close()
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.FATAL,
                message=f"Error verificando schema_version: {exc}",
            )

    def _check_schema_version_compatible(self) -> PreflightCheck:
        name = "Versión de esquema compatible"
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=8.0)
            try:
                row = conn.execute("SELECT MAX(version) FROM schema_version;").fetchone()
                if row is None or row[0] is None:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.WARNING,
                        message="No hay versiones registradas en schema_version.",
                    )
                current = int(row[0])
                if current > MAX_SUPPORTED_SCHEMA_VERSION:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.FATAL,
                        message=(
                            f"La base de datos requiere esquema v{current}, "
                            f"pero esta versión del software soporta hasta v{MAX_SUPPORTED_SCHEMA_VERSION}. "
                            f"Actualice el software."
                        ),
                    )
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.READY,
                    message=f"Esquema v{current} — compatible (máximo soportado: v{MAX_SUPPORTED_SCHEMA_VERSION}).",
                )
            finally:
                conn.close()
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=f"Error verificando versión de esquema: {exc}",
            )

    def _check_no_pending_migrations(self) -> PreflightCheck:
        name = "Migraciones pendientes"
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=8.0)
            try:
                row = conn.execute("SELECT MAX(version) FROM schema_version;").fetchone()
                current = int(row[0]) if row and row[0] is not None else 0
            finally:
                conn.close()

            if current < MAX_SUPPORTED_SCHEMA_VERSION:
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.WARNING,
                    message=(
                        f"Hay migraciones pendientes: esquema actual v{current}, "
                        f"versión esperada v{MAX_SUPPORTED_SCHEMA_VERSION}. "
                        f"Se aplicarán automáticamente al iniciar."
                    ),
                )
            return PreflightCheck(
                name=name,
                status=PreflightStatus.READY,
                message=f"Sin migraciones pendientes (esquema en v{current}).",
            )
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=f"No se pudo verificar migraciones pendientes: {exc}",
            )

    # ------------------------------------------------------------------
    # GRUPO 4: PATRIMONIAL
    # ------------------------------------------------------------------

    def _check_m5_historical_records(self) -> PreflightCheck:
        name = "Registros históricos Matriz_5"
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=8.0)
            try:
                # Verificar si la tabla participacion existe (los 32 registros históricos de Matriz_5 residen en participacion)
                table_row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='participacion';"
                ).fetchone()
                if not table_row:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.WARNING,
                        message=(
                            "La tabla participacion no existe aún. "
                            "Se creará con las migraciones iniciales."
                        ),
                    )

                row = conn.execute(
                    "SELECT COUNT(*) FROM participacion WHERE es_historico_preexistente = 1;"
                ).fetchone()
                count = int(row[0]) if row else 0

                if count == M5_HISTORICO_EXPECTED_COUNT:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.READY,
                        message=f"{count}/{M5_HISTORICO_EXPECTED_COUNT} registros históricos de Matriz_5 protegidos.",
                    )
                elif count == 0:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.WARNING,
                        message=(
                            f"No se encontraron registros históricos de Matriz_5 (esperados: {M5_HISTORICO_EXPECTED_COUNT}). "
                            f"Pueden no haberse cargado aún o requerir migración."
                        ),
                    )
                elif count < M5_HISTORICO_EXPECTED_COUNT:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.WARNING,
                        message=(
                            f"Solo se encontraron {count}/{M5_HISTORICO_EXPECTED_COUNT} "
                            f"registros históricos de Matriz_5. "
                            f"Posible carga parcial o corrupción."
                        ),
                        detail=f"Encontrados: {count}, Esperados: {M5_HISTORICO_EXPECTED_COUNT}",
                    )
                else:
                    return PreflightCheck(
                        name=name,
                        status=PreflightStatus.WARNING,
                        message=(
                            f"Se encontraron más registros históricos de los esperados: "
                            f"{count} (esperados: {M5_HISTORICO_EXPECTED_COUNT}). Revisar."
                        ),
                    )
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            if "no such column" in str(exc).lower():
                return PreflightCheck(
                    name=name,
                    status=PreflightStatus.WARNING,
                    message=(
                        "La columna es_historico_preexistente no existe aún. "
                        "Se creará con las migraciones de V002+."
                    ),
                )
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=f"Error verificando registros históricos M5: {exc}",
            )
        except Exception as exc:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=f"Error verificando registros históricos M5: {exc}",
            )

    # ------------------------------------------------------------------
    # GRUPO 5: ENTORNO
    # ------------------------------------------------------------------

    def _check_python_version(self) -> PreflightCheck:
        name = "Versión de Python"
        major, minor = sys.version_info[:2]
        min_major, min_minor = PYTHON_MIN_VERSION
        if (major, minor) >= (min_major, min_minor):
            return PreflightCheck(
                name=name,
                status=PreflightStatus.READY,
                message=f"Python {major}.{minor} — compatible (mínimo requerido: {min_major}.{min_minor}).",
            )
        else:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.FATAL,
                message=(
                    f"Python {major}.{minor} no es soportado. "
                    f"Se requiere Python {min_major}.{min_minor} o superior."
                ),
            )

    def _check_sqlite_module_version(self) -> PreflightCheck:
        name = "Versión de SQLite"
        sqlite_ver_str = sqlite3.sqlite_version
        try:
            parts = tuple(int(x) for x in sqlite_ver_str.split(".")[:3])
        except Exception:
            parts = (0, 0, 0)

        min_v = SQLITE_MIN_VERSION
        if parts >= min_v:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.READY,
                message=(
                    f"SQLite {sqlite_ver_str} — compatible "
                    f"(mínimo requerido: {'.'.join(str(x) for x in min_v)})."
                ),
            )
        else:
            return PreflightCheck(
                name=name,
                status=PreflightStatus.WARNING,
                message=(
                    f"SQLite {sqlite_ver_str} es inferior al mínimo recomendado "
                    f"{'.'.join(str(x) for x in min_v)}. Actualice si experimenta problemas."
                ),
            )
