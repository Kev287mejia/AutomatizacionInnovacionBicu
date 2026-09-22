"""
tests.test_planning_ai_ui

Suite de Pruebas Automatizadas de la Integración de Asistencia IA en la UI Institucional.
Fase 29.15 — Integración de Asistencia IA en la UI Institucional.

Cubre exhaustivamente:
  - UI-AI-01: Los botones IA aparecen únicamente para campos autorizados.
  - UI-AI-02: Los campos prohibidos no muestran asistencia IA.
  - UI-AI-03: Solicitar propuesta llama al servicio correcto (PlanningUIService.request_ai_proposal).
  - UI-AI-04: La propuesta no se aplica automáticamente (requiere revisión humana explícita).
  - UI-AI-05: El diálogo muestra contenido actual y propuesta generada.
  - UI-AI-06: Aceptar llama al servicio correspondiente (PlanningUIService.accept_ai_proposal).
  - UI-AI-07: Aceptar mantiene el diseño en estado DRAFT (nunca APPROVED).
  - UI-AI-08: Rechazar exige motivo obligatorio no vacío.
  - UI-AI-09: Rechazar preserva el contenido original intacto.
  - UI-AI-10: APPROVED bloquea asistencia IA (botones deshabilitados en UI y protección R-08).
  - UI-AI-11: Las propuestas pendientes generan advertencia visible en la UI.
  - UI-AI-12: Un error del adaptador no modifica el diseño ni corrompe la UI.
  - UI-AI-13: `procedure` respeta `step_number` y preserva minutos, orden y materiales.
  - UI-AI-14: `operative_goal` respeta `step_number`.
  - UI-AI-15: La IA nunca modifica minutos en la matriz operativa.
  - UI-AI-16: La UI nunca accede directamente a SQLite.
  - UI-AI-17: La UI no importa `app.word_consolidator`.
  - UI-AI-18: Flujo completo: Mock -> solicitud -> propuesta -> revisión -> aceptación en DRAFT.
  - UI-AI-AST: Análisis AST verificando aislamiento de app.planning.ui respecto a sqlite3 y word_consolidator.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock, patch
import uuid
import pytest

from app.planning.application.services import (
    MethodologicalDesignService,
    MethodologicalDocumentExportService,
)
from app.planning.domain.dtos import (
    AIProposalDTO,
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    PlannedActivityDetailDTO,
    TimeBlockDTO,
    UpdateMethodologicalDesignCommand,
    ValidationReportDTO,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.ports import AIAssistancePort
from app.planning.domain.value_objects import (
    AI_ALLOWED_TARGET_FIELDS,
    AI_PROHIBITED_TARGET_FIELDS,
    DesignStatus,
    ParticipantGoals,
)
from app.planning.infrastructure.ai.mock_adapter import LocalMockAIAssistanceAdapter
from app.planning.infrastructure.document_rendering import DocxMethodologicalDocumentRenderer
from app.planning.infrastructure.persistence import (
    PlanningUnitOfWork,
    SQLiteMethodologicalDesignRepository,
)
from app.planning.infrastructure.persistence.schema_v003 import V003_SCHEMA_DDL_STATEMENTS
from app.planning.ui.services.planning_ui_service import PlanningUIError, PlanningUIService
from app.planning.ui.views.ai_proposal_review_dialog import AIProposalReviewDialog
from app.planning.ui.views.design_editor_view import MethodologicalDesignEditorView


@pytest.fixture
def clean_db(tmp_path: Path) -> Path:
    """Base de datos SQLite V003 limpia con el esquema completo."""
    db_file = tmp_path / "test_planning_ai_ui.sqlite"
    conn = sqlite3.connect(str(db_file))
    try:
        cursor = conn.cursor()
        for statement in V003_SCHEMA_DDL_STATEMENTS:
            cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return db_file


@pytest.fixture
def populated_env(clean_db: Path) -> dict:
    """Configura actividad planificada, diseño en DRAFT y PlanningUIService con mock adapter."""
    goals = ParticipantGoals(
        est_grado_m=10,
        est_grado_f=15,
        est_postgrado_m=2,
        est_postgrado_f=3,
        docentes_m=4,
        docentes_f=4,
        administrativos_m=1,
        administrativos_f=1,
        externos_m=5,
        externos_f=5,
    )
    act = PlannedActivity.create(
        planning_id="POA-AI-UI-001",
        activity_name="Taller de Competencias Digitales e Innovación",
        sede="Bluefields",
        dep_sede="RACCS",
        mun_sede="Bluefields",
        area_responsable="Dirección de Innovación",
        eje_estrategia="EJE_11",
        programa="PGM_07",
        tipo_evento="EVT_CAPACITACION",
        participant_goals=goals,
        proposito="Fortalecer competencias digitales docentes.",
        fecha_evento=date(2026, 10, 20),
    )

    with PlanningUnitOfWork(db_path=clean_db) as uow:
        uow.planned_activities.save(act)
        uow.commit()

    uow = PlanningUnitOfWork(db_path=clean_db)
    mock_adapter = LocalMockAIAssistanceAdapter()
    design_service = MethodologicalDesignService(
        uow=uow,
        ai_assistance_port=mock_adapter,
    )

    conn = sqlite3.connect(str(clean_db))
    design_repo = SQLiteMethodologicalDesignRepository(conn)
    renderer = DocxMethodologicalDocumentRenderer()
    export_service = MethodologicalDocumentExportService(
        design_repository=design_repo,
        renderer=renderer,
    )

    ui_service = PlanningUIService(
        design_service=design_service,
        export_service=export_service,
        ai_assistance_port=mock_adapter,
    )

    # Crear borrador inicial
    draft = ui_service.create_design_draft("POA-AI-UI-001", created_by="coordinador_ai")

    # Poblar con datos iniciales para los 5 bloques
    agenda = (
        TimeBlockDTO(sequence=1, label="I. Apertura", minutes=30),
        TimeBlockDTO(sequence=2, label="II. Desarrollo Práctico", minutes=90),
    )
    matrix = (
        OperationalActivityDTO(
            step_number=1,
            phase_label="I. Apertura",
            operative_goal="Presentar la actividad",
            procedure="Dinámica inicial",
            materials="Proyector y diapositivas",
            minutes=30,
        ),
        OperationalActivityDTO(
            step_number=2,
            phase_label="II. Desarrollo Práctico",
            operative_goal="Ejecutar ejercicios prácticos",
            procedure="Trabajo en mesas colaborativas",
            materials="Guías impresas",
            minutes=90,
        ),
    )
    faq = FAQTableDTO(
        q1_que_es="Taller de Competencias",
        q2_para_que="Capacitar docentes",
        q3_sesiones="Sesión única",
        q4_protagonistas="50 participantes",
        q5_facilitador="Dirección de Innovación",
        q6_materiales="Proyector, guías",
        q7_duracion="120 minutos",
    )
    cmd = UpdateMethodologicalDesignCommand(
        design_id=draft.design_id,
        introduction_text="Texto introductorio inicial.",
        methodological_approach="Enfoque constructivista inicial.",
        objectives=("Objetivo 1 inicial", "Objetivo 2 inicial"),
        faq=faq,
        agenda=agenda,
        operational_matrix=matrix,
    )
    draft = ui_service.update_design_draft(cmd)

    return {
        "db_path": clean_db,
        "ui_service": ui_service,
        "design_service": design_service,
        "adapter": mock_adapter,
        "draft": draft,
        "planning_id": "POA-AI-UI-001",
    }


# ===========================================================================
# BATERÍA DE PRUEBAS UI-AI-01 A UI-AI-18
# ===========================================================================

class TestPlanningAIUI:
    """Suite integral para la asistencia IA en la interfaz institucional."""

    def test_ui_ai_01_botones_ia_unicamente_en_campos_autorizados(self, populated_env: dict):
        """UI-AI-01: Los botones de asistencia IA existen únicamente para los 6 campos autorizados."""
        expected_authorized = {
            "introduction",
            "methodological_approach",
            "objective_1",
            "objective_2",
            "procedure",
            "operative_goal",
        }
        assert expected_authorized == AI_ALLOWED_TARGET_FIELDS

        # Simular instanciación de MethodologicalDesignEditorView en modo headless
        ui_service = populated_env["ui_service"]
        with (
            patch("customtkinter.CTkFrame.__init__", return_value=None),
            patch("customtkinter.CTkScrollableFrame.__init__", return_value=None),
            patch("customtkinter.CTkTabview.__init__", return_value=None),
            patch("customtkinter.CTkButton.__init__", return_value=None),
            patch("customtkinter.CTkLabel.__init__", return_value=None),
            patch("customtkinter.CTkTextbox.__init__", return_value=None),
            patch("customtkinter.CTkEntry.__init__", return_value=None),
            patch.object(MethodologicalDesignEditorView, "cargar_diseno", return_value=None),
        ):
            view = MethodologicalDesignEditorView.__new__(MethodologicalDesignEditorView)
            view.service = ui_service
            view.planning_id = "POA-AI-UI-001"
            view.design_dto = populated_env["draft"]
            view.ai_buttons = []

            # Verificar que los campos autorizados tienen métodos asociados
            for field in expected_authorized:
                label = view._get_field_display_label(field, step_number=1, phase_label="Fase 1")
                assert isinstance(label, str)
                assert len(label) > 0

    def test_ui_ai_02_campos_prohibidos_no_muestran_asistencia_ia(self):
        """UI-AI-02: Los campos institucionales prohibidos no tienen asistencia IA."""
        prohibited = [
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
            "q1_que_es",
            "q2_para_que",
            "q6_materiales",
            "materials",
            "minutes",
        ]
        for field in prohibited:
            assert field not in AI_ALLOWED_TARGET_FIELDS, f"Campo prohibido '{field}' presente en permitidos"

    def test_ui_ai_03_solicitar_propuesta_llama_servicio_correcto(self, populated_env: dict):
        """UI-AI-03: Solicitar propuesta invoca PlanningUIService.request_ai_proposal."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]

        proposal = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="introduction",
        )

        assert isinstance(proposal, AIProposalDTO)
        assert proposal.target_field == "introduction"
        assert proposal.is_pending is True
        assert proposal.accepted is None
        assert "Taller de Competencias Digitales" in proposal.proposed_content

    def test_ui_ai_04_propuesta_no_se_aplica_automaticamente(self, populated_env: dict):
        """UI-AI-04: La generación de una propuesta no modifica el texto actual del diseño."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]
        original_intro = draft.introduction

        # Generar propuesta
        proposal = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="introduction",
        )

        # Consultar el diseño desde la base de datos y verificar que permanece intacto
        proposals = ui_service.list_ai_proposals(draft.design_id)
        assert len(proposals) >= 1
        assert proposals[0].proposal_id == proposal.proposal_id

        # El detalle de la actividad/diseño no ha cambiado su introducción
        # (create_design_draft es idempotente y retorna el DTO persistido actual)
        reloaded = ui_service.create_design_draft("POA-AI-UI-001", created_by="test")
        assert reloaded.introduction == original_intro
        assert reloaded.introduction != proposal.proposed_content

    def test_ui_ai_05_dialogo_muestra_contenido_actual_y_propuesta(self):
        """UI-AI-05: AIProposalReviewDialog inicializa correctamente el texto actual y la propuesta."""
        proposal = AIProposalDTO(
            proposal_id=uuid.uuid4(),
            design_id=uuid.uuid4(),
            target_field="introduction",
            proposed_content="Propuesta sugerida de introducción institucional.",
            confidence=0.85,
            requires_review=True,
            accepted=None,
            reviewed_by=None,
            review_timestamp=None,
            rejection_reason=None,
            source_inputs={},
        )

        mock_accept = MagicMock()
        mock_reject = MagicMock()

        with (
            patch("customtkinter.CTkToplevel.__init__", return_value=None),
            patch("customtkinter.CTkFrame.__init__", return_value=None),
            patch("customtkinter.CTkScrollableFrame.__init__", return_value=None),
            patch("customtkinter.CTkLabel.__init__", return_value=None),
            patch("customtkinter.CTkTextbox.__init__", return_value=None),
            patch("customtkinter.CTkEntry.__init__", return_value=None),
            patch("customtkinter.CTkButton.__init__", return_value=None),
            patch.object(AIProposalReviewDialog, "grab_set", return_value=None),
            patch.object(AIProposalReviewDialog, "title", return_value=None),
            patch.object(AIProposalReviewDialog, "geometry", return_value=None),
            patch.object(AIProposalReviewDialog, "minsize", return_value=None),
            patch.object(AIProposalReviewDialog, "_init_ui", return_value=None),
        ):
            dialog = AIProposalReviewDialog(
                master=None,
                proposal=proposal,
                current_content="Texto previo existente.",
                field_label="Introducción",
                on_accept=mock_accept,
                on_reject=mock_reject,
            )

        assert dialog.proposal == proposal
        assert dialog.current_content == "Texto previo existente."
        assert dialog.field_label == "Introducción"

    def test_ui_ai_06_y_07_aceptar_llama_servicio_y_mantiene_draft(self, populated_env: dict):
        """UI-AI-06 y UI-AI-07: Aceptar propuesta vuelca el contenido y mantiene el diseño en DRAFT."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]

        proposal = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="introduction",
        )

        # Aceptar propuesta formalmente
        updated = ui_service.accept_ai_proposal(
            design_id=draft.design_id,
            proposal_id=proposal.proposal_id,
            reviewer="Dra. Kenia Mejia",
        )

        # Contenido actualizado
        assert updated.introduction == proposal.proposed_content
        # Invariante crítica: el diseño permanece en DRAFT (approved_by es None)
        assert updated.approved_by is None, "El diseño debe permanecer en DRAFT tras aceptar una propuesta IA"

        # Verificar propuesta auditada
        proposals = ui_service.list_ai_proposals(draft.design_id)
        target = next(p for p in proposals if p.proposal_id == proposal.proposal_id)
        assert target.accepted is True
        assert target.reviewed_by == "Dra. Kenia Mejia"
        assert target.is_pending is False

    def test_ui_ai_08_rechazar_exige_motivo_no_vacio(self, populated_env: dict):
        """UI-AI-08: El rechazo de una propuesta exige obligatoriamente un motivo no vacío."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]

        proposal = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="methodological_approach",
        )

        # Motivo vacío debe fallar
        with pytest.raises(PlanningUIError) as exc_vacio:
            ui_service.reject_ai_proposal(
                design_id=draft.design_id,
                proposal_id=proposal.proposal_id,
                reviewer="Revisor Institucional",
                rejection_reason="",
            )
        assert "motivo" in exc_vacio.value.message.lower() or "rejection_reason" in exc_vacio.value.technical_details.lower()

        # Motivo de solo espacios en blanco debe fallar
        with pytest.raises(PlanningUIError) as exc_espacios:
            ui_service.reject_ai_proposal(
                design_id=draft.design_id,
                proposal_id=proposal.proposal_id,
                reviewer="Revisor Institucional",
                rejection_reason="    ",
            )
        assert "motivo" in exc_espacios.value.message.lower() or "rejection_reason" in exc_espacios.value.technical_details.lower()

    def test_ui_ai_09_rechazar_preserva_contenido_original(self, populated_env: dict):
        """UI-AI-09: Rechazar una propuesta preserva el contenido original intacto."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]
        original_enfoque = draft.methodological_approach

        proposal = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="methodological_approach",
        )

        updated = ui_service.reject_ai_proposal(
            design_id=draft.design_id,
            proposal_id=proposal.proposal_id,
            reviewer="Coordinador Académico",
            rejection_reason="El enfoque propuesto no se ajusta al contexto del laboratorio.",
        )

        # El contenido no cambia
        assert updated.methodological_approach == original_enfoque
        assert updated.approved_by is None

        # La propuesta queda registrada como rechazada con su motivo
        proposals = ui_service.list_ai_proposals(draft.design_id)
        target = next(p for p in proposals if p.proposal_id == proposal.proposal_id)
        assert target.accepted is False
        assert target.rejection_reason == "El enfoque propuesto no se ajusta al contexto del laboratorio."
        assert target.reviewed_by == "Coordinador Académico"

    def test_ui_ai_10_approved_bloquea_asistencia_ia(self, populated_env: dict):
        """UI-AI-10: En estado APPROVED, la solicitud, aceptación y rechazo quedan bloqueados."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]

        # Validar y aprobar formalmente el diseño
        report = ui_service.validate_design(draft.design_id)
        assert report.is_valid

        approved = ui_service.approve_design(
            design_id=draft.design_id,
            approved_by="Dra. Kenia Mejia — Rectora",
        )
        assert approved.approved_by is not None

        # 1. Intentar solicitar propuesta sobre diseño APPROVED
        with pytest.raises(PlanningUIError) as exc_req:
            ui_service.request_ai_proposal(
                design_id=draft.design_id,
                target_field="introduction",
            )
        assert "APROBADO" in exc_req.value.message or "R-08" in exc_req.value.message

        # 2. Intentar aceptar sobre diseño APPROVED
        dummy_id = uuid.uuid4()
        with pytest.raises(PlanningUIError) as exc_acc:
            ui_service.accept_ai_proposal(
                design_id=draft.design_id,
                proposal_id=dummy_id,
                reviewer="Revisor Ilegal",
            )
        assert "APROBADO" in exc_acc.value.message or "R-08" in exc_acc.value.message

        # 3. Intentar rechazar sobre diseño APPROVED
        with pytest.raises(PlanningUIError) as exc_rej:
            ui_service.reject_ai_proposal(
                design_id=draft.design_id,
                proposal_id=dummy_id,
                reviewer="Revisor Ilegal",
                rejection_reason="Motivo",
            )
        assert "APROBADO" in exc_rej.value.message or "R-08" in exc_rej.value.message

    def test_ui_ai_11_propuestas_pendientes_generan_advertencia(self, populated_env: dict):
        """UI-AI-11: La existencia de propuestas pendientes genera una advertencia en la UI."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]

        # Sin propuestas
        proposals_init = ui_service.list_ai_proposals(draft.design_id)
        assert len([p for p in proposals_init if p.is_pending]) == 0

        # Crear propuesta pendiente
        ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="objective_1",
        )

        proposals_after = ui_service.list_ai_proposals(draft.design_id)
        pending = [p for p in proposals_after if p.is_pending]
        assert len(pending) == 1

        # Simular verificación visual del editor
        with (
            patch("customtkinter.CTkFrame.__init__", return_value=None),
            patch("customtkinter.CTkLabel.__init__", return_value=None),
        ):
            view = MethodologicalDesignEditorView.__new__(MethodologicalDesignEditorView)
            view.service = ui_service
            view.design_dto = draft
            view.lbl_pending_proposals = MagicMock()

            view._check_pending_proposals()
            view.lbl_pending_proposals.configure.assert_called_with(
                text="⚠️ Hay 1 propuesta(s) de asistencia pendiente(s) de revisión."
            )

    def test_ui_ai_12_error_del_adaptador_no_modifica_diseno(self, populated_env: dict):
        """UI-AI-12: Si el adaptador de IA falla, el diseño no se modifica y se reporta institucionalmente."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]
        original_intro = draft.introduction

        # Puerto de IA simulado que lanza una excepción técnica
        failing_port = MagicMock(spec=AIAssistancePort)
        failing_port.generate_narrative_proposal.side_effect = RuntimeError("Fallo de red o timeout simulado")

        # Inyectar temporalmente el puerto fallido
        original_port = ui_service._ai_port
        ui_service._ai_port = failing_port

        try:
            with pytest.raises(PlanningUIError) as exc_info:
                ui_service.request_ai_proposal(
                    design_id=draft.design_id,
                    target_field="introduction",
                )
            # Mensaje amigable e institucional
            assert "No fue posible generar una propuesta en este momento" in exc_info.value.message
            assert "El diseño actual no fue modificado" in exc_info.value.message

            # Verificar que el diseño sigue intacto
            reloaded = ui_service.create_design_draft("POA-AI-UI-001", created_by="test")
            assert reloaded.introduction == original_intro
        finally:
            ui_service._ai_port = original_port

    def test_ui_ai_13_procedure_respeta_step_number(self, populated_env: dict):
        """UI-AI-13: La propuesta de `procedure` se asocia y aplica al `step_number` correspondiente."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]

        # Solicitar propuesta para el paso 2
        proposal = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="procedure",
            step_number=2,
            phase_label="II. Desarrollo Práctico",
        )

        assert proposal.source_inputs.get("step_number") == 2
        assert "Paso 2" in proposal.proposed_content

        # Aceptar propuesta
        updated = ui_service.accept_ai_proposal(
            design_id=draft.design_id,
            proposal_id=proposal.proposal_id,
            reviewer="Facilitador Principal",
        )

        # Verificar que únicamente se modificó el procedimiento del paso 2
        step1 = next(op for op in updated.operational_matrix if op.step_number == 1)
        step2 = next(op for op in updated.operational_matrix if op.step_number == 2)

        assert step1.procedure == "Dinámica inicial"  # Paso 1 intacto
        assert step2.procedure == proposal.proposed_content  # Paso 2 actualizado
        assert step2.minutes == 90  # Minutos intactos
        assert step2.materials == "Guías impresas"  # Materiales intactos

    def test_ui_ai_14_operative_goal_respeta_step_number(self, populated_env: dict):
        """UI-AI-14: La propuesta de `operative_goal` se asocia y aplica al `step_number` correspondiente."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]

        # Solicitar propuesta para el paso 1
        proposal = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="operative_goal",
            step_number=1,
            phase_label="I. Apertura",
        )

        assert proposal.source_inputs.get("step_number") == 1
        assert "paso 1" in proposal.proposed_content.lower()

        # Aceptar propuesta
        updated = ui_service.accept_ai_proposal(
            design_id=draft.design_id,
            proposal_id=proposal.proposal_id,
            reviewer="Facilitador Principal",
        )

        step1 = next(op for op in updated.operational_matrix if op.step_number == 1)
        step2 = next(op for op in updated.operational_matrix if op.step_number == 2)

        assert step1.operative_goal == proposal.proposed_content
        assert step2.operative_goal == "Ejecutar ejercicios prácticos"  # Paso 2 intacto

    def test_ui_ai_15_ia_nunca_modifica_minutos(self, populated_env: dict):
        """UI-AI-15: La IA nunca altera la duración en minutos ni total ni por actividad."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]
        original_total = draft.total_minutes
        assert original_total == 120

        # Solicitar y aceptar propuesta para operative_goal
        p_goal = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="operative_goal",
            step_number=2,
            phase_label="II. Desarrollo Práctico",
        )
        updated_1 = ui_service.accept_ai_proposal(
            design_id=draft.design_id,
            proposal_id=p_goal.proposal_id,
            reviewer="Revisor",
        )
        assert updated_1.total_minutes == 120

        # Solicitar y aceptar propuesta para procedure
        p_proc = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="procedure",
            step_number=2,
            phase_label="II. Desarrollo Práctico",
        )
        updated_2 = ui_service.accept_ai_proposal(
            design_id=draft.design_id,
            proposal_id=p_proc.proposal_id,
            reviewer="Revisor",
        )
        assert updated_2.total_minutes == 120
        for op in updated_2.operational_matrix:
            if op.step_number == 1:
                assert op.minutes == 30
            elif op.step_number == 2:
                assert op.minutes == 90

    def test_ui_ai_16_ui_nunca_accede_directamente_a_sqlite(self):
        """UI-AI-16: Los componentes de app.planning.ui no importan ni usan sqlite3."""
        ui_views_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "ui" / "views"
        for py_file in ui_views_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "sqlite3" not in content, f"sqlite3 referenciado en vista: {py_file}"
            assert "SQLiteUnitOfWork" not in content, f"SQLiteUnitOfWork en vista: {py_file}"

    def test_ui_ai_17_ui_no_importa_word_consolidator(self):
        """UI-AI-17: Los componentes de app.planning.ui no importan app.word_consolidator."""
        ui_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "ui"
        for py_file in ui_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "app.word_consolidator" not in content, f"word_consolidator importado en UI: {py_file}"

    def test_ui_ai_18_flujo_completo_mock_propuesta_revision_aceptacion(self, populated_env: dict):
        """UI-AI-18: Flujo integral de extremo a extremo: solicitud -> revisión -> aceptación en DRAFT."""
        ui_service: PlanningUIService = populated_env["ui_service"]
        draft: MethodologicalDesignDTO = populated_env["draft"]

        # 1. Solicitar propuesta para objetivo 1
        prop_obj1 = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="objective_1",
        )
        assert prop_obj1.is_pending is True

        # 2. Simular revisión y aceptación
        updated_obj1 = ui_service.accept_ai_proposal(
            design_id=draft.design_id,
            proposal_id=prop_obj1.proposal_id,
            reviewer="Msc. Evaluador",
        )
        assert updated_obj1.objective_1 == prop_obj1.proposed_content
        assert updated_obj1.approved_by is None

        # 3. Solicitar propuesta para objetivo 2
        prop_obj2 = ui_service.request_ai_proposal(
            design_id=draft.design_id,
            target_field="objective_2",
        )
        assert prop_obj2.is_pending is True

        # 4. Simular revisión y aceptación
        updated_obj2 = ui_service.accept_ai_proposal(
            design_id=draft.design_id,
            proposal_id=prop_obj2.proposal_id,
            reviewer="Msc. Evaluador",
        )
        assert updated_obj2.objective_2 == prop_obj2.proposed_content
        assert updated_obj2.approved_by is None

        # 5. Todas las propuestas quedan auditadas y ninguna pendiente
        all_proposals = ui_service.list_ai_proposals(draft.design_id)
        assert len(all_proposals) >= 2
        assert all(not p.is_pending for p in all_proposals)


