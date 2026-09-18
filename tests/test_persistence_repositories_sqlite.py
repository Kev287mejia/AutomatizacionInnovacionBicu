"""tests/test_persistence_repositories_sqlite.py

Pruebas completas para los adaptadores concretos SQLite (Subetapa 25.3.3):
- CRUD y consultas de los 6 repositorios SQLite.
- Integridad referencial y traducción de excepciones a errores de dominio.
- Regla RN-C04 (múltiples personas con cédula NULL sin colisión).
- Regla RN-C07 (DETECTAR ≠ CORREGIR en discrepancias).
- Seguridad contra inyección SQL (valores con comillas, apóstrofes y ampersands).
- Unit of Work: Confirmación atómica (commit) y reversión total (rollback) ante fallos.
"""

from datetime import date
from pathlib import Path
import pytest
import tempfile

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
def temp_db_manager():
    """Crea una base de datos temporal en disco con el esquema v001 aplicado."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_repos.db"
        config = DatabaseConfig(db_path=db_path)
        manager = SQLiteConnectionManager(config)

        # Aplicar migraciones iniciales
        conn = manager.get_connection()
        try:
            runner = MigrationRunner(conn)
            runner.apply_all_pending()
        finally:
            conn.close()

        yield manager, db_path


class TestSQLiteActividadRepository:
    """Pruebas del adaptador SQLiteActividadRepository."""

    def test_save_and_get_by_id_roundtrip(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            repo = SQLiteActividadRepository(conn)
            act = Activity(
                id_actividad="act-001",
                nombre_actividad_original="Taller de Innovación Abierta",
                nombre_actividad_oficial="Taller Oficial de Innovación 2026",
                fecha_evento="2026-09-20",
                sede="BLUEFIELDS",
                departamento="RACCS",
                municipio_evento="Bluefields",
                tipo_evento="TALLER",
                ambito="LOCAL",
                programa="Programa 25",
                eje_linea_estrategica="Eje 1: Innovación",
                informacion_adicional="Fondos concursables",
            )
            repo.save(act)

            assert repo.exists("act-001") is True
            assert repo.count() == 1

            retrieved = repo.get_by_id("act-001")
            assert retrieved is not None
            assert retrieved.id_actividad == "act-001"
            assert retrieved.nombre_actividad_original == "Taller de Innovación Abierta"
            assert retrieved.nombre_actividad_oficial == "Taller Oficial de Innovación 2026"
            assert retrieved.sede == "BLUEFIELDS"
            assert retrieved.departamento == "RACCS"
        finally:
            conn.close()

    def test_list_by_periodo_with_sede_filter(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            repo = SQLiteActividadRepository(conn)
            act1 = Activity(
                id_actividad="act-sept-1",
                nombre_actividad_original="Feria Tecnológica Bluefields",
                fecha_evento="2026-09-10",
                sede="BLUEFIELDS",
            )
            act2 = Activity(
                id_actividad="act-sept-2",
                nombre_actividad_original="Capacitación Bilwi",
                fecha_evento="2026-09-15",
                sede="BILWI",
            )
            act3 = Activity(
                id_actividad="act-oct-1",
                nombre_actividad_original="Hackatón Rama",
                fecha_evento="2026-10-05",
                sede="EL_RAMA",
            )
            repo.save(act1)
            repo.save(act2)
            repo.save(act3)

            # Consulta en rango de septiembre
            sept_all = repo.list_by_periodo("2026-09-01", "2026-09-30")
            assert len(sept_all) == 2

            # Consulta con filtro de sede
            sept_bluefields = repo.list_by_periodo("2026-09-01", "2026-09-30", sede="BLUEFIELDS")
            assert len(sept_bluefields) == 1
            assert sept_bluefields[0].id_actividad == "act-sept-1"
        finally:
            conn.close()

    def test_sql_injection_safety(self, temp_db_manager):
        """Verifica que caracteres especiales y comillas no rompan las consultas."""
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            repo = SQLiteActividadRepository(conn)
            act_inyeccion = Activity(
                id_actividad="act-inj-1",
                nombre_actividad_original="Taller O'Connor & \"Especial\"; DROP TABLE actividad; --",
                fecha_evento="2026-09-20",
                sede="OTRA",
            )
            repo.save(act_inyeccion)

            retrieved = repo.get_by_id("act-inj-1")
            assert retrieved is not None
            assert "O'Connor" in retrieved.nombre_actividad_original
            # Verificar que la tabla actividad sigue existiendo intacta
            assert repo.count() == 1
        finally:
            conn.close()


class TestSQLitePersonaRepository:
    """Pruebas del adaptador SQLitePersonaRepository."""

    def test_save_and_get_by_id_roundtrip(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            repo = SQLitePersonaRepository(conn)
            p = Person(
                id_persona_interno="per-001",
                nombre_completo="María Elena Dixon Taylor",
                nombres="María Elena",
                apellidos="Dixon Taylor",
                cedula="601-120598-0001X",
                numero_unico="2022-0045B",
                otro_id_institucional=None,
                sexo_normalizado="FEMENINO",
                edad=28,
                etnia="Creole",
                telefono="8888-1234",
                departamento_persona="RACCS",
                municipio_persona="Bluefields",
            )
            repo.save(p)

            assert repo.exists("per-001") is True
            retrieved = repo.get_by_id("per-001")
            assert retrieved is not None
            assert retrieved.nombre_completo == "María Elena Dixon Taylor"
            assert retrieved.cedula == "601-120598-0001X"
            assert retrieved.numero_unico == "2022-0045B"
            assert retrieved.sexo_normalizado == "F"
            assert retrieved.edad == 28
        finally:
            conn.close()

    def test_persona_cedula_null_allowed_and_no_collision_rn_c04(self, temp_db_manager):
        """Regla RN-C04: Múltiples personas con cédula NULL pueden coexistir sin colisión."""
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            repo = SQLitePersonaRepository(conn)
            p1 = Person(
                id_persona_interno="per-sin-cedula-1",
                nombre_completo="Protagonista Comunitario Uno",
                cedula=None,
                sexo_normalizado="M",
            )
            p2 = Person(
                id_persona_interno="per-sin-cedula-2",
                nombre_completo="Protagonista Comunitario Dos",
                cedula=None,
                sexo_normalizado="F",
            )
            repo.save(p1)
            repo.save(p2)

            assert repo.count() == 2
            assert repo.get_by_id("per-sin-cedula-1").cedula is None
            assert repo.get_by_id("per-sin-cedula-2").cedula is None
            # Búsqueda por cédula con None debe ser segura y retornar None
            assert repo.get_by_cedula(None) is None
            assert repo.get_by_cedula("") is None
        finally:
            conn.close()

    def test_search_by_nombre_and_lookups(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            repo = SQLitePersonaRepository(conn)
            p = Person(
                id_persona_interno="per-lookup",
                nombre_completo="Roberto Carlos Hodgson",
                cedula="602-150890-0002Y",
                numero_unico="DOC-9988",
                sexo_normalizado="M",
            )
            repo.save(p)

            by_ced = repo.get_by_cedula("602-150890-0002Y")
            assert by_ced is not None
            assert by_ced.id_persona_interno == "per-lookup"

            by_num = repo.get_by_numero_institucional("DOC-9988")
            assert by_num is not None
            assert by_num.id_persona_interno == "per-lookup"

            search_res = repo.search_by_nombre("hodgson")
            assert len(search_res) == 1
            assert search_res[0].id_persona_interno == "per-lookup"
        finally:
            conn.close()


class TestSQLiteParticipacionRepository:
    """Pruebas del adaptador SQLiteParticipacionRepository."""

    def test_save_and_get_by_id_roundtrip(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            part_repo = SQLiteParticipacionRepository(conn)

            # Insertar dependencias FK válidas
            act_repo.save(Activity(id_actividad="act-p-1", nombre_actividad_original="Taller Robótica"))
            per_repo.save(Person(id_persona_interno="per-p-1", nombre_completo="Luis Morales"))

            part = Participation(
                id_participacion="part-001",
                id_actividad="act-p-1",
                id_persona="per-p-1",
                categoria_participacion="ESTUDIANTE",
                observaciones="Ingeniería en Sistemas",
                requiere_revision=False,
            )
            part_repo.save(part)

            assert part_repo.count_by_actividad("act-p-1") == 1
            retrieved = part_repo.get_by_id("part-001")
            assert retrieved is not None
            assert retrieved.id_actividad == "act-p-1"
            assert retrieved.id_persona == "per-p-1"
            assert retrieved.categoria_participacion == "ESTUDIANTE"

            by_link = part_repo.get_by_actividad_and_persona("act-p-1", "per-p-1")
            assert by_link is not None
            assert by_link.id_participacion == "part-001"
        finally:
            conn.close()

    def test_referential_integrity_exception_translation(self, temp_db_manager):
        """Verifica que violaciones de FK sean traducidas a ReferentialIntegrityError."""
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            part_repo = SQLiteParticipacionRepository(conn)
            # Intento de insertar participación con actividad y persona inexistentes
            part_invalida = Participation(
                id_participacion="part-invalida",
                id_actividad="act-INEXISTENTE",
                id_persona="per-INEXISTENTE",
                categoria_participacion="ESTUDIANTE",
            )
            with pytest.raises(ReferentialIntegrityError, match="Violación de clave foránea"):
                part_repo.save(part_invalida)
        finally:
            conn.close()

    def test_save_batch_and_filters(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            per_repo = SQLitePersonaRepository(conn)
            part_repo = SQLiteParticipacionRepository(conn)

            act_repo.save(Activity(id_actividad="act-masiva", nombre_actividad_original="Rally Nacional"))
            per_repo.save(Person(id_persona_interno="p-m1", nombre_completo="Estudiante 1"))
            per_repo.save(Person(id_persona_interno="p-m2", nombre_completo="Docente 1"))

            parts = [
                Participation(
                    id_participacion="part-b-1",
                    id_actividad="act-masiva",
                    id_persona="p-m1",
                    categoria_participacion="ESTUDIANTE",
                    matriz_destino="M2",
                ),
                Participation(
                    id_participacion="part-b-2",
                    id_actividad="act-masiva",
                    id_persona="p-m2",
                    categoria_participacion="DOCENTE",
                    requiere_revision=True,
                    motivo_revision="Verificar departamento",
                ),
            ]
            part_repo.save_batch(parts)

            assert part_repo.count_by_actividad("act-masiva") == 2
            rev_list = part_repo.list_requieren_revision(id_actividad="act-masiva")
            assert len(rev_list) == 1
            assert rev_list[0].id_participacion == "part-b-2"

            m2_list = part_repo.list_by_matriz_destino("M2", id_actividad="act-masiva")
            assert len(m2_list) == 1
            assert m2_list[0].id_participacion == "part-b-1"
        finally:
            conn.close()


class TestSQLiteEvidenciaRepository:
    """Pruebas del adaptador SQLiteEvidenciaRepository."""

    def test_save_and_link_actividad_roundtrip(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            evi_repo = SQLiteEvidenciaRepository(conn)

            act_repo.save(Activity(id_actividad="act-evi", nombre_actividad_original="Feria de Ideas"))

            evi = Evidencia(
                id_evidencia="evi-001",
                tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
                titulo="Foto Inaugural",
                descripcion_pie="Acto de apertura en el auditorio central",
                ruta_archivo_relativa="evidencias/2026/foto1.jpg",
                hash_sha256="a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
                tamano_bytes=204800,
                mime_type="image/jpeg",
            )
            evi_repo.save(evi)

            by_hash = evi_repo.get_by_hash("a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890")
            assert by_hash is not None
            assert by_hash.id_evidencia == "evi-001"

            # Vincular a la actividad
            evi_repo.link_actividad("act-evi", "evi-001", orden=1, seccion="GALERIA")

            lista_act = evi_repo.get_by_actividad("act-evi")
            assert len(lista_act) == 1
            ev_ret, orden, seccion = lista_act[0]
            assert ev_ret.id_evidencia == "evi-001"
            assert orden == 1
            assert seccion == "GALERIA"

            # Desvincular
            evi_repo.unlink_actividad("act-evi", "evi-001")
            assert len(evi_repo.get_by_actividad("act-evi")) == 0
        finally:
            conn.close()


class TestSQLiteInformeSemanalRepository:
    """Pruebas del adaptador SQLiteInformeSemanalRepository."""

    def test_save_and_get_with_detalles(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            inf_repo = SQLiteInformeSemanalRepository(conn)

            act_repo.save(Activity(id_actividad="act-sem-1", nombre_actividad_original="Actividad Semana 1"))
            act_repo.save(Activity(id_actividad="act-sem-2", nombre_actividad_original="Actividad Semana 2"))

            informe = InformeSemanal(
                id_informe_semanal="inf-sem-001",
                anio=2026,
                mes=9,
                numero_semana=3,
                etiqueta_periodo="Semana 3 - Septiembre 2026",
                departamento_responsable="Innovación y Emprendimiento",
                sede_recinto="BLUEFIELDS",
                ruta_product_a="informes/Product_A_Semana3.docx",
                ruta_product_b="informes/Product_B_Semana3.docx",
            )
            detalles = [
                DetalleInformeSemanal(
                    id_informe_semanal="inf-sem-001",
                    id_actividad="act-sem-1",
                    orden_secuencia=1,
                    incluir_product_a=True,
                    incluir_product_b=True,
                ),
                DetalleInformeSemanal(
                    id_informe_semanal="inf-sem-001",
                    id_actividad="act-sem-2",
                    orden_secuencia=2,
                    incluir_product_a=True,
                    incluir_product_b=False,
                ),
            ]
            inf_repo.save(informe, detalles)

            retrieved = inf_repo.get_by_id("inf-sem-001")
            assert retrieved is not None
            assert retrieved.etiqueta_periodo == "Semana 3 - Septiembre 2026"
            assert retrieved.detalles is not None
            assert len(retrieved.detalles) == 2
            assert retrieved.detalles[0].orden_secuencia == 1
            assert retrieved.detalles[1].incluir_product_b is False

            by_period = inf_repo.get_by_periodo(2026, 9, 3, "BLUEFIELDS")
            assert by_period is not None
            assert by_period.id_informe_semanal == "inf-sem-001"
        finally:
            conn.close()


class TestSQLiteDiscrepanciaRepository:
    """Pruebas del adaptador SQLiteDiscrepanciaRepository (DETECTAR ≠ CORREGIR)."""

    def test_detectar_no_corregir_lifecycle(self, temp_db_manager):
        manager, _ = temp_db_manager
        conn = manager.get_connection()
        try:
            act_repo = SQLiteActividadRepository(conn)
            disc_repo = SQLiteDiscrepanciaRepository(conn)

            act_repo.save(Activity(id_actividad="act-disc", nombre_actividad_original="Evento con Discrepancia"))

            disc = Discrepancia(
                id_discrepancia="disc-001",
                id_actividad="act-disc",
                tipo_discrepancia=TipoDiscrepancia.PLAN_VS_REAL,
                severidad=SeveridadDiscrepancia.WARNING,
                fuente_a_nombre="Planificacion.meta_participantes",
                fuente_a_valor="30",
                fuente_b_nombre="Asistencias.total_presentes",
                fuente_b_valor="28",
                delta_valor="-2",
                estado=EstadoDiscrepancia.REQUIERE_REVISION,
            )
            disc_repo.save(disc)

            pendientes = disc_repo.list_pendientes()
            assert len(pendientes) == 1
            assert pendientes[0].id_discrepancia == "disc-001"

            # Registrar aclaración humana: las fuentes A y B deben permanecer intactas
            disc_repo.registrar_revision(
                id_discrepancia="disc-001",
                nuevo_estado="ACLARADO",
                justificacion="Dos estudiantes se justificaron por permiso médico.",
                usuario_revisor="Prof. Kenia",
            )

            actualizada = disc_repo.get_by_id("disc-001")
            assert actualizada is not None
            assert actualizada.estado == "ACLARADO"
            assert actualizada.justificacion_aclaratoria == "Dos estudiantes se justificaron por permiso médico."
            assert actualizada.usuario_revisor == "Prof. Kenia"
            # Inviolabilidad de fuentes originales
            assert actualizada.fuente_a_valor == "30"
            assert actualizada.fuente_b_valor == "28"
            assert actualizada.delta_valor == "-2"
        finally:
            conn.close()


class TestSQLiteUnitOfWork:
    """Pruebas de la frontera transaccional atómica SQLiteUnitOfWork."""

    def test_unit_of_work_commit_persists_across_multiple_repositories(self, temp_db_manager):
        manager, db_path = temp_db_manager
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        with uow:
            # 1. Guardar Actividad
            uow.actividades.save(Activity(id_actividad="act-uow", nombre_actividad_original="Actividad UoW"))
            # 2. Guardar Persona
            uow.personas.save(Person(id_persona_interno="per-uow", nombre_completo="Protagonista UoW"))
            # 3. Guardar Participación vinculando ambas
            uow.participaciones.save(Participation(
                id_participacion="part-uow",
                id_actividad="act-uow",
                id_persona="per-uow",
                categoria_participacion="ESTUDIANTE",
            ))
            # 4. Guardar Discrepancia
            uow.discrepancias.save(Discrepancia(
                id_discrepancia="disc-uow",
                id_actividad="act-uow",
                fuente_a_nombre="Meta",
                fuente_a_valor="10",
                fuente_b_nombre="Real",
                fuente_b_valor="1",
            ))
            uow.commit()

        # Verificar en una nueva conexión independiente que todas las entidades persisten
        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists("act-uow") is True
            assert SQLitePersonaRepository(conn).exists("per-uow") is True
            assert SQLiteParticipacionRepository(conn).get_by_id("part-uow") is not None
            assert SQLiteDiscrepanciaRepository(conn).get_by_id("disc-uow") is not None
        finally:
            conn.close()

    def test_unit_of_work_rollback_on_exception_leaves_zero_partial_data(self, temp_db_manager):
        manager, db_path = temp_db_manager
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        try:
            with uow:
                # 1. Operación válida
                uow.actividades.save(Activity(id_actividad="act-rollback", nombre_actividad_original="Actividad Cancelada"))
                # 2. Operación que causará fallo referencial (FK inválida)
                uow.participaciones.save(Participation(
                    id_participacion="part-fallida",
                    id_actividad="act-rollback",
                    id_persona="per-INEXISTENTE-TOTAL",
                    categoria_participacion="ESTUDIANTE",
                ))
                uow.commit()
        except ReferentialIntegrityError:
            pass  # Excepción esperada

        # Verificar en conexión separada que la actividad NO quedó huérfana en la base de datos
        conn = manager.get_connection()
        try:
            assert SQLiteActividadRepository(conn).exists("act-rollback") is False
            assert SQLiteParticipacionRepository(conn).get_by_id("part-fallida") is None
        finally:
            conn.close()

    def test_unit_of_work_access_outside_with_raises_transaction_error(self, temp_db_manager):
        manager, db_path = temp_db_manager
        uow = SQLiteUnitOfWork(manager, db_path=db_path)

        with pytest.raises(TransactionError, match="UnitOfWork no inicializado"):
            _ = uow.actividades
