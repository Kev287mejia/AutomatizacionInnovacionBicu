"""
Catalogos institucionales BICU — C1 a C5.
Fuente: FASE_29_1_ANALISIS_INSTITUCIONAL_PLANIFICACION_DISENO_METODOLOGICO.md
Clasificacion: EVIDENCIA DIRECTA (matrices POA reales)

ADVERTENCIA C1: Existe discrepancia entre la numeracion observada en matrices POA
("Linea Estrategica 7: Creatividad, Ciencias, Investigacion e Innovacion") y la lista
oficial C1 (EJE 7 = Cambio Climatico, EJE 11 = Investigacion e Innovacion).
Requiere aclaracion institucional antes de hardcodear como verdad absoluta.
Referencia: FASE_29_2_1_CIERRE_DECISIONES_INSTITUCIONALES.md §12

Fase 29.3 — Dominio Puro
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# C1 — Ejes de la Estrategia Nacional de Educacion
# EVIDENCIA DIRECTA: matrices POA reales.
# ADVERTENCIA: discrepancia en numeracion (ver docstring de modulo).
# ---------------------------------------------------------------------------
C1_EJES_ESTRATEGICOS: dict[str, str] = {
    "EJE_1":  "Calidad, Pertinencia y Relevancia del Aprendizaje y la Ensenanza",
    "EJE_2":  "Equidad, Inclusion y Permanencia en el Sistema Educativo",
    "EJE_3":  "Salud, Bienestar y Conducta Ciudadana",
    "EJE_4":  "Formacion Docente y Desarrollo Profesional",
    "EJE_5":  "Gestion Institucional, Autonomia Universitaria y Transparencia",
    "EJE_6":  "Conectividad y Acceso a las Tecnologias de la Informacion",
    "EJE_7":  "Cambio Climatico y Gestion de Riesgo",
    "EJE_8":  "Interculturalidad, Diversidad Linguistica e Identidad",
    "EJE_9":  "Ciudadania Global y Cooperacion Internacional",
    "EJE_10": "Creatividad, Ciencias, Investigacion e Innovacion",
    "EJE_11": "Innovacion, Ciencia, Tecnologia e Investigacion",
}

# Conjunto de codigos validos para validacion rapida (R-08)
C1_CODES: frozenset[str] = frozenset(C1_EJES_ESTRATEGICOS.keys())

# ---------------------------------------------------------------------------
# C2 — Programas Institucionales de Vinculacion
# EVIDENCIA DIRECTA: matrices POA reales.
# ---------------------------------------------------------------------------
C2_PROGRAMAS: dict[str, str] = {
    "PGM_01": "Formacion y Capacitacion Continua",
    "PGM_02": "Atencion y Acompanamiento Social",
    "PGM_03": "Asistencia Tecnica y Tecnologica",
    "PGM_04": "Promocion Cultural y Artistica",
    "PGM_05": "Educacion Ambiental y Gestion de Riesgo",
    "PGM_06": "Fortalecimiento Juridico y Ciudadano",
    "PGM_07": "Emprendimiento y Desarrollo Economico",
    "PGM_08": "Salud Comunitaria y Bienestar",
    "PGM_09": "Interculturalidad y Lenguas",
    "PGM_10": "Investigacion e Innovacion Comunitaria",
    "PGM_11": "Cooperacion y Alianzas Estrategicas",
}

C2_CODES: frozenset[str] = frozenset(C2_PROGRAMAS.keys())

# ---------------------------------------------------------------------------
# C3 — Ambitos Institucionales
# EVIDENCIA DIRECTA: 3 ambitos verificados en matrices POA.
# ---------------------------------------------------------------------------
C3_AMBITOS: dict[str, str] = {
    "AMB_EDU":  "Educativo",
    "AMB_ECO":  "Economico",
    "AMB_SPRO": "Socio-Productivo",
}

C3_CODES: frozenset[str] = frozenset(C3_AMBITOS.keys())

# ---------------------------------------------------------------------------
# C4 — Tipos de Evento Institucional
# EVIDENCIA DIRECTA: 11 tipos verificados en documentos reales y matrices POA.
# ---------------------------------------------------------------------------
C4_TIPOS_EVENTO: dict[str, str] = {
    "EVT_CAMPANA":       "Campana",
    "EVT_CAPACITACION":  "Capacitacion",
    "EVT_CHARLA":        "Charla",
    "EVT_COLOQUIO":      "Coloquio",
    "EVT_COMPETENCIA":   "Competencia",
    "EVT_CONFERENCIA":   "Conferencia",
    "EVT_CONGRESO":      "Congreso",
    "EVT_CONMEMORACION": "Conmemoracion",
    "EVT_CONVERSATORIO": "Conversatorio",
    "EVT_FERIA":         "Feria",
    "EVT_FESTIVAL":      "Festival",
}

C4_CODES: frozenset[str] = frozenset(C4_TIPOS_EVENTO.keys())

# ---------------------------------------------------------------------------
# C5 — Tipos de Proyecto
# EVIDENCIA DIRECTA: 4 tipos verificados.
# ---------------------------------------------------------------------------
C5_TIPOS_PROYECTO: dict[str, str] = {
    "PRY_SOCIAL":        "Social",
    "PRY_PRODUCTIVO":    "Productivo",
    "PRY_INNOVACION":    "Innovacion",
    "PRY_EMPRENDIMIENTO": "Emprendimiento",
}

C5_CODES: frozenset[str] = frozenset(C5_TIPOS_PROYECTO.keys())

# --- ALIASES CONVENCIONALES ---
CATALOG_C1_EJES = C1_EJES_ESTRATEGICOS
CATALOG_C2_PROGRAMAS = C2_PROGRAMAS
CATALOG_C3_AMBITOS = C3_AMBITOS
CATALOG_C4_TIPOS_EVENTO = C4_TIPOS_EVENTO
CATALOG_C5_TIPOS_PROYECTO = C5_TIPOS_PROYECTO

# ---------------------------------------------------------------------------
# LITERALES INSTITUCIONALES CONFIGURABLES
# Fuente: FASE_29_2 §12, FASE_29_2_1 §17
# Clasificacion: EVIDENCIA DIRECTA del literal historico
# Estado: Configurable (D-06, D-07 pendientes de validacion institucional)
# ---------------------------------------------------------------------------

# D-06: Encabezado del bloque de objetivos.
# Literal historico verificado en 100% del corpus (5/5 documentos).
# Semanticamente incorrecto para tipos no artisticos, pero es el estandar de facto.
OBJECTIVES_HEADING_DEFAULT: str = "OBJETIVOS DEL TALLER ARTISTICO"

# D-07: Encabezados de secciones Tabla 2 y Tabla 3.
# Literales historicos verificados en 100% del corpus.
PROGRAM_SECTION_HEADING_DEFAULT: str = "III. PROGRAMA"
MATRIX_SECTION_HEADING_DEFAULT: str = "VI. MATRIZ DE PLANIFICACION"

# D-05: Texto por defecto para Pregunta 3 (sesiones).
# Evidencia directa: 100% corpus = sesion unica.
DEFAULT_SESSION_TEXT: str = "Sesión única"

# Identificadores de catalogo — usados en CatalogReference.catalog_id
CATALOG_ID_EJE:      str = "C1_EJE"
CATALOG_ID_PROGRAMA: str = "C2_PROGRAMA"
CATALOG_ID_AMBITO:   str = "C3_AMBITO"
CATALOG_ID_EVENTO:   str = "C4_EVENTO"
CATALOG_ID_PROYECTO: str = "C5_PROYECTO"

VALID_CATALOG_IDS: frozenset[str] = frozenset({
    CATALOG_ID_EJE,
    CATALOG_ID_PROGRAMA,
    CATALOG_ID_AMBITO,
    CATALOG_ID_EVENTO,
    CATALOG_ID_PROYECTO,
})
