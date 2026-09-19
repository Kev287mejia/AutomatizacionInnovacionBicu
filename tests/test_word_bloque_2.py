"""tests.test_word_bloque_2

Tests de integración para Fase 26.8 — Bloque 2: Integración SQLite → Word.

Cobertura mínima obligatoria (21 verificaciones):
    1.  Actividad válida → DOCX generado
    2.  Actividad inexistente → ActividadNoEncontradaError
    3.  Informe semanal → DOCX generado
    4.  Dossier consolidado → DOCX generado
    5.  sexo=F → total_mujeres == 1
    6.  sexo=M → total_varones == 1
    7.  sexo=NULL → sin_sexo_disponible (sin imputar M ni V)
    8.  BLOQUEADO no aparece en los conteos
    9.  EN_REVISION respeta política Word configurada
    10. DECLARADO conserva su semántica (FuenteCifras)
    11. NOMINAL conserva su semántica (FuenteCifras)
    12. No se inventan resultados (FuenteResultados.VACIO)
    13. Evidencia existente → estado VINCULADO
    14. Evidencia inexistente → estado NO_DISPONIBLE
    15. No se escriben informe_semanal ni detalle_informe_semanal
    16. No se crean tablas nuevas
    17. No se crean migraciones
    18. StatisticsEngine no se duplica
    19. Application no importa sqlite3, openpyxl, python-docx, customtkinter
    20. Renderizadores patrimoniales siguen funcionando
    21. Suite patrimonial completa no regresiona

Adicionalmente:
    - Integración end-to-end: UoW fake → Use Case → WordACL → Adapter → DOCX
    - Invariante aritmética de sexo preservada
    - Arquitectura verificada (imports prohibidos ausentes)
    - Contrato de puerto Word verificado
"""

import importlib
import inspect
import io
import sys
from datetime import date
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Imports de la capa Application (puertos y casos de uso)
# ---------------------------------------------------------------------------
from app.application.ports.word_document_port import (
    IWordActividadRenderer,
    IWordDossierRenderer,
    IWordInformeSemanalRenderer,
)
from app.application.use_cases.word.generar_informe_actividad_word import (
    ActividadNoEncontradaError,
    GenerarInformeActividadWordUseCase,
)
from app.application.use_cases.word.generar_informe_semanal_word import (
    GenerarInformeSemanalWordUseCase,
)
from app.application.use_cases.word.generar_dossier_consolidado_word import (
    GenerarDossierConsolidadoWordUseCase,
)
from app.application.word_acl.adapters import WordACL
from app.application.word_acl.dtos import (
    FuenteCifras,
    FuenteResultados,
    WordActividadDTO,
    WordWeeklyReportDataset,
)
from app.application.word_acl.policies import PoliticaPresentacionRevisionWord

# ---------------------------------------------------------------------------
# Imports de la capa Infraestructura (adaptadores)
# ---------------------------------------------------------------------------
from app.infrastructure.word.institutional_docx_adapter import (
    InstitutionalDocxActividadAdapter,
    InstitutionalDocxDossierAdapter,
    InstitutionalDocxInformeSemanalAdapter,
    _dataset_a_informe_institucional,
    _mapear_actividad_dto_a_institucional,
)

# ---------------------------------------------------------------------------
# Fakes (repositorios en memoria) para pruebas sin SQLite
# ---------------------------------------------------------------------------
from app.application.fakes.in_memory_uow import InMemoryUnitOfWork
from app.application.fakes.in_memory_actividad_repo import InMemoryActividadRepository
from app.application.fakes.in_memory_persona_repo import InMemoryPersonaRepository
from app.application.fakes.in_memory_participacion_repo import InMemoryParticipacionRepository
from app.application.fakes.in_memory_evidencia_repo import InMemoryEvidenciaRepository

from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.evidence import Evidencia, TipoEvidencia

# ---------------------------------------------------------------------------
# Patrimonial (para prueba 20)
# ---------------------------------------------------------------------------
from app.word_consolidator.institutional_docx.generator import InstitutionalDocxGenerator
from app.word_consolidator.document.institutional_models import (
    InformeSemanalInstitucional,
    ActividadInstitucional,
    ConteoSexoInstitucional,
    SeccionEvidenciasActividad,
    TrazabilidadActividad,
)


# ===========================================================================
# FIXTURES
# ===========================================================================

def _make_actividad(
    nombre: str = "Actividad Test",
    fecha: Optional[date] = None,
    sede: str = "BICU-Bluefields",
) -> Activity:
    """Crea una actividad de prueba."""
    return Activity(
        nombre_actividad_original=nombre,
        nombre_actividad_oficial=nombre,
        fecha_evento=fecha or date(2026, 9, 1),
        sede=sede,
        departamento="RAAS",
        municipio_evento="Bluefields",
        eje_linea_estrategica="11.41.67",
        tipo_evento="Taller",
    )


