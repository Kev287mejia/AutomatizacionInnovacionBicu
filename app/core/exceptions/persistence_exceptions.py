"""Excepciones de dominio para la capa de persistencia - Sistema BICU.

Define errores tipados totalmente independientes de SQLite, JDBC o cualquier
tecnología física de base de datos.
"""

from app.core.exceptions.system_exceptions import SistemaBaseException


class PersistenceError(SistemaBaseException):
    """Excepción base para errores de persistencia en el dominio."""
    pass


class EntityNotFoundError(PersistenceError):
    """Excepción lanzada cuando una entidad esperada no existe en el almacenamiento."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"Entidad de tipo '{entity_type}' con identificador '{entity_id}' no fue encontrada.")


class EntityAlreadyExistsError(PersistenceError):
    """Excepción lanzada cuando se intenta insertar una entidad con una clave única preexistente."""

    def __init__(self, entity_type: str, key_field: str, key_value: str) -> None:
        self.entity_type = entity_type
        self.key_field = key_field
        self.key_value = key_value
        super().__init__(f"Entidad '{entity_type}' ya existe con {key_field}='{key_value}'.")


class ReferentialIntegrityError(PersistenceError):
    """Excepción lanzada ante violación de una regla de integridad referencial de dominio."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class TransactionError(PersistenceError):
    """Excepción lanzada ante fallos en la coordinación de transacciones en el Unit of Work."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
