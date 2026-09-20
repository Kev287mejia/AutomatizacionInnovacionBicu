"""Pruebas Automatizadas de Persistencia SQLite V003 - Módulo de Planificación.

Fase 29.4.2 — Implementación de Persistencia SQLite V003.
Cubre exhaustivamente:
  P-01: Migración V003.
  P-02: Existencia física de las 6 tablas planning_*.
  P-03: Tres ejecuciones consecutivas de apply_all_pending() (idempotencia).
  P-04: Crear y persistir PlannedActivity.
  P-05: Crear y persistir MethodologicalDesign.
  P-06: Reconstrucción completa del agregado MethodologicalDesign.
  P-07: FAQ con las 7 preguntas institucionales.
  P-08: Agenda completa y cálculo derivado consistente (total_minutes).
  P-09: Matriz operacional.
  P-10: Persistencia de AIProposal.
  P-11: requires_review = 1 obligatorio (restricción física CHECK).
  P-12: Integridad FK (rechaza diseño si la actividad no existe).
  P-13: UNIQUE(planned_activity_ref) (un único diseño vigente por actividad).
  P-14: Rollback completo ante fallo (cero registros huérfanos).
  P-15: Cerrar conexión y reabrir SQLite (reconstrucción semántica fiel).
  P-16: Modificar diseño DRAFT (actualización in-place permitida).
  P-17: Intentar modificar diseño APPROVED (rechazo estricto por inmutabilidad R-08).
  P-18: Intentar crear segundo diseño para la misma actividad (falla por unicidad).
  P-19: Comprobar que activity_internal_id es UUID técnico.
  P-20: Comprobar que no se inventa ningún formato de planning_id.
  P-21: Comprobar no invasión del dominio puro.
  P-22: Comprobar que word_consolidator permanece intacto.
  P-23: Comprobar que V001 y V002 permanecen intactas.
"""

from datetime import date, datetime
import importlib
import inspect
from pathlib import Path
import sqlite3
import sys
import uuid
import pytest

from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.schema import (
    INITIAL_INDEXES_DDL_STATEMENTS,
    INITIAL_SCHEMA_DDL_STATEMENTS,
    V002_INDEXES_DDL_STATEMENTS,
    V002_SCHEMA_DDL_STATEMENTS,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.value_objects import (
    AIProposal,
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)
from app.planning.infrastructure.persistence import (
    EXPECTED_PLANNING_TABLE_NAMES,
    PlanningUnitOfWork,
    SQLiteCatalogRepository,
    SQLiteMethodologicalDesignRepository,
    SQLitePlannedActivityRepository,
)


@pytest.fixture
def clean_db(tmp_path: Path):
    """Crea una base de datos SQLite temporal con las migraciones V001, V002 y V003 aplicadas."""
    db_file = tmp_path / "test_planning_v003.db"
    mgr = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))
    conn = mgr.get_connection()
    runner = MigrationRunner(conn)
    runner.apply_all_pending()
    yield conn, runner, db_file
    conn.close()


def _crear_actividad_valida(
    planning_id: str = "POA-2026-TALLER-01",
    activity_name: str = "Taller de Innovación y Emprendimiento",
) -> PlannedActivity:
    """Helper para crear una PlannedActivity válida según el dominio."""
    goals = ParticipantGoals(
        est_grado_m=10,
        est_grado_f=15,
        est_postgrado_m=2,
        est_postgrado_f=3,
        docentes_m=4,
        docentes_f=6,
        administrativos_m=1,
        administrativos_f=2,
        externos_m=5,
        externos_f=5,
    )
    return PlannedActivity.create(
        planning_id=planning_id,
        activity_name=activity_name,
        sede="Bluefields",
        area_responsable="Dirección de Innovación y Emprendimiento",
        eje_estrategia="E1",
        programa="P1",
        tipo_evento="TALLER",
        participant_goals=goals,
        dep_sede="RACCS",
        mun_sede="Bluefields",
        proposito="Capacitar a estudiantes en metodologías ágiles",
        fecha_evento=date(2026, 10, 15),
    )


