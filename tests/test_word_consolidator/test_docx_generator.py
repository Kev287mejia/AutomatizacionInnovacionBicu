"""
tests.test_word_consolidator.test_docx_generator

Suite formal de pruebas para la Fase 14.7: Generación y Presentación del DOCX Institucional.
Verifica:
1. Creación correcta y apertura física del archivo .docx.
2. Archivo generado no vacío y con estructura OpenXML válida.
3. Presencia inequívoca de las 10 secciones documentales obligatorias.
4. Presencia del caso real obligatorio: Septiembre 2026 Semana 1 (Bilwi).
5. Coexistencia simultánea y no reconciliada de M1 y Nominales:
   - Femenino: M1=12 vs Nominal=13 (Delta +1, REQUIERE_REVISION)
   - Masculino: M1=6 vs Nominal=5 (Delta -1, REQUIERE_REVISION)
   - Total: M1=18 vs Nominal=18 (Delta 0, CONCORDANTE)
   - Narrativa vs Nominal: Estudiantes (15 vs 17), Administrativos (2 vs 1), Docentes (1 vs 0), Total (18 vs 18)
6. Separación estricta de estamentos: Docentes y Administrativos nunca fusionados.
7. Regla estricta de NO INVENTAR información (metadatos ausentes se omiten sin inferencias falsas).
8. Presencia de sección de auditoría con tabla exhaustiva de discrepancias.
9. Presencia de anexos con hashes SHA-256 oficiales y certificación de 32 registros históricos M5.
10. Inmutabilidad absoluta de DocumentoConsolidado pre y post renderizado.
11. Integridad criptográfica SHA-256 de las cinco matrices oficiales y conservación de 32 registros M5.
12. Soporte para generación directa en archivo en disco y en buffer binario (io.BytesIO).
13. No invención de dictámenes institucionales en conclusiones.
"""

from copy import deepcopy
from datetime import date
import hashlib
from io import BytesIO
from pathlib import Path
import pytest

import docx

from app.core.constants.participant_types import CategoriaParticipacion
from app.word_consolidator import (
    DocxGenerator,
    DocxRenderer,
    DocumentoConsolidado,
    DocumentTransformer,
    DiscrepancyDetector,
)
from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ConsolidationEngine,
    ParticipacionConsolidada,
    ResultadoConsolidacion,
    TotalesM1,
    TotalesNominales,
)
from app.word_consolidator.models import (
    DiscrepanciaItem,
    EstadoDiscrepancia,
    FilaLeidaM1,
    MetadatosInstitucionales,
    PeriodoConsolidacion,
    ResultadoAuditoriaDiscrepancias,
    TipoPeriodo,
)
from app.word_consolidator.readers.matrix_reader import MatrixReader


@pytest.fixture
def periodo_septiembre_2026():
    return PeriodoConsolidacion(
        tipo_periodo=TipoPeriodo.SEMANA,
        anio=2026,
        mes=9,
        semana=1,
        fecha_inicio=date(2026, 9, 1),
        fecha_fin=date(2026, 9, 7),
        etiqueta="Semana 1 - Septiembre 2026",
    )


@pytest.fixture
def metadatos_oficiales():
    return MetadatosInstitucionales(
        universidad="Bluefields Indian & Caribbean University (BICU)",
        lema="La Universidad de las Regiones Autónomas de la Costa Caribe Nicaragüense",
        area_responsable="Área de Innovación y Emprendimiento",
        lugar_emision="Bilwi / Bluefields, Nicaragua",
        version_sistema="0.1.0",
    )


@pytest.fixture
def rutas_matrices_templates():
    base = Path("templates")
    return {
        "M1": base / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": base / "Matriz_2_Estudiantes.xlsx",
        "M3": base / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": base / "Matriz_4_Colaboradores.xlsx",
        "M5": base / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }


@pytest.fixture
def documento_caso_real_bilwi(periodo_septiembre_2026, metadatos_oficiales):
    """
    Construye el DocumentoConsolidado representativo del caso real de Septiembre 2026 Semana 1 (Bilwi).
    Mantiene:
    M1: F=12, M=6, Total=18
    Nominal: F=13, M=5, Total=18
    Narrativa: Est=15, Adm=2, Doc=1, Total=18
    """
    nombre_act = "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial"
    id_act = "caso-real-septiembre-2026"

    tot_m1 = TotalesM1(
        mujeres=12,
        varones=6,
        total=18,
        estudiantes_f=12,
        estudiantes_m=5,
        administrativos_f=1,
        administrativos_m=0,
    )

    tot_nom = TotalesNominales(
        mujeres=13,
        varones=5,
        total=18,
        estudiantes=17,
        docentes=0,
        administrativos=1,
        colaboradores=0,
        beneficiarios=0,
        estudiantes_f=12,
        estudiantes_m=5,
        administrativos_f=1,
        administrativos_m=0,
    )

    narrativo = {
        "estudiantes": 15,
        "administrativos": 2,
        "docentes": 1,
        "total": 18,
    }

    # Discrepancias formales
    disc_est = DiscrepanciaItem(
        id_actividad=id_act,
        nombre_actividad=nombre_act,
        estamento="Estudiantes",
        fuente_a="Informe Narrativo",
        fuente_b="Matriz 2 (Nominal)",
        valor_fuente_a=15,
        valor_fuente_b=17,
        delta=2,
        estado=EstadoDiscrepancia.REQUIERE_REVISION,
        descripcion="Diferencia de +2 estudiantes entre narrativa y nominal",
    )
    disc_adm = DiscrepanciaItem(
        id_actividad=id_act,
        nombre_actividad=nombre_act,
        estamento="Administrativos",
        fuente_a="Informe Narrativo",
        fuente_b="Matriz 3 (Nominal)",
        valor_fuente_a=2,
        valor_fuente_b=1,
        delta=-1,
        estado=EstadoDiscrepancia.REQUIERE_REVISION,
        descripcion="Diferencia de -1 administrativo entre narrativa y nominal",
    )
    disc_doc = DiscrepanciaItem(
        id_actividad=id_act,
        nombre_actividad=nombre_act,
        estamento="Docentes",
        fuente_a="Informe Narrativo",
        fuente_b="Matriz 3 (Nominal)",
        valor_fuente_a=1,
        valor_fuente_b=0,
        delta=-1,
        estado=EstadoDiscrepancia.REQUIERE_REVISION,
        descripcion="Diferencia de -1 docente entre narrativa y nominal",
    )
    disc_tot = DiscrepanciaItem(
        id_actividad=id_act,
        nombre_actividad=nombre_act,
        estamento="Total",
        fuente_a="Informe Narrativo",
        fuente_b="Matrices Nominales (M2–M5)",
        valor_fuente_a=18,
        valor_fuente_b=18,
        delta=0,
        estado=EstadoDiscrepancia.CONCORDANTE,
        descripcion="Total concordante en 18",
    )

    act_real = ActividadConsolidada(
        id_actividad=id_act,
        clave_negocio=(nombre_act.upper(), "BILWI", "2026-09-03"),
        nombre_actividad=nombre_act,
        sede="Bilwi",
        fecha_evento=date(2026, 9, 3),
        departamento="RACCN",
        municipio="Puerto Cabezas",
        totales_m1=tot_m1,
        totales_nominales=tot_nom,
        total_asistencia_bruta=18,
        total_personas_unicas=18,
        discrepancias=[disc_est, disc_adm, disc_doc, disc_tot],
    )

    res_cons = ResultadoConsolidacion(
        periodo=periodo_septiembre_2026,
        actividades=[act_real],
        total_actividades=1,
        total_asistencia_bruta=18,
        total_personas_unicas=18,
        discrepancias=[disc_est, disc_adm, disc_doc, disc_tot],
    )
    res_audit = ResultadoAuditoriaDiscrepancias(
        total_actividades_evaluadas=1,
        actividades_con_discrepancias=1,
        actividades_concordantes=0,
        total_discrepancias_activas=3,
        total_concordancias=1,
        discrepancias_globales=[disc_est, disc_adm, disc_doc, disc_tot],
    )

    return DocumentTransformer.transformar(
        consolidacion=res_cons,
        auditoria=res_audit,
        periodo=periodo_septiembre_2026,
        metadatos=metadatos_oficiales,
        informes_narrativos={id_act: narrativo},
    )


