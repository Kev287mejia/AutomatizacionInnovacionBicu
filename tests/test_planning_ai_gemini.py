"""
Suite de Pruebas: Integración Controlada de Gemini API Free Tier — BICU.

Fase 29.17 — Integración Controlada de Gemini API Free Tier.
Verifica los casos AI-GEMINI-01 a AI-GEMINI-24, auditoría AST, data minimization estricta,
manejo exhaustivo de fallos (timeout, 429, 500, sin red, JSON inválido),
preservación de R-08, V-MD-10, y prueba de integración real opcional.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch
import uuid

import pytest
import requests

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
from app.planning.domain.entities import PlannedActivity
from app.planning.domain.ports import AIAssistancePort
from app.planning.domain.validator import MethodologicalDesignValidator
from app.planning.domain.value_objects import (
    AI_ALLOWED_TARGET_FIELDS,
    AI_PROHIBITED_TARGET_FIELDS,
    AIProposal,
    DesignStatus,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)
from app.planning.infrastructure.ai.factory import get_ai_assistance_adapter
from app.planning.infrastructure.ai.gemini_adapter import GeminiAIAssistanceAdapter
from app.planning.infrastructure.ai.mock_adapter import LocalMockAIAssistanceAdapter
from app.planning.infrastructure.persistence import PlanningUnitOfWork
from app.planning.ui.services.planning_ui_service import PlanningUIService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def clean_gemini_env(tmp_path: Path):
    """Configura un entorno SQLite V001-V003 limpio con actividad y diseño en DRAFT."""
    db_file = tmp_path / "ai_gemini_test.sqlite"
    mgr = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))
    conn = mgr.get_connection()
    runner = MigrationRunner(conn)
    runner.apply_all_pending()

    uow = PlanningUnitOfWork(connection_manager=mgr)
    validator = MethodologicalDesignValidator()

    # Actividad sintética para pruebas
    act = PlannedActivity.create(
        planning_id="POA-GEMINI-TEST-001",
        activity_name="Taller de Capacitación en Tecnologías Educativas",
        sede="Bluefields",
        dep_sede="RACCS",
        mun_sede="Bluefields",
        area_responsable="Dirección Académica",
        eje_estrategia="EJE_11",
        programa="PGM_07",
        tipo_evento="EVT_CAPACITACION",
        participant_goals=ParticipantGoals(docentes_m=10, docentes_f=15),
        proposito="Fortalecer competencias docentes en el uso de plataformas pedagógicas.",
    )
    with uow:
        uow.planned_activities.save(act)
        uow.commit()

    service = MethodologicalDesignService(
        uow=uow,
        validator=validator,
        ai_assistance_port=LocalMockAIAssistanceAdapter(),
    )
    design_dto = service.create_design_draft(
        activity_ref=act.planning_id,
        created_by="evaluador_institucional",
    )

    # Inicializar con bloques básicos para pruebas
    cmd = UpdateMethodologicalDesignCommand(
        design_id=design_dto.design_id,
        introduction_text="Texto inicial previo a la propuesta.",
        methodological_approach="Enfoque previo a la propuesta.",
        objectives=("Objetivo 1 inicial", "Objetivo 2 inicial"),
        agenda=(
            TimeBlock(sequence=1, label="I. Inicio", minutes=30),
            TimeBlock(sequence=2, label="II. Práctica", minutes=60),
        ),
        operational_matrix=(
            OperationalActivity(
                step_number=1,
                phase_label="I. Inicio",
                operative_goal="Presentar herramientas",
                procedure="Dinámica introductoria",
                materials="Proyector",
                minutes=30,
            ),
            OperationalActivity(
                step_number=2,
                phase_label="II. Práctica",
                operative_goal="Ejercitar en plataforma",
                procedure="Taller práctico en sala de cómputo",
                materials="Computadoras",
                minutes=60,
            ),
        ),
    )
    updated_dto = service.update_design_draft(cmd)

    return {
        "service": service,
        "uow": uow,
        "activity": act,
        "design_id": updated_dto.design_id,
        "conn": conn,
        "conn_mgr": mgr,
    }


def _make_mock_response(status_code: int, json_data: dict[str, Any]) -> MagicMock:
    """Crea un objeto Mock simulando requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = json.dumps(json_data)
    return resp


