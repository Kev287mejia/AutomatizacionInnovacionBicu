"""Pruebas unitarias de contratos, modelos, DTOs, fakes y arquitectura de la capa Application.

Verifica:
1. Construcción e inmutabilidad de los 14 Commands oficiales.
2. Construcción e integridad de las 9 Queries oficiales.
3. Tipado y transporte en DTOs de entrada y salida.
4. Persistencia en memoria de los 6 repositorios Fake (cumpliendo contratos sin lógica de negocio).
5. Ciclo transaccional y reversión (rollback) en InMemoryUnitOfWork.
6. Aislamiento estricto de dependencias de infraestructura mediante inspección de árbol sintáctico (AST).
"""

import ast
from datetime import date
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.core.constants.participant_types import CategoriaParticipacion
from app.core.exceptions.persistence_exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    TransactionError,
)
from app.core.models.activity import Activity
from app.core.models.discrepancy import (
    Discrepancia,
    EstadoDiscrepancia,
    SeveridadDiscrepancia,
    TipoDiscrepancia,
)
from app.core.models.evidence import Evidencia, TipoEvidencia
from app.core.models.participation import Participation
from app.core.models.person import Person
from app.core.models.weekly_report import DetalleInformeSemanal, InformeSemanal
from app.core.models.validation_result import ValidationResult, NivelValidacion

# Imports de la capa Application
from app.application.commands import (
    RegistrarActividadCommand,
    AsignarPlanificacionCommand,
    AsignarDisenoMetodologicoCommand,
    RegistrarInformeActividadCommand,
    RegistrarPersonaCommand,
    RegistrarParticipacionIndividualCommand,
    IngestarListaAsistenciaCommand,
    RegistrarEvidenciaDigitalCommand,
    VincularEvidenciaActividadCommand,
    DesvincularEvidenciaActividadCommand,
    CrearInformeSemanalCommand,
    AsociarActividadesInformeSemanalCommand,
    RegistrarDiscrepanciaCommand,
    ResolverRevisionDiscrepanciaCommand,
)
from app.application.queries import (
    ConsultarActividadesPorPeriodoQuery,
    ObtenerDetalleActividadQuery,
    BuscarPersonasPorNombreQuery,
    ObtenerPersonaPorIdQuery,
    ConsultarParticipantesPorActividadQuery,
    ConsultarParticipantesEnRevisionQuery,
    ConsultarEvidenciasActividadQuery,
    ConsultarInformeSemanalPorPeriodoQuery,
    ConsultarDiscrepanciasPendientesQuery,
)
from app.application.dto import (
    FilaParticipanteIngestaDTO,
    PartidaPresupuestariaDTO,
    DetalleActividadInformeDTO,
    IngestaListaAsistenciaResultDTO,
    ActividadResumenDTO,
    ActividadDetalleDTO,
    PersonaResumenDTO,
    PersonaDetalleDTO,
    ParticipacionDetalleDTO,
    EvidenciaVinculadaDTO,
    DiscrepanciaDetalleDTO,
    InformeSemanalCompletoDTO,
)
from app.application.fakes import (
    InMemoryActividadRepository,
    InMemoryPersonaRepository,
    InMemoryParticipacionRepository,
    InMemoryEvidenciaRepository,
    InMemoryInformeSemanalRepository,
    InMemoryDiscrepanciaRepository,
    InMemoryUnitOfWork,
)


# ==============================================================================
# 1. PRUEBAS DE COMMANDS
# ==============================================================================

