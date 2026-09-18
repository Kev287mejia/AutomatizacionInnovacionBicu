"""Suite de Pruebas Automatizadas: Fase 26.5.1 - Routing Institucional.

Verifica de forma exhaustiva:
- CP-01 a CP-20: Matriz completa de soportabilidad funcional y técnica.
- Test específico del CHECK: NULL permitido + rechazo de valores inválidos ('M6', 'BLOQUEADOS', etc.).
- Test del Repositorio: Demostración de persistencia exacta sin inferencia heurística.
- Test de RoutingACL: Exclusión formal de M1 y traducción exacta Domain <-> Persistencia.
- Test E2E SQLite Real: Ingesta con NULL -> Routing Use Case -> Persistencia M2/M5.
"""

from datetime import date
from pathlib import Path
import pytest
import sqlite3
import tempfile
import uuid

from app.core.constants.participant_types import (
    CategoriaParticipacion,
    NivelValidacion,
)
from app.core.models import (
    Activity,
    Person,
    Participation,
    ValidationResult,
)
from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.repositories import (
    SQLiteActividadRepository,
    SQLitePersonaRepository,
    SQLiteParticipacionRepository,
    SQLiteUnitOfWork,
)
from app.routing.acl import RoutingACL
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.routing.participant_router import ParticipantRouter
from app.application.commands.participacion_commands import EnrutarParticipacionesCommand
from app.application.use_cases.participacion.enrutar_participaciones_actividad import (
    EnrutarParticipacionesActividadUseCase,
)


