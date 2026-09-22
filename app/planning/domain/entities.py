"""
Aggregate Roots del Dominio — Modulo Planificacion -> Diseno Metodologico.

Fuente arquitectonica:
  FASE_29_2_DISENO_ARQUITECTONICO_PLANIFICACION_DISENO.md §8, §10, §11
  FASE_29_2_1_CIERRE_DECISIONES_INSTITUCIONALES.md §7, §8, §21

Fase 29.3 — Dominio Puro
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from app.planning.domain.value_objects import (
    AIProposal,
    CatalogReference,
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)


# ---------------------------------------------------------------------------
# PlannedActivity — Aggregate Root
# Fuente: FASE_29_2 §8 (PlannedActivity), §11 (PlannedActivityDTO)
# Clasificacion: EVIDENCIA DIRECTA para los campos obligatorios.
#                DECISION ARQUITECTONICA para activity_internal_id.
#
# IDENTIDAD (D-04):
#   activity_internal_id = UUID tecnico interno.
#     - Generado automaticamente al crear PlannedActivity.
#     - NO es el codigo institucional visible al usuario.
#     - NO debe aparecer en el DOCX como identificador oficial.
#     - NO hardcodear formato ACT-AÑO-SEDE-SECUENCIAL.
#   planning_id = str RESERVADO para el ID institucional que BICU confirme.
#     - En v1 puede ser el nombre de actividad o un texto provisional.
#     - No se asume formato. No se inventa formato.
# ---------------------------------------------------------------------------
@dataclass
class PlannedActivity:
    """Actividad planificada en el POA institucional.

    Clasificacion: EVIDENCIA DIRECTA (campos obligatorios de matrices POA reales).
    Fuente: FASE_29_2 §8, §11 (PlannedActivityDTO).

    IDENTIDAD (D-04):
        activity_internal_id: UUID tecnico — DECISION ARQUITECTONICA.
        planning_id:          ID institucional — PENDIENTE DE VALIDACION BICU.

    El dominio no modifica los datos institucionales.
    La IA JAMAS puede modificar los campos de esta entidad (R-09).

    Atributos obligatorios (EVIDENCIA DIRECTA):
        activity_name, sede, programa, eje_estrategia, area_responsable,
        tipo_evento, participant_goals.
    """
    # --- IDENTIDAD ---
    activity_internal_id: uuid.UUID    # UUID tecnico — DECISION ARQUITECTONICA (D-04)
    planning_id: str                   # ID institucional — PENDIENTE BICU (D-04)

    # --- NOMBRE Y DATOS OBLIGATORIOS (EVIDENCIA DIRECTA) ---
    activity_name: str                 # Nombre de la actividad — OBLIGATORIO
    sede: str                          # Sede — OBLIGATORIO
    area_responsable: str              # Area/coordinacion facilitadora — OBLIGATORIO
    eje_estrategia: str                # Codigo eje en C1 — OBLIGATORIO
    programa: str                      # Codigo programa en C2 — OBLIGATORIO
    tipo_evento: str                   # Codigo tipo evento en C4 — OBLIGATORIO
    participant_goals: ParticipantGoals  # Metas de protagonistas — OBLIGATORIO

    # --- GEOGRAFICO (EVIDENCIA DIRECTA) ---
    dep_sede: str = ""                 # Departamento de la sede
    mun_sede: str = ""                 # Municipio de la sede

    # --- PROGRAMATICO (EVIDENCIA DIRECTA) ---
    otro_programa: Optional[str] = None
    proyecto: Optional[str] = None
    tipo_proyecto: Optional[str] = None    # Codigo C5 si aplica
    ambito: Optional[str] = None           # Codigo C3 si aplica
    codigo_presupuestario: Optional[str] = None
    departamento_responsable: Optional[str] = None

    # --- OPERATIVO ---
    proposito: Optional[str] = None
    fecha_evento: Optional[date] = None

    # --- ALIANZAS (opcionales) ---
    convenio: Optional[str] = None
    entidades_cooperantes: Optional[str] = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Valida invariantes de la entidad."""
        required_str = {
            "activity_name": self.activity_name,
            "sede": self.sede,
            "area_responsable": self.area_responsable,
            "eje_estrategia": self.eje_estrategia,
            "programa": self.programa,
            "tipo_evento": self.tipo_evento,
            "planning_id": self.planning_id,
        }
        for fname, fval in required_str.items():
            if not fval or not str(fval).strip():
                raise ValueError(f"PlannedActivity.{fname} es obligatorio y no puede ser vacio.")

        if not isinstance(self.participant_goals, ParticipantGoals):
            raise ValueError(
                "PlannedActivity.participant_goals debe ser instancia de ParticipantGoals."
            )
        if not isinstance(self.activity_internal_id, uuid.UUID):
            raise ValueError(
                "PlannedActivity.activity_internal_id debe ser instancia de uuid.UUID."
            )

    @classmethod
    def create(
        cls,
        planning_id: str,
        activity_name: str,
        sede: str,
        area_responsable: str,
        eje_estrategia: str,
        programa: str,
        tipo_evento: str,
        participant_goals: ParticipantGoals,
        **kwargs,
    ) -> "PlannedActivity":
        """Factory — genera el UUID tecnico interno automaticamente.

        El activity_internal_id se genera como UUID v4.
        No es visible por defecto al usuario ni se escribe en DOCX como ID oficial.
        """
        return cls(
            activity_internal_id=uuid.uuid4(),
            planning_id=planning_id,
            activity_name=activity_name,
            sede=sede,
            area_responsable=area_responsable,
            eje_estrategia=eje_estrategia,
            programa=programa,
            tipo_evento=tipo_evento,
            participant_goals=participant_goals,
            **kwargs,
        )

    @property
    def internal_id(self) -> uuid.UUID:
        """Alias para activity_internal_id."""
        return self.activity_internal_id

    def to_dto(self) -> PlannedActivityDTO:
        """Convierte la entidad a un PlannedActivityDTO inmutable."""
        from app.planning.domain.dtos import PlannedActivityDTO
        return PlannedActivityDTO(
            activity_internal_id=self.activity_internal_id,
            planning_id=self.planning_id,
            activity_name=self.activity_name,
            sede=self.sede,
            dep_sede=self.dep_sede,
            mun_sede=self.mun_sede,
            programa=self.programa,
            otro_programa=self.otro_programa,
            proyecto=self.proyecto,
            tipo_proyecto=self.tipo_proyecto,
            ambito=self.ambito,
            eje_estrategia=self.eje_estrategia,
            codigo_presupuestario=self.codigo_presupuestario,
            area_responsable=self.area_responsable,
            departamento_responsable=self.departamento_responsable,
            tipo_evento=self.tipo_evento,
            proposito=self.proposito,
            fecha_evento=self.fecha_evento,
            participant_goals=self.participant_goals,
            convenio=self.convenio,
            entidades_cooperantes=self.entidades_cooperantes,
        )


