"""
app.word_consolidator.institutional_docx.table_builder

Renderizador de la tabla ejecutiva institucional de 13 columnas del Informe Semanal BICU.
Consume las especificaciones calculadas por spec.py e implementa con exactitud
la cuadrícula, merges, sombreado, tipografías y propiedades de paginación definidas
en la Fase 16.4 del documento oficial 'Documento de Kevds3.docx'.

Responsabilidades:
- Crear la tabla Word con la cuadrícula de 13 columnas exacta.
- Aplicar shading (fill) por celda.
- Aplicar gridSpan (fusión horizontal) mediante XML directo.
- Aplicar vMerge (fusión vertical) mediante XML directo.
- Establecer cantSplit en todas las filas.
- Establecer tblHeader en filas de encabezado.
- Aplicar bordes Table Grid (cuadrícula estándar).
- Aplicar tipografía Bookman Old Style y alineaciones institucionales.
- NO lee el modelo directamente; consume únicamente RowLayoutSpec y TableLayoutSpec.
"""

from typing import List

from docx import Document
from docx.table import Table, _Row, _Cell
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, Twips, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.word_consolidator.institutional_docx.constants import (
    GRID_COLUMNS_TWIPS,
    TOTAL_TABLE_WIDTH_TWIPS,
)
from app.word_consolidator.institutional_docx.spec import (
    TableLayoutSpec,
    RowLayoutSpec,
    CellLayoutSpec,
    VMergeType,
)

# ============================================================================
# HELPERS XML DE BAJO NIVEL
# ============================================================================

def _set_cell_shading(tc_elem, fill_hex: str) -> None:
    """Establece el color de fondo (shading) de una celda mediante XML directo."""
    tcPr = tc_elem.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    # Eliminar shd anterior si existe
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    tcPr.append(shd)


def _set_cell_width(tc_elem, width_twips: int) -> None:
    """Establece el ancho de celda explícito (w:tcW) en twips."""
    tcPr = tc_elem.get_or_add_tcPr()
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(width_twips))
    tcW.set(qn("w:type"), "dxa")
    for old in tcPr.findall(qn("w:tcW")):
        tcPr.remove(old)
    # Insertar al inicio de tcPr (antes de los demás elementos)
    tcPr.insert(0, tcW)


def _set_grid_span(tc_elem, span: int) -> None:
    """Establece la fusión horizontal de celda (w:gridSpan)."""
    if span <= 1:
        return
    tcPr = tc_elem.get_or_add_tcPr()
    gridSpan = OxmlElement("w:gridSpan")
    gridSpan.set(qn("w:val"), str(span))
    for old in tcPr.findall(qn("w:gridSpan")):
        tcPr.remove(old)
    tcPr.append(gridSpan)


def _set_v_merge(tc_elem, v_merge: VMergeType) -> None:
    """Establece la propiedad de fusión vertical de celda (w:vMerge)."""
    if v_merge == VMergeType.NONE:
        return
    tcPr = tc_elem.get_or_add_tcPr()
    vMerge = OxmlElement("w:vMerge")
    if v_merge == VMergeType.RESTART:
        vMerge.set(qn("w:val"), "restart")
    # Para CONTINUE se deja el elemento vacío (sin atributo w:val)
    for old in tcPr.findall(qn("w:vMerge")):
        tcPr.remove(old)
    tcPr.append(vMerge)


def _set_cell_valign(tc_elem, align_v: str) -> None:
    """Establece la alineación vertical (w:vAlign) de una celda."""
    # Mapeo de valores de CellVisualSpec a OpenXML
    val_map = {"top": "top", "center": "center", "bottom": "bottom"}
    val = val_map.get(align_v.lower(), "center")
    tcPr = tc_elem.get_or_add_tcPr()
    vAlign = OxmlElement("w:vAlign")
    vAlign.set(qn("w:val"), val)
    for old in tcPr.findall(qn("w:vAlign")):
        tcPr.remove(old)
    tcPr.append(vAlign)


def _set_row_cant_split(tr_elem) -> None:
    """Establece w:cantSplit en una fila para evitar que se corte entre páginas."""
    trPr = tr_elem.get_or_add_trPr()
    cantSplit = OxmlElement("w:cantSplit")
    cantSplit.set(qn("w:val"), "1")
    # Solo agregar si no existe
    if trPr.find(qn("w:cantSplit")) is None:
        trPr.append(cantSplit)


