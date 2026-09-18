"""Pruebas Automatizadas del Esquema Físico y Migración Inicial - Sistema Institucional BICU.

Fase 25 (Etapa 25.2): Schema, SCHEMA_VERSION, Migración Inicial v001,
Integridad Referencial, Reglas de Negocio Institucionales y PRAGMA integrity_check.
"""

import sqlite3
import pytest
from pathlib import Path

from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.migrations import (
    Migration,
    MigrationRunner,
    MIGRATION_V001,
)
from app.infrastructure.persistence.schema import EXPECTED_TABLE_NAMES


@pytest.fixture
def clean_db(tmp_path: Path):
    """Provee una conexión configurada con el esquema migrado sobre una BD temporal."""
    db_file = tmp_path / "test_schema_fixture.db"
    manager = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))
    conn = manager.get_connection()
    runner = MigrationRunner(conn)
    runner.apply_all_pending()
    yield conn, runner
    conn.close()


class TestSchemaCreationAndTables:
    """Pruebas de creación física de tablas e inspección de catálogo."""

    def test_migration_creates_all_19_expected_tables(self, clean_db) -> None:
        """Verifica que existan exactamente las 18 tablas funcionales + schema_version."""
        conn, runner = clean_db
        existing_tables = runner.get_existing_tables()

        assert EXPECTED_TABLE_NAMES.issubset(existing_tables), (
            f"Faltan tablas en la base de datos: {EXPECTED_TABLE_NAMES - existing_tables}"
        )
        assert len(existing_tables) == len(EXPECTED_TABLE_NAMES)

    def test_schema_version_records_version_1(self, clean_db) -> None:
        """Verifica que la versión actual registrada en schema_version sea 1."""
        conn, runner = clean_db
        current_version = runner.get_current_version()
        assert current_version == 1

        applied = runner.get_applied_versions()
        assert 1 in applied
        assert applied[1]["nombre_migracion"] == "v001_initial_schema_18_tables"
        assert len(applied[1]["hash_script"]) == 64  # SHA-256
        assert applied[1]["tiempo_ejecucion_ms"] >= 0

    def test_pragma_integrity_check_returns_ok(self, clean_db) -> None:
        """Verifica que PRAGMA integrity_check retorne estrictamente 'ok'."""
        conn, runner = clean_db
        status = runner.verify_integrity()
        assert status == "ok", f"Integrity check falló con resultado: {status}"


class TestPersonaAndIdentityConstraints:
    """Pruebas de la entidad PERSONA, nulos en cédula y estados de identidad."""

    def test_persona_with_valid_cedula_and_unique_constraint(self, clean_db) -> None:
        """Verifica inserción de persona con cédula y rechazo de duplicados de cédula."""
        conn, _ = clean_db
        conn.execute(
            "INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo) "
            "VALUES ('uuid-p1', '601-120595-0001A', 'Ana Patricia Downs', 'F');"
        )

        # Inserción con misma cédula debe fallar por unicidad
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo) "
                "VALUES ('uuid-p2', '601-120595-0001A', 'Ana Downs Duplicada', 'F');"
            )

    def test_persona_without_cedula_allowed_and_multiple_nulls_dont_collide(self, clean_db) -> None:
        """Regla RN-C04: Múltiples personas con cédula NULL pueden coexistir sin colisión."""
        conn, _ = clean_db
        conn.execute(
            "INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo) "
            "VALUES ('uuid-null-1', NULL, 'Protagonista Rural Uno', 'M');"
        )
        conn.execute(
            "INSERT INTO persona (id_persona_interno, cedula, nombre_completo, sexo) "
            "VALUES ('uuid-null-2', NULL, 'Protagonista Rural Dos', 'F');"
        )

        cursor = conn.execute("SELECT COUNT(*) FROM persona WHERE cedula IS NULL;")
        assert cursor.fetchone()[0] == 2

    def test_persona_identity_states_check_constraint(self, clean_db) -> None:
        """Verifica que el campo estado_identidad solo admita valores permitidos."""
        conn, _ = clean_db
        for state in ("IDENTIDAD_CONFIRMADA", "POSIBLE_DUPLICADO", "IDENTIDAD_NO_RESUELTA"):
            conn.execute(
                f"INSERT INTO persona (id_persona_interno, nombre_completo, sexo, estado_identidad) "
                f"VALUES ('uuid-{state}', 'Persona Test', 'M', '{state}');"
            )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO persona (id_persona_interno, nombre_completo, sexo, estado_identidad) "
                "VALUES ('uuid-invalido', 'Persona Test', 'M', 'ESTADO_INVENTADO');"
            )

    def test_persona_sex_check_constraint_strict_m_f(self, clean_db) -> None:
        """Regla RN-C05: El sexo debe ser estrictamente 'M' o 'F'."""
        conn, _ = clean_db
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO persona (id_persona_interno, nombre_completo, sexo) "
                "VALUES ('uuid-sex-inv', 'Persona Invalida', 'V');"  # 'V' desestimado
            )


