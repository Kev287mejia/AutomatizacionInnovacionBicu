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