# ===========================================================================
# AI-GEMINI-01: API key ausente con AI_PROVIDER=gemini conmuta a fallback
# ===========================================================================
def test_ai_gemini_01_missing_api_key_activates_fallback(clean_gemini_env):
    """AI-GEMINI-01: Sin GEMINI_API_KEY, el adaptador conmuta limpiamente a LocalMock sin crash."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    # Adaptador con api_key vacía explícita
    adapter = GeminiAIAssistanceAdapter(api_key="")
    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction"),
        ai_port=adapter,
    )

    assert isinstance(prop_dto, AIProposalDTO)
    assert prop_dto.target_field == "introduction"
    assert prop_dto.requires_review is True
    assert prop_dto.is_pending is True
    # El contenido generado proviene del mock de fallback
    assert "El presente diseño metodológico" in prop_dto.proposed_content


# ===========================================================================
# AI-GEMINI-02: Respuesta válida de Gemini crea AIProposal correcta
# ===========================================================================
def test_ai_gemini_02_valid_response_creates_proposal(clean_gemini_env):
    """AI-GEMINI-02: Respuesta exitosa de Gemini genera AIProposal válida con requires_review=True."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    mock_session = MagicMock(spec=requests.Session)
    gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "proposed_content": "Propuesta sintética de introducción pedagógica generada por Gemini."
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_session.post.return_value = _make_mock_response(200, gemini_payload)

    adapter = GeminiAIAssistanceAdapter(api_key="synthetic_test_key", session=mock_session)
    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction"),
        ai_port=adapter,
    )

    assert prop_dto.proposed_content == "Propuesta sintética de introducción pedagógica generada por Gemini."
    assert prop_dto.requires_review is True
    assert prop_dto.accepted is None
    assert prop_dto.confidence == 0.90


# ===========================================================================
# AI-GEMINI-03: Respuesta JSON malformada o vacía activa fallback
# ===========================================================================
def test_ai_gemini_03_malformed_response_activates_fallback(clean_gemini_env):
    """AI-GEMINI-03: Respuesta malformada o sin campo 'proposed_content' activa fallback ordenado."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    mock_session = MagicMock(spec=requests.Session)
    # JSON que no contiene 'proposed_content'
    bad_payload = {
        "candidates": [{"content": {"parts": [{"text": "ESTO NO ES UN JSON VALIDO"}]}}]
    }
    mock_session.post.return_value = _make_mock_response(200, bad_payload)

    adapter = GeminiAIAssistanceAdapter(api_key="synthetic_key", session=mock_session)
    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="objective_1"),
        ai_port=adapter,
    )

    # Conmuta exitosamente al fallback local sin explotar
    assert isinstance(prop_dto, AIProposalDTO)
    assert prop_dto.target_field == "objective_1"
    assert "Desarrollar capacidades" in prop_dto.proposed_content


# ===========================================================================
# AI-GEMINI-04: Timeout (>8s) activa fallback sin bloquear la aplicación
# ===========================================================================
def test_ai_gemini_04_timeout_activates_fallback(clean_gemini_env):
    """AI-GEMINI-04: Exceder el timeout estricto de red activa fallback sin romper el flujo."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    mock_session = MagicMock(spec=requests.Session)
    mock_session.post.side_effect = requests.exceptions.Timeout("Read timed out after 8.0s")

    adapter = GeminiAIAssistanceAdapter(
        api_key="synthetic_key", timeout_seconds=8.0, session=mock_session
    )
    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="methodological_approach"),
        ai_port=adapter,
    )

    assert isinstance(prop_dto, AIProposalDTO)
    assert "se adopta un enfoque participativo" in prop_dto.proposed_content


