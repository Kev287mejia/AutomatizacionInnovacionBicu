"""
app.word_consolidator.models

Modelos de datos internos inmutables y fuertemente tipados para el generador
del Documento Word Consolidado Institucional (Fase 14.2).
Compatibles con Pydantic v2, totalmente desacoplados de openpyxl, python-docx y CLI.
Reutiliza de forma canónica EstadisticaGlobal de app.statistics.models.
"""

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator
from app.statistics.models import EstadisticaGlobal


class TipoPeriodo(str, Enum):
    """Tipos de períodos admitidos para la consolidación institucional."""
    SEMANA = "SEMANA"
    MES = "MES"
    TRIMESTRE = "TRIMESTRE"
    SEMESTRE = "SEMESTRE"
    ANIO = "ANIO"
    PERSONALIZADO = "PERSONALIZADO"


class EstadoDiscrepancia(str, Enum):
    """Estados del ciclo de vida de una discrepancia detectada entre M1 y M2–M5."""
    REQUIERE_REVISION = "REQUIERE_REVISION"
    CONCORDANTE = "CONCORDANTE"
    ACLARADO = "ACLARADO"
    RESUELTO = "RESUELTO"


class PeriodoConsolidacion(BaseModel):
    """
    Representa el rango temporal formal seleccionado para la consolidación.
    Permite separar el lote activo de consolidación del histórico acumulado en las matrices.
    """
    tipo_periodo: TipoPeriodo = Field(..., description="Tipo o escala del período seleccionado.")
    anio: int = Field(..., ge=2000, le=2100, description="Año calendario del período.")
    mes: Optional[int] = Field(default=None, ge=1, le=12, description="Número de mes (1..12) si aplica.")
    semana: Optional[int] = Field(default=None, ge=1, le=53, description="Número de semana operativa si aplica.")
    fecha_inicio: Optional[Union[date, str]] = Field(default=None, description="Fecha de inicio formal del período.")
    fecha_fin: Optional[Union[date, str]] = Field(default=None, description="Fecha de corte formal del período.")
    etiqueta: str = Field(..., description="Denominación textual legible oficial del período.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @field_validator("etiqueta")
    @classmethod
    def validar_etiqueta_no_vacia(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La etiqueta del período no puede estar vacía.")
        return v.strip()


class DiscrepanciaItem(BaseModel):
    """
    Representación inmutable de una discrepancia entre M1 y la sumatoria nominal de M2–M5
    (o entre Fuente A y Fuente B).
    Cumple rigurosamente el protocolo de 9 pasos de la Regla de Discrepancia Institucional.
    """
    id_actividad: str = Field(..., description="Identificador unívoco interno de la actividad.")
    nombre_actividad: str = Field(..., description="Nombre formal de la actividad evaluada.")
    estamento: str = Field(..., description="Estamento, dimensión o categoría evaluada (Estudiantes, Docentes, Total, etc.).")
    fuente_m1: str = Field(default="Matriz 1: Consolidado de Actividades", description="Fuente institucional agregada (Fuente A).")
    fuentes_nominales: List[str] = Field(
        default_factory=list,
        description="Lista de matrices nominales participantes (M2, M3, M4 o M5) (Fuente B)."
    )
    fuente_a: Optional[str] = Field(default=None, description="Identificación formal de la Fuente A.")
    fuente_b: Optional[str] = Field(default=None, description="Identificación formal de la Fuente B.")
    valor_m1: int = Field(default=0, ge=0, description="Valor agregado declarado originalmente en Matriz 1 / Fuente A.")
    valor_nominal: int = Field(default=0, ge=0, description="Valor calculado a partir de las filas nominales de M2..M5 / Fuente B.")
    valor_fuente_a: Optional[int] = Field(default=None, ge=0, description="Valor exacto en Fuente A.")
    valor_fuente_b: Optional[int] = Field(default=None, ge=0, description="Valor exacto en Fuente B.")
    diferencia: Optional[int] = Field(default=None, description="Diferencia matemática exacta (valor_m1 - valor_nominal o valor_fuente_b - valor_fuente_a).")
    delta: Optional[int] = Field(default=None, description="Delta institucional exacto: Fuente B (Nominal) - Fuente A (M1 / Narrativo).")
    estado: EstadoDiscrepancia = Field(
        default=EstadoDiscrepancia.REQUIERE_REVISION,
        description="Estado operativo de la discrepancia (CONCORDANTE o REQUIERE_REVISION)."
    )
    categoria_discrepancia: str = Field(
        default="ESTAMENTO",
        description="Categoría o dimensión de la discrepancia: TOTAL, ESTAMENTO, SEXO, FUENTE_FALTANTE, OTRO."
    )
    descripcion: str = Field(..., description="Explicación detallada y legible de la diferencia registrada.")
    trazabilidad: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos técnicos para trazabilidad (filas, columnas, nombres)."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @model_validator(mode="after")
    def verificar_diferencia_aritmetica(self) -> "DiscrepanciaItem":
        # Resolver valores de Fuente A y Fuente B
        v_a = self.valor_fuente_a if self.valor_fuente_a is not None else self.valor_m1
        v_b = self.valor_fuente_b if self.valor_fuente_b is not None else self.valor_nominal

        if self.valor_fuente_a is None:
            object.__setattr__(self, "valor_fuente_a", v_a)
        if self.valor_fuente_b is None:
            object.__setattr__(self, "valor_fuente_b", v_b)

        # Sincronizar valor_m1 y valor_nominal si se usó la nomenclatura fuente_a / fuente_b
        if self.valor_m1 == 0 and v_a != 0:
            object.__setattr__(self, "valor_m1", v_a)
        if self.valor_nominal == 0 and v_b != 0:
            object.__setattr__(self, "valor_nominal", v_b)

        # Resolver nombres de fuentes
        f_a = self.fuente_a if self.fuente_a is not None else self.fuente_m1
        f_b = (
            self.fuente_b
            if self.fuente_b is not None
            else (", ".join(self.fuentes_nominales) if self.fuentes_nominales else "Matrices Nominales (M2–M5)")
        )
        if self.fuente_a is None:
            object.__setattr__(self, "fuente_a", f_a)
        if self.fuente_b is None:
            object.__setattr__(self, "fuente_b", f_b)

        # Delta matemático canónico: Fuente B (Nominal) - Fuente A (M1 / Narrativo)
        delta_esperado = v_b - v_a
        diferencia_m1_menos_nom = v_a - v_b

        # Validar delta si fue provisto
        if self.delta is not None and self.delta != delta_esperado:
            raise ValueError(
                f"Inconsistencia en delta aritmético: se declaró {self.delta} "
                f"pero (Fuente B: {v_b} - Fuente A: {v_a}) = {delta_esperado}."
            )
        if self.delta is None:
            object.__setattr__(self, "delta", delta_esperado)

        # Validar diferencia si fue provista
        if self.diferencia is not None:
            if self.diferencia not in (diferencia_m1_menos_nom, delta_esperado):
                raise ValueError(
                    f"Inconsistencia en diferencia aritmética: se declaró {self.diferencia} "
                    f"pero (valor_m1: {v_a} - valor_nominal: {v_b}) = {diferencia_m1_menos_nom}."
                )
        else:
            object.__setattr__(self, "diferencia", diferencia_m1_menos_nom)

        return self


class RegistroFuenteArchivo(BaseModel):
    """
    Registro inmutable de trazabilidad y auditoría criptográfica de un archivo fuente procesado.
    """
    codigo_matriz: str = Field(..., description="Código formal de la matriz (M1, M2, M3, M4, M5).")
    nombre_archivo: str = Field(..., description="Nombre base del archivo procesado.")
    ruta_archivo: str = Field(..., description="Ruta o URI absoluta del archivo.")
    hash_sha256: str = Field(..., min_length=64, max_length=64, description="Hash criptográfico SHA-256 inmutable.")
    total_filas_leidas: int = Field(default=0, ge=0, description="Total de filas leídas en la matriz.")
    filas_en_periodo: int = Field(default=0, ge=0, description="Filas pertenecientes al período seleccionado.")
    fecha_modificacion: Optional[str] = Field(default=None, description="Fecha de última modificación del archivo.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class MetadatosInstitucionales(BaseModel):
    """
    Metadatos oficiales de la institución para encabezados, portadas y pies de página en Word.
    """
    universidad: str = Field(
        default="Bluefields Indian & Caribbean University (BICU)",
        description="Nombre oficial de la institución universitaria."
    )
    lema: str = Field(
        default="La Universidad de las Regiones Autónomas de la Costa Caribe Nicaragüense",
        description="Lema institucional oficial."
    )
    area_responsable: str = Field(
        default="Área de Innovación y Emprendimiento",
        description="Dirección o área universitaria ejecutora del informe."
    )
    programa: Optional[str] = Field(default=None, description="Programa institucional asociado.")
    departamento_institucional: Optional[str] = Field(default=None, description="Departamento institucional ejecutor.")
    lugar_emision: str = Field(default="Bilwi / Bluefields, Nicaragua", description="Sede o lugar de emisión.")
    version_sistema: str = Field(default="0.1.0", description="Versión formal del sistema generador.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class DesgloseEstamentoWord(BaseModel):
    """
    Representa una sub-fila de estamento dentro de la tabla institucional de 13 columnas del Word.
    Aplica rigurosamente la regla semántica:
      Femenino  -> Columna 'M' (Mujeres)
      Masculino -> Columna 'V' (Varones)
    """
    tipo_protagonistas: str = Field(
        ...,
        description="Denominación institucional del estamento (ej. '2. Estudiantes', '1. Maestras y maestros')."
    )
    mujeres: int = Field(default=0, ge=0, description="Participantes de sexo femenino (Columna 'M' en tabla Word).")
    varones: int = Field(default=0, ge=0, description="Participantes de sexo masculino (Columna 'V' en tabla Word).")
    total: int = Field(default=0, ge=0, description="Total suma de mujeres y varones en este estamento.")
    estado: str = Field(default="APTO", description="Condición de auditoría del estamento (APTO, REQUIERE_REVISION).")
    discrepancia: Optional[DiscrepanciaItem] = Field(
        default=None,
        description="Discrepancia documentada asociada a este estamento si existiere."
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @model_validator(mode="after")
    def verificar_suma_estamento(self) -> "DesgloseEstamentoWord":
        if self.total != (self.mujeres + self.varones):
            raise ValueError(
                f"El total ({self.total}) no coincide con la suma de mujeres ({self.mujeres}) "
                f"+ varones ({self.varones}) = {self.mujeres + self.varones}."
            )
        return self


class FilaActividadWord(BaseModel):
    """
    Representa una actividad completa preparada para ser renderizada en la tabla de 13 columnas
    y en su ficha descriptiva individual en el documento Word consolidado.
    """
    id_actividad: str = Field(..., description="Identificador unívoco técnico de la actividad (UUID v4).")
    nombre_actividad: str = Field(..., description="Nombre oficial de la actividad.")
    eje_vinculado: Optional[str] = Field(default=None, description="Código de eje institucional (ej. '11.41.67').")
    descripcion: Optional[str] = Field(default=None, description="Descripción cualitativa o resultados alcanzados.")
    sede: str = Field(..., description="Sede universitaria donde tuvo lugar el evento.")
    departamento: Optional[str] = Field(default=None, description="Departamento geográfico (ej. 'RACCN').")
    municipio: Optional[str] = Field(default=None, description="Municipio geográfico (ej. 'Puerto Cabezas').")
    tipo_actividad: Optional[str] = Field(default=None, description="Tipo institucional de evento.")
    desglose_estamentos: List[DesgloseEstamentoWord] = Field(
        default_factory=list,
        description="Sub-filas de estamentos (Estudiantes, Docentes, Admin, Colaboradores, Beneficiarios)."
    )
    total_mujeres: int = Field(default=0, ge=0, description="Total acumulado de mujeres en la actividad.")
    total_varones: int = Field(default=0, ge=0, description="Total acumulado de varones en la actividad.")
    gran_total: int = Field(default=0, ge=0, description="Total general de asistentes en la actividad.")
    enlaces_evidencias: List[str] = Field(default_factory=list, description="Enlaces web a publicaciones oficiales.")
    referencias_actas: List[str] = Field(default_factory=list, description="Identificadores o nombres de actas físicas.")
    discrepancias: List[DiscrepanciaItem] = Field(
        default_factory=list,
        description="Discrepancias institucionales detectadas en esta actividad."
    )

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @model_validator(mode="after")
    def validar_consistencia_totales(self) -> "FilaActividadWord":
        if self.desglose_estamentos:
            sum_m = sum(e.mujeres for e in self.desglose_estamentos)
            sum_v = sum(e.varones for e in self.desglose_estamentos)
            sum_t = sum(e.total for e in self.desglose_estamentos)

            # Si no fueron provistos explícitamente o difieren, se sincronizan con las sub-filas
            if self.total_mujeres != sum_m:
                object.__setattr__(self, "total_mujeres", sum_m)
            if self.total_varones != sum_v:
                object.__setattr__(self, "total_varones", sum_v)
            if self.gran_total != sum_t:
                object.__setattr__(self, "gran_total", sum_t)
        return self


class ReporteAuditoriaWord(BaseModel):
    """
    Contenedor de trazabilidad, salud de datos y metadatos de auditoría para la sección final del Word.
    """
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID de la corrida.")
    timestamp_generacion: str = Field(..., description="Marca temporal ISO de generación.")
    fuentes_procesadas: List[RegistroFuenteArchivo] = Field(
        default_factory=list,
        description="Listado de matrices oficiales con sus hashes criptográficos."
    )
    total_actividades: int = Field(default=0, ge=0, description="Total de actividades consolidadas.")
    total_participaciones_brutas: int = Field(default=0, ge=0, description="Total de participaciones brutas.")
    total_personas_unicas: int = Field(default=0, ge=0, description="Total de personas únicas netas.")
    total_discrepancias: int = Field(default=0, ge=0, description="Cantidad de discrepancias detectadas.")
    discrepancias: List[DiscrepanciaItem] = Field(default_factory=list, description="Detalle de discrepancias.")
    alertas: List[str] = Field(default_factory=list, description="Lista de advertencias emitidas.")
    invariante_verificada: bool = Field(
        default=True,
        description="True si la auditoría confirma que ninguna suma nominal o agregada fue alterada."
    )

    model_config = {
        "validate_assignment": True,
    }


class ContextoConsolidadoDocx(BaseModel):
    """
    Modelo agregador raíz que suministra el contexto íntegro necesario para la generación del DOCX.
    Desacopla totalmente la lógica de datos de la capa de renderizado documental.
    """
    institucion: MetadatosInstitucionales = Field(
        default_factory=MetadatosInstitucionales,
        description="Identificación y membrete institucional."
    )
    periodo: PeriodoConsolidacion = Field(..., description="Definición formal del período consolidado.")
    actividades: List[FilaActividadWord] = Field(
        default_factory=list,
        description="Lista de actividades formalizadas para la tabla de 13 columnas y fichas."
    )
    estadisticas_globales: EstadisticaGlobal = Field(
        ...,
        description="Instancia oficial del Motor Estadístico Institucional (Fase 7)."
    )
    auditoria: ReporteAuditoriaWord = Field(..., description="Metadatos de auditoría y trazabilidad criptográfica.")
    discrepancias_globales: List[DiscrepanciaItem] = Field(
        default_factory=list,
        description="Registro integral de discrepancias M1 vs M2–M5 marcadas como REQUIERE_REVISION."
    )

    model_config = {
        "validate_assignment": True,
    }

    @property
    def tiene_discrepancias(self) -> bool:
        """Indica si existen discrepancias activas que requieren revisión institucional."""
        return len(self.discrepancias_globales) > 0 or self.auditoria.total_discrepancias > 0


class FilaLeidaM1(BaseModel):
    """
    Representa una fila leída desde la Matriz 1 (Consolidado de Actividades).
    Conserva fielmente los valores extraídos de la hoja Excel con trazabilidad de coordenadas.
    """
    matriz_origen: str = Field(default="M1", description="Código de la matriz origen.")
    hoja: str = Field(..., description="Nombre de la hoja de cálculo de origen.")
    fila: int = Field(..., ge=2, description="Número de fila física en el libro Excel.")
    no: Optional[int] = Field(default=None, description="Número correlativo local (Columna A).")
    sede: str = Field(..., description="Sede o campus universitario ejecutor (Columna B).")
    dep_sede: Optional[str] = Field(default=None, description="Departamento territorial de la sede (Columna C).")
    mun_sede: Optional[str] = Field(default=None, description="Municipio territorial de la sede (Columna D).")
    programa: Optional[str] = Field(default=None, description="Programa institucional responsable (Columna E).")
    otro_programa: Optional[str] = Field(default=None, description="Denominación alterna de programa (Columna F).")
    proyecto: Optional[str] = Field(default=None, description="Proyecto específico vinculado (Columna G).")
    ambito: Optional[str] = Field(default=None, description="Ámbito institucional de cobertura (Columna H).")
    actividad: str = Field(..., description="Nombre oficial de la actividad (Columna I).")
    area_responsable: Optional[str] = Field(default=None, description="Área institucional ejecutora (Columna J).")
    financiamiento: Optional[str] = Field(default=None, description="Fuente de financiamiento (Columna K).")
    nombre_area: Optional[str] = Field(default=None, description="Nombre específico del área ejecutora (Columna L).")
    evento: Optional[str] = Field(default=None, description="Tipo de evento institucional (Columna M).")
    evento_otros: Optional[str] = Field(default=None, description="Detalle para evento no clasificado (Columna N).")
    fecha_evento: Optional[Union[date, str]] = Field(default=None, description="Fecha de realización reportada (Columna O).")
    resultados: Optional[str] = Field(default=None, description="Resultados cualitativos alcanzados (Columna P).")
    convenio: Optional[str] = Field(default=None, description="Indicador de convenio (Columna Q).")
    tipo_convenio: Optional[str] = Field(default=None, description="Clasificación de convenio (Columna R).")
    nombre_convenio: Optional[str] = Field(default=None, description="Denominación del convenio (Columna S).")
    region_atendida: Optional[str] = Field(default=None, description="Región geográfica atendida (Columna T).")
    departamento: Optional[str] = Field(default=None, description="Departamento donde se realizó (Columna U).")
    municipio: Optional[str] = Field(default=None, description="Municipio donde se realizó (Columna V).")
    comunidad: Optional[str] = Field(default=None, description="Comunidad de realización (Columna W).")
    total_comunidades: Optional[int] = Field(default=None, description="Total comunidades (Columna X).")
    total_atencion_m: int = Field(default=0, ge=0, description="Total Atención Masculino / Varones en Excel (Columna Y).")
    total_atencion_f: int = Field(default=0, ge=0, description="Total Atención Femenino / Mujeres en Excel (Columna Z).")
    total_estud_m_grado: int = Field(default=0, ge=0, description="Estudiantes grado masculinos (Columna AA).")
    total_estud_f_grado: int = Field(default=0, ge=0, description="Estudiantes grado femeninos (Columna AB).")
    total_estud_m_posgrado: int = Field(default=0, ge=0, description="Estudiantes posgrado masculinos (Columna AC).")
    total_estud_f_posgrado: int = Field(default=0, ge=0, description="Estudiantes posgrado femeninos (Columna AD).")
    total_docente_m: int = Field(default=0, ge=0, description="Docentes masculinos (Columna AE).")
    total_docente_f: int = Field(default=0, ge=0, description="Docentes femeninos (Columna AF).")
    total_administrativos_m: int = Field(default=0, ge=0, description="Administrativos masculinos (Columna AG).")
    total_administrativos_f: int = Field(default=0, ge=0, description="Administrativos femeninos (Columna AH).")
    total_partic_m_inst_publica: int = Field(default=0, ge=0, description="Colaboradores públicos masculinos (Columna AI).")
    total_partic_f_inst_publica: int = Field(default=0, ge=0, description="Colaboradores públicos femeninos (Columna AJ).")
    total_partic_m_inst_privada: int = Field(default=0, ge=0, description="Colaboradores privados masculinos (Columna AK).")
    total_partic_f_inst_privada: int = Field(default=0, ge=0, description="Colaboradores privados femeninos (Columna AL).")
    total_partic_m_ong: int = Field(default=0, ge=0, description="Colaboradores ONG masculinos (Columna AM).")
    total_partic_f_ong: int = Field(default=0, ge=0, description="Colaboradores ONG femeninos (Columna AN).")
    total_protagonistas_m: int = Field(default=0, ge=0, description="Beneficiarios masculinos (Columna AO).")
    total_protagonistas_f: int = Field(default=0, ge=0, description="Beneficiarios femeninos (Columna AP).")
    trazabilidad: Dict[str, Any] = Field(default_factory=dict, description="Metadatos de trazabilidad técnica.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @property
    def gran_total_m1(self) -> int:
        """Suma de total masculino + total femenino declarado en M1."""
        return self.total_atencion_m + self.total_atencion_f


class FilaLeidaNominal(BaseModel):
    """
    Representa una fila nominal leída desde las matrices M2, M3, M4 o M5.
    Preserva intactos los valores de celda sin corrección silenciosa.
    """
    matriz_origen: str = Field(..., description="Código formal de la matriz (M2, M3, M4 o M5).")
    hoja: str = Field(..., description="Nombre de la hoja de cálculo de origen.")
    fila: int = Field(..., ge=2, description="Número de fila física en el libro Excel.")
    no: Optional[int] = Field(default=None, description="Número correlativo local (Columna A).")
    sede: str = Field(..., description="Sede o campus universitario ejecutor (Columna B).")
    dep_sede: Optional[str] = Field(default=None, description="Departamento territorial de la sede (Columna C).")
    mun_sede: Optional[str] = Field(default=None, description="Municipio territorial de la sede (Columna D).")
    programa: Optional[str] = Field(default=None, description="Programa institucional responsable (Columna E).")
    otro_programa: Optional[str] = Field(default=None, description="Denominación alterna de programa (Columna F).")
    proyecto: Optional[str] = Field(default=None, description="Proyecto específico vinculado (Columna G).")
    ambito: Optional[str] = Field(default=None, description="Ámbito de la actividad (Columna H).")
    actividad: str = Field(..., description="Nombre oficial de la actividad (Columna I).")
    proposito: Optional[str] = Field(default=None, description="Propósito del evento (Columna J).")
    evento: Optional[str] = Field(default=None, description="Evento institucional (Columna K).")
    fecha_evento: Optional[Union[date, str]] = Field(default=None, description="Fecha de realización reportada si existiere.")
    eje_estrategia: Optional[str] = Field(default=None, description="Eje o línea estratégica (Columna O).")
    nombre_apellidos: str = Field(..., description="Nombre completo de la persona participante.")
    no_cedula: Optional[str] = Field(default=None, description="Cédula de identidad (preserva valor verbatim).")
    sexo: Optional[str] = Field(default=None, description="Sexo reportado en la celda.")
    fecha_nacimiento: Optional[Union[date, str]] = Field(default=None, description="Fecha de nacimiento reportada.")
    edad: Optional[Union[int, str]] = Field(default=None, description="Edad reportada o calculada por fórmula.")
    tipo_protagonistas: Optional[str] = Field(default=None, description="Tipo o clasificación institucional (ej. DOCENTE/ADMINISTRATIVO).")
    carrera: Optional[str] = Field(default=None, description="Carrera universitaria (preserva abreviaturas).")
    nivel_form: Optional[str] = Field(default=None, description="Nivel de formación (Grado, Posgrado, etc.).")
    cargo: Optional[str] = Field(default=None, description="Cargo laboral si aplica (M3/M4).")
    entidad: Optional[str] = Field(default=None, description="Entidad vinculada si aplica (M4).")
    beneficio: Optional[str] = Field(default=None, description="Beneficio recibido si aplica (M5).")
    trazabilidad: Dict[str, Any] = Field(default_factory=dict, description="Metadatos de trazabilidad técnica.")

    model_config = {
        "frozen": True,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ConjuntoMatricesLeidas(BaseModel):
    """
    Contenedor de todos los datos extraídos de las 5 matrices oficiales antes del filtrado temporal.
    """
    fuentes: Dict[str, RegistroFuenteArchivo] = Field(
        default_factory=dict,
        description="Metadatos y hashes SHA-256 de las matrices procesadas (M1..M5)."
    )
    actividades_m1: List[FilaLeidaM1] = Field(
        default_factory=list,
        description="Todas las filas de actividad leídas desde Matriz 1."
    )
    estudiantes_m2: List[FilaLeidaNominal] = Field(
        default_factory=list,
        description="Filas nominales de Matriz 2 (Estudiantes)."
    )
    academicos_admin_m3: List[FilaLeidaNominal] = Field(
        default_factory=list,
        description="Filas nominales de Matriz 3 (Académicos y Administrativos)."
    )
    colaboradores_m4: List[FilaLeidaNominal] = Field(
        default_factory=list,
        description="Filas nominales de Matriz 4 (Colaboradores)."
    )
    beneficiarios_m5: List[FilaLeidaNominal] = Field(
        default_factory=list,
        description="Filas nominales de Matriz 5 (Protagonistas y Beneficiarios, incluye históricos)."
    )
    errores_lectura: List[str] = Field(default_factory=list, description="Errores estructurales no fatales detectados.")
    observaciones: List[str] = Field(default_factory=list, description="Advertencias u observaciones emitidas.")

    model_config = {
        "validate_assignment": True,
    }

    @property
    def total_filas_nominales(self) -> int:
        return (
            len(self.estudiantes_m2)
            + len(self.academicos_admin_m3)
            + len(self.colaboradores_m4)
            + len(self.beneficiarios_m5)
        )


class ResultadoFiltradoPeriodo(BaseModel):
    """
    Resultado del filtrado temporal sobre el conjunto de matrices leídas.
    Separa de manera determinista y estricta el lote activo del período frente al histórico.
    """
    periodo: PeriodoConsolidacion = Field(..., description="Período formal de consolidación aplicado.")
    actividades_en_periodo: List[FilaLeidaM1] = Field(
        default_factory=list,
        description="Actividades de M1 pertenecientes al período seleccionado."
    )
    actividades_fuera_periodo: List[FilaLeidaM1] = Field(
        default_factory=list,
        description="Actividades de M1 fuera del período."
    )
    estudiantes_en_periodo: List[FilaLeidaNominal] = Field(default_factory=list)
    academicos_admin_en_periodo: List[FilaLeidaNominal] = Field(default_factory=list)
    colaboradores_en_periodo: List[FilaLeidaNominal] = Field(default_factory=list)
    beneficiarios_en_periodo: List[FilaLeidaNominal] = Field(default_factory=list)
    
    # Registros históricos que no deben desaparecer pero no pertenecen a este reporte
    nominales_historicos_fuera_periodo: List[FilaLeidaNominal] = Field(
        default_factory=list,
        description="Registros nominales fuera del período (ej. las 32 filas históricas de M5)."
    )

    model_config = {
        "validate_assignment": True,
    }

    @property
    def total_nominales_periodo(self) -> int:
        return (
            len(self.estudiantes_en_periodo)
            + len(self.academicos_admin_en_periodo)
            + len(self.colaboradores_en_periodo)
            + len(self.beneficiarios_en_periodo)
        )


class InformeDiscrepanciasActividad(BaseModel):
    """
    Informe consolidado de evaluación de discrepancias para una actividad institucional.
    Agrupa los resultados del cotejo M1 vs M2..M5 para todas las dimensiones auditadas.
    """
    id_actividad: str = Field(..., description="Identificador unívoco de la actividad.")
    nombre_actividad: str = Field(..., description="Nombre formal de la actividad.")
    clave_negocio: Optional[Tuple[str, str, Optional[str]]] = Field(
        default=None,
        description="Clave tripartita: (nombre_norm, sede_norm, fecha_norm)."
    )
    total_evaluaciones: int = Field(default=0, ge=0, description="Cantidad total de dimensiones comparadas.")
    total_discrepancias: int = Field(default=0, ge=0, description="Cantidad de dimensiones con estado REQUIERE_REVISION.")
    total_concordantes: int = Field(default=0, ge=0, description="Cantidad de dimensiones con estado CONCORDANTE.")
    tiene_discrepancias: bool = Field(default=False, description="True si existe al menos una discrepancia activa.")
    discrepancias: List[DiscrepanciaItem] = Field(default_factory=list, description="Detalle de discrepancias.")

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class ResultadoAuditoriaDiscrepancias(BaseModel):
    """
    Resultado global de la auditoría de discrepancias para todo el período consolidado.
    Contiene los reportes por actividad y el inventario global de discrepancias.
    """
    total_actividades_evaluadas: int = Field(default=0, ge=0, description="Total de actividades evaluadas.")
    actividades_con_discrepancias: int = Field(default=0, ge=0, description="Actividades con al menos una discrepancia.")
    actividades_concordantes: int = Field(default=0, ge=0, description="Actividades 100% concordantes.")
    total_discrepancias_activas: int = Field(default=0, ge=0, description="Total de discrepancias REQUIERE_REVISION.")
    total_concordancias: int = Field(default=0, ge=0, description="Total de comparaciones en estado CONCORDANTE.")
    informes_por_actividad: Dict[str, InformeDiscrepanciasActividad] = Field(
        default_factory=dict,
        description="Mapeo id_actividad -> InformeDiscrepanciasActividad."
    )
    discrepancias_globales: List[DiscrepanciaItem] = Field(
        default_factory=list,
        description="Listado global plano de discrepancias detectadas."
    )

    model_config = {
        "validate_assignment": True,
    }

    @property
    def tiene_discrepancias(self) -> bool:
        """Indica si el período presenta discrepancias que requieran revisión."""
        return self.total_discrepancias_activas > 0


