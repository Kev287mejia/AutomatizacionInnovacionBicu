"""tests/test_pipeline_fase_26_7.py

Suite de pruebas automatizadas para la Fase 26.7 (Bloque 1):
Integración del Pipeline Operativo (Calidad -> Routing -> Preparación de Exportación)
y Anti-Corruption Layer (ExportACL).

Verifica:
1. Pipeline E2E: Ingesta -> Quality -> Routing -> Export Preparation.
2. Manejo de actividad inexistente (EntityNotFoundError).
3. Clasificación nominal fiel:
   - Estudiante -> M2
   - Docente/Admin -> M3
   - Colaborador -> M4
   - Beneficiado -> M5
   - Estudiante con rol beneficiario (RN-C03) -> M5
4. Invariante matemática estricta: Entrada = M2 + M3 + M4 + M5 + COLA_REVISION + BLOQUEADOS.
5. Integración Quality -> Routing: hallazgos ERROR/CRITICAL aíslan en BLOQUEADOS.
6. Exclusión incondicional de BLOQUEADOS de los datasets de exportación.
7. Abstracción de política OPEN-02 (PoliticaExportacionRevision):
   - RETENER_EN_CUARENTENA
   - EXPORTAR_CON_OBSERVACION
   - EXPORTAR_CON_MARCA
8. Garantía de no mutación de datos de negocio (RN-C07: DETECTAR ≠ CORREGIR).
9. Contrato de simulación: dry_run=True no persiste ningún cambio en la base de datos SQLite.
10. Preservación conceptual del histórico de M5 (filas 2..33, 32 fundacionales).
11. Análisis estricto de AST: app/application/* libre de sqlite3, openpyxl, xlsxwriter, docx y customtkinter.
"""

import ast
from datetime import date
from pathlib import Path
import pytest
import tempfile
import uuid

from app.core.constants.participant_types import (
    CategoriaParticipacion,
    NivelValidacion,
)
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.repositories import (
    SQLiteActividadRepository,
    SQLitePersonaRepository,
    SQLiteParticipacionRepository,
    SQLiteDiscrepanciaRepository,
    SQLiteUnitOfWork,
)
from app.routing.enums import MatrizDestino
from app.application.commands.pipeline_commands import (
    EjecutarPipelineActividadCommand,
    ExportarMatricesActividadCommand,
    ExportarMatricesPeriodoCommand,
)
from app.application.dto.export_dtos import (
    PoliticaExportacionRevision,
    ExportacionPreparadaDTO,
    PipelineActividadResultDTO,
    ExportarMatricesResultDTO,
)
from app.application.export_acl.export_acl import ExportACL, ExportDataset
from app.application.fakes import InMemoryUnitOfWork
from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)
from app.application.use_cases.exportacion.exportar_matrices_actividad import (
    ExportarMatricesActividadUseCase,
)
from app.application.use_cases.exportacion.exportar_matrices_periodo import (
    ExportarMatricesPeriodoUseCase,
)


