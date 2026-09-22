"""Mapeadores Bidireccionales Dominio ↔ Persistencia SQLite.

Fase 29.4.2 — Implementación de Persistencia SQLite V003.
Transforman entre entidades / value objects de dominio y filas relacionales de SQLite.
Los mappers no contienen reglas de negocio ni realizan llamadas de I/O.
"""

from datetime import date, datetime
import json
from typing import Any, Dict, List, Optional, Sequence
import uuid

from app.planning.domain.entities import MethodologicalDesign, PlannedActivity, PlanningExecutionLink
from app.planning.domain.value_objects import (
    AIProposal,
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)


class PlannedActivityMapper:
    """Mapeador bidireccional para PlannedActivity."""

    @staticmethod
    def to_row(entity: PlannedActivity) -> Dict[str, Any]:
        """Convierte una entidad PlannedActivity en un diccionario para SQLite."""
        return {
            "activity_internal_id": str(entity.activity_internal_id),
            "planning_id": entity.planning_id,
            "activity_name": entity.activity_name,
            "sede": entity.sede,
            "area_responsable": entity.area_responsable,
            "eje_estrategia": entity.eje_estrategia,
            "programa": entity.programa,
            "tipo_evento": entity.tipo_evento,
            "dep_sede": entity.dep_sede,
            "mun_sede": entity.mun_sede,
            "otro_programa": entity.otro_programa,
            "proyecto": entity.proyecto,
            "tipo_proyecto": entity.tipo_proyecto,
            "ambito": entity.ambito,
            "codigo_presupuestario": entity.codigo_presupuestario,
            "departamento_responsable": entity.departamento_responsable,
            "proposito": entity.proposito,
            "fecha_evento": entity.fecha_evento.isoformat() if entity.fecha_evento else None,
            "convenio": entity.convenio,
            "entidades_cooperantes": entity.entidades_cooperantes,
            "est_grado_m": entity.participant_goals.est_grado_m,
            "est_grado_f": entity.participant_goals.est_grado_f,
            "est_postgrado_m": entity.participant_goals.est_postgrado_m,
            "est_postgrado_f": entity.participant_goals.est_postgrado_f,
            "docentes_m": entity.participant_goals.docentes_m,
            "docentes_f": entity.participant_goals.docentes_f,
            "administrativos_m": entity.participant_goals.administrativos_m,
            "administrativos_f": entity.participant_goals.administrativos_f,
            "externos_m": entity.participant_goals.externos_m,
            "externos_f": entity.participant_goals.externos_f,
        }

    @staticmethod
    def to_domain(row: Any) -> PlannedActivity:
        """Convierte una fila de SQLite en una entidad PlannedActivity."""
        fecha_val = row["fecha_evento"]
        fecha_evento: Optional[date] = None
        if fecha_val:
            if isinstance(fecha_val, date):
                fecha_evento = fecha_val
            else:
                fecha_evento = date.fromisoformat(str(fecha_val)[:10])

        goals = ParticipantGoals(
            est_grado_m=int(row["est_grado_m"]),
            est_grado_f=int(row["est_grado_f"]),
            est_postgrado_m=int(row["est_postgrado_m"]),
            est_postgrado_f=int(row["est_postgrado_f"]),
            docentes_m=int(row["docentes_m"]),
            docentes_f=int(row["docentes_f"]),
            administrativos_m=int(row["administrativos_m"]),
            administrativos_f=int(row["administrativos_f"]),
            externos_m=int(row["externos_m"]),
            externos_f=int(row["externos_f"]),
        )

        return PlannedActivity(
            activity_internal_id=uuid.UUID(str(row["activity_internal_id"])),
            planning_id=str(row["planning_id"]),
            activity_name=str(row["activity_name"]),
            sede=str(row["sede"]),
            area_responsable=str(row["area_responsable"]),
            eje_estrategia=str(row["eje_estrategia"]),
            programa=str(row["programa"]),
            tipo_evento=str(row["tipo_evento"]),
            participant_goals=goals,
            dep_sede=str(row["dep_sede"] or ""),
            mun_sede=str(row["mun_sede"] or ""),
            otro_programa=row["otro_programa"],
            proyecto=row["proyecto"],
            tipo_proyecto=row["tipo_proyecto"],
            ambito=row["ambito"],
            codigo_presupuestario=row["codigo_presupuestario"],
            departamento_responsable=row["departamento_responsable"],
            proposito=row["proposito"],
            fecha_evento=fecha_evento,
            convenio=row["convenio"],
            entidades_cooperantes=row["entidades_cooperantes"],
        )


