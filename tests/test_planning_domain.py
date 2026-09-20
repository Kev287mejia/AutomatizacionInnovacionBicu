"""
Tests Unitarios del Dominio Puro — Modulo Planificacion -> Diseno Metodologico.

Fase 29.3 — Implementacion del Dominio Puro
Fuente: FASE_29_2_DISENO_ARQUITECTONICO_PLANIFICACION_DISENO.md
        FASE_29_2_1_CIERRE_DECISIONES_INSTITUCIONALES.md

Cobertura requerida (§18 de especificacion):
  - Identidad (UUID tecnico D-04, planning_id institucional)
  - PlannedActivity (creacion valida, obligatorios, validaciones)
  - MethodologicalDesign (creacion, asociacion, 5 bloques)
  - TimeBlock (duracion valida/invalida, suma correcta, discrepancia)
  - FAQ (7 preguntas, literales, derivaciones R-02, R-03, R-04, R-10)
  - OperationalActivity (estructura, tiempos, espejo agenda R-06)
  - AIProposal (permitidos/prohibidos, trazabilidad, revision humana)
  - CatalogReference & Catalogos C1-C5 (C1-C5, discrepancia C1)
  - InstitutionalRulesEngine (R-01 a R-10)
  - MethodologicalDesignValidator (V-MD-01 a V-MD-12)
  - DTOs y Contratos de Transferencia
  - Puertos Abstractos
"""
import uuid
from datetime import date, datetime, timezone
import pytest