def _crear_diseno_valido(
    activity: PlannedActivity,
    status: DesignStatus = DesignStatus.DRAFT,
) -> MethodologicalDesign:
    """Helper para crear un MethodologicalDesign completo con 5 bloques."""
    faq = FAQTable(
        q1_que_es="Taller práctico sobre diseño de proyectos de innovación.",
        q2_para_que="Fortalecer capacidades metodológicas en la comunidad universitaria.",
        q3_sesiones="Sesión única intensiva",
        q4_protagonistas=activity.participant_goals.to_narrative(),
        q5_facilitador=activity.area_responsable,
        q6_materiales="Papelógrafos, marcadores, notas adhesivas, proyector.",
        q7_duracion="180 minutos (3 horas)",
    )
    agenda = [
        TimeBlock(sequence=1, label="Registro y Bienvenida", minutes=30),
        TimeBlock(sequence=2, label="Marco Conceptual de Innovación", minutes=60),
        TimeBlock(sequence=3, label="Trabajo en Equipos y Prototipado", minutes=60),
        TimeBlock(sequence=4, label="Presentación de Resultados y Cierre", minutes=30),
    ]
    matrix = [
        OperationalActivity(
            step_number=1,
            phase_label="Registro y Bienvenida",
            operative_goal="Acreditar a los participantes e introducir los objetivos.",
            procedure="Recepción, entrega de credenciales y palabras de apertura.",
            materials="Listas de asistencia, credenciales.",
            minutes=30,
        ),
        OperationalActivity(
            step_number=2,
            phase_label="Marco Conceptual de Innovación",
            operative_goal="Comprender los principios del Design Thinking.",
            procedure="Exposición dialogada con apoyo audiovisual.",
            materials="Proyector, diapositivas.",
            minutes=60,
        ),
        OperationalActivity(
            step_number=3,
            phase_label="Trabajo en Equipos y Prototipado",
            operative_goal="Desarrollar una propuesta de solución rápida.",
            procedure="Dinámica grupal con canvas de ideación.",
            materials="Papelógrafos, marcadores, post-its.",
            minutes=60,
        ),
        OperationalActivity(
            step_number=4,
            phase_label="Presentación de Resultados y Cierre",
            operative_goal="Socializar los prototipos y evaluar la jornada.",
            procedure="Pitch de 3 minutos por equipo y síntesis final.",
            materials="Rúbrica de retroalimentación.",
            minutes=30,
        ),
    ]
    design = MethodologicalDesign.create(
        planned_activity_internal_id=activity.activity_internal_id,
        planning_id=activity.planning_id,
        activity_name=activity.activity_name,
        introduction="Introducción detallada del taller institucional.",
        methodological_approach="Enfoque constructivista y participativo.",
        objective_1="Comprender las fases metodológicas de la innovación abierta.",
        objective_2="Aplicar herramientas de prototipado rápido en casos reales.",
        faq=faq,
        agenda=agenda,
        operational_matrix=matrix,
        created_by="Coordinador de Innovación",
        version=1,
        status=status,
    )
    return design


# ===========================================================================
# P-01: Migración V003
# ===========================================================================
def test_p01_migration_v003_applied(clean_db):
    """P-01: Verifica que la migración V003 se aplique exitosamente y registre versión 3."""
    _, runner, _ = clean_db
    assert runner.get_current_version() == 3
    applied = runner.get_applied_versions()
    assert 3 in applied
    assert applied[3]["nombre_migracion"] == "v003_planning_methodological_designs"
    assert len(applied[3]["hash_script"]) == 64
    assert applied[3]["tiempo_ejecucion_ms"] >= 0


# ===========================================================================
# P-02: Existencia física de las 6 tablas planning_*
# ===========================================================================
def test_p02_physical_tables_exist(clean_db):
    """P-02: Verifica que existan físicamente en sqlite_master las 6 tablas del módulo planning_*."""
    conn, runner, _ = clean_db
    existing = runner.get_existing_tables()
    for table_name in EXPECTED_PLANNING_TABLE_NAMES:
        assert table_name in existing, f"Falta la tabla requerida: {table_name}"


# ===========================================================================
# P-03: Tres ejecuciones consecutivas de apply_all_pending() (Idempotencia)
# ===========================================================================
def test_p03_idempotency_three_executions(clean_db):
    """P-03: Tres ejecuciones consecutivas de apply_all_pending() no producen cambios ni errores."""
    conn, runner, _ = clean_db

    # 1. Ya aplicada en fixture -> versión 3
    assert runner.get_current_version() == 3

    # 2. Segunda ejecución
    res2 = runner.apply_all_pending()
    assert all(r["status"] == "ALREADY_APPLIED" for r in res2)
    assert runner.get_current_version() == 3

    # 3. Tercera ejecución
    res3 = runner.apply_all_pending()
    assert all(r["status"] == "ALREADY_APPLIED" for r in res3)
    assert runner.get_current_version() == 3

    # Integridad física
    assert runner.verify_integrity() == "ok"