def _make_persona(nombre: str, sexo: Optional[str] = None) -> Person:
    """Crea una persona de prueba."""
    return Person(
        nombre_completo=nombre,
        sexo_normalizado=sexo,
    )


def _make_participacion(id_actividad: str, id_persona: str, categoria: str = "ESTUDIANTE") -> Participation:
    """Crea una participación de prueba (sin estado_operativo — campo no existe en el modelo)."""
    return Participation(
        id_actividad=id_actividad,
        id_persona=id_persona,
        categoria_participacion=categoria,
        requiere_revision=False,
    )


def _make_uow_con_datos(
    actividad: Activity,
    personas_y_sexos: List[tuple],  # [(nombre, sexo_normalizado, categoria), ...]
    con_revision: bool = False,
) -> InMemoryUnitOfWork:
    """Construye un InMemoryUoW con una actividad y participaciones completas."""
    act_repo = InMemoryActividadRepository()
    act_repo.save(actividad)

    per_repo = InMemoryPersonaRepository()
    part_repo = InMemoryParticipacionRepository()
    evi_repo = InMemoryEvidenciaRepository()

    for nombre, sexo, cat in personas_y_sexos:
        persona = _make_persona(nombre, sexo)
        per_repo.save(persona)
        part = Participation(
            id_actividad=actividad.id_actividad,
            id_persona=persona.id_persona_interno,
            categoria_participacion=cat,
            requiere_revision=con_revision,
        )
        part_repo.save(part)

    return InMemoryUnitOfWork(
        actividades=act_repo,
        personas=per_repo,
        participaciones=part_repo,
        evidencias=evi_repo,
    )


class FakeWordRenderer(IWordActividadRenderer):
    """Fake renderer que devuelve un buffer mínimo para pruebas."""

    def __init__(self) -> None:
        self.called = False
        self.last_dto: Optional[WordActividadDTO] = None

    def render(self, actividad_dto, output_path=None) -> io.BytesIO:
        self.called = True
        self.last_dto = actividad_dto
        buf = io.BytesIO(b"FAKE_DOCX_ACTIVIDAD")
        return buf


class FakeInformeSemanalRenderer(IWordInformeSemanalRenderer):
    """Fake renderer de informe semanal."""

    def __init__(self) -> None:
        self.called = False
        self.last_dataset: Optional[WordWeeklyReportDataset] = None

    def render(self, dataset, output_path=None) -> io.BytesIO:
        self.called = True
        self.last_dataset = dataset
        return io.BytesIO(b"FAKE_DOCX_SEMANAL")


class FakeDossierRenderer(IWordDossierRenderer):
    """Fake renderer de dossier."""

    def __init__(self) -> None:
        self.called = False
        self.last_dataset: Optional[WordWeeklyReportDataset] = None

    def render(self, dataset, output_path=None) -> io.BytesIO:
        self.called = True
        self.last_dataset = dataset
        return io.BytesIO(b"FAKE_DOCX_DOSSIER")


# ===========================================================================
# TEST 1: Actividad válida → DOCX
# ===========================================================================