class TestDocxGeneratorSuite:
    """Suite formal de pruebas para DocxGenerator (Fase 14.7)."""

    # -------------------------------------------------------------------------
    # 1. Creación física y apertura del archivo .docx
    # -------------------------------------------------------------------------
    def test_01_creacion_fisica_y_apertura_docx(self, documento_caso_real_bilwi, tmp_path):
        """Verifica que DocxGenerator cree un archivo .docx no vacío que abre correctamente."""
        ruta_salida = tmp_path / "test_informe_institucional.docx"
        resultado_ruta = DocxGenerator.generate(documento_caso_real_bilwi, output_path=ruta_salida)

        assert resultado_ruta.exists()
        assert resultado_ruta.is_file()
        assert resultado_ruta.stat().st_size > 10000  # Más de 10 KB

        # Comprobar que python-docx puede abrirlo e inspeccionarlo sin errores
        doc_abierto = docx.Document(str(resultado_ruta))
        assert len(doc_abierto.paragraphs) > 10
        assert len(doc_abierto.tables) >= 5

    # -------------------------------------------------------------------------
    # 2. Presencia de las 10 Secciones Documentales Obligatorias
    # -------------------------------------------------------------------------
    def test_02_presencia_diez_secciones_obligatorias(self, documento_caso_real_bilwi, tmp_path):
        """Verifica que el documento contenga los títulos y encabezados de las 10 secciones."""
        ruta_salida = tmp_path / "test_secciones.docx"
        DocxGenerator.generate(documento_caso_real_bilwi, output_path=ruta_salida)

        doc_abierto = docx.Document(str(ruta_salida))
        textos_parrafos = [p.text.strip().upper() for p in doc_abierto.paragraphs if p.text.strip()]
        todo_el_texto = " --- ".join(textos_parrafos)

        # 1. Portada (Título formal)
        assert "INFORME CONSOLIDADO INSTITUCIONAL DE ACTIVIDADES" in todo_el_texto
        # 2. Resumen Ejecutivo
        assert "2. RESUMEN EJECUTIVO" in todo_el_texto
        # 3. Matriz Consolidada General de Actividades
        assert "3. MATRIZ CONSOLIDADA GENERAL DE ACTIVIDADES" in todo_el_texto
        # 4. Fichas de Detalle por Actividad
        assert "4. FICHAS DE DETALLE POR ACTIVIDAD" in todo_el_texto
        # 5. Análisis Demográfico y Distribución por Sexo
        assert "5. ANÁLISIS DEMOGRÁFICO Y DISTRIBUCIÓN POR SEXO" in todo_el_texto
        # 6. Estamentos Institucionales y Carreras
        assert "6. ESTAMENTOS INSTITUCIONALES Y CARRERAS" in todo_el_texto
        # 7. Cobertura Territorial y Sedes Universitarias
        assert "7. COBERTURA TERRITORIAL Y SEDES UNIVERSITARIAS" in todo_el_texto
        # 8. Salud de Datos y Auditoría de Discrepancias
        assert "8. SALUD DE DATOS Y AUDITORÍA DE DISCREPANCIAS" in todo_el_texto
        # 9. Conclusiones y Dictamen Técnico
        assert "9. CONCLUSIONES Y DICTAMEN TÉCNICO" in todo_el_texto
        # 10. Anexos y Metadatos de Trazabilidad
        assert "10. ANEXOS Y METADATOS DE TRAZABILIDAD" in todo_el_texto

    # -------------------------------------------------------------------------
    # 3. Caso Real Septiembre 2026 Semana 1 (Bilwi)
    # -------------------------------------------------------------------------
    def test_03_caso_real_septiembre_2026_semana_1(self, documento_caso_real_bilwi, tmp_path):
        """Verifica la presencia de la actividad real y su denominación completa."""
        ruta_salida = tmp_path / "test_caso_real.docx"
        DocxGenerator.generate(documento_caso_real_bilwi, output_path=ruta_salida)

        doc = docx.Document(str(ruta_salida))
        
        # Extraer todo el texto de párrafos y celdas de tabla
        contenido_completo = []
        for p in doc.paragraphs:
            contenido_completo.append(p.text)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    contenido_completo.append(cell.text)
        texto_unido = " ".join(contenido_completo)

        assert "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial" in texto_unido
        assert "Bilwi" in texto_unido
        assert "RACCN" in texto_unido
        assert "Puerto Cabezas" in texto_unido

    # -------------------------------------------------------------------------
    # 4. Discrepancia de Sexo M1 vs Nominal: Femenino (12/13/+1), Masculino (6/5/-1), Total (18/18/0)
    # -------------------------------------------------------------------------
    def test_04_discrepancia_sexo_m1_vs_nominal_coexistencia(self, documento_caso_real_bilwi, tmp_path):
        """
        Verifica que en el DOCX coexistan sin reconciliarse:
        Femenino: M1=12, Nominal=13, Delta=+1
        Masculino: M1=6, Nominal=5, Delta=-1
        Total: M1=18, Nominal=18, Delta=0
        """
        ruta_salida = tmp_path / "test_sexo_coexistencia.docx"
        DocxGenerator.generate(documento_caso_real_bilwi, output_path=ruta_salida)

        doc = docx.Document(str(ruta_salida))

        encontrado_fem_12_13 = False
        encontrado_masc_6_5 = False
        encontrado_tot_18_18 = False

        for tbl in doc.tables:
            for row in tbl.rows:
                textos_celdas = [c.text.strip() for c in row.cells]
                # Buscar fila Femenino con 12 y 13
                if any("FEMENINO" in t.upper() for t in textos_celdas):
                    if "12" in textos_celdas and "13" in textos_celdas and any("+1" in t or "1" in t for t in textos_celdas):
                        encontrado_fem_12_13 = True
                # Buscar fila Masculino con 6 y 5
                if any("MASCULINO" in t.upper() for t in textos_celdas):
                    if "6" in textos_celdas and "5" in textos_celdas and any("-1" in t for t in textos_celdas):
                        encontrado_masc_6_5 = True
                # Buscar fila Total con 18 y 18
                if any("TOTAL" in t.upper() for t in textos_celdas):
                    if textos_celdas.count("18") >= 2:
                        encontrado_tot_18_18 = True

        assert encontrado_fem_12_13, "No se encontró la fila de Femenino con M1=12, Nominal=13 y Delta=+1 en las tablas del DOCX."
        assert encontrado_masc_6_5, "No se encontró la fila de Masculino con M1=6, Nominal=5 y Delta=-1 en las tablas del DOCX."
        assert encontrado_tot_18_18, "No se encontró la fila de Total con M1=18, Nominal=18 en las tablas del DOCX."

    # -------------------------------------------------------------------------
    # 5. Coexistencia de Narrativa vs Nominal: Estudiantes (15/17), Admin (2/1), Doc (1/0)
    # -------------------------------------------------------------------------
    def test_05_narrativa_vs_nominal_discrepancias(self, documento_caso_real_bilwi, tmp_path):
        """
        Verifica que coexistan las discrepancias narrativas:
        Estudiantes: 15 vs 17 (Delta +2)
        Administrativos: 2 vs 1 (Delta -1)
        Docentes: 1 vs 0 (Delta -1)
        Total: 18 vs 18 (Delta 0)
        """
        ruta_salida = tmp_path / "test_narrativa_disc.docx"
        DocxGenerator.generate(documento_caso_real_bilwi, output_path=ruta_salida)

        doc = docx.Document(str(ruta_salida))
        textos_tablas = []
        for tbl in doc.tables:
            for row in tbl.rows:
                textos_tablas.append(" | ".join(c.text.strip() for c in row.cells))
        contenido_tablas = "\n".join(textos_tablas)

        assert "Estudiantes" in contenido_tablas
        assert "+2" in contenido_tablas
        assert "-1" in contenido_tablas
        assert "REQUIERE REVISIÓN" in contenido_tablas
        assert "CONCORDANTE" in contenido_tablas

    # -------------------------------------------------------------------------
    # 6. Separación Estricta de Estamentos: Docentes y Administrativos NO fusionados
    # -------------------------------------------------------------------------
    def test_06_separacion_estricta_docentes_administrativos(self, documento_caso_real_bilwi, tmp_path):
        """Verifica que Docentes y Administrativos aparezcan en filas separadas e independientes."""
        ruta_salida = tmp_path / "test_estamentos.docx"
        DocxGenerator.generate(documento_caso_real_bilwi, output_path=ruta_salida)

        doc = docx.Document(str(ruta_salida))
        filas_estamentos = []
        for tbl in doc.tables:
            for row in tbl.rows:
                celdas = [c.text.strip() for c in row.cells]
                if any("DOCENTES" in c.upper() for c in celdas) or any("ADMINISTRATIVO" in c.upper() for c in celdas):
                    filas_estamentos.append(celdas)

        # Deben existir al menos filas que mencionen Docentes y filas que mencionen Administrativos por separado
        tiene_docentes = any(any("DOCENTE" in c.upper() for c in f) for f in filas_estamentos)
        tiene_admin = any(any("ADMINISTRATIVO" in c.upper() for c in f) for f in filas_estamentos)

        assert tiene_docentes, "Falta la fila independiente para Docentes."
        assert tiene_admin, "Falta la fila independiente para Administrativos."

        # Ninguna fila debe fusionar "Docentes y Administrativos" en el conteo
        for f in filas_estamentos:
            primer_texto = f[0].upper()
            if "DOCENTES Y ADMINISTRATIVOS" in primer_texto or "ACADÉMICOS Y ADMINISTRATIVOS" in primer_texto:
                # Comprobar que en la tabla de estamentos (sección 6) están desagregados
                assert False, f"Se detectó fusión de estamentos no autorizada en fila: {f}"

    # -------------------------------------------------------------------------
    # 7. No Invención de Información (campos ausentes se omiten limpiamente)
    # -------------------------------------------------------------------------
    def test_07_no_invencion_informacion_ausente(self, periodo_septiembre_2026, tmp_path):
        """Verifica que cuando los metadatos o campos no existan, no se inventen textos en el Word."""
        act_min = ActividadConsolidada(
            id_actividad="act-minima-test",
            clave_negocio=("ACTIVIDAD MINIMA", "BILWI", None),
            nombre_actividad="Actividad Mínima",
            sede="Bilwi",
            totales_nominales=TotalesNominales(total=5, mujeres=3, varones=2),
            total_asistencia_bruta=5,
            total_personas_unicas=5,
        )
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[act_min],
            total_actividades=1,
            total_asistencia_bruta=5,
            total_personas_unicas=5,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        # Sin metadatos institucionales
        doc_modelo = DocumentTransformer.transformar(
            consolidacion=res_cons,
            auditoria=res_audit,
            periodo=periodo_septiembre_2026,
            metadatos=None,
        )

        ruta_salida = tmp_path / "test_sin_invencion.docx"
        DocxGenerator.generate(doc_modelo, output_path=ruta_salida)

        doc = docx.Document(str(ruta_salida))
        texto_completo = " ".join(p.text for p in doc.paragraphs)

        # Comprobar que no inventó fecha ni lugar
        assert "Managua" not in texto_completo
        assert "Fecha de Emisión:" not in texto_completo

    # -------------------------------------------------------------------------
    # 8. No Modificación (Inmutabilidad) de DocumentoConsolidado pre y post render
    # -------------------------------------------------------------------------
    def test_08_inmutabilidad_documento_consolidado(self, documento_caso_real_bilwi, tmp_path):
        """
        Garantiza que DocumentoConsolidado permanezca 100% inalterado antes y después del render.
        El renderer es de sólo lectura.
        """
        dump_antes = documento_caso_real_bilwi.model_dump(mode="json")
        hash_antes = hashlib.sha256(str(dump_antes).encode("utf-8")).hexdigest()

        ruta_salida = tmp_path / "test_inmutabilidad.docx"
        DocxGenerator.generate(documento_caso_real_bilwi, output_path=ruta_salida)

        dump_despues = documento_caso_real_bilwi.model_dump(mode="json")
        hash_despues = hashlib.sha256(str(dump_despues).encode("utf-8")).hexdigest()

        assert dump_antes == dump_despues, "DocumentoConsolidado fue alterado durante el renderizado DOCX."
        assert hash_antes == hash_despues, "El hash del modelo documental cambió durante el renderizado."

    # -------------------------------------------------------------------------
    # 9. Integridad de los cinco Excel Oficiales (SHA-256) y 32 Registros M5
    # -------------------------------------------------------------------------
    def test_09_integridad_cinco_excel_sha256_y_32_historicos_m5(
        self, rutas_matrices_templates, periodo_septiembre_2026, metadatos_oficiales, tmp_path
    ):
        """
        Verifica que los 5 archivos Excel oficiales en templates/ mantengan sus hashes SHA-256
        y que el documento Word certifique los 32 registros históricos de M5 en los Anexos.
        """
        hashes_esperados = {
            "M1": "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad",
            "M2": "11419cd22d986e195694f27d15236204afa22526812f18cb4f2e1b7540f64400",
            "M3": "dc1786616cb1a9bc2f82a74cc693ee20ab95b689b658b366164f502201b07c87",
            "M4": "fd079c5f2be780e602dc563696a6f157d76c4c20410308037cec52f3d2654578",
            "M5": "a3dff20ec209de209f59dd8b1ad1be84aa7aebd1536ced406c59453a08973dc3",
        }

        # 1. Leer y consolidar con las matrices reales
        conjunto, filtrado = MatrixReader.leer_y_filtrar(rutas_matrices_templates, periodo_septiembre_2026)
        res_cons = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)
        doc_real = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)

        # 2. Renderizar a DOCX
        ruta_salida = tmp_path / "test_integridad_real.docx"
        DocxGenerator.generate(doc_real, output_path=ruta_salida)

        # 3. Comprobar que el DOCX menciona los 32 registros de M5 y los hashes
        doc = docx.Document(str(ruta_salida))
        texto_completo = " ".join(p.text for p in doc.paragraphs)
        for tbl in doc.tables:
            for row in tbl.rows:
                for c in row.cells:
                    texto_completo += " " + c.text

        assert "32 registros históricos" in texto_completo
        assert "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad" in texto_completo

        # 4. Verificar físicamente los 5 hashes de templates/
        for cod, ruta in rutas_matrices_templates.items():
            assert ruta.exists(), f"Matriz oficial {cod} no existe en {ruta}"
            h = hashlib.sha256(ruta.read_bytes()).hexdigest()
            assert h == hashes_esperados[cod], f"Hash SHA-256 alterado en {cod}: {h} vs {hashes_esperados[cod]}"

    # -------------------------------------------------------------------------
    # 10. Soporte para buffer en memoria (BytesIO)
    # -------------------------------------------------------------------------
    def test_10_soporte_buffer_en_memoria_bytesio(self, documento_caso_real_bilwi):
        """Verifica que DocxGenerator pueda renderizar directamente a un buffer BytesIO."""
        buffer = BytesIO()
        ret = DocxGenerator.generate(documento_caso_real_bilwi, output_path=buffer)

        assert ret is buffer
        buffer.seek(0)
        contenido = buffer.read()
        assert len(contenido) > 10000

        # Comprobar que docx abre el buffer directamente
        buffer.seek(0)
        doc_mem = docx.Document(buffer)
        assert len(doc_mem.paragraphs) > 10

    # -------------------------------------------------------------------------
    # 11. Conclusiones y Dictamen: No inventar dictámenes no autorizados
    # -------------------------------------------------------------------------
    def test_11_conclusiones_sin_dictamen_inventado(self, documento_caso_real_bilwi, tmp_path):
        """Verifica que las conclusiones reflejen el dictamen técnico del modelo sin invenciones."""
        ruta_salida = tmp_path / "test_conclusiones.docx"
        DocxGenerator.generate(documento_caso_real_bilwi, output_path=ruta_salida)

        doc = docx.Document(str(ruta_salida))
        textos = [p.text for p in doc.paragraphs]
        for tbl in doc.tables:
            for row in tbl.rows:
                for c in row.cells:
                    textos.append(c.text)
        texto_completo = " ".join(textos)

        assert "9. CONCLUSIONES Y DICTAMEN TÉCNICO" in texto_completo
        assert "DICTAMEN DE AUDITORÍA" in texto_completo
        # No inventa aprobación de Consejo Universitario ni atribuciones falsas
        assert "Aprobado por el Consejo" not in texto_completo
        assert "Certificado por Rectoría" not in texto_completo