class TestApplicationCommands:
    """Verifica construcción, validación e inmutabilidad de los Commands."""

    def test_registrar_actividad_command(self):
        cmd = RegistrarActividadCommand(
            nombre_actividad_original="Taller de Robótica",
            fecha_evento=date(2026, 9, 15),
            sede="Bluefields",
            departamento="RACCS",
        )
        assert cmd.nombre_actividad_original == "Taller de Robótica"
        assert cmd.sede == "Bluefields"
        assert cmd.nombre_actividad_oficial is None

        # Verificar inmutabilidad (frozen)
        with pytest.raises(ValidationError):
            cmd.nombre_actividad_original = "Nuevo Nombre"  # type: ignore

    def test_asignar_planificacion_command(self):
        partida = PartidaPresupuestariaDTO(
            rubro="Material Didáctico",
            cantidad=5,
            costo_unitario=100.0,
            subtotal=500.0,
        )
        cmd = AsignarPlanificacionCommand(
            id_actividad="act-123",
            anio=2026,
            mes=9,
            semana=2,
            meta_participantes=30,
            partidas_presupuestarias=[partida],
        )
        assert cmd.id_actividad == "act-123"
        assert len(cmd.partidas_presupuestarias) == 1
        assert cmd.partidas_presupuestarias[0].subtotal == 500.0

    def test_asignar_diseno_metodologico_command(self):
        cmd = AsignarDisenoMetodologicoCommand(
            id_actividad="act-123",
            objetivo_general="Capacitar en metodologías ágiles",
            horas_duracion=8,
        )
        assert cmd.id_actividad == "act-123"
        assert cmd.horas_duracion == 8

    def test_registrar_informe_actividad_command(self):
        cmd = RegistrarInformeActividadCommand(
            id_actividad="act-123",
            ruta_archivo_word="informes/act_123.docx",
            hash_sha256="abcdef1234567890",
            total_participantes_declarados=25,
        )
        assert cmd.hash_sha256 == "abcdef1234567890"

    def test_registrar_persona_command_cedula_nullable(self):
        # Caso con cédula None (RN-C04)
        cmd1 = RegistrarPersonaCommand(
            nombre_completo="Juan Pérez",
            cedula=None,
            edad=22,
        )
        assert cmd1.cedula is None
        assert cmd1.nombre_completo == "Juan Pérez"

        # Caso con cédula provista
        cmd2 = RegistrarPersonaCommand(
            nombre_completo="María López",
            cedula="601-010101-1001A",
        )
        assert cmd2.cedula == "601-010101-1001A"

    def test_registrar_participacion_individual_command(self):
        cmd = RegistrarParticipacionIndividualCommand(
            id_actividad="act-123",
            id_persona="per-456",
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            nivel_confianza_identidad=1,
        )
        assert cmd.id_actividad == "act-123"
        assert cmd.categoria_participacion == CategoriaParticipacion.ESTUDIANTE

    def test_ingestar_lista_asistencia_command(self):
        fila = FilaParticipanteIngestaDTO(
            nombre_fuente="Carlos García",
            cedula_fuente=None,
            sexo_fuente="M",
        )
        cmd = IngestarListaAsistenciaCommand(
            id_actividad="act-123",
            fuente_archivo="lista_asistencia.xlsx",
            filas_participantes=[fila],
        )
        assert cmd.id_actividad == "act-123"
        assert len(cmd.filas_participantes) == 1

    def test_evidencia_commands(self):
        cmd_reg = RegistrarEvidenciaDigitalCommand(
            titulo="Foto Grupal",
            tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
            hash_sha256="hash123",
        )
        assert cmd_reg.titulo == "Foto Grupal"

        cmd_link = VincularEvidenciaActividadCommand(
            id_actividad="act-123",
            id_evidencia="evi-789",
            orden_presentacion=2,
            seccion_informe="GALERIA",
        )
        assert cmd_link.orden_presentacion == 2

        cmd_unlink = DesvincularEvidenciaActividadCommand(
            id_actividad="act-123",
            id_evidencia="evi-789",
        )
        assert cmd_unlink.id_actividad == "act-123"

    def test_informe_semanal_commands(self):
        cmd_crear = CrearInformeSemanalCommand(
            anio=2026,
            mes=9,
            numero_semana=3,
            etiqueta_periodo="Semana 3 - Septiembre 2026",
            departamento_responsable="Vinculación",
            sede_recinto="Bluefields",
        )
        assert cmd_crear.numero_semana == 3

        detalle = DetalleActividadInformeDTO(
            id_actividad="act-123",
            orden_secuencia=1,
            incluir_product_a=True,
            incluir_product_b=True,
        )
        cmd_asoc = AsociarActividadesInformeSemanalCommand(
            id_informe_semanal="inf-999",
            detalles=[detalle],
        )
        assert len(cmd_asoc.detalles) == 1

    def test_discrepancia_commands(self):
        cmd_reg = RegistrarDiscrepanciaCommand(
            id_actividad="act-123",
            tipo_discrepancia=TipoDiscrepancia.PLAN_VS_REAL,
            severidad=SeveridadDiscrepancia.WARNING,
            fuente_a_nombre="Plan.meta",
            fuente_a_valor="30",
            fuente_b_nombre="Asistencias.reales",
            fuente_b_valor="20",
            delta_valor="-10",
        )
        assert cmd_reg.delta_valor == "-10"

        cmd_res = ResolverRevisionDiscrepanciaCommand(
            id_discrepancia="disc-123",
            nuevo_estado=EstadoDiscrepancia.ACLARADO,
            justificacion_aclaratoria="Se constató lluvia intensa",
            usuario_revisor="auditor_01",
        )
        assert cmd_res.usuario_revisor == "auditor_01"


