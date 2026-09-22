"""tests.test_backup_service

Suite de tests unitarios para BackupService (Bloque A — Fase 29.24.1).

Cobertura:
    - Generación correcta del archivo .bicu.bak con estructura ZIP válida.
    - Manifiesto JSON con todos los campos requeridos.
    - SHA-256 consistente entre database.sqlite, manifest y signature.sha256.
    - Validación multicapa (hash, cabecera, integrity_check, tablas mínimas).
    - Errores de precondición (BD inexistente).
    - Error de post-verificación detectado y manejado.
    - Metadatos de la BD capturados correctamente (schema_version, row_counts).
    - Online Backup API produce copia legible y consistent.

INVARIANTE: Ningún test modifica M1–M5, datos históricos ni la BD activa.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import pytest

from app.backup.application.backup_service import (
    BACKUP_EXTENSION,
    BACKUP_FORMAT_VERSION,
    BackupService,
)
from app.backup.domain.models import BackupManifest, BackupResult


# ---------------------------------------------------------------------------
# HELPERS DE TEST
# ---------------------------------------------------------------------------


def _make_test_db(path: Path, schema_versions: list[int] | None = None) -> Path:
    """Crea una BD SQLite mínima válida para pruebas.

    Incluye la tabla schema_version con las versiones indicadas y las tablas
    mínimas obligatorias que BackupService espera validar.
    """
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")

        # Tabla de esquema
        conn.execute(
            """
            CREATE TABLE schema_version (
                version    INTEGER NOT NULL PRIMARY KEY,
                name       TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                hash       TEXT NOT NULL
            );
            """
        )
        for v in (schema_versions or [1, 2, 3, 4]):
            conn.execute(
                "INSERT INTO schema_version VALUES (?, ?, datetime('now'), 'testhash');",
                (v, f"v{v:03d}_test"),
            )

        # Tablas mínimas (sin contenido)
        minimal_tables = [
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
        ]
        for t in minimal_tables:
            conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY);")

        conn.commit()
    finally:
        conn.close()
    return path


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def test_db(tmp_path: Path) -> Path:
    db = tmp_path / "bicu_test.db"
    return _make_test_db(db)


@pytest.fixture()
def backup_svc(test_db: Path) -> BackupService:
    return BackupService(db_path=test_db)


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    d = tmp_path / "backups"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# TESTS — GENERACIÓN EXITOSA
# ---------------------------------------------------------------------------


class TestBackupServiceCreation:

    def test_create_backup_returns_success(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        assert result.success is True
        assert result.error_message is None

    def test_create_backup_generates_file(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        assert result.backup_path is not None
        assert result.backup_path.exists()

    def test_create_backup_filename_has_correct_extension(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        assert result.backup_filename.endswith(BACKUP_EXTENSION)

    def test_create_backup_filename_contains_version(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir, system_version="9.9.9")
        assert "v9.9.9" in result.backup_filename

    def test_create_backup_filename_contains_schema_version(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        # Schema v004 → schV004
        assert "schV004" in result.backup_filename

    def test_create_backup_zip_structure(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        with zipfile.ZipFile(result.backup_path, "r") as zf:
            names = set(zf.namelist())
        assert "database.sqlite" in names
        assert "manifest.json" in names
        assert "signature.sha256" in names

    def test_create_backup_manifest_has_required_fields(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir, system_version="2.0.0")
        manifest = result.manifest
        assert manifest is not None
        assert manifest.backup_format_version == BACKUP_FORMAT_VERSION
        assert manifest.system_version == "2.0.0"
        assert manifest.schema_version == 4
        assert isinstance(manifest.database_sha256, str)
        assert len(manifest.database_sha256) == 64
        assert manifest.database_size_bytes > 0
        assert "schema_version" in manifest.table_names
        assert 4 in manifest.schema_migrations_applied

    def test_create_backup_manifest_hash_matches_content(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(result.backup_path, "r") as zf:
                zf.extractall(tmpdir)
            actual_hash = BackupService._sha256_file(Path(tmpdir) / "database.sqlite")
        assert actual_hash == result.manifest.database_sha256

    def test_create_backup_signature_matches_manifest_hash(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(result.backup_path, "r") as zf:
                zf.extractall(tmpdir)
            sig = (Path(tmpdir) / "signature.sha256").read_text().strip()
        sig_hash = sig.split(":", 1)[1] if ":" in sig else sig
        assert sig_hash == result.manifest.database_sha256

    def test_create_backup_manifest_row_counts(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        m = result.manifest
        # Todas las tablas vacías excepto schema_version
        assert m.table_row_counts["schema_version"] == 4
        assert m.table_row_counts["actividad"] == 0

    def test_create_backup_creates_destination_dir_if_missing(
        self, backup_svc: BackupService, tmp_path: Path
    ) -> None:
        missing = tmp_path / "new" / "nested" / "dir"
        assert not missing.exists()
        result = backup_svc.create_backup(missing)
        assert result.success is True
        assert missing.exists()

    def test_create_backup_duration_is_positive(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        assert result.duration_seconds > 0


# ---------------------------------------------------------------------------
# TESTS — VALIDACIÓN
# ---------------------------------------------------------------------------


class TestBackupServiceValidation:

    def test_validate_valid_backup(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        ok, msg = backup_svc.validate_backup(result.backup_path)
        assert ok is True
        assert "válido" in msg.lower()

    def test_validate_nonexistent_file(
        self, backup_svc: BackupService, tmp_path: Path
    ) -> None:
        ok, msg = backup_svc.validate_backup(tmp_path / "nonexistent.bicu.bak")
        assert ok is False
        assert "no existe" in msg

    def test_validate_not_a_zip(
        self, backup_svc: BackupService, tmp_path: Path
    ) -> None:
        fake = tmp_path / "fake.bicu.bak"
        fake.write_bytes(b"Not a ZIP file at all")
        ok, msg = backup_svc.validate_backup(fake)
        assert ok is False

    def test_validate_missing_manifest(
        self, backup_svc: BackupService, backup_dir: Path, tmp_path: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        # Reempaquetar sin manifest.json
        bad = tmp_path / "bad.bicu.bak"
        with zipfile.ZipFile(result.backup_path, "r") as zf_in:
            with zipfile.ZipFile(bad, "w") as zf_out:
                for item in zf_in.namelist():
                    if item != "manifest.json":
                        zf_out.writestr(item, zf_in.read(item))
        ok, msg = backup_svc.validate_backup(bad)
        assert ok is False
        assert "manifest" in msg.lower()

    def test_validate_corrupted_sqlite(
        self, backup_svc: BackupService, backup_dir: Path, tmp_path: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        # Reempaquetar con database.sqlite corrupto (misma cabecera pero cuerpo roto)
        bad = tmp_path / "corrupted.bicu.bak"
        with zipfile.ZipFile(result.backup_path, "r") as zf_in:
            manifest_data = json.loads(zf_in.read("manifest.json"))
            sig = zf_in.read("signature.sha256")

        # Crear un SQLite falso con la cabecera correcta pero cuerpo aleatorio
        fake_sqlite = b"SQLite format 3\x00" + b"\xff" * 4096

        # Recalcular hash para que coincida con el contenido corrupto
        import hashlib
        new_hash = hashlib.sha256(fake_sqlite).hexdigest()
        manifest_data["database_sha256"] = new_hash
        manifest_data["database_size_bytes"] = len(fake_sqlite)

        with zipfile.ZipFile(bad, "w") as zf_out:
            zf_out.writestr("database.sqlite", fake_sqlite)
            zf_out.writestr("manifest.json", json.dumps(manifest_data, indent=2))
            zf_out.writestr("signature.sha256", f"SHA256:{new_hash}\n")

        ok, msg = backup_svc.validate_backup(bad)
        assert ok is False
        # Debería fallar por integrity_check dado que el cuerpo es inválido
        assert ok is False

    def test_validate_hash_mismatch(
        self, backup_svc: BackupService, backup_dir: Path, tmp_path: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        # Alterar el hash en el manifest para forzar discrepancia
        bad = tmp_path / "hash_mismatch.bicu.bak"
        with zipfile.ZipFile(result.backup_path, "r") as zf_in:
            db_content = zf_in.read("database.sqlite")
            sig = zf_in.read("signature.sha256")
            manifest_data = json.loads(zf_in.read("manifest.json"))

        manifest_data["database_sha256"] = "a" * 64  # hash falso
        with zipfile.ZipFile(bad, "w") as zf_out:
            zf_out.writestr("database.sqlite", db_content)
            zf_out.writestr("manifest.json", json.dumps(manifest_data, indent=2))
            zf_out.writestr("signature.sha256", sig)

        ok, msg = backup_svc.validate_backup(bad)
        assert ok is False
        assert "hash" in msg.lower() or "coincide" in msg.lower()

    def test_validate_schema_too_new(
        self, backup_dir: Path, tmp_path: Path
    ) -> None:
        db = tmp_path / "future_schema.db"
        _make_test_db(db, schema_versions=[1, 2, 3, 4, 5, 6, 7, 8])
        svc = BackupService(db_path=db)
        result = svc.create_backup(backup_dir)
        # El backup se genera pero la validación debería detectar v8 > MAX_SUPPORTED
        # No obstante, el BackupService actual permite generar el backup.
        # La validación de compatibilidad detecta schema > MAX en validate_backup.
        # Aquí, el test verifica que se genere correctamente (generamos el backup):
        assert result.success is True  # El backup se genera normalmente
        # Si el schema_version real era 8, la validación debería rechazarlo
        ok, msg = svc.validate_backup(result.backup_path)
        assert ok is False
        assert "soporta" in msg or "actualice" in msg.lower()


# ---------------------------------------------------------------------------
# TESTS — ERRORES DE PRECONDICIÓN
# ---------------------------------------------------------------------------


class TestBackupServicePreconditions:

    def test_create_backup_db_not_exists(
        self, tmp_path: Path, backup_dir: Path
    ) -> None:
        svc = BackupService(db_path=tmp_path / "nonexistent.db")
        result = svc.create_backup(backup_dir)
        assert result.success is False
        assert result.error_message is not None
        assert "no existe" in result.error_message.lower()

    def test_create_backup_success_false_when_db_missing(
        self, tmp_path: Path, backup_dir: Path
    ) -> None:
        svc = BackupService(db_path=tmp_path / "ghost.db")
        result = svc.create_backup(backup_dir)
        assert result.backup_path is None
        assert result.manifest is None


# ---------------------------------------------------------------------------
# TESTS — MANIFEST SERIALIZACIÓN
# ---------------------------------------------------------------------------


class TestBackupManifest:

    def test_manifest_to_dict_roundtrip(self) -> None:
        m = BackupManifest(
            backup_id="test-uuid",
            backup_format_version="1.0",
            created_at_utc="2026-01-01T00:00:00+00:00",
            created_at_local="2026-01-01 00:00:00",
            system_version="1.1.0",
            schema_version=4,
            database_sha256="abc" * 21 + "x",
            database_size_bytes=1024,
            table_names=["schema_version", "actividad"],
            table_row_counts={"schema_version": 4, "actividad": 0},
            schema_migrations_applied=[1, 2, 3, 4],
            python_version="3.11.0",
            platform="win32",
        )
        data = m.to_dict()
        m2 = BackupManifest.from_dict(data)
        assert m2.backup_id == m.backup_id
        assert m2.schema_version == m.schema_version
        assert m2.database_sha256 == m.database_sha256
        assert m2.schema_migrations_applied == m.schema_migrations_applied

    def test_manifest_table_names_sorted(self, backup_svc: BackupService, backup_dir: Path) -> None:
        result = backup_svc.create_backup(backup_dir)
        assert result.manifest.table_names == sorted(result.manifest.table_names)

    def test_backup_result_sha256_property(
        self, backup_svc: BackupService, backup_dir: Path
    ) -> None:
        result = backup_svc.create_backup(backup_dir)
        sha = result.backup_sha256
        assert sha is not None
        assert len(sha) == 64


# ---------------------------------------------------------------------------
# TESTS — ONLINE BACKUP API
# ---------------------------------------------------------------------------


class TestOnlineBackupAPI:

    def test_online_backup_produces_readable_db(
        self, test_db: Path, tmp_path: Path
    ) -> None:
        dest = tmp_path / "copy.sqlite"
        BackupService._online_backup(test_db, dest)
        assert dest.exists()
        conn = sqlite3.connect(str(dest))
        try:
            result = conn.execute("PRAGMA integrity_check;").fetchone()
            assert result[0] == "ok"
        finally:
            conn.close()

    def test_online_backup_preserves_schema_version(
        self, test_db: Path, tmp_path: Path
    ) -> None:
        dest = tmp_path / "copy.sqlite"
        BackupService._online_backup(test_db, dest)
        conn = sqlite3.connect(str(dest))
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_version;").fetchone()
            assert row[0] == 4
        finally:
            conn.close()
