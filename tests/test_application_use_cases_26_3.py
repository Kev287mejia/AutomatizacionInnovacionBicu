"""tests/test_application_use_cases_26_3.py

Pruebas unitarias, funcionales y arquitectónicas para los 6 Casos de Uso Principales
de la capa Application (Fase 26.3):
1. CU-ACT-01: RegistrarActividadUseCase
2. CU-ACT-02: AsignarPlanificacionUseCase
3. CU-ACT-03: AsignarDisenoMetodologicoUseCase
4. CU-ACT-04: RegistrarInformeActividadUseCase
5. CU-PER-01: RegistrarPersonaUseCase
6. CU-PAR-01: RegistrarParticipacionIndividualUseCase
7. Pruebas de Arquitectura y Aislamiento (AST)
"""

import ast
from datetime import date
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.core.exceptions.persistence_exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
)
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.application.commands import (
    RegistrarActividadCommand,
    AsignarPlanificacionCommand,
    AsignarDisenoMetodologicoCommand,
    RegistrarInformeActividadCommand,
    RegistrarPersonaCommand,
    RegistrarParticipacionIndividualCommand,
)
from app.application.dto import (
    PartidaPresupuestariaDTO,
    ActividadDetalleDTO,
    PlanificacionAsignadaDTO,
    DisenoMetodologicoAsignadoDTO,
    InformeActividadRegistradoDTO,
    PersonaDetalleDTO,
    ParticipacionDetalleDTO,
)
from app.application.fakes import (
    InMemoryActividadRepository,
    InMemoryPersonaRepository,
    InMemoryParticipacionRepository,
    InMemoryUnitOfWork,
)
from app.application.use_cases import (
    RegistrarActividadUseCase,
    AsignarPlanificacionUseCase,
    AsignarDisenoMetodologicoUseCase,
    RegistrarInformeActividadUseCase,
    RegistrarPersonaUseCase,
    RegistrarParticipacionIndividualUseCase,
)


# ==============================================================================
# 1. PRUEBAS: CU-ACT-01 RegistrarActividadUseCase
# ==============================================================================

class TestRegistrarActividadUseCase:
    """Pruebas de creación, persistencia y validación de actividades."""

    def test_registrar_actividad_valida(self):
        repo = InMemoryActividadRepository()
        use_case = RegistrarActividadUseCase(actividad_repo=repo)

        cmd = RegistrarActividadCommand(
            nombre_actividad_original="Feria de Innovación Territorial 2026",
            nombre_actividad_oficial="Feria de Innovación Territorial",
            fecha_evento=date(2026, 10, 15),
            sede="Bluefields",
            departamento="RACCS",
            municipio_evento="Bluefields",
            programa="Innovación y Emprendimiento",
            ambito="Regional",
            tipo_evento="FERIA",
            eje_linea_estrategica="Eje 2 - Emprendimiento",
            informacion_adicional="Fondos institucionales",
            fuente_origen="Plan_Operativo_2026.xlsx",
        )

        dto = use_case.execute(cmd)

        assert isinstance(dto, ActividadDetalleDTO)
        assert dto.nombre_actividad_original == "Feria de Innovación Territorial 2026"
        assert dto.nombre_actividad_oficial == "Feria de Innovación Territorial"
        assert dto.sede == "Bluefields"
        assert dto.fecha_evento == "2026-10-15"
        assert dto.id_actividad is not None

        # Verificar persistencia en el repositorio
        assert repo.exists(dto.id_actividad) is True
        guardada = repo.get_by_id(dto.id_actividad)
        assert guardada is not None
        assert guardada.nombre_actividad_original == "Feria de Innovación Territorial 2026"

    def test_registrar_actividad_persiste_correctamente(self):
        repo = InMemoryActividadRepository()
        use_case = RegistrarActividadUseCase(actividad_repo=repo)

        cmd = RegistrarActividadCommand(
            nombre_actividad_original="Taller de Robótica Educativa",
            sede="Bilwi",
        )
        dto = use_case.execute(cmd)

        assert repo.count() == 1
        assert repo.exists(dto.id_actividad) is True

    def test_registrar_actividad_nombre_vacio_falla(self):
        repo = InMemoryActividadRepository()
        use_case = RegistrarActividadUseCase(actividad_repo=repo)

        cmd = RegistrarActividadCommand(
            nombre_actividad_original="   ",
        )
        with pytest.raises((ValidationError, ValueError)):
            use_case.execute(cmd)



