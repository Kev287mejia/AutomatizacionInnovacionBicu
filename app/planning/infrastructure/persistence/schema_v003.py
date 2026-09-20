"""Especificación del Esquema Físico DDL SQLite V003 - Módulo Planificación.

Fase 29.4.2 — Implementación de Persistencia SQLite V003.
Decisiones Institucionales cerradas:
  - D-10: Persistencia estructurada en SQLite.
  - D-02: Solo versión vigente in-place (sin tablas de histórico de versiones).
  - R-08: Inmutabilidad estricta cuando el estado alcanza APPROVED.
  - D-04: Identidad técnica UUID v4 (activity_internal_id / design_id) y preservación
          de planning_id como clave institucional externa.
  - Trazabilidad IA: Tabla planning_ai_proposals con CHECK (requires_review = 1).
"""

from typing import List, Set

# ---------------------------------------------------------------------------
# ESQUEMA V003: TABLAS PLANNING_*
# ---------------------------------------------------------------------------
V003_SCHEMA_DDL_STATEMENTS: List[str] = [
    # 1. PLANNING_PLANNED_ACTIVITIES
    """
    CREATE TABLE IF NOT EXISTS planning_planned_activities (
        activity_internal_id TEXT PRIMARY KEY,
        planning_id TEXT NOT NULL UNIQUE,
        activity_name TEXT NOT NULL,
        sede TEXT NOT NULL,
        area_responsable TEXT NOT NULL,
        eje_estrategia TEXT NOT NULL,
        programa TEXT NOT NULL,
        tipo_evento TEXT NOT NULL,
        dep_sede TEXT NOT NULL DEFAULT '',
        mun_sede TEXT NOT NULL DEFAULT '',
        otro_programa TEXT,
        proyecto TEXT,
        tipo_proyecto TEXT,
        ambito TEXT,
        codigo_presupuestario TEXT,
        departamento_responsable TEXT,
        proposito TEXT,
        fecha_evento TEXT,
        convenio TEXT,
        entidades_cooperantes TEXT,
        est_grado_m INTEGER NOT NULL DEFAULT 0 CHECK (est_grado_m >= 0),
        est_grado_f INTEGER NOT NULL DEFAULT 0 CHECK (est_grado_f >= 0),
        est_postgrado_m INTEGER NOT NULL DEFAULT 0 CHECK (est_postgrado_m >= 0),
        est_postgrado_f INTEGER NOT NULL DEFAULT 0 CHECK (est_postgrado_f >= 0),
        docentes_m INTEGER NOT NULL DEFAULT 0 CHECK (docentes_m >= 0),
        docentes_f INTEGER NOT NULL DEFAULT 0 CHECK (docentes_f >= 0),
        administrativos_m INTEGER NOT NULL DEFAULT 0 CHECK (administrativos_m >= 0),
        administrativos_f INTEGER NOT NULL DEFAULT 0 CHECK (administrativos_f >= 0),
        externos_m INTEGER NOT NULL DEFAULT 0 CHECK (externos_m >= 0),
        externos_f INTEGER NOT NULL DEFAULT 0 CHECK (externos_f >= 0),
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    );
    """,

    # 2. PLANNING_METHODOLOGICAL_DESIGNS
    """
    CREATE TABLE IF NOT EXISTS planning_methodological_designs (
        design_id TEXT PRIMARY KEY,
        planned_activity_internal_id TEXT NOT NULL REFERENCES planning_planned_activities(activity_internal_id) ON DELETE RESTRICT,
        planned_activity_ref TEXT NOT NULL UNIQUE,
        activity_name TEXT NOT NULL DEFAULT '',
        version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
        status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'GENERATED', 'REVIEW', 'APPROVED', 'REJECTED')),
        introduction_text TEXT NOT NULL DEFAULT '',
        methodological_approach TEXT NOT NULL DEFAULT '',
        objective_1 TEXT NOT NULL DEFAULT '',
        objective_2 TEXT NOT NULL DEFAULT '',
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        approved_by TEXT,
        approved_at TEXT,
        document_hash TEXT,
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    );
    """,

    # 3. PLANNING_DESIGN_FAQS (Bloque 3 - 7 preguntas institucionales 1:1)
    """
    CREATE TABLE IF NOT EXISTS planning_design_faqs (
        design_id TEXT PRIMARY KEY REFERENCES planning_methodological_designs(design_id) ON DELETE CASCADE,
        q1_que_es TEXT NOT NULL,
        q2_para_que TEXT NOT NULL DEFAULT '',
        q3_sesiones TEXT NOT NULL DEFAULT 'Sesión única',
        q4_protagonistas TEXT NOT NULL,
        q5_facilitador TEXT NOT NULL,
        q6_materiales TEXT NOT NULL DEFAULT '',
        q7_duracion TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    );
    """,

    # 4. PLANNING_DESIGN_AGENDA (Bloque 4 - Tabla 2 Programa)
    """
    CREATE TABLE IF NOT EXISTS planning_design_agenda (
        agenda_id TEXT PRIMARY KEY,
        design_id TEXT NOT NULL REFERENCES planning_methodological_designs(design_id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL CHECK (sequence > 0),
        label TEXT NOT NULL,
        minutes INTEGER NOT NULL CHECK (minutes > 0),
        UNIQUE (design_id, sequence)
    );
    """,

    # 5. PLANNING_DESIGN_OPERATIONAL_MATRIX (Bloque 5 - Tabla 3 Matriz de Planificación)
    """
    CREATE TABLE IF NOT EXISTS planning_design_operational_matrix (
        operational_id TEXT PRIMARY KEY,
        design_id TEXT NOT NULL REFERENCES planning_methodological_designs(design_id) ON DELETE CASCADE,
        step_number INTEGER NOT NULL CHECK (step_number > 0),
        phase_label TEXT NOT NULL,
        operative_goal TEXT NOT NULL DEFAULT '',
        procedure TEXT NOT NULL DEFAULT '',
        materials TEXT NOT NULL DEFAULT '',
        minutes INTEGER NOT NULL CHECK (minutes > 0),
        UNIQUE (design_id, step_number)
    );
    """,

    # 6. PLANNING_AI_PROPOSALS (Auditoría pericial de asistencia IA con contención física)
    """
    CREATE TABLE IF NOT EXISTS planning_ai_proposals (
        proposal_id TEXT PRIMARY KEY,
        design_id TEXT NOT NULL REFERENCES planning_methodological_designs(design_id) ON DELETE CASCADE,
        target_field TEXT NOT NULL CHECK (target_field IN ('introduction', 'methodological_approach', 'objective_1', 'objective_2', 'procedure', 'operative_goal')),
        proposed_content TEXT NOT NULL,
        source_inputs TEXT NOT NULL,
        confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
        requires_review INTEGER NOT NULL DEFAULT 1 CHECK (requires_review = 1),
        accepted INTEGER CHECK (accepted IS NULL OR accepted IN (0, 1)),
        reviewed_by TEXT,
        review_timestamp TEXT,
        rejection_reason TEXT,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    );
    """,
]

