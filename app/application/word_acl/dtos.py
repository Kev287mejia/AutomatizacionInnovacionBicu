"""Contratos de transporte (DTOs) para la presentacion en Word.

Cero dependencias de infraestructura concreta.
No almacena binarios. Las evidencias viajan como metadatos.
Todos los DTOs son inmutables (frozen).
None se conserva sin imputacion silenciosa.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from app.application.word_acl.policies import PoliticaPresentacionRevisionWord


class FuenteCifras(str, Enum):
    """Origen institucional de las cifras cuantitativas.

    DECLARADO: Cifra institucionalmente declarada (M1 o trazable).
    NOMINAL:   Asistencia efectiva registrada en participacion.
    Invariante: NOMINAL != DECLARADO. Sin fallback silencioso.
    """

    DECLARADO = "DECLARADO"
    NOMINAL = "NOMINAL"


class FuenteResultados(str, Enum):
    """Origen del contenido de la columna de logros o resultados.

    RESULTADOS_REGISTRADOS:    Campo especifico de resultados en SSOT si existe.
    OBJETIVO_GENERAL:          Requiere aprobacion institucional explicita.
    JUSTIFICACION_ESTRATEGICA: Requiere aprobacion institucional explicita.
    VACIO:                     Columna vacia por defecto.
    """

    RESULTADOS_REGISTRADOS = "RESULTADOS_REGISTRADOS"
    OBJETIVO_GENERAL = "OBJETIVO_GENERAL"
    JUSTIFICACION_ESTRATEGICA = "JUSTIFICACION_ESTRATEGICA"
    VACIO = "VACIO"


class WordEstamentoItemDTO(BaseModel):
    """Agregado estadistico de un estamento para presentacion Word.

    Traduccion canonica:
      F -> mujeres
      M -> varones
      NULL -> sin_sexo_disponible

    Invariante obligatoria:
      total_participantes == mujeres + varones + sin_sexo_disponible
    """

    estamento_tipo: str = Field(
        ...,
        description="Tipo de estamento institucional."
    )
    denominacion_visible: str = Field(
        ...,
        description="Etiqueta visible institucional."
    )
    mujeres: int = Field(
        default=0,
        ge=0,
        description="Participantes con sexo F."
    )
    varones: int = Field(
        default=0,
        ge=0,
        description="Participantes con sexo M."
    )
    sin_sexo_disponible: int = Field(
        default=0,
        ge=0,
        description="Participantes con sexo NULL o no disponible."
    )
    total_participantes: int = Field(
        default=0,
        ge=0,
        description="Total efectivo: mujeres + varones + sin_sexo_disponible."
    )
    orden_presentacion: int = Field(
        default=1,
        ge=1,
        description="Orden de presentacion canonico."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class WordEvidenciaItemDTO(BaseModel):
    """Metadatos de evidencia preparados para presentacion Word.

    Sin contenido binario. Rutas relativas originales preservadas.
    Resolucion absoluta inyectable y configurable.
    """

    id_evidencia: str = Field(
        ...,
        description="Identificador de la evidencia."
    )
    id_actividad: Optional[str] = Field(
        default="",
        description="Identificador de la actividad vinculada."
    )
    titulo: str = Field(
        ...,
        description="Titulo de la evidencia."
    )
    tipo_evidencia: str = Field(
        ...,
        description="Tipo funcional de evidencia."
    )
    descripcion_pie: Optional[str] = Field(
        default=None,
        description="Descripcion o pie de foto."
    )
    ruta_relativa_original: Optional[str] = Field(
        default=None,
        description="Ruta relativa original conservada del SSOT."
    )
    ruta_relativa: Optional[str] = Field(
        default=None,
        description="Ruta relativa de la evidencia."
    )
    ruta_absoluta_resuelta: Optional[str] = Field(
        default=None,
        description="Ruta absoluta resuelta contra base configurable."
    )
    hash_sha256: Optional[str] = Field(
        default=None,
        description="Hash SHA-256 de custodia criptografica."
    )
    orden_presentacion: int = Field(
        default=1,
        ge=1,
        description="Orden de presentacion."
    )
    seccion_informe: str = Field(
        default="GALERIA",
        description="Seccion de destino en el informe."
    )
    estado_disponibilidad: str = Field(
        default="VINCULADO",
        description="VINCULADO | PENDIENTE | NO_DISPONIBLE."
    )
    existe_fisicamente: Optional[bool] = Field(
        default=None,
        description="Indicador de existencia fisica en disco."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

    @model_validator(mode="before")
    @classmethod
    def sincronizar_rutas(cls, values: Any) -> Any:
        if isinstance(values, dict):
            r_rel = values.get("ruta_relativa")
            r_orig = values.get("ruta_relativa_original")
            if r_rel is not None and r_orig is None:
                values["ruta_relativa_original"] = r_rel
            elif r_orig is not None and r_rel is None:
                values["ruta_relativa"] = r_orig
        return values


class WordActividadDTO(BaseModel):
    """Actividad preparada para presentacion Word con politicas explicitas."""

    id_actividad: str = Field(
        ...,
        description="Identificador de la actividad."
    )
    numero_orden: int = Field(
        default=1,
        ge=1,
        description="Numero de orden."
    )
    nombre_actividad: str = Field(
        ...,
        description="Nombre de la actividad."
    )
    eje_vinculado: str = Field(
        default="",
        description="Eje o linea de vinculacion."
    )
    descripcion_logros: str = Field(
        default="",
        description="Descripcion de logros institucionales."
    )
    fuente_resultados: FuenteResultados = Field(
        default=FuenteResultados.VACIO,
        description="Fuente aprobada para logros."
    )
    sede: str = Field(
        default="",
        description="Sede o recinto."
    )
    departamento_territorial: str = Field(
        default="",
        description="Departamento territorial."
    )
    municipio_territorial: str = Field(
        default="",
        description="Municipio territorial."
    )
    tipo_actividad: str = Field(
        default="",
        description="Tipo de actividad."
    )
    fuente_cifras: FuenteCifras = Field(
        ...,
        description="DECLARADO o NOMINAL. Sin fallback silencioso."
    )
    etiqueta_fuente_cifras: str = Field(
        ...,
        description="Etiqueta visible diferenciadora."
    )
    total_mujeres: int = Field(
        default=0,
        ge=0,
        description="Total participantes sexo F."
    )
    total_varones: int = Field(
        default=0,
        ge=0,
        description="Total participantes sexo M."
    )
    sin_sexo_disponible: int = Field(
        default=0,
        ge=0,
        description="Participantes con sexo NULL."
    )
    total_participantes: int = Field(
        default=0,
        ge=0,
        description="Total general de participantes."
    )
    estamentos: List[WordEstamentoItemDTO] = Field(
        default_factory=list,
        description="Desglose de estamentos."
    )
    evidencias: List[WordEvidenciaItemDTO] = Field(
        default_factory=list,
        description="Metadatos de evidencias asociadas."
    )
    tiene_discrepancias: bool = Field(
        default=False,
        description="Indicador de discrepancias."
    )
    discrepancias_resumen: List[str] = Field(
        default_factory=list,
        description="Resumen de discrepancias."
    )
    observaciones_calidad: List[str] = Field(
        default_factory=list,
        description="Observaciones de calidad."
    )
    observaciones_revision: List[str] = Field(
        default_factory=list,
        description="Observaciones derivadas de revision."
    )
    trazabilidad: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos de trazabilidad."
    )

    model_config = {
        "frozen": True,
        "arbitrary_types_allowed": True,
        "str_strip_whitespace": True,
    }


class WordWeeklyReportDataset(BaseModel):
    """Dataset completo para Producto B (Informe Semanal Ejecutivo)."""

    id_informe_semanal: Optional[str] = Field(
        default=None,
        description="Identificador del informe semanal institucional."
    )
    departamento_responsable: str = Field(
        ...,
        description="Departamento o area responsable."
    )
    mes_planificado: str = Field(
        ...,
        description="Mes planificado de cobertura."
    )
    semana: str = Field(
        ...,
        description="Semana del informe."
    )
    sede_recinto: str = Field(
        default="",
        description="Sede o recinto institucional."
    )
    actividades: List[WordActividadDTO] = Field(
        default_factory=list,
        description="Lista de actividades adaptadas."
    )
    gran_total_actividades: int = Field(
        default=0,
        ge=0,
        description="Total de actividades."
    )
    gran_total_mujeres: int = Field(
        default=0,
        ge=0,
        description="Suma total de mujeres."
    )
    gran_total_varones: int = Field(
        default=0,
        ge=0,
        description="Suma total de varones."
    )
    gran_total_sin_sexo: int = Field(
        default=0,
        ge=0,
        description="Suma de participantes sin sexo disponible."
    )
    gran_total_participantes: int = Field(
        default=0,
        ge=0,
        description="Total general de participantes."
    )
    observaciones_calidad: List[str] = Field(
        default_factory=list,
        description="Observaciones globales de calidad."
    )
    politica_revision_aplicada: PoliticaPresentacionRevisionWord = Field(
        default=PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
        description="Politica Word aplicada para revision."
    )
    trazabilidad_global: Dict[str, str] = Field(
        default_factory=dict,
        description="Trazabilidad global del dataset."
    )

    model_config = {
        "frozen": True,
        "arbitrary_types_allowed": True,
        "str_strip_whitespace": True,
    }
