"""
app.word_consolidator.institutional_docx.evidences_builder

Renderizador de la sección 'EVIDENCIAS ANEXAS' del Informe Semanal Institucional BICU.
Implementa la estructura tripartita (Fotografías, Registros de asistencia, Enlaces)
conforme al documento oficial 'Documento de Kevds3.docx'.

Reglas de integridad estrictas:
- NO se inventan imágenes ficticias.
- NO se crean URLs falsas.
- NO se insertan placeholders visuales.
- Solo se renderiza lo que exista en el modelo como referencia válida.
- Si una imagen local no existe en disco, se omite y se registra la advertencia.
"""

import os
import warnings
from pathlib import Path
from typing import Optional

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.word_consolidator.institutional_docx.constants import (
    FONT_DOC_TITLE,
    FONT_ACTIVITY_HEADING,
    COLOR_WHITE,
    COLOR_BLACK,
)
from app.word_consolidator.institutional_docx.spec import (
    EvidenciasSectionSpec,
    EvidenciasActividadSpec,
    EvidenciaItemSpec,
)

# ============================================================================
# CONSTANTES DE ESTILO DE LA SECCIÓN DE EVIDENCIAS
# ============================================================================

_TITLE_FONT = FONT_DOC_TITLE       # "Trebuchet MS" (Bold, color blanco con fondo darkCyan)
_ACTIVITY_FONT = FONT_ACTIVITY_HEADING  # "Book Antiqua"
_BODY_FONT = "Calibri"             # Cuerpo de texto estándar

_TITLE_COLOR_RGB = RGBColor(0xFF, 0xFF, 0xFF)  # Blanco (sobre fondo darkCyan)
_BODY_COLOR_RGB = RGBColor(0x00, 0x00, 0x00)   # Negro

# Dimensiones máximas de imagen para mantener proporción sin desbordamiento
_MAX_IMAGE_WIDTH_CM = 8.0
_MAX_IMAGE_HEIGHT_CM = 6.0

# Separadores tipográficos entre categorías de evidencia
_CATEGORY_LABELS = {
    "fotografias": "Fotografías",
    "registros_asistencia": "Registro de asistencias",
    "enlaces_publicaciones": (
        "Enlaces de publicaciones de material gráfico "
        "y audiovisual en redes sociales o sitios web"
    ),
}


# ============================================================================
# HELPERS DE FORMATO
# ============================================================================

def _add_page_break(doc: Document) -> None:
    """Inserta un salto de página explícito al documento."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after = Pt(0)
    run = para.add_run()
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    run._r.append(br)


def _add_evidences_title(doc: Document, titulo: str) -> None:
    """
    Agrega el párrafo de título 'EVIDENCIAS ANEXAS' con el estilo
    del documento institucional real: texto blanco, Bold, sobre fondo darkCyan.
    """
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after = Pt(0)

    run = para.add_run(titulo)
    run.bold = True
    run.font.name = _TITLE_FONT
    run.font.color.rgb = _TITLE_COLOR_RGB

    # Aplicar highlight darkCyan (como en el documento original)
    rPr = run._r.get_or_add_rPr()
    highlight = OxmlElement("w:highlight")
    highlight.set(qn("w:val"), "darkCyan")
    rPr.append(highlight)


def _add_activity_heading(doc: Document, heading_text: str) -> None:
    """
    Agrega el encabezado numerado de una actividad dentro de la sección de evidencias.
    Usa Book Antiqua, sin negrita, texto negro.
    """
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(6)
    para.paragraph_format.space_after = Pt(0)

    run = para.add_run(heading_text)
    run.bold = False
    run.font.name = _ACTIVITY_FONT
    run.font.size = Pt(10.5)
    run.font.color.rgb = _BODY_COLOR_RGB


def _add_category_label(doc: Document, label: str) -> None:
    """
    Agrega el rótulo de categoría de evidencia (Fotografías, Registro, Enlaces)
    en estilo List Paragraph cursiva, justificado.
    """
    para = doc.add_paragraph(style="List Paragraph")
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    para.paragraph_format.space_before = Pt(12)
    para.paragraph_format.space_after = Pt(0)
    para.paragraph_format.line_spacing = Pt(1.15 * 12)  # 1.15 × cuerpo

    run = para.add_run(label)
    run.italic = True
    run.font.color.rgb = _BODY_COLOR_RGB


def _add_url_paragraph(doc: Document, url: str) -> None:
    """Agrega una URL como párrafo en estilo List Paragraph."""
    para = doc.add_paragraph(style="List Paragraph")
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after = Pt(0)
    para.paragraph_format.line_spacing = Pt(1.15 * 12)

    run = para.add_run(url)
    run.font.color.rgb = _BODY_COLOR_RGB


def _add_empty_separator(doc: Document) -> None:
    """Agrega un párrafo vacío de separación."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after = Pt(4)


# ============================================================================
# RENDERIZADORES DE EVIDENCIAS INDIVIDUALES
# ============================================================================

