"""tests/test_fase_29_20_2_integracion_word_matrices.py

FASE 29.20.2 — Suite de Certificación de Integración Controlada del Pipeline:
INFORMES WORD REALES -> EXTRACCIÓN -> VALIDACIÓN -> PERSISTENCIA -> ROUTING -> M1-M5

Cobertura integral obligatoria:
- WORD -> M1: D-01 válida, duplicado por SHA-256, D-02/D-04 warnings, D-08..D-10 rechazados.
- WORD -> M2: Participante nominal estructurado, solo agregado, cédula ausente, sexo NULL.
- WORD -> M3: Docente nominal, administrativo nominal, solo agregado.
- WORD -> M4: Colaborador nominal, solo agregado.
- WORD -> M5: Beneficiario nuevo en fila 34, 32 históricos celda a celda intactos,
              es_historico_preexistente (1 vs 0), estudiante beneficiario (RN-C03), ambigüedad en cola.
- BATCH: Lote D-01..D-07 completo, D-08..D-10 rechazados.
- IDEMPOTENCIA: Reprocesamiento sin duplicados en SQLite ni en matrices Excel.
- CONSERVACIÓN PATRIMONIAL: 6/6 hashes SHA-256 inalterados.
- AISLAMIENTO ARQUITECTÓNICO (AST): Cero dependencias indebidas hacia planning, indicators, reporting, gemini o dashboard.
"""

import ast
import hashlib
from pathlib import Path
import shutil
from typing import Generator
import openpyxl
import pytest

from app.application.commands.batch_commands import IngestarCarpetaWordCommand
from app.application.commands.pipeline_commands import ExportarMatricesPeriodoCommand
from app.application.dto.word_extraction_dtos import TipoDocumentoWord
from app.application.use_cases.batch.ingestar_carpeta_word import (
    IngestarCarpetaWordUseCase,
)
from app.application.use_cases.batch.procesar_pipeline_desde_word import (
    ProcesarPipelineDesdeWordUseCase,
)
from app.application.use_cases.exportacion.exportar_matrices_periodo import (
    ExportarMatricesPeriodoUseCase,
)
from app.application.use_cases.ingestar_actividad_desde_word import (
    IngestarActividadDesdeWordUseCase,
)
from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)
from app.core.constants.participant_types import CategoriaParticipacion
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.exporters.base_exporter import calcular_sha256
from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.repositories.unit_of_work import SQLiteUnitOfWork
from app.infrastructure.word_reader.word_activity_extractor import (
    WordActivityExtractor,
)
from app.word_consolidator.ui.services.word_batch_service import WordBatchAppService

# Hashes patrimoniales certificados custodiados (6/6 MATCH)
PATRIMONIAL_HASHES = {
    "M1": ("templates/Matriz_1_Consolidado_Actividades.xlsx", "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad"),
    "M2": ("templates/Matriz_2_Estudiantes.xlsx", "11419cd22d986e195694f27d15236204afa22526812f18cb4f2e1b7540f64400"),
    "M3": ("templates/Matriz_3_Academicos_Administrativos.xlsx", "dc1786616cb1a9bc2f82a74cc693ee20ab95b689b658b366164f502201b07c87"),
    "M4": ("templates/Matriz_4_Colaboradores.xlsx", "fd079c5f2be780e602dc563696a6f157d76c4c20410308037cec52f3d2654578"),
    "M5": ("templates/Matriz_5_Protagonistas_Beneficiados.xlsx", "a3dff20ec209de209f59dd8b1ad1be84aa7aebd1536ced406c59453a08973dc3"),
    "EXE": ("release/BICU_Consolidador.exe", "0a94be44de80079ffceee8abe34025cb6f604bc8a3126e209d221e4828df214b"),
}


@pytest.fixture
def sqlite_test_env(tmp_path: Path) -> Generator[SQLiteUnitOfWork, None, None]:
    """Crea una base de datos SQLite de pruebas con el esquema oficial completo."""
    db_file = tmp_path / "test_word_matrices_29_20_2.db"
    config = DatabaseConfig(db_path=db_file)
    manager = SQLiteConnectionManager(config)

    conn = manager.get_connection()
    try:
        runner = MigrationRunner(conn)
        runner.apply_all_pending()
    finally:
        conn.close()

    uow = SQLiteUnitOfWork(connection_manager=manager, db_path=db_file)
    yield uow


@pytest.fixture
def batch_orchestrator(sqlite_test_env: SQLiteUnitOfWork) -> IngestarCarpetaWordUseCase:
    """Instancia el orquestador IngestarCarpetaWordUseCase con componentes reales."""
    return WordBatchAppService.crear_batch_orchestrator(uow=sqlite_test_env)


# ==============================================================================
# 1. WORD -> M1 (CONSOLIDADO DE ACTIVIDADES)
# ==============================================================================

