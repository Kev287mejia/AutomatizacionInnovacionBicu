"""
tests.test_planning_operational_integration_e2e

Suite de Pruebas de Integración Operativa End-to-End (E2E) — Módulo de Planificación BICU.
Fase 29.12 — Integración Operativa Planificación → Diseño → Validación → Aprobación → DOCX.

Objetivo:
  Demostrar y certificar el flujo operativo completo sin mocks utilizando
  exclusivamente las APIs públicas y capacidades certificadas existentes.

Cubre:
  01. Actividad existente en Planning V003
  02. Consulta y selección desde UI / servicio
  03. Consulta de ficha técnica y detalle institucional
  04. Creación de borrador DRAFT con prellenado determinista
  05. Carga y verificación de datos iniciales en DTO
  06. Completamiento de los cinco bloques institucionales
  07. Guardado con persistencia atómica relacional
  08. Cierre formal de sesión y conexión
  09. Apertura de nueva conexión física SQLite
  10. Reconstrucción del diseño existente desde repositorio
  11. Comparación campo por campo entre guardado y reconstruido
  12. Validación negativa con detección de observaciones bloqueantes
  13. Corrección de observaciones detectadas
  14. Validación positiva exitosa (is_valid = True)
  15. Aprobación formal institucional (sellado R-08)
  16. Intento de modificación post-aprobación
  17. Confirmación estricta de rechazo por inmutabilidad R-08
  18. Generación y validación física DOCX contra 11 criterios documentales
  19. Verificación PLANIFICADO != EJECUTADO (tablas de ejecución, auditoría y M1–M5)
  + Prueba separada e independiente de idempotencia de create_design_draft()
  + Prueba de re-apertura y re-exportación de diseño APPROVED sin alteración
"""

from __future__ import annotations

from datetime import date, datetime
import hashlib
from pathlib import Path
import sqlite3
from typing import Dict, Tuple
import uuid
import zipfile

import docx
import pytest

from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.schema import (
    EXPECTED_TABLE_NAMES_V002,
)
from app.planning.application.services import (
    MethodologicalDesignService,
    MethodologicalDocumentExportService,
)
from app.planning.domain.dtos import (
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    PlannedActivityDetailDTO,
    PlannedActivitySummaryDTO,
    TimeBlockDTO,
    UpdateMethodologicalDesignCommand,
    ValidationReportDTO,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.value_objects import (
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)
from app.planning.infrastructure.document_rendering import DocxMethodologicalDocumentRenderer
from app.planning.infrastructure.persistence import (
    EXPECTED_PLANNING_TABLE_NAMES,
    PlanningUnitOfWork,
    SQLiteMethodologicalDesignRepository,
    SQLitePlannedActivityRepository,
)
from app.planning.ui.services.planning_ui_service import PlanningUIError, PlanningUIService

# Hashes patrimoniales certificados custodiados (6/6 MATCH)
PATRIMONIAL_HASHES = {
    "M1": ("templates/Matriz_1_Consolidado_Actividades.xlsx", "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad"),
    "M2": ("templates/Matriz_2_Estudiantes.xlsx", "11419cd22d986e195694f27d15236204afa22526812f18cb4f2e1b7540f64400"),
    "M3": ("templates/Matriz_3_Academicos_Administrativos.xlsx", "dc1786616cb1a9bc2f82a74cc693ee20ab95b689b658b366164f502201b07c87"),
    "M4": ("templates/Matriz_4_Colaboradores.xlsx", "fd079c5f2be780e602dc563696a6f157d76c4c20410308037cec52f3d2654578"),
    "M5": ("templates/Matriz_5_Protagonistas_Beneficiados.xlsx", "a3dff20ec209de209f59dd8b1ad1be84aa7aebd1536ced406c59453a08973dc3"),
    "EXE": ("release/BICU_Consolidador.exe", "0a94be44de80079ffceee8abe34025cb6f604bc8a3126e209d221e4828df214b"),
}


def _calcular_sha256(ruta: Path) -> str:
    """Calcula el hash SHA-256 de un archivo físico."""
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


@pytest.fixture
def operational_env(tmp_path: Path):
    """Configura un entorno de integración operativa limpio con SQLite V001-V003 real.

    Aplica todas las migraciones oficiales y siembra una actividad planificada del POA.
    """
    db_file = tmp_path / "operational_planning_test.sqlite"
    mgr = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))
    conn = mgr.get_connection()
    runner = MigrationRunner(conn)
    runner.apply_all_pending()
    conn.close()

    # Siembra de actividad institucional en planning_planned_activities
    goals = ParticipantGoals(
        est_grado_m=12,
        est_grado_f=18,
        est_postgrado_m=3,
        est_postgrado_f=2,
        docentes_m=5,
        docentes_f=5,
        administrativos_m=2,
        administrativos_f=3,
        externos_m=0,
        externos_f=0,
    )
    act = PlannedActivity.create(
        planning_id="POA-BLUE-2026-042",
        activity_name="Taller Institucional de Metodologías Ágiles para la Innovación",
        sede="Bluefields",
        area_responsable="Dirección de Innovación y Emprendimiento",
        eje_estrategia="EJE_11",   # Innovación, Ciencia, Tecnología e Investigación
        programa="PGM_07",         # Emprendimiento y Desarrollo Económico
        tipo_evento="EVT_CAPACITACION",
        dep_sede="RACCS",
        mun_sede="Bluefields",
        proposito="Capacitar a la comunidad universitaria en el diseño ágil de soluciones innovadoras.",
        fecha_evento=date(2026, 11, 12),
        codigo_presupuestario="PRE-INNOV-2026",
        participant_goals=goals,
    )

    with PlanningUnitOfWork(db_path=db_file) as uow:
        uow.planned_activities.save(act)
        uow.commit()

    return db_file, act


