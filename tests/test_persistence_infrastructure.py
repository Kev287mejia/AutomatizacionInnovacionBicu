"""Pruebas Automatizadas de Infraestructura SQLite y Gobernanza de Persistencia.

Fase 25 (Etapa 25.1): Validación de conexión, modo WAL, llaves foráneas,
aislamiento de OneDrive y transaccionalidad atómica.
"""

import os
import sqlite3
import pytest
from pathlib import Path

from app.infrastructure.persistence.config import (
    DatabaseConfig,
    DatabaseSecurityError,
    get_default_database_directory,
    get_default_database_path,
    is_onedrive_path,
)
from app.infrastructure.persistence.connection import (
    SQLiteConnectionManager,
    transaction,
)


class TestDatabaseConfigAndLocation:
    """Pruebas de gobernanza de ubicación física y seguridad de la base de datos."""

    def test_default_database_path_resolves_to_local_directory(self) -> None:
        """Verifica que la ruta predeterminada apunte a la carpeta local de BICU."""
        default_dir = get_default_database_directory()
        default_path = get_default_database_path()

        assert default_dir.exists(), "El directorio padre local debe crearse automáticamente"
        assert default_path.name == "bicu_sistema.db"
        assert default_path.parent == default_dir
        assert "bicu_sistema" in str(default_path).lower()

    def test_onedrive_detection_identifies_cloud_paths(self) -> None:
        """Verifica que el detector de OneDrive reconozca rutas sincronizadas."""
        onedrive_sample_1 = Path("C:/Users/Coordinador/OneDrive/bicu_sistema.db")
        onedrive_sample_2 = Path("C:/Users/Coordinador/OneDrive - BICU/data/bicu.db")
        safe_local_sample = Path("C:/Users/Coordinador/AppData/Local/BICU_Sistema/data/bicu.db")

        assert is_onedrive_path(onedrive_sample_1) is True
        assert is_onedrive_path(onedrive_sample_2) is True
        assert is_onedrive_path(safe_local_sample) is False

    def test_config_rejects_onedrive_path_by_default(self) -> None:
        """Verifica que DatabaseConfig lance DatabaseSecurityError si se intenta usar OneDrive."""
        onedrive_path = Path("C:/Users/Docente/OneDrive/bicu_sistema.db")

        with pytest.raises(DatabaseSecurityError) as exc_info:
            DatabaseConfig(db_path=onedrive_path)

        assert "VIOLACIÓN DE SEGURIDAD OPERACIONAL" in str(exc_info.value)
        assert "OneDrive" in str(exc_info.value)

    def test_config_allows_onedrive_only_with_explicit_flag(self) -> None:
        """Verifica que la bandera allow_onedrive permita eludir la restricción si se requiere."""
        onedrive_path = Path("C:/Users/Docente/OneDrive/bicu_sistema.db")
        config = DatabaseConfig(db_path=onedrive_path, allow_onedrive=True)
        assert config.db_path == onedrive_path

    def test_config_validates_journal_mode_and_synchronous(self) -> None:
        """Verifica que se rechacen valores no permitidos de journal_mode y synchronous."""
        with pytest.raises(ValueError, match="journal_mode inválido"):
            DatabaseConfig(journal_mode="INVALID_MODE")

        with pytest.raises(ValueError, match="synchronous inválido"):
            DatabaseConfig(synchronous="SUPER_FAST_INVALID")


