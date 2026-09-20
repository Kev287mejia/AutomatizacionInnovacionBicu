"""
Value Objects del Dominio — Modulo Planificacion -> Diseno Metodologico.

Fuente arquitectonica:
  FASE_29_2_DISENO_ARQUITECTONICO_PLANIFICACION_DISENO.md §8
  FASE_29_2_1_CIERRE_DECISIONES_INSTITUCIONALES.md §21

Clasificacion de cada elemento indicada inline.
Fase 29.3 — Dominio Puro
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from app.planning.domain.catalogs import (
    VALID_CATALOG_IDS,
)


# ---------------------------------------------------------------------------
# DesignStatus — DECISION ARQUITECTONICA (D-03 pendiente de validacion)
# Fuente: FASE_29_2 §8, FASE_29_2_1 §10
# Los estados mas alla de DRAFT/LISTO son propuestas arquitectonicas.
# No representan reglas institucionales confirmadas.
# ---------------------------------------------------------------------------
class DesignStatus(str, Enum):
    """Estado del ciclo de vida del Diseno Metodologico.

    Clasificacion: DECISION ARQUITECTONICA.
    Estado minimo para v1: DRAFT y LISTO (APPROVED).
    Los estados intermedios (GENERATED, REVIEW, REJECTED) son extensibles.
    Flujo de aprobacion exacto: PENDIENTE DE VALIDACION INSTITUCIONAL (D-03).
    """
    DRAFT    = "DRAFT"     # En construccion, no exportable
    GENERATED = "GENERATED" # DOCX generado, pendiente de revision
    REVIEW   = "REVIEW"    # En revision humana
    APPROVED = "APPROVED"  # Aprobado — estado LISTO institucional
    REJECTED = "REJECTED"  # Rechazado, requiere nueva iteracion


# ---------------------------------------------------------------------------
# CatalogReference — INFERENCIA CONTROLADA
# Fuente: FASE_29_2 §8, FASE_29_1 §catálogos
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CatalogReference:
    """Referencia a un catalogo institucional BICU.

    Clasificacion: INFERENCIA CONTROLADA.
    Permite representar entradas de C1-C5 sin duplicar el catalogo.

    Atributos:
        catalog_id: Identificador del catalogo (C1, C2, C3, C4, C5 o C1_EJE, etc.).
        code:       Codigo de la entrada dentro del catalogo.
        label:      Descripcion legible de la entrada.
        source:     Fuente institucional del catalogo.
    """
    catalog_id: str
    code: str
    label: str
    source: str = "POA BICU"

    def __post_init__(self) -> None:
        if not self.catalog_id:
            raise ValueError("catalog_id es obligatorio.")
        normalized_cat = self.catalog_id.upper()
        valid_prefixes = {"C1", "C2", "C3", "C4", "C5"}
        if normalized_cat not in VALID_CATALOG_IDS and normalized_cat not in valid_prefixes:
            raise ValueError(
                f"catalog_id '{self.catalog_id}' no es un identificador "
                f"de catalogo valido. Valores validos: {sorted(VALID_CATALOG_IDS)}"
            )
        if not self.code:
            raise ValueError("code es obligatorio.")
        if not self.label:
            raise ValueError("label es obligatorio.")


# ---------------------------------------------------------------------------
# ParticipantGoals — EVIDENCIA DIRECTA
# Fuente: FASE_29_2 §8 (R-03)
# Verificado en 5/5 documentos reales.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ParticipantGoals:
    """Metas de protagonistas por estamento y sexo.

    Clasificacion: EVIDENCIA DIRECTA (matrices POA reales).
    Todos los campos deben ser enteros no negativos.
    La IA JAMAS puede modificar estos valores (R-09 — Regla de Oro).

    Fuente: FASE_29_2 §8 (R-03), FASE_29_1 corpus real.
    """
    est_grado_m: int = 0
    est_grado_f: int = 0
    est_postgrado_m: int = 0
    est_postgrado_f: int = 0
    docentes_m: int = 0
    docentes_f: int = 0
    administrativos_m: int = 0
    administrativos_f: int = 0
    externos_m: int = 0
    externos_f: int = 0

    def __post_init__(self) -> None:
        for fname, fval in self.__dataclass_fields__.items():  # type: ignore[attr-defined]
            v = getattr(self, fname)
            if not isinstance(v, int) or v < 0:
                raise ValueError(
                    f"ParticipantGoals.{fname} debe ser entero no negativo. Valor: {v!r}"
                )

    @classmethod
    def from_totals(
        cls,
        estudiantes: int = 0,
        docentes: int = 0,
        administrativos: int = 0,
        externos: int = 0,
        mujeres: Optional[int] = None,
        varones: Optional[int] = None,
    ) -> "ParticipantGoals":
        """Factory de conveniencia para instanciar metas desde totales agregados."""
        for val, name in [(estudiantes, "estudiantes"), (docentes, "docentes"),
                          (administrativos, "administrativos"), (externos, "externos")]:
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"Metas de {name} no pueden ser negativos. Valor: {val!r}")

        total_calc = estudiantes + docentes + administrativos + externos

        if mujeres is not None and varones is not None:
            if not isinstance(mujeres, int) or mujeres < 0 or not isinstance(varones, int) or varones < 0:
                raise ValueError("Metas de mujeres y varones no pueden ser negativos.")
            if mujeres + varones != total_calc:
                raise ValueError(
                    f"Discrepancia en desglose por sexo: {mujeres} mujeres + {varones} varones "
                    f"!= {total_calc} total."
                )
            f_est = min(mujeres, estudiantes)
            m_est = estudiantes - f_est
            rem_f = mujeres - f_est

            f_doc = min(rem_f, docentes)
            m_doc = docentes - f_doc
            rem_f -= f_doc

            f_adm = min(rem_f, administrativos)
            m_adm = administrativos - f_adm
            rem_f -= f_adm

            f_ext = min(rem_f, externos)
            m_ext = externos - f_ext

            return cls(
                est_grado_m=m_est,
                est_grado_f=f_est,
                docentes_m=m_doc,
                docentes_f=f_doc,
                administrativos_m=m_adm,
                administrativos_f=f_adm,
                externos_m=m_ext,
                externos_f=f_ext,
            )
        else:
            return cls(
                est_grado_m=0,
                est_grado_f=estudiantes,
                docentes_m=0,
                docentes_f=docentes,
                administrativos_m=0,
                administrativos_f=administrativos,
                externos_m=0,
                externos_f=externos,
            )

    def total(self) -> int:
        """Suma de todos los estamentos. Usado en R-03.

        Fuente: FASE_29_2 §8 (ParticipantGoals), R-03.
        Clasificacion: REGLA MATEMATICA — CONFIRMADA.
        """
        return (
            self.est_grado_m + self.est_grado_f
            + self.est_postgrado_m + self.est_postgrado_f
            + self.docentes_m + self.docentes_f
            + self.administrativos_m + self.administrativos_f
            + self.externos_m + self.externos_f
        )

    def to_narrative(self) -> str:
        """Genera el texto narrativo de protagonistas (Pregunta 4 — R-03).

        Clasificacion: REGLA DETERMINISTA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-03).

        Regla:
          - Si solo hay estudiantes -> "{total} estudiantes."
          - Si hay estudiantes + docentes -> "{total} protagonistas en total: ..."
          - Si hay desglose completo con sexo -> texto con parentesis.
        """
        t = self.total()
        if t == 0:
            return "Sin protagonistas definidos."

        total_est = (
            self.est_grado_m + self.est_grado_f
            + self.est_postgrado_m + self.est_postgrado_f
        )
        total_doc = self.docentes_m + self.docentes_f
        total_adm = self.administrativos_m + self.administrativos_f
        total_ext = self.externos_m + self.externos_f
        total_f = (
            self.est_grado_f + self.est_postgrado_f
            + self.docentes_f + self.administrativos_f + self.externos_f
        )
        total_m = t - total_f

        has_only_students = (total_doc == 0 and total_adm == 0 and total_ext == 0)
        has_students_and_docentes = (total_est > 0 and total_doc > 0
                                     and total_adm == 0 and total_ext == 0)

        if has_only_students:
            return f"{t} estudiantes."

        if has_students_and_docentes:
            return (
                f"{t} protagonistas en total: "
                f"{total_est} estudiantes y {total_doc} docentes."
            )

        # Desglose completo con sexo
        return (
            f"{t} protagonistas en total "
            f"({total_f} mujeres y {total_m} varones; "
            f"integrando estudiantes y personal administrativo)."
        )


# ---------------------------------------------------------------------------
# TimeBlock — EVIDENCIA DIRECTA
# Fuente: FASE_29_2 §8 (TimeBlock), E-02
# Verificado en 5/5 documentos reales.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TimeBlock:
    """Bloque de tiempo de la agenda (Tabla 2).

    Clasificacion: EVIDENCIA DIRECTA.
    Fuente: FASE_29_2 §8 (TimeBlock), Regla R-05, R-06.

    Invariante: minutes > 0 (entero positivo).

    Atributos:
        sequence: Orden del bloque en la agenda (1..k). No necesariamente consecutivo
                  (la institucion puede tener huecos). Debe ser positivo.
        label:    Etiqueta del bloque (ej. "Apertura", "Bloque I", "Cierre").
                  El dominio no impone nombres fijos (sin evidencia de nombres obligatorios).
        minutes:  Duracion en minutos enteros. Invariante: > 0.
    """
    sequence: int
    label: str
    minutes: int

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or self.sequence <= 0:
            raise ValueError(
                f"TimeBlock.sequence debe ser entero positivo. Valor: {self.sequence!r}"
            )
        if not self.label or not self.label.strip():
            raise ValueError("TimeBlock.label no puede ser vacio.")
        if not isinstance(self.minutes, int) or self.minutes <= 0:
            raise ValueError(
                f"TimeBlock.minutes debe ser entero positivo. Valor: {self.minutes!r}"
            )


# ---------------------------------------------------------------------------
# OperationalActivity — EVIDENCIA DIRECTA
# Fuente: FASE_29_2 §8 (OperationalActivity), Tabla 3, R-06
# Verificado en 5/5 documentos reales.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OperationalActivity:
    """Actividad de la Matriz Operacional (Tabla 3).

    Clasificacion: EVIDENCIA DIRECTA.
    Fuente: FASE_29_2 §8 (OperationalActivity), R-06.

    Correspondencia conceptual con TimeBlock (R-06):
        OperationalActivity[i].minutes == TimeBlock[i].minutes para todo i.
        OperationalActivity[i].phase_label ~ TimeBlock[i].label (espejo semantico).

    Esta clase NO impone la correspondencia directamente — es responsabilidad
    de InstitutionalRulesEngine y MethodologicalDesignValidator verificarla.

    Atributos:
        step_number:    Numero secuencial (No. en Tabla 3). Positivo.
        phase_label:    Fase/etapa (debe corresponder al TimeBlock homologo).
        operative_goal: Objetivo operativo de la etapa.
        procedure:      Procedimiento detallado (puede ser asistido por IA).
        materials:      Materiales de la etapa (ingresado por usuario).
        minutes:        Duracion en minutos. DEBE igualar al TimeBlock homologo (R-06).
    """
    step_number: int
    phase_label: str
    operative_goal: str
    procedure: str
    materials: str
    minutes: int

    def __post_init__(self) -> None:
        if not isinstance(self.step_number, int) or self.step_number <= 0:
            raise ValueError(
                f"OperationalActivity.step_number debe ser entero positivo. "
                f"Valor: {self.step_number!r}"
            )
        if not self.phase_label or not self.phase_label.strip():
            raise ValueError("OperationalActivity.phase_label no puede ser vacio.")
        if not isinstance(self.minutes, int) or self.minutes <= 0:
            raise ValueError(
                f"OperationalActivity.minutes debe ser entero positivo. "
                f"Valor: {self.minutes!r}"
            )


# ---------------------------------------------------------------------------
# FAQTable — EVIDENCIA DIRECTA
# Fuente: FASE_29_2 §8 (FAQTable), E-01, Tabla 1 (7 preguntas fijas)
# Verificado en 5/5 documentos reales.
# ---------------------------------------------------------------------------
@dataclass
class FAQTable:
    """Tabla de Preguntas Frecuentes — Bloque 3 del Diseno Metodologico (Tabla 1).

    Clasificacion: EVIDENCIA DIRECTA.
    Fuente: FASE_29_2 §8 (FAQTable), Fase 29.1 corpus real.
    Las 7 preguntas son INVARIANTES (verificadas en 5/5 documentos).

    Preguntas (literales institucionales):
      P1: En que es esta actividad?
      P2: Para que se realiza? (puede estar vacia — sin evidencia de obligatoriedad)
      P3: Cuantas sesiones? (default "Sesion unica" — D-05)
      P4: Cuanto son los protagonistas? (DERIVADO de ParticipantGoals — R-03)
      P5: Quien va facilitar? (DESDE area_responsable — R-02)
      P6: Que materiales? (usuario + catalogo insumos)
      P7: Cuanto tiempo dura? (DERIVADO de total_minutes — R-04)

    Nota sobre P4, P5, P7: son campos DERIVADOS — no deben ingresarse manualmente
    sin validar contra los datos institucionales correspondientes.
    """
    q1_que_es: str
    q2_para_que: str
    q3_sesiones: str
    q4_protagonistas: str   # DERIVADO: ParticipantGoals.to_narrative() (R-03)
    q5_facilitador: str     # DERIVADO: area_responsable (R-02)
    q6_materiales: str
    q7_duracion: str        # DERIVADO: formato_duracion(total_minutes) (R-04)

    def __post_init__(self) -> None:
        if not self.q1_que_es or not self.q1_que_es.strip():
            raise ValueError("FAQTable.q1_que_es es obligatorio.")
        if not self.q4_protagonistas or not self.q4_protagonistas.strip():
            raise ValueError(
                "FAQTable.q4_protagonistas es obligatorio (derivado de ParticipantGoals)."
            )
        if not self.q5_facilitador or not self.q5_facilitador.strip():
            raise ValueError(
                "FAQTable.q5_facilitador es obligatorio (derivado de area_responsable)."
            )
        if not self.q7_duracion or not self.q7_duracion.strip():
            raise ValueError(
                "FAQTable.q7_duracion es obligatorio (derivado de total_minutes)."
            )


# ---------------------------------------------------------------------------
# AIProposal — DECISION ARQUITECTONICA
# Fuente: FASE_29_2 §8 (AIProposal), §14 (contrato IA)
# IMPORTANTE: Este objeto NO conecta ningun LLM. Es la representacion
# de una propuesta que un futuro proveedor de IA entregara al sistema.
# ---------------------------------------------------------------------------

# Campos que la IA PUEDE asistir — EVIDENCIA DIRECTA (FASE_29_2 §14)
AI_ALLOWED_TARGET_FIELDS: frozenset[str] = frozenset({
    "introduction",
    "methodological_approach",
    "objective_1",
    "objective_2",
    "procedure",       # Procedimiento de una OperationalActivity (T3)
    "operative_goal",  # Objetivo operativo de una OperationalActivity (T3)
})

# Campos que NUNCA puede tocar la IA — REGLA DE ORO (FASE_29_2 §14, R-09)
AI_PROHIBITED_TARGET_FIELDS: frozenset[str] = frozenset({
    "activity_name",
    "sede",
    "mun_sede",
    "dep_sede",
    "area_responsable",
    "eje_estrategia",
    "codigo_presupuestario",
    "participant_goals",
    "tipo_evento",
    "programa",
    "total_minutes",
    "planning_id",
    "activity_internal_id",
})


@dataclass
class AIProposal:
    """Propuesta de texto generada por un asistente de IA.

    Clasificacion: DECISION ARQUITECTONICA.
    Fuente: FASE_29_2 §8 (AIProposal), §14 (contrato IA), FASE_29_2_1 §11.

    IMPORTANTE:
    - Este objeto NO hace llamadas HTTP ni a ningun LLM.
    - Representa el resultado que un futuro AIAssistanceService (puerto IAIAssistPort)
      entregara al dominio.
    - requires_review=True SIEMPRE. Ningun texto de IA se usa sin revision humana.
    - La IA JAMAS puede modificar campos clasificados como deterministas (R-09).

    Trazabilidad:
        source_inputs:  Datos de planificacion usados como contexto de la IA.
                        Permite auditar que informacion recibio el LLM.
        accepted=None:  La propuesta aun no ha sido revisada.
        accepted=True:  El humano acepto el texto — se copia al campo destino.
        accepted=False: El humano rechazo el texto — escribe manualmente.
    """
    proposal_id: uuid.UUID
    target_field: str          # Campo al que esta propuesta aplica
    proposed_content: str      # Texto propuesto por la IA
    source_inputs: dict        # Datos de planificacion usados como contexto
    confidence: float          # 0.0 a 1.0 (orientativo, no normativo)
    requires_review: bool      # Siempre True por invariante del dominio
    reviewed_by: Optional[str] = None
    review_timestamp: Optional[datetime] = None
    accepted: Optional[bool] = None
    rejection_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.target_field not in AI_ALLOWED_TARGET_FIELDS:
            raise ValueError(
                f"AIProposal.target_field '{self.target_field}' no esta permitido. "
                f"La IA solo puede asistir los campos: {sorted(AI_ALLOWED_TARGET_FIELDS)}. "
                f"Referencia: FASE_29_2 §14 (contrato IA)."
            )
        if not self.proposed_content or not self.proposed_content.strip():
            raise ValueError("AIProposal.proposed_content no puede ser vacio.")
        if not isinstance(self.confidence, (int, float)) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"AIProposal.confidence debe estar en [0.0, 1.0]. Valor: {self.confidence!r}"
            )
        if not self.requires_review:
            raise ValueError(
                "AIProposal.requires_review debe ser True siempre. "
                "Ningun texto de IA puede usarse sin revision humana."
            )
        if not isinstance(self.source_inputs, dict):
            raise ValueError("AIProposal.source_inputs debe ser un dict.")

    @property
    def is_pending_review(self) -> bool:
        """True si la propuesta aun no ha sido revisada."""
        return self.accepted is None

    @property
    def is_accepted(self) -> bool:
        """True si el humano acepto la propuesta."""
        return self.accepted is True

    @property
    def is_rejected(self) -> bool:
        """True si el humano rechazo la propuesta."""
        return self.accepted is False

    @classmethod
    def create(
        cls,
        target_field: str,
        proposed_content: str,
        source_inputs: dict,
        confidence: float = 0.5,
    ) -> "AIProposal":
        """Factory — crea una propuesta nueva, aun sin revision.

        El proposal_id es generado automaticamente como UUID.
        requires_review siempre es True (invariante del dominio).
        """
        return cls(
            proposal_id=uuid.uuid4(),
            target_field=target_field,
            proposed_content=proposed_content,
            source_inputs=source_inputs,
            confidence=confidence,
            requires_review=True,
        )

    def accept(self, reviewer: str) -> "AIProposal":
        """Registra la aceptacion humana de la propuesta."""
        if not reviewer or not reviewer.strip():
            raise ValueError("reviewer no puede estar vacio.")
        self.accepted = True
        self.reviewed_by = reviewer.strip()
        self.review_timestamp = datetime.now()
        self.rejection_reason = None
        return self

    def reject(self, reviewer: str, reason: str) -> "AIProposal":
        """Registra el rechazo humano de la propuesta con motivo."""
        if not reviewer or not reviewer.strip():
            raise ValueError("reviewer no puede estar vacio.")
        if not reason or not reason.strip():
            raise ValueError("reason no puede estar vacio al rechazar.")
        self.accepted = False
        self.reviewed_by = reviewer.strip()
        self.review_timestamp = datetime.now()
        self.rejection_reason = reason.strip()
        return self
