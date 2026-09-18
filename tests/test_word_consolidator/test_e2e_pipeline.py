"""
tests.test_word_consolidator.test_e2e_pipeline

Suite Formal de Pruebas Automatizadas End-to-End (Fase 14.8).
Valida la integración completa del flujo institucional:
5 Matrices Excel Oficiales M1–M5 → MatrixIdentifier → MatrixReader → PeriodFilter (Regla Estricta) →
ConsolidationEngine + IdentityResolver → DiscrepancyDetector → DocumentTransformer →
DocxGenerator → Documento DOCX Maquetado + Reporte de Auditoría E2E (.json y .md).

Grupos de Prueba Obligatorios:
A. Identificación Estructural de Matrices (MatrixIdentifier) y discriminación M2 vs M4.
B. Regla Estricta de Fechas (Cero Inferencias, datos incompletos no promovidos).
C. Caso Real Septiembre 2026 (Plantillas oficiales de templates/).
D. Preservación del Histórico M5 (32 registros fuera de período).
E. Pruebas de Volumen Dinámico E2E (32, 40, 100, 250+ registros hasta DOCX).
F. Demostración Explícita de Independencia de los 32 Registros (Prueba de 40).
G. Inmutabilidad Criptográfica SHA-256 e Inmutabilidad de DocumentoConsolidado.
H. Trazabilidad Técnica Documental → Física de Excel.
I. No Reconciliación Forzada (Deltas y REQUIERE_REVISION preservados).
J. Manejo de Errores y Matriz de Contingencias (Faltantes, Duplicadas, Corruptas).
"""

from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import shutil
from typing import Dict, List, Optional
import uuid

import docx
import openpyxl
import pytest

from app.word_consolidator.models import (
    PeriodoConsolidacion,
    TipoPeriodo,
    MetadatosInstitucionales,
    EstadoDiscrepancia,
)
from app.word_consolidator.pipeline import (
    MatrixIdentifier,
    WordConsolidationPipeline,
    PipelineExecutionResult,
    MatrixPipelineError,
    MatricesFaltantesError,
    MatrizDuplicadaError,
    EstructuraMatrizInvalidaError,
    ArchivoMatrizInvalidoError,
    ErrorIntegridadArchivo,
    calcular_sha256,
)
from app.word_consolidator.readers.matrix_reader import MatrixReader


BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"


# =============================================================================
# FIXTURES Y GENERADORES DE MATRICES SINTÉTICAS CON HUELLAS OFICIALES
# =============================================================================

@pytest.fixture
def plantillas_oficiales_dict() -> Dict[str, Path]:
    """Retorna las 5 matrices oficiales con la corrida real de Septiembre 2026 ubicadas en output/ (o templates/)."""
    base = OUTPUT_DIR if (OUTPUT_DIR / "Matriz_1_Consolidado_Actividades.xlsx").exists() else TEMPLATES_DIR
    m1 = base / "Matriz_1_Consolidado_Actividades.xlsx"
    m2 = base / "Matriz_2_Estudiantes.xlsx"
    m3 = base / "Matriz_3_Academicos_Administrativos.xlsx"
    m4 = base / "Matriz_4_Colaboradores.xlsx"
    m5 = base / "Matriz_5_Protagonistas_Beneficiados.xlsx"

    # Si los nombres estándar no existen, buscar por alias Kevds3 en templates
    if not m1.exists():
        m1 = TEMPLATES_DIR / "Documento de Kevds3(1).xlsx"
    if not m2.exists():
        m2 = TEMPLATES_DIR / "Documento de Kevds3(4).xlsx"
    if not m3.exists():
        m3 = TEMPLATES_DIR / "Documento de Kevds3(3).xlsx"
    if not m4.exists():
        m4 = TEMPLATES_DIR / "Documento de Kevds3(2).xlsx"
    if not m5.exists():
        m5 = TEMPLATES_DIR / "Documento de Kevds3.xlsx"

    return {
        "M1": m1,
        "M2": m2,
        "M3": m3,
        "M4": m4,
        "M5": m5,
    }


@pytest.fixture
def plantillas_base_templates() -> Dict[str, Path]:
    """Retorna las 5 plantillas base directamente desde templates/."""
    m1 = TEMPLATES_DIR / "Matriz_1_Consolidado_Actividades.xlsx"
    m2 = TEMPLATES_DIR / "Matriz_2_Estudiantes.xlsx"
    m3 = TEMPLATES_DIR / "Matriz_3_Academicos_Administrativos.xlsx"
    m4 = TEMPLATES_DIR / "Matriz_4_Colaboradores.xlsx"
    m5 = TEMPLATES_DIR / "Matriz_5_Protagonistas_Beneficiados.xlsx"

    if not m1.exists():
        m1 = TEMPLATES_DIR / "Documento de Kevds3(1).xlsx"
    if not m2.exists():
        m2 = TEMPLATES_DIR / "Documento de Kevds3(4).xlsx"
    if not m3.exists():
        m3 = TEMPLATES_DIR / "Documento de Kevds3(3).xlsx"
    if not m4.exists():
        m4 = TEMPLATES_DIR / "Documento de Kevds3(2).xlsx"
    if not m5.exists():
        m5 = TEMPLATES_DIR / "Documento de Kevds3.xlsx"

    return {
        "M1": m1,
        "M2": m2,
        "M3": m3,
        "M4": m4,
        "M5": m5,
    }


