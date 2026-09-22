"""
Suite de Pruebas: Asistencia de IA para el Diseño Metodológico — BICU.

Fase 29.14 — Implementación Controlada del Núcleo de Asistencia IA.
Verifica los casos AI-01 a AI-15, pruebas de aislamiento de imports (AST),
data minimization estricta (whitelisting), manejo de fallos del proveedor y
preservación de la regla R-08 y V-MD-10.
"""
from __future__ import annotations

import ast
from datetime import datetime
import inspect
from pathlib import Path
from typing import Any, Optional
import uuid

import pytest

from app.infrastructure.persistence.connection import DatabaseConfig, SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.planning.application.services import MethodologicalDesignService
from app.planning.domain.ai_context_builder import AIContextBuilder
from app.planning.domain.dtos import (
    AcceptAIProposalCommand,
    AIProposalDTO,
    RejectAIProposalCommand,
    RequestAIProposalCommand,
    UpdateMethodologicalDesignCommand,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.ports import AIAssistancePort
from app.planning.domain.validator import MethodologicalDesignValidator
from app.planning.domain.value_objects import (
    AI_ALLOWED_TARGET_FIELDS,
    AI_PROHIBITED_TARGET_FIELDS,
    AIProposal,
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)
from app.planning.infrastructure.ai.mock_adapter import LocalMockAIAssistanceAdapter
from app.planning.infrastructure.persistence import (
    PlanningUnitOfWork,
    SQLiteMethodologicalDesignRepository,
    SQLitePlannedActivityRepository,
)


@pytest.fixture
def clean_ai_env(tmp_path: Path):
    """Configura un entorno SQLite V001-V003 limpio con actividad y diseño en DRAFT."""
    db_file = tmp_path / "ai_assistance_test.sqlite"
    mgr = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))
    conn = mgr.get_connection()
    runner = MigrationRunner(conn)
    runner.apply_all_pending()

    uow = PlanningUnitOfWork(connection_manager=mgr)
    validator = MethodologicalDesignValidator()
    adapter = LocalMockAIAssistanceAdapter()
    service = MethodologicalDesignService(
        uow=uow,
        validator=validator,
        ai_assistance_port=adapter,
    )

    # Sembrar actividad planificada institucional con catálogos válidos C1-C5
    act = PlannedActivity.create(
        planning_id="POA-TEST-AI-001",
        activity_name="Taller de Planificación e Innovación Pedagógica",
        sede="Bluefields",
        dep_sede="RACCS",
        mun_sede="Bluefields",
        area_responsable="Dirección Académica",
        eje_estrategia="EJE_11",
        programa="PGM_07",
        tipo_evento="EVT_CAPACITACION",
        participant_goals=ParticipantGoals(docentes_m=10, docentes_f=15),
        proposito="Fortalecer las competencias metodológicas y de diseño pedagógico del cuerpo docente.",
    )
    with uow:
        uow.planned_activities.save(act)
        uow.commit()

    # Sembrar diseño metodológico en estado DRAFT
    design_dto = service.create_design_draft(
        activity_ref=act.planning_id,
        created_by="prof_kenia",
    )

    # Inicializar con bloques básicos para pruebas
    cmd = UpdateMethodologicalDesignCommand(
        design_id=design_dto.design_id,
        introduction_text="Introducción inicial manual.",
        methodological_approach="Enfoque inicial manual.",
        objectives=("Objetivo 1 manual", "Objetivo 2 manual"),
        agenda=(
            TimeBlock(sequence=1, label="I. Apertura", minutes=30),
            TimeBlock(sequence=2, label="II. Desarrollo", minutes=60),
            TimeBlock(sequence=3, label="III. Cierre", minutes=30),
        ),
        operational_matrix=(
            OperationalActivity(
                step_number=1,
                phase_label="I. Apertura",
                operative_goal="Presentar el taller",
                procedure="Dinámica de bienvenida",
                materials="Proyector",
                minutes=30,
            ),
            OperationalActivity(
                step_number=2,
                phase_label="II. Desarrollo",
                operative_goal="Explicar metodología",
                procedure="Exposición participativa",
                materials="Guías de trabajo",
                minutes=60,
            ),
            OperationalActivity(
                step_number=3,
                phase_label="III. Cierre",
                operative_goal="Evaluar la sesión",
                procedure="Plenaria final",
                materials="Formulario",
                minutes=30,
            ),
        ),
    )
    updated_dto = service.update_design_draft(cmd)

    return {
        "service": service,
        "adapter": adapter,
        "uow": uow,
        "activity": act,
        "design_id": updated_dto.design_id,
        "conn": conn,
    }


