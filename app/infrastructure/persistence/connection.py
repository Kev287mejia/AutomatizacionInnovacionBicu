"""Gestor de Conexiones SQLite y Transacciones - Sistema Institucional BICU.

Fase 25 (Etapa 25.1): Infraestructura SQLite.
Proporciona la fábrica de conexiones SQLite configurada estrictamente con
PRAGMA journal_mode = WAL, PRAGMA foreign_keys = ON, busy_timeout y context
managers para transacciones atómicas con aislamiento IMMEDIATE.
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union, Dict, Any

from app.infrastructure.persistence.config import DatabaseConfig, get_default_database_path

logger = logging.getLogger(__name__)


class SQLiteConnectionManager:
    """Fábrica y administradora de conexiones SQLite configuradas.

    Garantiza que cada conexión aplique los pragmas institucionales mandatorios:
    - journal_mode = WAL (lecturas concurrentes no bloqueantes).
    - foreign_keys = ON (integridad referencial declarativa activada).
    - busy_timeout (espera automática ante contención para evitar bloqueos bruscos).
    - synchronous = NORMAL (seguridad transaccional de alto rendimiento en WAL).
    """

    def __init__(self, config: Optional[DatabaseConfig] = None) -> None:
        """Inicializa el gestor con la configuración provista o la predeterminada."""
        self.config = config or DatabaseConfig()

    def get_connection(self, db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
        """Abre y configura una conexión SQLite.

        Si se especifica `db_path`, se utiliza dicha ruta (útil para pruebas temporales);
        de lo contrario se utiliza la ruta configurada en `self.config.db_path`.
        """
        target_path = Path(db_path) if db_path is not None else self.config.db_path

        # Si no es en memoria, asegurar que el directorio padre exista
        if str(target_path) != ":memory:":
            target_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(target_path),
            timeout=self.config.busy_timeout_ms / 1000.0,
            isolation_level=None  # Control explícito de transacciones
        )

        # Configurar row_factory para acceso por nombre de columna
        conn.row_factory = sqlite3.Row

        # Aplicar PRAGMAs obligatorios de forma determinista
        self._apply_pragmas(conn)

        return conn

    def _apply_pragmas(self, conn: sqlite3.Connection) -> None:
        """Aplica la configuración de pragmas de SQLite sobre la conexión."""
        cursor = conn.cursor()

        # 1. Foreign Keys obligatorio
        if self.config.foreign_keys:
            cursor.execute("PRAGMA foreign_keys = ON;")

        # 2. Busy timeout en milisegundos
        cursor.execute(f"PRAGMA busy_timeout = {self.config.busy_timeout_ms};")

        # 3. Journal mode (WAL)
        # Nota: SQLite para bases en memoria ignora WAL y mantiene 'memory'
        cursor.execute(f"PRAGMA journal_mode = {self.config.journal_mode};")

        # 4. Synchronous
        cursor.execute(f"PRAGMA synchronous = {self.config.synchronous};")

        # 5. Cache size
        cursor.execute(f"PRAGMA cache_size = {self.config.cache_size};")

        cursor.close()

    @staticmethod
    def verify_pragmas(conn: sqlite3.Connection) -> Dict[str, Any]:
        """Consulta y retorna los valores reales activos de los PRAGMAs en la conexión."""
        cursor = conn.cursor()
        diagnostics = {}

        try:
            cursor.execute("PRAGMA journal_mode;")
            row = cursor.fetchone()
            diagnostics["journal_mode"] = str(row[0]).lower() if row else "unknown"

            cursor.execute("PRAGMA foreign_keys;")
            row = cursor.fetchone()
            diagnostics["foreign_keys"] = int(row[0]) if row else 0

            cursor.execute("PRAGMA busy_timeout;")
            row = cursor.fetchone()
            diagnostics["busy_timeout"] = int(row[0]) if row else 0

            cursor.execute("PRAGMA synchronous;")
            row = cursor.fetchone()
            diagnostics["synchronous"] = int(row[0]) if row else 0

            cursor.execute("PRAGMA cache_size;")
            row = cursor.fetchone()
            diagnostics["cache_size"] = int(row[0]) if row else 0
        finally:
            cursor.close()

        return diagnostics


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """Context manager para ejecutar un bloque de operaciones atómicas con SQLite.

    Utiliza `BEGIN IMMEDIATE` para adquirir de inmediato el bloqueo reservado
    de escritura en modo WAL, previniendo deadlocks entre múltiples transacciones.
    Si el bloque concluye sin excepciones, ejecuta `COMMIT`.
    Si ocurre cualquier excepción, ejecuta `ROLLBACK` y re-lanza el error.
    """
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE;")
    cursor.close()
    try:
        yield conn
        cursor = conn.cursor()
        cursor.execute("COMMIT;")
        cursor.close()
    except Exception as e:
        logger.warning(f"Excepción en transacción SQLite, ejecutando ROLLBACK: {e}")
        cursor = conn.cursor()
        cursor.execute("ROLLBACK;")
        cursor.close()
        raise