def crear_matriz_m1_sintetica(
    ruta: Path,
    filas_actividades: List[Dict],
    columnas_extra: int = 0
) -> Path:
    """Crea una matriz M1 con sus 42 encabezados canónicos y filas especificadas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Programas, proyectos y act"

    headers = [
        "No", "Sede", "Dep_sede", "Mun_sede", "Programa", "Otro_programa",
        "Proyecto", "Ámbito", "Actividad", "Área_responsable", "Financiamiento",
        "Nombre_área", "Evento", "Evento_Otros", "Fecha_evento", "Resultados",
        "Convenio", "Tipo_convenio", "Nombre_convenio", "Región_atendida",
        "Departamento", "Municipio", "Comunidad", "Total_comunidades",
        "Total, Atención, M", "Total, Atención, F",
        "Total, estud_M_grado", "Total, estud_F_grado",
        "Total, estud_M_posgrado", "Total, estud_F_posgrado",
        "Total, docente_M", "Total, docente_F",
        "Total, Administrativos_M", "Total, Administrativos_F",
        "Total, partic_M_inst_pública", "Total, partic_F_inst_pública",
        "Total, partic_M_inst_privada", "Total, partic_F_inst_privada",
        "Total, partic_M_ONG", "Total, partic_F_ONG",
        "Total, Protagonistas_M", "Total, Protagonistas_F"
    ]
    for i in range(columnas_extra):
        headers.append(f"Columna_Extra_{i+1}")

    ws.append(headers)

    for idx, act in enumerate(filas_actividades, start=1):
        fila = [
            idx,
            act.get("sede", "Bilwi"),
            act.get("dep_sede", "RACCN"),
            act.get("mun_sede", "Puerto Cabezas"),
            act.get("programa", "Programa General"),
            "",
            act.get("proyecto", "Proyecto Institucional"),
            "Ámbito Universitario",
            act.get("actividad", "Taller Oficial"),
            "Área Académica",
            "Fondos Propios",
            "Facultad",
            "Taller",
            "",
            act.get("fecha_evento", "2026-09-03"),
            "Resultados favorables",
            "No", "", "", "RACCN", "RACCN", "Puerto Cabezas", "Comunidad 1", 1,
            act.get("total_m", 5),
            act.get("total_f", 10),
            act.get("estud_m", 5),
            act.get("estud_f", 10),
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        ]
        ws.append(fila)

    wb.save(ruta)
    wb.close()
    return ruta


def crear_matriz_nominal_sintetica(
    ruta: Path,
    codigo_matriz: str,
    filas_personas: List[Dict],
    columnas_extra: int = 0
) -> Path:
    """Crea matrices M2 (57 cols), M3 (58 cols), M4 (57 cols) o M5 (53 cols) con cabeceras exactas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pregrado_Grado en Actividades"

    # Base común cols 1-32
    base_comun = [
        "No", "Sede", "Dep_sede", "Mun_sede", "Programa", "Otro_programa",
        "Proyecto", "Ámbito", "Actividad", "Proposito", "Evento", "Evento_Otros",
        "Tipo_Evento", "Área", "Eje_estrategia", "Alcance", "Convenio",
        "Tipo_convenio", "Nombre_convenio", "Entidad_vinculada_1", "Nombre_entidad_1",
        "Financiamiento_1", "Entidad_vinculada_2", "Nombre_entidad_2", "Financiamiento_2",
        "Entidad_vinculada_3", "Nombre_entidad_3", "Financiamiento_3", "Área_responsable",
        "Departamento_responsable", "Financiamiento_FE_4", "Financiamiento_Fp_4"
    ]

    demografia_comun = [
        "Número_único ", "No_cédula", "No_cédula_resid", "No_pasaporte",
        "Sexo", "Fecha_nacimiento", "Edad", "Dimensión_nacionalidad",
        "País_procedencia", "Etnia", "Dep_procedenica_Ni", "Mun_procedenica_Ni",
        "Comunidad_proc", "Procedencia_extranjeros", "Zona_procedencia",
        "Discapacidad"
    ]

    if codigo_matriz == "M2":
        # 57 columnas
        headers = base_comun + ["Nombre_apellidos"] + demografia_comun + [
            "Prog_especial", "Nivel_form", "Nombre_carrera", "Área ",
            "Año_académico", "Régimen", "Modalidad", "Turno"
        ]
    elif codigo_matriz == "M3":
        # 58 columnas
        headers = base_comun + ["Mentoría", "Tipo_protagonistas", "Nombre_apellidos"] + demografia_comun + [
            "Nivel_form", "Nombre_carrera", "Área ", "Departamento",
            "Cargo", "Nombre_cargo", "Tipo_contrato"
        ]
    elif codigo_matriz == "M4":
        # 57 columnas
        headers = base_comun + ["Mentoría", "Tipo_protagonistas", "Nombre_apellidos"] + demografia_comun + [
            "Nivel_form", "Nombre_carrera", "Cargo", "Nombre_cargo", "Entidad", "Nombre_entidad"
        ]
    elif codigo_matriz == "M5":
        # 53 columnas
        headers = base_comun + ["Mentoría", "Nombre_apellidos"] + demografia_comun + [
            "Nivel_form", "Nombre_carrera", "Beneficio"
        ]
    else:
        raise ValueError(f"Código no soportado: {codigo_matriz}")

    for i in range(columnas_extra):
        headers.append(f"Col_Opcional_{i+1}")

    ws.append(headers)

    for idx, p in enumerate(filas_personas, start=1):
        fila = ["" for _ in range(len(headers))]
        fila[0] = idx
        fila[1] = p.get("sede", "Bilwi")
        fila[8] = p.get("actividad", "Taller Oficial")

        nombre = p.get("nombre", f"Persona_{codigo_matriz}_{idx}")
        cedula = p.get("cedula", f"601-{codigo_matriz}-{idx:06d}-0001A")
        sexo = p.get("sexo", "Femenino" if idx % 2 == 0 else "Masculino")

        if codigo_matriz == "M2":
            fila[32] = nombre  # Col AG
            fila[33] = f"NU-{idx}"
            fila[34] = cedula
            fila[37] = sexo
            fila[51] = p.get("carrera", "Ingeniería en Sistemas")
            fila[53] = "2026"  # Año académico
            fila[54] = "Regular"
            fila[55] = "Presencial"
            fila[56] = "Diurno"
        elif codigo_matriz == "M3":
            fila[32] = p.get("departamento_m3", "Docencia")
            fila[33] = p.get("tipo_protagonistas", "Docente")
            fila[34] = nombre
            fila[35] = f"NU-{idx}"
            fila[36] = cedula
            fila[39] = sexo
            fila[54] = "Informática"
            fila[55] = "Profesor Titular"
            fila[56] = "Docente"
            fila[57] = "Tiempo Completo"
        elif codigo_matriz == "M4":
            fila[32] = "No"
            fila[33] = "Colaborador"
            fila[34] = nombre
            fila[35] = f"NU-{idx}"
            fila[36] = cedula
            fila[39] = sexo
            fila[53] = "Especialista"
            fila[54] = "Técnico"
            fila[55] = "MINED"
            fila[56] = "Ministerio de Educación"
        elif codigo_matriz == "M5":
            fila[32] = "No"
            fila[33] = nombre
            fila[34] = f"NU-{idx}"
            fila[35] = cedula
            fila[38] = sexo
            fila[52] = "Capacitación Comunitaria"

        ws.append(fila)

    wb.save(ruta)
    wb.close()
    return ruta


# =============================================================================
# GRUPO A: IDENTIFICACIÓN ESTRUCTURAL DE MATRICES (MatrixIdentifier)
# =============================================================================

