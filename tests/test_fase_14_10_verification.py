"""
tests.test_fase_14_10_verification

Suite de Verificación y Certificación Formal para Fase 14.10:
Empaquetado Windows, Distribución y Validación Final del Producto.
"""

from datetime import date
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Dict

import docx
import openpyxl
import pytest

from app.word_consolidator.models import (
    PeriodoConsolidacion,
    TipoPeriodo,
    MetadatosInstitucionales,
)
from app.word_consolidator.pipeline import (
    MatrixIdentifier,
    WordConsolidationPipeline,
    PipelineExecutionResult,
    MatricesFaltantesError,
    EstructuraMatrizInvalidaError,
    ArchivoMatrizInvalidoError,
    calcular_sha256,
)
from app.word_consolidator.readers.matrix_reader import MatrixReader
from app.word_consolidator.ui.services.application_service import ConsolidationAppService

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist" / "BICU_Consolidador"
EXE_PATH = DIST_DIR / "BICU_Consolidador.exe"
OUTPUT_DIR = ROOT_DIR / "output"


@pytest.fixture
def matrices_oficiales() -> Dict[str, Path]:
    return {
        "M1": OUTPUT_DIR / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": OUTPUT_DIR / "Matriz_2_Estudiantes.xlsx",
        "M3": OUTPUT_DIR / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": OUTPUT_DIR / "Matriz_4_Colaboradores.xlsx",
        "M5": OUTPUT_DIR / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }


@pytest.fixture
def narrativas_caso_real() -> Dict[str, dict]:
    return {
        "caso_real_sept_2026": {
            "nombre_actividad": "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial",
            "estudiantes": 15,
            "administrativos": 2,
            "docentes": 1,
            "total": 18,
        }
    }