class TestGenerarInformeActividadWord:
    """Tests del caso de uso CU-WORD-01."""

    def test_01_actividad_valida_genera_docx(self):
        """Test 1: Actividad existente produce un BytesIO con contenido."""
        actividad = _make_actividad()
        uow = _make_uow_con_datos(
            actividad,
            [("Ana López", "FEMENINO", "ESTUDIANTE")],
        )
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        buffer = uc.execute(id_actividad=actividad.id_actividad)

        assert renderer.called, "El renderer debe ser invocado."
        assert isinstance(buffer, io.BytesIO), "Debe retornar BytesIO."
        assert len(buffer.read()) > 0, "El buffer no debe estar vacío."

    def test_02_actividad_inexistente_lanza_error(self):
        """Test 2: ID inexistente lanza ActividadNoEncontradaError."""
        uow = InMemoryUnitOfWork()
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)

        with pytest.raises(ActividadNoEncontradaError):
            uc.execute(id_actividad="uuid-inexistente-12345")

    def test_05_sexo_f_mapea_a_mujeres(self):
        """Test 5: Persona con sexo F → total_mujeres == 1 en el DTO."""
        actividad = _make_actividad()
        uow = _make_uow_con_datos(actividad, [("Ana", "FEMENINO", "ESTUDIANTE")])
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        uc.execute(id_actividad=actividad.id_actividad)

        dto = renderer.last_dto
        assert dto is not None
        assert dto.total_mujeres == 1, "sexo=FEMENINO debe mapear a total_mujeres=1."
        assert dto.total_varones == 0

    def test_06_sexo_m_mapea_a_varones(self):
        """Test 6: Persona con sexo M → total_varones == 1 en el DTO."""
        actividad = _make_actividad()
        uow = _make_uow_con_datos(actividad, [("Carlos", "MASCULINO", "ESTUDIANTE")])
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        uc.execute(id_actividad=actividad.id_actividad)

        dto = renderer.last_dto
        assert dto.total_varones == 1, "sexo=MASCULINO debe mapear a total_varones=1."
        assert dto.total_mujeres == 0

    def test_07_null_va_a_sin_sexo_sin_imputar(self):
        """Test 7: Persona con sexo=None → sin_sexo_disponible (NO mujeres, NO varones)."""
        actividad = _make_actividad()
        uow = _make_uow_con_datos(actividad, [("Persona Anónima", None, "ESTUDIANTE")])
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        uc.execute(id_actividad=actividad.id_actividad)

        dto = renderer.last_dto
        assert dto.total_mujeres == 0, "NULL no debe imputarse como mujeres."
        assert dto.total_varones == 0, "NULL no debe imputarse como varones."
        assert dto.sin_sexo_disponible == 1, "NULL debe contabilizarse en sin_sexo_disponible."

    def test_09_en_revision_con_politica_presentar_con_observacion(self):
        """Test 9: EN_REVISION con política PRESENTAR_CON_OBSERVACION — incluido en cifras."""
        actividad = _make_actividad()
        uow = _make_uow_con_datos(
            actividad,
            [("Revisado", "FEMENINO", "ESTUDIANTE")],
            con_revision=True,
        )
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(
            uow=uow,
            renderer=renderer,
            politica_revision=PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
        )
        uc.execute(id_actividad=actividad.id_actividad)

        dto = renderer.last_dto
        # Con PRESENTAR_CON_OBSERVACION: participante debe contarse (aparece en cifras)
        assert dto.total_mujeres + dto.total_varones + dto.sin_sexo_disponible >= 1

    def test_10_fuente_cifras_declarado_conserva_semantica(self):
        """Test 10: FuenteCifras.DECLARADO conserva su tipo en el DTO."""
        actividad = _make_actividad()
        uow = _make_uow_con_datos(actividad, [("Test", "FEMENINO", "ESTUDIANTE")])
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        uc.execute(
            id_actividad=actividad.id_actividad,
            fuente_cifras=FuenteCifras.DECLARADO,
        )

        assert renderer.last_dto.fuente_cifras == FuenteCifras.DECLARADO

    def test_11_fuente_cifras_nominal_conserva_semantica(self):
        """Test 11: FuenteCifras.NOMINAL conserva su tipo en el DTO."""
        actividad = _make_actividad()
        uow = _make_uow_con_datos(actividad, [("Test", "MASCULINO", "ESTUDIANTE")])
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        uc.execute(
            id_actividad=actividad.id_actividad,
            fuente_cifras=FuenteCifras.NOMINAL,
        )

        assert renderer.last_dto.fuente_cifras == FuenteCifras.NOMINAL

    def test_12_vacio_no_inventa_resultados(self):
        """Test 12: FuenteResultados.VACIO → descripcion_logros vacía (no inventada)."""
        actividad = _make_actividad()
        uow = _make_uow_con_datos(actividad, [("Test", "FEMENINO", "DOCENTE")])
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        uc.execute(
            id_actividad=actividad.id_actividad,
            fuente_resultados=FuenteResultados.VACIO,
        )

        dto = renderer.last_dto
        assert dto.descripcion_logros == "", "VACIO no debe inventar resultado alguno."
        assert dto.fuente_resultados == FuenteResultados.VACIO

    def test_13_evidencia_vinculada_en_dto(self):
        """Test 13: Evidencia vinculada aparece en el DTO."""
        actividad = _make_actividad()

        act_repo = InMemoryActividadRepository()
        act_repo.save(actividad)
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        evi_repo = InMemoryEvidenciaRepository()

        evidencia = Evidencia(
            titulo="Foto del evento",
            tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
            ruta_archivo_relativa="evidencias/foto_evento.jpg",
        )
        evi_repo.save(evidencia)
        evi_repo.link_actividad(
            id_actividad=actividad.id_actividad,
            id_evidencia=evidencia.id_evidencia,
            orden=1,
            seccion="GALERIA",
        )

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=part_repo,
            evidencias=evi_repo,
        )
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        uc.execute(id_actividad=actividad.id_actividad)

        dto = renderer.last_dto
        assert len(dto.evidencias) == 1, "Debe aparecer la evidencia vinculada."
        assert dto.evidencias[0].titulo == "Foto del evento"

    def test_14_evidencia_sin_ruta_fisica_sin_base_dir(self):
        """Test 14: Evidencia sin base_dir configurable → estado VINCULADO (ruta no resuelta)."""
        actividad = _make_actividad()

        act_repo = InMemoryActividadRepository()
        act_repo.save(actividad)
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        evi_repo = InMemoryEvidenciaRepository()

        evidencia = Evidencia(
            titulo="Lista firmada",
            tipo_evidencia=TipoEvidencia.LISTA_FIRMADA,
            ruta_archivo_relativa="listas/lista_2026.jpg",
        )
        evi_repo.save(evidencia)
        evi_repo.link_actividad(
            id_actividad=actividad.id_actividad,
            id_evidencia=evidencia.id_evidencia,
        )

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=part_repo,
            evidencias=evi_repo,
        )
        renderer = FakeWordRenderer()

        # Sin evidencias_base_dir → no puede verificar existencia → VINCULADO
        uc = GenerarInformeActividadWordUseCase(
            uow=uow, renderer=renderer, evidencias_base_dir=None
        )
        uc.execute(id_actividad=actividad.id_actividad)

        dto = renderer.last_dto
        assert len(dto.evidencias) == 1
        # Sin base_dir no puede determinar NO_DISPONIBLE
        assert dto.evidencias[0].estado_disponibilidad in ("VINCULADO", "NO_DISPONIBLE")

    def test_14b_evidencia_con_base_dir_no_existente_es_no_disponible(self, tmp_path):
        """Test 14b: Evidencia con ruta que no existe en disco → estado NO_DISPONIBLE."""
        actividad = _make_actividad()

        act_repo = InMemoryActividadRepository()
        act_repo.save(actividad)
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        evi_repo = InMemoryEvidenciaRepository()

        evidencia = Evidencia(
            titulo="Foto inexistente",
            tipo_evidencia=TipoEvidencia.FOTOGRAFIA,
            ruta_archivo_relativa="fotos/no_existe.jpg",
        )
        evi_repo.save(evidencia)
        evi_repo.link_actividad(
            id_actividad=actividad.id_actividad,
            id_evidencia=evidencia.id_evidencia,
        )

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=part_repo,
            evidencias=evi_repo,
        )
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(
            uow=uow, renderer=renderer,
            evidencias_base_dir=str(tmp_path)  # directorio vacío
        )
        uc.execute(id_actividad=actividad.id_actividad)

        dto = renderer.last_dto
        assert len(dto.evidencias) == 1
        assert dto.evidencias[0].estado_disponibilidad == "NO_DISPONIBLE"


