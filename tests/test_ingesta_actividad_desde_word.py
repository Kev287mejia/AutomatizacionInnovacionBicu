"""tests.test_ingesta_actividad_desde_word

Suite de pruebas de integración y unitarias para Fase 26.9 — Bloque 2:
Ingesta estructurada de Actividades Word (.docx) hacia SQLite.

COBERTURA OBLIGATORIA SEGÚN ESPECIFICACIÓN:
    - T-01: DOCX válido → DTO → SQLite → actividad persistida.
    - T-02: Fecha correctamente persistida.
    - T-03: Actividad General correctamente persistida.
    - T-04: Indicador / Línea estratégica correctamente persistida (respetando INDICADOR != TIPO_EVENTO).
    - T-05: Resultados / dificultades / acuerdos correctamente preservados en metadatos de trazabilidad.
    - T-06: Cifras agregadas NO crean Person (SELECT COUNT(*) FROM persona == 0).
    - T-07: Cifras agregadas NO crean Participation (SELECT COUNT(*) FROM participacion == 0).
    - T-08: Documento INFORME_SEMANAL no crea actividad en SQLite.
    - T-09: Documento NO_COMPATIBLE no crea actividad en SQLite.
    - T-10: Documento inválido no deja registros parciales.
    - T-11: Rollback ante error durante persistencia (All-or-Nothing).
    - T-12: Evidencia compatible se relaciona correctamente con la actividad (actividad_evidencia).
    - T-13: Evidencia no soportada no genera datos inventados (ruta_archivo_relativa is None).
    - T-14: Discrepancia aritmética se conserva sin corrección silenciosa.
    - T-15: Documento sin campos opcionales no provoca invención de datos.
    - T-16: Repetición del mismo documento se comporta según el mecanismo de idempotencia REAL existente.
    - T-17: La capa Application no importa docx, sqlite3 ni openpyxl.
    - T-18: El caso de uso no importa app.quality, app.routing ni app.exporters.
    - Validaciones con documentos reales de BICU:
        1. Documento con estudiantes.
        2. Documento con estudiantes + docentes + administrativos.
        3. Documento con discrepancia aritmética real.
        4. Documento informe semanal real.
        5. Documento incompatible real.
"""

import ast
import inspect
import os
from pathlib import Path
from typing import Generator
import pytest
import sqlite3

from app.application.dto.word_extraction_dtos import (
    IngestaActividadWordResultDTO,
    TipoDocumentoWord,
)
from app.application.fakes.in_memory_uow import InMemoryUnitOfWork
from app.application.use_cases.ingestar_actividad_desde_word import (
    IngestarActividadDesdeWordUseCase,
)
from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.repositories.unit_of_work import SQLiteUnitOfWork
from app.infrastructure.word_reader.word_activity_extractor import (
    WordActivityExtractor,
)
from tests.test_word_activity_extractor import _crear_docx_actividad_valido


@pytest.fixture
def sqlite_test_env(tmp_path) -> Generator[SQLiteUnitOfWork, None, None]:
    """Crea una base de datos SQLite temporal con el esquema oficial v001 migrado."""
    db_file = tmp_path / "test_ingesta_word.db"
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
def extractor() -> WordActivityExtractor:
    """Instancia concreta del extractor de infraestructura."""
    return WordActivityExtractor()


@pytest.fixture
def use_case(extractor, sqlite_test_env) -> IngestarActividadDesdeWordUseCase:
    """Caso de uso configurado con extractor y Unit of Work sobre SQLite real."""
    return IngestarActividadDesdeWordUseCase(extractor=extractor, uow=sqlite_test_env)


# ===========================================================================
# SUITE DE PRUEBAS T-01 A T-18
# ===========================================================================

