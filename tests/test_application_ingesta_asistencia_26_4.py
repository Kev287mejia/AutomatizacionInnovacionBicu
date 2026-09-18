"""tests/test_application_ingesta_asistencia_26_4.py

Pruebas exhaustivas para la Fase 26.4:
Implementación Controlada del Caso de Uso IngestarListaAsistenciaUseCase.

Cubre las 22 condiciones obligatorias y la prueba específica de DETECTAR ≠ CORREGIR:
1. Actividad inexistente -> EntityNotFoundError
2. Persona nueva con cédula
3. Persona nueva sin cédula
4. Ausencia de cédula sin falso positivo de duplicado
5. Identidad no resuelta
6. Posible duplicado
7. Participación repetida
8. Nombre vacío (rechazo como error de datos)
9. Dato faltante (permanece en None)
10. Inconsistencia de cédula
11. Verificación de que una inconsistencia NO se corrige silenciosamente
12. Verificación de preservación del dato original cuando el contrato lo permita
13. Verificación de que NO se inventa una cédula
14. Mezcla de filas válidas + errores
15. Rollback ante excepción de persistencia
16. Commit correcto
17. matriz_destino is None
18. Ausencia de routing M2–M5
19. Ausencia de modificaciones de esquema
20. Ausencia de tablas nuevas
21. Separación Clean Architecture
22. Ausencia de imports prohibidos
"""

import ast
from pathlib import Path
import pytest

from app.core.constants.participant_types import (
    CategoriaParticipacion,
    NivelConfianzaIdentidad,
    NivelValidacion,
)
from app.core.exceptions.persistence_exceptions import (
    EntityNotFoundError,
    TransactionError,
)
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.discrepancy import Discrepancia, EstadoDiscrepancia
from app.application.commands import IngestarListaAsistenciaCommand
from app.application.dto import FilaParticipanteIngestaDTO
from app.application.fakes import (
    InMemoryActividadRepository,
    InMemoryPersonaRepository,
    InMemoryParticipacionRepository,
    InMemoryDiscrepanciaRepository,
    InMemoryUnitOfWork,
)
from app.application.use_cases import IngestarListaAsistenciaUseCase


@pytest.fixture
def repos():
    """Fixture con repositorios en memoria y actividad preconfigurada."""
    act_repo = InMemoryActividadRepository()
    per_repo = InMemoryPersonaRepository()
    part_repo = InMemoryParticipacionRepository()
    disc_repo = InMemoryDiscrepanciaRepository()

    # Registrar actividad válida base
    act_repo.save(
        Activity(
            id_actividad="act-base-001",
            nombre_actividad_original="Taller de Robótica Educativa",
            sede="BLUEFIELDS",
        )
    )

    return act_repo, per_repo, part_repo, disc_repo


# ==============================================================================
# BLOQUE 1: Identidad y Precondiciones (Pruebas 1 a 5)
# ==============================================================================