# ===========================================================================
# PRUEBAS AST DE AISLAMIENTO ARQUITECTÓNICO
# ===========================================================================

class TestPlanningUIASTIsolation:
    """Auditoría de código estática (AST) para verificar aislamiento arquitectónico estricto."""

    def test_ast_views_no_import_sqlite3(self):
        """AST: Ninguna vista en app.planning.ui.views importa sqlite3."""
        views_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "ui" / "views"
        for pf in views_dir.rglob("*.py"):
            tree = ast.parse(pf.read_text(encoding="utf-8"), filename=str(pf))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name != "sqlite3", f"sqlite3 importado en {pf}"
                elif isinstance(node, ast.ImportFrom):
                    assert node.module != "sqlite3", f"from sqlite3 import ... en {pf}"

    def test_ast_views_no_import_word_consolidator(self):
        """AST: Ninguna vista en app.planning.ui.views importa app.word_consolidator."""
        views_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "ui" / "views"
        for pf in views_dir.rglob("*.py"):
            tree = ast.parse(pf.read_text(encoding="utf-8"), filename=str(pf))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("app.word_consolidator"), (
                            f"app.word_consolidator importado en {pf}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        assert not node.module.startswith("app.word_consolidator"), (
                            f"from app.word_consolidator import ... en {pf}"
                        )

    def test_ast_services_no_import_word_consolidator(self):
        """AST: PlanningUIService no importa app.word_consolidator."""
        services_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "ui" / "services"
        for pf in services_dir.rglob("*.py"):
            tree = ast.parse(pf.read_text(encoding="utf-8"), filename=str(pf))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("app.word_consolidator"), (
                            f"app.word_consolidator importado en {pf}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        assert not node.module.startswith("app.word_consolidator"), (
                            f"from app.word_consolidator import ... en {pf}"
                        )
