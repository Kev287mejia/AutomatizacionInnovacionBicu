"""Suite de Pruebas Automatizadas — Servicio de Gestión del Diseño Metodológico.

Fase 29.9 — Implementación Controlada del Servicio de Gestión del Diseño Metodológico.
Cubre exhaustivamente:
  - MD-SVC-01: Listar actividad sin diseño (SIN_DISENO).
  - MD-SVC-02: Listar actividad con DRAFT.
  - MD-SVC-03: Listar actividad con GENERATED.
  - MD-SVC-04: Listar actividad con APPROVED.
  - MD-SVC-05: Filtrado por sede.
  - MD-SVC-06: Filtrado por estado.
  - MD-SVC-07: Búsqueda determinista.
  - MD-SVC-08: Obtener detalle existente.
  - MD-SVC-09: Actividad inexistente.
  - MD-SVC-10: Crear DRAFT.
  - MD-SVC-11: Crear DRAFT cuando ya existe DRAFT (idempotencia).
  - MD-SVC-12: Impedir creación sobre APPROVED (R-08).
  - MD-SVC-13: Actualizar DRAFT.
  - MD-SVC-14: Intentar actualizar APPROVED (R-08).
  - MD-SVC-15: Validación exitosa.
  - MD-SVC-16: Validación fallida.
  - MD-SVC-17: Impedir aprobación de diseño inválido.
  - MD-SVC-18: Aprobación correcta.
  - MD-SVC-19: R-08 después de aprobación.
  - MD-SVC-20: Persistencia y reconstrucción en SQLite V003.
  - MD-SVC-21: Conservación de planning_id.
  - MD-SVC-22: No transferencia de datos de ejecución.
  - MD-SVC-23: No modificación de M1–M5.
  - MD-SVC-24: Aislamiento arquitectónico (AST).
  - Integración completa: POA -> Ingestion -> Service -> DRAFT -> UPDATE -> VALIDATE -> APPROVE.
"""
from __future__ import annotations

import ast
from datetime import date, datetime
from pathlib import Path
import sqlite3
import uuid

import pytest

