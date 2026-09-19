"""app.application.dto.word_extraction_dtos

DTOs de transporte para la extracción estructurada de actividades desde documentos Word (.docx).

Reglas arquitectónicas:
- La capa Application define las estructuras de datos desacopladas de librerías físicas (sin python-docx).
- No mezclar con entidades SQLite ni realizar persistencia dentro del DTO.
- No inferir participantes individuales a partir de cifras cuantitativas de la Tabla 2.
- Total Cuantitativo != Participantes Nominales.
- Preservar advertencias de extracción (DETECTAR != CORREGIR).
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TipoDocumentoWord(str, Enum):
    """Clasificación del tipo de documento Word institucional procesado."""
    INFORME_ACTIVIDAD = "INFORME_ACTIVIDAD"
    INFORME_SEMANAL = "INFORME_SEMANAL"
    NO_COMPATIBLE = "NO_COMPATIBLE"
    DESCONOCIDO = "DESCONOCIDO"


class TipoEvidenciaWord(str, Enum):
    """Tipo de evidencia gráfica o anexo detectado dentro del documento Word."""
    LISTA_FIRMADA = "LISTA_FIRMADA"
    FOTOGRAFIA = "FOTOGRAFIA"
    OTRO = "OTRO"


class FichaTecnicaDTO(BaseModel):
    """Datos extraídos de la Tabla 1: Ficha Técnica Institucional (19 filas x 2 cols)."""

    actividad_general: Optional[str] = Field(
        default=None,
        description="Nombre oficial de la actividad (Tabla 1, Fila 1)."
    )
    linea_estrategica: Optional[str] = Field(
        default=None,
        description="Línea estratégica o eje institucional (Tabla 1, Fila 2)."
    )
    indicador: Optional[str] = Field(
        default=None,
        description="Indicador al que aporta la actividad (Tabla 1, Fila 3)."
    )
    lugar: Optional[str] = Field(
        default=None,
        description="Lugar de ejecución, sede o recinto (Tabla 1, Fila 4)."
    )
    fecha_realizacion: Optional[str] = Field(
        default=None,
        description="Fecha textual de realización declarada en la ficha técnica."
    )
    fecha_iso: Optional[str] = Field(
        default=None,
        description="Fecha normalizada en formato ISO (AAAA-MM-DD) si la conversión fue inequívoca."
    )
    total_participantes_declarado: Optional[int] = Field(
        default=None,
        description="Total de participantes declarado textualmente en la ficha técnica."
    )
    masculino_declarado: Optional[int] = Field(
        default=None,
        description="Total de varones declarado textualmente en la ficha técnica."
    )
    femenino_declarado: Optional[int] = Field(
        default=None,
        description="Total de mujeres declarado textualmente en la ficha técnica."
    )
    distribucion_etnica_declarada: Dict[str, int] = Field(
        default_factory=dict,
        description="Desglose étnico extraído del texto de la ficha técnica."
    )
    resultados: List[str] = Field(
        default_factory=list,
        description="Lista de resultados y logros institucionales (Tabla 1, Filas 12-14)."
    )
    dificultades: List[str] = Field(
        default_factory=list,
        description="Lista de principales dificultades registradas (Tabla 1, Filas 15-16)."
    )
    acuerdos: List[str] = Field(
        default_factory=list,
        description="Lista de acuerdos y compromisos adoptados (Tabla 1, Filas 17-19)."
    )
    mapa_etiquetas_crudo: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mapeo completo de todos los pares Etiqueta -> [Valores] encontrados en la Tabla 1."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class MatrizCuantitativaDTO(BaseModel):
    """Datos agregados de la Tabla 2: Matriz Cuantitativa Desagregada (3 filas x 15 cols).

    REGLA CRÍTICA:
    TOTAL CUANTITATIVO != PARTICIPANTES NOMINALES.
    Esta estructura almacena únicamente las cifras estadísticas declaradas en la actividad.
    NO genera objetos Person ni filas de asistencia individuales.
    """

    actividad_declarada: Optional[str] = Field(
        default=None,
        description="Texto de la actividad según la cabecera de la Tabla 2."
    )
    femenino: Optional[int] = Field(
        default=None,
        description="Cantidad total de participantes de sexo femenino (columna F)."
    )
    masculino: Optional[int] = Field(
        default=None,
        description="Cantidad total de participantes de sexo masculino (columna M)."
    )
    total: Optional[int] = Field(
        default=None,
        description="Total global de participantes declarado en la matriz cuantitativa."
    )
    estudiantes: Optional[int] = Field(
        default=None,
        description="Total de estudiantes participantes."
    )
    docentes: Optional[int] = Field(
        default=None,
        description="Total de docentes participantes."
    )
    trabajadores_administrativos: Optional[int] = Field(
        default=None,
        description="Total de personal administrativo participante."
    )
    otros: Optional[int] = Field(
        default=None,
        description="Total de otros participantes (colaboradores / comunidad / beneficiarios)."
    )
    distribucion_etnica: Dict[str, int] = Field(
        default_factory=dict,
        description="Totales por grupo étnico (Creole, Mestizo, Miskito, Rama, Ulwa, Mayangna, Garífuna)."
    )
    columnas_detectadas: List[str] = Field(
        default_factory=list,
        description="Lista de nombres de columnas identificadas en la cabecera."
    )
    discrepancia_suma_genero: bool = Field(
        default=False,
        description="Indica si total != femenino + masculino (DETECTAR != CORREGIR)."
    )
    discrepancia_suma_estamento: bool = Field(
        default=False,
        description="Indica si total != estudiantes + docentes + administrativos + otros."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class EvidenciaDetectadaDTO(BaseModel):
    """Representa una evidencia gráfica o anexo detectado dentro del documento."""

    tipo: TipoEvidenciaWord = Field(
        ...,
        description="Tipo de evidencia inferido por ubicación de sección (LISTA_FIRMADA, FOTOGRAFIA, OTRO)."
    )
    seccion_origen: str = Field(
        ...,
        description="Nombre de la sección o párrafo donde se detectó (ej. 'Anexo 2. Lista de Asistencia')."
    )
    indice_imagen: int = Field(
        ...,
        description="Índice secuencial de la imagen dentro del paquete Word."
    )
    nombre_archivo_imagen: Optional[str] = Field(
        default=None,
        description="Identificador interno o nombre de relación (ej. 'image1.png')."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class EvidenciasAnexosDTO(BaseModel):
    """Consolidado de evidencias gráficas y anexos detectados en el archivo."""

    conteo_total_imagenes: int = Field(
        default=0,
        description="Número total de imágenes incrustadas en el archivo Word."
    )
    imagenes_asistencia_count: int = Field(
        default=0,
        description="Número de imágenes vinculadas al Anexo 2 (Lista de Asistencia escaneada)."
    )
    imagenes_fotografia_count: int = Field(
        default=0,
        description="Número de imágenes vinculadas al Anexo 3 (Fotografías del evento)."
    )
    evidencias: List[EvidenciaDetectadaDTO] = Field(
        default_factory=list,
        description="Colección de evidencias individuales detectadas."
    )
    tiene_anexo_asistencia: bool = Field(
        default=False,
        description="Verdadero si el documento contiene sección de Lista de Asistencia."
    )
    tiene_anexo_fotografias: bool = Field(
        default=False,
        description="Verdadero si el documento contiene sección de Fotografías."
    )

    model_config = {
        "frozen": True,
    }


class NarrativaSeccionesDTO(BaseModel):
    """Contenido narrativo textual de las secciones principales del informe."""

    objetivo_general: Optional[str] = Field(
        default=None,
        description="Objetivo general extraído de la Sección 2: Objetivo de la Actividad."
    )
    objetivos_especificos: List[str] = Field(
        default_factory=list,
        description="Objetivos específicos numerados (ej. 2.1, 2.2)."
    )
    diseno_metodologico: Optional[str] = Field(
        default=None,
        description="Texto explicativo del diseño metodológico y pedagogía aplicada."
    )
    desarrollo_actividad: Optional[str] = Field(
        default=None,
        description="Narrativa del desarrollo cronológico de la actividad."
    )
    conclusiones: List[str] = Field(
        default_factory=list,
        description="Conclusiones alcanzadas al término del evento."
    )
    recomendaciones: List[str] = Field(
        default_factory=list,
        description="Recomendaciones operativas o técnicas formuladas."
    )
    enlaces_divulgacion: List[str] = Field(
        default_factory=list,
        description="URLs de publicaciones en redes sociales o portal web de la actividad."
    )

    model_config = {
        "frozen": True,
    }


class DiagnosticoExtraccionDTO(BaseModel):
    """Diagnóstico técnico del proceso de lectura y compatibilidad del documento."""

    es_valido: bool = Field(
        default=False,
        description="True si el archivo fue leído y contiene la estructura institucional mínima."
    )
    tipo_documento: TipoDocumentoWord = Field(
        default=TipoDocumentoWord.DESCONOCIDO,
        description="Clasificación del documento."
    )
    compatible_flujo_principal: bool = Field(
        default=False,
        description="True si el documento califica como actividad procesable hacia SQLite y M1."
    )
    tabla_1_encontrada: bool = Field(
        default=False,
        description="True si se identificó y procesó la Ficha Técnica (Tabla 1)."
    )
    tabla_2_encontrada: bool = Field(
        default=False,
        description="True si se identificó y procesó la Matriz Cuantitativa (Tabla 2)."
    )
    advertencias: List[str] = Field(
        default_factory=list,
        description="Observaciones no bloqueantes (ej. discrepancias aritméticas en origen, fechas no normalizadas)."
    )
    errores: List[str] = Field(
        default_factory=list,
        description="Errores críticos que impidieron la lectura (ej. archivo corrupto, formato no soportado)."
    )

    model_config = {
        "frozen": True,
    }


class WordActivityExtractionResultDTO(BaseModel):
    """Resultado integral estructurado de la extracción de una actividad Word.

    Este DTO es el producto oficial del puerto IWordActivityExtractor.
    """

    ruta_archivo: Optional[str] = Field(
        default=None,
        description="Ruta absoluta o relativa del archivo procesado."
    )
    nombre_archivo: str = Field(
        ...,
        description="Nombre del archivo procesado (con extensión .docx)."
    )
    hash_sha256: Optional[str] = Field(
        default=None,
        description="Hash criptográfico SHA-256 del archivo procesado."
    )
    tamano_bytes: int = Field(
        default=0,
        description="Tamaño físico del archivo en bytes."
    )
    diagnostico: DiagnosticoExtraccionDTO = Field(
        ...,
        description="Diagnóstico técnico de validación y compatibilidad."
    )
    ficha_tecnica: Optional[FichaTecnicaDTO] = Field(
        default=None,
        description="Datos estructurados de la Ficha Técnica (Tabla 1)."
    )
    matriz_cuantitativa: Optional[MatrizCuantitativaDTO] = Field(
        default=None,
        description="Cifras agregadas de la Matriz Cuantitativa (Tabla 2)."
    )
    narrativa: Optional[NarrativaSeccionesDTO] = Field(
        default=None,
        description="Secciones narrativas (Objetivo, Metodología, Desarrollo, etc.)."
    )
    evidencias: Optional[EvidenciasAnexosDTO] = Field(
        default=None,
        description="Evidencias gráficas e imágenes de listas de firmas detectadas."
    )

    model_config = {
        "frozen": True,
    }


class IngestaActividadWordResultDTO(BaseModel):
    """Resultado estructurado de la ingesta de un documento Word de actividad hacia SQLite."""

    exitoso: bool = Field(
        ...,
        description="True si la actividad fue extraída y persistida exitosamente en SQLite."
    )
    id_actividad: Optional[str] = Field(
        default=None,
        description="UUID de la actividad persistida en SQLite si la ingesta fue exitosa."
    )
    nombre_archivo: str = Field(
        ...,
        description="Nombre del archivo procesado."
    )
    ruta_archivo: Optional[str] = Field(
        default=None,
        description="Ruta física del archivo procesado."
    )
    tipo_documento: TipoDocumentoWord = Field(
        ...,
        description="Tipo de documento detectado por el extractor."
    )
    compatible_flujo_principal: bool = Field(
        ...,
        description="Indica si el documento califica para el flujo principal hacia SQLite."
    )
    total_participantes_declarado: Optional[int] = Field(
        default=None,
        description="Cifra cuantitativa agregada declarada en la actividad (Tabla 2 / Tabla 1)."
    )
    evidencias_registradas_count: int = Field(
        default=0,
        description="Número de evidencias compatibles registradas y vinculadas en SQLite."
    )
    motivo_rechazo: Optional[str] = Field(
        default=None,
        description="Razón explícita en caso de no ser compatible o no ser procesable."
    )
    advertencias: List[str] = Field(
        default_factory=list,
        description="Advertencias técnicas y discrepancias no bloqueantes observadas."
    )
    errores: List[str] = Field(
        default_factory=list,
        description="Errores críticos que impidieron la ingesta o persistencia."
    )
    extraction_dto: Optional[WordActivityExtractionResultDTO] = Field(
        default=None,
        description="DTO original producido por IWordActivityExtractor."
    )

    model_config = {
        "frozen": True,
    }

