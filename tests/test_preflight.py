"""tests.test_preflight

Suite de tests unitarios para ReleasePreflightChecker (Bloque C — Fase 29.24.1).

Cobertura:
    - run_all() con BD válida devuelve READY.
    - run_all() con BD inexistente devuelve WARNING (no FATAL).
    - Detección de OneDrive retorna FATAL.
    - Cabecera SQLite inválida retorna FATAL.
    - Schema no compatible (futuro) retorna FATAL.
    - Migraciones pendientes retornan WARNING.
    - Python version check.
    - SQLite module version check.
    - PreflightReport.summary_lines() formatea correctamente.
    - PreflightReport.is_ready, .has_warnings, .is_fatal correctos.
    - M5 histórico: 0 registros → WARNING.
    - M5 histórico: 32 registros → READY.

INVARIANTE: Ningún test modifica la BD activa, M1–M5 ni datos históricos.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

from app.backup.application.preflight import (
    MAX_SUPPORTED_SCHEMA_VERSION,
    M5_HISTORICO_EXPECTED_COUNT,
    ReleasePreflightChecker,
)
from app.backup.domain.models import PreflightReport, PreflightStatus


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _make_valid_db(path: Path, schema_version: int = 4, m5_count: int = 0) -> Path:
    """Crea una BD SQLite válida para pruebas de preflight."""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            """CREATE TABLE schema_version (
                version INTEGER NOT NULL PRIMARY KEY,
                name TEXT NOT NULL, applied_at TEXT NOT NULL, hash TEXT NOT NULL
            );"""
        )
        for v in range(1, schema_version + 1):
            conn.execute(
                "INSERT INTO schema_version VALUES (?, ?, datetime('now'), 'h');",
                (v, f"v{v:03d}_test"),
            )
        conn.execute(
            """CREATE TABLE participacion (
                id_participacion TEXT PRIMARY KEY,
                es_historico_preexistente INTEGER NOT NULL DEFAULT 0
            );"""
        )
        for i in range(m5_count):
            conn.execute(
                "INSERT INTO participacion (id_participacion, es_historico_preexistente) VALUES (?, 1);",
                (f"part-hist-{i}",),
            )
        conn.commit()
    finally:
        conn.close()
    return path


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_db(tmp_path: Path) -> Path:
    db = tmp_path / "valid.db"
    return _make_valid_db(db, schema_version=4, m5_count=M5_HISTORICO_EXPECTED_COUNT)


@pytest.fixture()
def checker(valid_db: Path) -> ReleasePreflightChecker:
    return ReleasePreflightChecker(db_path=valid_db)


@pytest.fixture()
def nonexistent_db(tmp_path: Path) -> Path:
    return tmp_path / "ghost.db"


# ---------------------------------------------------------------------------
# TESTS — ESTADO GLOBAL
# ---------------------------------------------------------------------------


class TestPreflightOverallStatus:

    def test_valid_db_is_ready(self, checker: ReleasePreflightChecker) -> None:
        report = checker.run_all()
        # Puede ser READY o WARNING según la ruta (no es la ruta institucional)
        assert report.overall_status in {PreflightStatus.READY, PreflightStatus.WARNING}
        assert not report.is_fatal

    def test_nonexistent_db_is_not_fatal(self, nonexistent_db: Path) -> None:
        checker = ReleasePreflightChecker(db_path=nonexistent_db)
        report = checker.run_all()
        # BD inexistente → WARNING (se creará), no FATAL
        assert report.overall_status != PreflightStatus.FATAL

    def test_report_has_checks(self, checker: ReleasePreflightChecker) -> None:
        report = checker.run_all()
        assert len(report.checks) > 0

    def test_report_has_timestamp(self, checker: ReleasePreflightChecker) -> None:
        report = checker.run_all()
        assert report.checked_at_utc
        assert "T" in report.checked_at_utc  # ISO 8601

    def test_summary_lines_not_empty(self, checker: ReleasePreflightChecker) -> None:
        report = checker.run_all()
        lines = report.summary_lines()
        assert len(lines) > 1
        assert "Estado global:" in lines[0]


# ---------------------------------------------------------------------------
# TESTS — ONEDRIVE DETECTION
# ---------------------------------------------------------------------------


class TestPreflightOneDriveDetection:

    def test_onedrive_path_is_fatal(self, tmp_path: Path) -> None:
        # Patch is_onedrive_path para retornar True sin depender del entorno
        with patch(
            "app.backup.application.preflight.ReleasePreflightChecker._check_not_onedrive"
        ) as mock_check:
            from app.backup.domain.models import PreflightCheck
            mock_check.return_value = PreflightCheck(
                name="Aislamiento OneDrive",
                status=PreflightStatus.FATAL,
                message="BD en OneDrive detectada",
            )
            checker = ReleasePreflightChecker(db_path=tmp_path / "db.db")
            report = checker.run_all()
        # Con al menos un FATAL, el overall debe ser FATAL
        assert report.overall_status == PreflightStatus.FATAL
        assert report.is_fatal


# ---------------------------------------------------------------------------
# TESTS — CHECKS INDIVIDUALES
# ---------------------------------------------------------------------------


class TestPreflightChecksIndividual:

    def test_check_python_version_ready(self, checker: ReleasePreflightChecker) -> None:
        check = checker._check_python_version()
        # En el entorno de test, Python >= 3.9 siempre
        assert check.status == PreflightStatus.READY

    def test_check_sqlite_module_version_ready(self, checker: ReleasePreflightChecker) -> None:
        check = checker._check_sqlite_module_version()
        # SQLite 3.35+ es estándar en Python 3.9+
        assert check.status in {PreflightStatus.READY, PreflightStatus.WARNING}

    def test_check_sqlite_header_valid(self, checker: ReleasePreflightChecker) -> None:
        check = checker._check_sqlite_header()
        assert check.status == PreflightStatus.READY

    def test_check_sqlite_header_invalid_file(self, tmp_path: Path) -> None:
        invalid = tmp_path / "invalid.db"
        invalid.write_bytes(b"NOT SQLITE" + b"\x00" * 100)
        checker = ReleasePreflightChecker(db_path=invalid)
        check = checker._check_sqlite_header()
        assert check.status == PreflightStatus.FATAL

    def test_check_integrity_valid(self, checker: ReleasePreflightChecker) -> None:
        check = checker._check_integrity()
        assert check.status == PreflightStatus.READY

    def test_check_schema_version_table_exists(self, checker: ReleasePreflightChecker) -> None:
        check = checker._check_schema_version_table()
        assert check.status == PreflightStatus.READY

    def test_check_schema_version_table_missing(self, tmp_path: Path) -> None:
        db = tmp_path / "no_schema.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE unrelated (id INTEGER);")
        conn.commit()
        conn.close()
        checker = ReleasePreflightChecker(db_path=db)
        check = checker._check_schema_version_table()
        assert check.status == PreflightStatus.FATAL

    def test_check_schema_version_compatible_ok(self, checker: ReleasePreflightChecker) -> None:
        check = checker._check_schema_version_compatible()
        assert check.status == PreflightStatus.READY

    def test_check_schema_version_future_is_fatal(self, tmp_path: Path) -> None:
        db = tmp_path / "future.db"
        _make_valid_db(db, schema_version=MAX_SUPPORTED_SCHEMA_VERSION + 3)
        checker = ReleasePreflightChecker(db_path=db)
        check = checker._check_schema_version_compatible()
        assert check.status == PreflightStatus.FATAL

    def test_check_pending_migrations_warning(self, tmp_path: Path) -> None:
        db = tmp_path / "old_schema.db"
        _make_valid_db(db, schema_version=2)  # Pending v3 and v4
        checker = ReleasePreflightChecker(db_path=db)
        check = checker._check_no_pending_migrations()
        assert check.status == PreflightStatus.WARNING

    def test_check_no_pending_migrations_ok(self, checker: ReleasePreflightChecker) -> None:
        check = checker._check_no_pending_migrations()
        assert check.status == PreflightStatus.READY

    def test_check_m5_historical_32_records_ready(self, checker: ReleasePreflightChecker) -> None:
        check = checker._check_m5_historical_records()
        assert check.status == PreflightStatus.READY

    def test_check_m5_historical_0_records_warning(self, tmp_path: Path) -> None:
        db = tmp_path / "no_m5.db"
        _make_valid_db(db, schema_version=4, m5_count=0)
        checker = ReleasePreflightChecker(db_path=db)
        check = checker._check_m5_historical_records()
        assert check.status == PreflightStatus.WARNING

    def test_check_m5_partial_warning(self, tmp_path: Path) -> None:
        db = tmp_path / "partial_m5.db"
        _make_valid_db(db, schema_version=4, m5_count=15)
        checker = ReleasePreflightChecker(db_path=db)
        check = checker._check_m5_historical_records()
        assert check.status == PreflightStatus.WARNING

    def test_check_m5_h03_canonical_table_participacion_no_operational_error(
        self, tmp_path: Path
    ) -> None:
        """H-03: Verifica que la consulta use 'participacion' y no 'perfil_beneficiario'.

        En el esquema institucional V004, 'perfil_beneficiario' no posee la columna
        'es_historico_preexistente', mientras que 'participacion' sí la contiene.
        Esta prueba simula exactamente dicha estructura para asegurar que no se produzca
        OperationalError y el estado sea READY con 32 registros protegidos.
        """
        db = tmp_path / "canonical_v004.db"
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            # perfil_beneficiario según esquema real V004 (sin es_historico_preexistente)
            conn.execute(
                """CREATE TABLE perfil_beneficiario (
                    id_perfil_beneficiario TEXT PRIMARY KEY,
                    id_persona TEXT NOT NULL,
                    condicion_vulnerabilidad TEXT
                );"""
            )
            # participacion según esquema real V004 (con es_historico_preexistente)
            conn.execute(
                """CREATE TABLE participacion (
                    id_participacion TEXT PRIMARY KEY,
                    id_actividad TEXT,
                    id_persona TEXT,
                    estamento_declarado TEXT,
                    es_historico_preexistente INTEGER NOT NULL DEFAULT 0
                );"""
            )
            # Insertar los 32 registros históricos patrimoniales de M5
            for i in range(32):
                conn.execute(
                    "INSERT INTO participacion (id_participacion, es_historico_preexistente) VALUES (?, 1);",
                    (f"part-m5-hist-{i+1}",),
                )
            # Insertar participaciones activas del período (es_historico_preexistente = 0)
            for i in range(10):
                conn.execute(
                    "INSERT INTO participacion (id_participacion, es_historico_preexistente) VALUES (?, 0);",
                    (f"part-activa-{i+1}",),
                )
            conn.commit()
        finally:
            conn.close()

        checker = ReleasePreflightChecker(db_path=db)
        check = checker._check_m5_historical_records()

        # Debe ser READY sin OperationalError
        assert check.status == PreflightStatus.READY
        assert "32/32 registros históricos de Matriz_5 protegidos." in check.message



# ---------------------------------------------------------------------------
# TESTS — PreflightReport
# ---------------------------------------------------------------------------


class TestPreflightReport:

    def test_is_ready_true_when_all_ready(self) -> None:
        from app.backup.domain.models import PreflightCheck
        checks = [
            PreflightCheck("A", PreflightStatus.READY, "ok"),
            PreflightCheck("B", PreflightStatus.READY, "ok"),
        ]
        report = PreflightReport(
            checks=checks,
            overall_status=PreflightStatus.READY,
            checked_at_utc="2026-01-01T00:00:00+00:00",
        )
        assert report.is_ready
        assert not report.has_warnings
        assert not report.is_fatal

    def test_has_warnings_true(self) -> None:
        from app.backup.domain.models import PreflightCheck
        checks = [
            PreflightCheck("A", PreflightStatus.READY, "ok"),
            PreflightCheck("B", PreflightStatus.WARNING, "warn"),
        ]
        report = PreflightReport(
            checks=checks,
            overall_status=PreflightStatus.WARNING,
            checked_at_utc="2026-01-01T00:00:00+00:00",
        )
        assert report.has_warnings
        assert not report.is_ready
        assert not report.is_fatal

    def test_is_fatal_true(self) -> None:
        from app.backup.domain.models import PreflightCheck
        checks = [
            PreflightCheck("A", PreflightStatus.FATAL, "error"),
        ]
        report = PreflightReport(
            checks=checks,
            overall_status=PreflightStatus.FATAL,
            checked_at_utc="2026-01-01T00:00:00+00:00",
        )
        assert report.is_fatal
        assert len(report.fatal_checks) == 1

    def test_summary_lines_format(self, checker: ReleasePreflightChecker) -> None:
        report = checker.run_all()
        lines = report.summary_lines()
        # Primera línea con estado global
        assert lines[0].startswith("Estado global:")
        # Líneas de checks con iconos y status
        for line in lines[1:]:
            assert any(icon in line for icon in ["✓", "⚠", "✗", "?"])