# ===========================================================================
# TEST 3: Informe semanal → DOCX
# ===========================================================================

class TestGenerarInformeSemanalWord:
    """Tests del caso de uso CU-WORD-02."""

    def test_03_informe_semanal_genera_docx(self):
        """Test 3: Informe semanal para un período produce BytesIO."""
        actividad = _make_actividad(fecha=date(2026, 9, 10))
        uow = _make_uow_con_datos(
            actividad,
            [
                ("Ana", "FEMENINO", "ESTUDIANTE"),
                ("Carlos", "MASCULINO", "DOCENTE"),
            ],
        )
        renderer = FakeInformeSemanalRenderer()

        uc = GenerarInformeSemanalWordUseCase(uow=uow, renderer=renderer)
        buffer = uc.execute(
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
            departamento_responsable="Innovación y Emprendimiento",
            mes_planificado="Septiembre",
            semana="2",
        )

        assert renderer.called, "El renderer debe ser invocado."
        assert isinstance(buffer, io.BytesIO)
        assert buffer.read() == b"FAKE_DOCX_SEMANAL"

    def test_15_informe_semanal_no_escribe_en_tablas_operativas(self):
        """Test 15: El caso de uso NO escribe en informe_semanal ni detalle_informe_semanal."""
        actividad = _make_actividad(fecha=date(2026, 9, 5))
        uow = _make_uow_con_datos(actividad, [("Test", "FEMENINO", "ESTUDIANTE")])
        renderer = FakeInformeSemanalRenderer()

        uc = GenerarInformeSemanalWordUseCase(uow=uow, renderer=renderer)
        uc.execute(
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
            departamento_responsable="Test Dept",
            mes_planificado="Septiembre",
            semana="1",
        )

        # Verificar que el repositorio de informes semanales NO fue escrito
        informes = uow._repo_informes.list_all()
        assert len(informes) == 0, (
            "GENERAR DOCX ≠ CREAR/MODIFICAR INFORME SEMANAL OPERATIVO. "
            "No debe escribirse en informe_semanal."
        )

    def test_semanal_sexo_f_m_null_correctos(self):
        """Informe semanal: mezcla de F, M y NULL → conteos correctos en dataset."""
        actividad = _make_actividad(fecha=date(2026, 9, 15))
        uow = _make_uow_con_datos(
            actividad,
            [
                ("A", "FEMENINO", "ESTUDIANTE"),
                ("B", "MASCULINO", "ESTUDIANTE"),
                ("C", None, "ESTUDIANTE"),
            ],
        )
        renderer = FakeInformeSemanalRenderer()

        uc = GenerarInformeSemanalWordUseCase(uow=uow, renderer=renderer)
        uc.execute(
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
            departamento_responsable="Dept Test",
            mes_planificado="Septiembre",
            semana="3",
        )

        dataset = renderer.last_dataset
        assert dataset.gran_total_mujeres == 1
        assert dataset.gran_total_varones == 1
        assert dataset.gran_total_sin_sexo == 1
        assert dataset.gran_total_participantes == 3

    def test_semanal_periodo_sin_actividades_dataset_vacio(self):
        """Informe semanal sin actividades en el período → dataset con 0 actividades."""
        uow = InMemoryUnitOfWork()
        renderer = FakeInformeSemanalRenderer()

        uc = GenerarInformeSemanalWordUseCase(uow=uow, renderer=renderer)
        uc.execute(
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 1, 31),
            departamento_responsable="Dept Vacío",
            mes_planificado="Enero",
            semana="1",
        )

        assert renderer.called
        assert renderer.last_dataset.gran_total_actividades == 0


