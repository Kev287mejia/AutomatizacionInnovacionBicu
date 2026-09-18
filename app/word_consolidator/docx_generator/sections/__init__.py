"""
app.word_consolidator.docx_generator.sections

Renderizadores modulares e independientes para las 10 secciones del
Informe Consolidado Institucional en formato Word (.docx).
"""

from app.word_consolidator.docx_generator.sections.cover import render_cover
from app.word_consolidator.docx_generator.sections.executive_summary import render_executive_summary
from app.word_consolidator.docx_generator.sections.consolidated_table import render_consolidated_table
from app.word_consolidator.docx_generator.sections.activity_cards import render_activity_cards
from app.word_consolidator.docx_generator.sections.demographics import render_demographics
from app.word_consolidator.docx_generator.sections.estamentos import render_estamentos
from app.word_consolidator.docx_generator.sections.territory import render_territory
from app.word_consolidator.docx_generator.sections.quality_audit import render_quality_audit
from app.word_consolidator.docx_generator.sections.conclusions import render_conclusions
from app.word_consolidator.docx_generator.sections.annexes import render_annexes

__all__ = [
    "render_cover",
    "render_executive_summary",
    "render_consolidated_table",
    "render_activity_cards",
    "render_demographics",
    "render_estamentos",
    "render_territory",
    "render_quality_audit",
    "render_conclusions",
    "render_annexes",
]