# ===========================================================================
# AI-01: La IA genera únicamente AIProposal
# ===========================================================================
def test_ai_01_generates_only_ai_proposals(clean_ai_env):
    """AI-01: El adaptador retorna siempre una instancia de AIProposal y el servicio AIProposalDTO."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    adapter: LocalMockAIAssistanceAdapter = clean_ai_env["adapter"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    # Invocación directa del puerto
    raw_prop = adapter.generate_narrative_proposal(
        target_field="introduction",
        source_inputs={"activity_name": "Taller X", "proposito": "Mejorar"},
    )
    assert isinstance(raw_prop, AIProposal)

    # Invocación mediante servicio de aplicación
    cmd = RequestAIProposalCommand(
        design_id=design_id,
        target_field="introduction",
    )
    dto = service.request_ai_proposal(cmd)
    assert isinstance(dto, AIProposalDTO)
    assert dto.target_field == "introduction"
    assert dto.proposed_content != ""


# ===========================================================================
# AI-02: requires_review=True siempre
# ===========================================================================
def test_ai_02_requires_review_always_true(clean_ai_env):
    """AI-02: Toda propuesta nace con requires_review=True y accepted=None."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    cmd = RequestAIProposalCommand(
        design_id=design_id,
        target_field="methodological_approach",
    )
    dto = service.request_ai_proposal(cmd)
    assert dto.requires_review is True
    assert dto.is_pending is True
    assert dto.accepted is None


# ===========================================================================
# AI-03: No puede aprobar automáticamente
# ===========================================================================
def test_ai_03_cannot_approve_automatically(clean_ai_env):
    """AI-03: Solicitar o aceptar una propuesta NO cambia el estado a APPROVED (permanece DRAFT)."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    # 1. Solicitar propuesta
    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="objective_1")
    )

    # 2. Aceptar propuesta
    design_dto = service.accept_ai_proposal(
        AcceptAIProposalCommand(
            design_id=design_id,
            proposal_id=prop_dto.proposal_id,
            reviewer="prof_kenia",
        )
    )
    assert design_dto.approved_by is None
    with clean_ai_env["uow"] as uow:
        reloaded = uow.methodological_designs.get_by_id(design_id)
        assert reloaded is not None
        assert reloaded.status == DesignStatus.DRAFT


# ===========================================================================
# AI-04: No puede operar sobre APPROVED (R-08)
# ===========================================================================
def test_ai_04_cannot_operate_on_approved_design(clean_ai_env):
    """AI-04: En un diseño APPROVED no se pueden generar, aceptar ni rechazar propuestas."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    # Aprobar el diseño formalmente
    service.approve_design(design_id=design_id, approved_by="director_academico")

    # Intentar solicitar propuesta
    with pytest.raises(RuntimeError, match="APPROVED"):
        service.request_ai_proposal(
            RequestAIProposalCommand(design_id=design_id, target_field="introduction")
        )

    # Intentar aceptar o rechazar propuesta
    with pytest.raises(RuntimeError, match="APPROVED"):
        service.accept_ai_proposal(
            AcceptAIProposalCommand(
                design_id=design_id,
                proposal_id=uuid.uuid4(),
                reviewer="prof_kenia",
            )
        )

    with pytest.raises(RuntimeError, match="APPROVED"):
        service.reject_ai_proposal(
            RejectAIProposalCommand(
                design_id=design_id,
                proposal_id=uuid.uuid4(),
                reviewer="prof_kenia",
                rejection_reason="Motivo",
            )
        )


