"""Adaptador SQLite para el patrón Unit of Work (IUnitOfWork).

Proporciona la frontera transaccional atómica para la capa de Aplicación,
asegurando que todos los repositorios compartan la misma conexión y el mismo
bloque de aislamiento `BEGIN IMMEDIATE` en modo WAL.
"""

from pathlib import Path
import sqlite3
from typing import Optional, Type, Union
from types import TracebackType

from app.core.exceptions.persistence_exceptions import TransactionError
from app.core.ports.unit_of_work import IUnitOfWork
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.repositories.actividad_repository import (
    SQLiteActividadRepository,
)
from app.infrastructure.persistence.repositories.discrepancia_repository import (
    SQLiteDiscrepanciaRepository,
)
from app.infrastructure.persistence.repositories.evidencia_repository import (
    SQLiteEvidenciaRepository,
)
from app.infrastructure.persistence.repositories.informe_semanal_repository import (
    SQLiteInformeSemanalRepository,
)
from app.infrastructure.persistence.repositories.participacion_repository import (
    SQLiteParticipacionRepository,
)
from app.infrastructure.persistence.repositories.persona_repository import (
    SQLitePersonaRepository,
)


class SQLiteUnitOfWork(IUnitOfWork):
    """Implementación concreta de Unit of Work sobre SQLite."""

    def __init__(
        self,
        connection_manager: Optional[SQLiteConnectionManager] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Inicializa el Unit of Work con el gestor de conexiones institucional."""
        self._connection_manager = connection_manager or SQLiteConnectionManager()
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._in_transaction: bool = False

        self._actividades: Optional[SQLiteActividadRepository] = None
        self._personas: Optional[SQLitePersonaRepository] = None
        self._participaciones: Optional[SQLiteParticipacionRepository] = None
        self._evidencias: Optional[SQLiteEvidenciaRepository] = None
        self._informes_semanales: Optional[SQLiteInformeSemanalRepository] = None
        self._discrepancias: Optional[SQLiteDiscrepanciaRepository] = None

    @property
    def actividades(self) -> SQLiteActividadRepository:
        """Acceso al repositorio de Actividades dentro de la transacción."""
        if self._actividades is None:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._actividades

    @property
    def personas(self) -> SQLitePersonaRepository:
        """Acceso al repositorio de Personas dentro de la transacción."""
        if self._personas is None:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._personas

    @property
    def participaciones(self) -> SQLiteParticipacionRepository:
        """Acceso al repositorio de Participaciones dentro de la transacción."""
        if self._participaciones is None:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._participaciones

    @property
    def evidencias(self) -> SQLiteEvidenciaRepository:
        """Acceso al repositorio de Evidencias dentro de la transacción."""
        if self._evidencias is None:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._evidencias

    @property
    def informes_semanales(self) -> SQLiteInformeSemanalRepository:
        """Acceso al repositorio de Informes Semanales dentro de la transacción."""
        if self._informes_semanales is None:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._informes_semanales

    @property
    def discrepancias(self) -> SQLiteDiscrepanciaRepository:
        """Acceso al repositorio de Discrepancias dentro de la transacción."""
        if self._discrepancias is None:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._discrepancias

    def __enter__(self) -> "SQLiteUnitOfWork":
        """Inicia la transacción adquiriendo conexión y ejecutando BEGIN IMMEDIATE."""
        self._conn = self._connection_manager.get_connection(db_path=self._db_path)
        try:
            self._conn.execute("BEGIN IMMEDIATE;")
            self._in_transaction = True
        except sqlite3.Error as e:
            if self._conn:
                self._conn.close()
                self._conn = None
            raise TransactionError(f"Fallo al iniciar transacción SQLite: {e}") from e

        # Inyectar la MISMA conexión en todos los repositorios
        self._actividades = SQLiteActividadRepository(self._conn)
        self._personas = SQLitePersonaRepository(self._conn)
        self._participaciones = SQLiteParticipacionRepository(self._conn)
        self._evidencias = SQLiteEvidenciaRepository(self._conn)
        self._informes_semanales = SQLiteInformeSemanalRepository(self._conn)
        self._discrepancias = SQLiteDiscrepanciaRepository(self._conn)

        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Finaliza la transacción con rollback automático si ocurrió excepción."""
        if self._conn is not None:
            try:
                if exc_type is not None and self._in_transaction:
                    self.rollback()
            finally:
                self._conn.close()
                self._conn = None
                self._in_transaction = False
                self._actividades = None
                self._personas = None
                self._participaciones = None
                self._evidencias = None
                self._informes_semanales = None
                self._discrepancias = None

    def commit(self) -> None:
        """Confirma atómicamente la transacción activa."""
        if self._conn is None or not self._in_transaction:
            raise TransactionError("No existe una transacción activa para confirmar.")
        try:
            self._conn.execute("COMMIT;")
            self._in_transaction = False
        except sqlite3.Error as e:
            raise TransactionError(f"Error al confirmar transacción SQLite: {e}") from e

    def rollback(self) -> None:
        """Revierte la transacción activa."""
        if self._conn is None or not self._in_transaction:
            return
        try:
            self._conn.execute("ROLLBACK;")
            self._in_transaction = False
        except sqlite3.Error as e:
            raise TransactionError(f"Error al revertir transacción SQLite: {e}") from e
