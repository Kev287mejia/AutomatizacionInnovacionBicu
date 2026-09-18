"""
app.statistics.models

Modelos de datos para el Motor Estadístico Institucional (Fase 7).
Define estructuras inmutables para agregaciones por sexo, categoría,
actividad (base del Consolidado), indicadores de calidad auditados con
numerador/denominador y métricas diferenciadas de recurrencia.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DesgloseSexo(BaseModel):
    """
    Agregación cuantitativa por sexo con cálculo de proporciones porcentuales.
    """
    femenino: int = Field(default=0, description="Cantidad de participantes de sexo femenino.")
    masculino: int = Field(default=0, description="Cantidad de participantes de sexo masculino.")
    indefinido: int = Field(default=0, description="Cantidad de participantes sin sexo normalizado confirmado.")
    total: int = Field(default=0, description="Total de participantes en este grupo.")
    porcentaje_femenino: float = Field(default=0.0, description="Porcentaje de participación femenina.")
    porcentaje_masculino: float = Field(default=0.0, description="Porcentaje de participación masculina.")

    model_config = {
        "validate_assignment": True,
    }


class DesgloseCategoria(BaseModel):
    """
    Agregación estadística para una categoría o rol institucional específico.
    Conserva la lista de IDs de participaciones para explicabilidad y trazabilidad completa.
    """
    categoria: str = Field(..., description="Nombre formal de la categoría o rol institucional.")
    conteo_sexo: DesgloseSexo = Field(
        default_factory=DesgloseSexo,
        description="Desglose por sexo dentro de esta categoría."
    )
    aptos: int = Field(default=0, description="Cantidad de registros aptos sin observaciones.")
    en_revision: int = Field(default=0, description="Cantidad de registros con observaciones no bloqueantes.")
    ids_participaciones: List[str] = Field(
        default_factory=list,
        description="Lista de id_participacion que componen esta estadística (trazabilidad auditable)."
    )

    model_config = {
        "validate_assignment": True,
    }


class EstadisticaActividad(BaseModel):
    """
    Estructura agregada de UNA actividad.
    Representa formalmente la fila que alimentará la Matriz 1: Consolidado de Actividades.
    """
    id_actividad: str = Field(..., description="Identificador único de la actividad.")
    nombre_actividad: str = Field(..., description="Nombre de la actividad.")
    sede: Optional[str] = Field(default=None, description="Sede o campus donde se realizó la actividad.")
    fecha: Optional[str] = Field(default=None, description="Fecha de realización del evento.")
    municipio: Optional[str] = Field(default=None, description="Municipio del evento.")
    departamento: Optional[str] = Field(default=None, description="Departamento territorial del evento.")
    eje_linea: Optional[str] = Field(default=None, description="Eje o línea estratégica institucional.")
    tipo_evento: Optional[str] = Field(default=None, description="Tipo de evento institucional.")
    total_asistencias: int = Field(default=0, description="Total de asistencias registradas para esta actividad.")
    total_personas_unicas: int = Field(default=0, description="Personas únicas distintas que asistieron a esta actividad.")
    desglose_sexo_global: DesgloseSexo = Field(
        default_factory=DesgloseSexo,
        description="Desglose total de sexo para la actividad."
    )
    # Columnas de salida hacia el Consolidado
    estudiantes: DesgloseCategoria = Field(..., description="Estadísticas de estudiantes en la actividad.")
    docentes: DesgloseCategoria = Field(..., description="Estadísticas de docentes (rol académico).")
    administrativos_no_docentes: DesgloseCategoria = Field(
        ...,
        description="Estadísticas de administrativos y no docentes (rol administrativo)."
    )
    beneficiados: DesgloseCategoria = Field(..., description="Estadísticas de protagonistas beneficiados / pobladores.")
    colaboradores: DesgloseCategoria = Field(..., description="Estadísticas de colaboradores y aliados externos.")
    cola_revision: int = Field(default=0, description="Participaciones con categoría desconocida o no determinable.")
    bloqueados: int = Field(default=0, description="Participaciones bloqueadas por error crítico.")

    model_config = {
        "validate_assignment": True,
    }


class MetricaCalidadItem(BaseModel):
    """
    Representación formal de una métrica de calidad con numerador, denominador, porcentaje y criterio auditado.
    """
    numerador: int = Field(default=0, description="Cantidad de registros que cumplen el criterio evaluado.")
    denominador: int = Field(default=0, description="Base total sobre la cual se calcula el indicador.")
    porcentaje: float = Field(default=0.0, description="Porcentaje resultante (numerador / denominador * 100).")
    definicion: str = Field(..., description="Definición explícita y auditable del criterio de disponibilidad aplicado.")

    model_config = {
        "validate_assignment": True,
    }


class EstadisticaCalidad(BaseModel):
    """
    Indicadores de calidad, completitud y salud de datos con denominadores explícitos.
    """
    total_registros: int = Field(default=0, description="Total de participaciones evaluadas.")
    registros_aptos: int = Field(default=0, description="Total de participaciones con estado APTO.")
    registros_en_revision: int = Field(default=0, description="Total de participaciones con estado EN_REVISION.")
    registros_bloqueados: int = Field(default=0, description="Total de participaciones con estado BLOQUEADO.")
    porcentaje_aptos: float = Field(default=0.0, description="% de registros listos sin observación.")
    porcentaje_en_revision: float = Field(default=0.0, description="% de registros que requieren supervisión humana.")
    
    # Métricas detalladas con numerador, denominador y definición
    cedula_disponible: MetricaCalidadItem = Field(..., description="Disponibilidad de cédula oficial.")
    sexo_confirmado: MetricaCalidadItem = Field(..., description="Confirmación de sexo normalizado.")
    edad_disponible: MetricaCalidadItem = Field(..., description="Disponibilidad de edad o fecha de nacimiento.")
    carrera_disponible: MetricaCalidadItem = Field(..., description="Disponibilidad de carrera en estudiantes.")

    # Atributos de compatibilidad directa hacia porcentajes numéricos
    cedula_disponible_pct: float = Field(default=0.0, description="% cédula disponible.")
    sexo_confirmado_pct: float = Field(default=0.0, description="% sexo confirmado.")
    edad_disponible_pct: float = Field(default=0.0, description="% edad disponible.")
    carrera_disponible_pct: float = Field(default=0.0, description="% carrera disponible.")


class DistribucionEdades(BaseModel):
    """
    Desglose etario y estadísticos descriptivos básicos.
    """
    menores_18: int = Field(default=0, description="Participantes menores de 18 años.")
    de_18_a_24: int = Field(default=0, description="Participantes entre 18 y 24 años.")
    de_25_a_29: int = Field(default=0, description="Participantes entre 25 y 29 años.")
    de_30_a_mas: int = Field(default=0, description="Participantes de 30 años o más.")
    sin_edad: int = Field(default=0, description="Participantes sin edad reportada.")
    edad_promedio: Optional[float] = Field(default=None, description="Edad promedio de quienes tienen edad.")
    edad_minima: Optional[int] = Field(default=None, description="Edad mínima registrada.")
    edad_maxima: Optional[int] = Field(default=None, description="Edad máxima registrada.")


class EstadisticaGlobal(BaseModel):
    """
    Contenedor global de todos los agregados e indicadores estadísticos institucionales.
    Distingue rigurosamente entre promedio de asistencias y tasa de recurrencia.
    """
    total_actividades: int = Field(default=0, description="Cantidad total de actividades institucionales.")
    total_asistencias: int = Field(default=0, description="Total de asistencias brutas registradas.")
    total_personas_unicas: int = Field(default=0, description="Total de individuos únicos participantes en el período.")
    
    # A) Promedio de asistencias por persona = total_asistencias / personas_unicas
    promedio_asistencias_por_persona: float = Field(
        default=1.0,
        description="Promedio de asistencias por persona única (total_asistencias / total_personas_unicas)."
    )
    
    # B) Personas recurrentes = personas unificadas que participaron en más de 1 actividad distinta
    personas_recurrentes: int = Field(
        default=0,
        description="Cantidad de personas únicas que participaron en más de una actividad distinta."
    )
    ids_personas_recurrentes: List[str] = Field(
        default_factory=list,
        description="Lista de id_persona de individuos identificados como recurrentes."
    )
    
    # C) Tasa de recurrencia = personas_recurrentes / personas_unicas (%)
    tasa_recurrencia: float = Field(
        default=0.0,
        description="Porcentaje de personas únicas que son recurrentes (personas_recurrentes / total_personas_unicas * 100)."
    )
    
    desglose_sexo_global: DesgloseSexo = Field(
        default_factory=DesgloseSexo,
        description="Distribución global por sexo."
    )
    desglose_categorias: Dict[str, DesgloseCategoria] = Field(
        default_factory=dict,
        description="Agregación por cada categoría institucional oficial."
    )
    distribucion_sedes: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribución de asistencias por sede institucional."
    )
    distribucion_carreras: Dict[str, int] = Field(
        default_factory=dict,
        description="Frecuencia de carreras en participantes estudiantiles."
    )
    distribucion_edades: DistribucionEdades = Field(
        default_factory=DistribucionEdades,
        description="Desglose demográfico por rangos etarios."
    )
    calidad_datos: EstadisticaCalidad = Field(
        default_factory=EstadisticaCalidad,
        description="Métricas de calidad y completitud de datos con denominadores explícitos."
    )
    actividades: List[EstadisticaActividad] = Field(
        default_factory=list,
        description="Lista de estadísticas a nivel de actividad para el Consolidado."
    )
    invariante_estadistica_valida: bool = Field(
        default=False,
        description="True si todas las sumas parciales coinciden exactamente con los totales globales."
    )