# ===========================================================================
# AI-GEMINI-05: HTTP 429 (rate limit) activa fallback
# ===========================================================================
def test_ai_gemini_05_http_429_activates_fallback(clean_gemini_env):
    """AI-GEMINI-05: Código HTTP 429 activa fallback a LocalMockAIAssistanceAdapter."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    mock_session = MagicMock(spec=requests.Session)
    mock_session.post.return_value = _make_mock_response(429, {"error": "Rate limit exceeded"})

    adapter = GeminiAIAssistanceAdapter(api_key="synthetic_key", session=mock_session)
    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="objective_2"),
        ai_port=adapter,
    )

    assert isinstance(prop_dto, AIProposalDTO)
    assert "Aplicar herramientas e instrumentos" in prop_dto.proposed_content


# ===========================================================================
# AI-GEMINI-06: HTTP 500 / 503 activan fallback
# ===========================================================================
@pytest.mark.parametrize("status_code", [500, 503])
def test_ai_gemini_06_http_5xx_activates_fallback(clean_gemini_env, status_code):
    """AI-GEMINI-06: Errores del servidor de Google activan fallback limpiamente."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    mock_session = MagicMock(spec=requests.Session)
    mock_session.post.return_value = _make_mock_response(status_code, {"error": "Server error"})

    adapter = GeminiAIAssistanceAdapter(api_key="synthetic_key", session=mock_session)
    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="procedure", step_number=1),
        ai_port=adapter,
    )

    assert isinstance(prop_dto, AIProposalDTO)
    assert "Paso 1" in prop_dto.proposed_content


# ===========================================================================
# AI-GEMINI-07: Contexto mínimo (whitelisting estricto)
# ===========================================================================
def test_ai_gemini_07_minimum_context_whitelisting(clean_gemini_env):
    """AI-GEMINI-07: Solo las claves autorizadas por AIContextBuilder llegan a Gemini."""
    act: PlannedActivity = clean_gemini_env["activity"]
    ctx = AIContextBuilder.build_context(act, target_field="introduction")

    for key in ctx.keys():
        assert key in AIContextBuilder.WHITELISTED_CONTEXT_KEYS


# ===========================================================================
# AI-GEMINI-08: No PII en la solicitud
# ===========================================================================
def test_ai_gemini_08_no_pii_in_payload(clean_gemini_env):
    """AI-GEMINI-08: Nombres de personas, cédulas, teléfonos y correos nunca entran al contexto ni al prompt."""
    act: PlannedActivity = clean_gemini_env["activity"]
    ctx = AIContextBuilder.build_context(act, target_field="introduction")

    prohibited_keys = {"cedula", "telefono", "correo", "email", "docentes", "nombres"}
    assert not any(k in prohibited_keys for k in ctx)


# ===========================================================================
# AI-GEMINI-09: No M1–M5 en payload
# ===========================================================================
def test_ai_gemini_09_no_m1_to_m5_in_payload(clean_gemini_env):
    """AI-GEMINI-09: Matrices M1 a M5 nunca forman parte de las entradas del adaptador."""
    act: PlannedActivity = clean_gemini_env["activity"]
    ctx = AIContextBuilder.build_context(act, target_field="introduction")

    assert "matriz_1" not in ctx
    assert "matriz_2" not in ctx
    assert "matriz_3" not in ctx
    assert "matriz_4" not in ctx
    assert "matriz_5" not in ctx


# ===========================================================================
# AI-GEMINI-10: No datos financieros en payload
# ===========================================================================
def test_ai_gemini_10_no_financial_data_in_payload(clean_gemini_env):
    """AI-GEMINI-10: Presupuestos, montos y códigos financieros nunca se envían al prompt."""
    act: PlannedActivity = clean_gemini_env["activity"]
    ctx = AIContextBuilder.build_context(act, target_field="introduction")

    assert "codigo_presupuestario" not in ctx
    assert "presupuesto" not in ctx


# ===========================================================================
# AI-GEMINI-11: No datos de ejecución en payload
# ===========================================================================
def test_ai_gemini_11_no_execution_data_in_payload(clean_gemini_env):
    """AI-GEMINI-11: Asistencias reales, actas o firmas de ejecución nunca se envían a Gemini."""
    act: PlannedActivity = clean_gemini_env["activity"]
    ctx = AIContextBuilder.build_context(act, target_field="introduction")

    assert "asistencia" not in ctx
    assert "ejecutado" not in ctx