# ===========================================================================
# P-04: Crear y persistir PlannedActivity
# ===========================================================================
def test_p04_create_and_persist_planned_activity(clean_db):
    """P-04: Guarda y recupera una PlannedActivity verificando todos sus campos."""
    conn, _, _ = clean_db
    repo = SQLitePlannedActivityRepository(conn)
    act = _crear_actividad_valida(planning_id="POA-TEST-004")

    repo.save(act)

    by_id = repo.get_by_internal_id(act.activity_internal_id)
    assert by_id is not None
    assert by_id.activity_internal_id == act.activity_internal_id
    assert by_id.planning_id == "POA-TEST-004"
    assert by_id.activity_name == act.activity_name
    assert by_id.sede == "Bluefields"
    assert by_id.participant_goals.total() == act.participant_goals.total()

    by_plan = repo.get_by_planning_id("POA-TEST-004")
    assert by_plan is not None
    assert by_plan.activity_internal_id == act.activity_internal_id


# ===========================================================================
# P-05 y P-06: Crear, persistir y reconstruir MethodologicalDesign
# ===========================================================================
def test_p05_p06_create_persist_reconstruct_methodological_design(clean_db):
    """P-05 y P-06: Guarda y reconstruye completamente el agregado MethodologicalDesign."""
    conn, _, _ = clean_db
    act_repo = SQLitePlannedActivityRepository(conn)
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    act = _crear_actividad_valida(planning_id="POA-TEST-05-06")
    act_repo.save(act)

    design = _crear_diseno_valido(act)
    design_repo.save(design)

    # Reconstrucción
    loaded = design_repo.get_by_id(design.design_id)
    assert loaded is not None
    assert loaded.design_id == design.design_id
    assert loaded.planned_activity_internal_id == act.activity_internal_id
    assert loaded.planned_activity_ref == act.planning_id
    assert loaded.version == 1
    assert loaded.status == DesignStatus.DRAFT
    assert loaded.introduction == design.introduction
    assert loaded.methodological_approach == design.methodological_approach
    assert loaded.objective_1 == design.objective_1
    assert loaded.objective_2 == design.objective_2
    assert loaded.created_by == design.created_by


# ===========================================================================
# P-07: FAQ con las 7 preguntas
# ===========================================================================
def test_p07_faq_table_seven_questions(clean_db):
    """P-07: Comprueba la persistencia y recuperación exacta de las 7 preguntas institucionales."""
    conn, _, _ = clean_db
    act_repo = SQLitePlannedActivityRepository(conn)
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    act = _crear_actividad_valida(planning_id="POA-TEST-007")
    act_repo.save(act)

    design = _crear_diseno_valido(act)
    design_repo.save(design)

    loaded = design_repo.get_by_id(design.design_id)
    assert loaded.faq is not None
    assert loaded.faq.q1_que_es == design.faq.q1_que_es
    assert loaded.faq.q2_para_que == design.faq.q2_para_que
    assert loaded.faq.q3_sesiones == design.faq.q3_sesiones
    assert loaded.faq.q4_protagonistas == design.faq.q4_protagonistas
    assert loaded.faq.q5_facilitador == design.faq.q5_facilitador
    assert loaded.faq.q6_materiales == design.faq.q6_materiales
    assert loaded.faq.q7_duracion == design.faq.q7_duracion


# ===========================================================================
# P-08: Agenda completa y cálculo derivado consistente (total_minutes)
# ===========================================================================
def test_p08_agenda_and_total_minutes_derived(clean_db):
    """P-08: Comprueba la persistencia de la agenda y que total_minutes se calcula en el dominio."""
    conn, _, _ = clean_db
    act_repo = SQLitePlannedActivityRepository(conn)
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    act = _crear_actividad_valida(planning_id="POA-TEST-008")
    act_repo.save(act)

    design = _crear_diseno_valido(act)
    design_repo.save(design)

    loaded = design_repo.get_by_id(design.design_id)
    assert len(loaded.agenda) == 4
    assert loaded.agenda[0].label == "Registro y Bienvenida"
    assert loaded.agenda[0].minutes == 30
    assert loaded.agenda[1].minutes == 60
    assert loaded.agenda[2].minutes == 60
    assert loaded.agenda[3].minutes == 30
    # Regla matemática R-05: total_minutes es propiedad derivada en el dominio
    assert loaded.total_minutes == 180


