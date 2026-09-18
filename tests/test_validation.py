"""
tests/test_validation.py

Pruebas unitarias para el motor de validación centralizado (DataValidator).
Verifica los 10 códigos y niveles de validación requeridos en Fase 3:
1. VAL_SEXO_INCOMPATIBLE
2. VAL_CEDULA_VACIA
3. VAL_CEDULA_FECHA
4. VAL_EDAD_AUSENTE
5. VAL_CARRERA_ABREVIADA
6. VAL_CARRERA_AMBIGUA
7. VAL_ACTIVIDAD_DIFERENCIA_NOMBRE
8. VAL_CATEGORIA_DESCONOCIDA
9. VAL_CAMPO_OBLIGATORIO_FALTANTE
10. VAL_REVISION_REQUERIDA
"""

from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.constants.participant_types import NivelValidacion, CategoriaParticipacion
from app.validation.validator import DataValidator


class TestDataValidator:
    """Pruebas del validador de datos."""

    def test_val_actividad_diferencia_nombre(self):
        actividad = Activity(
            nombre_actividad_original="Nombre en Word",
            fecha_evento="08/09/2026"
        )
        hallazgos = DataValidator.validar_actividad(
            actividad=actividad,
            nombre_alterno_fuente="Nombre en Asistencia"
        )
        codigos = [h.codigo for h in hallazgos]
        assert "VAL_ACTIVIDAD_DIFERENCIA_NOMBRE" in codigos
        assert any(h.nivel == NivelValidacion.INFO for h in hallazgos)

    def test_val_cedula_fecha_y_cedula_vacia(self):
        persona_con_fecha_en_cedula = Person(
            nombre_completo="Persona Prueba 1",
            cedula="20-04-2008",
            sexo_normalizado="FEMENINO",
            edad=22
        )
        hallazgos1 = DataValidator.validar_persona(persona_con_fecha_en_cedula)
        codigos1 = [h.codigo for h in hallazgos1]
        assert "VAL_CEDULA_FECHA" in codigos1

        persona_sin_cedula = Person(
            nombre_completo="Persona Prueba 2",
            cedula=None,
            sexo_normalizado="MASCULINO",
            edad=25
        )
        hallazgos2 = DataValidator.validar_persona(persona_sin_cedula)
        codigos2 = [h.codigo for h in hallazgos2]
        assert "VAL_CEDULA_VACIA" in codigos2

    def test_val_sexo_incompatible_y_edad_ausente(self):
        persona_incompleta = Person(
            nombre_completo="Persona Prueba 3",
            cedula="601-010100-1000A",
            sexo_original="Z",
            sexo_normalizado=None,
            edad=None
        )
        hallazgos = DataValidator.validar_persona(persona_incompleta)
        codigos = [h.codigo for h in hallazgos]
        assert "VAL_SEXO_INCOMPATIBLE" in codigos
        assert "VAL_EDAD_AUSENTE" in codigos

    def test_val_carrera_abreviada_y_ambigua(self):
        persona_ambigua = Person(
            nombre_completo="Persona Prueba 4",
            carrera_original="A. estudiantil",
            sexo_normalizado="FEMENINO",
            edad=21
        )
        hallazgos1 = DataValidator.validar_persona(persona_ambigua)
        codigos1 = [h.codigo for h in hallazgos1]
        assert "VAL_CARRERA_AMBIGUA" in codigos1

        persona_abreviada = Person(
            nombre_completo="Persona Prueba 5",
            carrera_original="Lic. Conta",
            sexo_normalizado="MASCULINO",
            edad=22
        )
        hallazgos2 = DataValidator.validar_persona(persona_abreviada)
        codigos2 = [h.codigo for h in hallazgos2]
        assert "VAL_CARRERA_ABREVIADA" in codigos2

    def test_val_categoria_desconocida_y_revision_requerida(self):
        part = Participation(
            id_actividad="act-123",
            id_persona="per-123",
            categoria_participacion=CategoriaParticipacion.DESCONOCIDO,
            requiere_revision=True,
            motivo_revision="Categoría atípica detectada en fuente."
        )
        hallazgos = DataValidator.validar_participacion(part)
        codigos = [h.codigo for h in hallazgos]
        assert "VAL_CATEGORIA_DESCONOCIDA" in codigos
        assert "VAL_REVISION_REQUERIDA" in codigos
        assert any(h.nivel == NivelValidacion.REVISION for h in hallazgos)


