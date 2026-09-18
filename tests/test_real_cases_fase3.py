"""
tests/test_real_cases_fase3.py

Prueba integral del caso real de Septiembre 2026 para Innovación y Emprendimiento.
Evalúa:
- 1 actividad institucional reportada en Word y en Asistencia física.
- Unificación por coincidencia de evidencia múltiple con conservación de nombres.
- 18 participantes reales divididos en:
  * Hoja 1: 7 participantes.
  * Hoja 2: 11 participantes.
- Corrección 1: 18 participaciones y 18 objetos Person conservados de forma independiente (sin deduplicación).
- Detección y registro de anomalías reales:
  * Fecha escrita en campo cédula ('20-04-2008').
  * Cédulas vacías.
  * Carreras abreviadas y ambiguas ('Lic Contabil.', 'Lic. Conta', 'Ing. sistc.', 'Sistema', 'A. estudiantil').
  * Categoría 'No Docente' con área 'ACCES'.
  * Mapeo de sexo dependiente de fuente ('asistencia_fisica').
"""

import pytest
from app.parsers.word_parser import WordReportParser
from app.parsers.attendance_parser import AttendanceParser
from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
from app.matching.activity_matcher import ActivityMatcher
from app.core.constants.participant_types import CategoriaParticipacion, NivelValidacion, NivelConfianzaIdentidad