class FAQTableMapper:
    """Mapeador bidireccional para FAQTable."""

    @staticmethod
    def to_row(faq: FAQTable, design_id: uuid.UUID) -> Dict[str, Any]:
        return {
            "design_id": str(design_id),
            "q1_que_es": faq.q1_que_es,
            "q2_para_que": faq.q2_para_que,
            "q3_sesiones": faq.q3_sesiones,
            "q4_protagonistas": faq.q4_protagonistas,
            "q5_facilitador": faq.q5_facilitador,
            "q6_materiales": faq.q6_materiales,
            "q7_duracion": faq.q7_duracion,
        }

    @staticmethod
    def to_domain(row: Any) -> Optional[FAQTable]:
        if not row:
            return None
        return FAQTable(
            q1_que_es=str(row["q1_que_es"]),
            q2_para_que=str(row["q2_para_que"] or ""),
            q3_sesiones=str(row["q3_sesiones"] or "Sesión única"),
            q4_protagonistas=str(row["q4_protagonistas"]),
            q5_facilitador=str(row["q5_facilitador"]),
            q6_materiales=str(row["q6_materiales"] or ""),
            q7_duracion=str(row["q7_duracion"]),
        )


class TimeBlockMapper:
    """Mapeador bidireccional para TimeBlock."""

    @staticmethod
    def to_row(block: TimeBlock, design_id: uuid.UUID) -> Dict[str, Any]:
        return {
            "agenda_id": str(uuid.uuid4()),
            "design_id": str(design_id),
            "sequence": block.sequence,
            "label": block.label,
            "minutes": block.minutes,
        }

    @staticmethod
    def to_domain(row: Any) -> TimeBlock:
        return TimeBlock(
            sequence=int(row["sequence"]),
            label=str(row["label"]),
            minutes=int(row["minutes"]),
        )


class OperationalActivityMapper:
    """Mapeador bidireccional para OperationalActivity."""

    @staticmethod
    def to_row(act: OperationalActivity, design_id: uuid.UUID) -> Dict[str, Any]:
        return {
            "operational_id": str(uuid.uuid4()),
            "design_id": str(design_id),
            "step_number": act.step_number,
            "phase_label": act.phase_label,
            "operative_goal": act.operative_goal,
            "procedure": act.procedure,
            "materials": act.materials,
            "minutes": act.minutes,
        }

    @staticmethod
    def to_domain(row: Any) -> OperationalActivity:
        return OperationalActivity(
            step_number=int(row["step_number"]),
            phase_label=str(row["phase_label"]),
            operative_goal=str(row["operative_goal"] or ""),
            procedure=str(row["procedure"] or ""),
            materials=str(row["materials"] or ""),
            minutes=int(row["minutes"]),
        )


class AIProposalMapper:
    """Mapeador bidireccional para AIProposal."""

    @staticmethod
    def to_row(prop: AIProposal, design_id: uuid.UUID) -> Dict[str, Any]:
        accepted_int = None
        if prop.accepted is True:
            accepted_int = 1
        elif prop.accepted is False:
            accepted_int = 0

        return {
            "proposal_id": str(prop.proposal_id),
            "design_id": str(design_id),
            "target_field": prop.target_field,
            "proposed_content": prop.proposed_content,
            "source_inputs": json.dumps(prop.source_inputs, ensure_ascii=False),
            "confidence": float(prop.confidence),
            "requires_review": 1,
            "accepted": accepted_int,
            "reviewed_by": prop.reviewed_by,
            "review_timestamp": prop.review_timestamp.isoformat() if prop.review_timestamp else None,
            "rejection_reason": prop.rejection_reason,
        }

    @staticmethod
    def to_domain(row: Any) -> AIProposal:
        accepted_bool: Optional[bool] = None
        if row["accepted"] == 1:
            accepted_bool = True
        elif row["accepted"] == 0:
            accepted_bool = False

        rev_ts_val = row["review_timestamp"]
        rev_ts: Optional[datetime] = None
        if rev_ts_val:
            rev_ts = datetime.fromisoformat(str(rev_ts_val))

        source_inputs_val = row["source_inputs"]
        if isinstance(source_inputs_val, str):
            source_inputs_dict = json.loads(source_inputs_val)
        else:
            source_inputs_dict = dict(source_inputs_val or {})

        return AIProposal(
            proposal_id=uuid.UUID(str(row["proposal_id"])),
            target_field=str(row["target_field"]),
            proposed_content=str(row["proposed_content"]),
            source_inputs=source_inputs_dict,
            confidence=float(row["confidence"]),
            requires_review=True,
            reviewed_by=row["reviewed_by"],
            review_timestamp=rev_ts,
            accepted=accepted_bool,
            rejection_reason=row["rejection_reason"],
        )