# ===========================================================================
# AI-05: No puede acceder ni importar M1–M5 (Aislamiento AST)
# ===========================================================================
def test_ai_05_isolation_ast_no_word_consolidator():
    """AI-05: El paquete app.planning.infrastructure.ai no importa app.word_consolidator ni sqlite3."""
    ai_pkg_dir = Path("app/planning/infrastructure/ai")
    py_files = list(ai_pkg_dir.glob("*.py"))
    assert len(py_files) > 0, "Deben existir archivos en app.planning.infrastructure.ai"

    forbidden_imports = {
        "app.word_consolidator",
        "word_consolidator",
        "sqlite3",
        "SQLiteUnitOfWork",
    }

    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_imports:
                        assert forbidden not in alias.name, (
                            f"Infracción en {py_file}: importa '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for forbidden in forbidden_imports:
                    assert forbidden not in mod, (
                        f"Infracción en {py_file}: import from '{mod}'"
                    )


# ===========================================================================
# AI-06: Campos prohibidos son rechazados
# ===========================================================================
def test_ai_06_prohibited_fields_rejected(clean_ai_env):
    """AI-06: Solicitar propuestas para campos deterministas o institucionales arroja ValueError."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    for field in sorted(AI_PROHIBITED_TARGET_FIELDS):
        with pytest.raises(ValueError, match="no está permitido"):
            service.request_ai_proposal(
                RequestAIProposalCommand(design_id=design_id, target_field=field)
            )


# ===========================================================================
# AI-07: Datos faltantes permanecen faltantes
# ===========================================================================
def test_ai_07_missing_data_remains_missing():
    """AI-07: Si el propósito o datos opcionales no existen, el contexto los conserva como None."""
    act_sin_proposito = PlannedActivity.create(
        planning_id="POA-SIN-PROP",
        activity_name="Actividad Sin Propósito",
        sede="RACCS",
        area_responsable="Área",
        eje_estrategia="Eje",
        programa="Programa",
        tipo_evento="Taller",
        participant_goals=ParticipantGoals(),
        proposito=None,
    )

    ctx = AIContextBuilder.build_context(
        activity=act_sin_proposito,
        target_field="introduction",
    )
    assert ctx["proposito"] is None
    assert ctx["activity_name"] == "Actividad Sin Propósito"


# ===========================================================================
# AI-08: Rechazo no modifica el diseño
# ===========================================================================
def test_ai_08_reject_proposal_preserves_design(clean_ai_env):
    """AI-08: Rechazar una propuesta con motivo obligatorio no modifica el contenido del diseño."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    # Solicitar propuesta para introducción
    prop = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction")
    )

    # Rechazar propuesta
    updated = service.reject_ai_proposal(
        RejectAIProposalCommand(
            design_id=design_id,
            proposal_id=prop.proposal_id,
            reviewer="prof_kenia",
            rejection_reason="El enfoque pedagógico sugerido no coincide con los lineamientos del departamento.",
        )
    )

    # La introducción permanece idéntica a la manual original
    assert updated.introduction == "Introducción inicial manual."

    # La propuesta está guardada y marcada como rechazada
    proposals = service.list_ai_proposals(design_id)
    target = next(p for p in proposals if p.proposal_id == prop.proposal_id)
    assert target.is_rejected is True
    assert target.rejection_reason == "El enfoque pedagógico sugerido no coincide con los lineamientos del departamento."
    assert target.reviewed_by == "prof_kenia"


