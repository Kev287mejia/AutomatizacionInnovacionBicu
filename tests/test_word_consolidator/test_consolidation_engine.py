"""
tests.test_word_consolidator.test_consolidation_engine

Suite exhaustiva de pruebas unitarias e integración para el Motor de Consolidación Institucional
(ConsolidationEngine - Fase 14.4).
Cubre los 25 requisitos obligatorios:
1. Consolidación de una actividad.
2. Consolidación de múltiples actividades.
3. Identificación por nombre + sede + fecha.
4. Separación de actividades iguales en fechas diferentes.
5. Separación de actividades iguales en sedes diferentes.
6. Asociación M2 → estudiante.
7. Asociación M3 → administrativo/docente.
8. Asociación M4 → colaborador.
9. Asociación M5 → beneficiario.
10. Caso real Septiembre 2026 Semana 1.
11. 17 estudiantes + 1 administrativo = 18 nominales.
12. Preservación de sexo.
13. Preservación de carreras.
14. Preservación de cargos.
15. Preservación de entidades.
16. Trazabilidad completa.
17. Distinción asistencia bruta/personas únicas.
18. Recurrencia dentro del período.
19. No deduplicación transversal histórica.
20. M5 histórico fuera del período.
21. No alteración de M1.
22. Datos incompletos/anómalos preservados.
23. No fusión por nombres similares.
24. Determinismo: misma entrada → mismo resultado.
25. Regresión completa e integridad de hashes.
"""

from datetime import date
import hashlib
from pathlib import Path
import pytest