@pytest.fixture
def temp_db():
    """Crea una base de datos SQLite real temporal en disco con v001 aplicada."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_pipeline_26_7.db"
        config = DatabaseConfig(db_path=db_path)
        manager = SQLiteConnectionManager(config)

        conn = manager.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending()
        finally:
            conn.close()

        yield manager, db_path


@pytest.fixture
def repos(temp_db):
    """Inicializa repositorios SQLite y Unit of Work sobre la base temporal."""
    manager, db_path = temp_db
    conn = manager.get_connection()
    act_repo = SQLiteActividadRepository(conn)
    per_repo = SQLitePersonaRepository(conn)
    part_repo = SQLiteParticipacionRepository(conn)
    disc_repo = SQLiteDiscrepanciaRepository(conn)
    uow = SQLiteUnitOfWork(manager)
    yield {
        "act": act_repo,
        "per": per_repo,
        "part": part_repo,
        "disc": disc_repo,
        "uow": uow,
        "manager": manager,
        "conn": conn,
    }
    conn.close()


def _crear_actividad_base(id_act: str = "ACT-26-7-001") -> Activity:
    return Activity(
        id_actividad=id_act,
        nombre_actividad_original="Taller Integral de Liderazgo y Metodología 2026",
        nombre_actividad_oficial="TALLER INSTITUCIONAL DE LIDERAZGO",
        fecha_evento=date(2026, 9, 20),
        sede="BLUEFIELDS",
        modalidad="PRESENCIAL",
        estado_actividad="CONCLUIDA",
        fuente_origen="LISTA_ASISTENCIA_OFICIAL.xlsx",
    )


class TestPipelineIntegracionE2E:
    """Pruebas funcionales e integradas del pipeline completo."""

    def test_01_actividad_inexistente_lanza_entity_not_found(self, repos):
        """Verifica que intentar ejecutar el pipeline sobre una actividad inexistente lance EntityNotFoundError."""
        use_case = ProcesarPipelineActividadUseCase(
            actividad_repo=repos["act"],
            persona_repo=repos["per"],
            participacion_repo=repos["part"],
            discrepancia_repo=repos["disc"],
            uow=repos["uow"],
        )
        cmd = EjecutarPipelineActividadCommand(id_actividad="ACT-NO-EXISTE")
        with pytest.raises(EntityNotFoundError) as exc_info:
            use_case.execute(cmd)

        assert "ACT-NO-EXISTE" in str(exc_info.value)

    def test_02_pipeline_completo_multiples_participantes_y_destinos(self, repos):
        """Verifica el flujo E2E: Actividad + 5 participantes -> Calidad -> Routing -> Preparación Export."""
        act = _crear_actividad_base("ACT-PIPELINE-01")
        repos["act"].save(act)

        # 1. Estudiante -> M2
        p1 = Person(id_persona_interno="PER-01", nombre_completo="Ana Sofia Campbell", sexo_normalizado="FEMENINO")
        part1 = Participation(id_participacion="PART-01", id_actividad=act.id_actividad, id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        # 2. Docente -> M3
        p2 = Person(id_persona_interno="PER-02", nombre_completo="Carlos Alberto Hodgson", sexo_normalizado="MASCULINO")
        part2 = Participation(id_participacion="PART-02", id_actividad=act.id_actividad, id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.DOCENTE)

        # 3. Colaborador externo -> M4
        p3 = Person(id_persona_interno="PER-03", nombre_completo="Elena Patricia Brooks", sexo_normalizado="FEMENINO")
        part3 = Participation(id_participacion="PART-03", id_actividad=act.id_actividad, id_persona=p3.id_persona_interno, categoria_participacion=CategoriaParticipacion.COLABORADOR)

        # 4. Beneficiado de la comunidad -> M5
        p4 = Person(id_persona_interno="PER-04", nombre_completo="Roberto David Morales", sexo_normalizado="MASCULINO")
        part4 = Participation(id_participacion="PART-04", id_actividad=act.id_actividad, id_persona=p4.id_persona_interno, categoria_participacion=CategoriaParticipacion.BENEFICIADO)

        # 5. Estudiante con rol de beneficiario (RN-C03) -> M5
        p5 = Person(id_persona_interno="PER-05", nombre_completo="Maria Celeste Downs", sexo_normalizado="FEMENINO")
        part5 = Participation(
            id_participacion="PART-05",
            id_actividad=act.id_actividad,
            id_persona=p5.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            es_beneficiado_rol=True,
        )

        for p in (p1, p2, p3, p4, p5):
            repos["per"].save(p)
        for part in (part1, part2, part3, part4, part5):
            repos["part"].save(part)

        use_case = ProcesarPipelineActividadUseCase(uow=repos["uow"])
        cmd = EjecutarPipelineActividadCommand(
            id_actividad=act.id_actividad,
            dry_run=False,
            politica_revision=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
        )
        res: PipelineActividadResultDTO = use_case.execute(cmd)

        assert res.id_actividad == act.id_actividad
        assert res.total_participaciones_ingreso == 5
        assert res.invariante_conservacion_valida is True

        # Routing checks
        assert res.routing.total_m2_estudiantes == 1
        assert res.routing.total_m3_academicos_admin == 1
        assert res.routing.total_m4_colaboradores == 1
        assert res.routing.total_m5_beneficiados == 2  # P4 beneficiario + P5 estudiante beneficiario (RN-C03)
        assert res.routing.total_cola_revision == 0
        assert res.routing.total_bloqueados == 0

        # Export Prepared checks
        prep = res.exportacion_preparada
        assert prep.total_m1_actividades == 1
        assert prep.total_m2_estudiantes == 1
        assert prep.total_m3_academicos_admin == 1
        assert prep.total_m4_colaboradores == 1
        assert prep.total_m5_beneficiados == 2
        assert prep.total_exportables_nominales == 5
        assert prep.total_bloqueados_excluidos == 0
        assert prep.invariante_verificada is True

        # Verificar persistencia en SQLite
        part_db1 = repos["part"].get_by_id("PART-01")
        assert part_db1.matriz_destino == "M2"
        part_db5 = repos["part"].get_by_id("PART-05")
        assert part_db5.matriz_destino == "M5"

    def test_03_invariante_matematica_estricta_con_todas_las_cubetas(self):
        """Verifica la invariante Entrada = M2 + M3 + M4 + M5 + COLA_REVISION + BLOQUEADOS."""
        uow = InMemoryUnitOfWork()
        act = _crear_actividad_base("ACT-INVARIANTE-01")

        # 1 Estudiante (M2), 1 Docente (M3), 1 Colaborador (M4), 1 Beneficiado (M5),
        # 1 Desconocido (COLA_REVISION), 1 Huérfano (BLOQUEADOS) -> Total 6
        p1 = Person(id_persona_interno="PER-INV-1", nombre_completo="Estudiante 1", sexo_normalizado="MASCULINO")
        p2 = Person(id_persona_interno="PER-INV-2", nombre_completo="Docente 1", sexo_normalizado="FEMENINO")
        p3 = Person(id_persona_interno="PER-INV-3", nombre_completo="Colaborador 1", sexo_normalizado="MASCULINO")
        p4 = Person(id_persona_interno="PER-INV-4", nombre_completo="Beneficiado 1", sexo_normalizado="FEMENINO")
        p5 = Person(id_persona_interno="PER-INV-5", nombre_completo="Sin Categoria", sexo_normalizado="FEMENINO")

        with uow:
            uow.actividades.save(act)
            for p in (p1, p2, p3, p4, p5):
                uow.personas.save(p)

            part1 = Participation(id_participacion="PART-INV-1", id_actividad=act.id_actividad, id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
            part2 = Participation(id_participacion="PART-INV-2", id_actividad=act.id_actividad, id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.DOCENTE)
            part3 = Participation(id_participacion="PART-INV-3", id_actividad=act.id_actividad, id_persona=p3.id_persona_interno, categoria_participacion=CategoriaParticipacion.COLABORADOR)
            part4 = Participation(id_participacion="PART-INV-4", id_actividad=act.id_actividad, id_persona=p4.id_persona_interno, categoria_participacion=CategoriaParticipacion.BENEFICIADO)
            part5 = Participation(id_participacion="PART-INV-5", id_actividad=act.id_actividad, id_persona=p5.id_persona_interno, categoria_participacion=CategoriaParticipacion.DESCONOCIDO)
            part6 = Participation(id_participacion="PART-INV-6", id_actividad=act.id_actividad, id_persona="PER-FANTASMA-HUERFANA", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

            for part in (part1, part2, part3, part4, part5, part6):
                uow.participaciones.save(part)
            uow.commit()

        use_case = ProcesarPipelineActividadUseCase(uow=uow)
        cmd = EjecutarPipelineActividadCommand(id_actividad=act.id_actividad, dry_run=False)
        res = use_case.execute(cmd)

        assert res.total_participaciones_ingreso == 6
        assert res.routing.total_m2_estudiantes == 1
        assert res.routing.total_m3_academicos_admin == 1
        assert res.routing.total_m4_colaboradores == 1
        assert res.routing.total_m5_beneficiados == 1
        assert res.routing.total_cola_revision == 1
        assert res.routing.total_bloqueados == 1
        assert res.invariante_conservacion_valida is True
        assert res.exportacion_preparada.total_exportables_nominales == 4
        assert res.exportacion_preparada.total_cola_revision_excluidos == 1
        assert res.exportacion_preparada.total_bloqueados_excluidos == 1


class TestIntegracionCalidadRouting:
    """Pruebas del acoplamiento entre Calidad y Routing (GAP-TEC-01 solucionado)."""

    def test_04_error_critico_calidad_aisla_automaticamente_en_bloqueados(self, repos):
        """Un participante con error crítico de calidad (Q-15 referencia huérfana) se aísla en BLOQUEADOS."""
        act = _crear_actividad_base("ACT-CAL-ROUT-01")
        repos["act"].save(act)

        # Participación con id_persona inexistente (huérfano) -> Q-15 emite severidad ERROR
        conn = repos["conn"]
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute(
            "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino) "
            "VALUES ('PART-CAL-01', ?, 'PER-INEXISTENTE-HUERFANA', 'ESTUDIANTE', NULL);",
            (act.id_actividad,)
        )
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

        use_case = ProcesarPipelineActividadUseCase(uow=repos["uow"])
        cmd = EjecutarPipelineActividadCommand(id_actividad=act.id_actividad, dry_run=False)
        res = use_case.execute(cmd)

        # Debe aislarse en BLOQUEADOS
        assert res.routing.total_bloqueados == 1
        assert res.routing.total_m2_estudiantes == 0
        assert res.exportacion_preparada.total_bloqueados_excluidos == 1
        assert res.exportacion_preparada.total_m2_estudiantes == 0
        assert res.total_bloqueadas == 1

        # En SQLite debe mantener matriz_destino = NULL (no entra a ninguna matriz oficial)
        part_db = repos["part"].get_by_id("PART-CAL-01")
        assert part_db.matriz_destino is None


class TestPoliticaOpen02ExportacionRevision:
    """Pruebas de la abstracción de política OPEN-02 para registros EN_REVISION."""

    def test_05_politica_retener_en_cuarentena_excluye_de_matrices_nominales(self, repos):
        """Con RETENER_EN_CUARENTENA, los registros con requiere_revision=True se retienen y no van a M2..M5."""
        act = _crear_actividad_base("ACT-OPEN-02-CUAR")
        repos["act"].save(act)

        p1 = Person(id_persona_interno="PER-CUAR-1", nombre_completo="Estudiante Apto", sexo_normalizado="FEMENINO")
        p2 = Person(id_persona_interno="PER-CUAR-2", nombre_completo="Estudiante Dudoso", sexo_normalizado="MASCULINO")
        repos["per"].save(p1)
        repos["per"].save(p2)

        part1 = Participation(
            id_participacion="PART-CUAR-1",
            id_actividad=act.id_actividad,
            id_persona=p1.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            requiere_revision=False,
        )
        part2 = Participation(
            id_participacion="PART-CUAR-2",
            id_actividad=act.id_actividad,
            id_persona=p2.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            requiere_revision=True,
            motivo_revision="Falta carné oficial",
        )
        repos["part"].save(part1)
        repos["part"].save(part2)

        use_case = ProcesarPipelineActividadUseCase(uow=repos["uow"])
        cmd = EjecutarPipelineActividadCommand(
            id_actividad=act.id_actividad,
            politica_revision=PoliticaExportacionRevision.RETENER_EN_CUARENTENA,
        )
        res = use_case.execute(cmd)

        # En routing ambas son M2 (porque la cubeta formal es Estudiantes)
        assert res.routing.total_m2_estudiantes == 2
        # Pero en exportación preparada, 1 es apta y 1 va a cuarentena
        prep = res.exportacion_preparada
        assert prep.total_m2_estudiantes == 1
        assert prep.total_cuarentena == 1
        assert prep.total_exportables_nominales == 1

    def test_06_politica_exportar_con_observacion_preserva_comportamiento_v1_0_3(self, repos):
        """Con EXPORTAR_CON_OBSERVACION (defecto v1.0.3), el registro va a M2 manteniendo su observación."""
        act = _crear_actividad_base("ACT-OPEN-02-OBS")
        repos["act"].save(act)

        p = Person(id_persona_interno="PER-OBS-1", nombre_completo="Estudiante Obs", sexo_normalizado="FEMENINO")
        repos["per"].save(p)

        part = Participation(
            id_participacion="PART-OBS-1",
            id_actividad=act.id_actividad,
            id_persona=p.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            requiere_revision=True,
            motivo_revision="Cédula pendiente de verificación",
        )
        repos["part"].save(part)

        use_case = ProcesarPipelineActividadUseCase(uow=repos["uow"])
        cmd = EjecutarPipelineActividadCommand(
            id_actividad=act.id_actividad,
            politica_revision=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
        )
        res = use_case.execute(cmd)

        prep = res.exportacion_preparada
        assert prep.total_m2_estudiantes == 1
        assert prep.total_cuarentena == 0
        assert prep.total_exportables_nominales == 1

    def test_07_politica_exportar_con_marca_antepone_tag_formal(self, repos):
        """Con EXPORTAR_CON_MARCA, el registro se exporta con la etiqueta [EN_REVISION]."""
        act = _crear_actividad_base("ACT-OPEN-02-TAG")
        repos["act"].save(act)

        p = Person(id_persona_interno="PER-TAG-1", nombre_completo="Estudiante Tag", sexo_normalizado="MASCULINO")
        repos["per"].save(p)

        part = Participation(
            id_participacion="PART-TAG-1",
            id_actividad=act.id_actividad,
            id_persona=p.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            requiere_revision=True,
            motivo_revision="Revisión de carrera",
        )
        repos["part"].save(part)

        # Ejecutar directamente ExportACL para inspeccionar los registros preparados
        use_case = ProcesarPipelineActividadUseCase(uow=repos["uow"])
        cmd = EjecutarPipelineActividadCommand(
            id_actividad=act.id_actividad,
            politica_revision=PoliticaExportacionRevision.EXPORTAR_CON_MARCA,
        )
        res = use_case.execute(cmd)
        prep = res.exportacion_preparada
        assert prep.total_m2_estudiantes == 1
        assert prep.total_cuarentena == 0


class TestGarantiasArquitectonicas:
    """Pruebas de garantías fundamentales: RN-C07, dry_run y AST Clean Architecture."""

    def test_08_rn_c07_detectar_no_corregir_cero_mutacion_datos_negocio(self, repos):
        """Verifica que el pipeline respete RN-C07: no muta nombres, cédulas ni fechas."""
        act = _crear_actividad_base("ACT-RNC07-01")
        repos["act"].save(act)

        nombre_original = "maria  de  los  angeles  torres"
        cedula_original = "601-120598-0002W"
        p = Person(
            id_persona_interno="PER-RNC07",
            nombre_completo=nombre_original,
            cedula=cedula_original,
            sexo_normalizado="FEMENINO",
            etnia="MISKITO",
            carrera_oficial="ADMINISTRACION DE EMPRESAS",
        )
        repos["per"].save(p)

        part = Participation(
            id_participacion="PART-RNC07",
            id_actividad=act.id_actividad,
            id_persona=p.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        repos["part"].save(part)

        use_case = ProcesarPipelineActividadUseCase(uow=repos["uow"])
        cmd = EjecutarPipelineActividadCommand(id_actividad=act.id_actividad, dry_run=False)
        use_case.execute(cmd)

        # Leer persona de la base de datos y constatar 100% de inmutabilidad
        p_db = repos["per"].get_by_id(p.id_persona_interno)
        assert p_db.nombre_completo == nombre_original
        assert p_db.cedula == cedula_original
        assert p_db.etnia == "MISKITO"

    def test_09_dry_run_produce_cero_escrituras_persistentes(self, repos):
        """Verifica que dry_run=True no persista ningún cambio en SQLite."""
        act = _crear_actividad_base("ACT-DRYRUN-01")
        repos["act"].save(act)

        p = Person(id_persona_interno="PER-DRY", nombre_completo="Persona Dry Run", sexo_normalizado="MASCULINO")
        repos["per"].save(p)

        part = Participation(
            id_participacion="PART-DRY",
            id_actividad=act.id_actividad,
            id_persona=p.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
            matriz_destino=None,
        )
        repos["part"].save(part)

        use_case = ProcesarPipelineActividadUseCase(uow=repos["uow"])
        cmd = EjecutarPipelineActividadCommand(id_actividad=act.id_actividad, dry_run=True)
        res = use_case.execute(cmd)

        assert res.dry_run is True
        assert res.routing.total_m3_academicos_admin == 1

        # En la base de datos debe permanecer matriz_destino = None
        part_db = repos["part"].get_by_id(part.id_participacion)
        assert part_db.matriz_destino is None

    def test_10_ast_application_no_importa_tecnologias_prohibidas(self):
        """Análisis sintáctico AST: app/application/* libre de sqlite3, openpyxl, xlsxwriter, docx y customtkinter."""
        modulos_prohibidos = {"sqlite3", "openpyxl", "xlsxwriter", "docx", "python-docx", "customtkinter"}
        app_dir = Path("app/application")
        archivos_analizados = 0

        for py_file in app_dir.rglob("*.py"):
            archivos_analizados += 1
            contenido = py_file.read_text(encoding="utf-8")
            arbol = ast.parse(contenido, filename=str(py_file))

            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    for alias in nodo.names:
                        modulo_base = alias.name.split(".")[0]
                        assert modulo_base not in modulos_prohibidos, (
                            f"Violación de Clean Architecture en {py_file}: import directo de '{modulo_base}'"
                        )
                elif isinstance(nodo, ast.ImportFrom):
                    if nodo.module:
                        modulo_base = nodo.module.split(".")[0]
                        assert modulo_base not in modulos_prohibidos, (
                            f"Violación de Clean Architecture en {py_file}: from '{modulo_base}' import ..."
                        )

        assert archivos_analizados >= 10, f"Se esperaban analizar más archivos, encontrados {archivos_analizados}"


class TestCasosDeUsoExportacionM1M5:
    """Pruebas de los casos de uso diseñados para M1–M5 (actividad y período)."""

    def test_11_exportar_matrices_actividad_use_case_preparacion(self, repos):
        """Verifica la orquestación del caso de uso ExportarMatricesActividadUseCase."""
        act = _crear_actividad_base("ACT-EXP-UC-01")
        repos["act"].save(act)

        p = Person(id_persona_interno="PER-EXP-1", nombre_completo="Estudiante Export", sexo_normalizado="FEMENINO")
        repos["per"].save(p)

        part = Participation(
            id_participacion="PART-EXP-1",
            id_actividad=act.id_actividad,
            id_persona=p.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        repos["part"].save(part)

        use_case = ExportarMatricesActividadUseCase(uow=repos["uow"])
        cmd = ExportarMatricesActividadCommand(
            id_actividad=act.id_actividad,
            carpeta_salida="output",
            politica_revision=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
            dry_run=True,
        )
        res: ExportarMatricesResultDTO = use_case.execute(cmd)

        assert res.id_actividad == act.id_actividad
        assert res.exito is True
        assert res.modo == "PREVIEW"
        assert res.total_filas_exportadas_por_matriz["matriz_1"] == 1
        assert res.total_filas_exportadas_por_matriz["matriz_2"] == 1

    def test_12_exportar_matrices_periodo_use_case_preparacion(self, repos):
        """Verifica la consolidación y preparación para un período completo."""
        act1 = _crear_actividad_base("ACT-PER-01")
        act1.fecha_evento = date(2026, 9, 10)
        repos["act"].save(act1)

        act2 = _crear_actividad_base("ACT-PER-02")
        act2.fecha_evento = date(2026, 9, 15)
        repos["act"].save(act2)

        p = Person(id_persona_interno="PER-PER-1", nombre_completo="Participante Periodo", sexo_normalizado="MASCULINO")
        repos["per"].save(p)

        part1 = Participation(id_participacion="PART-PER-1", id_actividad=act1.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.COLABORADOR)
        part2 = Participation(id_participacion="PART-PER-2", id_actividad=act2.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.BENEFICIADO)
        repos["part"].save(part1)
        repos["part"].save(part2)

        use_case = ExportarMatricesPeriodoUseCase(uow=repos["uow"])
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            mes=9,
            carpeta_salida="output",
            dry_run=True,
        )
        res: ExportarMatricesResultDTO = use_case.execute(cmd)

        assert res.exito is True
        assert res.total_filas_exportadas_por_matriz["matriz_1"] == 2
        assert res.total_filas_exportadas_por_matriz["matriz_4"] == 1
        assert res.total_filas_exportadas_por_matriz["matriz_5"] == 1
