"""
tests.test_word_consolidator.test_readers

Pruebas unitarias y de integración para el lector oficial no destructivo de las
cinco matrices Excel y el módulo de filtrado temporal (Fase 14.3).
Cubre los 20 requisitos obligatorios de lectura, validación, filtrado,
preservación de históricos y verificación de no modificación de fuentes.
"""

from datetime import date
import hashlib
import os
from pathlib import Path
import pytest

from app.word_consolidator.models import (
    ConjuntoMatricesLeidas,
    FilaLeidaM1,
    FilaLeidaNominal,
    PeriodoConsolidacion,
    TipoPeriodo,
)
from app.word_consolidator.readers.matrix_reader import MatrixReader
from app.word_consolidator.readers.period_filter import PeriodFilter


BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"


@pytest.fixture
def rutas_matrices_oficiales_output():
    """Retorna las rutas a las matrices con la corrida real de Septiembre 2026."""
    return {
        "M1": OUTPUT_DIR / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": OUTPUT_DIR / "Matriz_2_Estudiantes.xlsx",
        "M3": OUTPUT_DIR / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": OUTPUT_DIR / "Matriz_4_Colaboradores.xlsx",
        "M5": OUTPUT_DIR / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }


@pytest.fixture
def rutas_matrices_templates():
    """Retorna las rutas a las plantillas base en templates/."""
    return {
        "M1": TEMPLATES_DIR / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": TEMPLATES_DIR / "Matriz_2_Estudiantes.xlsx",
        "M3": TEMPLATES_DIR / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": TEMPLATES_DIR / "Matriz_4_Colaboradores.xlsx",
        "M5": TEMPLATES_DIR / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }


class TestLecturaMatricesIndividuales:
    """1 a 5: Lectura correcta de cada una de las 5 matrices."""

    def test_01_lectura_correcta_m1(self, rutas_matrices_oficiales_output):
        filas, fuente = MatrixReader.leer_matriz_1(rutas_matrices_oficiales_output["M1"])
        assert fuente.codigo_matriz == "M1"
        assert len(fuente.hash_sha256) == 64
        assert len(filas) == 1
        m1 = filas[0]
        assert "diseño de logotipos e inteligencia artificial" in m1.actividad.lower()
        assert m1.sede == "Bilwi"
        assert m1.total_atencion_m == 6   # Varones en Excel
        assert m1.total_atencion_f == 12  # Mujeres en Excel
        assert m1.gran_total_m1 == 18
        assert m1.fila == 2

    def test_02_lectura_correcta_m2(self, rutas_matrices_oficiales_output):
        filas, fuente = MatrixReader.leer_matriz_nominal(rutas_matrices_oficiales_output["M2"], "M2")
        assert fuente.codigo_matriz == "M2"
        assert len(filas) == 17
        nombres = [f.nombre_apellidos.lower() for f in filas]
        assert any("shana ruiz watson" in n for n in nombres)
        assert any("dadam ossiel mendoza" in n for n in nombres)
        assert all(f.matriz_origen == "M2" for f in filas)
        # Trazabilidad
        assert filas[0].trazabilidad["fila"] == 2
        assert filas[0].trazabilidad["matriz"] == "M2"

    def test_03_lectura_correcta_m3(self, rutas_matrices_oficiales_output):
        filas, fuente = MatrixReader.leer_matriz_nominal(rutas_matrices_oficiales_output["M3"], "M3")
        assert fuente.codigo_matriz == "M3"
        assert len(filas) == 1
        admin = filas[0]
        assert "elba wilson smith" in admin.nombre_apellidos.lower()
        assert admin.tipo_protagonistas == "ADMINISTRATIVO"
        assert admin.sede == "Bilwi"

    def test_04_lectura_correcta_m4(self, rutas_matrices_oficiales_output):
        filas, fuente = MatrixReader.leer_matriz_nominal(rutas_matrices_oficiales_output["M4"], "M4")
        assert fuente.codigo_matriz == "M4"
        # En la corrida de Septiembre no hubo colaboradores externos
        assert len(filas) == 0

    def test_05_lectura_correcta_m5_con_historicos(self, rutas_matrices_oficiales_output):
        filas, fuente = MatrixReader.leer_matriz_nominal(rutas_matrices_oficiales_output["M5"], "M5")
        assert fuente.codigo_matriz == "M5"
        # Los 32 registros históricos de El Rama / Bluefields deben leerse intactos
        assert len(filas) == 32
        sedes = {f.sede for f in filas}
        assert any("El Rama" in s for s in sedes)