class TestCasoRealSeptiembre2026:
    """Suite de validación integral sobre los datos reales de Septiembre 2026."""

    @pytest.fixture
    def datos_word_reales(self):
        """Metadatos reales del informe Word de septiembre 2026."""
        return {
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

    @pytest.fixture
    def datos_asistencia_18_filas(self):
        """
        Las 18 filas reales registradas en las dos hojas de asistencia física escaneadas.
        Hoja 1: 7 participantes.
        Hoja 2: 11 participantes.
        Total: 18 participaciones.
        """
        filas = [
            # --- HOJA 1: 7 participantes ---
            RawParticipantRow(
                numero_fila=1,
                hoja=1,
                nombre_completo="Johnny Melvin",
                sexo="M",
                cedula="601-120502-1001A",
                edad=24,
                carrera="Lic. Conta",  # Abreviada
                categoria="Estudiante",
                area=None
            ),
            RawParticipantRow(
                numero_fila=2,
                hoja=1,
                nombre_completo="Shana Ruiz Watson",
                sexo="F",
                cedula="20-04-2008",  # ANOMALÍA: fecha escrita accidentalmente en campo cédula
                edad=22,
                carrera="Contabilidad",
                categoria="Estudiante",
                area=None
            ),
            RawParticipantRow(
                numero_fila=3,
                hoja=1,
                nombre_completo="Claudia J Fernandez",
                sexo="F",
                cedula="607-221205-1002W",
                edad=18,
                carrera="contabilidad",
                categoria="Estudiante",
                area=None
            ),
            RawParticipantRow(
                numero_fila=4,
                hoja=1,
                nombre_completo="Besi Wrealy N Taylor",
                sexo="F",
                cedula="612-311004-1000B",  # Cédula válida registrada
                edad=21,
                carrera="Lic Contabil.",  # Abreviada
                categoria="Estudiante",
                area=None
            ),
            RawParticipantRow(
                numero_fila=5,
                hoja=1,
                nombre_completo="Yeison Johnston R.M.",
                sexo="M",
                cedula="601-140703-1003C",
                edad=23,
                carrera="Ing. sistc.",  # Abreviada
                categoria="Estudiante",
                area=None
            ),
            RawParticipantRow(
                numero_fila=6,
                hoja=1,
                nombre_completo="Neidy Rivera G",
                sexo="F",
                cedula="601-090905-1004D",
                edad=21,
                carrera="Sistema",  # Abreviada / ambigua
                categoria="Estudiante",
                area=None
            ),
            RawParticipantRow(
                numero_fila=7,
                hoja=1,
                nombre_completo="Elba Wilson Smith",
                sexo="F",
                cedula="601-300101-1005E",
                edad=25,
                carrera="A. estudiantil",  # AMBIGUA: no docente o área
                categoria="No Docente",  # CATEGORÍA COMPUESTA
                area="ACCES"
            ),

            # --- HOJA 2: 11 participantes ---
            RawParticipantRow(
                numero_fila=8,
                hoja=2,
                nombre_completo="Keyra Rolack G",
                sexo="F",
                cedula="601-180304-1006F",
                edad=22,
                carrera="Contabilidad",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=9,
                hoja=2,
                nombre_completo="Luz Marina Alan A",
                sexo="F",
                cedula="23/06/2008",  # ANOMALÍA: fecha escrita accidentalmente en campo cédula
                edad=23,
                carrera="Contabilidad",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=10,
                hoja=2,
                nombre_completo="Mari Esther Zeniga",
                sexo="F",
                cedula="601-050604-1008H",
                edad=22,
                carrera="Contabilidad",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=11,
                hoja=2,
                nombre_completo="Jessenia Gomez Rivera",
                sexo="F",
                cedula="601-150205-1009I",
                edad=21,
                carrera="Contabilidad",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=12,
                hoja=2,
                nombre_completo="Esther Gabriela Pedro",
                sexo="F",
                cedula="601-111004-1010J",
                edad=22,
                carrera="Contabilidad",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=13,
                hoja=2,
                nombre_completo="Nelba Jhanida Pablo Zamora",
                sexo="F",
                cedula="601-040403-1011K",
                edad=23,
                carrera="Contabilidad",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=14,
                hoja=2,
                nombre_completo="Estrella Reymundo Peñer",
                sexo="F",
                cedula="601-290704-1012L",
                edad=22,
                carrera="Contabilidad",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=15,
                hoja=2,
                nombre_completo="Marcos Michell Hernandez",
                sexo="M",
                cedula="601-170802-1013M",
                edad=24,
                carrera="Ing. sistc.",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=16,
                hoja=2,
                nombre_completo="Jhondy Jimmy Arragón",
                sexo="M",
                cedula="601-020903-1014N",
                edad=23,
                carrera="Ing. sistc.",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=17,
                hoja=2,
                nombre_completo="Dadam Ossiel Mendoza",
                sexo="M",
                cedula=None,  # ANOMALÍA: cédula vacía
                edad=24,
                carrera="Ing. sistc.",
                categoria="Estudiante"
            ),
            RawParticipantRow(
                numero_fila=18,
                hoja=2,
                nombre_completo="Joyner Henr Ruiz Watson",
                sexo="M",
                cedula="601-070104-1016P",
                edad=22,
                carrera="Ing. sistc.",
                categoria="Estudiante"
            ),
        ]

        return RawAttendanceSheetData(
            nombre_actividad="Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial",
            fecha="08/09/2026",
            horario="10:00 AM – 12:00 PM",
            sede="Bilwi",
            departamento="RACCN",
            municipio="Puerto Cabezas",
            filas=filas,
            fuente_origen="asistencia_fisica"
        )

    def test_flujo_completo_septiembre_2026(self, datos_word_reales, datos_asistencia_18_filas):
        # 1. Parsing del informe Word
        actividad_word = WordReportParser.parse_from_dict(datos_word_reales, fuente="informe_word")
        assert actividad_word.id_actividad is not None
        assert "logotipos e inteligencia artificial" in actividad_word.nombre_actividad_original

        # 2. Matching de actividad con evidencia múltiple (Corrección 2)
        match_result = ActivityMatcher.evaluar_coincidencia(
            actividad_word=actividad_word,
            datos_asistencia={
                "nombre_actividad_asistencia": datos_asistencia_18_filas.nombre_actividad,
                "fecha_evento": datos_asistencia_18_filas.fecha,
                "sede": datos_asistencia_18_filas.sede,
                "departamento": datos_asistencia_18_filas.departamento,
                "municipio_evento": datos_asistencia_18_filas.municipio,
                "horario": datos_asistencia_18_filas.horario,
                "fuente_origen": datos_asistencia_18_filas.fuente_origen
            }
        )

        assert match_result.coinciden is True
        assert match_result.nivel_confianza == "ALTA"
        actividad_unificada = match_result.actividad_unificada
        assert actividad_unificada.id_actividad == actividad_word.id_actividad

        # 3. Parsing de las 18 asistencias (Corrección 1: sin deduplicación)
        resultado_asistencia = AttendanceParser.parse_sheet_data(
            sheet_data=datos_asistencia_18_filas,
            id_actividad=actividad_unificada.id_actividad,
            fuente="asistencia_fisica"
        )

        # Regla 10: Total 18 participaciones registradas vinculadas a la misma actividad
        assert len(resultado_asistencia.participaciones) == 18
        assert len(resultado_asistencia.personas) == 18
        assert all(p.id_actividad == actividad_unificada.id_actividad for p in resultado_asistencia.participaciones)

        # Corrección 1: Cada persona tiene su propio ID interno independiente (no se deduplica)
        ids_personas = [p.id_persona_interno for p in resultado_asistencia.personas]
        assert len(set(ids_personas)) == 18

        # 4. Verificar caso anómalo: Shana Ruiz Watson con fecha en cédula (20-04-2008)
        shana_person = next(p for p in resultado_asistencia.personas if "Shana" in p.nombre_completo)
        assert shana_person.cedula is None  # Normalizada es None
        assert shana_person.fecha_nacimiento is None  # No se traslada a fecha de nacimiento
        shana_part = next(p for p in resultado_asistencia.participaciones if p.id_persona == shana_person.id_persona_interno)
        assert shana_part.requiere_revision is True
        assert shana_part.nivel_confianza_identidad == NivelConfianzaIdentidad.NIVEL_4_CANDIDATO.value

        val_shana = next(v for v in resultado_asistencia.validaciones if v.codigo == "VAL_CEDULA_FECHA" and "20-04-2008" in v.mensaje)
        assert val_shana is not None

        # 5. Verificar caso anómalo: Luz Marina Alan A con fecha en cédula (23/06/2008)
        luz_person = next(p for p in resultado_asistencia.personas if "Luz Marina" in p.nombre_completo)
        assert luz_person.cedula is None  # Normalizada es None
        assert luz_person.fecha_nacimiento is None  # No se traslada a fecha de nacimiento
        luz_part = next(p for p in resultado_asistencia.participaciones if p.id_persona == luz_person.id_persona_interno)
        assert luz_part.requiere_revision is True
        assert luz_part.nivel_confianza_identidad == NivelConfianzaIdentidad.NIVEL_4_CANDIDATO.value

        val_luz = next(v for v in resultado_asistencia.validaciones if v.codigo == "VAL_CEDULA_FECHA" and "23/06/2008" in v.mensaje)
        assert val_luz is not None

        # 6. Verificar caso anómalo: Dadam Ossiel Mendoza con cédula vacía
        dadam_person = next(p for p in resultado_asistencia.personas if "Dadam" in p.nombre_completo)
        assert dadam_person.cedula is None
        dadam_part = next(p for p in resultado_asistencia.participaciones if p.id_persona == dadam_person.id_persona_interno)
        assert dadam_part.requiere_revision is True
        assert dadam_part.nivel_confianza_identidad == NivelConfianzaIdentidad.NIVEL_4_CANDIDATO.value

        val_dadam = next(v for v in resultado_asistencia.validaciones if v.codigo == "VAL_CEDULA_VACIA")
        assert val_dadam is not None

        # 7. Verificar que Besi Wrealy N Taylor conserva su cédula válida (612-311004-1000B)
        besi_person = next(p for p in resultado_asistencia.personas if "Besi" in p.nombre_completo)
        assert besi_person.cedula == "612-311004-1000B"
        besi_part = next(p for p in resultado_asistencia.participaciones if p.id_persona == besi_person.id_persona_interno)
        assert besi_part.nivel_confianza_identidad == NivelConfianzaIdentidad.NIVEL_1_CEDULA.value

        # 6. Verificar caso anómalo: Elba Wilson Smith con categoría 'No Docente' y área 'ACCES'
        elba_person = next(p for p in resultado_asistencia.personas if "Elba" in p.nombre_completo)
        elba_part = next(p for p in resultado_asistencia.participaciones if p.id_persona == elba_person.id_persona_interno)
        assert elba_part.categoria_participacion == CategoriaParticipacion.NO_DOCENTE
        assert "ACCES" in elba_part.observaciones
        assert elba_person.carrera_original == "A. estudiantil"
        assert elba_person.carrera_normalizada == "A. Estudiantil"
        assert elba_person.carrera_oficial is None  # Sin catálogo confirmado

        val_ambigua = next(v for v in resultado_asistencia.validaciones if v.codigo == "VAL_CARRERA_AMBIGUA")
        assert "A. estudiantil" in val_ambigua.mensaje

        # 7. Verificar interpretación de sexo en asistencia física:
        # Johnny Melvin (M en asistencia) -> MASCULINO
        johnny_person = next(p for p in resultado_asistencia.personas if "Johnny" in p.nombre_completo)
        assert johnny_person.sexo_original == "M"
        assert johnny_person.sexo_normalizado == "MASCULINO"

        # Shana Ruiz Watson (F en asistencia) -> FEMENINO
        shana_person = next(p for p in resultado_asistencia.personas if "Shana" in p.nombre_completo)
        assert shana_person.sexo_original == "F"
        assert shana_person.sexo_normalizado == "FEMENINO"

        # 8. Verificar carreras abreviadas
        val_abreviadas = [v for v in resultado_asistencia.validaciones if v.codigo == "VAL_CARRERA_ABREVIADA"]
        assert len(val_abreviadas) > 0  # Lic. Conta, Lic Contabil., Ing. sistc.
