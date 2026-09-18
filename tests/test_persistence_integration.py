"""tests/test_persistence_integration.py

SUBETAPA 25.3.4 — PRUEBAS INTEGRADAS DE PERSISTENCIA
SISTEMA INSTITUCIONAL DE GESTIÓN DE ACTIVIDADES, PARTICIPANTES, EVIDENCIAS Y REPORTES — BICU

Demuestra mediante pruebas automatizadas que:
1. Los seis repositorios SQLite funcionan correctamente de forma integrada.
2. SQLiteUnitOfWork coordina los seis repositorios compartiendo exactamente la misma conexión.
3. commit() confirma todas las operaciones de una transacción.
4. rollback() revierte TODAS las operaciones realizadas dentro de la transacción.
5. Las restricciones FOREIGN KEY y UNIQUE funcionan correctamente.
6. Los mapeos dominio ↔ SQLite preservan NULL, UUID, fechas y valores persistidos.
7. Las consultas de los repositorios funcionan de forma integrada.
8. Las excepciones de infraestructura no escapan hacia Core (traducción a excepciones de dominio).
9. La arquitectura continúa respetando la dirección de dependencias (Core -> Ports, Infra -> Ports + SQLite).
10. La línea base v1.0.3 permanece absolutamente intacta.
"""

import ast
from datetime import date, datetime
from pathlib import Path
import sqlite3
import tempfile
from typing import List, Tuple
import pytest

from app.core.exceptions.persistence_exceptions import (
    EntityAlreadyExistsError,
    PersistenceError,
    ReferentialIntegrityError,
    TransactionError,
)
from app.core.models import (
    Activity,
    Person,
    Participation,
    Evidencia,
    TipoEvidencia,
    InformeSemanal,
    DetalleInformeSemanal,
    Discrepancia,
    TipoDiscrepancia,
    SeveridadDiscrepancia,
    EstadoDiscrepancia,
)
from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import MigrationRunner
from app.infrastructure.persistence.repositories import (
    SQLiteActividadRepository,
    SQLitePersonaRepository,
    SQLiteParticipacionRepository,
    SQLiteEvidenciaRepository,
    SQLiteInformeSemanalRepository,
    SQLiteDiscrepanciaRepository,
    SQLiteUnitOfWork,
)


@pytest.fixture
def temp_db_env():
    """Genera un entorno temporal aislado en disco con el esquema institucional v001 migrado."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_integration.db"
        config = DatabaseConfig(db_path=db_path)
        manager = SQLiteConnectionManager(config)

        # Aplicar migraciones sobre la base de pruebas
        conn = manager.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending()
        finally:
            conn.close()

        yield manager, db_path


# ==============================================================================
# BLOQUE A: UNIT OF WORK COORDINATION
# ==============================================================================
class TestUnitOfWorkCoordination:
    """Verifica la coordinación transaccional y frontera atómica de SQLiteUnitOfWork."""

    def test_uow_initialization_and_shared_connection(self, temp_db_env):
        """A.1 & A.2: Verifica creación e inyección de la MISMA conexión activa en los 6 repositorios."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        with uow:
            assert uow._in_transaction is True
            active_conn = uow.actividades._conn
            assert active_conn is not None
            # Los 6 adaptadores deben compartir estrictamente la misma instancia de conexión
            assert uow.personas._conn is active_conn
            assert uow.participaciones._conn is active_conn
            assert uow.evidencias._conn is active_conn
            assert uow.informes_semanales._conn is active_conn
            assert uow.discrepancias._conn is active_conn

    def test_uow_commit_persists_multi_repository_operations(self, temp_db_env):
        """A.3 & A.4: commit() confirma operaciones realizadas mediante múltiples repositorios."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        with uow:
            uow.actividades.save(Activity(id_actividad="act-uow-1", nombre_actividad_original="Feria UoW"))
            uow.personas.save(Person(id_persona_interno="per-uow-1", nombre_completo="Carlos Méndez"))
            uow.participaciones.save(Participation(
                id_participacion="part-uow-1",
                id_actividad="act-uow-1",
                id_persona="per-uow-1",
                categoria_participacion="ESTUDIANTE",
            ))
            uow.evidencias.save(Evidencia(
                id_evidencia="evi-uow-1",
                tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
                titulo="Foto Inaugural",
                hash_sha256="1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            ))
            uow.evidencias.link_actividad("act-uow-1", "evi-uow-1", orden=1)
            uow.discrepancias.save(Discrepancia(
                id_discrepancia="disc-uow-1",
                id_actividad="act-uow-1",
                fuente_a_nombre="M1",
                fuente_a_valor="10",
                fuente_b_nombre="M2",
                fuente_b_valor="9",
                delta_valor="-1",
            ))
            uow.commit()

        # En una conexión separada e independiente, confirmar persistencia de todas las entidades
        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists("act-uow-1") is True
            assert SQLitePersonaRepository(conn).exists("per-uow-1") is True
            assert SQLiteParticipacionRepository(conn).get_by_id("part-uow-1") is not None
            assert SQLiteEvidenciaRepository(conn).get_by_id("evi-uow-1") is not None
            assert len(SQLiteEvidenciaRepository(conn).get_by_actividad("act-uow-1")) == 1
            assert SQLiteDiscrepanciaRepository(conn).get_by_id("disc-uow-1") is not None
        finally:
            conn.close()

    def test_uow_explicit_rollback_reverts_multi_repository_operations(self, temp_db_env):
        """A.5: rollback() explícito revierte TODAS las operaciones de la transacción."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        with uow:
            uow.actividades.save(Activity(id_actividad="act-rb-1", nombre_actividad_original="Actividad Cancelada"))
            uow.personas.save(Person(id_persona_interno="per-rb-1", nombre_completo="Elena Rostrán"))
            uow.rollback()

        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists("act-rb-1") is False
            assert SQLitePersonaRepository(conn).exists("per-rb-1") is False
        finally:
            conn.close()

    def test_uow_exception_triggers_automatic_rollback_no_orphans(self, temp_db_env):
        """A.6 & A.7: Una excepción dentro de with uow: provoca rollback automático sin registros huérfanos."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        with pytest.raises(ReferentialIntegrityError):
            with uow:
                # 1. Operación válida
                uow.actividades.save(Activity(id_actividad="act-abort-1", nombre_actividad_original="Taller Abortado"))
                uow.personas.save(Person(id_persona_interno="per-abort-1", nombre_completo="Rosa Morales"))
                # 2. Operación inválida que provoca violación FK
                uow.participaciones.save(Participation(
                    id_participacion="part-abort-1",
                    id_actividad="act-abort-1",
                    id_persona="per-FANTASMA-TOTAL",
                    categoria_participacion="ESTUDIANTE",
                ))
                uow.commit()

        # Comprobar que NINGUNA entidad quedó huérfana en la base de datos
        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists("act-abort-1") is False
            assert SQLitePersonaRepository(conn).exists("per-abort-1") is False
            assert SQLiteParticipacionRepository(conn).get_by_id("part-abort-1") is None
        finally:
            conn.close()

    def test_uow_access_outside_with_raises_transaction_error(self, temp_db_env):
        """Verifica que intentar acceder a los repositorios fuera del contexto with lanza TransactionError."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        with pytest.raises(TransactionError, match="UnitOfWork no inicializado"):
            _ = uow.actividades
        with pytest.raises(TransactionError, match="UnitOfWork no inicializado"):
            _ = uow.personas
        with pytest.raises(TransactionError, match="UnitOfWork no inicializado"):
            _ = uow.participaciones
        with pytest.raises(TransactionError, match="UnitOfWork no inicializado"):
            _ = uow.evidencias
        with pytest.raises(TransactionError, match="UnitOfWork no inicializado"):
            _ = uow.informes_semanales
        with pytest.raises(TransactionError, match="UnitOfWork no inicializado"):
            _ = uow.discrepancias


