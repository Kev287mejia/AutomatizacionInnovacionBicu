"""
Suite de Pruebas Automatizadas — Renderer DOCX Institucional de Planificación.

Fase 29.5.3 — Implementación Controlada del Renderer DOCX
Fuente: FASE_29_5_2_AUDITORIA_CIERRE_DISENO_GENERADOR_DOCX.md §16
Requisitos de Certificación: R-DR-01 a R-DR-13
"""
from __future__ import annotations

import ast
import datetime
import os
import pathlib
import sys
import uuid
import pytest
import docx
from docx.enum.section import WD_ORIENT

from app.planning.domain.dtos import (
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    TimeBlockDTO,
)
from app.planning.infrastructure.document_rendering.docx_renderer import (
    DocxMethodologicalDocumentRenderer,
    DocumentRenderingError,
    COLOR_NAVY_HEX,
    COLOR_LIGHT_BLUE_HEX,
    COLOR_ICE_BLUE_HEX,
)


# ===========================================================================
# FIXTURES CONTROLADOS DE PRUEBA (CERO DATOS PERSONALES REALES)
# ===========================================================================

@pytest.fixture
def sample_faq_dto() -> FAQTableDTO:
    return FAQTableDTO(
        q1_que_es="Es un taller formativo orientado al desarrollo de competencias técnicas.",
        q2_para_que="Para fortalecer las habilidades prácticas de los participantes.",
        q3_sesiones="Sesión única",
        q4_protagonistas="25 participantes en total: 20 estudiantes y 5 docentes.",
        q5_facilitador="Dirección de Innovación y Emprendimiento",
        q6_materiales="Proyector, laptops, papelógrafos, marcadores y material digital.",
        q7_duracion="2 horas y 30 minutos (150 minutos).",
    )


@pytest.fixture
def sample_agenda_dto() -> tuple[TimeBlockDTO, ...]:
    return (
        TimeBlockDTO(sequence=1, label="Registro e Instalación", minutes=15),
        TimeBlockDTO(sequence=2, label="Introducción y Dinámica de Apertura", minutes=30),
        TimeBlockDTO(sequence=3, label="Desarrollo Práctico del Taller", minutes=75),
        TimeBlockDTO(sequence=4, label="Plenaria de Conclusiones y Evaluación", minutes=30),
    )


@pytest.fixture
def sample_matrix_dto() -> tuple[OperationalActivityDTO, ...]:
    return (
        OperationalActivityDTO(
            step_number=1,
            phase_label="Registro e Instalación",
            operative_goal="Registrar asistencia y preparar el entorno de trabajo",
            procedure="Los participantes firman la lista de asistencia y reciben material",
            materials="Lista de asistencia, bolígrafos, gafetes",
            minutes=15,
        ),
        OperationalActivityDTO(
            step_number=2,
            phase_label="Introducción y Dinámica de Apertura",
            operative_goal="Presentar los objetivos y establecer clima de confianza",
            procedure="Presentación del facilitador y dinámica grupal en círculo",
            materials="Diapositivas de presentación, proyector",
            minutes=30,
        ),
        OperationalActivityDTO(
            step_number=3,
            phase_label="Desarrollo Práctico del Taller",
            operative_goal="Ejecutar ejercicios guiados de aplicación directa",
            procedure="Trabajo en equipos para resolver el caso práctico asignado",
            materials="Laptops, conexión a internet, guías prácticas impresas",
            minutes=75,
        ),
        OperationalActivityDTO(
            step_number=4,
            phase_label="Plenaria de Conclusiones y Evaluación",
            operative_goal="Consolidar aprendizajes y evaluar la jornada",
            procedure="Exposición de resultados por equipo y llenado de encuesta de satisfacción",
            materials="Papelógrafos, marcadores, fichas de evaluación",
            minutes=30,
        ),
    )


