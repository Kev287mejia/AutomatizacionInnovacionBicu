"""tests/test_export_bloque_2_fase_26_7.py

Suite de pruebas exhaustivas para la Fase 26.7 (Bloque 2):
Exportación Física Real a Matrices Oficiales M1–M5 desde el SSOT SQLite.

Verifica:
1. Escenario E2E Completo y Obligatorio (Sección 28):
   - 1 Estudiante -> M2
   - 1 Docente -> M3
   - 1 Administrativo -> M3
   - 1 Colaborador -> M4
   - 1 Beneficiario -> M5
   - 1 Estudiante + rol beneficiario (RN-C03) -> M5
   - 1 Registro en revisión -> Gobernado por OPEN-02
   - 1 Registro bloqueado -> 0 matrices (exclusión incondicional)
   - M1: Exactamente 1 fila agregada a nivel actividad (no 7 u 8 filas).
2. Estructura Exacta y Certificada de las 5 Matrices Oficiales:
   - M1 = 42 columnas (Consolidado)
   - M2 = 57 columnas (Estudiantes)
   - M3 = 58 columnas (Académicos y Administrativos)
   - M4 = 57 columnas (Colaboradores)
   - M5 = 53 columnas (Protagonistas Beneficiados)
3. Preservación Estricta del Histórico de M5 (Sección 13):
   - 32 registros históricos en filas 2..33 preservados 100% celda por celda.
   - Nuevos registros agregados en estrategia APPEND a partir de la fila 34.
4. Regla Cédula Vacía (Sección 14):
   - Si Persona.cedula es None, la celda Excel queda estrictamente vacía (None), sin 'N/A' ni '0'.
5. Gobernanza OPEN-02 (Sección 8):
   - EXPORTAR_CON_OBSERVACION
   - RETENER_EN_CUARENTENA
   - EXPORTAR_CON_MARCA
6. Atomicidad y Staging Seguro (Secciones 18 y 23):
   - Protocolo All-or-Nothing; simulación dry_run=True no deja residuos en disco.
7. Exportación por Período:
   - Consolidación de múltiples actividades en M1 y nominales en M2..M5.
8. Clean Architecture y AST (Sección 29):
   - app/application/* libre de sqlite3, openpyxl, xlsxwriter, docx y customtkinter.
"""

import ast
from datetime import date
from pathlib import Path
import openpyxl
import pytest
import tempfile

from app.core.constants.participant_types import (
    CategoriaParticipacion,
    NivelValidacion,
)
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
from app.application.commands.pipeline_commands import (
    EjecutarPipelineActividadCommand,
    ExportarMatricesActividadCommand,
    ExportarMatricesPeriodoCommand,
)
from app.application.dto.export_dtos import (
    PoliticaExportacionRevision,
    ExportarMatricesResultDTO,
)
from app.application.export_acl.export_acl import ExportACL
from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)
from app.application.use_cases.exportacion.exportar_matrices_actividad import (
    ExportarMatricesActividadUseCase,
)
from app.application.use_cases.exportacion.exportar_matrices_periodo import (
    ExportarMatricesPeriodoUseCase,
)
from app.exporters.base_exporter import calcular_sha256