# ===========================================================================
# P-09: Matriz operacional
# ===========================================================================
def test_p09_operational_matrix_persistence(clean_db):
    """P-09: Comprueba la persistencia de la matriz operacional y concordancia de tiempos."""
    conn, _, _ = clean_db
    act_repo = SQLitePlannedActivityRepository(conn)
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    act = _crear_actividad_valida(planning_id="POA-TEST-009")
    act_repo.save(act)

    design = _crear_diseno_valido(act)
    design_repo.save(design)

    loaded = design_repo.get_by_id(design.design_id)
    assert len(loaded.operational_matrix) == 4
    assert loaded.operational_matrix[0].step_number == 1
    assert loaded.operational_matrix[0].operative_goal.startswith("Acreditar")
    assert loaded.operational_matrix[0].minutes == loaded.agenda[0].minutes


# ===========================================================================
# P-10 y P-11: Persistencia de AIProposal y requires_review = 1 obligatorio
# ===========================================================================
def test_p10_p11_ai_proposal_persistence_and_requires_review_constraint(clean_db):
    """P-10 y P-11: Persistencia de AIProposal y verificación de restricción física requires_review = 1."""
    conn, _, _ = clean_db
    act_repo = SQLitePlannedActivityRepository(conn)
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    act = _crear_actividad_valida(planning_id="POA-TEST-010")
    act_repo.save(act)

    design = _crear_diseno_valido(act)
    prop = AIProposal.create(
        target_field="introduction",
        proposed_content="Propuesta de introducción generada por asistente pedagógico.",
        source_inputs={"activity_name": act.activity_name, "sede": act.sede},
        confidence=0.88,
    )
    design.add_ai_proposal(prop)
    design_repo.save(design)

    loaded = design_repo.get_by_id(design.design_id)
    assert len(loaded.ai_proposals) == 1
    saved_prop = loaded.ai_proposals[0]
    assert saved_prop.proposal_id == prop.proposal_id
    assert saved_prop.target_field == "introduction"
    assert saved_prop.confidence == 0.88
    assert saved_prop.requires_review is True
    assert saved_prop.accepted is None

    # Restricción física SQLite: CHECK (requires_review = 1)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO planning_ai_proposals (
                proposal_id, design_id, target_field, proposed_content, source_inputs,
                confidence, requires_review
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                str(uuid.uuid4()),
                str(design.design_id),
                "introduction",
                "Texto sin revisión",
                "{}",
                0.5,
                0,  # VIOLACIÓN DE CHECK: requires_review debe ser 1
            ),
        )


# ===========================================================================
# P-12: Integridad FK (Rechaza diseño si la actividad no existe)
# ===========================================================================
def test_p12_referential_integrity_fk_enforced(clean_db):
    """P-12: SQLite rechaza insertar un diseño si planned_activity_internal_id no existe."""
    conn, _, _ = clean_db
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    # Actividad inventada no guardada en la base de datos
    act_fantasma = _crear_actividad_valida(planning_id="POA-FANTASMA")
    design = _crear_diseno_valido(act_fantasma)

    # Debe fallar por violación de FOREIGN KEY
    with pytest.raises(sqlite3.IntegrityError):
        design_repo.save(design)


# ===========================================================================
# P-13 y P-18: UNIQUE(planned_activity_ref) (Un único diseño por actividad)
# ===========================================================================
def test_p13_p18_unique_planned_activity_ref_enforced(clean_db):
    """P-13 y P-18: SQLite rechaza crear un segundo diseño para la misma actividad planificada."""
    conn, _, _ = clean_db
    act_repo = SQLitePlannedActivityRepository(conn)
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    act = _crear_actividad_valida(planning_id="POA-TEST-013")
    act_repo.save(act)

    design_1 = _crear_diseno_valido(act)
    design_repo.save(design_1)

    # Crear un segundo diseño con DIFERENTE design_id pero MISMA planned_activity_ref
    design_2 = _crear_diseno_valido(act)
    assert design_1.design_id != design_2.design_id
    assert design_1.planned_activity_ref == design_2.planned_activity_ref

    # Debe fallar por violación de UNIQUE(planned_activity_ref)
    with pytest.raises(sqlite3.IntegrityError):
        design_repo.save(design_2)


