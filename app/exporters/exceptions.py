"""
app.exporters.exceptions

Excepciones del Motor de Exportación a Excel (Fase 9).
"""


class ExporterError(Exception):
    """Excepción base para errores del motor de exportación."""
    pass


class PlantillasOficialesRequeridasError(ExporterError):
    """
    Se dispara cuando se intenta ejecutar la exportación oficial (--mode export)
    y una o más matrices no cuentan con una plantilla oficial real en el directorio
    de plantillas institucionales. Los fixtures de prueba no autorizan la exportación oficial.
    """
    pass


class ExportacionBloqueadaError(ExporterError):
    """
    Se dispara cuando una directiva institucional bloqueante (como un catálogo
    pendiente marcado como requerido, o una columna obligatoria sin fuente)
    impide generar el paquete oficial.
    """
    pass


class ViolacionInvarianteExportacionError(ExporterError):
    """
    Se dispara cuando el número de filas escritas en las matrices no coincide
    exactamente con el total de actividades o participaciones enrutadas.
    """
    pass


class ViolacionZonaEscribibleError(ExporterError):
    """
    Se dispara cuando se intenta escribir en una celda fuera de la ZonaEscribible
    autorizada o sobre una celda protegida con fórmulas.
    """
    pass


class ModificacionPlantillaBaseError(ExporterError):
    """
    Se dispara si el hash SHA-256 de una plantilla base antes de exportar
    difiere del hash después de exportar, demostrando que fue alterada indebidamente.
    """
    pass