# ==============================================================================
# 2. PRUEBAS DE QUERIES
# ==============================================================================

class TestApplicationQueries:
    """Verifica construcción y parámetros de las Queries."""

    def test_queries_construction(self):
        q_act = ConsultarActividadesPorPeriodoQuery(
            fecha_inicio="2026-09-01",
            fecha_fin="2026-09-30",
            sede="Bilwi",
        )
        assert q_act.sede == "Bilwi"

        q_det = ObtenerDetalleActividadQuery(id_actividad="act-123")
        assert q_det.id_actividad == "act-123"

        q_per_nom = BuscarPersonasPorNombreQuery(nombre_query="López", limite=5)
        assert q_per_nom.limite == 5

        q_per_id = ObtenerPersonaPorIdQuery(id_persona_interno="per-456")
        assert q_per_id.id_persona_interno == "per-456"

        q_part_act = ConsultarParticipantesPorActividadQuery(id_actividad="act-123")
        assert q_part_act.id_actividad == "act-123"

        q_part_rev = ConsultarParticipantesEnRevisionQuery(id_actividad=None)
        assert q_part_rev.id_actividad is None

        q_evi = ConsultarEvidenciasActividadQuery(id_actividad="act-123")
        assert q_evi.id_actividad == "act-123"

        q_inf = ConsultarInformeSemanalPorPeriodoQuery(
            anio=2026, mes=9, numero_semana=2, sede="Bluefields"
        )
        assert q_inf.numero_semana == 2

        q_disc = ConsultarDiscrepanciasPendientesQuery(severidad="WARNING")
        assert q_disc.severidad == "WARNING"


# ==============================================================================
# 3. PRUEBAS DE DTOs
# ==============================================================================

