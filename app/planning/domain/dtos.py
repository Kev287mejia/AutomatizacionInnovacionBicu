"""
DTOs del Modulo Planificacion — Contratos de Transferencia de Datos.

Fuente: FASE_29_2_DISENO_ARQUITECTONICO_PLANIFICACION_DISENO.md §11, §12
Clasificacion: DECISION ARQUITECTONICA (estructura de DTOs).

Estos DTOs son contratos de lectura/transferencia.
PlannedActivityDTO es SOLO LECTURA — el modulo de Diseno Metodologico
consume esta informacion pero JAMAS la modifica.

Fase 29.3 — Dominio Puro
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from app.planning.domain.value_objects import DesignStatus, ParticipantGoals


# ---------------------------------------------------------------------------
# PlannedActivityDTO
# Vista de solo lectura de una actividad planificada.
# Fuente: FASE_29_2 §11
# Clasificacion: DECISION ARQUITECTONICA
# El modulo Diseno Metodologico la consume pero NUNCA la modifica.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PlannedActivityDTO:
    """DTO de solo lectura de una actividad planificada.

    Fuente: FASE_29_2 §11 (PlannedActivityDTO).
    Clasificacion: DECISION ARQUITECTONICA.

    REGLA ABSOLUTA:
        El modulo de Diseno Metodologico NUNCA modifica este DTO.
        Los campos son INMUTABLES (frozen=True).
        La IA JAMAS puede modificar estos valores (R-09).

    Campos obligatorios (EVIDENCIA DIRECTA):
        activity_internal_id, planning_id, activity_name, sede,
        area_responsable, eje_estrategia, programa, tipo_evento,
        participant_goals.
    """
    # --- IDENTIDAD ---
    activity_internal_id: uuid.UUID    # UUID tecnico — DECISION ARQUITECTONICA (D-04)
    planning_id: str                   # ID institucional — PENDIENTE BICU (D-04)

    # --- DATOS INSTITUCIONALES (INMUTABLES) ---
    activity_name: str
    sede: str
    dep_sede: str
    mun_sede: str
    programa: str
    eje_estrategia: str
    area_responsable: str
    tipo_evento: str
    participant_goals: ParticipantGoals

    # --- OPCIONALES ---
    otro_programa: Optional[str] = None
    proyecto: Optional[str] = None
    tipo_proyecto: Optional[str] = None
    ambito: Optional[str] = None
    codigo_presupuestario: Optional[str] = None
    departamento_responsable: Optional[str] = None
    proposito: Optional[str] = None
    fecha_evento: Optional[date] = None
    convenio: Optional[str] = None
    entidades_cooperantes: Optional[str] = None


# ---------------------------------------------------------------------------
# TimeBlockDTO — sublista dentro de MethodologicalDesignDTO
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TimeBlockDTO:
    """DTO de un bloque de tiempo de la agenda (Tabla 2)."""
    sequence: int
    label: str
    minutes: int


# ---------------------------------------------------------------------------
# OperationalActivityDTO — sublista dentro de MethodologicalDesignDTO
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OperationalActivityDTO:
    """DTO de una actividad de la Matriz Operacional (Tabla 3)."""
    step_number: int
    phase_label: str
    operative_goal: str
    procedure: str
    materials: str
    minutes: int


# ---------------------------------------------------------------------------
# FAQTableDTO — bloque 3 dentro de MethodologicalDesignDTO
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FAQTableDTO:
    """DTO de la Tabla de Preguntas Frecuentes (Tabla 1 — 7 preguntas fijas).

    Fuente: FASE_29_2 §12.
    Clasificacion: EVIDENCIA DIRECTA.
    """
    q1_que_es: str
    q2_para_que: str
    q3_sesiones: str
    q4_protagonistas: str   # DERIVADO (R-03)
    q5_facilitador: str     # DERIVADO (R-02)
    q6_materiales: str
    q7_duracion: str        # DERIVADO (R-04)


# ---------------------------------------------------------------------------
# MethodologicalDesignDTO
# Contrato de transferencia al renderer (futuro Fase 29.5).
# Fuente: FASE_29_2 §12
# Clasificacion: DECISION ARQUITECTONICA
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MethodologicalDesignDTO:
    """DTO completo del Diseno Metodologico, listo para renderizar.

    Fuente: FASE_29_2 §12 (MethodologicalDesignDTO).
    Clasificacion: DECISION ARQUITECTONICA.

    Este DTO solo se genera cuando el diseno ha pasado todas las
    validaciones V-MD-01 a V-MD-12. El Renderer es ciego a las reglas:
    recibe un DTO valido y lo transforma en estructura de documento.

    Literales institucionales configurables (D-06, D-07):
        objectives_heading:    Default "OBJETIVOS DEL TALLER ARTISTICO"
        program_section_label: Default "III. PROGRAMA"
        matrix_section_label:  Default "VI. MATRIZ DE PLANIFICACION"
    """
    # --- METADATOS ---
    design_id: uuid.UUID
    version: int
    created_at: datetime
    created_by: str
    approved_by: Optional[str]

    # --- TITULO DEL DOCUMENTO (R-01) ---
    document_title: str     # "Diseno metodologico " + activity_name

    # --- BLOQUE 1: INTRODUCCION ---
    introduction: str
    methodological_approach: str

    # --- BLOQUE 2: OBJETIVOS ---
    objectives_heading: str  # Default: "OBJETIVOS DEL TALLER ARTISTICO" (D-06)
    objective_1: str
    objective_2: str

    # --- BLOQUE 3: FAQ ---
    faq: FAQTableDTO

    # --- BLOQUE 4: AGENDA (Tabla 2) ---
    program_section_label: str       # Default: "III. PROGRAMA" (D-07)
    agenda: tuple[TimeBlockDTO, ...]
    total_minutes: int               # Σ(agenda.minutes) — CALCULADO

    # --- BLOQUE 5: MATRIZ OPERACIONAL (Tabla 3) ---
    matrix_section_label: str        # Default: "VI. MATRIZ DE PLANIFICACION" (D-07)
    operational_matrix: tuple[OperationalActivityDTO, ...]


# ---------------------------------------------------------------------------
# PlanningSourceActivityDTO — Fila leída de una fuente externa POA (Fase 29.7)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PlanningSourceActivityDTO:
    """Representa un registro individual de actividad leído de una matriz POA externa.

    Fuente: FASE_29_7 §7.
    Clasificación: DECISIÓN ARQUITECTÓNICA (Contrato de lectura sin acoplamiento a SQLite ni PlannedActivity).

    Conserva trazabilidad de origen y valores observados explícitos sin fabricar datos.
    """
    source_file: str
    sheet_name: str
    row_number: int

    raw_no: Optional[str] = None
    planning_id: Optional[str] = None
    activity_name: Optional[str] = None
    sede: Optional[str] = None
    dep_sede: Optional[str] = None
    mun_sede: Optional[str] = None
    programa: Optional[str] = None
    otro_programa: Optional[str] = None
    proyecto: Optional[str] = None
    tipo_proyecto: Optional[str] = None
    ambito: Optional[str] = None
    eje_estrategia: Optional[str] = None
    codigo_presupuestario: Optional[str] = None
    area_responsable: Optional[str] = None
    departamento_responsable: Optional[str] = None
    tipo_evento: Optional[str] = None
    proposito: Optional[str] = None
    fecha_evento: Optional[str] = None
    convenio: Optional[str] = None
    entidades_cooperantes: Optional[str] = None

    # Metas cuantitativas observadas (None si no están presentes en la hoja)
    est_grado_m: Optional[int] = None
    est_grado_f: Optional[int] = None
    est_postgrado_m: Optional[int] = None
    est_postgrado_f: Optional[int] = None
    docentes_m: Optional[int] = None
    docentes_f: Optional[int] = None
    administrativos_m: Optional[int] = None
    administrativos_f: Optional[int] = None
    externos_m: Optional[int] = None
    externos_f: Optional[int] = None

    reading_warnings: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# PlanningSourceReadResultDTO — Resultado técnico de lectura del Reader
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PlanningSourceReadResultDTO:
    """Resultado general de la lectura técnica de un archivo institucional POA."""
    source_file: str
    sheet_name: str
    activities: tuple[PlanningSourceActivityDTO, ...]
    structural_errors: tuple[str, ...] = field(default_factory=tuple)
    reading_warnings: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# PlanningIngestionReportDTO — Reporte del Servicio de Ingestión
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PlanningIngestionReportDTO:
    """Reporte institucional de la ingestión de actividades del POA en Planning V003.

    Fuente: FASE_29_7 §13.
    """
    source_file: str
    sheet_name: str
    total_rows_examined: int
    rows_accepted: int
    rows_rejected: int
    created_activity_ids: tuple[str, ...] = field(default_factory=tuple)
    updated_activity_ids: tuple[str, ...] = field(default_factory=tuple)
    duplicates_detected: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    rejection_reasons: tuple[tuple[int, str], ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# DTOs de Gestión del Ciclo del Diseño Metodológico (Fase 29.9)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PlannedActivitySummaryDTO:
    """Resumen de una actividad planificada con su estado de diseño para listados y filtros.

    Fuente: FASE_29_9 §7.
    """
    activity_internal_id: uuid.UUID
    planning_id: str
    activity_name: str
    sede: str
    area_responsable: str
    total_participants: int
    design_status: str  # "SIN_DISENO", "DRAFT", "GENERATED", "APPROVED"
    design_id: Optional[uuid.UUID] = None
    design_version: Optional[int] = None


@dataclass(frozen=True)
class PlannedActivityDetailDTO:
    """Detalle completo de una actividad planificada y su diseño metodológico asociado.

    Fuente: FASE_29_9 §8.
    """
    activity_internal_id: uuid.UUID
    planning_id: str
    activity_name: str
    sede: str
    area_responsable: str
    eje_estrategia: str
    programa: str
    tipo_evento: str
    dep_sede: str = ""
    mun_sede: str = ""
    otro_programa: Optional[str] = None
    proyecto: Optional[str] = None
    tipo_proyecto: Optional[str] = None
    ambito: Optional[str] = None
    codigo_presupuestario: Optional[str] = None
    departamento_responsable: Optional[str] = None
    proposito: Optional[str] = None
    fecha_evento: Optional[date] = None
    convenio: Optional[str] = None
    entidades_cooperantes: Optional[str] = None
    participant_goals: Optional[ParticipantGoals] = None
    design_id: Optional[uuid.UUID] = None
    design_status: str = "SIN_DISENO"
    design_version: Optional[int] = None


@dataclass(frozen=True)
class UpdateMethodologicalDesignCommand:
    """Comando inmutable para actualizar los bloques de un diseño metodológico en DRAFT.

    Fuente: FASE_29_9 §12.
    """
    design_id: uuid.UUID
    introduction_text: Optional[str] = None
    methodological_approach: Optional[str] = None
    objectives: Optional[tuple[str, ...]] = None
    faq: Optional[FAQTableDTO] = None
    agenda: Optional[tuple[TimeBlockDTO, ...]] = None
    operational_matrix: Optional[tuple[OperationalActivityDTO, ...]] = None


@dataclass(frozen=True)
class ValidationResultDTO:
    """Resultado individual de una regla de validación institucional."""
    rule_id: str
    severity: str  # "ERROR", "WARNING", "INFO"
    message: str
    field: Optional[str] = None


@dataclass(frozen=True)
class ValidationReportDTO:
    """Reporte agregado de validación de un diseño metodológico."""
    is_valid: bool
    errors: tuple[ValidationResultDTO, ...] = field(default_factory=tuple)
    warnings: tuple[ValidationResultDTO, ...] = field(default_factory=tuple)
    results: tuple[ValidationResultDTO, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# DTOs y Comandos para Asistencia de IA (Fase 29.14)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RequestAIProposalCommand:
    """Comando inmutable para solicitar una propuesta de asistencia a la IA."""
    design_id: uuid.UUID
    target_field: str
    step_number: Optional[int] = None
    phase_label: Optional[str] = None


@dataclass(frozen=True)
class AcceptAIProposalCommand:
    """Comando inmutable para aceptar formalmente una propuesta y volcar su contenido."""
    design_id: uuid.UUID
    proposal_id: uuid.UUID
    reviewer: str


@dataclass(frozen=True)
class RejectAIProposalCommand:
    """Comando inmutable para rechazar una propuesta con justificación obligatoria."""
    design_id: uuid.UUID
    proposal_id: uuid.UUID
    reviewer: str
    rejection_reason: str


@dataclass(frozen=True)
class AIProposalDTO:
    """DTO inmutable para transferir datos de auditoría de propuestas hacia la UI."""
    proposal_id: uuid.UUID
    design_id: uuid.UUID
    target_field: str
    proposed_content: str
    confidence: float
    requires_review: bool
    accepted: Optional[bool]
    reviewed_by: Optional[str]
    review_timestamp: Optional[datetime]
    rejection_reason: Optional[str]
    source_inputs: dict
    step_number: Optional[int] = None

    @property
    def is_pending(self) -> bool:
        """True si la propuesta aún no ha sido revisada por un humano."""
        return self.accepted is None

    @property
    def is_accepted(self) -> bool:
        """True si la propuesta fue formalmente aceptada."""
        return self.accepted is True

    @property
    def is_rejected(self) -> bool:
        """True si la propuesta fue rechazada."""
        return self.accepted is False

    @classmethod
    def from_domain(cls, proposal: Any, design_id: uuid.UUID) -> "AIProposalDTO":
        """Factory de conveniencia para construir el DTO a partir de la entidad AIProposal."""
        step_no = proposal.step_number if hasattr(proposal, "step_number") else None
        if step_no is None and isinstance(proposal.source_inputs, dict):
            step_no = proposal.source_inputs.get("step_number")

        return cls(
            proposal_id=proposal.proposal_id,
            design_id=design_id,
            target_field=proposal.target_field,
            proposed_content=proposal.proposed_content,
            confidence=float(proposal.confidence),
            requires_review=bool(proposal.requires_review),
            accepted=proposal.accepted,
            reviewed_by=proposal.reviewed_by,
            review_timestamp=proposal.review_timestamp,
            rejection_reason=proposal.rejection_reason,
            source_inputs=dict(proposal.source_inputs or {}),
            step_number=step_no,
        )