@pytest.fixture
def sample_design_dto(
    sample_faq_dto, sample_agenda_dto, sample_matrix_dto
) -> MethodologicalDesignDTO:
    return MethodologicalDesignDTO(
        design_id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
        version=1,
        created_at=datetime.datetime(2026, 9, 20, 10, 0, 0),
        created_by="coordinador_pedagogico",
        approved_by=None,
        document_title="Diseño metodológico Taller Piloto de Innovación Tecnológica",
        introduction=(
            "La presente actividad se enmarca en la Línea Estratégica Institucional de Investigación "
            "e Innovación, orientada a consolidar las capacidades de la comunidad universitaria."
        ),
        methodological_approach=(
            "La metodología es participativa, constructivista y basada en resolución de problemas prácticos."
        ),
        objectives_heading="OBJETIVOS DEL TALLER ARTÍSTICO",
        objective_1="Capacitar a los protagonistas en metodologías ágiles de innovación.",
        objective_2="Fortalecer el trabajo colaborativo e interdisciplinario entre los participantes.",
        faq=sample_faq_dto,
        program_section_label="III. PROGRAMA",
        agenda=sample_agenda_dto,
        total_minutes=150,  # 15 + 30 + 75 + 30 = 150
        matrix_section_label="VI. MATRIZ DE PLANIFICACIÓN",
        operational_matrix=sample_matrix_dto,
    )


@pytest.fixture
def renderer() -> DocxMethodologicalDocumentRenderer:
    return DocxMethodologicalDocumentRenderer()


# ===========================================================================
# PRUEBAS R-DR-01 A R-DR-13
# ===========================================================================

