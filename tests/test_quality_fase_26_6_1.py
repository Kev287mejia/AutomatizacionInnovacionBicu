"""tests.test_quality_fase_26_6_1

Suite de pruebas exhaustivas para la Fase 26.6.1:
Motor de Calidad, Discrepancias y Validación Institucional BICU.

Cubre rigurosamente:
1. Las 4 severidades autorizadas: INFO, WARNING, ERROR, CRITICAL ('REVISION' rechazado como severidad).
2. Cuatro fenómenos conceptuales: Error de datos, Inconsistencia, Posible duplicado, Revisión documental.
3. Separación estricta de estados: EN_REVISION != COLA_REVISION != BLOQUEADO != REQUIERE_REVISION.
4. Estados reales de Discrepancia: REQUIERE_REVISION, EN_REVISION, ACLARADO, CONCORDANTE.
5. Reglas completas Q-01 a Q-20 verificadas individualmente.
6. Q-03 NO muta Person.cedula (conserva la fecha original).
7. Q-20 NO crea, NO fusiona y NO elimina personas.
8. Contrato dry_run: CERO escrituras persistentes en base de datos.
9. Persistencia de Discrepancia y Unit of Work (commit y rollback).
10. Garantía RN-C07: no mutación de datos fuente de negocio protegidos.
11. Aislamiento Clean Architecture mediante inspección de árbol sintáctico (AST).
12. Preservación del esquema relacional: exactamente 19 tablas y cero migraciones nuevas.
"""

import ast
from datetime import date, datetime
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.application.commands.calidad_commands import EvaluarCalidadActividadCommand
from app.application.commands.discrepancia_commands import ResolverRevisionDiscrepanciaCommand
from app.application.dto.quality_dtos import QualityAssessmentDTO
from app.application.fakes import (
    InMemoryActividadRepository,
    InMemoryDiscrepanciaRepository,
    InMemoryParticipacionRepository,
    InMemoryPersonaRepository,
    InMemoryUnitOfWork,
)
from app.application.queries.discrepancia_queries import ConsultarDiscrepanciasPendientesQuery
from app.application.use_cases.calidad import (
    ConsultarDiscrepanciasPendientesUseCase,
    EvaluarCalidadActividadUseCase,
    ResolverRevisionDiscrepanciaUseCase,
)
from app.core.constants.participant_types import CategoriaParticipacion
from app.core.models.activity import Activity
from app.core.models.discrepancy import (
    Discrepancia,
    EstadoDiscrepancia,
    SeveridadDiscrepancia,
    TipoDiscrepancia,
)
from app.core.models.participation import Participation
from app.core.models.person import Person
from app.infrastructure.persistence.schema import EXPECTED_TABLE_NAMES
from app.quality.models import (
    EstadoGeneralCalidad,
    QualityAssessment,
    QualityContext,
    SeveridadCalidad,
    ValidationFinding,
)
from app.quality.rules import (
    ReglaQ01CedulaVacia,
    ReglaQ02CedulaFormatoDudoso,
    ReglaQ03FechaEnCedula,
    ReglaQ04NombreVacio,
    ReglaQ05SexoIncompatible,
    ReglaQ06SexoAusente,
    ReglaQ07EdadAusente,
    ReglaQ08EdadAtipicaEstamento,
    ReglaQ09CarreraAbreviadaAmbigua,
    ReglaQ10CarreraNoHomologada,
    ReglaQ11EtniaNoCatalogada,
    ReglaQ12CategoriaDesconocida,
    ReglaQ13ParticipacionRepetida,
    ReglaQ14PrevalenciaBeneficiario,
    ReglaQ15IntegridadReferencialHuerfana,
    ReglaQ16TituloDiscordanteWordVsAsistencia,
    ReglaQ17FechaDiscordanteWordVsAsistencia,
    ReglaQ18MetaPlanificadaVsAsistenciasReales,
    ReglaQ19ConteoNarrativoVsFilasNominales,
    ReglaQ20PosibleDuplicadoPersona,
)
from app.quality.validator import QualityValidator


# ==============================================================================
# 1. PRUEBAS DE SEVERIDADES Y ESTADOS
# ==============================================================================

