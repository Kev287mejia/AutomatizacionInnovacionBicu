"""app.application.commands.pipeline_commands

Comandos para la orquestación integral del pipeline institucional y la exportación de matrices oficiales.
Gobernados por CQRS lógico en la capa de Aplicación.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.application.dto.export_dtos import PoliticaExportacionRevision


class EjecutarPipelineActividadCommand(BaseModel):
    """Comando para ejecutar el pipeline integral sobre una actividad: Ingesta/Persistencia -> Calidad -> Routing -> Prep Export."""

    id_actividad: str = Field(..., description="UUID de la actividad a procesar.")
    dry_run: bool = Field(
        default=False,
        description="Si True, ejecuta la evaluación y clasificación en memoria sin persistir cambios en SQLite."
    )
    persistir_discrepancias: bool = Field(
        default=True,
        description="Si True y dry_run es False, persiste las discrepancias detectadas en la tabla 'discrepancia'."
    )
    politica_revision: PoliticaExportacionRevision = Field(
        default=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
        description="Política OPEN-02 para el tratamiento de registros en revisión."
    )
    fuente_archivo_asistencia: Optional[str] = Field(
        default=None,
        description="Nombre o ruta del archivo de asistencia para contrastes de calidad."
    )
    fuente_archivo_informe: Optional[str] = Field(
        default=None,
        description="Nombre o ruta del archivo de informe Word para contrastes de calidad."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ExportarMatricesActividadCommand(BaseModel):
    """Comando para exportar las 5 matrices oficiales M1–M5 de una actividad individual."""

    id_actividad: str = Field(..., description="UUID de la actividad a exportar.")
    carpeta_salida: str = Field(
        default="output",
        description="Ruta de destino donde se generarán las matrices XLSX."
    )
    politica_revision: PoliticaExportacionRevision = Field(
        default=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
        description="Política OPEN-02 para registros en revisión."
    )
    dry_run: bool = Field(
        default=False,
        description="Si True, realiza simulación en memoria (PREVIEW) sin tocar el disco de salida."
    )
    permitir_fixtures_test_only: bool = Field(
        default=False,
        description="Bandera de testing para entornos con fixtures simuladas."
    )
    carpeta_templates: Optional[str] = Field(
        default=None,
        description="Ruta personalizada a la carpeta de plantillas oficiales."
    )
    carpeta_fixtures: Optional[str] = Field(
        default=None,
        description="Ruta personalizada a la carpeta de plantillas fixtures para testing."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ExportarMatricesPeriodoCommand(BaseModel):
    """Comando para exportar las matrices oficiales agregadas para un período institucional."""

    anio: int = Field(..., ge=2000, le=2100, description="Año calendario.")
    mes: Optional[int] = Field(default=None, ge=1, le=12, description="Mes opcional (1..12).")
    semana: Optional[int] = Field(default=None, ge=1, le=5, description="Semana operativa opcional (1..5).")
    sede_recinto: Optional[str] = Field(default=None, description="Filtrar por sede o recinto.")
    ids_actividades: Optional[List[str]] = Field(
        default=None,
        description="Lista explícita de UUIDs de actividades a consolidar en lugar de filtro temporal."
    )
    carpeta_salida: str = Field(
        default="output",
        description="Ruta de destino donde se generarán los archivos XLSX."
    )
    politica_revision: PoliticaExportacionRevision = Field(
        default=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
        description="Política OPEN-02 para registros en revisión."
    )
    dry_run: bool = Field(
        default=False,
        description="Si True, simulación en memoria sin escrituras físicas."
    )
    permitir_fixtures_test_only: bool = Field(
        default=False,
        description="Bandera de testing para entornos con fixtures simuladas."
    )
    carpeta_templates: Optional[str] = Field(
        default=None,
        description="Ruta personalizada a la carpeta de plantillas oficiales."
    )
    carpeta_fixtures: Optional[str] = Field(
        default=None,
        description="Ruta personalizada a la carpeta de plantillas fixtures para testing."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