class TestApplicationDTOs:
    """Verifica tipado y estructura de los DTOs."""

    def test_fila_participante_ingesta_dto(self):
        dto = FilaParticipanteIngestaDTO(
            nombre_fuente="Ana Rosa Morales",
            cedula_fuente=None,
            sexo_fuente="F",
            carrera_cargo_fuente="Enfermería",
        )
        assert dto.nombre_fuente == "Ana Rosa Morales"
        assert dto.cedula_fuente is None

    def test_ingesta_lista_asistencia_result_dto(self):
        hallazgo = ValidationResult(
            nivel=NivelValidacion.WARNING,
            codigo="WARN_CEDULA_AUSENTE",
            mensaje="Participante sin cédula registrada",
        )
        dto = IngestaListaAsistenciaResultDTO(
            id_actividad="act-123",
            total_procesados=10,
            nuevas_personas_registradas=8,
            personas_existentes_vinculadas=2,
            participaciones_creadas=10,
            participaciones_en_revision=1,
            hallazgos_validacion=[hallazgo],
        )
        assert dto.total_procesados == 10
        assert len(dto.hallazgos_validacion) == 1

    def test_proyecciones_salida(self):
        resumen_act = ActividadResumenDTO(
            id_actividad="act-1",
            nombre_actividad="Feria",
            total_participantes=45,
        )
        assert resumen_act.total_participantes == 45

        detalle_part = ParticipacionDetalleDTO(
            id_participacion="part-1",
            id_actividad="act-1",
            id_persona="per-1",
            nombre_completo="Carlos Morales",
            categoria="ESTUDIANTE",
            matriz_destino="M2",
        )
        assert detalle_part.matriz_destino == "M2"


# ==============================================================================
# 4. PRUEBAS DE FAKES EN MEMORIA
# ==============================================================================