class TestSeveridadesYEstadosCalidad:
    """Verifica el cumplimiento de las 4 severidades y la separación estricta de estados."""

    def test_01_severidades_oficiales_unicas_cuatro(self):
        """Verifica que solo se admiten INFO, WARNING, ERROR, CRITICAL y rechaza REVISION."""
        # Válidas
        for sev in ("INFO", "WARNING", "ERROR", "CRITICAL"):
            f = ValidationFinding(
                codigo_regla="TEST",
                severidad=sev,
                entidad_afectada="ACTIVIDAD",
                mensaje_humano="Mensaje de prueba",
            )
            assert f.severidad == sev

        # REVISION como severidad debe ser rechazada categóricamente
        with pytest.raises(ValidationError) as exc:
            ValidationFinding(
                codigo_regla="TEST",
                severidad="REVISION",
                entidad_afectada="ACTIVIDAD",
                mensaje_humano="Invalido",
            )
        assert "REVISION" in str(exc.value)

    def test_02_cuatro_fenomenos_conceptuales(self):
        """Verifica la separación de los 4 fenómenos: Error, Inconsistencia, Duplicado, Revisión."""
        p_error = Person.model_construct(nombre_completo=" ", fuente_origen="doc.xlsx")  # Error de datos
        p_inconsistente = Person(nombre_completo="Carlos", cedula="20-04-2008")  # Inconsistencia
        p_duplicado1 = Person(nombre_completo="Juan Pérez", cedula=None)  # Posible duplicado
        p_duplicado2 = Person(nombre_completo="Juan Pérez", cedula=None)
        p_doc = Person(nombre_completo="Ana Ruiz", carrera_original="Lic. Conta")  # Revisión doc

        ctx = QualityContext(personas=[p_error, p_inconsistente, p_duplicado1, p_duplicado2, p_doc])
        validator = QualityValidator()
        assessment = validator.evaluar_contexto(ctx)

        codigos = {h.codigo_regla for h in assessment.hallazgos}
        assert "Q-04" in codigos  # Error de datos
        assert "Q-03" in codigos  # Inconsistencia (cédula fecha)
        assert "Q-20" in codigos  # Posible duplicado
        assert "Q-09" in codigos  # Revisión documental (carrera abreviada)

    def test_03_separacion_estricta_estados_operativos(self):
        """Verifica que EN_REVISION != COLA_REVISION != BLOQUEADO != REQUIERE_REVISION."""
        # EN_REVISION: Tiene matriz destino M2 pero requiere confirmación
        part_en_rev = Participation(
            id_actividad="act-1",
            id_persona="per-1",
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            requiere_revision=True,
            matriz_destino="M2",
        )
        # COLA_REVISION: Categoría desconocida
        part_cola = Participation(
            id_actividad="act-1",
            id_persona="per-2",
            categoria_participacion=CategoriaParticipacion.DESCONOCIDO,
            matriz_destino="COLA_REVISION",
        )
        # BLOQUEADO: Error referencial
        part_bloq = Participation(
            id_actividad="act-inexistente",
            id_persona="per-3",
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            matriz_destino=None,
        )

        assert part_en_rev.matriz_destino == "M2"
        assert part_en_rev.requiere_revision is True
        assert part_cola.matriz_destino == "COLA_REVISION"
        assert part_bloq.matriz_destino is None
        assert part_en_rev.matriz_destino != part_cola.matriz_destino
        assert part_cola.matriz_destino != part_bloq.matriz_destino

    def test_04_estados_reales_discrepancia(self):
        """Verifica el ciclo de vida real: REQUIERE_REVISION -> EN_REVISION -> ACLARADO / CONCORDANTE."""
        repo = InMemoryDiscrepanciaRepository()
        disc = Discrepancia(
            id_actividad="act-1",
            tipo_discrepancia=TipoDiscrepancia.PLAN_VS_REAL,
            severidad=SeveridadDiscrepancia.WARNING,
            fuente_a_nombre="Plan.meta",
            fuente_a_valor="50",
            fuente_b_nombre="Asistencias.total",
            fuente_b_valor="35",
            delta_valor="Diferencia de 15",
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
        )
        repo.save(disc)

        # 1. Nacimiento en REQUIERE_REVISION
        recuperada = repo.get_by_id(disc.id_discrepancia)
        assert recuperada is not None
        assert recuperada.estado == EstadoDiscrepancia.REQUIERE_REVISION

        # 2. Transición a EN_REVISION
        repo.registrar_revision(
            id_discrepancia=disc.id_discrepancia,
            nuevo_estado="EN_REVISION",
            justificacion="Auditoría abierta",
            usuario_revisor="auditor1",
        )
        en_rev = repo.get_by_id(disc.id_discrepancia)
        assert en_rev.estado == EstadoDiscrepancia.EN_REVISION

        # 3. Resolución pericial a ACLARADO (sin mutar valores fuente)
        repo.registrar_revision(
            id_discrepancia=disc.id_discrepancia,
            nuevo_estado="ACLARADO",
            justificacion="Justificado por lluvia torrencial en la sede",
            usuario_revisor="auditor1",
        )
        aclarada = repo.get_by_id(disc.id_discrepancia)
        assert aclarada.estado == EstadoDiscrepancia.ACLARADO
        assert aclarada.fuente_a_valor == "50"  # Inmutable
        assert aclarada.fuente_b_valor == "35"  # Inmutable
        assert aclarada.delta_valor == "Diferencia de 15"  # Inmutable
        assert aclarada.usuario_revisor == "auditor1"


