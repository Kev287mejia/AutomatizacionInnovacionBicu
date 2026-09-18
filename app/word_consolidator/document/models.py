"""
app.word_consolidator.document.models

Modelos de datos documentales intermedios inmutables y fuertemente tipados
para la generación del Informe Consolidado Institucional (Fase 14.6).
Totalmente desacoplados de python-docx, tablas Word y estilos visuales.

Aplica con rigor absoluto:
1. No invención de información (campos no respaldados permanecen None o listas vacías).
2. No reconciliación automática de fuentes (M1, Nominales, Narrativa y Discrepancias coexisten).
3. Semántica canónica de sexo: FEMENINO / MASCULINO (prohibido usar 'M' como mujeres).
4. Separación estricta de estamentos: Estudiantes, Docentes, Administrativos, Colaboradores, Beneficiarios.
5. Trazabilidad completa por dimensión y elemento.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Union
import uuid

from pydantic import BaseModel, Field, model_validator

from app.word_consolidator.models import (
    EstadoDiscrepancia,
    MetadatosInstitucionales,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
)


# ============================================================================
# SUB-MODELOS COMPONENTES DOCUMENTALES
# ============================================================================

class TrazabilidadFuenteDocumental(BaseModel):
    """
    Trazabilidad de procedencia para un dato o sección documental.
    Permite rastrear exactamente la matriz, archivo, hoja y fila de origen.
    """
    matriz: str = Field(..., description="Código de la matriz origen (M1, M2, M3, M4, M5 o NARRATIVO).")
    archivo: Optional[str] = Field(default=None, description="Nombre o ruta del archivo origen si está disponible.")
    hoja: Optional[str] = Field(default=None, description="Nombre de la hoja de cálculo de origen si aplica.")
    fila: Optional[int] = Field(default=None, description="Número de fila física de origen si aplica.")
    actividad: Optional[str] = Field(default=None, description="Nombre formal de la actividad vinculada.")
    periodo: Optional[str] = Field(default=None, description="Etiqueta del período asociado.")
    detalles_extra: Dict[str, Any] = Field(default_factory=dict, description="Metadatos técnicos adicionales.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ItemDiscrepanciaDocumental(BaseModel):
    """
    Representación inmutable de una discrepancia preparada para auditoría y visualización tabular:
    DIMENSIÓN | FUENTE A | FUENTE B | DELTA | ESTADO
    """
    id_actividad: str = Field(..., description="Identificador unívoco de la actividad.")
    nombre_actividad: str = Field(..., description="Nombre formal de la actividad evaluada.")
    categoria: str = Field(..., description="Categoría de discrepancia (ESTAMENTO, SEXO, TOTAL, FUENTE_FALTANTE, etc.).")
    dimension: str = Field(..., description="Dimensión o estamento evaluado (Estudiantes, Docentes, Total, etc.).")
    fuente_a: str = Field(..., description="Denominación formal de la Fuente A (ej. 'Matriz 1' o 'Informe Narrativo').")
    fuente_b: str = Field(..., description="Denominación formal de la Fuente B (ej. 'Matrices Nominales (M2–M5)').")
    valor_fuente_a: Optional[int] = Field(default=None, description="Valor reportado en Fuente A.")
    valor_fuente_b: Optional[int] = Field(default=None, description="Valor reportado en Fuente B.")
    delta: Optional[int] = Field(default=None, description="Delta institucional exacto: Fuente B - Fuente A.")
    estado: EstadoDiscrepancia = Field(
        default=EstadoDiscrepancia.REQUIERE_REVISION,
        description="Estado de la discrepancia (CONCORDANTE, REQUIERE_REVISION)."
    )
    descripcion: Optional[str] = Field(default=None, description="Descripción técnica legible de la diferencia.")
    trazabilidad: Dict[str, Any] = Field(default_factory=dict, description="Metadatos de trazabilidad de las celdas.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class DistribucionSexoDocumental(BaseModel):
    """
    Distribución cuantitativa y porcentual por sexo en semántica canónica:
    FEMENINO y MASCULINO. Queda prohibido interpretar 'M' como Mujeres.
    """
    femenino: int = Field(default=0, ge=0, description="Participantes de sexo femenino.")
    masculino: int = Field(default=0, ge=0, description="Participantes de sexo masculino.")
    total: int = Field(default=0, ge=0, description="Total suma de femenino y masculino.")
    porcentaje_femenino: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Porcentaje de sexo femenino.")
    porcentaje_masculino: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Porcentaje de sexo masculino.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }

    @model_validator(mode="after")
    def sincronizar_totales_y_porcentajes(self) -> "DistribucionSexoDocumental":
        suma = self.femenino + self.masculino
        if self.total == 0 and suma > 0:
            object.__setattr__(self, "total", suma)
        tot = self.total if self.total > 0 else suma
        if tot > 0:
            if self.porcentaje_femenino is None:
                object.__setattr__(self, "porcentaje_femenino", round((self.femenino / tot) * 100.0, 2))
            if self.porcentaje_masculino is None:
                object.__setattr__(self, "porcentaje_masculino", round((self.masculino / tot) * 100.0, 2))
        return self


class MetricasRecurrenciaDocumental(BaseModel):
    """
    Métricas de participación neta, recurrencia y asistencia institucional.
    Aplica la Regla Participación ≠ Persona.
    """
    total_asistencia_bruta: int = Field(default=0, ge=0, description="Total de participaciones o asistencias brutas.")
    total_personas_unicas: int = Field(default=0, ge=0, description="Total de personas únicas netas.")
    total_recurrencia: int = Field(default=0, ge=0, description="Total de asistencias recurrentes.")
    tasa_recurrencia: float = Field(default=0.0, ge=0.0, le=100.0, description="Tasa porcentual de recurrencia.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


class ConteoEstamentoDocumental(BaseModel):
    """
    Conteo por estamento institucional segregado por sexo canónico.
    """
    femenino: int = Field(default=0, ge=0, description="Participantes femeninas en el estamento.")
    masculino: int = Field(default=0, ge=0, description="Participantes masculinos en el estamento.")
    total: int = Field(default=0, ge=0, description="Total en el estamento.")
    porcentaje_del_total: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Porcentaje respecto al gran total.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


class ItemCarreraDocumental(BaseModel):
    """
    Distribución de estudiantes por carrera universitaria respaldada en fuentes.
    Si una carrera no fue declarada en la matriz nominal, no se inventa.
    """
    carrera: str = Field(..., description="Nombre o abreviatura de la carrera universitaria.")
    femenino: int = Field(default=0, ge=0, description="Estudiantes de sexo femenino.")
    masculino: int = Field(default=0, ge=0, description="Estudiantes de sexo masculino.")
    total: int = Field(default=0, ge=0, description="Total de estudiantes en la carrera.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ItemSedeDocumental(BaseModel):
    """
    Resumen cuantitativo de actividades y participantes por sede universitaria.
    """
    sede: str = Field(..., description="Nombre de la sede o campus universitario.")
    total_actividades: int = Field(default=0, ge=0, description="Cantidad de actividades realizadas en la sede.")
    total_asistencias: int = Field(default=0, ge=0, description="Total de asistencias registradas en la sede.")
    femenino: int = Field(default=0, ge=0, description="Asistencias de sexo femenino.")
    masculino: int = Field(default=0, ge=0, description="Asistencias de sexo masculino.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ItemTerritorioDocumental(BaseModel):
    """
    Cobertura territorial por departamento respaldado por las fuentes.
    """
    departamento: str = Field(..., description="Nombre formal del departamento o región.")
    municipios: List[str] = Field(default_factory=list, description="Municipios atendidos en este departamento.")
    total_actividades: int = Field(default=0, ge=0, description="Total de actividades en el departamento.")
    total_asistencias: int = Field(default=0, ge=0, description="Total de asistencias en el departamento.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ItemMunicipioDocumental(BaseModel):
    """
    Cobertura territorial por municipio respaldado por las fuentes.
    """
    municipio: str = Field(..., description="Nombre formal del municipio.")
    departamento: Optional[str] = Field(default=None, description="Departamento al que pertenece el municipio.")
    total_actividades: int = Field(default=0, ge=0, description="Total de actividades en el municipio.")
    total_asistencias: int = Field(default=0, ge=0, description="Total de asistencias en el municipio.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ItemComparativaDimension(BaseModel):
    """
    Comparación dimensional entre dos fuentes (ej. M1 vs Nominales o Narrativo vs Nominal).
    """
    dimension: str = Field(..., description="Nombre de la dimensión evaluada (Femenino, Masculino, Total, etc.).")
    fuente_a_nombre: str = Field(..., description="Nombre formal de Fuente A.")
    fuente_b_nombre: str = Field(..., description="Nombre formal de Fuente B.")
    valor_fuente_a: Optional[int] = Field(default=None, description="Valor en Fuente A.")
    valor_fuente_b: Optional[int] = Field(default=None, description="Valor en Fuente B.")
    delta: Optional[int] = Field(default=None, description="Diferencia matemática: Fuente B - Fuente A.")
    estado: EstadoDiscrepancia = Field(default=EstadoDiscrepancia.CONCORDANTE, description="Estado de concordancia.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }

    @property
    def m1(self) -> Optional[int]:
        return self.valor_fuente_a

    @property
    def nominal(self) -> Optional[int]:
        return self.valor_fuente_b


class FilaEstamentoDetalle(BaseModel):
    """
    Fila de detalle por estamento para la tabla Word de 13 columnas y fichas individuales.
    Aplica rigurosamente la separación entre Docentes y Administrativos.
    """
    tipo_estamento: str = Field(
        ...,
        description="Denominación institucional (ej. '1. Docentes', '2. Estudiantes', '3. Administrativos', etc.)."
    )
    femenino: int = Field(default=0, ge=0, description="Participantes de sexo femenino.")
    masculino: int = Field(default=0, ge=0, description="Participantes de sexo masculino.")
    total: int = Field(default=0, ge=0, description="Total de participantes en este estamento.")
    estado: str = Field(default="APTO", description="Condición de auditoría del estamento.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @model_validator(mode="after")
    def verificar_suma(self) -> "FilaEstamentoDetalle":
        suma = self.femenino + self.masculino
        if suma > 0:
            if self.total == 0:
                object.__setattr__(self, "total", suma)
            elif self.total != suma:
                raise ValueError(
                    f"Inconsistencia en estamento '{self.tipo_estamento}': total {self.total} "
                    f"!= femenino {self.femenino} + masculino {self.masculino} ({suma})."
                )
        return self


class ComparativaTotalesActividad(BaseModel):
    """
    Comparativa explícita de totales declarados en M1 frente a totales nominales calculados (M2–M5).
    Conserva ambos valores sin alterar ninguno.
    """
    total_m1: Optional[int] = Field(default=None, description="Total general declarado en M1.")
    femenino_m1: Optional[int] = Field(default=None, description="Mujeres / Femenino declarado en M1.")
    masculino_m1: Optional[int] = Field(default=None, description="Varones / Masculino declarado en M1.")
    total_nominal: int = Field(default=0, ge=0, description="Total de participantes nominales calculados.")
    femenino_nominal: int = Field(default=0, ge=0, description="Participantes femeninas nominales.")
    masculino_nominal: int = Field(default=0, ge=0, description="Participantes masculinos nominales.")
    delta_total: Optional[int] = Field(default=None, description="Delta total: Nominal - M1.")
    delta_femenino: Optional[int] = Field(default=None, description="Delta femenino: Nominal - M1.")
    delta_masculino: Optional[int] = Field(default=None, description="Delta masculino: Nominal - M1.")
    estado: EstadoDiscrepancia = Field(default=EstadoDiscrepancia.CONCORDANTE, description="Estado de concordancia.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


class TotalesComparativosDocumentales(BaseModel):
    """
    Totales acumulados globales para la matriz general de actividades.
    """
    total_actividades: int = Field(default=0, ge=0, description="Total de actividades listadas.")
    total_m1: Optional[int] = Field(default=None, description="Gran total acumulado M1.")
    femenino_m1: Optional[int] = Field(default=None, description="Total femenino acumulado M1.")
    masculino_m1: Optional[int] = Field(default=None, description="Total masculino acumulado M1.")
    total_nominal: int = Field(default=0, ge=0, description="Gran total nominal acumulado.")
    femenino_nominal: int = Field(default=0, ge=0, description="Total femenino nominal acumulado.")
    masculino_nominal: int = Field(default=0, ge=0, description="Total masculino nominal acumulado.")
    estudiantes_nominal: int = Field(default=0, ge=0, description="Total estudiantes nominales.")
    docentes_nominal: int = Field(default=0, ge=0, description="Total docentes nominales.")
    administrativos_nominal: int = Field(default=0, ge=0, description="Total administrativos nominales.")
    colaboradores_nominal: int = Field(default=0, ge=0, description="Total colaboradores nominales.")
    beneficiarios_nominal: int = Field(default=0, ge=0, description="Total beneficiarios nominales.")
    estado_global: EstadoDiscrepancia = Field(
        default=EstadoDiscrepancia.CONCORDANTE,
        description="Estado general de concordancia de la matriz."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


# ============================================================================
# SECCIÓN 1: PORTADA
# ============================================================================

class PortadaDocumental(BaseModel):
    """
    Modelo representativo de la Sección 1: Portada institucional.
    No inventa fechas ni lugares que no estén respaldados por metadatos oficiales.
    """
    titulo: Optional[str] = Field(default=None, description="Título formal del informe institucional.")
    subtitulo: Optional[str] = Field(default=None, description="Subtítulo descriptivo institucional.")
    universidad: Optional[str] = Field(default=None, description="Nombre oficial de la institución universitaria.")
    lema: Optional[str] = Field(default=None, description="Lema oficial institucional.")
    area_responsable: Optional[str] = Field(default=None, description="Área institucional responsable del informe.")
    periodo_texto: Optional[str] = Field(default=None, description="Denominación formal y legible del período.")
    fecha_emision: Optional[str] = Field(default=None, description="Fecha formal de emisión. Si no existe, es None.")
    lugar_emision: Optional[str] = Field(default=None, description="Lugar formal de emisión. Si no existe, es None.")
    version_sistema: Optional[str] = Field(default=None, description="Versión formal del sistema generador.")
    metadatos: Optional[MetadatosInstitucionales] = Field(default=None, description="Metadatos institucionales fuente.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


# ============================================================================
# SECCIÓN 2: RESUMEN EJECUTIVO
# ============================================================================

class ResumenEjecutivoDocumental(BaseModel):
    """
    Modelo representativo de la Sección 2: Resumen Ejecutivo institucional.
    Presenta métricas agregadas globales verificadas sin narrativa inventada.
    """
    periodo: PeriodoConsolidacion = Field(..., description="Definición formal del período consolidado.")
    total_actividades: int = Field(default=0, ge=0, description="Cantidad total de actividades consolidadas.")
    total_asistencia_bruta: int = Field(default=0, ge=0, description="Total de asistencias brutas.")
    total_personas_unicas: int = Field(default=0, ge=0, description="Total de personas únicas netas.")
    total_recurrencia: int = Field(default=0, ge=0, description="Total de asistencias recurrentes.")
    tasa_recurrencia: float = Field(default=0.0, ge=0.0, le=100.0, description="Tasa porcentual de recurrencia.")
    distribucion_sexo: DistribucionSexoDocumental = Field(
        ...,
        description="Distribución de género en semántica canónica FEMENINO / MASCULINO."
    )
    total_discrepancias: int = Field(default=0, ge=0, description="Total de discrepancias que requieren revisión.")
    actividades_concordantes: int = Field(default=0, ge=0, description="Cantidad de actividades 100% concordantes.")
    actividades_con_observaciones: int = Field(default=0, ge=0, description="Actividades con al menos una discrepancia.")
    total_fuentes_faltantes: int = Field(default=0, ge=0, description="Cantidad de fuentes nominales faltantes.")
    alertas_principales: List[str] = Field(default_factory=list, description="Alertas emitidas por auditoría.")
    sinopsis: Optional[str] = Field(default=None, description="Sinopsis formal respaldada. Si no existe, es None.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


# ============================================================================
# SECCIÓN 3: MATRIZ GENERAL DE ACTIVIDADES
# ============================================================================

class FilaActividadDocumental(BaseModel):
    """
    Fila individual de actividad dentro de la Matriz General Documental (Sección 3).
    Representa simultáneamente valores de M1, Nominales, Narrativos y Discrepancias.
    """
    id_actividad: str = Field(..., description="Identificador unívoco técnico de la actividad.")
    nombre_actividad: str = Field(..., description="Nombre formal de la actividad.")
    eje_estrategico: Optional[str] = Field(default=None, description="Eje o ámbito estratégico.")
    tipo_actividad: Optional[str] = Field(default=None, description="Tipo o modalidad de evento.")
    area_responsable: Optional[str] = Field(default=None, description="Área institucional ejecutora.")
    sede: str = Field(..., description="Sede universitaria de realización.")
    departamento: Optional[str] = Field(default=None, description="Departamento territorial.")
    municipio: Optional[str] = Field(default=None, description="Municipio territorial.")
    fecha: Optional[Union[date, str]] = Field(default=None, description="Fecha de realización reportada.")

    # Valores M1 (Declarados originalmente en Matriz 1)
    total_m1: Optional[int] = Field(default=None, description="Total general declarado en M1.")
    femenino_m1: Optional[int] = Field(default=None, description="Mujeres / Femenino declarado en M1.")
    masculino_m1: Optional[int] = Field(default=None, description="Varones / Masculino declarado en M1.")
    estudiantes_m1: Optional[int] = Field(default=None, description="Estudiantes declarados en M1 si existieren.")
    docentes_m1: Optional[int] = Field(default=None, description="Docentes declarados en M1 si existieren.")
    administrativos_m1: Optional[int] = Field(default=None, description="Administrativos declarados en M1 si existieren.")
    colaboradores_m1: Optional[int] = Field(default=None, description="Colaboradores declarados en M1 si existieren.")
    beneficiarios_m1: Optional[int] = Field(default=None, description="Beneficiarios declarados en M1 si existieren.")

    # Valores Nominales (Derivados matemáticamente de las matrices M2–M5)
    total_nominal: int = Field(default=0, ge=0, description="Total de participantes nominales.")
    femenino_nominal: int = Field(default=0, ge=0, description="Participantes femeninas nominales.")
    masculino_nominal: int = Field(default=0, ge=0, description="Participantes masculinos nominales.")
    estudiantes_nominal: int = Field(default=0, ge=0, description="Estudiantes nominales (M2).")
    docentes_nominal: int = Field(default=0, ge=0, description="Docentes nominales (M3).")
    administrativos_nominal: int = Field(default=0, ge=0, description="Administrativos nominales (M3).")
    colaboradores_nominal: int = Field(default=0, ge=0, description="Colaboradores nominales (M4).")
    beneficiarios_nominal: int = Field(default=0, ge=0, description="Beneficiarios nominales (M5).")

    # Información narrativa explícita (si fue suministrada)
    datos_narrativos: Optional[Dict[str, int]] = Field(
        default=None,
        description="Valores reportados en informes narrativos o minutas institucionales."
    )

    # Sub-filas de estamentos para tablas detalladas
    desglose_estamentos: List[FilaEstamentoDetalle] = Field(
        default_factory=list,
        description="Sub-filas de estamentos (Docentes, Estudiantes, Administrativos, Colaboradores, Beneficiarios)."
    )

    # Auditoría y discrepancias
    discrepancias: List[ItemDiscrepanciaDocumental] = Field(
        default_factory=list,
        description="Discrepancias institucionales asociadas a la actividad."
    )
    estado_auditoria: EstadoDiscrepancia = Field(
        default=EstadoDiscrepancia.CONCORDANTE,
        description="Estado general de auditoría de la actividad."
    )
    tiene_discrepancias: bool = Field(default=False, description="True si presenta discrepancias activas.")

    # Trazabilidad
    trazabilidad_fuentes: List[TrazabilidadFuenteDocumental] = Field(
        default_factory=list,
        description="Lista de fuentes matrices, hojas y filas que componen esta actividad."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    # Propiedades de compatibilidad para nombres alternos
    @property
    def mujeres_m1(self) -> Optional[int]:
        return self.femenino_m1

    @property
    def varones_m1(self) -> Optional[int]:
        return self.masculino_m1

    @property
    def mujeres_nominal(self) -> int:
        return self.femenino_nominal

    @property
    def varones_nominal(self) -> int:
        return self.masculino_nominal

    @property
    def estudiantes(self) -> int:
        return self.estudiantes_nominal

    @property
    def docentes(self) -> int:
        return self.docentes_nominal

    @property
    def administrativos(self) -> int:
        return self.administrativos_nominal

    @property
    def colaboradores(self) -> int:
        return self.colaboradores_nominal

    @property
    def beneficiarios(self) -> int:
        return self.beneficiarios_nominal


class MatrizGeneralDocumental(BaseModel):
    """
    Modelo representativo de la Sección 3: Matriz Consolidada General de Actividades.
    Contiene la lista completa de actividades con sus columnas declaradas y nominales.
    """
    filas: List[FilaActividadDocumental] = Field(default_factory=list, description="Listado de filas de actividades.")
    total_actividades: int = Field(default=0, ge=0, description="Total de actividades consolidadas.")
    totales_generales: TotalesComparativosDocumentales = Field(
        ...,
        description="Totales acumulados comparativos de la matriz general."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


# ============================================================================
# SECCIÓN 4: FICHAS DE DETALLE POR ACTIVIDAD
# ============================================================================

class FichaActividadDocumental(BaseModel):
    """
    Modelo representativo de la Sección 4: Ficha individual detallada de actividad.
    No inventa programas, proyectos, descripciones, enlaces ni actas que no existan en las fuentes.
    """
    id_actividad: str = Field(..., description="Identificador unívoco técnico de la actividad.")
    nombre_actividad: str = Field(..., description="Nombre formal de la actividad.")
    sede: str = Field(..., description="Sede universitaria de realización.")
    fecha: Optional[Union[date, str]] = Field(default=None, description="Fecha de realización reportada.")
    departamento: Optional[str] = Field(default=None, description="Departamento territorial.")
    municipio: Optional[str] = Field(default=None, description="Municipio territorial.")
    comunidad: Optional[str] = Field(default=None, description="Comunidad si existe en las fuentes. Si no, None.")
    eje: Optional[str] = Field(default=None, description="Eje estratégico vinculado.")
    programa: Optional[str] = Field(default=None, description="Programa institucional vinculado. Si no existe, None.")
    proyecto: Optional[str] = Field(default=None, description="Proyecto institucional vinculado. Si no existe, None.")
    area_responsable: Optional[str] = Field(default=None, description="Área institucional responsable. Si no existe, None.")
    tipo_evento: Optional[str] = Field(default=None, description="Tipo institucional de evento. Si no existe, None.")
    descripcion_resultados: Optional[str] = Field(
        default=None,
        description="Descripción o resultados reportados. Si no existe en la fuente, permanece None."
    )
    comparativa_m1_vs_nominal: ComparativaTotalesActividad = Field(
        ...,
        description="Comparativa numérica explícita entre valores declarados M1 y calculados nominalmente."
    )
    desglose_estamentos: List[FilaEstamentoDetalle] = Field(
        default_factory=list,
        description="Sub-filas de estamentos diferenciando docentes, estudiantes, administrativos, etc."
    )
    discrepancias: List[ItemDiscrepanciaDocumental] = Field(
        default_factory=list,
        description="Discrepancias activas asociadas a la actividad."
    )
    estado_auditoria: EstadoDiscrepancia = Field(
        default=EstadoDiscrepancia.CONCORDANTE,
        description="Estado de auditoría (CONCORDANTE o REQUIERE_REVISION)."
    )
    trazabilidad_fuentes: List[TrazabilidadFuenteDocumental] = Field(
        default_factory=list,
        description="Trazabilidad exacta de las matrices y filas participantes."
    )
    datos_narrativos: Optional[Dict[str, int]] = Field(
        default=None,
        description="Valores del informe narrativo asociados si existieren."
    )
    enlaces_evidencias: List[str] = Field(
        default_factory=list,
        description="Enlaces a publicaciones oficiales respaldadas. Si no existen, lista vacía."
    )
    referencias_actas: List[str] = Field(
        default_factory=list,
        description="Referencias a actas físicas respaldadas. Si no existen, lista vacía."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


# ============================================================================
# SECCIÓN 5: ANÁLISIS DEMOGRÁFICO Y SEXO
# ============================================================================

class DemografiaDocumental(BaseModel):
    """
    Modelo representativo de la Sección 5: Análisis Demográfico y Sexo.
    Preserva estrictamente FEMENINO / MASCULINO y métricas de recurrencia.
    """
    total_participaciones: int = Field(default=0, ge=0, description="Total de participaciones registradas.")
    total_personas_unicas: int = Field(default=0, ge=0, description="Total de personas únicas netas.")
    distribucion_sexo_nominal: DistribucionSexoDocumental = Field(
        ...,
        description="Distribución por sexo calculada sobre filas nominales (M2–M5)."
    )
    distribucion_sexo_m1: Optional[DistribucionSexoDocumental] = Field(
        default=None,
        description="Distribución por sexo reportada formalmente en Matriz 1 si existiere."
    )
    comparativa_sexo: List[ItemComparativaDimension] = Field(
        default_factory=list,
        description="Comparativa M1 vs Nominales para femenino, masculino y total."
    )
    metricas_recurrencia: MetricasRecurrenciaDocumental = Field(
        ...,
        description="Métricas de asistencia bruta, personas únicas, recurrencia y tasa."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


# ============================================================================
# SECCIÓN 6: ESTAMENTOS Y CARRERAS
# ============================================================================

class EstamentosDocumental(BaseModel):
    """
    Modelo representativo de la Sección 6: Estamentos y Carreras Universitarias.
    Separa de manera obligatoria: Estudiantes, Docentes, Administrativos, Colaboradores y Beneficiarios.
    """
    estudiantes: ConteoEstamentoDocumental = Field(..., description="Participantes clasificados como estudiantes.")
    docentes: ConteoEstamentoDocumental = Field(..., description="Personal académico / docente (no fusionar con admin).")
    administrativos: ConteoEstamentoDocumental = Field(..., description="Personal administrativo institucional.")
    colaboradores: ConteoEstamentoDocumental = Field(..., description="Colaboradores de entidades externas (M4).")
    beneficiarios: ConteoEstamentoDocumental = Field(..., description="Protagonistas y beneficiarios comunitarios (M5).")
    total_general: int = Field(default=0, ge=0, description="Suma total de todos los estamentos nominales.")
    desglose_carreras: List[ItemCarreraDocumental] = Field(
        default_factory=list,
        description="Desglose de estudiantes por carrera universitaria respaldada en fuentes."
    )
    comparativa_estamentos: List[ItemComparativaDimension] = Field(
        default_factory=list,
        description="Comparativa M1 vs Nominal para cada estamento institucional."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


# ============================================================================
# SECCIÓN 7: TERRITORIO / COBERTURA
# ============================================================================

class TerritorioDocumental(BaseModel):
    """
    Modelo representativo de la Sección 7: Cobertura Territorial y Sedes.
    No asume ni inventa comunidades que no figuren en los datos de entrada.
    """
    desglose_sedes: List[ItemSedeDocumental] = Field(
        default_factory=list,
        description="Resumen de actividades y participantes por campus universitario."
    )
    desglose_departamentos: List[ItemTerritorioDocumental] = Field(
        default_factory=list,
        description="Distribución geográfica por departamentos o regiones autónomas."
    )
    desglose_municipios: List[ItemMunicipioDocumental] = Field(
        default_factory=list,
        description="Distribución geográfica por municipios respaldados."
    )
    comunidades: List[str] = Field(
        default_factory=list,
        description="Listado de comunidades explícitamente reportadas. Si no hay, lista vacía."
    )
    total_sedes_participantes: int = Field(default=0, ge=0, description="Cantidad de sedes con actividades.")
    total_departamentos_cubiertos: int = Field(default=0, ge=0, description="Total departamentos cubiertos.")
    total_municipios_cubiertos: int = Field(default=0, ge=0, description="Total municipios cubiertos.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


# ============================================================================
# SECCIÓN 8: SALUD DE DATOS / AUDITORÍA
# ============================================================================

class AuditoriaDocumental(BaseModel):
    """
    Modelo representativo de la Sección 8: Salud de Datos y Auditoría de Discrepancias.
    Permite generar directamente la tabla:
    DIMENSIÓN | FUENTE A | FUENTE B | DELTA | ESTADO
    sin recalcular la consolidación.
    """
    total_actividades_evaluadas: int = Field(default=0, ge=0, description="Total de actividades evaluadas.")
    actividades_concordantes: int = Field(default=0, ge=0, description="Actividades con total coincidencia (0 deltas).")
    actividades_con_discrepancias: int = Field(default=0, ge=0, description="Actividades con al menos una discrepancia.")
    total_discrepancias_activas: int = Field(default=0, ge=0, description="Cantidad de discrepancias REQUIERE_REVISION.")
    total_concordancias: int = Field(default=0, ge=0, description="Cantidad de dimensiones con estado CONCORDANTE.")
    total_fuentes_faltantes: int = Field(default=0, ge=0, description="Cantidad de fuentes nominales no entregadas.")
    invariante_verificada: bool = Field(
        default=True,
        description="True si la auditoría confirma que ninguna suma nominal o agregada fue alterada."
    )
    tabla_discrepancias: List[ItemDiscrepanciaDocumental] = Field(
        default_factory=list,
        description="Listado tabular formal de discrepancias con categoría, fuentes, valores, delta y estado."
    )
    fuentes_procesadas: List[RegistroFuenteArchivo] = Field(
        default_factory=list,
        description="Archivos procesados con sus hashes criptográficos inmutables SHA-256."
    )
    alertas: List[str] = Field(default_factory=list, description="Alertas emitidas durante el cotejo institucional.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


# ============================================================================
# SECCIÓN 9: CONCLUSIONES
# ============================================================================

class ConclusionDocumental(BaseModel):
    """
    Modelo representativo de la Sección 9: Conclusiones del Informe Institucional.
    Derivado estrictamente de las métricas y hallazgos cuantitativos, sin inventar juicios de valor.
    """
    puntos_clave: List[str] = Field(
        default_factory=list,
        description="Puntos cuantitativos y hallazgos consolidados derivados de los datos."
    )
    recomendaciones_auditoria: List[str] = Field(
        default_factory=list,
        description="Recomendaciones operativas respecto a las discrepancias detectadas."
    )
    dictamen_auditoria: str = Field(
        default="CONCORDANTE",
        description="Dictamen general ('CONCORDANTE' o 'CON OBSERVACIONES')."
    )
    resumen_narrativo: Optional[str] = Field(
        default=None,
        description="Resumen narrativo formal si fue suministrado. Si no, None."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


# ============================================================================
# SECCIÓN 10: ANEXOS
# ============================================================================

class AnexosDocumentales(BaseModel):
    """
    Modelo representativo de la Sección 10: Anexos y Metadatos de Trazabilidad.
    Confirma la conservación de los registros históricos (32 filas de M5) y archivos procesados.
    """
    registro_fuentes: List[RegistroFuenteArchivo] = Field(
        default_factory=list,
        description="Matrices oficiales con sus hashes criptográficos SHA-256."
    )
    total_registros_historicos_m5: int = Field(
        default=32,
        ge=0,
        description="Cantidad de registros históricos de M5 fuera del período preservados intactos."
    )
    total_actividades_fuera_periodo: int = Field(
        default=0,
        ge=0,
        description="Cantidad de actividades de M1 situadas fuera de la ventana del período."
    )
    glosario_estamentos: Dict[str, str] = Field(
        default_factory=dict,
        description="Definición formal de los estamentos institucionales."
    )
    glosario_estados_auditoria: Dict[str, str] = Field(
        default_factory=dict,
        description="Definición de estados de auditoría (CONCORDANTE, REQUIERE_REVISION)."
    )
    metadatos_tecnicos: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos de trazabilidad técnica del motor (UUID ejecución, etc.)."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


# ============================================================================
# MODELO AGREGADOR RAÍZ: DOCUMENTO CONSOLIDADO
# ============================================================================

class DocumentoConsolidado(BaseModel):
    """
    Modelo documental raíz institucional para el consolidado de actividades.
    Integra de forma estructurada e inmutable las 10 secciones documentales,
    completamente desacoplado de python-docx y de la capa de renderizado visual.
    """
    id_documento: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único del documento consolidado (UUID v4)."
    )
    periodo: PeriodoConsolidacion = Field(..., description="Período formal de consolidación del informe.")
    metadatos: Optional[MetadatosInstitucionales] = Field(
        default=None,
        description="Metadatos institucionales oficiales si fueron proporcionados."
    )

    # Las 10 secciones institucionales obligatorias
    portada: PortadaDocumental = Field(..., description="Sección 1: Portada institucional.")
    resumen_ejecutivo: ResumenEjecutivoDocumental = Field(..., description="Sección 2: Resumen Ejecutivo.")
    matriz_general: MatrizGeneralDocumental = Field(..., description="Sección 3: Matriz Consolidada General.")
    fichas_actividades: List[FichaActividadDocumental] = Field(
        default_factory=list,
        description="Sección 4: Fichas individuales de detalle por actividad."
    )
    demografia: DemografiaDocumental = Field(..., description="Sección 5: Análisis Demográfico y Sexo.")
    estamentos: EstamentosDocumental = Field(..., description="Sección 6: Estamentos y Carreras.")
    territorio: TerritorioDocumental = Field(..., description="Sección 7: Cobertura Territorial y Sedes.")
    auditoria: AuditoriaDocumental = Field(..., description="Sección 8: Salud de Datos y Auditoría de Discrepancias.")
    conclusiones: ConclusionDocumental = Field(..., description="Sección 9: Conclusiones del Informe.")
    anexos: AnexosDocumentales = Field(..., description="Sección 10: Anexos y Metadatos Técnicos.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }

    @property
    def total_actividades(self) -> int:
        """Cantidad de actividades en la matriz general."""
        return len(self.matriz_general.filas)

    @property
    def tiene_discrepancias(self) -> bool:
        """Indica si el informe presenta discrepancias que requieran revisión institucional."""
        return self.auditoria.total_discrepancias_activas > 0