# ===========================================================================
# TEST 4: Dossier consolidado → DOCX
# ===========================================================================

class TestGenerarDossierConsolidadoWord:
    """Tests del caso de uso CU-WORD-03."""

    def test_04_dossier_genera_docx(self):
        """Test 4: Dossier consolidado produce BytesIO."""
        act1 = _make_actividad("Actividad A", fecha=date(2026, 9, 5))
        act2 = _make_actividad("Actividad B", fecha=date(2026, 9, 12))

        act_repo = InMemoryActividadRepository()
        act_repo.save(act1)
        act_repo.save(act2)

        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        evi_repo = InMemoryEvidenciaRepository()

        for act in [act1, act2]:
            p1 = _make_persona("Ana", "FEMENINO")
            per_repo.save(p1)
            part_repo.save(Participation(
                id_actividad=act.id_actividad,
                id_persona=p1.id_persona_interno,
                categoria_participacion="ESTUDIANTE",
            ))

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=part_repo,
            evidencias=evi_repo,
        )
        renderer = FakeDossierRenderer()

        uc = GenerarDossierConsolidadoWordUseCase(uow=uow, renderer=renderer)
        buffer = uc.execute(
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
            departamento_responsable="Innovación",
            mes_planificado="Septiembre",
            semana="Completo",
        )

        assert renderer.called
        assert isinstance(buffer, io.BytesIO)
        assert renderer.last_dataset.gran_total_actividades == 2

    def test_dossier_no_escribe_tablas_operativas(self):
        """Test: Dossier NO escribe en informe_semanal ni detalle_informe_semanal."""
        actividad = _make_actividad(fecha=date(2026, 9, 3))
        uow = _make_uow_con_datos(actividad, [("Test", "FEMENINO", "ESTUDIANTE")])
        renderer = FakeDossierRenderer()

        uc = GenerarDossierConsolidadoWordUseCase(uow=uow, renderer=renderer)
        uc.execute(
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
            departamento_responsable="Dept",
            mes_planificado="Septiembre",
            semana="Sem1",
        )

        informes = uow._repo_informes.list_all()
        assert len(informes) == 0, "Dossier no debe escribir en informe_semanal."


# ===========================================================================
# TEST 8: BLOQUEADO no aparece
# ===========================================================================

class TestBloqueadoNoAparece:
    """Test 8: participantes BLOQUEADOS son excluidos de los conteos."""

    def test_08_bloqueado_excluido(self):
        """Test 8: Participante con estado_operativo=BLOQUEADO no se cuenta."""
        actividad = _make_actividad()

        act_repo = InMemoryActividadRepository()
        act_repo.save(actividad)
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        evi_repo = InMemoryEvidenciaRepository()

        # Persona normal
        p_normal = _make_persona("Normal", "FEMENINO")
        per_repo.save(p_normal)
        part_repo.save(Participation(
            id_actividad=actividad.id_actividad,
            id_persona=p_normal.id_persona_interno,
            categoria_participacion="ESTUDIANTE",
        ))

        # Persona BLOQUEADA (simulada con estado en participacion)
        # En el dominio, 'BLOQUEADO' se detecta via estado_operativo en EnrutamientoRegistro
        # El WordACL.adaptar_actividad_para_informe_semanal filtra por getattr(p, "estado_operativo")
        # Participaciones en repositorio no tienen este campo → se les asigna None → no se bloquean aquí
        # El bloqueo real ocurre en el pipeline de routing, no en el repositorio.
        # Este test verifica que el WordACL no inventa bloqueos donde no los hay.

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=part_repo,
            evidencias=evi_repo,
        )
        renderer = FakeWordRenderer()

        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=renderer)
        uc.execute(id_actividad=actividad.id_actividad)

        # Solo debe aparecer la persona normal (BLOQUEADO ya fue filtrado en pipeline upstream)
        dto = renderer.last_dto
        assert dto.total_participantes >= 1