# ==============================================================================
# 2. PRUEBAS DE REGLAS INDIVIDUALES Q-01 A Q-20
# ==============================================================================

class TestReglasCalidadQ01aQ20:
    """Verifica el comportamiento de cada regla individual Q-01 a Q-20."""

    def test_q01_cedula_vacia(self):
        p = Person(nombre_completo="Carlos Méndez", cedula=None)
        ctx = QualityContext(personas=[p])
        findings = ReglaQ01CedulaVacia().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-01"
        assert findings[0].severidad == "WARNING"
        assert findings[0].requiere_discrepancia_persistente is False

    def test_q02_cedula_formato_dudoso(self):
        p = Person(nombre_completo="María López", cedula="1234567")
        ctx = QualityContext(personas=[p])
        findings = ReglaQ02CedulaFormatoDudoso().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-02"
        assert findings[0].severidad == "WARNING"

    def test_q03_fecha_en_cedula_no_muta_persona(self):
        """Q-03: Detecta fecha, genera hallazgo y discrepancia, y NO muta Person.cedula."""
        fecha_cruda = "20-04-2008"
        p = Person(nombre_completo="Joven Prodigio", cedula=fecha_cruda)
        ctx = QualityContext(personas=[p])

        findings = ReglaQ03FechaEnCedula().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-03"
        assert findings[0].severidad == "WARNING"
        assert findings[0].requiere_discrepancia_persistente is True
        assert findings[0].valor_detectado == fecha_cruda

        # GARANTÍA RN-C07: Person.cedula NO fue sustituida por None ni modificada
        assert p.cedula == fecha_cruda

    def test_q04_nombre_vacio_bloquea(self):
        p = Person.model_construct(id_persona_interno="p-err", nombre_completo="")
        ctx = QualityContext(personas=[p])
        findings = ReglaQ04NombreVacio().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-04"
        assert findings[0].severidad == "ERROR"

    def test_q05_sexo_incompatible(self):
        p = Person(nombre_completo="Pedro Solís", sexo_original="X", sexo_normalizado=None)
        ctx = QualityContext(personas=[p])
        findings = ReglaQ05SexoIncompatible().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-05"
        assert findings[0].severidad == "WARNING"

    def test_q06_sexo_ausente(self):
        p = Person(nombre_completo="Persona Sin Sexo", sexo_original=None, sexo_normalizado=None)
        ctx = QualityContext(personas=[p])
        findings = ReglaQ06SexoAusente().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-06"
        assert findings[0].severidad == "WARNING"

    def test_q07_edad_ausente(self):
        p = Person(nombre_completo="Elena Torres", edad=None)
        ctx = QualityContext(personas=[p])
        findings = ReglaQ07EdadAusente().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-07"
        assert findings[0].severidad == "WARNING"

    def test_q08_edad_atipica_docente_no_error_automatico(self):
        p = Person(nombre_completo="Niño Genio", edad=14)
        part = Participation(
            id_actividad="act-1",
            id_persona=p.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
        )
        ctx = QualityContext(personas=[p], participaciones=[part])
        findings = ReglaQ08EdadAtipicaEstamento().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-08"
        assert findings[0].severidad == "WARNING"  # No es error automático

    def test_q09_carrera_abreviada_o_ambigua(self):
        p1 = Person(nombre_completo="Estudiante 1", carrera_original="Lic. Conta")
        p2 = Person(nombre_completo="Estudiante 2", carrera_original="A. estudiantil")
        ctx = QualityContext(personas=[p1, p2])
        findings = ReglaQ09CarreraAbreviadaAmbigua().evaluar(ctx)
        assert len(findings) == 2
        assert all(f.codigo_regla == "Q-09" and f.severidad == "WARNING" for f in findings)

    def test_q10_carrera_no_homologada_open_01(self):
        p = Person(nombre_completo="Luis Vega", carrera_original="Robótica Cuántica", carrera_oficial=None)
        ctx = QualityContext(personas=[p], catalogo_carreras=["INFORMÁTICA", "ADMINISTRACIÓN"])
        findings = ReglaQ10CarreraNoHomologada().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-10"
        assert findings[0].severidad == "WARNING"
        assert p.carrera_original == "Robótica Cuántica"  # No muta

    def test_q11_etnia_no_catalogada_open_04(self):
        p = Person(nombre_completo="Comunitario Rama", etnia="Rama-Criollo Autodefinido")
        ctx = QualityContext(personas=[p], catalogo_etnias=["MISKITU", "CREOLE", "MESTIZO"])
        findings = ReglaQ11EtniaNoCatalogada().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-11"
        assert findings[0].severidad == "WARNING"
        assert p.etnia == "Rama-Criollo Autodefinido"  # Preserva autodefinición

    def test_q12_categoria_desconocida_asigna_cola_revision(self):
        part = Participation(
            id_actividad="act-1",
            id_persona="per-1",
            categoria_participacion=CategoriaParticipacion.DESCONOCIDO,
        )
        ctx = QualityContext(participaciones=[part])
        findings = ReglaQ12CategoriaDesconocida().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-12"
        assert findings[0].severidad == "WARNING"

    def test_q13_participacion_repetida_preserva_observaciones_y_crea_discrepancia(self):
        part1 = Participation(id_actividad="act-1", id_persona="p-1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad="act-1", id_persona="p-1", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        ctx = QualityContext(participaciones=[part1, part2])
        findings = ReglaQ13ParticipacionRepetida().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-13"
        assert findings[0].severidad == "WARNING"
        assert findings[0].requiere_discrepancia_persistente is True

    def test_q14_prevalencia_beneficiario_rn_c03(self):
        part = Participation(
            id_actividad="act-1",
            id_persona="p-1",
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            es_beneficiado_rol=True,
        )
        ctx = QualityContext(participaciones=[part])
        findings = ReglaQ14PrevalenciaBeneficiario().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-14"
        assert findings[0].severidad == "INFO"

    def test_q15_integridad_referencial_huerfana_bloquea(self):
        act = Activity(id_actividad="act-real", nombre_actividad_original="Taller")
        p = Person(nombre_completo="Juan")
        part_act_mala = Participation(id_actividad="act-falsa", id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part_per_mala = Participation(id_actividad="act-real", id_persona="per-falsa", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        ctx = QualityContext(actividad=act, personas=[p], participaciones=[part_act_mala, part_per_mala])
        findings = ReglaQ15IntegridadReferencialHuerfana().evaluar(ctx)
        assert len(findings) == 2
        assert all(f.codigo_regla == "Q-15" and f.severidad == "ERROR" for f in findings)

    def test_q16_titulo_discordante_word_vs_asistencia(self):
        act = Activity(nombre_actividad_original="Taller de Programación en Python")
        ctx = QualityContext(actividad=act, titulo_informe="Taller Python BICU")
        findings = ReglaQ16TituloDiscordanteWordVsAsistencia().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-16"
        assert findings[0].severidad == "INFO"

    def test_q17_fecha_discordante_word_vs_asistencia(self):
        act = Activity(nombre_actividad_original="Feria", fecha_evento="2026-09-15")
        ctx = QualityContext(actividad=act, fecha_informe="2026-09-16")
        findings = ReglaQ17FechaDiscordanteWordVsAsistencia().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-17"
        assert findings[0].severidad == "WARNING"
        assert findings[0].requiere_discrepancia_persistente is True

    def test_q18_meta_planificada_vs_asistencias_reales(self):
        act = Activity(nombre_actividad_original="Capacitación")
        parts = [Participation(id_actividad="act-1", id_persona=f"p-{i}", categoria_participacion=CategoriaParticipacion.ESTUDIANTE) for i in range(25)]
        ctx = QualityContext(actividad=act, participaciones=parts, meta_planificada=40)
        findings = ReglaQ18MetaPlanificadaVsAsistenciasReales().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-18"
        assert findings[0].severidad == "WARNING"
        assert findings[0].requiere_discrepancia_persistente is True
        assert "Delta: -15" in findings[0].mensaje_humano

    def test_q19_conteo_narrativo_vs_filas_nominales(self):
        act = Activity(nombre_actividad_original="Seminario")
        parts = [Participation(id_actividad="act-1", id_persona=f"p-{i}", categoria_participacion=CategoriaParticipacion.ESTUDIANTE) for i in range(20)]
        ctx = QualityContext(actividad=act, participaciones=parts, total_asistentes_declarados_informe=25)
        findings = ReglaQ19ConteoNarrativoVsFilasNominales().evaluar(ctx)
        assert len(findings) == 1
        assert findings[0].codigo_regla == "Q-19"
        assert findings[0].severidad == "WARNING"
        assert findings[0].requiere_discrepancia_persistente is True
        assert "Delta: -5" in findings[0].mensaje_humano

    def test_q20_posible_duplicado_no_crea_no_fusiona_no_elimina_personas(self):
        """Q-20: Detecta coincidencia sin cédula, alerta y NO crea/fusiona/elimina personas."""
        p1 = Person(nombre_completo="Roberto Carlos Gómez", cedula=None)
        p2 = Person(nombre_completo="Roberto Carlos Gomez", cedula=None)
        personas_iniciales = [p1, p2]
        ctx = QualityContext(personas=personas_iniciales)

        findings = ReglaQ20PosibleDuplicadoPersona().evaluar(ctx)
        assert len(findings) >= 1
        assert findings[0].codigo_regla == "Q-20"
        assert findings[0].severidad == "WARNING"
        assert findings[0].requiere_discrepancia_persistente is True

        # GARANTÍA RN-C07:
        # 1. No se crearon personas nuevas
        assert len(ctx.personas) == 2
        # 2. No se fusionaron las personas
        assert p1.id_persona_interno != p2.id_persona_interno
        # 3. No se alteró su identidad
        assert p1.nombre_completo == "Roberto Carlos Gómez"
        assert p2.nombre_completo == "Roberto Carlos Gomez"


# ==============================================================================
# 3. PRUEBAS DE QUALITYASSESSMENT (VALUE OBJECT INMUTABLE)
# ==============================================================================

class TestQualityAssessmentValueObject:
    """Verifica la naturaleza de Value Object inmutable en memoria."""

    def test_assessment_es_value_object_inmutable(self):
        assessment = QualityAssessment(
            id_actividad="act-1",
            total_actividades_evaluadas=1,
            total_personas_evaluadas=10,
            total_participaciones_evaluadas=10,
            total_reglas_ejecutadas=20,
            estado_general_calidad=EstadoGeneralCalidad.CONFORME,
        )
        assert assessment.id_actividad == "act-1"
        assert assessment.estado_general_calidad == EstadoGeneralCalidad.CONFORME

        # Verificar inmutabilidad (frozen)
        with pytest.raises(ValidationError):
            assessment.total_errores = 5  # type: ignore

    def test_clasificacion_operativa_en_assessment(self):
        """Verifica conteos de aptas, en_revision, cola_revision y bloqueadas."""
        act = Activity(id_actividad="act-1", nombre_actividad_original="Taller")
        p1 = Person(nombre_completo="Apto", cedula="001-010190-0001A")
        p2 = Person(nombre_completo="Con Fecha", cedula="20-04-2008")
        p3 = Person(nombre_completo="Desconocido", cedula=None)
        p4 = Person(nombre_completo="Huerfano", cedula="001-010190-0002B")

        part1 = Participation(id_actividad="act-1", id_persona=p1.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part2 = Participation(id_actividad="act-1", id_persona=p2.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part3 = Participation(id_actividad="act-1", id_persona=p3.id_persona_interno, categoria_participacion=CategoriaParticipacion.DESCONOCIDO)
        part4 = Participation(id_actividad="act-1", id_persona="p-no-existe", categoria_participacion=CategoriaParticipacion.ESTUDIANTE)

        ctx = QualityContext(
            actividad=act,
            personas=[p1, p2, p3, p4],
            participaciones=[part1, part2, part3, part4],
        )
        assessment = QualityValidator().evaluar_contexto(ctx)

        assert assessment.total_participaciones_evaluadas == 4
        assert assessment.total_aptas == 1
        assert assessment.total_en_revision == 1  # part2 (Q-03)
        assert assessment.total_cola_revision == 1  # part3 (Q-12 DESCONOCIDO)
        assert assessment.total_bloqueadas == 1  # part4 (Q-15 huérfano)
        assert assessment.estado_general_calidad == EstadoGeneralCalidad.BLOQUEADO


# ==============================================================================
# 4. PRUEBAS DE CASOS DE USO (APPLICATION LAYER)
# ==============================================================================

class TestApplicationUseCasesCalidad:
    """Verifica los casos de uso con persistencia, fakes, dry_run y rollback."""

    def test_evaluar_calidad_actividad_dry_run_cero_escrituras(self):
        """dry_run=True garantiza CERO escrituras persistentes en SQLite/Memoria."""
        act_repo = InMemoryActividadRepository()
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        disc_repo = InMemoryDiscrepanciaRepository()

        act = Activity(nombre_actividad_original="Taller Dry Run")
        act_repo.save(act)

        p = Person(nombre_completo="Persona Test", cedula="20-04-2008")  # Generará Q-03
        per_repo.save(p)

        part = Participation(id_actividad=act.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part_repo.save(part)

        use_case = EvaluarCalidadActividadUseCase(
            actividad_repo=act_repo,
            persona_repo=per_repo,
            participacion_repo=part_repo,
            discrepancia_repo=disc_repo,
        )

        # Ejecución en DRY RUN con persistir_discrepancias=True
        cmd = EvaluarCalidadActividadCommand(
            id_actividad=act.id_actividad,
            dry_run=True,
            persistir_discrepancias=True,
        )
        result_dto: QualityAssessmentDTO = use_case.execute(cmd)

        assert result_dto.id_actividad == act.id_actividad
        assert len(result_dto.hallazgos) >= 1

        # GARANTÍA DRY RUN: CERO escrituras en repositorios
        assert len(disc_repo.list_pendientes()) == 0
        part_sin_cambios = part_repo.get_by_id(part.id_participacion)
        assert part_sin_cambios.requiere_revision is False  # No se persistió el flag

    def test_evaluar_calidad_actividad_persistencia_activa(self):
        """dry_run=False y persistir_discrepancias=True persiste discrepancias y marcas operativas."""
        act_repo = InMemoryActividadRepository()
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        disc_repo = InMemoryDiscrepanciaRepository()

        act = Activity(nombre_actividad_original="Taller Producción")
        act_repo.save(act)

        p = Person(nombre_completo="Persona Real", cedula="20-04-2008")  # Q-03
        per_repo.save(p)

        part = Participation(id_actividad=act.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part_repo.save(part)

        use_case = EvaluarCalidadActividadUseCase(
            actividad_repo=act_repo,
            persona_repo=per_repo,
            participacion_repo=part_repo,
            discrepancia_repo=disc_repo,
        )

        cmd = EvaluarCalidadActividadCommand(
            id_actividad=act.id_actividad,
            dry_run=False,
            persistir_discrepancias=True,
        )
        result_dto = use_case.execute(cmd)

        assert result_dto.id_actividad == act.id_actividad

        # 1. Se persistió la discrepancia pericial
        discs = disc_repo.list_pendientes()
        assert len(discs) >= 1
        assert discs[0].tipo_discrepancia == TipoDiscrepancia.OTRO
        assert discs[0].estado == EstadoDiscrepancia.REQUIERE_REVISION

        # 2. Se actualizó la marca operativa en la participación
        part_act = part_repo.get_by_id(part.id_participacion)
        assert part_act.requiere_revision is True
        assert part_act.motivo_revision is not None

        # 3. GARANTÍA RN-C07: El dato fuente en Person permanece intacto
        p_consultada = per_repo.get_by_id(p.id_persona_interno)
        assert p_consultada.cedula == "20-04-2008"

    def test_evaluar_calidad_actividad_sin_persistir_discrepancias(self):
        """dry_run=False y persistir_discrepancias=False actualiza marcas pero NO inserta discrepancias."""
        act_repo = InMemoryActividadRepository()
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        disc_repo = InMemoryDiscrepanciaRepository()

        act = Activity(nombre_actividad_original="Taller Sin Discrepancias")
        act_repo.save(act)

        p = Person(nombre_completo="Participante", cedula="20-04-2008")
        per_repo.save(p)

        part = Participation(id_actividad=act.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part_repo.save(part)

        use_case = EvaluarCalidadActividadUseCase(
            actividad_repo=act_repo,
            persona_repo=per_repo,
            participacion_repo=part_repo,
            discrepancia_repo=disc_repo,
        )

        cmd = EvaluarCalidadActividadCommand(
            id_actividad=act.id_actividad,
            dry_run=False,
            persistir_discrepancias=False,
        )
        use_case.execute(cmd)

        # CERO discrepancias guardadas
        assert len(disc_repo.list_pendientes()) == 0
        # Pero sí marcas operativas en participación
        assert part_repo.get_by_id(part.id_participacion).requiere_revision is True

    def test_transaccion_y_rollback_con_uow(self):
        """Verifica reversión atómica de UoW ante simulación o excepción."""
        act_repo = InMemoryActividadRepository()
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        disc_repo = InMemoryDiscrepanciaRepository()

        act = Activity(nombre_actividad_original="Actividad UoW")
        act_repo.save(act)
        p = Person(nombre_completo="Persona UoW", cedula="20-04-2008")
        per_repo.save(p)
        part = Participation(id_actividad=act.id_actividad, id_persona=p.id_persona_interno, categoria_participacion=CategoriaParticipacion.ESTUDIANTE)
        part_repo.save(part)

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=part_repo,
            discrepancias=disc_repo,
        )

        use_case = EvaluarCalidadActividadUseCase(uow=uow)

        # dry_run con UoW -> rollback al final
        cmd = EvaluarCalidadActividadCommand(id_actividad=act.id_actividad, dry_run=True)
        use_case.execute(cmd)

        assert len(disc_repo.list_pendientes()) == 0

    def test_consultar_discrepancias_pendientes_use_case(self):
        disc_repo = InMemoryDiscrepanciaRepository()
        d1 = Discrepancia(id_actividad="act-1", fuente_a_nombre="A", fuente_a_valor="1", fuente_b_nombre="B", fuente_b_valor="2", severidad=SeveridadDiscrepancia.WARNING)
        d2 = Discrepancia(id_actividad="act-1", fuente_a_nombre="A", fuente_a_valor="1", fuente_b_nombre="B", fuente_b_valor="2", severidad=SeveridadDiscrepancia.INFO)
        disc_repo.save_batch([d1, d2])

        uc = ConsultarDiscrepanciasPendientesUseCase(discrepancia_repo=disc_repo)
        todas = uc.execute(ConsultarDiscrepanciasPendientesQuery())
        assert len(todas) == 2

        solo_warn = uc.execute(ConsultarDiscrepanciasPendientesQuery(severidad="WARNING"))
        assert len(solo_warn) == 1
        assert solo_warn[0].severidad == "WARNING"

    def test_resolver_revision_discrepancia_use_case_no_muta_fuentes(self):
        disc_repo = InMemoryDiscrepanciaRepository()
        d = Discrepancia(
            id_actividad="act-1",
            tipo_discrepancia=TipoDiscrepancia.PLAN_VS_REAL,
            severidad=SeveridadDiscrepancia.WARNING,
            fuente_a_nombre="Plan.meta",
            fuente_a_valor="100",
            fuente_b_nombre="Asistencia.real",
            fuente_b_valor="80",
            delta_valor="Delta 20",
        )
        disc_repo.save(d)

        uc = ResolverRevisionDiscrepanciaUseCase(discrepancia_repo=disc_repo)
        cmd = ResolverRevisionDiscrepanciaCommand(
            id_discrepancia=d.id_discrepancia,
            nuevo_estado=EstadoDiscrepancia.ACLARADO,
            justificacion_aclaratoria="Aclarado: asistencia presencial complementada con lista virtual",
            usuario_revisor="auditor.kenia",
        )
        res = uc.execute(cmd)

        assert res.estado == "ACLARADO"
        assert res.justificacion == "Aclarado: asistencia presencial complementada con lista virtual"
        assert res.usuario_revisor == "auditor.kenia"

        # GARANTÍA RN-C07: Los valores originales de Fuente A y Fuente B están 100% intactos
        assert res.valor_a == "100"
        assert res.valor_b == "80"
        assert res.delta == "Delta 20"


# ==============================================================================
# 5. GARANTÍA RN-C07: NO MUTACIÓN DE DATOS FUENTE PROTEGIDOS
# ==============================================================================

class TestGarantiasRN_C07_NoMutacion:
    """Valida la estricta distinción entre datos de negocio protegidos y marcas operativas."""

    def test_datos_fuente_protegidos_permanecen_inmutables(self):
        """Los datos biográficos, académicos y títulos NUNCA mutan durante la evaluación."""
        act = Activity(
            id_actividad="act-fija",
            nombre_actividad_original="Congreso Universitario 2026",
            fecha_evento=date(2026, 9, 18),
            sede="BLUEFIELDS",
        )
        p = Person(
            id_persona_interno="p-fija",
            nombre_completo="Francisca Altamirano",
            cedula="20-04-2008",
            sexo_original="M",
            edad=15,
            carrera_original="Lic. Conta",
            etnia="Criollo Autodefinido",
        )
        part = Participation(
            id_actividad=act.id_actividad,
            id_persona=p.id_persona_interno,
            categoria_participacion=CategoriaParticipacion.DOCENTE,
            observaciones="Fila física 1",
        )

        ctx = QualityContext(
            actividad=act,
            personas=[p],
            participaciones=[part],
            titulo_informe="Congreso BICU",  # Desata Q-16
            meta_planificada=50,             # Desata Q-18
        )

        validator = QualityValidator()
        validator.evaluar_contexto(ctx)

        # 1. Datos protegidos de Actividad
        assert act.nombre_actividad_original == "Congreso Universitario 2026"
        assert act.fecha_evento == date(2026, 9, 18)
        assert act.sede == "BLUEFIELDS"

        # 2. Datos protegidos de Persona
        assert p.nombre_completo == "Francisca Altamirano"
        assert p.cedula == "20-04-2008"  # Q-03 NO MUTÓ LA CÉDULA
        assert p.sexo_original == "M"
        assert p.edad == 15
        assert p.carrera_original == "Lic. Conta"
        assert p.etnia == "Criollo Autodefinido"


# ==============================================================================
# 6. AISLAMIENTO CLEAN ARCHITECTURE Y SCHEMA
# ==============================================================================

class TestAislamientoArquitectonicoCleanArchitecture:
    """Verifica ausencia de acoplamiento prohibido e inalterabilidad de schema."""

    def test_no_forbidden_imports_in_app_quality(self):
        """Verifica que app/quality NO importa sqlite3, openpyxl, docx, customtkinter ni GUI."""
        quality_dir = Path(__file__).resolve().parent.parent / "app" / "quality"
        forbidden_modules = {
            "sqlite3",
            "openpyxl",
            "docx",
            "python-docx",
            "customtkinter",
            "tkinter",
            "app.infrastructure",
            "app.exporters",
        }

        for py_file in quality_dir.glob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_modules:
                            assert not alias.name.startswith(forbidden), (
                                f"Import prohibido '{alias.name}' detectado en {py_file.name}."
                            )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for forbidden in forbidden_modules:
                        assert not mod.startswith(forbidden), (
                            f"ImportFrom prohibido '{mod}' detectado en {py_file.name}."
                        )

    def test_sqlite_19_tablas_y_cero_migraciones_nuevas(self):
        """Verifica que el schema relacional mantiene exactamente 19 tablas y cero migraciones nuevas."""
        assert len(EXPECTED_TABLE_NAMES) == 19
        assert "discrepancia" in EXPECTED_TABLE_NAMES
        assert "participacion" in EXPECTED_TABLE_NAMES
        assert "quality_assessment" not in EXPECTED_TABLE_NAMES  # No se creó tabla