class TestInMemoryRepositories:
    """Verifica las implementaciones Fake de los 6 repositorios."""

    def test_in_memory_actividad_repo(self):
        repo = InMemoryActividadRepository()
        act = Activity(
            id_actividad="act-01",
            nombre_actividad_original="Feria Tecnológica",
            fecha_evento="2026-09-10",
            sede="Bluefields",
        )
        repo.save(act)
        assert repo.count() == 1
        assert repo.exists("act-01") is True
        assert repo.exists("act-99") is False

        recup = repo.get_by_id("act-01")
        assert recup is not None
        assert recup.nombre_actividad_original == "Feria Tecnológica"

        filtradas = repo.list_by_periodo("2026-09-01", "2026-09-15", sede="Bluefields")
        assert len(filtradas) == 1

    def test_in_memory_persona_repo_unique_cedula_and_nullable(self):
        repo = InMemoryPersonaRepository()

        # 1. Registrar personas sin cédula (RN-C04: múltiples None permitidos)
        p1 = Person(id_persona_interno="p1", nombre_completo="Persona Sin Cédula 1", cedula=None)
        p2 = Person(id_persona_interno="p2", nombre_completo="Persona Sin Cédula 2", cedula=None)
        repo.save(p1)
        repo.save(p2)
        assert repo.count() == 2

        # 2. Registrar persona con cédula
        p3 = Person(
            id_persona_interno="p3",
            nombre_completo="Persona Con Cédula",
            cedula="601-121290-0001A",
            numero_unico="EST-2026-01",
        )
        repo.save(p3)
        assert repo.get_by_cedula("601-121290-0001A") is not None
        assert repo.get_by_numero_institucional("EST-2026-01") is not None

        # 3. Simular UNIQUE en cédula no nula: colisión con ID distinto lanza EntityAlreadyExistsError
        p3_duplicada = Person(
            id_persona_interno="p4",
            nombre_completo="Intento Duplicado",
            cedula="601-121290-0001A",
        )
        with pytest.raises(EntityAlreadyExistsError):
            repo.save(p3_duplicada)

        # 4. Búsqueda por nombre
        encontrados = repo.search_by_nombre("Persona", limite=2)
        assert len(encontrados) == 2

    def test_in_memory_participacion_repo(self):
        repo = InMemoryParticipacionRepository()
        part1 = Participation(
            id_participacion="part-01",
            id_actividad="act-01",
            id_persona="p1",
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            requiere_revision=False,
        )
        part2 = Participation(
            id_participacion="part-02",
            id_actividad="act-01",
            id_persona="p2",
            categoria_participacion=CategoriaParticipacion.BENEFICIADO,
            requiere_revision=True,
            motivo_revision="Duda de rol",
        )
        repo.save_batch([part1, part2])

        assert repo.count_by_actividad("act-01") == 2
        assert len(repo.get_by_actividad("act-01")) == 2
        assert len(repo.list_requieren_revision()) == 1

        unívoca = repo.get_by_actividad_and_persona("act-01", "p1")
        assert unívoca is not None
        assert unívoca.id_participacion == "part-01"

    def test_in_memory_evidencia_repo(self):
        repo = InMemoryEvidenciaRepository()
        evi = Evidencia(
            id_evidencia="evi-01",
            titulo="Foto Inauguración",
            hash_sha256="sha_hash_12345",
        )
        repo.save(evi)
        assert repo.get_by_hash("sha_hash_12345") is not None

        repo.link_actividad("act-01", "evi-01", orden=1, seccion="GALERIA")
        vinculadas = repo.get_by_actividad("act-01")
        assert len(vinculadas) == 1
        ev_recup, orden, seccion = vinculadas[0]
        assert ev_recup.id_evidencia == "evi-01"
        assert orden == 1
        assert seccion == "GALERIA"

        repo.unlink_actividad("act-01", "evi-01")
        assert len(repo.get_by_actividad("act-01")) == 0

    def test_in_memory_informe_semanal_repo(self):
        repo = InMemoryInformeSemanalRepository()
        inf = InformeSemanal(
            id_informe_semanal="inf-01",
            anio=2026,
            mes=9,
            numero_semana=2,
            etiqueta_periodo="Semana 2 - Septiembre 2026",
            departamento_responsable="Innovación",
            sede_recinto="Bluefields",
        )
        detalle = DetalleInformeSemanal(
            id_detalle="det-01",
            id_informe_semanal="inf-01",
            id_actividad="act-01",
            orden_secuencia=1,
        )
        repo.save(inf, detalles=[detalle])

        recup = repo.get_by_periodo(2026, 9, 2, "Bluefields")
        assert recup is not None
        assert recup.id_informe_semanal == "inf-01"

        detalles = repo.get_detalles("inf-01")
        assert len(detalles) == 1
        assert detalles[0].orden_secuencia == 1

    def test_in_memory_discrepancia_repo_detectar_no_corregir(self):
        repo = InMemoryDiscrepanciaRepository()
        disc = Discrepancia(
            id_discrepancia="disc-01",
            id_actividad="act-01",
            fuente_a_nombre="Meta Plan",
            fuente_a_valor="50",
            fuente_b_nombre="Asistencia Real",
            fuente_b_valor="35",
            delta_valor="-15",
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
        )
        repo.save(disc)

        pendientes = repo.list_pendientes()
        assert len(pendientes) == 1

        # Registrar revisión humana: no debe alterar fuente_a_valor ni fuente_b_valor (RN-C07)
        repo.registrar_revision(
            id_discrepancia="disc-01",
            nuevo_estado="ACLARADO",
            justificacion="Justificación pericial por lluvia",
            usuario_revisor="auditor_kenia",
        )

        actualizada = repo.get_by_id("disc-01")
        assert actualizada is not None
        assert actualizada.estado == EstadoDiscrepancia.ACLARADO
        assert actualizada.fuente_a_valor == "50"  # Inalterado
        assert actualizada.fuente_b_valor == "35"  # Inalterado
        assert actualizada.delta_valor == "-15"    # Inalterado
        assert actualizada.justificacion_aclaratoria == "Justificación pericial por lluvia"
        assert actualizada.usuario_revisor == "auditor_kenia"


# ==============================================================================
# 5. PRUEBAS DE IN MEMORY UNIT OF WORK
# ==============================================================================