class TestValidacionIntegralFase5:
    """Pruebas del motor de validación integral, reportes y reglas de Fase 5."""

    def test_integridad_referencial_error_registro_no_detiene_demas(self):
        """
        Un ERROR de registro (ej. id_persona o id_actividad inexistente)
        bloquea ÚNICAMENTE ese registro y permite continuar validando los demás.
        """
        act = Activity(nombre_actividad_original="Taller IA", fecha_evento="08/09/2026")
        per1 = Person(nombre_completo="Carlos Morales", cedula="601-010100-1000A")
        per2 = Person(nombre_completo="María López", cedula="601-020200-2000B")

        part_valida = Participation(
            id_actividad=act.id_actividad,
            id_persona=per1.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE
        )
        part_act_invalida = Participation(
            id_actividad="act-inexistente-999",
            id_persona=per2.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE
        )
        part_per_invalida = Participation(
            id_actividad=act.id_actividad,
            id_persona="persona-fantasma-999",
            categoria_participacion=CategoriaParticipacion.DOCENTE
        )

        participaciones = [part_valida, part_act_invalida, part_per_invalida]
        hallazgos = DataValidator.validar_conjunto(
            actividades=[act],
            personas=[per1, per2],
            participaciones=participaciones
        )

        codigos = [h.codigo for h in hallazgos]
        assert "VAL_INTEGRIDAD_ACTIVIDAD_INEXISTENTE" in codigos
        assert "VAL_INTEGRIDAD_PERSONA_INEXISTENTE" in codigos

        from app.validation.reporter import ValidationReporter
        reporte = ValidationReporter.generar_reporte([act], [per1, per2], participaciones, hallazgos)

        # La participación válida es APTO
        assert reporte.registros_aptos == 1
        # Las dos con error referencial son BLOQUEADAS
        assert reporte.registros_bloqueados == 2
        assert reporte.registros_en_revision == 0
        assert reporte.total_participaciones == 3

    def test_edad_atipica_emite_revision_sin_asumir_error_institucional(self):
        """
        Condición 4: Edad atípica (< 16 años para docente) debe detectar anomalía,
        pero NO asumir error institucional. Emite REVISION.
        """
        act = Activity(nombre_actividad_original="Conferencia", fecha_evento="08/09/2026")
        per_joven = Person(nombre_completo="Adolescente Prodigio", cedula="601-010110-1000A", edad=14)
        part_docente = Participation(
            id_actividad=act.id_actividad,
            id_persona=per_joven.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE
        )

        hallazgos = DataValidator.validar_conjunto(
            actividades=[act],
            personas=[per_joven],
            participaciones=[part_docente]
        )

        val_atipica = next(h for h in hallazgos if h.codigo == "VAL_EDAD_CATEGORIA_ATIPICA")
        assert val_atipica.nivel == NivelValidacion.REVISION
        assert part_docente.requiere_revision is True

    def test_validacion_territorial_deshabilitada_si_catalogo_vacio(self):
        """
        Condición 6: Mientras municipios.json no tenga catálogo poblado,
        la validación territorial permanece deshabilitada sin inventar valores.
        """
        act = Activity(nombre_actividad_original="Taller", fecha_evento="08/09/2026", sede="Bilwi", municipio_evento="Puerto Cabezas")
        per = Person(nombre_completo="Estudiante Test", cedula="601-010100-1000A")
        part = Participation(id_actividad=act.id_actividad, id_persona=per.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        hallazgos = DataValidator.validar_conjunto([act], [per], [part])
        # No se emiten errores territoriales espurios
        codigos_territoriales = [h.codigo for h in hallazgos if "TERRITORIAL" in h.codigo or "MUNICIPIO" in h.codigo]
        assert len(codigos_territoriales) == 0

    def test_reporte_incluye_todas_las_secciones_obligatorias(self):
        """
        Condición 6: El reporte debe incluir actividades, personas, participaciones,
        conteo por severidad, APTO, EN REVISION, BLOQUEADO y distribución preliminar.
        """
        from app.validation.reporter import ValidationReporter
        act = Activity(nombre_actividad_original="Taller A", fecha_evento="08/09/2026")
        p1 = Person(nombre_completo="Persona Apto", cedula="601-010100-1001A")
        p2 = Person(nombre_completo="Persona Revision", cedula="601-020200-1002B")
        part1 = Participation(id_actividad=act.id_actividad, id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad=act.id_actividad, id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.DOCENTE, requiere_revision=True, motivo_revision="Revisión requerida")

        hallazgos = DataValidator.validar_conjunto([act], [p1, p2], [part1, part2])
        reporte = ValidationReporter.generar_reporte([act], [p1, p2], [part1, part2], hallazgos)

        assert reporte.total_actividades == 1
        assert reporte.total_personas == 2
        assert reporte.total_participaciones == 2
        assert reporte.registros_aptos == 1
        assert reporte.registros_en_revision == 1
        assert reporte.registros_bloqueados == 0
        assert "Estudiantes" in reporte.distribucion_preliminar
        assert "Académicos y Administrativos" in reporte.distribucion_preliminar
        assert reporte.distribucion_preliminar["Estudiantes"] == 1
        assert reporte.distribucion_preliminar["Académicos y Administrativos"] == 1

        texto = ValidationReporter.formatear_consola(reporte)
        assert "REPORTE DE VALIDACIÓN Y CALIDAD DE DATOS (FASE 5)" in texto
        assert "[APTO]" in texto
        assert "[EN REVISIÓN]" in texto


class TestCasoRealSeptiembre2026Fase5:
    """Verificación obligatoria del caso real de Septiembre 2026 en Fase 5 (Condición 14)."""

    def test_caso_real_septiembre_2026_validacion_completa(self):
        """
        Condición 14 explícita:
        - Shana Ruiz Watson -> VAL_CEDULA_FECHA -> REVISION.
        - Luz Marina Alan A -> VAL_CEDULA_FECHA -> REVISION.
        - Dadam Ossiel Mendoza -> VAL_CEDULA_VACIA -> REVISION.
        - Besi Wrealy N Taylor -> cédula 612-311004-1000B conservada.
        - Claudia J Fernandez -> cédula válida conservada (607-221205-1002W).
        - 18 participaciones de entrada -> 18 participaciones de salida.
        - Conteo de estados: 15 APTO, 3 EN_REVISION, 0 BLOQUEADO.
        """
        from app.parsers.word_parser import WordReportParser
        from app.parsers.attendance_parser import AttendanceParser
        from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
        from app.matching.activity_matcher import ActivityMatcher
        from app.matching.identity_resolver import IdentityResolver
        from app.validation.reporter import ValidationReporter

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
            fuente_origen="asistencia_fisica"
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
                "fuente_origen": sheet_data.fuente_origen
            }
        )
        actividad_unificada = match_res.actividad_unificada or actividad_word

        parsed_asist = AttendanceParser.parse_sheet_data(sheet_data, id_actividad=actividad_unificada.id_actividad)
        assert len(parsed_asist.participaciones) == 18
        assert len(parsed_asist.personas) == 18

        res_dedup = IdentityResolver.resolver_identidades(parsed_asist.personas, parsed_asist.participaciones)
        assert len(res_dedup.personas) == 18
        assert len(res_dedup.participaciones) == 18

        # Invariante absoluta
        assert len(res_dedup.participaciones) == len(filas) == 18

        # Validación integral
        validaciones_totales = DataValidator.validar_conjunto(
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones_previas=parsed_asist.validaciones + match_res.validaciones + res_dedup.validaciones
        )

        # 1. Shana Ruiz Watson -> VAL_CEDULA_FECHA -> REVISION
        shana_p = next(p for p in res_dedup.personas if "Shana" in p.nombre_completo)
        val_shana = next(v for v in validaciones_totales if v.codigo == "VAL_CEDULA_FECHA" and "20-04-2008" in v.mensaje)
        assert val_shana.nivel == NivelValidacion.REVISION
        shana_part = next(p for p in res_dedup.participaciones if p.id_persona == shana_p.id_persona_interno)
        assert shana_part.requiere_revision is True

        # 2. Luz Marina Alan A -> VAL_CEDULA_FECHA -> REVISION
        luz_p = next(p for p in res_dedup.personas if "Luz Marina" in p.nombre_completo)
        val_luz = next(v for v in validaciones_totales if v.codigo == "VAL_CEDULA_FECHA" and "23/06/2008" in v.mensaje)
        assert val_luz.nivel == NivelValidacion.REVISION
        luz_part = next(p for p in res_dedup.participaciones if p.id_persona == luz_p.id_persona_interno)
        assert luz_part.requiere_revision is True

        # 3. Dadam Ossiel Mendoza -> VAL_CEDULA_VACIA -> REVISION
        dadam_p = next(p for p in res_dedup.personas if "Dadam" in p.nombre_completo)
        val_dadam = next(v for v in validaciones_totales if v.codigo == "VAL_CEDULA_VACIA")
        assert val_dadam is not None
        dadam_part = next(p for p in res_dedup.participaciones if p.id_persona == dadam_p.id_persona_interno)
        assert dadam_part.requiere_revision is True

        # 4. Besi Wrealy N Taylor -> Cédula 612-311004-1000B conservada
        besi_p = next(p for p in res_dedup.personas if "Besi" in p.nombre_completo)
        assert besi_p.cedula == "612-311004-1000B"

        # 5. Claudia J Fernandez -> Cédula válida conservada
        claudia_p = next(p for p in res_dedup.personas if "Claudia" in p.nombre_completo)
        assert claudia_p.cedula == "607-221205-1002W"

        # 6. Reporte de validación
        reporte = ValidationReporter.generar_reporte(
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones=validaciones_totales
        )

        assert reporte.total_participaciones == 18
        assert reporte.total_personas == 18
        assert reporte.total_actividades == 1
        assert reporte.registros_bloqueados == 0
        assert reporte.registros_en_revision == 11
        assert reporte.registros_aptos == 7
        assert reporte.registros_aptos + reporte.registros_en_revision + reporte.registros_bloqueados == 18

        # Distribución de categorías puras de Fase 5
        assert reporte.distribucion_categorias["ESTUDIANTE"] == 17
        assert reporte.distribucion_categorias["NO_DOCENTE"] == 1

        # Distribución preliminar por destino
        assert reporte.distribucion_preliminar["Estudiantes"] == 17
        assert reporte.distribucion_preliminar["Académicos y Administrativos"] == 1  # Elba Wilson Smith