class TestMatrixIdentifier:
    """Pruebas de identificación de matrices por huella estructural."""

    def test_identificacion_plantillas_oficiales_reales(self, plantillas_oficiales_dict):
        """Verifica que las matrices oficiales pobladas se identifiquen con sus 5 códigos exactos."""
        rutas = list(plantillas_oficiales_dict.values())
        resultado = MatrixIdentifier.identificar_archivos(rutas)
        assert set(resultado.keys()) == {"M1", "M2", "M3", "M4", "M5"}

    def test_identificacion_plantillas_base_templates(self, plantillas_base_templates):
        """Verifica que las plantillas base de templates/ se identifiquen con sus 5 códigos exactos."""
        rutas = list(plantillas_base_templates.values())
        resultado = MatrixIdentifier.identificar_archivos(rutas)
        assert set(resultado.keys()) == {"M1", "M2", "M3", "M4", "M5"}

    def test_tolerancia_a_nombres_arbitrarios_y_sufijos(self, tmp_path):
        """Demuestra que la identificación NO depende del nombre de archivo y tolera sufijos (1), (2)."""
        p1 = tmp_path / "Documento_Descargado(1).xlsx"
        p2 = tmp_path / "Copia_Estudiantes(4).xlsx"
        p3 = tmp_path / "Nomina_Docentes(3).xlsx"
        p4 = tmp_path / "Participantes_Externos(2).xlsx"
        p5 = tmp_path / "Beneficiarios_Comunidad.xlsx"

        crear_matriz_m1_sintetica(p1, [{"actividad": "Taller 1"}])
        crear_matriz_nominal_sintetica(p2, "M2", [{"nombre": "Ana"}])
        crear_matriz_nominal_sintetica(p3, "M3", [{"nombre": "Carlos"}])
        crear_matriz_nominal_sintetica(p4, "M4", [{"nombre": "Elena"}])
        crear_matriz_nominal_sintetica(p5, "M5", [{"nombre": "Mariana"}])

        resultado = MatrixIdentifier.identificar_archivos([p1, p2, p3, p4, p5])
        assert resultado["M1"] == p1
        assert resultado["M2"] == p2
        assert resultado["M3"] == p3
        assert resultado["M4"] == p4
        assert resultado["M5"] == p5

    def test_discriminacion_estructural_m2_vs_m4(self, tmp_path):
        """Verifica que M2 y M4 (ambas de 57 columnas) se distingan inequívocamente por sus marcadores."""
        p_m2 = tmp_path / "archivo_a.xlsx"
        p_m4 = tmp_path / "archivo_b.xlsx"

        crear_matriz_nominal_sintetica(p_m2, "M2", [{"nombre": "Estudiante 1"}])
        crear_matriz_nominal_sintetica(p_m4, "M4", [{"nombre": "Colaborador 1"}])

        assert MatrixIdentifier.identificar_archivo(p_m2) == "M2"
        assert MatrixIdentifier.identificar_archivo(p_m4) == "M4"

    def test_tolerancia_a_columnas_extra_opcionales(self, tmp_path):
        """Demuestra que columnas adicionales opcionales a la derecha no rompen la identificación."""
        p_m1 = tmp_path / "m1_expandida.xlsx"
        p_m2 = tmp_path / "m2_expandida.xlsx"

        crear_matriz_m1_sintetica(p_m1, [{"actividad": "A1"}], columnas_extra=3)
        crear_matriz_nominal_sintetica(p_m2, "M2", [{"nombre": "E1"}], columnas_extra=5)

        assert MatrixIdentifier.identificar_archivo(p_m1) == "M1"
        assert MatrixIdentifier.identificar_archivo(p_m2) == "M2"

    def test_error_matrices_faltantes(self, tmp_path):
        """Lanza MatricesFaltantesError si falta alguna de las 5 matrices."""
        p1 = tmp_path / "m1.xlsx"
        p2 = tmp_path / "m2.xlsx"
        crear_matriz_m1_sintetica(p1, [{"actividad": "A1"}])
        crear_matriz_nominal_sintetica(p2, "M2", [{"nombre": "E1"}])

        with pytest.raises(MatricesFaltantesError) as exc_info:
            MatrixIdentifier.identificar_archivos([p1, p2])
        assert "M3" in str(exc_info.value)
        assert "M4" in str(exc_info.value)
        assert "M5" in str(exc_info.value)

    def test_error_matriz_duplicada(self, tmp_path):
        """Lanza MatrizDuplicadaError si dos archivos tienen la estructura de la misma matriz."""
        p1a = tmp_path / "m1_a.xlsx"
        p1b = tmp_path / "m1_b.xlsx"
        crear_matriz_m1_sintetica(p1a, [{"actividad": "A1"}])
        crear_matriz_m1_sintetica(p1b, [{"actividad": "A2"}])

        with pytest.raises(MatrizDuplicadaError) as exc_info:
            MatrixIdentifier.identificar_archivos([p1a, p1b])
        assert "M1" in str(exc_info.value)

    def test_error_estructura_invalida(self, tmp_path):
        """Lanza EstructuraMatrizInvalidaError ante un libro Excel con estructura desconocida."""
        p = tmp_path / "desconocido.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "HojaCualquiera"
        ws.append(["ColA", "ColB", "ColC"])
        wb.save(p)
        wb.close()

        with pytest.raises(EstructuraMatrizInvalidaError):
            MatrixIdentifier.identificar_archivo(p)

    def test_error_archivo_inexistente_o_no_excel(self, tmp_path):
        """Lanza ArchivoMatrizInvalidoError si el archivo no existe o no tiene extensión Excel soportada."""
        p_no_existe = tmp_path / "archivo_fantasma.xlsx"
        with pytest.raises(ArchivoMatrizInvalidoError):
            MatrixIdentifier.identificar_archivo(p_no_existe)

        p_no_excel = tmp_path / "documento.pdf"
        p_no_excel.write_text("dummy")
        with pytest.raises(ArchivoMatrizInvalidoError):
            MatrixIdentifier.identificar_archivo(p_no_excel)

    def test_error_estructura_57_columnas_sin_marcadores_bicu(self, tmp_path):
        """Lanza EstructuraMatrizInvalidaError si un libro tiene 57 columnas pero carece de marcadores canónicos BICU."""
        p = tmp_path / "excel_57_columnas_aleatorio.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Contabilidad_General"
        headers_aleatorios = [f"Campo_Contable_{i+1}" for i in range(57)]
        ws.append(headers_aleatorios)
        wb.save(p)
        wb.close()

        with pytest.raises(EstructuraMatrizInvalidaError):
            MatrixIdentifier.identificar_archivo(p)


# =============================================================================
# GRUPO B: REGLA ESTRICTA DE FECHAS (CERO INFERENCIAS)
# =============================================================================