@pytest.fixture
def temp_db():
    """Crea una base de datos SQLite temporal en disco con v001 aplicada."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_routing_26_5_1.db"
        config = DatabaseConfig(db_path=db_path)
        manager = SQLiteConnectionManager(config)

        conn = manager.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending()
        finally:
            conn.close()

        yield manager, db_path


@pytest.fixture
def actividad_test():
    return Activity(
        id_actividad="act-routing-01",
        nombre_actividad_original="Taller Regional de Innovación y Tecnología",
        sede="Bilwi",
        fecha_evento="17/09/2026",
    )


@pytest.fixture
def persona_test():
    return Person(
        id_persona_interno="per-routing-01",
        nombre_completo="Carlos Morales Jarquín",
        cedula="601-120502-1001A",
        sexo_normalizado="MASCULINO",
        edad=24,
    )


# ==============================================================================
# PRUEBAS DEL CHECK CONSTRAINT Y PERSISTENCIA DIRECTA (SECCIONES 21 Y 22)
# ==============================================================================

class TestCheckConstraintYPersistenciaDirecta:
    """Valida que matriz_destino admita NULL y conserve su catálogo estricto."""

    def test_check_permite_null_en_matriz_destino(self, temp_db):
        """Verifica que el schema admita NULL en matriz_destino tras eliminar NOT NULL."""
        manager, _ = temp_db
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            act_repo.save(Activity(id_actividad="act-chk-1", nombre_actividad_original="Actividad Check"))
            per_repo.save(Person(id_persona_interno="per-chk-1", nombre_completo="Persona Check"))
            conn.commit()

            # Insertar participación con matriz_destino = NULL (pre-routing)
            conn.execute(
                "INSERT INTO participacion ("
                "   id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino"
                ") VALUES ('part-chk-null', 'act-chk-1', 'per-chk-1', 'ESTUDIANTE', NULL);"
            )
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT matriz_destino FROM participacion WHERE id_participacion = 'part-chk-null';")
            val = cursor.fetchone()[0]
            assert val is None, "matriz_destino debe ser NULL en SQLite antes del routing"
        finally:
            conn.close()

    def test_check_rechaza_valores_invalidos(self, temp_db):
        """Verifica que el CHECK continúe rechazando códigos fuera del catálogo ('M6', 'BLOQUEADOS', etc.)."""
        manager, _ = temp_db
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            act_repo.save(Activity(id_actividad="act-chk-2", nombre_actividad_original="Actividad Check 2"))
            per_repo.save(Person(id_persona_interno="per-chk-2", nombre_completo="Persona Check 2"))
            conn.commit()

            # 1. Rechaza 'M6'
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO participacion ("
                    "   id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino"
                    ") VALUES ('part-inv-1', 'act-chk-2', 'per-chk-2', 'ESTUDIANTE', 'M6');"
                )

            # 2. Rechaza 'BLOQUEADOS' (debe ser None/NULL en BD)
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO participacion ("
                    "   id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino"
                    ") VALUES ('part-inv-2', 'act-chk-2', 'per-chk-2', 'ESTUDIANTE', 'BLOQUEADOS');"
                )

            # 3. Rechaza 'DESTINO_INVALIDO'
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO participacion ("
                    "   id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino"
                    ") VALUES ('part-inv-3', 'act-chk-2', 'per-chk-2', 'ESTUDIANTE', 'DESTINO_INVALIDO');"
                )
        finally:
            conn.close()

    def test_repositorio_persistencia_directa_sin_inferencia_heuristica(self, temp_db):
        """Sección 22: Demuestra que el repositorio no infiere M2..M5 si matriz_destino es None."""
        manager, _ = temp_db
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            part_repo = SQLiteParticipacionRepository(conn)

            act = Activity(id_actividad="act-repo-01", nombre_actividad_original="Feria Científica")
            per = Person(id_persona_interno="per-repo-01", nombre_completo="María López")
            act_repo.save(act)
            per_repo.save(per)
            conn.commit()

            # A. Antes del routing: matriz_destino=None -> Debe persistirse como NULL en SQLite
            part_pre = Participation(
                id_participacion="part-repo-pre",
                id_actividad="act-repo-01",
                id_persona="per-repo-01",
                categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
                matriz_destino=None,
            )
            part_repo.save(part_pre)
            conn.commit()

            # Verificar en base de datos física
            cursor = conn.cursor()
            cursor.execute("SELECT matriz_destino FROM participacion WHERE id_participacion = 'part-repo-pre';")
            assert cursor.fetchone()[0] is None, "El repositorio no debe inferir M2 si matriz_destino es None"

            # Verificar recuperación vía entity
            entity_recuperada = part_repo.get_by_id("part-repo-pre")
            assert entity_recuperada.matriz_destino is None

            # B. Después del routing: matriz_destino="M2" -> Debe persistirse como "M2"
            part_pre.matriz_destino = "M2"
            part_repo.save(part_pre)
            conn.commit()

            cursor.execute("SELECT matriz_destino FROM participacion WHERE id_participacion = 'part-repo-pre';")
            assert cursor.fetchone()[0] == "M2"

            entity_recuperada_m2 = part_repo.get_by_id("part-repo-pre")
            assert entity_recuperada_m2.matriz_destino == "M2"

            # C. Equivalente para M5
            part_pre.matriz_destino = "M5"
            part_repo.save(part_pre)
            conn.commit()

            cursor.execute("SELECT matriz_destino FROM participacion WHERE id_participacion = 'part-repo-pre';")
            assert cursor.fetchone()[0] == "M5"
        finally:
            conn.close()


# ==============================================================================
# PRUEBAS DEL ROUTING ACL (SECCIÓN 15)
# ==============================================================================

class TestRoutingACL:
    """Verifica que RoutingACL traduzca exactamente y excluya formalmente a M1."""

    def test_routing_acl_traducciones_validas(self):
        assert RoutingACL.to_relational_code(MatrizDestino.ESTUDIANTES) == "M2"
        assert RoutingACL.to_relational_code(MatrizDestino.ACADEMICOS_ADMINISTRATIVOS) == "M3"
        assert RoutingACL.to_relational_code(MatrizDestino.COLABORADORES) == "M4"
        assert RoutingACL.to_relational_code(MatrizDestino.BENEFICIADOS) == "M5"
        assert RoutingACL.to_relational_code(MatrizDestino.COLA_REVISION) == "COLA_REVISION"
        assert RoutingACL.to_relational_code(MatrizDestino.BLOQUEADOS) is None

    def test_routing_acl_excluye_m1_consolidado(self):
        """M1 / CONSOLIDADO debe ser formalmente rechazado por RoutingACL."""
        with pytest.raises(ValueError, match="M1 / CONSOLIDADO no es un destino de routing nominal"):
            RoutingACL.to_relational_code(MatrizDestino.CONSOLIDADO)

        with pytest.raises(ValueError, match="M1 / CONSOLIDADO no es un destino de routing nominal"):
            RoutingACL.to_relational_code("M1")

        with pytest.raises(ValueError, match="M1 / CONSOLIDADO no es un destino de routing nominal"):
            RoutingACL.to_domain("M1")


# ==============================================================================
# CASOS DE PRUEBA CP-01 A CP-20 (SECCIÓN 20)
# ==============================================================================

class TestCasosPruebaCP01aCP20:
    """Matriz formal de casos de prueba CP-01 a CP-20."""

    def test_cp01_estudiante_a_m2(self, actividad_test, persona_test):
        """CP-01: Estudiante -> M2 (MatrizDestino.ESTUDIANTES)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.estudiantes) == 1
        assert res.estudiantes[0].matriz_destino == MatrizDestino.ESTUDIANTES
        assert res.estudiantes[0].subtipo_institucional == SubtipoInstitucional.NO_APLICA
        assert RoutingACL.to_relational_code(res.estudiantes[0].matriz_destino) == "M2"

    def test_cp02_docente_a_m3_academico(self, actividad_test, persona_test):
        """CP-02: Docente -> M3 (subtipo ACADEMICO)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.academicos_administrativos) == 1
        reg = res.academicos_administrativos[0]
        assert reg.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
        assert reg.subtipo_institucional == SubtipoInstitucional.ACADEMICO
        assert RoutingACL.to_relational_code(reg.matriz_destino) == "M3"

    def test_cp03_administrativo_a_m3_administrativo(self, actividad_test, persona_test):
        """CP-03: Administrativo -> M3 (subtipo ADMINISTRATIVO)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ADMINISTRATIVO,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.academicos_administrativos) == 1
        reg = res.academicos_administrativos[0]
        assert reg.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
        assert reg.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO
        assert RoutingACL.to_relational_code(reg.matriz_destino) == "M3"

    def test_cp04_no_docente_a_m3_administrativo_inmutable(self, actividad_test, persona_test):
        """CP-04: No Docente -> M3 (subtipo ADMINISTRATIVO) conservando categoría NO_DOCENTE inalterada."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.NO_DOCENTE,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.academicos_administrativos) == 1
        reg = res.academicos_administrativos[0]
        assert reg.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
        assert reg.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO
        assert reg.participacion.categoria_participacion == CategoriaParticipacion.NO_DOCENTE
        assert RoutingACL.to_relational_code(reg.matriz_destino) == "M3"

    def test_cp05_colaborador_a_m4(self, actividad_test, persona_test):
        """CP-05: Colaborador -> M4 (MatrizDestino.COLABORADORES)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.COLABORADOR,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.colaboradores) == 1
        assert res.colaboradores[0].matriz_destino == MatrizDestino.COLABORADORES
        assert RoutingACL.to_relational_code(res.colaboradores[0].matriz_destino) == "M4"

    def test_cp06_beneficiario_a_m5(self, actividad_test, persona_test):
        """CP-06: Beneficiario -> M5 (MatrizDestino.BENEFICIADOS)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion="BENEFICIARIO",
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.beneficiados) == 1
        assert res.beneficiados[0].matriz_destino == MatrizDestino.BENEFICIADOS
        assert RoutingACL.to_relational_code(res.beneficiados[0].matriz_destino) == "M5"

    def test_cp07_poblador_general_a_m5(self, actividad_test, persona_test):
        """CP-07: Poblador general -> M5 (MatrizDestino.BENEFICIADOS)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.POBLADOR_GENERAL,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.beneficiados) == 1
        assert res.beneficiados[0].matriz_destino == MatrizDestino.BENEFICIADOS
        assert RoutingACL.to_relational_code(res.beneficiados[0].matriz_destino) == "M5"

    def test_cp08_emprendedor_a_m5(self, actividad_test, persona_test):
        """CP-08: Emprendedor -> M5 (MatrizDestino.BENEFICIADOS)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion="EMPRENDEDOR",
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.beneficiados) == 1
        assert res.beneficiados[0].matriz_destino == MatrizDestino.BENEFICIADOS
        assert RoutingACL.to_relational_code(res.beneficiados[0].matriz_destino) == "M5"

    def test_cp09_estudiante_mas_beneficiario_rol_a_m5_rnc03(self, actividad_test, persona_test):
        """CP-09 (RN-C03): Estudiante con es_beneficiado_rol=True prevalece hacia M5."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            es_beneficiado_rol=True,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.beneficiados) == 1
        assert len(res.estudiantes) == 0
        reg = res.beneficiados[0]
        assert reg.matriz_destino == MatrizDestino.BENEFICIADOS
        # La categoría original permanece ESTUDIANTE (inmutabilidad)
        assert reg.participacion.categoria_participacion == CategoriaParticipacion.ESTUDIANTE
        assert reg.participacion.es_beneficiado_rol is True
        assert RoutingACL.to_relational_code(reg.matriz_destino) == "M5"

    def test_cp10_desconocido_a_cola_revision(self, actividad_test, persona_test):
        """CP-10: Desconocido -> COLA_REVISION (no se adivina matriz)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DESCONOCIDO,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.cola_revision) == 1
        reg = res.cola_revision[0]
        assert reg.matriz_destino == MatrizDestino.COLA_REVISION
        assert reg.estado_operativo == "EN_REVISION"
        assert RoutingACL.to_relational_code(reg.matriz_destino) == "COLA_REVISION"

    def test_cp11_incidencia_documental_matriz_natural_mas_en_revision(self, actividad_test, persona_test):
        """CP-11: Incidencia documental -> Matriz natural + EN_REVISION (no a COLA_REVISION)."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
            requiere_revision=True,
            motivo_revision="Falta cédula física escaneada",
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        assert len(res.academicos_administrativos) == 1
        assert len(res.cola_revision) == 0
        reg = res.academicos_administrativos[0]
        assert reg.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
        assert reg.estado_operativo == "EN_REVISION"

    def test_cp12_error_critico_o_huerfano_a_bloqueado(self, actividad_test):
        """CP-12: Error crítico o referencia huérfana -> BLOQUEADO con matriz_destino None."""
        part_huerfana = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona="per-inexistente-huerfana",
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        res = ParticipantRouter.enrutar([actividad_test], [], [part_huerfana])
        assert len(res.bloqueados) == 1
        reg = res.bloqueados[0]
        assert reg.estado_operativo == "BLOQUEADO"
        assert reg.matriz_destino == MatrizDestino.BLOQUEADOS
        # ACL debe traducir BLOQUEADOS a None sin inventar código relacional
        assert RoutingACL.to_persistence(reg) is None

    def test_cp13_ingesta_genera_matriz_destino_none(self, actividad_test, persona_test):
        """CP-13: Ingesta -> Participation.matriz_destino es None por defecto."""
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
        )
        assert part.matriz_destino is None, "Durante la ingesta, matriz_destino debe ser None"

    def test_cp14_routing_persiste_destino(self, temp_db, actividad_test, persona_test):
        """CP-14: Routing -> Destino asignado y persistido correctamente en SQLite."""
        manager, _ = temp_db
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            part_repo = SQLiteParticipacionRepository(conn)

            act_repo.save(actividad_test)
            per_repo.save(persona_test)
            conn.commit()

            part = Participation(
                id_participacion="part-cp14",
                id_actividad=actividad_test.id_actividad,
                id_persona=persona_test.id_persona_interno,
                categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
                matriz_destino=None,
            )
            part_repo.save(part)
            conn.commit()

            use_case = EnrutarParticipacionesActividadUseCase(
                participacion_repo=part_repo,
                actividad_repo=act_repo,
                persona_repo=per_repo,
            )
            res_dto = use_case.execute(EnrutarParticipacionesCommand(id_actividad=actividad_test.id_actividad))
            conn.commit()

            assert res_dto.total_m2_estudiantes == 1
            part_actualizada = part_repo.get_by_id("part-cp14")
            assert part_actualizada.matriz_destino == "M2"
        finally:
            conn.close()

    def test_cp15_en_revision_conserva_motivo_revision(self, actividad_test, persona_test):
        """CP-15: EN_REVISION conserva intacto su motivo_revision original."""
        motivo_esperado = "Requiere confirmación de título profesional"
        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
            requiere_revision=True,
            motivo_revision=motivo_esperado,
        )
        res = ParticipantRouter.enrutar([actividad_test], [persona_test], [part])
        reg = res.academicos_administrativos[0]
        assert reg.participacion.motivo_revision == motivo_esperado

    def test_cp16_cola_revision_solamente_cuando_no_es_determinable(self, actividad_test, persona_test):
        """CP-16: COLA_REVISION solo se activa cuando no existe destino determinable."""
        part_docente_alerta = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
            requiere_revision=True,
            motivo_revision="Alerta menor",
        )
        part_desconocido = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona=persona_test.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DESCONOCIDO,
        )
        res = ParticipantRouter.enrutar(
            [actividad_test],
            [persona_test],
            [part_docente_alerta, part_desconocido]
        )
        assert len(res.cola_revision) == 1
        assert res.cola_revision[0].participacion.categoria_participacion == CategoriaParticipacion.DESCONOCIDO
        assert len(res.academicos_administrativos) == 1

    def test_cp17_invariante_de_conservacion(self, actividad_test):
        """CP-17: Invariante: Entrada == M2 + M3 + M4 + M5 + COLA_REVISION + BLOQUEADOS."""
        p1 = Person(id_persona_interno="p-1", nombre_completo="P1")
        p2 = Person(id_persona_interno="p-2", nombre_completo="P2")
        p3 = Person(id_persona_interno="p-3", nombre_completo="P3")
        p4 = Person(id_persona_interno="p-4", nombre_completo="P4")
        p5 = Person(id_persona_interno="p-5", nombre_completo="P5")

        participaciones = [
            Participation(id_actividad=actividad_test.id_actividad, id_persona="p-1", categoria_participacion="ESTUDIANTE"),
            Participation(id_actividad=actividad_test.id_actividad, id_persona="p-2", categoria_participacion="DOCENTE"),
            Participation(id_actividad=actividad_test.id_actividad, id_persona="p-3", categoria_participacion="COLABORADOR"),
            Participation(id_actividad=actividad_test.id_actividad, id_persona="p-4", categoria_participacion="BENEFICIARIO"),
            Participation(id_actividad=actividad_test.id_actividad, id_persona="p-5", categoria_participacion="DESCONOCIDO"),
            Participation(id_actividad=actividad_test.id_actividad, id_persona="p-inexistente", categoria_participacion="ESTUDIANTE"),
        ]

        res = ParticipantRouter.enrutar([actividad_test], [p1, p2, p3, p4, p5], participaciones)
        assert res.total_entrada == 6
        assert res.total_clasificadas == 6
        assert res.invariante_valida is True
        assert len(res.estudiantes) == 1
        assert len(res.academicos_administrativos) == 1
        assert len(res.colaboradores) == 1
        assert len(res.beneficiados) == 1
        assert len(res.cola_revision) == 1
        assert len(res.bloqueados) == 1

    def test_cp18_router_no_modifica_person(self, actividad_test):
        """CP-18: Router no modifica la entidad Person."""
        persona = Person(
            id_persona_interno="per-inmutable",
            nombre_completo="Rigoberto Pérez",
            cedula="601-111111-0001A",
            sexo_normalizado="MASCULINO",
            edad=30,
        )
        persona_dict_antes = persona.model_dump()

        part = Participation(
            id_actividad=actividad_test.id_actividad,
            id_persona="per-inmutable",
            categoria_participacion=CategoriaParticipacion.DOCENTE,
        )
        ParticipantRouter.enrutar([actividad_test], [persona], [part])

        assert persona.model_dump() == persona_dict_antes, "La entidad Person debe permanecer estrictamente inalterada"

    def test_cp19_participacion_repetida_sigue_siendo_unica(self, temp_db, actividad_test, persona_test):
        """CP-19: La combinación id_actividad + id_persona sigue gobernada por UNIQUE(id_actividad, id_persona)."""
        manager, _ = temp_db
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            act_repo.save(actividad_test)
            per_repo.save(persona_test)
            conn.commit()

            conn.execute(
                "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino) "
                "VALUES ('part-rep-1', ?, ?, 'ESTUDIANTE', 'M2');",
                (actividad_test.id_actividad, persona_test.id_persona_interno)
            )
            conn.commit()

            # Un segundo intento de inserción con la misma actividad y persona debe violar la restricción UNIQUE
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino) "
                    "VALUES ('part-rep-2', ?, ?, 'ESTUDIANTE', 'M2');",
                    (actividad_test.id_actividad, persona_test.id_persona_interno)
                )
        finally:
            conn.close()

    def test_cp20_sqlite_end_to_end_ingesta_null_routing_persistencia(self, temp_db):
        """CP-20: Flujo SQLite end-to-end: Ingesta (matriz_destino=NULL) -> Use Case Routing -> Persistencia M2 y M5."""
        manager, db_path = temp_db
        uow = SQLiteUnitOfWork(connection_manager=manager, db_path=db_path)

        # 1. Crear actividad y personas dentro de la transacción UoW
        act = Activity(id_actividad="act-e2e-20", nombre_actividad_original="Encuentro de Emprendedores")
        p_estudiante = Person(id_persona_interno="per-e2e-1", nombre_completo="Ana López")
        p_beneficiado = Person(id_persona_interno="per-e2e-2", nombre_completo="Pedro Castillo")

        # 2. Ingesta: participaciones persistidas inicialmente con matriz_destino = None (NULL en SQLite)
        part1 = Participation(
            id_participacion="part-e2e-1",
            id_actividad="act-e2e-20",
            id_persona="per-e2e-1",
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            matriz_destino=None,
        )
        part2 = Participation(
            id_participacion="part-e2e-2",
            id_actividad="act-e2e-20",
            id_persona="per-e2e-2",
            categoria_participacion=CategoriaParticipacion.BENEFICIADO,
            matriz_destino=None,
        )

        with uow:
            uow.actividades.save(act)
            uow.personas.save(p_estudiante)
            uow.personas.save(p_beneficiado)
            uow.participaciones.save(part1)
            uow.participaciones.save(part2)
            uow.commit()

        # 3. Verificar que en SQLite físico están en NULL
        conn = manager.get_connection(db_path=db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id_participacion, matriz_destino FROM participacion WHERE id_actividad = 'act-e2e-20';")
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert all(r[1] is None for r in rows), "Todas las participaciones deben tener matriz_destino=NULL tras la ingesta"
        conn.close()

        # 4. Ejecutar Use Case de Routing
        use_case = EnrutarParticipacionesActividadUseCase(uow=uow)
        res = use_case.execute(EnrutarParticipacionesCommand(id_actividad="act-e2e-20"))

        assert res.total_participaciones == 2
        assert res.total_m2_estudiantes == 1
        assert res.total_m5_beneficiados == 1
        assert res.invariante_conservacion_valida is True

        # 5. Verificar que en SQLite físico las columnas fueron actualizadas a M2 y M5 sin IntegrityError
        conn2 = manager.get_connection(db_path=db_path)
        try:
            cursor2 = conn2.cursor()
            cursor2.execute(
                "SELECT id_participacion, matriz_destino FROM participacion "
                "WHERE id_actividad = 'act-e2e-20' ORDER BY id_participacion;"
            )
            rows_post = cursor2.fetchall()
            assert (rows_post[0]["id_participacion"], rows_post[0]["matriz_destino"]) == ("part-e2e-1", "M2")
            assert (rows_post[1]["id_participacion"], rows_post[1]["matriz_destino"]) == ("part-e2e-2", "M5")

            # 6. Integridad de la base de datos
            cursor2.execute("PRAGMA integrity_check;")
            assert cursor2.fetchone()[0] == "ok"
            cursor2.execute("PRAGMA foreign_key_check;")
            assert len(cursor2.fetchall()) == 0
        finally:
            conn2.close()