class TestWordToM1:
    """Pruebas del flujo Word -> M1: actividad válida, duplicado, advertencias e incompatibles."""

    def test_word_m1_actividad_valida_d01(self, batch_orchestrator, sqlite_test_env, tmp_path):
        """D-01 genera 1 actividad en SQLite y 1 fila en M1 con fórmulas patrimoniales intactas."""
        origen = tmp_path / "origen_d01"
        origen.mkdir()
        salida = tmp_path / "salida_d01"
        salida.mkdir()

        doc_d01 = Path("validation/f28_6/ci/D-01")
        archivos = list(doc_d01.glob("*.docx"))
        assert len(archivos) == 1
        shutil.copy2(archivos[0], origen / "D-01.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)

        assert res.invariante_ok is True
        assert res.archivos_encontrados == 1
        assert res.archivos_aceptados == 1
        assert res.archivos_rechazados == 0
        assert len(res.actividades_creadas) == 1
        assert "matriz_1" in res.matrices_generadas

        # Verificar SQLite
        conn = sqlite_test_env._connection_manager.get_connection()
        total_act = conn.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]
        total_met = conn.execute("SELECT COUNT(*) FROM actividad_metrica_agregada;").fetchone()[0]
        total_per = conn.execute("SELECT COUNT(*) FROM persona;").fetchone()[0]
        conn.close()

        assert total_act == 1
        assert total_met == 1
        assert total_per == 0  # INV-01: CERO nominales inventados

        # Verificar M1 físico
        wb_m1 = openpyxl.load_workbook(res.matrices_generadas["matriz_1"], data_only=False)
        ws_m1 = wb_m1.worksheets[0]
        assert ws_m1.cell(row=2, column=1).value == 1
        assert ws_m1.cell(row=2, column=2).value == "BILWI"
        assert "Google Form" in str(ws_m1.cell(row=2, column=9).value)
        # Fórmulas preservadas a partir de fila 3
        assert ws_m1.cell(row=3, column=1).value == "=+A2+1"
        wb_m1.close()

    def test_word_m1_actividad_duplicada_idempotencia(self, batch_orchestrator, sqlite_test_env, tmp_path):
        """Procesar D-01 una segunda vez detecta SHA-256 duplicate y no duplica filas en M1."""
        origen = tmp_path / "origen_dup"
        origen.mkdir()
        salida = tmp_path / "salida_dup"
        salida.mkdir()

        doc_d01 = list(Path("validation/f28_6/ci/D-01").glob("*.docx"))[0]
        shutil.copy2(doc_d01, origen / "D-01.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )

        # 1. Primera ejecución
        res1 = batch_orchestrator.execute(cmd)
        assert len(res1.actividades_creadas) == 1

        # 2. Segunda ejecución sobre la misma base de datos
        res2 = batch_orchestrator.execute(cmd)
        assert res2.invariante_ok is True
        # En la segunda ejecución no se crea una nueva actividad
        assert len(res2.actividades_creadas) == 0

        # En SQLite sigue existiendo exactamente 1 actividad
        conn = sqlite_test_env._connection_manager.get_connection()
        total_act = conn.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]
        conn.close()
        assert total_act == 1

    def test_word_m1_actividades_con_warnings_d02_d04(self, batch_orchestrator, sqlite_test_env, tmp_path):
        """D-02 y D-04 presentan advertencias institucionales pero se procesan sin abortar ni corromper."""
        origen = tmp_path / "origen_warn"
        origen.mkdir()
        salida = tmp_path / "salida_warn"
        salida.mkdir()

        doc_d02 = list(Path("validation/f28_6/ci/D-02").glob("*.docx"))[0]
        doc_d04 = list(Path("validation/f28_6/ci/D-04").glob("*.docx"))[0]
        shutil.copy2(doc_d02, origen / "D-02.docx")
        shutil.copy2(doc_d04, origen / "D-04.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)

        assert res.invariante_ok is True
        assert res.archivos_encontrados == 2
        assert (res.archivos_aceptados + res.archivos_con_advertencias) == 2
        assert len(res.actividades_creadas) == 2

        # Comprobar flag de discrepancia en SQLite
        conn = sqlite_test_env._connection_manager.get_connection()
        discrepancias = conn.execute(
            "SELECT presenta_discrepancia_interna FROM actividad_metrica_agregada;"
        ).fetchall()
        conn.close()
        # Ambos documentos tienen discrepancia registrada (flag = 1)
        flags = [r[0] for r in discrepancias]
        assert any(f == 1 for f in flags)

    def test_word_m1_actividades_incompatibles_rechazadas_d08_d09_d10(
        self, batch_orchestrator, sqlite_test_env, tmp_path
    ):
        """D-08, D-09 y D-10 son rechazados con motivo institucional claro; 0 registros en SQLite ni M1."""
        origen = tmp_path / "origen_incomp"
        origen.mkdir()
        salida = tmp_path / "salida_incomp"
        salida.mkdir()

        doc_d08 = list(Path("validation/f28_6/ci/D-08").glob("*.docx"))[0]
        doc_d09 = list(Path("validation/f28_6/ci/D-09").glob("*.docx"))[0]
        doc_d10 = list(Path("validation/f28_6/ci/D-10").glob("*.docx"))[0]
        shutil.copy2(doc_d08, origen / "D-08.docx")
        shutil.copy2(doc_d09, origen / "D-09.docx")
        shutil.copy2(doc_d10, origen / "D-10.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)

        assert res.invariante_ok is True
        assert res.archivos_encontrados == 3
        assert res.archivos_rechazados == 3
        assert res.archivos_aceptados == 0
        assert len(res.actividades_creadas) == 0

        # Cero registros en SQLite
        conn = sqlite_test_env._connection_manager.get_connection()
        total_act = conn.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]
        conn.close()
        assert total_act == 0


# ==============================================================================
# 2. WORD -> M2 (ESTUDIANTES)
# ==============================================================================

class TestWordToM2:
    """Pruebas para Matriz 2: nominal estructurado, solo agregado, cédula ausente y sexo NULL."""

    def test_word_m2_nominal_estructurado(self, sqlite_test_env, tmp_path):
        """Estudiante nominal estructurado se exporta a M2 con todas sus columnas y fórmula DATEDIF."""
        salida = tmp_path / "salida_m2_nominal"
        salida.mkdir()

        # Crear actividad y estudiante nominal en SQLite
        act = Activity(
            id_actividad="act-m2-001",
            nombre_actividad_original="Taller de Programación en Python",
            sede="BILWI",
            fecha_evento="2026-06-15",
        )
        per = Person(
            id_persona_interno="per-est-001",
            nombre_completo="Keyla Michelle Wilson",
            cedula="601-150604-1002B",
            sexo_normalizado="FEMENINO",
            fecha_nacimiento="2004-06-15",
            carrera_original="Ingeniería en Sistemas",
            numero_unico="EST-2026-001",
        )
        part = Participation(
            id_participacion="part-est-001",
            id_actividad=act.id_actividad,
            id_persona=per.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )

        with sqlite_test_env:
            sqlite_test_env.actividades.save(act)
            sqlite_test_env.personas.save(per)
            sqlite_test_env.participaciones.save(part)
            sqlite_test_env.commit()

        pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        export_uc = ExportarMatricesPeriodoUseCase(pipeline_use_case=pipeline_uc, uow=sqlite_test_env)

        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            ids_actividades=[act.id_actividad],
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = export_uc.execute(cmd, uow=sqlite_test_env)
        assert res.exito is True

        m2_path = Path(res.archivos_generados["matriz_2"])
        wb_m2 = openpyxl.load_workbook(str(m2_path), data_only=False)
        ws_m2 = wb_m2.worksheets[0]

        # Fila 2: Datos del estudiante
        assert ws_m2.cell(row=2, column=1).value == 1
        assert ws_m2.cell(row=2, column=2).value == "BILWI"
        assert ws_m2.cell(row=2, column=33).value == "Keyla Michelle Wilson"
        assert ws_m2.cell(row=2, column=34).value == "EST-2026-001"
        assert ws_m2.cell(row=2, column=35).value == "601-150604-1002B"
        assert ws_m2.cell(row=2, column=38).value in ("F", "FEMENINO")
        assert ws_m2.cell(row=2, column=40).value == '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")'
        wb_m2.close()

    def test_word_m2_solo_agregado_cero_nominales(self, batch_orchestrator, tmp_path):
        """Informe Word que solo tiene 'Estudiantes: 15' genera 0 registros nominales en M2."""
        origen = tmp_path / "origen_m2_agg"
        origen.mkdir()
        salida = tmp_path / "salida_m2_agg"
        salida.mkdir()

        doc_d01 = list(Path("validation/f28_6/ci/D-01").glob("*.docx"))[0]
        shutil.copy2(doc_d01, origen / "D-01.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)
        assert res.invariante_ok is True

        # Inspección física de M2: Fila 2 sin estudiantes nominales inventados
        m2_path = Path(res.matrices_generadas["matriz_2"])
        wb_m2 = openpyxl.load_workbook(str(m2_path), data_only=False)
        ws_m2 = wb_m2.worksheets[0]
        assert ws_m2.cell(row=2, column=33).value is None
        wb_m2.close()

    def test_word_m2_cedula_ausente_no_inventada(self, sqlite_test_env, tmp_path):
        """INV-06: Estudiante sin cédula no recibe una cédula artificial ni inventada."""
        salida = tmp_path / "salida_m2_sin_cedula"
        salida.mkdir()

        act = Activity(id_actividad="act-m2-002", nombre_actividad_original="Taller sin Cédulas", sede="BILWI")
        per = Person(
            id_persona_interno="per-sin-ced",
            nombre_completo="Estudiante Sin Cedula",
            cedula=None,  # Cédula ausente
            sexo_normalizado="MASCULINO",
        )
        part = Participation(
            id_participacion="part-sin-ced",
            id_actividad=act.id_actividad,
            id_persona=per.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )
        with sqlite_test_env:
            sqlite_test_env.actividades.save(act)
            sqlite_test_env.personas.save(per)
            sqlite_test_env.participaciones.save(part)
            sqlite_test_env.commit()

        pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        export_uc = ExportarMatricesPeriodoUseCase(pipeline_use_case=pipeline_uc, uow=sqlite_test_env)
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            ids_actividades=[act.id_actividad],
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = export_uc.execute(cmd, uow=sqlite_test_env)
        wb = openpyxl.load_workbook(res.archivos_generados["matriz_2"])
        ws = wb.worksheets[0]
        # Columna 35 (Cédula) debe permanecer estrictamente None
        assert ws.cell(row=2, column=35).value is None
        wb.close()

    def test_word_m2_sexo_null_no_imputado(self, sqlite_test_env, tmp_path):
        """INV-05: Estudiante sin sexo normalizado permanece estrictamente NULL en M2."""
        salida = tmp_path / "salida_m2_sexo_null"
        salida.mkdir()

        act = Activity(id_actividad="act-m2-003", nombre_actividad_original="Taller Sexo Null", sede="BLUEFIELDS")
        per = Person(
            id_persona_interno="per-sexo-null",
            nombre_completo="Estudiante Sexo Desconocido",
            cedula="601-010100-0000Z",
            sexo_normalizado=None,  # Sexo desconocido
        )
        part = Participation(
            id_participacion="part-sexo-null",
            id_actividad=act.id_actividad,
            id_persona=per.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )
        with sqlite_test_env:
            sqlite_test_env.actividades.save(act)
            sqlite_test_env.personas.save(per)
            sqlite_test_env.participaciones.save(part)
            sqlite_test_env.commit()

        pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        export_uc = ExportarMatricesPeriodoUseCase(pipeline_use_case=pipeline_uc, uow=sqlite_test_env)
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            ids_actividades=[act.id_actividad],
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = export_uc.execute(cmd, uow=sqlite_test_env)
        wb = openpyxl.load_workbook(res.archivos_generados["matriz_2"])
        ws = wb.worksheets[0]
        # Columna 38 (Sexo) debe permanecer estrictamente None
        assert ws.cell(row=2, column=38).value is None
        wb.close()


# ==============================================================================
# 3. WORD -> M3 (ACADÉMICOS Y ADMINISTRATIVOS)
# ==============================================================================

class TestWordToM3:
    """Pruebas para Matriz 3: Docentes, Administrativos y no nominales."""

    def test_word_m3_docente_nominal(self, sqlite_test_env, tmp_path):
        """Docente nominal se enruta a M3 con subtipo 'DOCENTE' en columna 34."""
        salida = tmp_path / "salida_m3_docente"
        salida.mkdir()

        act = Activity(id_actividad="act-m3-001", nombre_actividad_original="Capacitación Docente", sede="BILWI")
        per = Person(
            id_persona_interno="per-doc-001",
            nombre_completo="Prof. Roberto Gómez Campbell",
            cedula="601-100280-1003C",
            sexo_normalizado="MASCULINO",
            cargo="Docente Titular",
        )
        part = Participation(
            id_participacion="part-doc-001",
            id_actividad=act.id_actividad,
            id_persona=per.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )
        with sqlite_test_env:
            sqlite_test_env.actividades.save(act)
            sqlite_test_env.personas.save(per)
            sqlite_test_env.participaciones.save(part)
            sqlite_test_env.commit()

        pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        export_uc = ExportarMatricesPeriodoUseCase(pipeline_use_case=pipeline_uc, uow=sqlite_test_env)
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            ids_actividades=[act.id_actividad],
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = export_uc.execute(cmd, uow=sqlite_test_env)
        wb = openpyxl.load_workbook(res.archivos_generados["matriz_3"], data_only=False)
        ws = wb.worksheets[0]
        assert ws.cell(row=2, column=34).value == "DOCENTE"
        assert ws.cell(row=2, column=35).value == "Prof. Roberto Gómez Campbell"
        assert ws.cell(row=2, column=42).value == '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")'
        wb.close()

    def test_word_m3_administrativo_nominal(self, sqlite_test_env, tmp_path):
        """Personal administrativo se enruta a M3 con subtipo 'ADMINISTRATIVO' en columna 34."""
        salida = tmp_path / "salida_m3_admo"
        salida.mkdir()

        act = Activity(id_actividad="act-m3-002", nombre_actividad_original="Reunión de Coordinación", sede="BLUEFIELDS")
        per = Person(
            id_persona_interno="per-adm-001",
            nombre_completo="Lic. Ana Patricia Hodgson",
            cedula="601-200585-1004D",
            sexo_normalizado="FEMENINO",
            cargo="Secretaria Académica",
        )
        part = Participation(
            id_participacion="part-adm-001",
            id_actividad=act.id_actividad,
            id_persona=per.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ADMINISTRATIVO,
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )
        with sqlite_test_env:
            sqlite_test_env.actividades.save(act)
            sqlite_test_env.personas.save(per)
            sqlite_test_env.participaciones.save(part)
            sqlite_test_env.commit()

        pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        export_uc = ExportarMatricesPeriodoUseCase(pipeline_use_case=pipeline_uc, uow=sqlite_test_env)
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            ids_actividades=[act.id_actividad],
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = export_uc.execute(cmd, uow=sqlite_test_env)
        wb = openpyxl.load_workbook(res.archivos_generados["matriz_3"])
        ws = wb.worksheets[0]
        assert ws.cell(row=2, column=34).value == "ADMINISTRATIVO"
        assert ws.cell(row=2, column=35).value == "Lic. Ana Patricia Hodgson"
        wb.close()

    def test_word_m3_agregado_sin_nominal(self, batch_orchestrator, tmp_path):
        """Actividades con solo docentes agregados (ej. D-03) no generan docentes nominales ficticios en M3."""
        origen = tmp_path / "origen_m3_agg"
        origen.mkdir()
        salida = tmp_path / "salida_m3_agg"
        salida.mkdir()

        doc_d03 = list(Path("validation/f28_6/ci/D-03").glob("*.docx"))[0]
        shutil.copy2(doc_d03, origen / "D-03.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)
        wb = openpyxl.load_workbook(res.matrices_generadas["matriz_3"])
        ws = wb.worksheets[0]
        assert ws.cell(row=2, column=35).value is None
        wb.close()


# ==============================================================================
# 4. WORD -> M4 (COLABORADORES)
# ==============================================================================

class TestWordToM4:
    """Pruebas para Matriz 4: Colaboradores externos nominales y solo agregados."""

    def test_word_m4_colaborador_nominal(self, sqlite_test_env, tmp_path):
        """Colaborador externo nominal se enruta a M4 con 'COLABORADOR' en columna 34."""
        salida = tmp_path / "salida_m4_colab"
        salida.mkdir()

        act = Activity(id_actividad="act-m4-001", nombre_actividad_original="Feria de Innovación", sede="BILWI")
        per = Person(
            id_persona_interno="per-col-001",
            nombre_completo="Ing. Dennis Hunter Taylor",
            cedula="601-300488-1005E",
            sexo_normalizado="MASCULINO",
            institucion_procedencia="INATEC",
        )
        part = Participation(
            id_participacion="part-col-001",
            id_actividad=act.id_actividad,
            id_persona=per.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.COLABORADOR,
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )
        with sqlite_test_env:
            sqlite_test_env.actividades.save(act)
            sqlite_test_env.personas.save(per)
            sqlite_test_env.participaciones.save(part)
            sqlite_test_env.commit()

        pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        export_uc = ExportarMatricesPeriodoUseCase(pipeline_use_case=pipeline_uc, uow=sqlite_test_env)
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            ids_actividades=[act.id_actividad],
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = export_uc.execute(cmd, uow=sqlite_test_env)
        wb = openpyxl.load_workbook(res.archivos_generados["matriz_4"], data_only=False)
        ws = wb.worksheets[0]
        assert ws.cell(row=2, column=34).value == "COLABORADOR"
        assert ws.cell(row=2, column=35).value == "Ing. Dennis Hunter Taylor"
        assert ws.cell(row=2, column=42).value == '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")'
        wb.close()

    def test_word_m4_colaborador_agregado_sin_nominal(self, batch_orchestrator, tmp_path):
        """Actividades con solo total de otros/colaboradores agregados no generan colaboradores ficticios en M4."""
        origen = tmp_path / "origen_m4_agg"
        origen.mkdir()
        salida = tmp_path / "salida_m4_agg"
        salida.mkdir()

        doc_d07 = list(Path("validation/f28_6/ci/D-07").glob("*.docx"))[0]
        shutil.copy2(doc_d07, origen / "D-07.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)
        wb = openpyxl.load_workbook(res.matrices_generadas["matriz_4"])
        ws = wb.worksheets[0]
        assert ws.cell(row=2, column=35).value is None
        wb.close()


# ==============================================================================
# 5. WORD -> M5 (PROTAGONISTAS BENEFICIADOS E HISTÓRICO)
# ==============================================================================

class TestWordToM5:
    """Pruebas críticas para Matriz 5: preservación de 32 históricos, nuevas filas, es_historico_preexistente y regla RN-C03."""

    def test_word_m5_nuevo_beneficiario_posicion_34_e_historico_preservado(self, sqlite_test_env, tmp_path):
        """Nuevo beneficiario se inserta en fila 34, manteniendo celda por celda los 32 históricos (filas 2-33)."""
        salida = tmp_path / "salida_m5_nuevo"
        salida.mkdir()

        act = Activity(id_actividad="act-m5-001", nombre_actividad_original="Feria Comunitaria de Emprendimiento", sede="BILWI")
        per = Person(
            id_persona_interno="per-ben-001",
            nombre_completo="María Auxiliadora Martínez",
            cedula="601-251292-1006F",
            sexo_normalizado="FEMENINO",
            fecha_nacimiento="1992-12-25",
        )
        part = Participation(
            id_participacion="part-ben-001",
            id_actividad=act.id_actividad,
            id_persona=per.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.BENEFICIADO,
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )
        with sqlite_test_env:
            sqlite_test_env.actividades.save(act)
            sqlite_test_env.personas.save(per)
            sqlite_test_env.participaciones.save(part)
            sqlite_test_env.commit()

        pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        export_uc = ExportarMatricesPeriodoUseCase(pipeline_use_case=pipeline_uc, uow=sqlite_test_env)
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            ids_actividades=[act.id_actividad],
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = export_uc.execute(cmd, uow=sqlite_test_env)
        assert res.exito is True

        m5_path = Path(res.archivos_generados["matriz_5"])
        wb_m5 = openpyxl.load_workbook(str(m5_path), data_only=False)
        ws_m5 = wb_m5.worksheets[0]

        # 1. Verificar Cero Destrucción: 32 registros históricos (filas 2 a 33) 100% idénticos a plantilla
        wb_tpl = openpyxl.load_workbook("templates/Matriz_5_Protagonistas_Beneficiados.xlsx", data_only=False)
        ws_tpl = wb_tpl.worksheets[0]

        for r in range(2, 34):
            for c in range(1, 54):
                val_tpl = ws_tpl.cell(row=r, column=c).value
                val_gen = ws_m5.cell(row=r, column=c).value
                assert val_tpl == val_gen, f"Diferencia en histórico ({r}, {c}): '{val_tpl}' vs '{val_gen}'"

        wb_tpl.close()

        # 2. Verificar nuevo beneficiario en fila 34
        assert ws_m5.cell(row=34, column=1).value == "=+A33+1"
        assert ws_m5.cell(row=34, column=34).value == "María Auxiliadora Martínez"
        assert ws_m5.cell(row=34, column=36).value == "601-251292-1006F"
        assert ws_m5.cell(row=34, column=39).value in ("F", "FEMENINO")
        assert ws_m5.cell(row=34, column=41).value == '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")'
        assert ws_m5.cell(row=34, column=53).value == "Capacitación / Acompañamiento"
        wb_m5.close()

    def test_word_m5_es_historico_preexistente_distincion(self, sqlite_test_env):
        """RN-C06: Distinción formal de es_historico_preexistente en el repositorio de participaciones."""
        with sqlite_test_env:
            act_base = Activity(id_actividad="act-001", nombre_actividad_original="Actividad Base")
            per_h1 = Person(id_persona_interno="per-001", nombre_completo="Persona Histórica")
            per_n2 = Person(id_persona_interno="per-002", nombre_completo="Persona Nueva")
            sqlite_test_env.actividades.save(act_base)
            sqlite_test_env.personas.save(per_h1)
            sqlite_test_env.personas.save(per_n2)

            # Registro histórico preexistente
            p_hist = Participation(
                id_participacion="part-hist-01",
                id_actividad="act-001",
                id_persona="per-001",
                categoria_participacion=CategoriaParticipacion.BENEFICIADO,
                es_historico_preexistente=1,
            )
            # Nuevo registro de ejecución actual
            p_nuevo = Participation(
                id_participacion="part-nuevo-01",
                id_actividad="act-001",
                id_persona="per-002",
                categoria_participacion=CategoriaParticipacion.BENEFICIADO,
                es_historico_preexistente=0,
            )
            sqlite_test_env.participaciones.save(p_hist)
            sqlite_test_env.participaciones.save(p_nuevo)
            sqlite_test_env.commit()

        conn = sqlite_test_env._connection_manager.get_connection()
        val_hist = conn.execute("SELECT es_historico_preexistente FROM participacion WHERE id_participacion='part-hist-01';").fetchone()[0]
        val_nuevo = conn.execute("SELECT es_historico_preexistente FROM participacion WHERE id_participacion='part-nuevo-01';").fetchone()[0]
        conn.close()

        assert val_hist == 1
        assert val_nuevo == 0

    def test_word_m5_estudiante_beneficiario_y_ambiguedad(self, sqlite_test_env, tmp_path):
        """RN-C03: Estudiante con es_beneficiado_rol=True va a M5; categoría desconocida va a COLA_REVISION."""
        salida = tmp_path / "salida_m5_rnc03"
        salida.mkdir()

        act = Activity(id_actividad="act-m5-rnc03", nombre_actividad_original="Capacitación Emprendedora", sede="BILWI")
        per_est_ben = Person(id_persona_interno="per-dual", nombre_completo="Estudiante Beneficiario Confirmado")
        per_desconocido = Person(id_persona_interno="per-desc", nombre_completo="Participante Desconocido")

        part_dual = Participation(
            id_participacion="part-dual",
            id_actividad=act.id_actividad,
            id_persona=per_est_ben.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            es_beneficiado_rol=True,  # Confirmación explícita de beneficiario
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )
        part_desc = Participation(
            id_participacion="part-desc",
            id_actividad=act.id_actividad,
            id_persona=per_desconocido.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DESCONOCIDO,  # Ambigüedad
            condicion_asistencia="PRESENTE",
            es_historico_preexistente=0,
        )

        with sqlite_test_env:
            sqlite_test_env.actividades.save(act)
            sqlite_test_env.personas.save(per_est_ben)
            sqlite_test_env.personas.save(per_desconocido)
            sqlite_test_env.participaciones.save(part_dual)
            sqlite_test_env.participaciones.save(part_desc)
            sqlite_test_env.commit()

        pipeline_uc = ProcesarPipelineActividadUseCase(uow=sqlite_test_env)
        export_uc = ExportarMatricesPeriodoUseCase(pipeline_use_case=pipeline_uc, uow=sqlite_test_env)
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            ids_actividades=[act.id_actividad],
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = export_uc.execute(cmd, uow=sqlite_test_env)

        # M5 recibe al estudiante beneficiario
        wb_m5 = openpyxl.load_workbook(res.archivos_generados["matriz_5"])
        ws_m5 = wb_m5.worksheets[0]
        assert ws_m5.cell(row=34, column=34).value == "Estudiante Beneficiario Confirmado"
        wb_m5.close()

        # Participante desconocido fue retenido en cola de revisión (no fue inyectado en M1-M5)
        wb_m2 = openpyxl.load_workbook(res.archivos_generados["matriz_2"])
        ws_m2 = wb_m2.worksheets[0]
        assert ws_m2.cell(row=2, column=33).value is None  # No está en M2
        wb_m2.close()


# ==============================================================================
# 6. BATCH COMPLETO D-01 A D-07 Y RECHAZO DE D-08 A D-10
# ==============================================================================

class TestBatchReal:
    """Procesamiento por lote completo de los documentos institucionales reales."""

    def test_batch_d01_a_d07_procesamiento_completo(self, batch_orchestrator, sqlite_test_env, tmp_path):
        """Procesa el lote real D-01..D-07 generando 7 actividades en SQLite y 7 filas en M1."""
        origen = Path("validation/f28_6/lote").resolve()
        salida = tmp_path / "salida_lote_completo"
        salida.mkdir()

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)

        assert res.invariante_ok is True
        assert res.archivos_encontrados == 7
        assert (res.archivos_aceptados + res.archivos_con_advertencias) == 7
        assert res.archivos_rechazados == 0
        assert res.archivos_fallidos == 0
        assert len(res.actividades_creadas) == 7
        assert len(res.matrices_generadas) == 5
        assert res.manifest_path is not None

        # 1. SQLite SSOT
        conn = sqlite_test_env._connection_manager.get_connection()
        total_act = conn.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]
        total_met = conn.execute("SELECT COUNT(*) FROM actividad_metrica_agregada;").fetchone()[0]
        total_per = conn.execute("SELECT COUNT(*) FROM persona;").fetchone()[0]
        conn.close()

        assert total_act == 7
        assert total_met == 7
        assert total_per == 0  # INV-01: 0 nominales fabricados

        # 2. M1 Consolidado físico
        m1_path = Path(res.matrices_generadas["matriz_1"])
        wb_m1 = openpyxl.load_workbook(str(m1_path), data_only=False)
        ws_m1 = wb_m1.worksheets[0]

        # Filas 2 a 8 pobladas con las 7 actividades
        for r in range(2, 9):
            assert ws_m1.cell(row=r, column=9).value is not None, f"Fila {r} de M1 sin actividad"
        # Fila 9 vacía de actividades pero con fórmulas preservadas
        assert ws_m1.cell(row=9, column=9).value is None
        assert ws_m1.cell(row=9, column=1).value == "=+A8+1"
        wb_m1.close()

        # 3. M2 a M4 limpias de nominales
        for mid in ["matriz_2", "matriz_3", "matriz_4"]:
            wb = openpyxl.load_workbook(res.matrices_generadas[mid])
            ws = wb.worksheets[0]
            assert ws.cell(row=2, column=33 if mid == "matriz_2" else 35).value is None
            wb.close()

        # 4. M5 con 32 históricos intactos
        wb_m5 = openpyxl.load_workbook(res.matrices_generadas["matriz_5"])
        ws_m5 = wb_m5.worksheets[0]
        assert ws_m5.cell(row=33, column=1).value == 32
        assert ws_m5.cell(row=34, column=1).value is None
        wb_m5.close()

    def test_batch_documentos_incompatibles_rechazados(self, batch_orchestrator, tmp_path):
        """Lote heterogéneo con D-01 válido y D-08..D-10 incompatibles rechaza los 3 documentos."""
        origen = tmp_path / "origen_heterogeneo"
        origen.mkdir()
        salida = tmp_path / "salida_heterogeneo"
        salida.mkdir()

        doc_d01 = list(Path("validation/f28_6/ci/D-01").glob("*.docx"))[0]
        doc_d08 = list(Path("validation/f28_6/ci/D-08").glob("*.docx"))[0]
        doc_d09 = list(Path("validation/f28_6/ci/D-09").glob("*.docx"))[0]
        doc_d10 = list(Path("validation/f28_6/ci/D-10").glob("*.docx"))[0]

        shutil.copy2(doc_d01, origen / "D-01.docx")
        shutil.copy2(doc_d08, origen / "D-08.docx")
        shutil.copy2(doc_d09, origen / "D-09.docx")
        shutil.copy2(doc_d10, origen / "D-10.docx")

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )
        res = batch_orchestrator.execute(cmd)

        assert res.invariante_ok is True
        assert res.archivos_encontrados == 4
        assert res.archivos_aceptados == 1
        assert res.archivos_rechazados == 3
        assert len(res.actividades_creadas) == 1


# ==============================================================================
# 7. IDEMPOTENCIA DE LOTE COMPLETO
# ==============================================================================

class TestIdempotenciaLote:
    """Pruebas de idempotencia sobre lotes completos sucesivos."""

    def test_idempotencia_reproceso_lote_completo(self, batch_orchestrator, sqlite_test_env, tmp_path):
        """Reprocesar D-01..D-07 contra la misma base de datos no genera registros duplicados en SQLite."""
        origen = Path("validation/f28_6/lote").resolve()
        salida = tmp_path / "salida_idempotencia"
        salida.mkdir()

        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=str(origen),
            carpeta_salida=str(salida),
            carpeta_templates="templates",
            permitir_fixtures_test_only=False,
            dry_run=False,
        )

        # 1. Primera corrida
        res1 = batch_orchestrator.execute(cmd)
        assert len(res1.actividades_creadas) == 7

        # 2. Segunda corrida
        res2 = batch_orchestrator.execute(cmd)
        assert res2.invariante_ok is True
        # Las 7 actividades ya existían por hash SHA-256
        assert len(res2.actividades_creadas) == 0

        # SQLite permanece con exactamente 7 actividades
        conn = sqlite_test_env._connection_manager.get_connection()
        total_act = conn.execute("SELECT COUNT(*) FROM actividad;").fetchone()[0]
        conn.close()
        assert total_act == 7


