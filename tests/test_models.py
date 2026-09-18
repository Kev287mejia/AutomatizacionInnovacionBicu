"""
tests/test_models.py

Pruebas unitarias para los modelos de datos internos (FASE 2):
- Activity
- Person
- Participation
- ValidationResult
- Relaciones entre modelos (1 actividad + múltiples participantes de distintas categorías)
- Regla de no invención (campos faltantes = None)
- Mapeos de sexo y catálogos
"""

import pytest
import uuid
from datetime import date, datetime
from pydantic import ValidationError

from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import (
    CategoriaParticipacion,
    NivelValidacion,
    NivelConfianzaIdentidad,
)
from app.core.catalog.catalog_loader import CatalogLoader


class TestActivityModel:
    """Pruebas del modelo Activity."""

    def test_creacion_basica_con_id_autogenerado(self):
        """Verifica que el ID interno se genere automáticamente como UUID válido."""
        act = Activity(nombre_actividad_original="Taller de Robótica")
        assert act.nombre_actividad_original == "Taller de Robótica"
        assert act.id_actividad is not None
        # Validar que sea un UUID4 válido
        validador_uuid = uuid.UUID(act.id_actividad, version=4)
        assert str(validador_uuid) == act.id_actividad

    def test_dos_actividades_tienen_ids_distintos(self):
        """Regla C-13: Dos actividades con el mismo nombre deben tener IDs distintos."""
        act1 = Activity(nombre_actividad_original="Feria de Innovación")
        act2 = Activity(nombre_actividad_original="Feria de Innovación")
        assert act1.id_actividad != act2.id_actividad

    def test_todos_los_campos_opcionales(self):
        """Verifica la asignación correcta de todos los metadatos de actividad."""
        act = Activity(
            nombre_actividad_original="Conferencia IA 2026",
            nombre_actividad_oficial="Conferencia de Inteligencia Artificial 2026",
            fecha_evento="2026-05-15",
            sede="Recinto Central",
            departamento="Managua",
            municipio_evento="Managua",
            programa="Vinculación Social",
            ambito="Nacional",
            tipo_evento="Conferencia",
            eje_linea_estrategica="Eje 1: Innovación Tecnológica",
            informacion_adicional="Evento híbrido presencial y virtual",
            fuente_origen="informe_mayo.docx",
        )
        assert act.sede == "Recinto Central"
        assert act.departamento == "Managua"
        assert act.fuente_origen == "informe_mayo.docx"

    def test_nombre_vacio_falla_validacion(self):
        """Regla de integridad: No se permite una actividad sin nombre."""
        with pytest.raises(ValidationError):
            Activity(nombre_actividad_original="")

    def test_nombre_espacios_en_blanco_falla_validacion(self):
        with pytest.raises(ValidationError):
            Activity(nombre_actividad_original="   ")


