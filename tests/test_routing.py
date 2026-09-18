"""
tests/test_routing.py

Suite de pruebas automatizadas para la Fase 6: Motor de Enrutamiento Institucional.
Cubre las 16 pruebas obligatorias establecidas en la auditoría y orden de implementación:

1. ESTUDIANTE -> ESTUDIANTES.
2. DOCENTE -> Académico (ACADEMICOS_ADMINISTRATIVOS).
3. ADMINISTRATIVO -> Administrativo (ACADEMICOS_ADMINISTRATIVOS).
4. NO_DOCENTE -> Administrativo sin modificar la categoría original (inmutabilidad).
5. BENEFICIADO -> Beneficiados.
6. POBLADOR_GENERAL -> Beneficiados.
7. COLABORADOR -> Colaboradores.
8. DESCONOCIDO -> Cola de revisión.
9. Participación huérfana -> Bloqueado.
10. Error crítico asociado -> Bloqueado.
11. EN_REVISION + categoría válida -> permanece en matriz (EN_REVISION != COLA_REVISION).
12. Misma persona con diferentes categorías -> routing independiente.
13. Actividad con múltiples tipos de participantes.
14. Ninguna participación aparece en más de un destino (unicidad).
15. Invariante de conservación (Entrada == suma de destinos).
16. Caso real Septiembre 2026 (18 = 17 Estudiantes + 1 Académico/Admin, 7 Apto, 11 En Revisión).
"""

import pytest
from app.core.constants.participant_types import (
    CategoriaParticipacion,
    NivelValidacion,
    NivelConfianzaIdentidad,
)
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.routing.participant_router import ParticipantRouter


@pytest.fixture
def actividad_base():
    return Activity(
        id_actividad="act-test-01",
        nombre_actividad_original="Taller de Innovación y Emprendimiento",
        sede="Bilwi",
        fecha_evento="08/09/2026",
    )


@pytest.fixture
def persona_base():
    return Person(
        id_persona_interno="per-test-01",
        nombre_completo="Carlos Morales Jarquín",
        cedula="601-120502-1001A",
        sexo_normalizado="MASCULINO",
        edad=24,
    )


