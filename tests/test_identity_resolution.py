"""
tests/test_identity_resolution.py

Pruebas exhaustivas para la Fase 4: Resolución de Identidad y Deduplicación Controlada.

Verifica:
1. Invariante Absoluta (Regla de Oro):
   len(participaciones_salida) == len(participaciones_entrada)
   Cada participación conserva id_actividad, categoria_participacion, observaciones y demás atributos,
   actualizando únicamente de forma legítima id_persona en caso de fusión.
2. Nivel 1 — Cédula oficial válida:
   - Misma cédula válida -> Fusión automática segura.
   - Cédulas válidas diferentes -> Personas distintas (incluso con nombres idénticos).
   - Casos que NO son cédula (fechas '20-04-2008', '23/06/2008', cédula vacía) no identifican.
3. Nivel 2 — Número único institucional:
   - Mismo número único -> Fusión automática segura.
   - Números únicos diferentes -> Personas distintas.
4. Nivel 3 — Otro identificador institucional:
   - NO autoriza fusión automática.
   - Conserva personas separadas, genera MATCH_NIVEL3_REVISION y marca revisión humana.
5. Nivel 4 — Candidato a duplicado (Evidencia secundaria):
   - Ejemplo Johnny Melvin vs Johnny M: detecta candidato, emite MATCH_PERSONA_CANDIDATO,
     mantiene personas independientes y marca revisión humana.
6. Enriquecimiento de atributos y detección de conflictos:
   - No sobreescribe silenciosamente.
   - Ante contradicciones (sexos o edades distintas), emite DEDUP_CONFLICTO_DATOS.
   - Trazabilidad completa en FusionRecord.
7. Caso real de Septiembre 2026:
   - 18 Person y 18 Participation de entrada -> 18 Person y 18 Participation de salida (0 fusiones).
8. Prueba de fusión controlada (19.ª participación):
   - 19 Person y 19 Participation de entrada (Johnny Melvin en 2.ª actividad) -> 18 Person y 19 Participation de salida.
   - Ambas participaciones de Johnny existen de forma independiente.
"""

import pytest
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.constants.participant_types import CategoriaParticipacion, NivelValidacion, NivelConfianzaIdentidad
from app.matching.person_matcher import PersonMatcher, TipoCoincidenciaPersona
from app.matching.identity_resolver import IdentityResolver
from app.parsers.word_parser import WordReportParser
from app.parsers.attendance_parser import AttendanceParser
from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow


class TestInvarianteAbsolutaParticipaciones:
    """Verifica la Regla de Oro: len(participaciones_salida) == len(participaciones_entrada) y conservación de atributos."""

    def test_participaciones_se_conservan_identicas_sin_fusiones(self):
        p1 = Person(nombre_completo="Ana López", cedula="601-010100-1001A")
        p2 = Person(nombre_completo="Carlos Ruiz", cedula="601-020200-1002B")
        part1 = Participation(
            id_actividad="act-1",
            id_persona=p1.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            observaciones="Nota 1",
            fuente_origen="lista_1"
        )
        part2 = Participation(
            id_actividad="act-2",
            id_persona=p2.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
            observaciones="Nota 2",
            fuente_origen="lista_2"
        )

        resultado = IdentityResolver.resolver_identidades([p1, p2], [part1, part2])

        # Invariante de conteo
        assert len(resultado.participaciones) == 2
        assert len(resultado.personas) == 2

        # Invariante de atributos
        salida1 = next(p for p in resultado.participaciones if p.id_participacion == part1.id_participacion)
        salida2 = next(p for p in resultado.participaciones if p.id_participacion == part2.id_participacion)

        assert salida1.id_actividad == "act-1"
        assert salida1.categoria_participacion == CategoriaParticipacion.ESTUDIANTE
        assert salida1.observaciones == "Nota 1"
        assert salida1.fuente_origen == "lista_1"
        assert salida1.id_persona == p1.id_persona_interno

        assert salida2.id_actividad == "act-2"
        assert salida2.categoria_participacion == CategoriaParticipacion.DOCENTE
        assert salida2.observaciones == "Nota 2"
        assert salida2.fuente_origen == "lista_2"
        assert salida2.id_persona == p2.id_persona_interno

    def test_participaciones_se_conservan_al_fusionar_personas(self):
        """
        Dos participaciones de la misma persona física (misma cédula) en distintas actividades.
        Deben conservarse ambas participaciones, con id_persona actualizado al canónico.
        """
        p_a = Person(nombre_completo="Johnny Melvin", cedula="601-120502-1001A", carrera_original="Contabilidad")
        p_b = Person(nombre_completo="Johnny Melvin", cedula="601-120502-1001A", carrera_original="Contabilidad")

        part_act1 = Participation(
            id_actividad="act-taller-ia",
            id_persona=p_a.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            observaciones="Participante en taller IA",
            fuente_origen="asistencia_taller"
        )
        part_act2 = Participation(
            id_actividad="act-feria-innovacion",
            id_persona=p_b.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.BENEFICIADO,
            observaciones="Beneficiado en feria de innovación",
            fuente_origen="asistencia_feria"
        )

        participaciones_entrada = [part_act1, part_act2]
        personas_entrada = [p_a, p_b]

        resultado = IdentityResolver.resolver_identidades(personas_entrada, participaciones_entrada)

        # Regla de oro: 2 participaciones entran, 2 salen
        assert len(resultado.participaciones) == len(participaciones_entrada) == 2
        # Fusión válida: 2 personas entran, 1 persona sale
        assert len(resultado.personas) == 1
        persona_unificada = resultado.personas[0]

        # Comprobar que ambas participaciones siguen existiendo de forma independiente
        p1_salida = next(p for p in resultado.participaciones if p.id_participacion == part_act1.id_participacion)
        p2_salida = next(p for p in resultado.participaciones if p.id_participacion == part_act2.id_participacion)

        # Ambas apuntan a la persona unificada legítima
        assert p1_salida.id_persona == persona_unificada.id_persona_interno
        assert p2_salida.id_persona == persona_unificada.id_persona_interno

        # Sus atributos propios de actividad, categoría y observaciones están INTACTOS
        assert p1_salida.id_actividad == "act-taller-ia"
        assert p1_salida.categoria_participacion == CategoriaParticipacion.ESTUDIANTE
        assert p1_salida.observaciones == "Participante en taller IA"
        assert p1_salida.fuente_origen == "asistencia_taller"

        assert p2_salida.id_actividad == "act-feria-innovacion"
        assert p2_salida.categoria_participacion == CategoriaParticipacion.BENEFICIADO
        assert p2_salida.observaciones == "Beneficiado en feria de innovación"
        assert p2_salida.fuente_origen == "asistencia_feria"


class TestNivel1CedulaOficial:
    """Pruebas del Nivel 1: Cédula oficial válida."""

    def test_misma_cedula_valida_produce_fusion_automatica(self):
        p1 = Person(nombre_completo="Besi Wrealy N Taylor", cedula="612-311004-1000B")
        p2 = Person(nombre_completo="Besi Wrealy N Taylor", cedula="612-311004-1000B")

        res = PersonMatcher.comparar_personas(p1, p2)
        assert res.tipo_coincidencia == TipoCoincidenciaPersona.FUSION_AUTOMATICA
        assert res.nivel_jerarquia == 1
        assert "Misma cédula" in res.evidencias[0]

    def test_cedulas_validas_diferentes_son_personas_distintas_incluso_mismo_nombre(self):
        """
        Dos registros con exactamente el mismo nombre pero cédulas válidas distintas
        DEBEN considerarse personas distintas.
        """
        p1 = Person(nombre_completo="Juan Pérez López", cedula="601-100100-1001A")
        p2 = Person(nombre_completo="Juan Pérez López", cedula="601-200200-2002B")

        res = PersonMatcher.comparar_personas(p1, p2)
        assert res.tipo_coincidencia == TipoCoincidenciaPersona.DISTINTAS
        assert res.nivel_jerarquia == 1
        assert "Cédulas oficiales válidas diferentes" in res.evidencias[0]

    def test_fecha_en_campo_cedula_no_es_cedula_valida_y_no_identifica(self):
        """
        Fechas como '20-04-2008' o '23/06/2008' NO son cédulas válidas y no deben permitir fusión.
        """
        assert PersonMatcher.es_cedula_valida("20-04-2008") is False
        assert PersonMatcher.es_cedula_valida("23/06/2008") is False
        assert PersonMatcher.es_cedula_valida(None) is False
        assert PersonMatcher.es_cedula_valida("") is False
        assert PersonMatcher.es_cedula_valida("601-120502-1001A") is True


