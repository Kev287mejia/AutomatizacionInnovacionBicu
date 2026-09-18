"""
tests.test_word_consolidator.test_discrepancy_detector

Suite formal de pruebas unitarias y de integración para la Fase 14.5: DiscrepancyDetector.
Verifica exhaustivamente los 10 requisitos obligatorios:
1. Concordancia total.
2. Discrepancia de estamento.
3. Discrepancia de sexo.
4. Discrepancia del total.
5. Múltiples discrepancias simultáneas.
6. Fuente faltante (M1 ausente o nominales ausentes).
7. Trazabilidad de cada discrepancia.
8. Confirmación de que las fuentes originales no son modificadas.
9. Estados CONCORDANTE y REQUIERE_REVISION.
10. Caso real Septiembre 2026 Semana 1 (validando delta +2, -1, -1, 0 y hashes SHA-256 intactos).
"""

from datetime import date
import hashlib
from pathlib import Path
from typing import Dict
import pytest

from app.core.constants.participant_types import CategoriaParticipacion
from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ConsolidationEngine,
    ParticipacionConsolidada,
    TotalesM1,
    TotalesNominales,
)
from app.word_consolidator.engine.discrepancy_detector import DiscrepancyDetector
from app.word_consolidator.models import (
    DiscrepanciaItem,
    EstadoDiscrepancia,
    FilaLeidaM1,
    FilaLeidaNominal,
    PeriodoConsolidacion,
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
        etiqueta="Semana 1 - Septiembre 2026"
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
def rutas_matrices_oficiales_output():
    base = Path("output")
    return {
        "M1": base / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": base / "Matriz_2_Estudiantes.xlsx",
        "M3": base / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": base / "Matriz_4_Colaboradores.xlsx",
        "M5": base / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }


class TestDiscrepancyDetectorSuite:
    """Suite de pruebas formal para el detector de discrepancias institucionales."""

    # -------------------------------------------------------------------------
    # 1. Concordancia total
    # -------------------------------------------------------------------------
    def test_01_concordancia_total(self):
        tot_m1 = TotalesM1(
            mujeres=9,
            varones=6,
            total=15,
            estudiantes_f=6,
            estudiantes_m=4,
            docentes_f=1,
            docentes_m=1,
            administrativos_f=2,
            administrativos_m=1,
            colaboradores_f=0,
            colaboradores_m=0,
            protagonistas_f=0,
            protagonistas_m=0,
        )
        tot_nom = TotalesNominales(
            mujeres=9,
            varones=6,
            total=15,
            estudiantes=10,
            docentes=2,
            administrativos=3,
            no_docentes=0,
            colaboradores=0,
            beneficiarios=0,
            estudiantes_f=6,
            estudiantes_m=4,
            docentes_f=1,
            docentes_m=1,
            administrativos_f=2,
            administrativos_m=1,
        )
        act = ActividadConsolidada(
            clave_negocio=("actividad concordante", "bilwi", "2026-09-02"),
            nombre_actividad="Actividad Concordante",
            sede="Bilwi",
            fecha_evento="2026-09-02",
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
            total_asistencia_bruta=15,
            total_personas_unicas=15,
        )

        inf = DiscrepancyDetector.evaluar_actividad(act, incluir_concordantes=True)

        assert inf.tiene_discrepancias is False
        assert inf.total_discrepancias == 0
        assert inf.total_concordantes > 0
        assert all(it.estado == EstadoDiscrepancia.CONCORDANTE for it in inf.discrepancias)
        assert all(it.delta == 0 for it in inf.discrepancias)

    # -------------------------------------------------------------------------
    # 2. Discrepancia de estamento
    # -------------------------------------------------------------------------
    def test_02_discrepancia_estamento(self):
        tot_m1 = TotalesM1(
            mujeres=12,
            varones=6,
            total=18,
            estudiantes_f=10,
            estudiantes_m=5,  # 15 estudiantes en M1
            docentes_f=1,
            docentes_m=0,     # 1 docente en M1
            administrativos_f=1,
            administrativos_m=1,  # 2 administrativos en M1
        )
        tot_nom = TotalesNominales(
            mujeres=12,
            varones=6,
            total=18,
            estudiantes=17,   # 17 estudiantes nominales
            docentes=0,       # 0 docentes nominales
            administrativos=1, # 1 administrativo nominal
        )
        act = ActividadConsolidada(
            clave_negocio=("taller estamentos", "bilwi", "2026-09-03"),
            nombre_actividad="Taller Estamentos",
            sede="Bilwi",
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
            total_asistencia_bruta=18,
            total_personas_unicas=18,
        )

        inf = DiscrepancyDetector.evaluar_actividad(act, incluir_concordantes=True)

        assert inf.tiene_discrepancias is True
        mapa = {d.estamento: d for d in inf.discrepancias}

        # Estudiantes: 15 vs 17 -> delta +2 -> REQUIERE_REVISION
        assert "Estudiantes" in mapa
        d_est = mapa["Estudiantes"]
        assert d_est.valor_fuente_a == 15
        assert d_est.valor_fuente_b == 17
        assert d_est.delta == 2
        assert d_est.estado == EstadoDiscrepancia.REQUIERE_REVISION

        # Docentes: 1 vs 0 -> delta -1 -> REQUIERE_REVISION
        assert "Docentes" in mapa
        d_doc = mapa["Docentes"]
        assert d_doc.valor_fuente_a == 1
        assert d_doc.valor_fuente_b == 0
        assert d_doc.delta == -1
        assert d_doc.estado == EstadoDiscrepancia.REQUIERE_REVISION

        # Administrativos: 2 vs 1 -> delta -1 -> REQUIERE_REVISION
        assert "Administrativos" in mapa
        d_adm = mapa["Administrativos"]
        assert d_adm.valor_fuente_a == 2
        assert d_adm.valor_fuente_b == 1
        assert d_adm.delta == -1
        assert d_adm.estado == EstadoDiscrepancia.REQUIERE_REVISION

        # Total general: 18 vs 18 -> delta 0 -> CONCORDANTE
        assert "Total General" in mapa
        d_tot = mapa["Total General"]
        assert d_tot.valor_fuente_a == 18
        assert d_tot.valor_fuente_b == 18
        assert d_tot.delta == 0
        assert d_tot.estado == EstadoDiscrepancia.CONCORDANTE

    # -------------------------------------------------------------------------
    # 3. Discrepancia de sexo
    # -------------------------------------------------------------------------
    def test_03_discrepancia_sexo(self):
        # M1: 20 total (12 mujeres, 8 varones)
        # Nominales: 20 total (14 mujeres, 6 varones)
        tot_m1 = TotalesM1(mujeres=12, varones=8, total=20)
        tot_nom = TotalesNominales(mujeres=14, varones=6, total=20)
        act = ActividadConsolidada(
            clave_negocio=("simposio genero", "bluefields", "2026-09-04"),
            nombre_actividad="Simposio Género",
            sede="Bluefields",
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
            total_asistencia_bruta=20,
            total_personas_unicas=20,
        )

        inf = DiscrepancyDetector.evaluar_actividad(act, incluir_concordantes=True)
        assert inf.tiene_discrepancias is True

        mapa = {d.estamento: d for d in inf.discrepancias}
        d_muj = mapa["Sexo: Femenino (Mujeres)"]
        assert d_muj.valor_fuente_a == 12
        assert d_muj.valor_fuente_b == 14
        assert d_muj.delta == 2
        assert d_muj.estado == EstadoDiscrepancia.REQUIERE_REVISION

        d_var = mapa["Sexo: Masculino (Varones)"]
        assert d_var.valor_fuente_a == 8
        assert d_var.valor_fuente_b == 6
        assert d_var.delta == -2
        assert d_var.estado == EstadoDiscrepancia.REQUIERE_REVISION

        # Total general permanece concordante
        d_tot = mapa["Total General"]
        assert d_tot.delta == 0
        assert d_tot.estado == EstadoDiscrepancia.CONCORDANTE

    # -------------------------------------------------------------------------
    # 4. Discrepancia del total
    # -------------------------------------------------------------------------
    def test_04_discrepancia_del_total(self):
        # M1 declara 25 participantes; nominales registran 20
        tot_m1 = TotalesM1(mujeres=15, varones=10, total=25)
        tot_nom = TotalesNominales(mujeres=12, varones=8, total=20)
        act = ActividadConsolidada(
            clave_negocio=("feria tecnologica", "las minas", "2026-09-05"),
            nombre_actividad="Feria Tecnológica",
            sede="Las Minas",
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
            total_asistencia_bruta=20,
            total_personas_unicas=20,
        )

        inf = DiscrepancyDetector.evaluar_actividad(act, incluir_concordantes=True)
        assert inf.tiene_discrepancias is True

        mapa = {d.estamento: d for d in inf.discrepancias}
        d_tot = mapa["Total General"]
        assert d_tot.valor_fuente_a == 25
        assert d_tot.valor_fuente_b == 20
        assert d_tot.delta == -5
        assert d_tot.estado == EstadoDiscrepancia.REQUIERE_REVISION

    # -------------------------------------------------------------------------
    # 5. Múltiples discrepancias simultáneas
    # -------------------------------------------------------------------------
    def test_05_multiples_discrepancias_simultaneas(self):
        tot_m1 = TotalesM1(
            mujeres=18,
            varones=12,
            total=30,
            estudiantes_f=12,
            estudiantes_m=8,   # 20 estudiantes
            docentes_f=3,
            docentes_m=2,      # 5 docentes
            colaboradores_f=3,
            colaboradores_m=2, # 5 colaboradores
        )
        tot_nom = TotalesNominales(
            mujeres=16,
            varones=12,
            total=28,          # delta total -2
            estudiantes=22,    # delta est +2
            docentes=3,        # delta doc -2
            colaboradores=3,   # delta col -2
        )
        act = ActividadConsolidada(
            clave_negocio=("congreso regional", "bilwi", "2026-09-05"),
            nombre_actividad="Congreso Regional",
            sede="Bilwi",
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
            total_asistencia_bruta=28,
            total_personas_unicas=28,
        )

        inf = DiscrepancyDetector.evaluar_actividad(act, incluir_concordantes=True)
        assert inf.tiene_discrepancias is True
        assert inf.total_discrepancias >= 4

        # Verificar que cada discrepancia conserve sus deltas y su trazabilidad
        mapa = {d.estamento: d for d in inf.discrepancias}
        assert mapa["Total General"].delta == -2
        assert mapa["Estudiantes"].delta == 2
        assert mapa["Docentes"].delta == -2
        assert mapa["Colaboradores"].delta == -2
        assert mapa["Sexo: Femenino (Mujeres)"].delta == -2
        assert mapa["Sexo: Masculino (Varones)"].delta == 0  # Concordante 12 vs 12

    # -------------------------------------------------------------------------
    # 6. Fuente faltante
    # -------------------------------------------------------------------------
    def test_06_fuente_faltante(self):
        # 6a) M1 ausente (actividad reportada sólo en nominales)
        tot_nom = TotalesNominales(mujeres=10, varones=5, total=15, estudiantes=15)
        act_sin_m1 = ActividadConsolidada(
            clave_negocio=("charla comunitaria", "el rama", None),
            nombre_actividad="Charla Comunitaria",
            sede="El Rama",
            fuente_m1=None,
            totales_m1=None,
            totales_nominales=tot_nom,
            total_asistencia_bruta=15,
            total_personas_unicas=15,
        )

        inf_sin_m1 = DiscrepancyDetector.evaluar_actividad(act_sin_m1)
        assert inf_sin_m1.tiene_discrepancias is True
        disc_m1 = inf_sin_m1.discrepancias[0]
        assert disc_m1.categoria_discrepancia == "FUENTE_FALTANTE"
        assert disc_m1.valor_fuente_a == 0
        assert disc_m1.valor_fuente_b == 15
        assert disc_m1.delta == 15
        assert disc_m1.estado == EstadoDiscrepancia.REQUIERE_REVISION
        assert "ausente en Matriz 1" in disc_m1.descripcion

        # 6b) Nominales ausentes (actividad declarada en M1 pero sin nominales en M2..M5)
        tot_m1 = TotalesM1(mujeres=10, varones=10, total=20)
        tot_nom_vacio = TotalesNominales(total=0)
        act_sin_nom = ActividadConsolidada(
            clave_negocio=("taller sin asistencia", "bilwi", "2026-09-06"),
            nombre_actividad="Taller Sin Asistencia",
            sede="Bilwi",
            totales_m1=tot_m1,
            totales_nominales=tot_nom_vacio,
            participaciones=[],
        )

        inf_sin_nom = DiscrepancyDetector.evaluar_actividad(act_sin_nom)
        assert inf_sin_nom.tiene_discrepancias is True
        mapa_anomalias = {d.categoria_discrepancia: d for d in inf_sin_nom.discrepancias}
        assert "FUENTE_FALTANTE" in mapa_anomalias
        disc_nom = mapa_anomalias["FUENTE_FALTANTE"]
        assert disc_nom.valor_fuente_a == 20
        assert disc_nom.valor_fuente_b == 0
        assert disc_nom.delta == -20
        assert disc_nom.estado == EstadoDiscrepancia.REQUIERE_REVISION

    # -------------------------------------------------------------------------
    # 7. Trazabilidad de cada discrepancia
    # -------------------------------------------------------------------------
    def test_07_trazabilidad_de_cada_discrepancia(self):
        tot_m1 = TotalesM1(mujeres=10, varones=5, total=15, estudiantes_m=5, estudiantes_f=5)
        tot_nom = TotalesNominales(mujeres=12, varones=5, total=17, estudiantes=17)
        act = ActividadConsolidada(
            clave_negocio=("curso trazabilidad", "bilwi", "2026-09-02"),
            nombre_actividad="Curso Trazabilidad",
            sede="Bilwi",
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
        )

        inf = DiscrepancyDetector.evaluar_actividad(act, incluir_concordantes=True)

        for d in inf.discrepancias:
            assert isinstance(d.trazabilidad, dict)
            assert "fuente_a" in d.trazabilidad
            assert "fuente_b" in d.trazabilidad
            assert "valor_fuente_a" in d.trazabilidad
            assert "valor_fuente_b" in d.trazabilidad
            assert "delta" in d.trazabilidad
            assert "categoria" in d.trazabilidad
            # Identificación de ambas fuentes
            assert d.fuente_a is not None and len(d.fuente_a) > 0
            assert d.fuente_b is not None and len(d.fuente_b) > 0

    # -------------------------------------------------------------------------
    # 8. Confirmación de que las fuentes originales no son modificadas
    # -------------------------------------------------------------------------
    def test_08_confirmacion_fuentes_originales_no_modificadas(self):
        tot_m1 = TotalesM1(
            mujeres=12, varones=6, total=18,
            estudiantes_f=10, estudiantes_m=5,
            docentes_f=1, docentes_m=0,
            administrativos_f=1, administrativos_m=1,
        )
        tot_nom = TotalesNominales(
            mujeres=12, varones=6, total=18,
            estudiantes=17, docentes=0, administrativos=1
        )
        act = ActividadConsolidada(
            clave_negocio=("invariante inmutabilidad", "bilwi", "2026-09-02"),
            nombre_actividad="Invariante Inmutabilidad",
            sede="Bilwi",
            totales_m1=tot_m1,
            totales_nominales=tot_nom,
        )

        # Snapshot de valores antes
        m1_total_antes = tot_m1.total
        m1_est_antes = tot_m1.total_estudiantes
        nom_total_antes = tot_nom.total
        nom_est_antes = tot_nom.estudiantes

        # Ejecutar evaluación
        inf = DiscrepancyDetector.evaluar_actividad(act)

        # Comprobar que ningún objeto en memoria fue mutado o reconciliado
        assert tot_m1.total == m1_total_antes == 18
        assert tot_m1.total_estudiantes == m1_est_antes == 15
        assert tot_nom.total == nom_total_antes == 18
        assert tot_nom.estudiantes == nom_est_antes == 17
        assert act.totales_m1.total_estudiantes == 15
        assert act.totales_nominales.estudiantes == 17

    # -------------------------------------------------------------------------
    # 9. Estados CONCORDANTE y REQUIERE_REVISION
    # -------------------------------------------------------------------------
    def test_09_estados_concordante_y_requiere_revision(self):
        # Función evaluar_dimension directa
        d_conc = DiscrepancyDetector.evaluar_dimension(
            id_actividad="act-1",
            nombre_actividad="Prueba",
            estamento_o_dimension="Total",
            valor_a=50,
            valor_b=50,
            fuente_a_nombre="Fuente A",
            fuente_b_nombre="Fuente B",
        )
        assert d_conc.delta == 0
        assert d_conc.estado == EstadoDiscrepancia.CONCORDANTE
        assert d_conc.valor_fuente_a == 50
        assert d_conc.valor_fuente_b == 50

        d_req = DiscrepancyDetector.evaluar_dimension(
            id_actividad="act-1",
            nombre_actividad="Prueba",
            estamento_o_dimension="Total",
            valor_a=50,
            valor_b=52,
            fuente_a_nombre="Fuente A",
            fuente_b_nombre="Fuente B",
        )
        assert d_req.delta == 2
        assert d_req.estado == EstadoDiscrepancia.REQUIERE_REVISION
        assert d_req.valor_fuente_a == 50
        assert d_req.valor_fuente_b == 52

        # Inmutabilidad del item Pydantic
        with pytest.raises(Exception):
            d_req.estado = EstadoDiscrepancia.CONCORDANTE

    # -------------------------------------------------------------------------
    # 10. Caso real Septiembre 2026 Semana 1 (obligatorio)
    # -------------------------------------------------------------------------
    def test_10_caso_real_septiembre_2026_semana_1(
        self,
        rutas_matrices_templates,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        """
        Validación formal del Caso Real obligatorio especificado:
        Informe narrativo:
          estudiantes: 15
          administrativos: 2
          docentes: 1
          total: 18
        Nominal:
          estudiantes: 17
          administrativos: 1
          docentes: 0
          total: 18
        Debe producir:
          estudiantes: delta +2 → REQUIERE_REVISION
          administrativos: delta -1 → REQUIERE_REVISION
          docentes: delta -1 → REQUIERE_REVISION
          total: delta 0 → CONCORDANTE
        """
        narrativo = {
            "estudiantes": 15,
            "administrativos": 2,
            "docentes": 1,
            "total": 18,
        }
        nominal = {
            "estudiantes": 17,
            "administrativos": 1,
            "docentes": 0,
            "total": 18,
        }

        # 1. Evaluación directa mediante el método formal de caso real
        discrepancias_caso = DiscrepancyDetector.evaluar_caso_narrativo_vs_nominal(
            informe_narrativo=narrativo,
            nominales=nominal,
            id_actividad="caso-real-sept-2026",
            nombre_actividad="BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e IA",
            incluir_concordantes=True,
        )

        mapa_caso = {d.estamento.lower(): d for d in discrepancias_caso}

        # Estudiantes: delta +2 -> REQUIERE_REVISION
        assert "estudiantes" in mapa_caso
        d_est = mapa_caso["estudiantes"]
        assert d_est.valor_fuente_a == 15
        assert d_est.valor_fuente_b == 17
        assert d_est.delta == 2
        assert d_est.estado == EstadoDiscrepancia.REQUIERE_REVISION

        # Administrativos: delta -1 -> REQUIERE_REVISION
        assert "administrativos" in mapa_caso
        d_adm = mapa_caso["administrativos"]
        assert d_adm.valor_fuente_a == 2
        assert d_adm.valor_fuente_b == 1
        assert d_adm.delta == -1
        assert d_adm.estado == EstadoDiscrepancia.REQUIERE_REVISION

        # Docentes: delta -1 -> REQUIERE_REVISION
        assert "docentes" in mapa_caso
        d_doc = mapa_caso["docentes"]
        assert d_doc.valor_fuente_a == 1
        assert d_doc.valor_fuente_b == 0
        assert d_doc.delta == -1
        assert d_doc.estado == EstadoDiscrepancia.REQUIERE_REVISION

        # Total: delta 0 -> CONCORDANTE
        assert "total" in mapa_caso
        d_tot = mapa_caso["total"]
        assert d_tot.valor_fuente_a == 18
        assert d_tot.valor_fuente_b == 18
        assert d_tot.delta == 0
        assert d_tot.estado == EstadoDiscrepancia.CONCORDANTE

        # 2. Evaluación sobre la consolidación real leída de output/
        conjunto_output, filtrado_output = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res_output = ConsolidationEngine.consolidar(filtrado_output, fuentes=conjunto_output.fuentes)
        assert res_output.total_actividades == 1

        auditoria = DiscrepancyDetector.evaluar_consolidacion(res_output, incluir_concordantes=True)
        assert auditoria.total_actividades_evaluadas == 1
        # En output/ las matrices fueron diligenciadas con los 18 participantes nominales (17 est + 1 adm = 18 total)
        # por lo que M1 y M2/M3 coinciden al 100% entre sí
        assert auditoria.actividades_concordantes == 1
        assert auditoria.total_discrepancias_activas == 0

        # 3. Comprobación de que los hashes SHA-256 de las 5 matrices en templates/ no se alteraron
        hashes_esperados = {
            "M1": "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad",
            "M2": "11419cd22d986e195694f27d15236204afa22526812f18cb4f2e1b7540f64400",
            "M3": "dc1786616cb1a9bc2f82a74cc693ee20ab95b689b658b366164f502201b07c87",
            "M4": "fd079c5f2be780e602dc563696a6f157d76c4c20410308037cec52f3d2654578",
            "M5": "a3dff20ec209de209f59dd8b1ad1be84aa7aebd1536ced406c59453a08973dc3",
        }
        for code, path in rutas_matrices_templates.items():
            h_actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
            assert h_actual == hashes_esperados[code]

    # -------------------------------------------------------------------------
    # 11. Prueba de integración con ConsolidationEngine
    # -------------------------------------------------------------------------
    def test_11_evaluacion_consolidacion_multiples_actividades(self, periodo_septiembre_2026):
        # Actividad 1: 100% concordante
        act1 = ActividadConsolidada(
            id_actividad="act-001",
            clave_negocio=("actividad uno", "bilwi", "2026-09-02"),
            nombre_actividad="Actividad Uno",
            sede="Bilwi",
            totales_m1=TotalesM1(total=10, estudiantes_m=5, estudiantes_f=5, mujeres=5, varones=5),
            totales_nominales=TotalesNominales(total=10, estudiantes=10, mujeres=5, varones=5),
        )

        # Actividad 2: Con discrepancia (M1=15, Nominales=17)
        act2 = ActividadConsolidada(
            id_actividad="act-002",
            clave_negocio=("actividad dos", "bluefields", "2026-09-03"),
            nombre_actividad="Actividad Dos",
            sede="Bluefields",
            totales_m1=TotalesM1(total=15, estudiantes_m=5, estudiantes_f=5, mujeres=5, varones=10),
            totales_nominales=TotalesNominales(total=17, estudiantes=17, mujeres=7, varones=10),
        )

        resultado = ConsolidationEngine.consolidar(
            filtrado=MatrixReader.leer_y_filtrar.__globals__["ResultadoFiltradoPeriodo"](
                periodo=periodo_septiembre_2026
            )
        )
        resultado.actividades = [act1, act2]
        resultado.total_actividades = 2

        auditoria = DiscrepancyDetector.evaluar_consolidacion(resultado, incluir_concordantes=True)

        assert auditoria.total_actividades_evaluadas == 2
        assert auditoria.actividades_concordantes == 1
        assert auditoria.actividades_con_discrepancias == 1
        assert auditoria.tiene_discrepancias is True
        assert len(resultado.discrepancias) > 0