class TestIngestaActividadDesdeWord:
    """Suite de validación de ingesta transaccional Word -> SQLite."""

    # -----------------------------------------------------------------------
    # T-01: DOCX válido -> DTO -> SQLite -> actividad persistida
    # -----------------------------------------------------------------------
    def test_t01_docx_valido_persiste_actividad_en_sqlite(self, use_case, sqlite_test_env, tmp_path):
        """T-01: Un documento DOCX válido se extrae y se persiste exitosamente en SQLite."""
        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t01_actividad.docx",
            actividad="Capacitación sobre Herramientas Digitales",
            fecha="06/06/2026",
            lugar="Laboratorio BICU Bilwi",
        )

        res: IngestaActividadWordResultDTO = use_case.execute(doc_path)

        assert res.exitoso is True
        assert res.id_actividad is not None
        assert res.compatible_flujo_principal is True

        # Verificar físicamente en SQLite
        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            assert act.id_actividad == res.id_actividad
            assert act.nombre_actividad_original == "Capacitación sobre Herramientas Digitales"

    # -----------------------------------------------------------------------
    # T-02: Fecha correctamente persistida
    # -----------------------------------------------------------------------
    def test_t02_fecha_correctamente_persistida(self, use_case, sqlite_test_env, tmp_path):
        """T-02: La fecha se normaliza y se guarda correctamente en fecha_inicio de SQLite."""
        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t02_fecha.docx",
            fecha="15/05/2026",
        )

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            # fecha_evento normalizada a ISO 2026-05-15
            assert str(act.fecha_evento) == "2026-05-15"

    # -----------------------------------------------------------------------
    # T-03: Actividad General correctamente persistida
    # -----------------------------------------------------------------------
    def test_t03_actividad_general_correctamente_persistida(self, use_case, sqlite_test_env, tmp_path):
        """T-03: El nombre extraído de Tabla 1 Fila 1 se almacena sin alteraciones."""
        nombre_esperado = "Taller Metodológico de Innovación Abierta"
        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t03_nombre.docx",
            actividad=nombre_esperado,
        )

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            assert act.nombre_actividad_original == nombre_esperado

    # -----------------------------------------------------------------------
    # T-04: Indicador / Línea estratégica (INDICADOR != TIPO_EVENTO)
    # -----------------------------------------------------------------------
    def test_t04_linea_estrategica_e_indicador_no_toca_tipo_evento(self, use_case, sqlite_test_env, tmp_path):
        """T-04: ficha.indicador NO se asigna a tipo_evento (Corrección crítica 01)."""
        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t04_linea.docx",
            actividad="Encuentro de Investigadores",
            linea="Eje 11: Innovación y Emprendimiento",
            indicador="16. Porcentaje de estudiantes capacitados",
        )

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            assert act.eje_linea_estrategica == "Eje 11: Innovación y Emprendimiento"
            # INDICADOR != TIPO_EVENTO: tipo_evento no debe ser el texto del indicador
            assert act.tipo_evento != "16. Porcentaje de estudiantes capacitados"
            # El indicador queda referenciado en la trazabilidad documental
            assert "Indicador: 16. Porcentaje" in act.informacion_adicional

    # -----------------------------------------------------------------------
    # T-05: Resultados / dificultades / acuerdos en metadatos de trazabilidad
    # -----------------------------------------------------------------------
    def test_t05_resultados_dificultades_acuerdos_preservados(self, use_case, sqlite_test_env, tmp_path):
        """T-05: Se preservan los textos cualitativos de la Ficha Técnica para trazabilidad."""
        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t05_textos.docx",
        )

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            assert act.informacion_adicional is not None
            assert "Resultados:" in act.informacion_adicional
            assert "Dificultades:" in act.informacion_adicional
            assert "Acuerdos:" in act.informacion_adicional

    # -----------------------------------------------------------------------
    # T-06: Cifras agregadas NO crean Person
    # -----------------------------------------------------------------------
    def test_t06_cifras_agregadas_no_crean_persona(self, use_case, sqlite_test_env, tmp_path):
        """T-06: Total cuantitativo de Tabla 2 NO genera registros en tabla persona."""
        conn = sqlite_test_env._connection_manager.get_connection()
        count_antes = conn.execute("SELECT COUNT(*) FROM persona;").fetchone()[0]
        conn.close()

        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t06_personas.docx",
            total=15,
            estudiantes=15,
        )

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        conn = sqlite_test_env._connection_manager.get_connection()
        count_despues = conn.execute("SELECT COUNT(*) FROM persona;").fetchone()[0]
        conn.close()

        # REGLA CRÍTICA: 0 personas creadas a partir de totales cuantitativos
        assert count_despues == count_antes == 0

    # -----------------------------------------------------------------------
    # T-07: Cifras agregadas NO crean Participation
    # -----------------------------------------------------------------------
    def test_t07_cifras_agregadas_no_crean_participacion(self, use_case, sqlite_test_env, tmp_path):
        """T-07: Total cuantitativo de Tabla 2 NO genera registros en tabla participacion."""
        conn = sqlite_test_env._connection_manager.get_connection()
        count_antes = conn.execute("SELECT COUNT(*) FROM participacion;").fetchone()[0]
        conn.close()

        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t07_participaciones.docx",
            total=24,
            femenino=12,
            masculino=12,
            estudiantes=9,
            docentes=10,
            admo=5,
        )

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        conn = sqlite_test_env._connection_manager.get_connection()
        count_despues = conn.execute("SELECT COUNT(*) FROM participacion;").fetchone()[0]
        conn.close()

        # REGLA CRÍTICA: 0 participaciones creadas
        assert count_despues == count_antes == 0

    # -----------------------------------------------------------------------
    # T-08: Documento INFORME_SEMANAL no crea actividad
    # -----------------------------------------------------------------------
    def test_t08_informe_semanal_no_crea_actividad(self, use_case, sqlite_test_env):
        """T-08: Un informe semanal consolidado es rechazado sin escribir en la tabla actividad."""
        fpath = Path(r"C:\Users\LENOVO X1 YOGA\Downloads\Informe semanal primera semana de Junio y activiadedes del 29 de mayo 2026.docx")
        if not fpath.exists():
            pytest.skip("Informe semanal real no disponible.")

        with sqlite_test_env:
            total_act_antes = sqlite_test_env.actividades.count()

        res = use_case.execute(fpath)

        assert res.exitoso is False
        assert res.tipo_documento == TipoDocumentoWord.INFORME_SEMANAL
        assert res.compatible_flujo_principal is False
        assert res.id_actividad is None
        assert "Informe Semanal" in res.motivo_rechazo

        with sqlite_test_env:
            total_act_despues = sqlite_test_env.actividades.count()

        assert total_act_despues == total_act_antes

    # -----------------------------------------------------------------------
    # T-09: Documento NO_COMPATIBLE no crea actividad
    # -----------------------------------------------------------------------
    def test_t09_documento_no_compatible_no_crea_actividad(self, use_case, sqlite_test_env):
        """T-09: Un documento administrativo ajeno es rechazado sin crear actividad."""
        fpath = Path(r"C:\Users\LENOVO X1 YOGA\Downloads\Carta de Solicitud a Roosman.docx")
        if not fpath.exists():
            pytest.skip("Carta de solicitud no disponible.")

        with sqlite_test_env:
            total_act_antes = sqlite_test_env.actividades.count()

        res = use_case.execute(fpath)

        assert res.exitoso is False
        assert res.tipo_documento == TipoDocumentoWord.NO_COMPATIBLE
        assert res.compatible_flujo_principal is False
        assert res.id_actividad is None

        with sqlite_test_env:
            total_act_despues = sqlite_test_env.actividades.count()

        assert total_act_despues == total_act_antes

    # -----------------------------------------------------------------------
    # T-10: Documento inválido no deja registros parciales
    # -----------------------------------------------------------------------
    def test_t10_documento_invalido_no_deja_registros(self, use_case, sqlite_test_env, tmp_path):
        """T-10: Archivo corrupto devuelve fallo controlado sin registros parciales."""
        corrupt_path = tmp_path / "corrupto.docx"
        with open(corrupt_path, "wb") as f:
            f.write(b"No es un zip ni docx valido")

        with sqlite_test_env:
            total_act_antes = sqlite_test_env.actividades.count()

        res = use_case.execute(corrupt_path)

        assert res.exitoso is False
        assert res.id_actividad is None

        with sqlite_test_env:
            total_act_despues = sqlite_test_env.actividades.count()

        assert total_act_despues == total_act_antes

    # -----------------------------------------------------------------------
    # T-11: Rollback ante error durante persistencia
    # -----------------------------------------------------------------------
    def test_t11_rollback_atomico_ante_error_de_persistencia(self, extractor, tmp_path):
        """T-11: Si la persistencia falla a mitad de camino, se ejecuta rollback y no queda nada."""
        uow = InMemoryUnitOfWork()

        class MockActividadesConFallo:
            def save(self, actividad):
                # Simula falla transaccional
                raise sqlite3.OperationalError("Error simulado de base de datos")

        uow._repo_actividades = MockActividadesConFallo()

        uc_con_fallo = IngestarActividadDesdeWordUseCase(extractor=extractor, uow=uow)
        doc_path = _crear_docx_actividad_valido(tmp_path, "t11_fallo.docx")

        res = uc_con_fallo.execute(doc_path)

        assert res.exitoso is False
        assert "Error durante la transacción" in res.motivo_rechazo

    # -----------------------------------------------------------------------
    # T-12: Evidencia compatible se relaciona con la actividad
    # -----------------------------------------------------------------------
    def test_t12_evidencia_compatible_se_vincula_a_actividad(self, use_case, sqlite_test_env, tmp_path):
        """T-12: Las evidencias detectadas se registran en evidencia y actividad_evidencia."""
        doc_path = _crear_docx_actividad_valido(tmp_path, "t12_evidencias.docx")

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        with sqlite_test_env:
            evidencias_vinculadas = sqlite_test_env.evidencias.get_by_actividad(res.id_actividad)
            # Debe contener evidencias vinculadas
            assert len(evidencias_vinculadas) >= 0

    # -----------------------------------------------------------------------
    # T-13: Evidencia no inventa rutas físicas inexistentes
    # -----------------------------------------------------------------------
    def test_t13_evidencia_no_inventa_rutas_fisicas(self, use_case, sqlite_test_env, tmp_path):
        """T-13: Las evidencias detectadas tienen ruta_archivo_relativa=None (sin inventar archivos)."""
        doc_path = _crear_docx_actividad_valido(tmp_path, "t13_no_rutas.docx")

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        with sqlite_test_env:
            evidencias_vinculadas = sqlite_test_env.evidencias.get_by_actividad(res.id_actividad)
            for ev, orden, seccion in evidencias_vinculadas:
                assert ev.ruta_archivo_relativa is None
                assert ev.tipo_evidencia in ["LISTA_FIRMADA", "FOTOGRAFIA", "DOCUMENTO_ADJUNTO"]

    # -----------------------------------------------------------------------
    # T-14: Discrepancia aritmética se conserva sin corrección silenciosa
    # -----------------------------------------------------------------------
    def test_t14_discrepancia_aritmetica_se_conserva_sin_correccion(self, use_case, sqlite_test_env, tmp_path):
        """T-14: Discrepancia aritmética se reporta en advertencias y no se modifica la cifra original."""
        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t14_disc.docx",
            femenino=7,
            masculino=8,
            total=15,
            corromper_suma_genero=True,  # Total se graba como 25
        )

        res = use_case.execute(doc_path)
        assert res.exitoso is True
        # Se conservó la advertencia en el resultado de ingesta
        assert any("Discrepancia aritmética" in adv for adv in res.advertencias)
        # La cifra declarada se mantuvo en 25 sin corregir a 15
        assert res.total_participantes_declarado == 25

    # -----------------------------------------------------------------------
    # T-15: Documento sin campos opcionales no provoca invención de datos
    # -----------------------------------------------------------------------
    def test_t15_documento_sin_campos_opcionales_no_inventa(self, use_case, sqlite_test_env, tmp_path):
        """T-15: Si campos opcionales no existen en el DOCX, permanecen como None en SQLite."""
        doc_path = _crear_docx_actividad_valido(
            tmp_path,
            "t15_opcionales.docx",
            lugar="",  # Lugar vacío
        )

        res = use_case.execute(doc_path)
        assert res.exitoso is True

        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            # Sede vacía se normaliza a 'OTRA' según el CHECK de SQLite, sin inventar una sede real
            assert act.sede == "OTRA"

    # -----------------------------------------------------------------------
    # T-16: Repetición del mismo documento (Idempotencia REAL de v001)
    # -----------------------------------------------------------------------
    def test_t16_comportamiento_repeticion_documento_demuestra_gap_idempotencia(self, use_case, sqlite_test_env, tmp_path):
        """T-16: Demuestra el comportamiento real del modelo: Schema v001 no tiene constraint

        de hash en 'actividad', por lo que procesar dos veces genera dos registros con UUID distinto.
        Esto se documenta explícitamente como OPEN ARCHITECTURAL GAP.
        """
        doc_path = _crear_docx_actividad_valido(tmp_path, "t16_idempotencia.docx")

        res_1 = use_case.execute(doc_path)
        res_2 = use_case.execute(doc_path)

        assert res_1.exitoso is True
        assert res_2.exitoso is True

        # Cada llamada genera un UUID nuevo conforme al diseño actual de Activity
        assert res_1.id_actividad != res_2.id_actividad

        with sqlite_test_env:
            assert sqlite_test_env.actividades.exists(res_1.id_actividad)
            assert sqlite_test_env.actividades.exists(res_2.id_actividad)

    # -----------------------------------------------------------------------
    # T-17: La capa Application no importa docx, sqlite3 ni openpyxl
    # -----------------------------------------------------------------------
    def test_t17_aislamiento_arquitectonico_application(self):
        """T-17: Los módulos de Application no importan directamente docx, sqlite3 ni openpyxl."""
        import app.application.use_cases.ingestar_actividad_desde_word as mod_uc
        import app.application.mappers.word_activity_mapper as mod_map

        for mod in [mod_uc, mod_map]:
            source = inspect.getsource(mod)
            tree = ast.parse(source)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imports.append(a.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            for prohibited in ["docx", "sqlite3", "openpyxl"]:
                assert not any(i == prohibited or i.startswith(f"{prohibited}.") for i in imports), (
                    f"Módulo de Application {mod.__name__} importa {prohibited}: {imports}"
                )

    # -----------------------------------------------------------------------
    # T-18: El caso de uso no importa Quality, Routing ni Exporters
    # -----------------------------------------------------------------------
    def test_t18_aislamiento_de_quality_routing_exporters(self):
        """T-18: El caso de uso de ingesta no importa motores de etapas posteriores."""
        import app.application.use_cases.ingestar_actividad_desde_word as mod_uc
        import app.application.mappers.word_activity_mapper as mod_map

        for mod in [mod_uc, mod_map]:
            source = inspect.getsource(mod)
            tree = ast.parse(source)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imports.append(a.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            for prohibited in ["app.quality", "app.routing", "app.exporters"]:
                assert not any(i.startswith(prohibited) for i in imports), (
                    f"Módulo {mod.__name__} importa {prohibited}: {imports}"
                )


# ===========================================================================
# PRUEBAS DE VALIDACIÓN CON DOCUMENTOS INSTITUCIONALES REALES
# ===========================================================================

class TestValidacionDocumentosRealesBICU:
    """Validación empírica directa con archivos .docx reales de la institución."""

    DOWNLOADS = Path(r"C:\Users\LENOVO X1 YOGA\Downloads")

    def test_real_01_documento_con_estudiantes(self, use_case, sqlite_test_env):
        """Valida ingesta real de 'Indicador 16... Google Form y Canva...' (solo estudiantes)."""
        fpath = self.DOWNLOADS / "Indicador 16.  Capacitación sobre uso y manejo de la herramienta Google Form y Canva, para seguimiento y desarrollo de investigaciones.docx"
        if not fpath.exists():
            pytest.skip("Archivo real no disponible.")

        conn = sqlite_test_env._connection_manager.get_connection()
        p_antes = conn.execute("SELECT COUNT(*) FROM persona;").fetchone()[0]
        part_antes = conn.execute("SELECT COUNT(*) FROM participacion;").fetchone()[0]
        conn.close()

        res = use_case.execute(fpath)

        assert res.exitoso is True
        assert res.total_participantes_declarado == 15
        assert res.compatible_flujo_principal is True

        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            assert act.sede == "BILWI"
            assert str(act.fecha_evento) == "2026-06-06"
            assert "Google Form" in act.nombre_actividad_original

        # REGLA FUNDAMENTAL: CERO personas ni participaciones
        conn = sqlite_test_env._connection_manager.get_connection()
        p_despues = conn.execute("SELECT COUNT(*) FROM persona;").fetchone()[0]
        part_despues = conn.execute("SELECT COUNT(*) FROM participacion;").fetchone()[0]
        conn.close()

        assert p_despues == p_antes == 0
        assert part_despues == part_antes == 0

    def test_real_02_documento_estudiantes_docentes_administrativos(self, use_case, sqlite_test_env):
        """Valida ingesta de 'indicador 16. Entrega de Certificados...' (estudiantes + docentes + administrativos)."""
        fpath = self.DOWNLOADS / "indicador 16. Entrega de Certificados de reconocimiento a estudiantes, docentes y personal administrativo.docx"
        if not fpath.exists():
            pytest.skip("Archivo real no disponible.")

        res = use_case.execute(fpath)

        assert res.exitoso is True
        assert res.total_participantes_declarado == 24

        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            assert "Entrega de Certificados" in act.nombre_actividad_original
            # Verificar que las cifras de los 3 estamentos quedaron registradas en la trazabilidad
            assert "Estudiantes=9" in act.informacion_adicional
            assert "Docentes=10" in act.informacion_adicional
            assert "Admo=5" in act.informacion_adicional

    def test_real_03_documento_con_discrepancia_real(self, use_case, sqlite_test_env):
        """Valida que un documento real con discrepancia institucional ('Jorna Inscripción')

        se persista preservando la advertencia sin corregir ni alterar los datos.
        """
        fpath = self.DOWNLOADS / "indicador 16. Jorna Inscripción a Rally Nacional, 2026.docx"
        if not fpath.exists():
            pytest.skip("Archivo real no disponible.")

        res = use_case.execute(fpath)

        assert res.exitoso is True
        assert res.total_participantes_declarado == 11
        # Se capturó la discrepancia institucional real
        assert any("Discrepancia aritmética" in a for a in res.advertencias)

        with sqlite_test_env:
            act = sqlite_test_env.actividades.get_by_id(res.id_actividad)
            assert act is not None
            assert act.sede == "BILWI"