from app.core.constants.participant_types import CategoriaParticipacion
from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ConsolidationEngine,
    ParticipacionConsolidada,
    ResultadoConsolidacion,
    TotalesM1,
    TotalesNominales,
)
from app.word_consolidator.models import (
    ConjuntoMatricesLeidas,
    FilaLeidaM1,
    FilaLeidaNominal,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
    ResultadoFiltradoPeriodo,
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


@pytest.fixture
def periodo_septiembre_2026():
    """Período canónico de la corrida de validación oficial."""
    return PeriodoConsolidacion(
        tipo_periodo=TipoPeriodo.SEMANA,
        anio=2026,
        mes=9,
        semana=1,
        fecha_inicio=date(2026, 9, 1),
        fecha_fin=date(2026, 9, 7),
        etiqueta="Septiembre 2026 - Semana 1"
    )


class TestConsolidationEngineSuite:
    """Suite integral para validar todos los requisitos de Fase 14.4."""

    # -------------------------------------------------------------------------
    # 1. Consolidación de una actividad
    # -------------------------------------------------------------------------
    def test_01_consolidacion_una_actividad(self, periodo_septiembre_2026):
        m1 = FilaLeidaM1(
            hoja="Actividades",
            fila=2,
            sede="Bilwi",
            actividad="Taller de Programación",
            fecha_evento=date(2026, 9, 2),
            total_atencion_m=5,
            total_atencion_f=10,
        )
        nom1 = FilaLeidaNominal(
            matriz_origen="M2",
            hoja="Estudiantes",
            fila=2,
            sede="Bilwi",
            actividad="Taller de Programación",
            nombre_apellidos="Ana Pérez Watson",
            no_cedula="601-010101-1001A",
            sexo="F",
            carrera="Ingeniería en Sistemas"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            actividades_en_periodo=[m1],
            estudiantes_en_periodo=[nom1]
        )

        res = ConsolidationEngine.consolidar(filtrado)
        assert res.total_actividades == 1
        assert res.total_asistencia_bruta == 1
        assert res.total_personas_unicas == 1
        act = res.actividades[0]
        assert act.nombre_actividad == "Taller de Programación"
        assert act.totales_m1.total == 15
        assert act.totales_nominales.total == 1
        assert len(act.estudiantes) == 1

    # -------------------------------------------------------------------------
    # 2. Consolidación de múltiples actividades
    # -------------------------------------------------------------------------
    def test_02_consolidacion_multiples_actividades(self, periodo_septiembre_2026):
        m1_a = FilaLeidaM1(
            hoja="Actividades", fila=2, sede="Bilwi",
            actividad="Taller de Innovación", fecha_evento=date(2026, 9, 2),
            total_atencion_m=2, total_atencion_f=3
        )
        m1_b = FilaLeidaM1(
            hoja="Actividades", fila=3, sede="Bluefields",
            actividad="Foro de Emprendimiento", fecha_evento=date(2026, 9, 4),
            total_atencion_m=4, total_atencion_f=6
        )
        nom_a = FilaLeidaNominal(
            matriz_origen="M2", hoja="Estudiantes", fila=2, sede="Bilwi",
            actividad="Taller de Innovación", nombre_apellidos="Estudiante A",
            sexo="F", no_cedula="601-111111-1001A"
        )
        nom_b = FilaLeidaNominal(
            matriz_origen="M3", hoja="Personal", fila=2, sede="Bluefields",
            actividad="Foro de Emprendimiento", nombre_apellidos="Docente B",
            sexo="M", tipo_protagonistas="DOCENTE", no_cedula="602-222222-2002B"
        )

        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            actividades_en_periodo=[m1_a, m1_b],
            estudiantes_en_periodo=[nom_a],
            academicos_admin_en_periodo=[nom_b]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        assert res.total_actividades == 2
        assert res.total_asistencia_bruta == 2
        assert res.total_personas_unicas == 2

    # -------------------------------------------------------------------------
    # 3. Identificación por nombre + sede + fecha
    # -------------------------------------------------------------------------
    def test_03_identificacion_por_nombre_sede_fecha(self):
        clave = ConsolidationEngine.generar_clave_negocio(
            actividad="  Taller de Robótica Aplicada  ",
            sede="  BICU Bilwi  ",
            fecha=date(2026, 9, 3)
        )
        assert clave == ("taller de robótica aplicada", "bilwi", "2026-09-03")

    # -------------------------------------------------------------------------
    # 4. Separación de actividades iguales en fechas diferentes
    # -------------------------------------------------------------------------
    def test_04_separacion_actividades_iguales_fechas_diferentes(self, periodo_septiembre_2026):
        m1_dia2 = FilaLeidaM1(
            hoja="H1", fila=2, sede="Bilwi", actividad="Taller Liderazgo",
            fecha_evento=date(2026, 9, 2), total_atencion_m=5, total_atencion_f=5
        )
        m1_dia5 = FilaLeidaM1(
            hoja="H1", fila=3, sede="Bilwi", actividad="Taller Liderazgo",
            fecha_evento=date(2026, 9, 5), total_atencion_m=6, total_atencion_f=6
        )

        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            actividades_en_periodo=[m1_dia2, m1_dia5]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        # Deben mantenerse como 2 actividades independientes por tener fechas distintas
        assert res.total_actividades == 2
        claves = {a.clave_negocio for a in res.actividades}
        assert ("taller liderazgo", "bilwi", "2026-09-02") in claves
        assert ("taller liderazgo", "bilwi", "2026-09-05") in claves

    # -------------------------------------------------------------------------
    # 5. Separación de actividades iguales en sedes diferentes
    # -------------------------------------------------------------------------
    def test_05_separacion_actividades_iguales_sedes_diferentes(self, periodo_septiembre_2026):
        m1_bilwi = FilaLeidaM1(
            hoja="H1", fila=2, sede="Bilwi", actividad="Seminario Metodología",
            fecha_evento=date(2026, 9, 3), total_atencion_m=3, total_atencion_f=3
        )
        m1_bluefields = FilaLeidaM1(
            hoja="H1", fila=3, sede="Bluefields", actividad="Seminario Metodología",
            fecha_evento=date(2026, 9, 3), total_atencion_m=4, total_atencion_f=4
        )

        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            actividades_en_periodo=[m1_bilwi, m1_bluefields]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        assert res.total_actividades == 2
        claves = {a.clave_negocio for a in res.actividades}
        assert ("seminario metodología", "bilwi", "2026-09-03") in claves
        assert ("seminario metodología", "bluefields", "2026-09-03") in claves

    # -------------------------------------------------------------------------
    # 6. Asociación M2 → estudiante
    # -------------------------------------------------------------------------
    def test_06_asociacion_m2_estudiante(self, periodo_septiembre_2026):
        nom = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=5, sede="Bilwi",
            actividad="Feria Vocacional", nombre_apellidos="Estudiante M2",
            sexo="M", no_cedula="601-101010-1001M"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            estudiantes_en_periodo=[nom]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        act = res.actividades[0]
        assert len(act.estudiantes) == 1
        assert act.estudiantes[0].categoria == CategoriaParticipacion.ESTUDIANTE
        assert act.estudiantes[0].matriz_origen == "M2"

    # -------------------------------------------------------------------------
    # 7. Asociación M3 → administrativo / docente
    # -------------------------------------------------------------------------
    def test_07_asociacion_m3_administrativo_docente(self, periodo_septiembre_2026):
        nom_adm = FilaLeidaNominal(
            matriz_origen="M3", hoja="H3", fila=2, sede="Bilwi",
            actividad="Consejo de Facultad", nombre_apellidos="Elba Wilson",
            sexo="F", tipo_protagonistas="ADMINISTRATIVO", no_cedula="601-202020-2002A"
        )
        nom_doc = FilaLeidaNominal(
            matriz_origen="M3", hoja="H3", fila=3, sede="Bilwi",
            actividad="Consejo de Facultad", nombre_apellidos="Profesor Juan",
            sexo="M", tipo_protagonistas="DOCENTE", no_cedula="601-303030-3003D"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            academicos_admin_en_periodo=[nom_adm, nom_doc]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        act = res.actividades[0]
        assert len(act.administrativos) == 1
        assert act.administrativos[0].categoria == CategoriaParticipacion.ADMINISTRATIVO
        assert len(act.docentes) == 1
        assert act.docentes[0].categoria == CategoriaParticipacion.DOCENTE

    # -------------------------------------------------------------------------
    # 8. Asociación M4 → colaborador
    # -------------------------------------------------------------------------
    def test_08_asociacion_m4_colaborador(self, periodo_septiembre_2026):
        nom = FilaLeidaNominal(
            matriz_origen="M4", hoja="H4", fila=2, sede="Bilwi",
            actividad="Taller Interinstitucional", nombre_apellidos="Delegado MINED",
            sexo="M", entidad="MINED", no_cedula="601-404040-4004C"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            colaboradores_en_periodo=[nom]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        act = res.actividades[0]
        assert len(act.colaboradores) == 1
        assert act.colaboradores[0].categoria == CategoriaParticipacion.COLABORADOR
        assert act.colaboradores[0].entidad == "MINED"

    # -------------------------------------------------------------------------
    # 9. Asociación M5 → beneficiario
    # -------------------------------------------------------------------------
    def test_09_asociacion_m5_beneficiario(self, periodo_septiembre_2026):
        nom = FilaLeidaNominal(
            matriz_origen="M5", hoja="H5", fila=2, sede="Bilwi",
            actividad="Capacitación Comunitaria", nombre_apellidos="Poblador Comunitario",
            sexo="F", beneficio="Semillas", no_cedula="601-505050-5005B"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            beneficiarios_en_periodo=[nom]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        act = res.actividades[0]
        assert len(act.beneficiarios) == 1
        assert act.beneficiarios[0].categoria == CategoriaParticipacion.BENEFICIADO

    # -------------------------------------------------------------------------
    # 10. Caso real Septiembre 2026 Semana 1
    # -------------------------------------------------------------------------
    def test_10_caso_real_septiembre_2026_semana_1(
        self,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        conjunto, filtrado = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)

        assert res.total_actividades == 1
        act = res.actividades[0]
        assert "diseño de logotipos e inteligencia artificial" in act.nombre_actividad.lower()
        assert act.sede == "Bilwi"

        # Verificación M1
        assert act.totales_m1 is not None
        assert act.totales_m1.mujeres == 12
        assert act.totales_m1.varones == 6
        assert act.totales_m1.total == 18

        # Verificación Nominales
        assert act.totales_nominales.mujeres == 12
        assert act.totales_nominales.varones == 6
        assert act.totales_nominales.total == 18

    # -------------------------------------------------------------------------
    # 11. 17 estudiantes + 1 administrativo = 18 nominales
    # -------------------------------------------------------------------------
    def test_11_caso_real_17_estudiantes_1_administrativo_18_nominales(
        self,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        conjunto, filtrado = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)
        act = res.actividades[0]

        assert len(act.estudiantes) == 17
        assert len(act.administrativos) == 1
        assert len(act.docentes) == 0
        assert len(act.colaboradores) == 0
        assert len(act.beneficiarios) == 0

        assert act.totales_nominales.estudiantes == 17
        assert act.totales_nominales.administrativos == 1
        assert act.totales_nominales.total == 18

    # -------------------------------------------------------------------------
    # 12. Preservación de sexo
    # -------------------------------------------------------------------------
    def test_12_preservacion_sexo(
        self,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        conjunto, filtrado = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)
        act = res.actividades[0]

        # En M2 hay 11 mujeres y 6 varones
        m2_parts = [p for p in act.participaciones if p.matriz_origen == "M2"]
        assert sum(1 for p in m2_parts if p.sexo_normalizado == "FEMENINO") == 11
        assert sum(1 for p in m2_parts if p.sexo_normalizado == "MASCULINO") == 6

        # En M3 hay 1 mujer (Elba Wilson)
        m3_parts = [p for p in act.participaciones if p.matriz_origen == "M3"]
        assert len(m3_parts) == 1
        assert m3_parts[0].sexo_normalizado == "FEMENINO"

        # Conservación estricta de valores textuales originales
        assert all(p.sexo_original in ("F", "M", "FEMENINO", "MASCULINO") for p in act.participaciones)
        assert all(p.sexo_normalizado in ("FEMENINO", "MASCULINO") for p in act.participaciones)

    # -------------------------------------------------------------------------
    # 13. Preservación de carreras
    # -------------------------------------------------------------------------
    def test_13_preservacion_carreras(
        self,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        conjunto, filtrado = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)
        act = res.actividades[0]

        carreras = [p.carrera for p in act.estudiantes if p.carrera]
        # Preserva valores verbatim de los estudiantes
        assert any("Lic. Contabilidad" in c or "Lic. Conta" in c for c in carreras)
        assert any("Ing. Sistemas" in c for c in carreras)

    # -------------------------------------------------------------------------
    # 14. Preservación de cargos
    # -------------------------------------------------------------------------
    def test_14_preservacion_cargos(
        self,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        conjunto, filtrado = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)
        admin = res.actividades[0].administrativos[0]
        # Elba Wilson Smith
        assert "elba wilson smith" in admin.nombre_apellidos.lower()
        assert admin.fila_nominal_origen is not None

    # -------------------------------------------------------------------------
    # 15. Preservación de entidades
    # -------------------------------------------------------------------------
    def test_15_preservacion_entidades(self, periodo_septiembre_2026):
        nom_colab = FilaLeidaNominal(
            matriz_origen="M4", hoja="H4", fila=10, sede="Bilwi",
            actividad="Reunión Red de Innovación", nombre_apellidos="Carlos Vega",
            sexo="M", entidad="Cooperativa Cacaotera", cargo="Gerente Técnico"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            colaboradores_en_periodo=[nom_colab]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        colab = res.actividades[0].colaboradores[0]
        assert colab.entidad == "Cooperativa Cacaotera"
        assert colab.cargo == "Gerente Técnico"

    # -------------------------------------------------------------------------
    # 16. Trazabilidad completa
    # -------------------------------------------------------------------------
    def test_16_trazabilidad_completa(
        self,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        conjunto, filtrado = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)
        act = res.actividades[0]

        # Trazabilidad de M1
        assert act.trazabilidad["fuente_m1"]["matriz"] == "M1"
        assert act.trazabilidad["fuente_m1"]["fila"] == 2

        # Trazabilidad nominal de las 18 participaciones
        for p in act.participaciones:
            assert p.matriz_origen in ("M2", "M3")
            assert p.fila >= 2
            assert p.hoja is not None
            assert len(p.trazabilidad) > 0

    # -------------------------------------------------------------------------
    # 17. Distinción asistencia bruta / personas únicas
    # -------------------------------------------------------------------------
    def test_17_distincion_asistencia_bruta_personas_unicas(self, periodo_septiembre_2026):
        # Misma persona con cédula válida participando en dos actividades del período
        nom_act1 = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=2, sede="Bilwi",
            actividad="Actividad Uno", nombre_apellidos="Denis Hodgson",
            no_cedula="601-121212-1001H", sexo="M"
        )
        nom_act2 = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=3, sede="Bilwi",
            actividad="Actividad Dos", nombre_apellidos="Denis Hodgson",
            no_cedula="601-121212-1001H", sexo="M"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            estudiantes_en_periodo=[nom_act1, nom_act2]
        )
        res = ConsolidationEngine.consolidar(filtrado)

        # 2 participaciones registradas
        assert res.total_asistencia_bruta == 2
        # Pero 1 sola persona física única por Nivel 1 Cédula
        assert res.total_personas_unicas == 1
        # Ambas participaciones apuntan al mismo id_persona canónico
        id_persona_1 = res.actividades[0].participaciones[0].id_persona
        id_persona_2 = res.actividades[1].participaciones[0].id_persona
        assert id_persona_1 == id_persona_2

    # -------------------------------------------------------------------------
    # 18. Recurrencia dentro del período
    # -------------------------------------------------------------------------
    def test_18_recurrencia_dentro_del_periodo(self, periodo_septiembre_2026):
        # 3 asistencias de 2 personas (1 recurrente)
        p1_a = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=2, sede="Bilwi",
            actividad="Act A", nombre_apellidos="Persona 1",
            no_cedula="601-111111-1001A", sexo="F"
        )
        p1_b = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=3, sede="Bilwi",
            actividad="Act B", nombre_apellidos="Persona 1",
            no_cedula="601-111111-1001A", sexo="F"
        )
        p2_a = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=4, sede="Bilwi",
            actividad="Act A", nombre_apellidos="Persona 2",
            no_cedula="601-222222-2002B", sexo="M"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            estudiantes_en_periodo=[p1_a, p1_b, p2_a]
        )
        res = ConsolidationEngine.consolidar(filtrado)

        assert res.total_asistencia_bruta == 3
        assert res.total_personas_unicas == 2
        assert res.total_recurrencia == 1
        assert res.tasa_recurrencia == 33.33

    # -------------------------------------------------------------------------
    # 19. No deduplicación transversal histórica
    # -------------------------------------------------------------------------
    def test_19_no_deduplicacion_transversal_historica(self, periodo_septiembre_2026):
        # Un participante activo en el período
        activo = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=2, sede="Bilwi",
            actividad="Taller Activo", nombre_apellidos="Persona Activa",
            no_cedula="601-999999-9999Z", sexo="F"
        )
        # Un registro histórico preexistente fuera del período con la misma cédula
        historico = FilaLeidaNominal(
            matriz_origen="M5", hoja="H5", fila=50, sede="BICU CUR El Rama",
            actividad="Actividad Histórica Año 2024", nombre_apellidos="Persona Activa",
            no_cedula="601-999999-9999Z", sexo="F"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            estudiantes_en_periodo=[activo],
            nominales_historicos_fuera_periodo=[historico]
        )
        res = ConsolidationEngine.consolidar(filtrado)

        # El período solo tiene 1 asistencia y 1 persona única
        assert res.total_asistencia_bruta == 1
        assert res.total_personas_unicas == 1
        assert res.total_recurrencia == 0

        # El histórico permanece intacto en nominales_historicos_fuera_periodo
        assert len(res.nominales_historicos_fuera_periodo) == 1
        assert res.nominales_historicos_fuera_periodo[0].actividad == "Actividad Histórica Año 2024"

    # -------------------------------------------------------------------------
    # 20. M5 histórico fuera del período
    # -------------------------------------------------------------------------
    def test_20_m5_historico_fuera_del_periodo(
        self,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        conjunto, filtrado = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)

        # Los 32 registros de M5 deben estar catalogados en nominales_historicos_fuera_periodo
        historicos_m5 = [r for r in res.nominales_historicos_fuera_periodo if r.matriz_origen == "M5"]
        assert len(historicos_m5) == 32

        # Cero beneficiarios activos en la actividad consolidada de Septiembre 2026
        act = res.actividades[0]
        assert len(act.beneficiarios) == 0
        assert act.totales_nominales.beneficiarios == 0

    # -------------------------------------------------------------------------
    # 21. No alteración de M1
    # -------------------------------------------------------------------------
    def test_21_no_alteracion_m1(self, periodo_septiembre_2026):
        # M1 declara 20 participantes, pero nominalmente solo hay 15
        m1 = FilaLeidaM1(
            hoja="H1", fila=2, sede="Bilwi", actividad="Actividad Discrepante",
            total_atencion_m=10, total_atencion_f=10
        )
        nominales = [
            FilaLeidaNominal(
                matriz_origen="M2", hoja="H2", fila=i + 2, sede="Bilwi",
                actividad="Actividad Discrepante", nombre_apellidos=f"Estudiante {i}",
                sexo="F" if i % 2 == 0 else "M", no_cedula=f"601-00000{i}-1001A"
            )
            for i in range(15)
        ]
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            actividades_en_periodo=[m1],
            estudiantes_en_periodo=nominales
        )
        res = ConsolidationEngine.consolidar(filtrado)
        act = res.actividades[0]

        # M1 se mantiene en 20 (sin reducirlo)
        assert act.totales_m1.total == 20
        assert act.totales_m1.mujeres == 10
        assert act.totales_m1.varones == 10

        # Nominales se mantienen en 15 (sin inventar participantes)
        assert act.totales_nominales.total == 15
        assert len(act.participaciones) == 15

    # -------------------------------------------------------------------------
    # 22. Datos incompletos / anómalos preservados
    # -------------------------------------------------------------------------
    def test_22_datos_incompletos_anomalos_preservados(self, periodo_septiembre_2026):
        nom_anomalo = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=2, sede="Bilwi",
            actividad="Taller Especial", nombre_apellidos="Dadam Ossiel Mendoza",
            no_cedula=None,  # Cédula ausente
            sexo="M",
            edad="",         # Edad vacía
            carrera=None     # Carrera ausente
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            estudiantes_en_periodo=[nom_anomalo]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        p = res.actividades[0].participaciones[0]

        assert p.nombre_apellidos == "Dadam Ossiel Mendoza"
        assert p.identificacion is None
        assert p.carrera is None
        assert p.sexo_normalizado == "MASCULINO"

    # -------------------------------------------------------------------------
    # 23. No fusión por nombres similares
    # -------------------------------------------------------------------------
    def test_23_no_fusion_por_nombres_similares(self, periodo_septiembre_2026):
        m1_a = FilaLeidaM1(
            hoja="H1", fila=2, sede="Bilwi",
            actividad="Taller de Inteligencia Artificial para Estudiantes",
            total_atencion_m=5, total_atencion_f=5
        )
        m1_b = FilaLeidaM1(
            hoja="H1", fila=3, sede="Bilwi",
            actividad="Taller de Inteligencia Artificial para Docentes",
            total_atencion_m=5, total_atencion_f=5
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            actividades_en_periodo=[m1_a, m1_b]
        )
        res = ConsolidationEngine.consolidar(filtrado)
        # Nombres parecidos no deben fusionarse
        assert res.total_actividades == 2

    # -------------------------------------------------------------------------
    # 24. Determinismo: misma entrada → mismo resultado
    # -------------------------------------------------------------------------
    def test_24_determinismo_misma_entrada_mismo_resultado(
        self,
        rutas_matrices_oficiales_output,
        periodo_septiembre_2026
    ):
        conjunto, filtrado = MatrixReader.leer_y_filtrar(
            rutas_matrices_oficiales_output,
            periodo_septiembre_2026
        )
        res_1 = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)
        res_2 = ConsolidationEngine.consolidar(filtrado, fuentes=conjunto.fuentes)

        assert res_1.total_actividades == res_2.total_actividades
        assert res_1.total_asistencia_bruta == res_2.total_asistencia_bruta
        assert res_1.total_personas_unicas == res_2.total_personas_unicas
        assert res_1.total_recurrencia == res_2.total_recurrencia

        act1 = res_1.actividades[0]
        act2 = res_2.actividades[0]
        assert act1.clave_negocio == act2.clave_negocio
        assert act1.totales_m1.model_dump() == act2.totales_m1.model_dump()
        assert act1.totales_nominales.model_dump() == act2.totales_nominales.model_dump()

    # -------------------------------------------------------------------------
    # 25. Regresión completa e integridad de hashes
    # -------------------------------------------------------------------------
    def test_25_regresion_completa_integridad_hashes(
        self,
        rutas_matrices_templates,
        periodo_septiembre_2026
    ):
        hashes_esperados = {
            "M1": "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad",
            "M2": "11419cd22d986e195694f27d15236204afa22526812f18cb4f2e1b7540f64400",
            "M3": "dc1786616cb1a9bc2f82a74cc693ee20ab95b689b658b366164f502201b07c87",
            "M4": "fd079c5f2be780e602dc563696a6f157d76c4c20410308037cec52f3d2654578",
            "M5": "a3dff20ec209de209f59dd8b1ad1be84aa7aebd1536ced406c59453a08973dc3",
        }

        # 1. Comprobar hashes antes
        for code, path in rutas_matrices_templates.items():
            h_actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
            assert h_actual == hashes_esperados[code]

        # 2. Ejecutar consolidación sobre plantillas
        conjunto = MatrixReader.leer_conjunto_matrices(rutas_matrices_templates)
        res = ConsolidationEngine.consolidar_conjunto(conjunto, periodo_septiembre_2026)
        assert res is not None

        # 3. Comprobar hashes después
        for code, path in rutas_matrices_templates.items():
            h_despues = hashlib.sha256(open(path, "rb").read()).hexdigest()
            assert h_despues == hashes_esperados[code]

    # -------------------------------------------------------------------------
    # 26. Una persona en tres actividades: participaciones=3, únicas=1, recurrencia=2
    # -------------------------------------------------------------------------
    def test_26_una_persona_tres_actividades_coexistencia_participaciones(self, periodo_septiembre_2026):
        # Persona A con la misma cédula válida participa en 3 actividades distintas
        p_act1 = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=2, sede="Bilwi",
            actividad="Actividad Uno", nombre_apellidos="Melvin Cooper",
            no_cedula="601-150895-0001A", sexo="M"
        )
        p_act2 = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=3, sede="Bilwi",
            actividad="Actividad Dos", nombre_apellidos="Melvin Cooper",
            no_cedula="601-150895-0001A", sexo="M"
        )
        p_act3 = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=4, sede="Bilwi",
            actividad="Actividad Tres", nombre_apellidos="Melvin Cooper",
            no_cedula="601-150895-0001A", sexo="M"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            estudiantes_en_periodo=[p_act1, p_act2, p_act3]
        )
        res = ConsolidationEngine.consolidar(filtrado)

        # 3 participaciones legítimas conservadas al 100%
        assert res.total_asistencia_bruta == 3
        # 1 sola persona única por resolución de identidad de Nivel 1 Cédula
        assert res.total_personas_unicas == 1
        # Recurrencia exacta = 3 - 1 = 2
        assert res.total_recurrencia == 2
        assert len(res.actividades) == 3

        # Las tres participaciones permanecen accesibles en sus respectivas actividades
        part1 = res.actividades[0].participaciones[0]
        part2 = res.actividades[1].participaciones[0]
        part3 = res.actividades[2].participaciones[0]

        # Conservan sus id_participacion únicos e independientes
        ids_part = {part1.id_participacion, part2.id_participacion, part3.id_participacion}
        assert len(ids_part) == 3

        # Todas comparten el mismo id_persona canónico
        assert part1.id_persona == part2.id_persona == part3.id_persona

    # -------------------------------------------------------------------------
    # 27. Múltiples personas con recurrencia parcial: participaciones=3, únicas=2, recurrencia=1
    # -------------------------------------------------------------------------
    def test_27_multiples_personas_con_recurrencia_parcial(self, periodo_septiembre_2026):
        # Persona A -> Actividad 1 y Actividad 2
        # Persona B -> Actividad 2
        pa_act1 = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=2, sede="Bilwi",
            actividad="Actividad Alfa", nombre_apellidos="Persona A",
            no_cedula="601-111111-1001A", sexo="F"
        )
        pa_act2 = FilaLeidaNominal(
            matriz_origen="M2", hoja="H2", fila=3, sede="Bilwi",
            actividad="Actividad Beta", nombre_apellidos="Persona A",
            no_cedula="601-111111-1001A", sexo="F"
        )
        pb_act2 = FilaLeidaNominal(
            matriz_origen="M3", hoja="H3", fila=2, sede="Bilwi",
            actividad="Actividad Beta", nombre_apellidos="Persona B",
            tipo_protagonistas="ADMINISTRATIVO",
            no_cedula="601-222222-2002B", sexo="M"
        )
        filtrado = ResultadoFiltradoPeriodo(
            periodo=periodo_septiembre_2026,
            estudiantes_en_periodo=[pa_act1, pa_act2],
            academicos_admin_en_periodo=[pb_act2]
        )
        res = ConsolidationEngine.consolidar(filtrado)

        # 3 participaciones conservadas
        assert res.total_asistencia_bruta == 3
        # 2 personas únicas
        assert res.total_personas_unicas == 2
        # 1 recurrencia (3 - 2 = 1)
        assert res.total_recurrencia == 1

        # En Actividad Alfa hay 1 participación
        act_alfa = next(a for a in res.actividades if a.nombre_actividad == "Actividad Alfa")
        assert len(act_alfa.participaciones) == 1

        # En Actividad Beta hay 2 participaciones (Persona A y Persona B)
        act_beta = next(a for a in res.actividades if a.nombre_actividad == "Actividad Beta")
        assert len(act_beta.participaciones) == 2
        assert len(act_beta.estudiantes) == 1
        assert len(act_beta.administrativos) == 1

