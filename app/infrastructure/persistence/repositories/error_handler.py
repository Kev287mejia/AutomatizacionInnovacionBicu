"""Traductor de excepciones SQLite a excepciones de dominio - Sistema BICU.

Garantiza que las excepciones físicas de SQLite (sqlite3.Error, sqlite3.IntegrityError)
no escapen hacia las capas de Dominio o Aplicación, preservando el contexto
original mediante encadenamiento de excepciones ('from e').
"""

import functools
import sqlite3
from typing import Any, Callable

from app.core.exceptions.persistence_exceptions import (
    EntityAlreadyExistsError,
    PersistenceError,
    ReferentialIntegrityError,
)


def translate_sqlite_errors(entity_name: str) -> Callable:
    """Decorador para interceptar errores de SQLite y traducirlos a excepciones de dominio."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except sqlite3.IntegrityError as e:
                msg = str(e).lower()
                if "unique" in msg:
                    raise EntityAlreadyExistsError(
                        entity_type=entity_name,
                        key_field="restriccion_unica",
                        key_value=str(e),
                    ) from e
                elif "foreign key" in msg:
                    raise ReferentialIntegrityError(
                        f"Violación de clave foránea en la entidad '{entity_name}': {e}"
                    ) from e
                else:
                    raise PersistenceError(
                        f"Violación de restricción de integridad en '{entity_name}': {e}"
                    ) from e
            except sqlite3.Error as e:
                raise PersistenceError(
                    f"Error de persistencia SQLite al operar sobre '{entity_name}': {e}"
                ) from e

        return wrapper

    return decorator