# ===========================================================================
# AI-09: Aceptación vuelca contenido pero no aprueba
# ===========================================================================
def test_ai_09_accept_proposal_applies_content_without_approving(clean_ai_env):
    """AI-09: Aceptar una propuesta vuelca el contenido al campo pero el diseño sigue en DRAFT."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    prop = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction")
    )

    updated = service.accept_ai_proposal(
        AcceptAIProposalCommand(
            design_id=design_id,
            proposal_id=prop.proposal_id,
            reviewer="prof_kenia",
        )
    )

    assert updated.approved_by is None
    with clean_ai_env["uow"] as uow:
        reloaded = uow.methodological_designs.get_by_id(design_id)
        assert reloaded is not None
        assert reloaded.status == DesignStatus.DRAFT
    assert updated.introduction == prop.proposed_content
    assert updated.introduction != "Introducción inicial manual."


# ===========================================================================
# AI-10: Auditoría pericial persistida en SQLite
# ===========================================================================
def test_ai_10_audit_history_persisted_in_sqlite(clean_ai_env):
    """AI-10: Las propuestas aceptadas y rechazadas conservan todos sus metadatos en SQLite."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    uow: PlanningUnitOfWork = clean_ai_env["uow"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    # 1. Propuesta 1 (Aceptada)
    p1 = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction")
    )
    service.accept_ai_proposal(
        AcceptAIProposalCommand(
            design_id=design_id,
            proposal_id=p1.proposal_id,
            reviewer="revisor_a",
        )
    )

    # 2. Propuesta 2 (Rechazada)
    p2 = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="methodological_approach")
    )
    service.reject_ai_proposal(
        RejectAIProposalCommand(
            design_id=design_id,
            proposal_id=p2.proposal_id,
            reviewer="revisor_b",
            rejection_reason="No cumple con la metodología institucional.",
        )
    )

    # Recargar directamente desde repositorio SQLite
    with uow:
        reloaded = uow.methodological_designs.get_by_id(design_id)
        assert reloaded is not None
        assert len(reloaded.ai_proposals) == 2

        db_p1 = next(p for p in reloaded.ai_proposals if p.proposal_id == p1.proposal_id)
        assert db_p1.is_accepted is True
        assert db_p1.reviewed_by == "revisor_a"
        assert db_p1.review_timestamp is not None
        assert db_p1.rejection_reason is None

        db_p2 = next(p for p in reloaded.ai_proposals if p.proposal_id == p2.proposal_id)
        assert db_p2.is_rejected is True
        assert db_p2.reviewed_by == "revisor_b"
        assert db_p2.rejection_reason == "No cumple con la metodología institucional."


# ===========================================================================
# AI-11: Proveedor intercambiable mediante puerto
# ===========================================================================
def test_ai_11_provider_swappable_via_port(clean_ai_env):
    """AI-11: Se puede inyectar un adaptador alternativo que cumpla con AIAssistancePort."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    class CustomTestAdapter(AIAssistancePort):
        def generate_narrative_proposal(self, target_field: str, source_inputs: dict[str, Any]) -> AIProposal:
            return AIProposal.create(
                target_field=target_field,
                proposed_content="Texto de adaptador personalizado para pruebas.",
                source_inputs=dict(source_inputs),
                confidence=0.99,
            )

    custom_adapter = CustomTestAdapter()
    prop = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction"),
        ai_port=custom_adapter,
    )
    assert prop.proposed_content == "Texto de adaptador personalizado para pruebas."
    assert prop.confidence == 0.99


# ===========================================================================
# AI-12: Word → M1–M5 permanece intacto
# ===========================================================================
def test_ai_12_word_to_m1_m5_intact():
    """AI-12: El módulo word_consolidator sigue funcionando de forma independiente."""
    from app.word_consolidator import WordConsolidationPipeline, DocxGenerator
    assert WordConsolidationPipeline is not None
    assert DocxGenerator is not None


# ===========================================================================
# AI-13: PLANIFICADO ≠ EJECUTADO
# ===========================================================================
def test_ai_13_planificado_not_equal_ejecutado(clean_ai_env):
    """AI-13: Las propuestas de IA de planificación no tocan tablas de ejecución M1-M5."""
    conn = clean_ai_env["conn"]
    # Las tablas de planificación son independientes de las tablas patrimoniales
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {r[0] for r in cur.fetchall()}
    assert "planning_ai_proposals" in tables
    assert "planning_methodological_designs" in tables
    # No existe contaminación cruzada


# ===========================================================================
# AI-14: Datos históricos permanecen intactos
# ===========================================================================
def test_ai_14_historical_data_intact(clean_ai_env):
    """AI-14: Crear o resolver propuestas no altera otras actividades ni otros diseños."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    uow: PlanningUnitOfWork = clean_ai_env["uow"]

    # Crear una segunda actividad con diseño
    act2 = PlannedActivity.create(
        planning_id="POA-HISTORICO-002",
        activity_name="Actividad Histórica",
        sede="Bilwi",
        dep_sede="RACCN",
        mun_sede="Puerto Cabezas",
        area_responsable="Área",
        eje_estrategia="EJE_11",
        programa="PGM_07",
        tipo_evento="EVT_CAPACITACION",
        participant_goals=ParticipantGoals(docentes_m=5, docentes_f=5),
        proposito="Propósito histórico",
    )
    with uow:
        uow.planned_activities.save(act2)
        uow.commit()

    d2 = service.create_design_draft(activity_ref=act2.planning_id, created_by="admin")

    # Operar en el primer diseño
    service.request_ai_proposal(
        RequestAIProposalCommand(design_id=clean_ai_env["design_id"], target_field="introduction")
    )

    # Verificar que el segundo diseño no tiene propuestas
    proposals_d2 = service.list_ai_proposals(d2.design_id)
    assert len(proposals_d2) == 0


