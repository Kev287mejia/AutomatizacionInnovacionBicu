"""
tests/test_parsers.py

Pruebas unitarias para los parsers de fuentes reales:
- WordReportParser: extracción de informe semanal.
- AttendanceParser: parsing de filas respetando Corrección 1 (sin deduplicación).
- ExcelAttendanceParser: extracción desde plantillas / listas Excel.
"""

from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
from app.parsers.word_parser import WordReportParser
from app.parsers.attendance_parser import AttendanceParser
from app.core.constants.participant_types import CategoriaParticipacion


class TestWordReportParser:
    """Pruebas del parser de Word."""

    def test_parse_from_dict_extrae_todos_los_metadatos_institucionales(self):
        datos = {
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

        actividad = WordReportParser.parse_from_dict(datos)

        assert actividad.nombre_actividad_original == "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial"
        assert actividad.sede == "Bilwi"
        assert actividad.departamento == "RACCN"
        assert actividad.municipio_evento == "Puerto Cabezas"
        assert actividad.eje_linea_estrategica == "11.41.67"
        assert actividad.tipo_evento == "7. Creatividad, Ciencias, Investigación e Innovación"
        assert actividad.fecha_evento == "08/09/2026"
        assert "Innovación y Emprendimiento" in actividad.informacion_adicional
        assert "Horario: 10:00 AM – 12:00 PM" in actividad.informacion_adicional


class TestAttendanceParser:
    """Pruebas del parser de listas de asistencia."""

    def test_cumple_correccion_1_cada_fila_es_participacion_independiente_sin_deduplicar(self):
        """
        Verifica que AttendanceParser crea objetos Person y Participation independientes
        por cada fila, sin asumir ni resolver identidades duplicadas.
        """
        filas = [
            RawParticipantRow(
                numero_fila=1,
                hoja=1,
                nombre_completo="Johnny Melvin",
                sexo="M",
                cedula="601-010100-1001A",
                edad=21,
                carrera="Contabilidad",
                categoria="Estudiante"
            ),
            # Fila con el mismo nombre exacto pero debe conservarse como persona y participación independiente
            RawParticipantRow(
                numero_fila=2,
                hoja=1,
                nombre_completo="Johnny Melvin",
                sexo="M",
                cedula=None,
                edad=21,
                carrera="Contabilidad",
                categoria="Estudiante"
            )
        ]

        sheet_data = RawAttendanceSheetData(
            nombre_actividad="Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial",
            fecha="08/09/2026",
            sede="Bilwi",
            filas=filas
        )

        resultado = AttendanceParser.parse_sheet_data(sheet_data, id_actividad="act-test-01")

        # Se crean exactamente 2 personas y 2 participaciones
        assert len(resultado.personas) == 2
        assert len(resultado.participaciones) == 2

        # NO están deduplicadas: tienen IDs de persona distintos
        p1, p2 = resultado.personas
        assert p1.id_persona_interno != p2.id_persona_interno

        # Ambas participaciones apuntan a la misma actividad
        assert resultado.participaciones[0].id_actividad == "act-test-01"
        assert resultado.participaciones[1].id_actividad == "act-test-01"

        # Cada participación apunta a su respectiva persona
        assert resultado.participaciones[0].id_persona == p1.id_persona_interno
        assert resultado.participaciones[1].id_persona == p2.id_persona_interno

        # Sexo en asistencia física se mapea como MASCULINO
        assert p1.sexo_normalizado == "MASCULINO"
        assert p2.sexo_normalizado == "MASCULINO"
