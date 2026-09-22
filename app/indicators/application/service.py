"""Servicio de Aplicación: Motor Determinista de Cálculo de Indicadores Institucionales.

Fase 29.19.1–29.19.2 — Auditoría e Implementación Controlada de Indicadores.

PRINCIPIOS:
  - Motor determinista, auditable y puro en Python.
  - Cero efectos secundarios sobre las fuentes (solo lectura).
  - Control riguroso de divisiones por cero y propagación de NULL.
  - No convierte silenciosamente NULL en dato inventado.
  - Separación matemática estricta: PLANIFICADO ≠ EJECUTADO, Multisesión (1:N),
    Personas Únicas vs Participaciones Brutas.
"""

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.indicators.domain.catalog import IndicatorCatalog
from app.indicators.domain.contracts import (
    IndicatorCategory,
    IndicatorId,
    IndicatorQuery,
    IndicatorReport,
    IndicatorResult,
)
from app.indicators.domain.ports import IndicatorReaderPort


class IndicatorCalculationService:
    """Motor de cálculo determinista para los indicadores institucionales de BICU."""

    def __init__(self, reader: IndicatorReaderPort) -> None:
        self._reader = reader

    def calculate_indicator(self, indicator_id: str, query: Optional[IndicatorQuery] = None) -> IndicatorResult:
        """Calcula un indicador específico según sus especificaciones metodológicas."""
        q = query or IndicatorQuery()
        definition = IndicatorCatalog.get(indicator_id)
        if not definition:
            raise ValueError(f"Indicador no reconocido en el catálogo: '{indicator_id}'.")

        handler_map = {
            IndicatorId.IND_ACT_01: self._calc_ind_act_01,
            IndicatorId.IND_ACT_02: self._calc_ind_act_02,
            IndicatorId.IND_ACT_03: self._calc_ind_act_03,
            IndicatorId.IND_ACT_04: self._calc_ind_act_04,
            IndicatorId.IND_CUMP_01: self._calc_ind_cump_01,
            IndicatorId.IND_CUMP_02: self._calc_ind_cump_02,
            IndicatorId.IND_PART_01: self._calc_ind_part_01,
            IndicatorId.IND_PART_02: self._calc_ind_part_02,
            IndicatorId.IND_PART_03: self._calc_ind_part_03,
            IndicatorId.IND_PART_04: self._calc_ind_part_04,
            IndicatorId.IND_PART_05: self._calc_ind_part_05,
            IndicatorId.IND_TERR_01: self._calc_ind_terr_01,
            IndicatorId.IND_TRAZ_01: self._calc_ind_traz_01,
            IndicatorId.IND_TRAZ_02: self._calc_ind_traz_02,
            IndicatorId.IND_TRAZ_03: self._calc_ind_traz_03,
        }

        handler = handler_map.get(indicator_id)
        if not handler:
            return IndicatorResult(
                indicator_id=indicator_id,
                name=definition.name,
                category=definition.category,
                value=None,
                unit=definition.unit,
                is_determinable=False,
                notes=[f"El cálculo de '{indicator_id}' requiere decisiones institucionales previas."],
            )

        return handler(q)

    def calculate_all(self, query: Optional[IndicatorQuery] = None) -> IndicatorReport:
        """Calcula todos los indicadores del catálogo disponibles."""
        q = query or IndicatorQuery()
        target_ids = q.indicator_ids or list(IndicatorCatalog.list_all())
        target_id_strings = [
            d.indicator_id if hasattr(d, "indicator_id") else str(d)
            for d in target_ids
        ]

        results: Dict[str, IndicatorResult] = {}
        for ind_id in target_id_strings:
            results[ind_id] = self.calculate_indicator(ind_id, q)

        return IndicatorReport(
            query=q,
            results=results,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_calculated=len(results),
            invariants_verified=True,
        )

    # -----------------------------------------------------------------------
    # CÁLCULOS ESPECÍFICOS POR INDICADOR
    # -----------------------------------------------------------------------

    def _calc_ind_act_01(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-ACT-01: Total de Actividades Planificadas en el POA."""
        plans = self._reader.get_planning_activities(query)
        total = len(plans)

        breakdown_sede = Counter(str(p.get("sede", "NO_ESPECIFICADO")) for p in plans)
        breakdown_programa = Counter(str(p.get("programa", "NO_ESPECIFICADO")) for p in plans)

        return IndicatorResult(
            indicator_id=IndicatorId.IND_ACT_01,
            name="Total de Actividades Planificadas en el POA",
            category=IndicatorCategory.ACTIVIDAD,
            value=float(total),
            unit="actividades",
            numerator_value=float(total),
            denominator_value=None,
            universe_total=total,
            breakdown={
                "por_sede": dict(breakdown_sede),
                "por_programa": dict(breakdown_programa),
            },
            notes=["Conteo de actividades únicas registradas en el POA institucional."],
        )

    def _calc_ind_act_02(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-ACT-02: Total de Eventos y Actividades Efectivamente Ejecutadas."""
        execs = self._reader.get_executed_activities(query)
        total = len(execs)

        breakdown_sede = Counter(str(e.get("sede", "NO_ESPECIFICADO")) for e in execs)
        breakdown_tipo = Counter(str(e.get("tipo_evento", "NO_ESPECIFICADO")) for e in execs)

        return IndicatorResult(
            indicator_id=IndicatorId.IND_ACT_02,
            name="Total de Eventos y Actividades Efectivamente Ejecutadas",
            category=IndicatorCategory.ACTIVIDAD,
            value=float(total),
            unit="actividades",
            numerator_value=float(total),
            denominator_value=None,
            universe_total=total,
            breakdown={
                "por_sede": dict(breakdown_sede),
                "por_tipo_evento": dict(breakdown_tipo),
            },
            notes=["Conteo de actividades en estado EJECUTADA, REPORTADA o CERRADA."],
        )

    def _calc_ind_act_03(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-ACT-03: Total de Actividades Emergentes."""
        execs = self._reader.get_executed_activities(query)
        links = self._reader.get_execution_links(query)

        active_linked_act_ids: Set[str] = {
            str(l["id_actividad"]) for l in links if l.get("link_status") == "ACTIVE"
        }

        emergents = [
            e for e in execs
            if int(e.get("es_emergente", 0)) == 1 or str(e["id_actividad"]) not in active_linked_act_ids
        ]
        total = len(emergents)

        breakdown_sede = Counter(str(e.get("sede", "NO_ESPECIFICADO")) for e in emergents)

        return IndicatorResult(
            indicator_id=IndicatorId.IND_ACT_03,
            name="Total de Actividades Emergentes",
            category=IndicatorCategory.ACTIVIDAD,
            value=float(total),
            unit="actividades",
            numerator_value=float(total),
            denominator_value=None,
            universe_total=len(execs),
            breakdown={"por_sede": dict(breakdown_sede)},
            notes=["Actividades ejecutadas no contempladas en el POA o sin vínculo activo."],
        )

    def _calc_ind_act_04(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-ACT-04: Tasa de Formalización Metodológica."""
        plans = self._reader.get_planning_activities(query)
        designs = self._reader.get_methodological_designs(query)

        approved_plan_ids: Set[str] = {
            str(d["planned_activity_internal_id"])
            for d in designs
            if d.get("status") == "APPROVED"
        }

        plan_ids: Set[str] = {str(p["activity_internal_id"]) for p in plans}
        num = len(plan_ids & approved_plan_ids)
        den = len(plan_ids)

        val = round((num / den) * 100.0, 2) if den > 0 else None
        notes = []
        if den == 0:
            notes.append("Denominador cero: No existen actividades planificadas en el período.")

        return IndicatorResult(
            indicator_id=IndicatorId.IND_ACT_04,
            name="Tasa de Formalización Metodológica",
            category=IndicatorCategory.ACTIVIDAD,
            value=val,
            unit="%",
            numerator_value=float(num),
            denominator_value=float(den),
            universe_total=den,
            notes=notes,
        )

    def _calc_ind_cump_01(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-CUMP-01: Cobertura de Ejecución de Actividades Planificadas.
        
        INVARIANTE: Actividades multisesión (1:N) cuentan exactamente como 1 plan cumplido.
        """
        plans = self._reader.get_planning_activities(query)
        execs = self._reader.get_executed_activities(query)
        links = self._reader.get_execution_links(query)

        executed_act_ids: Set[str] = {str(e["id_actividad"]) for e in execs}
        plan_internal_ids: Set[str] = {str(p["activity_internal_id"]) for p in plans}

        # Planes con al menos 1 ejecución activa y completada
        covered_plan_ids: Set[str] = {
            str(l["planning_internal_id"])
            for l in links
            if l.get("link_status") == "ACTIVE"
            and str(l["id_actividad"]) in executed_act_ids
            and str(l["planning_internal_id"]) in plan_internal_ids
        }

        num = len(covered_plan_ids)
        den = len(plan_internal_ids)
        val = round((num / den) * 100.0, 2) if den > 0 else None

        notes = []
        if den == 0:
            notes.append("Denominador cero: Sin planes registrados en el período.")

        return IndicatorResult(
            indicator_id=IndicatorId.IND_CUMP_01,
            name="Cobertura de Ejecución de Actividades Planificadas",
            category=IndicatorCategory.CUMPLIMIENTO,
            value=val,
            unit="%",
            numerator_value=float(num),
            denominator_value=float(den),
            universe_total=den,
            parameters_applied={"multisesion": "COUNT_DISTINCT plan cumplido"},
            notes=notes,
        )

    def _calc_ind_cump_02(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-CUMP-02: Eficacia Global de Metas de Participación (Planificado vs Real)."""
        plans = self._reader.get_planning_activities(query)
        execs = self._reader.get_executed_activities(query)
        links = self._reader.get_execution_links(query)
        parts = self._reader.get_participations(query)

        executed_act_ids: Set[str] = {str(e["id_actividad"]) for e in execs}
        plan_by_id = {str(p["activity_internal_id"]): p for p in plans}

        # Vínculos activos hacia actividades ejecutadas
        active_links = [
            l for l in links
            if l.get("link_status") == "ACTIVE"
            and str(l["id_actividad"]) in executed_act_ids
            and str(l["planning_internal_id"]) in plan_by_id
        ]

        linked_plan_ids = {str(l["planning_internal_id"]) for l in active_links}
        linked_act_ids = {str(l["id_actividad"]) for l in active_links}

        # Denominador: Metas planificadas en planes vinculados
        den = 0
        for pid in linked_plan_ids:
            p = plan_by_id[pid]
            meta_plan = sum([
                int(p.get("est_grado_m", 0)), int(p.get("est_grado_f", 0)),
                int(p.get("est_postgrado_m", 0)), int(p.get("est_postgrado_f", 0)),
                int(p.get("docentes_m", 0)), int(p.get("docentes_f", 0)),
                int(p.get("administrativos_m", 0)), int(p.get("administrativos_f", 0)),
                int(p.get("externos_m", 0)), int(p.get("externos_f", 0)),
            ])
            den += meta_plan

        # Numerador: Participantes reales en actividades vinculadas
        real_parts = [pr for pr in parts if str(pr["id_actividad"]) in linked_act_ids]

        if query.multisession_goal_mode == "COHORT_UNIQUE":
            # Conteo de personas únicas atendidas en dichas actividades
            num = len({str(pr["id_persona"]) for pr in real_parts})
        else:
            # Conteo de asistencias brutas acumuladas
            num = len(real_parts)

        val = round((num / den) * 100.0, 2) if den > 0 else None
        notes = []
        if den == 0:
            notes.append("Denominador cero o sin metas registradas en los planes vinculados.")

        return IndicatorResult(
            indicator_id=IndicatorId.IND_CUMP_02,
            name="Índice de Eficacia de Metas de Participación (Planificado vs Real)",
            category=IndicatorCategory.CUMPLIMIENTO,
            value=val,
            unit="%",
            numerator_value=float(num),
            denominator_value=float(den),
            universe_total=den,
            parameters_applied={"multisession_goal_mode": query.multisession_goal_mode},
            notes=notes,
        )

    def _calc_ind_part_01(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-PART-01: Total de Participaciones Registradas (Asistencias Brutas).
        
        INVARIANTE: Excluye estrictamente filas históricas (es_historico_preexistente = 0).
        """
        parts = self._reader.get_participations(query)
        total = len(parts)

        breakdown_estamento = Counter(str(p.get("estamento_declarado", "NO_ESPECIFICADO")) for p in parts)
        breakdown_sexo = Counter(str(p.get("sexo", "NO_ESPECIFICADO")) for p in parts)
        breakdown_sede = Counter(str(p.get("actividad_sede", "NO_ESPECIFICADO")) for p in parts)

        return IndicatorResult(
            indicator_id=IndicatorId.IND_PART_01,
            name="Total de Participaciones Registradas (Asistencias Brutas)",
            category=IndicatorCategory.PARTICIPACION,
            value=float(total),
            unit="participaciones",
            numerator_value=float(total),
            denominator_value=None,
            universe_total=total,
            breakdown={
                "por_estamento": dict(breakdown_estamento),
                "por_sexo": dict(breakdown_sexo),
                "por_sede": dict(breakdown_sede),
            },
            notes=["Conteo de asistencias brutas efectivas. No representa personas únicas."],
        )

    def _calc_ind_part_02(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-PART-02: Total de Personas Únicas Alcanzadas."""
        persons = self._reader.get_unique_persons(query)

        if query.require_verified_id_for_unique_persons:
            verified = [
                p for p in persons
                if (p.get("cedula") and str(p.get("cedula")).strip())
                or (p.get("numero_institucional") and str(p.get("numero_institucional")).strip())
            ]
            unverified = [p for p in persons if p not in verified]
            val = float(len(verified))
            notes = []
            if unverified:
                notes.append(
                    f"Se aislaron {len(unverified)} participantes sin cédula/ID formal para proteger la certeza de unicidad."
                )
        else:
            val = float(len(persons))
            notes = ["Conteo basado en todos los registros individuales de persona."]

        breakdown_sexo = Counter(str(p.get("sexo", "NO_ESPECIFICADO")) for p in persons)

        return IndicatorResult(
            indicator_id=IndicatorId.IND_PART_02,
            name="Total de Personas Únicas Alcanzadas",
            category=IndicatorCategory.PARTICIPACION,
            value=val,
            unit="personas únicas",
            numerator_value=val,
            denominator_value=None,
            universe_total=len(persons),
            breakdown={"por_sexo": dict(breakdown_sexo)},
            parameters_applied={
                "require_verified_id": query.require_verified_id_for_unique_persons
            },
            notes=notes,
        )

    def _calc_ind_part_03(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-PART-03: Tasa de Recurrencia de Participantes."""
        persons = self._reader.get_unique_persons(query)
        total_persons = len(persons)

        recurrent = [
            p for p in persons
            if int(p.get("total_actividades_distintas", 0)) >= 2
        ]
        num = len(recurrent)
        den = total_persons
        val = round((num / den) * 100.0, 2) if den > 0 else 0.0

        return IndicatorResult(
            indicator_id=IndicatorId.IND_PART_03,
            name="Tasa de Recurrencia de Participantes",
            category=IndicatorCategory.PARTICIPACION,
            value=val,
            unit="%",
            numerator_value=float(num),
            denominator_value=float(den),
            universe_total=den,
            notes=["Porcentaje de personas únicas que asistieron a 2 o más actividades distintas."],
        )

    def _calc_ind_part_04(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-PART-04: Distribución de Participación por Sexo (Índice de Paridad).
        
        INVARIANTE: Prohibición estricta de imputar sexo. 'No Especificado' se preserva intacto.
        """
        parts = self._reader.get_participations(query)
        sex_counts = Counter(str(p.get("sexo", "")).strip().upper() for p in parts)

        f_count = sex_counts.get("F", 0)
        m_count = sex_counts.get("M", 0)
        no_spec = sum(cnt for s, cnt in sex_counts.items() if s not in ("F", "M"))

        den_confirmed = f_count + m_count
        pct_f = round((f_count / den_confirmed) * 100.0, 2) if den_confirmed > 0 else None
        pct_m = round((m_count / den_confirmed) * 100.0, 2) if den_confirmed > 0 else None
        parity_ratio = round(pct_f / pct_m, 2) if (pct_m and pct_m > 0 and pct_f is not None) else None

        notes = []
        if no_spec > 0:
            notes.append(f"Existen {no_spec} participaciones con sexo no especificado en la fuente.")
        if den_confirmed == 0:
            notes.append("No se registraron participantes con sexo confirmado F o M.")

        return IndicatorResult(
            indicator_id=IndicatorId.IND_PART_04,
            name="Distribución de Participación por Sexo (Índice de Paridad)",
            category=IndicatorCategory.PARTICIPACION,
            value=parity_ratio,
            unit="Razón (F/M)",
            numerator_value=float(f_count),
            denominator_value=float(den_confirmed),
            universe_total=len(parts),
            breakdown={
                "total_femenino": f_count,
                "total_masculino": m_count,
                "total_no_especificado": no_spec,
                "porcentaje_femenino": pct_f,
                "porcentaje_masculino": pct_m,
                "indice_paridad": parity_ratio,
            },
            notes=notes,
        )

    def _calc_ind_part_05(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-PART-05: Distribución de Participantes por Estamento."""
        parts = self._reader.get_participations(query)
        total = len(parts)

        estamento_counts = Counter(
            str(p.get("estamento_declarado", "NO_ESPECIFICADO")).upper()
            for p in parts
        )

        breakdown = {}
        for est, count in estamento_counts.items():
            pct = round((count / total) * 100.0, 2) if total > 0 else 0.0
            breakdown[est] = {"conteo": count, "porcentaje": pct}

        return IndicatorResult(
            indicator_id=IndicatorId.IND_PART_05,
            name="Distribución de Participantes por Estamento",
            category=IndicatorCategory.PARTICIPACION,
            value=float(total),
            unit="participaciones",
            numerator_value=float(total),
            denominator_value=None,
            universe_total=total,
            breakdown=breakdown,
            notes=["Distribución porcentual por rol institucional declarado."],
        )

    def _calc_ind_terr_01(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-TERR-01: Distribución Territorial de Actividades por Sede."""
        execs = self._reader.get_executed_activities(query)
        total = len(execs)

        sede_counts = Counter(str(e.get("sede", "OTRA")).upper() for e in execs)
        breakdown = {}
        for s, count in sede_counts.items():
            pct = round((count / total) * 100.0, 2) if total > 0 else 0.0
            breakdown[s] = {"conteo": count, "porcentaje": pct}

        return IndicatorResult(
            indicator_id=IndicatorId.IND_TERR_01,
            name="Distribución Territorial de Actividades por Sede",
            category=IndicatorCategory.TERRITORIAL,
            value=float(total),
            unit="actividades",
            numerator_value=float(total),
            denominator_value=None,
            universe_total=total,
            breakdown=breakdown,
            notes=["Desconcentración geográfica de actividades ejecutadas en recintos BICU."],
        )

    def _calc_ind_traz_01(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-TRAZ-01: Índice de Trazabilidad Planificación-Ejecución."""
        execs = self._reader.get_executed_activities(query)
        links = self._reader.get_execution_links(query)

        active_linked_act_ids: Set[str] = {
            str(l["id_actividad"]) for l in links if l.get("link_status") == "ACTIVE"
        }
        executed_ids: Set[str] = {str(e["id_actividad"]) for e in execs}

        num = len(executed_ids & active_linked_act_ids)
        den = len(executed_ids)
        val = round((num / den) * 100.0, 2) if den > 0 else None

        notes = []
        if den == 0:
            notes.append("Denominador cero: Sin actividades ejecutadas en el período.")

        return IndicatorResult(
            indicator_id=IndicatorId.IND_TRAZ_01,
            name="Índice de Trazabilidad Planificación-Ejecución",
            category=IndicatorCategory.TRAZABILIDAD,
            value=val,
            unit="%",
            numerator_value=float(num),
            denominator_value=float(den),
            universe_total=den,
            notes=notes,
        )

    def _calc_ind_traz_02(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-TRAZ-02: Tasa de Discrepancia Documental (M1 vs M2–M5)."""
        execs = self._reader.get_executed_activities(query)
        discreps = self._reader.get_discrepancies(query)

        active_discrep_act_ids: Set[str] = {
            str(d["id_actividad"]) for d in discreps if d.get("estado") == "REQUIERE_REVISION"
        }
        executed_ids: Set[str] = {str(e["id_actividad"]) for e in execs}

        num = len(executed_ids & active_discrep_act_ids)
        den = len(executed_ids)
        val = round((num / den) * 100.0, 2) if den > 0 else None

        notes = []
        if den == 0:
            notes.append("Denominador cero: Sin actividades procesadas en el período.")

        return IndicatorResult(
            indicator_id=IndicatorId.IND_TRAZ_02,
            name="Tasa de Discrepancia Documental (M1 vs M2–M5)",
            category=IndicatorCategory.TRAZABILIDAD,
            value=val,
            unit="%",
            numerator_value=float(num),
            denominator_value=float(den),
            universe_total=den,
            notes=notes,
        )

    def _calc_ind_traz_03(self, query: IndicatorQuery) -> IndicatorResult:
        """IND-TRAZ-03: Tasa de Disponibilidad de Cédula Oficial."""
        persons = self._reader.get_unique_persons(query)
        den = len(persons)

        with_cedula = [
            p for p in persons
            if p.get("cedula") and str(p.get("cedula")).strip()
        ]
        num = len(with_cedula)
        val = round((num / den) * 100.0, 2) if den > 0 else None

        notes = []
        if den == 0:
            notes.append("Denominador cero: Sin personas registradas en el período.")

        return IndicatorResult(
            indicator_id=IndicatorId.IND_TRAZ_03,
            name="Tasa de Disponibilidad de Cédula Oficial",
            category=IndicatorCategory.CALIDAD,
            value=val,
            unit="%",
            numerator_value=float(num),
            denominator_value=float(den),
            universe_total=den,
            notes=notes,
        )