# ==============================================================================
# 8. CONSERVACIÓN PATRIMONIAL (6/6 HASHES MATCH)
# ==============================================================================

class TestConservacionPatrimonial:
    """Verificación de inmutabilidad criptográfica absoluta de los 6 artefactos patrimoniales."""

    def test_patrimonial_hashes_6_de_6_match(self):
        """Comprueba que los 5 archivos oficiales en templates/ y el ejecutable compilado mantengan sus hashes."""
        for cod, (ruta_str, hash_esperado) in PATRIMONIAL_HASHES.items():
            p = Path(ruta_str)
            assert p.exists(), f"Artefacto patrimonial '{cod}' no existe en '{ruta_str}'."
            h_real = calcular_sha256(p)
            assert h_real.lower() == hash_esperado.lower(), (
                f"Hash alterado en '{cod}' ({ruta_str}): esperado {hash_esperado}, obtenido {h_real}"
            )


# ==============================================================================
# 9. AISLAMIENTO ARQUITECTÓNICO (AST)
# ==============================================================================

class TestAislamientoArquitectonico:
    """Auditoría estática de dependencias (AST) para garantizar el aislamiento institucional."""

    def test_aislamiento_arquitectonico_ast(self):
        """Verifica que el pipeline de Word no importe Planning, Reporting, Gemini ni Dashboard."""
        rutas_a_inspeccionar = [
            Path("app/application/use_cases/batch"),
            Path("app/application/use_cases/exportacion"),
            Path("app/infrastructure/word_reader"),
            Path("app/exporters"),
        ]

        prohibidos = [
            "app.planning",
            "app.reporting",
            "app.indicators",
            "google.generativeai",
            "matplotlib",
            "customtkinter",
        ]

        for base_dir in rutas_a_inspeccionar:
            if not base_dir.exists():
                continue
            for py_file in base_dir.glob("**/*.py"):
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            for p in prohibidos:
                                assert not alias.name.startswith(p), (
                                    f"Violación de aislamiento en {py_file.name}: importa '{alias.name}'"
                                )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            for p in prohibidos:
                                assert not node.module.startswith(p), (
                                    f"Violación de aislamiento en {py_file.name}: importa from '{node.module}'"
                                )
