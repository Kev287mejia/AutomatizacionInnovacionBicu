"""
app.word_consolidator.document.institutional_models

Modelos de datos intermedios inmutables para el Producto B:
Informe Semanal Institucional de BICU (Fase 16.3).

Desacoplados de python-docx, estilos de Word y del Producto A (Dossier Técnico).
Aplica con rigor absoluto:
1. Inmutabilidad (Pydantic v2 frozen=True).
2. Cardinalidad N >= 0 en actividades (no forzar N >= 1).
3. Conteo de sexo estricto: total == mujeres + varones (validar, no autocorregir).
4. Conservación paralela de fuentes: dato_declarado, dato_nominal y discrepancia.
5. Evidencias como referencias de datos (fotografías, asistencias, enlaces).
6. Separación de metadatos de presentación (orden_presentacion).
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field, model_validator


class TipoEstamentoInstitucional(str, Enum):
    """Estamentos institucionales reconocidos en el Informe Semanal BICU."""
    ESTUDIANTES = "ESTUDIANTES"
    PERSONAL_ADMINISTRATIVO = "PERSONAL_ADMINISTRATIVO"
    MAESTRAS_Y_MAESTROS = "MAESTRAS_Y_MAESTROS"
    COLABORADORES = "COLABORADORES"
    BENEFICIARIOS_POBLADORES = "BENEFICIARIOS_POBLADORES"


class TipoEvidenciaEnum(str, Enum):
    """Categorías funcionales de evidencias anexas al informe."""
    FOTOGRAFIA = "FOTOGRAFIA"
    REGISTRO_ASISTENCIA = "REGISTRO_ASISTENCIA"
    ENLACE_MEDIOS = "ENLACE_MEDIOS"


class EstadoEvidenciaEnum(str, Enum):
    """Estado de vinculación o disponibilidad de la evidencia."""
    VINCULADO = "VINCULADO"
    PENDIENTE = "PENDIENTE"
    NO_DISPONIBLE = "NO_DISPONIBLE"


class ConteoSexoInstitucional(BaseModel):
    """
    Desglose cuantitativo estricto por sexo: Mujeres, Varones y Total.
    Cumple la convención institucional: M, V y Total = M + V.
    Regla crítica: Valida y rechaza inconsistencias; no corrige silenciosamente.
    """
    mujeres: int = Field(default=0, ge=0, description="Total de participantes de sexo femenino (Columna M).")
    varones: int = Field(default=0, ge=0, description="Total de participantes de sexo masculino (Columna V).")
    total: int = Field(default=0, ge=0, description="Total general verificado (Columna Total = M + V).")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @model_validator(mode="after")
    def validar_total_estricto(self) -> "ConteoSexoInstitucional":
        suma_esperada = self.mujeres + self.varones
        if self.total != suma_esperada:
            raise ValueError(
                f"Inconsistencia en conteo de sexo: Total declarado ({self.total}) "
                f"no coincide con la suma de mujeres ({self.mujeres}) + varones ({self.varones}) = {suma_esperada}."
            )
        return self

    @property
    def M(self) -> int:
        """Alias para presentación institucional de Mujeres."""
        return self.mujeres

    @property
    def V(self) -> int:
        """Alias para presentación institucional de Varones."""
        return self.varones


class DiscrepanciaEstamento(BaseModel):
    """
    Detalle de discrepancia cuantitativa a nivel de un estamento específico.
    Conserva delta = nominal - declarado para auditoría transparente.
    """
    delta_mujeres: int = Field(default=0, description="Diferencia en mujeres (nominal - declarado).")
    delta_varones: int = Field(default=0, description="Diferencia en varones (nominal - declarado).")
    delta_total: int = Field(default=0, description="Diferencia total (nominal - declarado).")
    estado: str = Field(default="REQUIERE_REVISION", description="Estado operativo de la discrepancia.")
    descripcion: Optional[str] = Field(default=None, description="Detalle técnico de la diferencia.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ProtagonistaEstamentoInstitucional(BaseModel):
    """
    Fila de estamento participante dentro de una actividad en la tabla institucional.
    Conserva en paralelo el dato declarado (M1), el dato nominal (M2–M5) y la discrepancia.
    """
    estamento_tipo: TipoEstamentoInstitucional = Field(..., description="Tipo canónico del estamento.")
    denominacion_visible: str = Field(..., description="Texto institucional visible (ej. 'Estudiantes').")
    conteo_presentacion: ConteoSexoInstitucional = Field(..., description="Cifras cuantitativas principales (M, V, Total).")
    dato_declarado: Optional[ConteoSexoInstitucional] = Field(
        default=None,
        description="Cifras reportadas en M1 o informe manual si existen."
    )
    dato_nominal: Optional[ConteoSexoInstitucional] = Field(
        default=None,
        description="Cifras verificadas en matrices nominales (M2–M5) si existen."
    )
    tiene_discrepancia: bool = Field(default=False, description="Indica si existe discrepancia entre fuentes.")
    discrepancia_detalle: Optional[DiscrepanciaEstamento] = Field(
        default=None,
        description="Detalle matemático de la discrepancia."
    )
    orden_presentacion: int = Field(
        default=10,
        description="Metadato de configuración para el renderizado visual futuro (no altera datos de negocio)."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class DiscrepanciaActividadInstitucional(BaseModel):
    """
    Registro formal de discrepancia entre M1 y Nominales a nivel de actividad.
    Permite auditar la diferencia sin modificar ninguna fuente.
    """
    estamento: str = Field(..., description="Estamento o dimensión analizada.")
    fuente_declarada: str = Field(..., description="Fuente agregada declarada (ej. 'Matriz 1').")
    fuente_nominal: str = Field(..., description="Fuentes nominales asociadas (ej. 'Matriz 2').")
    declarado_m: int = Field(default=0, ge=0, description="Mujeres declaradas en M1.")
    declarado_v: int = Field(default=0, ge=0, description="Varones declarados en M1.")
    declarado_total: int = Field(default=0, ge=0, description="Total declarado en M1.")
    nominal_m: int = Field(default=0, ge=0, description="Mujeres contabilizadas nominalmente.")
    nominal_v: int = Field(default=0, ge=0, description="Varones contabilizados nominalmente.")
    nominal_total: int = Field(default=0, ge=0, description="Total contabilizado nominalmente.")
    delta_total: int = Field(..., description="Diferencia neta: nominal_total - declarado_total.")
    delta_m: int = Field(default=0, description="Diferencia en mujeres: nominal_m - declarado_m.")
    delta_v: int = Field(default=0, description="Diferencia en varones: nominal_v - declarado_v.")
    estado: str = Field(default="REQUIERE_REVISION", description="Estado formal de auditoría.")
    descripcion: str = Field(..., description="Explicación legible de la discrepancia.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ItemEvidenciaInstitucional(BaseModel):
    """
    Referencia de datos a una evidencia física, fotográfica o digital.
    No realiza lectura física de archivos ni descargas de red en esta fase.
    """
    id_evidencia: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID de la evidencia.")
    tipo: TipoEvidenciaEnum = Field(..., description="Tipo de evidencia.")
    titulo: str = Field(..., description="Título o pie descriptivo.")
    referencia: str = Field(..., description="Ruta de archivo local o URL web.")
    orden: int = Field(default=1, ge=1, description="Orden secuencial dentro de su sección.")
    descripcion: Optional[str] = Field(default=None, description="Contexto o detalle adicional.")
    estado: EstadoEvidenciaEnum = Field(default=EstadoEvidenciaEnum.PENDIENTE, description="Estado de vinculación.")
    origen: str = Field(default="MANUAL", description="Procedencia de la referencia.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class SeccionEvidenciasActividad(BaseModel):
    """
    Colección de evidencias asociadas a una actividad institucional específica.
    """
    id_actividad: str = Field(..., description="Identificador unívoco de la actividad asociada.")
    numero_actividad: int = Field(..., ge=1, description="Número ordinal de la actividad para encabezado.")
    nombre_actividad: str = Field(..., description="Nombre formal de la actividad.")
    fotografias: List[ItemEvidenciaInstitucional] = Field(
        default_factory=list,
        description="Colección de fotografías de la actividad."
    )
    registros_asistencia: List[ItemEvidenciaInstitucional] = Field(
        default_factory=list,
        description="Imágenes de listas de asistencia físicas firmadas."
    )
    enlaces_publicaciones: List[ItemEvidenciaInstitucional] = Field(
        default_factory=list,
        description="URLs a publicaciones web o de redes sociales."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @property
    def total_evidencias(self) -> int:
        return len(self.fotografias) + len(self.registros_asistencia) + len(self.enlaces_publicaciones)


class TrazabilidadActividad(BaseModel):
    """
    Trazabilidad de procedencia real disponible para una actividad consolidada.
    No inventa campos inexistentes; refleja los metadatos efectivamente leídos.
    """
    id_actividad: str = Field(..., description="UUID de la actividad.")
    matriz_m1_origen: Optional[str] = Field(default=None, description="Archivo o clave de M1 origen.")
    fila_m1_origen: Optional[int] = Field(default=None, description="Fila física en M1 si se conoce.")
    matrices_nominales: List[str] = Field(default_factory=list, description="Matrices nominales con registros.")
    total_filas_nominales: int = Field(default=0, ge=0, description="Cantidad de participaciones nominales.")
    hash_m1: Optional[str] = Field(default=None, description="Hash SHA-256 de M1 si está disponible.")
    detalles: Dict[str, str] = Field(default_factory=dict, description="Metadatos textuales específicos.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ActividadInstitucional(BaseModel):
    """
    Representación completa de una actividad en el Informe Semanal Institucional.
    Corresponde al bloque fusionado en la tabla de 13 columnas y su sección de evidencias.
    """
    id_actividad: str = Field(..., description="UUID unívoco de la actividad.")
    numero_orden: int = Field(..., ge=1, description="Índice ordinal secuencial (1..N).")
    nombre_actividad: str = Field(..., description="Nombre formal de la actividad.")
    eje_vinculado: str = Field(default="", description="Código del eje institucional (ej. '11.41.67').")
    descripcion: str = Field(default="", description="Descripción cualitativa o logros alcanzados.")
    sede: str = Field(..., description="Sede universitaria de realización.")
    departamento: str = Field(default="", description="Departamento territorial.")
    municipio: str = Field(default="", description="Municipio territorial.")
    tipo_actividad: str = Field(default="", description="Tipo de evento o actividad.")
    protagonistas: List[ProtagonistaEstamentoInstitucional] = Field(
        default_factory=list,
        description="Filas de estamentos con participación efectiva (sin filas artificiales con 0)."
    )
    totales_actividad: ConteoSexoInstitucional = Field(
        ...,
        description="Sumatoria total de participantes de la actividad (M, V, Total)."
    )
    discrepancias: List[DiscrepanciaActividadInstitucional] = Field(
        default_factory=list,
        description="Discrepancias institucionales conservadas para esta actividad."
    )
    evidencias: SeccionEvidenciasActividad = Field(
        ...,
        description="Sección de evidencias anexas vinculadas."
    )
    trazabilidad: TrazabilidadActividad = Field(
        ...,
        description="Metadatos de procedencia técnica."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @property
    def tiene_discrepancias(self) -> bool:
        return len(self.discrepancias) > 0


class InformeSemanalInstitucional(BaseModel):
    """
    Modelo documental raíz inmutable para el Informe Semanal Institucional BICU.
    Representa el Producto B completamente desacoplado del Producto A.
    Admite cardinalidad N >= 0 en actividades.
    """
    id_informe: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID técnico del informe.")
    mecanismo_institucional: str = Field(
        default="MECANISMO INSTITUCIONAL",
        description="Constante institucional del encabezado superior."
    )
    tipo_informe: str = Field(
        default="INFORME SEMANAL",
        description="Tipo formal de documento institucional."
    )
    departamento_responsable: str = Field(
        ...,
        description="Área o departamento responsable (ej. 'Innovación y Emprendimiento')."
    )
    mes_planificado: str = Field(
        ...,
        description="Nombre institucional del mes (ej. 'Septiembre')."
    )
    semana: str = Field(
        ...,
        description="Semana operativa reportada (ej. '1')."
    )
    actividades: List[ActividadInstitucional] = Field(
        default_factory=list,
        description="Listado de N actividades (N >= 0)."
    )
    observaciones: Optional[str] = Field(
        default=None,
        description="Observaciones institucionales complementarias."
    )
    trazabilidad_global: Dict[str, str] = Field(
        default_factory=dict,
        description="Hashes SHA-256 de matrices y metadatos del pipeline."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @property
    def total_actividades(self) -> int:
        return len(self.actividades)

    @property
    def total_mujeres(self) -> int:
        return sum(act.totales_actividad.mujeres for act in self.actividades)

    @property
    def total_varones(self) -> int:
        return sum(act.totales_actividad.varones for act in self.actividades)

    @property
    def total_participantes(self) -> int:
        return sum(act.totales_actividad.total for act in self.actividades)

    @property
    def tiene_discrepancias(self) -> bool:
        return any(act.tiene_discrepancias for act in self.actividades)