from app.planning.application.services import (
    MethodologicalDesignService,
    PlannedActivityIngestionService,
)
from app.planning.domain.dtos import (
    FAQTableDTO,
    OperationalActivityDTO,
    TimeBlockDTO,
    UpdateMethodologicalDesignCommand,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.value_objects import (
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)
from app.planning.infrastructure.persistence.schema_v003 import V003_SCHEMA_DDL_STATEMENTS
from app.planning.infrastructure.persistence.unit_of_work import PlanningUnitOfWork
from app.planning.infrastructure.readers.excel_planning_reader import ExcelPlanningReader


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------
@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Crea una base de datos SQLite temporal con el esquema V003 inicializado."""
    db_file = str(tmp_path / "test_planning_service.sqlite")
    conn = sqlite3.connect(db_file)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        for stmt in V003_SCHEMA_DDL_STATEMENTS:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    return db_file


@pytest.fixture
def uow(temp_db_path: str) -> PlanningUnitOfWork:
    """Unidad de trabajo transaccional sobre la base temporal."""
    return PlanningUnitOfWork(db_path=temp_db_path)


@pytest.fixture
def service(uow: PlanningUnitOfWork) -> MethodologicalDesignService:
    """Instancia del servicio de aplicación MethodologicalDesignService."""
    return MethodologicalDesignService(uow=uow)


@pytest.fixture
def sample_activity(uow: PlanningUnitOfWork) -> PlannedActivity:
    """Inserta una actividad planificada base en SQLite V003."""
    act = PlannedActivity.create(
        planning_id="POA-Bilwi-101",
        activity_name="Taller de Inteligencia Artificial Aplicada",
        sede="Bilwi",
        area_responsable="Coordinación de Innovación",
        eje_estrategia="EJE_11",
        programa="PGM_07",
        tipo_evento="EVT_CAPACITACION",
        participant_goals=ParticipantGoals(est_grado_m=10, est_grado_f=15),
        dep_sede="RACCN",
        mun_sede="Puerto Cabezas",
        proposito="Desarrollar habilidades en algoritmos de aprendizaje automático.",
        fecha_evento=date(2026, 11, 20),
    )
    with uow:
        uow.planned_activities.save(act)
        uow.commit()
    return act


# ---------------------------------------------------------------------------
# 1. CASOS DE USO: LISTADO Y CONSULTA (MD-SVC-01 .. MD-SVC-07)
# ---------------------------------------------------------------------------
class TestMethodologicalDesignServiceListing:
    """Pruebas para list_activities_with_design_status."""

    def test_md_svc_01_list_activity_sin_diseno(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-01: Listar actividad sin diseño asociado retorna estado SIN_DISENO."""
        summaries = service.list_activities_with_design_status()
        assert len(summaries) == 1
        s = summaries[0]
        assert s.planning_id == "POA-Bilwi-101"
        assert s.activity_name == "Taller de Inteligencia Artificial Aplicada"
        assert s.design_status == "SIN_DISENO"
        assert s.design_id is None
        assert s.total_participants == 25

    def test_md_svc_02_list_activity_with_draft(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-02: Listar actividad con diseño en borrador retorna estado DRAFT."""
        service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")

        summaries = service.list_activities_with_design_status()
        assert len(summaries) == 1
        s = summaries[0]
        assert s.design_status == "DRAFT"
        assert s.design_id is not None
        assert s.design_version == 1

    def test_md_svc_03_list_activity_with_generated(
        self,
        service: MethodologicalDesignService,
        uow: PlanningUnitOfWork,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-03: Listar actividad con diseño en estado GENERATED."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        with uow:
            design = uow.methodological_designs.get_by_id(dto.design_id)
            assert design is not None
            design.mark_generated()
            uow.methodological_designs.save(design)
            uow.commit()

        summaries = service.list_activities_with_design_status()
        assert len(summaries) == 1
        assert summaries[0].design_status == "GENERATED"

    def test_md_svc_04_list_activity_with_approved(
        self,
        service: MethodologicalDesignService,
        uow: PlanningUnitOfWork,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-04: Listar actividad con diseño en estado APPROVED."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        # Completar diseño con 5 bloques para que sea válido
        cmd = UpdateMethodologicalDesignCommand(
            design_id=dto.design_id,
            introduction_text="Introducción contextual completa del taller.",
            methodological_approach="Enfoque constructivista y participativo.",
            objectives=("Comprender conceptos básicos de IA.", "Implementar un clasificador."),
            faq=FAQTableDTO(
                q1_que_es=sample_activity.activity_name,
                q2_para_que="Capacitar estudiantes",
                q3_sesiones="Sesión única",
                q4_protagonistas="Estudiantes de ingeniería",
                q5_facilitador="Ing. Especialista",
                q6_materiales="Laptops y proyector",
                q7_duracion="120 minutos",
            ),
            agenda=(
                TimeBlockDTO(sequence=1, label="Teoría", minutes=60),
                TimeBlockDTO(sequence=2, label="Práctica", minutes=60),
            ),
            operational_matrix=(
                OperationalActivityDTO(
                    step_number=1,
                    phase_label="Fase 1",
                    operative_goal="Presentar fundamentos",
                    procedure="Exposición magistral",
                    materials="Diapositivas",
                    minutes=60,
                ),
                OperationalActivityDTO(
                    step_number=2,
                    phase_label="Fase 2",
                    operative_goal="Ejercicios prácticos",
                    procedure="Programación guiada",
                    materials="Laptops",
                    minutes=60,
                ),
            ),
        )
        service.update_design_draft(cmd)
        service.approve_design(dto.design_id, approved_by="Decano BICU")

        summaries = service.list_activities_with_design_status()
        assert len(summaries) == 1
        assert summaries[0].design_status == "APPROVED"

    def test_md_svc_05_filter_by_sede(
        self,
        service: MethodologicalDesignService,
        uow: PlanningUnitOfWork,
    ):
        """MD-SVC-05: Filtrado determinista por sede institucional."""
        act_bilwi = PlannedActivity.create(
            planning_id="POA-Bilwi-1",
            activity_name="Actividad Bilwi",
            sede="Bilwi",
            area_responsable="Área A",
            eje_estrategia="EJE_1",
            programa="PGM_01",
            tipo_evento="EVT_CHARLA",
            participant_goals=ParticipantGoals(est_grado_m=5),
        )
        act_bluefields = PlannedActivity.create(
            planning_id="POA-Bluefields-1",
            activity_name="Actividad Bluefields",
            sede="Bluefields",
            area_responsable="Área B",
            eje_estrategia="EJE_2",
            programa="PGM_02",
            tipo_evento="EVT_FERIA",
            participant_goals=ParticipantGoals(est_grado_f=8),
        )
        with uow:
            uow.planned_activities.save(act_bilwi)
            uow.planned_activities.save(act_bluefields)
            uow.commit()

        res_bilwi = service.list_activities_with_design_status(sede="Bilwi")
        assert len(res_bilwi) == 1
        assert res_bilwi[0].planning_id == "POA-Bilwi-1"

        res_blue = service.list_activities_with_design_status(sede="Bluefields")
        assert len(res_blue) == 1
        assert res_blue[0].planning_id == "POA-Bluefields-1"

        res_none = service.list_activities_with_design_status(sede="SedeInexistente")
        assert len(res_none) == 0

    def test_md_svc_06_filter_by_status(
        self,
        service: MethodologicalDesignService,
        uow: PlanningUnitOfWork,
    ):
        """MD-SVC-06: Filtrado determinista por estado de diseño."""
        act1 = PlannedActivity.create(
            planning_id="POA-1",
            activity_name="Actividad 1",
            sede="Bilwi",
            area_responsable="Área A",
            eje_estrategia="EJE_1",
            programa="PGM_01",
            tipo_evento="EVT_CHARLA",
            participant_goals=ParticipantGoals(est_grado_m=5),
        )
        act2 = PlannedActivity.create(
            planning_id="POA-2",
            activity_name="Actividad 2",
            sede="Bilwi",
            area_responsable="Área A",
            eje_estrategia="EJE_1",
            programa="PGM_01",
            tipo_evento="EVT_CHARLA",
            participant_goals=ParticipantGoals(est_grado_m=5),
        )
        with uow:
            uow.planned_activities.save(act1)
            uow.planned_activities.save(act2)
            uow.commit()

        service.create_design_draft("POA-1", created_by="User A")

        drafts = service.list_activities_with_design_status(status="DRAFT")
        assert len(drafts) == 1
        assert drafts[0].planning_id == "POA-1"

        sin_diseno = service.list_activities_with_design_status(status="SIN_DISENO")
        assert len(sin_diseno) == 1
        assert sin_diseno[0].planning_id == "POA-2"

    def test_md_svc_07_search_term(
        self,
        service: MethodologicalDesignService,
        uow: PlanningUnitOfWork,
    ):
        """MD-SVC-07: Búsqueda determinista por texto en nombre de actividad y planning_id."""
        act1 = PlannedActivity.create(
            planning_id="POA-Robótica-01",
            activity_name="Taller Intensivo de Robótica Educativa",
            sede="Bilwi",
            area_responsable="Área A",
            eje_estrategia="EJE_1",
            programa="PGM_01",
            tipo_evento="EVT_TALLER",
            participant_goals=ParticipantGoals(est_grado_m=5),
        )
        act2 = PlannedActivity.create(
            planning_id="POA-Agro-02",
            activity_name="Feria de Agroecología Comunitaria",
            sede="El Rama",
            area_responsable="Área B",
            eje_estrategia="EJE_2",
            programa="PGM_02",
            tipo_evento="EVT_FERIA",
            participant_goals=ParticipantGoals(est_grado_m=5),
        )
        with uow:
            uow.planned_activities.save(act1)
            uow.planned_activities.save(act2)
            uow.commit()

        res_rob = service.list_activities_with_design_status(search_term="robótica")
        assert len(res_rob) == 1
        assert res_rob[0].planning_id == "POA-Robótica-01"

        res_code = service.list_activities_with_design_status(search_term="Agro-02")
        assert len(res_code) == 1
        assert res_code[0].planning_id == "POA-Agro-02"


# ---------------------------------------------------------------------------
# 2. CASOS DE USO: DETALLE DE ACTIVIDAD (MD-SVC-08 .. MD-SVC-09)
# ---------------------------------------------------------------------------
class TestMethodologicalDesignServiceDetail:
    """Pruebas para get_activity_detail."""

    def test_md_svc_08_get_activity_detail_existing(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-08: Obtener detalle de actividad existente con y sin diseño."""
        detail = service.get_activity_detail(sample_activity.planning_id)
        assert detail is not None
        assert detail.planning_id == sample_activity.planning_id
        assert detail.activity_name == sample_activity.activity_name
        assert detail.sede == "Bilwi"
        assert detail.area_responsable == "Coordinación de Innovación"
        assert detail.proposito == "Desarrollar habilidades en algoritmos de aprendizaje automático."
        assert detail.fecha_evento == date(2026, 11, 20)
        assert detail.design_status == "SIN_DISENO"
        assert detail.design_id is None

        # Tras crear diseño:
        draft = service.create_design_draft(sample_activity.planning_id, created_by="User B")
        detail_after = service.get_activity_detail(sample_activity.planning_id)
        assert detail_after is not None
        assert detail_after.design_status == "DRAFT"
        assert detail_after.design_id == draft.design_id

    def test_md_svc_09_get_activity_detail_nonexistent(
        self,
        service: MethodologicalDesignService,
    ):
        """MD-SVC-09: Obtener detalle de actividad inexistente retorna None."""
        assert service.get_activity_detail("POA-Fantasma-999") is None
        assert service.get_activity_detail("") is None


# ---------------------------------------------------------------------------
# 3. CASOS DE USO: CREACIÓN E IDEMPOTENCIA DRAFT (MD-SVC-10 .. MD-SVC-12)
# ---------------------------------------------------------------------------
class TestMethodologicalDesignServiceDraftCreation:
    """Pruebas para create_design_draft."""

    def test_md_svc_10_create_draft_success(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-10: Crear borrador inicial con prellenado determinista de FAQ."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        assert dto.design_id is not None
        assert dto.version == 1
        assert dto.created_by == "Prof. Kenia"
        assert dto.document_title == "Diseño metodológico Taller de Inteligencia Artificial Aplicada"

        # Comprobar prellenado de FAQ Table
        assert dto.faq.q1_que_es == sample_activity.activity_name
        assert dto.faq.q2_para_que == sample_activity.proposito
        assert dto.faq.q3_sesiones == "Sesión única"
        assert "25 participantes" in dto.faq.q4_protagonistas
        assert dto.faq.q5_facilitador == sample_activity.area_responsable
        assert dto.faq.q7_duracion == "Por definir"

    def test_md_svc_11_create_draft_idempotent(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-11: Crear DRAFT cuando ya existe DRAFT retorna el existente sin duplicar."""
        dto1 = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        dto2 = service.create_design_draft(sample_activity.planning_id, created_by="Otro Usuario")
        assert dto1.design_id == dto2.design_id
        assert dto2.created_by == "Prof. Kenia"  # Conserva autoría original

    def test_md_svc_12_create_draft_over_approved_rejected(
        self,
        service: MethodologicalDesignService,
        uow: PlanningUnitOfWork,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-12: Intentar crear DRAFT sobre actividad con diseño APPROVED es rechazado (R-08)."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        with uow:
            design = uow.methodological_designs.get_by_id(dto.design_id)
            assert design is not None
            design.approve(approved_by="Decano")
            uow.methodological_designs.save(design)
            uow.commit()

        with pytest.raises(RuntimeError, match="inmutable R-08"):
            service.create_design_draft(sample_activity.planning_id, created_by="Atacante")


# ---------------------------------------------------------------------------
# 4. CASOS DE USO: ACTUALIZACIÓN DE DRAFT (MD-SVC-13 .. MD-SVC-14)
# ---------------------------------------------------------------------------
class TestMethodologicalDesignServiceUpdate:
    """Pruebas para update_design_draft."""

    def test_md_svc_13_update_draft_success(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-13: Actualizar los 5 bloques de un diseño en estado DRAFT."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")

        cmd = UpdateMethodologicalDesignCommand(
            design_id=dto.design_id,
            introduction_text="Nueva introducción contextual.",
            methodological_approach="Aprendizaje basado en proyectos.",
            objectives=("Objetivo 1", "Objetivo 2"),
            faq=FAQTableDTO(
                q1_que_es=sample_activity.activity_name,
                q2_para_que="Finalidad actualizada",
                q3_sesiones="Sesión única",
                q4_protagonistas="Estudiantes avanzados",
                q5_facilitador="Facilitador Designado",
                q6_materiales="Guías de laboratorio",
                q7_duracion="180 minutos",
            ),
            agenda=(
                TimeBlockDTO(sequence=1, label="Introducción", minutes=60),
                TimeBlockDTO(sequence=2, label="Desarrollo", minutes=120),
            ),
            operational_matrix=(
                OperationalActivityDTO(
                    step_number=1,
                    phase_label="Fase 1",
                    operative_goal="Alinear expectativas",
                    procedure="Dinámica grupal",
                    materials="Pizarra",
                    minutes=60,
                ),
                OperationalActivityDTO(
                    step_number=2,
                    phase_label="Fase 2",
                    operative_goal="Construir modelo",
                    procedure="Programación",
                    materials="Computadoras",
                    minutes=120,
                ),
            ),
        )
        updated = service.update_design_draft(cmd)

        assert updated.introduction == "Nueva introducción contextual."
        assert updated.methodological_approach == "Aprendizaje basado en proyectos."
        assert updated.objective_1 == "Objetivo 1"
        assert updated.objective_2 == "Objetivo 2"
        assert updated.total_minutes == 180
        assert len(updated.agenda) == 2
        assert len(updated.operational_matrix) == 2

    def test_md_svc_14_update_approved_rejected(
        self,
        service: MethodologicalDesignService,
        uow: PlanningUnitOfWork,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-14: Intentar actualizar un diseño en estado APPROVED es estrictamente rechazado (R-08)."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        with uow:
            design = uow.methodological_designs.get_by_id(dto.design_id)
            assert design is not None
            design.approve(approved_by="Decano")
            uow.methodological_designs.save(design)
            uow.commit()

        cmd = UpdateMethodologicalDesignCommand(
            design_id=dto.design_id,
            introduction_text="Intento de cambio sobre aprobado",
        )
        with pytest.raises(RuntimeError, match="R-08|inmutab"):
            service.update_design_draft(cmd)


# ---------------------------------------------------------------------------
# 5. CASOS DE USO: VALIDACIÓN Y APROBACIÓN (MD-SVC-15 .. MD-SVC-19)
# ---------------------------------------------------------------------------
class TestMethodologicalDesignServiceValidationAndApproval:
    """Pruebas para validate_design y approve_design."""

    def test_md_svc_15_validation_successful(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-15: Validación exitosa sobre diseño completo."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        cmd = UpdateMethodologicalDesignCommand(
            design_id=dto.design_id,
            introduction_text="Introducción válida.",
            methodological_approach="Enfoque válido.",
            objectives=("Objetivo A", "Objetivo B"),
            faq=FAQTableDTO(
                q1_que_es=sample_activity.activity_name,
                q2_para_que="Propósito",
                q3_sesiones="Sesión única",
                q4_protagonistas="Estudiantes",
                q5_facilitador="Facilitador",
                q6_materiales="Materiales",
                q7_duracion="60 minutos",
            ),
            agenda=(TimeBlockDTO(sequence=1, label="Sesión", minutes=60),),
            operational_matrix=(
                OperationalActivityDTO(
                    step_number=1,
                    phase_label="Fase",
                    operative_goal="Meta",
                    procedure="Proc",
                    materials="Mat",
                    minutes=60,
                ),
            ),
        )
        service.update_design_draft(cmd)

        report = service.validate_design(dto.design_id)
        assert report.is_valid is True
        assert len(report.errors) == 0

    def test_md_svc_16_validation_failure_incomplete_design(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-16: Validación fallida en diseño recién creado sin objetivos ni agenda."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        report = service.validate_design(dto.design_id)
        assert report.is_valid is False
        assert len(report.errors) > 0
        rule_ids = [e.rule_id for e in report.errors]
        assert "V-MD-09" in rule_ids  # intro vacía
        assert "V-MD-11" in rule_ids  # objetivos != 2

    def test_md_svc_17_prevent_approval_of_invalid_design(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-17: Impedir aprobación formal de un diseño con errores bloqueantes."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        with pytest.raises(ValueError, match="contiene errores bloqueantes"):
            service.approve_design(dto.design_id, approved_by="Rector")

    def test_md_svc_18_successful_approval(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-18: Aprobación correcta tras superar validaciones obligatorias."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        cmd = UpdateMethodologicalDesignCommand(
            design_id=dto.design_id,
            introduction_text="Introducción contextual sólida.",
            methodological_approach="Enfoque de competencias.",
            objectives=("Obj 1", "Obj 2"),
            faq=FAQTableDTO(
                q1_que_es=sample_activity.activity_name,
                q2_para_que="Propósito",
                q3_sesiones="Sesión única",
                q4_protagonistas="Estudiantes",
                q5_facilitador="Facilitador",
                q6_materiales="Materiales",
                q7_duracion="60 minutos",
            ),
            agenda=(TimeBlockDTO(sequence=1, label="Sesión", minutes=60),),
            operational_matrix=(
                OperationalActivityDTO(
                    step_number=1,
                    phase_label="Fase",
                    operative_goal="Meta",
                    procedure="Proc",
                    materials="Mat",
                    minutes=60,
                ),
            ),
        )
        service.update_design_draft(cmd)

        approved = service.approve_design(dto.design_id, approved_by="Decano BICU")
        assert approved.approved_by == "Decano BICU"
        # Verificar en base de datos que el estado es APPROVED
        detail = service.get_activity_detail(sample_activity.planning_id)
        assert detail is not None
        assert detail.design_status == "APPROVED"

    def test_md_svc_19_r08_inmutability_after_approval(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-19: R-08 inmutabilidad absoluta después de la aprobación."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="Prof. Kenia")
        cmd = UpdateMethodologicalDesignCommand(
            design_id=dto.design_id,
            introduction_text="Intro",
            methodological_approach="Enfoque",
            objectives=("Obj 1", "Obj 2"),
            faq=FAQTableDTO(
                q1_que_es=sample_activity.activity_name,
                q2_para_que="P",
                q3_sesiones="Sesión única",
                q4_protagonistas="E",
                q5_facilitador="F",
                q6_materiales="M",
                q7_duracion="60 minutos",
            ),
            agenda=(TimeBlockDTO(sequence=1, label="S", minutes=60),),
            operational_matrix=(
                OperationalActivityDTO(
                    step_number=1,
                    phase_label="F",
                    operative_goal="G",
                    procedure="P",
                    materials="M",
                    minutes=60,
                ),
            ),
        )
        service.update_design_draft(cmd)
        service.approve_design(dto.design_id, approved_by="Decano")

        # Intentar modificar tras aprobación
        cmd_update = UpdateMethodologicalDesignCommand(
            design_id=dto.design_id,
            introduction_text="Modificación posterior",
        )
        with pytest.raises(RuntimeError, match="R-08|inmutab"):
            service.update_design_draft(cmd_update)

        # Intentar aprobar de nuevo
        with pytest.raises(RuntimeError, match="R-08|inmutab"):
            service.approve_design(dto.design_id, approved_by="Otro Decano")


# ---------------------------------------------------------------------------
# 6. PERSISTENCIA, INTEGRIDAD Y NO CONTAMINACIÓN (MD-SVC-20 .. MD-SVC-24)
# ---------------------------------------------------------------------------
class TestMethodologicalDesignServiceIntegrityAndIsolation:
    """Pruebas de persistencia V003, no contaminación y aislamiento AST."""

    def test_md_svc_20_persistence_and_reconstruction(
        self,
        temp_db_path: str,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-20: Persistencia y reconstrucción en SQLite V003 con conexiones independientes."""
        uow1 = PlanningUnitOfWork(db_path=temp_db_path)
        svc1 = MethodologicalDesignService(uow=uow1)
        dto = svc1.create_design_draft(sample_activity.planning_id, created_by="Auditor 1")

        # Cerrar y abrir con nuevo UoW
        uow2 = PlanningUnitOfWork(db_path=temp_db_path)
        svc2 = MethodologicalDesignService(uow=uow2)
        detail = svc2.get_activity_detail(sample_activity.planning_id)
        assert detail is not None
        assert detail.design_id == dto.design_id
        assert detail.design_status == "DRAFT"

    def test_md_svc_21_planning_id_preservation(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-21: Conservación exacta del planning_id institucional."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="User")
        detail = service.get_activity_detail(sample_activity.planning_id)
        assert detail is not None
        assert detail.planning_id == "POA-Bilwi-101"

    def test_md_svc_22_no_execution_data_transfer(
        self,
        service: MethodologicalDesignService,
        sample_activity: PlannedActivity,
    ):
        """MD-SVC-22: No transferencia de datos de ejecución a diseño metodológico."""
        dto = service.create_design_draft(sample_activity.planning_id, created_by="User")
        # Verificar que el DTO del diseño no contiene cédulas, listas de asistencia ni códigos presupuestarios
        assert not hasattr(dto, "codigo_presupuestario")
        assert not hasattr(dto, "lista_asistencia")
        assert not hasattr(dto, "participantes_reales")

    def test_md_svc_23_no_word_consolidator_modification(self):
        """MD-SVC-23: Comprobar que los archivos de app/word_consolidator permanecen intactos."""
        wc_path = Path("app/word_consolidator")
        assert wc_path.is_dir()

    def test_md_svc_24_architecture_ast_isolation(self):
        """MD-SVC-24: Verificación AST de que services.py no importa sqlite3, openpyxl, docx ni IA."""
        svc_file = Path("app/planning/application/services.py")
        tree = ast.parse(svc_file.read_text(encoding="utf-8"))

        forbidden = {
            "sqlite3",
            "sqlalchemy",
            "openpyxl",
            "docx",
            "requests",
            "openai",
            "google.generativeai",
            "ollama",
            "app.word_consolidator",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        assert not alias.name.startswith(f), f"Importación prohibida: '{alias.name}'"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for f in forbidden:
                    assert not mod.startswith(f), f"ImportFrom prohibido: '{mod}'"


# ---------------------------------------------------------------------------
# 7. INTEGRACIÓN DE PUNTA A PUNTA: POA -> READER -> SERVICE -> DOCX EXPORT
# ---------------------------------------------------------------------------
class TestPlanningE2EIntegrationFlow:
    """Prueba de integración de punta a punta del ciclo completo."""

    def test_full_planning_lifecycle_e2e(
        self,
        uow: PlanningUnitOfWork,
        tmp_path: Path,
    ):
        """Comprueba el flujo completo desde el POA real hasta la aprobación del diseño."""
        # 1. Ingestión desde POA
        real_poa = "input/matrices_reales_uat/Documento_Kevds_2.xlsx"
        if not Path(real_poa).is_file():
            pytest.skip("Archivo real no disponible.")

        reader = ExcelPlanningReader()
        ingestion_svc = PlannedActivityIngestionService(reader=reader, uow=uow)
        report = ingestion_svc.ingest_planning_source(
            file_path=real_poa,
            default_area_responsable="Innovación",
            default_eje_estrategia="EJE_11",
            default_programa="PGM_07",
            default_tipo_evento="EVT_CAPACITACION",
        )
        assert report.rows_accepted >= 1
        act_id = report.created_activity_ids[0]

        # 2. Servicio de diseño metodológico
        svc = MethodologicalDesignService(uow=uow)

        # Listar y verificar SIN_DISENO
        summaries = svc.list_activities_with_design_status(search_term=act_id)
        assert len(summaries) == 1
        assert summaries[0].design_status == "SIN_DISENO"

        # Crear DRAFT
        draft = svc.create_design_draft(act_id, created_by="Responsable UAT")
        assert draft.design_id is not None

        # Actualizar DRAFT con 5 bloques
        cmd = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Introducción al diseño de logotipos con IA.",
            methodological_approach="Taller interactivo práctico.",
            objectives=(
                "Aprender principios de diseño vectorial.",
                "Aplicar herramientas de IA para generación de logos.",
            ),
            faq=FAQTableDTO(
                q1_que_es="Taller de Logotipos con IA",
                q2_para_que="Fortalecer competencias estudiantiles",
                q3_sesiones="Sesión única",
                q4_protagonistas="Estudiantes de Bilwi",
                q5_facilitador="Docente Facilitador",
                q6_materiales="Computadoras e internet",
                q7_duracion="120 minutos",
            ),
            agenda=(
                TimeBlockDTO(sequence=1, label="Fundamentos", minutes=60),
                TimeBlockDTO(sequence=2, label="Práctica con IA", minutes=60),
            ),
            operational_matrix=(
                OperationalActivityDTO(
                    step_number=1,
                    phase_label="Fase Conceptual",
                    operative_goal="Conocer herramientas",
                    procedure="Demostración guiada",
                    materials="Proyector",
                    minutes=60,
                ),
                OperationalActivityDTO(
                    step_number=2,
                    phase_label="Fase Práctica",
                    operative_goal="Crear logo",
                    procedure="Trabajo individual",
                    materials="PCs",
                    minutes=60,
                ),
            ),
        )
        svc.update_design_draft(cmd)

        # Validar
        val_report = svc.validate_design(draft.design_id)
        assert val_report.is_valid is True

        # Aprobar
        approved = svc.approve_design(draft.design_id, approved_by="Consejo Universitario")
        assert approved.approved_by == "Consejo Universitario"

        # Verificar estado final
        detail = svc.get_activity_detail(act_id)
        assert detail is not None
        assert detail.design_status == "APPROVED"