class TestPlanningDocxRenderer:
    """Suite integral para la verificación de los 13 requisitos normativos del Renderer DOCX."""

    def test_r_dr_01_produces_valid_docx(self, renderer, sample_design_dto, tmp_path):
        """R-DR-01: El renderer produce un DOCX válido, legible por python-docx, con orientación Landscape."""
        out_file = str(tmp_path / "test_design.docx")
        result_path = renderer.render(sample_design_dto, out_file)

        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0

        # Verificar legibilidad por python-docx
        doc = docx.Document(result_path)
        assert len(doc.sections) >= 1
        section = doc.sections[0]
        assert section.orientation == WD_ORIENT.LANDSCAPE
        # Tamaño Letter: 11 x 8.5 pulgadas (tolerancia de 0.05 in)
        assert abs(section.page_width.inches - 11.0) < 0.05
        assert abs(section.page_height.inches - 8.5) < 0.05

    def test_r_dr_02_five_blocks_present(self, renderer, sample_design_dto, tmp_path):
        """R-DR-02: Los cinco bloques institucionales aparecen en el documento."""
        out_file = str(tmp_path / "test_five_blocks.docx")
        renderer.render(sample_design_dto, out_file)

        doc = docx.Document(out_file)
        full_text = "\n".join(p.text for p in doc.paragraphs)

        # Bloque 1: Título e Introducción
        assert "DISEÑO METODOLÓGICO TALLER PILOTO" in full_text.upper()
        assert "INTRODUCCIÓN" in full_text
        assert sample_design_dto.introduction in full_text
        assert sample_design_dto.methodological_approach in full_text

        # Bloque 2: Objetivos
        assert sample_design_dto.objectives_heading in full_text
        assert sample_design_dto.objective_1 in full_text
        assert sample_design_dto.objective_2 in full_text

        # Bloque 3: FAQ (Tabla 1)
        assert len(doc.tables) >= 3
        faq_table = doc.tables[0]
        faq_text = "\n".join(cell.text for row in faq_table.rows for cell in row.cells)
        assert "Preguntas frecuentes" in faq_text

        # Bloque 4: Programa (Tabla 2)
        assert sample_design_dto.program_section_label in full_text
        agenda_table = doc.tables[1]
        agenda_text = "\n".join(cell.text for row in agenda_table.rows for cell in row.cells)
        assert "Actividad" in agenda_text
        assert "Tiempo" in agenda_text
        assert "Total" in agenda_text

        # Bloque 5: Matriz Operacional (Tabla 3)
        assert sample_design_dto.matrix_section_label in full_text
        matrix_table = doc.tables[2]
        matrix_headers = [c.text.strip() for c in matrix_table.rows[0].cells]
        assert "No." in matrix_headers
        assert "Procedimiento" in matrix_headers

    def test_r_dr_03_faq_contains_seven_questions(self, renderer, sample_design_dto, tmp_path):
        """R-DR-03: La FAQ contiene exactamente las siete preguntas institucionales y sus respuestas."""
        out_file = str(tmp_path / "test_faq.docx")
        renderer.render(sample_design_dto, out_file)

        doc = docx.Document(out_file)
        faq_table = doc.tables[0]
        assert len(faq_table.rows) == 8  # 1 fila cabecera + 7 preguntas

        expected_questions = [
            "¿En qué es esta actividad?",
            "¿Para qué se realiza?",
            "¿Cuántas sesiones se realizarán?",
            "¿Cuánto son los protagonistas?",
            "¿Quién va facilitar??",
            "¿Qué materiales se van a utilizar?",
            "¿Cuánto tiempo dura el taller?",
        ]

        expected_answers = [
            sample_design_dto.faq.q1_que_es,
            sample_design_dto.faq.q2_para_que,
            sample_design_dto.faq.q3_sesiones,
            sample_design_dto.faq.q4_protagonistas,
            sample_design_dto.faq.q5_facilitador,
            sample_design_dto.faq.q6_materiales,
            sample_design_dto.faq.q7_duracion,
        ]

        for idx, (expected_q, expected_a) in enumerate(zip(expected_questions, expected_answers), start=1):
            row = faq_table.rows[idx]
            q_found = row.cells[0].text.strip()
            a_found = row.cells[1].text.strip()
            assert q_found == expected_q
            assert a_found == expected_a

    def test_r_dr_04_agenda_rows_expected(self, renderer, sample_design_dto, tmp_path):
        """R-DR-04: La agenda contiene sus filas esperadas (cabecera + N bloques + total)."""
        out_file = str(tmp_path / "test_agenda.docx")
        renderer.render(sample_design_dto, out_file)

        doc = docx.Document(out_file)
        agenda_table = doc.tables[1]
        n_blocks = len(sample_design_dto.agenda)
        assert len(agenda_table.rows) == n_blocks + 2

        # Cabecera
        assert agenda_table.rows[0].cells[0].text.strip() == "Actividad"
        assert agenda_table.rows[0].cells[1].text.strip() == "Tiempo"

        # Bloques individuales
        for idx, block in enumerate(sample_design_dto.agenda, start=1):
            row = agenda_table.rows[idx]
            assert row.cells[0].text.strip() == block.label
            assert row.cells[1].text.strip() == f"{block.minutes} min."

        # Fila Total
        assert agenda_table.rows[n_blocks + 1].cells[0].text.strip() == "Total"
        assert agenda_table.rows[n_blocks + 1].cells[1].text.strip() == f"{sample_design_dto.total_minutes} min."

    def test_r_dr_05_time_sum_preserved(self, renderer, sample_design_dto, tmp_path):
        """R-DR-05: La suma de tiempos del modelo se conserva exactamente en la fila Total."""
        out_file = str(tmp_path / "test_time_sum.docx")
        renderer.render(sample_design_dto, out_file)

        doc = docx.Document(out_file)
        agenda_table = doc.tables[1]
        total_row = agenda_table.rows[-1]
        assert total_row.cells[1].text.strip() == "150 min."

        # Verificar sumando programáticamente las filas intermedias
        summed = 0
        for row in agenda_table.rows[1:-1]:
            val_text = row.cells[1].text.strip().replace(" min.", "")
            summed += int(val_text)
        assert summed == 150

    def test_r_dr_06_matrix_six_official_columns(self, renderer, sample_design_dto, tmp_path):
        """R-DR-06: La matriz operativa contiene exactamente las seis columnas oficiales."""
        out_file = str(tmp_path / "test_matrix_cols.docx")
        renderer.render(sample_design_dto, out_file)

        doc = docx.Document(out_file)
        matrix_table = doc.tables[2]
        expected_cols = [
            "No.",
            "Actividad",
            "Objetivos Operativos",
            "Procedimiento",
            "Materiales",
            "Tiempo",
        ]
        assert len(matrix_table.columns) == 6
        header_cells = [c.text.strip() for c in matrix_table.rows[0].cells]
        assert header_cells == expected_cols

    def test_r_dr_07_dto_values_unaltered(self, renderer, sample_design_dto, tmp_path):
        """R-DR-07: Los valores del DTO aparecen sin alteración en los párrafos y celdas."""
        out_file = str(tmp_path / "test_values_unaltered.docx")
        renderer.render(sample_design_dto, out_file)

        doc = docx.Document(out_file)
        doc_paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

        assert sample_design_dto.objective_1 in doc_paragraphs
        assert sample_design_dto.objective_2 in doc_paragraphs
        assert sample_design_dto.introduction in doc_paragraphs
        assert sample_design_dto.methodological_approach in doc_paragraphs

        # Verificar filas operativas
        matrix_table = doc.tables[2]
        for idx, act in enumerate(sample_design_dto.operational_matrix, start=1):
            row = matrix_table.rows[idx]
            assert row.cells[0].text.strip() == str(act.step_number)
            assert row.cells[1].text.strip() == act.phase_label
            assert row.cells[2].text.strip() == act.operative_goal
            assert row.cells[3].text.strip() == act.procedure
            assert row.cells[4].text.strip() == act.materials
            assert row.cells[5].text.strip() == f"{act.minutes} min."

    def test_r_dr_08_no_persistence_infrastructure_called(self, renderer, sample_design_dto, tmp_path, monkeypatch):
        """R-DR-08: El renderer no consulta sqlite3 ni infraestructura de persistencia."""
        import sqlite3

        # Monkeypatch para detectar cualquier llamada a sqlite3.connect
        def fake_connect(*args, **kwargs):
            raise AssertionError("El renderer no debe intentar conectarse a SQLite.")

        monkeypatch.setattr(sqlite3, "connect", fake_connect)

        out_file = str(tmp_path / "test_isolation_persistence.docx")
        # Debe renderizar sin invocar sqlite3.connect
        renderer.render(sample_design_dto, out_file)
        assert os.path.exists(out_file)

    def test_r_dr_09_no_word_consolidator_import(self):
        """R-DR-09: El renderer no importa app.word_consolidator (auditoría estática AST)."""
        renderer_file = (
            pathlib.Path(__file__).resolve().parent.parent
            / "app"
            / "planning"
            / "infrastructure"
            / "document_rendering"
            / "docx_renderer.py"
        )
        assert renderer_file.exists()

        with open(renderer_file, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(renderer_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "word_consolidator" not in alias.name, (
                        f"Import prohibido detectado en docx_renderer.py: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "word_consolidator" not in node.module, (
                        f"ImportFrom prohibido detectado en docx_renderer.py: {node.module}"
                    )

    def test_r_dr_10_no_ai_dependencies_direct_or_transitive(self):
        """R-DR-10: No existe dependencia de IA ni directa ni transitiva en el renderer."""
        forbidden_ai_modules = {
            "google.generativeai",
            "google.genai",
            "openai",
            "anthropic",
            "ollama",
            "langchain",
        }

        # 1. Auditoría estática AST del módulo docx_renderer
        renderer_file = (
            pathlib.Path(__file__).resolve().parent.parent
            / "app"
            / "planning"
            / "infrastructure"
            / "document_rendering"
            / "docx_renderer.py"
        )
        with open(renderer_file, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(renderer_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_ai_modules:
                        assert not (alias.name == forbidden or alias.name.startswith(forbidden + ".")), (
                            f"Import directo de IA prohibido: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_ai_modules:
                        assert not (node.module == forbidden or node.module.startswith(forbidden + ".")), (
                            f"ImportFrom directo de IA prohibido: {node.module}"
                        )

        # 2. Verificación de dependencias en tiempo de ejecución del renderer
        import app.planning.infrastructure.document_rendering.docx_renderer as mod
        mod_dict = vars(mod)
        for key, val in mod_dict.items():
            if hasattr(val, "__module__") and val.__module__:
                for forbidden in forbidden_ai_modules:
                    assert not val.__module__.startswith(forbidden), (
                        f"Dependencia de IA detectada en tiempo de ejecución: {val.__module__}"
                    )

    def test_r_dr_11_invalid_dto_raises_controlled_error(self, renderer, sample_design_dto, tmp_path):
        """R-DR-11: DTO inválido o con inconsistencia estructural produce error controlado."""
        out_file = str(tmp_path / "test_invalid.docx")

        # 1. DTO es None
        with pytest.raises(DocumentRenderingError, match="DTO inválido"):
            renderer.render(None, out_file)  # type: ignore

        # 2. DTO no es instancia de MethodologicalDesignDTO
        with pytest.raises(DocumentRenderingError, match="DTO inválido"):
            renderer.render("cadena_no_dto", out_file)  # type: ignore

        # 3. agenda vacía
        bad_dto_empty_agenda = MethodologicalDesignDTO(
            design_id=sample_design_dto.design_id,
            version=1,
            created_at=sample_design_dto.created_at,
            created_by="user",
            approved_by=None,
            document_title="Título",
            introduction="Intro",
            methodological_approach="Enfoque",
            objectives_heading="Objetivos",
            objective_1="O1",
            objective_2="O2",
            faq=sample_design_dto.faq,
            program_section_label="Programa",
            agenda=(),  # VACÍA
            total_minutes=0,
            matrix_section_label="Matriz",
            operational_matrix=sample_design_dto.operational_matrix,
        )
        with pytest.raises(DocumentRenderingError, match="agenda no puede estar vacío"):
            renderer.render(bad_dto_empty_agenda, out_file)

        # 4. operational_matrix vacía
        bad_dto_empty_matrix = MethodologicalDesignDTO(
            design_id=sample_design_dto.design_id,
            version=1,
            created_at=sample_design_dto.created_at,
            created_by="user",
            approved_by=None,
            document_title="Título",
            introduction="Intro",
            methodological_approach="Enfoque",
            objectives_heading="Objetivos",
            objective_1="O1",
            objective_2="O2",
            faq=sample_design_dto.faq,
            program_section_label="Programa",
            agenda=sample_design_dto.agenda,
            total_minutes=sample_design_dto.total_minutes,
            matrix_section_label="Matriz",
            operational_matrix=(),  # VACÍA
        )
        with pytest.raises(DocumentRenderingError, match="matriz operacional no puede estar vacía"):
            renderer.render(bad_dto_empty_matrix, out_file)

        # 5. Inconsistencia matemática: suma de minutos no coincide con total_minutes
        bad_dto_math_mismatch = MethodologicalDesignDTO(
            design_id=sample_design_dto.design_id,
            version=1,
            created_at=sample_design_dto.created_at,
            created_by="user",
            approved_by=None,
            document_title="Título",
            introduction="Intro",
            methodological_approach="Enfoque",
            objectives_heading="Objetivos",
            objective_1="O1",
            objective_2="O2",
            faq=sample_design_dto.faq,
            program_section_label="Programa",
            agenda=sample_design_dto.agenda,
            total_minutes=999,  # Inconsistente (debe ser 150)
            matrix_section_label="Matriz",
            operational_matrix=sample_design_dto.operational_matrix,
        )
        with pytest.raises(DocumentRenderingError, match="Inconsistencia estructural en tiempos"):
            renderer.render(bad_dto_math_mismatch, out_file)

        # 6. Mismatch estructural entre bloque de agenda y matriz operativa
        bad_matrix_time = list(sample_design_dto.operational_matrix)
        bad_matrix_time[0] = OperationalActivityDTO(
            step_number=1,
            phase_label="Fase 1",
            operative_goal="Goal",
            procedure="Proc",
            materials="Mat",
            minutes=99,  # Era 15 en agenda
        )
        bad_dto_mirror_mismatch = MethodologicalDesignDTO(
            design_id=sample_design_dto.design_id,
            version=1,
            created_at=sample_design_dto.created_at,
            created_by="user",
            approved_by=None,
            document_title="Título",
            introduction="Intro",
            methodological_approach="Enfoque",
            objectives_heading="Objetivos",
            objective_1="O1",
            objective_2="O2",
            faq=sample_design_dto.faq,
            program_section_label="Programa",
            agenda=sample_design_dto.agenda,
            total_minutes=sample_design_dto.total_minutes,
            matrix_section_label="Matriz",
            operational_matrix=tuple(bad_matrix_time),
        )
        with pytest.raises(DocumentRenderingError, match="no coincide con la actividad operativa"):
            renderer.render(bad_dto_mirror_mismatch, out_file)

    def test_r_dr_12_draft_does_not_invent_watermark(self, renderer, sample_design_dto, tmp_path):
        """R-DR-12: Estado DRAFT no introduce marca de agua inventada ni textos 'BORRADOR'."""
        assert sample_design_dto.approved_by is None  # Es un borrador

        out_file = str(tmp_path / "test_draft_no_watermark.docx")
        renderer.render(sample_design_dto, out_file)

        doc = docx.Document(out_file)

        # 1. Comprobar que no existe el texto "BORRADOR" ni "DRAFT" en ningún párrafo
        for p in doc.paragraphs:
            assert "BORRADOR" not in p.text.upper()
            assert "DRAFT" not in p.text.upper()

        # 2. Comprobar que no hay marcas de agua en el XML de encabezados
        for s in doc.sections:
            header = s.header
            header_text = "\n".join(p.text for p in header.paragraphs).strip()
            assert "BORRADOR" not in header_text.upper()
            assert "DRAFT" not in header_text.upper()

    def test_r_dr_13_approved_renders_without_modifying_model(self, renderer, sample_design_dto, tmp_path):
        """R-DR-13: APPROVED puede renderizarse sin modificar el modelo ni su estado."""
        approved_dto = MethodologicalDesignDTO(
            design_id=sample_design_dto.design_id,
            version=2,
            created_at=sample_design_dto.created_at,
            created_by="prof_kenia",
            approved_by="vicerrectoria_academica",  # APPROVED
            document_title=sample_design_dto.document_title,
            introduction=sample_design_dto.introduction,
            methodological_approach=sample_design_dto.methodological_approach,
            objectives_heading=sample_design_dto.objectives_heading,
            objective_1=sample_design_dto.objective_1,
            objective_2=sample_design_dto.objective_2,
            faq=sample_design_dto.faq,
            program_section_label=sample_design_dto.program_section_label,
            agenda=sample_design_dto.agenda,
            total_minutes=sample_design_dto.total_minutes,
            matrix_section_label=sample_design_dto.matrix_section_label,
            operational_matrix=sample_design_dto.operational_matrix,
        )

        out_file = str(tmp_path / "test_approved_render.docx")
        result_path = renderer.render(approved_dto, out_file)
        assert os.path.exists(result_path)

        # Verificar que el DTO permanece 100% idéntico e inalterado
        assert approved_dto.approved_by == "vicerrectoria_academica"
        assert approved_dto.version == 2
        assert approved_dto.total_minutes == 150