# ==============================================================================
# 2. PRUEBAS: CU-ACT-02 AsignarPlanificacionUseCase
# ==============================================================================

class TestAsignarPlanificacionUseCase:
    """Pruebas de asignación de metas y presupuesto a actividades."""

    def test_asignar_planificacion_actividad_existente(self):
        repo = InMemoryActividadRepository()
        actividad = Activity(
            id_actividad="act-plan-100",
            nombre_actividad_original="Taller de Desarrollo Web",
            sede="Bluefields",
        )
        repo.save(actividad)

        use_case = AsignarPlanificacionUseCase(actividad_repo=repo)

        partidas = [
            PartidaPresupuestariaDTO(
                rubro="Materiales Didácticos",
                cantidad=10,
                costo_unitario=50.0,
                subtotal=500.0,
            ),
            PartidaPresupuestariaDTO(
                rubro="Refrigerios",
                cantidad=25,
                costo_unitario=60.0,
                subtotal=1500.0,
            ),
        ]
        cmd = AsignarPlanificacionCommand(
            id_actividad="act-plan-100",
            anio=2026,
            mes=10,
            semana=2,
            meta_participantes=25,
            partidas_presupuestarias=partidas,
        )

        dto = use_case.execute(cmd)

        assert isinstance(dto, PlanificacionAsignadaDTO)
        assert dto.id_actividad == "act-plan-100"
        assert dto.anio == 2026
        assert dto.mes == 10
        assert dto.semana == 2
        assert dto.meta_participantes == 25
        assert dto.total_presupuesto == 2000.0
        assert dto.cantidad_partidas == 2

    def test_asignar_planificacion_actividad_inexistente_lanza_error(self):
        repo = InMemoryActividadRepository()
        use_case = AsignarPlanificacionUseCase(actividad_repo=repo)

        cmd = AsignarPlanificacionCommand(
            id_actividad="act-inexistente-999",
            anio=2026,
            mes=11,
            semana=1,
            meta_participantes=30,
        )

        with pytest.raises(EntityNotFoundError) as excinfo:
            use_case.execute(cmd)

        assert excinfo.value.entity_type == "Actividad"
        assert excinfo.value.entity_id == "act-inexistente-999"

    def test_asignar_planificacion_opcional_sin_partidas(self):
        repo = InMemoryActividadRepository()
        actividad = Activity(
            id_actividad="act-plan-200",
            nombre_actividad_original="Charla Informativa",
        )
        repo.save(actividad)

        use_case = AsignarPlanificacionUseCase(actividad_repo=repo)

        cmd = AsignarPlanificacionCommand(
            id_actividad="act-plan-200",
            anio=2026,
            mes=9,
            semana=4,
            meta_participantes=15,
            partidas_presupuestarias=[],
        )

        dto = use_case.execute(cmd)
        assert dto.total_presupuesto == 0.0
        assert dto.cantidad_partidas == 0


# ==============================================================================
# 3. PRUEBAS: CU-ACT-03 AsignarDisenoMetodologicoUseCase
# ==============================================================================

