"""
tests.test_planning_e2e_real_poa_to_ui_list

Prueba End-to-End (E2E) Real — Módulo 3: Planificación y Diseño Metodológico.
Fase 29.26.1 — Conexión Controlada de Ingestión POA en el Módulo 3.

Demuestra la cadena de valor completa sin datos ficticios:
  1. Base de datos limpia con 0 actividades iniciales en el Módulo 3.
  2. Ingestión de la fuente institucional real 'Documento_Kevds_2.xlsx'.
  3. Validación de PlanningIngestionReportDTO y persistencia atómica V003.
  4. Refresco y consulta en el listado del Módulo 3 (estado 'SIN_DISENO').
  5. Consulta de ficha de detalle con datos y metas reales.
  6. Creación y completamiento de los 5 bloques del Diseño Metodológico.
  7. Validación institucional positiva (is_valid == True).
  8. Aprobación formal institucional (sellado R-08).
  9. Generación física del documento Word (.docx) oficial.
  10. Reimportación de la misma fuente POA demostrando la protección estricta R-08.
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import pytest

from app.planning.application.services import (
    MethodologicalDesignService,
    MethodologicalDocumentExportService,
    PlannedActivityIngestionService,
)
from app.planning.domain.dtos import (
    FAQTableDTO,
    OperationalActivityDTO,
    TimeBlockDTO,
    UpdateMethodologicalDesignCommand,
)
from app.planning.infrastructure.document_rendering import DocxMethodologicalDocumentRenderer
from app.planning.infrastructure.persistence import (
    PlanningUnitOfWork,
    SQLiteMethodologicalDesignRepository,
)
from app.planning.infrastructure.persistence.schema_v003 import V003_SCHEMA_DDL_STATEMENTS
from app.planning.infrastructure.readers.excel_planning_reader import ExcelPlanningReader
from app.planning.ui.services.planning_ui_service import PlanningUIService


@pytest.fixture
def clean_db(tmp_path: Path) -> Path:
    """Crea una base de datos SQLite con el esquema V003 completamente limpio."""
    db_file = tmp_path / "test_e2e_poa_to_ui.sqlite"
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        for stmt in V003_SCHEMA_DDL_STATEMENTS:
            cursor.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    return db_file


@pytest.fixture
def ui_service_e2e(clean_db: Path) -> PlanningUIService:
    """Configura PlanningUIService conectado a la base de datos de prueba."""
    uow = PlanningUnitOfWork(db_path=clean_db)
    design_service = MethodologicalDesignService(uow=uow)

    conn = sqlite3.connect(str(clean_db))
    design_repo = SQLiteMethodologicalDesignRepository(conn)
    renderer = DocxMethodologicalDocumentRenderer()
    export_service = MethodologicalDocumentExportService(
        design_repository=design_repo,
        renderer=renderer,
    )

    reader = ExcelPlanningReader()
    ingestion_service = PlannedActivityIngestionService(reader=reader, uow=uow)

    return PlanningUIService(
        design_service=design_service,
        export_service=export_service,
        ingestion_service=ingestion_service,
    )


class TestPlanningE2ERealPOAToUIList:
    """Demostración E2E del flujo integral: POA Real -> Persistencia -> Módulo 3 -> Diseño -> Word -> R-08."""

    def test_e2e_flujo_completo_poa_real(self, ui_service_e2e: PlanningUIService, tmp_path: Path):
        real_poa = Path("input/matrices_reales_uat/Documento_Kevds_2.xlsx")
        if not real_poa.is_file():
            pytest.skip(f"Archivo POA real '{real_poa}' no disponible en el entorno.")

        # 1. Base limpia: Módulo 3 inicia con 0 actividades
        actividades_iniciales = ui_service_e2e.list_activities()
        assert len(actividades_iniciales) == 0, (
            "El Módulo 3 debe iniciar con 0 actividades registradas en la base limpia"
        )

        # 2. Ingestión de la matriz institucional POA real mediante la Fachada UI
        report = ui_service_e2e.ingest_planning_matrix(
            file_path=str(real_poa),
            default_area_responsable="Dirección de Innovación y Emprendimiento",
            default_eje_estrategia="EJE_11",
            default_programa="PGM_07",
            default_tipo_evento="EVT_CAPACITACION",
        )

        # 3. Comprobación del reporte pericial de ingestión
        assert len(report.errors) == 0, f"No deben existir errores estructurales: {report.errors}"
        assert report.total_rows_examined >= 1
        assert report.rows_accepted >= 1
        assert len(report.created_activity_ids) >= 1
        act_id = report.created_activity_ids[0]

        # 4. Actualización del listado del Módulo 3: actividades reales visibles
        actividades_cargadas = ui_service_e2e.list_activities()
        assert len(actividades_cargadas) >= 1
        act_summary = next((a for a in actividades_cargadas if a.planning_id == act_id), None)
        assert act_summary is not None
        assert "logotipos" in act_summary.activity_name.lower() or "inteligencia artificial" in act_summary.activity_name.lower()
        assert act_summary.sede == "Bilwi"
        assert act_summary.design_status == "SIN_DISENO"
        assert act_summary.total_participants > 0

        # 5. Abrir Ficha de Detalle de la actividad
        detail = ui_service_e2e.get_activity_detail(act_id)
        assert detail is not None
        assert detail.planning_id == act_id
        assert detail.sede == "Bilwi"
        assert detail.dep_sede == "RACCN"
        assert detail.mun_sede == "Puerto Cabezas"
        assert detail.participant_goals.est_grado_m == 6
        assert detail.participant_goals.est_grado_f == 11
        assert detail.design_status == "SIN_DISENO"

        # 6. Crear borrador DRAFT de Diseño Metodológico
        draft = ui_service_e2e.create_design_draft(
            activity_ref=act_id,
            created_by="Responsable UAT Institucional",
        )
        assert draft.design_id is not None
        assert draft.created_by == "Responsable UAT Institucional"

        # 7. Completar los 5 bloques del Diseño Metodológico
        agenda = (
            TimeBlockDTO(sequence=1, label="I. Inauguración y Encuadre Metodológico", minutes=30),
            TimeBlockDTO(sequence=2, label="II. Taller Práctico de Diseño y Asistencia IA", minutes=90),
        )
        matrix = (
            OperationalActivityDTO(
                step_number=1,
                phase_label="Inauguración",
                operative_goal="Presentar los objetivos y metodología del taller",
                procedure="Exposición magistral y bienvenida institucional",
                materials="Proyector multimedia, diapositivas institucionales",
                minutes=30,
            ),
            OperationalActivityDTO(
                step_number=2,
                phase_label="Taller Práctico",
                operative_goal="Desarrollar bocetos y logotipos asistidos con IA",
                procedure="Trabajo individual y en parejas en laboratorio de cómputo",
                materials="Computadoras, software gráfico, conexión a internet",
                minutes=90,
            ),
        )
        faq = FAQTableDTO(
            q1_que_es=draft.faq.q1_que_es if draft.faq else "Taller Institucional",
            q2_para_que="Fortalecer competencias de diseño e innovación estudiantil",
            q3_sesiones="Sesión única presencial",
            q4_protagonistas=draft.faq.q4_protagonistas if draft.faq else "18 protagonistas",
            q5_facilitador="Dirección de Innovación y Emprendimiento",
            q6_materiales="Laboratorio de cómputo y herramientas de diseño",
            q7_duracion="120 minutos (2 horas académicas)",
        )
        cmd_update = UpdateMethodologicalDesignCommand(
            design_id=draft.design_id,
            introduction_text="El presente diseño metodológico orienta el desarrollo formativo...",
            methodological_approach="Metodología basada en talleres prácticos participativos.",
            objectives=(
                "Conocer los principios del diseño de identidad visual y logotipos.",
                "Aplicar herramientas de asistencia digital e IA en la creación de propuestas.",
            ),
            faq=faq,
            agenda=agenda,
            operational_matrix=matrix,
        )
        updated_design = ui_service_e2e.update_design_draft(cmd_update)
        assert updated_design.total_minutes == 120

        # 8. Validación Institucional
        val_report = ui_service_e2e.validate_design(draft.design_id)
        assert val_report.is_valid, f"El diseño debe ser válido: {val_report.errors}"
        assert len(val_report.errors) == 0

        # 9. Aprobación Formal Institucional (sellado R-08)
        approved = ui_service_e2e.approve_design(
            design_id=draft.design_id,
            approved_by="Dra. Secretaria General — BICU",
        )
        assert approved.approved_by == "Dra. Secretaria General — BICU"

        # Verificar que el listado visual ahora reporta el estado 'APPROVED'
        actividades_post_aprobacion = ui_service_e2e.list_activities()
        act_aprobada = next(a for a in actividades_post_aprobacion if a.planning_id == act_id)
        assert act_aprobada.design_status == "APPROVED"

        # 10. Generación y exportación del documento Word (.docx) oficial
        out_docx = tmp_path / f"Diseno_Metodologico_{act_id}.docx"
        exported_path = ui_service_e2e.export_docx(draft.design_id, out_docx)
        assert Path(exported_path).exists()
        assert Path(exported_path).stat().st_size > 1000

        # 11. Reimportación de la misma fuente POA (Demostración estricta de la regla R-08)
        report_reimport = ui_service_e2e.ingest_planning_matrix(
            file_path=str(real_poa),
            default_area_responsable="Dirección de Innovación y Emprendimiento",
            default_eje_estrategia="EJE_11",
            default_programa="PGM_07",
            default_tipo_evento="EVT_CAPACITACION",
        )
        assert report_reimport.rows_accepted >= 1
        assert any(
            "APPROVED" in d and "inmutable R-08" in d
            for d in report_reimport.duplicates_detected
        ), "Debe detectarse y respetarse la inmutabilidad R-08 de la actividad aprobada"

        # Comprobar que la actividad en la base de datos sigue enlazada a su diseño aprobado intacto
        detail_reimport = ui_service_e2e.get_activity_detail(act_id)
        assert detail_reimport is not None
        assert detail_reimport.design_status == "APPROVED"
        assert detail_reimport.design_id == draft.design_id
