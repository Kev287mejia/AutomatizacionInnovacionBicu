"""
tests/test_statistics.py

Suite de pruebas automatizadas para la Fase 7: Motor Estadístico Institucional y Agregaciones.
Cubre las 14 pruebas formales definidas en el plan de implementación:

1. Total asistencias coincide con modelo interno.
2. Totales por categoría coinciden con ResultadoRouting.
3. Asistencias vs Personas únicas sin recurrencia.
4. Asistencias vs Personas únicas con recurrencia (persona en 2 actividades).
5. Desglose de sexo por actividad y global (F + M + Indefinido == Total).
6. Actividad con cero participantes en una categoría.
7. Fila de consolidado por actividad desacoplada (1 fila por actividad).
8. Trazabilidad explicable de métricas (lista de IDs que respaldan cada cifra).
9. Desglose de subtipo académico vs administrativo.
10. Preservación inmutable de NO_DOCENTE en estadísticas (rol operativo administrativo).
11. Métricas de calidad y salud de datos (% completitud y aptos).
12. Invariante de conservación estadística (sin fugas numéricas).
13. Caso Real Septiembre 2026 (18 asistencias, 18 únicas, 17 est, 1 adm, 12 F, 6 M, 7 Aptos, 11 En Rev).
14. Exportación y serialización JSON del reporte estadístico.
"""

import pytest
from pathlib import Path
from app.core.constants.participant_types import (
    CategoriaParticipacion,
    NivelValidacion,
)
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.routing.participant_router import ParticipantRouter
from app.statistics.models import EstadisticaGlobal
from app.statistics.statistics_engine import StatisticsEngine
from app.statistics.reporter import StatisticsReporter


@pytest.fixture
def actividad_1():
    return Activity(
        id_actividad="act-01",
        nombre_actividad_original="Taller de Inteligencia Artificial",
        sede="Bilwi",
        fecha_evento="08/09/2026",
        municipio_evento="Puerto Cabezas",
        departamento="RACCN",
    )


@pytest.fixture
def actividad_2():
    return Activity(
        id_actividad="act-02",
        nombre_actividad_original="Seminario de Emprendimiento Comunitario",
        sede="Las Minas",
        fecha_evento="15/09/2026",
        municipio_evento="Siuna",
        departamento="RACCN",
    )