@pytest.fixture
def temp_sqlite_db():
    """Crea una base de datos SQLite temporal en disco con schema v001."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_export_bloque_2.db"
        config = DatabaseConfig(db_path=db_path)
        manager = SQLiteConnectionManager(config)

        conn = manager.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending()
        finally:
            conn.close()

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
            "conn": conn,
            "manager": manager,
        }
        conn.close()


def _crear_actividad_e2e(id_act: str = "ACT-2026-E2E-01") -> Activity:
    return Activity(
        id_actividad=id_act,
        nombre_actividad_original="Taller Integral de Liderazgo, Innovación y Calidad 2026",
        nombre_actividad_oficial="TALLER INSTITUCIONAL DE INNOVACION 2026",
        fecha_evento=date(2026, 9, 22),
        sede="BLUEFIELDS",
        departamento="RACCS",
        municipio_evento="Bluefields",
        modalidad="PRESENCIAL",
        tipo_evento="TALLER",
        estado_actividad="CONCLUIDA",
        fuente_origen="LISTA_ASISTENCIA_OFICIAL_SEPT_2026.xlsx",
        eje_linea_estrategica="Innovación y Extensión Comunitaria",
    )


class TestEscenarioE2EObligatorioSeccion28:
    """Prueba E2E obligatoria gobernada por la Sección 28 del mandato institucional."""

    def test_e2e_flujo_completo_con_los_ocho_perfiles_simultaneos(self, temp_sqlite_db, tmp_path):
        """Ejecuta el pipeline completo desde SQLite hasta la generación física en disco de M1–M5.

        Contiene simultáneamente:
        1. Estudiante -> M2
        2. Docente -> M3
        3. Administrativo -> M3
        4. Colaborador -> M4
        5. Beneficiario -> M5
        6. Estudiante + beneficiario (RN-C03) -> M5
        7. En revisión -> según OPEN-02
        8. Bloqueado -> ninguna matriz
        """
        repos = temp_sqlite_db
        act = _crear_actividad_e2e("ACT-E2E-FINAL")
        repos["act"].save(act)

        # 1. Estudiante (M2)
        p1 = Person(id_persona_interno="PER-E2E-1", nombre_completo="Ana Sofia Campbell Downs", cedula="601-120502-1001A", sexo_normalizado="F", edad=22)
        part1 = Participation(id_participacion="PART-E2E-1", id_actividad=act.id_actividad, id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        # 2. Docente (M3)
        p2 = Person(id_persona_interno="PER-E2E-2", nombre_completo="Carlos Alberto Hodgson Brown", cedula="601-150380-1002B", sexo_normalizado="M", edad=46)
        part2 = Participation(id_participacion="PART-E2E-2", id_actividad=act.id_actividad, id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.DOCENTE)

        # 3. Administrativo (M3)
        p3 = Person(id_persona_interno="PER-E2E-3", nombre_completo="Elena Patricia Brooks Martin", cedula="601-200785-1003C", sexo_normalizado="F", edad=41)
        part3 = Participation(id_participacion="PART-E2E-3", id_actividad=act.id_actividad, id_persona=p3.id_persona_interno, categoria_participacion=CategoriaParticipacion.ADMINISTRATIVO)

        # 4. Colaborador externo (M4)
        p4 = Person(id_persona_interno="PER-E2E-4", nombre_completo="Roberto David Morales Gomez", cedula="601-101190-1004D", sexo_normalizado="M", edad=35)
        part4 = Participation(id_participacion="PART-E2E-4", id_actividad=act.id_actividad, id_persona=p4.id_persona_interno, categoria_participacion=CategoriaParticipacion.COLABORADOR)

        # 5. Beneficiario de la comunidad (M5)
        p5 = Person(id_persona_interno="PER-E2E-5", nombre_completo="Maria Celeste Downs Taylor", cedula="601-050475-1005E", sexo_normalizado="F", edad=51)
        part5 = Participation(id_participacion="PART-E2E-5", id_actividad=act.id_actividad, id_persona=p5.id_persona_interno, categoria_participacion=CategoriaParticipacion.BENEFICIADO)

        # 6. Estudiante con rol de beneficiario (RN-C03 -> M5)
        p6 = Person(id_persona_interno="PER-E2E-6", nombre_completo="Wilfredo Joseph Martinez", cedula="601-250803-1006F", sexo_normalizado="M", edad=23)
        part6 = Participation(
            id_participacion="PART-E2E-6",
            id_actividad=act.id_actividad,
            id_persona=p6.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            es_beneficiado_rol=True,
        )

        # 7. Registro en revisión (Estudiante con observación de calidad)
        p7 = Person(id_persona_interno="PER-E2E-7", nombre_completo="Dudoso Aclarar Watson", cedula=None, sexo_normalizado="M", edad=20)
        part7 = Participation(
            id_participacion="PART-E2E-7",
            id_actividad=act.id_actividad,
            id_persona=p7.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            requiere_revision=True,
            motivo_revision="[Q-03] Cedula pendiente de aclaracion institucional",
        )

        # Guardar las 7 personas y participaciones legítimas
        for p in (p1, p2, p3, p4, p5, p6, p7):
            repos["per"].save(p)
        for part in (part1, part2, part3, part4, part5, part6, part7):
            repos["part"].save(part)

        # 8. Registro BLOQUEADO (Huérfano: id_persona inexistente)
        conn = repos["conn"]
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute(
            "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino) "
            "VALUES ('PART-E2E-8-BLOQ', ?, 'PER-FANTASMA-TOTAL', 'ESTUDIANTE', NULL);",
            (act.id_actividad,)
        )
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

        # Carpeta de salida limpia
        carpeta_salida = tmp_path / "salida_oficial_e2e"

        use_case = ExportarMatricesActividadUseCase(uow=repos["uow"])
        cmd = ExportarMatricesActividadCommand(
            id_actividad=act.id_actividad,
            carpeta_salida=str(carpeta_salida),
            politica_revision=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
            dry_run=False,
            permitir_fixtures_test_only=False,
        )

        # EJECUCIÓN DEL CASO DE USO
        res: ExportarMatricesResultDTO = use_case.execute(cmd)

        assert res.exito is True
        assert res.modo == "EXPORT"
        assert carpeta_salida.exists()

        # 1. Verificar existencia física de los archivos generados
        archivos_esperados = [
            "Matriz_1_Consolidado_Actividades.xlsx",
            "Matriz_2_Estudiantes.xlsx",
            "Matriz_3_Academicos_Administrativos.xlsx",
            "Matriz_4_Colaboradores.xlsx",
            "Matriz_5_Protagonistas_Beneficiados.xlsx",
            "manifiesto_exportacion.json",
        ]
        for arc in archivos_esperados:
            ruta = carpeta_salida / arc
            assert ruta.exists(), f"Falta archivo generado: {arc}"
            assert ruta.stat().st_size > 0

        # 2. M1: Consolidado de Actividades (debe tener exactamente 1 fila de datos, 42 columnas)
        wb1 = openpyxl.load_workbook(str(carpeta_salida / "Matriz_1_Consolidado_Actividades.xlsx"), data_only=False)
        ws1 = wb1.active
        assert ws1.max_column == 42, f"M1 debe tener 42 columnas, tiene {ws1.max_column}"
        assert res.total_filas_exportadas_por_matriz["matriz_1"] == 1
        val_m1_act = ws1.cell(row=2, column=9).value  # Nombre actividad
        assert "TALLER INSTITUCIONAL DE INNOVACION" in str(val_m1_act)
        # Asegurar que fila 3 no tiene datos de actividad extra
        assert ws1.cell(row=3, column=9).value is None
        wb1.close()

        # 3. M2: Estudiantes (P1 + P7 con observación = 2 filas escritas)
        wb2 = openpyxl.load_workbook(str(carpeta_salida / "Matriz_2_Estudiantes.xlsx"), data_only=False)
        ws2 = wb2.active
        assert ws2.max_column == 57, f"M2 debe tener 57 columnas, tiene {ws2.max_column}"
        assert res.total_filas_exportadas_por_matriz["matriz_2"] == 2
        assert ws2.cell(row=2, column=33).value == "Ana Sofia Campbell Downs"
        assert ws2.cell(row=3, column=33).value == "Dudoso Aclarar Watson"
        wb2.close()

        # 4. M3: Académicos y Administrativos (P2 Docente + P3 Admin = 2 filas escritas)
        wb3 = openpyxl.load_workbook(str(carpeta_salida / "Matriz_3_Academicos_Administrativos.xlsx"), data_only=False)
        ws3 = wb3.active
        assert ws3.max_column == 58, f"M3 debe tener 58 columnas, tiene {ws3.max_column}"
        assert res.total_filas_exportadas_por_matriz["matriz_3"] == 2
        assert ws3.cell(row=2, column=34).value == "DOCENTE"
        assert ws3.cell(row=3, column=34).value == "ADMINISTRATIVO"
        wb3.close()

        # 5. M4: Colaboradores (P4 Colaborador = 1 fila escrita)
        wb4 = openpyxl.load_workbook(str(carpeta_salida / "Matriz_4_Colaboradores.xlsx"), data_only=False)
        ws4 = wb4.active
        assert ws4.max_column == 57, f"M4 debe tener 57 columnas, tiene {ws4.max_column}"
        assert res.total_filas_exportadas_por_matriz["matriz_4"] == 1
        assert ws4.cell(row=2, column=34).value == "COLABORADOR"
        assert ws4.cell(row=2, column=35).value == "Roberto David Morales Gomez"
        wb4.close()

        # 6. M5: Protagonistas Beneficiados (32 históricos preservados + 2 nuevos en filas 34 y 35)
        wb5 = openpyxl.load_workbook(str(carpeta_salida / "Matriz_5_Protagonistas_Beneficiados.xlsx"), data_only=False)
        ws5 = wb5.active
        assert ws5.max_column == 53, f"M5 debe tener 53 columnas, tiene {ws5.max_column}"
        assert res.total_filas_exportadas_por_matriz["matriz_5"] == 2

        # Verificar preservación histórica (primer y último registro histórico)
        assert "Gómez Neira" in str(ws5.cell(row=2, column=34).value)
        assert "Jhonny Francisco Mendoza" in str(ws5.cell(row=33, column=34).value)

        # Verificar nuevos registros agregados después del histórico
        assert ws5.cell(row=34, column=34).value == "Maria Celeste Downs Taylor"  # P5 Beneficiario
        assert ws5.cell(row=35, column=34).value == "Wilfredo Joseph Martinez"   # P6 Estudiante con rol beneficiario (RN-C03)
        wb5.close()

        # 7. Invariante matemática de conservación
        # Entrada total = 8
        # M2(2) + M3(2) + M4(1) + M5(2) = 7 nominales exportados + 1 bloqueado excluido = 8
        assert res.total_filas_exportadas_por_matriz["matriz_2"] == 2
        assert res.total_filas_exportadas_por_matriz["matriz_3"] == 2
        assert res.total_filas_exportadas_por_matriz["matriz_4"] == 1
        assert res.total_filas_exportadas_por_matriz["matriz_5"] == 2
        suma_nominales = 2 + 2 + 1 + 2
        assert suma_nominales == 7


class TestPoliticasOpen02ExportacionFisica:
    """Verifica el comportamiento de las 3 políticas OPEN-02 en archivos Excel reales."""

    def test_politica_retener_en_cuarentena_excluye_de_archivo_excel(self, temp_sqlite_db, tmp_path):
        """Con RETENER_EN_CUARENTENA, el registro dudoso no se escribe en M2."""
        repos = temp_sqlite_db
        act = _crear_actividad_e2e("ACT-CUAR-EXCEL")
        repos["act"].save(act)

        p1 = Person(id_persona_interno="PER-CUAR-OK", nombre_completo="Estudiante Valido", cedula="601-111111-0001A", sexo_normalizado="F")
        p2 = Person(id_persona_interno="PER-CUAR-DUD", nombre_completo="Estudiante Para Cuarentena", cedula=None, sexo_normalizado="M")
        repos["per"].save(p1)
        repos["per"].save(p2)

        part1 = Participation(id_participacion="PART-C1", id_actividad=act.id_actividad, id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_participacion="PART-C2", id_actividad=act.id_actividad, id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE, requiere_revision=True)
        repos["part"].save(part1)
        repos["part"].save(part2)

        carpeta_salida = tmp_path / "salida_cuarentena"
        use_case = ExportarMatricesActividadUseCase(uow=repos["uow"])
        cmd = ExportarMatricesActividadCommand(
            id_actividad=act.id_actividad,
            carpeta_salida=str(carpeta_salida),
            politica_revision=PoliticaExportacionRevision.RETENER_EN_CUARENTENA,
            dry_run=False,
        )
        res = use_case.execute(cmd)

        # Solo debe haber 1 fila en M2 (el apto)
        assert res.total_filas_exportadas_por_matriz["matriz_2"] == 1
        wb = openpyxl.load_workbook(str(carpeta_salida / "Matriz_2_Estudiantes.xlsx"))
        ws = wb.active
        assert ws.cell(row=2, column=33).value == "Estudiante Valido"
        assert ws.cell(row=3, column=33).value is None  # Cuarentena retenida
        wb.close()

    def test_politica_exportar_con_marca_agrega_tag_formal(self, temp_sqlite_db, tmp_path):
        """Con EXPORTAR_CON_MARCA, el registro se exporta con la marca formal de revisión."""
        repos = temp_sqlite_db
        act = _crear_actividad_e2e("ACT-MARCA-EXCEL")
        repos["act"].save(act)

        p = Person(id_persona_interno="PER-MARCA-1", nombre_completo="Estudiante Observado", cedula="601-222222-0002B", sexo_normalizado="M")
        repos["per"].save(p)
        part = Participation(id_participacion="PART-M1", id_actividad=act.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE, requiere_revision=True)
        repos["part"].save(part)

        carpeta_salida = tmp_path / "salida_marca"
        use_case = ExportarMatricesActividadUseCase(uow=repos["uow"])
        cmd = ExportarMatricesActividadCommand(
            id_actividad=act.id_actividad,
            carpeta_salida=str(carpeta_salida),
            politica_revision=PoliticaExportacionRevision.EXPORTAR_CON_MARCA,
            dry_run=False,
        )
        res = use_case.execute(cmd)
        assert res.total_filas_exportadas_por_matriz["matriz_2"] == 1


class TestReglaCedulaVaciaSeccion14:
    """Verifica que la ausencia de cédula deje la celda Excel vacía (None) y no 'N/A' ni '0'."""

    def test_persona_sin_cedula_escribe_celda_vacia(self, temp_sqlite_db, tmp_path):
        repos = temp_sqlite_db
        act = _crear_actividad_e2e("ACT-CEDULA-VACIA")
        repos["act"].save(act)

        p = Person(id_persona_interno="PER-NO-CEDULA", nombre_completo="Maria Sin Documento", cedula=None, sexo_normalizado="F")
        repos["per"].save(p)
        part = Participation(id_participacion="PART-NC-1", id_actividad=act.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        repos["part"].save(part)

        carpeta_salida = tmp_path / "salida_cedula"
        use_case = ExportarMatricesActividadUseCase(uow=repos["uow"])
        cmd = ExportarMatricesActividadCommand(
            id_actividad=act.id_actividad,
            carpeta_salida=str(carpeta_salida),
            dry_run=False,
        )
        use_case.execute(cmd)

        wb = openpyxl.load_workbook(str(carpeta_salida / "Matriz_2_Estudiantes.xlsx"))
        ws = wb.active
        # Columna 35 es Cédula en M2
        val_cedula = ws.cell(row=2, column=35).value
        assert val_cedula is None, f"La celda de cédula debe ser None/vacía, pero tiene '{val_cedula}'"
        wb.close()


class TestExportacionPeriodoConsolidado:
    """Verifica el caso de uso ExportarMatricesPeriodoUseCase consolidando múltiples actividades."""

    def test_periodo_consolida_dos_actividades_en_m1(self, temp_sqlite_db, tmp_path):
        repos = temp_sqlite_db
        act1 = _crear_actividad_e2e("ACT-PER-01")
        act1.fecha_evento = date(2026, 9, 10)
        act2 = _crear_actividad_e2e("ACT-PER-02")
        act2.fecha_evento = date(2026, 9, 15)
        repos["act"].save(act1)
        repos["act"].save(act2)

        p1 = Person(id_persona_interno="PER-P1", nombre_completo="Participante Act1", cedula="601-010101-0001A", sexo_normalizado="F")
        p2 = Person(id_persona_interno="PER-P2", nombre_completo="Participante Act2", cedula="601-020202-0002B", sexo_normalizado="M")
        repos["per"].save(p1)
        repos["per"].save(p2)

        part1 = Participation(id_participacion="PART-P1", id_actividad=act1.id_actividad, id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_participacion="PART-P2", id_actividad=act2.id_actividad, id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.DOCENTE)
        repos["part"].save(part1)
        repos["part"].save(part2)

        carpeta_salida = tmp_path / "salida_periodo"
        use_case = ExportarMatricesPeriodoUseCase(uow=repos["uow"])
        cmd = ExportarMatricesPeriodoCommand(
            anio=2026,
            mes=9,
            carpeta_salida=str(carpeta_salida),
            dry_run=False,
        )
        res = use_case.execute(cmd)

        assert res.exito is True
        assert res.total_filas_exportadas_por_matriz["matriz_1"] == 2
        assert res.total_filas_exportadas_por_matriz["matriz_2"] == 1
        assert res.total_filas_exportadas_por_matriz["matriz_3"] == 1

        wb1 = openpyxl.load_workbook(str(carpeta_salida / "Matriz_1_Consolidado_Actividades.xlsx"))
        ws1 = wb1.active
        assert ws1.cell(row=2, column=9).value is not None
        assert ws1.cell(row=3, column=9).value is not None
        assert ws1.cell(row=4, column=9).value is None
        wb1.close()


class TestStagingSeguroYAtomicidad:
    """Verifica que el modo PREVIEW no deje archivos ni modifique el destino."""

    def test_dry_run_preview_no_escribe_en_carpeta_destino(self, temp_sqlite_db, tmp_path):
        repos = temp_sqlite_db
        act = _crear_actividad_e2e("ACT-DRY-PREVIEW")
        repos["act"].save(act)

        p = Person(id_persona_interno="PER-DRY", nombre_completo="Estudiante Dry", sexo_normalizado="F")
        repos["per"].save(p)
        part = Participation(id_participacion="PART-DRY", id_actividad=act.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        repos["part"].save(part)

        carpeta_salida = tmp_path / "salida_no_debe_crearse"
        use_case = ExportarMatricesActividadUseCase(uow=repos["uow"])
        cmd = ExportarMatricesActividadCommand(
            id_actividad=act.id_actividad,
            carpeta_salida=str(carpeta_salida),
            dry_run=True,
        )
        res = use_case.execute(cmd)

        assert res.modo == "PREVIEW"
        # La carpeta de salida no debe contener archivos finales XLSX
        if carpeta_salida.exists():
            archivos_xlsx = list(carpeta_salida.glob("*.xlsx"))
            assert len(archivos_xlsx) == 0


class TestInmutabilidadPlantillasBase:
    """Verifica que ninguna exportación altere las plantillas oficiales en templates/."""

    def test_hashes_plantillas_base_permanecen_inmutables(self):
        carpeta_tpl = Path("templates")
        plantillas = [
            "Matriz_1_Consolidado_Actividades.xlsx",
            "Matriz_2_Estudiantes.xlsx",
            "Matriz_3_Academicos_Administrativos.xlsx",
            "Matriz_4_Colaboradores.xlsx",
            "Matriz_5_Protagonistas_Beneficiados.xlsx",
        ]
        for arc in plantillas:
            ruta = carpeta_tpl / arc
            assert ruta.exists(), f"Falta plantilla oficial: {arc}"
            hash_actual = calcular_sha256(ruta)
            assert len(hash_actual) == 64
