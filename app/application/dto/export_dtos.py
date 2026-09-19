"""app.application.dto.export_dtos

DTOs y enumeraciones para la preparación, gobernanza y ejecución de la exportación institucional.
Define:
- PoliticaExportacionRevision: Abstracción de política para OPEN-02 (tratamiento de EN_REVISION).
- ExportacionPreparadaDTO: Resumen cuantificado de la preparación de exportación.
- PipelineActividadResultDTO: Resultado integral de la corrida del pipeline institucional.
- ExportarMatricesResultDTO: Resultado de la exportación a matrices oficiales M1–M5.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.application.dto.output_dtos import EnrutarParticipacionesResultDTO
from app.application.dto.quality_dtos import QualityAssessmentDTO


class PoliticaExportacionRevision(str, Enum):
    """Abstracción de política de gobierno para la decisión abierta OPEN-02.
    
    Determina cómo se procesan durante la exportación los registros que poseen
    la marca 'requiere_revision = 1' o estado operativo 'EN_REVISION'.
    
    Opciones:
    - EXPORTAR_CON_OBSERVACION: (Defecto patrimonial v1.0.3) Se exporta a la matriz oficial
      con el texto de advertencia pericial en la columna de observaciones.
    - RETENER_EN_CUARENTENA: Se excluye de las matrices oficiales y se retiene en cuarentena.
    - EXPORTAR_CON_MARCA: Se exporta a la matriz oficial anteponiendo el tag institucional '[EN_REVISION]'.
    """
    EXPORTAR_CON_OBSERVACION = "EXPORTAR_CON_OBSERVACION"
    RETENER_EN_CUARENTENA = "RETENER_EN_CUARENTENA"
    EXPORTAR_CON_MARCA = "EXPORTAR_CON_MARCA"


class ExportacionPreparadaDTO(BaseModel):
    """Proyección de los datos consolidados y depurados listos para ser entregados al ACL."""

    id_actividad: str = Field(..., description="UUID de la actividad preparada.")
    politica_revision: PoliticaExportacionRevision = Field(
        default=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
        description="Política de tratamiento aplicada a registros en revisión."
    )
    total_m1_actividades: int = Field(default=1, ge=0, description="Cantidad de actividades en M1.")
    total_m2_estudiantes: int = Field(default=0, ge=0, description="Total exportable a M2 Estudiantes.")
    total_m3_academicos_admin: int = Field(default=0, ge=0, description="Total exportable a M3 Académicos/Admin.")
    total_m4_colaboradores: int = Field(default=0, ge=0, description="Total exportable a M4 Colaboradores.")
    total_m5_beneficiados: int = Field(default=0, ge=0, description="Total exportable a M5 Protagonistas.")
    total_exportables_nominales: int = Field(default=0, ge=0, description="Suma M2 + M3 + M4 + M5 aptos para exportar.")
    total_cuarentena: int = Field(default=0, ge=0, description="Registros en revisión retenidos por política.")
    total_cola_revision_excluidos: int = Field(default=0, ge=0, description="Registros en COLA_REVISION excluidos de matrices.")
    total_bloqueados_excluidos: int = Field(default=0, ge=0, description="Registros BLOQUEADOS excluidos incondicionalmente.")
    invariante_verificada: bool = Field(default=True, description="Garantía de conservación estricta de registros.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class PipelineActividadResultDTO(BaseModel):
    """Resultado holístico de la ejecución del pipeline integral: Ingesta -> Quality -> Routing -> Export Prep."""

    id_actividad: str = Field(..., description="UUID de la actividad procesada.")
    nombre_actividad: str = Field(..., description="Nombre de la actividad.")
    fecha_ejecucion_iso: str = Field(..., description="Timestamp ISO del procesamiento.")
    dry_run: bool = Field(default=False, description="True si fue una corrida en memoria sin escrituras.")
    
    # Fases del Pipeline
    calidad: QualityAssessmentDTO = Field(..., description="Evaluación pericial emitida por el Motor de Calidad.")
    routing: EnrutarParticipacionesResultDTO = Field(..., description="Decisiones de asignación a matrices oficiales.")
    exportacion_preparada: ExportacionPreparadaDTO = Field(..., description="Preparación de datos lista para exportadores.")

    # Balances globales
    total_participaciones_ingreso: int = Field(..., ge=0, description="Total participaciones evaluadas.")
    total_aptas: int = Field(default=0, ge=0, description="Registros operativos APTO.")
    total_en_revision: int = Field(default=0, ge=0, description="Registros operativos EN_REVISION.")
    total_bloqueadas: int = Field(default=0, ge=0, description="Registros aislados BLOQUEADO.")
    invariante_conservacion_valida: bool = Field(default=True, description="True si entrada == suma de todas las cubetas.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ExportarMatricesResultDTO(BaseModel):
    """Resultado formal del caso de uso de exportación física a libros Excel M1–M5."""

    id_actividad: str = Field(..., description="UUID de la actividad exportada.")
    modo: str = Field(default="EXPORT", description="Modo de ejecución: 'PREVIEW' o 'EXPORT'.")
    carpeta_salida: str = Field(..., description="Directorio de destino de los archivos.")
    archivos_generados: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapeo id_matriz -> ruta absoluta/relativa del archivo generado."
    )
    hashes_sha256_salida: Dict[str, str] = Field(
        default_factory=dict,
        description="Hashes SHA-256 de los archivos XLSX generados."
    )
    total_filas_exportadas_por_matriz: Dict[str, int] = Field(
        default_factory=dict,
        description="Cantidad de filas escritas en cada matriz oficial."
    )
    manifiesto_ruta: Optional[str] = Field(
        default=None,
        description="Ruta al manifiesto_exportacion.json si fue emitido."
    )
    exito: bool = Field(default=True, description="True si la exportación finalizó sin errores.")
    mensaje: str = Field(default="Exportación completada exitosamente.", description="Mensaje pericial.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