class TestValidacionEstructuralYErrores:
    """6, 15, 16, 17: Validación de hojas, columnas y manejo de errores."""

    def test_06_validacion_de_hojas_y_columnas(self, rutas_matrices_templates):
        conjunto = MatrixReader.leer_conjunto_matrices(rutas_matrices_templates)
        assert "M1" in conjunto.fuentes
        assert "M2" in conjunto.fuentes
        assert "M3" in conjunto.fuentes
        assert "M4" in conjunto.fuentes
        assert "M5" in conjunto.fuentes
        assert conjunto.fuentes["M1"].hash_sha256 == "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad"

    def test_15_archivo_inexistente_lanza_error(self):
        with pytest.raises(FileNotFoundError):
            MatrixReader.leer_matriz_1(BASE_DIR / "no_existe_archivo.xlsx")

    def test_16_estructura_invalida_hoja_vacia(self, tmp_path):
        # Crear archivo Excel temporal vacío sin encabezados
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "HojaVacia"
        temp_file = tmp_path / "vacio.xlsx"
        wb.save(temp_file)
        wb.close()

        with pytest.raises(ValueError, match="está vacía o sin encabezados"):
            MatrixReader.leer_matriz_1(temp_file)

    def test_17_datos_incompletos_no_fallan_silenciosamente(self, rutas_matrices_oficiales_output):
        # Shana Ruiz y Dadam tienen cédula vacía o no normalizada en celda; se deben leer sin error
        filas, _ = MatrixReader.leer_matriz_nominal(rutas_matrices_oficiales_output["M2"], "M2")
        dadam = next(f for f in filas if "dadam" in f.nombre_apellidos.lower())
        assert dadam.no_cedula is None or dadam.no_cedula == ""
        # Preserva la fila y la carrera
        assert "sistemas" in str(dadam.carrera).lower()


class TestFiltradoTemporalPeriodFilter:
    """7 a 12: Filtrado por SEMANA, MES, TRIMESTRE, SEMESTRE, AÑO y PERSONALIZADO."""

    def test_07_filtrado_semana(self):
        p = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 7),
            etiqueta="Semana 1 Septiembre"
        )
        assert PeriodFilter.evaluar_fecha(date(2026, 9, 4), p) is True
        assert PeriodFilter.evaluar_fecha(date(2026, 9, 15), p) is False
        assert PeriodFilter.evaluar_fecha(date(2026, 8, 4), p) is False

    def test_08_filtrado_mes(self):
        p = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026"
        )
        assert PeriodFilter.evaluar_fecha(date(2026, 9, 20), p) is True
        assert PeriodFilter.evaluar_fecha(date(2026, 10, 1), p) is False

    def test_09_filtrado_trimestre(self):
        # T3: Julio (7), Agosto (8), Septiembre (9)
        p = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.TRIMESTRE,
            anio=2026,
            mes=9,
            etiqueta="Tercer Trimestre 2026"
        )
        assert PeriodFilter.evaluar_fecha(date(2026, 7, 10), p) is True
        assert PeriodFilter.evaluar_fecha(date(2026, 9, 30), p) is True
        assert PeriodFilter.evaluar_fecha(date(2026, 6, 30), p) is False  # T2

    def test_10_filtrado_semestre(self):
        # S2: Julio a Diciembre
        p = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMESTRE,
            anio=2026,
            mes=9,
            etiqueta="Segundo Semestre 2026"
        )
        assert PeriodFilter.evaluar_fecha(date(2026, 8, 15), p) is True
        assert PeriodFilter.evaluar_fecha(date(2026, 12, 1), p) is True
        assert PeriodFilter.evaluar_fecha(date(2026, 5, 1), p) is False  # S1

    def test_11_filtrado_anio(self):
        p = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.ANIO,
            anio=2026,
            etiqueta="Año 2026"
        )
        assert PeriodFilter.evaluar_fecha(date(2026, 1, 1), p) is True
        assert PeriodFilter.evaluar_fecha(date(2026, 12, 31), p) is True
        assert PeriodFilter.evaluar_fecha(date(2025, 12, 31), p) is False

    def test_12_filtrado_personalizado(self):
        p = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.PERSONALIZADO,
            anio=2026,
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 15),
            etiqueta="Primera Quincena Septiembre 2026"
        )
        assert PeriodFilter.evaluar_fecha(date(2026, 9, 10), p) is True
        assert PeriodFilter.evaluar_fecha(date(2026, 9, 16), p) is False


