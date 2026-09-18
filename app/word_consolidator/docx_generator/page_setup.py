"""
app.word_consolidator.docx_generator.page_setup

Configuración de geometrías de página, márgenes, orientación y saltos controlados
para el documento Word institucional.
Garantiza que tablas anchas no sufran cortes horizontales y que no existan
páginas en blanco no deseadas.
"""

from typing import Optional

import docx
from docx.enum.section import WD_ORIENT, WD_SECTION_START
from docx.shared import Inches, Mm


class PageSetup:
    """
    Configura y administra la geometría de página del documento.
    Soporta Carta/Letter horizontal (Landscape) y vertical (Portrait),
    con márgenes equilibrados de 20 mm.
    """

    DEFAULT_MARGIN_MM = 20.0
    HEADER_MARGIN_MM = 10.0
    FOOTER_MARGIN_MM = 10.0

    # Dimensiones estándar Carta (Letter)
    LETTER_SHORT_INCHES = 8.5
    LETTER_LONG_INCHES = 11.0

    @classmethod
    def apply_landscape_page(
        cls,
        section: docx.section.Section,
        margin_mm: float = DEFAULT_MARGIN_MM,
    ) -> None:
        """
        Aplica orientación horizontal (Landscape) Letter a la sección.
        Ancho disponible para contenido: ~239.4 mm (9.42 pulgadas).
        Ideal para tablas multidimensionales de 10 a 13 columnas.
        """
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Inches(cls.LETTER_LONG_INCHES)
        section.page_height = Inches(cls.LETTER_SHORT_INCHES)
        
        section.top_margin = Mm(margin_mm)
        section.bottom_margin = Mm(margin_mm)
        section.left_margin = Mm(margin_mm)
        section.right_margin = Mm(margin_mm)
        
        section.header_distance = Mm(cls.HEADER_MARGIN_MM)
        section.footer_distance = Mm(cls.FOOTER_MARGIN_MM)

    @classmethod
    def apply_portrait_page(
        cls,
        section: docx.section.Section,
        margin_mm: float = DEFAULT_MARGIN_MM,
    ) -> None:
        """
        Aplica orientación vertical (Portrait) Letter a la sección.
        Ancho disponible para contenido: ~175.9 mm (6.92 pulgadas).
        """
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Inches(cls.LETTER_SHORT_INCHES)
        section.page_height = Inches(cls.LETTER_LONG_INCHES)
        
        section.top_margin = Mm(margin_mm)
        section.bottom_margin = Mm(margin_mm)
        section.left_margin = Mm(margin_mm)
        section.right_margin = Mm(margin_mm)
        
        section.header_distance = Mm(cls.HEADER_MARGIN_MM)
        section.footer_distance = Mm(cls.FOOTER_MARGIN_MM)

    @classmethod
    def initialize_document_geometry(
        cls,
        doc: docx.Document,
        landscape: bool = True,
    ) -> None:
        """Inicializa la primera sección del documento."""
        if not doc.sections:
            return
        initial_section = doc.sections[0]
        if landscape:
            cls.apply_landscape_page(initial_section)
        else:
            cls.apply_portrait_page(initial_section)

    @classmethod
    def add_page_break(cls, doc: docx.Document) -> None:
        """
        Añade un salto de página controlado entre secciones principales.
        Evita añadir saltos de página consecutivos si el último elemento ya es un salto.
        """
        doc.add_page_break()