def _set_row_tbl_header(tr_elem) -> None:
    """Establece w:tblHeader en una fila para que se repita como encabezado en cada página."""
    trPr = tr_elem.get_or_add_trPr()
    tblHeader = OxmlElement("w:tblHeader")
    if trPr.find(qn("w:tblHeader")) is None:
        trPr.append(tblHeader)


def _set_table_grid_borders(tbl_elem) -> None:
    """Aplica el estilo de bordes Table Grid a la tabla (cuadrícula estándar negra)."""
    tblPr = tbl_elem.tblPr
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl_elem.insert(0, tblPr)

    # Eliminar borders anteriores
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)

    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "4")       # 0.5 pt = 4 eighths-of-a-point
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), "000000")
        tblBorders.append(border)
    tblPr.append(tblBorders)


def _set_table_width(tbl_elem, total_twips: int) -> None:
    """Establece el ancho total de la tabla en twips."""
    tblPr = tbl_elem.tblPr
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl_elem.insert(0, tblPr)

    for old in tblPr.findall(qn("w:tblW")):
        tblPr.remove(old)

    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(total_twips))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)


def _set_no_cell_padding(tblPr_elem) -> None:
    """Establece padding de celda = 0 por defecto (para control manual total)."""
    for old in tblPr_elem.findall(qn("w:tblCellMar")):
        tblPr_elem.remove(old)
    tblCellMar = OxmlElement("w:tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        mar = OxmlElement(f"w:{side}")
        mar.set(qn("w:w"), "72")   # 72 twips = 5 cm → revisado a 72 ≈ 0.05 in, padding estándar Word
        mar.set(qn("w:type"), "dxa")
        tblCellMar.append(mar)
    tblPr_elem.append(tblCellMar)


# ============================================================================
# CONSTRUCTOR PRINCIPAL DE LA CUADRÍCULA BASE
# ============================================================================

def _create_table_grid(doc: Document) -> Table:
    """
    Crea la tabla vacía con la cuadrícula exacta de 13 columnas.
    Retorna la tabla lista para que se agreguen filas.
    """
    # Crear tabla con 1 fila, 1 columna → luego se ajusta la cuadrícula XML
    table = doc.add_table(rows=0, cols=13)
    tbl_elem = table._tbl

    # Aplicar estilo base (hereda borders básicos; los reemplazaremos explícitamente)
    table.style = "Table Grid"

    # Configurar cuadrícula exacta (w:tblGrid)
    tblGrid = OxmlElement("w:tblGrid")
    for _, _, width_twips in GRID_COLUMNS_TWIPS:
        gridCol = OxmlElement("w:gridCol")
        gridCol.set(qn("w:w"), str(width_twips))
        tblGrid.append(gridCol)
    # Reemplazar tblGrid existente
    existing_grid = tbl_elem.find(qn("w:tblGrid"))
    if existing_grid is not None:
        tbl_elem.remove(existing_grid)
    tbl_elem.append(tblGrid)

    # Ancho total de la tabla
    _set_table_width(tbl_elem, TOTAL_TABLE_WIDTH_TWIPS)

    # Bordes Table Grid
    _set_table_grid_borders(tbl_elem)

    return table


# ============================================================================
# RENDERIZADOR DE CELDA INDIVIDUAL
# ============================================================================

def _render_cell(
    tr_elem,
    cell_spec: CellLayoutSpec,
    existing_tc=None,
) -> None:
    """
    Renderiza una celda individual según su especificación.
    Si existing_tc es None, crea un nuevo elemento w:tc y lo añade a tr_elem.

    Args:
        tr_elem: Elemento XML w:tr de la fila.
        cell_spec: Especificación completa de la celda.
        existing_tc: Elemento tc existente (opcional).
    """
    if existing_tc is None:
        tc = OxmlElement("w:tc")
        tr_elem.append(tc)
    else:
        tc = existing_tc

    # --- Propiedades de celda (tcPr) ---
    _set_cell_width(tc, cell_spec.ancho_twips)
    if cell_spec.merge.grid_span > 1:
        _set_grid_span(tc, cell_spec.merge.grid_span)
    _set_v_merge(tc, cell_spec.merge.v_merge)
    _set_cell_shading(tc, cell_spec.visual.fill_hex)
    _set_cell_valign(tc, cell_spec.visual.align_v)

    # --- Párrafo y texto ---
    # Eliminar párrafos existentes en el tc
    for old_p in tc.findall(qn("w:p")):
        tc.remove(old_p)

    p = OxmlElement("w:p")
    tc.append(p)

    # Propiedades del párrafo
    pPr = OxmlElement("w:pPr")
    p.append(pPr)

    # Alineación horizontal
    jc_map = {
        "left": "left",
        "center": "center",
        "right": "right",
        "justify": "both",
    }
    jc_val = jc_map.get(cell_spec.visual.align_h.lower(), "left")
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), jc_val)
    pPr.append(jc)

    # Espaciado estándar (sin espacio extra)
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "240")
    spacing.set(qn("w:lineRule"), "auto")
    pPr.append(spacing)

    # Propiedades de la fuente en pPr (para celdas de continuación vMerge)
    pPr_rPr = OxmlElement("w:rPr")
    _apply_run_font_properties(pPr_rPr, cell_spec)
    pPr.append(pPr_rPr)

    # Solo agregar run con texto si hay contenido
    if cell_spec.texto:
        r = OxmlElement("w:r")
        p.append(r)

        rPr = OxmlElement("w:rPr")
        _apply_run_font_properties(rPr, cell_spec)
        r.append(rPr)

        t = OxmlElement("w:t")
        t.text = cell_spec.texto
        if cell_spec.texto.startswith(" ") or cell_spec.texto.endswith(" "):
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        r.append(t)