class TestPersonModel:
    """Pruebas del modelo Person."""

    def test_creacion_basica_con_id_autogenerado(self):
        persona = Person(nombre_completo="Carlos Alberto Mendoza Ruiz")
        assert persona.nombre_completo == "Carlos Alberto Mendoza Ruiz"
        assert persona.id_persona_interno is not None
        # Verificar UUID
        assert uuid.UUID(persona.id_persona_interno, version=4)

    def test_carreras_separadas_segun_regla_c12(self):
        """Regla C-12: carrera_original, carrera_normalizada y carrera_oficial deben ser independientes."""
        persona = Person(
            nombre_completo="Ana María Morales",
            carrera_original="ing. en computacion",
            carrera_normalizada="INGENIERIA EN COMPUTACION",
            carrera_oficial="Ingeniería en Computación",
        )
        assert persona.carrera_original == "ing. en computacion"
        assert persona.carrera_normalizada == "INGENIERIA EN COMPUTACION"
        assert persona.carrera_oficial == "Ingeniería en Computación"

    def test_regla_no_invencion_campos_faltantes_son_none(self):
        """Regla C-10: Los datos que no vienen en la fuente deben ser None."""
        persona = Person(nombre_completo="Pedro Páramo")
        assert persona.cedula is None
        assert persona.telefono is None
        assert persona.fecha_nacimiento is None
        assert persona.edad is None
        assert persona.carrera_original is None
        assert persona.carrera_oficial is None

    def test_jerarquia_identidad_niveles(self):
        """Regla C-09: Soporta cédula (Nivel 1), carné (Nivel 2) y otro ID (Nivel 3)."""
        p1 = Person(nombre_completo="P1", cedula="001-010190-0001A")
        p2 = Person(nombre_completo="P2", numero_unico="2023-0102U")
        p3 = Person(nombre_completo="P3", otro_id_institucional="DOC-9988")

        assert p1.cedula == "001-010190-0001A"
        assert p2.numero_unico == "2023-0102U"
        assert p3.otro_id_institucional == "DOC-9988"

    def test_sexo_especifico_por_fuente_regla_c08(self):
        """Regla C-08: Conserva sexo_original, sexo_fuente y sexo_normalizado."""
        p = Person(
            nombre_completo="Lucía Gómez",
            sexo_original="M",
            sexo_fuente="lista_asistencia_taller.xlsx",
            sexo_normalizado="FEMENINO",
        )
        assert p.sexo_original == "M"
        assert p.sexo_fuente == "lista_asistencia_taller.xlsx"
        assert p.sexo_normalizado == "FEMENINO"

    def test_validacion_edad_invalida(self):
        with pytest.raises(ValidationError):
            Person(nombre_completo="Invalido", edad=-5)

        with pytest.raises(ValidationError):
            Person(nombre_completo="Invalido", edad=150)