class TestNivel2NumeroUnico:
    """Pruebas del Nivel 2: Número único institucional."""

    def test_mismo_numero_unico_produce_fusion_automatica(self):
        p1 = Person(nombre_completo="María Elena Sujo", numero_unico="UNI-2024-8891")
        p2 = Person(nombre_completo="María E. Sujo", numero_unico="UNI-2024-8891")

        res = PersonMatcher.comparar_personas(p1, p2)
        assert res.tipo_coincidencia == TipoCoincidenciaPersona.FUSION_AUTOMATICA
        assert res.nivel_jerarquia == 2
        assert "Mismo número único" in res.evidencias[0]

    def test_numeros_unicos_diferentes_son_personas_distintas(self):
        p1 = Person(nombre_completo="María Elena Sujo", numero_unico="UNI-2024-8891")
        p2 = Person(nombre_completo="María Elena Sujo", numero_unico="UNI-2024-9999")

        res = PersonMatcher.comparar_personas(p1, p2)
        assert res.tipo_coincidencia == TipoCoincidenciaPersona.DISTINTAS
        assert res.nivel_jerarquia == 2


class TestNivel3OtroIdInstitucional:
    """Pruebas del Nivel 3: Corrección obligatoria 1."""

    def test_otro_id_institucional_no_autoriza_fusion_automatica_y_emite_revision(self):
        """
        otro_id_institucional NO autoriza por sí mismo una fusión automática.
        Debe conservar las personas separadas, registrar evidencia, emitir MATCH_NIVEL3_REVISION
        y requerir revisión humana.
        """
        p1 = Person(nombre_completo="Docente Invitado A", otro_id_institucional="ID-EXT-770")
        p2 = Person(nombre_completo="Docente Invitado B", otro_id_institucional="ID-EXT-770")

        res = PersonMatcher.comparar_personas(p1, p2)
        assert res.tipo_coincidencia == TipoCoincidenciaPersona.CANDIDATO_REVISION
        assert res.nivel_jerarquia == 3
        codigos = [v.codigo for v in res.validaciones]
        assert "MATCH_NIVEL3_REVISION" in codigos
        assert res.validaciones[0].nivel == NivelValidacion.REVISION

        part1 = Participation(id_actividad="act-1", id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.DOCENTE)
        part2 = Participation(id_actividad="act-2", id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.DOCENTE)

        resultado = IdentityResolver.resolver_identidades([p1, p2], [part1, part2])

        # Se mantienen separadas
        assert len(resultado.personas) == 2
        assert len(resultado.participaciones) == 2
        assert len(resultado.fusiones_realizadas) == 0
        assert len(resultado.candidatos_revision) == 1
        assert resultado.candidatos_revision[0].nivel_jerarquia == 3

        # Participaciones marcadas con requiere_revision
        assert all(p.requiere_revision is True for p in resultado.participaciones)