def _apply_run_font_properties(rPr_elem, cell_spec: CellLayoutSpec) -> None:
    """
    Aplica propiedades de fuente (nombre, tamaño, negrita, cursiva, color)
    al elemento w:rPr proporcionado.
    """
    # Fuente
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), cell_spec.visual.font_name)
    rFonts.set(qn("w:hAnsi"), cell_spec.visual.font_name)
    rPr_elem.append(rFonts)

    # Negrita
    if cell_spec.visual.bold:
        b = OxmlElement("w:b")
        rPr_elem.append(b)
        bCs = OxmlElement("w:bCs")
        rPr_elem.append(bCs)

    # Cursiva
    if cell_spec.visual.italic:
        i = OxmlElement("w:i")
        rPr_elem.append(i)
        iCs = OxmlElement("w:iCs")
        rPr_elem.append(iCs)

    # Tamaño: en OpenXML el tamaño es en half-points (pt * 2)
    sz_val = str(int(cell_spec.visual.font_size_pt * 2))
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), sz_val)
    rPr_elem.append(sz)
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), sz_val)
    rPr_elem.append(szCs)

    # Color de texto
    color = OxmlElement("w:color")
    color.set(qn("w:val"), cell_spec.visual.text_color_hex)
    rPr_elem.append(color)


# ============================================================================
# RENDERIZADOR DE FILA COMPLETA
# ============================================================================

def _render_row(table: Table, row_spec: RowLayoutSpec) -> None:
    """
    Renderiza una fila completa de la tabla institucional.
    Crea el elemento w:tr con todas sus celdas y propiedades de paginación.

    Args:
        table: Objeto Table de python-docx.
        row_spec: Especificación completa de la fila.
    """
    # Agregar fila vacía a la tabla
    tr = OxmlElement("w:tr")
    table._tbl.append(tr)

    # Propiedades de fila
    trPr = OxmlElement("w:trPr")
    tr.append(trPr)

    # cantSplit: evitar que la fila se divida entre páginas
    if row_spec.cant_split:
        cantSplit = OxmlElement("w:cantSplit")
        cantSplit.set(qn("w:val"), "1")
        trPr.append(cantSplit)

    # tblHeader: repetir como encabezado al inicio de cada página
    if row_spec.tbl_header:
        tblHeader = OxmlElement("w:tblHeader")
        trPr.append(tblHeader)

    # Renderizar cada celda de la fila
    for cell_spec in row_spec.celdas:
        _render_cell(tr, cell_spec)


# ============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ============================================================================

def build_institutional_table(doc: Document, tabla_spec: TableLayoutSpec) -> Table:
    """
    Construye y agrega la tabla ejecutiva institucional al documento.

    Args:
        doc: Objeto Document de python-docx con la página ya configurada.
        tabla_spec: Especificación calculada por build_table_layout_spec().

    Returns:
        La instancia Table de python-docx creada.
    """
    table = _create_table_grid(doc)

    for row_spec in tabla_spec.filas:
        _render_row(table, row_spec)

    return table