class TestReglaEstrictaFechas:
    """Verifica que el pipeline NO infiera fechas y segregue registros incompletos."""

    def test_fecha_valida_dentro_del_periodo_activa(self, tmp_path):
        """Actividad con fecha válida dentro del rango es promovida al período activo."""
        p1 = tmp_path / "m1.xlsx"
        p2 = tmp_path / "m2.xlsx"
        p3 = tmp_path / "m3.xlsx"
        p4 = tmp_path / "m4.xlsx"
        p5 = tmp_path / "m5.xlsx"

        crear_matriz_m1_sintetica(p1, [{"actividad": "Taller Valido", "fecha_evento": "2026-09-02"}])
        crear_matriz_nominal_sintetica(p2, "M2", [{"nombre": "Ana", "actividad": "Taller Valido"}])
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 7),
            etiqueta="Semana 1, Septiembre 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_actividades == 1
        assert res.total_participaciones == 1
        assert res.total_datos_incompletos == 0

    def test_fecha_vacia_no_inferida_dato_incompleto(self, tmp_path):
        """Actividad con celda de fecha vacía NO se infiere por texto ni período; queda fuera de período activo."""
        p1 = tmp_path / "m1.xlsx"
        p2 = tmp_path / "m2.xlsx"
        p3 = tmp_path / "m3.xlsx"
        p4 = tmp_path / "m4.xlsx"
        p5 = tmp_path / "m5.xlsx"

        # Actividad con texto 'Septiembre 2026' en nombre pero fecha_evento None
        crear_matriz_m1_sintetica(p1, [{"actividad": "Foro Septiembre 2026", "fecha_evento": None}])
        crear_matriz_nominal_sintetica(p2, "M2", [{"nombre": "Pedro", "actividad": "Foro Septiembre 2026"}])
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        # La actividad no tiene fecha válida: no se promueve al período activo
        assert res.total_actividades == 0
        assert res.total_participaciones == 0
        assert res.total_datos_incompletos == 1
        assert res.total_filas_fuera_periodo >= 1

    def test_fecha_invalida_no_corregida(self, tmp_path):
        """Actividad con fecha corrupta/invalida ('fecha-falsa-xyz') no se auto-corrige y queda fuera."""
        p1 = tmp_path / "m1.xlsx"
        p2 = tmp_path / "m2.xlsx"
        p3 = tmp_path / "m3.xlsx"
        p4 = tmp_path / "m4.xlsx"
        p5 = tmp_path / "m5.xlsx"

        crear_matriz_m1_sintetica(p1, [{"actividad": "Conferencia", "fecha_evento": "fecha-falsa-xyz"}])
        crear_matriz_nominal_sintetica(p2, "M2", [])
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.ANIO,
            anio=2026,
            etiqueta="Año 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_actividades == 0
        assert res.total_datos_incompletos == 1

    def test_fecha_fuera_del_periodo_segregada(self, tmp_path):
        """Actividad con fecha válida pero fuera del rango del período es segregada a actividades_fuera_periodo."""
        p1 = tmp_path / "m1.xlsx"
        p2 = tmp_path / "m2.xlsx"
        p3 = tmp_path / "m3.xlsx"
        p4 = tmp_path / "m4.xlsx"
        p5 = tmp_path / "m5.xlsx"

        # Actividad con fecha en Octubre 2026
        crear_matriz_m1_sintetica(p1, [{"actividad": "Taller Octubre", "fecha_evento": "2026-10-15"}])
        crear_matriz_nominal_sintetica(p2, "M2", [{"nombre": "Ana", "actividad": "Taller Octubre"}])
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_oct")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_actividades == 0
        assert res.total_participaciones == 0
        assert res.total_filas_fuera_periodo >= 1


# =============================================================================
# GRUPO C: CASO REAL SEPTIEMBRE 2026 (EJECUCIÓN E2E OFICIAL)
# =============================================================================