class TestRoutingInstitucionalFase6:
    """Pruebas del motor de routing institucional."""

    def test_01_enrutamiento_estudiante_a_estudiantes(self, actividad_base, persona_base):
        """1. ESTUDIANTE -> Matriz de Estudiantes con Subtipo NO_APLICA."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
        )

        assert len(res.estudiantes) == 1
        assert res.estudiantes[0].matriz_destino == MatrizDestino.ESTUDIANTES
        assert res.estudiantes[0].subtipo_institucional == SubtipoInstitucional.NO_APLICA
        assert res.estudiantes[0].estado_operativo == "APTO"
        assert res.total_entrada == 1
        assert res.total_clasificadas == 1
        assert res.invariante_valida is True

    def test_02_enrutamiento_docente_a_academico(self, actividad_base, persona_base):
        """2. DOCENTE -> Matriz Académicos y Administrativos con Subtipo ACADEMICO."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
        )

        assert len(res.academicos_administrativos) == 1
        registro = res.academicos_administrativos[0]
        assert registro.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
        assert registro.subtipo_institucional == SubtipoInstitucional.ACADEMICO

    def test_03_enrutamiento_administrativo_a_administrativo(self, actividad_base, persona_base):
        """3. ADMINISTRATIVO -> Matriz Académicos y Administrativos con Subtipo ADMINISTRATIVO."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ADMINISTRATIVO,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
        )

        assert len(res.academicos_administrativos) == 1
        registro = res.academicos_administrativos[0]
        assert registro.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
        assert registro.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO

    def test_04_enrutamiento_no_docente_conserva_categoria_y_subtipo_administrativo(
        self, actividad_base, persona_base
    ):
        """
        4. NO_DOCENTE -> Administrativo sin modificar la categoría original.
        Verifica que part.categoria_participacion permanezca NO_DOCENTE.
        """
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.NO_DOCENTE,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
        )

        assert len(res.academicos_administrativos) == 1
        registro = res.academicos_administrativos[0]
        assert registro.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
        assert registro.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO
        # REGLA DE ORO DE INMUTABILIDAD:
        assert registro.participacion.categoria_participacion == CategoriaParticipacion.NO_DOCENTE
        assert part.categoria_participacion == CategoriaParticipacion.NO_DOCENTE

    def test_05_enrutamiento_beneficiado_a_beneficiados(self, actividad_base, persona_base):
        """5. BENEFICIADO -> Protagonistas Beneficiados."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.BENEFICIADO,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
        )

        assert len(res.beneficiados) == 1
        assert res.beneficiados[0].matriz_destino == MatrizDestino.BENEFICIADOS
        assert res.beneficiados[0].subtipo_institucional == SubtipoInstitucional.NO_APLICA

    def test_06_enrutamiento_poblador_general_a_beneficiados(self, actividad_base, persona_base):
        """6. POBLADOR_GENERAL -> Protagonistas Beneficiados."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.POBLADOR_GENERAL,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
        )

        assert len(res.beneficiados) == 1
        assert res.beneficiados[0].matriz_destino == MatrizDestino.BENEFICIADOS
        assert res.beneficiados[0].subtipo_institucional == SubtipoInstitucional.NO_APLICA

    def test_07_enrutamiento_colaborador_a_colaboradores(self, actividad_base, persona_base):
        """7. COLABORADOR -> Colaboradores."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.COLABORADOR,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
        )

        assert len(res.colaboradores) == 1
        assert res.colaboradores[0].matriz_destino == MatrizDestino.COLABORADORES
        assert res.colaboradores[0].subtipo_institucional == SubtipoInstitucional.NO_APLICA

    def test_08_enrutamiento_desconocido_a_cola_revision(self, actividad_base, persona_base):
        """8. DESCONOCIDO -> Cola de revisión (no se adivina matriz)."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DESCONOCIDO,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
        )

        assert len(res.cola_revision) == 1
        assert res.cola_revision[0].matriz_destino == MatrizDestino.COLA_REVISION
        assert res.cola_revision[0].estado_operativo == "EN_REVISION"
        assert len(res.estudiantes) == 0
        assert len(res.academicos_administrativos) == 0
        assert len(res.beneficiados) == 0
        assert len(res.colaboradores) == 0

    def test_09_participacion_huerfana_a_bloqueados(self, actividad_base):
        """9. Participación huérfana (persona inexistente) -> Bloqueado."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona="persona-inexistente-123",
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[],  # Sin la persona
            participaciones=[part],
        )

        assert len(res.bloqueados) == 1
        assert res.bloqueados[0].matriz_destino == MatrizDestino.BLOQUEADOS
        assert res.bloqueados[0].estado_operativo == "BLOQUEADO"
        assert len(res.estudiantes) == 0

    def test_10_error_critico_asociado_a_bloqueados(self, actividad_base, persona_base):
        """10. Error crítico asociado específicamente a la participación -> Bloqueado."""
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        val_error = ValidationResult(
            id_referencia=part.id_participacion,
            nivel=NivelValidacion.ERROR,
            codigo="ERR_CRITICO_TEST",
            mensaje="Error crítico de prueba que bloquea el registro.",
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
            validaciones=[val_error],
        )

        assert len(res.bloqueados) == 1
        assert res.bloqueados[0].matriz_destino == MatrizDestino.BLOQUEADOS
        assert res.bloqueados[0].estado_operativo == "BLOQUEADO"
        assert len(res.estudiantes) == 0

    def test_11_en_revision_con_categoria_valida_permanece_en_matriz(
        self, actividad_base, persona_base
    ):
        """
        11. EN_REVISION + categoría válida permanece en su matriz oficial.
        Demuestra formalmente que EN_REVISION != COLA_REVISION.
        """
        part = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            requiere_revision=True,
            motivo_revision="Cédula sospechosa de fecha.",
        )
        val_rev = ValidationResult(
            id_referencia=part.id_participacion,
            nivel=NivelValidacion.REVISION,
            codigo="VAL_CEDULA_FECHA",
            mensaje="Formato de fecha en campo cédula.",
        )
        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part],
            validaciones=[val_rev],
        )

        # Permanece en Estudiantes
        assert len(res.estudiantes) == 1
        assert res.estudiantes[0].matriz_destino == MatrizDestino.ESTUDIANTES
        assert res.estudiantes[0].estado_operativo == "EN_REVISION"
        # NO va a COLA_REVISION
        assert len(res.cola_revision) == 0

    def test_12_misma_persona_diferentes_categorias_routing_independiente(
        self, actividad_base, persona_base
    ):
        """
        12. Misma persona con diferentes participaciones en diferentes actividades
        se enruta de forma totalmente independiente según su categoria_participacion.
        """
        actividad_2 = Activity(
            id_actividad="act-test-02",
            nombre_actividad_original="Feria Tecnológica",
            sede="Bilwi",
            fecha_evento="15/09/2026",
        )
        part_estudiante = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        part_colaborador = Participation(
            id_actividad=actividad_2.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.COLABORADOR,
        )

        res = ParticipantRouter.enrutar(
            actividades=[actividad_base, actividad_2],
            personas=[persona_base],
            participaciones=[part_estudiante, part_colaborador],
        )

        assert len(res.estudiantes) == 1
        assert len(res.colaboradores) == 1
        assert res.estudiantes[0].participacion.id_participacion == part_estudiante.id_participacion
        assert res.colaboradores[0].participacion.id_participacion == part_colaborador.id_participacion
        assert res.total_entrada == 2
        assert res.total_clasificadas == 2

    def test_13_actividad_con_multiples_tipos_de_participantes(self, actividad_base):
        """13. Una misma actividad alimenta múltiples matrices preservando el id_actividad."""
        p_est = Person(id_persona_interno="p1", nombre_completo="Estudiante Uno")
        p_doc = Person(id_persona_interno="p2", nombre_completo="Docente Dos")
        p_ben = Person(id_persona_interno="p3", nombre_completo="Beneficiado Tres")

        part1 = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=p_est.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        part2 = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=p_doc.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
        )
        part3 = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=p_ben.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.BENEFICIADO,
        )

        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[p_est, p_doc, p_ben],
            participaciones=[part1, part2, part3],
        )

        assert len(res.estudiantes) == 1
        assert len(res.academicos_administrativos) == 1
        assert len(res.beneficiados) == 1
        assert res.estudiantes[0].actividad.id_actividad == actividad_base.id_actividad
        assert res.academicos_administrativos[0].actividad.id_actividad == actividad_base.id_actividad
        assert res.beneficiados[0].actividad.id_actividad == actividad_base.id_actividad

    def test_14_unicidad_de_destino_ninguna_participacion_duplicada(
        self, actividad_base, persona_base
    ):
        """14. Cada participación tiene exactamente un destino y no se duplica en ninguna lista."""
        part1 = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        part2 = Participation(
            id_actividad=actividad_base.id_actividad,
            id_persona=persona_base.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
        )

        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=[persona_base],
            participaciones=[part1, part2],
        )

        ids_est = {r.participacion.id_participacion for r in res.estudiantes}
        ids_acad = {r.participacion.id_participacion for r in res.academicos_administrativos}
        ids_colab = {r.participacion.id_participacion for r in res.colaboradores}
        ids_ben = {r.participacion.id_participacion for r in res.beneficiados}
        ids_rev = {r.participacion.id_participacion for r in res.cola_revision}
        ids_bloq = {r.participacion.id_participacion for r in res.bloqueados}

        # Intersecciones completamente vacías (disjuntas)
        assert ids_est.isdisjoint(ids_acad)
        assert ids_est.isdisjoint(ids_colab)
        assert ids_est.isdisjoint(ids_ben)
        assert ids_est.isdisjoint(ids_rev)
        assert ids_est.isdisjoint(ids_bloq)
        assert ids_acad.isdisjoint(ids_colab)

    def test_15_invariante_de_conservacion(self, actividad_base):
        """
        15. Invariante formal estricta:
        Entrada == Estudiantes + Academicos/Admin + Beneficiados + Colaboradores + ColaRevision + Bloqueados
        (CONSOLIDADO no participa en la suma).
        """
        personas = [
            Person(id_persona_interno=f"p-{i}", nombre_completo=f"Persona {i}")
            for i in range(10)
        ]
        participaciones = [
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-0", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-2", categoria_participacion=CategoriaParticipacion.DOCENTE),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-3", categoria_participacion=CategoriaParticipacion.ADMINISTRATIVO),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-4", categoria_participacion=CategoriaParticipacion.NO_DOCENTE),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-5", categoria_participacion=CategoriaParticipacion.POBLADOR_GENERAL),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-6", categoria_participacion=CategoriaParticipacion.BENEFICIADO),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-7", categoria_participacion=CategoriaParticipacion.COLABORADOR),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="p-8", categoria_participacion=CategoriaParticipacion.DESCONOCIDO),
            Participation(id_actividad=actividad_base.id_actividad, id_persona="huerfana-999", categoria_participacion=CategoriaParticipacion.ESTUDIANTE),
        ]

        res = ParticipantRouter.enrutar(
            actividades=[actividad_base],
            personas=personas,
            participaciones=participaciones,
        )

        assert res.total_entrada == 10
        assert res.total_clasificadas == 10
        assert len(res.estudiantes) == 2
        assert len(res.academicos_administrativos) == 3  # DOCENTE, ADMINISTRATIVO, NO_DOCENTE
        assert len(res.beneficiados) == 2               # POBLADOR_GENERAL, BENEFICIADO
        assert len(res.colaboradores) == 1              # COLABORADOR
        assert len(res.cola_revision) == 1              # DESCONOCIDO
        assert len(res.bloqueados) == 1                 # huerfana
        assert res.invariante_valida is True

    def test_16_caso_real_septiembre_2026_routing_oficial(self):
        """
        16. Caso Real Septiembre 2026:
        - 18 participaciones de entrada.
        - 17 a Estudiantes.
        - 1 a Académicos y Administrativos (Elba Wilson Smith, NO_DOCENTE -> ADMINISTRATIVO).
        - 0 a Beneficiados, 0 a Colaboradores, 0 a Cola de Revisión, 0 a Bloqueados.
        - 7 APTO, 11 EN_REVISION (permanecen en su matriz).
        - Invariante formal: 18 = 17 + 1 + 0 + 0 + 0 + 0.
        """
        from app.parsers.word_parser import WordReportParser
        from app.parsers.attendance_parser import AttendanceParser
        from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
        from app.matching.activity_matcher import ActivityMatcher
        from app.matching.identity_resolver import IdentityResolver
        from app.validation.validator import DataValidator
        from app.routing.reporter import RoutingReporter

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

        # EJECUCIÓN DE FASE 6 (ROUTING)
        resultado_routing = ParticipantRouter.enrutar(
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones=validaciones_totales,
        )

        # Comprobaciones formales:
        assert resultado_routing.total_entrada == 18
        assert resultado_routing.total_clasificadas == 18
        assert resultado_routing.invariante_valida is True

        # Distribución a matrices
        assert len(resultado_routing.estudiantes) == 17
        assert len(resultado_routing.academicos_administrativos) == 1
        assert len(resultado_routing.beneficiados) == 0
        assert len(resultado_routing.colaboradores) == 0
        assert len(resultado_routing.cola_revision) == 0
        assert len(resultado_routing.bloqueados) == 0

        # Elba Wilson Smith: conservación de NO_DOCENTE y subtipo ADMINISTRATIVO
        reg_elba = resultado_routing.academicos_administrativos[0]
        assert reg_elba.persona.nombre_completo == "Elba Wilson Smith"
        assert reg_elba.participacion.categoria_participacion == CategoriaParticipacion.NO_DOCENTE
        assert reg_elba.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
        assert reg_elba.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO
        assert reg_elba.estado_operativo == "EN_REVISION"

        # Estados operativos totales: 7 APTO + 11 EN_REVISION
        total_aptos = sum(
            1
            for lista in [
                resultado_routing.estudiantes,
                resultado_routing.academicos_administrativos,
            ]
            for r in lista
            if r.estado_operativo == "APTO"
        )
        total_revision = sum(
            1
            for lista in [
                resultado_routing.estudiantes,
                resultado_routing.academicos_administrativos,
            ]
            for r in lista
            if r.estado_operativo == "EN_REVISION"
        )
        assert total_aptos == 7
        assert total_revision == 11
        assert total_aptos + total_revision == 18

        # Verificar formateo de reporter
        texto_consola = RoutingReporter.formatear_consola(resultado_routing)
        assert "REPORTE OFICIAL DE ENRUTAMIENTO INSTITUCIONAL (FASE 6)" in texto_consola
        assert "18" in texto_consola
        assert "Estudiantes:                   17 registros" in texto_consola
        assert "Académicos y Administrativos:  1 registros" in texto_consola
        assert "[CUMPLIDA: 100% CONSERVADO]" in texto_consola