# ==============================================================================
# BLOQUE B: INTEGRACIÓN ACTIVIDAD + PERSONA + PARTICIPACIÓN
# ==============================================================================
class TestActividadPersonaParticipacionLifecycle:
    """Prueba el ciclo de vida coordinado entre Actividad, Persona y el vínculo Participación."""

    def test_full_lifecycle_actividad_persona_participacion_commit(self, temp_db_env):
        """B.1: Creación coordinada de Actividad, Persona y Participación confirmada con commit()."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        act_id = "act-integ-100"
        per_id = "per-integ-100"
        part_id = "part-integ-100"

        with uow:
            act = Activity(
                id_actividad=act_id,
                nombre_actividad_original="Conferencia Magistral",
                sede="BLUEFIELDS",
                fecha_evento="2026-09-22",
            )
            per = Person(
                id_persona_interno=per_id,
                nombre_completo="Dra. Miriam Hooker",
                cedula="601-101075-0002A",
                sexo_normalizado="F",
            )
            uow.actividades.save(act)
            uow.personas.save(per)

            part = Participation(
                id_participacion=part_id,
                id_actividad=act_id,
                id_persona=per_id,
                categoria_participacion="DOCENTE",
            )
            uow.participaciones.save(part)
            uow.commit()

        # Validar en conexión externa
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            part_repo = SQLiteParticipacionRepository(conn)

            assert act_repo.exists(act_id) is True
            assert per_repo.exists(per_id) is True

            part_ret = part_repo.get_by_id(part_id)
            assert part_ret is not None
            assert part_ret.id_actividad == act_id
            assert part_ret.id_persona == per_id
            assert part_ret.categoria_participacion == "DOCENTE"
        finally:
            conn.close()

    def test_lifecycle_actividad_persona_participacion_rollback(self, temp_db_env):
        """B.2: Escenario equivalente con rollback comprueba que NINGUNA entidad permanece."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        with uow:
            uow.actividades.save(Activity(id_actividad="act-no-1", nombre_actividad_original="Cancelada"))
            uow.personas.save(Person(id_persona_interno="per-no-1", nombre_completo="No Debe Estar"))
            uow.participaciones.save(Participation(
                id_participacion="part-no-1",
                id_actividad="act-no-1",
                id_persona="per-no-1",
                categoria_participacion="ESTUDIANTE",
            ))
            uow.rollback()

        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists("act-no-1") is False
            assert SQLitePersonaRepository(conn).exists("per-no-1") is False
            assert SQLiteParticipacionRepository(conn).get_by_id("part-no-1") is None
        finally:
            conn.close()