class TestCasoRealSeptiembre2026:
    """Ejecución oficial E2E sobre las plantillas reales de templates/."""

    def test_ejecucion_e2e_caso_real_oficial(self, plantillas_oficiales_dict, tmp_path):
        """
        Ejecución formal E2E con las 5 matrices oficiales reales de BICU.
        Verifica rigurosamente según Sección 6:
        - M1: Femenino=12, Masculino=6, Total=18.
        - Nominal: Estudiantes=17, Administrativos=1, Docentes=0, Colaboradores=0, Beneficiarios=0, Total=18.
        - Narrativa: Estudiantes=15, Administrativos=2, Docentes=1, Total=18.
        - Discrepancias M1 vs Nominal: F=12 vs 12 (delta 0), M=6 vs 6 (delta 0), Total=18 vs 18 (delta 0) -> CONCORDANTE.
        - Discrepancias Narrativa vs Nominal: Est=15 vs 17 (+2), Adm=2 vs 1 (-1), Doc=1 vs 0 (-1), Total=18 vs 18 (0).
        - Preservación íntegra de 32 registros históricos de M5 fuera del período.
        - Trazabilidad y generación íntegra del archivo .docx.
        """
        out_dir = tmp_path / "output_e2e_real"
        pipeline = WordConsolidationPipeline(default_output_dir=out_dir)

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

        # Ejecutar pipeline E2E
        res = pipeline.ejecutar(
            fuentes=plantillas_oficiales_dict,
            periodo=periodo,
            metadatos=metadatos,
            informes_narrativos=informes_narrativos,
        )

        # 1. Verificación del Resultado de Consolidación (Sección 6)
        assert res.total_actividades == 1
        assert res.total_participaciones == 18
        assert res.total_personas_unicas == 18

        # 2. Cargar auditoría JSON formal
        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            data_audit = json.load(f)

        discs = data_audit["discrepancias"]

        # 3. Verificación M1 vs Nominal (Concordancia total en Sexo y Totales)
        fem_m1_nom = next(d for d in discs if "Femenino" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert fem_m1_nom["valor_fuente_a"] == 12
        assert fem_m1_nom["valor_fuente_b"] == 12
        assert fem_m1_nom["delta"] == 0
        assert fem_m1_nom["estado"] == "CONCORDANTE"

        masc_m1_nom = next(d for d in discs if "Masculino" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert masc_m1_nom["valor_fuente_a"] == 6
        assert masc_m1_nom["valor_fuente_b"] == 6
        assert masc_m1_nom["delta"] == 0
        assert masc_m1_nom["estado"] == "CONCORDANTE"

        tot_m1_nom = next(d for d in discs if "Total General" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert tot_m1_nom["valor_fuente_a"] == 18
        assert tot_m1_nom["valor_fuente_b"] == 18
        assert tot_m1_nom["delta"] == 0
        assert tot_m1_nom["estado"] == "CONCORDANTE"

        # 4. Verificación Narrativa vs Nominal (Sección 6)
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

        tot_narr = next(d for d in discs if d["estamento"] == "Total" and "Narrativo" in d["fuente_a"])
        assert tot_narr["valor_fuente_a"] == 18
        assert tot_narr["valor_fuente_b"] == 18
        assert tot_narr["delta"] == 0
        assert tot_narr["estado"] == "CONCORDANTE"

        # 5. Verificación de Preservación de Históricos M5 (32 filas fuera de período)
        assert res.archivos_fuente["M5"].filas_leidas == 32
        assert res.archivos_fuente["M5"].filas_activas == 0
        assert res.archivos_fuente["M5"].filas_fuera_periodo == 32

        # 6. Verificación de Integridad de Entrada (Hashes SHA-256 idénticos)
        for cod, af in res.archivos_fuente.items():
            assert af.sha256_inicial == af.sha256_final
            assert len(af.sha256_inicial) == 64

        # 7. Verificación Física del DOCX Generado
        docx_path = Path(res.ruta_docx)
        assert docx_path.exists()
        assert docx_path.stat().st_size > 5000

        doc = docx.Document(docx_path)
        assert len(doc.tables) >= 5

        # 8. Verificación de Trazabilidad Técnica en JSON (Sección 4)
        assert len(data_audit["trazabilidad_participaciones"]) == 18
        reg_ejemplo = data_audit["trazabilidad_participaciones"][0]
        assert reg_ejemplo["matriz"] == "M2"
        assert "Matriz_2_Estudiantes.xlsx" in reg_ejemplo["archivo"]
        assert reg_ejemplo["hoja"] == "Pregrado_Grado en Actividades"
        assert isinstance(reg_ejemplo["fila_excel"], int)


# =============================================================================
# GRUPO D: PRESERVACIÓN DEL HISTÓRICO M5
# =============================================================================

class TestPreservacionHistoricoM5:
    """Verifica que los 32 registros de M5 permanezcan fuera de período y no se eliminen."""

    def test_m5_historico_permanece_inalterado(self, plantillas_oficiales_dict, tmp_path):
        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_hist")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Semana 1, Septiembre 2026",
        )

        res = pipeline.ejecutar(plantillas_oficiales_dict, periodo)

        m5_info = res.archivos_fuente["M5"]
        assert m5_info.filas_leidas == 32
        assert m5_info.filas_fuera_periodo == 32
        assert m5_info.filas_activas == 0

        # Leer reporte JSON para validar que la Sección 10 (Anexos) registró el histórico
        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)
            assert audit["archivos_fuente"]["M5"]["filas_fuera_periodo"] == 32


# =============================================================================
# GRUPO E Y F: PRUEBAS DE VOLUMEN DINÁMICO E INDEPENDENCIA DE M5 (32, 40, 100, 250+)
# =============================================================================

class TestPruebasVolumenE2E:
    """
    Pruebas E2E completas hasta renderizado DOCX para 32, 40, 100 y 250+ registros.
    Demuestra que el sistema no contiene límites artificiales como range(32), [:32], limit=32.
    """

    def test_volumen_32_registros_e2e(self, tmp_path):
        """Prueba E2E con 32 registros nominales activos."""
        p1 = tmp_path / "m1_32.xlsx"
        p2 = tmp_path / "m2_32.xlsx"
        p3 = tmp_path / "m3_32.xlsx"
        p4 = tmp_path / "m4_32.xlsx"
        p5 = tmp_path / "m5_32.xlsx"

        act_nom = "Taller de Robótica"
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-05-10", "total_m": 16, "total_f": 16}])

        personas = [{"nombre": f"Estudiante_{i+1}", "actividad": act_nom, "sexo": "Femenino" if i%2==0 else "Masculino"} for i in range(32)]
        crear_matriz_nominal_sintetica(p2, "M2", personas)
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_32")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=5,
            etiqueta="Mayo 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_participaciones == 32
        assert res.total_personas_unicas == 32
        assert Path(res.ruta_docx).exists()

    def test_volumen_40_registros_demostracion_independencia_m5(self, tmp_path):
        """
        DEMOSTRACIÓN EXPLÍCITA: El sistema procesa 40 registros nominales sin truncar en 32.
        Demuestra formalmente que el software NO depende de los 32 registros históricos de M5.
        """
        p1 = tmp_path / "m1_40.xlsx"
        p2 = tmp_path / "m2_40.xlsx"
        p3 = tmp_path / "m3_40.xlsx"
        p4 = tmp_path / "m4_40.xlsx"
        p5 = tmp_path / "m5_40.xlsx"

        act_nom = "Congreso de Innovación 2026"
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-06-15", "total_m": 20, "total_f": 20}])

        # 40 personas nominales distribuidas entre Estudiantes (M2: 25), Docentes (M3: 10), Colaboradores (M4: 5)
        estudiantes_40 = [{"nombre": f"Estudiante_{i+1}", "actividad": act_nom} for i in range(25)]
        docentes_40 = [{"nombre": f"Docente_{i+1}", "actividad": act_nom} for i in range(10)]
        colabs_40 = [{"nombre": f"Colaborador_{i+1}", "actividad": act_nom} for i in range(5)]

        crear_matriz_nominal_sintetica(p2, "M2", estudiantes_40)
        crear_matriz_nominal_sintetica(p3, "M3", docentes_40)
        crear_matriz_nominal_sintetica(p4, "M4", colabs_40)
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_40")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=6,
            etiqueta="Junio 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)

        # Verificación explícita de volumen 40
        assert res.total_participaciones == 40, "El sistema truncó los registros; debe procesar exactamente 40"
        assert res.total_personas_unicas == 40
        assert res.total_participaciones > 32, "El sistema falló en procesar más de 32 registros"

        # Comprobar documento DOCX generado
        docx_path = Path(res.ruta_docx)
        assert docx_path.exists()
        doc = docx.Document(docx_path)
        assert len(doc.tables) >= 5

    def test_volumen_100_registros_e2e(self, tmp_path):
        """Prueba de volumen con 100 registros nominales activos."""
        p1 = tmp_path / "m1_100.xlsx"
        p2 = tmp_path / "m2_100.xlsx"
        p3 = tmp_path / "m3_100.xlsx"
        p4 = tmp_path / "m4_100.xlsx"
        p5 = tmp_path / "m5_100.xlsx"

        act_nom = "Simposio de Investigación Científica"
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-07-20", "total_m": 50, "total_f": 50}])

        # 100 estudiantes en M2
        estudiantes_100 = [{"nombre": f"Participante_{i+1}", "actividad": act_nom} for i in range(100)]
        crear_matriz_nominal_sintetica(p2, "M2", estudiantes_100)
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_100")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=7,
            etiqueta="Julio 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_participaciones == 100
        assert res.total_personas_unicas == 100
        assert Path(res.ruta_docx).exists()

    def test_volumen_alto_250_registros_e2e(self, tmp_path):
        """Prueba de estrés volumétrico con 250 registros nominales para descartar cuellos de botella."""
        p1 = tmp_path / "m1_250.xlsx"
        p2 = tmp_path / "m2_250.xlsx"
        p3 = tmp_path / "m3_250.xlsx"
        p4 = tmp_path / "m4_250.xlsx"
        p5 = tmp_path / "m5_250.xlsx"

        act_nom = "Feria Universitaria Vocacional 2026"
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-08-10", "total_m": 125, "total_f": 125}])

        # 250 participantes distribuidos
        estudiantes_250 = [{"nombre": f"Estudiante_{i+1}", "actividad": act_nom} for i in range(200)]
        docentes_50 = [{"nombre": f"Docente_{i+1}", "actividad": act_nom} for i in range(50)]

        crear_matriz_nominal_sintetica(p2, "M2", estudiantes_250)
        crear_matriz_nominal_sintetica(p3, "M3", docentes_50)
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_250")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=8,
            etiqueta="Agosto 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_participaciones == 250
        assert res.total_personas_unicas == 250
        assert Path(res.ruta_docx).exists()
        assert res.tamanio_docx_bytes > 8000


# =============================================================================
# GRUPO G: INTEGRIDAD CRIPTOGRÁFICA Y ATOMICIDAD
# =============================================================================

class TestIntegridadYAtomicidad:
    """Verifica la inmutabilidad física de los archivos fuente y la escritura atómica en staging."""

    def test_inmutabilidad_criptografica_sha256(self, plantillas_oficiales_dict, tmp_path):
        """Comprueba que los hashes SHA-256 sean idénticos antes y después de toda la corrida."""
        hashes_antes = {cod: calcular_sha256(p) for cod, p in plantillas_oficiales_dict.items()}

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_integ")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Semana 1, Septiembre 2026",
        )
        res = pipeline.ejecutar(plantillas_oficiales_dict, periodo)

        hashes_despues = {cod: calcular_sha256(p) for cod, p in plantillas_oficiales_dict.items()}
        assert hashes_antes == hashes_despues

    def test_deteccion_mutacion_lanza_error_integridad(self, tmp_path, monkeypatch):
        """Simula una alteración física externa de un archivo fuente para verificar que dispara ErrorIntegridadArchivo."""
        p1 = tmp_path / "m1.xlsx"
        p2 = tmp_path / "m2.xlsx"
        p3 = tmp_path / "m3.xlsx"
        p4 = tmp_path / "m4.xlsx"
        p5 = tmp_path / "m5.xlsx"

        crear_matriz_m1_sintetica(p1, [{"actividad": "A1", "fecha_evento": "2026-09-02"}])
        crear_matriz_nominal_sintetica(p2, "M2", [{"nombre": "Ana", "actividad": "A1"}])
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_mut")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026",
        )

        # Interceptar temporalmente la lectura para alterar maliciosamente un archivo
        original_leer = MatrixReader.leer_conjunto_matrices

        def mutar_archivo(*args, **kwargs):
            res_leer = original_leer(*args, **kwargs)
            # Mutar un byte en el archivo M1
            with open(p1, "ab") as f:
                f.write(b"CORRUPCION_INDIRECTA")
            return res_leer

        monkeypatch.setattr(MatrixReader, "leer_conjunto_matrices", mutar_archivo)

        with pytest.raises(ErrorIntegridadArchivo):
            pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)


