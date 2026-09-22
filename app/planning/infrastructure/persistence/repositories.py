"""Repositorios Concretos SQLite para el Módulo de Planificación.

Fase 29.4.2 — Implementación de Persistencia SQLite V003.
Implementa los puertos abstractos definidos en app/planning/domain/ports.py:
  - SQLitePlannedActivityRepository (PlannedActivityRepositoryPort)
  - SQLiteMethodologicalDesignRepository (MethodologicalDesignRepositoryPort)
  - SQLiteCatalogRepository (CatalogRepositoryPort)
"""

import sqlite3
from typing import Optional, Sequence
import uuid

from app.planning.domain.catalogs import (
    CATALOG_C1_EJES,
    CATALOG_C2_PROGRAMAS,
    CATALOG_C3_AMBITOS,
    CATALOG_C4_TIPOS_EVENTO,
    CATALOG_C5_TIPOS_PROYECTO,
    VALID_CATALOG_IDS,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity, PlanningExecutionLink
from app.planning.domain.ports import (
    CatalogRepositoryPort,
    MethodologicalDesignRepositoryPort,
    PlannedActivityRepositoryPort,
    PlanningExecutionLinkRepositoryPort,
)
from app.planning.domain.value_objects import CatalogReference, DesignStatus
from app.planning.infrastructure.persistence.mappers import (
    AIProposalMapper,
    FAQTableMapper,
    MethodologicalDesignMapper,
    OperationalActivityMapper,
    PlannedActivityMapper,
    PlanningExecutionLinkMapper,
    TimeBlockMapper,
)


class SQLitePlannedActivityRepository(PlannedActivityRepositoryPort):
    """Adaptador concreto SQLite para lectura y persistencia de PlannedActivity."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def get_by_internal_id(self, activity_internal_id: uuid.UUID) -> Optional[PlannedActivity]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM planning_planned_activities WHERE activity_internal_id = ?;",
                (str(activity_internal_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return PlannedActivityMapper.to_domain(row)
        finally:
            cursor.close()

    def get_by_planning_id(self, planning_id: str) -> Optional[PlannedActivity]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM planning_planned_activities WHERE planning_id = ?;",
                (planning_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return PlannedActivityMapper.to_domain(row)
        finally:
            cursor.close()

    def list_all(self) -> Sequence[PlannedActivity]:
        cursor = self._conn.cursor()
        try:
            cursor.execute("SELECT * FROM planning_planned_activities ORDER BY activity_name ASC;")
            rows = cursor.fetchall()
            return [PlannedActivityMapper.to_domain(r) for r in rows]
        finally:
            cursor.close()

    def save(self, activity: PlannedActivity) -> None:
        """Inserta o actualiza una actividad planificada en SQLite."""
        row_dict = PlannedActivityMapper.to_row(activity)
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO planning_planned_activities (
                    activity_internal_id, planning_id, activity_name, sede, area_responsable,
                    eje_estrategia, programa, tipo_evento, dep_sede, mun_sede, otro_programa,
                    proyecto, tipo_proyecto, ambito, codigo_presupuestario, departamento_responsable,
                    proposito, fecha_evento, convenio, entidades_cooperantes,
                    est_grado_m, est_grado_f, est_postgrado_m, est_postgrado_f,
                    docentes_m, docentes_f, administrativos_m, administrativos_f,
                    externos_m, externos_f
                ) VALUES (
                    :activity_internal_id, :planning_id, :activity_name, :sede, :area_responsable,
                    :eje_estrategia, :programa, :tipo_evento, :dep_sede, :mun_sede, :otro_programa,
                    :proyecto, :tipo_proyecto, :ambito, :codigo_presupuestario, :departamento_responsable,
                    :proposito, :fecha_evento, :convenio, :entidades_cooperantes,
                    :est_grado_m, :est_grado_f, :est_postgrado_m, :est_postgrado_f,
                    :docentes_m, :docentes_f, :administrativos_m, :administrativos_f,
                    :externos_m, :externos_f
                )
                ON CONFLICT(activity_internal_id) DO UPDATE SET
                    planning_id = excluded.planning_id,
                    activity_name = excluded.activity_name,
                    sede = excluded.sede,
                    area_responsable = excluded.area_responsable,
                    eje_estrategia = excluded.eje_estrategia,
                    programa = excluded.programa,
                    tipo_evento = excluded.tipo_evento,
                    dep_sede = excluded.dep_sede,
                    mun_sede = excluded.mun_sede,
                    otro_programa = excluded.otro_programa,
                    proyecto = excluded.proyecto,
                    tipo_proyecto = excluded.tipo_proyecto,
                    ambito = excluded.ambito,
                    codigo_presupuestario = excluded.codigo_presupuestario,
                    departamento_responsable = excluded.departamento_responsable,
                    proposito = excluded.proposito,
                    fecha_evento = excluded.fecha_evento,
                    convenio = excluded.convenio,
                    entidades_cooperantes = excluded.entidades_cooperantes,
                    est_grado_m = excluded.est_grado_m,
                    est_grado_f = excluded.est_grado_f,
                    est_postgrado_m = excluded.est_postgrado_m,
                    est_postgrado_f = excluded.est_postgrado_f,
                    docentes_m = excluded.docentes_m,
                    docentes_f = excluded.docentes_f,
                    administrativos_m = excluded.administrativos_m,
                    administrativos_f = excluded.administrativos_f,
                    externos_m = excluded.externos_m,
                    externos_f = excluded.externos_f;
                """,
                row_dict,
            )
        finally:
            cursor.close()