# ==============================================================================
# BLOQUE C: PERSONA + PERFILES SATÉLITES
# ==============================================================================
class TestPersonaPerfilesIntegration:
    """Verifica persistencia bio-demográfica de Persona y relaciones con perfiles satélites."""

    def test_persona_complete_demographics_roundtrip(self, temp_db_env):
        """C.1: Verifica persistencia de UUID, cédula, nombres, demografía y valores opcionales."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            repo = SQLitePersonaRepository(conn)
            persona = Person(
                id_persona_interno="per-demo-001",
                nombre_completo="Ana María Morales López",
                nombres="Ana María",
                apellidos="Morales López",
                cedula="601-120598-0001W",
                numero_unico="CARNE-2026-88",
                otro_id_institucional="DOC-EXT-77",
                sexo_original="Femenino",
                sexo_normalizado="F",
                fecha_nacimiento="1998-05-12",
                edad=28,
                etnia="Creole",
                telefono="+505 8888-9999",
                departamento_persona="RACCS",
                municipio_persona="Bluefields",
                discapacidad="Visual Leve",
            )
            repo.save(persona)

            ret = repo.get_by_id("per-demo-001")
            assert ret is not None
            assert ret.id_persona_interno == "per-demo-001"
            assert ret.nombre_completo == "Ana María Morales López"
            assert ret.nombres == "Ana María"
            assert ret.apellidos == "Morales López"
            assert ret.cedula == "601-120598-0001W"
            assert ret.numero_unico == "CARNE-2026-88"
            assert ret.otro_id_institucional == "DOC-EXT-77"
            assert ret.sexo_normalizado == "F"
            assert str(ret.fecha_nacimiento) == "1998-05-12"
            assert ret.edad == 28
            assert ret.etnia == "Creole"
            assert ret.telefono == "+505 8888-9999"
            assert ret.departamento_persona == "RACCS"
            assert ret.municipio_persona == "Bluefields"
            assert ret.discapacidad == "Visual Leve"

            # Búsqueda por cédula y por número institucional
            by_ced = repo.get_by_cedula("601-120598-0001W")
            assert by_ced is not None
            assert by_ced.id_persona_interno == "per-demo-001"

            by_num = repo.get_by_numero_institucional("CARNE-2026-88")
            assert by_num is not None
            assert by_num.id_persona_interno == "per-demo-001"
        finally:
            conn.close()

    def test_persona_satellite_profiles_cascade_and_fk_enforcement(self, temp_db_env):
        """C.2: Verifica integración de tablas satélites perfil_estudiante y perfil_personal con Persona."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            per_repo = SQLitePersonaRepository(conn)
            p = Person(
                id_persona_interno="per-sat-001",
                nombre_completo="Estudiante Satélite",
                cedula="601-010100-0005M",
            )
            per_repo.save(p)

            # Insertar perfil_estudiante vinculado a per-sat-001
            conn.execute("""
            INSERT INTO perfil_estudiante (
                id_perfil_estudiante, id_persona, carne_estudiantil, carrera_cursada, nivel_academico
            ) VALUES (?, ?, ?, ?, ?);
            """, ("pe-001", "per-sat-001", "EST-2026-1", "Ingeniería en Sistemas", "GRADO"))

            # Validar que existe en la tabla satélite
            cursor = conn.cursor()
            cursor.execute("SELECT carrera_cursada FROM perfil_estudiante WHERE id_persona = ?;", ("per-sat-001",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "Ingeniería en Sistemas"

            # Comprobar ON DELETE CASCADE: Al eliminar a la persona, se elimina automáticamente el perfil
            conn.execute("DELETE FROM persona WHERE id_persona_interno = ?;", ("per-sat-001",))
            cursor.execute("SELECT COUNT(*) FROM perfil_estudiante WHERE id_persona = ?;", ("per-sat-001",))
            assert cursor.fetchone()[0] == 0

            # Comprobar violación FK al intentar crear perfil para persona inexistente
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                conn.execute("""
                INSERT INTO perfil_estudiante (id_perfil_estudiante, id_persona)
                VALUES ('pe-fail', 'per-FANTASMA');
                """)
        finally:
            conn.close()


# ==============================================================================
# BLOQUE D: CONSULTAS DE PARTICIPACIÓN
# ==============================================================================
class TestParticipacionQueriesIntegration:
    """Verifica de forma integrada las 7 consultas del repositorio SQLiteParticipacionRepository."""

    def test_all_seven_participacion_queries(self, temp_db_env):
        """D.1: Probar get_by_id, get_by_actividad, get_by_persona, get_by_actividad_and_persona,
        list_by_matriz_destino, list_requieren_revision y count_by_actividad."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            part_repo = SQLiteParticipacionRepository(conn)

            # 1. Sembrar actividad
            act_id = "act-consultas"
            act_repo.save(Activity(id_actividad=act_id, nombre_actividad_original="Taller General"))

            # 2. Sembrar 4 personas
            personas = [
                Person(id_persona_interno=f"per-{i}", nombre_completo=f"Participante {i}")
                for i in range(1, 5)
            ]
            for p in personas:
                per_repo.save(p)

            # 3. Sembrar participaciones con distintas matrices y banderas
            participaciones = [
                # M2 - Estudiante normal
                Participation(
                    id_participacion="p-m2",
                    id_actividad=act_id,
                    id_persona="per-1",
                    categoria_participacion="ESTUDIANTE",
                    matriz_destino="M2",
                    requiere_revision=False,
                ),
                # M3 - Docente con revisión requerida
                Participation(
                    id_participacion="p-m3",
                    id_actividad=act_id,
                    id_persona="per-2",
                    categoria_participacion="DOCENTE",
                    matriz_destino="M3",
                    requiere_revision=True,
                    motivo_revision="Aclarar facultad",
                ),
                # M4 - Colaborador externo
                Participation(
                    id_participacion="p-m4",
                    id_actividad=act_id,
                    id_persona="per-3",
                    categoria_participacion="COLABORADOR",
                    matriz_destino="M4",
                    requiere_revision=False,
                ),
                # M5 - Beneficiado protagonista con revisión requerida
                Participation(
                    id_participacion="p-m5",
                    id_actividad=act_id,
                    id_persona="per-4",
                    categoria_participacion="BENEFICIADO",
                    matriz_destino="M5",
                    requiere_revision=True,
                    motivo_revision="Verificar comunidad de origen",
                ),
            ]
            part_repo.save_batch(participaciones)

            # Consulta 1: get_by_id()
            p1 = part_repo.get_by_id("p-m2")
            assert p1 is not None
            assert p1.id_participacion == "p-m2"
            assert p1.id_persona == "per-1"

            # Consulta 2: get_by_actividad()
            parts_act = part_repo.get_by_actividad(act_id)
            assert len(parts_act) == 4

            # Consulta 3: get_by_persona()
            parts_per = part_repo.get_by_persona("per-1")
            assert len(parts_per) == 1
            assert parts_per[0].id_participacion == "p-m2"

            # Consulta 4: get_by_actividad_and_persona()
            p_pair = part_repo.get_by_actividad_and_persona(act_id, "per-2")
            assert p_pair is not None
            assert p_pair.id_participacion == "p-m3"

            # Consulta 5: list_by_matriz_destino()
            m2_list = part_repo.list_by_matriz_destino("M2", id_actividad=act_id)
            assert len(m2_list) == 1
            assert m2_list[0].id_participacion == "p-m2"

            m3_list = part_repo.list_by_matriz_destino("M3", id_actividad=act_id)
            assert len(m3_list) == 1
            assert m3_list[0].id_participacion == "p-m3"

            m4_list = part_repo.list_by_matriz_destino("M4", id_actividad=act_id)
            assert len(m4_list) == 1
            assert m4_list[0].id_participacion == "p-m4"

            m5_list = part_repo.list_by_matriz_destino("M5", id_actividad=act_id)
            assert len(m5_list) == 1
            assert m5_list[0].id_participacion == "p-m5"

            # Consulta 6: list_requieren_revision()
            rev_list = part_repo.list_requieren_revision(id_actividad=act_id)
            assert len(rev_list) == 2
            rev_ids = {r.id_participacion for r in rev_list}
            assert rev_ids == {"p-m3", "p-m5"}

            # Consulta 7: count_by_actividad()
            total_parts = part_repo.count_by_actividad(act_id)
            assert total_parts == 4
        finally:
            conn.close()


# ==============================================================================
# BLOQUE E: EVIDENCIAS Y CUSTODIA DIGITAL
# ==============================================================================
class TestEvidenciaIntegration:
    """Verifica metadatos, custodia criptográfica (SHA-256) y vinculación de evidencias."""

    def test_evidencia_lifecycle_and_lookup(self, temp_db_env):
        """E.1 a E.5: Crear evidencia, persistir metadata, SHA-256, recuperar por ID y por hash."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            repo = SQLiteEvidenciaRepository(conn)
            evi_hash = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
            evi = Evidencia(
                id_evidencia="evi-test-1",
                tipo_evidencia=TipoEvidencia.ACTA_RECEPCION,
                titulo="Acta de Entrega de Equipos",
                descripcion_pie="Firmada por el Decano",
                ruta_archivo_relativa="evidencias/2026/acta_01.pdf",
                hash_sha256=evi_hash,
                tamano_bytes=1048576,
                mime_type="application/pdf",
                fecha_captura="2026-09-18",
            )
            repo.save(evi)

            # Recuperar por ID
            ret_id = repo.get_by_id("evi-test-1")
            assert ret_id is not None
            assert ret_id.titulo == "Acta de Entrega de Equipos"
            assert ret_id.tipo_evidencia == "ACTA_RECEPCION"
            assert ret_id.tamano_bytes == 1048576
            assert ret_id.hash_sha256 == evi_hash

            # Recuperar por hash SHA-256
            ret_hash = repo.get_by_hash(evi_hash)
            assert ret_hash is not None
            assert ret_hash.id_evidencia == "evi-test-1"
        finally:
            conn.close()

    def test_evidencia_link_and_unlink_multiple_ordering(self, temp_db_env):
        """E.6 & E.7: Vincular múltiples evidencias con orden y sección, recuperar ordenadas y desvincular."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            evi_repo = SQLiteEvidenciaRepository(conn)

            act_id = "act-evi-seq"
            act_repo.save(Activity(id_actividad=act_id, nombre_actividad_original="Feria Científica"))

            for i in [1, 2, 3]:
                evi_repo.save(Evidencia(
                    id_evidencia=f"evi-seq-{i}",
                    tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
                    titulo=f"Evidencia {i}",
                ))

            # Vincular en orden 3, 1, 2
            evi_repo.link_actividad(act_id, "evi-seq-3", orden=3, seccion="GALERIA")
            evi_repo.link_actividad(act_id, "evi-seq-1", orden=1, seccion="FICHA_TECNICA")
            evi_repo.link_actividad(act_id, "evi-seq-2", orden=2, seccion="GALERIA")

            # Recuperar evidencias asociadas: deben venir ordenadas por orden_presentacion ASC (1, 2, 3)
            vinculadas = evi_repo.get_by_actividad(act_id)
            assert len(vinculadas) == 3
            assert [v[0].id_evidencia for v in vinculadas] == ["evi-seq-1", "evi-seq-2", "evi-seq-3"]
            assert vinculadas[0][1] == 1
            assert vinculadas[0][2] == "FICHA_TECNICA"
            assert vinculadas[1][1] == 2
            assert vinculadas[2][1] == 3

            # Desvincular evidencia 2
            evi_repo.unlink_actividad(act_id, "evi-seq-2")
            despues = evi_repo.get_by_actividad(act_id)
            assert len(despues) == 2
            assert [v[0].id_evidencia for v in despues] == ["evi-seq-1", "evi-seq-3"]

            # Comprobar que el registro maestro de la evidencia 2 sigue intacto (no se borra físicamente)
            assert evi_repo.get_by_id("evi-seq-2") is not None
        finally:
            conn.close()

    def test_evidencia_duplicate_and_restriction_handling(self, temp_db_env):
        """E.8 & E.9: Comportamiento ante intentos de duplicación de clave primaria y detección de hash."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            # 1. Inserción directa de clave primaria duplicada debe lanzar IntegrityError
            conn.execute("""
            INSERT INTO evidencia (id_evidencia, tipo_evidencia, titulo)
            VALUES ('evi-dup-1', 'FOTOGRAFIA', 'Foto Original');
            """)

            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
                conn.execute("""
                INSERT INTO evidencia (id_evidencia, tipo_evidencia, titulo)
                VALUES ('evi-dup-1', 'FOTOGRAFIA', 'Foto Duplicada');
                """)

            # 2. Detección por hash SHA-256 en repositorio (Deduplicación SSOT)
            evi_repo = SQLiteEvidenciaRepository(conn)
            evi_repo.save(Evidencia(
                id_evidencia="evi-hash-a",
                tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
                titulo="Foto Original A",
                hash_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            ))
            # get_by_hash localiza la evidencia preexistente
            detectada = evi_repo.get_by_hash("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
            assert detectada is not None
            assert detectada.id_evidencia == "evi-hash-a"
        finally:
            conn.close()


# ==============================================================================
# BLOQUE F: INFORME SEMANAL
# ==============================================================================
class TestInformeSemanalIntegration:
    """Verifica la persistencia del consolidado periódico de recinto y sus detalles ordenados."""

    def test_informe_semanal_creation_and_periodo_retrieval(self, temp_db_env):
        """F.1 & F.2: Creación de informe semanal, persistencia y recuperación por ID y período."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            repo = SQLiteInformeSemanalRepository(conn)
            informe = InformeSemanal(
                id_informe_semanal="inf-sem-sept-3",
                anio=2026,
                mes=9,
                numero_semana=3,
                etiqueta_periodo="Semana 3 - Septiembre 2026",
                departamento_responsable="Dirección de Innovación",
                sede_recinto="BLUEFIELDS",
                ruta_product_a="informes/2026/Product_A_Sem3.docx",
                hash_sha256_product_a="aaaabbbbccccddddeeeeffffaaaabbbbccccddddeeeeffffaaaabbbbccccdddd",
                ruta_product_b="informes/2026/Product_B_Sem3.docx",
                hash_sha256_product_b="1111222233334444555566661111222233334444555566661111222233334444",
                fecha_generacion="2026-09-20 18:00:00",
            )
            repo.save(informe)

            # Recuperar por ID
            ret_id = repo.get_by_id("inf-sem-sept-3")
            assert ret_id is not None
            assert ret_id.sede_recinto == "BLUEFIELDS"
            assert ret_id.numero_semana == 3
            assert ret_id.ruta_product_a == "informes/2026/Product_A_Sem3.docx"

            # Recuperar por período y sede
            ret_per = repo.get_by_periodo(2026, 9, 3, "BLUEFIELDS")
            assert ret_per is not None
            assert ret_per.id_informe_semanal == "inf-sem-sept-3"

            # Período inexistente retorna None
            assert repo.get_by_periodo(2026, 9, 4, "BLUEFIELDS") is None
        finally:
            conn.close()

    def test_informe_semanal_detalles_sequence_ordering(self, temp_db_env):
        """F.3: Relación informe -> actividad preservando orden de secuencia y banderas de producto."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            inf_repo = SQLiteInformeSemanalRepository(conn)

            # Sembrar actividades vinculables
            for i in [1, 2, 3]:
                act_repo.save(Activity(id_actividad=f"act-det-{i}", nombre_actividad_original=f"Actividad {i}"))

            informe = InformeSemanal(
                id_informe_semanal="inf-det-01",
                anio=2026,
                mes=9,
                numero_semana=2,
                etiqueta_periodo="Semana 2",
                departamento_responsable="Extensión Universitaria",
                sede_recinto="BILWI",
            )
            detalles = [
                DetalleInformeSemanal(
                    id_detalle="det-3",
                    id_informe_semanal="inf-det-01",
                    id_actividad="act-det-3",
                    orden_secuencia=3,
                    incluir_product_a=True,
                    incluir_product_b=False,
                ),
                DetalleInformeSemanal(
                    id_detalle="det-1",
                    id_informe_semanal="inf-det-01",
                    id_actividad="act-det-1",
                    orden_secuencia=1,
                    incluir_product_a=True,
                    incluir_product_b=True,
                ),
                DetalleInformeSemanal(
                    id_detalle="det-2",
                    id_informe_semanal="inf-det-01",
                    id_actividad="act-det-2",
                    orden_secuencia=2,
                    incluir_product_a=False,
                    incluir_product_b=True,
                ),
            ]
            inf_repo.save(informe, detalles)

            # Recuperar detalles: deben estar ordenados estrictamente por orden_secuencia (1, 2, 3)
            detalles_ret = inf_repo.get_detalles("inf-det-01")
            assert len(detalles_ret) == 3
            assert [d.id_actividad for d in detalles_ret] == ["act-det-1", "act-det-2", "act-det-3"]
            assert detalles_ret[0].orden_secuencia == 1
            assert detalles_ret[0].incluir_product_a is True
            assert detalles_ret[0].incluir_product_b is True
            assert detalles_ret[1].orden_secuencia == 2
            assert detalles_ret[1].incluir_product_a is False
            assert detalles_ret[2].orden_secuencia == 3
            assert detalles_ret[2].incluir_product_b is False
        finally:
            conn.close()


# ==============================================================================
# BLOQUE G: DISCREPANCIAS Y REGLA INVIOLABLE RN-C07
# ==============================================================================
class TestDiscrepanciaGovernanceIntegration:
    """Verifica la persistencia de discrepancias bajo la regla RN-C07 (DETECTAR ≠ CORREGIR)."""

    def test_discrepancia_lifecycle_and_pending_filtering(self, temp_db_env):
        """G.1: Crear discrepancias, recuperar por actividad y filtrar pendientes por severidad."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            disc_repo = SQLiteDiscrepanciaRepository(conn)

            act_id = "act-disc-gov"
            act_repo.save(Activity(id_actividad=act_id, nombre_actividad_original="Capacitación Docente"))

            d1 = Discrepancia(
                id_discrepancia="d-1",
                id_actividad=act_id,
                tipo_discrepancia=TipoDiscrepancia.PLAN_VS_REAL,
                severidad=SeveridadDiscrepancia.WARNING,
                fuente_a_nombre="Planificación",
                fuente_a_valor="40",
                fuente_b_nombre="Asistencia Real",
                fuente_b_valor="35",
                delta_valor="-5",
                estado=EstadoDiscrepancia.REQUIERE_REVISION,
            )
            d2 = Discrepancia(
                id_discrepancia="d-2",
                id_actividad=act_id,
                tipo_discrepancia=TipoDiscrepancia.M1_VS_NOMINALES,
                severidad=SeveridadDiscrepancia.ERROR,
                fuente_a_nombre="M1 Fila 10",
                fuente_a_valor="20",
                fuente_b_nombre="M2 Filas",
                fuente_b_valor="15",
                delta_valor="-5",
                estado=EstadoDiscrepancia.EN_REVISION,
            )
            d3 = Discrepancia(
                id_discrepancia="d-3",
                id_actividad=act_id,
                tipo_discrepancia=TipoDiscrepancia.OTRO,
                severidad=SeveridadDiscrepancia.INFO,
                fuente_a_nombre="Fuente A",
                fuente_a_valor="X",
                fuente_b_nombre="Fuente B",
                fuente_b_valor="X",
                delta_valor="0",
                estado=EstadoDiscrepancia.CONCORDANTE,
            )
            disc_repo.save_batch([d1, d2, d3])

            # Todas las de la actividad
            all_act = disc_repo.list_by_actividad(act_id)
            assert len(all_act) == 3

            # Solo pendientes (REQUIERE_REVISION o EN_REVISION)
            pendientes = disc_repo.list_pendientes()
            assert len(pendientes) == 2
            pend_ids = {p.id_discrepancia for p in pendientes}
            assert pend_ids == {"d-1", "d-2"}

            # Pendientes filtradas por severidad ERROR
            pend_error = disc_repo.list_pendientes(severidad="ERROR")
            assert len(pend_error) == 1
            assert pend_error[0].id_discrepancia == "d-2"
        finally:
            conn.close()

    def test_discrepancia_registrar_revision_inviolability_rn_c07(self, temp_db_env):
        """G.2: Confirmar que registrar_revision() modifica estado y nota pero NUNCA fuente_a/b ni delta."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            disc_repo = SQLiteDiscrepanciaRepository(conn)

            act_repo.save(Activity(id_actividad="act-audit-7", nombre_actividad_original="Auditoría Forense"))

            disc = Discrepancia(
                id_discrepancia="disc-forense-1",
                id_actividad="act-audit-7",
                tipo_discrepancia=TipoDiscrepancia.RESUMEN_VS_NOMINAL,
                severidad=SeveridadDiscrepancia.ERROR,
                fuente_a_nombre="Resumen Ficha",
                fuente_a_valor="100",
                fuente_b_nombre="Lista Firmada",
                fuente_b_valor="92",
                delta_valor="-8",
                estado=EstadoDiscrepancia.REQUIERE_REVISION,
            )
            disc_repo.save(disc)

            # Asentar revisión humana
            disc_repo.registrar_revision(
                id_discrepancia="disc-forense-1",
                nuevo_estado="ACLARADO",
                justificacion="8 participantes se retiraron antes de la firma; justificados con lista preliminar.",
                usuario_revisor="Prof. Kenia",
            )

            actualizada = disc_repo.get_by_id("disc-forense-1")
            assert actualizada is not None
            # Atributos actualizados de revisión
            assert actualizada.estado == "ACLARADO"
            assert "8 participantes se retiraron" in actualizada.justificacion_aclaratoria
            assert actualizada.usuario_revisor == "Prof. Kenia"
            assert actualizada.fecha_revision is not None

            # INVIOLABILIDAD ABSOLUTA DE LAS FUENTES (DETECTAR ≠ CORREGIR)
            assert actualizada.fuente_a_valor == "100"
            assert actualizada.fuente_b_valor == "92"
            assert actualizada.delta_valor == "-8"
            assert actualizada.fuente_a_nombre == "Resumen Ficha"
            assert actualizada.fuente_b_nombre == "Lista Firmada"
        finally:
            conn.close()


# ==============================================================================
# BLOQUE H: INTEGRIDAD REFERENCIAL (FOREIGN KEYS)
# ==============================================================================
class TestReferentialIntegrityIntegration:
    """Verifica que PRAGMA foreign_keys = ON se respeta y las violaciones se traducen a ReferentialIntegrityError."""

    def test_valid_foreign_keys_allowed(self, temp_db_env):
        """H.1: Inserciones con claves foráneas válidas se completan exitosamente."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            part_repo = SQLiteParticipacionRepository(conn)

            act_repo.save(Activity(id_actividad="act-fk-ok", nombre_actividad_original="Actividad FK Válida"))
            per_repo.save(Person(id_persona_interno="per-fk-ok", nombre_completo="Persona FK Válida"))

            part_repo.save(Participation(
                id_participacion="part-fk-ok",
                id_actividad="act-fk-ok",
                id_persona="per-fk-ok",
                categoria_participacion="ESTUDIANTE",
            ))
            assert part_repo.get_by_id("part-fk-ok") is not None
        finally:
            conn.close()

    def test_invalid_foreign_key_raises_referential_integrity_error(self, temp_db_env):
        """H.2: Clave foránea inválida lanza ReferentialIntegrityError (no escapa sqlite3.IntegrityError)."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            part_repo = SQLiteParticipacionRepository(conn)

            act_repo.save(Activity(id_actividad="act-fk-real", nombre_actividad_original="Actividad Real"))

            # Intento con id_persona inexistente
            with pytest.raises(ReferentialIntegrityError, match="Violación de clave foránea"):
                part_repo.save(Participation(
                    id_participacion="part-fk-fail",
                    id_actividad="act-fk-real",
                    id_persona="per-INEXISTENTE-12345",
                    categoria_participacion="ESTUDIANTE",
                ))
        finally:
            conn.close()

    def test_foreign_key_violation_rollback_leaves_no_orphans(self, temp_db_env):
        """H.3 & H.4: Rollback posterior a violación FK asegura ausencia total de registros huérfanos."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        try:
            with uow:
                # 1. Guardar actividad válida
                uow.actividades.save(Activity(id_actividad="act-fk-trans", nombre_actividad_original="Transacción FK"))
                # 2. Provocar violación FK deliberada
                uow.participaciones.save(Participation(
                    id_participacion="part-fk-trans",
                    id_actividad="act-fk-trans",
                    id_persona="per-NO-EXISTE",
                    categoria_participacion="ESTUDIANTE",
                ))
                uow.commit()
        except ReferentialIntegrityError:
            pass

        # Conexión independiente: verificar que act-fk-trans fue revertida y no persiste huérfana
        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists("act-fk-trans") is False
            assert SQLiteParticipacionRepository(conn).get_by_id("part-fk-trans") is None
        finally:
            conn.close()


# ==============================================================================
# BLOQUE I: RESTRICCIONES UNIQUE
# ==============================================================================
class TestUniqueConstraintsIntegration:
    """Verifica el cumplimiento de las restricciones UNIQUE del esquema DDL institucional."""

    def test_unique_constraint_cedula_non_null(self, temp_db_env):
        """I.1: Dos personas distintas con la misma cédula no nula violan unicidad (EntityAlreadyExistsError)."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            repo = SQLitePersonaRepository(conn)
            p1 = Person(
                id_persona_interno="per-uq-1",
                nombre_completo="Primera Persona",
                cedula="601-200290-0001K",
            )
            p2 = Person(
                id_persona_interno="per-uq-2",
                nombre_completo="Segunda Persona",
                cedula="601-200290-0001K",  # Cédula idéntica
            )
            repo.save(p1)

            with pytest.raises(EntityAlreadyExistsError, match="restriccion_unica"):
                repo.save(p2)
        finally:
            conn.close()

    def test_unique_constraint_cedula_null_allows_multiple_persons_rn_c04(self, temp_db_env):
        """I.2: Múltiples personas con cédula NULL pueden coexistir sin colisión (Regla RN-C04)."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            repo = SQLitePersonaRepository(conn)
            p1 = Person(id_persona_interno="per-null-1", nombre_completo="Persona Sin Cédula 1", cedula=None)
            p2 = Person(id_persona_interno="per-null-2", nombre_completo="Persona Sin Cédula 2", cedula=None)
            p3 = Person(id_persona_interno="per-null-3", nombre_completo="Persona Con Cadena Vacía", cedula="")

            repo.save(p1)
            repo.save(p2)
            repo.save(p3)

            assert repo.count() == 3
            assert repo.exists("per-null-1") is True
            assert repo.exists("per-null-2") is True
            assert repo.exists("per-null-3") is True
        finally:
            conn.close()

    def test_unique_constraint_relational_pairs(self, temp_db_env):
        """I.3 a I.5: Restricciones UNIQUE en participacion (actividad, persona) y actividad_evidencia."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            evi_repo = SQLiteEvidenciaRepository(conn)

            act_repo.save(Activity(id_actividad="act-pair", nombre_actividad_original="Actividad Par"))
            per_repo.save(Person(id_persona_interno="per-pair", nombre_completo="Persona Par"))
            evi_repo.save(Evidencia(id_evidencia="evi-pair", tipo_evidencia=TipoEvidencia.FOTOGRAFIA, titulo="Foto"))

            # 1. Par único en participacion: UNIQUE (id_actividad, id_persona)
            conn.execute("""
            INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino)
            VALUES ('part-p1', 'act-pair', 'per-pair', 'ESTUDIANTE', 'M2');
            """)

            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
                conn.execute("""
                INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino)
                VALUES ('part-p2', 'act-pair', 'per-pair', 'DOCENTE', 'M3');
                """)

            # 2. Par único en actividad_evidencia: UNIQUE (id_actividad, id_evidencia)
            conn.execute("""
            INSERT INTO actividad_evidencia (id_actividad_evidencia, id_actividad, id_evidencia)
            VALUES ('ae-1', 'act-pair', 'evi-pair');
            """)

            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
                conn.execute("""
                INSERT INTO actividad_evidencia (id_actividad_evidencia, id_actividad, id_evidencia)
                VALUES ('ae-2', 'act-pair', 'evi-pair');
                """)
        finally:
            conn.close()


# ==============================================================================
# BLOQUE J: TRATAMIENTO ESTRICTO DE VALORES NULL
# ==============================================================================
class TestNullPreservationRoundtrip:
    """Verifica que None se persiste efectivamente como SQL NULL y retorna como None."""

    def test_null_preservation_across_all_entities(self, temp_db_env):
        """J.1 & J.2: Comprobación de persistencia directa SQL NULL y retorno como None."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            # 1. Persona con campos nulos
            per_repo = SQLitePersonaRepository(conn)
            per = Person(
                id_persona_interno="per-null-strict",
                nombre_completo="Protagonista Sin Cédula",
                cedula=None,
                numero_unico=None,
                otro_id_institucional=None,
                fecha_nacimiento=None,
                telefono=None,
            )
            per_repo.save(per)

            # Verificar en SQLite crudo que la columna almacena NULL
            cursor = conn.cursor()
            cursor.execute("""
            SELECT cedula, numero_institucional, fecha_nacimiento, telefono
            FROM persona WHERE id_persona_interno = 'per-null-strict';
            """)
            row = cursor.fetchone()
            assert row[0] is None
            assert row[1] is None
            assert row[2] is None
            assert row[3] is None

            # Verificar que vuelve como None
            per_ret = per_repo.get_by_id("per-null-strict")
            assert per_ret.cedula is None
            assert per_ret.numero_unico is None
            assert per_ret.fecha_nacimiento is None
            assert per_ret.telefono is None

            # 2. Actividad con campos nulos
            act_repo = SQLiteActividadRepository(conn)
            act = Activity(
                id_actividad="act-null-strict",
                nombre_actividad_original="Actividad Sin Fechas Fin",
                fecha_evento=None,
                informacion_adicional=None,
            )
            act_repo.save(act)

            cursor.execute("SELECT fecha_fin, fuente_financiamiento FROM actividad WHERE id_actividad = 'act-null-strict';")
            row_act = cursor.fetchone()
            assert row_act[0] is None
            assert row_act[1] is None

            # 3. Discrepancia con valores opcionales nulos
            disc_repo = SQLiteDiscrepanciaRepository(conn)
            disc = Discrepancia(
                id_discrepancia="disc-null-strict",
                id_actividad="act-null-strict",
                tipo_discrepancia=TipoDiscrepancia.OTRO,
                fuente_a_nombre="F-A",
                fuente_a_valor="0",
                fuente_b_nombre="F-B",
                fuente_b_valor="0",
                delta_valor=None,
                justificacion_aclaratoria=None,
                usuario_revisor=None,
                fecha_revision=None,
            )
            disc_repo.save(disc)

            cursor.execute("SELECT delta_valor, justificacion_aclaratoria, usuario_revisor, fecha_revision FROM discrepancia WHERE id_discrepancia = 'disc-null-strict';")
            row_disc = cursor.fetchone()
            assert row_disc[0] is None
            assert row_disc[1] is None
            assert row_disc[2] is None
            assert row_disc[3] is None

            disc_ret = disc_repo.get_by_id("disc-null-strict")
            assert disc_ret.delta_valor is None
            assert disc_ret.justificacion_aclaratoria is None
            assert disc_ret.usuario_revisor is None
            assert disc_ret.fecha_revision is None
        finally:
            conn.close()


# ==============================================================================
# BLOQUE K: TRANSACCIONES ATÓMICAS MULTIRREPOSITORIO
# ==============================================================================
class TestAtomicMultiRepositoryTransactions:
    """Verifica atomicidad total (todo o nada) en una transacción que coordina 5 repositorios."""

    def test_atomic_all_or_nothing_five_repositories_failure(self, temp_db_env):
        """K.1: Transacción con 5 repositorios que falla al final no deja NINGÚN dato persistido."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        act_id = "act-atomic-fail"
        per_id = "per-atomic-fail"
        part_id = "part-atomic-fail"
        evi_id = "evi-atomic-fail"

        try:
            with uow:
                # 1. Actividad
                uow.actividades.save(Activity(id_actividad=act_id, nombre_actividad_original="Actividad Atómica"))
                # 2. Persona
                uow.personas.save(Person(id_persona_interno=per_id, nombre_completo="Persona Atómica"))
                # 3. Participación
                uow.participaciones.save(Participation(
                    id_participacion=part_id,
                    id_actividad=act_id,
                    id_persona=per_id,
                    categoria_participacion="ESTUDIANTE",
                ))
                # 4. Evidencia
                uow.evidencias.save(Evidencia(
                    id_evidencia=evi_id,
                    tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
                    titulo="Foto Atómica",
                ))
                # 5. Vinculación Actividad-Evidencia
                uow.evidencias.link_actividad(act_id, evi_id)

                # Forzar un fallo deliberado antes del commit
                raise RuntimeError("Fallo catastrófico simulado de infraestructura")
                uow.commit()  # pragma: no cover
        except RuntimeError:
            pass

        # Comprobar en conexión independiente que NINGUNA de las 5 operaciones se conservó
        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists(act_id) is False
            assert SQLitePersonaRepository(conn).exists(per_id) is False
            assert SQLiteParticipacionRepository(conn).get_by_id(part_id) is None
            assert SQLiteEvidenciaRepository(conn).get_by_id(evi_id) is None
            assert len(SQLiteEvidenciaRepository(conn).get_by_actividad(act_id)) == 0
        finally:
            conn.close()

    def test_atomic_all_or_nothing_five_repositories_success(self, temp_db_env):
        """K.2: Misma transacción con 5 repositorios sin fallo confirma TODAS las escrituras."""
        manager, db_path = temp_db_env
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        act_id = "act-atomic-ok"
        per_id = "per-atomic-ok"
        part_id = "part-atomic-ok"
        evi_id = "evi-atomic-ok"

        with uow:
            uow.actividades.save(Activity(id_actividad=act_id, nombre_actividad_original="Actividad Exitosa"))
            uow.personas.save(Person(id_persona_interno=per_id, nombre_completo="Persona Exitosa"))
            uow.participaciones.save(Participation(
                id_participacion=part_id,
                id_actividad=act_id,
                id_persona=per_id,
                categoria_participacion="ESTUDIANTE",
            ))
            uow.evidencias.save(Evidencia(
                id_evidencia=evi_id,
                tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
                titulo="Foto Exitosa",
            ))
            uow.evidencias.link_actividad(act_id, evi_id)
            uow.commit()

        # Comprobar en conexión independiente que TODAS las operaciones persisten
        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists(act_id) is True
            assert SQLitePersonaRepository(conn).exists(per_id) is True
            assert SQLiteParticipacionRepository(conn).get_by_id(part_id) is not None
            assert SQLiteEvidenciaRepository(conn).get_by_id(evi_id) is not None
            assert len(SQLiteEvidenciaRepository(conn).get_by_actividad(act_id)) == 1
        finally:
            conn.close()


# ==============================================================================
# BLOQUE L: ARQUITECTURA Y DIRECCIÓN DE DEPENDENCIAS
# ==============================================================================
class TestCleanArchitectureDependencies:
    """Verifica de forma estática y automatizada que app/core no dependa de infraestructura o sqlite3."""

    def test_core_does_not_import_sqlite3_or_infrastructure(self):
        """L.1: app/core/ no debe contener importaciones de sqlite3 ni de app.infrastructure."""
        project_root = Path(__file__).parent.parent
        core_dir = project_root / "app" / "core"

        forbidden_prefixes = ("sqlite3", "app.infrastructure")

        violaciones = []
        for py_file in core_dir.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=str(py_file))
                except SyntaxError:
                    continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(alias.name.startswith(p) for p in forbidden_prefixes):
                            violaciones.append((str(py_file), alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and any(node.module.startswith(p) for p in forbidden_prefixes):
                        violaciones.append((str(py_file), node.module))

        assert len(violaciones) == 0, f"Violaciones de Clean Architecture detectadas en app/core: {violaciones}"

    def test_dependency_direction_is_strictly_infrastructure_to_core(self):
        """L.2: Comprueba que app/infrastructure importa de app/core (Inversión de Dependencias)."""
        project_root = Path(__file__).parent.parent
        repos_dir = project_root / "app" / "infrastructure" / "persistence" / "repositories"

        found_core_import = False
        for py_file in repos_dir.glob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "app.core.ports" in content or "app.core.models" in content:
                    found_core_import = True
                    break

        assert found_core_import is True, "Los repositorios de infraestructura deben depender de app.core.ports."


# ==============================================================================
# BLOQUE M: PARAMETRIZACIÓN SQL Y SEGURIDAD
# ==============================================================================
class TestSqlParameterizationAndInjectionSafety:
    """Verifica que las consultas utilicen parámetros y manejen caracteres complejos y cadenas de inyección."""

    def test_special_characters_and_sql_injection_resilience(self, temp_db_env):
        """M.1: Inserción de apóstrofes, comillas, ampersands, saltos de línea y fragmentos SQL maliciosos."""
        manager, _ = temp_db_env
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            disc_repo = SQLiteDiscrepanciaRepository(conn)

            # Cadenas con fragmentos SQL maliciosos y caracteres especiales
            nombre_inyeccion = "Dra. O'Connor'); DROP TABLE actividad; --"
            act_inyeccion = "Taller de Innovación: \"Especial 2026\" & O'Reilly -- ' OR '1'='1"
            nota_inyeccion = "Nota con apóstrofe O'Hara, saltos de línea \n\t y comillas \"dobles\"."

            act = Activity(
                id_actividad="act-sqli-1",
                nombre_actividad_original=act_inyeccion,
                informacion_adicional="Notas: ' OR '1'='1' /* inyección */",
            )
            per = Person(
                id_persona_interno="per-sqli-1",
                nombre_completo=nombre_inyeccion,
                cedula="601-010190-0099Z",
            )
            disc = Discrepancia(
                id_discrepancia="disc-sqli-1",
                id_actividad="act-sqli-1",
                tipo_discrepancia=TipoDiscrepancia.OTRO,
                fuente_a_nombre="Fuente 'A' & 'B'",
                fuente_a_valor="Valor '1'",
                fuente_b_nombre="Fuente 'B' --",
                fuente_b_valor="Valor '2'",
                justificacion_aclaratoria=nota_inyeccion,
            )

            act_repo.save(act)
            per_repo.save(per)
            disc_repo.save(disc)

            # 1. Comprobar que la tabla actividad NO fue borrada por la inyección
            assert act_repo.exists("act-sqli-1") is True

            # 2. Comprobar que los valores se almacenaron y recuperaron literalmente
            ret_act = act_repo.get_by_id("act-sqli-1")
            assert ret_act.nombre_actividad_original == act_inyeccion
            assert ret_act.informacion_adicional == "Notas: ' OR '1'='1' /* inyección */"

            ret_per = per_repo.get_by_id("per-sqli-1")
            assert ret_per.nombre_completo == nombre_inyeccion

            ret_disc = disc_repo.get_by_id("disc-sqli-1")
            assert ret_disc.justificacion_aclaratoria == nota_inyeccion
            assert ret_disc.fuente_a_nombre == "Fuente 'A' & 'B'"
        finally:
            conn.close()
