"""
app.word_consolidator.institutional_docx.spec

Especificación técnica, matemática y de diseño del maquetado visual DOCX
para el Informe Semanal Ejecutivo del Mecanismo Institucional BICU (Producto B).
Fase 16.4.

Define con precisión:
1. Las 13 columnas exactas de la tabla institucional (anchos, spans, twips).
2. Estructura de filas (Metadatos, Superencabezados, Subencabezados y Datos).
3. Estrategia de fusiones horizontales (gridSpan) y verticales (vMerge).
4. Manejo de múltiples actividades (N >= 0) y K estamentos por actividad.
5. Política parametrizable de fuentes de datos (Declarado M1 vs Nominal vs Presentación).
6. Especificación de la sección 'EVIDENCIAS ANEXAS' (Fotos, Asistencias, Enlaces).
7. Reglas de paginación (cantSplit, tblHeader, saltos de página).
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from app.word_consolidator.institutional_docx.constants import (
    PAGE_ORIENTATION,
    PAGE_WIDTH_PT,
    PAGE_HEIGHT_PT,
    MARGIN_TOP_PT,
    MARGIN_BOTTOM_PT,
    MARGIN_LEFT_PT,
    MARGIN_RIGHT_PT,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_MAGENTA,
    COLOR_WHITE,
    COLOR_BLACK,
    COLOR_BORDER_GRID,
    FONT_DOC_TITLE,
    FONT_TABLE_HEADER,
    FONT_TABLE_BODY,
    FONT_EVIDENCES_TITLE,
    FONT_ACTIVITY_HEADING,
    GRID_COLUMNS_TWIPS,
    TOTAL_TABLE_WIDTH_TWIPS,
    HEADER_DEPTO_LABEL,
    HEADER_MES_LABEL,
    HEADER_SEMANA_LABEL,
    SUPERHEADER_ACTIVIDAD,
    SUPERHEADER_RESULTADOS,
    SUPERHEADER_PROTAGONISTAS,
)
from app.word_consolidator.document.institutional_models import (
    InformeSemanalInstitucional,
    ActividadInstitucional,
    ProtagonistaEstamentoInstitucional,
    ConteoSexoInstitucional,
    SeccionEvidenciasActividad,
)


class ModoFuenteDatosEnum(str, Enum):
    """Política parametrizable para determinar qué cifra numérica se proyecta en la tabla."""
    PRESENTACION = "PRESENTACION"  # Toma conteo_presentacion del modelo (modo por defecto)
    DECLARADO_M1 = "DECLARADO_M1"  # Proyecta dato_declarado (M1) de cada estamento si existe
    NOMINAL = "NOMINAL"            # Proyecta dato_nominal (M2-M5) de cada estamento si existe


class TipoFilaEnum(str, Enum):
    """Categoría funcional de cada fila en la tabla institucional."""
    META_DEPTO = "META_DEPTO"              # Fila 0: Nombre del Depto + Valor
    META_MES_SEMANA = "META_MES_SEMANA"    # Fila 1: Mes planificado + Semana
    SUPERHEADER = "SUPERHEADER"            # Fila 2: Actividad (magenta) + Resultados + Protagonistas
    SUBHEADER = "SUBHEADER"                # Fila 3: Las 11 celdas visuales / 13 columnas
    DATA_ROW = "DATA_ROW"                  # Filas de actividad / estamentos
    EMPTY_STATE = "EMPTY_STATE"            # Fila informativa cuando N=0 actividades


class VMergeType(str, Enum):
    """Tipo de fusión vertical de celda OpenXML (w:vMerge)."""
    RESTART = "restart"    # Inicia un bloque fusionado verticalmente
    CONTINUE = "continue"  # Continúa el bloque fusionado anterior (celda subordinada)
    NONE = "none"          # Celda estándar sin fusión vertical


class CellMergeSpec(BaseModel):
    """Especificación de fusiones para una celda de la cuadrícula."""
    grid_span: int = Field(default=1, ge=1, le=13, description="Cantidad de columnas que abarca horizontalmente.")
    v_merge: VMergeType = Field(default=VMergeType.NONE, description="Comportamiento de fusión vertical.")

    model_config = {"frozen": True}


class CellVisualSpec(BaseModel):
    """Estilos tipográficos y visuales de una celda."""
    fill_hex: str = Field(default=COLOR_WHITE, description="Color de fondo hexadecimal (RRGGBB).")
    text_color_hex: str = Field(default=COLOR_BLACK, description="Color del texto hexadecimal.")
    font_name: str = Field(default=FONT_TABLE_BODY, description="Familia tipográfica.")
    font_size_pt: float = Field(default=10.0, ge=6.0, le=24.0, description="Tamaño en puntos.")
    bold: bool = Field(default=False, description="Texto en negrita.")
    italic: bool = Field(default=False, description="Texto en cursiva.")
    align_h: str = Field(default="left", description="Alineación horizontal: left, center, right, justify.")
    align_v: str = Field(default="center", description="Alineación vertical: top, center, bottom.")

    model_config = {"frozen": True}


class CellLayoutSpec(BaseModel):
    """Especificación completa de una celda calculada para la tabla de 13 columnas."""
    col_grid_idx: int = Field(..., ge=0, le=12, description="Índice inicial en la cuadrícula de 13 columnas (0..12).")
    texto: str = Field(default="", description="Contenido textual a renderizar.")
    merge: CellMergeSpec = Field(default_factory=CellMergeSpec, description="Especificación de fusiones.")
    visual: CellVisualSpec = Field(default_factory=CellVisualSpec, description="Estilos visuales.")
    ancho_twips: int = Field(..., ge=1, description="Ancho total asignado en twips.")

    model_config = {"frozen": True}


class RowLayoutSpec(BaseModel):
    """Especificación de una fila completa de la tabla institucional."""
    row_idx: int = Field(..., ge=0, description="Índice ordinal de la fila dentro de la tabla (0-based).")
    tipo_fila: TipoFilaEnum = Field(..., description="Tipo semántico de la fila.")
    cant_split: bool = Field(default=True, description="Evita que Word divida la fila entre páginas (w:cantSplit).")
    tbl_header: bool = Field(default=False, description="Repite la fila como encabezado en cada página (w:tblHeader).")
    celdas: List[CellLayoutSpec] = Field(..., description="Lista de celdas que componen la fila.")
    total_span: int = Field(..., description="Suma de grid_span de todas las celdas (DEBE ser exactamente 13).")
    actividad_id: Optional[str] = Field(default=None, description="UUID de la actividad asociada si es fila de datos.")
    estamento_tipo: Optional[str] = Field(default=None, description="Tipo de estamento de la fila si aplica.")

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validar_invariante_13_columnas(self) -> "RowLayoutSpec":
        span_calculado = sum(c.merge.grid_span for c in self.celdas)
        if span_calculado != 13:
            raise ValueError(
                f"Invariante de tabla violado en fila {self.row_idx} ({self.tipo_fila}): "
                f"la suma de grid_span es {span_calculado}, pero DEBE ser exactamente 13."
            )
        if self.total_span != 13:
            raise ValueError(f"total_span debe ser 13, pero se indicó {self.total_span}.")
        return self


class TableLayoutSpec(BaseModel):
    """Especificación calculada y validada de la tabla ejecutiva de 13 columnas."""
    filas: List[RowLayoutSpec] = Field(..., description="Secuencia ordenada de filas calculadas.")
    total_filas: int = Field(..., ge=1, description="Total de filas en la tabla.")
    total_columnas: int = Field(default=13, description="Total de columnas de la cuadrícula base.")
    ancho_total_twips: int = Field(default=TOTAL_TABLE_WIDTH_TWIPS, description="Ancho total en twips.")
    modo_fuente: ModoFuenteDatosEnum = Field(default=ModoFuenteDatosEnum.PRESENTACION, description="Política de fuente.")
    actividades_count: int = Field(..., ge=0, description="Cantidad de actividades representadas.")
    total_mujeres: int = Field(default=0, ge=0, description="Suma total de mujeres en la tabla.")
    total_varones: int = Field(default=0, ge=0, description="Suma total de varones en la tabla.")
    total_participantes: int = Field(default=0, ge=0, description="Suma total de participantes.")

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def validar_consistencia_tabla(self) -> "TableLayoutSpec":
        if len(self.filas) != self.total_filas:
            raise ValueError(f"total_filas ({self.total_filas}) no coincide con len(filas) ({len(self.filas)}).")
        return self


class EvidenciaItemSpec(BaseModel):
    """Especificación de un elemento individual en la sección de evidencias."""
    tipo: str = Field(..., description="Tipo de evidencia (FOTOGRAFIA, REGISTRO_ASISTENCIA, ENLACE_MEDIOS).")
    titulo: str = Field(..., description="Título descriptivo o pie de foto.")
    referencia: str = Field(..., description="Ruta de archivo local o URL web.")
    estado: str = Field(..., description="Estado de vinculación.")
    orden: int = Field(default=1, ge=1, description="Orden secuencial.")

    model_config = {"frozen": True}


class EvidenciasActividadSpec(BaseModel):
    """Especificación visual de las evidencias para una actividad."""
    id_actividad: str = Field(..., description="UUID de la actividad.")
    numero_actividad: int = Field(..., ge=1, description="Número ordinal de la actividad (1..N).")
    nombre_actividad: str = Field(..., description="Nombre formal de la actividad.")
    heading_text: str = Field(..., description="Encabezado visible numerado: '1. Nombre...'")
    fotografias: List[EvidenciaItemSpec] = Field(default_factory=list)
    registros_asistencia: List[EvidenciaItemSpec] = Field(default_factory=list)
    enlaces_publicaciones: List[EvidenciaItemSpec] = Field(default_factory=list)
    tiene_evidencias: bool = Field(default=False)

    model_config = {"frozen": True}


class EvidenciasSectionSpec(BaseModel):
    """Especificación completa de la sección EVIDENCIAS ANEXAS."""
    titulo: str = Field(default="EVIDENCIAS ANEXAS", description="Título principal de la sección.")
    actividades: List[EvidenciasActividadSpec] = Field(default_factory=list)
    requiere_salto_pagina_previo: bool = Field(
        default=True,
        description="Indica que debe existir un salto de página formal antes de esta sección."
    )
    total_evidencias: int = Field(default=0, ge=0)

    model_config = {"frozen": True}


class InstitutionalDocxSpec(BaseModel):
    """
    Especificación integral del maquetado visual para el documento Word institucional.
    Combina configuración de página, encabezados institucionales, tabla ejecutiva de 13
    columnas y la sección de evidencias anexas.
    """
    mecanismo_institucional: str = Field(default="MECANISMO INSTITUCIONAL")
    tipo_informe: str = Field(default="INFORME SEMANAL")
    orientacion: str = Field(default=PAGE_ORIENTATION)
    page_width_pt: float = Field(default=PAGE_WIDTH_PT)
    page_height_pt: float = Field(default=PAGE_HEIGHT_PT)
    margen_superior_pt: float = Field(default=MARGIN_TOP_PT)
    margen_inferior_pt: float = Field(default=MARGIN_BOTTOM_PT)
    margen_izquierdo_pt: float = Field(default=MARGIN_LEFT_PT)
    margen_derecho_pt: float = Field(default=MARGIN_RIGHT_PT)
    tabla_ejecutiva: TableLayoutSpec = Field(..., description="Tabla ejecutiva de 13 columnas calculada.")
    seccion_evidencias: EvidenciasSectionSpec = Field(..., description="Sección de evidencias anexas calculada.")
    tiene_discrepancias: bool = Field(default=False, description="Indica si existen discrepancias conservadas.")

    model_config = {"frozen": True}


# ============================================================================
# CÁLCULOS DE ANCHO POR COLUMNAS
# ============================================================================

def _calcular_ancho_span(col_inicio: int, span: int) -> int:
    """Calcula la sumatoria de anchos en twips para un rango de columnas de la cuadrícula base."""
    return sum(GRID_COLUMNS_TWIPS[i][2] for i in range(col_inicio, col_inicio + span))


# ============================================================================
# CONSTRUCTORES DE ESPECIFICACIÓN
# ============================================================================

def _extraer_conteo_segun_modo(
    estamento: ProtagonistaEstamentoInstitucional,
    modo_fuente: ModoFuenteDatosEnum
) -> ConteoSexoInstitucional:
    """
    Extrae el desglose por sexo M/V/Total para un estamento según la política de fuente solicitada,
    sin reconciliación forzada ni pérdida de datos.
    """
    if modo_fuente == ModoFuenteDatosEnum.DECLARADO_M1:
        if estamento.dato_declarado is not None:
            return estamento.dato_declarado
        # C6: Terminantemente prohibido hacer fallback silencioso a datos nominales
        # cuando la fuente solicitada es DECLARADO_M1. Si no hay dato declarado,
        # se retorna cero explícito neutro.
        return ConteoSexoInstitucional(mujeres=0, varones=0, total=0)
    elif modo_fuente == ModoFuenteDatosEnum.NOMINAL:
        if estamento.dato_nominal is not None:
            return estamento.dato_nominal
    return estamento.conteo_presentacion


def build_table_layout_spec(
    informe: InformeSemanalInstitucional,
    modo_fuente: ModoFuenteDatosEnum = ModoFuenteDatosEnum.PRESENTACION
) -> TableLayoutSpec:
    """
    Construye la especificación completa de la tabla institucional de 13 columnas a partir
    del modelo 'InformeSemanalInstitucional', garantizando rigurosamente la invariante de
    13 columnas en cada fila.
    """
    filas: List[RowLayoutSpec] = []
    current_row_idx = 0

    # -------------------------------------------------------------------------
    # FILA 0: Nombre del Depto: [span 1] | <Valor Depto> [span 12]
    # -------------------------------------------------------------------------
    c0_0 = CellLayoutSpec(
        col_grid_idx=0,
        texto=HEADER_DEPTO_LABEL,
        merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
        visual=CellVisualSpec(
            fill_hex=COLOR_PRIMARY_BLUE,
            text_color_hex=COLOR_WHITE,
            font_name=FONT_TABLE_HEADER,
            font_size_pt=10.0,
            bold=True,
            align_h="left",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(0, 1),
    )
    c0_1 = CellLayoutSpec(
        col_grid_idx=1,
        texto=informe.departamento_responsable,
        merge=CellMergeSpec(grid_span=12, v_merge=VMergeType.NONE),
        visual=CellVisualSpec(
            fill_hex=COLOR_WHITE,
            text_color_hex=COLOR_BLACK,
            font_name=FONT_TABLE_BODY,
            font_size_pt=10.0,
            bold=False,
            align_h="left",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(1, 12),
    )
    filas.append(RowLayoutSpec(
        row_idx=current_row_idx,
        tipo_fila=TipoFilaEnum.META_DEPTO,
        cant_split=True,
        tbl_header=False,
        celdas=[c0_0, c0_1],
        total_span=13,
    ))
    current_row_idx += 1

    # -------------------------------------------------------------------------
    # FILA 1: Mes planificado: [span 1] | <Mes> [span 6] | Semana: [span 2] | <Semana> [span 4]
    # -------------------------------------------------------------------------
    c1_0 = CellLayoutSpec(
        col_grid_idx=0,
        texto=HEADER_MES_LABEL,
        merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
        visual=CellVisualSpec(
            fill_hex=COLOR_PRIMARY_BLUE,
            text_color_hex=COLOR_WHITE,
            font_name=FONT_TABLE_HEADER,
            font_size_pt=10.0,
            bold=True,
            align_h="left",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(0, 1),
    )
    c1_1 = CellLayoutSpec(
        col_grid_idx=1,
        texto=informe.mes_planificado,
        merge=CellMergeSpec(grid_span=6, v_merge=VMergeType.NONE),
        visual=CellVisualSpec(
            fill_hex=COLOR_WHITE,
            text_color_hex=COLOR_BLACK,
            font_name=FONT_TABLE_BODY,
            font_size_pt=10.0,
            bold=False,
            align_h="left",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(1, 6),
    )
    c1_2 = CellLayoutSpec(
        col_grid_idx=7,
        texto=HEADER_SEMANA_LABEL,
        merge=CellMergeSpec(grid_span=2, v_merge=VMergeType.NONE),
        visual=CellVisualSpec(
            fill_hex=COLOR_PRIMARY_BLUE,
            text_color_hex=COLOR_WHITE,
            font_name=FONT_TABLE_HEADER,
            font_size_pt=10.0,
            bold=True,
            align_h="left",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(7, 2),
    )
    c1_3 = CellLayoutSpec(
        col_grid_idx=9,
        texto=informe.semana,
        merge=CellMergeSpec(grid_span=4, v_merge=VMergeType.NONE),
        visual=CellVisualSpec(
            fill_hex=COLOR_WHITE,
            text_color_hex=COLOR_BLACK,
            font_name=FONT_TABLE_BODY,
            font_size_pt=10.0,
            bold=False,
            align_h="left",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(9, 4),
    )
    filas.append(RowLayoutSpec(
        row_idx=current_row_idx,
        tipo_fila=TipoFilaEnum.META_MES_SEMANA,
        cant_split=True,
        tbl_header=False,
        celdas=[c1_0, c1_1, c1_2, c1_3],
        total_span=13,
    ))
    current_row_idx += 1

    # -------------------------------------------------------------------------
    # FILA 2: SUPERHEADER
    # Col 0: "Nombre de la actividad" [span 1, vMerge=restart, fill=D86DCB]
    # Cols 1..6: "Resultados alcanzados vinculados con el alcance de un Eje" [span 6, fill=153D63]
    # Cols 7..12: "Protagonistas" [span 6, fill=153D63]
    # -------------------------------------------------------------------------
    c2_0 = CellLayoutSpec(
        col_grid_idx=0,
        texto=SUPERHEADER_ACTIVIDAD,
        merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.RESTART),
        visual=CellVisualSpec(
            fill_hex=COLOR_ACCENT_MAGENTA,
            text_color_hex=COLOR_WHITE,
            font_name=FONT_TABLE_HEADER,
            font_size_pt=10.0,
            bold=True,
            align_h="center",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(0, 1),
    )
    c2_1 = CellLayoutSpec(
        col_grid_idx=1,
        texto=SUPERHEADER_RESULTADOS,
        merge=CellMergeSpec(grid_span=6, v_merge=VMergeType.NONE),
        visual=CellVisualSpec(
            fill_hex=COLOR_PRIMARY_BLUE,
            text_color_hex=COLOR_WHITE,
            font_name=FONT_TABLE_HEADER,
            font_size_pt=10.0,
            bold=True,
            align_h="center",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(1, 6),
    )
    c2_2 = CellLayoutSpec(
        col_grid_idx=7,
        texto=SUPERHEADER_PROTAGONISTAS,
        merge=CellMergeSpec(grid_span=6, v_merge=VMergeType.NONE),
        visual=CellVisualSpec(
            fill_hex=COLOR_PRIMARY_BLUE,
            text_color_hex=COLOR_WHITE,
            font_name=FONT_TABLE_HEADER,
            font_size_pt=10.0,
            bold=True,
            align_h="center",
            align_v="center",
        ),
        ancho_twips=_calcular_ancho_span(7, 6),
    )
    filas.append(RowLayoutSpec(
        row_idx=current_row_idx,
        tipo_fila=TipoFilaEnum.SUPERHEADER,
        cant_split=True,
        tbl_header=True,  # Se repite en cada página si la tabla se extiende
        celdas=[c2_0, c2_1, c2_2],
        total_span=13,
    ))
    current_row_idx += 1

    # -------------------------------------------------------------------------
    # FILA 3: SUBHEADER (11 celdas visuales = 13 columnas de cuadrícula)
    # Col 0: "" [span 1, vMerge=continue, fill=D86DCB]
    # Col 1: Eje vinculado [span 1]
    # Col 2: Descripción [span 1]
    # Col 3: Sede [span 1]
    # Col 4: Departamento [span 1]
    # Col 5: Municipio [span 1]
    # Cols 6..7: Tipo de actividad [span 2]
    # Cols 8..9: Tipo de protagonistas [span 2]
    # Col 10: M [span 1]
    # Col 11: V [span 1]
    # Col 12: Total [span 1]
    # -------------------------------------------------------------------------
    subheaders_defs = [
        (0, "", 1, VMergeType.CONTINUE, COLOR_ACCENT_MAGENTA),
        (1, "Eje vinculado", 1, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (2, "Descripción", 1, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (3, "Sede", 1, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (4, "Departamento", 1, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (5, "Municipio", 1, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (6, "Tipo de actividad", 2, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (8, "Tipo de protagonistas", 2, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (10, "M", 1, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (11, "V", 1, VMergeType.NONE, COLOR_PRIMARY_BLUE),
        (12, "Total", 1, VMergeType.NONE, COLOR_PRIMARY_BLUE),
    ]

    c3_celdas: List[CellLayoutSpec] = []
    for col_idx, txt, span, v_merge, fill in subheaders_defs:
        c3_celdas.append(CellLayoutSpec(
            col_grid_idx=col_idx,
            texto=txt,
            merge=CellMergeSpec(grid_span=span, v_merge=v_merge),
            visual=CellVisualSpec(
                fill_hex=fill,
                text_color_hex=COLOR_WHITE,
                font_name=FONT_TABLE_HEADER,
                font_size_pt=10.0,
                bold=True,
                align_h="center",
                align_v="center",
            ),
            ancho_twips=_calcular_ancho_span(col_idx, span),
        ))

    filas.append(RowLayoutSpec(
        row_idx=current_row_idx,
        tipo_fila=TipoFilaEnum.SUBHEADER,
        cant_split=True,
        tbl_header=True,  # Se repite en cada página si la tabla se extiende
        celdas=c3_celdas,
        total_span=13,
    ))
    current_row_idx += 1

    # -------------------------------------------------------------------------
    # CASO N = 0 ACTIVIDADES (Informe sin actividades)
    # -------------------------------------------------------------------------
    if len(informe.actividades) == 0:
        c_empty = CellLayoutSpec(
            col_grid_idx=0,
            texto="No se registraron actividades para el período seleccionado.",
            merge=CellMergeSpec(grid_span=13, v_merge=VMergeType.NONE),
            visual=CellVisualSpec(
                fill_hex=COLOR_WHITE,
                text_color_hex=COLOR_BLACK,
                font_name=FONT_TABLE_BODY,
                font_size_pt=10.0,
                bold=False,
                italic=True,
                align_h="center",
                align_v="center",
            ),
            ancho_twips=TOTAL_TABLE_WIDTH_TWIPS,
        )
        filas.append(RowLayoutSpec(
            row_idx=current_row_idx,
            tipo_fila=TipoFilaEnum.EMPTY_STATE,
            cant_split=True,
            tbl_header=False,
            celdas=[c_empty],
            total_span=13,
        ))
        return TableLayoutSpec(
            filas=filas,
            total_filas=len(filas),
            total_columnas=13,
            modo_fuente=modo_fuente,
            actividades_count=0,
            total_mujeres=0,
            total_varones=0,
            total_participantes=0,
        )

    # -------------------------------------------------------------------------
    # CASO N >= 1 ACTIVIDADES: Construcción de bloques por actividad
    # -------------------------------------------------------------------------
    sum_mujeres = 0
    sum_varones = 0
    sum_total = 0

    for actividad in informe.actividades:
        estamentos = actividad.protagonistas
        num_estamentos = len(estamentos)

        # Si no hay estamentos registrados en la actividad, crear fila placeholder
        if num_estamentos == 0:
            row_cells: List[CellLayoutSpec] = [
                CellLayoutSpec(
                    col_grid_idx=0,
                    texto=actividad.nombre_actividad,
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="left"),
                    ancho_twips=_calcular_ancho_span(0, 1),
                ),
                CellLayoutSpec(
                    col_grid_idx=1,
                    texto=actividad.eje_vinculado,
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="left"),
                    ancho_twips=_calcular_ancho_span(1, 1),
                ),
                CellLayoutSpec(
                    col_grid_idx=2,
                    texto=actividad.descripcion,
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="left"),
                    ancho_twips=_calcular_ancho_span(2, 1),
                ),
                CellLayoutSpec(
                    col_grid_idx=3,
                    texto=actividad.sede,
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center"),
                    ancho_twips=_calcular_ancho_span(3, 1),
                ),
                CellLayoutSpec(
                    col_grid_idx=4,
                    texto=actividad.departamento,
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center"),
                    ancho_twips=_calcular_ancho_span(4, 1),
                ),
                CellLayoutSpec(
                    col_grid_idx=5,
                    texto=actividad.municipio,
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center"),
                    ancho_twips=_calcular_ancho_span(5, 1),
                ),
                CellLayoutSpec(
                    col_grid_idx=6,
                    texto=actividad.tipo_actividad,
                    merge=CellMergeSpec(grid_span=2, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center"),
                    ancho_twips=_calcular_ancho_span(6, 2),
                ),
                CellLayoutSpec(
                    col_grid_idx=8,
                    texto="Sin protagonistas",
                    merge=CellMergeSpec(grid_span=2, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center", italic=True),
                    ancho_twips=_calcular_ancho_span(8, 2),
                ),
                CellLayoutSpec(
                    col_grid_idx=10,
                    texto="0",
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center"),
                    ancho_twips=_calcular_ancho_span(10, 1),
                ),
                CellLayoutSpec(
                    col_grid_idx=11,
                    texto="0",
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center"),
                    ancho_twips=_calcular_ancho_span(11, 1),
                ),
                CellLayoutSpec(
                    col_grid_idx=12,
                    texto="0",
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center"),
                    ancho_twips=_calcular_ancho_span(12, 1),
                ),
            ]
            filas.append(RowLayoutSpec(
                row_idx=current_row_idx,
                tipo_fila=TipoFilaEnum.DATA_ROW,
                cant_split=True,
                tbl_header=False,
                celdas=row_cells,
                total_span=13,
                actividad_id=actividad.id_actividad,
            ))
            current_row_idx += 1
            continue

        # Bloque con K estamentos participantes
        for k_idx, estamento in enumerate(estamentos):
            conteo = _extraer_conteo_segun_modo(estamento, modo_fuente)
            sum_mujeres += conteo.mujeres
            sum_varones += conteo.varones
            sum_total += conteo.total

            # Determinación de vMerge para columnas compartidas (Cols 0..7)
            if k_idx == 0:
                v_merge_act = VMergeType.RESTART if num_estamentos > 1 else VMergeType.NONE
                txt_nombre = actividad.nombre_actividad
                txt_eje = actividad.eje_vinculado
                txt_desc = actividad.descripcion
                txt_sede = actividad.sede
                txt_depto = actividad.departamento
                txt_muni = actividad.municipio
                txt_tipo = actividad.tipo_actividad
            else:
                v_merge_act = VMergeType.CONTINUE
                txt_nombre = ""
                txt_eje = ""
                txt_desc = ""
                txt_sede = ""
                txt_depto = ""
                txt_muni = ""
                txt_tipo = ""

            row_cells = [
                # Col 0: Nombre actividad [span 1]
                CellLayoutSpec(
                    col_grid_idx=0,
                    texto=txt_nombre,
                    merge=CellMergeSpec(grid_span=1, v_merge=v_merge_act),
                    visual=CellVisualSpec(align_h="left", align_v="center"),
                    ancho_twips=_calcular_ancho_span(0, 1),
                ),
                # Col 1: Eje vinculado [span 1]
                CellLayoutSpec(
                    col_grid_idx=1,
                    texto=txt_eje,
                    merge=CellMergeSpec(grid_span=1, v_merge=v_merge_act),
                    visual=CellVisualSpec(align_h="left", align_v="center"),
                    ancho_twips=_calcular_ancho_span(1, 1),
                ),
                # Col 2: Descripción [span 1]
                CellLayoutSpec(
                    col_grid_idx=2,
                    texto=txt_desc,
                    merge=CellMergeSpec(grid_span=1, v_merge=v_merge_act),
                    visual=CellVisualSpec(align_h="left", align_v="center"),
                    ancho_twips=_calcular_ancho_span(2, 1),
                ),
                # Col 3: Sede [span 1]
                CellLayoutSpec(
                    col_grid_idx=3,
                    texto=txt_sede,
                    merge=CellMergeSpec(grid_span=1, v_merge=v_merge_act),
                    visual=CellVisualSpec(align_h="center", align_v="center"),
                    ancho_twips=_calcular_ancho_span(3, 1),
                ),
                # Col 4: Departamento [span 1]
                CellLayoutSpec(
                    col_grid_idx=4,
                    texto=txt_depto,
                    merge=CellMergeSpec(grid_span=1, v_merge=v_merge_act),
                    visual=CellVisualSpec(align_h="center", align_v="center"),
                    ancho_twips=_calcular_ancho_span(4, 1),
                ),
                # Col 5: Municipio [span 1]
                CellLayoutSpec(
                    col_grid_idx=5,
                    texto=txt_muni,
                    merge=CellMergeSpec(grid_span=1, v_merge=v_merge_act),
                    visual=CellVisualSpec(align_h="center", align_v="center"),
                    ancho_twips=_calcular_ancho_span(5, 1),
                ),
                # Cols 6..7: Tipo de actividad [span 2]
                CellLayoutSpec(
                    col_grid_idx=6,
                    texto=txt_tipo,
                    merge=CellMergeSpec(grid_span=2, v_merge=v_merge_act),
                    visual=CellVisualSpec(align_h="center", align_v="center"),
                    ancho_twips=_calcular_ancho_span(6, 2),
                ),
                # Cols 8..9: Tipo de protagonistas [span 2, sin vMerge]
                CellLayoutSpec(
                    col_grid_idx=8,
                    texto=estamento.denominacion_visible,
                    merge=CellMergeSpec(grid_span=2, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center", align_v="center"),
                    ancho_twips=_calcular_ancho_span(8, 2),
                ),
                # Col 10: M [span 1, sin vMerge]
                CellLayoutSpec(
                    col_grid_idx=10,
                    texto=str(conteo.mujeres),
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center", align_v="center"),
                    ancho_twips=_calcular_ancho_span(10, 1),
                ),
                # Col 11: V [span 1, sin vMerge]
                CellLayoutSpec(
                    col_grid_idx=11,
                    texto=str(conteo.varones),
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center", align_v="center"),
                    ancho_twips=_calcular_ancho_span(11, 1),
                ),
                # Col 12: Total [span 1, sin vMerge]
                CellLayoutSpec(
                    col_grid_idx=12,
                    texto=str(conteo.total),
                    merge=CellMergeSpec(grid_span=1, v_merge=VMergeType.NONE),
                    visual=CellVisualSpec(align_h="center", align_v="center"),
                    ancho_twips=_calcular_ancho_span(12, 1),
                ),
            ]

            filas.append(RowLayoutSpec(
                row_idx=current_row_idx,
                tipo_fila=TipoFilaEnum.DATA_ROW,
                cant_split=True,
                tbl_header=False,
                celdas=row_cells,
                total_span=13,
                actividad_id=actividad.id_actividad,
                estamento_tipo=estamento.estamento_tipo.value,
            ))
            current_row_idx += 1

    return TableLayoutSpec(
        filas=filas,
        total_filas=len(filas),
        total_columnas=13,
        ancho_total_twips=TOTAL_TABLE_WIDTH_TWIPS,
        modo_fuente=modo_fuente,
        actividades_count=len(informe.actividades),
        total_mujeres=sum_mujeres,
        total_varones=sum_varones,
        total_participantes=sum_total,
    )


def build_evidencias_spec(informe: InformeSemanalInstitucional) -> EvidenciasSectionSpec:
    """
    Construye la especificación estructurada para la sección 'EVIDENCIAS ANEXAS',
    garantizando que cada actividad conserve su bloque formal con las tres categorías
    (fotografías, registros de asistencia, enlaces) sin inventar contenidos inexistentes.
    """
    actividades_evidencias: List[EvidenciasActividadSpec] = []
    total_evs = 0

    for idx, act in enumerate(informe.actividades, start=1):
        sec = act.evidencias
        fotos_spec = [
            EvidenciaItemSpec(
                tipo=f.tipo.value,
                titulo=f.titulo,
                referencia=f.referencia,
                estado=f.estado.value,
                orden=f.orden,
            )
            for f in sec.fotografias
        ]
        asistencias_spec = [
            EvidenciaItemSpec(
                tipo=a.tipo.value,
                titulo=a.titulo,
                referencia=a.referencia,
                estado=a.estado.value,
                orden=a.orden,
            )
            for a in sec.registros_asistencia
        ]
        enlaces_spec = [
            EvidenciaItemSpec(
                tipo=e.tipo.value,
                titulo=e.titulo,
                referencia=e.referencia,
                estado=e.estado.value,
                orden=e.orden,
            )
            for e in sec.enlaces_publicaciones
        ]

        total_act_evs = len(fotos_spec) + len(asistencias_spec) + len(enlaces_spec)
        total_evs += total_act_evs

        heading_title = f"{idx}. {act.nombre_actividad}"

        actividades_evidencias.append(EvidenciasActividadSpec(
            id_actividad=act.id_actividad,
            numero_actividad=idx,
            nombre_actividad=act.nombre_actividad,
            heading_text=heading_title,
            fotografias=fotos_spec,
            registros_asistencia=asistencias_spec,
            enlaces_publicaciones=enlaces_spec,
            tiene_evidencias=(total_act_evs > 0),
        ))

    return EvidenciasSectionSpec(
        titulo="EVIDENCIAS ANEXAS",
        actividades=actividades_evidencias,
        requiere_salto_pagina_previo=True,
        total_evidencias=total_evs,
    )


def build_document_layout_spec(
    informe: InformeSemanalInstitucional,
    modo_fuente: ModoFuenteDatosEnum = ModoFuenteDatosEnum.PRESENTACION
) -> InstitutionalDocxSpec:
    """
    Punto de entrada principal para generar la especificación completa del documento
    institucional a partir del modelo intermedio.
    """
    tabla = build_table_layout_spec(informe, modo_fuente=modo_fuente)
    evidencias = build_evidencias_spec(informe)

    return InstitutionalDocxSpec(
        mecanismo_institucional=informe.mecanismo_institucional,
        tipo_informe=informe.tipo_informe,
        orientacion=PAGE_ORIENTATION,
        page_width_pt=PAGE_WIDTH_PT,
        page_height_pt=PAGE_HEIGHT_PT,
        margen_superior_pt=MARGIN_TOP_PT,
        margen_inferior_pt=MARGIN_BOTTOM_PT,
        margen_izquierdo_pt=MARGIN_LEFT_PT,
        margen_derecho_pt=MARGIN_RIGHT_PT,
        tabla_ejecutiva=tabla,
        seccion_evidencias=evidencias,
        tiene_discrepancias=informe.tiene_discrepancias,
    )