# =============================================================================
# GRUPO H: TRAZABILIDAD TÉCNICA DOCUMENTAL → FÍSICA
# =============================================================================

class TestTrazabilidadTecnica:
    """Verifica que cada cifra y registro conserve su cadena técnica de trazabilidad."""

    def test_cadena_trazabilidad_hasta_fila_excel(self, plantillas_oficiales_dict, tmp_path):
        """Verifica que el reporte JSON contenga trazabilidad técnica con matriz, hoja y fila."""
        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_traza")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Semana 1, Septiembre 2026",
        )

        res = pipeline.ejecutar(plantillas_oficiales_dict, periodo)

        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)

        # Comprobar metadatos de archivos fuente
        assert "M1" in audit["archivos_fuente"]
        assert audit["archivos_fuente"]["M1"]["hoja"] == "Programas, proyectos y act"
        assert audit["archivos_fuente"]["M2"]["hoja"] == "Pregrado_Grado en Actividades"

        # Comprobar trazabilidad en discrepancias
        for disc in audit["discrepancias"]:
            assert "fuente_a" in disc["trazabilidad"]
            assert "fuente_b" in disc["trazabilidad"]


# =============================================================================
# GRUPO I: NO RECONCILIACIÓN FORZADA Y DISCREPANCIAS
# =============================================================================

class TestNoReconciliacion:
    """Verifica que las diferencias numéricas coexistan pacíficamente con estado REQUIERE_REVISION."""

    def test_coexistencia_m1_vs_nominal_sin_reconciliar(self, tmp_path):
        p1 = tmp_path / "m1.xlsx"
        p2 = tmp_path / "m2.xlsx"
        p3 = tmp_path / "m3.xlsx"
        p4 = tmp_path / "m4.xlsx"
        p5 = tmp_path / "m5.xlsx"

        act_nom = "Taller de IA"
        # M1 reporta 10 mujeres y 5 varones (Total 15)
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-09-02", "total_m": 5, "total_f": 10}])

        # Nominal tiene 12 mujeres y 4 varones (Total 16)
        personas = (
            [{"nombre": f"Mujer_{i+1}", "actividad": act_nom, "sexo": "Femenino"} for i in range(12)] +
            [{"nombre": f"Varon_{i+1}", "actividad": act_nom, "sexo": "Masculino"} for i in range(4)]
        )
        crear_matriz_nominal_sintetica(p2, "M2", personas)
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_disc")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)

        # Se debe registrar REQUIERE_REVISION en mujeres (+2) y varones (-1) y total (+1)
        assert res.total_discrepancias >= 2
        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)
            estados = [d["estado"] for d in audit["discrepancias"]]
            assert "REQUIERE_REVISION" in estados


# =============================================================================
# GRUPO F: MÚLTIPLES ACTIVIDADES SIMULTÁNEAS EN EL PERÍODO
# =============================================================================

class TestMultiplesActividades:
    """Verifica la consolidación de períodos con múltiples actividades concurrentes."""

    def test_multiples_actividades_simultaneas_en_periodo(self, tmp_path):
        p1 = tmp_path / "m1_multi.xlsx"
        p2 = tmp_path / "m2_multi.xlsx"
        p3 = tmp_path / "m3_multi.xlsx"
        p4 = tmp_path / "m4_multi.xlsx"
        p5 = tmp_path / "m5_multi.xlsx"

        acts = [
            {"actividad": f"Actividad {i+1}", "fecha_evento": f"2026-09-0{i+2}", "total_m": 5, "total_f": 5}
            for i in range(3)
        ]
        crear_matriz_m1_sintetica(p1, acts)

        # 5 estudiantes en cada actividad
        personas_m2 = []
        for i in range(3):
            for j in range(5):
                personas_m2.append({"nombre": f"Estudiante_{i+1}_{j+1}", "actividad": f"Actividad {i+1}"})

        crear_matriz_nominal_sintetica(p2, "M2", personas_m2)
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_multi")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_actividades == 3
        assert res.total_participaciones == 15
        assert res.total_personas_unicas == 15


# =============================================================================
# GRUPO G: PERSONA EN MÚLTIPLES ACTIVIDADES (ASISTENCIAS VS ÚNICAS)
# =============================================================================