# ---------------------------------------------------------------------------
# MethodologicalDesign — Aggregate Root
# Fuente: FASE_29_2 §8 (MethodologicalDesign), §9 (cardinalidad)
# Clasificacion: EVIDENCIA DIRECTA (5 bloques invariantes verificados en 5/5 docs).
#                DECISION ARQUITECTONICA (versionado, ciclo de vida).
#
# Cardinalidad:
#   PlannedActivity (1) ---- (0..N) MethodologicalDesign
#   CONSTRAINT: maximo 1 MethodologicalDesign en APPROVED para cada actividad.
# ---------------------------------------------------------------------------
@dataclass
class MethodologicalDesign:
    """Diseno Metodologico asociado a una PlannedActivity.

    Clasificacion: EVIDENCIA DIRECTA (estructura de 5 bloques, 2 objetivos, R-05, R-06).
    Fuente: FASE_29_2 §8 (MethodologicalDesign), E-01, E-02.

    Estructura de 5 Bloques (EVIDENCIA DIRECTA — 5/5 documentos):
        Bloque 1: Introduccion + Enfoque Metodologico
        Bloque 2: Objetivos (exactamente 2 — R-07)
        Bloque 3: FAQTable (7 preguntas fijas — Tabla 1)
        Bloque 4: Agenda / Programa (Tabla 2)
        Bloque 5: Matriz Operacional (Tabla 3)

    Invariantes matematicos (EVIDENCIA DIRECTA):
        total_minutes == Σ(agenda[i].minutes)  [R-05]
        matrix[i].minutes == agenda[i].minutes  ∀i  [R-06]
        len(objectives) == 2  [R-07]

    Ciclo de vida (DECISION ARQUITECTONICA, D-03 pendiente):
        DRAFT -> GENERATED -> REVIEW -> APPROVED
                                     -> REJECTED -> DRAFT (nueva iteracion)

    AUDITORIA:
        created_by, created_at, approved_by, approved_at, document_hash.
    """
    # --- IDENTIDAD (DECISION ARQUITECTONICA) ---
    design_id: uuid.UUID
    planned_activity_ref: str          # Referencia al planning_id de PlannedActivity
    version: int                       # Version tecnica (inicia en 1)
    status: DesignStatus
    planned_activity_internal_id: Optional[uuid.UUID] = None
    activity_name: str = ""

    # --- AUDITORIA (DECISION ARQUITECTONICA) ---
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    document_hash: Optional[str] = None  # SHA-256 del DOCX cuando se genere

    # --- BLOQUE 1: INTRODUCCION (EVIDENCIA DIRECTA) ---
    introduction_text: str = ""
    methodological_approach: str = ""

    # --- BLOQUE 2: OBJETIVOS (EVIDENCIA DIRECTA — R-07: exactamente 2) ---
    objectives: list[str] = field(default_factory=list)

    # --- BLOQUE 3: FAQ (EVIDENCIA DIRECTA — 7 preguntas fijas) ---
    faq_table: Optional[FAQTable] = None

    # --- BLOQUE 4: AGENDA — Tabla 2 (EVIDENCIA DIRECTA — R-05) ---
    agenda: list[TimeBlock] = field(default_factory=list)

    # --- BLOQUE 5: MATRIZ OPERACIONAL — Tabla 3 (EVIDENCIA DIRECTA — R-06) ---
    operational_matrix: list[OperationalActivity] = field(default_factory=list)

    # --- PROPUESTAS IA (DECISION ARQUITECTONICA) ---
    ai_proposals: list[AIProposal] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate_identity()

    def _validate_identity(self) -> None:
        """Valida invariantes de identidad que deben cumplirse siempre."""
        if not isinstance(self.design_id, uuid.UUID):
            raise ValueError("MethodologicalDesign.design_id debe ser instancia de uuid.UUID.")
        if not self.planned_activity_ref or not self.planned_activity_ref.strip():
            raise ValueError("MethodologicalDesign.planned_activity_ref es obligatorio.")
        if not isinstance(self.version, int) or self.version < 1:
            raise ValueError(
                f"MethodologicalDesign.version debe ser entero >= 1. Valor: {self.version!r}"
            )
        if not isinstance(self.status, DesignStatus):
            raise ValueError("MethodologicalDesign.status debe ser instancia de DesignStatus.")
        if not self.created_by or not self.created_by.strip():
            raise ValueError("MethodologicalDesign.created_by es obligatorio.")
        if not isinstance(self.created_at, datetime):
            raise ValueError("MethodologicalDesign.created_at debe ser instancia de datetime.")

    @property
    def total_minutes(self) -> int:
        """Suma total de minutos de la agenda.

        Clasificacion: REGLA MATEMATICA — EVIDENCIA DIRECTA (R-05).
        Calculado automaticamente por el dominio. NO ingresado por el usuario.
        """
        return sum(tb.minutes for tb in self.agenda)

    @property
    def is_exportable(self) -> bool:
        """True si el diseno puede ser validado para exportar.

        El diseno debe estar en DRAFT, GENERATED, REVIEW (no REJECTED) y
        pasar las validaciones V-MD-01 a V-MD-12 para exportarse.
        Esta propiedad solo indica que el status no es REJECTED.
        """
        return self.status != DesignStatus.REJECTED

    @property
    def has_pending_ai_proposals(self) -> bool:
        """True si hay propuestas IA sin revision (accepted=None).

        Relacionado con V-MD-10: Ningun campo exportable puede tener
        propuesta IA pendiente de revision.
        """
        return any(p.is_pending_review for p in self.ai_proposals)

    def add_time_block(self, block: TimeBlock) -> None:
        """Agrega un bloque de tiempo a la agenda.

        El total_minutes se recalcula automaticamente (propiedad derivada).
        """
        if not isinstance(block, TimeBlock):
            raise TypeError("Solo se pueden agregar instancias de TimeBlock.")
        self.agenda.append(block)

    def add_operational_activity(self, activity: OperationalActivity) -> None:
        """Agrega una actividad a la matriz operacional."""
        if not isinstance(activity, OperationalActivity):
            raise TypeError("Solo se pueden agregar instancias de OperationalActivity.")
        self.operational_matrix.append(activity)

    def add_ai_proposal(self, proposal: AIProposal) -> None:
        """Registra una propuesta de IA para auditoria."""
        if not isinstance(proposal, AIProposal):
            raise TypeError("Solo se pueden agregar instancias de AIProposal.")
        self.ai_proposals.append(proposal)

    @classmethod
    def create_draft(
        cls,
        planned_activity_ref: str,
        created_by: str,
        created_at: Optional[datetime] = None,
    ) -> "MethodologicalDesign":
        """Factory — crea un nuevo diseno en estado DRAFT.

        Genera design_id como UUID v4.
        Version inicial = 1.
        """
        return cls(
            design_id=uuid.uuid4(),
            planned_activity_ref=planned_activity_ref,
            version=1,
            status=DesignStatus.DRAFT,
            created_by=created_by,
            created_at=created_at or datetime.now(),
        )

    @property
    def document_title(self) -> str:
        """R-01: 'Diseño metodológico ' + activity_name."""
        from app.planning.domain.rules_engine import InstitutionalRulesEngine
        name = self.activity_name or self.planned_activity_ref
        return InstitutionalRulesEngine.derive_document_title(name)

    @property
    def introduction(self) -> str:
        return self.introduction_text

    @introduction.setter
    def introduction(self, val: str) -> None:
        self.introduction_text = val

    @property
    def objective_1(self) -> str:
        return self.objectives[0] if len(self.objectives) > 0 else ""

    @property
    def objective_2(self) -> str:
        return self.objectives[1] if len(self.objectives) > 1 else ""

    @property
    def faq(self) -> Optional[FAQTable]:
        return self.faq_table

    def mark_generated(self) -> None:
        """Marca el diseno como GENERATED tras crear o renderizar."""
        if self.status == DesignStatus.APPROVED:
            raise RuntimeError("No se puede modificar un diseno en estado APPROVED.")
        self.status = DesignStatus.GENERATED

    def approve(self, approved_by: str) -> None:
        """Marca el diseno como APPROVED."""
        if not approved_by or not approved_by.strip():
            raise ValueError("approved_by no puede estar vacio.")
        self.status = DesignStatus.APPROVED
        self.approved_by = approved_by.strip()
        self.approved_at = datetime.now()

    @classmethod
    def create(
        cls,
        planned_activity_internal_id: uuid.UUID,
        planning_id: str,
        activity_name: str,
        introduction: str,
        methodological_approach: str,
        objective_1: str,
        objective_2: str,
        faq: FAQTable,
        agenda: Sequence[TimeBlock],
        operational_matrix: Sequence[OperationalActivity],
        created_by: str,
        version: int = 1,
        status: DesignStatus = DesignStatus.DRAFT,
    ) -> "MethodologicalDesign":
        """Factory de conveniencia para instanciar diseno con todos los 5 bloques."""
        if not objective_1 or not objective_1.strip():
            raise ValueError("objective_1 no puede estar vacio.")
        if not objective_2 or not objective_2.strip():
            raise ValueError("objective_2 no puede estar vacio.")
        if len(agenda) != len(operational_matrix):
            raise ValueError("R-06: agenda y operational_matrix deben tener la misma cantidad de elementos.")
        return cls(
            design_id=uuid.uuid4(),
            planned_activity_internal_id=planned_activity_internal_id,
            planned_activity_ref=planning_id,
            activity_name=activity_name,
            version=version,
            status=status,
            created_by=created_by,
            created_at=datetime.now(),
            introduction_text=introduction,
            methodological_approach=methodological_approach,
            objectives=[objective_1.strip(), objective_2.strip()],
            faq_table=faq,
            agenda=list(agenda),
            operational_matrix=list(operational_matrix),
        )

    def to_dto(
        self,
        objectives_heading: str = "OBJETIVOS DEL TALLER ARTÍSTICO",
        program_section_label: str = "III. PROGRAMA",
        matrix_section_label: str = "VI. MATRIZ DE PLANIFICACIÓN",
    ) -> MethodologicalDesignDTO:
        """Exporta el diseno validado a un MethodologicalDesignDTO inmutable."""
        from app.planning.domain.dtos import (
            FAQTableDTO,
            MethodologicalDesignDTO,
            OperationalActivityDTO,
            TimeBlockDTO,
        )
        faq_dto = FAQTableDTO(
            q1_que_es=self.faq_table.q1_que_es,
            q2_para_que=self.faq_table.q2_para_que,
            q3_sesiones=self.faq_table.q3_sesiones,
            q4_protagonistas=self.faq_table.q4_protagonistas,
            q5_facilitador=self.faq_table.q5_facilitador,
            q6_materiales=self.faq_table.q6_materiales,
            q7_duracion=self.faq_table.q7_duracion,
        ) if self.faq_table else None

        agenda_dtos = tuple(
            TimeBlockDTO(sequence=tb.sequence, label=tb.label, minutes=tb.minutes)
            for tb in self.agenda
        )
        matrix_dtos = tuple(
            OperationalActivityDTO(
                step_number=oa.step_number,
                phase_label=oa.phase_label,
                operative_goal=oa.operative_goal,
                procedure=oa.procedure,
                materials=oa.materials,
                minutes=oa.minutes,
            )
            for oa in self.operational_matrix
        )

        return MethodologicalDesignDTO(
            design_id=self.design_id,
            version=self.version,
            created_at=self.created_at,
            created_by=self.created_by,
            approved_by=self.approved_by,
            document_title=self.document_title,
            introduction=self.introduction_text,
            methodological_approach=self.methodological_approach,
            objectives_heading=objectives_heading,
            objective_1=self.objective_1,
            objective_2=self.objective_2,
            faq=faq_dto,
            program_section_label=program_section_label,
            agenda=agenda_dtos,
            total_minutes=self.total_minutes,
            matrix_section_label=matrix_section_label,
            operational_matrix=matrix_dtos,
        )


