"""Unidad de Trabajo Satélite para el Módulo de Planificación (PlanningUnitOfWork).

Fase 29.4.2 — Implementación de Persistencia SQLite V003.
Proporciona la frontera transaccional atómica para la capa de Aplicación de Planificación,
asegurando que todos los repositorios satélites compartan la misma conexión y el mismo
bloque de aislamiento `BEGIN IMMEDIATE` en modo WAL, con llaves foráneas habilitadas.
Totalmente independiente de SQLiteUnitOfWork del núcleo patrimonial.
"""

from pathlib import Path
import sqlite3
from typing import Optional, Type, Union
from types import TracebackType

from app.core.exceptions.persistence_exceptions import TransactionError
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.planning.domain.ports import PlanningUnitOfWorkPort
from app.planning.infrastructure.persistence.repositories import (
    SQLiteCatalogRepository,
    SQLiteMethodologicalDesignRepository,
    SQLitePlannedActivityRepository,
    SQLitePlanningExecutionLinkRepository,
)


class PlanningUnitOfWork(PlanningUnitOfWorkPort):
    """Unidad de Trabajo satélite para el módulo de Planificación y Diseño Metodológico."""

    def __init__(
        self,
        connection_manager: Optional[SQLiteConnectionManager] = None,
        db_path: Optional[Union[str, Path]] = None,
        connection: Optional[sqlite3.Connection] = None,
    ) -> None:
        self._connection_manager = connection_manager or SQLiteConnectionManager()
        self._db_path = db_path
        self._external_conn = connection
        self._conn: Optional[sqlite3.Connection] = None
        self._in_transaction: bool = False
        self._owns_connection: bool = False

        self._planned_activities: Optional[SQLitePlannedActivityRepository] = None
        self._methodological_designs: Optional[SQLiteMethodologicalDesignRepository] = None
        self._catalogs: Optional[SQLiteCatalogRepository] = None
        self._execution_links: Optional[SQLitePlanningExecutionLinkRepository] = None

    @property
    def planned_activities(self) -> SQLitePlannedActivityRepository:
        """Acceso al repositorio de Actividades Planificadas dentro de la transacción."""
        if self._planned_activities is None:
            raise TransactionError(
                "PlanningUnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._planned_activities

    @property
    def methodological_designs(self) -> SQLiteMethodologicalDesignRepository:
        """Acceso al repositorio de Diseños Metodológicos dentro de la transacción."""
        if self._methodological_designs is None:
            raise TransactionError(
                "PlanningUnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._methodological_designs

    @property
    def catalogs(self) -> SQLiteCatalogRepository:
        """Acceso al repositorio de Catálogos dentro de la transacción."""
        if self._catalogs is None:
            raise TransactionError(
                "PlanningUnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._catalogs

    @property
    def execution_links(self) -> SQLitePlanningExecutionLinkRepository:
        """Acceso al repositorio de vínculos Planificación ↔ Ejecución (V004)."""
        if self._execution_links is None:
            raise TransactionError(
                "PlanningUnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._execution_links

    @property
    def connection(self) -> sqlite3.Connection:
        """Conexión activa dentro de la transacción."""
        if self._conn is None:
            raise TransactionError(
                "PlanningUnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._conn

    def __enter__(self) -> "PlanningUnitOfWork":
        if self._external_conn is not None:
            self._conn = self._external_conn
            self._owns_connection = False
        else:
            self._conn = self._connection_manager.get_connection(db_path=self._db_path)
            self._owns_connection = True

        try:
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.execute("BEGIN IMMEDIATE;")
            self._in_transaction = True
        except sqlite3.Error as e:
            if self._owns_connection and self._conn:
                self._conn.close()
                self._conn = None
            raise TransactionError(f"Fallo al iniciar transacción SQLite en Planning: {e}") from e

        # Inyectar la MISMA conexión en todos los repositorios satélites
        self._planned_activities = SQLitePlannedActivityRepository(self._conn)
        self._methodological_designs = SQLiteMethodologicalDesignRepository(self._conn)
        self._catalogs = SQLiteCatalogRepository()
        self._execution_links = SQLitePlanningExecutionLinkRepository(self._conn)

        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self._conn is not None:
            try:
                if exc_type is not None and self._in_transaction:
                    self.rollback()
            finally:
                if self._owns_connection:
                    self._conn.close()
                self._conn = None
                self._in_transaction = False
                self._planned_activities = None
                self._methodological_designs = None
                self._catalogs = None
                self._execution_links = None

    def commit(self) -> None:
        """Confirma atómicamente la transacción activa."""
        if self._conn is None or not self._in_transaction:
            raise TransactionError("No existe una transacción activa para confirmar en Planning.")
        try:
            self._conn.execute("COMMIT;")
            self._in_transaction = False
        except sqlite3.Error as e:
            raise TransactionError(f"Error al confirmar transacción SQLite en Planning: {e}") from e

    def rollback(self) -> None:
        """Revierte la transacción activa."""
        if self._conn is None or not self._in_transaction:
            return
        try:
            self._conn.execute("ROLLBACK;")
            self._in_transaction = False
        except sqlite3.Error as e:
            self._in_transaction = False
            if "no transaction is active" not in str(e).lower():
                raise TransactionError(f"Error al revertir transacción SQLite en Planning: {e}") from e
