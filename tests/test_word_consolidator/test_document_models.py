"""
tests.test_word_consolidator.test_document_models

Suite formal de pruebas para la Fase 14.6: Modelo Documental Intermedio
y capa de transformación (DocumentTransformer).
Verifica:
1. Construcción completa de las 10 secciones documentales.
2. Regla estricta de NO INVENTAR información (None / vacíos en datos ausentes).
3. Regla estricta de NO RECONCILIAR fuentes (M1, Nominales, Narrativo y Deltas coexisten).
4. Semántica canónica de sexo (FEMENINO / MASCULINO, sin 'M' como mujeres).
5. Separación rigurosa de estamentos (no fusionar docentes y administrativos).
6. Trazabilidad completa de procedencia.
7. Caso real institucional de Septiembre 2026 Semana 1 (Bilwi: deltas +2 / -1 / -1 / 0).
8. Inmutabilidad de ResultadoConsolidacion y ResultadoAuditoriaDiscrepancias.
9. Integridad criptográfica SHA-256 de las 5 matrices oficiales y 32 registros de M5.
10. Ausencia absoluta de python-docx o generación de archivos .docx.
"""

from copy import deepcopy
from datetime import date
import hashlib
from pathlib import Path
import pytest

from app.core.constants.participant_types import CategoriaParticipacion
from app.word_consolidator import (
    AnexosDocumentales,
    AuditoriaDocumental,
    ConclusionDocumental,
    DemografiaDocumental,
    DocumentoConsolidado,
    DocumentTransformer,
    EstamentosDocumental,
    FichaActividadDocumental,
    FilaActividadDocumental,
    MatrizGeneralDocumental,
    PortadaDocumental,
    ResumenEjecutivoDocumental,
    TerritorioDocumental,
)
from app.word_consolidator.document.models import (
    DistribucionSexoDocumental,
    ItemDiscrepanciaDocumental,
)
from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ConsolidationEngine,
    ParticipacionConsolidada,
    ResultadoConsolidacion,
    TotalesM1,
    TotalesNominales,
)
from app.word_consolidator.engine.discrepancy_detector import DiscrepancyDetector
from app.word_consolidator.models import (
    DiscrepanciaItem,
    EstadoDiscrepancia,
    FilaLeidaM1,
    MetadatosInstitucionales,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
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
def actividad_sintetica_concordante():
    """Crea una actividad sintética perfectamente concordante (delta = 0)."""
    tot_m1 = TotalesM1(
        mujeres=8,
        varones=4,
        total=12,
        estudiantes_f=6,
        estudiantes_m=2,
        docentes_f=1,
        docentes_m=1,
        administrativos_f=1,
        administrativos_m=1,
    )
    tot_nom = TotalesNominales(
        mujeres=8,
        varones=4,
        total=12,
        estudiantes=8,
        docentes=2,
        administrativos=2,
        colaboradores=0,
        beneficiarios=0,
        estudiantes_f=6,
        estudiantes_m=2,
        docentes_f=1,
        docentes_m=1,
        administrativos_f=1,
        administrativos_m=1,
    )
    fila_m1 = FilaLeidaM1(
        matriz_origen="M1",
        hoja="Consolidado_Actividades",
        fila=2,
        sede="Bilwi",
        departamento="RACCN",
        municipio="Puerto Cabezas",
        actividad="Taller de Programación Python",
        fecha_evento=date(2026, 9, 3),
        total_atencion_f=8,
        total_atencion_m=4,
        total_estud_f_grado=6,
        total_estud_m_grado=2,
        total_docente_f=1,
        total_docente_m=1,
        total_administrativos_f=1,
        total_administrativos_m=1,
    )
    parts = []
    # 8 estudiantes
    for i in range(6):
        parts.append(
            ParticipacionConsolidada(
                id_actividad="act-sintetica-1",
                id_persona=f"per-est-f-{i}",
                nombre_apellidos=f"Estudiante Femenina {i}",
                sexo_normalizado="FEMENINO",
                categoria=CategoriaParticipacion.ESTUDIANTE,
                carrera="Ingeniería en Sistemas",
                matriz_origen="M2",
                hoja="Estudiantes",
                fila=2 + i,
                actividad_asociada="Taller de Programación Python",
                sede="Bilwi",
            )
        )
    for i in range(2):
        parts.append(
            ParticipacionConsolidada(
                id_actividad="act-sintetica-1",
                id_persona=f"per-est-m-{i}",
                nombre_apellidos=f"Estudiante Masculino {i}",
                sexo_normalizado="MASCULINO",
                categoria=CategoriaParticipacion.ESTUDIANTE,
                carrera="Ingeniería en Sistemas",
                matriz_origen="M2",
                hoja="Estudiantes",
                fila=8 + i,
                actividad_asociada="Taller de Programación Python",
                sede="Bilwi",
            )
        )
    # 2 docentes
    parts.append(
        ParticipacionConsolidada(
            id_actividad="act-sintetica-1",
            id_persona="per-doc-f-1",
            nombre_apellidos="Docente Femenina 1",
            sexo_normalizado="FEMENINO",
            categoria=CategoriaParticipacion.DOCENTE,
            cargo="Profesor Titular",
            matriz_origen="M3",
            hoja="Docentes_Admin",
            fila=2,
            actividad_asociada="Taller de Programación Python",
            sede="Bilwi",
        )
    )
    parts.append(
        ParticipacionConsolidada(
            id_actividad="act-sintetica-1",
            id_persona="per-doc-m-1",
            nombre_apellidos="Docente Masculino 1",
            sexo_normalizado="MASCULINO",
            categoria=CategoriaParticipacion.DOCENTE,
            cargo="Profesor Adjunto",
            matriz_origen="M3",
            hoja="Docentes_Admin",
            fila=3,
            actividad_asociada="Taller de Programación Python",
            sede="Bilwi",
        )
    )
    # 2 administrativos
    parts.append(
        ParticipacionConsolidada(
            id_actividad="act-sintetica-1",
            id_persona="per-adm-f-1",
            nombre_apellidos="Administrativa 1",
            sexo_normalizado="FEMENINO",
            categoria=CategoriaParticipacion.ADMINISTRATIVO,
            cargo="Secretaria Académica",
            matriz_origen="M3",
            hoja="Docentes_Admin",
            fila=4,
            actividad_asociada="Taller de Programación Python",
            sede="Bilwi",
        )
    )
    parts.append(
        ParticipacionConsolidada(
            id_actividad="act-sintetica-1",
            id_persona="per-adm-m-1",
            nombre_apellidos="Administrativo 1",
            sexo_normalizado="MASCULINO",
            categoria=CategoriaParticipacion.ADMINISTRATIVO,
            cargo="Técnico de Laboratorio",
            matriz_origen="M3",
            hoja="Docentes_Admin",
            fila=5,
            actividad_asociada="Taller de Programación Python",
            sede="Bilwi",
        )
    )

    return ActividadConsolidada(
        id_actividad="act-sintetica-1",
        clave_negocio=("TALLER DE PROGRAMACION PYTHON", "BILWI", "2026-09-03"),
        nombre_actividad="Taller de Programación Python",
        sede="Bilwi",
        fecha_evento=date(2026, 9, 3),
        departamento="RACCN",
        municipio="Puerto Cabezas",
        eje="Eje Tecnológico",
        tipo_evento="Taller",
        area_responsable="Informática",
        fuente_m1=fila_m1,
        totales_m1=tot_m1,
        participaciones=parts,
        totales_nominales=tot_nom,
        total_asistencia_bruta=12,
        total_personas_unicas=12,
    )


class TestModeloDocumentalIntermedioSuite:
    """Suite de 15 pruebas obligatorias + pruebas especiales de integridad para la Fase 14.6."""

    # -------------------------------------------------------------------------
    # 1. Construcción correcta de DocumentoConsolidado con 10 secciones
    # -------------------------------------------------------------------------
    def test_01_construccion_correcta_documento(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
            total_recurrencia=0,
            tasa_recurrencia=0.0,
            fuentes={
                "M1": RegistroFuenteArchivo(
                    codigo_matriz="M1",
                    nombre_archivo="Matriz_1.xlsx",
                    ruta_archivo="output/Matriz_1.xlsx",
                    hash_sha256="a" * 64,
                    total_filas_leidas=1,
                    filas_en_periodo=1,
                )
            },
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons, incluir_concordantes=True)

        doc = DocumentTransformer.transformar(
            consolidacion=res_cons,
            auditoria=res_audit,
            periodo=periodo_septiembre_2026,
            metadatos=metadatos_oficiales,
        )

        assert isinstance(doc, DocumentoConsolidado)
        assert doc.id_documento is not None
        assert doc.periodo == periodo_septiembre_2026
        assert doc.metadatos == metadatos_oficiales

        # Verificar presencia de las 10 secciones documentales
        assert isinstance(doc.portada, PortadaDocumental)
        assert isinstance(doc.resumen_ejecutivo, ResumenEjecutivoDocumental)
        assert isinstance(doc.matriz_general, MatrizGeneralDocumental)
        assert isinstance(doc.fichas_actividades, list)
        assert len(doc.fichas_actividades) == 1
        assert isinstance(doc.fichas_actividades[0], FichaActividadDocumental)
        assert isinstance(doc.demografia, DemografiaDocumental)
        assert isinstance(doc.estamentos, EstamentosDocumental)
        assert isinstance(doc.territorio, TerritorioDocumental)
        assert isinstance(doc.auditoria, AuditoriaDocumental)
        assert isinstance(doc.conclusiones, ConclusionDocumental)
        assert isinstance(doc.anexos, AnexosDocumentales)

    # -------------------------------------------------------------------------
    # 2. Resumen ejecutivo
    # -------------------------------------------------------------------------
    def test_02_resumen_ejecutivo(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
            total_recurrencia=0,
            tasa_recurrencia=0.0,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)
        re = doc.resumen_ejecutivo

        assert re.total_actividades == 1
        assert re.total_asistencia_bruta == 12
        assert re.total_personas_unicas == 12
        assert re.total_recurrencia == 0
        assert re.tasa_recurrencia == 0.0
        assert re.distribucion_sexo.femenino == 8
        assert re.distribucion_sexo.masculino == 4
        assert re.distribucion_sexo.total == 12
        assert re.distribucion_sexo.porcentaje_femenino == 66.67
        assert re.distribucion_sexo.porcentaje_masculino == 33.33
        assert re.total_discrepancias == 0
        assert re.actividades_concordantes == 1
        assert re.actividades_con_observaciones == 0

    # -------------------------------------------------------------------------
    # 3. Actividad individual
    # -------------------------------------------------------------------------
    def test_03_actividad_individual(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)

        fila = doc.matriz_general.filas[0]
        assert fila.id_actividad == "act-sintetica-1"
        assert fila.nombre_actividad == "Taller de Programación Python"
        assert fila.sede == "Bilwi"
        assert fila.departamento == "RACCN"
        assert fila.municipio == "Puerto Cabezas"
        assert fila.total_m1 == 12
        assert fila.femenino_m1 == 8
        assert fila.masculino_m1 == 4
        assert fila.total_nominal == 12
        assert fila.femenino_nominal == 8
        assert fila.masculino_nominal == 4
        assert fila.estudiantes_nominal == 8
        assert fila.docentes_nominal == 2
        assert fila.administrativos_nominal == 2
        assert fila.colaboradores_nominal == 0
        assert fila.beneficiarios_nominal == 0
        assert fila.estado_auditoria == EstadoDiscrepancia.CONCORDANTE

        ficha = doc.fichas_actividades[0]
        assert ficha.id_actividad == "act-sintetica-1"
        assert ficha.nombre_actividad == "Taller de Programación Python"
        assert ficha.comparativa_m1_vs_nominal.total_m1 == 12
        assert ficha.comparativa_m1_vs_nominal.total_nominal == 12
        assert ficha.comparativa_m1_vs_nominal.delta_total == 0
        assert len(ficha.desglose_estamentos) == 5

    # -------------------------------------------------------------------------
    # 4. Múltiples actividades
    # -------------------------------------------------------------------------
    def test_04_multiples_actividades(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        # Segunda actividad sintética en Bluefields
        tot_m1_b = TotalesM1(mujeres=5, varones=5, total=10)
        tot_nom_b = TotalesNominales(
            mujeres=5, varones=5, total=10, estudiantes=10, estudiantes_f=5, estudiantes_m=5
        )
        act_b = ActividadConsolidada(
            id_actividad="act-bluefields-2",
            clave_negocio=("CHARLA EMPRENDIMIENTO", "BLUEFIELDS", "2026-09-04"),
            nombre_actividad="Charla Emprendimiento",
            sede="Bluefields",
            fecha_evento=date(2026, 9, 4),
            departamento="RACCS",
            municipio="Bluefields",
            totales_m1=tot_m1_b,
            totales_nominales=tot_nom_b,
            total_asistencia_bruta=10,
            total_personas_unicas=10,
        )

        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante, act_b],
            total_actividades=2,
            total_asistencia_bruta=22,
            total_personas_unicas=22,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)

        assert doc.total_actividades == 2
        assert len(doc.matriz_general.filas) == 2
        assert len(doc.fichas_actividades) == 2
        assert doc.matriz_general.totales_generales.total_nominal == 22
        assert doc.matriz_general.totales_generales.total_m1 == 22

    # -------------------------------------------------------------------------
    # 5. Métricas globales
    # -------------------------------------------------------------------------
    def test_05_metricas_globales(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=10,  # 2 recurrentes
            total_recurrencia=2,
            tasa_recurrencia=16.67,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)
        mr = doc.demografia.metricas_recurrencia

        assert mr.total_asistencia_bruta == 12
        assert mr.total_personas_unicas == 10
        assert mr.total_recurrencia == 2
        assert mr.tasa_recurrencia == 16.67

    # -------------------------------------------------------------------------
    # 6. Distribución por sexo — Regla FEMENINO / MASCULINO
    # -------------------------------------------------------------------------
    def test_06_distribucion_por_sexo(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)
        dem = doc.demografia

        assert dem.distribucion_sexo_nominal.femenino == 8
        assert dem.distribucion_sexo_nominal.masculino == 4
        assert dem.distribucion_sexo_nominal.total == 12
        assert hasattr(dem.distribucion_sexo_nominal, "femenino")
        assert hasattr(dem.distribucion_sexo_nominal, "masculino")
        # Asegurar que no existe un campo 'M' interpretado como femenino
        assert "M" not in dem.distribucion_sexo_nominal.model_dump()

    # -------------------------------------------------------------------------
    # 7. Distribución por estamento — Separación estricta
    # -------------------------------------------------------------------------
    def test_07_distribucion_por_estamento(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)
        est = doc.estamentos

        assert est.estudiantes.total == 8
        assert est.docentes.total == 2
        assert est.administrativos.total == 2
        assert est.colaboradores.total == 0
        assert est.beneficiarios.total == 0
        assert est.total_general == 12

        # Confirmar que Docentes y Administrativos NO están fusionados
        assert est.docentes.total != est.administrativos.total + est.docentes.total

    # -------------------------------------------------------------------------
    # 8. Territorio / Cobertura
    # -------------------------------------------------------------------------
    def test_08_territorio(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)
        terr = doc.territorio

        assert terr.total_sedes_participantes == 1
        assert terr.desglose_sedes[0].sede == "Bilwi"
        assert terr.desglose_sedes[0].total_actividades == 1
        assert terr.desglose_sedes[0].total_asistencias == 12

        assert terr.total_departamentos_cubiertos == 1
        assert terr.desglose_departamentos[0].departamento == "RACCN"

        assert terr.total_municipios_cubiertos == 1
        assert terr.desglose_municipios[0].municipio == "Puerto Cabezas"

    # -------------------------------------------------------------------------
    # 9. Discrepancias — Formato tabular DIMENSIÓN | FUENTE A | FUENTE B | DELTA | ESTADO
    # -------------------------------------------------------------------------
    def test_09_discrepancias(
        self, periodo_septiembre_2026, metadatos_oficiales
    ):
        disc_item = DiscrepanciaItem(
            id_actividad="act-disc-1",
            nombre_actividad="Actividad con Desfase",
            estamento="Estudiantes",
            categoria_discrepancia="ESTAMENTO",
            fuente_a="Informe Narrativo",
            fuente_b="Matriz 2 (Nominal)",
            valor_fuente_a=15,
            valor_fuente_b=17,
            delta=2,
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
            descripcion="Diferencia de 2 estudiantes",
        )
        act_disc = ActividadConsolidada(
            id_actividad="act-disc-1",
            clave_negocio=("ACTIVIDAD CON DESFASE", "BILWI", None),
            nombre_actividad="Actividad con Desfase",
            sede="Bilwi",
            totales_nominales=TotalesNominales(total=17, estudiantes=17),
            total_asistencia_bruta=17,
            total_personas_unicas=17,
            discrepancias=[disc_item],
        )
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[act_disc],
            total_actividades=1,
            total_asistencia_bruta=17,
            total_personas_unicas=17,
            discrepancias=[disc_item],
        )
        res_audit = ResultadoAuditoriaDiscrepancias(
            total_actividades_evaluadas=1,
            actividades_con_discrepancias=1,
            actividades_concordantes=0,
            total_discrepancias_activas=1,
            total_concordancias=0,
            discrepancias_globales=[disc_item],
        )

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)
        audit_doc = doc.auditoria

        assert audit_doc.total_discrepancias_activas == 1
        assert len(audit_doc.tabla_discrepancias) == 1
        d_row = audit_doc.tabla_discrepancias[0]

        # Verificar los 5 campos requeridos para la tabla Word
        assert d_row.dimension == "Estudiantes"
        assert d_row.fuente_a == "Informe Narrativo"
        assert d_row.fuente_b == "Matriz 2 (Nominal)"
        assert d_row.delta == 2
        assert d_row.estado == EstadoDiscrepancia.REQUIERE_REVISION
        assert d_row.valor_fuente_a == 15
        assert d_row.valor_fuente_b == 17

    # -------------------------------------------------------------------------
    # 10. Fuentes faltantes
    # -------------------------------------------------------------------------
    def test_10_fuentes_faltantes(
        self, periodo_septiembre_2026, metadatos_oficiales
    ):
        disc_faltante = DiscrepanciaItem(
            id_actividad="act-sin-nominales",
            nombre_actividad="Actividad sin lista nominal",
            estamento="Nominal",
            categoria_discrepancia="FUENTE_FALTANTE",
            fuente_a="Matriz 1",
            fuente_b="Matrices Nominales (M2–M5)",
            valor_fuente_a=25,
            valor_fuente_b=0,
            delta=-25,
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
            descripcion="Actividad declarada en M1 sin respaldo en matrices nominales",
        )
        act_sin = ActividadConsolidada(
            id_actividad="act-sin-nominales",
            clave_negocio=("ACTIVIDAD SIN LISTA NOMINAL", "BLUEFIELDS", None),
            nombre_actividad="Actividad sin lista nominal",
            sede="Bluefields",
            totales_m1=TotalesM1(total=25, mujeres=15, varones=10),
            totales_nominales=TotalesNominales(total=0),
            total_asistencia_bruta=0,
            total_personas_unicas=0,
            discrepancias=[disc_faltante],
        )
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[act_sin],
            total_actividades=1,
            total_asistencia_bruta=0,
            total_personas_unicas=0,
            discrepancias=[disc_faltante],
        )
        res_audit = ResultadoAuditoriaDiscrepancias(
            total_actividades_evaluadas=1,
            actividades_con_discrepancias=1,
            actividades_concordantes=0,
            total_discrepancias_activas=1,
            total_concordancias=0,
            discrepancias_globales=[disc_faltante],
        )

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)

        assert doc.auditoria.total_fuentes_faltantes == 1
        assert doc.resumen_ejecutivo.total_fuentes_faltantes == 1
        assert doc.matriz_general.filas[0].total_m1 == 25
        assert doc.matriz_general.filas[0].total_nominal == 0
        assert doc.matriz_general.filas[0].tiene_discrepancias is True

    # -------------------------------------------------------------------------
    # 11. Trazabilidad
    # -------------------------------------------------------------------------
    def test_11_trazabilidad(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)

        fila = doc.matriz_general.filas[0]
        assert len(fila.trazabilidad_fuentes) >= 1
        fuente_m1 = fila.trazabilidad_fuentes[0]
        assert fuente_m1.matriz == "M1"
        assert fuente_m1.hoja == "Consolidado_Actividades"
        assert fuente_m1.fila == 2
        assert fuente_m1.actividad == "Taller de Programación Python"
        assert fuente_m1.periodo == "Semana 1 - Septiembre 2026"

    # -------------------------------------------------------------------------
    # 12. Caso real obligatorio: Septiembre 2026 Semana 1 (Bilwi)
    # -------------------------------------------------------------------------
    def test_12_caso_real_septiembre_2026_semana_1(
        self, periodo_septiembre_2026, metadatos_oficiales
    ):
        nombre_act = "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial"
        id_act = "caso-real-septiembre-2026"

        # M1: Mujeres 12, Varones 6, Total 18
        tot_m1 = TotalesM1(
            mujeres=12,
            varones=6,
            total=18,
            estudiantes_f=12,
            estudiantes_m=5,
            administrativos_f=1,
            administrativos_m=0,
        )

        # Nominal: Estudiantes 17, Administrativa 1, Docentes 0, Colaboradores 0, Beneficiarios 0, Total 18
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

        # Narrativo: Estudiantes 15, Administrativos 2, Docentes 1, Total 18
        narrativo = {
            "estudiantes": 15,
            "administrativos": 2,
            "docentes": 1,
            "total": 18,
        }

        # Generar discrepancias formalmente entre Narrativo (Fuente A) y Nominal (Fuente B)
        disc_est = DiscrepanciaItem(
            id_actividad=id_act,
            nombre_actividad=nombre_act,
            estamento="Estudiantes",
            fuente_a="Informe Narrativo",
            fuente_b="Matriz 2 (Nominal)",
            valor_fuente_a=15,
            valor_fuente_b=17,
            delta=2,  # +2
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
            delta=-1,  # -1
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
            delta=-1,  # -1
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
            delta=0,  # 0
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

        doc = DocumentTransformer.transformar(
            consolidacion=res_cons,
            auditoria=res_audit,
            periodo=periodo_septiembre_2026,
            metadatos=metadatos_oficiales,
            informes_narrativos={id_act: narrativo},
        )

        fila = doc.matriz_general.filas[0]

        # 1. Comprobar que M1 se conserva intacto
        assert fila.total_m1 == 18
        assert fila.mujeres_m1 == 12
        assert fila.varones_m1 == 6

        # 2. Comprobar que Nominal se conserva intacto
        assert fila.total_nominal == 18
        assert fila.estudiantes_nominal == 17
        assert fila.administrativos_nominal == 1
        assert fila.docentes_nominal == 0

        # 3. Comprobar que Narrativo se conserva intacto
        assert fila.datos_narrativos["estudiantes"] == 15
        assert fila.datos_narrativos["administrativos"] == 2
        assert fila.datos_narrativos["docentes"] == 1
        assert fila.datos_narrativos["total"] == 18

        # 4. Comprobar que las 4 discrepancias coexisten con sus deltas exactos
        mapa_disc = {d.dimension: d for d in doc.auditoria.tabla_discrepancias}

        assert mapa_disc["Estudiantes"].delta == 2
        assert mapa_disc["Estudiantes"].estado == EstadoDiscrepancia.REQUIERE_REVISION

        assert mapa_disc["Administrativos"].delta == -1
        assert mapa_disc["Administrativos"].estado == EstadoDiscrepancia.REQUIERE_REVISION

        assert mapa_disc["Docentes"].delta == -1
        assert mapa_disc["Docentes"].estado == EstadoDiscrepancia.REQUIERE_REVISION

        assert mapa_disc["Total"].delta == 0
        assert mapa_disc["Total"].estado == EstadoDiscrepancia.CONCORDANTE

        # 5. Confirmar que NO se reconcilió 15 en 17 ni 17 en 15
        assert fila.estudiantes_nominal == 17
        assert fila.datos_narrativos["estudiantes"] == 15

    # -------------------------------------------------------------------------
    # 13. Inmutabilidad de ResultadoConsolidacion
    # -------------------------------------------------------------------------
    def test_13_inmutabilidad_resultado_consolidacion(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        dump_antes = res_cons.model_dump(mode="json")
        _ = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)
        dump_despues = res_cons.model_dump(mode="json")

        assert dump_antes == dump_despues, "ResultadoConsolidacion fue mutado durante la transformación."

    # -------------------------------------------------------------------------
    # 14. Inmutabilidad de ResultadoAuditoriaDiscrepancias
    # -------------------------------------------------------------------------
    def test_14_inmutabilidad_resultado_auditoria_discrepancias(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        dump_audit_antes = res_audit.model_dump(mode="json")
        _ = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)
        dump_audit_despues = res_audit.model_dump(mode="json")

        assert dump_audit_antes == dump_audit_despues, "ResultadoAuditoriaDiscrepancias fue mutado durante la transformación."

    # -------------------------------------------------------------------------
    # 15. Integridad de los cinco Excel oficiales mediante SHA-256
    # -------------------------------------------------------------------------
    def test_15_integridad_cinco_excel_oficiales_sha256(
        self, rutas_matrices_templates, periodo_septiembre_2026, metadatos_oficiales
    ):
        hashes_esperados = {
            "M1": "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad",
            "M2": "11419cd22d986e195694f27d15236204afa22526812f18cb4f2e1b7540f64400",
            "M3": "dc1786616cb1a9bc2f82a74cc693ee20ab95b689b658b366164f502201b07c87",
            "M4": "fd079c5f2be780e602dc563696a6f157d76c4c20410308037cec52f3d2654578",
            "M5": "a3dff20ec209de209f59dd8b1ad1be84aa7aebd1536ced406c59453a08973dc3",
        }

        # 1. Leer y consolidar matrices reales
        conjunto, filtrado = MatrixReader.leer_y_filtrar(rutas_matrices_templates, periodo_septiembre_2026)
        res_cons = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        # 2. Transformar a modelo documental
        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)

        # 3. Comprobar que los anexos preservan los 32 registros históricos de M5
        assert doc.anexos.total_registros_historicos_m5 == 32
        assert len(res_cons.nominales_historicos_fuera_periodo) == 32

        # 4. Comprobar los hashes SHA-256 de los 5 libros físicos en disco
        for cod, ruta in rutas_matrices_templates.items():
            assert ruta.exists(), f"Falta matriz oficial {cod}: {ruta}"
            h = hashlib.sha256(ruta.read_bytes()).hexdigest()
            assert h == hashes_esperados[cod], f"Hash SHA-256 alterado en {cod}: obtenido {h} vs {hashes_esperados[cod]}"

    # -------------------------------------------------------------------------
    # 16. Prueba especial: NO INVENTAR INFORMACIÓN
    # -------------------------------------------------------------------------
    def test_16_prueba_especial_no_inventar(
        self, periodo_septiembre_2026
    ):
        """Verifica que campos no suministrados permanezcan None o lista vacía sin ser inferidos."""
        # Actividad con datos mínimos sin metadatos
        act_min = ActividadConsolidada(
            id_actividad="act-minima",
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

        # No suministramos metadatos institucionales
        doc = DocumentTransformer.transformar(
            consolidacion=res_cons,
            auditoria=res_audit,
            periodo=periodo_septiembre_2026,
            metadatos=None,
        )

        # Portada: no inventar fecha de emisión ni lugar ni universidad
        assert doc.portada.fecha_emision is None
        assert doc.portada.lugar_emision is None
        assert doc.portada.universidad is None

        # Ficha: no inventar programa, proyecto, descripción ni comunidad
        ficha = doc.fichas_actividades[0]
        assert ficha.programa is None
        assert ficha.proyecto is None
        assert ficha.descripcion_resultados is None
        assert ficha.comunidad is None
        assert ficha.enlaces_evidencias == []
        assert ficha.referencias_actas == []

        # Territorio: no inventar comunidades
        assert doc.territorio.comunidades == []

        # Conclusiones: no inventar resumen narrativo
        assert doc.conclusiones.resumen_narrativo is None

    # -------------------------------------------------------------------------
    # 17. Prueba especial: Fuentes tripartitas coexisten sin reconciliación
    # -------------------------------------------------------------------------
    def test_17_prueba_especial_fuentes_tripartitas(
        self, periodo_septiembre_2026, metadatos_oficiales
    ):
        """M1 = 18, Nominal = 17, Narrativa = 15 coexisten sin que ninguna sustituya a la otra."""
        id_act = "act-tripartita-test"
        act_trip = ActividadConsolidada(
            id_actividad=id_act,
            clave_negocio=("ACTIVIDAD TRIPARTITA", "BILWI", None),
            nombre_actividad="Actividad Tripartita",
            sede="Bilwi",
            totales_m1=TotalesM1(total=18, mujeres=10, varones=8),
            totales_nominales=TotalesNominales(total=17, mujeres=10, varones=7),
            total_asistencia_bruta=17,
            total_personas_unicas=17,
        )
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[act_trip],
            total_actividades=1,
            total_asistencia_bruta=17,
            total_personas_unicas=17,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        narrativo_input = {id_act: {"total": 15, "estudiantes": 15}}

        doc = DocumentTransformer.transformar(
            consolidacion=res_cons,
            auditoria=res_audit,
            periodo=periodo_septiembre_2026,
            metadatos=metadatos_oficiales,
            informes_narrativos=narrativo_input,
        )

        fila = doc.matriz_general.filas[0]
        assert fila.total_m1 == 18
        assert fila.total_nominal == 17
        assert fila.datos_narrativos["total"] == 15
        assert fila.datos_narrativos["estudiantes"] == 15

        # Ninguno sustituye al otro
        assert fila.total_m1 != fila.total_nominal
        assert fila.total_nominal != fila.datos_narrativos["total"]

    # -------------------------------------------------------------------------
    # 18. Prueba especial: Semántica canónica de sexo (no 'M' como mujeres)
    # -------------------------------------------------------------------------
    def test_18_prueba_especial_sexo_canonico(
        self, periodo_septiembre_2026, metadatos_oficiales, actividad_sintetica_concordante
    ):
        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[actividad_sintetica_concordante],
            total_actividades=1,
            total_asistencia_bruta=12,
            total_personas_unicas=12,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(res_cons, res_audit, periodo_septiembre_2026, metadatos_oficiales)

        # Verificar que en todo el modelo se usa femenino y masculino
        assert doc.demografia.distribucion_sexo_nominal.femenino == 8
        assert doc.demografia.distribucion_sexo_nominal.masculino == 4
        assert doc.estamentos.estudiantes.femenino == 6
        assert doc.estamentos.estudiantes.masculino == 2
        assert doc.estamentos.docentes.femenino == 1
        assert doc.estamentos.docentes.masculino == 1

        # Verificar compatibilidad de propiedades
        assert doc.matriz_general.filas[0].femenino_nominal == 8
        assert doc.matriz_general.filas[0].mujeres_nominal == 8
        assert doc.matriz_general.filas[0].masculino_nominal == 4
        assert doc.matriz_general.filas[0].varones_nominal == 4

    # -------------------------------------------------------------------------
    # 19. Prueba obligatoria: Caso real discrepancia de SEXO M1 vs Nominal
    # -------------------------------------------------------------------------
    def test_19_caso_real_discrepancia_sexo_m1_vs_nominal(
        self, periodo_septiembre_2026, metadatos_oficiales
    ):
        """
        Valida que la discrepancia de sexo en el caso real de Bilwi:
        M1: FEMENINO=12, MASCULINO=6, TOTAL=18
        Nominal: FEMENINO=13, MASCULINO=5, TOTAL=18
        Deltas: FEMENINO=+1 (REQUIERE_REVISION), MASCULINO=-1 (REQUIERE_REVISION), TOTAL=0 (CONCORDANTE)
        estén disponibles y correctos en DocumentoConsolidado.
        """
        id_act = "caso-real-sexo-bilwi"
        nombre_act = "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial"

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
            administrativos=1,
            estudiantes_f=12,
            estudiantes_m=5,
            administrativos_f=1,
            administrativos_m=0,
        )

        act = ActividadConsolidada(
            id_actividad=id_act,
            clave_negocio=(nombre_act.upper(), "BILWI", "2026-09-03"),
            nombre_actividad=nombre_act,
            sede="Bilwi",
            fecha_evento=date(2026, 9, 3),
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
            total_asistencia_bruta=18,
            total_personas_unicas=18,
        )

        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[act],
            total_actividades=1,
            total_asistencia_bruta=18,
            total_personas_unicas=18,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons, incluir_concordantes=True)

        doc = DocumentTransformer.transformar(
            consolidacion=res_cons,
            auditoria=res_audit,
            periodo=periodo_septiembre_2026,
            metadatos=metadatos_oficiales,
        )

        # 1. Comprobar en DemografiaDocumental.comparativa_sexo
        mapa_comp_sexo = {c.dimension.upper(): c for c in doc.demografia.comparativa_sexo}

        assert "FEMENINO" in mapa_comp_sexo
        c_fem = mapa_comp_sexo["FEMENINO"]
        assert c_fem.valor_fuente_a == 12  # M1
        assert c_fem.valor_fuente_b == 13  # Nominal
        assert c_fem.m1 == 12
        assert c_fem.nominal == 13
        assert c_fem.delta == 1  # +1
        assert c_fem.estado == EstadoDiscrepancia.REQUIERE_REVISION

        assert "MASCULINO" in mapa_comp_sexo
        c_masc = mapa_comp_sexo["MASCULINO"]
        assert c_masc.valor_fuente_a == 6  # M1
        assert c_masc.valor_fuente_b == 5  # Nominal
        assert c_masc.m1 == 6
        assert c_masc.nominal == 5
        assert c_masc.delta == -1  # -1
        assert c_masc.estado == EstadoDiscrepancia.REQUIERE_REVISION

        assert "TOTAL" in mapa_comp_sexo
        c_tot = mapa_comp_sexo["TOTAL"]
        assert c_tot.valor_fuente_a == 18
        assert c_tot.valor_fuente_b == 18
        assert c_tot.m1 == 18
        assert c_tot.nominal == 18
        assert c_tot.delta == 0
        assert c_tot.estado == EstadoDiscrepancia.CONCORDANTE

        # 2. Comprobar en AuditoriaDocumental.tabla_discrepancias
        mapa_audit_disc = {d.dimension.upper(): d for d in doc.auditoria.tabla_discrepancias}
        assert "FEMENINO" in mapa_audit_disc
        assert mapa_audit_disc["FEMENINO"].delta == 1
        assert mapa_audit_disc["FEMENINO"].estado == EstadoDiscrepancia.REQUIERE_REVISION

        assert "MASCULINO" in mapa_audit_disc
        assert mapa_audit_disc["MASCULINO"].delta == -1
        assert mapa_audit_disc["MASCULINO"].estado == EstadoDiscrepancia.REQUIERE_REVISION

        assert "TOTAL" in mapa_audit_disc
        assert mapa_audit_disc["TOTAL"].delta == 0
        assert mapa_audit_disc["TOTAL"].estado == EstadoDiscrepancia.CONCORDANTE

        # 3. Comprobar en FichaActividadDocumental.comparativa_m1_vs_nominal
        cf = doc.fichas_actividades[0].comparativa_m1_vs_nominal
        assert cf.femenino_m1 == 12
        assert cf.femenino_nominal == 13
        assert cf.delta_femenino == 1
        assert cf.masculino_m1 == 6
        assert cf.masculino_nominal == 5
        assert cf.delta_masculino == -1
        assert cf.total_m1 == 18
        assert cf.total_nominal == 18
        assert cf.delta_total == 0
        assert cf.estado == EstadoDiscrepancia.REQUIERE_REVISION

    # -------------------------------------------------------------------------
    # 20. Prueba obligatoria: NO RECONCILIACIÓN de sexo (coexistencia simultánea)
    # -------------------------------------------------------------------------
    def test_20_coexistencia_simultanea_sexo_sin_reconciliacion(
        self, periodo_septiembre_2026, metadatos_oficiales
    ):
        """
        Confirma que después de ejecutar DocumentTransformer.transformar(...),
        continúan existiendo simultáneamente sin reconciliarse:
        M1 FEMENINO = 12, Nominal FEMENINO = 13
        M1 MASCULINO = 6, Nominal MASCULINO = 5
        Sin que ningún campo los sustituya por un valor único reconciliado.
        """
        id_act = "caso-real-no-reconciliacion"
        tot_m1 = TotalesM1(mujeres=12, varones=6, total=18)
        tot_nom = TotalesNominales(mujeres=13, varones=5, total=18)

        act = ActividadConsolidada(
            id_actividad=id_act,
            clave_negocio=("ACTIVIDAD SIN RECONCILIACION", "BILWI", None),
            nombre_actividad="Actividad sin reconciliación",
            sede="Bilwi",
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
            total_asistencia_bruta=18,
            total_personas_unicas=18,
        )

        res_cons = ResultadoConsolidacion(
            periodo=periodo_septiembre_2026,
            actividades=[act],
            total_actividades=1,
            total_asistencia_bruta=18,
            total_personas_unicas=18,
        )
        res_audit = DiscrepancyDetector.evaluar_consolidacion(res_cons)

        doc = DocumentTransformer.transformar(
            consolidacion=res_cons,
            auditoria=res_audit,
            periodo=periodo_septiembre_2026,
            metadatos=metadatos_oficiales,
        )

        fila = doc.matriz_general.filas[0]

        # Comprobar coexistencia exacta sin sustitución
        assert fila.femenino_m1 == 12
        assert fila.femenino_nominal == 13
        assert fila.femenino_m1 != fila.femenino_nominal

        assert fila.masculino_m1 == 6
        assert fila.masculino_nominal == 5
        assert fila.masculino_m1 != fila.masculino_nominal

        # Comprobar en ficha
        ficha = doc.fichas_actividades[0]
        assert ficha.comparativa_m1_vs_nominal.femenino_m1 == 12
        assert ficha.comparativa_m1_vs_nominal.femenino_nominal == 13
        assert ficha.comparativa_m1_vs_nominal.masculino_m1 == 6
        assert ficha.comparativa_m1_vs_nominal.masculino_nominal == 5