from app.planning.domain.catalogs import (
    CATALOG_C1_EJES,
    CATALOG_C2_PROGRAMAS,
    CATALOG_C3_AMBITOS,
    CATALOG_C4_TIPOS_EVENTO,
    CATALOG_C5_TIPOS_PROYECTO,
)
from app.planning.domain.dtos import (
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    PlannedActivityDTO,
    TimeBlockDTO,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.ports import (
    AIAssistancePort,
    CatalogRepositoryPort,
    MethodologicalDesignRepositoryPort,
    MethodologicalDocumentRendererPort,
    PlannedActivityRepositoryPort,
)
from app.planning.domain.rules_engine import InstitutionalRulesEngine
from app.planning.domain.validator import (
    MethodologicalDesignValidator,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from app.planning.domain.value_objects import (
    AIProposal,
    CatalogReference,
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)


# ===========================================================================
# FIXTURES
# ===========================================================================

@pytest.fixture
def sample_goals():
    return ParticipantGoals.from_totals(
        estudiantes=25,
        docentes=5,
        administrativos=0,
        externos=0,
        mujeres=18,
        varones=12,
    )


@pytest.fixture
def sample_activity(sample_goals):
    return PlannedActivity.create(
        planning_id="ACT-2026-BIL-016",
        activity_name="Taller de Expresion Artistica y Comunicacion Asertiva",
        sede="Bluefields",
        dep_sede="RACCS",
        mun_sede="Bluefields",
        programa="Formacion y Capacitacion Continua",
        eje_estrategia="Eje 5: Investigacion, Innovacion y Extension",
        area_responsable="Direccion de Extension Universitaria",
        tipo_evento="Capacitación",
        participant_goals=sample_goals,
        proposito="Desarrollar habilidades expresivas en los estudiantes.",
    )


@pytest.fixture
def sample_agenda():
    return (
        TimeBlock(sequence=1, label="Inscripcion y Acogida", minutes=30),
        TimeBlock(sequence=2, label="Dinamica de Integracion", minutes=45),
        TimeBlock(sequence=3, label="Desarrollo del Ejercicio", minutes=60),
        TimeBlock(sequence=4, label="Cierre y Evaluacion", minutes=15),
    )


@pytest.fixture
def sample_operational_activities():
    return (
        OperationalActivity(
            step_number=1,
            phase_label="Inscripcion y Acogida",
            operative_goal="Registrar asistencia y crear clima favorable",
            procedure="Registro en lista de asistencia y entrega de gafetes",
            materials="Lista, gafetes, marcadores",
            minutes=30,
        ),
        OperationalActivity(
            step_number=2,
            phase_label="Dinamica de Integracion",
            operative_goal="Fomentar confianza entre participantes",
            procedure="Juego de presentacion en circulo",
            materials="Pelota de goma",
            minutes=45,
        ),
        OperationalActivity(
            step_number=3,
            phase_label="Desarrollo del Ejercicio",
            operative_goal="Elaborar propuesta artistica colectiva",
            procedure="Trabajo en grupos de 5 personas",
            materials="Papelografo, marcadores de colores",
            minutes=60,
        ),
        OperationalActivity(
            step_number=4,
            phase_label="Cierre y Evaluacion",
            operative_goal="Sintetizar aprendizajes y evaluar jornada",
            procedure="Plenaria de reflexion",
            materials="Ficha de evaluacion",
            minutes=15,
        ),
    )


@pytest.fixture
def sample_faq(sample_goals):
    engine = InstitutionalRulesEngine()
    return FAQTable(
        q1_que_es="Es un taller formativo orientado al desarrollo de tecnicas expresivas.",
        q2_para_que="Para fortalecer competencias comunicativas en la comunidad universitaria.",
        q3_sesiones=engine.r10_sesion_unica_default(),
        q4_protagonistas=engine.r03_protagonistas_narrativa(sample_goals),
        q5_facilitador=engine.r02_facilitador("Direccion de Extension Universitaria"),
        q6_materiales="Papelografos, marcadores, fichas, equipo audiovisual.",
        q7_duracion=engine.r04_duracion_formateada(150),
    )


# ===========================================================================
# 1. IDENTIDAD Y D-04
# ===========================================================================

class TestIdentityAndD04:
    """Pruebas de identidad tecnica vs institucional (D-04)."""

    def test_internal_id_is_uuid(self, sample_activity):
        """D-04: internal_id es UUID tecnico obligatorio."""
        assert isinstance(sample_activity.internal_id, uuid.UUID)

    def test_internal_id_is_unique(self, sample_goals):
        """Dos actividades tienen internal_id distintos aun con mismo planning_id."""
        a1 = PlannedActivity.create(
            planning_id="ACT-2026-BIL-001",
            activity_name="Actividad 1",
            sede="Bluefields",
            dep_sede="RACCS",
            mun_sede="Bluefields",
            programa="Programa 1",
            eje_estrategia="Eje 1",
            area_responsable="Area 1",
            tipo_evento="Taller",
            participant_goals=sample_goals,
        )
        a2 = PlannedActivity.create(
            planning_id="ACT-2026-BIL-001",
            activity_name="Actividad 1",
            sede="Bluefields",
            dep_sede="RACCS",
            mun_sede="Bluefields",
            programa="Programa 1",
            eje_estrategia="Eje 1",
            area_responsable="Area 1",
            tipo_evento="Taller",
            participant_goals=sample_goals,
        )
        assert a1.internal_id != a2.internal_id

    def test_planning_id_is_preserved(self, sample_activity):
        """planning_id institucional se preserva sin modificacion."""
        assert sample_activity.planning_id == "ACT-2026-BIL-016"

    def test_empty_planning_id_raises(self, sample_goals):
        """planning_id no puede ser vacio."""
        with pytest.raises(ValueError, match="es obligatorio y no puede ser vacio"):
            PlannedActivity.create(
                planning_id="",
                activity_name="Actividad",
                sede="Bluefields",
                dep_sede="RACCS",
                mun_sede="Bluefields",
                programa="Programa",
                eje_estrategia="Eje",
                area_responsable="Area",
                tipo_evento="Taller",
                participant_goals=sample_goals,
            )


# ===========================================================================
# 2. PLANNED ACTIVITY AGGREGATE
# ===========================================================================

class TestPlannedActivity:
    """Pruebas de la entidad PlannedActivity."""

    def test_valid_creation(self, sample_activity):
        """Creacion valida con todos los campos obligatorios."""
        assert sample_activity.activity_name == "Taller de Expresion Artistica y Comunicacion Asertiva"
        assert sample_activity.sede == "Bluefields"
        assert sample_activity.participant_goals.total() == 30

    def test_empty_name_raises(self, sample_goals):
        """activity_name vacio lanza ValueError."""
        with pytest.raises(ValueError, match="es obligatorio y no puede ser vacio"):
            PlannedActivity.create(
                planning_id="ACT-001",
                activity_name="   ",
                sede="Bluefields",
                dep_sede="RACCS",
                mun_sede="Bluefields",
                programa="P",
                eje_estrategia="E",
                area_responsable="A",
                tipo_evento="Taller",
                participant_goals=sample_goals,
            )

    def test_empty_sede_raises(self, sample_goals):
        """sede vacia lanza ValueError."""
        with pytest.raises(ValueError, match="es obligatorio y no puede ser vacio"):
            PlannedActivity.create(
                planning_id="ACT-001",
                activity_name="Actividad",
                sede="",
                dep_sede="RACCS",
                mun_sede="Bluefields",
                programa="P",
                eje_estrategia="E",
                area_responsable="A",
                tipo_evento="Taller",
                participant_goals=sample_goals,
            )

    def test_empty_area_responsable_raises(self, sample_goals):
        """area_responsable vacia lanza ValueError."""
        with pytest.raises(ValueError, match="es obligatorio y no puede ser vacio"):
            PlannedActivity.create(
                planning_id="ACT-001",
                activity_name="Actividad",
                sede="Bluefields",
                dep_sede="RACCS",
                mun_sede="Bluefields",
                programa="P",
                eje_estrategia="E",
                area_responsable="",
                tipo_evento="Taller",
                participant_goals=sample_goals,
            )

    def test_to_dto_immutability(self, sample_activity):
        """to_dto produce un PlannedActivityDTO inmutable."""
        dto = sample_activity.to_dto()
        assert isinstance(dto, PlannedActivityDTO)
        assert dto.planning_id == sample_activity.planning_id
        assert dto.activity_name == sample_activity.activity_name
        with pytest.raises(AttributeError):
            dto.activity_name = "Otro nombre"  # type: ignore


# ===========================================================================
# 3. VALUE OBJECT: PARTICIPANT GOALS
# ===========================================================================

class TestParticipantGoals:
    """Pruebas de ParticipantGoals (metas de protagonistas)."""

    def test_total_calculation(self):
        """total() suma estudiantes, docentes, administrativos y externos."""
        goals = ParticipantGoals.from_totals(estudiantes=20, docentes=5, administrativos=2, externos=3)
        assert goals.total() == 30

    def test_negative_values_raise(self):
        """Metas negativas son rechazadas."""
        with pytest.raises(ValueError, match="no pueden ser negativos"):
            ParticipantGoals.from_totals(estudiantes=-5)

    def test_sex_breakdown_mismatch_raises(self):
        """Si mujeres + varones != total, lanza ValueError."""
        with pytest.raises(ValueError, match="Discrepancia en desglose por sexo"):
            ParticipantGoals.from_totals(estudiantes=10, mujeres=6, varones=6)  # 12 != 10

    def test_sex_breakdown_matches_total(self):
        """Desglose por sexo exacto es valido."""
        goals = ParticipantGoals.from_totals(estudiantes=10, mujeres=6, varones=4)
        assert goals.total() == 10

    def test_immutable_value_object(self):
        """ParticipantGoals es frozen."""
        goals = ParticipantGoals.from_totals(estudiantes=10)
        with pytest.raises(AttributeError):
            goals.est_grado_f = 20  # type: ignore


# ===========================================================================
# 4. VALUE OBJECT: TIMEBLOCK & OPERATIONAL ACTIVITY
# ===========================================================================

class TestTimeBlockAndOperationalActivity:
    """Pruebas de TimeBlock y OperationalActivity."""

    def test_valid_time_block(self):
        tb = TimeBlock(sequence=1, label="Bienvenida", minutes=15)
        assert tb.sequence == 1
        assert tb.label == "Bienvenida"
        assert tb.minutes == 15

    def test_time_block_invalid_minutes(self):
        with pytest.raises(ValueError, match="debe ser entero positivo"):
            TimeBlock(sequence=1, label="Error", minutes=0)
        with pytest.raises(ValueError, match="debe ser entero positivo"):
            TimeBlock(sequence=1, label="Error", minutes=-10)

    def test_time_block_empty_label(self):
        with pytest.raises(ValueError, match="no puede ser vacio"):
            TimeBlock(sequence=1, label="   ", minutes=15)

    def test_valid_operational_activity(self):
        oa = OperationalActivity(
            step_number=1,
            phase_label="Fase 1",
            operative_goal="Meta 1",
            procedure="Procedimiento 1",
            materials="Materiales 1",
            minutes=30,
        )
        assert oa.step_number == 1
        assert oa.minutes == 30

    def test_operational_activity_invalid_minutes(self):
        with pytest.raises(ValueError, match="debe ser entero positivo"):
            OperationalActivity(
                step_number=1,
                phase_label="Fase 1",
                operative_goal="Meta 1",
                procedure="Procedimiento 1",
                materials="Materiales 1",
                minutes=0,
            )


# ===========================================================================
# 5. VALUE OBJECT: FAQ TABLE
# ===========================================================================

class TestFAQTable:
    """Pruebas de la tabla de 7 preguntas frecuentes (Tabla 1)."""

    def test_faq_table_structure(self, sample_faq):
        """Verifica los 7 campos de la tabla FAQ."""
        assert sample_faq.q1_que_es != ""
        assert sample_faq.q2_para_que != ""
        assert sample_faq.q3_sesiones == "Sesión única"
        assert "30 protagonistas en total" in sample_faq.q4_protagonistas
        assert "Direccion de Extension Universitaria" in sample_faq.q5_facilitador
        assert sample_faq.q6_materiales != ""
        assert "2 horas y media" in sample_faq.q7_duracion

    def test_faq_empty_required_fields_raise(self):
        """q1, q4, q5, q7 son obligatorios."""
        with pytest.raises(ValueError, match="es obligatorio"):
            FAQTable(
                q1_que_es="",
                q2_para_que="",
                q3_sesiones="Sesión única",
                q4_protagonistas="20 estudiantes.",
                q5_facilitador="Facilitador",
                q6_materiales="Materiales",
                q7_duracion="2 horas.",
            )


# ===========================================================================
# 6. VALUE OBJECT: AI PROPOSAL (§11, §14)
# ===========================================================================

class TestAIProposal:
    """Pruebas de AIProposal y principio de contencion estricta."""

    def test_proposal_creation_defaults(self):
        """requires_review es True por defecto, accepted=None."""
        prop = AIProposal.create(
            target_field="introduction",
            proposed_content="Propuesta narrativa de introduccion...",
            source_inputs={"activity_name": "Taller", "tipo_evento": "Taller"},
            confidence=0.85,
        )
        assert prop.requires_review is True
        assert prop.accepted is None
        assert prop.reviewed_by is None
        assert prop.review_timestamp is None

    def test_allowed_fields(self):
        """Campos permitidos son validos."""
        allowed = [
            "introduction",
            "methodological_approach",
            "objective_1",
            "objective_2",
            "procedure",
            "operative_goal",
        ]
        for field in allowed:
            prop = AIProposal.create(
                target_field=field,
                proposed_content="Texto",
                source_inputs={"field": field},
            )
            assert prop.target_field == field

    def test_forbidden_fields_raise(self):
        """Campos institucionales deterministas estan PROHIBIDOS para IA."""
        forbidden = [
            "activity_name",
            "sede",
            "area_responsable",
            "participant_goals",
            "eje_estrategia",
            "programa",
            "tipo_evento",
            "total_minutes",
            "codigo_presupuestario",
        ]
        for field in forbidden:
            with pytest.raises(ValueError, match="no esta permitido"):
                AIProposal.create(
                    target_field=field,
                    proposed_content="Texto prohibido",
                    source_inputs={},
                )

    def test_accept_proposal(self):
        """Aceptar propuesta registra auditoria y setea accepted=True."""
        prop = AIProposal.create(
            target_field="introduction",
            proposed_content="Texto de prueba",
            source_inputs={},
        )
        accepted = prop.accept(reviewer="prof_kenia")
        assert accepted.accepted is True
        assert accepted.reviewed_by == "prof_kenia"
        assert accepted.review_timestamp is not None
        assert accepted.rejection_reason is None

    def test_reject_proposal(self):
        """Rechazar propuesta registra auditoria, razon y setea accepted=False."""
        prop = AIProposal.create(
            target_field="objective_1",
            proposed_content="Objetivo inadecuado",
            source_inputs={},
        )
        rejected = prop.reject(reviewer="prof_kenia", reason="No alineado con el proposito")
        assert rejected.accepted is False
        assert rejected.reviewed_by == "prof_kenia"
        assert rejected.rejection_reason == "No alineado con el proposito"


# ===========================================================================
# 7. CATALOGS AND CATALOG REFERENCE
# ===========================================================================

class TestCatalogs:
    """Pruebas de catalogos institucionales C1 a C5."""

    def test_catalogs_count(self):
        """Verifica cardinalidad segun Fase 29.1."""
        assert len(CATALOG_C1_EJES) == 11
        assert len(CATALOG_C2_PROGRAMAS) == 11
        assert len(CATALOG_C3_AMBITOS) == 3
        assert len(CATALOG_C4_TIPOS_EVENTO) == 11
        assert len(CATALOG_C5_TIPOS_PROYECTO) == 4

    def test_c1_contains_ejes(self):
        assert "EJE_1" in CATALOG_C1_EJES
        assert "EJE_5" in CATALOG_C1_EJES
        assert "EJE_11" in CATALOG_C1_EJES

    def test_catalog_reference_structure(self):
        ref = CatalogReference(
            catalog_id="C4",
            code="Taller",
            label="Taller formativo/artistico",
            source="POA BICU",
        )
        assert ref.catalog_id == "C4"
        assert ref.code == "Taller"
        assert ref.source == "POA BICU"


# ===========================================================================
# 8. INSTITUTIONAL RULES ENGINE (R-01 A R-10)
# ===========================================================================

class TestInstitutionalRulesEngine:
    """Pruebas de las reglas deterministas R-01 a R-10."""

    def setup_method(self):
        self.engine = InstitutionalRulesEngine()

    def test_r01_titulo_documento(self):
        """R-01: 'Diseño metodológico ' + activity_name."""
        title = self.engine.r01_titulo_documento("Taller de Innovacion")
        assert title == "Diseño metodológico Taller de Innovacion"

    def test_r01_empty_raises(self):
        with pytest.raises(ValueError):
            self.engine.r01_titulo_documento("")

    def test_r02_facilitador(self):
        """R-02: q5_facilitador = area_responsable."""
        fac = self.engine.r02_facilitador("Direccion de Investigacion")
        assert fac == "Direccion de Investigacion"

    def test_r03_protagonistas_solo_estudiantes(self):
        """R-03: Formato solo estudiantes."""
        goals = ParticipantGoals.from_totals(estudiantes=30)
        narrative = self.engine.r03_protagonistas_narrativa(goals)
        assert narrative == "30 estudiantes."

    def test_r03_protagonistas_estudiantes_y_docentes(self):
        """R-03: Formato estudiantes y docentes."""
        goals = ParticipantGoals.from_totals(estudiantes=20, docentes=5)
        narrative = self.engine.r03_protagonistas_narrativa(goals)
        assert narrative == "25 protagonistas en total: 20 estudiantes y 5 docentes."

    def test_r03_protagonistas_desglose_completo_con_sexo(self):
        """R-03: Formato desglose completo con sexo y administrativos."""
        goals = ParticipantGoals.from_totals(
            estudiantes=20,
            docentes=5,
            administrativos=5,
            externos=0,
            mujeres=18,
            varones=12,
        )
        narrative = self.engine.r03_protagonistas_narrativa(goals)
        assert "30 protagonistas en total" in narrative
        assert "18 mujeres y 12 varones" in narrative
        assert "integrando estudiantes y personal administrativo" in narrative

    def test_r04_duracion_formateada_exacta(self):
        """R-04: Formato horas exactas."""
        assert self.engine.r04_duracion_formateada(60) == "1 hora."
        assert self.engine.r04_duracion_formateada(120) == "2 horas."

    def test_r04_duracion_formateada_media_hora(self):
        """R-04: Formato hora y media."""
        assert self.engine.r04_duracion_formateada(90) == "1 hora y media (90 minutos)."
        assert self.engine.r04_duracion_formateada(150) == "2 horas y media (150 minutos)."
        assert self.engine.r04_duracion_formateada(210) == "3 horas y media (210 minutos)."

    def test_r04_duracion_formateada_otros_minutos(self):
        """R-04: Formato otros minutos."""
        assert self.engine.r04_duracion_formateada(195) == "3 horas y 15 minutos."
        assert self.engine.r04_duracion_formateada(45) == "0 horas y 45 minutos."

    def test_r05_suma_agenda(self, sample_agenda):
        """R-05: total_minutes == sum(agenda[i].minutes)."""
        total = self.engine.r05_calcular_total_minutos(sample_agenda)
        assert total == 150
        assert self.engine.r05_verificar_suma_agenda(sample_agenda, 150) is True
        assert self.engine.r05_verificar_suma_agenda(sample_agenda, 140) is False

    def test_r06_espejo_agenda_matriz(self, sample_agenda, sample_operational_activities):
        """R-06: operational_matrix[i].minutes == agenda[i].minutes."""
        assert self.engine.r06_verificar_espejo_agenda_matriz(
            sample_agenda, sample_operational_activities
        ) is True

    def test_r06_espejo_mismatch_fails(self, sample_agenda, sample_operational_activities):
        """R-06 detecta diferencias en tiempos entre agenda y matriz."""
        bad_matrix = list(sample_operational_activities)
        bad_matrix[2] = OperationalActivity(
            step_number=3,
            phase_label="Desarrollo del Ejercicio",
            operative_goal="Meta",
            procedure="Procedimiento",
            materials="Materiales",
            minutes=50,  # Era 60 en agenda
        )
        assert self.engine.r06_verificar_espejo_agenda_matriz(
            sample_agenda, tuple(bad_matrix)
        ) is False

    def test_r07_numero_de_objetivos(self):
        """R-07: Exactamente 2 objetivos institucionales."""
        assert self.engine.r07_verificar_numero_objetivos(["Obj 1", "Obj 2"]) is True
        assert self.engine.r07_verificar_numero_objetivos(["Obj 1"]) is False
        assert self.engine.r07_verificar_numero_objetivos(["Obj 1", "Obj 2", "Obj 3"]) is False

    def test_r08_catalogos_pertenencia(self):
        """R-08: Pertenencia a catalogos C1-C5."""
        assert self.engine.r08_validar_eje_estrategia("Eje 1") is True
        assert self.engine.r08_validar_eje_estrategia("Eje Inexistente") is False

        assert self.engine.r08_validar_tipo_evento("Capacitación") is True
        assert self.engine.r08_validar_tipo_evento("Evento Fantasma") is False

        assert self.engine.r08_validar_ambito("Educativo") is True
        assert self.engine.r08_validar_ambito(None) is True  # Opcional

    def test_r10_sesion_unica_default(self):
        """R-10: Literal 'Sesión única'."""
        assert self.engine.r10_sesion_unica_default() == "Sesión única"


# ===========================================================================
# 9. METHODOLOGICAL DESIGN AGGREGATE
# ===========================================================================

class TestMethodologicalDesign:
    """Pruebas del Aggregate Root MethodologicalDesign."""

    def test_create_draft(self, sample_activity, sample_agenda, sample_operational_activities, sample_faq):
        """Creacion valida de diseno metodologico en estado DRAFT."""
        design = MethodologicalDesign.create(
            planned_activity_internal_id=sample_activity.internal_id,
            planning_id=sample_activity.planning_id,
            activity_name=sample_activity.activity_name,
            introduction="Introduccion del taller...",
            methodological_approach="Enfoque participativo y constructivista.",
            objective_1="Desarrollar competencias tecnicas.",
            objective_2="Fortalecer el trabajo colaborativo.",
            faq=sample_faq,
            agenda=sample_agenda,
            operational_matrix=sample_operational_activities,
            created_by="prof_kenia",
        )
        assert design.status == DesignStatus.DRAFT
        assert design.version == 1
        assert design.total_minutes == 150
        assert design.document_title == "Diseño metodológico Taller de Expresion Artistica y Comunicacion Asertiva"

    def test_empty_objectives_raises(self, sample_activity, sample_agenda, sample_operational_activities, sample_faq):
        """Objetivos vacios lanzan ValueError."""
        with pytest.raises(ValueError, match="objective_1 no puede estar vacio"):
            MethodologicalDesign.create(
                planned_activity_internal_id=sample_activity.internal_id,
                planning_id=sample_activity.planning_id,
                activity_name=sample_activity.activity_name,
                introduction="Intro",
                methodological_approach="Enfoque",
                objective_1="   ",
                objective_2="Obj 2",
                faq=sample_faq,
                agenda=sample_agenda,
                operational_matrix=sample_operational_activities,
                created_by="user",
            )

    def test_agenda_matrix_length_mismatch_raises(self, sample_activity, sample_agenda, sample_faq):
        """Discrepancia en cantidad de items agenda vs matriz lanza ValueError."""
        with pytest.raises(ValueError, match="R-06"):
            MethodologicalDesign.create(
                planned_activity_internal_id=sample_activity.internal_id,
                planning_id=sample_activity.planning_id,
                activity_name=sample_activity.activity_name,
                introduction="Intro",
                methodological_approach="Enfoque",
                objective_1="Obj 1",
                objective_2="Obj 2",
                faq=sample_faq,
                agenda=sample_agenda,  # 4 items
                operational_matrix=(),  # 0 items
                created_by="user",
            )

    def test_approval_lifecycle(self, sample_activity, sample_agenda, sample_operational_activities, sample_faq):
        """Transiciones de estado DRAFT -> GENERATED -> APPROVED."""
        design = MethodologicalDesign.create(
            planned_activity_internal_id=sample_activity.internal_id,
            planning_id=sample_activity.planning_id,
            activity_name=sample_activity.activity_name,
            introduction="Intro",
            methodological_approach="Enfoque",
            objective_1="Obj 1",
            objective_2="Obj 2",
            faq=sample_faq,
            agenda=sample_agenda,
            operational_matrix=sample_operational_activities,
            created_by="user",
        )
        assert design.status == DesignStatus.DRAFT

        # Transicion a GENERATED
        design.mark_generated()
        assert design.status == DesignStatus.GENERATED

        # Transicion a APPROVED
        design.approve(approved_by="coordinacion_academica")
        assert design.status == DesignStatus.APPROVED
        assert design.approved_by == "coordinacion_academica"
        assert design.approved_at is not None

    def test_approved_design_is_immutable(self, sample_activity, sample_agenda, sample_operational_activities, sample_faq):
        """Un diseno APPROVED no puede modificarse."""
        design = MethodologicalDesign.create(
            planned_activity_internal_id=sample_activity.internal_id,
            planning_id=sample_activity.planning_id,
            activity_name=sample_activity.activity_name,
            introduction="Intro",
            methodological_approach="Enfoque",
            objective_1="Obj 1",
            objective_2="Obj 2",
            faq=sample_faq,
            agenda=sample_agenda,
            operational_matrix=sample_operational_activities,
            created_by="user",
        )
        design.mark_generated()
        design.approve(approved_by="coordinacion")

        with pytest.raises(RuntimeError, match="No se puede modificar un diseno en estado APPROVED"):
            design.mark_generated()


# ===========================================================================
# 10. METHODOLOGICAL DESIGN VALIDATOR (V-MD-01 A V-MD-12)
# ===========================================================================

class TestMethodologicalDesignValidator:
    """Pruebas del validador de dominio V-MD-01 a V-MD-12."""

    def setup_method(self):
        self.validator = MethodologicalDesignValidator()

    def test_full_valid_design_passes(
        self, sample_activity, sample_agenda, sample_operational_activities, sample_faq
    ):
        """Diseno perfectamente valido no produce errores."""
        design = MethodologicalDesign.create(
            planned_activity_internal_id=sample_activity.internal_id,
            planning_id=sample_activity.planning_id,
            activity_name=sample_activity.activity_name,
            introduction="Intro",
            methodological_approach="Enfoque",
            objective_1="Obj 1",
            objective_2="Obj 2",
            faq=sample_faq,
            agenda=sample_agenda,
            operational_matrix=sample_operational_activities,
            created_by="user",
        )
        report = self.validator.validate(design, sample_activity)
        assert report.is_valid is True
        assert len(report.errors) == 0

    def test_v_md_01_activity_ref_mismatch(
        self, sample_activity, sample_agenda, sample_operational_activities, sample_faq
    ):
        """V-MD-01: planned_activity_internal_id no coincide."""
        design = MethodologicalDesign.create(
            planned_activity_internal_id=uuid.uuid4(),  # ID distinto
            planning_id=sample_activity.planning_id,
            activity_name=sample_activity.activity_name,
            introduction="Intro",
            methodological_approach="Enfoque",
            objective_1="Obj 1",
            objective_2="Obj 2",
            faq=sample_faq,
            agenda=sample_agenda,
            operational_matrix=sample_operational_activities,
            created_by="user",
        )
        report = self.validator.validate(design, sample_activity)
        assert report.has_error("V-MD-01") is True

    def test_v_md_05_zero_participants(
        self, sample_agenda, sample_operational_activities, sample_faq
    ):
        """V-MD-05: Metas de protagonistas = 0 produce ERROR."""
        zero_goals = ParticipantGoals.from_totals(estudiantes=0)
        activity = PlannedActivity.create(
            planning_id="ACT-001",
            activity_name="Actividad",
            sede="Bluefields",
            dep_sede="RACCS",
            mun_sede="Bluefields",
            programa="P",
            eje_estrategia="Eje 1",
            area_responsable="A",
            tipo_evento="Taller",
            participant_goals=zero_goals,
        )
        design = MethodologicalDesign.create(
            planned_activity_internal_id=activity.internal_id,
            planning_id=activity.planning_id,
            activity_name=activity.activity_name,
            introduction="Intro",
            methodological_approach="Enfoque",
            objective_1="Obj 1",
            objective_2="Obj 2",
            faq=sample_faq,
            agenda=sample_agenda,
            operational_matrix=sample_operational_activities,
            created_by="user",
        )
        report = self.validator.validate(design, activity)
        assert report.has_error("V-MD-05") is True

    def test_v_md_10_pending_ai_proposal_in_exported_fields(
        self, sample_activity, sample_agenda, sample_operational_activities, sample_faq
    ):
        """V-MD-10: Propuesta de IA sin revisar (accepted=None) en campo exportado produce ERROR."""
        design = MethodologicalDesign.create(
            planned_activity_internal_id=sample_activity.internal_id,
            planning_id=sample_activity.planning_id,
            activity_name=sample_activity.activity_name,
            introduction="Intro",
            methodological_approach="Enfoque",
            objective_1="Obj 1",
            objective_2="Obj 2",
            faq=sample_faq,
            agenda=sample_agenda,
            operational_matrix=sample_operational_activities,
            created_by="user",
        )
        # Agregamos una propuesta IA sin revisar para introduction
        prop = AIProposal.create(
            target_field="introduction",
            proposed_content="Propuesta pendiente",
            source_inputs={},
        )
        design.add_ai_proposal(prop)

        report = self.validator.validate(design, sample_activity)
        assert report.has_error("V-MD-10") is True


# ===========================================================================
# 11. DTOS AND PORTS INTERFACES
# ===========================================================================

class TestDTOsAndPorts:
    """Pruebas de contratos DTO y puertos abstractos."""

    def test_methodological_design_dto_generation(
        self, sample_activity, sample_agenda, sample_operational_activities, sample_faq
    ):
        """MethodologicalDesign.to_dto() genera MethodologicalDesignDTO inmutable."""
        design = MethodologicalDesign.create(
            planned_activity_internal_id=sample_activity.internal_id,
            planning_id=sample_activity.planning_id,
            activity_name=sample_activity.activity_name,
            introduction="Intro",
            methodological_approach="Enfoque",
            objective_1="Obj 1",
            objective_2="Obj 2",
            faq=sample_faq,
            agenda=sample_agenda,
            operational_matrix=sample_operational_activities,
            created_by="user",
        )
        dto = design.to_dto()
        assert isinstance(dto, MethodologicalDesignDTO)
        assert dto.document_title == "Diseño metodológico Taller de Expresion Artistica y Comunicacion Asertiva"
        assert dto.objectives_heading == "OBJETIVOS DEL TALLER ARTÍSTICO"  # D-06
        assert dto.program_section_label == "III. PROGRAMA"                 # D-07
        assert dto.matrix_section_label == "VI. MATRIZ DE PLANIFICACIÓN"    # D-07
        assert len(dto.agenda) == 4
        assert len(dto.operational_matrix) == 4
        assert dto.total_minutes == 150

    def test_abstract_ports_cannot_be_instantiated(self):
        """Los puertos son clases abstractas puras y no pueden instanciarse directamente."""
        with pytest.raises(TypeError):
            PlannedActivityRepositoryPort()  # type: ignore

        with pytest.raises(TypeError):
            MethodologicalDesignRepositoryPort()  # type: ignore

        with pytest.raises(TypeError):
            CatalogRepositoryPort()  # type: ignore

        with pytest.raises(TypeError):
            AIAssistancePort()  # type: ignore

        with pytest.raises(TypeError):
            MethodologicalDocumentRendererPort()  # type: ignore