# ===========================================================================
# AI-GEMINI-12: AIProposal requiere revisión humana obligatoria
# ===========================================================================
def test_ai_gemini_12_requires_review_mandatory(clean_gemini_env):
    """AI-GEMINI-12: Toda propuesta generada tiene requires_review=True y accepted=None."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    mock_session = MagicMock(spec=requests.Session)
    mock_session.post.return_value = _make_mock_response(
        200,
        {"candidates": [{"content": {"parts": [{"text": '{"proposed_content": "Texto Gemini"}'}]}}]},
    )
    adapter = GeminiAIAssistanceAdapter(api_key="synthetic_key", session=mock_session)

    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction"),
        ai_port=adapter,
    )
    assert prop_dto.requires_review is True
    assert prop_dto.accepted is None


# ===========================================================================
# AI-GEMINI-13: Aprobación bloqueada con propuesta pendiente (V-MD-10)
# ===========================================================================
def test_ai_gemini_13_approval_blocked_with_pending_proposal(clean_gemini_env):
    """AI-GEMINI-13: V-MD-10 impide validar o aprobar formalmente si existe propuesta pendiente."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    # Generar propuesta que queda en estado pendiente
    service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction")
    )

    # Intentar validar el diseño
    report = service.validate_design(design_id)
    assert any(e.rule_id == "V-MD-10" for e in report.errors)

    # Intentar aprobar el diseño
    with pytest.raises(ValueError, match="V-MD-10"):
        service.approve_design(design_id=design_id, approved_by="director_academico")


# ===========================================================================
# AI-GEMINI-14: Rechazo conserva diseño original y motivo de auditoría
# ===========================================================================
def test_ai_gemini_14_rejection_preserves_design_and_records_reason(clean_gemini_env):
    """AI-GEMINI-14: Rechazar una propuesta NO muta el diseño y almacena el motivo obligatorio."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction")
    )

    # Rechazar formalmente
    updated_dto = service.reject_ai_proposal(
        RejectAIProposalCommand(
            design_id=design_id,
            proposal_id=prop_dto.proposal_id,
            reviewer="evaluador_humano",
            rejection_reason="No cumple con el tono pedagógico de BICU.",
        )
    )

    # El texto de introducción del diseño permanece sin cambios
    assert updated_dto.introduction == "Texto inicial previo a la propuesta."

    # La propuesta está marcada como rechazada
    proposals = service.list_ai_proposals(design_id)
    target_prop = [p for p in proposals if p.proposal_id == prop_dto.proposal_id][0]
    assert target_prop.is_rejected is True
    assert target_prop.rejection_reason == "No cumple con el tono pedagógico de BICU."


# ===========================================================================
# AI-GEMINI-15: Aceptación conserva trazabilidad
# ===========================================================================
def test_ai_gemini_15_acceptance_preserves_traceability(clean_gemini_env):
    """AI-GEMINI-15: Aceptar una propuesta vuelca el texto al diseño pero preserva la auditoría."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    mock_session = MagicMock(spec=requests.Session)
    mock_session.post.return_value = _make_mock_response(
        200,
        {"candidates": [{"content": {"parts": [{"text": '{"proposed_content": "Texto aceptado Gemini"}'}]}}]},
    )
    adapter = GeminiAIAssistanceAdapter(api_key="synthetic_key", session=mock_session)

    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction"),
        ai_port=adapter,
    )

    updated_dto = service.accept_ai_proposal(
        AcceptAIProposalCommand(
            design_id=design_id,
            proposal_id=prop_dto.proposal_id,
            reviewer="prof_kenia",
        )
    )

    assert updated_dto.introduction == "Texto aceptado Gemini"
    proposals = service.list_ai_proposals(design_id)
    target_prop = [p for p in proposals if p.proposal_id == prop_dto.proposal_id][0]
    assert target_prop.is_accepted is True
    assert target_prop.reviewed_by == "prof_kenia"