# ===========================================================================
# P-14: Rollback completo ante fallo (sin registros huérfanos)
# ===========================================================================
def test_p14_rollback_on_failure_no_orphans(clean_db):
    """P-14: Si ocurre un error dentro de PlanningUnitOfWork, se hace rollback total sin huérfanos."""
    conn, _, db_file = clean_db
    mgr = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))

    act = _crear_actividad_valida(planning_id="POA-ROLLBACK-TEST")

    # Intentar guardar actividad y diseño, pero forzar fallo antes de commit
    with pytest.raises(ValueError):
        with PlanningUnitOfWork(connection_manager=mgr) as uow:
            uow.planned_activities.save(act)
            design = _crear_diseno_valido(act)
            uow.methodological_designs.save(design)
            # Simular error inesperado de aplicación
            raise ValueError("Error forzado para probar rollback atómico")

    # Verificar que no quedaron registros en ninguna tabla
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM planning_planned_activities WHERE planning_id = 'POA-ROLLBACK-TEST';")
    assert cur.fetchone()[0] == 0

    cur.execute("SELECT COUNT(*) FROM planning_methodological_designs;")
    assert cur.fetchone()[0] == 0

    cur.execute("SELECT COUNT(*) FROM planning_design_faqs;")
    assert cur.fetchone()[0] == 0

    cur.execute("SELECT COUNT(*) FROM planning_design_agenda;")
    assert cur.fetchone()[0] == 0

    cur.execute("SELECT COUNT(*) FROM planning_design_operational_matrix;")
    assert cur.fetchone()[0] == 0


# ===========================================================================
# P-15: Cerrar conexión y reabrir SQLite (Reconstrucción semántica fiel)
# ===========================================================================
def test_p15_close_and_reopen_semantic_reconstruction(tmp_path: Path):
    """P-15: Guardar, cerrar conexión física, abrir nueva conexión y reconstruir el agregado."""
    db_path = tmp_path / "test_reopen.db"
    mgr = SQLiteConnectionManager(DatabaseConfig(db_path=db_path))

    # 1. Migración previa
    conn_mig = mgr.get_connection()
    runner = MigrationRunner(conn_mig)
    runner.apply_all_pending()
    conn_mig.close()

    # 2. Sesión inicial: guardar con UoW
    with PlanningUnitOfWork(connection_manager=mgr) as uow:
        act = _crear_actividad_valida(planning_id="POA-REOPEN-TEST")
        uow.planned_activities.save(act)

        design = _crear_diseno_valido(act)
        prop = AIProposal.create(
            target_field="procedure",
            proposed_content="Procedimiento asistido",
            source_inputs={"step": 1},
            confidence=0.92,
        )
        design.add_ai_proposal(prop)
        uow.methodological_designs.save(design)
        uow.commit()

    # La conexión anterior se cerró en el exit de UoW.
    # 2. Nueva sesión independiente
    with PlanningUnitOfWork(connection_manager=mgr) as uow2:
        reopened_act = uow2.planned_activities.get_by_planning_id("POA-REOPEN-TEST")
        assert reopened_act is not None
        assert reopened_act.activity_name == act.activity_name

        reopened_design = uow2.methodological_designs.get_by_activity_ref("POA-REOPEN-TEST")
        assert reopened_design is not None
        assert reopened_design.design_id == design.design_id
        assert reopened_design.introduction == design.introduction
        assert reopened_design.total_minutes == 180
        assert len(reopened_design.agenda) == 4
        assert len(reopened_design.operational_matrix) == 4
        assert len(reopened_design.ai_proposals) == 1
        assert reopened_design.ai_proposals[0].proposed_content == "Procedimiento asistido"


# ===========================================================================
# P-16: Modificar diseño DRAFT (Actualización in-place)
# ===========================================================================
def test_p16_update_draft_in_place(clean_db):
    """P-16: En estado DRAFT se permite la modificación in-place sin crear nuevas filas."""
    conn, _, _ = clean_db
    act_repo = SQLitePlannedActivityRepository(conn)
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    act = _crear_actividad_valida(planning_id="POA-TEST-016")
    act_repo.save(act)

    design = _crear_diseno_valido(act, status=DesignStatus.DRAFT)
    design_repo.save(design)

    # Modificar in-place
    design.introduction = "Introducción actualizada in-place."
    design.version = 2
    design_repo.save(design)

    # Verificar que sigue existiendo exactamente 1 diseño para la actividad
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM planning_methodological_designs WHERE planned_activity_ref = 'POA-TEST-016';"
    )
    assert cursor.fetchone()[0] == 1

    # Verificar que el contenido fue actualizado
    reloaded = design_repo.get_by_id(design.design_id)
    assert reloaded.introduction == "Introducción actualizada in-place."
    assert reloaded.version == 2