class TestCasoRealSeptiembreYPreservacionHistorica:
    """13, 14: Caso real Septiembre 2026 y preservación lógica de los 32 registros de M5."""

    def test_13_caso_real_septiembre_2026_periodo(self, rutas_matrices_oficiales_output):
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 - Semana 1"
        )
        conjunto, filtrado = MatrixReader.leer_y_filtrar(rutas_matrices_oficiales_output, periodo)

        # 1 actividad en M1
        assert len(filtrado.actividades_en_periodo) == 1
        assert "diseño de logotipos" in filtrado.actividades_en_periodo[0].actividad.lower()

        # 17 estudiantes en M2
        assert len(filtrado.estudiantes_en_periodo) == 17

        # 1 administrativo en M3
        assert len(filtrado.academicos_admin_en_periodo) == 1
        assert "elba wilson" in filtrado.academicos_admin_en_periodo[0].nombre_apellidos.lower()

        # 0 en M4
        assert len(filtrado.colaboradores_en_periodo) == 0

        # 0 nuevos en M5 para esta actividad
        assert len(filtrado.beneficiarios_en_periodo) == 0

        # Total nominales del período: 17 + 1 = 18
        assert filtrado.total_nominales_periodo == 18

    def test_14_preservacion_logica_32_registros_m5_fuera_periodo(self, rutas_matrices_oficiales_output):
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 - Semana 1"
        )
        _, filtrado = MatrixReader.leer_y_filtrar(rutas_matrices_oficiales_output, periodo)

        # Los 32 registros de M5 deben estar catalogados en nominales_historicos_fuera_periodo
        historicos_m5 = [r for r in filtrado.nominales_historicos_fuera_periodo if r.matriz_origen == "M5"]
        assert len(historicos_m5) == 32
        # Cero registros perdidos (las sedes reportadas son El Rama, Bluefields o no especificadas en celda)
        assert all(r.sede in ("BICU CUR El Rama", "BICU Bluefields", "No especificada") for r in historicos_m5)



class TestGarantiasDeNoModificacionYTrazabilidad:
    """18, 19, 20: Verificación de que nunca llama a save(), trazabilidad y no alteración."""

    def test_18_lector_abre_exclusivamente_read_only(self, rutas_matrices_oficiales_output, monkeypatch):
        # Monitorear openpyxl.Workbook.save para certificar que NUNCA es invocado
        import openpyxl.workbook.workbook
        def mock_save(*args, **kwargs):
            raise AssertionError("VIOLACIÓN DE INTEGRIDAD: Se intentó llamar a workbook.save()")

        monkeypatch.setattr(openpyxl.workbook.workbook.Workbook, "save", mock_save)

        # Ejecutar lectura completa
        conjunto = MatrixReader.leer_conjunto_matrices(rutas_matrices_oficiales_output)
        assert len(conjunto.actividades_m1) == 1

    def test_19_trazabilidad_matriz_hoja_fila(self, rutas_matrices_oficiales_output):
        conjunto = MatrixReader.leer_conjunto_matrices(rutas_matrices_oficiales_output)

        # Fila M1
        act = conjunto.actividades_m1[0]
        assert act.trazabilidad["matriz"] == "M1"
        assert act.trazabilidad["hoja"] == "Programas, proyectos y act"
        assert act.trazabilidad["fila"] == 2
        assert "Matriz_1" in act.trazabilidad["archivo"]

        # Filas M2
        est = conjunto.estudiantes_m2[0]
        assert est.trazabilidad["matriz"] == "M2"
        assert est.trazabilidad["hoja"] == "Pregrado_Grado en Actividades"
        assert est.trazabilidad["fila"] == 2

    def test_20_leer_no_modifica_hashes_de_archivos(self, rutas_matrices_templates):
        # 1. Calcular hashes iniciales
        hashes_antes = {
            code: hashlib.sha256(open(p, "rb").read()).hexdigest()
            for code, p in rutas_matrices_templates.items()
        }

        # 2. Ejecutar lectura completa de las 5 matrices
        conjunto = MatrixReader.leer_conjunto_matrices(rutas_matrices_templates)
        assert len(conjunto.fuentes) == 5

        # 3. Calcular hashes posteriores
        hashes_despues = {
            code: hashlib.sha256(open(p, "rb").read()).hexdigest()
            for code, p in rutas_matrices_templates.items()
        }

        # 4. Certificar igualdad bit a bit
        assert hashes_antes == hashes_despues
        assert hashes_despues["M1"] == "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad"
        assert hashes_despues["M5"] == "a3dff20ec209de209f59dd8b1ad1be84aa7aebd1536ced406c59453a08973dc3"