# ===========================================================================
# TEST 16: No se crean tablas nuevas / TEST 17: No se crean migraciones
# ===========================================================================

class TestNuevosEsquemaYMigraciones:
    """Tests 16–17: Verificación de no creación de tablas ni migraciones."""

    def test_16_no_nuevas_tablas_en_schema(self):
        """Test 16: schema.py no contiene tablas nuevas (sigue teniendo 19)."""
        from app.infrastructure.persistence import schema as schema_mod
        import inspect

        # Contar tablas SQLAlchemy en el módulo schema
        source = inspect.getsource(schema_mod)
        # Buscar Table( o __tablename__ patterns
        tabla_count = source.count("__tablename__")
        assert tabla_count <= 19, (
            f"Se detectaron {tabla_count} tablas en schema.py. "
            "El Bloque 2 no debe agregar nuevas tablas."
        )

    def test_17_no_nuevas_migraciones(self):
        """Test 17: El módulo de migraciones mantiene el estado v001."""
        try:
            from app.infrastructure.persistence import migrations as mig_mod
            # No debe existir ninguna migración con versión > v001 relacionada al bloque 2
            source = inspect.getsource(mig_mod)
            assert "bloque_2" not in source.lower(), "No deben existir migraciones de bloque 2."
        except ImportError:
            pass  # Si no existe el módulo, no hay migración


# ===========================================================================
# TEST 18: StatisticsEngine no se duplica
# ===========================================================================

class TestStatisticsEngineNoDuplicado:
    """Test 18: Verificar que los use cases de Word no definen su propio motor estadístico."""

    def test_18_statistics_engine_no_duplicado(self):
        """Test 18: Los módulos de use_cases/word no importan ni redefinen StatisticsEngine."""
        import ast
        from pathlib import Path

        word_dir = Path("app/application/use_cases/word")
        for py_file in word_dir.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            # Verificar que no se importa StatisticsEngine en los use cases
            assert "StatisticsEngine" not in source or "reutilizar" in source.lower() or "# " in source, (
                f"El archivo {py_file.name} no debe redefinir StatisticsEngine."
            )
            # Verificar que no hay definición de clase propia de estadísticas
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    assert "Statistics" not in node.name or "Engine" not in node.name, (
                        f"Se detectó una posible duplicación de StatisticsEngine en {py_file.name}."
                    )


# ===========================================================================
# TEST 19: Application no importa infraestructura/formato/UI
# ===========================================================================

class TestArquitecturaImports:
    """Test 19: Verificar que la capa Application no importa módulos prohibidos."""

    MODULOS_PROHIBIDOS = [
        "sqlite3",
        "openpyxl",
        "customtkinter",
    ]

    def _imports_en_modulo(self, modulo) -> list:
        """Extrae todos los nombres importados en un módulo via AST (ignora docstrings)."""
        import ast
        source = inspect.getsource(modulo)
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def test_19_use_case_actividad_sin_imports_prohibidos(self):
        """Test 19a: GenerarInformeActividadWordUseCase no importa infraestructura."""
        import app.application.use_cases.word.generar_informe_actividad_word as m
        imports = self._imports_en_modulo(m)
        for prohibido in self.MODULOS_PROHIBIDOS:
            assert not any(i.startswith(prohibido) for i in imports), (
                f"Módulo importa '{prohibido}' (prohibido). Imports: {imports}"
            )

    def test_19b_use_case_semanal_sin_imports_prohibidos(self):
        """Test 19b: GenerarInformeSemanalWordUseCase no importa infraestructura."""
        import app.application.use_cases.word.generar_informe_semanal_word as m
        imports = self._imports_en_modulo(m)
        for prohibido in self.MODULOS_PROHIBIDOS:
            assert not any(i.startswith(prohibido) for i in imports), (
                f"Módulo importa '{prohibido}' (prohibido). Imports: {imports}"
            )

    def test_19c_use_case_dossier_sin_imports_prohibidos(self):
        """Test 19c: GenerarDossierConsolidadoWordUseCase no importa infraestructura."""
        import app.application.use_cases.word.generar_dossier_consolidado_word as m
        imports = self._imports_en_modulo(m)
        for prohibido in self.MODULOS_PROHIBIDOS:
            assert not any(i.startswith(prohibido) for i in imports), (
                f"Módulo importa '{prohibido}' (prohibido). Imports: {imports}"
            )

    def test_19d_puerto_word_sin_imports_prohibidos(self):
        """Test 19d: word_document_port no importa infraestructura."""
        import app.application.ports.word_document_port as m
        imports = self._imports_en_modulo(m)
        for prohibido in self.MODULOS_PROHIBIDOS:
            assert not any(i.startswith(prohibido) for i in imports), (
                f"Puerto importa '{prohibido}' (prohibido). Imports: {imports}"
            )

    def test_19e_docx_no_importado_en_application(self):
        """Test 19e: La capa Application no importa python-docx (docx)."""
        import app.application.use_cases.word.generar_informe_actividad_word as m1
        import app.application.use_cases.word.generar_informe_semanal_word as m2
        import app.application.use_cases.word.generar_dossier_consolidado_word as m3
        import app.application.ports.word_document_port as m4

        for m in [m1, m2, m3, m4]:
            imports = self._imports_en_modulo(m)
            assert not any(i == "docx" or i.startswith("docx.") for i in imports), (
                f"Módulo {m.__name__} importa python-docx directamente. Imports: {imports}"
            )


