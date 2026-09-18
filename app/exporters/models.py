"""
app.exporters.models

Modelos de datos inmutables y enums para el Motor de Exportación a Excel (Fase 9).
"""

from enum import Enum
from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class ModoExportacion(str, Enum):
    """Modo de ejecución de exportación."""
    PREVIEW = "preview"
    EXPORT = "export"


class EstatusPlantilla(str, Enum):
    """Estatus de origen de la plantilla utilizada."""
    OFICIAL_REAL = "OFICIAL_REAL"
    GOLDEN_TEST_FIXTURE_TEST_ONLY = "GOLDEN_TEST_FIXTURE_TEST_ONLY"


class EstrategiaExportacion(str, Enum):
    """Estrategia de inserción de registros en la matriz."""
    APPEND = "APPEND"
    GENERACION_DESDE_PLANTILLA = "GENERACION_DESDE_PLANTILLA"


class ModoExportacionCatalogo(str, Enum):
    """Directiva institucional para columnas con catálogo pendiente."""
    TEXTO_LITERAL_NO_HOMOLOGADO = "TEXTO_LITERAL_NO_HOMOLOGADO"
    BLOQUEAR = "BLOQUEAR"
    CELDA_VACIA = "CELDA_VACIA"


class PoliticaCatalogo(BaseModel):
    """Política institucional declarativa configurada en settings.yaml."""
    estado: str = Field(default="CATALOGO_PENDIENTE", description="Estado del catálogo.")
    requerido: bool = Field(default=False, description="Indica si la homologación es obligatoria para exportar.")
    modo_exportacion: ModoExportacionCatalogo = Field(
        default=ModoExportacionCatalogo.TEXTO_LITERAL_NO_HOMOLOGADO,
        description="Tratamiento del valor no homologado en la celda."
    )

    model_config = {"validate_assignment": True}


class TipoSinFuente(str, Enum):
    """Clasificación de columnas sin fuente en el registro."""
    SIN_FUENTE_OPCIONAL = "SIN_FUENTE_OPCIONAL"
    SIN_FUENTE_OBLIGATORIO = "SIN_FUENTE_OBLIGATORIO"


class FormulaVerificada(BaseModel):
    """
    Registro de verificación estática de fórmulas en plantilla y salida.
    Diferencia explícitamente PRESERVACIÓN ESTRUCTURAL de RECALCULACIÓN DEL RESULTADO.
    """
    coordenada: str = Field(..., description="Coordenada Excel (ej. 'I10').")
    formula: str = Field(..., description="Fórmula exacta (ej. '=SUM(I5:I9)').")
    formula_original: str = Field(default="", description="Fórmula original presente en la plantilla base.")
    formula_posterior: str = Field(default="", description="Fórmula verificada en el archivo generado tras exportación.")
    rango_referenciado: Optional[str] = Field(default=None, description="Rango de celdas referenciado por la fórmula (ej. 'I5:I9').")
    preservada: bool = Field(default=True, description="True si formula_original == formula_posterior.")
    tipo_preservacion: str = Field(
        default="PRESERVACION_ESTRUCTURAL",
        description="PRESERVACION_ESTRUCTURAL: sintaxis, operadores y celda se mantienen intactos en openpyxl sin sustitución por Python. La RECALCULACIÓN DEL RESULTADO corresponde a Microsoft Excel al abrir el archivo."
    )
    recalculacion_nota: str = Field(
        default="openpyxl preserva la definición sintáctica de la fórmula pero carece de motor de evaluación en tiempo de ejecución. La recalculación matemática es realizada por Microsoft Excel al abrir el archivo.",
        description="Aclaración técnica sobre la ausencia de recálculo dinámico en openpyxl."
    )
    no_reemplazada: bool = Field(
        default=True,
        description="True si la fórmula no fue reemplazada por un valor numérico o texto estático calculado en Python."
    )
    filas_no_invaden_rango: bool = Field(
        default=True,
        description="True si las filas de datos escritas no invaden ni sobrescriben la celda de la fórmula."
    )
    valor_evaluado_en_celda: Optional[str] = Field(default=None, description="Valor literal presente en la celda.")

    model_config = {"validate_assignment": True}