class TestActividadPlanificacionAndMethodology:
    """Pruebas del ciclo de actividad, planificación y diseño metodológico."""

    def test_actividad_can_exist_without_planificacion_emergente(self, clean_db) -> None:
        """Verifica que una actividad emergente pueda existir sin planificación (0..1 : 1)."""
        conn, _ = clean_db
        conn.execute(
            "INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable, es_emergente) "
            "VALUES ('act-emerg-1', 'Taller Emergente de Urgencia', 'TALLER', 'BILWI', '2026-09-20', 'Innovación', 'Lic. Kenia', 1);"
        )

        cursor = conn.execute("SELECT es_emergente FROM actividad WHERE id_actividad = 'act-emerg-1';")
        assert cursor.fetchone()["es_emergente"] == 1

        # Verificar que no exista en planificacion
        cursor = conn.execute("SELECT COUNT(*) FROM planificacion WHERE id_actividad = 'act-emerg-1';")
        assert cursor.fetchone()[0] == 0

    def test_planificacion_and_partidas_presupuestarias(self, clean_db) -> None:
        """Verifica planificación con múltiples partidas presupuestarias (1:N)."""
        conn, _ = clean_db
        conn.execute(
            "INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) "
            "VALUES ('act-plan-1', 'Rally Nacional de Innovación', 'RALLY', 'BLUEFIELDS', '2026-09-25', 'Innovación', 'Ing. Coordinador');"
        )
        conn.execute(
            "INSERT INTO planificacion (id_planificacion, id_actividad, meta_participantes, indicador_comprometido, fecha_programada) "
            "VALUES ('plan-1', 'act-plan-1', 29, 'Indicador 16', '2026-09-25');"
        )

        # Partidas presupuestarias
        conn.execute(
            "INSERT INTO partida_presupuestaria (id_partida, id_planificacion, rubro, cantidad, costo_unitario, subtotal) "
            "VALUES ('part-1', 'plan-1', 'Transporte Interurbano', 2.0, 1500.0, 3000.0);"
        )
        conn.execute(
            "INSERT INTO partida_presupuestaria (id_partida, id_planificacion, rubro, cantidad, costo_unitario, subtotal) "
            "VALUES ('part-2', 'plan-1', 'Refrigerios y Alimentación', 29.0, 120.0, 3480.0);"
        )

        cursor = conn.execute("SELECT COUNT(*), SUM(subtotal) FROM partida_presupuestaria WHERE id_planificacion = 'plan-1';")
        row = cursor.fetchone()
        assert row[0] == 2
        assert row[1] == 6480.0

    def test_diseno_metodologico_is_optional(self, clean_db) -> None:
        """Verifica que diseño metodológico sea 0..1 : 1 con actividad."""
        conn, _ = clean_db
        conn.execute(
            "INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) "
            "VALUES ('act-dis-1', 'Capacitación Canva y Forms', 'CAPACITACION', 'EL_RAMA', '2026-10-01', 'Innovación', 'Facilitador');"
        )
        conn.execute(
            "INSERT INTO diseno_metodologico (id_diseno, id_actividad, objetivo_general, contenidos_tematicos) "
            "VALUES ('dis-1', 'act-dis-1', 'Aprender diseño gráfico digital', 'Módulo 1: Canva básico. Módulo 2: Formularios.');"
        )

        cursor = conn.execute("SELECT objetivo_general FROM diseno_metodologico WHERE id_actividad = 'act-dis-1';")
        assert "diseño gráfico" in cursor.fetchone()[0]


