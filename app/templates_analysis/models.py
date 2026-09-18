"""
app.templates_analysis.models

Modelos de datos inmutables para el análisis físico de plantillas oficiales (Fase 8A)
y la generación del Mapping Manifesto multidimensional (Fase 8B).
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TipoMapeoColumna(str, Enum):
    """
    Tipo semántico de relación entre una columna física de la plantilla y el modelo interno.
    """
    DIRECTO = "DIRECTO"            # Correspondencia 1:1 directa desde atributo SSOT
    DERIVADO = "DERIVADO"          # Regla institucional lógica derivada (e.g. subtipo desde categoria)
    CALCULADO = "CALCULADO"        # Métrica estadística o agregación matemática (Fase 7)
    CATALOGO = "CATALOGO"          # Requiere validación / cruce con catálogo institucional
    MANUAL = "MANUAL"              # Campo reservado para llenado humano / firmas / supervisión
    SIN_FUENTE = "SIN_FUENTE"      # Exigido por plantilla pero sin dato en fuentes originales
    PROTEGIDO = "PROTEGIDO"        # Fórmula, total preexistente o celda bloqueada que no debe modificarse
    NO_APLICA = "NO_APLICA"        # Columna auxiliar o irrelevante para el flujo en curso


class EstadoMapeo(str, Enum):
    """
    Estado de validación y certeza institucional del mapeo asignado.
    """
    VALIDADO = "VALIDADO"
    REQUIERE_REVISION = "REQUIERE_REVISION"
    SIN_FUENTE = "SIN_FUENTE"
    CATALOGO_PENDIENTE = "CATALOGO_PENDIENTE"


class CeldaProtegida(BaseModel):
    """
    Representa una celda que contiene fórmulas, encabezados o bloqueo de edición.
    """
    coordenada: str = Field(..., description="Coordenada A1 de la celda.")
    fila: int = Field(..., description="Número de fila (base 1).")
    columna: int = Field(..., description="Número de columna (base 1).")
    tipo_proteccion: str = Field(..., description="FORMULA, CABECERA o BLOQUEO_ESTRUCTURAL.")
    formula: Optional[str] = Field(default=None, description="Fórmula detectada en la celda.")
    valor_actual: Optional[str] = Field(default=None, description="Valor visible o texto de la celda.")

    model_config = {"validate_assignment": True}


class RangoCombinado(BaseModel):
    """
    Representa un bloque de celdas combinadas (Merged Cells).
    """
    rango: str = Field(..., description="Coordenadas de rango (ej. 'A1:E1').")
    celda_inicio: str = Field(..., description="Celda superior izquierda que contiene el valor.")
    celda_fin: str = Field(..., description="Celda inferior derecha del rango combinado.")
    valor_principal: Optional[str] = Field(default=None, description="Contenido textual o valor visible.")

    model_config = {"validate_assignment": True}


class ColumnaDetectada(BaseModel):
    """
    Representa una columna descubierta físicamente en la hoja de cálculo.
    """
    indice_columna: int = Field(..., description="Índice numérico base 1 (1, 2, 3...).")
    letra_columna: str = Field(..., description="Letra de la columna en Excel ('A', 'B'...).")
    encabezado_principal: str = Field(default="", description="Texto del encabezado en la fila principal.")
    subencabezados: List[str] = Field(default_factory=list, description="Textos en filas de subencabezados si existen.")
    tipo_dato_inferido: str = Field(default="str", description="Tipo de dato inferido (str, int, float, date).")

    model_config = {"validate_assignment": True}


class ZonaEscribible(BaseModel):
    """
    Delimitación de la zona segura donde se pueden escribir registros sin destruir fórmulas ni cabeceras.
    """
    fila_inicio: int = Field(..., description="Primera fila segura para inserción de datos.")
    columna_inicio: int = Field(..., description="Primera columna escribible.")
    columna_fin: int = Field(..., description="Última columna escribible.")
    fila_fin_estimada: Optional[int] = Field(default=None, description="Fila límite antes de fórmulas de pie de página.")

    model_config = {"validate_assignment": True}


class EsquemaPlantilla(BaseModel):
    """
    Resultado formal de la Inspección Física (Fase 8A) de un archivo Excel.
    """
    id_matriz: str = Field(..., description="Identificador unificado de la matriz (1 a 5).")
    nombre_matriz: str = Field(..., description="Nombre descriptivo institucional de la matriz.")
    ruta_archivo: str = Field(..., description="Ruta absoluta o relativa del archivo inspeccionado.")
    es_oficial: bool = Field(default=False, description="True si es plantilla real oficial, False si es Golden Test Fixture.")
    hojas_disponibles: List[str] = Field(default_factory=list, description="Lista de nombres de todas las hojas.")
    hojas_ocultas: List[str] = Field(default_factory=list, description="Hojas con visibilidad oculta o muy oculta.")
    hoja_inspeccionada: str = Field(..., description="Hoja analizada para este esquema.")
    max_filas: int = Field(default=0, description="Cantidad máxima de filas en la hoja.")
    max_columnas: int = Field(default=0, description="Cantidad máxima de columnas en la hoja.")
    fila_encabezados: Optional[int] = Field(default=None, description="Fila detectada para encabezados principales.")
    fila_inicio_datos: Optional[int] = Field(default=None, description="Fila calculada para el inicio de datos.")
    estado_fila_inicio: str = Field(default="DETERMINADA", description="DETERMINADA o REQUIERE_REVISION.")
    columnas_detectadas: List[ColumnaDetectada] = Field(default_factory=list, description="Columnas encontradas.")
    celdas_combinadas: List[RangoCombinado] = Field(default_factory=list, description="Rangos combinados.")
    celdas_protegidas: List[CeldaProtegida] = Field(default_factory=list, description="Celdas con fórmulas o bloqueos.")
    validaciones_datos: List[str] = Field(default_factory=list, description="Reglas DataValidation detectadas.")
    tiene_macros: bool = Field(default=False, description="True si es archivo habilitado para macros (.xlsm).")
    tiene_proteccion_hoja: bool = Field(default=False, description="True si la hoja tiene protección activa.")
    zonas_escribibles: List[ZonaEscribible] = Field(default_factory=list, description="Zonas seguras de escritura.")

    model_config = {"validate_assignment": True}


class ItemMappingManifesto(BaseModel):
    """
    Contrato individual de mapeo para una columna física detectada.
    """
    matriz: str = Field(..., description="Nombre o identificador de la matriz oficial.")
    hoja: str = Field(..., description="Hoja donde se encuentra la columna.")
    columna_letra: str = Field(..., description="Letra de columna física ('A', 'B', 'C'...).")
    columna_indice: int = Field(..., description="Índice numérico de columna (1-indexed).")
    encabezado_original: str = Field(..., description="Texto textual detectado en la plantilla física.")
    significado_interpretado: str = Field(..., description="Interpretación semántica del campo institucional.")
    campo_ssot_fuente: Optional[str] = Field(default=None, description="Atributo del modelo interno SSOT asociado.")
    tipo_mapeo: TipoMapeoColumna = Field(..., description="DIRECTO, DERIVADO, CALCULADO, CATALOGO, MANUAL, SIN_FUENTE, PROTEGIDO, NO_APLICA.")
    transformacion: Optional[str] = Field(default=None, description="Descripción de la función o regla de transformación.")
    catalogo_requerido: Optional[str] = Field(default=None, description="Nombre del catálogo requerido en config/catalogs/.")
    obligatoriedad: bool = Field(default=False, description="True si el campo no puede quedar vacío.")
    fuente_del_dato: str = Field(default="Ninguna", description="Origen de la información: Word, Asistencia, Fase6, Fase7, etc.")
    estado: EstadoMapeo = Field(default=EstadoMapeo.VALIDADO, description="Estado técnico del mapeo.")
    nivel_confianza: str = Field(default="ALTO", description="ALTO, MEDIO o BAJO.")
    observaciones: str = Field(default="", description="Notas de auditoría y directivas de protección.")

    model_config = {"validate_assignment": True}


class MappingManifesto(BaseModel):
    """
    Colección integral y auditable del mapeo físico-semántico para una matriz.
    """
    id_matriz: str = Field(..., description="Identificador unificado de la matriz.")
    nombre_matriz: str = Field(..., description="Nombre oficial institucional.")
    hoja: str = Field(..., description="Hoja objetivo.")
    items: List[ItemMappingManifesto] = Field(default_factory=list, description="Lista ordenada de contratos por columna.")
    total_columnas: int = Field(default=0, description="Total de columnas mapeadas.")
    columnas_directas: int = Field(default=0, description="Cantidad de columnas DIRECTO.")
    columnas_calculadas: int = Field(default=0, description="Cantidad de columnas CALCULADO.")
    columnas_sin_fuente: int = Field(default=0, description="Cantidad de columnas SIN_FUENTE.")
    columnas_catalogo_pendiente: int = Field(default=0, description="Cantidad de columnas CATALOGO_PENDIENTE.")

    model_config = {"validate_assignment": True}


class ReporteInspeccionPlantillas(BaseModel):
    """
    Contenedor global de auditoría de la Fase 8 (Fase 8A + Fase 8B).
    """
    total_plantillas_evaluadas: int = Field(default=0, description="Total de plantillas analizadas.")
    plantillas_reales_encontradas: int = Field(default=0, description="Total de plantillas oficiales reales.")
    plantillas_ausentes: List[str] = Field(default_factory=list, description="Lista de matrices oficiales sin plantilla en disco.")
    esquemas: Dict[str, EsquemaPlantilla] = Field(default_factory=dict, description="Esquemas de Fase 8A indexados por id_matriz.")
    manifestos: Dict[str, MappingManifesto] = Field(default_factory=dict, description="Manifestos de Fase 8B indexados por id_matriz.")
    conformidad_global: bool = Field(default=False, description="True si la inspección y mapeo se completaron satisfactoriamente.")
    timestamp: Optional[str] = Field(default=None, description="Fecha y hora de generación de la auditoría.")

    model_config = {"validate_assignment": True}