class TestIngestaAsistenciaBasicos:
    """Pruebas para precondiciones e identidad básica."""

    def test_01_actividad_inexistente_lanza_entity_not_found(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-INEXISTENTE",
            fuente_archivo="lista_asistencia.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(nombre_fuente="Juan Pérez")
            ],
        )

        with pytest.raises(EntityNotFoundError) as exc_info:
            use_case.execute(cmd)

        assert "Actividad" in str(exc_info.value)
        assert per_repo.count() == 0
        assert part_repo.count_by_actividad("act-INEXISTENTE") == 0

    def test_02_persona_nueva_con_cedula(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_valida.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Ana Rosa Morales",
                    cedula_fuente="601-120598-0001A",
                    carrera_cargo_fuente="Ingeniería en Sistemas",
                    categoria_sugerida="ESTUDIANTE",
                )
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 1
        assert res.nuevas_personas_registradas == 1
        assert res.personas_existentes_vinculadas == 0
        assert res.participaciones_creadas == 1
        assert res.participaciones_en_revision == 0

        # Verificar persistencia en repositorios
        persona = per_repo.get_by_cedula("601-120598-0001A")
        assert persona is not None
        assert persona.nombre_completo == "Ana Rosa Morales"

        parts = part_repo.get_by_actividad("act-base-001")
        assert len(parts) == 1
        assert parts[0].id_persona == persona.id_persona_interno
        assert parts[0].nivel_confianza_identidad == NivelConfianzaIdentidad.NIVEL_1_CEDULA.value
        assert parts[0].requiere_revision is False

    def test_03_persona_nueva_sin_cedula(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_sin_cedula.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Kenia Lizeth Dixon",
                    cedula_fuente=None,
                    etnia_fuente="Miskitu",
                    categoria_sugerida="BENEFICIADO",
                )
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 1
        assert res.nuevas_personas_registradas == 1
        assert res.participaciones_creadas == 1

        personas = per_repo.search_by_nombre("Kenia")
        assert len(personas) == 1
        assert personas[0].cedula is None  # RN-C04
        assert personas[0].etnia == "Miskitu"

    def test_04_ausencia_cedula_sin_falso_positivo_duplicado(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        # Ingestar una persona sin cédula legítima
        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_comunitaria.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Brenda Jackson Taylor",
                    cedula_fuente=None,
                    categoria_sugerida="POBLADOR_GENERAL",
                )
            ],
        )

        res = use_case.execute(cmd)

        # No debe marcarse como posible duplicado si no hay antecedentes en el sistema
        assert res.participaciones_en_revision == 0
        assert len(disc_repo.list_by_actividad("act-base-001")) == 0
        parts = part_repo.get_by_actividad("act-base-001")
        assert len(parts) == 1
        assert parts[0].requiere_revision is False

    def test_05_identidad_no_resuelta(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_precaria.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Carlos",  # Nombre de una sola palabra sin más datos
                    cedula_fuente=None,
                )
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 1
        assert res.participaciones_creadas == 1
        assert res.participaciones_en_revision == 1

        parts = part_repo.get_by_actividad("act-base-001")
        assert len(parts) == 1
        assert parts[0].requiere_revision is True
        assert "Identidad no resuelta" in (parts[0].motivo_revision or "")


# ==============================================================================
# BLOQUE 2: Casos Complejos y Duplicados (Pruebas 6 a 9 y 14)
# ==============================================================================