def _render_image(doc: Document, evidencia: EvidenciaItemSpec) -> bool:
    """
    Intenta insertar una imagen referenciada por ruta local.

    Returns:
        True si la imagen fue insertada exitosamente.
        False si no existe el archivo (no se inserta placeholder).
    """
    ref = evidencia.referencia.strip()

    # Validar si es una ruta local (no URL)
    if ref.startswith("http://") or ref.startswith("https://"):
        return False  # URLs de imágenes no se descargan en esta fase

    path = Path(ref)
    if not path.exists() or not path.is_file():
        warnings.warn(
            f"[EvidencesBuilder] Imagen no encontrada en disco: '{ref}'. "
            "Se omite sin insertar placeholder.",
            UserWarning,
            stacklevel=2,
        )
        return False

    # Determinar extensión compatible con python-docx
    ext = path.suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif"}:
        warnings.warn(
            f"[EvidencesBuilder] Formato de imagen no compatible: '{ext}'. "
            "Se omite.",
            UserWarning,
            stacklevel=2,
        )
        return False

    try:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(4)

        run = para.add_run()
        run.add_picture(str(path), width=Cm(_MAX_IMAGE_WIDTH_CM))
        return True
    except Exception as exc:
        warnings.warn(
            f"[EvidencesBuilder] Error al insertar imagen '{ref}': {exc}. "
            "Se omite.",
            UserWarning,
            stacklevel=2,
        )
        return False


def _render_fotografias(
    doc: Document,
    evidencias: list,
    actividad_nombre: str,
) -> None:
    """
    Renderiza la subsección de Fotografías de una actividad.
    Si no hay fotografías, no inserta nada.
    """
    if not evidencias:
        return

    _add_category_label(doc, _CATEGORY_LABELS["fotografias"])

    para_imgs = doc.add_paragraph()
    para_imgs.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para_imgs.paragraph_format.space_before = Pt(0)
    para_imgs.paragraph_format.space_after = Pt(4)

    images_inserted = 0
    for ev in sorted(evidencias, key=lambda e: e.orden):
        inserted = _render_image(doc, ev)
        if inserted:
            images_inserted += 1


def _render_registros_asistencia(
    doc: Document,
    evidencias: list,
) -> None:
    """
    Renderiza la subsección de Registros de Asistencia de una actividad.
    Si no hay registros, no inserta nada.
    """
    if not evidencias:
        return

    _add_category_label(doc, _CATEGORY_LABELS["registros_asistencia"])

    for ev in sorted(evidencias, key=lambda e: e.orden):
        _render_image(doc, ev)
        _add_empty_separator(doc)


def _render_enlaces(doc: Document, evidencias: list) -> None:
    """
    Renderiza la subsección de Enlaces de Publicaciones.
    Solo incluye URLs reales del modelo; no crea URLs ficticias.
    """
    if not evidencias:
        return

    _add_category_label(doc, _CATEGORY_LABELS["enlaces_publicaciones"])

    for ev in sorted(evidencias, key=lambda e: e.orden):
        ref = ev.referencia.strip()
        if ref:
            _add_url_paragraph(doc, ref)


# ============================================================================
# RENDERIZADOR DE ACTIVIDAD COMPLETA
# ============================================================================

def _render_actividad_evidencias(
    doc: Document,
    act_spec: EvidenciasActividadSpec,
) -> None:
    """
    Renderiza el bloque completo de evidencias de una actividad:
    encabezado numerado + tres categorías en orden institucional.
    """
    _add_activity_heading(doc, act_spec.heading_text)

    _render_fotografias(doc, act_spec.fotografias, act_spec.nombre_actividad)
    _render_registros_asistencia(doc, act_spec.registros_asistencia)
    _render_enlaces(doc, act_spec.enlaces_publicaciones)

    _add_empty_separator(doc)


# ============================================================================
# RENDERIZADOR DE OBSERVACIÓN DE DISCREPANCIAS
# ============================================================================

def add_discrepancy_observation(doc: Document, informe_nombre_depto: str) -> None:
    """
    Agrega una observación institucional breve e discreta cuando existen discrepancias
    activas entre los datos declarados (M1) y los registros nominales verificados.

    Esta observación es formalmente distinta del dossier técnico (Producto A).
    """
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(6)
    para.paragraph_format.space_after = Pt(6)

    run = para.add_run(
        "Observación: Existen diferencias entre los datos declarados y los registros "
        "nominales verificados en uno o más estamentos de este informe. "
        "El análisis detallado está disponible en el Dossier Técnico de Auditoría."
    )
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x60, 0x60, 0x60)  # Gris discreto


# ============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ============================================================================

def build_evidences_section(
    doc: Document,
    evidencias_spec: EvidenciasSectionSpec,
    tiene_discrepancias: bool = False,
    nombre_depto: str = "",
) -> None:
    """
    Construye y agrega la sección 'EVIDENCIAS ANEXAS' completa al documento.

    Args:
        doc: Objeto Document de python-docx.
        evidencias_spec: Especificación calculada por build_evidencias_spec().
        tiene_discrepancias: True si el informe tiene discrepancias activas.
        nombre_depto: Nombre del departamento para la observación.
    """
    # Salto de página formal antes de la sección de evidencias
    if evidencias_spec.requiere_salto_pagina_previo:
        _add_page_break(doc)

    # Título de sección
    _add_evidences_title(doc, evidencias_spec.titulo)

    # Observación de discrepancias si aplica (antes de las evidencias)
    if tiene_discrepancias:
        add_discrepancy_observation(doc, nombre_depto)

    # Renderizar cada actividad
    for act_spec in evidencias_spec.actividades:
        _render_actividad_evidencias(doc, act_spec)

    # Si no hay actividades ni evidencias, agregar nota formal
    if len(evidencias_spec.actividades) == 0:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(6)
        run = para.add_run("No existen evidencias disponibles para este período.")
        run.italic = True
        run.font.size = Pt(10)
        run.font.color.rgb = _BODY_COLOR_RGB
