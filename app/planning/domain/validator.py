"""
MethodologicalDesignValidator — Domain Service.
Implementa las validaciones V-MD-01 a V-MD-12.

Fuente: FASE_29_2_DISENO_ARQUITECTONICO_PLANIFICACION_DISENO.md §15
Clasificacion: DECISION ARQUITECTONICA + EVIDENCIA DIRECTA (segun cada validacion).
Fase 29.3 — Dominio Puro
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.planning.domain.catalogs import C1_CODES, C2_CODES, C4_CODES
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.rules_engine import InstitutionalRulesEngine


class ValidationSeverity(str, Enum):
    """Severidad de un resultado de validacion.

    ERROR:   Impide considerar valido el diseno. Bloquea la exportacion.
    WARNING: Permite continuar, pero requiere atencion.
    INFO:    Informativo, no bloquea.
    """
    ERROR   = "ERROR"
    WARNING = "WARNING"
    INFO    = "INFO"


@dataclass(frozen=True)
class ValidationResult:
    """Resultado de una validacion individual.

    Atributos:
        rule_id:   Identificador de la validacion (V-MD-01, etc.)
        severity:  ERROR, WARNING o INFO.
        message:   Descripcion del problema o informacion.
        field:     Campo del diseño afectado (si aplica).
    """
    rule_id: str
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None

    @property
    def is_error(self) -> bool:
        return self.severity == ValidationSeverity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == ValidationSeverity.WARNING


@dataclass
class ValidationReport:
    """Reporte agregado de todas las validaciones."""
    results: list[ValidationResult]

    @property
    def errors(self) -> list[ValidationResult]:
        return [r for r in self.results if r.is_error]

    @property
    def warnings(self) -> list[ValidationResult]:
        return [r for r in self.results if r.is_warning]

    @property
    def is_valid(self) -> bool:
        """True si no hay errores (puede haber warnings)."""
        return len(self.errors) == 0

    @property
    def has_blocking_errors(self) -> bool:
        """True si el diseno NO puede exportarse por errores criticos."""
        return len(self.errors) > 0

    def has_error(self, rule_id: str) -> bool:
        """Retorna True si existe al menos un error con el rule_id dado."""
        return any(r.rule_id == rule_id and r.is_error for r in self.results)


# Alias de conveniencia
ValidationIssue = ValidationResult


class MethodologicalDesignValidator:
    """Servicio de dominio que ejecuta V-MD-01 a V-MD-12.

    Fuente: FASE_29_2 §15 (Validaciones Pre-Exportacion).
    Clasificacion de cada validacion indicada en cada metodo.

    Uso:
        validator = MethodologicalDesignValidator()
        report = validator.validate(design, activity)
        if report.is_valid:
            # continuar con exportacion
    """

    def validate(
        self,
        design: MethodologicalDesign,
        activity: Optional[PlannedActivity] = None,
    ) -> ValidationReport:
        """Ejecuta todas las validaciones V-MD-01 a V-MD-12.

        Args:
            design:   MethodologicalDesign a validar.
            activity: PlannedActivity asociada (necesaria para V-MD-02, V-MD-04, V-MD-05, V-MD-06).
                      Si es None, esas validaciones se emiten como WARNING (no puede verificarse).

        Returns:
            ValidationReport con todos los resultados.
        """
        results: list[ValidationResult] = []

        results.extend(self._vmd_01(design, activity))
        results.extend(self._vmd_02(design, activity))
        results.extend(self._vmd_03(design, activity))
        results.extend(self._vmd_04(design, activity))
        results.extend(self._vmd_05(design, activity))
        results.extend(self._vmd_06(design, activity))
        results.extend(self._vmd_07(design))
        results.extend(self._vmd_08(design))
        results.extend(self._vmd_09(design))
        results.extend(self._vmd_10(design))
        results.extend(self._vmd_11(design))
        results.extend(self._vmd_12(design, activity))

        return ValidationReport(results=results)

    # -----------------------------------------------------------------------
    # V-MD-01 — Actividad obligatoria: planned_activity_ref resoluble
    # Estado: CONFIRMADA (FASE_29_2 §15)
    # -----------------------------------------------------------------------
    def _vmd_01(
        self,
        design: MethodologicalDesign,
        activity: Optional[PlannedActivity] = None,
    ) -> list[ValidationResult]:
        """V-MD-01: planned_activity_ref no vacio y resoluble."""
        if not design.planned_activity_ref or not design.planned_activity_ref.strip():
            return [ValidationResult(
                rule_id="V-MD-01",
                severity=ValidationSeverity.ERROR,
                field="planned_activity_ref",
                message=(
                    "V-MD-01: planned_activity_ref es obligatorio. "
                    "El diseno debe estar asociado a una actividad planificada."
                ),
            )]
        if activity is not None:
            if (
                design.planned_activity_internal_id is not None
                and design.planned_activity_internal_id != activity.activity_internal_id
            ):
                return [ValidationResult(
                    rule_id="V-MD-01",
                    severity=ValidationSeverity.ERROR,
                    field="planned_activity_internal_id",
                    message="V-MD-01: planned_activity_internal_id no coincide con la actividad.",
                )]
            if design.planned_activity_ref != activity.planning_id:
                return [ValidationResult(
                    rule_id="V-MD-01",
                    severity=ValidationSeverity.ERROR,
                    field="planned_activity_ref",
                    message="V-MD-01: planned_activity_ref no coincide con la actividad.",
                )]
        return []

    # -----------------------------------------------------------------------
    # V-MD-02 — Sede valida: no vacio
    # Estado: CONFIRMADA (FASE_29_2 §15)
    # -----------------------------------------------------------------------
    def _vmd_02(
        self,
        design: MethodologicalDesign,
        activity: Optional[PlannedActivity],
    ) -> list[ValidationResult]:
        """V-MD-02: sede no vacia en la actividad asociada."""
        if activity is None:
            return [ValidationResult(
                rule_id="V-MD-02",
                severity=ValidationSeverity.WARNING,
                field="sede",
                message=(
                    "V-MD-02: No se puede verificar sede porque no se proporciono "
                    "la PlannedActivity asociada."
                ),
            )]
        if not activity.sede or not activity.sede.strip():
            return [ValidationResult(
                rule_id="V-MD-02",
                severity=ValidationSeverity.ERROR,
                field="sede",
                message="V-MD-02: sede de la actividad no puede ser vacia.",
            )]
        return []

    # -----------------------------------------------------------------------
    # V-MD-03 — Codigo presupuestario coherente (si presente)
    # Estado: PROPUESTA (FASE_29_2 §15) — Warning, no error critico
    # -----------------------------------------------------------------------
    def _vmd_03(
        self,
        design: MethodologicalDesign,
        activity: Optional[PlannedActivity],
    ) -> list[ValidationResult]:
        """V-MD-03: Codigo presupuestario coherente si presente.

        Clasificacion: PROPUESTA (sin evidencia de formato obligatorio).
        Se emite WARNING si el codigo parece vacio o invalido, no ERROR.
        """
        if activity is None:
            return []
        if activity.codigo_presupuestario is not None:
            val = activity.codigo_presupuestario.strip()
            if not val:
                return [ValidationResult(
                    rule_id="V-MD-03",
                    severity=ValidationSeverity.WARNING,
                    field="codigo_presupuestario",
                    message=(
                        "V-MD-03: codigo_presupuestario esta presente pero es una cadena vacia. "
                        "Si no aplica, usar None."
                    ),
                )]
        return []

    # -----------------------------------------------------------------------
    # V-MD-04 — Eje estrategico en Catalogo C1
    # Estado: CONFIRMADA (FASE_29_2 §15)
    # -----------------------------------------------------------------------
    def _vmd_04(
        self,
        design: MethodologicalDesign,
        activity: Optional[PlannedActivity],
    ) -> list[ValidationResult]:
        """V-MD-04: eje_estrategia debe pertenecer al Catalogo C1."""
        if activity is None:
            return [ValidationResult(
                rule_id="V-MD-04",
                severity=ValidationSeverity.WARNING,
                field="eje_estrategia",
                message=(
                    "V-MD-04: No se puede verificar eje_estrategia sin PlannedActivity."
                ),
            )]
        if not InstitutionalRulesEngine.r08_validar_eje_estrategia(activity.eje_estrategia):
            return [ValidationResult(
                rule_id="V-MD-04",
                severity=ValidationSeverity.ERROR,
                field="eje_estrategia",
                message=(
                    f"V-MD-04: eje_estrategia '{activity.eje_estrategia}' no pertenece "
                    f"al Catalogo C1. Referencia: FASE_29_2 §13 (R-08)."
                ),
            )]
        return []

    # -----------------------------------------------------------------------
    # V-MD-05 — Meta de protagonistas > 0
    # Estado: CONFIRMADA (FASE_29_2 §15)
    # -----------------------------------------------------------------------
    def _vmd_05(
        self,
        design: MethodologicalDesign,
        activity: Optional[PlannedActivity],
    ) -> list[ValidationResult]:
        """V-MD-05: ParticipantGoals.total() debe ser > 0."""
        if activity is None:
            return [ValidationResult(
                rule_id="V-MD-05",
                severity=ValidationSeverity.WARNING,
                field="participant_goals",
                message=(
                    "V-MD-05: No se puede verificar participant_goals sin PlannedActivity."
                ),
            )]
        if activity.participant_goals.total() <= 0:
            return [ValidationResult(
                rule_id="V-MD-05",
                severity=ValidationSeverity.ERROR,
                field="participant_goals",
                message=(
                    "V-MD-05: La meta de protagonistas debe ser mayor que 0. "
                    "Referencia: FASE_29_2 §15."
                ),
            )]
        return []

    # -----------------------------------------------------------------------
    # V-MD-06 — Tipo de evento en Catalogo C4
    # Estado: CONFIRMADA (FASE_29_2 §15)
    # -----------------------------------------------------------------------
    def _vmd_06(
        self,
        design: MethodologicalDesign,
        activity: Optional[PlannedActivity],
    ) -> list[ValidationResult]:
        """V-MD-06: tipo_evento debe pertenecer al Catalogo C4."""
        if activity is None:
            return [ValidationResult(
                rule_id="V-MD-06",
                severity=ValidationSeverity.WARNING,
                field="tipo_evento",
                message=(
                    "V-MD-06: No se puede verificar tipo_evento sin PlannedActivity."
                ),
            )]
        if not InstitutionalRulesEngine.r08_validar_tipo_evento(activity.tipo_evento):
            return [ValidationResult(
                rule_id="V-MD-06",
                severity=ValidationSeverity.ERROR,
                field="tipo_evento",
                message=(
                    f"V-MD-06: tipo_evento '{activity.tipo_evento}' no pertenece "
                    f"al Catalogo C4. Referencia: FASE_29_2 §13 (R-08)."
                ),
            )]
        return []

    # -----------------------------------------------------------------------
    # V-MD-07 — total_minutes > 0 y == Σ(agenda.minutes)
    # Estado: CONFIRMADA (FASE_29_2 §15) — R-05
    # -----------------------------------------------------------------------
    def _vmd_07(self, design: MethodologicalDesign) -> list[ValidationResult]:
        """V-MD-07: total_minutes > 0 y == Σ(agenda.minutes).

        Clasificacion: REGLA MATEMATICA — EVIDENCIA DIRECTA (R-05).
        """
        results = []
        total = design.total_minutes

        if total <= 0:
            results.append(ValidationResult(
                rule_id="V-MD-07",
                severity=ValidationSeverity.ERROR,
                field="agenda",
                message=(
                    f"V-MD-07: total_minutes calculado es {total}. "
                    "La agenda debe tener al menos un bloque con duracion positiva."
                ),
            ))

        if not design.agenda:
            results.append(ValidationResult(
                rule_id="V-MD-07",
                severity=ValidationSeverity.ERROR,
                field="agenda",
                message="V-MD-07: La agenda no puede estar vacia (sin bloques de tiempo).",
            ))
        return results

    # -----------------------------------------------------------------------
    # V-MD-08 — len(agenda) == len(matrix) y tiempos iguales para todo i
    # Estado: CONFIRMADA (FASE_29_2 §15) — R-06
    # -----------------------------------------------------------------------
    def _vmd_08(self, design: MethodologicalDesign) -> list[ValidationResult]:
        """V-MD-08: Agenda y Matriz Operacional deben ser congruentes (R-06).

        Clasificacion: REGLA MATEMATICA — EVIDENCIA DIRECTA (R-06).
        """
        results = []

        if len(design.agenda) != len(design.operational_matrix):
            results.append(ValidationResult(
                rule_id="V-MD-08",
                severity=ValidationSeverity.ERROR,
                field="operational_matrix",
                message=(
                    f"V-MD-08: Tabla 2 (agenda) tiene {len(design.agenda)} bloques "
                    f"pero Tabla 3 (matriz) tiene {len(design.operational_matrix)}. "
                    "Deben ser iguales (R-06)."
                ),
            ))
            return results  # Si longitudes difieren, no se puede verificar tiempos

        agenda_min = [tb.minutes for tb in design.agenda]
        matrix_min = [oa.minutes for oa in design.operational_matrix]
        ok = InstitutionalRulesEngine.verify_mirror_t2_t3(agenda_min, matrix_min)

        if not ok:
            discrepancias = [
                f"posicion {i+1}: agenda={a}, matriz={m}"
                for i, (a, m) in enumerate(zip(agenda_min, matrix_min))
                if a != m
            ]
            results.append(ValidationResult(
                rule_id="V-MD-08",
                severity=ValidationSeverity.ERROR,
                field="operational_matrix",
                message=(
                    "V-MD-08: Los tiempos de Tabla 2 y Tabla 3 no coinciden (R-06). "
                    f"Discrepancias: {'; '.join(discrepancias)}."
                ),
            ))
        return results

    # -----------------------------------------------------------------------
    # V-MD-09 — Todos los campos obligatorios no vacios
    # Estado: CONFIRMADA (FASE_29_2 §15)
    # -----------------------------------------------------------------------
    def _vmd_09(self, design: MethodologicalDesign) -> list[ValidationResult]:
        """V-MD-09: Los campos obligatorios del diseno no pueden estar vacios."""
        results = []

        if not design.introduction_text or not design.introduction_text.strip():
            results.append(ValidationResult(
                rule_id="V-MD-09",
                severity=ValidationSeverity.ERROR,
                field="introduction_text",
                message="V-MD-09: introduction_text es obligatorio.",
            ))

        if not design.methodological_approach or not design.methodological_approach.strip():
            results.append(ValidationResult(
                rule_id="V-MD-09",
                severity=ValidationSeverity.ERROR,
                field="methodological_approach",
                message="V-MD-09: methodological_approach es obligatorio.",
            ))

        if design.faq_table is None:
            results.append(ValidationResult(
                rule_id="V-MD-09",
                severity=ValidationSeverity.ERROR,
                field="faq_table",
                message="V-MD-09: faq_table es obligatoria (Bloque 3 — 7 preguntas fijas).",
            ))

        return results

    # -----------------------------------------------------------------------
    # V-MD-10 — Ninguna propuesta IA con accepted=None en campos exportados
    # Estado: CONFIRMADA (FASE_29_2 §15)
    # -----------------------------------------------------------------------
    def _vmd_10(self, design: MethodologicalDesign) -> list[ValidationResult]:
        """V-MD-10: No debe haber propuestas de IA sin revisar.

        Si existe alguna propuesta con accepted=None, el diseno no puede exportarse
        porque no se sabe si el contenido es IA sin revision humana.
        """
        pending = [p for p in design.ai_proposals if p.is_pending_review]
        if pending:
            return [ValidationResult(
                rule_id="V-MD-10",
                severity=ValidationSeverity.ERROR,
                field="ai_proposals",
                message=(
                    f"V-MD-10: Hay {len(pending)} propuesta(s) de IA sin revisar. "
                    "Todas las propuestas deben ser aceptadas o rechazadas antes de exportar."
                ),
            )]
        return []

    # -----------------------------------------------------------------------
    # V-MD-11 — len(objectives) == 2
    # Estado: CONFIRMADA (FASE_29_2 §15) — R-07
    # -----------------------------------------------------------------------
    def _vmd_11(self, design: MethodologicalDesign) -> list[ValidationResult]:
        """V-MD-11: Exactamente 2 objetivos especificos (R-07).

        Clasificacion: CONFIRMADA — EVIDENCIA DIRECTA.
        """
        n = len(design.objectives)
        if n != 2:
            return [ValidationResult(
                rule_id="V-MD-11",
                severity=ValidationSeverity.ERROR,
                field="objectives",
                message=(
                    f"V-MD-11: Se requieren exactamente 2 objetivos especificos (R-07). "
                    f"Encontrados: {n}."
                ),
            )]
        # Verificar que los objetivos no esten vacios
        errors = []
        for i, obj in enumerate(design.objectives, start=1):
            if not obj or not str(obj).strip():
                errors.append(ValidationResult(
                    rule_id="V-MD-11",
                    severity=ValidationSeverity.ERROR,
                    field=f"objectives[{i}]",
                    message=f"V-MD-11: El objetivo {i} no puede estar vacio.",
                ))
        return errors

    # -----------------------------------------------------------------------
    # V-MD-12 — programa in C2 o otro_programa presente
    # Estado: PROPUESTA (FASE_29_2 §15)
    # -----------------------------------------------------------------------
    def _vmd_12(
        self,
        design: MethodologicalDesign,
        activity: Optional[PlannedActivity],
    ) -> list[ValidationResult]:
        """V-MD-12: programa pertenece a C2 o se proporciona otro_programa.

        Clasificacion: PROPUESTA (FASE_29_2 §15).
        """
        if activity is None:
            return []

        programa_valido = InstitutionalRulesEngine.r08_validar_programa(activity.programa)
        otro_presente = bool(activity.otro_programa and activity.otro_programa.strip())

        if not programa_valido and not otro_presente:
            return [ValidationResult(
                rule_id="V-MD-12",
                severity=ValidationSeverity.ERROR,
                field="programa",
                message=(
                    f"V-MD-12: programa '{activity.programa}' no pertenece al Catalogo C2 "
                    "y no se proporciono otro_programa alternativo. "
                    "Referencia: FASE_29_2 §15."
                ),
            )]
        return []