class TestIngestaAsistenciaCasosComplejos:
    """Pruebas para duplicados, participaciones repetidas y errores de datos."""

    def test_06_posible_duplicado(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        # Preexistencia de persona con nombre completo idéntico pero sin cédula
        per_previa = Person(
            id_persona_interno="per-previa-001",
            nombre_completo="Johnny Melvin Hodgson",
            cedula=None,
            fuente_origen="censo_antiguo",
        )
        per_repo.save(per_previa)

        # Llega una lista con el mismo nombre y sin cédula
        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_nueva.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Johnny Melvin Hodgson",
                    cedula_fuente=None,
                    categoria_sugerida="ESTUDIANTE",
                )
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 1
        assert res.nuevas_personas_registradas == 1  # No se fusiona automáticamente (DETECTAR ≠ CORREGIR)
        assert res.participaciones_en_revision == 1

        # Verificar que se generó discrepancia
        discs = disc_repo.list_by_actividad("act-base-001")
        assert len(discs) == 1
        assert "per-previa-001" in discs[0].fuente_b_valor

        # Verificar que las dos personas existen separadas
        assert per_repo.count() == 2

    def test_07_participacion_repetida(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        # Lista con la misma persona en dos filas distintas de la misma actividad
        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_doble_firma.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Elena Smith Brown",
                    cedula_fuente="601-201095-0003K",
                    categoria_sugerida="DOCENTE",
                    observaciones_fuente="Sesión matutina",
                ),
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Elena Smith Brown",
                    cedula_fuente="601-201095-0003K",
                    categoria_sugerida="DOCENTE",
                    observaciones_fuente="Sesión vespertina",
                ),
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 2
        assert res.nuevas_personas_registradas == 1
        assert res.personas_existentes_vinculadas == 1
        assert res.participaciones_creadas == 1  # Opción A: Participación única por Persona + Actividad
        assert res.participaciones_en_revision == 1  # Marcada para revisión

        parts = part_repo.get_by_actividad("act-base-001")
        assert len(parts) == 1  # Invariante de unicidad respetada
        assert parts[0].requiere_revision is True
        assert "Participación repetida" in (parts[0].motivo_revision or "")
        assert "Sesión vespertina" in (parts[0].observaciones or "")
        assert "fila 2" in (parts[0].observaciones or "")

        # Se registra discrepancia formal sin borrar nada
        discs = disc_repo.list_by_actividad("act-base-001")
        assert len(discs) == 1
        assert "Participación repetida" in (discs[0].delta_valor or "")
        assert discs[0].fuente_b_valor == parts[0].id_participacion

        # Hallazgo de validación emitido en el resultado
        assert any(h.codigo == "VAL_PARTICIPACION_REPETIDA" for h in res.hallazgos_validacion)

    def test_08_nombre_vacio(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_defectuosa.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="",  # Vacío
                    cedula_fuente="601-010100-0000X",
                )
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 1
        assert res.participaciones_creadas == 0  # Rechazada
        assert len(res.hallazgos_validacion) == 1
        assert res.hallazgos_validacion[0].codigo == "VAL_NOMBRE_VACIO"
        assert res.hallazgos_validacion[0].nivel == NivelValidacion.ERROR

    def test_09_dato_faltante(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_minima.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Silvia Gómez Flores",
                    cedula_fuente=None,
                    sexo_fuente=None,
                    etnia_fuente=None,
                    carrera_cargo_fuente=None,
                )
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 1
        assert res.participaciones_creadas == 1

        persona = per_repo.search_by_nombre("Silvia Gómez Flores")[0]
        assert persona.sexo_original is None
        assert persona.etnia is None
        assert persona.carrera_original is None
        assert persona.edad is None

    def test_14_mezcla_filas_validas_y_errores(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_mixta.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(nombre_fuente="Participante Válido 1", cedula_fuente="601-010190-0001A"),
                FilaParticipanteIngestaDTO(nombre_fuente="   "),  # Error de datos
                FilaParticipanteIngestaDTO(nombre_fuente="Participante Válido 2", cedula_fuente=None),
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 3
        assert res.participaciones_creadas == 2  # Las dos válidas
        errores = [h for h in res.hallazgos_validacion if h.nivel == NivelValidacion.ERROR]
        assert len(errores) == 1
        assert errores[0].codigo == "VAL_NOMBRE_VACIO"



# ==============================================================================
# BLOQUE 3: Principio DETECTAR ≠ CORREGIR e Inconsistencias (Pruebas 10 a 13 y 16)
# ==============================================================================

class TestDetectarNoCorregirInconsistencias:
    """Pruebas dedicadas a validar la detección estricta sin corrección silenciosa."""

    def test_10_inconsistencia_cedula(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_anomala.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Adolescente Escolar",
                    cedula_fuente="20-04-2008",  # Fecha en celda de cédula
                )
            ],
        )

        res = use_case.execute(cmd)

        assert res.total_procesados == 1
        assert res.participaciones_creadas == 1
        assert res.participaciones_en_revision == 1

        # Validar que se emitió el código de alerta exacto
        codigos = [h.codigo for h in res.hallazgos_validacion]
        assert "VAL_CEDULA_FECHA" in codigos

    def test_11_verificacion_de_que_una_inconsistencia_no_se_corrige_silenciosamente(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_anomala.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Adolescente Escolar",
                    cedula_fuente="20-04-2008",
                )
            ],
        )

        use_case.execute(cmd)

        persona = per_repo.search_by_nombre("Adolescente Escolar")[0]
        # NO se trasladó automáticamente a fecha de nacimiento
        assert persona.fecha_nacimiento is None

    def test_12_verificacion_de_preservacion_del_dato_original_cuando_el_contrato_lo_permita(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_anomala.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Adolescente Escolar",
                    cedula_fuente="20-04-2008",
                )
            ],
        )

        use_case.execute(cmd)

        # 1. Preservado en Discrepancia
        discs = disc_repo.list_by_actividad("act-base-001")
        assert len(discs) == 1
        assert discs[0].fuente_a_valor == "20-04-2008"
        assert discs[0].estado == EstadoDiscrepancia.REQUIERE_REVISION

        # 2. Preservado en Observaciones de la Participación
        parts = part_repo.get_by_actividad("act-base-001")
        assert "20-04-2008" in (parts[0].observaciones or "")

    def test_13_verificacion_de_que_no_se_inventa_una_cedula(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_anomala.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Adolescente Escolar",
                    cedula_fuente="20-04-2008",
                )
            ],
        )

        use_case.execute(cmd)

        persona = per_repo.search_by_nombre("Adolescente Escolar")[0]
        # Queda como None; NUNCA se inventa un código sintético como '000-200408-0000X'
        assert persona.cedula is None

    def test_especifica_seccion_16_detectar_no_corregir_anomalia_incompatible(self, repos):
        """Prueba mandatoria de la Sección 16: Valor incompatible en una columna."""
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_incompatible.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Test Incompatible",
                    cedula_fuente="TEXTO_INVALIDO_TOTALMENTE_CORRUPTO_1234",
                )
            ],
        )

        res = use_case.execute(cmd)

        # 1. Detecta la anomalía
        assert res.participaciones_en_revision == 1
        codigos = [h.codigo for h in res.hallazgos_validacion]
        assert "VAL_CEDULA_FORMATO_DUDOSO" in codigos

        # 2. No inventa valor
        persona = per_repo.search_by_nombre("Test Incompatible")[0]
        assert persona.cedula is None

        # 3. No realiza corrección silenciosa
        assert persona.nombre_completo == "Test Incompatible"

        # 4. Genera revisión y discrepancia
        discs = disc_repo.list_by_actividad("act-base-001")
        assert len(discs) == 1
        assert discs[0].fuente_a_valor == "TEXTO_INVALIDO_TOTALMENTE_CORRUPTO_1234"

        # 5. Preserva el valor original disponible
        parts = part_repo.get_by_actividad("act-base-001")
        assert "TEXTO_INVALIDO_TOTALMENTE_CORRUPTO_1234" in (parts[0].observaciones or "")