class TestNivel4CandidatoDuplicado:
    """Pruebas del Nivel 4: Candidato a duplicado basado en evidencia secundaria."""

    def test_caso_johnny_m_vs_johnny_melvin_mantiene_personas_separadas_y_emite_candidato(self):
        """
        Ejemplo del usuario: Johnny M vs Johnny Melvin sin cédula o con evidencia secundaria.
        NUNCA autoriza fusión automática.
        Conserva personas independientes, emite MATCH_PERSONA_CANDIDATO y marca revisión humana.
        """
        p1 = Person(
            nombre_completo="Johnny Melvin",
            carrera_original="Contabilidad",
            carrera_normalizada="Contabilidad",
            edad=24
        )
        p2 = Person(
            nombre_completo="Johnny M",
            carrera_original="Contabilidad",
            carrera_normalizada="Contabilidad",
            edad=24
        )

        res = PersonMatcher.comparar_personas(p1, p2)
        assert res.tipo_coincidencia == TipoCoincidenciaPersona.CANDIDATO_REVISION
        assert res.nivel_jerarquia == 4
        codigos = [v.codigo for v in res.validaciones]
        assert "MATCH_PERSONA_CANDIDATO" in codigos

        part1 = Participation(id_actividad="act-1", id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad="act-2", id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        resultado = IdentityResolver.resolver_identidades([p1, p2], [part1, part2])

        # NO se fusionan
        assert len(resultado.personas) == 2
        assert len(resultado.participaciones) == 2
        assert len(resultado.fusiones_realizadas) == 0
        assert len(resultado.candidatos_revision) == 1

        # Revisión humana requerida
        assert any(p.requiere_revision for p in resultado.participaciones)


class TestEnriquecimientoYConflictos:
    """Pruebas del enriquecimiento de atributos y detección de conflictos (Corrección 2)."""

    def test_enriquecimiento_no_destructivo_cuando_no_hay_conflicto(self):
        """Si una persona tiene un campo vacío y la otra tiene dato, se enriquece sin conflicto."""
        p1 = Person(
            nombre_completo="Claudia Fernandez",
            cedula="607-221205-1002W",
            edad=18,
            telefono=None
        )
        p2 = Person(
            nombre_completo="Claudia J Fernandez",
            cedula="607-221205-1002W",
            edad=None,
            telefono="8888-1234",
            carrera_normalizada="Contabilidad"
        )
        part1 = Participation(id_actividad="act-1", id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad="act-2", id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        resultado = IdentityResolver.resolver_identidades([p1, p2], [part1, part2])

        assert len(resultado.personas) == 1
        assert len(resultado.participaciones) == 2

        fusionada = resultado.personas[0]
        assert fusionada.edad == 18
        assert fusionada.telefono == "8888-1234"
        assert fusionada.carrera_normalizada == "Contabilidad"
        # Trazabilidad completa registrada
        assert len(resultado.fusiones_realizadas) == 1
        record = resultado.fusiones_realizadas[0]
        assert len(record.conflictos_detectados) == 0

    def test_conflicto_de_datos_emite_dedup_conflicto_datos(self):
        """
        Dos registros con la misma cédula válida pero datos biológicos/demográficos contradictorios
        (ej: sexos distintos) deben generar DEDUP_CONFLICTO_DATOS y registrar el conflicto.
        """
        p1 = Person(
            nombre_completo="Alex Martinez",
            cedula="601-010100-9999Z",
            sexo_normalizado="MASCULINO",
            fuente_origen="fuente_a"
        )
        p2 = Person(
            nombre_completo="Alex Martinez",
            cedula="601-010100-9999Z",
            sexo_normalizado="FEMENINO",
            fuente_origen="fuente_b"
        )
        part1 = Participation(id_actividad="act-1", id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad="act-2", id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        resultado = IdentityResolver.resolver_identidades([p1, p2], [part1, part2])

        # Se fusiona por Nivel 1 pero se alerta el conflicto
        assert len(resultado.personas) == 1
        assert len(resultado.participaciones) == 2
        codigos = [v.codigo for v in resultado.validaciones]
        assert "DEDUP_CONFLICTO_DATOS" in codigos

        record = resultado.fusiones_realizadas[0]
        assert len(record.conflictos_detectados) > 0
        assert "Conflicto de sexo" in record.conflictos_detectados[0]


class TestCasoRealSeptiembre2026:
    """Pruebas del caso real de Septiembre 2026 y de la prueba de fusión controlada (Correcciones 3 y 4)."""

    @pytest.fixture
    def datos_reales_18_filas(self):
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
        return RawAttendanceSheetData(
            nombre_actividad="Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial",
            fecha="08/09/2026",
            filas=filas,
            fuente_origen="asistencia_fisica"
        )

    def test_caso_real_septiembre_2026_produce_18_personas_y_18_participaciones(self, datos_reales_18_filas):
        """
        Corrección 3 obligatoria:
        Entrada: 18 Person, 18 Participation.
        Salida: 18 Person, 18 Participation.
        No debe existir ninguna fusión entre los 18 registros reales.
        """
        parsed = AttendanceParser.parse_sheet_data(datos_reales_18_filas, id_actividad="act-sept-2026")
        assert len(parsed.personas) == 18
        assert len(parsed.participaciones) == 18

        resultado = IdentityResolver.resolver_identidades(parsed.personas, parsed.participaciones)

        # Invariante y resultado esperado exacto
        assert len(resultado.personas) == 18
        assert len(resultado.participaciones) == 18
        assert len(resultado.fusiones_realizadas) == 0

        # Shana Ruiz Watson y Luz Marina Alan A tienen cédula None y no fueron fusionadas
        shana = next(p for p in resultado.personas if "Shana" in p.nombre_completo)
        assert shana.cedula is None

        luz = next(p for p in resultado.personas if "Luz Marina" in p.nombre_completo)
        assert luz.cedula is None

        dadam = next(p for p in resultado.personas if "Dadam" in p.nombre_completo)
        assert dadam.cedula is None

        besi = next(p for p in resultado.personas if "Besi" in p.nombre_completo)
        assert besi.cedula == "612-311004-1000B"

    def test_prueba_fusion_controlada_19_participaciones_con_johnny_melvin(self, datos_reales_18_filas):
        """
        Corrección 4 obligatoria:
        Agregar una 19.ª participación artificial correspondiente a Johnny Melvin en otra actividad.
        Entrada:
          19 Person
          19 Participation
        Salida:
          18 Person
          19 Participation
        La reducción de 19 -> 18 debe ocurrir exclusivamente porque la nueva participación
        utiliza una identidad oficial válida que coincide con Johnny Melvin.
        Debe demostrarse que ambas participaciones de Johnny siguen existiendo de forma independiente.
        """
        parsed = AttendanceParser.parse_sheet_data(datos_reales_18_filas, id_actividad="act-sept-2026")
        personas = list(parsed.personas)
        participaciones = list(parsed.participaciones)

        # 19.ª participación artificial: Johnny Melvin en otra actividad con su cédula oficial válida
        p19 = Person(
            nombre_completo="Johnny Melvin",
            cedula="601-120502-1001A",  # Misma cédula válida oficial de Johnny
            sexo_normalizado="MASCULINO",
            carrera_normalizada="Contabilidad",
            edad=24,
            fuente_origen="asistencia_segunda_actividad"
        )
        part19 = Participation(
            id_actividad="act-feria-tecnologica-2026",
            id_persona=p19.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            observaciones="Johnny participó como expositor",
            fuente_origen="asistencia_segunda_actividad"
        )

        personas.append(p19)
        participaciones.append(part19)

        # Validar entrada
        assert len(personas) == 19
        assert len(participaciones) == 19

        resultado = IdentityResolver.resolver_identidades(personas, participaciones)

        # Validar salida estricta
        assert len(resultado.participaciones) == 19
        assert len(resultado.personas) == 18
        assert len(resultado.fusiones_realizadas) == 1

        # La única fusión realizada debe ser Johnny Melvin por Nivel 1
        fusion = resultado.fusiones_realizadas[0]
        assert "601-120502-1001A" in fusion.criterio_fusion
        assert "NIVEL_1_CEDULA" in fusion.criterio_fusion

        johnny_unificado = next(p for p in resultado.personas if p.cedula == "601-120502-1001A")
        assert johnny_unificado.id_persona_interno == fusion.id_persona_canonico

        # Demostrar que ambas participaciones de Johnny existen de forma independiente
        part_johnny_1 = next(p for p in resultado.participaciones if p.id_participacion == participaciones[0].id_participacion)
        part_johnny_2 = next(p for p in resultado.participaciones if p.id_participacion == part19.id_participacion)

        # Son registros independientes con IDs distintos
        assert part_johnny_1.id_participacion != part_johnny_2.id_participacion

        # Pertenecen a actividades diferentes
        assert part_johnny_1.id_actividad == "act-sept-2026"
        assert part_johnny_2.id_actividad == "act-feria-tecnologica-2026"

        # Conservan sus observaciones originales intactas
        assert part_johnny_2.observaciones == "Johnny participó como expositor"

        # Ambas apuntan al ID interno de la misma persona física unificada
        assert part_johnny_1.id_persona == johnny_unificado.id_persona_interno
        assert part_johnny_2.id_persona == johnny_unificado.id_persona_interno
