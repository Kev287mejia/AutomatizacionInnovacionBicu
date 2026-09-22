"""Especificación del Esquema Físico DDL SQLite V004 — Trazabilidad Planificación ↔ Ejecución.

Fase 29.18.1 — Implementación Controlada de Trazabilidad PlanningExecutionLink.

PRINCIPIO RECTOR ABSOLUTO: PLANIFICADO ≠ EJECUTADO.

La tabla planning_execution_links es el ÚNICO punto de contacto institucional entre
el dominio de planificación y el dominio de ejecución. Su propósito es registrar la
voluntad institucional auditada de vincular una actividad planificada con su ejecución
real. NO copia datos personales, metas, fechas, ni cantidades entre dominios.

Decisiones de diseño V004 (cerradas, inmutables):
  D-V004-01: UNIQUE(planning_internal_id, id_actividad) — un solo vínculo activo por par.
  D-V004-02: linked_by, linked_at, link_rationale — auditoría completa de autoría humana.
  D-V004-03: link_status IN {'ACTIVE', 'SUPERSEDED', 'REVOKED'} — ciclo de vida auditable.
  D-V004-04: numero_sesion INTEGER (nullable) — soporte a actividades multi-sesión.
  D-V004-05: FK RESTRICT → planning_planned_activities.activity_internal_id.
  D-V004-06: FK RESTRICT → actividad.id_actividad (tabla patrimonial de ejecución).
  D-V004-07: V003 es INMUTABLE. Esta migración es aditiva y exclusivamente V004.

PROHIBICIÓN ABSOLUTA:
  - Cero columnas copiadas de datos personales (cédulas, nombres, sexo).
  - Cero columnas copiadas de metas de planificación (ParticipantGoals).
  - Cero columnas copiadas de cifras de ejecución (conteos reales).
  - La IA no puede crear ni revocar vínculos.
"""

from typing import List, Set

# ---------------------------------------------------------------------------
# ESQUEMA V004: TABLA DE TRAZABILIDAD planning_execution_links
# ---------------------------------------------------------------------------
V004_SCHEMA_DDL_STATEMENTS: List[str] = [
    # planning_execution_links — Entidad de trazabilidad institucional BICU.
    #
    # COLUMNAS:
    #   link_id                — UUID v4 técnico (PK). Generado en dominio.
    #   planning_internal_id   — FK a planning_planned_activities.activity_internal_id.
    #                            Identifica la actividad planificada vinculada.
    #   id_actividad           — FK a actividad.id_actividad (dominio ejecución).
    #                            Identifica la ejecución real vinculada.
    #   linked_by              — Actor humano institucional responsable del vínculo.
    #                            NUNCA puede ser un agente IA.
    #   linked_at              — Marca temporal ISO 8601 del momento de creación.
    #   link_rationale         — Justificación textual del vínculo (obligatoria).
    #   numero_sesion          — Número de sesión si la actividad es multi-sesión
    #                            (NULL si sesión única).
    #   link_status            — Estado del vínculo: ACTIVE | SUPERSEDED | REVOKED.
    #   revoked_by             — Actor humano que revocó (NULL si no revocado).
    #   revoked_at             — Marca temporal de revocación (NULL si no revocado).
    #   revocation_reason      — Motivo de revocación textual (NULL si no revocado).
    #
    # RESTRICCIONES:
    #   UNIQUE(planning_internal_id, id_actividad) — un solo vínculo por par.
    #   ON DELETE RESTRICT en ambas FK — protección patrimonial.
    """
    CREATE TABLE IF NOT EXISTS planning_execution_links (
        link_id TEXT PRIMARY KEY,
        planning_internal_id TEXT NOT NULL
            REFERENCES planning_planned_activities(activity_internal_id) ON DELETE RESTRICT,
        id_actividad TEXT NOT NULL
            REFERENCES actividad(id_actividad) ON DELETE RESTRICT,
        linked_by TEXT NOT NULL,
        linked_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        link_rationale TEXT NOT NULL,
        numero_sesion INTEGER,
        link_status TEXT NOT NULL DEFAULT 'ACTIVE'
            CHECK (link_status IN ('ACTIVE', 'SUPERSEDED', 'REVOKED')),
        revoked_by TEXT,
        revoked_at TEXT,
        revocation_reason TEXT,
        UNIQUE (planning_internal_id, id_actividad)
    );
    """,
]

# ---------------------------------------------------------------------------
# ÍNDICES B-TREE V004 — Justificados por patrones de consulta operativa
# ---------------------------------------------------------------------------
V004_INDEXES_DDL_STATEMENTS: List[str] = [
    # Búsqueda: "¿Qué ejecuciones tiene vinculadas esta actividad planificada?"
    "CREATE INDEX IF NOT EXISTS idx_pel_planning_id ON planning_execution_links(planning_internal_id);",
    # Búsqueda: "¿Con qué planificación está vinculada esta ejecución?"
    "CREATE INDEX IF NOT EXISTS idx_pel_id_actividad ON planning_execution_links(id_actividad);",
    # Filtrado operativo por estado del vínculo
    "CREATE INDEX IF NOT EXISTS idx_pel_link_status ON planning_execution_links(link_status);",
]

# Catálogo de tablas agregadas en V004 (para verificación en tests)
EXPECTED_V004_TABLE_NAMES: Set[str] = {
    "planning_execution_links",
}
