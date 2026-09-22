"""app.reporting.application.reporting_service

Servicio de Aplicación: Núcleo Orquestador de Reporting y Dashboard Institucional BICU.
Fase 29.20.1 — Implementación Controlada del Núcleo Reporting Service.

PRINCIPIOS ARQUITECTÓNICOS INMUTABLES:
  1. DATOS ≠ INDICADORES ≠ REPORTES ≠ DASHBOARD ≠ INTERPRETACIONES
  2. PLANIFICADO ≠ EJECUTADO
  3. FUENTE ÚNICA DE VERDAD: Todo número emana exclusivamente de app/indicators/.
  4. CERO FÓRMULAS DUPLICADAS: Reporting compone y estructura; no calcula indicadores.
  5. CERO MUTACIONES: No escribe SQLite, no altera datos, no modifica V001-V004.
  6. AISLAMIENTO ABSOLUTO: No importa CustomTkinter, no importa Gemini, no importa Word Consolidator.
  7. MANEJO DEFENSIVO: Cero ZeroDivisionError; valores None se presentan como "N/D".
  8. MULTISESIÓN (1:N): 1 plan + N ejecuciones = 1 plan cumplido (max 100%).
  9. EMERGENTES: 0 aporte al cumplimiento POA; computan en volumen y territorio.
  10. M5 HISTÓRICO: Excluido estrictamente de reportes de período (es_historico_preexistente = 0).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.indicators.application.service import IndicatorCalculationService
from app.indicators.domain.contracts import IndicatorId, IndicatorQuery, IndicatorResult
from app.reporting.domain.enums import AlertStatus, MultisessionGoalMode, ReportType
from app.reporting.domain.dto import (
    ChartDatasetDTO,
    DashboardCardDTO,
    DashboardDataDTO,
    DashboardSectionDTO,
    ReportDocumentDTO,
    ReportFilterDTO,
    ReportMetricItemDTO,
    ReportSectionDTO,
)
from app.reporting.infrastructure.memory_cache import ReportingMemoryCache


class ReportingService:
    """Orquestador de composición y estructuración de reportes y dashboard institucional."""

    def __init__(
        self,
        indicator_service: IndicatorCalculationService,
        cache: Optional[ReportingMemoryCache] = None,
    ) -> None:
        self._indicator_service = indicator_service
        self._cache = cache or ReportingMemoryCache(default_ttl_seconds=60, enabled=True)

    # -----------------------------------------------------------------------
    # GENERACIÓN DE REPORTES INSTITUCIONALES (REP-01 a REP-05)
    # -----------------------------------------------------------------------

    def generate_report(
        self,
        report_type: ReportType,
        filters: Optional[ReportFilterDTO] = None,
    ) -> ReportDocumentDTO:
        """Compone y genera un informe oficial estructurado según su especificación."""
        f = filters or ReportFilterDTO()
        cache_key = self._cache.make_key(f"REPORT::{report_type.value}", f)
        cached = self._cache.get(cache_key)
        if cached is not None and isinstance(cached, ReportDocumentDTO):
            return cached

        q = self._to_indicator_query(f)

        handler_map = {
            ReportType.REP_01: self._build_rep_01_balance_ejecutivo,
            ReportType.REP_02: self._build_rep_02_cumplimiento_poa,
            ReportType.REP_03: self._build_rep_03_cobertura_demografica,
            ReportType.REP_04: self._build_rep_04_descentralizacion_territorial,
            ReportType.REP_05: self._build_rep_05_auditoria_trazabilidad,
        }

        handler = handler_map.get(report_type)
        if not handler:
            raise ValueError(f"Tipo de reporte no soportado: '{report_type}'.")

        document = handler(f, q)
        self._cache.set(cache_key, document)
        return document

    # -----------------------------------------------------------------------
    # PROVEEDOR DE DATOS PARA DASHBOARD INTERACTIVO (5 NIVELES)
    # -----------------------------------------------------------------------

    def get_dashboard_data(
        self,
        filters: Optional[ReportFilterDTO] = None,
    ) -> DashboardDataDTO:
        """Prepara y empaqueta el payload completo e inmutable para el Dashboard (Niveles 1 a 5).
        
        La futura vista CustomTkinter recibirá este DTO listo para pintar, sin realizar cálculos.
        """
        f = filters or ReportFilterDTO()
        cache_key = self._cache.make_key("DASHBOARD::FULL", f)
        cached = self._cache.get(cache_key)
        if cached is not None and isinstance(cached, DashboardDataDTO):
            return cached

        q = self._to_indicator_query(f)

        # 1. Consulta determinista a los 15 indicadores certificados
        act_01 = self._calc(IndicatorId.IND_ACT_01, q)
        act_02 = self._calc(IndicatorId.IND_ACT_02, q)
        act_03 = self._calc(IndicatorId.IND_ACT_03, q)
        act_04 = self._calc(IndicatorId.IND_ACT_04, q)
        cump_01 = self._calc(IndicatorId.IND_CUMP_01, q)
        cump_02 = self._calc(IndicatorId.IND_CUMP_02, q)
        part_01 = self._calc(IndicatorId.IND_PART_01, q)
        part_02 = self._calc(IndicatorId.IND_PART_02, q)
        part_03 = self._calc(IndicatorId.IND_PART_03, q)
        part_04 = self._calc(IndicatorId.IND_PART_04, q)
        part_05 = self._calc(IndicatorId.IND_PART_05, q)
        terr_01 = self._calc(IndicatorId.IND_TERR_01, q)
        traz_01 = self._calc(IndicatorId.IND_TRAZ_01, q)
        traz_02 = self._calc(IndicatorId.IND_TRAZ_02, q)
        traz_03 = self._calc(IndicatorId.IND_TRAZ_03, q)

        # 2. Tarjetas KPI de Resumen Ejecutivo (Nivel 1 Superior)
        card_poa = self._make_card(
            card_id="kpi_poa_plans",
            indicator_id=IndicatorId.IND_ACT_01,
            title="Actividades Planificadas POA",
            result=act_01,
            unit_label="planes",
            sub_label="Programadas en el POA",
            alert_status=AlertStatus.NEUTRAL,
            tooltip="Total de actividades registradas formalmente en el POA institucional.",
        )
        card_exec = self._make_card(
            card_id="kpi_executed_acts",
            indicator_id=IndicatorId.IND_ACT_02,
            title="Actividades Ejecutadas",
            result=act_02,
            unit_label="actividades",
            sub_label="Realizadas en territorio",
            alert_status=AlertStatus.NEUTRAL,
            tooltip="Volumen total de actividades en estado EJECUTADA, REPORTADA o CERRADA.",
        )
        card_emerg = self._make_card(
            card_id="kpi_emergent_acts",
            indicator_id=IndicatorId.IND_ACT_03,
            title="Actividades Emergentes",
            result=act_03,
            unit_label="actividades",
            sub_label="No contempladas en POA",
            alert_status=AlertStatus.YELLOW if (act_03.value or 0) > 0 else AlertStatus.NEUTRAL,
            tooltip="Actividades ejecutadas sin vínculo activo hacia el POA (0 aporte a cumplimiento).",
        )

        cump_01_alert = AlertStatus.NEUTRAL
        if cump_01.value is not None:
            cump_01_alert = AlertStatus.GREEN if cump_01.value >= 80.0 else (
                AlertStatus.YELLOW if cump_01.value >= 50.0 else AlertStatus.RED
            )

        card_cump = self._make_card(
            card_id="kpi_poa_coverage",
            indicator_id=IndicatorId.IND_CUMP_01,
            title="Cobertura de Planes POA",
            result=cump_01,
            unit_label="%",
            sub_label=f"{int(cump_01.numerator_value or 0)} de {int(cump_01.denominator_value or 0)} planes cumplidos",
            alert_status=cump_01_alert,
            tooltip="Porcentaje de planes del POA con al menos una ejecución trazada (Max 100% por plan).",
        )

        p1_val_str = self._format_count(part_01.value)
        p2_val_str = self._format_count(part_02.value)
        card_part = DashboardCardDTO(
            card_id="kpi_protagonists",
            indicator_id=IndicatorId.IND_PART_01,
            title="Protagonistas Atendidos",
            main_value=p1_val_str,
            unit_label="asistencias brutas",
            sub_label=f"{p2_val_str} personas únicas verificadas",
            alert_status=AlertStatus.NEUTRAL,
            tooltip_explanation="Asistencias brutas totales frente a personas únicas identificadas.",
            multisession_mode_applied=f.multisession_goal_mode,
            raw_value=part_01.value,
        )

        kpi_summary = [card_poa, card_exec, card_emerg, card_cump, card_part]

        # 3. Nivel 1: Resumen Ejecutivo
        lvl_1 = DashboardSectionDTO(
            section_id="level_1_summary",
            title="Nivel 1: Resumen Ejecutivo y Estado General",
            cards=kpi_summary,
            table_headers=["Indicador Clave", "Valor", "Unidad", "Estado"],
            table_rows=[
                ["Planes Planificados POA", card_poa.main_value, card_poa.unit_label, card_poa.alert_status.value],
                ["Eventos Ejecutados en Territorio", card_exec.main_value, card_exec.unit_label, card_exec.alert_status.value],
                ["Eventos Emergentes (Fuera de POA)", card_emerg.main_value, card_emerg.unit_label, card_emerg.alert_status.value],
                ["Cobertura de Ejecución POA", card_cump.main_value, card_cump.unit_label, card_cump.alert_status.value],
                ["Total Asistencias Brutas", p1_val_str, "participaciones", "INFORMACIÓN"],
                ["Total Personas Únicas", p2_val_str, "personas únicas", "INFORMACIÓN"],
            ],
            notes=[
                "Las actividades emergentes se reconocen como esfuerzo institucional pero no aumentan el cumplimiento del POA.",
                "Se excluyen estrictamente los 32 beneficiarios históricos preexistentes de M5.",
            ],
        )

        # 4. Nivel 2: Actividad y Cumplimiento
        card_formaliz = self._make_card(
            card_id="kpi_methodological_designs",
            indicator_id=IndicatorId.IND_ACT_04,
            title="Formalización Metodológica",
            result=act_04,
            unit_label="%",
            sub_label=f"{int(act_04.numerator_value or 0)} de {int(act_04.denominator_value or 0)} diseños aprobados",
            alert_status=AlertStatus.GREEN if (act_04.value or 0) >= 80.0 else AlertStatus.YELLOW,
            tooltip="Porcentaje de planes que cuentan con Diseño Metodológico formalmente aprobado.",
        )
        card_eficacia = self._make_card(
            card_id="kpi_participant_goals",
            indicator_id=IndicatorId.IND_CUMP_02,
            title="Eficacia de Metas Participantes",
            result=cump_02,
            unit_label="%",
            sub_label=f"Modo: {f.multisession_goal_mode}",
            alert_status=AlertStatus.GREEN if (cump_02.value or 0) >= 80.0 else AlertStatus.YELLOW,
            tooltip="Razón entre participantes reales y meta planificada según modo de meta.",
            multisession_mode=f.multisession_goal_mode,
        )

        # Gráfico Nivel 2: Comparativa Planificado vs Ejecutado vs Emergente
        chart_act = ChartDatasetDTO(
            chart_type="BAR",
            title="Volumen de Actividades: Planificado vs Ejecutado",
            labels=["Planificadas POA", "Ejecutadas en Territorio", "Emergentes"],
            values=[act_01.value or 0.0, act_02.value or 0.0, act_03.value or 0.0],
        )

        # Gráfico por Tipo de Evento
        tipo_breakdown = act_02.breakdown.get("por_tipo_evento", {})
        chart_tipos = ChartDatasetDTO(
            chart_type="BAR",
            title="Ejecución por Tipo de Evento",
            labels=list(tipo_breakdown.keys()),
            values=[float(v) for v in tipo_breakdown.values()],
        )

        lvl_2 = DashboardSectionDTO(
            section_id="level_2_activity",
            title="Nivel 2: Actividad y Cumplimiento de Metas",
            cards=[card_poa, card_exec, card_cump, card_formaliz, card_eficacia],
            charts=[chart_act, chart_tipos],
            table_headers=["Cuadrante Operativo", "Concepto", "Cantidad", "Aporte al POA"],
            table_rows=[
                ["Cuadrante 1", "Planes con Ejecución Activa (Trazados)", str(int(cump_01.numerator_value or 0)), "Aporta al cumplimiento"],
                ["Cuadrante 2", "Planes Pendientes de Ejecución al Corte", str(int(max(0, (cump_01.denominator_value or 0) - (cump_01.numerator_value or 0)))), "0 aporte al cumplimiento"],
                ["Cuadrante 3", "Acciones Extraordinarias / Emergentes", str(int(act_03.value or 0)), "0 aporte al cumplimiento"],
                ["Cuadrante 4", "Total Ejecutadas en Territorio", str(int(act_02.value or 0)), "Volumen real"],
            ],
            notes=[
                f"Modo multisesión de meta activo: {f.multisession_goal_mode}.",
                "Regla 1:N: Un plan con múltiples sesiones de ejecución equivale como máximo a 1 plan cumplido (100%).",
            ],
        )

        # 5. Nivel 3: Audiencia y Demografía
        card_recurrence = self._make_card(
            card_id="kpi_recurrence_rate",
            indicator_id=IndicatorId.IND_PART_03,
            title="Tasa de Recurrencia",
            result=part_03,
            unit_label="%",
            sub_label="Asistieron a >= 2 actividades",
            alert_status=AlertStatus.NEUTRAL,
            tooltip="Porcentaje de personas únicas que participaron en más de un evento.",
        )
        card_parity = self._make_card(
            card_id="kpi_gender_parity",
            indicator_id=IndicatorId.IND_PART_04,
            title="Índice de Paridad de Género",
            result=part_04,
            unit_label="Razón F/M",
            sub_label=f"F: {part_04.breakdown.get('total_femenino', 0)} | M: {part_04.breakdown.get('total_masculino', 0)}",
            alert_status=AlertStatus.GREEN if (0.8 <= (part_04.value or 0) <= 1.25) else AlertStatus.NEUTRAL,
            tooltip="Razón entre participación femenina y masculina. Prohibida la imputación de nulos.",
        )

        # Gráfico Composición Sexo
        sex_labels = ["Femenino", "Masculino", "No Especificado"]
        sex_values = [
            float(part_04.breakdown.get("total_femenino", 0)),
            float(part_04.breakdown.get("total_masculino", 0)),
            float(part_04.breakdown.get("total_no_especificado", 0)),
        ]
        chart_sex = ChartDatasetDTO(
            chart_type="PIE",
            title="Composición por Sexo (Sin Imputación)",
            labels=sex_labels,
            values=sex_values,
        )

        # Gráfico Estamentos
        est_bk = part_05.breakdown
        chart_est = ChartDatasetDTO(
            chart_type="BAR",
            title="Participación por Estamento Declarado",
            labels=list(est_bk.keys()),
            values=[float(v.get("conteo", 0)) for v in est_bk.values()],
        )

        lvl_3 = DashboardSectionDTO(
            section_id="level_3_demography",
            title="Nivel 3: Audiencia y Demografía de Protagonistas",
            cards=[card_part, card_recurrence, card_parity],
            charts=[chart_sex, chart_est],
            table_headers=["Estamento", "Participaciones", "Porcentaje"],
            table_rows=[
                [est, str(v.get("conteo", 0)), f"{v.get('porcentaje', 0.0):.2f}%"]
                for est, v in est_bk.items()
            ],
            notes=[
                "Prohibición estricta de imputar sexo. Las casillas vacías se reportan como 'No Especificado'.",
                f"Cálculo de personas únicas con criterio de cédula requerida: {f.require_verified_id_for_unique_persons}.",
            ],
        )

        # 6. Nivel 4: Cobertura Territorial
        terr_bk = terr_01.breakdown
        chart_sedes = ChartDatasetDTO(
            chart_type="BAR",
            title="Concentración Territorial por Sede Institucional",
            labels=list(terr_bk.keys()),
            values=[float(v.get("conteo", 0)) for v in terr_bk.values()],
        )

        sedes_activas = sum(1 for v in terr_bk.values() if v.get("conteo", 0) > 0)
        card_sedes = DashboardCardDTO(
            card_id="kpi_active_sedes",
            indicator_id=IndicatorId.IND_TERR_01,
            title="Sedes Institucionales con Actividad",
            main_value=str(sedes_activas),
            unit_label="sedes",
            sub_label=f"De {len(terr_bk)} sedes relacionales V001",
            alert_status=AlertStatus.NEUTRAL,
            tooltip_explanation="Sedes con al menos 1 actividad ejecutada en el período.",
            raw_value=float(sedes_activas),
        )

        lvl_4 = DashboardSectionDTO(
            section_id="level_4_territory",
            title="Nivel 4: Cobertura y Descentralización Territorial",
            cards=[card_sedes],
            charts=[chart_sedes],
            table_headers=["Sede Institucional (DDL V001)", "Actividades Ejecutadas", "Porcentaje de Concentración"],
            table_rows=[
                [s, str(v.get("conteo", 0)), f"{v.get('porcentaje', 0.0):.2f}%"]
                for s, v in terr_bk.items()
            ],
            notes=[
                "Las sedes corresponden al CHECK constraint de la tabla actividad en SQLite V001.",
                "No se asume un catálogo dogmático de 9 recintos (DEC-CAT-01 pendiente de homologación).",
                "Municipios no consignados en la fuente se presentan como 'Municipio No Especificado'.",
            ],
        )

        # 7. Nivel 5: Trazabilidad y Salud del Dato
        card_traz = self._make_card(
            card_id="kpi_traceability_index",
            indicator_id=IndicatorId.IND_TRAZ_01,
            title="Índice de Trazabilidad Plan-Ejecución",
            result=traz_01,
            unit_label="%",
            sub_label=f"{int(traz_01.numerator_value or 0)} de {int(traz_01.denominator_value or 0)} ejecutadas con enlace ACTIVE",
            alert_status=AlertStatus.GREEN if (traz_01.value or 0) >= 80.0 else AlertStatus.YELLOW,
            tooltip="Porcentaje de actividades ejecutadas que cuentan con vínculo ACTIVE hacia el POA.",
        )
        card_discrep = self._make_card(
            card_id="kpi_discrepancy_rate",
            indicator_id=IndicatorId.IND_TRAZ_02,
            title="Tasa de Discrepancia Documental",
            result=traz_02,
            unit_label="%",
            sub_label=f"{int(traz_02.numerator_value or 0)} actividades observadas",
            alert_status=AlertStatus.GREEN if (traz_02.value or 0) == 0.0 else AlertStatus.RED,
            tooltip="Porcentaje de actividades donde la Ficha macro difiere de las listas de firmas M2-M5.",
        )
        card_cedulas = self._make_card(
            card_id="kpi_id_availability",
            indicator_id=IndicatorId.IND_TRAZ_03,
            title="Disponibilidad de Cédula Oficial",
            result=traz_03,
            unit_label="%",
            sub_label=f"{int(traz_03.numerator_value or 0)} de {int(traz_03.denominator_value or 0)} con cédula registrada",
            alert_status=AlertStatus.GREEN if (traz_03.value or 0) >= 80.0 else AlertStatus.YELLOW,
            tooltip="Proporción de personas registradas que cuentan con documento de identidad nacional.",
        )

        lvl_5 = DashboardSectionDTO(
            section_id="level_5_traceability",
            title="Nivel 5: Auditoría de Trazabilidad, Gobernanza y Salud del Dato",
            cards=[card_traz, card_discrep, card_cedulas],
            charts=[],
            table_headers=["Control de Calidad", "Resultado", "Estado de Alerta", "Criterio de Validación"],
            table_rows=[
                ["Trazabilidad V004 (Vínculos ACTIVE)", card_traz.main_value, card_traz.alert_status.value, "Vínculos REVOKED/SUPERSEDED se excluyen"],
                ["Discrepancia Documental M1 vs M2-M5", card_discrep.main_value, card_discrep.alert_status.value, "0.00% requerido para auditoría limpia"],
                ["Disponibilidad de Cédula de Identidad", card_cedulas.main_value, card_cedulas.alert_status.value, "Garantía de unicidad pericial"],
            ],
            notes=[
                "Los enlaces en estado REVOKED y SUPERSEDED no suman al numerador de trazabilidad.",
                "Persistencia relacional SQLite permanece inmutable en esquema V004 (sin V005).",
            ],
        )

        # 8. Alertas del Sistema
        alerts: List[str] = []
        if (traz_02.value or 0) > 0.0:
            alerts.append(f"ALERTA: Se detectaron discrepancias documentales en el {traz_02.value:.2f}% de las actividades.")
        if (act_03.value or 0) > 0.0:
            alerts.append(f"NOTA: Existen {int(act_03.value)} actividades emergentes fuera del POA que no suman a cobertura.")
        if traz_01.value is not None and traz_01.value < 50.0:
            alerts.append("ALERTA: Menos del 50% de las actividades ejecutadas cuentan con trazabilidad activa hacia el POA.")
        if not alerts:
            alerts.append("Sistema operando con consistencia pericial y gobernanza íntegra.")

        dashboard_dto = DashboardDataDTO(
            timestamp=datetime.now(timezone.utc).isoformat(),
            filters_active=f,
            kpi_cards_summary=kpi_summary,
            level_1_summary=lvl_1,
            level_2_activity=lvl_2,
            level_3_demography=lvl_3,
            level_4_territory=lvl_4,
            level_5_traceability=lvl_5,
            system_health_alerts=alerts,
            parameters_applied={
                "multisession_goal_mode": f.multisession_goal_mode,
                "require_verified_id": f.require_verified_id_for_unique_persons,
            },
        )

        self._cache.set(cache_key, dashboard_dto)
        return dashboard_dto

    # -----------------------------------------------------------------------
    # MÉTODOS PRIVADOS DE COMPOSICIÓN DE REPORTES INDIVIDUALES
    # -----------------------------------------------------------------------

    def _build_rep_01_balance_ejecutivo(
        self,
        filters: ReportFilterDTO,
        query: IndicatorQuery,
    ) -> ReportDocumentDTO:
        """REP-01: Balance Ejecutivo de Gestión Institucional."""
        act_01 = self._calc(IndicatorId.IND_ACT_01, query)
        act_02 = self._calc(IndicatorId.IND_ACT_02, query)
        act_03 = self._calc(IndicatorId.IND_ACT_03, query)
        cump_01 = self._calc(IndicatorId.IND_CUMP_01, query)
        part_01 = self._calc(IndicatorId.IND_PART_01, query)
        part_02 = self._calc(IndicatorId.IND_PART_02, query)
        part_04 = self._calc(IndicatorId.IND_PART_04, query)
        terr_01 = self._calc(IndicatorId.IND_TERR_01, query)
        traz_01 = self._calc(IndicatorId.IND_TRAZ_01, query)

        # Sección 1: Resumen General
        sec_resumen = ReportSectionDTO(
            section_id="resumen_ejecutivo",
            title="Balance Cuantitativo de Gestión Institucional",
            description="Consolidado de metas programadas frente a resultados operacionales en territorio.",
            metrics=[
                self._to_metric_item(act_01, "Actividades Planificadas en POA"),
                self._to_metric_item(act_02, "Actividades Efectivamente Ejecutadas"),
                self._to_metric_item(act_03, "Actividades Emergentes (Fuera de POA)"),
                self._to_metric_item(cump_01, "Tasa de Cobertura de Ejecución del POA"),
                self._to_metric_item(part_01, "Total Participaciones Registradas (Asistencias Brutas)"),
                self._to_metric_item(part_02, "Total Personas Únicas Alcanzadas"),
                self._to_metric_item(part_04, "Índice de Paridad de Género (Razón F/M)"),
                self._to_metric_item(traz_01, "Índice de Trazabilidad Planificación-Ejecución"),
            ],
            table_headers=["Indicador Institucional", "Resultado Obtenido", "Unidad de Medida", "Evaluación"],
            table_rows=[
                ["Planes Programados en el POA", self._format_count(act_01.value), "actividades", "Programación oficial"],
                ["Eventos Ejecutados en Territorio", self._format_count(act_02.value), "actividades", "Extensión universitaria"],
                ["Eventos Emergentes Atendidos", self._format_count(act_03.value), "actividades", "Fuera del POA"],
                ["Cobertura del Plan Operativo Anual", self._format_percent(cump_01.value), "%", "Planes cumplidos"],
                ["Volumen Bruto de Asistencias", self._format_count(part_01.value), "participaciones", "Servicio formativo"],
                ["Protagonistas Únicos Verificados", self._format_count(part_02.value), "personas únicas", "Alcance neto"],
                ["Paridad de Género (Razón F/M)", f"{part_04.value:.2f}" if part_04.value else "N/D", "Razón (F/M)", "Equidad"],
            ],
        )

        # Sección 2: Desconcentración Territorial
        terr_rows = [
            [s, str(v.get("conteo", 0)), f"{v.get('porcentaje', 0.0):.2f}%"]
            for s, v in terr_01.breakdown.items()
        ]
        sec_territorio = ReportSectionDTO(
            section_id="desconcentracion_territorial",
            title="Desconcentración Territorial por Sede Institucional",
            description="Distribución del esfuerzo universitario en las sedes relacionales según DDL V001.",
            metrics=[self._to_metric_item(terr_01, "Total Actividades Distribuidas por Sede")],
            table_headers=["Sede Institucional", "Eventos Ejecutados", "Porcentaje de Concentración"],
            table_rows=terr_rows,
        )

        # Sección 3: Gobernanza y Notas Periciales
        sec_gobernanza = ReportSectionDTO(
            section_id="gobernanza_y_calidad",
            title="Gobernanza Institucional y Salud del Dato",
            description="Cláusulas de salvaguarda metodológica aplicadas al cálculo del balance.",
            audit_notes=[
                "Las actividades emergentes se auditan en volumen territorial pero aportan 0 al porcentaje de cumplimiento del POA.",
                "Se excluyen estrictamente los 32 registros de beneficiarios preexistentes de M5 (es_historico_preexistente = 0).",
                "Prohibición estricta de imputar sexo. Casillas en blanco se reportan como 'No Especificado'.",
                f"Modo multisesión activo: {filters.multisession_goal_mode}. Criterio de cédula requerida: {filters.require_verified_id_for_unique_persons}.",
            ],
        )

        return ReportDocumentDTO(
            report_id=f"REP-01-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            report_type=ReportType.REP_01,
            title="REP-01: Balance Ejecutivo de Gestión Institucional",
            subtitle="Informe Integral de Desempeño Operativo, Poblacional y Territorial",
            institution_name="Bluefields Indian & Caribbean University (BICU)",
            generated_at=datetime.now(timezone.utc).isoformat(),
            generated_by="Sistema Institucional BICU — ReportingService Core",
            filters_applied=filters,
            sections=[sec_resumen, sec_territorio, sec_gobernanza],
            parameters_applied={
                "multisession_goal_mode": filters.multisession_goal_mode,
                "require_verified_id": filters.require_verified_id_for_unique_persons,
            },
        )

    def _build_rep_02_cumplimiento_poa(
        self,
        filters: ReportFilterDTO,
        query: IndicatorQuery,
    ) -> ReportDocumentDTO:
        """REP-02: Evaluación de Cumplimiento del Plan Operativo Anual (POA)."""
        act_01 = self._calc(IndicatorId.IND_ACT_01, query)
        act_02 = self._calc(IndicatorId.IND_ACT_02, query)
        act_03 = self._calc(IndicatorId.IND_ACT_03, query)
        act_04 = self._calc(IndicatorId.IND_ACT_04, query)
        cump_01 = self._calc(IndicatorId.IND_CUMP_01, query)
        cump_02 = self._calc(IndicatorId.IND_CUMP_02, query)

        sec_poa = ReportSectionDTO(
            section_id="cumplimiento_operativo_poa",
            title="Cumplimiento Operativo del Plan Operativo Anual",
            description="Evaluación del avance de metas de planificación institucional frente a la ejecución real.",
            metrics=[
                self._to_metric_item(act_01, "Actividades Planificadas POA"),
                self._to_metric_item(act_04, "Tasa de Formalización Metodológica"),
                self._to_metric_item(cump_01, "Cobertura de Ejecución de Actividades Planificadas"),
                self._to_metric_item(cump_02, "Eficacia Global de Metas de Participación"),
            ],
        )

        # Cuadrantes Operativos de Gestión
        num_cump = int(cump_01.numerator_value or 0)
        den_cump = int(cump_01.denominator_value or 0)
        pendientes = max(0, den_cump - num_cump)
        emergentes = int(act_03.value or 0)
        total_exec = int(act_02.value or 0)

        sec_cuadrantes = ReportSectionDTO(
            section_id="cuadrantes_operativos",
            title="Cuadrantes Operativos de Gestión",
            description="Separación metodológica estricta entre planes cumplidos, pendientes y emergentes.",
            table_headers=["Cuadrante", "Concepto Metodológico", "Cantidad de Actividades", "Tratamiento en Cumplimiento POA"],
            table_rows=[
                ["Cuadrante 1", "Compromisos Cumplidos (Con ejecución activa vinculada)", str(num_cump), "Aporta al numerador de cobertura POA"],
                ["Cuadrante 2", "Compromisos Pendientes (Sin ejecución en el período)", str(pendientes), "Pendientes (0 aporte a cumplimiento)"],
                ["Cuadrante 3", "Acciones Extraordinarias (Emergentes no en POA)", str(emergentes), "Fuera de POA (0 aporte a cumplimiento)"],
                ["Cuadrante 4", "Volumen Total de Extensión en Territorio", str(total_exec), "Volumen operativo bruto"],
            ],
            audit_notes=[
                "Regla Multisesión (1:N): 1 actividad planificada con N ejecuciones aporta como máximo 1 plan cumplido.",
                f"Modo de Meta de Participantes aplicado: {filters.multisession_goal_mode}.",
                "IND-CUMP-03 (Planes Vencidos) queda fuera del KPI oficial en espera de ratificación de Rectoría (DEC-INST-01).",
            ],
        )

        return ReportDocumentDTO(
            report_id=f"REP-02-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            report_type=ReportType.REP_02,
            title="REP-02: Evaluación de Cumplimiento del POA (Plan vs Ejecución)",
            subtitle="Auditoría de Cumplimiento Operativo, Metas de Participación y Cuadrantes de Gestión",
            institution_name="Bluefields Indian & Caribbean University (BICU)",
            generated_at=datetime.now(timezone.utc).isoformat(),
            generated_by="Sistema Institucional BICU — ReportingService Core",
            filters_applied=filters,
            sections=[sec_poa, sec_cuadrantes],
            parameters_applied={
                "multisession_goal_mode": filters.multisession_goal_mode,
                "require_verified_id": filters.require_verified_id_for_unique_persons,
            },
        )

    def _build_rep_03_cobertura_demografica(
        self,
        filters: ReportFilterDTO,
        query: IndicatorQuery,
    ) -> ReportDocumentDTO:
        """REP-03: Cobertura Demográfica y Atención de Protagonistas."""
        part_01 = self._calc(IndicatorId.IND_PART_01, query)
        part_02 = self._calc(IndicatorId.IND_PART_02, query)
        part_03 = self._calc(IndicatorId.IND_PART_03, query)
        part_04 = self._calc(IndicatorId.IND_PART_04, query)
        part_05 = self._calc(IndicatorId.IND_PART_05, query)

        sec_poblacion = ReportSectionDTO(
            section_id="alcance_poblacional",
            title="Alcance Poblacional y Penetración Formativa",
            description="Comparación entre volumen total de asistencias y personas únicas alcanzadas.",
            metrics=[
                self._to_metric_item(part_01, "Total Asistencias Brutas Efectivas"),
                self._to_metric_item(part_02, "Total Personas Únicas Alcanzadas"),
                self._to_metric_item(part_03, "Tasa de Recurrencia de Participantes"),
                self._to_metric_item(part_04, "Índice de Paridad de Género"),
            ],
            table_headers=["Concepto Analítico", "Valor Registrado", "Unidad", "Criterio de Medición"],
            table_rows=[
                ["Total Participaciones (Asistencias Brutas)", self._format_count(part_01.value), "participaciones", "Suma de firmas efectivas (excluye ausentes y M5 histórico)"],
                ["Total Personas Únicas Verificadas", self._format_count(part_02.value), "personas únicas", f"Cédula válida (require_verified_id={filters.require_verified_id_for_unique_persons})"],
                ["Tasa de Recurrencia de Participantes", self._format_percent(part_03.value), "%", "Personas que asistieron a 2 o más eventos distintos"],
            ],
        )

        sec_genero = ReportSectionDTO(
            section_id="equidad_genero",
            title="Equidad de Género y Distribución por Sexo",
            description="Distribución de participantes por sexo sin imputación de datos ausentes.",
            table_headers=["Categoría de Sexo", "Participaciones", "Tratamiento Pericial"],
            table_rows=[
                ["Femenino", str(part_04.breakdown.get("total_femenino", 0)), "Verificado en planilla"],
                ["Masculino", str(part_04.breakdown.get("total_masculino", 0)), "Verificado en planilla"],
                ["No Especificado", str(part_04.breakdown.get("total_no_especificado", 0)), "Preservado intacto (cero imputación)"],
            ],
        )

        est_rows = [
            [est, str(v.get("conteo", 0)), f"{v.get('porcentaje', 0.0):.2f}%"]
            for est, v in part_05.breakdown.items()
        ]
        sec_estamentos = ReportSectionDTO(
            section_id="distribucion_estamentos",
            title="Participación por Estamento Institucional",
            description="Desglose de asistentes según su vinculación con la universidad.",
            table_headers=["Estamento Institucional Declarado", "Total Asistencias", "Porcentaje del Total"],
            table_rows=est_rows,
        )

        return ReportDocumentDTO(
            report_id=f"REP-03-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            report_type=ReportType.REP_03,
            title="REP-03: Cobertura Demográfica y Atención de Protagonistas",
            subtitle="Auditoría de Inclusión, Paridad de Género, Estamentos y Fidelización",
            institution_name="Bluefields Indian & Caribbean University (BICU)",
            generated_at=datetime.now(timezone.utc).isoformat(),
            generated_by="Sistema Institucional BICU — ReportingService Core",
            filters_applied=filters,
            sections=[sec_poblacion, sec_genero, sec_estamentos],
            parameters_applied={
                "multisession_goal_mode": filters.multisession_goal_mode,
                "require_verified_id": filters.require_verified_id_for_unique_persons,
            },
        )

    def _build_rep_04_descentralizacion_territorial(
        self,
        filters: ReportFilterDTO,
        query: IndicatorQuery,
    ) -> ReportDocumentDTO:
        """REP-04: Extensión y Descentralización Territorial."""
        terr_01 = self._calc(IndicatorId.IND_TERR_01, query)
        act_02 = self._calc(IndicatorId.IND_ACT_02, query)

        terr_rows = [
            [s, str(v.get("conteo", 0)), f"{v.get('porcentaje', 0.0):.2f}%"]
            for s, v in terr_01.breakdown.items()
        ]

        sec_sedes = ReportSectionDTO(
            section_id="desconcentracion_geografica",
            title="Desconcentración Geográfica de Actividades Universitarias",
            description="Concentración y cobertura territorial por sede institucional normalizada.",
            metrics=[
                self._to_metric_item(act_02, "Total de Actividades Ejecutadas en Territorio"),
                self._to_metric_item(terr_01, "Distribución Territorial por Sede"),
            ],
            table_headers=["Sede Institucional (DDL V001)", "Actividades Realizadas", "Porcentaje de Concentración"],
            table_rows=terr_rows,
            audit_notes=[
                "Las sedes se basan en la columna 'sede' de SQLite V001 (BLUEFIELDS, BILWI, EL_RAMA, CORN_ISLAND, WASPAM, PAIWAS, LAS_MINAS, MANAGUA, OTRA).",
                "El catálogo de Recintos Universitarios vs Extensiones Municipales se mantiene como Decisión Institucional Pendiente (DEC-CAT-01).",
                "Las actividades sin municipio registrado se clasifican como 'Municipio No Especificado'.",
            ],
        )

        return ReportDocumentDTO(
            report_id=f"REP-04-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            report_type=ReportType.REP_04,
            title="REP-04: Extensión y Descentralización Territorial",
            subtitle="Monitoreo de Desconcentración Geográfica y Presencia Regional en la Costa Caribe",
            institution_name="Bluefields Indian & Caribbean University (BICU)",
            generated_at=datetime.now(timezone.utc).isoformat(),
            generated_by="Sistema Institucional BICU — ReportingService Core",
            filters_applied=filters,
            sections=[sec_sedes],
            parameters_applied={
                "multisession_goal_mode": filters.multisession_goal_mode,
                "require_verified_id": filters.require_verified_id_for_unique_persons,
            },
        )

    def _build_rep_05_auditoria_trazabilidad(
        self,
        filters: ReportFilterDTO,
        query: IndicatorQuery,
    ) -> ReportDocumentDTO:
        """REP-05: Auditoría de Trazabilidad, Gobernanza y Salud del Dato."""
        traz_01 = self._calc(IndicatorId.IND_TRAZ_01, query)
        traz_02 = self._calc(IndicatorId.IND_TRAZ_02, query)
        traz_03 = self._calc(IndicatorId.IND_TRAZ_03, query)

        sec_traz = ReportSectionDTO(
            section_id="trazabilidad_plan_ejecucion",
            title="Trazabilidad Planificación ↔ Ejecución (V004)",
            description="Auditoría pericial del estado de los enlaces entre metas planificadas y eventos de campo.",
            metrics=[self._to_metric_item(traz_01, "Índice de Trazabilidad Plan-Ejecución")],
            table_headers=["Métrica de Trazabilidad", "Cantidad", "Porcentaje", "Criterio de Auditoría"],
            table_rows=[
                ["Ejecuciones con Enlace Activo (ACTIVE)", str(int(traz_01.numerator_value or 0)), self._format_percent(traz_01.value), "Vínculos válidos certificados"],
                ["Total de Actividades Ejecutadas Auditadas", str(int(traz_01.denominator_value or 0)), "100.00%", "Universo de eventos en territorio"],
            ],
            audit_notes=[
                "Enlaces en estado REVOKED y SUPERSEDED se excluyen estrictamente del numerador de trazabilidad.",
                "Toda actividad con enlace revocado pasa automáticamente a tratarse como no vinculada (emergente).",
            ],
        )

        discrep_desc = "Consistencia documental íntegra" if (traz_02.value or 0) == 0.0 else "Requiere revisión pericial"
        sec_calidad = ReportSectionDTO(
            section_id="calidad_y_salud_dato",
            title="Salud del Dato y Calidad de las Fuentes Primarias",
            description="Control de discrepancias documentales (M1 vs M2–M5) y disponibilidad de cédulas.",
            metrics=[
                self._to_metric_item(traz_02, "Tasa de Discrepancia Documental (M1 vs M2–M5)"),
                self._to_metric_item(traz_03, "Tasa de Disponibilidad de Cédula Oficial"),
            ],
            table_headers=["Control de Calidad", "Valor Observado", "Umbral / Estado", "Diagnóstico Pericial"],
            table_rows=[
                ["Tasa de Discrepancia Documental (M1 vs M2–M5)", self._format_percent(traz_02.value), "0.00% requerido", discrep_desc],
                ["Tasa de Disponibilidad de Cédula Oficial", self._format_percent(traz_03.value), "100.00% ideal", "Padrón nominal verificado"],
            ],
            audit_notes=[
                "La persistencia relacional permanece inalterada en esquema V004. No existe esquema V005.",
                "Los datos de M5 histórico se mantienen aislados para no contaminar las métricas de calidad.",
            ],
        )

        return ReportDocumentDTO(
            report_id=f"REP-05-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            report_type=ReportType.REP_05,
            title="REP-05: Auditoría de Trazabilidad, Gobernanza y Salud del Dato",
            subtitle="Dictamen Pericial de Consistencia Documental, Calidad del Padrón y Enlaces V004",
            institution_name="Bluefields Indian & Caribbean University (BICU)",
            generated_at=datetime.now(timezone.utc).isoformat(),
            generated_by="Sistema Institucional BICU — ReportingService Core",
            filters_applied=filters,
            sections=[sec_traz, sec_calidad],
            parameters_applied={
                "multisession_goal_mode": filters.multisession_goal_mode,
                "require_verified_id": filters.require_verified_id_for_unique_persons,
            },
        )

    # -----------------------------------------------------------------------
    # HELPERS AUXILIARES PRIVADOS
    # -----------------------------------------------------------------------

    def _calc(self, indicator_id: str, query: IndicatorQuery) -> IndicatorResult:
        """Invoca el motor determinista de indicadores sin duplicar fórmulas."""
        return self._indicator_service.calculate_indicator(indicator_id, query)

    def _to_indicator_query(self, filters: ReportFilterDTO) -> IndicatorQuery:
        """Mapea un ReportFilterDTO al IndicatorQuery inmutable del núcleo analítico."""
        start = filters.start_date
        end = filters.end_date
        if filters.period_year and not start:
            start = f"{filters.period_year:04d}-01-01"
            end = f"{filters.period_year:04d}-12-31"

        return IndicatorQuery(
            start_date=start,
            end_date=end,
            sede=filters.sede,
            programa=filters.programa,
            eje_estrategico=filters.eje_estrategia,
            tipo_evento=filters.tipo_evento,
            multisession_goal_mode=filters.multisession_goal_mode,
            require_verified_id_for_unique_persons=filters.require_verified_id_for_unique_persons,
        )

    def _make_card(
        self,
        card_id: str,
        indicator_id: str,
        title: str,
        result: IndicatorResult,
        unit_label: str,
        sub_label: str,
        alert_status: AlertStatus,
        tooltip: str,
        multisession_mode: Optional[str] = None,
    ) -> DashboardCardDTO:
        """Construye un DashboardCardDTO inmutable a partir de un IndicatorResult."""
        val_str = self._format_value_display(result.value, result.unit)
        return DashboardCardDTO(
            card_id=card_id,
            indicator_id=indicator_id,
            title=title,
            main_value=val_str,
            unit_label=unit_label,
            sub_label=sub_label,
            alert_status=alert_status,
            tooltip_explanation=tooltip,
            multisession_mode_applied=multisession_mode,
            raw_value=result.value,
        )

    def _to_metric_item(
        self,
        res: IndicatorResult,
        custom_label: Optional[str] = None,
    ) -> ReportMetricItemDTO:
        """Proyecta un IndicatorResult a un ReportMetricItemDTO estructurado."""
        label = custom_label or res.name
        val_disp = self._format_value_display(res.value, res.unit)
        num_disp = self._format_count(res.numerator_value) if res.numerator_value is not None else None
        den_disp = self._format_count(res.denominator_value) if res.denominator_value is not None else None

        alert = "NORMAL"
        if res.value is None:
            alert = "INFO"
        elif res.indicator_id == IndicatorId.IND_TRAZ_02 and (res.value or 0) > 0.0:
            alert = "WARNING"
        elif res.indicator_id == IndicatorId.IND_CUMP_01 and (res.value or 0) < 50.0:
            alert = "WARNING"

        note = " ".join(res.notes) if res.notes else None

        return ReportMetricItemDTO(
            indicator_id=res.indicator_id,
            label=label,
            value_display=val_disp,
            raw_value=res.value,
            unit=res.unit,
            numerator_display=num_disp,
            denominator_display=den_disp,
            interpretation_note=note,
            alert_level=alert,
        )

    @staticmethod
    def _format_value_display(value: Optional[float], unit: str) -> str:
        """Formatea defensivamente un valor numérico para presentación en pantalla/reporte."""
        if value is None:
            return "N/D"
        if unit == "%":
            return f"{value:.2f}%"
        if unit in ("actividades", "participaciones", "personas únicas", "personas", "planes"):
            return f"{int(value):,}".replace(",", ".")
        return f"{value:.2f}"

    @staticmethod
    def _format_count(value: Optional[float]) -> str:
        """Formatea un conteo entero con separador de miles latinoamericano."""
        if value is None:
            return "0"
        return f"{int(value):,}".replace(",", ".")

    @staticmethod
    def _format_percent(value: Optional[float]) -> str:
        """Formatea un porcentaje o devuelve N/D si es None."""
        if value is None:
            return "N/D"
        return f"{value:.2f}%"