class SQLiteMethodologicalDesignRepository(MethodologicalDesignRepositoryPort):
    """Adaptador concreto SQLite para persistencia y consulta de MethodologicalDesign."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def get_by_id(self, design_id: uuid.UUID) -> Optional[MethodologicalDesign]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM planning_methodological_designs WHERE design_id = ?;",
                (str(design_id),),
            )
            design_row = cursor.fetchone()
            if not design_row:
                return None

            cursor.execute(
                "SELECT * FROM planning_design_faqs WHERE design_id = ?;",
                (str(design_id),),
            )
            faq_row = cursor.fetchone()

            cursor.execute(
                "SELECT * FROM planning_design_agenda WHERE design_id = ? ORDER BY sequence ASC;",
                (str(design_id),),
            )
            agenda_rows = cursor.fetchall()

            cursor.execute(
                "SELECT * FROM planning_design_operational_matrix WHERE design_id = ? ORDER BY step_number ASC;",
                (str(design_id),),
            )
            matrix_rows = cursor.fetchall()

            cursor.execute(
                "SELECT * FROM planning_ai_proposals WHERE design_id = ? ORDER BY created_at ASC;",
                (str(design_id),),
            )
            proposal_rows = cursor.fetchall()

            return MethodologicalDesignMapper.to_domain(
                row=design_row,
                faq_row=faq_row,
                agenda_rows=agenda_rows,
                matrix_rows=matrix_rows,
                proposal_rows=proposal_rows,
            )
        finally:
            cursor.close()

    def get_by_activity_id(self, activity_internal_id: uuid.UUID) -> Sequence[MethodologicalDesign]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT design_id FROM planning_methodological_designs WHERE planned_activity_internal_id = ?;",
                (str(activity_internal_id),),
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = self.get_by_id(uuid.UUID(str(r["design_id"])))
                if d:
                    results.append(d)
            return results
        finally:
            cursor.close()

    def get_by_activity_ref(self, planned_activity_ref: str) -> Optional[MethodologicalDesign]:
        """Obtiene el diseño metodológico vigente asociado a una referencia institucional."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT design_id FROM planning_methodological_designs WHERE planned_activity_ref = ?;",
                (planned_activity_ref,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self.get_by_id(uuid.UUID(str(row["design_id"])))
        finally:
            cursor.close()

    def save(self, design: MethodologicalDesign) -> None:
        """Persiste un diseño metodológico aplicando las reglas R-08 y D-02.

        Reglas:
          1. Si existe y su estado actual en base de datos es APPROVED -> RECHAZAR modificación (R-08).
          2. Si existe y es editable -> ACTUALIZAR in-place (D-02).
          3. Si no existe -> INSERTAR.
          4. Respeta UNIQUE(planned_activity_ref) y FOREIGN KEY hacia planning_planned_activities.
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT status, planned_activity_ref FROM planning_methodological_designs WHERE design_id = ?;",
                (str(design.design_id),),
            )
            existing = cursor.fetchone()

            if existing:
                existing_status = str(existing["status"])
                if existing_status == DesignStatus.APPROVED.value:
                    raise RuntimeError(
                        "No se puede modificar un diseño metodológico en estado APPROVED "
                        "(Regla R-08 de inmutabilidad institucional)."
                    )

                # Actualización in-place del diseño
                row_dict = MethodologicalDesignMapper.to_row(design)
                cursor.execute(
                    """
                    UPDATE planning_methodological_designs SET
                        planned_activity_internal_id = :planned_activity_internal_id,
                        planned_activity_ref = :planned_activity_ref,
                        activity_name = :activity_name,
                        version = :version,
                        status = :status,
                        introduction_text = :introduction_text,
                        methodological_approach = :methodological_approach,
                        objective_1 = :objective_1,
                        objective_2 = :objective_2,
                        created_by = :created_by,
                        created_at = :created_at,
                        approved_by = :approved_by,
                        approved_at = :approved_at,
                        document_hash = :document_hash,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE design_id = :design_id;
                    """,
                    row_dict,
                )

                # Reemplazo de componentes hijos
                cursor.execute("DELETE FROM planning_design_faqs WHERE design_id = ?;", (str(design.design_id),))
                cursor.execute("DELETE FROM planning_design_agenda WHERE design_id = ?;", (str(design.design_id),))
                cursor.execute("DELETE FROM planning_design_operational_matrix WHERE design_id = ?;", (str(design.design_id),))
                cursor.execute("DELETE FROM planning_ai_proposals WHERE design_id = ?;", (str(design.design_id),))
            else:
                # Inserción inicial
                row_dict = MethodologicalDesignMapper.to_row(design)
                cursor.execute(
                    """
                    INSERT INTO planning_methodological_designs (
                        design_id, planned_activity_internal_id, planned_activity_ref,
                        activity_name, version, status, introduction_text,
                        methodological_approach, objective_1, objective_2,
                        created_by, created_at, approved_by, approved_at, document_hash
                    ) VALUES (
                        :design_id, :planned_activity_internal_id, :planned_activity_ref,
                        :activity_name, :version, :status, :introduction_text,
                        :methodological_approach, :objective_1, :objective_2,
                        :created_by, :created_at, :approved_by, :approved_at, :document_hash
                    );
                    """,
                    row_dict,
                )

            # Insertar componentes hijos
            if design.faq_table:
                faq_dict = FAQTableMapper.to_row(design.faq_table, design.design_id)
                cursor.execute(
                    """
                    INSERT INTO planning_design_faqs (
                        design_id, q1_que_es, q2_para_que, q3_sesiones,
                        q4_protagonistas, q5_facilitador, q6_materiales, q7_duracion
                    ) VALUES (
                        :design_id, :q1_que_es, :q2_para_que, :q3_sesiones,
                        :q4_protagonistas, :q5_facilitador, :q6_materiales, :q7_duracion
                    );
                    """,
                    faq_dict,
                )

            for tb in design.agenda:
                tb_dict = TimeBlockMapper.to_row(tb, design.design_id)
                cursor.execute(
                    """
                    INSERT INTO planning_design_agenda (
                        agenda_id, design_id, sequence, label, minutes
                    ) VALUES (
                        :agenda_id, :design_id, :sequence, :label, :minutes
                    );
                    """,
                    tb_dict,
                )

            for op in design.operational_matrix:
                op_dict = OperationalActivityMapper.to_row(op, design.design_id)
                cursor.execute(
                    """
                    INSERT INTO planning_design_operational_matrix (
                        operational_id, design_id, step_number, phase_label,
                        operative_goal, procedure, materials, minutes
                    ) VALUES (
                        :operational_id, :design_id, :step_number, :phase_label,
                        :operative_goal, :procedure, :materials, :minutes
                    );
                    """,
                    op_dict,
                )

            for prop in design.ai_proposals:
                prop_dict = AIProposalMapper.to_row(prop, design.design_id)
                cursor.execute(
                    """
                    INSERT INTO planning_ai_proposals (
                        proposal_id, design_id, target_field, proposed_content,
                        source_inputs, confidence, requires_review, accepted,
                        reviewed_by, review_timestamp, rejection_reason
                    ) VALUES (
                        :proposal_id, :design_id, :target_field, :proposed_content,
                        :source_inputs, :confidence, :requires_review, :accepted,
                        :reviewed_by, :review_timestamp, :rejection_reason
                    );
                    """,
                    prop_dict,
                )
        finally:
            cursor.close()


class SQLiteCatalogRepository(CatalogRepositoryPort):
    """Adaptador concreto para consulta de catálogos institucionales C1 a C5."""

    _CATALOG_MAP = {
        "C1": ("C1", CATALOG_C1_EJES),
        "C1_EJE": ("C1", CATALOG_C1_EJES),
        "C2": ("C2", CATALOG_C2_PROGRAMAS),
        "C2_PROGRAMA": ("C2", CATALOG_C2_PROGRAMAS),
        "C3": ("C3", CATALOG_C3_AMBITOS),
        "C3_AMBITO": ("C3", CATALOG_C3_AMBITOS),
        "C4": ("C4", CATALOG_C4_TIPOS_EVENTO),
        "C4_TIPO_EVENTO": ("C4", CATALOG_C4_TIPOS_EVENTO),
        "C5": ("C5", CATALOG_C5_TIPOS_PROYECTO),
        "C5_TIPO_PROYECTO": ("C5", CATALOG_C5_TIPOS_PROYECTO),
    }

    def get_catalog_entries(self, catalog_name: str) -> Sequence[CatalogReference]:
        key = catalog_name.upper().strip()
        if key not in self._CATALOG_MAP:
            raise ValueError(f"Catálogo desconocido '{catalog_name}'. Válidos: {list(self._CATALOG_MAP.keys())}")
        cat_id, mapping = self._CATALOG_MAP[key]
        return [
            CatalogReference(catalog_id=cat_id, code=code, label=label, source="POA BICU")
            for code, label in mapping.items()
        ]

    def is_valid_code(self, catalog_name: str, code: str) -> bool:
        key = catalog_name.upper().strip()
        if key not in self._CATALOG_MAP:
            return False
        _, mapping = self._CATALOG_MAP[key]
        return code.strip() in mapping


class SQLitePlanningExecutionLinkRepository(PlanningExecutionLinkRepositoryPort):
    """Adaptador concreto SQLite para PlanningExecutionLink.

    Fase 29.18.1 — Trazabilidad Planificación ↔ Ejecución.
    PRINCIPIO: Solo persiste/consulta el vínculo. Jamas accede a datos de ejecución.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def save(self, link: PlanningExecutionLink) -> None:
        """Persiste un v\u00ednculo: actualiza si el link_id ya existe, inserta si es nuevo.

        Patr\u00f3n UPDATE-then-INSERT:
          - Mismo link_id (actualizaci\u00f3n de estado, p.ej. revocaci\u00f3n) \u2192 UPDATE.
          - Nuevo link_id con par ya vinculado \u2192 INSERT falla con IntegrityError.
            Esto preserva la invariante UNIQUE(planning_internal_id, id_actividad).

        La IA no puede invocar este m\u00e9todo (R-09 extendido de Fase 29.18.1).
        """
        row = PlanningExecutionLinkMapper.to_row(link)
        cursor = self._conn.cursor()
        try:
            # Intenta actualizar un v\u00ednculo existente por link_id
            cursor.execute(
                """
                UPDATE planning_execution_links SET
                    link_status      = :link_status,
                    revoked_by       = :revoked_by,
                    revoked_at       = :revoked_at,
                    revocation_reason = :revocation_reason
                WHERE link_id = :link_id;
                """,
                row,
            )
            if cursor.rowcount == 0:
                # No exist\u00eda: INSERT nuevo (lanza IntegrityError si el par ya existe)
                cursor.execute(
                    """
                    INSERT INTO planning_execution_links (
                        link_id, planning_internal_id, id_actividad,
                        linked_by, linked_at, link_rationale,
                        numero_sesion, link_status,
                        revoked_by, revoked_at, revocation_reason
                    ) VALUES (
                        :link_id, :planning_internal_id, :id_actividad,
                        :linked_by, :linked_at, :link_rationale,
                        :numero_sesion, :link_status,
                        :revoked_by, :revoked_at, :revocation_reason
                    );
                    """,
                    row,
                )
        finally:
            cursor.close()

    def get_by_id(self, link_id: uuid.UUID) -> Optional[PlanningExecutionLink]:
        """Obtiene un vínculo por su UUID técnico."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM planning_execution_links WHERE link_id = ?;",
                (str(link_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return PlanningExecutionLinkMapper.to_domain(row)
        finally:
            cursor.close()

    def get_by_planning_id(
        self, planning_internal_id: uuid.UUID
    ) -> Sequence[PlanningExecutionLink]:
        """Obtiene todos los vínculos de una actividad planificada (cualquier estado)."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM planning_execution_links "
                "WHERE planning_internal_id = ? ORDER BY linked_at DESC;",
                (str(planning_internal_id),),
            )
            rows = cursor.fetchall()
            return [PlanningExecutionLinkMapper.to_domain(r) for r in rows]
        finally:
            cursor.close()

    def get_by_actividad_id(self, id_actividad: str) -> Sequence[PlanningExecutionLink]:
        """Obtiene todos los vínculos de una actividad ejecutada (cualquier estado)."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM planning_execution_links "
                "WHERE id_actividad = ? ORDER BY linked_at DESC;",
                (id_actividad,),
            )
            rows = cursor.fetchall()
            return [PlanningExecutionLinkMapper.to_domain(r) for r in rows]
        finally:
            cursor.close()

    def get_active_by_planning_id(
        self, planning_internal_id: uuid.UUID
    ) -> Optional[PlanningExecutionLink]:
        """Obtiene el vínculo ACTIVE de una actividad planificada (None si no existe)."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM planning_execution_links "
                "WHERE planning_internal_id = ? AND link_status = 'ACTIVE' "
                "ORDER BY linked_at DESC LIMIT 1;",
                (str(planning_internal_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return PlanningExecutionLinkMapper.to_domain(row)
        finally:
            cursor.close()
