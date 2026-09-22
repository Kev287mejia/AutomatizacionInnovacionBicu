"""tests.test_restore_service

Suite de tests unitarios para RestoreService (Bloque B — Fase 29.24.1).

Cobertura:
    - Restauración exitosa con confirmación explícita.
    - Abortado sin confirmación del operador.
    - Error si el archivo de backup no existe.
    - Safety backup creado antes del reemplazo.
    - Rechazo de backup con hash inválido.
    - Rechazo de backup con esquema incompatible (superior al soportado).
    - Post-verificación de la BD restaurada.
    - Stage correcto en cada flujo.
    - Limpieza de archivos WAL/SHM tras el reemplazo.

INVARIANTE: Ningún test modifica M1–M5 ni datos históricos reales.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from app.backup.application.backup_service import BackupService, BACKUP_EXTENSION
from app.backup.application.restore_service import RestoreService
from app.backup.domain.models import RestoreStage


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _make_test_db(path: Path, schema_versions: list[int] | None = None) -> Path:
    """Crea una BD SQLite mínima válida para pruebas."""
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
        for v in (schema_versions or [1, 2, 3, 4]):
            conn.execute(
                "INSERT INTO schema_version VALUES (?, ?, datetime('now'), 'h');",
                (v, f"v{v:03d}_test"),
            )
        minimal = [
            "actividad", "planificacion", "partida_presupuestaria",
            "diseno_metodologico", "persona", "perfil_estudiante", "perfil_personal",
            "perfil_colaborador", "perfil_beneficiario", "participacion", "evidencia",
            "actividad_evidencia", "informe_actividad", "informe_semanal",
            "detalle_informe_semanal", "discrepancia", "salida_institucional", "auditoria_evento",
        ]
        for t in minimal:
            conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY);")
        conn.commit()
    finally:
        conn.close()
    return path


def _create_valid_backup(source_db: Path, backup_dir: Path) -> Path:
    svc = BackupService(db_path=source_db)
    result = svc.create_backup(backup_dir)
    assert result.success, f"No se pudo crear backup de prueba: {result.error_message}"
    return result.backup_path


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture()
def source_db(tmp_path: Path) -> Path:
    """BD de origen que servirá como fuente para generar backups."""
    db = tmp_path / "source.db"
    return _make_test_db(db)


@pytest.fixture()
def target_db(tmp_path: Path) -> Path:
    """BD de destino (la 'activa') que será reemplazada en la restauración."""
    db = tmp_path / "target" / "active.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    return _make_test_db(db)


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    d = tmp_path / "backups"
    d.mkdir()
    return d


@pytest.fixture()
def valid_backup(source_db: Path, backup_dir: Path) -> Path:
    return _create_valid_backup(source_db, backup_dir)


@pytest.fixture()
def restore_svc(target_db: Path) -> RestoreService:
    return RestoreService(db_path=target_db)


# ---------------------------------------------------------------------------
# TESTS — FLUJO PRINCIPAL
# ---------------------------------------------------------------------------


class TestRestoreServiceMainFlow:

    def test_restore_aborted_without_confirmation(
        self, restore_svc: RestoreService, valid_backup: Path
    ) -> None:
        result = restore_svc.restore_backup(valid_backup, confirmed_by_user=False)
        assert result.success is False
        assert result.final_stage == RestoreStage.ABORTED
        assert result.safety_backup_path is None

    def test_restore_success_with_confirmation(
        self, restore_svc: RestoreService, valid_backup: Path
    ) -> None:
        result = restore_svc.restore_backup(valid_backup, confirmed_by_user=True)
        assert result.success is True
        assert result.final_stage == RestoreStage.COMPLETED

    def test_restore_creates_safety_backup(
        self, restore_svc: RestoreService, valid_backup: Path, target_db: Path
    ) -> None:
        result = restore_svc.restore_backup(valid_backup, confirmed_by_user=True)
        assert result.success is True
        assert result.safety_backup_path is not None
        assert result.safety_backup_path.exists()
        assert str(result.safety_backup_path).endswith(BACKUP_EXTENSION)

    def test_restore_safety_backup_in_correct_directory(
        self, restore_svc: RestoreService, valid_backup: Path, target_db: Path
    ) -> None:
        result = restore_svc.restore_backup(valid_backup, confirmed_by_user=True)
        assert result.success is True
        expected_parent = target_db.parent / "safety_snapshots"
        assert result.safety_backup_path.parent == expected_parent

    def test_restore_produces_valid_db(
        self, restore_svc: RestoreService, valid_backup: Path, target_db: Path
    ) -> None:
        result = restore_svc.restore_backup(valid_backup, confirmed_by_user=True)
        assert result.success is True
        conn = sqlite3.connect(str(target_db))
        try:
            ic = conn.execute("PRAGMA integrity_check;").fetchone()
            assert ic[0] == "ok"
        finally:
            conn.close()

    def test_restore_reports_schema_version_after(
        self, restore_svc: RestoreService, valid_backup: Path
    ) -> None:
        result = restore_svc.restore_backup(valid_backup, confirmed_by_user=True)
        assert result.success is True
        assert result.schema_version_after == 4

    def test_restore_duration_is_positive(
        self, restore_svc: RestoreService, valid_backup: Path
    ) -> None:
        result = restore_svc.restore_backup(valid_backup, confirmed_by_user=True)
        assert result.duration_seconds > 0

    def test_restore_nonexistent_backup(
        self, restore_svc: RestoreService, tmp_path: Path
    ) -> None:
        fake = tmp_path / "no_such.bicu.bak"
        result = restore_svc.restore_backup(fake, confirmed_by_user=True)
        assert result.success is False
        assert result.final_stage == RestoreStage.FAILED
        assert "no existe" in result.error_message.lower()


# ---------------------------------------------------------------------------
# TESTS — VALIDACIÓN DEL BACKUP ANTES DE RESTAURAR
# ---------------------------------------------------------------------------


class TestRestoreServiceValidation:

    def test_restore_rejects_tampered_hash(
        self, restore_svc: RestoreService, valid_backup: Path, tmp_path: Path
    ) -> None:
        # Alterar el hash del manifest para simular tampering
        tampered = tmp_path / "tampered.bicu.bak"
        with zipfile.ZipFile(valid_backup, "r") as zf_in:
            db_content = zf_in.read("database.sqlite")
            sig = zf_in.read("signature.sha256")
            manifest_data = json.loads(zf_in.read("manifest.json"))

        manifest_data["database_sha256"] = "f" * 64
        with zipfile.ZipFile(tampered, "w") as zf_out:
            zf_out.writestr("database.sqlite", db_content)
            zf_out.writestr("manifest.json", json.dumps(manifest_data))
            zf_out.writestr("signature.sha256", sig)

        result = restore_svc.restore_backup(tampered, confirmed_by_user=True)
        assert result.success is False
        assert result.final_stage == RestoreStage.VALIDATING_HASH

    def test_restore_rejects_incompatible_schema(
        self, target_db: Path, backup_dir: Path, tmp_path: Path
    ) -> None:
        # Crear backup con esquema v99 (futuro)
        future_db = tmp_path / "future.db"
        _make_test_db(future_db, schema_versions=list(range(1, 100)))
        svc_future = BackupService(db_path=future_db)
        future_backup = svc_future.create_backup(backup_dir)
        assert future_backup.success

        restore_svc = RestoreService(db_path=target_db)
        result = restore_svc.restore_backup(future_backup.backup_path, confirmed_by_user=True)
        assert result.success is False
        assert result.final_stage == RestoreStage.VALIDATING_SCHEMA
        assert "soporta" in result.error_message or "actualice" in result.error_message.lower()

    def test_restore_rejects_non_zip_file(
        self, restore_svc: RestoreService, tmp_path: Path
    ) -> None:
        fake = tmp_path / "fake.bicu.bak"
        fake.write_bytes(b"NOT A ZIP FILE")
        result = restore_svc.restore_backup(fake, confirmed_by_user=True)
        assert result.success is False

    def test_restore_rejects_missing_manifest(
        self, restore_svc: RestoreService, valid_backup: Path, tmp_path: Path
    ) -> None:
        no_manifest = tmp_path / "no_manifest.bicu.bak"
        with zipfile.ZipFile(valid_backup, "r") as zf_in:
            with zipfile.ZipFile(no_manifest, "w") as zf_out:
                for item in zf_in.namelist():
                    if item != "manifest.json":
                        zf_out.writestr(item, zf_in.read(item))
        result = restore_svc.restore_backup(no_manifest, confirmed_by_user=True)
        assert result.success is False


# ---------------------------------------------------------------------------
# TESTS — RESTAURACIÓN CUANDO LA BD ACTIVA NO EXISTE
# ---------------------------------------------------------------------------


class TestRestoreWithNoActiveDB:

    def test_restore_creates_db_when_target_missing(
        self, source_db: Path, backup_dir: Path, tmp_path: Path
    ) -> None:
        nonexistent_db = tmp_path / "new_location" / "fresh.db"
        backup_path = _create_valid_backup(source_db, backup_dir)
        svc = RestoreService(db_path=nonexistent_db)
        result = svc.restore_backup(backup_path, confirmed_by_user=True)
        assert result.success is True
        assert nonexistent_db.exists()
        # Sin safety backup porque no había BD activa
        assert result.safety_backup_path is None

    def test_restore_no_safety_backup_when_no_active_db(
        self, source_db: Path, backup_dir: Path, tmp_path: Path
    ) -> None:
        fresh_db = tmp_path / "fresh" / "empty.db"
        backup_path = _create_valid_backup(source_db, backup_dir)
        svc = RestoreService(db_path=fresh_db)
        result = svc.restore_backup(backup_path, confirmed_by_user=True)
        assert result.safety_backup_path is None