class TestAsignarDisenoMetodologicoUseCase:
    """Pruebas de asociación de diseño pedagógico y metodológico."""

    def test_asignar_diseno_metodologico_actividad_existente(self):
        repo = InMemoryActividadRepository()
        actividad = Activity(
            id_actividad="act-dis-100",
            nombre_actividad_original="Capacitación en Metodologías Ágiles",
        )
        repo.save(actividad)

        use_case = AsignarDisenoMetodologicoUseCase(actividad_repo=repo)

        cmd = AsignarDisenoMetodologicoCommand(
            id_actividad="act-dis-100",
            objetivo_general="Capacitar a los protagonistas en Scrum y Kanban",
            objetivos_especificos="1. Aprender artefactos. 2. Implementar sprints.",
            contenidos_tematicos="Módulo 1: Fundamentos. Módulo 2: Simulación.",
            metodologia="Taller práctico vivencial",
            horas_duracion=16,
            materiales_insumos="Pizarras, post-its, plumones",
            facilitadores="Ing. Facilitador Principal",
        )

        dto = use_case.execute(cmd)

        assert isinstance(dto, DisenoMetodologicoAsignadoDTO)
        assert dto.id_actividad == "act-dis-100"
        assert dto.objetivo_general == "Capacitar a los protagonistas en Scrum y Kanban"
        assert dto.horas_duracion == 16
        assert dto.facilitadores == "Ing. Facilitador Principal"

    def test_asignar_diseno_metodologico_actividad_inexistente_lanza_error(self):
        repo = InMemoryActividadRepository()
        use_case = AsignarDisenoMetodologicoUseCase(actividad_repo=repo)

        cmd = AsignarDisenoMetodologicoCommand(
            id_actividad="act-inexistente-555",
            objetivo_general="Objetivo sin actividad",
        )

        with pytest.raises(EntityNotFoundError) as excinfo:
            use_case.execute(cmd)

        assert excinfo.value.entity_type == "Actividad"
        assert excinfo.value.entity_id == "act-inexistente-555"


# ==============================================================================
# 4. PRUEBAS: CU-ACT-04 RegistrarInformeActividadUseCase
# ==============================================================================

class TestRegistrarInformeActividadUseCase:
    """Pruebas de registro de informe individual y custodia documental."""

    def test_registrar_informe_actividad_existente(self):
        repo = InMemoryActividadRepository()
        actividad = Activity(
            id_actividad="act-inf-100",
            nombre_actividad_original="Jornada de Vinculación Comunitaria",
        )
        repo.save(actividad)

        use_case = RegistrarInformeActividadUseCase(actividad_repo=repo)

        cmd = RegistrarInformeActividadCommand(
            id_actividad="act-inf-100",
            ruta_archivo_word="informes/2026/act_inf_100_informe.docx",
            hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            total_participantes_declarados=40,
        )

        dto = use_case.execute(cmd)

        assert isinstance(dto, InformeActividadRegistradoDTO)
        assert dto.id_actividad == "act-inf-100"
        assert dto.ruta_archivo_word == "informes/2026/act_inf_100_informe.docx"
        assert dto.hash_sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert dto.total_participantes_declarados == 40

    def test_registrar_informe_actividad_con_uow(self):
        uow = InMemoryUnitOfWork()
        with uow:
            uow.actividades.save(Activity(
                id_actividad="act-inf-uow-1",
                nombre_actividad_original="Actividad UoW",
            ))
            use_case = RegistrarInformeActividadUseCase(actividad_repo=uow.actividades)
            cmd = RegistrarInformeActividadCommand(
                id_actividad="act-inf-uow-1",
                ruta_archivo_word="informes/act_uow.docx",
                hash_sha256="abcd1234ef5678",
                total_participantes_declarados=12,
            )
            dto = use_case.execute(cmd)
            uow.commit()

        assert dto.id_actividad == "act-inf-uow-1"


    def test_registrar_informe_actividad_inexistente_lanza_error(self):
        repo = InMemoryActividadRepository()
        use_case = RegistrarInformeActividadUseCase(actividad_repo=repo)

        cmd = RegistrarInformeActividadCommand(
            id_actividad="act-inexistente-777",
            ruta_archivo_word="informes/inexistente.docx",
            hash_sha256="1234567890abcdef",
        )

        with pytest.raises(EntityNotFoundError) as excinfo:
            use_case.execute(cmd)

        assert excinfo.value.entity_type == "Actividad"
        assert excinfo.value.entity_id == "act-inexistente-777"