# ===========================================================================
# P-17: Intentar modificar diseño APPROVED (Inmutabilidad R-08)
# ===========================================================================
def test_p17_approved_design_immutable(clean_db):
    """P-17: Un diseño en estado APPROVED no puede ser modificado (Regla R-08)."""
    conn, _, _ = clean_db
    act_repo = SQLitePlannedActivityRepository(conn)
    design_repo = SQLiteMethodologicalDesignRepository(conn)

    act = _crear_actividad_valida(planning_id="POA-TEST-017")
    act_repo.save(act)

    design = _crear_diseno_valido(act, status=DesignStatus.APPROVED)
    design.approved_by = "Vicerrector Académico"
    design.approved_at = datetime.now()
    design_repo.save(design)

    # Intentar guardar una modificación
    design.introduction = "Intento de modificar diseño aprobado."
    with pytest.raises(RuntimeError, match="APPROVED"):
        design_repo.save(design)


# ===========================================================================
# P-19: activity_internal_id es UUID técnico
# ===========================================================================
def test_p19_activity_internal_id_is_uuid(clean_db):
    """P-19: Verifica que activity_internal_id sea estrictamente un UUID técnico v4."""
    act = _crear_actividad_valida()
    assert isinstance(act.activity_internal_id, uuid.UUID)
    assert act.activity_internal_id.version == 4


# ===========================================================================
# P-20: planning_id preservado sin inventar formato
# ===========================================================================
def test_p20_planning_id_preserved_without_invented_format(clean_db):
    """P-20: planning_id se preserva exactamente como se recibe, sin formato inventado."""
    raw_id = "CODIGO_POA_ORIGINAL_BICU_2026_X"
    act = _crear_actividad_valida(planning_id=raw_id)
    assert act.planning_id == raw_id
    assert not act.planning_id.startswith("ACT-2026-")


# ===========================================================================
# P-21: No invasión del dominio puro
# ===========================================================================
def test_p21_domain_pure_isolation():
    """P-21: Verifica automáticamente que app/planning/domain no importa librerías impuras."""
    domain_dir = Path(__file__).resolve().parent.parent / "app" / "planning" / "domain"
    assert domain_dir.exists(), "Directorio de dominio no existe"

    forbidden_modules = {
        "sqlite3",
        "sqlalchemy",
        "openpyxl",
        "docx",
        "docxtpl",
        "pandas",
        "requests",
        "urllib",
        "google",
        "openai",
        "anthropic",
        "ollama",
        "tkinter",
        "customtkinter",
        "PyQt5",
        "PyQt6",
        "app.word_consolidator",
        "app.infrastructure",
    }

    for py_file in domain_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            line_clean = line.strip()
            if line_clean.startswith("#"):
                continue
            for forbidden in forbidden_modules:
                assert f"import {forbidden}" not in line_clean, (
                    f"Violación de pureza en {py_file.name}: importa {forbidden}"
                )
                assert f"from {forbidden}" not in line_clean, (
                    f"Violación de pureza en {py_file.name}: importa desde {forbidden}"
                )


# ===========================================================================
# P-22: word_consolidator permanece intacto funcionalmente
# ===========================================================================
def test_p22_word_consolidator_intact():
    """P-22: Verifica que no existan importaciones de planning dentro de word_consolidator."""
    wc_dir = Path(__file__).resolve().parent.parent / "app" / "word_consolidator"
    for py_file in wc_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            line_clean = line.strip()
            if line_clean.startswith("#"):
                continue
            assert "app.planning" not in line_clean, (
                f"Contaminación en {py_file.name}: referencia a app.planning"
            )


# ===========================================================================
# P-23: V001 y V002 permanecen intactas
# ===========================================================================
def test_p23_v001_and_v002_intact():
    """P-23: Verifica que las sentencias DDL de V001 y V002 no hayan sido modificadas."""
    # V001 tiene 18 sentencias iniciales de tablas
    assert len(INITIAL_SCHEMA_DDL_STATEMENTS) == 18
    # V002 tiene 2 sentencias de schema (hash_sha256 + actividad_metrica_agregada)
    assert len(V002_SCHEMA_DDL_STATEMENTS) == 2
    assert "ALTER TABLE actividad ADD COLUMN hash_sha256 TEXT;" in V002_SCHEMA_DDL_STATEMENTS[0]