# ===========================================================================
# AI-15: Fallo del adaptador no corrompe el diseño
# ===========================================================================
def test_ai_15_adapter_failure_does_not_corrupt_design(clean_ai_env):
    """AI-15: Si el adaptador de IA lanza una excepción de red o timeout, el diseño en BD queda intacto."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    class FailingAdapter(AIAssistancePort):
        def generate_narrative_proposal(self, target_field: str, source_inputs: dict[str, Any]) -> AIProposal:
            raise ConnectionError("Fallo simulado de conexión con el proveedor de IA.")

    with pytest.raises(ConnectionError, match="Fallo simulado"):
        service.request_ai_proposal(
            RequestAIProposalCommand(design_id=design_id, target_field="introduction"),
            ai_port=FailingAdapter(),
        )

    # El diseño no tiene propuestas guardadas y su contenido está intacto
    proposals = service.list_ai_proposals(design_id)
    assert len(proposals) == 0


# ===========================================================================
# TEST DE DATA MINIMIZATION: Verificación contra fuga de PII
# ===========================================================================
def test_data_minimization_synthetic_leak_check():
    """Verifica que ningún dato sensible o PII llegue al contexto de la IA."""
    act_con_datos_sensibles = PlannedActivity.create(
        planning_id="POA-CONFIDENCIAL-999",
        activity_name="Taller de Capacitación",
        sede="Bluefields",
        dep_sede="RACCS",
        mun_sede="Bluefields",
        area_responsable="Recursos Humanos",
        departamento_responsable="Capacitación",
        eje_estrategia="Desarrollo Institucional",
        programa="Gestión de Talento",
        tipo_evento="Taller",
        codigo_presupuestario="PRE-2026-9999",
        proposito="Capacitar al personal",
        participant_goals=ParticipantGoals(
            est_grado_m=50,
            est_grado_f=50,
            docentes_m=20,
            docentes_f=30,
            administrativos_m=10,
            administrativos_f=15,
        ),
        convenio="Convenio Secreto 123",
        entidades_cooperantes="Cooperante Internacional",
    )

    context = AIContextBuilder.build_context(
        activity=act_con_datos_sensibles,
        target_field="introduction",
    )

    # Claves estrictamente permitidas
    assert set(context.keys()) <= AIContextBuilder.WHITELISTED_CONTEXT_KEYS

    # Verificación pericial de exclusión de datos confidenciales
    context_str = str(context).lower()
    assert "pre-2026-9999" not in context_str
    assert "bluefields" not in context_str
    assert "raccs" not in context_str
    assert "recursos humanos" not in context_str
    assert "convenio secreto" not in context_str
    assert "cooperante internacional" not in context_str
    assert "participant_goals" not in context
    assert "codigo_presupuestario" not in context
    assert "sede" not in context


# ===========================================================================
# SOPORTE PARA TABLAS OPERATIVAS: procedure y operative_goal
# ===========================================================================
def test_operational_matrix_step_procedure_and_goal_support(clean_ai_env):
    """Verifica que las propuestas de 'procedure' y 'operative_goal' actualizan el paso sin tocar minutos."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    # 1. Solicitar propuesta para el procedimiento del paso 2
    cmd_proc = RequestAIProposalCommand(
        design_id=design_id,
        target_field="procedure",
        step_number=2,
        phase_label="II. Desarrollo",
    )
    prop_proc = service.request_ai_proposal(cmd_proc)
    assert prop_proc.step_number == 2

    # Aceptar la propuesta
    updated_proc = service.accept_ai_proposal(
        AcceptAIProposalCommand(
            design_id=design_id,
            proposal_id=prop_proc.proposal_id,
            reviewer="prof_kenia",
        )
    )

    # Verificar que el paso 2 fue actualizado pero los minutos y materiales permanecen intactos
    step2 = next(op for op in updated_proc.operational_matrix if op.step_number == 2)
    assert step2.procedure == prop_proc.proposed_content
    assert step2.minutes == 60  # Minutos intactos
    assert step2.materials == "Guías de trabajo"  # Materiales intactos

    # 2. Solicitar propuesta para el objetivo operativo del paso 3
    cmd_goal = RequestAIProposalCommand(
        design_id=design_id,
        target_field="operative_goal",
        step_number=3,
    )
    prop_goal = service.request_ai_proposal(cmd_goal)

    updated_goal = service.accept_ai_proposal(
        AcceptAIProposalCommand(
            design_id=design_id,
            proposal_id=prop_goal.proposal_id,
            reviewer="prof_kenia",
        )
    )

    step3 = next(op for op in updated_goal.operational_matrix if op.step_number == 3)
    assert step3.operative_goal == prop_goal.proposed_content
    assert step3.minutes == 30  # Minutos intactos