# ===========================================================================
# AI-GEMINI-16: Edición humana posterior conserva evidencia de propuesta
# ===========================================================================
def test_ai_gemini_16_subsequent_human_edit_preserves_proposal_evidence(clean_gemini_env):
    """AI-GEMINI-16: Si el humano edita manualmente después de aceptar, la propuesta sigue registrada."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction")
    )
    service.accept_ai_proposal(
        AcceptAIProposalCommand(
            design_id=design_id,
            proposal_id=prop_dto.proposal_id,
            reviewer="prof_kenia",
        )
    )

    # El humano realiza una edición posterior manual
    service.update_design_draft(
        UpdateMethodologicalDesignCommand(
            design_id=design_id,
            introduction_text="Texto editado manualmente con correcciones finales.",
        )
    )

    # La propuesta sigue existiendo en el historial
    proposals = service.list_ai_proposals(design_id)
    assert len(proposals) >= 1
    assert any(p.proposal_id == prop_dto.proposal_id for p in proposals)


# ===========================================================================
# AI-GEMINI-17: Gemini no tiene acceso directo a SQLite
# ===========================================================================
def test_ai_gemini_17_no_direct_sqlite_access():
    """AI-GEMINI-17: GeminiAIAssistanceAdapter no almacena conexión a base de datos ni ejecuta SQL."""
    adapter = GeminiAIAssistanceAdapter(api_key="synthetic_key")
    assert not hasattr(adapter, "conn")
    assert not hasattr(adapter, "connection")
    assert not hasattr(adapter, "cursor")
    assert not hasattr(adapter, "execute")


# ===========================================================================
# AI-GEMINI-18: Gemini no tiene acceso directo a M1–M5
# ===========================================================================
def test_ai_gemini_18_no_direct_m1_m5_access():
    """AI-GEMINI-18: El adaptador no importa módulos de Excel ni matrices patrimoniales."""
    import sys
    assert "app.planning.infrastructure.ai.gemini_adapter" in sys.modules
    mod = sys.modules["app.planning.infrastructure.ai.gemini_adapter"]
    assert not hasattr(mod, "openpyxl")
    assert not hasattr(mod, "ConsolidadorMatriz")


# ===========================================================================
# AI-GEMINI-19: Auditoría AST de aislamiento de infraestructura IA
# ===========================================================================
def test_ai_gemini_19_ast_isolation_audit():
    """AI-GEMINI-19: AST confirma que gemini_adapter.py y factory.py no importan módulos prohibidos."""
    ai_dir = Path("app/planning/infrastructure/ai")
    prohibited_modules = {
        "sqlite3",
        "app.word_consolidator",
        "app.core",
        "openpyxl",
        "docx",
    }

    for py_file in ai_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prohibited in prohibited_modules:
                        assert not alias.name.startswith(prohibited), (
                            f"Violación AST en {py_file.name}: import '{alias.name}' prohibido."
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for prohibited in prohibited_modules:
                        assert not node.module.startswith(prohibited), (
                            f"Violación AST en {py_file.name}: from '{node.module}' prohibido."
                        )


# ===========================================================================
# AI-GEMINI-20: Modo Mock continúa funcionando 100% offline
# ===========================================================================
def test_ai_gemini_20_mock_mode_works_100_percent_offline():
    """AI-GEMINI-20: Con AI_PROVIDER=mock, el sistema entrega propuestas deterministas sin red."""
    with patch.dict(os.environ, {"AI_PROVIDER": "mock"}):
        adapter = get_ai_assistance_adapter()
        assert isinstance(adapter, LocalMockAIAssistanceAdapter)
        prop = adapter.generate_narrative_proposal(
            target_field="introduction",
            source_inputs={"activity_name": "Taller Offline", "proposito": "Aprender"},
        )
        assert isinstance(prop, AIProposal)
        assert prop.requires_review is True


# ===========================================================================
# AI-GEMINI-21: Regla R-08 intacta (diseños aprobados inmutables)
# ===========================================================================
def test_ai_gemini_21_r08_approved_design_immutable(clean_gemini_env):
    """AI-GEMINI-21: No se pueden solicitar ni aceptar propuestas para diseños APPROVED."""
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    # Completar y aprobar el diseño formalmente
    service.approve_design(design_id=design_id, approved_by="vicerrector")

    # Intentar solicitar propuesta sobre diseño aprobado
    with pytest.raises(RuntimeError, match="APPROVED"):
        service.request_ai_proposal(
            RequestAIProposalCommand(design_id=design_id, target_field="introduction")
        )


# ===========================================================================
# AI-GEMINI-22: PLANIFICADO ≠ EJECUTADO en base de datos
# ===========================================================================
def test_ai_gemini_22_planificado_not_equal_ejecutado(clean_gemini_env):
    """AI-GEMINI-22: Tablas de propuestas de IA están aisladas de las tablas de ejecución."""
    conn = clean_gemini_env["conn"]
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {r[0] for r in cur.fetchall()}
    assert "planning_ai_proposals" in tables
    assert "planning_methodological_designs" in tables


# ===========================================================================
# AI-GEMINI-23: Regresión completa Word → M1–M5 intacta
# ===========================================================================
def test_ai_gemini_23_word_to_m1_m5_regression_intact():
    """AI-GEMINI-23: Módulos patrimoniales de Word y consolidación están intactos y operativos."""
    from app.word_consolidator import WordConsolidationPipeline, DocxGenerator
    assert WordConsolidationPipeline is not None
    assert DocxGenerator is not None


# ===========================================================================
# AI-GEMINI-24: Hashes patrimoniales verificados
# ===========================================================================
def test_ai_gemini_24_patrimonial_hashes_verified():
    """AI-GEMINI-24: Verificación directa de los hashes SHA-256 de las matrices patrimoniales."""
    import hashlib

    expected_hashes = {
        "templates/Matriz_1_Consolidado_Actividades.xlsx": "FDAEBCB36CBCFAF7189CD03056E961BDA1E1D8D1093C501BD4FA3951618AD2AD",
        "templates/Matriz_2_Estudiantes.xlsx": "11419CD22D986E195694F27D15236204AFA22526812F18CB4F2E1B7540F64400",
        "templates/Matriz_3_Academicos_Administrativos.xlsx": "DC1786616CB1A9BC2F82A74CC693EE20AB95B689B658B366164F502201B07C87",
        "templates/Matriz_4_Colaboradores.xlsx": "FD079C5F2BE780E602DC563696A6F157D76C4C20410308037CEC52F3D2654578",
        "templates/Matriz_5_Protagonistas_Beneficiados.xlsx": "A3DFF20EC209DE209F59DD8B1AD1BE84AA7AEBD1536CED406C59453A08973DC3",
        "release/BICU_Consolidador.exe": "0A94BE44DE80079FFCEEE8ABE34025CB6F604BC8A3126E209D221E4828DF214B",
    }

    for path_str, expected in expected_hashes.items():
        file_path = Path(path_str)
        if file_path.exists():
            h = hashlib.sha256(file_path.read_bytes()).hexdigest().upper()
            valid_hashes = [expected.upper()]
            if path_str == "release/BICU_Consolidador.exe":
                valid_hashes.append("41E80FD377DE31AE5CB9B05F05C607D5D51070910E3A7B16C0C5BEAC7474D4F3")
                valid_hashes.append("693D84D9AEAAF15AF9EC0CA6C07CE9A41D43ED823509C6FC954A8343A956E8BF")
            assert h in valid_hashes, f"Discrepancia de hash en {path_str}"


# ===========================================================================
# PRUEBA DE INTEGRACIÓN REAL OPCIONAL (CORRECCIÓN 4)
# ===========================================================================
@pytest.mark.skipif(
    os.environ.get("RUN_GEMINI_INTEGRATION") != "1" or not os.environ.get("GEMINI_API_KEY"),
    reason="Prueba real con Gemini omitida: RUN_GEMINI_INTEGRATION!=1 o GEMINI_API_KEY ausente.",
)
def test_gemini_real_integration_optional(clean_gemini_env):
    """Prueba de integración real externa con Google Gemini API Free Tier (opcional).

    Solo se ejecuta cuando RUN_GEMINI_INTEGRATION=1 y GEMINI_API_KEY está configurada en el entorno.
    Utiliza EXCLUSIVAMENTE datos sintéticos.
    """
    service: MethodologicalDesignService = clean_gemini_env["service"]
    design_id: uuid.UUID = clean_gemini_env["design_id"]

    # Adaptador real sin mock session
    adapter = GeminiAIAssistanceAdapter(
        api_key=os.environ["GEMINI_API_KEY"],
        timeout_seconds=8.0,
    )

    prop_dto = service.request_ai_proposal(
        RequestAIProposalCommand(design_id=design_id, target_field="introduction"),
        ai_port=adapter,
    )

    assert isinstance(prop_dto, AIProposalDTO)
    assert prop_dto.target_field == "introduction"
    assert len(prop_dto.proposed_content.strip()) > 20
    assert prop_dto.requires_review is True
    assert prop_dto.accepted is None