class ResultadoMatrizExportada(BaseModel):
    """Resumen de exportación de una matriz individual."""
    id_matriz: str = Field(..., description="Identificador interno (matriz_1 a matriz_5).")
    nombre_matriz: str = Field(..., description="Nombre formal institucional.")
    nombre_archivo: str = Field(..., description="Nombre del archivo generado.")
    ruta_salida: str = Field(..., description="Ruta absoluta o relativa del archivo generado.")
    plantilla_utilizada: str = Field(..., description="Nombre del archivo de plantilla base.")
    estatus_plantilla: EstatusPlantilla = Field(..., description="OFICIAL_REAL o GOLDEN_TEST_FIXTURE_TEST_ONLY.")
    sha256_plantilla_antes: str = Field(..., description="Hash SHA-256 de la plantilla antes de procesar.")
    sha256_plantilla_despues: str = Field(..., description="Hash SHA-256 de la plantilla tras procesar.")
    plantilla_inalterada: bool = Field(default=True, description="True si sha256_antes == sha256_despues.")
    total_filas_escritas: int = Field(default=0, description="Cantidad de filas de datos escritas.")
    total_registros_historicos_preservados: int = Field(
        default=0, description="Cantidad de registros históricos preexistentes conservados intactos."
    )
    estrategia_exportacion: Optional[EstrategiaExportacion] = Field(
        default=None, description="Estrategia utilizada: APPEND o GENERACION_DESDE_PLANTILLA."
    )
    fila_inicio: Optional[int] = Field(default=None, description="Primera fila con datos escritos.")
    fila_fin: Optional[int] = Field(default=None, description="Última fila con datos escritos.")
    celdas_con_formula_preservadas: List[FormulaVerificada] = Field(
        default_factory=list,
        description="Fórmulas verificadas post-escritura en el archivo resultante."
    )
    columnas_sin_fuente_respetadas: List[str] = Field(
        default_factory=list,
        description="Columnas dejadas en blanco por regla de no invención."
    )
    columnas_catalogo_no_homologadas: List[str] = Field(
        default_factory=list,
        description="Columnas exportadas con texto literal marcadas como no homologadas."
    )
    advertencias: List[str] = Field(
        default_factory=list,
        description="Advertencias operativas acumuladas durante la exportación."
    )
    exitosa: bool = Field(default=True, description="True si la matriz se exportó sin violaciones.")

    model_config = {"validate_assignment": True}


class ManifiestoExportacion(BaseModel):
    """
    Manifiesto institucional de exportación (SSOT del resultado de exportación).
    Permite auditar de forma matemática la integridad de la entrega.
    """
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Identificador único universal de ejecución.")
    estado_ejecucion: str = Field(default="COMPLETADA", description="Estado operativo de la ejecución (Fase 10).")
    fecha_exportacion: str = Field(..., description="Marca temporal ISO-8601 de la exportación.")
    modo: ModoExportacion = Field(..., description="Modo ejecutado: PREVIEW o EXPORT.")
    version_sistema: str = Field(default="0.1.0", description="Versión del sistema.")
    es_oficial: bool = Field(
        default=False,
        description="True si y solo si todas las 5 matrices usaron plantillas OFICIAL_REAL en modo EXPORT."
    )
    total_matrices: int = Field(default=5, description="Cantidad de matrices oficiales procesadas.")
    total_asistencias_enrutadas: int = Field(default=0, description="Total de participaciones enrutadas.")
    total_filas_detalle_escritas: int = Field(
        default=0,
        description="Suma de filas escritas en Matrices 2, 3, 4 y 5."
    )
    invariante_filas_valida: bool = Field(
        default=False,
        description="True si total_asistencias_enrutadas == total_filas_detalle_escritas."
    )
    invariante_conservacion_valida: bool = Field(
        default=False,
        description="True si filas de Matriz 1 coinciden exactamente con total de actividades evaluadas."
    )
    plantillas_todas_oficiales: bool = Field(
        default=False,
        description="True si las 5 plantillas son OFICIAL_REAL."
    )
    hashes_plantillas_coinciden: bool = Field(
        default=True,
        description="True si ninguna plantilla base sufrió alteraciones (sha_antes == sha_despues en todas)."
    )
    matrices: Dict[str, ResultadoMatrizExportada] = Field(
        default_factory=dict,
        description="Resultados individuales indexados por id_matriz."
    )
    observaciones_generales: List[str] = Field(
        default_factory=list,
        description="Observaciones institucionales consolidadas."
    )
    ruta_manifiesto: Optional[str] = Field(
        default=None,
        description="Ruta donde se serializó este manifiesto en disco."
    )

    model_config = {"validate_assignment": True}
