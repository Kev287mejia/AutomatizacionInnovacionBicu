"""
app.audit.models

Modelos de datos formales para la capa de Auditoría, Historial y Manifiestos (Fase 10).
Provee estructuras inmutables para registrar evidencias de ejecución, trazabilidad,
hashes criptográficos de entrada y salida, preservación de fórmulas y control de integridad.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class EstadoEjecucion(str, Enum):
    """Estados explícitos del ciclo de vida de una ejecución institucional."""
    INICIADA = "INICIADA"
    PROCESANDO = "PROCESANDO"
    COMPLETADA = "COMPLETADA"
    COMPLETADA_CON_REVISION = "COMPLETADA_CON_REVISION"
    FALLIDA = "FALLIDA"
    ROLLBACK = "ROLLBACK"


class MetadatosEntrada(BaseModel):
    """Evidencia de integridad de un archivo que ingresa al procesamiento."""
    nombre: str = Field(..., description="Nombre del archivo de entrada.")
    ruta_relativa: str = Field(..., description="Ruta relativa dentro del repositorio/sistema.")
    tipo: str = Field(..., description="Tipo conceptual: 'informe_word', 'asistencia_fisica', 'plantilla_base', etc.")
    tamano_bytes: int = Field(..., description="Tamaño físico del archivo en bytes.")
    sha256: str = Field(..., description="Hash criptográfico SHA-256 de verificación.")
    fecha_modificacion: Optional[str] = Field(default=None, description="Marca temporal ISO de última modificación en disco.")

    model_config = {"validate_assignment": True}


class MetadatosSalida(BaseModel):
    """Evidencia de integridad de un entregable generado por el sistema."""
    nombre: str = Field(..., description="Nombre del archivo generado.")
    tipo: str = Field(..., description="Tipo de archivo: 'matriz_excel', 'manifiesto_json', 'resumen_markdown'.")
    tamano_bytes: int = Field(..., description="Tamaño físico del entregable en bytes.")
    sha256: str = Field(..., description="Hash criptográfico SHA-256 del entregable final.")
    matriz: Optional[str] = Field(default=None, description="Identificador de matriz asociada (ej. 'matriz_1'..'matriz_5').")
    registros_generados: int = Field(default=0, description="Cantidad de registros o filas de datos escritas.")

    model_config = {"validate_assignment": True}


class AuditoriaM5(BaseModel):
    """Auditoría de integridad y regla de cero destrucción en la Matriz 5 (Beneficiados)."""
    registros_historicos_antes: int = Field(default=32, description="Registros históricos previos en la plantilla base.")
    registros_nuevos: int = Field(default=0, description="Nuevos beneficiarios añadidos en esta ejecución.")
    registros_historicos_preservados: int = Field(default=32, description="Registros históricos confirmados intactos.")
    total_despues: int = Field(default=32, description="Total de registros en la matriz tras la exportación.")
    celdas_comparadas: int = Field(default=1696, description="Total de celdas históricas comparadas celda por celda.")
    diferencias: int = Field(default=0, description="Total de discrepancias detectadas con la plantilla original.")
    resultado_cero_destruccion: bool = Field(default=True, description="True si diferencias == 0 y históricos conservados.")
    estrategia: str = Field(default="APPEND", description="Estrategia oficial de exportación de M5.")

    model_config = {"validate_assignment": True}


class AuditoriaTabla(BaseModel):
    """Auditoría de sincronización dinámica de tablas estructuradas (Tabla1)."""
    nombre_tabla: str = Field(default="Tabla1", description="Nombre de la tabla Excel.")
    ref_antes: str = Field(..., description="Rango de referencia original en la plantilla.")
    ref_despues: str = Field(..., description="Rango de referencia tras la exportación.")
    auto_filter_antes: Optional[str] = Field(default=None, description="Rango autoFilter original.")
    auto_filter_despues: Optional[str] = Field(default=None, description="Rango autoFilter resultante.")
    sincronizada_correctamente: bool = Field(default=True, description="True si la tabla mantiene estructura íntegra.")
    resultado: str = Field(default="SINCRONIZADA", description="Estado de la auditoría de tabla.")

    model_config = {"validate_assignment": True}


class AuditoriaFormulaColumna(BaseModel):
    """Auditoría de preservación estructural de fórmulas en columnas críticas."""
    matriz: str = Field(..., description="Matriz auditada (ej. 'matriz_1' a 'matriz_5').")
    columna: int = Field(..., description="Índice de columna base 1.")
    nombre_columna: str = Field(..., description="Nombre del campo o encabezado institucional.")
    formula_esperada: str = Field(..., description="Patrón o fórmula institucional requerida.")
    cantidad_verificada: int = Field(..., description="Cantidad de celdas comprobadas con la fórmula.")
    cantidad_incorrecta: int = Field(default=0, description="Celdas con fórmula rota o convertida a valor estático.")
    resultado: str = Field(default="PRESERVADA_ESTRUCTURAL", description="Resultado de la verificación.")

    model_config = {"validate_assignment": True}


class TrazaParticipacion(BaseModel):
    """
    Trazabilidad unívoca de una participación individual a través de todo el ciclo de vida.
    Permite reconstruir el camino: Entrada -> Activity/Person -> Routing/Validation -> Salida Excel.
    No duplica información sensible innecesaria (Regla 11).
    """
    id_participacion: str = Field(..., description="Identificador único inmutable de la participación.")
    id_persona_interno: str = Field(..., description="Identificador único interno de la persona (UUID).")
    id_actividad: str = Field(..., description="Identificador único de la actividad asociada.")
    categoria_origen: str = Field(..., description="Categoría declarada en la fuente (Estudiante, No Docente, etc.).")
    matriz_destino: str = Field(..., description="Matriz oficial de destino asignada por el router.")
    subtipo_institucional: str = Field(default="NO_APLICA", description="Subtipo institucional (Docente, Administrativo, etc.).")
    estado_operativo: str = Field(..., description="Estado operativo de control: APTO, EN_REVISION, BLOQUEADO.")
    motivo_enrutamiento: str = Field(..., description="Regla o motivo institucional que determinó el destino.")
    codigos_validacion: List[str] = Field(default_factory=list, description="Códigos de hallazgos emitidos en validación.")
    fuente_origen: str = Field(..., description="Fuente de extracción de la participación.")
    fila_exportada: Optional[int] = Field(default=None, description="Número de fila exacta en la matriz Excel generada.")
    archivo_exportado: Optional[str] = Field(default=None, description="Nombre del archivo Excel oficial generado.")

    model_config = {"validate_assignment": True}


class EventoAuditoria(BaseModel):
    """Registro estructurado de eventos, advertencias, fallos y revisiones."""
    codigo: str = Field(..., description="Código estandarizado del evento (ej. VAL_*, RISK_*, ERR_*).")
    severidad: str = Field(..., description="Nivel de severidad: 'INFO', 'WARNING', 'REVISION', 'ERROR', 'RIESGO'.")
    mensaje: str = Field(..., description="Descripción detallada del evento u observación.")
    entidad_afectada: Optional[str] = Field(default=None, description="Entidad u objeto relacionado (Person, Table, etc.).")
    id_referencia: Optional[str] = Field(default=None, description="ID o clave de la entidad afectada.")
    fase: str = Field(..., description="Fase del pipeline donde ocurrió: 'parsing', 'validation', 'routing', 'export', 'audit'.")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Marca temporal del evento.")

    model_config = {"validate_assignment": True}


class RegistroRiesgo(BaseModel):
    """Documentación formal de limitaciones técnicas y riesgos controlados."""
    codigo_riesgo: str = Field(..., description="Identificador del riesgo (ej. 'RISK-DV-X14').")
    descripcion: str = Field(..., description="Detalle del riesgo técnico identificado.")
    impacto: str = Field(..., description="Impacto operativo en los entregables o la institución.")
    mitigacion_o_estado: str = Field(..., description="Medida de mitigación o estado actual del riesgo.")

    model_config = {"validate_assignment": True}


class MetadatosEntorno(BaseModel):
    """Metadatos de reproducibilidad técnica del entorno de ejecución."""
    version_sistema: str = Field(default="0.1.0", description="Versión del sistema de automatización.")
    version_python: str = Field(..., description="Versión del intérprete de Python.")
    dependencias_clave: Dict[str, str] = Field(default_factory=dict, description="Versiones de openpyxl, pydantic, pyyaml, pytest.")
    git_commit: Optional[str] = Field(default="N/A - repositorio local sin git", description="Hash de commit si está disponible.")
    hash_configuracion: str = Field(..., description="Hash SHA-256 de config/settings.yaml utilizado.")
    plataforma_os: str = Field(..., description="Sistema operativo de ejecución.")

    model_config = {"validate_assignment": True}


class ManifiestoEjecucionCompleto(BaseModel):
    """
    Manifiesto integral de auditoría de la ejecución (Fase 10).
    Documenta inequívocamente todo lo que ocurrió durante el procesamiento.
    """
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Identificador único universal (UUID4).")
    timestamp_inicio: str = Field(..., description="Marca temporal ISO-8601 del inicio del procesamiento.")
    timestamp_fin: Optional[str] = Field(default=None, description="Marca temporal ISO-8601 de la finalización.")
    version_sistema: str = Field(default="0.1.0", description="Versión del software.")
    modo_ejecucion: str = Field(..., description="Modo ejecutado: 'preview', 'export', 'validate', 'analyze'.")
    estado: EstadoEjecucion = Field(default=EstadoEjecucion.INICIADA, description="Estado de la ejecución.")
    entorno: MetadatosEntorno = Field(..., description="Metadatos técnicos de reproducibilidad.")
    inputs: List[MetadatosEntrada] = Field(default_factory=list, description="Evidencias criptográficas de los archivos de entrada.")
    actividades_procesadas: List[Dict[str, Any]] = Field(default_factory=list, description="Resumen de actividades procesadas.")
    total_participaciones_entrada: int = Field(default=0, description="Participaciones totales leídas.")
    total_participaciones_enrutadas: int = Field(default=0, description="Participaciones clasificadas.")
    conteo_por_matriz: Dict[str, int] = Field(default_factory=dict, description="Conteo por matriz: matriz_1 a matriz_5.")
    conteo_estados_operativos: Dict[str, int] = Field(default_factory=dict, description="Conteo de APTO, EN_REVISION, BLOQUEADO.")
    trazabilidad_participaciones: List[TrazaParticipacion] = Field(default_factory=list, description="Trazas unívocas por participación.")
    auditoria_m5: AuditoriaM5 = Field(default_factory=AuditoriaM5, description="Evidencia de cero destrucción en M5.")
    auditoria_tablas: Dict[str, AuditoriaTabla] = Field(default_factory=dict, description="Evidencia de sincronización de tablas.")
    auditoria_formulas: List[AuditoriaFormulaColumna] = Field(default_factory=list, description="Evidencia de fórmulas institucionales.")
    riesgos_documentados: List[RegistroRiesgo] = Field(default_factory=list, description="Riesgos técnicos formales (ej. RISK-DV-X14).")
    eventos: List[EventoAuditoria] = Field(default_factory=list, description="Bitácora de eventos y advertencias.")
    outputs: List[MetadatosSalida] = Field(default_factory=list, description="Evidencias criptográficas de entregables generados.")
    invariantes: Dict[str, bool] = Field(default_factory=dict, description="Verificación de invariantes matemáticas.")
    observaciones: List[str] = Field(default_factory=list, description="Notas institucionales y conclusiones.")

    model_config = {"validate_assignment": True}