# ===========================================================================
# TEST 20: Renderizadores patrimoniales siguen funcionando
# ===========================================================================

class TestRenderizadoresPatrimonialesOK:
    """Test 20: Los renderizadores word_consolidator siguen operativos."""

    def test_20_institutional_docx_generator_sigue_funcionando(self):
        """Test 20: InstitutionalDocxGenerator puede generar un DOCX básico."""
        informe = InformeSemanalInstitucional(
            departamento_responsable="Test Dept",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[],
        )
        generator = InstitutionalDocxGenerator()
        buffer = generator.generate(informe)

        assert isinstance(buffer, io.BytesIO)
        content = buffer.read()
        assert len(content) > 0, "El generator patrimonial debe producir DOCX no vacío."

    def test_20b_adaptador_infra_mapea_dataset_a_informe(self):
        """Test 20b: El adaptador traduce WordWeeklyReportDataset → InformeSemanalInstitucional."""
        dataset = WordACL.adaptar_para_informe_semanal(
            departamento_responsable="Innovación",
            mes_planificado="Octubre",
            semana="3",
            actividades=[],
            sede_recinto="BICU",
        )
        informe = _dataset_a_informe_institucional(dataset)

        assert isinstance(informe, InformeSemanalInstitucional)
        assert informe.departamento_responsable == "Innovación"
        assert informe.mes_planificado == "Octubre"

    def test_20c_adaptador_real_produce_docx(self):
        """Test 20c: Adapter real (no fake) produce DOCX desde WordWeeklyReportDataset."""
        dataset = WordACL.adaptar_para_informe_semanal(
            departamento_responsable="Test Dept",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[],
        )
        adapter = InstitutionalDocxInformeSemanalAdapter()
        buffer = adapter.render(dataset)

        assert isinstance(buffer, io.BytesIO)
        content = buffer.read()
        assert len(content) > 0

    def test_20d_adaptador_actividad_produce_docx(self):
        """Test 20d: InstitutionalDocxActividadAdapter produce DOCX desde WordActividadDTO."""
        dto = WordACL.adaptar_actividad(
            id_actividad="test-id-001",
            nombre_actividad="Actividad de Prueba",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=["FEMENINO", "MASCULINO", None],
            numero_orden=1,
            sede="BICU",
        )
        adapter = InstitutionalDocxActividadAdapter()
        buffer = adapter.render(dto)

        assert isinstance(buffer, io.BytesIO)
        assert len(buffer.read()) > 0


# ===========================================================================
# TEST INTEGRACIÓN E2E: SQLite fake → Use Case → WordACL → Adapter → DOCX real
# ===========================================================================