class MethodologicalDesignMapper:
    """Mapeador bidireccional para el aggregate root MethodologicalDesign."""

    @staticmethod
    def to_row(entity: MethodologicalDesign) -> Dict[str, Any]:
        return {
            "design_id": str(entity.design_id),
            "planned_activity_internal_id": (
                str(entity.planned_activity_internal_id)
                if entity.planned_activity_internal_id
                else None
            ),
            "planned_activity_ref": entity.planned_activity_ref,
            "activity_name": entity.activity_name,
            "version": entity.version,
            "status": entity.status.value if isinstance(entity.status, DesignStatus) else str(entity.status),
            "introduction_text": entity.introduction_text,
            "methodological_approach": entity.methodological_approach,
            "objective_1": entity.objective_1,
            "objective_2": entity.objective_2,
            "created_by": entity.created_by,
            "created_at": entity.created_at.isoformat() if entity.created_at else datetime.now().isoformat(),
            "approved_by": entity.approved_by,
            "approved_at": entity.approved_at.isoformat() if entity.approved_at else None,
            "document_hash": entity.document_hash,
        }

    @staticmethod
    def to_domain(
        row: Any,
        faq_row: Optional[Any] = None,
        agenda_rows: Sequence[Any] = (),
        matrix_rows: Sequence[Any] = (),
        proposal_rows: Sequence[Any] = (),
    ) -> MethodologicalDesign:
        created_at_val = row["created_at"]
        created_at = (
            datetime.fromisoformat(str(created_at_val))
            if created_at_val
            else datetime.now()
        )

        approved_at_val = row["approved_at"]
        approved_at = (
            datetime.fromisoformat(str(approved_at_val))
            if approved_at_val
            else None
        )

        planned_act_id = row["planned_activity_internal_id"]
        planned_activity_internal_id: Optional[uuid.UUID] = (
            uuid.UUID(str(planned_act_id)) if planned_act_id else None
        )

        objectives: List[str] = []
        if row["objective_1"]:
            objectives.append(str(row["objective_1"]))
        if row["objective_2"]:
            objectives.append(str(row["objective_2"]))

        faq_table = FAQTableMapper.to_domain(faq_row) if faq_row else None
        agenda = [TimeBlockMapper.to_domain(r) for r in agenda_rows]
        matrix = [OperationalActivityMapper.to_domain(r) for r in matrix_rows]
        proposals = [AIProposalMapper.to_domain(r) for r in proposal_rows]

        return MethodologicalDesign(
            design_id=uuid.UUID(str(row["design_id"])),
            planned_activity_ref=str(row["planned_activity_ref"]),
            version=int(row["version"]),
            status=DesignStatus(str(row["status"])),
            planned_activity_internal_id=planned_activity_internal_id,
            activity_name=str(row["activity_name"] or ""),
            created_by=str(row["created_by"]),
            created_at=created_at,
            approved_by=row["approved_by"],
            approved_at=approved_at,
            document_hash=row["document_hash"],
            introduction_text=str(row["introduction_text"] or ""),
            methodological_approach=str(row["methodological_approach"] or ""),
            objectives=objectives,
            faq_table=faq_table,
            agenda=agenda,
            operational_matrix=matrix,
            ai_proposals=proposals,
        )


class PlanningExecutionLinkMapper:
    """Mapeador bidireccional para PlanningExecutionLink.

    Fase 29.18.1 — Trazabilidad Planificación ↔ Ejecución.
    Este mapper no accede a datos del dominio de ejecución más allá de id_actividad.
    """

    @staticmethod
    def to_row(link: PlanningExecutionLink) -> Dict[str, Any]:
        """Convierte un PlanningExecutionLink en un diccionario para INSERT/UPDATE SQLite."""
        return {
            "link_id": str(link.link_id),
            "planning_internal_id": str(link.planning_internal_id),
            "id_actividad": link.id_actividad,
            "linked_by": link.linked_by,
            "linked_at": link.linked_at.isoformat() if link.linked_at else None,
            "link_rationale": link.link_rationale,
            "numero_sesion": link.numero_sesion,
            "link_status": link.link_status,
            "revoked_by": link.revoked_by,
            "revoked_at": link.revoked_at.isoformat() if link.revoked_at else None,
            "revocation_reason": link.revocation_reason,
        }

    @staticmethod
    def to_domain(row: Any) -> PlanningExecutionLink:
        """Convierte una fila SQLite en un PlanningExecutionLink del dominio."""
        from datetime import timezone

        def _parse_dt(val: Any) -> Optional[datetime]:
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(str(val))

        return PlanningExecutionLink(
            link_id=uuid.UUID(str(row["link_id"])),
            planning_internal_id=uuid.UUID(str(row["planning_internal_id"])),
            id_actividad=str(row["id_actividad"]),
            linked_by=str(row["linked_by"]),
            linked_at=_parse_dt(row["linked_at"]) or datetime.now(),
            link_rationale=str(row["link_rationale"]),
            numero_sesion=int(row["numero_sesion"]) if row["numero_sesion"] is not None else None,
            link_status=str(row["link_status"]),
            revoked_by=row["revoked_by"],
            revoked_at=_parse_dt(row["revoked_at"]),
            revocation_reason=row["revocation_reason"],
        )