# ==============================================================================
# 5. PRUEBAS: CU-PER-01 RegistrarPersonaUseCase
# ==============================================================================

class TestRegistrarPersonaUseCase:
    """Pruebas del SSOT bio-demográfico y de la regla institucional RN-C04."""

    def test_registrar_persona_valida_con_cedula(self):
        repo = InMemoryPersonaRepository()
        use_case = RegistrarPersonaUseCase(persona_repo=repo)

        cmd = RegistrarPersonaCommand(
            nombre_completo="Carlos Alberto Mendoza Ruiz",
            nombres="Carlos Alberto",
            apellidos="Mendoza Ruiz",
            cedula="601-150898-0002A",
            numero_unico="CARNE-2026-001",
            sexo_normalizado="MASCULINO",
            edad=28,
            telefono="8888-1234",
            departamento_persona="RACCS",
            municipio_persona="Bluefields",
            carrera_original="Ingeniería en Sistemas",
        )

        dto = use_case.execute(cmd)

        assert isinstance(dto, PersonaDetalleDTO)
        assert dto.nombre_completo == "Carlos Alberto Mendoza Ruiz"
        assert dto.cedula == "601-150898-0002A"
        assert dto.numero_unico == "CARNE-2026-001"
        assert dto.edad == 28
        assert repo.exists(dto.id_persona_interno) is True

    def test_registrar_persona_cedula_none_preserva_null_rn_c04(self):
        """Regla RN-C04: La ausencia de cédula permanece estrictamente como None."""
        repo = InMemoryPersonaRepository()
        use_case = RegistrarPersonaUseCase(persona_repo=repo)

        cmd = RegistrarPersonaCommand(
            nombre_completo="María Elena Suazo Jackson",
            cedula=None,
            sexo_normalizado="FEMENINO",
            edad=21,
        )

        dto = use_case.execute(cmd)

        assert dto.cedula is None
        assert repo.exists(dto.id_persona_interno) is True

        persona_guardada = repo.get_by_id(dto.id_persona_interno)
        assert persona_guardada is not None
        assert persona_guardada.cedula is None

    def test_coexistencia_pacifica_multiples_personas_sin_cedula(self):
        """Múltiples personas con cédula=None coexisten sin error de colisión (RN-C04)."""
        repo = InMemoryPersonaRepository()
        use_case = RegistrarPersonaUseCase(persona_repo=repo)

        dto1 = use_case.execute(RegistrarPersonaCommand(
            nombre_completo="Participante Sin Cédula Uno",
            cedula=None,
        ))
        dto2 = use_case.execute(RegistrarPersonaCommand(
            nombre_completo="Participante Sin Cédula Dos",
            cedula=None,
        ))

        assert dto1.id_persona_interno != dto2.id_persona_interno
        assert repo.count() == 2
        assert repo.get_by_id(dto1.id_persona_interno).cedula is None
        assert repo.get_by_id(dto2.id_persona_interno).cedula is None

    def test_duplicidad_cedula_lanza_error_segun_contrato(self):
        """Si dos personas diferentes tienen la misma cédula oficial, se lanza EntityAlreadyExistsError."""
        repo = InMemoryPersonaRepository()
        use_case = RegistrarPersonaUseCase(persona_repo=repo)

        cmd1 = RegistrarPersonaCommand(
            nombre_completo="Primer Titular",
            cedula="601-010190-0001B",
        )
        use_case.execute(cmd1)

        cmd2 = RegistrarPersonaCommand(
            nombre_completo="Segundo Con Misma Cedula",
            cedula="601-010190-0001B",
        )

        with pytest.raises(EntityAlreadyExistsError) as excinfo:
            use_case.execute(cmd2)

        assert excinfo.value.entity_type == "Persona"
        assert excinfo.value.key_field == "cedula"
        assert excinfo.value.key_value == "601-010190-0001B"


