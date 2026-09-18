"""
app.word_consolidator.docx_generator

Paquete de renderizado y maquetación de documentos Word (.docx) institucionales
para el generador consolidado de asistencias.
Fase 14.7 — Capa de presentación ("Presentación, No Negocio").
"""

from app.word_consolidator.docx_generator.renderer import DocxGenerator, DocxRenderer
from app.word_consolidator.docx_generator.style_manager import ColorPalette, StyleManager
from app.word_consolidator.docx_generator.page_setup import PageSetup
from app.word_consolidator.docx_generator.table_builder import TableBuilder
from app.word_consolidator.docx_generator.header_footer import HeaderFooterManager

__all__ = [
    "DocxGenerator",
    "DocxRenderer",
    "ColorPalette",
    "StyleManager",
    "PageSetup",
    "TableBuilder",
    "HeaderFooterManager",
]
