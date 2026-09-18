"""
tests.test_word_consolidator.test_matrix_auto_identification

Suite de pruebas exhaustivas para la Identificación Automática Estructural de Matrices M1–M5.
Verifica que la clasificación no dependa de nombres de archivo, soporte selección en cualquier orden,
detecte matrices duplicadas, faltantes, archivos no reconocidos e inválidos,
y garantice la integridad del caso real de Septiembre 2026 y de los 32 registros históricos de M5.
"""

from datetime import date
import json
from pathlib import Path
import shutil
from typing import Dict
import openpyxl
import pytest
import customtkinter as ctk

from app.word_consolidator.models import (
    MetadatosInstitucionales,
    PeriodoConsolidacion,
    TipoPeriodo,
)
from app.word_consolidator.pipeline import WordConsolidationPipeline
from app.word_consolidator.ui.services.application_service import (
    ConsolidationAppService,
)
from app.word_consolidator.ui.views.matrix_selection_view import MatrixSelectionView

TEMPLATES_DIR = Path("templates")
OUTPUT_DIR = Path("output")


# app_root se hereda con scope='session' desde tests/conftest.py


@pytest.fixture
def matrices_kevds3_dict() -> Dict[str, Path]:
    """Retorna las 5 matrices oficiales con nombres reales de descarga Kevds3."""
    return {
        "M1": TEMPLATES_DIR / "Documento de Kevds3(1).xlsx",
        "M2": TEMPLATES_DIR / "Documento de Kevds3(4).xlsx",
        "M3": TEMPLATES_DIR / "Documento de Kevds3(3).xlsx",
        "M4": TEMPLATES_DIR / "Documento de Kevds3(2).xlsx",
        "M5": TEMPLATES_DIR / "Documento de Kevds3.xlsx",
    }


@pytest.fixture
def matrices_caso_real_dict() -> Dict[str, Path]:
    """Retorna las 5 matrices oficiales con los datos poblados del caso real de Septiembre 2026."""
    return {
        "M1": OUTPUT_DIR / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": OUTPUT_DIR / "Matriz_2_Estudiantes.xlsx",
        "M3": OUTPUT_DIR / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": OUTPUT_DIR / "Matriz_4_Colaboradores.xlsx",
        "M5": OUTPUT_DIR / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }


class TestMatrixAutoIdentification:
    """Suite de 10 pruebas obligatorias para la certificación de usabilidad."""

    # -------------------------------------------------------------------------
    # Test 1 — Orden aleatorio
    # -------------------------------------------------------------------------
    def test_01_orden_aleatorio(self, matrices_kevds3_dict):
        """Seleccionar en orden desordenado (M5, M2, M4, M1, M3) debe reorganizar a M1..M5."""
        p1 = matrices_kevds3_dict["M1"]
        p2 = matrices_kevds3_dict["M2"]
        p3 = matrices_kevds3_dict["M3"]
        p4 = matrices_kevds3_dict["M4"]
        p5 = matrices_kevds3_dict["M5"]

        orden_desordenado = [p5, p2, p4, p1, p3]
        analisis = ConsolidationAppService.analizar_conjunto_archivos(orden_desordenado)

        assert analisis["es_completo"] is True
        assert analisis["total_identificadas"] == 5
        assert set(analisis["matrices"].keys()) == {"M1", "M2", "M3", "M4", "M5"}
        assert analisis["matrices"]["M1"] == p1
        assert analisis["matrices"]["M2"] == p2
        assert analisis["matrices"]["M3"] == p3
        assert analisis["matrices"]["M4"] == p4
        assert analisis["matrices"]["M5"] == p5
        assert len(analisis["duplicados"]) == 0
        assert len(analisis["faltantes"]) == 0

    # -------------------------------------------------------------------------
    # Test 2 — Nombres genéricos
    # -------------------------------------------------------------------------
    def test_02_nombres_genericos(self, matrices_kevds3_dict, tmp_path):
        """Archivos con nombres totalmente arbitrarios deben identificarse por estructura."""
        f_a = tmp_path / "datos_a.xlsx"
        f_b = tmp_path / "informacion_b.xlsx"
        f_c = tmp_path / "reporte_c.xlsx"
        f_d = tmp_path / "archivo_d.xlsx"
        f_e = tmp_path / "matriz_e.xlsx"

        shutil.copy2(matrices_kevds3_dict["M1"], f_a)
        shutil.copy2(matrices_kevds3_dict["M2"], f_b)
        shutil.copy2(matrices_kevds3_dict["M3"], f_c)
        shutil.copy2(matrices_kevds3_dict["M4"], f_d)
        shutil.copy2(matrices_kevds3_dict["M5"], f_e)

        analisis = ConsolidationAppService.analizar_conjunto_archivos([f_e, f_c, f_a, f_d, f_b])

        assert analisis["es_completo"] is True
        assert analisis["matrices"]["M1"] == f_a
        assert analisis["matrices"]["M2"] == f_b
        assert analisis["matrices"]["M3"] == f_c
        assert analisis["matrices"]["M4"] == f_d
        assert analisis["matrices"]["M5"] == f_e

    # -------------------------------------------------------------------------
    # Test 3 — Nombres actuales Kevds3
    # -------------------------------------------------------------------------
    def test_03_nombres_actuales_kevds3(self, matrices_kevds3_dict):
        """Probar específicamente los 5 archivos reales con prefijo 'Documento de Kevds3'."""
        archivos = list(matrices_kevds3_dict.values())
        analisis = ConsolidationAppService.analizar_conjunto_archivos(archivos)

        assert analisis["es_completo"] is True
        assert analisis["matrices"]["M1"].name == "Documento de Kevds3(1).xlsx"
        assert analisis["matrices"]["M2"].name == "Documento de Kevds3(4).xlsx"
        assert analisis["matrices"]["M3"].name == "Documento de Kevds3(3).xlsx"
        assert analisis["matrices"]["M4"].name == "Documento de Kevds3(2).xlsx"
        assert analisis["matrices"]["M5"].name == "Documento de Kevds3.xlsx"

    # -------------------------------------------------------------------------
    # Test 4 — Matriz duplicada
    # -------------------------------------------------------------------------
    def test_04_error_matriz_duplicada(self, matrices_kevds3_dict, tmp_path):
        """Dos archivos que corresponden a M1 deben ser rechazados sin asignación arbitraria."""
        copia_m1 = tmp_path / "otro_m1.xlsx"
        shutil.copy2(matrices_kevds3_dict["M1"], copia_m1)

        lista = [
            matrices_kevds3_dict["M1"],
            copia_m1,
            matrices_kevds3_dict["M2"],
            matrices_kevds3_dict["M3"],
            matrices_kevds3_dict["M4"],
        ]

        analisis = ConsolidationAppService.analizar_conjunto_archivos(lista)

        assert analisis["es_completo"] is False
        assert "M1" in analisis["duplicados"]
        assert len(analisis["duplicados"]["M1"]) == 2
        # M1 no debe ser asignada arbitrariamente a ninguna de las dos
        assert "M1" not in analisis["matrices"]
        assert analisis["error_resumen"] is not None
        assert analisis["error_resumen"]["tipo"] == "MATRIZ_DUPLICADA"
        assert "MATRIZ DUPLICADA — M1" in analisis["error_resumen"]["titulo"]
        assert "Selecciona solamente una matriz oficial M1" in analisis["error_resumen"]["mensaje"]

    # -------------------------------------------------------------------------
    # Test 5 — Matriz faltante
    # -------------------------------------------------------------------------
    def test_05_error_matriz_faltante(self, matrices_kevds3_dict):
        """Si falta M5, el sistema debe reportar matriz faltante e impedir continuar."""
        solo_cuatro = [
            matrices_kevds3_dict["M1"],
            matrices_kevds3_dict["M2"],
            matrices_kevds3_dict["M3"],
            matrices_kevds3_dict["M4"],
        ]

        analisis = ConsolidationAppService.analizar_conjunto_archivos(solo_cuatro)

        assert analisis["es_completo"] is False
        assert "M5" in analisis["faltantes"]
        assert analisis["error_resumen"] is not None
        assert analisis["error_resumen"]["tipo"] == "MATRIZ_FALTANTE"
        assert "MATRIZ FALTANTE — M5" in analisis["error_resumen"]["titulo"]
        assert "No se encontró:" in analisis["error_resumen"]["mensaje"]

    # -------------------------------------------------------------------------
    # Test 6 — Archivo no reconocido
    # -------------------------------------------------------------------------
    def test_06_error_archivo_no_reconocido(self, matrices_kevds3_dict, tmp_path):
        """Un archivo Excel con estructura ajena debe rechazarse con error claro."""
        excel_ajeno = tmp_path / "Documento desconocido.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ventas_Anuales"
        ws.append(["Producto", "Precio", "Stock", "Fecha"])
        wb.save(excel_ajeno)
        wb.close()

        lista = [
            matrices_kevds3_dict["M1"],
            matrices_kevds3_dict["M2"],
            matrices_kevds3_dict["M3"],
            matrices_kevds3_dict["M4"],
            excel_ajeno,
        ]

        analisis = ConsolidationAppService.analizar_conjunto_archivos(lista)

        assert analisis["es_completo"] is False
        assert len(analisis["desconocidos"]) == 1
        assert analisis["desconocidos"][0][0] == excel_ajeno
        assert analisis["error_resumen"] is not None
        assert analisis["error_resumen"]["tipo"] == "ARCHIVO_NO_RECONOCIDO"
        assert "ARCHIVO NO RECONOCIDO" in analisis["error_resumen"]["titulo"]
        assert "Documento desconocido.xlsx" in analisis["error_resumen"]["mensaje"]

    # -------------------------------------------------------------------------
    # Test 7 — Archivo inválido
    # -------------------------------------------------------------------------
    def test_07_error_archivo_invalido(self, matrices_kevds3_dict, tmp_path):
        """Un archivo corrupto o con formato no-Excel debe manejarse limpiamente."""
        f_corrupto = tmp_path / "archivo_danado.xlsx"
        f_corrupto.write_text("Este no es un archivo excel valido")

        lista = [
            matrices_kevds3_dict["M1"],
            matrices_kevds3_dict["M2"],
            matrices_kevds3_dict["M3"],
            matrices_kevds3_dict["M4"],
            f_corrupto,
        ]

        analisis = ConsolidationAppService.analizar_conjunto_archivos(lista)

        assert analisis["es_completo"] is False
        assert len(analisis["archivos_invalidos"]) == 1
        assert analisis["archivos_invalidos"][0][0] == f_corrupto
        assert analisis["error_resumen"] is not None
        assert analisis["error_resumen"]["tipo"] == "ARCHIVO_INVALIDO"
        assert "ARCHIVO INVÁLIDO" in analisis["error_resumen"]["titulo"]
        assert "No fue posible leer:" in analisis["error_resumen"]["mensaje"]

    # -------------------------------------------------------------------------
    # Test 8 — Caso real Septiembre 2026
    # -------------------------------------------------------------------------
    def test_08_caso_real_septiembre_2026(self, matrices_caso_real_dict, tmp_path):
        """Ejecutar el pipeline tras identificación y verificar métricas oficiales exactas."""
        # Identificar primero en orden desordenado
        archivos = [
            matrices_caso_real_dict["M5"],
            matrices_caso_real_dict["M3"],
            matrices_caso_real_dict["M1"],
            matrices_caso_real_dict["M4"],
            matrices_caso_real_dict["M2"],
        ]
        analisis = ConsolidationAppService.analizar_conjunto_archivos(archivos)
        assert analisis["es_completo"] is True
        fuentes = analisis["matrices"]

        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 7),
            etiqueta="Septiembre 2026 — Semana 1",
        )

        metadatos = MetadatosInstitucionales(
            periodo=periodo,
            elaborado_por="Comisión Institucional de Auditoría",
            revisado_por="Secretaría General Académica",
            aprobado_por="Rectoría BICU",
        )

        informes_narrativos = {
            "caso_real_sept_2026": {
                "nombre_actividad": "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial",
                "estudiantes": 15,
                "administrativos": 2,
                "docentes": 1,
                "total": 18,
            }
        }

        pipeline = WordConsolidationPipeline(default_output_dir=tmp_path / "out_real")
        resultado = pipeline.ejecutar(
            fuentes=fuentes,
            periodo=periodo,
            metadatos=metadatos,
            informes_narrativos=informes_narrativos,
        )

        # Métricas volumétricas globales
        assert resultado.total_actividades == 1
        assert resultado.total_participaciones == 18
        assert resultado.total_personas_unicas == 18

        with open(resultado.ruta_reporte_json, "r", encoding="utf-8") as f:
            data_audit = json.load(f)

        discs = data_audit["discrepancias"]

        # 1. M1 Consolidado vs Nominal (Concordancia Sexo y Totales)
        fem_m1 = next(d for d in discs if "Femenino" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert fem_m1["valor_fuente_a"] == 12
        assert fem_m1["valor_fuente_b"] == 12

        masc_m1 = next(d for d in discs if "Masculino" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert masc_m1["valor_fuente_a"] == 6
        assert masc_m1["valor_fuente_b"] == 6

        tot_m1 = next(d for d in discs if "Total General" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert tot_m1["valor_fuente_a"] == 18
        assert tot_m1["valor_fuente_b"] == 18

        # 2. Conteo Nominal vs Narrativa
        est_narr = next(d for d in discs if d["estamento"] == "Estudiantes" and "Narrativo" in d["fuente_a"])
        assert est_narr["valor_fuente_a"] == 15
        assert est_narr["valor_fuente_b"] == 17
        assert est_narr["delta"] == 2
        assert est_narr["estado"] == "REQUIERE_REVISION"

        adm_narr = next(d for d in discs if d["estamento"] == "Administrativos" and "Narrativo" in d["fuente_a"])
        assert adm_narr["valor_fuente_a"] == 2
        assert adm_narr["valor_fuente_b"] == 1
        assert adm_narr["delta"] == -1
        assert adm_narr["estado"] == "REQUIERE_REVISION"

        doc_narr = next(d for d in discs if d["estamento"] == "Docentes" and "Narrativo" in d["fuente_a"])
        assert doc_narr["valor_fuente_a"] == 1
        assert doc_narr["valor_fuente_b"] == 0
        assert doc_narr["delta"] == -1
        assert doc_narr["estado"] == "REQUIERE_REVISION"

        # 3. Discrepancias totales activas
        discs_revision = [d for d in discs if d["estado"] == "REQUIERE_REVISION"]
        assert len(discs_revision) == 3

    # -------------------------------------------------------------------------
    # Test 9 — Preservación de M5 Histórico
    # -------------------------------------------------------------------------
    def test_09_m5_historico_preservado(self, matrices_caso_real_dict, tmp_path):
        """Confirmar que los 32 registros históricos de M5 permanecen intactos y fuera del período."""
        analisis = ConsolidationAppService.analizar_conjunto_archivos(list(matrices_caso_real_dict.values()))
        fuentes = analisis["matrices"]

        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 — Semana 1",
        )

        pipeline = WordConsolidationPipeline(default_output_dir=tmp_path / "out_hist")
        resultado = pipeline.ejecutar(fuentes, periodo)

        m5_info = resultado.archivos_fuente["M5"]
        assert m5_info.filas_leidas == 32
        assert m5_info.filas_fuera_periodo == 32
        assert m5_info.filas_activas == 0

        with open(resultado.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)
            assert audit["archivos_fuente"]["M5"]["filas_fuera_periodo"] == 32

    # -------------------------------------------------------------------------
    # Test 10 — Interfaz MatrixSelectionView y Reorganización
    # -------------------------------------------------------------------------
    def test_10_ui_matrix_selection_view_flujo(self, app_root, matrices_kevds3_dict):
        """Verificar la experiencia visual en MatrixSelectionView: slots genéricos y tarjetas."""
        view = MatrixSelectionView(app_root)

        # 1. Estado inicial
        assert len(view.obtener_matrices()) == 0
        for i in range(5):
            assert view.slot_widgets[i]["label_num"].cget("text") == f"Archivo {i + 1}:"
            assert view.slot_widgets[i]["label_file"].cget("text") == "[ No seleccionado ]"

        # 2. Cargar en desorden
        p1 = matrices_kevds3_dict["M1"]
        p2 = matrices_kevds3_dict["M2"]
        p3 = matrices_kevds3_dict["M3"]
        p4 = matrices_kevds3_dict["M4"]
        p5 = matrices_kevds3_dict["M5"]

        view.archivos_seleccionados = [p4, p1, p5, p3, p2]
        view._actualizar_etiquetas_slots()

        # Comprobar que los slots muestran los nombres de archivo cargados
        assert view.slot_widgets[0]["label_file"].cget("text") == p4.name
        assert view.slot_widgets[1]["label_file"].cget("text") == p1.name

        # Ejecutar identificación estructural
        res = view.identificar_matrices(mostrar_alertas=False)

        assert len(res) == 5
        assert set(res.keys()) == {"M1", "M2", "M3", "M4", "M5"}
        assert "5 de 5 matrices identificadas" in view.status_lbl.cget("text")

        # Comprobar que las tarjetas visuales muestran los datos identificados
        for cod in ["M1", "M2", "M3", "M4", "M5"]:
            card = view.matrix_cards[cod]
            assert card["icon"].cget("text") == "✓"
            assert "Estructura reconocida" in card["detalle"].cget("text")

        # 3. Limpiar
        view.limpiar()
        assert len(view.obtener_matrices()) == 0
        assert "0 de 5 matrices" in view.status_lbl.cget("text")
        for i in range(5):
            assert view.slot_widgets[i]["label_file"].cget("text") == "[ No seleccionado ]"