# ==============================================================================
# 6. PRUEBAS: CU-PAR-01 RegistrarParticipacionIndividualUseCase
# ==============================================================================

class TestRegistrarParticipacionIndividualUseCase:
    """Pruebas de registro de asistencia individual e independencia de routing."""

    def test_registrar_participacion_individual_valida(self):
        act_repo = InMemoryActividadRepository()
        act_repo.save(Activity(
            id_actividad="act-part-1",
            nombre_actividad_original="Taller de Innovación",
        ))

        per_repo = InMemoryPersonaRepository()
        per_repo.save(Person(
            id_persona_interno="per-part-1",
            nombre_completo="Kevin Alexander Hodgson",
            cedula="601-200500-0003C",
        ))

        part_repo = InMemoryParticipacionRepository()
        use_case = RegistrarParticipacionIndividualUseCase(
            participacion_repo=part_repo,
            actividad_repo=act_repo,
            persona_repo=per_repo,
        )

        cmd = RegistrarParticipacionIndividualCommand(
            id_actividad="act-part-1",
            id_persona="per-part-1",
            categoria_participacion="ESTUDIANTE",
            nivel_confianza_identidad=1,
            fuente_origen="Lista_Asistencia_Taller.xlsx",
            observaciones="Asistencia puntual confirmada",
        )

        dto = use_case.execute(cmd)

        assert isinstance(dto, ParticipacionDetalleDTO)
        assert dto.id_actividad == "act-part-1"
        assert dto.id_persona == "per-part-1"
        assert dto.nombre_completo == "Kevin Alexander Hodgson"
        assert dto.cedula == "601-200500-0003C"
        assert dto.categoria == "ESTUDIANTE"

        # Verificar persistencia en el repositorio
        assert part_repo.count_by_actividad("act-part-1") == 1
        p_guardada = part_repo.get_by_id(dto.id_participacion)
        assert p_guardada is not None
        assert p_guardada.id_persona == "per-part-1"

    def test_no_aparicion_de_logica_de_routing_en_application(self):
        """Application NO debe forzar ni inferir routing hacia M2..M5."""
        act_repo = InMemoryActividadRepository()
        act_repo.save(Activity(
            id_actividad="act-noroute-1",
            nombre_actividad_original="Actividad Sin Routing Application",
        ))
        per_repo = InMemoryPersonaRepository()
        per_repo.save(Person(
            id_persona_interno="per-noroute-1",
            nombre_completo="Docente Participante",
        ))
        part_repo = InMemoryParticipacionRepository()

        use_case = RegistrarParticipacionIndividualUseCase(
            participacion_repo=part_repo,
            actividad_repo=act_repo,
            persona_repo=per_repo,
        )

        # Enviar rol DOCENTE: Application NO debe calcular ni asignar 'M3'
        cmd = RegistrarParticipacionIndividualCommand(
            id_actividad="act-noroute-1",
            id_persona="per-noroute-1",
            categoria_participacion="DOCENTE",
        )
        dto = use_case.execute(cmd)

        # El caso de uso debe preservar matriz_destino como None si no fue asignada por Domain
        assert dto.matriz_destino is None

    def test_registrar_participacion_actividad_inexistente_lanza_error(self):
        act_repo = InMemoryActividadRepository()
        per_repo = InMemoryPersonaRepository()
        per_repo.save(Person(
            id_persona_interno="per-existente-1",
            nombre_completo="Persona Existente",
        ))
        part_repo = InMemoryParticipacionRepository()

        use_case = RegistrarParticipacionIndividualUseCase(
            participacion_repo=part_repo,
            actividad_repo=act_repo,
            persona_repo=per_repo,
        )

        cmd = RegistrarParticipacionIndividualCommand(
            id_actividad="act-inexistente-000",
            id_persona="per-existente-1",
            categoria_participacion="ESTUDIANTE",
        )

        with pytest.raises(EntityNotFoundError) as excinfo:
            use_case.execute(cmd)

        assert excinfo.value.entity_type == "Actividad"
        assert excinfo.value.entity_id == "act-inexistente-000"

    def test_registrar_participacion_persona_inexistente_lanza_error(self):
        act_repo = InMemoryActividadRepository()
        act_repo.save(Activity(
            id_actividad="act-existente-1",
            nombre_actividad_original="Actividad Existente",
        ))
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()

        use_case = RegistrarParticipacionIndividualUseCase(
            participacion_repo=part_repo,
            actividad_repo=act_repo,
            persona_repo=per_repo,
        )

        cmd = RegistrarParticipacionIndividualCommand(
            id_actividad="act-existente-1",
            id_persona="per-inexistente-000",
            categoria_participacion="ESTUDIANTE",
        )

        with pytest.raises(EntityNotFoundError) as excinfo:
            use_case.execute(cmd)

        assert excinfo.value.entity_type == "Persona"
        assert excinfo.value.entity_id == "per-inexistente-000"

    def test_registrar_participacion_con_uow(self):
        uow = InMemoryUnitOfWork()
        with uow:
            uow.actividades.save(Activity(
                id_actividad="act-uow-part-1",
                nombre_actividad_original="Actividad Transaccional",
            ))
            uow.personas.save(Person(
                id_persona_interno="per-uow-part-1",
                nombre_completo="Protagonista UoW",
            ))
            use_case = RegistrarParticipacionIndividualUseCase(
                participacion_repo=uow.participaciones,
                actividad_repo=uow.actividades,
                persona_repo=uow.personas,
            )
            cmd = RegistrarParticipacionIndividualCommand(
                id_actividad="act-uow-part-1",
                id_persona="per-uow-part-1",
                categoria_participacion="COLABORADOR",
            )
            dto = use_case.execute(cmd)
            uow.commit()

        assert dto.id_actividad == "act-uow-part-1"
        assert dto.id_persona == "per-uow-part-1"
        assert dto.nombre_completo == "Protagonista UoW"