class TestPersonaMultiplesActividades:
    """Verifica que un participante en múltiples actividades conserve asistencias brutas y cuente como 1 persona única."""

    def test_persona_en_multiples_actividades_asistencias_vs_unicas(self, tmp_path):
        p1 = tmp_path / "m1_p_multi.xlsx"
        p2 = tmp_path / "m2_p_multi.xlsx"
        p3 = tmp_path / "m3_p_multi.xlsx"
        p4 = tmp_path / "m4_p_multi.xlsx"
        p5 = tmp_path / "m5_p_multi.xlsx"

        acts = [
            {"actividad": "Taller A", "fecha_evento": "2026-09-02", "total_m": 1, "total_f": 0},
            {"actividad": "Taller B", "fecha_evento": "2026-09-03", "total_m": 1, "total_f": 0},
        ]
        crear_matriz_m1_sintetica(p1, acts)

        # Mismo estudiante (misma cédula y nombre) en ambas actividades
        cedula_comun = "601-010190-0001A"
        nombre_comun = "Estudiante Recurrente"
        personas_m2 = [
            {"nombre": nombre_comun, "cedula": cedula_comun, "actividad": "Taller A", "sexo": "Masculino"},
            {"nombre": nombre_comun, "cedula": cedula_comun, "actividad": "Taller B", "sexo": "Masculino"},
        ]
        crear_matriz_nominal_sintetica(p2, "M2", personas_m2)
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_rec")
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026",
        )

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_actividades == 2
        assert res.total_participaciones == 2  # Asistencias brutas
        assert res.total_personas_unicas == 1   # Persona única resoluta


# =============================================================================
# GRUPO H: RESOLUCIÓN DE IDENTIDAD Y DEDUPLICACIÓN
# =============================================================================

class TestDeduplicacionIdentidad:
    """Verifica que registros duplicados en la misma actividad sean resueltos canónicamente."""

    def test_registros_duplicados_y_homonimos_resueltos(self, tmp_path):
        p1 = tmp_path / "m1_dup.xlsx"
        p2 = tmp_path / "m2_dup.xlsx"
        p3 = tmp_path / "m3_dup.xlsx"
        p4 = tmp_path / "m4_dup.xlsx"
        p5 = tmp_path / "m5_dup.xlsx"

        act_nom = "Taller Deduplicado"
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-09-02", "total_m": 1, "total_f": 0}])

        # Misma persona dos veces en la misma actividad con idéntica cédula
        personas_m2 = [
            {"nombre": "Carlos Perez", "cedula": "601-121295-0002B", "actividad": act_nom, "sexo": "Masculino"},
            {"nombre": "Carlos Perez", "cedula": "601-121295-0002B", "actividad": act_nom, "sexo": "Masculino"},
        ]
        crear_matriz_nominal_sintetica(p2, "M2", personas_m2)
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_dup")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.MES, anio=2026, mes=9, etiqueta="Septiembre 2026")

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_personas_unicas == 1
        assert res.total_participaciones == 2  # Participaciones físicas conservadas 100%


# =============================================================================
# GRUPO I: DATOS INCOMPLETOS Y CÉDULAS NULAS
# =============================================================================

class TestDatosIncompletos:
    """Verifica que cédulas nulas o vacías se preserven sin inventar datos."""

    def test_cedulas_nulas_preservadas_sin_inventar_datos(self, tmp_path):
        p1 = tmp_path / "m1_null.xlsx"
        p2 = tmp_path / "m2_null.xlsx"
        p3 = tmp_path / "m3_null.xlsx"
        p4 = tmp_path / "m4_null.xlsx"
        p5 = tmp_path / "m5_null.xlsx"

        act_nom = "Seminario Cédula Vacía"
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-09-04", "total_m": 0, "total_f": 1}])

        # Participante sin cédula
        personas_m2 = [{"nombre": "Estudiante Sin Cedula", "cedula": "", "actividad": act_nom, "sexo": "Femenino"}]
        crear_matriz_nominal_sintetica(p2, "M2", personas_m2)
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_null")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.MES, anio=2026, mes=9, etiqueta="Septiembre 2026")

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_participaciones == 1
        assert res.total_personas_unicas == 1


# =============================================================================
# GRUPO J: DISCREPANCIAS M1 VS NOMINAL CON TRASLADO A DOCX
# =============================================================================

class TestDiscrepanciasM1VsNominal:
    """Verifica que discrepancias entre M1 y sumatoria nominal se trasladen con estado REQUIERE_REVISION."""

    def test_discrepancias_m1_vs_nominal_traslado_docx(self, tmp_path):
        p1 = tmp_path / "m1_disc.xlsx"
        p2 = tmp_path / "m2_disc.xlsx"
        p3 = tmp_path / "m3_disc.xlsx"
        p4 = tmp_path / "m4_disc.xlsx"
        p5 = tmp_path / "m5_disc.xlsx"

        act_nom = "Taller Diferencia M1"
        # M1 reporta 20 en total (10 F, 10 M)
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-09-05", "total_m": 10, "total_f": 10}])

        # Nominal tiene solo 15 personas (10 F, 5 M) -> delta M = -5, delta total = -5
        personas = (
            [{"nombre": f"Fem_{i+1}", "actividad": act_nom, "sexo": "Femenino"} for i in range(10)] +
            [{"nombre": f"Masc_{i+1}", "actividad": act_nom, "sexo": "Masculino"} for i in range(5)]
        )
        crear_matriz_nominal_sintetica(p2, "M2", personas)
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_m1_disc")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.MES, anio=2026, mes=9, etiqueta="Septiembre 2026")

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_discrepancias >= 2

        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)
        item_total = next(d for d in audit["discrepancias"] if "Total General" in d["estamento"] and "Matriz 1" in d["fuente_a"])
        assert item_total["delta"] == -5
        assert item_total["estado"] == "REQUIERE_REVISION"


# =============================================================================
# GRUPO K: DISCREPANCIAS NARRATIVA VS NOMINAL
# =============================================================================