class TestMotorEstadisticoFase7:
    """Pruebas unitarias y de integración del Motor Estadístico Institucional."""

    def test_01_total_asistencias_coincide_con_modelo_interno(self, actividad_1):
        """1. El total de asistencias calculadas coincide con las participaciones de entrada."""
        p1 = Person(id_persona_interno="p1", nombre_completo="Juan Perez", sexo_normalizado="MASCULINO")
        p2 = Person(id_persona_interno="p2", nombre_completo="Maria Lopez", sexo_normalizado="FEMENINO")
        part1 = Participation(id_actividad=actividad_1.id_actividad, id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad=actividad_1.id_actividad, id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        routing = ParticipantRouter.enrutar([actividad_1], [p1, p2], [part1, part2])
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p1, p2], [part1, part2])

        assert stats.total_asistencias == 2
        assert stats.total_actividades == 1
        assert stats.invariante_estadistica_valida is True

    def test_02_totales_por_categoria_coinciden_con_routing(self, actividad_1):
        """2. Los conteos por categoría coinciden al 100% con los conteos de ResultadoRouting."""
        personas = [
            Person(id_persona_interno=f"p-{i}", nombre_completo=f"Persona {i}", sexo_normalizado="FEMENINO")
            for i in range(5)
        ]
        participaciones = [
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p-0", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p-1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p-2", categoria_participacion=CategoriaParticipacion.DOCENTE),
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p-3", categoria_participacion=CategoriaParticipacion.BENEFICIADO),
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p-4", categoria_participacion=CategoriaParticipacion.COLABORADOR),
        ]

        routing = ParticipantRouter.enrutar([actividad_1], personas, participaciones)
        stats = StatisticsEngine.calcular(routing, [actividad_1], personas, participaciones)

        assert stats.desglose_categorias["ESTUDIANTES"].conteo_sexo.total == len(routing.estudiantes)
        assert stats.desglose_categorias["DOCENTES"].conteo_sexo.total == 1
        assert stats.desglose_categorias["BENEFICIADOS"].conteo_sexo.total == len(routing.beneficiados)
        assert stats.desglose_categorias["COLABORADORES"].conteo_sexo.total == len(routing.colaboradores)

    def test_03_asistencias_vs_personas_unicas_sin_recurrencia(self, actividad_1):
        """3. Sin recurrencia: Total Asistencias == Total Personas Únicas (promedio = 1.0, recurrentes = 0, tasa = 0%)."""
        personas = [Person(id_persona_interno=f"p{i}", nombre_completo=f"P {i}") for i in range(3)]
        parts = [
            Participation(id_actividad=actividad_1.id_actividad, id_persona=f"p{i}", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
            for i in range(3)
        ]

        routing = ParticipantRouter.enrutar([actividad_1], personas, parts)
        stats = StatisticsEngine.calcular(routing, [actividad_1], personas, parts)

        assert stats.total_asistencias == 3
        assert stats.total_personas_unicas == 3
        assert stats.promedio_asistencias_por_persona == 1.0
        assert stats.personas_recurrentes == 0
        assert stats.tasa_recurrencia == 0.0

    def test_04_asistencias_vs_personas_unicas_con_recurrencia(self, actividad_1, actividad_2):
        """4. Con recurrencia: Una persona asiste a 2 actividades distintas -> Asistencias=2, Únicas=1, Recurrentes=1, tasa=100%."""
        p = Person(id_persona_interno="p-recurrente", nombre_completo="Ana Ruiz", sexo_normalizado="FEMENINO")
        part1 = Participation(id_actividad=actividad_1.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad=actividad_2.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.COLABORADOR)

        routing = ParticipantRouter.enrutar([actividad_1, actividad_2], [p], [part1, part2])
        stats = StatisticsEngine.calcular(routing, [actividad_1, actividad_2], [p], [part1, part2])

        assert stats.total_asistencias == 2
        assert stats.total_personas_unicas == 1
        assert stats.promedio_asistencias_por_persona == 2.0
        assert stats.personas_recurrentes == 1
        assert stats.tasa_recurrencia == 100.0
        assert stats.ids_personas_recurrentes == [p.id_persona_interno]

    def test_persona_con_dos_participaciones_misma_actividad_no_es_recurrente(self, actividad_1):
        """Una persona con dos participaciones en la misma actividad NO se considera recurrente automáticamente."""
        p = Person(id_persona_interno="p-repetida", nombre_completo="Carlos Mora", sexo_normalizado="MASCULINO")
        part1 = Participation(id_actividad=actividad_1.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad=actividad_1.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        routing = ParticipantRouter.enrutar([actividad_1], [p], [part1, part2])
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p], [part1, part2])

        assert stats.total_asistencias == 2
        assert stats.total_personas_unicas == 1
        assert stats.promedio_asistencias_por_persona == 2.0
        assert stats.personas_recurrentes == 0
        assert stats.tasa_recurrencia == 0.0
        assert stats.ids_personas_recurrentes == []

    def test_distincion_promedio_asistencias_vs_tasa_recurrencia(self, actividad_1, actividad_2):
        """Demuestra formalmente que promedio de asistencias por persona != tasa de recurrencia."""
        # 3 personas: P1 asiste a ambas actividades; P2 solo a act1; P3 solo a act2
        p1 = Person(id_persona_interno="p1", nombre_completo="Persona Recurrente")
        p2 = Person(id_persona_interno="p2", nombre_completo="Persona 2")
        p3 = Person(id_persona_interno="p3", nombre_completo="Persona 3")

        parts = [
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_2.id_actividad, id_persona="p1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p2", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_2.id_actividad, id_persona="p3", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
        ]

        routing = ParticipantRouter.enrutar([actividad_1, actividad_2], [p1, p2, p3], parts)
        stats = StatisticsEngine.calcular(routing, [actividad_1, actividad_2], [p1, p2, p3], parts)

        # 4 asistencias / 3 personas únicas = 1.33 asistencias por persona
        assert stats.total_asistencias == 4
        assert stats.total_personas_unicas == 3
        assert stats.promedio_asistencias_por_persona == 1.33
        # Recurrencia: 1 persona en >1 actividad / 3 personas únicas = 33.33%
        assert stats.personas_recurrentes == 1
        assert stats.tasa_recurrencia == 33.33
        assert stats.promedio_asistencias_por_persona != stats.tasa_recurrencia

    def test_05_desglose_sexo_por_actividad_y_global(self, actividad_1):
        """5. F + M + Indefinido == Total tanto por actividad como a nivel global."""
        p_f = Person(id_persona_interno="pf", nombre_completo="Femenina", sexo_normalizado="FEMENINO")
        p_m = Person(id_persona_interno="pm", nombre_completo="Masculino", sexo_normalizado="MASCULINO")
        p_x = Person(id_persona_interno="px", nombre_completo="Sin Sexo", sexo_normalizado=None)

        parts = [
            Participation(id_actividad=actividad_1.id_actividad, id_persona="pf", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_1.id_actividad, id_persona="pm", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_1.id_actividad, id_persona="px", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
        ]

        routing = ParticipantRouter.enrutar([actividad_1], [p_f, p_m, p_x], parts)
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p_f, p_m, p_x], parts)

        # Global
        ds_g = stats.desglose_sexo_global
        assert ds_g.femenino == 1
        assert ds_g.masculino == 1
        assert ds_g.indefinido == 1
        assert ds_g.total == 3
        assert ds_g.femenino + ds_g.masculino + ds_g.indefinido == ds_g.total

        # Actividad
        ds_a = stats.actividades[0].desglose_sexo_global
        assert ds_a.femenino == 1
        assert ds_a.masculino == 1
        assert ds_a.indefinido == 1
        assert ds_a.total == 3

    def test_06_actividad_con_cero_participantes_en_categoria(self, actividad_1):
        """6. Actividad sin participantes en ciertas categorías registra 0 sin romper el cálculo."""
        p = Person(id_persona_interno="p1", nombre_completo="Solo Estudiante", sexo_normalizado="MASCULINO")
        part = Participation(id_actividad=actividad_1.id_actividad, id_persona="p1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        routing = ParticipantRouter.enrutar([actividad_1], [p], [part])
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p], [part])

        act_stat = stats.actividades[0]
        assert act_stat.estudiantes.conteo_sexo.total == 1
        assert act_stat.docentes.conteo_sexo.total == 0
        assert act_stat.administrativos_no_docentes.conteo_sexo.total == 0
        assert act_stat.beneficiados.conteo_sexo.total == 0
        assert act_stat.colaboradores.conteo_sexo.total == 0
        assert act_stat.total_asistencias == 1

    def test_07_fila_consolidado_por_actividad_desacoplada(self, actividad_1, actividad_2):
        """7. Cada Activity produce exactamente 1 fila estadística agregada (sin duplicaciones)."""
        p1 = Person(id_persona_interno="p1", nombre_completo="Persona 1")
        p2 = Person(id_persona_interno="p2", nombre_completo="Persona 2")
        parts = [
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_2.id_actividad, id_persona="p2", categoria_participacion=CategoriaParticipacion.DOCENTE),
        ]

        routing = ParticipantRouter.enrutar([actividad_1, actividad_2], [p1, p2], parts)
        stats = StatisticsEngine.calcular(routing, [actividad_1, actividad_2], [p1, p2], parts)

        assert len(stats.actividades) == 2
        ids_actividades = [a.id_actividad for a in stats.actividades]
        assert actividad_1.id_actividad in ids_actividades
        assert actividad_2.id_actividad in ids_actividades

    def test_08_trazabilidad_explicable_de_metricas(self, actividad_1):
        """8. Cada métrica agregada guarda los id_participacion que la sustentan."""
        p = Person(id_persona_interno="p1", nombre_completo="Estudiante Test")
        part = Participation(id_actividad=actividad_1.id_actividad, id_persona="p1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        routing = ParticipantRouter.enrutar([actividad_1], [p], [part])
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p], [part])

        cat_est = stats.desglose_categorias["ESTUDIANTES"]
        assert part.id_participacion in cat_est.ids_participaciones

        act_est = stats.actividades[0].estudiantes
        assert part.id_participacion in act_est.ids_participaciones

    def test_09_desglose_subtipo_academico_vs_administrativo(self, actividad_1):
        """9. Desglose correcto de docentes (académico) vs administrativos."""
        p_doc = Person(id_persona_interno="p_doc", nombre_completo="Docente Test", sexo_normalizado="FEMENINO")
        p_adm = Person(id_persona_interno="p_adm", nombre_completo="Admin Test", sexo_normalizado="MASCULINO")

        part_doc = Participation(id_actividad=actividad_1.id_actividad, id_persona="p_doc", categoria_participacion=CategoriaParticipacion.DOCENTE)
        part_adm = Participation(id_actividad=actividad_1.id_actividad, id_persona="p_adm", categoria_participacion=CategoriaParticipacion.ADMINISTRATIVO)

        routing = ParticipantRouter.enrutar([actividad_1], [p_doc, p_adm], [part_doc, part_adm])
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p_doc, p_adm], [part_doc, part_adm])

        assert stats.desglose_categorias["DOCENTES"].conteo_sexo.total == 1
        assert stats.desglose_categorias["DOCENTES"].conteo_sexo.femenino == 1
        assert stats.desglose_categorias["ADMINISTRATIVOS_NO_DOCENTES"].conteo_sexo.total == 1
        assert stats.desglose_categorias["ADMINISTRATIVOS_NO_DOCENTES"].conteo_sexo.masculino == 1

    def test_10_preservacion_inmutable_de_no_docente_en_estadisticas(self, actividad_1):
        """10. NO_DOCENTE tributa al rol operativo administrativo sin alterar su categoría."""
        p_nodoc = Person(id_persona_interno="p_nodoc", nombre_completo="No Docente Test", sexo_normalizado="FEMENINO")
        part_nodoc = Participation(
            id_actividad=actividad_1.id_actividad,
            id_persona="p_nodoc",
            categoria_participacion=CategoriaParticipacion.NO_DOCENTE,
        )

        routing = ParticipantRouter.enrutar([actividad_1], [p_nodoc], [part_nodoc])
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p_nodoc], [part_nodoc])

        # En estadísticas tributa a ADMINISTRATIVOS_NO_DOCENTES
        assert stats.desglose_categorias["ADMINISTRATIVOS_NO_DOCENTES"].conteo_sexo.total == 1
        # Pero la participación original conserva inmutable su categoría
        assert part_nodoc.categoria_participacion == CategoriaParticipacion.NO_DOCENTE

    def test_11_metricas_de_calidad_de_datos(self, actividad_1):
        """11. Cálculo de métricas de completitud con numerador, denominador y definición."""
        p1 = Person(id_persona_interno="p1", nombre_completo="P1", cedula="601-120502-1001A", sexo_normalizado="FEMENINO", edad=22, carrera_original="Contabilidad")
        p2 = Person(id_persona_interno="p2", nombre_completo="P2", cedula=None, sexo_normalizado=None, edad=None)

        part1 = Participation(id_actividad=actividad_1.id_actividad, id_persona="p1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad=actividad_1.id_actividad, id_persona="p2", categoria_participacion=CategoriaParticipacion.ESTUDIANTE, requiere_revision=True)

        routing = ParticipantRouter.enrutar([actividad_1], [p1, p2], [part1, part2])
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p1, p2], [part1, part2])

        cal = stats.calidad_datos
        assert cal.total_registros == 2
        assert cal.registros_aptos == 1
        assert cal.registros_en_revision == 1
        assert cal.porcentaje_aptos == 50.0
        assert cal.porcentaje_en_revision == 50.0

        # Cédula
        assert cal.cedula_disponible.numerador == 1
        assert cal.cedula_disponible.denominador == 2
        assert cal.cedula_disponible.porcentaje == 50.0
        assert len(cal.cedula_disponible.definicion) > 0
        assert cal.cedula_disponible_pct == 50.0

        # Sexo
        assert cal.sexo_confirmado.numerador == 1
        assert cal.sexo_confirmado.denominador == 2
        assert cal.sexo_confirmado.porcentaje == 50.0
        assert len(cal.sexo_confirmado.definicion) > 0
        assert cal.sexo_confirmado_pct == 50.0

        # Edad
        assert cal.edad_disponible.numerador == 1
        assert cal.edad_disponible.denominador == 2
        assert cal.edad_disponible.porcentaje == 50.0
        assert len(cal.edad_disponible.definicion) > 0
        assert cal.edad_disponible_pct == 50.0

        # Carrera
        assert cal.carrera_disponible.numerador == 1
        assert cal.carrera_disponible.denominador == 2
        assert cal.carrera_disponible.porcentaje == 50.0
        assert len(cal.carrera_disponible.definicion) > 0
        assert cal.carrera_disponible_pct == 50.0

    def test_12_invariante_de_conservacion_estadistica(self, actividad_1, actividad_2):
        """12. Verificación de invariantes numéricas sin discrepancias."""
        personas = [Person(id_persona_interno=f"p{i}", nombre_completo=f"P {i}", sexo_normalizado="FEMENINO") for i in range(4)]
        parts = [
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p0", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_1.id_actividad, id_persona="p1", categoria_participacion=CategoriaParticipacion.DOCENTE),
            Participation(id_actividad=actividad_2.id_actividad, id_persona="p2", categoria_participacion=CategoriaParticipacion.ADMINISTRATIVO),
            Participation(id_actividad=actividad_2.id_actividad, id_persona="p3", categoria_participacion=CategoriaParticipacion.BENEFICIADO),
        ]

        routing = ParticipantRouter.enrutar([actividad_1, actividad_2], personas, parts)
        stats = StatisticsEngine.calcular(routing, [actividad_1, actividad_2], personas, parts)

        assert stats.invariante_estadistica_valida is True
        suma_act = sum(a.total_asistencias for a in stats.actividades)
        assert suma_act == stats.total_asistencias == 4

    def test_13_caso_real_septiembre_2026_estadisticas(self):
        """
        13. Caso Real Septiembre 2026:
        - 1 actividad.
        - 18 asistencias brutas.
        - 18 personas únicas.
        - Promedio asistencias por persona = 1.00.
        - Personas recurrentes = 0.
        - Tasa de recurrencia = 0.00%.
        - 17 estudiantes (11 Femenino, 6 Masculino).
        - 1 administrativo (Elba Wilson Smith, Femenino).
        - 0 docentes, 0 beneficiados, 0 colaboradores.
        - Total Sexo: 12 Femenino (66.67%), 6 Masculino (33.33%).
        - Calidad: 7 Aptos (38.89%), 11 En Revisión (61.11%).
        - Métricas con numerador/denominador auditados.
        """
        from app.parsers.word_parser import WordReportParser
        from app.parsers.attendance_parser import AttendanceParser
        from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
        from app.matching.activity_matcher import ActivityMatcher
        from app.matching.identity_resolver import IdentityResolver
        from app.validation.validator import DataValidator

        datos_word = {
            "actividad": "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial",
            "departamento_institucional": "Innovación y Emprendimiento",
            "mes": "Septiembre",
            "semana": "1",
            "sede": "Bilwi",
            "departamento_territorial": "RACCN",
            "municipio": "Puerto Cabezas",
            "eje": "11.41.67",
            "tipo_actividad": "7. Creatividad, Ciencias, Investigación e Innovación",
            "fecha": "08/09/2026",
            "horario": "10:00 AM – 12:00 PM",
        }
        filas = [
            RawParticipantRow(numero_fila=1, hoja=1, nombre_completo="Johnny Melvin", sexo="M", cedula="601-120502-1001A", edad=24, carrera="Lic. Conta", categoria="Estudiante"),
            RawParticipantRow(numero_fila=2, hoja=1, nombre_completo="Shana Ruiz Watson", sexo="F", cedula="20-04-2008", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=3, hoja=1, nombre_completo="Claudia J Fernandez", sexo="F", cedula="607-221205-1002W", edad=18, carrera="contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=4, hoja=1, nombre_completo="Besi Wrealy N Taylor", sexo="F", cedula="612-311004-1000B", edad=21, carrera="Lic Contabil.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=5, hoja=1, nombre_completo="Yeison Johnston R.M.", sexo="M", cedula="601-140703-1003C", edad=23, carrera="Ing. sistc.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=6, hoja=1, nombre_completo="Neidy Rivera G", sexo="F", cedula="601-090905-1004D", edad=21, carrera="Sistema", categoria="Estudiante"),
            RawParticipantRow(numero_fila=7, hoja=1, nombre_completo="Elba Wilson Smith", sexo="F", cedula="601-300101-1005E", edad=25, carrera="A. estudiantil", categoria="No Docente", area="ACCES"),
            RawParticipantRow(numero_fila=8, hoja=2, nombre_completo="Keyra Rolack G", sexo="F", cedula="601-180304-1006F", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=9, hoja=2, nombre_completo="Luz Marina Alan A", sexo="F", cedula="23/06/2008", edad=23, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=10, hoja=2, nombre_completo="Mari Esther Zeniga", sexo="F", cedula="601-050604-1008H", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=11, hoja=2, nombre_completo="Jessenia Gomez Rivera", sexo="F", cedula="601-150205-1009I", edad=21, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=12, hoja=2, nombre_completo="Esther Gabriela Pedro", sexo="F", cedula="601-111004-1010J", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=13, hoja=2, nombre_completo="Nelba Jhanida Pablo Zamora", sexo="F", cedula="601-040403-1011K", edad=23, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=14, hoja=2, nombre_completo="Estrella Reymundo Peñer", sexo="F", cedula="601-290704-1012L", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=15, hoja=2, nombre_completo="Marcos Michell Hernandez", sexo="M", cedula="601-170802-1013M", edad=24, carrera="Ing. sistc.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=16, hoja=2, nombre_completo="Jhondy Jimmy Arragón", sexo="M", cedula="601-020903-1014N", edad=23, carrera="Ing. sistc.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=17, hoja=2, nombre_completo="Dadam Ossiel Mendoza", sexo="M", cedula=None, edad=24, carrera="Ing. sistc.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=18, hoja=2, nombre_completo="Joyner Henr Ruiz Watson", sexo="M", cedula="601-070104-1016P", edad=22, carrera="Ing. sistc.", categoria="Estudiante"),
        ]
        sheet_data = RawAttendanceSheetData(
            nombre_actividad="Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial",
            fecha="08/09/2026",
            sede="Bilwi",
            departamento="RACCN",
            municipio="Puerto Cabezas",
            horario="10:00 AM – 12:00 PM",
            filas=filas,
            fuente_origen="asistencia_fisica",
        )

        actividad_word = WordReportParser.parse_from_dict(datos_word, fuente="informe_word")
        match_res = ActivityMatcher.evaluar_coincidencia(
            actividad_word=actividad_word,
            datos_asistencia={
                "nombre_actividad_asistencia": sheet_data.nombre_actividad,
                "fecha_evento": sheet_data.fecha,
                "sede": sheet_data.sede,
                "departamento": sheet_data.departamento,
                "municipio_evento": sheet_data.municipio,
                "horario": sheet_data.horario,
                "fuente_origen": sheet_data.fuente_origen,
            },
        )
        actividad_unificada = match_res.actividad_unificada or actividad_word
        parsed_asist = AttendanceParser.parse_sheet_data(sheet_data, id_actividad=actividad_unificada.id_actividad)
        res_dedup = IdentityResolver.resolver_identidades(parsed_asist.personas, parsed_asist.participaciones)
        validaciones_totales = DataValidator.validar_conjunto(
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones_previas=parsed_asist.validaciones + match_res.validaciones + res_dedup.validaciones,
        )
        resultado_routing = ParticipantRouter.enrutar(
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones=validaciones_totales,
        )

        # CÁLCULO ESTADÍSTICO (FASE 7)
        stats = StatisticsEngine.calcular(
            resultado_routing=resultado_routing,
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
        )

        # Validaciones de totales y recurrencia
        assert stats.total_actividades == 1
        assert stats.total_asistencias == 18
        assert stats.total_personas_unicas == 18
        assert stats.promedio_asistencias_por_persona == 1.00
        assert stats.personas_recurrentes == 0
        assert stats.tasa_recurrencia == 0.00
        assert stats.ids_personas_recurrentes == []

        # Validaciones de sexo
        assert stats.desglose_sexo_global.femenino == 12
        assert stats.desglose_sexo_global.masculino == 6
        assert stats.desglose_sexo_global.indefinido == 0
        assert stats.desglose_sexo_global.porcentaje_femenino == 66.67
        assert stats.desglose_sexo_global.porcentaje_masculino == 33.33

        # Categorías
        assert stats.desglose_categorias["ESTUDIANTES"].conteo_sexo.total == 17
        assert stats.desglose_categorias["ESTUDIANTES"].conteo_sexo.femenino == 11
        assert stats.desglose_categorias["ESTUDIANTES"].conteo_sexo.masculino == 6
        assert stats.desglose_categorias["ADMINISTRATIVOS_NO_DOCENTES"].conteo_sexo.total == 1
        assert stats.desglose_categorias["ADMINISTRATIVOS_NO_DOCENTES"].conteo_sexo.femenino == 1
        assert stats.desglose_categorias["DOCENTES"].conteo_sexo.total == 0
        assert stats.desglose_categorias["BENEFICIADOS"].conteo_sexo.total == 0
        assert stats.desglose_categorias["COLABORADORES"].conteo_sexo.total == 0

        # Calidad Operativa
        assert stats.calidad_datos.registros_aptos == 7
        assert stats.calidad_datos.registros_en_revision == 11
        assert stats.calidad_datos.registros_bloqueados == 0
        assert stats.calidad_datos.porcentaje_aptos == 38.89
        assert stats.calidad_datos.porcentaje_en_revision == 61.11

        # Auditoría de métricas de calidad (Numerador, Denominador, Porcentaje y Criterio)
        assert stats.calidad_datos.cedula_disponible.numerador == 15
        assert stats.calidad_datos.cedula_disponible.denominador == 18
        assert stats.calidad_datos.cedula_disponible.porcentaje == 83.33
        assert stats.calidad_datos.cedula_disponible_pct == 83.33

        assert stats.calidad_datos.sexo_confirmado.numerador == 18
        assert stats.calidad_datos.sexo_confirmado.denominador == 18
        assert stats.calidad_datos.sexo_confirmado.porcentaje == 100.00
        assert stats.calidad_datos.sexo_confirmado_pct == 100.00

        assert stats.calidad_datos.edad_disponible.numerador == 18
        assert stats.calidad_datos.edad_disponible.denominador == 18
        assert stats.calidad_datos.edad_disponible.porcentaje == 100.00
        assert stats.calidad_datos.edad_disponible_pct == 100.00

        assert stats.calidad_datos.carrera_disponible.numerador == 17
        assert stats.calidad_datos.carrera_disponible.denominador == 17
        assert stats.calidad_datos.carrera_disponible.porcentaje == 100.00
        assert stats.calidad_datos.carrera_disponible_pct == 100.00

        # Invariante
        assert stats.invariante_estadistica_valida is True

    def test_14_exportacion_reporte_estadistico_json(self, tmp_path, actividad_1):
        """14. Generación y serialización correcta de output/reporte_estadistico.json."""
        p = Person(id_persona_interno="p1", nombre_completo="Test", sexo_normalizado="MASCULINO")
        part = Participation(id_actividad=actividad_1.id_actividad, id_persona="p1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        routing = ParticipantRouter.enrutar([actividad_1], [p], [part])
        stats = StatisticsEngine.calcular(routing, [actividad_1], [p], [part])

        ruta_salida = tmp_path / "reporte_estadistico.json"
        guardada = StatisticsReporter.guardar_json(stats, ruta_salida)

        assert guardada.exists()
        assert guardada.stat().st_size > 0

        # Formateo consola sin excepciones
        texto = StatisticsReporter.formatear_consola(stats)
        assert "REPORTE ESTADÍSTICO INSTITUCIONAL Y AGREGACIONES (FASE 7)" in texto
        assert "Promedio de asistencias por persona:" in texto
        assert "Personas recurrentes:" in texto
        assert "Tasa de recurrencia:" in texto
        assert "Métricas de Calidad y Disponibilidad (Auditadas con Denominador):" in texto