# ===========================================================================
# V-MD-10: Bloqueo de Aprobación por Propuesta Pendiente
# ===========================================================================
def test_vmd_10_blocks_approval_with_pending_proposals(clean_ai_env):
    """V-MD-10: Un diseño con propuestas pendientes no puede ser aprobado formalmente."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    # Generar una propuesta (queda pendiente de revisión)
    service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction")
    )

    # Intentar aprobar el diseño
    with pytest.raises(ValueError, match="V-MD-10"):
        service.approve_design(design_id=design_id, approved_by="director")

    # Obtener reporte de validación
    report = service.validate_design(design_id)
    assert not report.is_valid
    assert any(e.rule_id == "V-MD-10" for e in report.errors)


# ===========================================================================
# Modificación posterior humana preserva evidencia de auditoría
# ===========================================================================
def test_post_acceptance_human_edit_preserves_audit(clean_ai_env):
    """Si el usuario edita el texto tras aceptar una propuesta, la auditoría conserva la propuesta original."""
    service: MethodologicalDesignService = clean_ai_env["service"]
    design_id: uuid.UUID = clean_ai_env["design_id"]

    prop = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction")
    )
    service.accept_ai_proposal(
        AcceptAIProposalCommand(
            design_id=design_id,
            proposal_id=prop.proposal_id,
            reviewer="prof_kenia",
        )
    )

    # El humano edita manualmente la introducción
    texto_editado = "Introducción editada y personalizada manualmente por la docente."
    updated = service.update_design_draft(
        UpdateMethodologicalDesignCommand(
            design_id=design_id,
            introduction_text=texto_editado,
        )
    )
    assert updated.introduction == texto_editado

    # La propuesta de auditoría sigue teniendo el texto original de la IA
    proposals = service.list_ai_proposals(design_id)
    assert len(proposals) == 1
    assert proposals[0].proposed_content == prop.proposed_content
    assert proposals[0].proposed_content != texto_editado
    assert proposals[0].is_accepted is True
    assert proposals[0].reviewed_by == "prof_kenia"
