"""
tests.test_word_consolidator.test_fase_16_8_f2_product_b

Suite de certificación técnica para la Fase 16.8-F.2:
Corrección Controlada de Defectos en Product B (Informe Institucional).

Cubre exhaustivamente:
- C1: Propagación explícita de departamento_institucional desde metadatos
- C2: Política DECLARADO_M1 explícita sin depender de default NOMINAL
- C3: Eje estratégico nominal preservado como metadata complementaria de auditoría sin falsear M1
- C4: Descripción proveniente exclusivamente de resultados M1 (eliminado hasattr descripcion)
- C5/C8: Concatenación de evento y evento_otros de M1 sin pérdida
- C6: Prohibición absoluta de fallback silencioso dato_declarado=None -> nominal en spec.py
- C7: Inclusión estricta de estamentos bajo DECLARADO_M1 (solo declaraciones positivas)
- Pruebas A, B, C, D, E, F, G, H
- T01 a T14 planificados
- Aislamiento e inmunidad de Product A y M5 histórico
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from docx import Document

from app.word_consolidator.document.institutional_models import (
    ActividadInstitucional,
    ConteoSexoInstitucional,
    InformeSemanalInstitucional,
    ProtagonistaEstamentoInstitucional,
    TipoEstamentoInstitucional,
    TrazabilidadActividad,
)
from app.word_consolidator.document.institutional_transformer import InstitutionalReportTransformer
from app.word_consolidator.document.orchestrator import (
    DocumentOutputOrchestrator,
    DocumentGenerationResult,
)
from app.word_consolidator.document.transformer import DocumentTransformer
from app.word_consolidator.docx_generator.renderer import DocxGenerator
from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ConsolidationEngine,
    FilaLeidaM1,
    FilaLeidaNominal,
    ResultadoConsolidacion,
    TotalesM1,
)
from app.word_consolidator.institutional_docx.generator import (
    InstitutionalDocxGenerator,
    generate_institutional_docx,
)
from app.word_consolidator.institutional_docx.spec import (
    ModoFuenteDatosEnum,
    _extraer_conteo_segun_modo,
    build_table_layout_spec,
)
from app.word_consolidator.models import (
    MetadatosInstitucionales,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
    ResultadoAuditoriaDiscrepancias,
    TipoPeriodo,
)
from app.word_consolidator.pipeline import WordConsolidationPipeline
from app.word_consolidator.readers.matrix_reader import MatrixReader


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def periodo_septiembre_2026() -> PeriodoConsolidacion:
    return PeriodoConsolidacion(
        tipo_periodo=TipoPeriodo.SEMANA,
        anio=2026,
        mes=9,
        semana=1,
        etiqueta="Septiembre 2026 — Semana 1",
    )


@pytest.fixture
def metadatos_innovacion() -> MetadatosInstitucionales:
    return MetadatosInstitucionales(
        departamento_institucional="Innovación y Emprendimiento",
        responsable_elaboracion="Dra. Kenia",
    )


@pytest.fixture
def auditoria_vacia() -> ResultadoAuditoriaDiscrepancias:
    return ResultadoAuditoriaDiscrepancias(
        total_actividades_evaluadas=1,
        actividades_concordantes=1,
        actividades_con_discrepancias=0,
        total_discrepancias_activas=0,
        total_concordancias=1,
        invariante_verificada=True,
        informes_por_actividad={},
        discrepancias_globales=[],
    )


# ============================================================================
# TEST A & T01: MATCH M1 + NOMINAL CON TOTALES DECLARADOS
# ============================================================================

def test_t01_test_a_match_m1_completo_product_b_usa_declarados(periodo_septiembre_2026, metadatos_innovacion):
    """
    Test A & T01: Fixture independiente con M1 completo + nominales concordantes/discrepantes.
    Bajo DECLARADO_M1, Product B debe reflejar exactamente las cifras declaradas de M1,
    incluyendo docentes si M1 los declaró positivos.
    """
    fila_m1 = FilaLeidaM1(
        hoja="Consolidado",
        fila=2,
        sede="Bilwi",
        actividad="Taller de Innovación y Emprendimiento",
        ambito="11.41.67",
        evento="Taller",
        evento_otros="Especializado",
        resultados="Estudiantes y docentes capacitados con éxito.",
        departamento="RACCN",
        municipio="Puerto Cabezas",
        total_atencion_m=7,
        total_atencion_f=12,
        total_estud_m_grado=6,
        total_estud_f_grado=11,
        total_docente_m=1,
        total_docente_f=0,
        total_administrativos_m=0,
        total_administrativos_f=1,
    )
    totales_m1 = TotalesM1(
        total_general=19,
        mujeres=12,
        varones=7,
        total_estudiantes=17,
        estudiantes_m=6,
        estudiantes_f=11,
        total_docentes=1,
        docentes_m=1,
        docentes_f=0,
        total_administrativos=1,
        administrativos_m=0,
        administrativos_f=1,
        fila_m1=fila_m1,
    )

    act_cons = ActividadConsolidada(
        clave_negocio=("taller de innovacion y emprendimiento", "bilwi", None),
        nombre_actividad=fila_m1.actividad,
        sede=fila_m1.sede,
        departamento=fila_m1.departamento,
        municipio=fila_m1.municipio,
        eje=fila_m1.ambito,
        tipo_evento=f"{fila_m1.evento} / {fila_m1.evento_otros}",
        resultados=fila_m1.resultados,
        fuente_m1=fila_m1,
        totales_m1=totales_m1,
        trazabilidad={"fuente_m1": {}},
    )

    consolidacion = ResultadoConsolidacion(
        actividades=[act_cons],
        fuentes={
            "M1": RegistroFuenteArchivo(
                codigo_matriz="M1",
                nombre_archivo="M1.xlsx",
                ruta_archivo="output/M1.xlsx",
                hash_sha256="a" * 64,
                total_filas_leidas=1,
                filas_en_periodo=1,
            )
        },
        total_actividades=1,
        total_asistencia_bruta=19,
        total_personas_unicas=19,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )

    informe = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        departamento_responsable=metadatos_innovacion.departamento_institucional,
        politica_presentacion="DECLARADO_M1",
    )

    assert informe.departamento_responsable == "Innovación y Emprendimiento"
    assert len(informe.actividades) == 1
    act_doc = informe.actividades[0]
    assert act_doc.eje_vinculado == "11.41.67"
    assert act_doc.tipo_actividad == "Taller / Especializado"
    assert act_doc.descripcion == "Estudiantes y docentes capacitados con éxito."
    assert act_doc.totales_actividad.mujeres == 12
    assert act_doc.totales_actividad.varones == 7
    assert act_doc.totales_actividad.total == 19

    # Verificar inclusión de estamentos
    estamentos_map = {p.estamento_tipo: p for p in act_doc.protagonistas}
    assert TipoEstamentoInstitucional.ESTUDIANTES in estamentos_map
    assert TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO in estamentos_map
    assert TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS in estamentos_map
    assert estamentos_map[TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS].conteo_presentacion.total == 1
    assert estamentos_map[TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS].conteo_presentacion.varones == 1


# ============================================================================
# TEST B & T15: GOLDEN CASE REAL SEPTIEMBRE 2026 SEMANA 1
# ============================================================================

def test_t15_test_b_golden_case_real_archivos_actuales(tmp_path, periodo_septiembre_2026, metadatos_innovacion):
    """
    Test B & T15: Ejecuta el pipeline completo sobre los archivos Excel reales en output/.
    Verifica que el informe institucional reproduce fielmente la verdad empírica:
    - Estudiantes = 17
    - Administrativos = 1
    - Docentes = 0 (no aparece en tabla)
    - Totales: M = 12, V = 6, Total = 18
    - Departamento institucional = 'Innovación y Emprendimiento'
    - Eje declarado = '' (M1.ambito=None), pero trazabilidad complementaria conserva '11.41.67'
    - Descripción = '' (M1.resultados=None)
    - Tipo actividad = '' (M1.evento=None)
    """
    dir_output = Path("output")
    if not (dir_output / "Matriz_1_Consolidado_Actividades.xlsx").exists():
        pytest.skip("Archivos reales en output/ no disponibles en este entorno")

    pipeline = WordConsolidationPipeline(output_dir=tmp_path)
    res = pipeline.ejecutar(
        fuentes=dir_output,
        periodo=periodo_septiembre_2026,
        metadatos=metadatos_innovacion,
        generar_tecnico=True,
        generar_institucional=True,
    )

    assert res.status_institucional == "SUCCESS"
    assert res.ruta_docx_institucional is not None
    assert Path(res.ruta_docx_institucional).exists()

    # Abrir el DOCX generado de Product B y comprobar tabla
    doc = Document(res.ruta_docx_institucional)
    tabla = doc.tables[0]
    # Comprobar departamento en cabecera de la tabla
    assert "Innovación y Emprendimiento" in tabla.rows[0].cells[1].text

    # Leer también directamente de ConsolidationEngine sobre las matrices reales
    conjunto = MatrixReader.leer_conjunto_matrices({
        "M1": dir_output / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": dir_output / "Matriz_2_Estudiantes.xlsx",
        "M3": dir_output / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": dir_output / "Matriz_4_Colaboradores.xlsx",
        "M5": dir_output / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    })
    filtrado, _ = pipeline._filtrar_fechas_estricto(conjunto, periodo_septiembre_2026)
    consolidacion = ConsolidationEngine.consolidar(filtrado, conjunto.fuentes)
    assert len(consolidacion.actividades) == 1
    act_cons = consolidacion.actividades[0]
    assert act_cons.fuente_m1 is not None
    assert len(act_cons.participaciones) == 18
    assert act_cons.trazabilidad.get("eje_complementario_nominal") == "11.41.67"

    informe = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        departamento_responsable=metadatos_innovacion.departamento_institucional,
        politica_presentacion="DECLARADO_M1",
    )
    assert informe.departamento_responsable == "Innovación y Emprendimiento"
    act_doc = informe.actividades[0]
    assert act_doc.eje_vinculado == ""
    assert act_doc.tipo_actividad == ""
    assert act_doc.descripcion == ""
    assert act_doc.totales_actividad.mujeres == 12
    assert act_doc.totales_actividad.varones == 6
    assert act_doc.totales_actividad.total == 18

    estamentos_map = {p.estamento_tipo: p for p in act_doc.protagonistas}
    assert TipoEstamentoInstitucional.ESTUDIANTES in estamentos_map
    assert TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO in estamentos_map
    assert TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS not in estamentos_map
    assert len(act_doc.protagonistas) == 2


# ============================================================================
# TEST C & T05: DOCENTE DECLARADO M1 > 0, NOMINAL = 0
# ============================================================================

def test_t05_test_c_docente_declarado_m1_positivo_nominal_cero(periodo_septiembre_2026):
    """
    Test C & T05: M1 declara Docentes = 1 (0M / 1V / 1) pero no hay registros nominales en M3.
    Bajo DECLARADO_M1, Docentes SÍ debe aparecer en la tabla institucional.
    """
    fila_m1 = FilaLeidaM1(
        hoja="Consolidado",
        fila=2,
        sede="Bilwi",
        actividad="Actividad con Docente Declarado",
        total_atencion_m=1,
        total_atencion_f=0,
        total_docente_m=1,
        total_docente_f=0,
    )
    totales_m1 = TotalesM1(
        total_general=1,
        mujeres=0,
        varones=1,
        total_docentes=1,
        docentes_m=1,
        docentes_f=0,
        fila_m1=fila_m1,
    )

    act_cons = ActividadConsolidada(
        clave_negocio=("actividad con docente declarado", "bilwi", None),
        nombre_actividad=fila_m1.actividad,
        sede=fila_m1.sede,
        fuente_m1=fila_m1,
        totales_m1=totales_m1,
    )

    consolidacion = ResultadoConsolidacion(
        actividades=[act_cons],
        fuentes={},
        total_actividades=1,
        total_asistencia_bruta=1,
        total_personas_unicas=1,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )

    informe = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        politica_presentacion="DECLARADO_M1",
    )

    act_doc = informe.actividades[0]
    estamentos_map = {p.estamento_tipo: p for p in act_doc.protagonistas}
    assert TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS in estamentos_map
    doc_est = estamentos_map[TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS]
    assert doc_est.conteo_presentacion.mujeres == 0
    assert doc_est.conteo_presentacion.varones == 1
    assert doc_est.conteo_presentacion.total == 1


# ============================================================================
# TEST D & T04: DOCENTE M1 = 0, NOMINAL > 0
# ============================================================================

def test_t04_test_d_docente_m1_cero_nominal_positivo_no_aparece(periodo_septiembre_2026):
    """
    Test D & T04: M1 declara Docentes = 0, pero nominalmente existen 2 docentes en M3.
    Bajo DECLARADO_M1, Docentes NO debe aparecer en la tabla institucional.
    """
    fila_m1 = FilaLeidaM1(
        hoja="Consolidado",
        fila=2,
        sede="Bilwi",
        actividad="Actividad Sin Docentes Declarados",
        total_atencion_m=5,
        total_atencion_f=5,
        total_estud_m_grado=5,
        total_estud_f_grado=5,
        total_docente_m=0,
        total_docente_f=0,
    )
    totales_m1 = TotalesM1(
        total_general=10,
        mujeres=5,
        varones=5,
        total_estudiantes=10,
        estudiantes_m=5,
        estudiantes_f=5,
        total_docentes=0,
        docentes_m=0,
        docentes_f=0,
        fila_m1=fila_m1,
    )

    act_cons = ActividadConsolidada(
        clave_negocio=("actividad sin docentes declarados", "bilwi", None),
        nombre_actividad=fila_m1.actividad,
        sede=fila_m1.sede,
        fuente_m1=fila_m1,
        totales_m1=totales_m1,
    )
    # Simular totales nominales con docentes existentes
    act_cons.totales_nominales.docentes = 2
    act_cons.totales_nominales.docentes_m = 1
    act_cons.totales_nominales.docentes_f = 1

    consolidacion = ResultadoConsolidacion(
        actividades=[act_cons],
        fuentes={},
        total_actividades=1,
        total_asistencia_bruta=12,
        total_personas_unicas=12,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )

    informe = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        politica_presentacion="DECLARADO_M1",
    )

    act_doc = informe.actividades[0]
    estamentos_map = {p.estamento_tipo: p for p in act_doc.protagonistas}
    assert TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS not in estamentos_map
    assert TipoEstamentoInstitucional.ESTUDIANTES in estamentos_map


# ============================================================================
# TEST E: EJE M1 PRESENTE
# ============================================================================

def test_test_e_eje_m1_presente_se_propaga(periodo_septiembre_2026):
    """
    Test E: Cuando M1 sí tiene ámbito declarado, se propaga fielmente como eje_vinculado.
    """
    fila_m1 = FilaLeidaM1(
        hoja="Consolidado",
        fila=2,
        sede="Bilwi",
        actividad="Actividad con Ambito M1",
        ambito="11.41.67",
        total_atencion_m=1,
        total_atencion_f=1,
        total_estud_m_grado=1,
        total_estud_f_grado=1,
    )
    totales_m1 = TotalesM1(
        total_general=2,
        mujeres=1,
        varones=1,
        total_estudiantes=2,
        estudiantes_m=1,
        estudiantes_f=1,
        fila_m1=fila_m1,
    )
    act_cons = ActividadConsolidada(
        clave_negocio=("actividad con ambito m1", "bilwi", None),
        nombre_actividad=fila_m1.actividad,
        sede=fila_m1.sede,
        eje=fila_m1.ambito,
        fuente_m1=fila_m1,
        totales_m1=totales_m1,
    )
    consolidacion = ResultadoConsolidacion(
        actividades=[act_cons],
        fuentes={},
        total_actividades=1,
        total_asistencia_bruta=2,
        total_personas_unicas=2,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )
    informe = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        politica_presentacion="DECLARADO_M1",
    )
    assert informe.actividades[0].eje_vinculado == "11.41.67"


# ============================================================================
# TEST F & T08: EJE M1 AUSENTE + EJE NOMINAL PRESENTE
# ============================================================================

def test_t08_test_f_eje_m1_ausente_nominal_presente_metadata_audit(periodo_septiembre_2026):
    """
    Test F & T08: M1.ambito es None, pero el registro nominal tiene eje_estrategia = '11.41.67'.
    Product B:
    - eje_vinculado debe quedar vacío ('' / ausente en M1, no falsear procedencia).
    - La trazabilidad debe registrar '11.41.67' como metadata complementaria de auditoría.
    """
    fila_m1 = FilaLeidaM1(
        hoja="Consolidado",
        fila=2,
        sede="Bilwi",
        actividad="Actividad Sin Ambito M1",
        ambito=None,
        total_atencion_m=1,
        total_atencion_f=1,
        total_estud_m_grado=1,
        total_estud_f_grado=1,
    )
    totales_m1 = TotalesM1(
        total_general=2,
        mujeres=1,
        varones=1,
        total_estudiantes=2,
        estudiantes_m=1,
        estudiantes_f=1,
        fila_m1=fila_m1,
    )
    act_cons = ActividadConsolidada(
        clave_negocio=("actividad sin ambito m1", "bilwi", None),
        nombre_actividad=fila_m1.actividad,
        sede=fila_m1.sede,
        eje=None,
        fuente_m1=fila_m1,
        totales_m1=totales_m1,
        trazabilidad={
            "eje_complementario_nominal": "11.41.67",
            "procedencia_eje_complementario": "NOMINAL_AUDITORIA",
        },
    )
    consolidacion = ResultadoConsolidacion(
        actividades=[act_cons],
        fuentes={},
        total_actividades=1,
        total_asistencia_bruta=2,
        total_personas_unicas=2,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )
    informe = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        politica_presentacion="DECLARADO_M1",
    )
    act_doc = informe.actividades[0]
    # Eje declarado no se inventa
    assert act_doc.eje_vinculado == ""
    # Trazabilidad conserva procedencia
    assert act_doc.trazabilidad.detalles.get("eje_complementario_nominal") == "11.41.67"
    assert act_doc.trazabilidad.detalles.get("procedencia_eje_complementario") == "NOMINAL_AUDITORIA"
    assert act_doc.trazabilidad.detalles.get("m1_ambito_declarado") == "AUSENTE"


# ============================================================================
# TEST G & T09: EVENTO Y EVENTO_OTROS M1 CONCATENADOS
# ============================================================================

def test_t09_test_g_evento_y_evento_otros_m1(periodo_septiembre_2026):
    """
    Test G & T09: M1 evento y evento_otros se concatenan con ' / '.
    Si ambos son None, tipo_actividad queda vacío.
    Nunca se sustituye por nominal.evento.
    """
    # Caso 1: Ambos presentes en M1
    fila_m1_completa = FilaLeidaM1(
        hoja="Consolidado",
        fila=2,
        sede="Bilwi",
        actividad="Actividad A",
        evento="Taller",
        evento_otros="Desarrollo Web",
        total_atencion_m=1,
        total_atencion_f=1,
        total_estud_m_grado=1,
        total_estud_f_grado=1,
    )
    totales_1 = TotalesM1(
        total_general=2, mujeres=1, varones=1, total_estudiantes=2,
        estudiantes_m=1, estudiantes_f=1, fila_m1=fila_m1_completa,
    )
    partes = [v.strip() for v in [fila_m1_completa.evento, fila_m1_completa.evento_otros] if v and v.strip()]
    act_1 = ActividadConsolidada(
        clave_negocio=("actividad a", "bilwi", None),
        nombre_actividad=fila_m1_completa.actividad,
        sede=fila_m1_completa.sede,
        tipo_evento=" / ".join(partes),
        fuente_m1=fila_m1_completa,
        totales_m1=totales_1,
    )

    # Caso 2: Ambos ausentes en M1
    fila_m1_vacia = FilaLeidaM1(
        hoja="Consolidado",
        fila=3,
        sede="Bilwi",
        actividad="Actividad B",
        evento=None,
        evento_otros=None,
        total_atencion_m=1,
        total_atencion_f=1,
        total_estud_m_grado=1,
        total_estud_f_grado=1,
    )
    totales_2 = TotalesM1(
        total_general=2, mujeres=1, varones=1, total_estudiantes=2,
        estudiantes_m=1, estudiantes_f=1, fila_m1=fila_m1_vacia,
    )
    act_2 = ActividadConsolidada(
        clave_negocio=("actividad b", "bilwi", None),
        nombre_actividad=fila_m1_vacia.actividad,
        sede=fila_m1_vacia.sede,
        tipo_evento=None,
        fuente_m1=fila_m1_vacia,
        totales_m1=totales_2,
    )

    consolidacion = ResultadoConsolidacion(
        actividades=[act_1, act_2],
        fuentes={},
        total_actividades=2,
        total_asistencia_bruta=4,
        total_personas_unicas=4,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )
    informe = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        politica_presentacion="DECLARADO_M1",
    )
    assert informe.actividades[0].tipo_actividad == "Taller / Desarrollo Web"
    assert informe.actividades[1].tipo_actividad == ""


# ============================================================================
# TEST H & T06: FALLBACK PROHIBIDO: DATO_DECLARADO=NONE NO RETORNA NOMINAL
# ============================================================================

def test_t06_test_h_fallback_prohibido_retorna_cero_neutro():
    """
    Test H & T06: En spec.py, _extraer_conteo_segun_modo con DECLARADO_M1 y dato_declarado=None
    NUNCA debe devolver el dato nominal ni conteo_presentacion.
    Debe devolver ConteoSexoInstitucional(0, 0, 0).
    """
    estamento = ProtagonistaEstamentoInstitucional(
        estamento_tipo=TipoEstamentoInstitucional.ESTUDIANTES,
        denominacion_visible="Estudiantes",
        conteo_presentacion=ConteoSexoInstitucional(mujeres=15, varones=10, total=25),
        dato_nominal=ConteoSexoInstitucional(mujeres=15, varones=10, total=25),
        dato_declarado=None,  # Ausencia de datos M1
    )

    conteo = _extraer_conteo_segun_modo(estamento, ModoFuenteDatosEnum.DECLARADO_M1)
    assert conteo.mujeres == 0
    assert conteo.varones == 0
    assert conteo.total == 0
    assert conteo != estamento.dato_nominal
    assert conteo != estamento.conteo_presentacion


# ============================================================================
# T02: MISMATCH CLAVE: NOMINAL SIN M1 NO SUPLANTA M1
# ============================================================================

def test_t02_mismatch_clave_nominal_sin_m1_no_suplanta_m1(periodo_septiembre_2026):
    """
    T02: Actividad nominal huérfana (sin match M1).
    Bajo DECLARADO_M1, ningún dato nominal se hace pasar por declaración M1.
    """
    act_huerfana = ActividadConsolidada(
        clave_negocio=("actividad huérfana", "bilwi", None),
        nombre_actividad="Actividad Huérfana",
        sede="Bilwi",
        fuente_m1=None,
        totales_m1=None,
    )
    act_huerfana.totales_nominales.estudiantes = 10
    act_huerfana.totales_nominales.estudiantes_f = 6
    act_huerfana.totales_nominales.estudiantes_m = 4

    consolidacion = ResultadoConsolidacion(
        actividades=[act_huerfana],
        fuentes={},
        total_actividades=1,
        total_asistencia_bruta=10,
        total_personas_unicas=10,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )

    informe = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        politica_presentacion="DECLARADO_M1",
    )
    act_doc = informe.actividades[0]
    # No se incluye ningún estamento porque declarado_positivo es False
    assert len(act_doc.protagonistas) == 0
    assert act_doc.totales_actividad.total == 0


# ============================================================================
# T03: POLÍTICA DECLARADO_M1 EXPLÍCITA EN ORQUESTADOR
# ============================================================================

def test_t03_politica_declarado_m1_explicita_en_orquestador(periodo_septiembre_2026, auditoria_vacia, tmp_path):
    """
    T03: Verifica que DocumentOutputOrchestrator pasa explícitamente politica_presentacion='DECLARADO_M1'
    y modo_fuente=ModoFuenteDatosEnum.DECLARADO_M1.
    """
    consolidacion = ResultadoConsolidacion(
        actividades=[],
        fuentes={},
        total_actividades=0,
        total_asistencia_bruta=0,
        total_personas_unicas=0,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )

    with patch("app.word_consolidator.document.orchestrator.InstitutionalReportTransformer.transformar") as mock_trans, \
         patch("app.word_consolidator.document.orchestrator.InstitutionalDocxGenerator") as mock_gen_cls:
        
        mock_trans.return_value = MagicMock(spec=InformeSemanalInstitucional)
        mock_gen_inst = MagicMock()
        mock_gen_cls.return_value = mock_gen_inst

        res = DocumentOutputOrchestrator.orchestrate_generation(
            consolidacion=consolidacion,
            auditoria=auditoria_vacia,
            periodo=periodo_septiembre_2026,
            output_dir=tmp_path,
            generar_tecnico=False,
            generar_institucional=True,
            metadatos=MetadatosInstitucionales(departamento_institucional="Innovación y Emprendimiento"),
        )

        assert res.overall_status == "SUCCESS"
        mock_trans.assert_called_once()
        _, kwargs_trans = mock_trans.call_args
        assert kwargs_trans.get("politica_presentacion") == "DECLARADO_M1"
        assert kwargs_trans.get("departamento_responsable") == "Innovación y Emprendimiento"

        mock_gen_cls.assert_called_once_with(modo_fuente=ModoFuenteDatosEnum.DECLARADO_M1)


# ============================================================================
# T07: DEPARTAMENTO INSTITUCIONAL SE PROPAGA DESDE METADATOS
# ============================================================================

def test_t07_departamento_institucional_se_propaga_desde_metadatos(periodo_septiembre_2026):
    """
    T07: Si metadatos.departamento_institucional está presente, se asigna.
    Si no está disponible, no explota y recurre a comportamiento seguro.
    """
    consolidacion = ResultadoConsolidacion(
        actividades=[],
        fuentes={},
        total_actividades=0,
        total_asistencia_bruta=0,
        total_personas_unicas=0,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )

    # Con departamento explícito
    inf1 = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        departamento_responsable="Innovación y Emprendimiento",
        politica_presentacion="DECLARADO_M1",
    )
    assert inf1.departamento_responsable == "Innovación y Emprendimiento"

    # Sin departamento
    inf2 = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        departamento_responsable=None,
        politica_presentacion="DECLARADO_M1",
    )
    assert inf2.departamento_responsable == "Área No Especificada"


# ============================================================================
# T10: DESCRIPCIÓN PROVIENE EXCLUSIVAMENTE DE RESULTADOS M1
# ============================================================================

def test_t10_descripcion_proviene_de_resultados_m1(periodo_septiembre_2026):
    """
    T10: M1 resultados se usa fielmente como descripción.
    Si resultados es None, queda vacío; no se usa hasattr('descripcion').
    """
    fila_m1 = FilaLeidaM1(
        hoja="Consolidado",
        fila=2,
        sede="Bilwi",
        actividad="Actividad X",
        resultados="Logros alcanzados verificados",
        total_atencion_m=1,
        total_atencion_f=1,
        total_estud_m_grado=1,
        total_estud_f_grado=1,
    )
    totales_m1 = TotalesM1(
        total_general=2, mujeres=1, varones=1, total_estudiantes=2,
        estudiantes_m=1, estudiantes_f=1, fila_m1=fila_m1,
    )
    act_cons = ActividadConsolidada(
        clave_negocio=("actividad x", "bilwi", None),
        nombre_actividad=fila_m1.actividad,
        sede=fila_m1.sede,
        resultados=fila_m1.resultados,
        fuente_m1=fila_m1,
        totales_m1=totales_m1,
    )
    consolidacion = ResultadoConsolidacion(
        actividades=[act_cons],
        fuentes={},
        total_actividades=1,
        total_asistencia_bruta=2,
        total_personas_unicas=2,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )
    inf = InstitutionalReportTransformer.transformar(
        consolidacion=consolidacion,
        politica_presentacion="DECLARADO_M1",
    )
    assert inf.actividades[0].descripcion == "Logros alcanzados verificados"


# ============================================================================
# T11: M5 HISTÓRICO PRESERVADO INTACTO
# ============================================================================

def test_t11_m5_historico_32_registros_preservados():
    """
    T11: Verifica que Matriz 5 preserva intactos sus 32 registros históricos
    y no contiene registros activos para Septiembre 2026 Semana 1.
    """
    dir_output = Path("output")
    m5_path = dir_output / "Matriz_5_Protagonistas_Beneficiados.xlsx"
    if not m5_path.exists():
        pytest.skip("Matriz 5 real no encontrada en output/")

    from app.word_consolidator.readers.matrix_reader import MatrixReader
    from app.word_consolidator.readers.period_filter import PeriodFilter
    from app.word_consolidator.models import ConjuntoMatricesLeidas

    filas_m5, _ = MatrixReader.leer_matriz_nominal(m5_path, "M5")
    assert len(filas_m5) == 32, f"Se esperaban 32 registros históricos en M5, se obtuvieron {len(filas_m5)}"

    periodo = PeriodoConsolidacion(
        tipo_periodo=TipoPeriodo.SEMANA,
        anio=2026,
        mes=9,
        semana=1,
        etiqueta="Septiembre 2026 — Semana 1",
    )
    conjunto = ConjuntoMatricesLeidas(
        actividades_m1=[],
        estudiantes_m2=[],
        academicos_admin_m3=[],
        colaboradores_m4=[],
        beneficiarios_m5=filas_m5,
    )
    filtrado = PeriodFilter.filtrar(conjunto=conjunto, periodo=periodo)
    assert len(filtrado.beneficiarios_en_periodo) == 0
    assert len(filtrado.nominales_historicos_fuera_periodo) == 32


# ============================================================================
# T12: PRODUCT A CONTINÚA SIN CAMBIOS
# ============================================================================

def test_t12_product_a_continua_sin_cambios(periodo_septiembre_2026, auditoria_vacia, tmp_path):
    """
    T12: Product A (Dossier Técnico) sigue funcionando exactamente como antes.
    DocumentTransformer y DocxGenerator generan el documento sin afectación.
    """
    consolidacion = ResultadoConsolidacion(
        actividades=[],
        fuentes={},
        total_actividades=0,
        total_asistencia_bruta=0,
        total_personas_unicas=0,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )
    doc_tecnico = DocumentTransformer.transformar(
        consolidacion=consolidacion,
        auditoria=auditoria_vacia,
        periodo=periodo_septiembre_2026,
    )
    assert doc_tecnico is not None
    out_file = tmp_path / "test_tecnico.docx"
    DocxGenerator.generate(doc_tecnico, out_file, landscape=True)
    assert out_file.exists()
    assert out_file.stat().st_size > 0


# ============================================================================
# T13: A+B DESDE UNA SOLA CONSOLIDACIÓN
# ============================================================================

def test_t13_a_plus_b_desde_una_sola_consolidacion(periodo_septiembre_2026, auditoria_vacia, tmp_path):
    """
    T13: DocumentOutputOrchestrator genera tanto Product A como Product B
    desde un único objeto ResultadoConsolidacion.
    """
    consolidacion = ResultadoConsolidacion(
        actividades=[],
        fuentes={},
        total_actividades=0,
        total_asistencia_bruta=0,
        total_personas_unicas=0,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_septiembre_2026,
    )
    res = DocumentOutputOrchestrator.orchestrate_generation(
        consolidacion=consolidacion,
        auditoria=auditoria_vacia,
        periodo=periodo_septiembre_2026,
        output_dir=tmp_path,
        generar_tecnico=True,
        generar_institucional=True,
        metadatos=MetadatosInstitucionales(departamento_institucional="Innovación y Emprendimiento"),
    )
    assert res.overall_status == "SUCCESS"
    assert res.tecnico.status == "SUCCESS"
    assert res.institucional.status == "SUCCESS"
    assert Path(res.tecnico.path).exists()
    assert Path(res.institucional.path).exists()