# ---------------------------------------------------------------------------
# ÍNDICES RELACIONALES B-TREE V003
# ---------------------------------------------------------------------------
V003_INDEXES_DDL_STATEMENTS: List[str] = [
    "CREATE INDEX IF NOT EXISTS idx_planning_act_name ON planning_planned_activities(activity_name);",
    "CREATE INDEX IF NOT EXISTS idx_planning_act_sede ON planning_planned_activities(sede);",
    "CREATE INDEX IF NOT EXISTS idx_planning_act_programa ON planning_planned_activities(programa);",
    "CREATE INDEX IF NOT EXISTS idx_planning_design_act_id ON planning_methodological_designs(planned_activity_internal_id);",
    "CREATE INDEX IF NOT EXISTS idx_planning_design_status ON planning_methodological_designs(status);",
    "CREATE INDEX IF NOT EXISTS idx_planning_agenda_design ON planning_design_agenda(design_id, sequence);",
    "CREATE INDEX IF NOT EXISTS idx_planning_matrix_design ON planning_design_operational_matrix(design_id, step_number);",
    "CREATE INDEX IF NOT EXISTS idx_planning_proposals_design ON planning_ai_proposals(design_id);",
]

# Catálogo ampliado de tablas en V003
EXPECTED_PLANNING_TABLE_NAMES: Set[str] = {
    "planning_planned_activities",
    "planning_methodological_designs",
    "planning_design_faqs",
    "planning_design_agenda",
    "planning_design_operational_matrix",
    "planning_ai_proposals",
}