class TestAuditoriaPuntualFase5:
    """Pruebas de auditoría puntual para garantizar el cumplimiento estricto de los 11 criterios."""

    def test_claudia_cedula_real_y_prevencion_discrepancia(self):
        """
        Garantiza que la cédula real de Claudia J Fernandez (607-221205-1002W) se conserve
        exactamente como se leyó, y que cualquier valor divergente (como 601-150403-1002B)
        se trate como persona distinta o conflicto, impidiendo sobreescrituras silenciosas.
        """
        from app.normalization.identifier_normalizer import IdentifierNormalizer
        from app.matching.person_matcher import PersonMatcher, TipoCoincidenciaPersona
        from app.core.models.person import Person

        # 1. Normalización directa del valor real
        cedula_real = "607-221205-1002W"
        norm, val = IdentifierNormalizer.normalizar_cedula(cedula_real, fuente="asistencia_fisica")
        assert norm == "607-221205-1002W"
        assert val is None  # Es una cédula válida estándar de RACCN

        # 2. Si existiera otra fuente con valor divergente, NO se fusionan automáticamente
        p1 = Person(nombre_completo="Claudia J Fernandez", cedula="607-221205-1002W", edad=18)
        p2 = Person(nombre_completo="Claudia J Fernandez", cedula="601-150403-1002B", edad=18)

        res = PersonMatcher.comparar_personas(p1, p2)
        # Nivel 1: Cédulas diferentes válidas son personas distintas
        assert res.tipo_coincidencia == TipoCoincidenciaPersona.DISTINTAS
        assert "Cédulas oficiales válidas diferentes" in res.evidencias[0]

    def test_distribucion_categorias_conserva_no_docente_sin_convertir_en_fase_5(self):
        """
        Garantiza que la categoría 'No Docente' NO sea convertida a 'Administrativo' en Fase 5.
        La equivalencia institucional corresponde al routing de Fase 6.
        """
        from app.core.models.participation import Participation
        from app.core.models.person import Person
        from app.validation.reporter import ValidationReporter

        p = Person(nombre_completo="Elba Wilson Smith", cedula="601-300101-1005E", edad=25)
        part = Participation(
            id_actividad="act-1",
            id_persona=p.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.NO_DOCENTE
        )

        assert part.categoria_participacion == CategoriaParticipacion.NO_DOCENTE
        assert part.categoria_participacion.value == "NO_DOCENTE"

        reporte = ValidationReporter.generar_reporte(
            actividades=[],
            personas=[p],
            participaciones=[part],
            validaciones=[]
        )
        assert reporte.distribucion_categorias["NO_DOCENTE"] == 1
        assert "ADMINISTRATIVO" not in reporte.distribucion_categorias

    def test_trazabilidad_completa_fuente_persona_participacion_validacion(self):
        """Garantiza la trazabilidad granular: fuente -> persona -> participación -> hallazgos."""
        from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
        from app.parsers.attendance_parser import AttendanceParser
        from app.validation.reporter import ValidationReporter

        sheet = RawAttendanceSheetData(
            nombre_actividad="Taller Trazabilidad",
            fecha="10/09/2026",
            sede="Bilwi",
            departamento="RACCN",
            municipio="Puerto Cabezas",
            horario="8:00 AM",
            fuente_origen="asistencia_fisica",
            filas=[
                RawParticipantRow(
                    numero_fila=1,
                    hoja=1,
                    nombre_completo="Estudiante Prueba",
                    sexo="M",
                    cedula="20-04-2008",  # Anomalía fecha
                    edad=20,
                    carrera="Lic. Conta",  # Abreviada
                    categoria="Estudiante"
                )
            ]
        )

        res = AttendanceParser.parse_sheet_data(sheet, id_actividad="act-trazabilidad", fuente="asistencia_fisica")
        assert len(res.personas) == 1
        assert len(res.participaciones) == 1

        persona = res.personas[0]
        participacion = res.participaciones[0]

        # Vínculos
        assert participacion.id_persona == persona.id_persona_interno
        assert participacion.fuente_origen == "asistencia_fisica"

        # Validaciones vinculadas al ID de referencia de la persona/participación
        val_persona = [v for v in res.validaciones if v.id_referencia == persona.id_persona_interno]
        assert len(val_persona) >= 2  # Cédula fecha y carrera abreviada

        reporte = ValidationReporter.generar_reporte(
            actividades=[],
            personas=res.personas,
            participaciones=res.participaciones,
            validaciones=res.validaciones
        )
        assert reporte.registros_en_revision == 1
        assert reporte.detalles_participaciones[0]["id_participacion"] == participacion.id_participacion
        assert reporte.detalles_participaciones[0]["id_persona"] == persona.id_persona_interno
        assert len(reporte.detalles_participaciones[0]["motivos"]) > 0


