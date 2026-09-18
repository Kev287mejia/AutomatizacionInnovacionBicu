"""
tests/test_matching.py

Pruebas unitarias para el evaluador de coincidencias de actividades (ActivityMatcher).
Verifica:
- Unificación de actividad de informe Word y lista de asistencia por EVIDENCIA MÚLTIPLE.
- Conservación de ambos nombres originales para trazabilidad.
- Generación de ValidationResult(INFO, 'MATCH_ACTIVIDAD_UNIFICADA').
- Generación de ValidationResult(REVISION, 'MATCH_ACTIVIDAD_REVISION') cuando la evidencia es insuficiente.
- Mantenimiento de actividades separadas cuando no coinciden.
"""

from app.core.models.activity import Activity
from app.matching.activity_matcher import ActivityMatcher
from app.core.constants.participant_types import NivelValidacion


class TestActivityMatching:
    """Pruebas del unificador de actividades con evidencia múltiple."""

    def test_unificacion_alta_confianza_caso_real_septiembre_2026(self):
        """
        Caso real:
        Word: 'BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial'
        Asistencia: 'Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial'
        Fecha: 08/09/2026
        Sede: Bilwi / CUR BICU Bilwi
        Municipio: Puerto Cabezas
        Departamento: RACCN
        Horario: 10:00 AM – 12:00 PM
        """
        actividad_word = Activity(
            nombre_actividad_original="BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial",
            fecha_evento="08/09/2026",
            sede="Bilwi",
            departamento="RACCN",
            municipio_evento="Puerto Cabezas",
            eje_linea_estrategica="11.41.67",
            tipo_evento="7. Creatividad, Ciencias, Investigación e Innovación",
            informacion_adicional="Horario: 10:00 AM – 12:00 PM",
            fuente_origen="informe_word"
        )

        datos_asistencia = {
            "nombre_actividad_asistencia": "Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial",
            "fecha_evento": "08/09/2026",
            "sede": "Bilwi",
            "departamento": "RACCN",
            "municipio_evento": "Puerto Cabezas",
            "horario": "10:00 AM – 12:00 PM",
            "fuente_origen": "asistencia_fisica"
        }

        resultado = ActivityMatcher.evaluar_coincidencia(actividad_word, datos_asistencia)

        assert resultado.coinciden is True
        assert resultado.nivel_confianza == "ALTA"
        assert resultado.actividad_unificada is not None

        # El id_actividad interno es compartido
        assert resultado.actividad_unificada.id_actividad == actividad_word.id_actividad

        # Trazabilidad: ambos nombres originales se conservan
        assert resultado.actividad_unificada.nombre_actividad_original == actividad_word.nombre_actividad_original
        assert "Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial" in resultado.actividad_unificada.informacion_adicional

        # Validación informativa generada
        codigos = [v.codigo for v in resultado.validaciones]
        assert "MATCH_ACTIVIDAD_UNIFICADA" in codigos
        assert "VAL_ACTIVIDAD_DIFERENCIA_NOMBRE" in codigos

    def test_confianza_insuficiente_envia_a_revision_sin_unificar(self):
        """
        Si solo coincide la fecha pero la sede o tema son distintos o ambiguos,
        no debe unificar automáticamente y debe enviar a REVISION.
        """
        actividad_word = Activity(
            nombre_actividad_original="Taller sobre innovación y robótica",
            fecha_evento="08/09/2026",
            sede="Bluefields",
            departamento="RACCS",
            fuente_origen="informe_word"
        )

        datos_asistencia = {
            "nombre_actividad_asistencia": "Capacitación en marketing digital",
            "fecha_evento": "08/09/2026",
            "sede": "Bilwi",
            "fuente_origen": "asistencia_fisica"
        }

        resultado = ActivityMatcher.evaluar_coincidencia(actividad_word, datos_asistencia)

        assert resultado.coinciden is False
        assert resultado.nivel_confianza == "INSUFICIENTE"
        assert resultado.actividad_unificada is None

        # Genera ValidationResult de REVISION
        assert len(resultado.validaciones) == 1
        val = resultado.validaciones[0]
        assert val.nivel == NivelValidacion.REVISION
        assert val.codigo == "MATCH_ACTIVIDAD_REVISION"

    def test_no_coincidencia_mantiene_separadas(self):
        """
        Actividades en fechas completamente distintas y sin relación.
        """
        actividad_word = Activity(
            nombre_actividad_original="Conferencia magistral de bienvenida",
            fecha_evento="01/02/2026",
            sede="Bilwi",
            fuente_origen="informe_word"
        )

        datos_asistencia = {
            "nombre_actividad_asistencia": "Feria de proyectos de innovación",
            "fecha_evento": "15/10/2026",
            "sede": "Bluefields",
            "fuente_origen": "asistencia_fisica"
        }

        resultado = ActivityMatcher.evaluar_coincidencia(actividad_word, datos_asistencia)

        assert resultado.coinciden is False
        assert resultado.nivel_confianza == "NULA"
        assert resultado.actividad_unificada is None