class TestSQLiteConnectionManagerAndPragmas:
    """Pruebas del administrador de conexiones y verificación de PRAGMAs obligatorios."""

    def test_connection_sets_wal_and_foreign_keys_on_disk(self, tmp_path: Path) -> None:
        """Verifica que una base de datos en disco aplique journal_mode=WAL y foreign_keys=ON."""
        db_file = tmp_path / "test_persistence_wal.db"
        config = DatabaseConfig(db_path=db_file, busy_timeout_ms=6000)
        manager = SQLiteConnectionManager(config)

        conn = manager.get_connection()
        try:
            diagnostics = manager.verify_pragmas(conn)

            assert diagnostics["journal_mode"] == "wal", "El modo journal debe ser WAL"
            assert diagnostics["foreign_keys"] == 1, "Las llaves foráneas deben estar activadas (1)"
            assert diagnostics["busy_timeout"] == 6000, "El busy_timeout debe coincidir con la config"
            assert diagnostics["synchronous"] == 1, "En WAL, synchronous NORMAL corresponde al código 1"
        finally:
            conn.close()

    def test_foreign_keys_enforces_referential_integrity(self, tmp_path: Path) -> None:
        """Verifica que la base de datos rechace violaciones de integridad referencial."""
        db_file = tmp_path / "test_fk.db"
        manager = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))

        conn = manager.get_connection()
        try:
            conn.execute("CREATE TABLE padre (id INTEGER PRIMARY KEY, nombre TEXT);")
            conn.execute(
                "CREATE TABLE hijo ("
                "  id INTEGER PRIMARY KEY, "
                "  padre_id INTEGER, "
                "  FOREIGN KEY(padre_id) REFERENCES padre(id) ON DELETE RESTRICT"
                ");"
            )

            # Inserción con padre válido debe funcionar
            conn.execute("INSERT INTO padre (id, nombre) VALUES (1, 'Actividad A');")
            conn.execute("INSERT INTO hijo (id, padre_id) VALUES (10, 1);")

            # Inserción con padre inexistente debe fallar por Foreign Key
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
                conn.execute("INSERT INTO hijo (id, padre_id) VALUES (20, 999);")

            # Eliminación de padre con hijos debe fallar por RESTRICT
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
                conn.execute("DELETE FROM padre WHERE id = 1;")
        finally:
            conn.close()

    def test_row_factory_allows_column_name_access(self, tmp_path: Path) -> None:
        """Verifica que sqlite3.Row permita acceder a columnas por nombre."""
        db_file = tmp_path / "test_rows.db"
        manager = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))

        conn = manager.get_connection()
        try:
            conn.execute("CREATE TABLE demo (codigo TEXT, valor REAL);")
            conn.execute("INSERT INTO demo (codigo, valor) VALUES ('IND-16', 29.5);")

            cursor = conn.execute("SELECT codigo, valor FROM demo;")
            row = cursor.fetchone()

            assert row["codigo"] == "IND-16"
            assert row["valor"] == 29.5
        finally:
            conn.close()


class TestTransactionsAndAtomicity:
    """Pruebas de transacciones atómicas y rollback."""

    def test_transaction_commits_successfully(self, tmp_path: Path) -> None:
        """Verifica que una transacción exitosa persista los cambios en disco."""
        db_file = tmp_path / "test_tx_commit.db"
        manager = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))

        conn = manager.get_connection()
        try:
            conn.execute("CREATE TABLE registros (item TEXT);")

            with transaction(conn):
                conn.execute("INSERT INTO registros (item) VALUES ('Alpha');")
                conn.execute("INSERT INTO registros (item) VALUES ('Beta');")

            # Consultar en la misma conexión
            cursor = conn.execute("SELECT COUNT(*) FROM registros;")
            assert cursor.fetchone()[0] == 2
        finally:
            conn.close()

        # Reabrir en una nueva conexión y verificar persistencia
        conn2 = manager.get_connection()
        try:
            cursor = conn2.execute("SELECT COUNT(*) FROM registros;")
            assert cursor.fetchone()[0] == 2
        finally:
            conn2.close()

    def test_transaction_rolls_back_on_exception(self, tmp_path: Path) -> None:
        """Verifica que si ocurre una excepción dentro del bloque, se ejecute ROLLBACK."""
        db_file = tmp_path / "test_tx_rollback.db"
        manager = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))

        conn = manager.get_connection()
        try:
            conn.execute("CREATE TABLE transaccional (dato TEXT);")

            with pytest.raises(RuntimeError, match="Error simulado en proceso"):
                with transaction(conn):
                    conn.execute("INSERT INTO transaccional (dato) VALUES ('Guardado preliminar');")
                    raise RuntimeError("Error simulado en proceso")

            cursor = conn.execute("SELECT COUNT(*) FROM transaccional;")
            assert cursor.fetchone()[0] == 0, "La transacción abortada debió revertirse íntegramente"
        finally:
            conn.close()

    def test_wal_allows_concurrent_readers(self, tmp_path: Path) -> None:
        """Verifica que el modo WAL permita lecturas concurrentes sin bloqueo."""
        db_file = tmp_path / "test_wal_readers.db"
        manager = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))

        conn_writer = manager.get_connection()
        try:
            conn_writer.execute("CREATE TABLE concurrentes (val INTEGER);")
            conn_writer.execute("INSERT INTO concurrentes (val) VALUES (100);")

            # Segundo lector mientras el escritor está abierto
            conn_reader = manager.get_connection()
            try:
                cursor = conn_reader.execute("SELECT val FROM concurrentes;")
                assert cursor.fetchone()["val"] == 100
            finally:
                conn_reader.close()
        finally:
            conn_writer.close()