# ==============================================================================
# BLOQUE 4: Transaccionalidad y Unit of Work (Pruebas 15 y 16)
# ==============================================================================

class TestIngestaTransaccionalUoW:
    """Pruebas para rollback y commit mediante IUnitOfWork."""

    def test_15_rollback_ante_excepcion_persistencia(self):
        act_repo = InMemoryActividadRepository()
        act_repo.save(Activity(id_actividad="act-uow-01", nombre_actividad_original="Taller UoW"))
        per_repo = InMemoryPersonaRepository()
        disc_repo = InMemoryDiscrepanciaRepository()

        # Clase repositorio que simula fallo imprevisto de persistencia
        class FaultyParticipacionRepo(InMemoryParticipacionRepository):
            def save(self, p):
                raise TransactionError("Fallo simulado de conexión I/O durante inserción")

        faulty_part_repo = FaultyParticipacionRepo()

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=faulty_part_repo,
            discrepancias=disc_repo,
        )

        use_case = IngestarListaAsistenciaUseCase(uow=uow)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-uow-01",
            fuente_archivo="lista_fail.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(nombre_fuente="Persona Fallida", cedula_fuente="601-010190-0009Z")
            ],
        )

        with pytest.raises(TransactionError, match="Fallo simulado"):
            use_case.execute(cmd)

        # Verificar que se ejecutó rollback y no quedó la persona registrada
        with uow:
            assert uow.personas.get_by_cedula("601-010190-0009Z") is None

    def test_16_commit_correcto(self):
        act_repo = InMemoryActividadRepository()
        act_repo.save(Activity(id_actividad="act-commit-01", nombre_actividad_original="Taller Commit"))
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        disc_repo = InMemoryDiscrepanciaRepository()

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=part_repo,
            discrepancias=disc_repo,
        )

        use_case = IngestarListaAsistenciaUseCase(uow=uow)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-commit-01",
            fuente_archivo="lista_commit.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(nombre_fuente="Persona Éxito", cedula_fuente="601-010190-0088A")
            ],
        )

        res = use_case.execute(cmd)

        assert res.participaciones_creadas == 1
        assert per_repo.get_by_cedula("601-010190-0088A") is not None
        assert len(part_repo.get_by_actividad("act-commit-01")) == 1



# ==============================================================================
# BLOQUE 5: Neutralidad de Routing y Matrices M2–M5 (Pruebas 17 y 18)
# ==============================================================================

class TestIngestaAislamientoYRouting:
    """Verifica que matriz_destino permanece neutral (None) sin ruteo a M2..M5."""

    def test_17_matriz_destino_is_none(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_routing.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Estudiante Normal",
                    categoria_sugerida="ESTUDIANTE",
                )
            ],
        )

        use_case.execute(cmd)

        parts = part_repo.get_by_actividad("act-base-001")
        assert len(parts) == 1
        # La entidad Participation no decide matriz_destino en la capa Application
        assert getattr(parts[0], "matriz_destino", None) is None

    def test_18_ausencia_routing_m2_m5(self, repos):
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_multiple_roles.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(nombre_fuente="P1", categoria_sugerida="ESTUDIANTE"),
                FilaParticipanteIngestaDTO(nombre_fuente="P2", categoria_sugerida="DOCENTE"),
                FilaParticipanteIngestaDTO(nombre_fuente="P3", categoria_sugerida="BENEFICIADO"),
            ],
        )

        use_case.execute(cmd)

        # Comprobar que en memoria ningún objeto tiene forzada M2, M3 o M5
        for p in part_repo.get_by_actividad("act-base-001"):
            assert getattr(p, "matriz_destino", None) is None


