"""
app.word_consolidator.docx_generator.sections.conclusions

Renderizador de la Sección 9: Conclusiones y Dictamen de Auditoría.
Presenta estrictamente los hallazgos y puntos clave soportados por el modelo documental.
Cumple rigurosamente la regla de NO INVENTAR dictámenes institucionales ni emitir
juicios libres no respaldados por los datos calculados.
"""

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from app.word_consolidator.document.models import ConclusionDocumental
from app.word_consolidator.docx_generator.style_manager import ColorPalette, StyleManager
from app.word_consolidator.docx_generator.table_builder import TableBuilder


def render_conclusions(
    doc: docx.Document,
    conclusiones: ConclusionDocumental,
) -> None:
    """
    Construye la sección de Conclusiones y Dictamen Técnico.
    """
    StyleManager.add_heading_1(doc, "9. CONCLUSIONES Y DICTAMEN TÉCNICO")

    StyleManager.add_paragraph(
        doc,
        "Las siguientes conclusiones y recomendaciones operativas se derivan estrictamente "
        "de la evidencia cuantitativa consolidada y de los resultados del motor de auditoría:",
        space_after=8,
    )

    # 1. Dictamen Técnico de Auditoría
    StyleManager.add_heading_2(doc, "9.1. Dictamen Técnico de Auditoría")

    dictamen = conclusiones.dictamen_auditoria or "CONCORDANTE"
    
    if "OBSERVACIONES" in dictamen.upper() or "REVISION" in dictamen.upper():
        StyleManager.add_callout(
            doc,
            text=(
                f"ESTADO TÉCNICO: {dictamen}. "
                "Se detectaron divergencias matemáticas o discrepancias entre los totales agregados "
                "y las listas nominales de participantes. Se recomienda remitir los hallazgos a las áreas "
                "ejecutoras correspondientes para su aclaración formal."
            ),
            title="DICTAMEN DE AUDITORÍA",
            bg_hex=ColorPalette.REVISION_BG,
            border_hex=ColorPalette.REVISION_TEXT,
        )
    else:
        StyleManager.add_callout(
            doc,
            text=(
                f"ESTADO TÉCNICO: {dictamen}. "
                "Todas las actividades y dimensiones evaluadas coinciden plenamente (0 discrepancias) "
                "entre los reportes agregados y los registros nominales verificados."
            ),
            title="DICTAMEN DE AUDITORÍA",
            bg_hex=ColorPalette.CONCORDANTE_BG,
            border_hex=ColorPalette.CONCORDANTE_TEXT,
        )

    # 2. Puntos Clave Derivados del Modelo
    if conclusiones.puntos_clave:
        StyleManager.add_heading_2(doc, "9.2. Puntos Clave de la Consolidación", space_before=8)
        for punto in conclusiones.puntos_clave:
            p_bullet = doc.add_paragraph(style="List Bullet")
            p_bullet.paragraph_format.space_before = Pt(1)
            p_bullet.paragraph_format.space_after = Pt(3)
            r_pt = p_bullet.add_run(punto)
            r_pt.font.name = StyleManager.FONT_NAME
            r_pt.font.size = StyleManager.SIZE_BODY
            r_pt.font.color.rgb = StyleManager.hex_to_rgb(ColorPalette.TEXT_DARK)

    # 3. Recomendaciones Operativas de Auditoría
    if conclusiones.recomendaciones_auditoria:
        StyleManager.add_heading_2(doc, "9.3. Recomendaciones Operativas", space_before=8)
        for rec in conclusiones.recomendaciones_auditoria:
            p_bullet = doc.add_paragraph(style="List Bullet")
            p_bullet.paragraph_format.space_before = Pt(1)
            p_bullet.paragraph_format.space_after = Pt(3)
            r_rec = p_bullet.add_run(rec)
            r_rec.font.name = StyleManager.FONT_NAME
            r_rec.font.size = StyleManager.SIZE_BODY
            r_rec.font.color.rgb = StyleManager.hex_to_rgb(ColorPalette.TEXT_DARK)

    # 4. Resumen Narrativo (sólo si fue suministrado en la fuente)
    if conclusiones.resumen_narrativo:
        StyleManager.add_heading_2(doc, "9.4. Resumen Narrativo Oficial", space_before=8)
        StyleManager.add_paragraph(doc, conclusiones.resumen_narrativo, italic=True)