def _crear_ui_service(db_file: Path) -> PlanningUIService:
    """Construye una instancia de PlanningUIService conectada a la base SQLite especificada."""
    uow = PlanningUnitOfWork(db_path=db_file)
    design_service = MethodologicalDesignService(uow=uow)

    conn = sqlite3.connect(str(db_file))
    design_repo = SQLiteMethodologicalDesignRepository(conn)
    renderer = DocxMethodologicalDocumentRenderer()
    export_service = MethodologicalDocumentExportService(
        design_repository=design_repo,
        renderer=renderer,
    )
    return PlanningUIService(
        design_service=design_service,
        export_service=export_service,
    )


# ===========================================================================
# SUITE E2E DE INTEGRACIÓN OPERATIVA (19 PASOS REALES SIN MOCKS)
# ===========================================================================

class TestPlanningOperationalIntegrationE2E:
    """Demostración y certificación del flujo operativo institucional completo."""

    def test_flujo_operativo_completo_19_pasos(self, operational_env, tmp_path: Path):
        """Ejecuta ordenadamente los 19 pasos del flujo operativo institucional."""
        db_file, act_inicial = operational_env
        planning_id = act_inicial.planning_id

        # ---------------------------------------------------------------------
        # ESTADO PREVIO: Snapshot de conteos de tablas de ejecución y hashes
        # ---------------------------------------------------------------------
        # Tablas de ejecución e histórico de V001/V002 (excluyendo auditoria_evento y schema_version)
        tablas_ejecucion = sorted(list(EXPECTED_TABLE_NAMES_V002 - {"schema_version", "auditoria_evento"}))
        assert len(tablas_ejecucion) == 18, f"Se esperaban 18 tablas de ejecución, halladas: {len(tablas_ejecucion)}"

        conn_snap = sqlite3.connect(str(db_file))
        conteos_ejecucion_before = {}
        for t in tablas_ejecucion:
            cur = conn_snap.execute(f"SELECT COUNT(*) FROM {t};")
            conteos_ejecucion_before[t] = cur.fetchone()[0]

        cur_aud = conn_snap.execute("SELECT COUNT(*) FROM auditoria_evento;")
        conteo_auditoria_before = cur_aud.fetchone()[0]

        cur_plan_act = conn_snap.execute("SELECT COUNT(*) FROM planning_planned_activities;")
        conteo_plan_act_before = cur_plan_act.fetchone()[0]
        conn_snap.close()

        # Hashes patrimoniales BEFORE
        hashes_patrimoniales_before = {}
        for k, (rel_path, exp_hash) in PATRIMONIAL_HASHES.items():
            h = _calcular_sha256(Path(rel_path))
            assert h == exp_hash, f"Hash previo de {k} no coincide con el certificado"
            hashes_patrimoniales_before[k] = h

        # ---------------------------------------------------------------------
        # PASO 01: Actividad existente en Planning V003
        # ---------------------------------------------------------------------
        assert conteo_plan_act_before >= 1

        # ---------------------------------------------------------------------
        # PASO 02: Consulta / Selección mediante PlanningUIService
        # ---------------------------------------------------------------------
        ui_svc = _crear_ui_service(db_file)
        actividades = ui_svc.list_activities(sede="Bluefields", status="SIN_DISENO")
        assert len(actividades) == 1
        assert actividades[0].planning_id == planning_id
        assert actividades[0].design_status == "SIN_DISENO"
        assert actividades[0].total_participants == 50

        # ---------------------------------------------------------------------
        # PASO 03: Detalle de actividad planificada
        # ---------------------------------------------------------------------
        detalle = ui_svc.get_activity_detail(planning_id)
        assert detalle is not None
        assert detalle.planning_id == planning_id
        assert detalle.activity_name == "Taller Institucional de Metodologías Ágiles para la Innovación"
        assert detalle.sede == "Bluefields"
        assert detalle.area_responsable == "Dirección de Innovación y Emprendimiento"
        assert detalle.design_status == "SIN_DISENO"
        assert detalle.design_id is None
        assert detalle.participant_goals is not None
        assert detalle.participant_goals.total() == 50

        # ---------------------------------------------------------------------
        # PASO 04: Creación de Diseño DRAFT con prellenado determinista
        # ---------------------------------------------------------------------
        draft_dto = ui_svc.create_design_draft(
            activity_ref=planning_id,
            created_by="Dra. Kenia Mejia",
        )
        assert draft_dto is not None
        assert draft_dto.created_by == "Dra. Kenia Mejia"
        assert draft_dto.approved_by is None, "DRAFT: no debe tener aprobador"
        assert draft_dto.document_title == "Diseño metodológico Taller Institucional de Metodologías Ágiles para la Innovación"
        assert draft_dto.faq is not None
        assert draft_dto.faq.q1_que_es == "Taller Institucional de Metodologías Ágiles para la Innovación"
        assert draft_dto.faq.q2_para_que == "Capacitar a la comunidad universitaria en el diseño ágil de soluciones innovadoras."
        assert draft_dto.faq.q3_sesiones == "Sesión única"
        assert "50 participantes" in draft_dto.faq.q4_protagonistas
        assert draft_dto.faq.q5_facilitador == "Dirección de Innovación y Emprendimiento"
        # Regla: ausencia de fabricación: objetivos no inventados
        assert draft_dto.objective_1 == ""
        assert draft_dto.objective_2 == ""

        # ---------------------------------------------------------------------
        # PASO 05: Apertura / Edición (Verificación de DTO inicial)
        # ---------------------------------------------------------------------
        design_id = draft_dto.design_id
        assert isinstance(design_id, uuid.UUID)

        # ---------------------------------------------------------------------
        # PASO 06: Completar los cinco bloques institucionales
        # ---------------------------------------------------------------------
        intro_text = (
            "En el marco del fortalecimiento institucional y los lineamientos del Plan Operativo Anual (POA), "
            "la Bluefields Indian & Caribbean University (BICU) promueve la formación continua en innovación."
        )
        enfoque_text = (
            "Se adopta un enfoque constructivista y experiencial bajo la metodología Design Thinking, "
            "favoreciendo la participación activa de los protagonistas mediante dinámicas de co-creación."
        )
        obj1 = "Comprender los fundamentos y etapas del proceso de innovación ágil."
        obj2 = "Diseñar prototipos de soluciones innovadoras aplicables al contexto comunitario y regional."

        agenda_items = (
            TimeBlockDTO(sequence=1, label="Registro y Bienvenida Institucional", minutes=30),
            TimeBlockDTO(sequence=2, label="Marco Conceptual y Metodología Design Thinking", minutes=60),
            TimeBlockDTO(sequence=3, label="Talleres de Ideación y Prototipado en Equipos", minutes=90),
            TimeBlockDTO(sequence=4, label="Presentación de Prototipos, Retroalimentación y Cierre", minutes=60),
        )

        matrix_items = (
            OperationalActivityDTO(
                step_number=1,
                phase_label="Registro y Bienvenida Institucional",
                operative_goal="Acreditar a los protagonistas y presentar los objetivos institucionales.",
                procedure="Recepción, entrega de materiales y palabras de bienvenida de autoridades.",
                materials="Listas de asistencia oficiales, carpetas institucionales, credenciales.",
                minutes=30,
            ),
            OperationalActivityDTO(
                step_number=2,
                phase_label="Marco Conceptual y Metodología Design Thinking",
                operative_goal="Apropiar a los participantes en las fases de empatía, definición e ideación.",
                procedure="Exposición magistral dialogada con apoyo audiovisual y ejemplos prácticos.",
                materials="Proyector multimedia, computadora portátil, diapositivas oficiales.",
                minutes=60,
            ),
            OperationalActivityDTO(
                step_number=3,
                phase_label="Talleres de Ideación y Prototipado en Equipos",
                operative_goal="Desarrollar prototipos de baja fidelidad en mesas de trabajo interdisciplinarias.",
                procedure="Dinámica guiada con lienzos de ideación y matrices de priorización de soluciones.",
                materials="Papelógrafos, notas adhesivas (post-its), marcadores de colores, cinta adhesiva.",
                minutes=90,
            ),
            OperationalActivityDTO(
                step_number=4,
                phase_label="Presentación de Prototipos, Retroalimentación y Cierre",
                operative_goal="Socializar las soluciones desarrolladas y evaluar la pertinencia metodológica.",
                procedure="Sesión de pitch de 3 minutos por mesa, sesión de preguntas y evaluación final.",
                materials="Rúbrica de evaluación, formulario de satisfacción institucional.",
                minutes=60,
            ),
        )

        faq_completed = FAQTableDTO(
            q1_que_es="Taller Institucional de Metodologías Ágiles para la Innovación",
            q2_para_que="Capacitar a la comunidad universitaria en el diseño ágil de soluciones innovadoras.",
            q3_sesiones="Sesión única intensiva",
            q4_protagonistas="50 protagonistas (estudiantes, docentes y personal administrativo)",
            q5_facilitador="Dirección de Innovación y Emprendimiento — BICU",
            q6_materiales="Papelógrafos, marcadores, proyector, notas adhesivas, material didáctico.",
            q7_duracion="240 minutos (4 horas)",
        )

        cmd_completo = UpdateMethodologicalDesignCommand(
            design_id=design_id,
            introduction_text=intro_text,
            methodological_approach=enfoque_text,
            objectives=(obj1, obj2),
            faq=faq_completed,
            agenda=agenda_items,
            operational_matrix=matrix_items,
        )

        # ---------------------------------------------------------------------
        # PASO 07: Guardar el borrador en base de datos
        # ---------------------------------------------------------------------
        saved_dto = ui_svc.update_design_draft(cmd_completo)
        assert saved_dto.introduction == intro_text
        assert saved_dto.methodological_approach == enfoque_text
        assert saved_dto.objective_1 == obj1
        assert saved_dto.objective_2 == obj2
        assert len(saved_dto.agenda) == 4
        assert saved_dto.total_minutes == 240
        assert len(saved_dto.operational_matrix) == 4

        # ---------------------------------------------------------------------
        # PASO 08: Cerrar sesión y conexión
        # ---------------------------------------------------------------------
        # Se destruyen las instancias previas de servicio para asegurar desconexión
        del ui_svc

        # ---------------------------------------------------------------------
        # PASO 09: Nueva conexión física SQLite
        # ---------------------------------------------------------------------
        nueva_conn = sqlite3.connect(str(db_file))

        # ---------------------------------------------------------------------
        # PASO 10: Reconstrucción del diseño existente desde repositorio
        # ---------------------------------------------------------------------
        repo_reconstruccion = SQLiteMethodologicalDesignRepository(nueva_conn)
        reconstructed_aggregate = repo_reconstruccion.get_by_id(design_id)
        nueva_conn.close()

        assert reconstructed_aggregate is not None, "El aggregate debe reconstruirse fielmente desde SQLite"

        # ---------------------------------------------------------------------
        # PASO 11: Comparación campo por campo entre guardado y reconstruido
        # ---------------------------------------------------------------------
        assert reconstructed_aggregate.design_id == design_id
        assert reconstructed_aggregate.planned_activity_ref == planning_id
        assert reconstructed_aggregate.introduction_text == intro_text
        assert reconstructed_aggregate.methodological_approach == enfoque_text
        assert reconstructed_aggregate.objectives == [obj1, obj2]
        assert reconstructed_aggregate.created_by == "Dra. Kenia Mejia"
        assert reconstructed_aggregate.status == DesignStatus.DRAFT
        assert reconstructed_aggregate.total_minutes == 240

        # Bloque 3 FAQ
        assert reconstructed_aggregate.faq_table is not None
        assert reconstructed_aggregate.faq_table.q1_que_es == faq_completed.q1_que_es
        assert reconstructed_aggregate.faq_table.q2_para_que == faq_completed.q2_para_que
        assert reconstructed_aggregate.faq_table.q3_sesiones == faq_completed.q3_sesiones
        assert reconstructed_aggregate.faq_table.q4_protagonistas == faq_completed.q4_protagonistas
        assert reconstructed_aggregate.faq_table.q5_facilitador == faq_completed.q5_facilitador
        assert reconstructed_aggregate.faq_table.q6_materiales == faq_completed.q6_materiales
        assert reconstructed_aggregate.faq_table.q7_duracion == "240 minutos"

        # Bloque 4 Agenda
        assert len(reconstructed_aggregate.agenda) == 4
        for idx, item in enumerate(reconstructed_aggregate.agenda):
            assert item.sequence == agenda_items[idx].sequence
            assert item.label == agenda_items[idx].label
            assert item.minutes == agenda_items[idx].minutes

        # Bloque 5 Matriz Operativa
        assert len(reconstructed_aggregate.operational_matrix) == 4
        for idx, item in enumerate(reconstructed_aggregate.operational_matrix):
            assert item.step_number == matrix_items[idx].step_number
            assert item.phase_label == matrix_items[idx].phase_label
            assert item.operative_goal == matrix_items[idx].operative_goal
            assert item.procedure == matrix_items[idx].procedure
            assert item.materials == matrix_items[idx].materials
            assert item.minutes == matrix_items[idx].minutes

        # ---------------------------------------------------------------------
        # PASO 12: Validación negativa con errores bloqueantes
        # ---------------------------------------------------------------------
        ui_svc_v2 = _crear_ui_service(db_file)

        # Introducir una omisión temporal (eliminar objetivos y desincronizar agenda)
        cmd_con_errores = UpdateMethodologicalDesignCommand(
            design_id=design_id,
            objectives=(),  # Viola R-07 (deben ser exactamente 2)
        )
        ui_svc_v2.update_design_draft(cmd_con_errores)

        report_errores = ui_svc_v2.validate_design(design_id)
        assert not report_errores.is_valid, "La validación debe fallar si faltan objetivos"
        assert len(report_errores.errors) > 0
        rule_ids = [e.rule_id for e in report_errores.errors]
        assert "V-MD-11" in rule_ids, "Debe reportar violación de V-MD-11 (Objetivos R-07)"

        # Comprobar que no es posible aprobar con errores
        with pytest.raises(PlanningUIError) as exc_aprobacion_bloqueada:
            ui_svc_v2.approve_design(design_id, approved_by="Aprobador Ilegal")
        assert "observaciones pendientes" in exc_aprobacion_bloqueada.value.message

        # ---------------------------------------------------------------------
        # PASO 13: Corrección de las observaciones detectadas
        # ---------------------------------------------------------------------
        cmd_corregido = UpdateMethodologicalDesignCommand(
            design_id=design_id,
            objectives=(obj1, obj2),  # Subsanar objetivos (R-07)
        )
        ui_svc_v2.update_design_draft(cmd_corregido)

        # ---------------------------------------------------------------------
        # PASO 14: Validación exitosa (V-MD-01 a V-MD-12)
        # ---------------------------------------------------------------------
        report_exitoso = ui_svc_v2.validate_design(design_id)
        assert report_exitoso.is_valid, "El diseño corregido debe ser 100% válido"
        assert len(report_exitoso.errors) == 0

        # ---------------------------------------------------------------------
        # PASO 15: Aprobación formal institucional
        # ---------------------------------------------------------------------
        approver_name = "Dra. Kenia Mejia — Directora de Innovación y Emprendimiento"
        approved_dto = ui_svc_v2.approve_design(design_id, approved_by=approver_name)
        assert approved_dto.approved_by == approver_name

        # Verificar en base de datos el sellado formal y estado APPROVED persistido
        conn_app = sqlite3.connect(str(db_file))
        cur_app = conn_app.execute(
            "SELECT approved_by, approved_at, status FROM planning_methodological_designs WHERE design_id = ?;",
            (str(design_id),),
        )
        row_app = cur_app.fetchone()
        conn_app.close()
        assert row_app[0] == approver_name
        assert row_app[1] is not None, "approved_at debe registrar timestamp de auditoría"
        assert row_app[2] == "APPROVED"

        detalle_post_aprobacion = ui_svc_v2.get_activity_detail(planning_id)
        assert detalle_post_aprobacion.design_status == "APPROVED"

        # ---------------------------------------------------------------------
        # PASO 16: Intento de modificación post-aprobación
        # ---------------------------------------------------------------------
        cmd_modificacion_ilegal = UpdateMethodologicalDesignCommand(
            design_id=design_id,
            introduction_text="Intento ilegal de modificar diseño aprobado...",
        )

        # ---------------------------------------------------------------------
        # PASO 17: Confirmación estricta de rechazo R-08
        # ---------------------------------------------------------------------
        with pytest.raises(PlanningUIError) as exc_r08:
            ui_svc_v2.update_design_draft(cmd_modificacion_ilegal)

        assert "Regla R-08" in exc_r08.value.message
        assert "APROBADO" in exc_r08.value.message

        # Confirmar que en base de datos el texto NO cambió
        conn_check = sqlite3.connect(str(db_file))
        cur_chk = conn_check.execute(
            "SELECT introduction_text, status FROM planning_methodological_designs WHERE design_id = ?;",
            (str(design_id),),
        )
        row_chk = cur_chk.fetchone()
        conn_check.close()
        assert row_chk[0] == intro_text, "El texto institucional no debió ser alterado"
        assert row_chk[1] == "APPROVED", "El estado debe permanecer APPROVED"

        # ---------------------------------------------------------------------
        # PASO 18: Generación y validación física DOCX (11 Criterios)
        # ---------------------------------------------------------------------
        output_docx = tmp_path / f"Diseno_Metodologico_{planning_id}.docx"
        generated_path_str = ui_svc_v2.export_docx(design_id, output_path=output_docx)
        generated_path = Path(generated_path_str)

        # Criterio 1: El archivo existe físicamente
        assert generated_path.exists(), "El archivo DOCX debe existir físicamente"

        # Criterio 2: La extensión es .docx
        assert generated_path.suffix.lower() == ".docx", "La extensión debe ser .docx"

        # Criterio 3: python-docx puede abrirlo correctamente sin corrupción
        doc = docx.Document(str(generated_path))
        assert doc is not None

        # Extracción de párrafos y tablas
        all_paragraphs_text = "\n".join(p.text for p in doc.paragraphs)
        tables = doc.tables

        # Criterio 4: Bloque 1 presente (Introducción y Enfoque)
        assert "INTRODUCCIÓN" in all_paragraphs_text.upper() or "I. INTRODUCCIÓN" in all_paragraphs_text.upper()
        assert "fortalecimiento institucional" in all_paragraphs_text
        assert "Design Thinking" in all_paragraphs_text

        # Criterio 5: Bloque 2 presente (Objetivos)
        assert "OBJETIVOS" in all_paragraphs_text.upper()
        assert "proceso de innovación ágil" in all_paragraphs_text
        assert "soluciones innovadoras aplicables" in all_paragraphs_text

        # Criterio 6: Bloque 3 presente (Tabla 1 FAQ con 7 preguntas)
        assert len(tables) >= 3, f"Se esperaban al menos 3 tablas institucionales, halladas: {len(tables)}"
        faq_table_text = " ".join(cell.text for row in tables[0].rows for cell in row.cells)
        assert "Taller Institucional" in faq_table_text
        assert "Sesión única intensiva" in faq_table_text
        assert "50 protagonistas" in faq_table_text
        assert "Dirección de Innovación y Emprendimiento" in faq_table_text
        assert "Papelógrafos" in faq_table_text

        # Criterio 7: Bloque 4 presente (Tabla 2 Programa/Agenda)
        agenda_table_text = " ".join(cell.text for row in tables[1].rows for cell in row.cells)
        assert "Bienvenida Institucional" in agenda_table_text
        assert "Design Thinking" in agenda_table_text
        assert "Talleres de Ideación" in agenda_table_text
        assert "240" in agenda_table_text or "Total" in agenda_table_text

        # Criterio 8: Bloque 5 presente (Tabla 3 Matriz Operativa)
        matrix_table_text = " ".join(cell.text for row in tables[2].rows for cell in row.cells)
        assert "Acreditar a los protagonistas" in matrix_table_text
        assert "Lienzos de ideación" in matrix_table_text or "post-its" in matrix_table_text
        assert "Sesión de pitch" in matrix_table_text

        # Criterio 9: Correspondencia semántica con diseño aprobado
        assert "TALLER INSTITUCIONAL" in all_paragraphs_text.upper() or planning_id in all_paragraphs_text

        # Criterio 10: Integridad del archivo (no corrupto / formato ZIP válido)
        file_bytes = generated_path.read_bytes()
        assert file_bytes[:4] == b"PK\x03\x04", "El archivo DOCX debe ser un contenedor OpenXML/ZIP válido"

        # Criterio 11: Hash documental calculable y registrado
        docx_hash = _calcular_sha256(generated_path)
        assert len(docx_hash) == 64
        # Tamaño informativo (no criterio de aprobación)
        file_size = generated_path.stat().st_size
        assert file_size > 0

        # ---------------------------------------------------------------------
        # PASO 19: Verificación PLANIFICADO != EJECUTADO
        # ---------------------------------------------------------------------
        conn_after = sqlite3.connect(str(db_file))

        # Invariante A: Planning
        cur_act_after = conn_after.execute("SELECT COUNT(*) FROM planning_planned_activities;")
        conteo_plan_act_after = cur_act_after.fetchone()[0]
        assert conteo_plan_act_after == conteo_plan_act_before, (
            "No deben crearse ni eliminarse actividades del POA durante el flujo de diseño"
        )
        cur_ai = conn_after.execute("SELECT COUNT(*) FROM planning_ai_proposals;")
        assert cur_ai.fetchone()[0] == 0, "No deben crearse propuestas de IA en esta fase manual"

        # Invariante B: Tablas de Ejecución e Histórico (18 tablas)
        for t in tablas_ejecucion:
            cur = conn_after.execute(f"SELECT COUNT(*) FROM {t};")
            cnt_after = cur.fetchone()[0]
            assert cnt_after == conteos_ejecucion_before[t], (
                f"Violación de contención: la tabla de ejecución '{t}' fue alterada. "
                f"Antes: {conteos_ejecucion_before[t]}, Después: {cnt_after}"
            )

        # Invariante C: Tratamiento diferenciado de auditoria_evento
        cur_aud_after = conn_after.execute("SELECT COUNT(*) FROM auditoria_evento;")
        conteo_auditoria_after = cur_aud_after.fetchone()[0]
        if conteo_auditoria_after > conteo_auditoria_before:
            # Inspeccionar eventos nuevos
            cur_events = conn_after.execute("SELECT tabla_afectada, tipo_operacion FROM auditoria_evento;")
            for row_ev in cur_events.fetchall():
                tabla_afectada = row_ev[0]
                assert tabla_afectada not in tablas_ejecucion, (
                    f"Violación: auditoria_evento registró afectación sobre tabla de ejecución '{tabla_afectada}'"
                )
        else:
            assert conteo_auditoria_after == conteo_auditoria_before

        conn_after.close()

        # Invariante D: M1–M5 y EXE permanecen intactos
        for k, (rel_path, exp_hash) in PATRIMONIAL_HASHES.items():
            h_after = _calcular_sha256(Path(rel_path))
            assert h_after == exp_hash, f"Hash patrimonial de {k} cambió tras la ejecución"
            assert h_after == hashes_patrimoniales_before[k]

    def test_idempotencia_creacion_draft(self, operational_env):
        """Demuestra que create_design_draft() es estrictamente idempotente.

        Múltiples llamadas para la misma actividad retornan el mismo diseño,
        preservan el autor original y no duplican registros en la base de datos.
        """
        db_file, act = operational_env
        ui_svc = _crear_ui_service(db_file)

        # Primera llamada
        d1 = ui_svc.create_design_draft(act.planning_id, created_by="Profesor_Kenia")
        assert d1.created_by == "Profesor_Kenia"

        # Segunda llamada con autor diferente
        d2 = ui_svc.create_design_draft(act.planning_id, created_by="Segundo_Usuario")
        assert d2.design_id == d1.design_id, "Debe retornar el mismo design_id"
        assert d2.created_by == "Profesor_Kenia", "Debe preservar el creador original"

        # Verificar unicidad física en SQLite V003
        conn = sqlite3.connect(str(db_file))
        cur = conn.execute(
            "SELECT COUNT(*) FROM planning_methodological_designs WHERE planned_activity_ref = ?;",
            (act.planning_id,),
        )
        assert cur.fetchone()[0] == 1, "Debe existir exactamente 1 registro de diseño para la actividad"
        conn.close()

    def test_docx_reapertura_y_reexportacion_sin_alterar_diseno(self, operational_env, tmp_path: Path):
        """Demuestra que un diseño APPROVED puede reabrirse y reexportarse a DOCX idéntico."""
        db_file, act = operational_env
        ui_svc = _crear_ui_service(db_file)

        # 1. Crear, completar, validar y aprobar
        draft = ui_svc.create_design_draft(act.planning_id, created_by="Autor_Reexport")
        cmd = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="Introducción formal para prueba de reexportación.",
            methodological_approach="Enfoque participativo institucional.",
            objectives=("Objetivo de reexportación 1", "Objetivo de reexportación 2"),
            faq=FAQTableDTO(
                q1_que_es=act.activity_name,
                q2_para_que="Propósito",
                q3_sesiones="Sesión única",
                q4_protagonistas="50",
                q5_facilitador="Facilitador",
                q6_materiales="Materiales requeridos",
                q7_duracion="60 minutos",
            ),
            agenda=(TimeBlockDTO(sequence=1, label="Sesión Única", minutes=60),),
            operational_matrix=(
                OperationalActivityDTO(
                    step_number=1,
                    phase_label="Sesión Única",
                    operative_goal="Meta operativa",
                    procedure="Procedimiento",
                    materials="Materiales",
                    minutes=60,
                ),
            ),
        )
        ui_svc.update_design_draft(cmd)
        approved = ui_svc.approve_design(draft.design_id, approved_by="Director_Academico")

        # 2. Primera exportación DOCX
        docx_1 = tmp_path / "export_1.docx"
        ui_svc.export_docx(approved.design_id, output_path=docx_1)
        assert docx_1.exists()
        assert docx_1.stat().st_size > 0

        # 3. Cerrar sesión y simular reapertura limpia
        del ui_svc
        ui_svc_reopened = _crear_ui_service(db_file)

        # 4. Consultar y verificar inmutabilidad
        detalle = ui_svc_reopened.get_activity_detail(act.planning_id)
        assert detalle.design_status == "APPROVED"
        assert detalle.design_id == approved.design_id

        # 5. Segunda exportación DOCX desde la nueva sesión
        docx_2 = tmp_path / "export_2.docx"
        ui_svc_reopened.export_docx(approved.design_id, output_path=docx_2)
        assert docx_2.exists()
        assert docx_2.stat().st_size > 0

        # 5.1 Comparación normalizada del contenedor OpenXML / ZIP (ignorando timestamps de empaquetado)
        with zipfile.ZipFile(docx_1) as z1, zipfile.ZipFile(docx_2) as z2:
            assert set(z1.namelist()) == set(z2.namelist()), (
                "Ambos archivos DOCX deben contener exactamente la misma estructura de entradas OpenXML"
            )
            # Verificación explícita de word/document.xml
            xml1 = z1.read("word/document.xml")
            xml2 = z2.read("word/document.xml")
            assert xml1 == xml2, (
                "El contenido de 'word/document.xml' debe ser 100% idéntico entre ambas exportaciones"
            )
            # Verificación exhaustiva de cada entrada interna del contenedor ZIP
            for entry_name in z1.namelist():
                assert z1.read(entry_name) == z2.read(entry_name), (
                    f"El contenido interno de '{entry_name}' debe ser idéntico entre ambas exportaciones"
                )

        # 5.2 Validación estructural y semántica completa mediante python-docx
        doc1 = docx.Document(docx_1)
        doc2 = docx.Document(docx_2)

        # Mismos párrafos y mismo texto en orden idéntico
        assert len(doc1.paragraphs) == len(doc2.paragraphs), "Debe existir el mismo número de párrafos"
        assert [p.text for p in doc1.paragraphs] == [p.text for p in doc2.paragraphs], (
            "El texto de todos los párrafos debe ser exactamente idéntico"
        )

        # Mismas tablas, filas y celdas con idéntico contenido
        assert len(doc1.tables) == len(doc2.tables), "Debe existir el mismo número de tablas"
        for t_idx, (t1, t2) in enumerate(zip(doc1.tables, doc2.tables)):
            assert len(t1.rows) == len(t2.rows), f"Tabla {t_idx} debe tener el mismo número de filas"
            for r_idx, (r1, r2) in enumerate(zip(t1.rows, t2.rows)):
                assert len(r1.cells) == len(r2.cells), f"Fila {r_idx} de tabla {t_idx} debe tener el mismo número de celdas"
                assert [c.text for c in r1.cells] == [c.text for c in r2.cells], (
                    f"Contenido de celdas en fila {r_idx} de tabla {t_idx} debe ser idéntico"
                )

        # Mismos cinco bloques institucionales verificables
        full_text = "\n".join(p.text for p in doc2.paragraphs)
        assert "Introducción formal para prueba de reexportación" in full_text
        assert "Objetivo de reexportación 1" in full_text
        assert "Objetivo de reexportación 2" in full_text
        assert "Enfoque participativo institucional" in full_text

        # Verificación en tablas de los bloques FAQ, Agenda y Matriz Operativa
        assert len(doc2.tables) >= 3, "Deben existir al menos 3 tablas institucionales"
        faq_text = " ".join(c.text for row in doc2.tables[0].rows for c in row.cells)
        assert "Propósito" in faq_text
        agenda_text = " ".join(c.text for row in doc2.tables[1].rows for c in row.cells)
        assert "Sesión Única" in agenda_text
        matriz_text = " ".join(c.text for row in doc2.tables[2].rows for c in row.cells)
        assert "Meta operativa" in matriz_text

        # 6. Comprobar que en base de datos el diseño no cambió
        conn = sqlite3.connect(str(db_file))
        cur = conn.execute(
            "SELECT approved_by, approved_at, status FROM planning_methodological_designs WHERE design_id = ?;",
            (str(approved.design_id),),
        )
        row = cur.fetchone()
        conn.close()
        assert row[0] == "Director_Academico"
        assert row[1] is not None
        assert row[2] == "APPROVED"
