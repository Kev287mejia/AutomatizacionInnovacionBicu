"""
app.word_consolidator.institutional_docx.page_setup

Motor de configuración de página para el Informe Semanal Institucional BICU.
Implementa con exactitud el formato Letter Horizontal con los parámetros
extraídos forense del documento oficial 'Documento de Kevds3.docx'.

Responsabilidades:
- Configurar orientación landscape.
- Establecer márgenes exactos (3.0 cm superior/inferior, 2.5 cm izquierdo/derecho).
- Generar los dos párrafos de título institucional:
    'MECANISMO INSTITUCIONAL' y 'INFORME SEMANAL'
  con Trebuchet MS 14 pt Bold centrado color #215E99.
- NO crea la tabla ni las evidencias.
"""

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT

from app.word_consolidator.institutional_docx.constants import (
    FONT_DOC_TITLE,
    COLOR_WHITE,
)

# Color exacto del documento real (obtenido por inspección XML)
_TITLE_COLOR_RGB = RGBColor(0x21, 0x5E, 0x99)

# Márgenes institucionales exactos en cm
_MARGIN_TOP_CM = 3.0
_MARGIN_BOTTOM_CM = 3.0
_MARGIN_LEFT_CM = 2.5
_MARGIN_RIGHT_CM = 2.5

# Tipografía y tamaño de los títulos
_TITLE_FONT_NAME = FONT_DOC_TITLE   # "Trebuchet MS"
_TITLE_FONT_SIZE_PT = 14.0


def configure_page(doc: Document) -> None:
    """
    Configura la primera sección del documento como Letter Landscape
    con los márgenes institucionales exactos.

    Args:
        doc: Objeto Document de python-docx ya inicializado.
    """
    section = doc.sections[0]

    # Landscape Letter: ancho > alto
    section.orientation = WD_ORIENT.LANDSCAPE
    # En python-docx el set de orientación no intercambia automáticamente
    # anchura y altura → se deben asignar explícitamente.
    section.page_width = Cm(27.94)   # 11.0 in = 27.94 cm
    section.page_height = Cm(21.59)  # 8.5 in  = 21.59 cm

    # Márgenes institucionales
    section.top_margin = Cm(_MARGIN_TOP_CM)
    section.bottom_margin = Cm(_MARGIN_BOTTOM_CM)
    section.left_margin = Cm(_MARGIN_LEFT_CM)
    section.right_margin = Cm(_MARGIN_RIGHT_CM)


def _add_title_paragraph(doc: Document, text: str) -> None:
    """
    Agrega un párrafo de título institucional con el estilo exacto del documento real.

    Args:
        doc: Objeto Document.
        text: Texto del párrafo (ej. 'MECANISMO INSTITUCIONAL').
    """
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Controlar el espaciado: sin espacio antes/después para replicar el original
    pf = para.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = Pt(14)  # Interlineado simple ajustado al cuerpo de 14 pt

    run = para.add_run(text)
    run.bold = True
    run.font.name = _TITLE_FONT_NAME
    run.font.size = Pt(_TITLE_FONT_SIZE_PT)
    run.font.color.rgb = _TITLE_COLOR_RGB


def add_institutional_headers(doc: Document) -> None:
    """
    Inserta los dos párrafos de título institucional requeridos por el formato oficial:
      1. 'MECANISMO INSTITUCIONAL'
      2. 'INFORME SEMANAL'

    Args:
        doc: Objeto Document con la página ya configurada.
    """
    _add_title_paragraph(doc, "MECANISMO INSTITUCIONAL")
    _add_title_paragraph(doc, "INFORME SEMANAL")