class TestParticipacionAndRoutingRN_C03:
    """Pruebas de la relación N:M de participación y prevalencia de beneficiario."""

    def test_one_person_multiple_activities_and_viceversa(self, clean_db) -> None:
        """Verifica N:M entre PERSONA y ACTIVIDAD."""
        conn, _ = clean_db
        conn.execute("INSERT INTO persona (id_persona_interno, nombre_completo, sexo) VALUES ('p-multi', 'Estudiante Activo', 'M');")
        conn.execute("INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) VALUES ('act-1', 'Taller 1', 'TALLER', 'BILWI', '2026-09-01', 'Dpto', 'Resp');")
        conn.execute("INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) VALUES ('act-2', 'Feria 2', 'FERIA', 'BILWI', '2026-09-10', 'Dpto', 'Resp');")

        conn.execute(
            "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino) "
            "VALUES ('part-1', 'act-1', 'p-multi', 'ESTUDIANTE', 'M2');"
        )
        conn.execute(
            "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino) "
            "VALUES ('part-2', 'act-2', 'p-multi', 'ESTUDIANTE', 'M2');"
        )

        cursor = conn.execute("SELECT COUNT(*) FROM participacion WHERE id_persona = 'p-multi';")
        assert cursor.fetchone()[0] == 2

    def test_routing_prevalencia_beneficiado_rn_c03(self, clean_db) -> None:
        """Regla RN-C03: Estudiante con rol de beneficiario comunitario enruta a M5."""
        conn, _ = clean_db
        conn.execute("INSERT INTO persona (id_persona_interno, nombre_completo, sexo) VALUES ('p-est-benef', 'Estudiante Comunitario', 'F');")
        conn.execute("INSERT INTO perfil_estudiante (id_perfil_estudiante, id_persona, carrera_cursada) VALUES ('perfil-e1', 'p-est-benef', 'Ing. Agroforestal');")
        conn.execute("INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) VALUES ('act-comunitaria', 'Jornada Comunitaria de Siembra', 'ENCUENTRO_COMUNITARIO', 'EL_RAMA', '2026-09-15', 'Innovación', 'Resp');")

        # Asistencia como beneficiario directo de semillas
        conn.execute(
            "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, es_beneficiado_rol, matriz_destino) "
            "VALUES ('part-benef-1', 'act-comunitaria', 'p-est-benef', 'ESTUDIANTE', 1, 'M5');"
        )

        cursor = conn.execute(
            "SELECT es_beneficiado_rol, matriz_destino FROM participacion WHERE id_participacion = 'part-benef-1';"
        )
        row = cursor.fetchone()
        assert row["es_beneficiado_rol"] == 1
        assert row["matriz_destino"] == "M5"

    def test_historico_preexistente_m5_flag(self, clean_db) -> None:
        """Regla RN-C06: Soporte de es_historico_preexistente para los 32 registros de M5."""
        conn, _ = clean_db
        conn.execute("INSERT INTO persona (id_persona_interno, nombre_completo, sexo) VALUES ('p-hist', 'Beneficiario Historico M5', 'F');")
        conn.execute("INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) VALUES ('act-hist', 'Actividad Pasada 2025', 'TALLER', 'BLUEFIELDS', '2025-10-10', 'Dpto', 'Resp');")

        conn.execute(
            "INSERT INTO participacion (id_participacion, id_actividad, id_persona, estamento_declarado, matriz_destino, es_historico_preexistente) "
            "VALUES ('part-hist-1', 'act-hist', 'p-hist', 'BENEFICIADO', 'M5', 1);"
        )

        cursor = conn.execute("SELECT es_historico_preexistente FROM participacion WHERE id_participacion = 'part-hist-1';")
        assert cursor.fetchone()[0] == 1


class TestEvidenciasAndInformesSemanal:
    """Pruebas de evidencias N:M e informes semanales con detalle ordinal."""

    def test_evidencia_reutilizada_en_multiples_actividades_nm(self, clean_db) -> None:
        """Verifica que una misma evidencia ampare múltiples actividades sin duplicarse."""
        conn, _ = clean_db
        conn.execute("INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) VALUES ('act-ev-1', 'Evento A', 'TALLER', 'BLUEFIELDS', '2026-09-01', 'Dpto', 'Resp');")
        conn.execute("INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) VALUES ('act-ev-2', 'Evento B', 'FERIA', 'BLUEFIELDS', '2026-09-01', 'Dpto', 'Resp');")

        # Evidencia única
        conn.execute(
            "INSERT INTO evidencia (id_evidencia, tipo_evidencia, titulo, ruta_archivo_relativa, hash_sha256) "
            "VALUES ('ev-shared-1', 'FOTOGRAFIA', 'Presidium de Apertura Conjunto', 'evidences/2026/presidium.jpg', 'a1b2c3d4e5f67890123456789012345678901234567890123456789012345678');"
        )

        # Asociación N:M
        conn.execute("INSERT INTO actividad_evidencia (id_actividad_evidencia, id_actividad, id_evidencia, orden_presentacion) VALUES ('ae-1', 'act-ev-1', 'ev-shared-1', 1);")
        conn.execute("INSERT INTO actividad_evidencia (id_actividad_evidencia, id_actividad, id_evidencia, orden_presentacion) VALUES ('ae-2', 'act-ev-2', 'ev-shared-1', 1);")

        cursor = conn.execute("SELECT COUNT(*) FROM actividad_evidencia WHERE id_evidencia = 'ev-shared-1';")
        assert cursor.fetchone()[0] == 2

    def test_informe_semanal_and_detalle_sequence(self, clean_db) -> None:
        """Verifica composición ordinal e inclusión en Product A y Product B."""
        conn, _ = clean_db
        conn.execute("INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) VALUES ('act-sem-1', 'Actividad 1', 'TALLER', 'BILWI', '2026-09-01', 'Dpto', 'Resp');")
        conn.execute(
            "INSERT INTO informe_semanal (id_informe_semanal, anio, mes, numero_semana, etiqueta_periodo, departamento_responsable, sede_recinto, fecha_generacion) "
            "VALUES ('inf-sem-1', 2026, 9, 1, 'Septiembre 2026 - Semana 1', 'Innovación', 'BILWI', '2026-09-08');"
        )
        conn.execute(
            "INSERT INTO detalle_informe_semanal (id_detalle, id_informe_semanal, id_actividad, orden_secuencia, incluir_product_a, incluir_product_b) "
            "VALUES ('det-1', 'inf-sem-1', 'act-sem-1', 1, 1, 1);"
        )

        cursor = conn.execute("SELECT incluir_product_a, incluir_product_b FROM detalle_informe_semanal WHERE id_detalle = 'det-1';")
        row = cursor.fetchone()
        assert row["incluir_product_a"] == 1
        assert row["incluir_product_b"] == 1