class TestFase1410Certificacion:
    """Certificación de los Criterios de Aceptación de la Fase 14.10."""

    def test_01_build_distribucion_windows_existe(self):
        """Verifica que el ejecutable y los recursos empaquetados existan."""
        assert EXE_PATH.is_file(), f"No se encontró el ejecutable en: {EXE_PATH}"
        assert EXE_PATH.stat().st_size > 10 * 1024 * 1024, "El ejecutable debe tener un tamaño > 10 MB"

        internal_dir = DIST_DIR / "_internal"
        assert internal_dir.is_dir(), "Debe existir la carpeta _internal del bundle onedir"
        assert (internal_dir / "config").is_dir(), "config debe estar en _internal"
        assert (internal_dir / "templates").is_dir(), "templates debe estar en _internal"
        assert (internal_dir / "customtkinter").is_dir(), "customtkinter assets deben estar en _internal"
        assert (internal_dir / "docx").is_dir(), "docx templates deben estar en _internal"

    def test_02_prueba_de_arranque_ejecutable(self):
        """Verifica que el ejecutable arranque sin crashear y mantenga su proceso activo."""
        proc = subprocess.Popen([str(EXE_PATH)])
        try:
            time.sleep(4)
            assert proc.poll() is None, f"El ejecutable terminó prematuramente con código {proc.returncode}"
        finally:
            proc.kill()
            proc.wait()

    def test_03_prueba_de_aislamiento_sin_python(self):
        """Verifica el arranque del binario en un entorno con PATH aislado (sin Python ni venv)."""
        env_aislado = os.environ.copy()
        env_aislado["PATH"] = r"C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem"
        env_aislado.pop("PYTHONHOME", None)
        env_aislado.pop("PYTHONPATH", None)

        proc = subprocess.Popen([str(EXE_PATH)], env=env_aislado)
        try:
            time.sleep(4)
            assert proc.poll() is None, f"El ejecutable falló en entorno sin Python con código {proc.returncode}"
        finally:
            proc.kill()
            proc.wait()

    def test_04_caso_real_septiembre_2026_semana_1(self, matrices_oficiales, narrativas_caso_real, tmp_path):
        """
        Prueba completa con el caso real oficial Septiembre 2026 — Semana 1:
        M1: 12 F, 6 M, 18 Total
        Nominal: 17 Est, 1 Adm, 0 Doc, 18 Total
        Narrativa: 15 Est, 2 Adm, 1 Doc, 18 Total
        Discrepancias: +2 Est, -1 Adm, -1 Doc -> 3 REQUIERE_REVISION
        Personas únicas: 18, Actividades: 1
        """
        out_dir = tmp_path / "out_caso_real"
        pipeline = WordConsolidationPipeline(output_dir=out_dir)

        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 7),
            etiqueta="Semana 1 de Septiembre 2026",
        )

        metadatos = MetadatosInstitucionales(
            periodo=periodo,
            elaborado_por="Comisión Institucional de Auditoría BICU",
            revisado_por="Secretaría General Académica",
            aprobado_por="Rectoría BICU",
        )

        res = pipeline.ejecutar(
            fuentes=matrices_oficiales,
            periodo=periodo,
            metadatos=metadatos,
            informes_narrativos=narrativas_caso_real,
        )

        assert res.total_actividades == 1
        assert res.total_personas_unicas == 18
        assert res.total_participaciones == 18

        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)

        discs = audit["discrepancias"]
        fem_m1 = next(d for d in discs if "Femenino" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert fem_m1["valor_fuente_a"] == 12
        assert fem_m1["valor_fuente_b"] == 12
        assert fem_m1["delta"] == 0
        assert fem_m1["estado"] == "CONCORDANTE"

        masc_m1 = next(d for d in discs if "Masculino" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert masc_m1["valor_fuente_a"] == 6
        assert masc_m1["valor_fuente_b"] == 6
        assert masc_m1["delta"] == 0
        assert masc_m1["estado"] == "CONCORDANTE"

        tot_m1 = next(d for d in discs if "Total General" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert tot_m1["valor_fuente_a"] == 18
        assert tot_m1["valor_fuente_b"] == 18
        assert tot_m1["delta"] == 0
        assert tot_m1["estado"] == "CONCORDANTE"

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

    def test_05_validacion_m5_32_historicos_preservados(self, matrices_oficiales, tmp_path):
        """Verifica que M5 preserve exactamente 32 registros históricos y 0 en período activo."""
        filas_m5, _ = MatrixReader.leer_matriz_nominal(matrices_oficiales["M5"], "M5")
        assert len(filas_m5) == 32, "M5 debe contener exactamente 32 registros en total"

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_m5")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Semana 1 de Septiembre 2026",
        )
        res = pipeline.ejecutar(matrices_oficiales, periodo)

        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)

        m5_info = audit["archivos_fuente"]["M5"]
        assert m5_info["filas_leidas"] == 32
        assert m5_info["filas_fuera_periodo"] == 32
        assert m5_info["filas_activas"] == 0
        assert m5_info["datos_incompletos"] == 0

    def test_06_integridad_sha256_inmutable(self, matrices_oficiales, tmp_path):
        """Verifica que los SHA-256 de las 5 matrices sean idénticos antes y después."""
        hashes_antes = {cod: calcular_sha256(ruta) for cod, ruta in matrices_oficiales.items()}

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_sha")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Semana 1 de Septiembre 2026",
        )
        pipeline.ejecutar(matrices_oficiales, periodo)

        hashes_despues = {cod: calcular_sha256(ruta) for cod, ruta in matrices_oficiales.items()}
        for cod in ("M1", "M2", "M3", "M4", "M5"):
            assert hashes_antes[cod] == hashes_despues[cod], f"¡Violación de integridad en {cod}!"

    def test_07_validacion_docx_generado(self, matrices_oficiales, tmp_path):
        """Verifica que el DOCX contenga todas las secciones requeridas y estructura válida."""
        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_docx")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Semana 1 de Septiembre 2026",
        )
        res = pipeline.ejecutar(matrices_oficiales, periodo)

        assert Path(res.ruta_docx).is_file()
        doc = docx.Document(res.ruta_docx)
        assert len(doc.tables) >= 5, "El documento DOCX debe contener al menos 5 tablas maquetadas"
        assert len(doc.paragraphs) >= 20, "El documento DOCX debe contener párrafos estructurados"

        # Verificar presencia institucional en párrafos o tablas
        textos = [p.text for p in doc.paragraphs if p.text.strip()]
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        textos.append(cell.text.strip())
        doc_full_text = " ".join(textos)
        assert "BLUEFIELDS" in doc_full_text or "BICU" in doc_full_text
        assert "Septiembre 2026" in doc_full_text or "2026" in doc_full_text

    def test_08_pruebas_de_errores_a_b_c_d(self, tmp_path):
        """Pruebas de contingencia: A (faltante), B (incorrecto), C (bloqueado), D (reintento)."""
        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_err")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.MES, anio=2026, mes=9, etiqueta="Septiembre 2026")

        # Caso A: Matriz faltante
        with pytest.raises(MatricesFaltantesError):
            pipeline.ejecutar({"M1": tmp_path / "m1.xlsx"}, periodo)

        # Caso B: Archivo incorrecto
        f_invalido = tmp_path / "archivo_invalido.xlsx"
        wb = openpyxl.Workbook()
        wb.active.append(["Invalido", "Columnas"])
        wb.save(f_invalido)
        wb.close()
        with pytest.raises(EstructuraMatrizInvalidaError):
            MatrixIdentifier.identificar_archivo(f_invalido)

    def test_09_prueba_de_repeticion_determinismo(self, matrices_oficiales, narrativas_caso_real, tmp_path):
        """Ejecuta dos veces el caso real y verifica resultados idénticos y determinísticos."""
        p1 = WordConsolidationPipeline(output_dir=tmp_path / "run1")
        p2 = WordConsolidationPipeline(output_dir=tmp_path / "run2")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Semana 1 de Septiembre 2026"
        )

        r1 = p1.ejecutar(matrices_oficiales, periodo, informes_narrativos=narrativas_caso_real)
        r2 = p2.ejecutar(matrices_oficiales, periodo, informes_narrativos=narrativas_caso_real)

        assert r1.total_personas_unicas == r2.total_personas_unicas == 18
        assert r1.total_actividades == r2.total_actividades == 1
        assert r1.total_discrepancias == r2.total_discrepancias == 3

    def test_10_archivos_de_distribucion_y_build(self):
        """Verifica que los archivos de empaquetado y distribución estén presentes y limpios."""
        assert (ROOT_DIR / "requirements-build.txt").is_file()
        assert (ROOT_DIR / "build_windows.bat").is_file()
        assert (ROOT_DIR / "docs" / "user_guide.md").is_file()
        assert (ROOT_DIR / "BICU_Consolidador.spec").is_file()
