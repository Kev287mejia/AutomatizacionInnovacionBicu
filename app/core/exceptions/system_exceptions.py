"""
app.core.exceptions.system_exceptions

Excepciones de dominio del sistema de automatización.
Permite manejar fallos con claridad y trazabilidad para el usuario.
"""


class SistemaBaseException(Exception):
    """Excepción base del sistema."""
    pass


class ModelValidationError(SistemaBaseException):
    """Error al validar la integridad estructural de un modelo de datos."""
    pass


class CatalogNotFoundError(SistemaBaseException):
    """Error cuando un catálogo institucional requerido no se encuentra en disco."""
    pass


class ParsingError(SistemaBaseException):
    """Error al leer o extraer datos de una fuente Word o Excel."""
    pass


class RoutingError(SistemaBaseException):
    """Error durante el enrutamiento de participantes hacia las matrices oficiales."""
    pass


class TemplateError(SistemaBaseException):
    """Error al manipular plantillas oficiales de Excel."""
    pass