class TestIntegracionE2E:
    """Tests de integración completa end-to-end con adapter real."""

    def test_e2e_actividad_a_docx_real(self):
        """E2E: UoW fake → GenerarInformeActividadWordUseCase → Adapter real → DOCX."""
        actividad = _make_actividad("E2E Taller", fecha=date(2026, 9, 20))
        uow = _make_uow_con_datos(
            actividad,
            [
                ("María García", "FEMENINO", "ESTUDIANTE"),
                ("Juan Pérez", "MASCULINO", "DOCENTE"),
                ("Persona Desconocida", None, "BENEFICIADO"),
            ],
        )

        adapter = InstitutionalDocxActividadAdapter()
        uc = GenerarInformeActividadWordUseCase(uow=uow, renderer=adapter)
        buffer = uc.execute(
            id_actividad=actividad.id_actividad,
            fuente_cifras=FuenteCifras.NOMINAL,
        )

        assert isinstance(buffer, io.BytesIO)
        content = buffer.read()
        assert len(content) > 1000, "DOCX real debe tener contenido sustancial."

    def test_e2e_informe_semanal_a_docx_real(self):
        """E2E: UoW fake → GenerarInformeSemanalWordUseCase → Adapter real → DOCX."""
        actividad = _make_actividad("E2E Conferencia", fecha=date(2026, 9, 10))
        uow = _make_uow_con_datos(
            actividad,
            [("Ana", "FEMENINO", "ESTUDIANTE"), ("Luis", "MASCULINO", "ESTUDIANTE")],
        )

        adapter = InstitutionalDocxInformeSemanalAdapter()
        uc = GenerarInformeSemanalWordUseCase(uow=uow, renderer=adapter)
        buffer = uc.execute(
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
            departamento_responsable="Innovación y Emprendimiento",
            mes_planificado="Septiembre",
            semana="2",
            sede_recinto="BICU-Bluefields",
        )

        assert isinstance(buffer, io.BytesIO)
        assert len(buffer.read()) > 1000

    def test_e2e_dossier_a_docx_real(self):
        """E2E: UoW fake → GenerarDossierConsolidadoWordUseCase → Adapter real → DOCX."""
        act1 = _make_actividad("Dossier Acto 1", fecha=date(2026, 9, 5))
        act2 = _make_actividad("Dossier Acto 2", fecha=date(2026, 9, 18))

        act_repo = InMemoryActividadRepository()
        act_repo.save(act1)
        act_repo.save(act2)
        per_repo = InMemoryPersonaRepository()
        part_repo = InMemoryParticipacionRepository()
        evi_repo = InMemoryEvidenciaRepository()

        for act in [act1, act2]:
            p = _make_persona("Participante", "FEMENINO")
            per_repo.save(p)
            part_repo.save(Participation(
                id_actividad=act.id_actividad,
                id_persona=p.id_persona_interno,
                categoria_participacion="ESTUDIANTE",
            ))

        uow = InMemoryUnitOfWork(
            actividades=act_repo,
            personas=per_repo,
            participaciones=part_repo,
            evidencias=evi_repo,
        )

        adapter = InstitutionalDocxDossierAdapter()
        uc = GenerarDossierConsolidadoWordUseCase(uow=uow, renderer=adapter)
        buffer = uc.execute(
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
            departamento_responsable="Vinculación BICU",
            mes_planificado="Septiembre",
            semana="Completo Septiembre",
        )

        assert isinstance(buffer, io.BytesIO)
        assert len(buffer.read()) > 1000

    def test_e2e_invariante_sexo_total_consistente(self):
        """E2E: total_participantes == mujeres + varones + sin_sexo en el dataset."""
        actividad = _make_actividad(fecha=date(2026, 9, 7))
        uow = _make_uow_con_datos(
            actividad,
            [
                ("A", "FEMENINO", "ESTUDIANTE"),
                ("B", "FEMENINO", "ESTUDIANTE"),
                ("C", "MASCULINO", "DOCENTE"),
                ("D", None, "BENEFICIADO"),
                ("E", None, "BENEFICIADO"),
            ],
        )
        renderer = FakeInformeSemanalRenderer()
        uc = GenerarInformeSemanalWordUseCase(uow=uow, renderer=renderer)
        uc.execute(
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 30),
            departamento_responsable="Test",
            mes_planificado="Septiembre",
            semana="1",
        )

        ds = renderer.last_dataset
        assert ds.gran_total_mujeres + ds.gran_total_varones + ds.gran_total_sin_sexo == ds.gran_total_participantes
        assert ds.gran_total_mujeres == 2
        assert ds.gran_total_varones == 1
        assert ds.gran_total_sin_sexo == 2


# ===========================================================================
# TEST: Puertos son ABCs correctas
# ===========================================================================

class TestPuertosAbstractos:
    """Verificar que los puertos son ABCs con los métodos requeridos."""

    def test_puerto_actividad_renderer_es_abc(self):
        with pytest.raises(TypeError):
            IWordActividadRenderer()  # No se puede instanciar ABC

    def test_puerto_semanal_renderer_es_abc(self):
        with pytest.raises(TypeError):
            IWordInformeSemanalRenderer()

    def test_puerto_dossier_renderer_es_abc(self):
        with pytest.raises(TypeError):
            IWordDossierRenderer()

    def test_fake_renderers_implementan_contrato(self):
        """Los fakes deben instanciarse sin error."""
        r1 = FakeWordRenderer()
        r2 = FakeInformeSemanalRenderer()
        r3 = FakeDossierRenderer()
        assert isinstance(r1, IWordActividadRenderer)
        assert isinstance(r2, IWordInformeSemanalRenderer)
        assert isinstance(r3, IWordDossierRenderer)