# ==============================================================================
# BLOQUE 6: Aislamiento Arquitectónico y Esquema (Pruebas 19 a 22)
# ==============================================================================

class TestIngestaArquitecturaYAislamiento:
    """Verificación de integridad de esquema SQLite y Clean Architecture AST."""

    def test_19_ausencia_modificaciones_esquema(self):
        schema_path = Path("app/infrastructure/persistence/schema.py")
        assert schema_path.exists()
        content = schema_path.read_text(encoding="utf-8")
        # El esquema no debe tener tablas de ingesta temporales
        assert "CREATE TABLE IF NOT EXISTS ingesta_asistencia" not in content
        assert "CREATE TABLE IF NOT EXISTS participacion_temporal" not in content

    def test_20_ausencia_tablas_nuevas(self):
        schema_path = Path("app/infrastructure/persistence/schema.py")
        content = schema_path.read_text(encoding="utf-8")
        # No existe tabla cuarentena ni tabla de duplicados
        assert "CREATE TABLE IF NOT EXISTS cuarentena" not in content
        assert "CREATE TABLE IF NOT EXISTS duplicados" not in content

    def test_21_separacion_clean_architecture(self):
        uc_path = Path("app/application/use_cases/participacion/ingestar_lista_asistencia.py")
        tree = ast.parse(uc_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "infrastructure" not in alias.name
                    assert "sqlite3" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "infrastructure" not in node.module
                    assert "sqlite3" not in node.module

    def test_22_ausencia_imports_prohibidos(self):
        uc_path = Path("app/application/use_cases/participacion/ingestar_lista_asistencia.py")
        tree = ast.parse(uc_path.read_text(encoding="utf-8"))

        prohibidos = {"openpyxl", "xlsxwriter", "docx", "customtkinter", "tkinter"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in prohibidos
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    base = node.module.split(".")[0]
                    assert base not in prohibidos


# ==============================================================================
# BLOQUE 7: Integración Real con SQLite y Verificación de UNIQUE (Fase 26.4.2)
# ==============================================================================

class TestIngestaSQLiteIntegracionReal:
    """Pruebas de integración con base de datos SQLite real y restricción UNIQUE."""

    def test_sqlite_participacion_repetida_no_lanza_integrity_error_y_preserva_evidencia(self, tmp_path):
        """Demuestra que una segunda aparición procesada en SQLite real no lanza IntegrityError,
        se confirma con COMMIT, respeta UNIQUE (id_actividad, id_persona) y registra la discrepancia.
        """
        import sqlite3
        from app.infrastructure.persistence.config import DatabaseConfig
        from app.infrastructure.persistence.connection import SQLiteConnectionManager
        from app.infrastructure.persistence.migrations import MigrationRunner
        from app.infrastructure.persistence.repositories.actividad_repository import SQLiteActividadRepository
        from app.infrastructure.persistence.repositories.persona_repository import SQLitePersonaRepository
        from app.infrastructure.persistence.repositories.participacion_repository import SQLiteParticipacionRepository
        from app.infrastructure.persistence.repositories.discrepancia_repository import SQLiteDiscrepanciaRepository
        from app.infrastructure.persistence.repositories.unit_of_work import SQLiteUnitOfWork

        db_file = tmp_path / "test_ingesta_real.db"
        manager = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))
        conn = manager.get_connection()

        # 1. Aplicar exclusivamente el esquema oficial existente (v001)
        runner = MigrationRunner(conn)
        runner.apply_all_pending()

        # 2. Confirmar que la restricción UNIQUE existe en el esquema SQLite
        cursor = conn.cursor()
        cursor.execute("PRAGMA index_list('participacion');")
        indexes = cursor.fetchall()
        has_unique = any(idx[2] == 1 for idx in indexes)  # unique == 1
        assert has_unique, "La tabla participacion debe poseer restricción de unicidad."

        # 3. Preparar repositorios y sembrar actividad inicial
        act_repo = SQLiteActividadRepository(conn)
        per_repo = SQLitePersonaRepository(conn)
        part_repo = SQLiteParticipacionRepository(conn)
        disc_repo = SQLiteDiscrepanciaRepository(conn)

        act_repo.save(Activity(
            id_actividad="act-sql-001",
            nombre_actividad_original="Taller Agroforestal",
            sede="BLUEFIELDS",
            fecha_evento="2026-09-17",
        ))

        # 4. Crear caso de uso con UoW real
        uow = SQLiteUnitOfWork(connection_manager=manager, db_path=db_file)
        use_case = IngestarListaAsistenciaUseCase(uow=uow)

        # 5. Ejecutar ingesta con dos apariciones de la misma persona en la misma actividad
        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-sql-001",
            fuente_archivo="lista_asistencia_taller.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Carlos Manuel Gomez",
                    cedula_fuente="601-150388-0004M",
                    categoria_sugerida="ESTUDIANTE",
                    observaciones_fuente="Turno Mañana",
                ),
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Carlos Manuel Gomez",
                    cedula_fuente="601-150388-0004M",
                    categoria_sugerida="ESTUDIANTE",
                    observaciones_fuente="Turno Tarde",
                ),
            ],
        )

        res = use_case.execute(cmd)

        # 6. Confirmar resultado del use case
        assert res.total_procesados == 2
        assert res.nuevas_personas_registradas == 1
        assert res.personas_existentes_vinculadas == 1
        assert res.participaciones_creadas == 1  # Solo 1 participación física creada
        assert res.participaciones_en_revision == 1

        # 7. Confirmar en SQLite que no hubo IntegrityError y ocurrió COMMIT
        cursor.execute("SELECT COUNT(*) FROM participacion WHERE id_actividad = 'act-sql-001';")
        assert cursor.fetchone()[0] == 1  # Exactamente 1 participación

        cursor.execute("SELECT requiere_revision, motivo_revision, carrera_o_cargo_actividad FROM participacion WHERE id_actividad = 'act-sql-001';")
        row = cursor.fetchone()
        assert row[0] == 1  # requiere_revision == True
        assert "Participación repetida" in row[1]
        assert "Turno Tarde" in row[2]  # observaciones enriquecidas
        assert "fila 2" in row[2]

        # 8. Confirmar que existe la Discrepancia en SQLite
        cursor.execute("SELECT COUNT(*) FROM discrepancia WHERE id_actividad = 'act-sql-001';")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT delta_valor, estado FROM discrepancia WHERE id_actividad = 'act-sql-001';")
        row_disc = cursor.fetchone()
        assert "Participación repetida" in row_disc[0]
        assert row_disc[1] == "REQUIERE_REVISION"

        # 9. Confirmar que PRAGMA integrity_check sigue 'ok'
        cursor.execute("PRAGMA integrity_check;")
        assert cursor.fetchone()[0] == "ok"

        # 10. Confirmar que un intento manual de insertar duplicado directo falla con IntegrityError (UNIQUE activo)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino) "
                "VALUES ('part-forzada', 'act-sql-001', (SELECT id_persona_interno FROM persona WHERE cedula = '601-150388-0004M'), 'ESTUDIANTE', 'M2');"
            )

        conn.close()

    def test_inmemory_participacion_repetida_no_lanza_integrity_error(self, repos):
        """Demuestra que la lógica en memoria también procesa la repetición sin error de integridad."""
        act_repo, per_repo, part_repo, disc_repo = repos
        use_case = IngestarListaAsistenciaUseCase(act_repo, per_repo, part_repo, disc_repo)

        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-base-001",
            fuente_archivo="lista_doble.xlsx",
            filas_participantes=[
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Rosa Parks Campbell",
                    cedula_fuente="601-010192-0001A",
                    categoria_sugerida="ESTUDIANTE",
                    observaciones_fuente="Mesa 1",
                ),
                FilaParticipanteIngestaDTO(
                    nombre_fuente="Rosa Parks Campbell",
                    cedula_fuente="601-010192-0001A",
                    categoria_sugerida="ESTUDIANTE",
                    observaciones_fuente="Mesa 2",
                ),
            ],
        )

        res = use_case.execute(cmd)
        assert res.total_procesados == 2
        assert res.participaciones_creadas == 1
        assert res.participaciones_en_revision == 1

        parts = part_repo.get_by_actividad("act-base-001")
        assert len(parts) == 1
        assert parts[0].requiere_revision is True
        assert "Mesa 2" in (parts[0].observaciones or "")