# ---------------------------------------------------------------------------
# PlanningExecutionLink — Entidad de Trazabilidad Planificación ↔ Ejecución
#
# Fase 29.18.1 — PRINCIPIO RECTOR: PLANIFICADO ≠ EJECUTADO.
#
# Esta entidad es el ÚNICO punto institucional que referencia a la vez:
#   - planning_internal_id (UUID del dominio de planificación)
#   - id_actividad (clave del dominio de ejecución)
#
# PROHIBICIÓN ABSOLUTA: No copia datos personales, metas, fechas ni cifras.
# Solo registra la voluntad institucional auditada del vínculo.
# La IA JAMÁS puede crear, modificar ni revocar vínculos (R-09 extendido).
# ---------------------------------------------------------------------------
@dataclass
class PlanningExecutionLink:
    """Entidad de trazabilidad institucional entre planificación y ejecución.

    Principio Rector: PLANIFICADO ≠ EJECUTADO.
    Esta entidad NO copia datos entre dominios. Solo registra:
      - El par (planning_internal_id, id_actividad) vinculado.
      - Quién lo vinculó (linked_by), cuándo (linked_at) y por qué (link_rationale).
      - El ciclo de vida del vínculo (link_status, revocation fields).

    Atributos:
        link_id: UUID v4 técnico del vínculo. Inmutable tras creación.
        planning_internal_id: UUID de PlannedActivity en el dominio de planificación.
        id_actividad: Clave de actividad en el dominio de ejecución (solo referencia).
        linked_by: Actor humano institucional responsable. NUNCA un agente IA.
        linked_at: Marca temporal de creación del vínculo.
        link_rationale: Justificación textual del vínculo (obligatoria).
        numero_sesion: Número de sesión para actividades multi-sesión (None = única).
        link_status: Estado del vínculo. Valores: 'ACTIVE', 'SUPERSEDED', 'REVOKED'.
        revoked_by: Actor humano que revocó (None si no revocado).
        revoked_at: Marca temporal de revocación (None si no revocado).
        revocation_reason: Motivo de revocación (None si no revocado).
    """

    # --- IDENTIDAD (inmutable tras creación) ---
    link_id: uuid.UUID
    planning_internal_id: uuid.UUID
    id_actividad: str  # Referencia al dominio de ejecución — solo identificador

    # --- AUDITORÍA DE AUTORÍA (obligatoria) ---
    linked_by: str
    linked_at: datetime
    link_rationale: str

    # --- MULTI-SESIÓN (opcional) ---
    numero_sesion: Optional[int] = None

    # --- CICLO DE VIDA ---
    link_status: str = "ACTIVE"

    # --- REVOCACIÓN (solo si link_status = 'REVOKED') ---
    revoked_by: Optional[str] = None
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Valida invariantes de la entidad PlanningExecutionLink."""
        if not isinstance(self.link_id, uuid.UUID):
            raise ValueError("PlanningExecutionLink.link_id debe ser instancia de uuid.UUID.")
        if not isinstance(self.planning_internal_id, uuid.UUID):
            raise ValueError(
                "PlanningExecutionLink.planning_internal_id debe ser instancia de uuid.UUID."
            )
        if not self.id_actividad or not str(self.id_actividad).strip():
            raise ValueError("PlanningExecutionLink.id_actividad es obligatorio y no puede ser vacío.")
        if not self.linked_by or not str(self.linked_by).strip():
            raise ValueError("PlanningExecutionLink.linked_by es obligatorio y no puede ser vacío.")
        if not self.link_rationale or not str(self.link_rationale).strip():
            raise ValueError(
                "PlanningExecutionLink.link_rationale es obligatorio y no puede ser vacío."
            )
        valid_statuses = {"ACTIVE", "SUPERSEDED", "REVOKED"}
        if self.link_status not in valid_statuses:
            raise ValueError(
                f"PlanningExecutionLink.link_status debe ser uno de {valid_statuses}. "
                f"Recibido: '{self.link_status}'."
            )
        if self.link_status == "REVOKED":
            if not self.revoked_by:
                raise ValueError(
                    "PlanningExecutionLink.revoked_by es obligatorio cuando link_status='REVOKED'."
                )
            if not self.revocation_reason:
                raise ValueError(
                    "PlanningExecutionLink.revocation_reason es obligatorio cuando "
                    "link_status='REVOKED'."
                )
        if self.numero_sesion is not None and self.numero_sesion < 1:
            raise ValueError(
                "PlanningExecutionLink.numero_sesion debe ser >= 1 si está definido."
            )

    @classmethod
    def create(
        cls,
        planning_internal_id: uuid.UUID,
        id_actividad: str,
        linked_by: str,
        link_rationale: str,
        numero_sesion: Optional[int] = None,
    ) -> "PlanningExecutionLink":
        """Factory — crea un nuevo vínculo ACTIVE con UUID v4 generado automáticamente.

        PRECONDICIÓN: linked_by debe ser un actor humano institucional.
        La IA no puede invocar este factory (R-09 extendido de Fase 29.18.1).

        Args:
            planning_internal_id: UUID de la PlannedActivity en dominio planificación.
            id_actividad: Clave de la actividad en dominio ejecución (solo referencia).
            linked_by: Actor humano responsable del vínculo.
            link_rationale: Justificación textual del vínculo.
            numero_sesion: Número de sesión si es multi-sesión (None = sesión única).

        Returns:
            PlanningExecutionLink con link_status='ACTIVE' y link_id generado.
        """
        return cls(
            link_id=uuid.uuid4(),
            planning_internal_id=planning_internal_id,
            id_actividad=id_actividad,
            linked_by=linked_by,
            linked_at=datetime.now(),
            link_rationale=link_rationale,
            numero_sesion=numero_sesion,
            link_status="ACTIVE",
        )

    def revoke(self, revoked_by: str, reason: str) -> "PlanningExecutionLink":
        """Retorna una nueva instancia con link_status='REVOKED'.

        INMUTABILIDAD: No modifica la instancia actual. Retorna una copia revocada.
        PRECONDICIÓN: revoked_by debe ser un actor humano institucional.
        La IA no puede revocar vínculos (R-09 extendido de Fase 29.18.1).

        Args:
            revoked_by: Actor humano que revoca el vínculo.
            reason: Motivo de la revocación.

        Returns:
            Nueva instancia PlanningExecutionLink con link_status='REVOKED'.

        Raises:
            ValueError: Si el vínculo ya estaba revocado.
        """
        if self.link_status == "REVOKED":
            raise ValueError(
                f"PlanningExecutionLink '{self.link_id}' ya está revocado. "
                "No se puede revocar dos veces."
            )
        if not revoked_by or not str(revoked_by).strip():
            raise ValueError("revoked_by es obligatorio para revocar un vínculo.")
        if not reason or not str(reason).strip():
            raise ValueError("reason es obligatorio para revocar un vínculo.")
        return PlanningExecutionLink(
            link_id=self.link_id,
            planning_internal_id=self.planning_internal_id,
            id_actividad=self.id_actividad,
            linked_by=self.linked_by,
            linked_at=self.linked_at,
            link_rationale=self.link_rationale,
            numero_sesion=self.numero_sesion,
            link_status="REVOKED",
            revoked_by=revoked_by,
            revoked_at=datetime.now(),
            revocation_reason=reason,
        )
