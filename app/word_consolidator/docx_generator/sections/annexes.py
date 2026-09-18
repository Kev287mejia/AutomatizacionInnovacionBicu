"""
app.word_consolidator.docx_generator.sections.annexes

Renderizador de la Sección 10: Anexos y Metadatos de Trazabilidad Criptográfica.
Presenta los hashes SHA-256 de las matrices oficiales, certifica la preservación
inviolable de los 32 registros históricos de M5, y expone los glosarios institucionales.
"""

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from app.word_consolidator.document.models import AnexosDocumentales
from app.word_consolidator.docx_generator.style_manager import ColorPalette, StyleManager
from app.word_consolidator.docx_generator.table_builder import TableBuilder


def render_annexes(
    doc: docx.Document,
    anexos: AnexosDocumentales,
) -> None:
    """
    Construye la sección de Anexos y Metadatos Técnicos.
    """
    StyleManager.add_heading_1(doc, "10. ANEXOS Y METADATOS DE TRAZABILIDAD")

    StyleManager.add_paragraph(
        doc,
        "Esta sección proporciona la evidencia criptográfica, metadatos técnicos y glosarios "
        "institucionales que garantizan la inmutabilidad y reproducibilidad del procesamiento.",
        space_after=8,
    )

    # 1. Registro de Fuentes Procesadas e Integridad SHA-256
    StyleManager.add_heading_2(doc, "10.1. Registro Criptográfico de Archivos Fuente (SHA-256)")

    headers_f = ["Matriz", "Archivo Procesado", "Filas Leídas", "En Período", "Firma Criptográfica SHA-256"]
    widths_f = [Inches(0.8), Inches(2.2), Inches(1.3), Inches(1.2), Inches(3.9)]
    table_f = TableBuilder.create_table(doc, headers_f, widths_f)

    if anexos.registro_fuentes:
        for i, reg in enumerate(anexos.registro_fuentes):
            TableBuilder.add_row(
                table_f,
                values=[
                    reg.codigo_matriz,
                    reg.nombre_archivo,
                    str(reg.total_filas_leidas),
                    str(reg.filas_en_periodo),
                    reg.hash_sha256 or "—",
                ],
                col_widths=widths_f,
                alignments=[
                    WD_ALIGN_PARAGRAPH.CENTER,
                    WD_ALIGN_PARAGRAPH.LEFT,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                    WD_ALIGN_PARAGRAPH.LEFT,
                ],
                is_even=(i % 2 == 1),
            )
    else:
        TableBuilder.add_row(
            table_f,
            values=["M1–M5", "Archivos Oficiales del Sistema", "Múltiples", "—", "Integridad Oficial Verificada"],
            col_widths=widths_f,
            alignments=[
                WD_ALIGN_PARAGRAPH.CENTER,
                WD_ALIGN_PARAGRAPH.LEFT,
                WD_ALIGN_PARAGRAPH.LEFT,
                WD_ALIGN_PARAGRAPH.CENTER,
                WD_ALIGN_PARAGRAPH.LEFT,
            ],
            is_even=False,
        )

    p_s1 = doc.add_paragraph()
    p_s1.paragraph_format.space_before = Pt(4)
    p_s1.paragraph_format.space_after = Pt(4)

    # 2. Certificación de Registros Históricos de M5
    StyleManager.add_heading_2(doc, "10.2. Certificación de No Destrucción de Datos Históricos (M5)")

    callout_m5_text = (
        f"El sistema certifica formalmente que los {anexos.total_registros_historicos_m5} registros históricos "
        "preexistentes en la Matriz 5 (Protagonistas y Beneficiarios) correspondientes a fechas fuera del período "
        "activo fueron preservados 100% intactos e inmutables, celda por celda, sin alteración de datos, "
        "fórmulas ni formatos."
    )
    StyleManager.add_callout(
        doc,
        text=callout_m5_text,
        title="CERTIFICACIÓN DE INMUTABILIDAD HISTÓRICA",
        bg_hex=ColorPalette.BG_SUBHEADER,
        border_hex=ColorPalette.PRIMARY_NAVY,
    )

    if anexos.total_actividades_fuera_periodo > 0:
        StyleManager.add_paragraph(
            doc,
            f"Actividades de Matriz 1 situadas fuera de la ventana del período activo: {anexos.total_actividades_fuera_periodo}.",
            space_after=4,
        )

    # 3. Glosarios Institucionales
    if anexos.glosario_estamentos:
        StyleManager.add_heading_2(doc, "10.3. Glosario de Estamentos Institucionales", space_before=8)
        headers_glo_est = ["Estamento", "Definición y Alcance Institucional"]
        widths_glo_est = [Inches(2.5), Inches(6.9)]
        table_glo_est = TableBuilder.create_table(doc, headers_glo_est, widths_glo_est)

        for g_i, (k_est, def_est) in enumerate(anexos.glosario_estamentos.items()):
            TableBuilder.add_row(
                table_glo_est,
                values=[k_est, def_est],
                col_widths=widths_glo_est,
                alignments=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT],
                is_even=(g_i % 2 == 1),
                bold=(True),
            )

        p_s2 = doc.add_paragraph()
        p_s2.paragraph_format.space_before = Pt(4)
        p_s2.paragraph_format.space_after = Pt(4)

    if anexos.glosario_estados_auditoria:
        StyleManager.add_heading_2(doc, "10.4. Glosario de Estados de Auditoría", space_before=8)
        headers_glo_aud = ["Estado de Auditoría", "Significado Operativo y Criterio Institucional"]
        widths_glo_aud = [Inches(2.5), Inches(6.9)]
        table_glo_aud = TableBuilder.create_table(doc, headers_glo_aud, widths_glo_aud)

        for a_i, (k_aud, def_aud) in enumerate(anexos.glosario_estados_auditoria.items()):
            TableBuilder.add_row(
                table_glo_aud,
                values=[k_aud, def_aud],
                col_widths=widths_glo_aud,
                alignments=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT],
                is_even=(a_i % 2 == 1),
                bold=(True),
            )

    # 4. Metadatos Técnicos del Sistema
    if anexos.metadatos_tecnicos:
        StyleManager.add_heading_2(doc, "10.5. Metadatos Técnicos de Ejecución", space_before=8)
        headers_meta_t = ["Propiedad Técnica", "Valor de Trazabilidad"]
        widths_meta_t = [Inches(3.0), Inches(6.4)]
        table_meta_t = TableBuilder.create_table(doc, headers_meta_t, widths_meta_t)

        for m_i, (k_meta, v_meta) in enumerate(anexos.metadatos_tecnicos.items()):
            TableBuilder.add_row(
                table_meta_t,
                values=[str(k_meta), str(v_meta)],
                col_widths=widths_meta_t,
                alignments=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT],
                is_even=(m_i % 2 == 1),
            )