# ==============================================================================
# 7. PRUEBAS DE AISLAMIENTO ARQUITECTÓNICO (AST)
# ==============================================================================

class TestUseCasesArchitectureIsolation:
    """Verifica que app/application/use_cases no importe infraestructura ni use SQL."""

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

    def test_no_forbidden_imports_in_use_cases(self):
        use_cases_dir = (
            Path(__file__).resolve().parent.parent
            / "app"
            / "application"
            / "use_cases"
        )
        python_files = list(use_cases_dir.rglob("*.py"))
        assert len(python_files) >= 6, "Deben existir los archivos de casos de uso"

        violaciones = []
        for file_path in python_files:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in self.FORBIDDEN_MODULES:
                            if alias.name == forbidden or alias.name.startswith(
                                forbidden + "."
                            ):
                                violaciones.append(
                                    f"{file_path.name}: import {alias.name}"
                                )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for forbidden in self.FORBIDDEN_MODULES:
                            if node.module == forbidden or node.module.startswith(
                                forbidden + "."
                            ):
                                violaciones.append(
                                    f"{file_path.name}: from {node.module} import ..."
                                )

        assert (
            not violaciones
        ), f"Violaciones de Clean Architecture en use_cases: {violaciones}"

    def test_no_sql_in_use_cases(self):
        use_cases_dir = (
            Path(__file__).resolve().parent.parent
            / "app"
            / "application"
            / "use_cases"
        )
        python_files = list(use_cases_dir.rglob("*.py"))

        violaciones = []
        for file_path in python_files:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val_upper = node.value.upper()
                    for sql_pat in self.FORBIDDEN_SQL_PATTERNS:
                        if sql_pat in val_upper:
                            violaciones.append(
                                f"{file_path.name}: posible SQL '{sql_pat.strip()}' en '{node.value}'"
                            )

        assert (
            not violaciones
        ), f"Violaciones de Clean Architecture: SQL en use_cases: {violaciones}"