class TestParticipationModel:
    """Pruebas del modelo Participation."""

    def test_creacion_participacion_valida(self):
        id_act = str(uuid.uuid4())
        id_per = str(uuid.uuid4())
        part = Participation(
            id_actividad=id_act,
            id_persona=id_per,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        assert part.id_actividad == id_act
        assert part.id_persona == id_per
        assert part.categoria_participacion == CategoriaParticipacion.ESTUDIANTE
        assert part.id_participacion is not None
        assert part.nivel_confianza_identidad == 1
        assert not part.requiere_revision

    def test_conversion_automatica_de_string_a_categoria(self):
        """Permite pasar string como 'DOCENTE' o 'docente' y lo normaliza a Enum."""
        part = Participation(
            id_actividad="act-1",
            id_persona="per-1",
            categoria_participacion="docente",
        )
        assert part.categoria_participacion == CategoriaParticipacion.DOCENTE

    def test_categoria_desconocida_asigna_enum_desconocido(self):
        part = Participation(
            id_actividad="act-1",
            id_persona="per-1",
            categoria_participacion="INVITADO_EXTERNO_NO_REGISTRADO",
        )
        assert part.categoria_participacion == CategoriaParticipacion.DESCONOCIDO

    def test_nivel_confianza_invalido_falla(self):
        with pytest.raises(ValidationError):
            Participation(
                id_actividad="act-1",
                id_persona="per-1",
                categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
                nivel_confianza_identidad=9,
            )

    def test_participacion_marcada_para_revision(self):
        part = Participation(
            id_actividad="act-1",
            id_persona="per-1",
            categoria_participacion=CategoriaParticipacion.DESCONOCIDO,
            requiere_revision=True,
            motivo_revision="Categoría ilegible en lista manuscrita.",
        )
        assert part.requiere_revision
        assert "ilegible" in part.motivo_revision


class TestValidationResultModel:
    """Pruebas del modelo ValidationResult."""

    def test_creacion_los_cuatro_niveles(self):
        for nivel in (NivelValidacion.ERROR, NivelValidacion.WARNING, NivelValidacion.INFO, NivelValidacion.REVISION):
            vr = ValidationResult(
                nivel=nivel,
                codigo=f"CODE_{nivel.value}",
                mensaje=f"Mensaje de prueba para nivel {nivel.value}",
            )
            assert vr.nivel == nivel
            assert vr.id_resultado is not None
            assert isinstance(vr.timestamp, datetime)

    def test_conversion_string_a_nivel(self):
        vr = ValidationResult(
            nivel="warning",
            codigo="WARN_CEDULA_VACIA",
            mensaje="La cédula no fue suministrada en la lista.",
        )
        assert vr.nivel == NivelValidacion.WARNING

    def test_nivel_invalido_falla(self):
        with pytest.raises(ValidationError):
            ValidationResult(
                nivel="CRITICAL_FATAL",
                codigo="BAD_LEVEL",
                mensaje="No permitido",
            )


class TestEscenarioRelacional:
    """
    Criterio de aceptación 5 de FASE 2:
    1 actividad con 3 participantes de distintas categorías y verificación de relaciones.
    """

    def test_actividad_con_tres_participantes_de_distintas_categorias(self):
        # 1. Crear actividad
        actividad = Activity(
            nombre_actividad_original="Taller de Prototipado Rápido e Innovación",
            fecha_evento="2026-06-10",
            sede="Campus RUCFA",
        )

        # 2. Crear 3 personas distintas
        estudiante = Person(
            nombre_completo="María Auxiliadora Martínez",
            cedula="001-150802-1002K",
            carrera_original="Ing. en Sistemas",
        )
        docente = Person(
            nombre_completo="Dr. Fernando José Castillo",
            cedula="001-200575-0014B",
            carrera_original="Ciencias de la Computación",
        )
        beneficiario = Person(
            nombre_completo="Silvia Elena Torres",
            cedula="001-050488-0021M",
            municipio_persona="Tipitapa",
        )

        # 3. Crear participaciones con sus respectivas categorías
        part1 = Participation(
            id_actividad=actividad.id_actividad,
            id_persona=estudiante.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        part2 = Participation(
            id_actividad=actividad.id_actividad,
            id_persona=docente.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
        )
        part3 = Participation(
            id_actividad=actividad.id_actividad,
            id_persona=beneficiario.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.BENEFICIADO,
        )

        participaciones = [part1, part2, part3]

        # 4. Verificaciones de integridad relacional
        # Todas las participaciones apuntan a la misma actividad
        assert all(p.id_actividad == actividad.id_actividad for p in participaciones)

        # Cada participación apunta a la persona correcta
        assert part1.id_persona == estudiante.id_persona_interno
        assert part2.id_persona == docente.id_persona_interno
        assert part3.id_persona == beneficiario.id_persona_interno

        # Las categorías de routing son las esperadas
        categorias = [p.categoria_participacion for p in participaciones]
        assert CategoriaParticipacion.ESTUDIANTE in categorias
        assert CategoriaParticipacion.DOCENTE in categorias
        assert CategoriaParticipacion.BENEFICIADO in categorias

        # Regla C-10: Se conservan los 3 registros como asistencias individuales
        assert len(participaciones) == 3


class TestCatalogLoader:
    """Pruebas del cargador de catálogos."""

    def test_obtener_catalogo_carreras_no_rompe(self):
        carreras = CatalogLoader.obtener_catalogo_carreras()
        assert isinstance(carreras, list)

    def test_obtener_catalogo_etnias_no_rompe(self):
        etnias = CatalogLoader.obtener_catalogo_etnias()
        assert isinstance(etnias, list)

    def test_mapeos_sexo_y_normalizacion_por_fuente(self):
        # Mapeos cargados correctamente
        mapeos = CatalogLoader.obtener_mapeos_sexo()
        assert isinstance(mapeos, dict)
        # Si la fuente no existe, devuelve None sin inventar
        resultado = CatalogLoader.normalizar_sexo_segun_fuente("M", "fuente_inexistente")
        assert resultado is None