class TestInMemoryUnitOfWork:
    """Verifica transaccionalidad, reversión por rollback y detección de acceso fuera de contexto."""

    def test_access_outside_context_raises_transaction_error(self):
        uow = InMemoryUnitOfWork()
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

    def test_commit_persists_changes(self):
        uow = InMemoryUnitOfWork()
        with uow:
            act = Activity(
                id_actividad="act-commit-1",
                nombre_actividad_original="Actividad Confirmada",
            )
            uow.actividades.save(act)
            uow.commit()

        # Verificar que persiste en el repositorio base
        assert uow._repo_actividades.exists("act-commit-1") is True

    def test_rollback_reverts_uncommitted_changes(self):
        uow = InMemoryUnitOfWork()
        with uow:
            act = Activity(
                id_actividad="act-rollback-1",
                nombre_actividad_original="Actividad Descartada",
            )
            uow.actividades.save(act)
            assert uow.actividades.exists("act-rollback-1") is True
            uow.rollback()

        # Después de rollback, no debe existir
        assert uow._repo_actividades.exists("act-rollback-1") is False

    def test_exception_in_context_triggers_automatic_rollback(self):
        uow = InMemoryUnitOfWork()
        with pytest.raises(RuntimeError, match="Fallo simulado"):
            with uow:
                per = Person(
                    id_persona_interno="per-err-1",
                    nombre_completo="Persona Revertida",
                )
                uow.personas.save(per)
                raise RuntimeError("Fallo simulado durante la operación")

        # Comprobar que los cambios fueron revertidos automáticamente
        assert uow._repo_personas.exists("per-err-1") is False

    def test_isolation_between_distinct_uow_instances(self):
        uow1 = InMemoryUnitOfWork()
        uow2 = InMemoryUnitOfWork()

        with uow1:
            uow1.actividades.save(Activity(
                id_actividad="act-uow1",
                nombre_actividad_original="Actividad de UoW 1",
            ))
            uow1.commit()

        assert uow1._repo_actividades.exists("act-uow1") is True
        assert uow2._repo_actividades.exists("act-uow1") is False


# ==============================================================================
# 6. VERIFICACIÓN ARQUITECTÓNICA DE INDEPENDENCIA DE INFRAESTRUCTURA (AST)
# ==============================================================================

class TestApplicationArchitectureIsolation:
    """Verifica mediante análisis sintáctico que app/application no importe infraestructura ni use SQL."""

    FORBIDDEN_MODULES = {
        "sqlite3",
        "openpyxl",
        "xlsxwriter",
        "docx",
        "python-docx",
        "customtkinter",
        "tkinter",
        "app.infrastructure",
    }

    FORBIDDEN_SQL_PATTERNS = [
        "SELECT ",
        "INSERT INTO ",
        "UPDATE ",
        "DELETE FROM ",
        "CREATE TABLE ",
        "DROP TABLE ",
    ]

    def test_no_forbidden_imports_in_application(self):
        app_dir = Path(__file__).resolve().parent.parent / "app" / "application"
        python_files = list(app_dir.rglob("*.py"))
        assert len(python_files) > 0, "No se encontraron archivos en app/application"

        violaciones = []
        for file_path in python_files:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in self.FORBIDDEN_MODULES:
                            if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                                violaciones.append(f"{file_path.name}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for forbidden in self.FORBIDDEN_MODULES:
                            if node.module == forbidden or node.module.startswith(forbidden + "."):
                                violaciones.append(f"{file_path.name}: from {node.module} import ...")

        assert not violaciones, f"Violaciones de Clean Architecture en imports: {violaciones}"

    def test_no_sql_queries_in_application(self):
        app_dir = Path(__file__).resolve().parent.parent / "app" / "application"
        python_files = list(app_dir.rglob("*.py"))

        violaciones = []
        for file_path in python_files:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                # Inspeccionar constantes de cadenas en el código
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val_upper = node.value.upper()
                    for sql_pat in self.FORBIDDEN_SQL_PATTERNS:
                        if sql_pat in val_upper:
                            violaciones.append(f"{file_path.name}: posible consulta SQL '{sql_pat.strip()}' en '{node.value}'")

        assert not violaciones, f"Violaciones de Clean Architecture: SQL detectado en application: {violaciones}"