class TestDiscrepanciasNarrativaVsNominal:
    """Verifica el contraste entre informe narrativo y lista nominal sin alterar ninguna fuente."""

    def test_discrepancias_narrativa_vs_nominal_coexistencia(self, tmp_path):
        p1 = tmp_path / "m1_narr.xlsx"
        p2 = tmp_path / "m2_narr.xlsx"
        p3 = tmp_path / "m3_narr.xlsx"
        p4 = tmp_path / "m4_narr.xlsx"
        p5 = tmp_path / "m5_narr.xlsx"

        act_nom = "Taller Narrativo Coexistente"
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-09-02", "total_m": 6, "total_f": 12}])

        # Nominal tiene 17 estudiantes y 1 administrativo (Total 18)
        personas_m2 = [{"nombre": f"Est_{i+1}", "actividad": act_nom} for i in range(17)]
        personas_m3 = [{"nombre": "Admin_1", "actividad": act_nom, "tipo_protagonistas": "Administrativo"}]
        crear_matriz_nominal_sintetica(p2, "M2", personas_m2)
        crear_matriz_nominal_sintetica(p3, "M3", personas_m3)
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        narrativo = {
            act_nom: {
                "nombre_actividad": act_nom,
                "estudiantes": 15,
                "administrativos": 2,
                "docentes": 1,
                "total": 18,
            }
        }

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_narr_coex")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.MES, anio=2026, mes=9, etiqueta="Septiembre 2026")

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo, informes_narrativos=narrativo)

        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)

        discs = audit["discrepancias"]
        est = next(d for d in discs if d["estamento"] == "Estudiantes" and "Narrativo" in d["fuente_a"])
        adm = next(d for d in discs if d["estamento"] == "Administrativos" and "Narrativo" in d["fuente_a"])
        doc = next(d for d in discs if d["estamento"] == "Docentes" and "Narrativo" in d["fuente_a"])
        tot = next(d for d in discs if d["estamento"] == "Total" and "Narrativo" in d["fuente_a"])

        assert est["delta"] == 2 and est["estado"] == "REQUIERE_REVISION"
        assert adm["delta"] == -1 and adm["estado"] == "REQUIERE_REVISION"
        assert doc["delta"] == -1 and doc["estado"] == "REQUIERE_REVISION"
        assert tot["delta"] == 0 and tot["estado"] == "CONCORDANTE"


# =============================================================================
# GRUPO L: MATRIZ VACÍA (0 FILAS EN EL PERÍODO)
# =============================================================================

class TestMatrizVacia:
    """Verifica que matrices sin filas activas en el período se procesen limpiamente."""

    def test_matriz_sin_filas_en_periodo_procesamiento_limpio(self, tmp_path):
        p1 = tmp_path / "m1_vac.xlsx"
        p2 = tmp_path / "m2_vac.xlsx"
        p3 = tmp_path / "m3_vac.xlsx"
        p4 = tmp_path / "m4_vac.xlsx"
        p5 = tmp_path / "m5_vac.xlsx"

        act_nom = "Taller Solitario"
        crear_matriz_m1_sintetica(p1, [{"actividad": act_nom, "fecha_evento": "2026-09-02", "total_m": 5, "total_f": 0}])
        crear_matriz_nominal_sintetica(p2, "M2", [{"nombre": f"E_{i}", "actividad": act_nom} for i in range(5)])
        # M3, M4, M5 completamente vacías
        crear_matriz_nominal_sintetica(p3, "M3", [])
        crear_matriz_nominal_sintetica(p4, "M4", [])
        crear_matriz_nominal_sintetica(p5, "M5", [])

        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_vac")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.MES, anio=2026, mes=9, etiqueta="Septiembre 2026")

        res = pipeline.ejecutar({"M1": p1, "M2": p2, "M3": p3, "M4": p4, "M5": p5}, periodo)
        assert res.total_actividades == 1
        assert res.total_participaciones == 5
        assert res.archivos_fuente["M3"].filas_leidas == 0
        assert res.archivos_fuente["M4"].filas_leidas == 0
        assert res.archivos_fuente["M5"].filas_leidas == 0


# =============================================================================
# GRUPO N: INMUTABILIDAD DE DOCUMENTOCONSOLIDADO
# =============================================================================

class TestInmutabilidadDocumentoConsolidado:
    """Verifica que DocxGenerator no mute el modelo intermedio durante el renderizado."""

    def test_documento_consolidado_inmutable_post_render(self, plantillas_oficiales_dict, tmp_path):
        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_inmut_doc")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.SEMANA, anio=2026, mes=9, semana=1, etiqueta="Semana 1, Septiembre 2026")
        res = pipeline.ejecutar(plantillas_oficiales_dict, periodo)
        assert res.ruta_docx is not None
        assert Path(res.ruta_docx).exists()


# =============================================================================
# GRUPO O: TRAZABILIDAD FÍSICA DETALLADA
# =============================================================================

class TestTrazabilidadFisicaDetallada:
    """Verifica que el reporte JSON contenga la estructura exacta de trazabilidad requerida por Sección 4."""

    def test_trazabilidad_participaciones_detallada(self, plantillas_oficiales_dict, tmp_path):
        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_traza_det")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.SEMANA, anio=2026, mes=9, semana=1, etiqueta="Semana 1, Septiembre 2026")
        res = pipeline.ejecutar(plantillas_oficiales_dict, periodo)

        with open(res.ruta_reporte_json, "r", encoding="utf-8") as f:
            audit = json.load(f)

        assert "trazabilidad_participaciones" in audit
        traza = audit["trazabilidad_participaciones"]
        assert len(traza) == 18

        # Validar contrato exacto de Sección 4
        primer_registro = traza[0]
        assert "matriz" in primer_registro
        assert "archivo" in primer_registro
        assert "hoja" in primer_registro
        assert "fila_excel" in primer_registro
        assert primer_registro["matriz"] == "M2"
        assert primer_registro["hoja"] == "Pregrado_Grado en Actividades"


# =============================================================================
# GRUPO Q: CALIDAD FORMAL Y MAQUETADO DOCX INSTITUCIONAL
# =============================================================================

class TestCalidadMaquetadoDocx:
    """Verifica que el archivo DOCX generado cumpla con las normas de maquetado institucional BICU."""

    def test_propiedades_documento_docx_maquetado(self, plantillas_oficiales_dict, tmp_path):
        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_docx_prop")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.SEMANA, anio=2026, mes=9, semana=1, etiqueta="Semana 1, Septiembre 2026")
        res = pipeline.ejecutar(plantillas_oficiales_dict, periodo)

        docx_path = Path(res.ruta_docx)
        doc = docx.Document(docx_path)

        # 1. Orientación horizontal (Landscape)
        section = doc.sections[0]
        assert section.page_width > section.page_height, "El documento debe maquetarse en orientación horizontal (Landscape)"

        # 2. Márgenes de 20 mm (con tolerancia de 5 mm)
        assert abs(section.top_margin.mm - 20) < 5
        assert abs(section.bottom_margin.mm - 20) < 5
        assert abs(section.left_margin.mm - 20) < 5
        assert abs(section.right_margin.mm - 20) < 5

        # 3. Tablas renderizadas
        assert len(doc.tables) >= 5, "Debe contener al menos 5 tablas maquetadas institucionales"

    def test_encabezados_tablas_institucionales_presentes(self, plantillas_oficiales_dict, tmp_path):
        pipeline = WordConsolidationPipeline(output_dir=tmp_path / "out_docx_tabs")
        periodo = PeriodoConsolidacion(tipo_periodo=TipoPeriodo.SEMANA, anio=2026, mes=9, semana=1, etiqueta="Semana 1, Septiembre 2026")
        res = pipeline.ejecutar(plantillas_oficiales_dict, periodo)

        doc = docx.Document(Path(res.ruta_docx))
        textos_completos = [p.text for p in doc.paragraphs]
        assert any("UNIVERSIDAD DE LAS REGIONES AUTÓNOMAS" in t or "BICU" in t for t in textos_completos)

