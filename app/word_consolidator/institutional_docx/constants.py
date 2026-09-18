"""
app.word_consolidator.institutional_docx.constants

Constantes institucionales formales extraídas del documento oficial de referencia
BICU: 'Documento de Kevds3.docx' (Fase 16.4).
"""

from typing import Dict, List, Tuple

# ============================================================================
# CONFIGURACIÓN DE PÁGINA (Letter Horizontal / Landscape)
# ============================================================================
PAGE_ORIENTATION = "LANDSCAPE"
PAGE_WIDTH_PT = 792.0    # 11.00 inches
PAGE_HEIGHT_PT = 612.0   # 8.50 inches
MARGIN_TOP_PT = 85.05    # 3.0 cm (~1.18 in)
MARGIN_BOTTOM_PT = 85.05 # 3.0 cm (~1.18 in)
MARGIN_LEFT_PT = 70.9    # 2.5 cm (~0.98 in)
MARGIN_RIGHT_PT = 70.9   # 2.5 cm (~0.98 in)

# ============================================================================
# PALETA DE COLORES INSTITUCIONAL (HEX)
# ============================================================================
COLOR_PRIMARY_BLUE = "153D63"     # Azul profundo institucional (Encabezados generales)
COLOR_ACCENT_MAGENTA = "D86DCB"   # Magenta / Púrpura institucional (Columna 'Nombre de la actividad')
COLOR_WHITE = "FFFFFF"            # Blanco (Fondo de valores / Texto sobre azul)
COLOR_BLACK = "000000"            # Negro institucional para textos regulares
COLOR_BORDER_GRID = "000000"      # Color de cuadrícula de la tabla (Table Grid)

# ============================================================================
# TIPOGRAFÍAS Y TAMAÑOS DE FUENTE
# ============================================================================
FONT_DOC_TITLE = "Trebuchet MS"        # Títulos superiores (14.0 pt, Bold, Centrado)
FONT_TABLE_HEADER = "Bookman Old Style" # Encabezados de tabla (10.0 pt, Bold)
FONT_TABLE_BODY = "Bookman Old Style"   # Celdas de datos (10.0 pt, Regular)
FONT_EVIDENCES_TITLE = "Trebuchet MS"  # Sección 'EVIDENCIAS ANEXAS' (12.0 pt, Bold)
FONT_ACTIVITY_HEADING = "Book Antiqua"  # Numeración y nombre de actividad en evidencias (10.5 pt)

# ============================================================================
# DEFINICIÓN EXACTA DE LAS 13 COLUMNAS DE LA TABLA (Anchos en Twips)
# ============================================================================
# 1 twip = 1/20 de punto = 1/1440 de pulgada
GRID_COLUMNS_TWIPS: List[Tuple[int, str, int]] = [
    (0, "Nombre de la actividad", 1980),      # Col 0: ~1.38 in
    (1, "Eje vinculado", 1559),               # Col 1: ~1.08 in
    (2, "Descripción", 2604),                 # Col 2: ~1.81 in
    (3, "Sede", 794),                         # Col 3: ~0.55 in
    (4, "Departamento", 1702),                # Col 4: ~1.18 in
    (5, "Municipio", 994),                    # Col 5: ~0.69 in
    (6, "Tipo de actividad (parte 1)", 1160), # Col 6: span=2 junto a Col 7
    (7, "Tipo de actividad (parte 2)", 235),  # Col 7: span=2 (ancho total: 1395 twips / ~0.97 in)
    (8, "Tipo de protagonistas (p1)", 934),   # Col 8: span=2 junto a Col 9
    (9, "Tipo de protagonistas (p2)", 934),   # Col 9: span=2 (ancho total: 1868 twips / ~1.30 in)
    (10, "M", 565),                           # Col 10: ~0.39 in
    (11, "V", 426),                           # Col 11: ~0.30 in
    (12, "Total", 991),                       # Col 12: ~0.69 in
]

TOTAL_TABLE_WIDTH_TWIPS = sum(w for _, _, w in GRID_COLUMNS_TWIPS) # 14,878 twips (~10.33 in)

# ============================================================================
# MAPA DE ENCABEZADOS Y NOMBRES FORMALES
# ============================================================================
HEADER_DEPTO_LABEL = "Nombre del Depto:"
HEADER_MES_LABEL = "Mes planificado:"
HEADER_SEMANA_LABEL = "Semana:"

SUPERHEADER_ACTIVIDAD = "Nombre de la actividad"
SUPERHEADER_RESULTADOS = "Resultados alcanzados vinculados con el alcance de un Eje"
SUPERHEADER_PROTAGONISTAS = "Protagonistas"

SUBHEADERS_TEXTOS = [
    "Nombre de la actividad",
    "Eje vinculado",
    "Descripción",
    "Sede",
    "Departamento",
    "Municipio",
    "Tipo de actividad",
    "Tipo de protagonistas",
    "M",
    "V",
    "Total",
]