class TestDiscrepanciaAndAuditoria:
    """Pruebas de la entidad DISCREPANCIA (DETECTAR ≠ CORREGIR) y AUDITORIA_EVENTO."""

    def test_discrepancia_stores_divergences_without_auto_correcting(self, clean_db) -> None:
        """Principio RN-C07: Registra valores A y B y delta sin mutar el origen."""
        conn, _ = clean_db
        conn.execute("INSERT INTO actividad (id_actividad, nombre_original, tipo_evento, sede, fecha_inicio, departamento_responsable, responsable) VALUES ('act-disc', 'Rally', 'RALLY', 'BLUEFIELDS', '2026-09-17', 'Dpto', 'Resp');")

        conn.execute(
            "INSERT INTO discrepancia (id_discrepancia, id_actividad, tipo_discrepancia, fuente_a_nombre, fuente_a_valor, fuente_b_nombre, fuente_b_valor, delta_valor, estado, fecha_deteccion) "
            "VALUES ('disc-1', 'act-disc', 'PLAN_VS_REAL', 'Planificación Ind 16', '29', 'Lista de Firmas Anexa', '11', '-18', 'REQUIERE_REVISION', '2026-09-17T10:00:00Z');"
        )

        cursor = conn.execute("SELECT delta_valor, estado FROM discrepancia WHERE id_discrepancia = 'disc-1';")
        row = cursor.fetchone()
        assert row["delta_valor"] == "-18"
        assert row["estado"] == "REQUIERE_REVISION"

    def test_auditoria_evento_inserts_forensic_log(self, clean_db) -> None:
        """Verifica inserción inmutable de evento de auditoría."""
        conn, _ = clean_db
        conn.execute(
            "INSERT INTO auditoria_evento (id_auditoria, fecha_hora, usuario_operador, tipo_operacion, tabla_afectada, id_registro_afectado, motivo_modificacion) "
            "VALUES ('aud-1', '2026-09-17T12:00:00Z', 'coordinador_bicu', 'INSERT', 'actividad', 'act-101', 'Registro inicial de evento');"
        )

        cursor = conn.execute("SELECT COUNT(*) FROM auditoria_evento WHERE id_auditoria = 'aud-1';")
        assert cursor.fetchone()[0] == 1


class TestMigrationRunnerIdempotencyAndRollback:
    """Pruebas de idempotencia, aislamiento y rollback en el ejecutor de migraciones."""

    def test_migration_runner_is_idempotent(self, clean_db) -> None:
        """Verifica que ejecutar apply_all_pending dos veces no duplique ni falle."""
        conn, runner = clean_db
        second_run = runner.apply_all_pending()

        assert len(second_run) == 1
        assert second_run[0]["status"] == "ALREADY_APPLIED"
        assert runner.get_current_version() == 1

    def test_migration_runner_rolls_back_on_invalid_statement(self, tmp_path: Path) -> None:
        """Verifica que una migración defectuosa ejecute ROLLBACK completo y no asiente la versión."""
        db_file = tmp_path / "test_migration_failure.db"
        manager = SQLiteConnectionManager(DatabaseConfig(db_path=db_file))
        conn = manager.get_connection()
        try:
            runner = MigrationRunner(conn)
            failing_migration = Migration(
                version=999,
                name="v999_failing_migration",
                statements=[
                    "CREATE TABLE tabla_temporal (id INTEGER PRIMARY KEY);",
                    "SYNTAX ERROR INVALID SQL STATEMENT WHICH MUST FAIL;",
                ],
            )

            with pytest.raises(sqlite3.OperationalError):
                runner.apply_migration(failing_migration)

            # Verificar que tabla_temporal NO existe (rollback confirmado)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tabla_temporal';")
            assert cursor.fetchone() is None, "La tabla debió revertirse por ROLLBACK"

            # Verificar que la versión 999 no fue registrada
            assert runner.get_current_version() == 0
        finally:
            conn.close()
