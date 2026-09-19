"""app.application.dto.batch_dtos

Data Transfer Objects para el procesamiento por lote (batch) de carpetas
con documentos Word de actividades institucionales.

Reglas arquitectónicas:
- Capa Application únicamente. No importa sqlite3, python-docx ni openpyxl.
- No mezclar con entidades de dominio; los DTOs son de transporte puro.
- BatchArchivoResultadoDTO: estado individual por archivo DOCX.
- BatchResultadoDTO: resumen consolidado de la ejecución del lote.
- PipelineDesdeWordResultDTO: encadenamiento Ingesta→Pipeline para un DOCX.
- GAP-3 documentado: la detección de posibles duplicados es heurística,
  NO idempotencia formal. No afirmar que el sistema es idempotente.

Decisiones aprobadas en Bloque 3:
- P-01: Exportación consolidada al final del lote (ExportarMatricesPeriodoUseCase).
- P-02: M2–M5 como plantillas limpias cuando no existen participantes nominales.
- P-03: Advertir posibles duplicados sin bloquear ni modificar schema.
- P-04: Manifest JSON externo persistente.
- P-07: Subcarpeta por batch_id en destino de exportación.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------

EstadoArchivoBatch = Literal["ACEPTADO", "RECHAZADO", "FALLIDO", "CON_ADVERTENCIAS"]


# ---------------------------------------------------------------------------
# DTO por archivo individual
# ---------------------------------------------------------------------------

class BatchArchivoResultadoDTO(BaseModel):
    """Resultado de procesamiento de un único archivo DOCX dentro del lote.

    - ACEPTADO: ingesta exitosa (con o sin exportación posterior).
    - RECHAZADO: tipo incompatible (INFORME_SEMANAL, NO_COMPATIBLE) o
                 extracción sin datos mínimos.
    - FALLIDO: error técnico irrecuperable durante ingesta o pipeline.
    - CON_ADVERTENCIAS: ingesta OK pero pipeline/export con incidencias no bloqueantes.
    """
    nombre_archivo: str = Field(
        ...,
        description="Nombre base del archivo DOCX procesado."
    )
    ruta_archivo: str = Field(
        ...,
        description="Ruta absoluta o relativa al archivo DOCX procesado."
    )
    estado: EstadoArchivoBatch = Field(
        ...,
        description="Estado resultante del procesamiento: ACEPTADO, RECHAZADO, FALLIDO o CON_ADVERTENCIAS."
    )
    tipo_documento: Optional[str] = Field(
        default=None,
        description="Clasificación del documento: INFORME_ACTIVIDAD, INFORME_SEMANAL, NO_COMPATIBLE, DESCONOCIDO."
    )
    id_actividad: Optional[str] = Field(
        default=None,
        description="UUID de la actividad creada en SQLite. None si no fue persistida."
    )
    motivo_rechazo: Optional[str] = Field(
        default=None,
        description="Descripción del motivo de rechazo cuando estado=RECHAZADO."
    )
    advertencias: List[str] = Field(
        default_factory=list,
        description=(
            "Lista de advertencias no bloqueantes. Incluye la advertencia heurística de "
            "posible duplicado (GAP-3). NO implica idempotencia garantizada."
        )
    )
    errores: List[str] = Field(
        default_factory=list,
        description="Lista de errores técnicos registrados durante el procesamiento."
    )
    evidencias_registradas: int = Field(
        default=0,
        ge=0,
        description="Cantidad de evidencias persistidas en SQLite para esta actividad."
    )
    # --- Resultado del pipeline (solo si ingesta OK y pipeline ejecutado) ---
    calidad_estado: Optional[str] = Field(
        default=None,
        description="Estado sintético del motor de calidad: CONFORME, CON_OBSERVACIONES, REQUIERE_ACCION, BLOQUEADO."
    )
    total_hallazgos_calidad: int = Field(
        default=0,
        ge=0,
        description="Cantidad de hallazgos emitidos por QualityValidator para esta actividad."
    )
    total_participaciones_enrutadas: int = Field(
        default=0,
        ge=0,
        description="Total de participaciones enrutadas. Puede ser 0 cuando el DOCX no tiene nominales (comportamiento esperado)."
    )
    posible_duplicado_advertido: bool = Field(
        default=False,
        description=(
            "True si la heurística de GAP-3 detectó que el nombre de archivo ya existe en el lote "
            "o en SQLite. Advertencia únicamente; NO bloquea ni garantiza identidad documental."
        )
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


# ---------------------------------------------------------------------------
# DTO de resultado de pipeline por DOCX (thin wrapper)
# ---------------------------------------------------------------------------

class PipelineDesdeWordResultDTO(BaseModel):
    """Resultado del flujo encadenado Ingesta → Pipeline para un único archivo DOCX.

    Producido por ProcesarPipelineDesdeWordUseCase.
    La exportación física se realiza de forma consolidada al final del lote
    (decisión P-01), por lo que este DTO no incluye resultados de export.
    """
    nombre_archivo: str = Field(
        ...,
        description="Nombre base del archivo DOCX procesado."
    )
    exitoso: bool = Field(
        ...,
        description="True si la ingesta y el pipeline completaron sin errores bloqueantes."
    )
    id_actividad: Optional[str] = Field(
        default=None,
        description="UUID de la actividad persistida. None si la ingesta no fue exitosa."
    )
    tipo_documento: Optional[str] = Field(
        default=None,
        description="Clasificación del documento extraído."
    )
    # Resultados de ingesta
    ingesta_exitosa: bool = Field(
        default=False,
        description="True si la ingesta en SQLite completó correctamente."
    )
    evidencias_registradas: int = Field(
        default=0,
        ge=0,
        description="Evidencias persistidas durante la ingesta."
    )
    motivo_rechazo: Optional[str] = Field(
        default=None,
        description="Motivo de rechazo si ingesta_exitosa=False."
    )
    # Resultados del pipeline
    pipeline_ejecutado: bool = Field(
        default=False,
        description="True si ProcesarPipelineActividadUseCase fue invocado."
    )
    calidad_estado: Optional[str] = Field(
        default=None,
        description="Estado del motor de calidad. None si pipeline no fue ejecutado."
    )
    total_hallazgos: int = Field(
        default=0,
        ge=0,
        description="Hallazgos Q-01..Q-20 emitidos."
    )
    total_participaciones: int = Field(
        default=0,
        ge=0,
        description="Participaciones enrutadas (0 es comportamiento esperado en flujo Word)."
    )
    # Advertencias y errores
    advertencias: List[str] = Field(
        default_factory=list,
        description="Advertencias no bloqueantes del proceso."
    )
    errores: List[str] = Field(
        default_factory=list,
        description="Errores técnicos registrados."
    )
    posible_duplicado_advertido: bool = Field(
        default=False,
        description="True si la heurística GAP-3 detectó coincidencia de nombre de archivo."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

    def to_batch_archivo_resultado(self, ruta_archivo: str) -> "BatchArchivoResultadoDTO":
        """Convierte este DTO en un BatchArchivoResultadoDTO para consolidación en el lote."""
        if not self.ingesta_exitosa:
            estado: EstadoArchivoBatch = (
                "RECHAZADO"
                if self.motivo_rechazo or (self.tipo_documento and self.tipo_documento != "INFORME_ACTIVIDAD")
                else "FALLIDO"
            )
        elif self.errores:
            estado = "FALLIDO"
        elif self.advertencias or self.posible_duplicado_advertido:
            estado = "CON_ADVERTENCIAS"
        else:
            estado = "ACEPTADO"

        return BatchArchivoResultadoDTO(
            nombre_archivo=self.nombre_archivo,
            ruta_archivo=str(ruta_archivo),
            estado=estado,
            tipo_documento=self.tipo_documento,
            id_actividad=self.id_actividad,
            motivo_rechazo=self.motivo_rechazo,
            evidencias_registradas=self.evidencias_registradas,
            advertencias=list(self.advertencias),
            errores=list(self.errores),
            calidad_estado=self.calidad_estado,
            total_hallazgos_calidad=self.total_hallazgos,
            total_participaciones_enrutadas=self.total_participaciones,
            posible_duplicado_advertido=self.posible_duplicado_advertido,
        )


# ---------------------------------------------------------------------------
# DTO de resultado del lote completo
# ---------------------------------------------------------------------------

class BatchResultadoDTO(BaseModel):
    """Resultado consolidado de la ejecución del lote completo de archivos DOCX.

    Producido por IngestarCarpetaWordUseCase al finalizar el procesamiento
    de todos los archivos encontrados en la carpeta origen.

    Importante sobre GAP-3:
      El campo `actividades_con_posible_duplicado` contiene IDs de actividades
      para las cuales la heurística detectó un posible nombre duplicado.
      Esto NO es idempotencia formal. El schema v001 no tiene restricción UNIQUE
      para documentos; la detección es meramente informativa.
    """
    batch_id: str = Field(
        ...,
        description="Identificador único UUIDv4 del lote de procesamiento."
    )
    carpeta_origen: str = Field(
        ...,
        description="Ruta absoluta de la carpeta DOCX procesada."
    )
    patron_glob: str = Field(
        default="*.docx",
        description="Patrón de búsqueda utilizado para encontrar archivos."
    )
    timestamp_inicio: str = Field(
        ...,
        description="Timestamp ISO 8601 del inicio del procesamiento."
    )
    timestamp_fin: str = Field(
        default="",
        description="Timestamp ISO 8601 del fin del procesamiento."
    )
    dry_run: bool = Field(
        default=False,
        description="True si el lote fue ejecutado en modo simulación (cero escrituras)."
    )
    # --- Contadores ---
    archivos_encontrados: int = Field(
        default=0,
        ge=0,
        description="Total de archivos coincidentes con el patrón en la carpeta."
    )
    archivos_aceptados: int = Field(
        default=0,
        ge=0,
        description="Archivos procesados con ingesta exitosa (ACEPTADO)."
    )
    archivos_rechazados: int = Field(
        default=0,
        ge=0,
        description="Archivos rechazados por tipo incompatible o sin datos mínimos."
    )
    archivos_con_advertencias: int = Field(
        default=0,
        ge=0,
        description="Archivos con ingesta OK pero con incidencias no bloqueantes."
    )
    archivos_fallidos: int = Field(
        default=0,
        ge=0,
        description="Archivos con error técnico irrecuperable durante el procesamiento."
    )
    # --- Resultados ---
    actividades_creadas: List[str] = Field(
        default_factory=list,
        description="UUIDs de actividades persistidas exitosamente en SQLite."
    )
    evidencias_registradas_total: int = Field(
        default=0,
        ge=0,
        description="Total de evidencias persistidas en SQLite durante el lote."
    )
    actividades_con_posible_duplicado: List[str] = Field(
        default_factory=list,
        description=(
            "UUIDs de actividades para las cuales la heurística GAP-3 detectó un posible "
            "nombre de archivo duplicado. ADVERTENCIA: no es garantía de identidad documental. "
            "El schema v001 no tiene restricción UNIQUE por documento."
        )
    )
    # --- Pipeline consolidado ---
    pipeline_ejecutado: bool = Field(
        default=False,
        description="True si el pipeline Quality+Routing fue ejecutado para el lote."
    )
    total_hallazgos_calidad: int = Field(
        default=0,
        ge=0,
        description="Total de hallazgos Q-01..Q-20 emitidos en todo el lote."
    )
    total_participaciones_enrutadas: int = Field(
        default=0,
        ge=0,
        description="Total de participaciones enrutadas (0 es esperado en flujo Word sin nominales)."
    )
    # --- Exportación consolidada (P-01: al final del lote) ---
    exportacion_ejecutada: bool = Field(
        default=False,
        description="True si la exportación consolidada de matrices fue ejecutada."
    )
    matrices_generadas: Dict[str, str] = Field(
        default_factory=dict,
        description="Rutas de los archivos XLSX generados, indexadas por clave de matriz (matriz_1..matriz_5)."
    )
    hashes_matrices: Dict[str, str] = Field(
        default_factory=dict,
        description="Hashes SHA-256 de las matrices oficiales XLSX generadas."
    )
    carpeta_batch_salida: Optional[str] = Field(
        default=None,
        description="Subcarpeta de salida exclusiva del lote: output/<batch_id>/."
    )
    # --- Trazabilidad ---
    manifest_path: Optional[str] = Field(
        default=None,
        description="Ruta del manifest JSON externo generado para este lote."
    )
    invariante_ok: bool = Field(
        default=True,
        description=(
            "True si el lote no tuvo errores técnicos en ningún archivo. "
            "False si al menos un archivo resultó en estado FALLIDO."
        )
    )
    errores_criticos: List[str] = Field(
        default_factory=list,
        description="Errores técnicos irrecuperables registrados a nivel de lote."
    )
    advertencias_lote: List[str] = Field(
        default_factory=list,
        description="Advertencias globales del lote, incluyendo resumen de GAP-3."
    )
    # --- Detalle por archivo ---
    resultados_por_archivo: List[BatchArchivoResultadoDTO] = Field(
        default_factory=list,
        description="Resultado detallado para cada archivo procesado en el lote."
    )

    model_config = {
        "frozen": False,  # mutable durante construcción por el use case
        "str_strip_whitespace": True,
        "arbitrary_types_allowed": False,
    }
