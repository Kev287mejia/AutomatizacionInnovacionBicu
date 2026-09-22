"""tests.test_review_application

Pruebas de la capa de aplicación para la Cola de Revisión (Fase 29.22.1).
Valida:
- Orquestación de casos de uso mediante ReviewQueueApplicationService.
- Validación determinista de estamentos del catálogo oficial BICU.
- Rechazo de estamentos arbitrarios o texto libre.
- Resolución de identidad (persona existente vs nueva cédula validada).
- Marcado de casos como NO_RESOLUBLE.
- Búsqueda de candidatos sugeridos (EVIDENCIA ≠ SUPOSICIÓN).
"""

from unittest.mock import MagicMock
import pytest

from app.review.application.dto import (
    CandidateMatchDTO,
    ReviewCaseDetailDTO,
    ReviewCaseSummaryDTO,
    ReviewHistoryItemDTO,
    ReviewResolutionResultDTO,
)
from app.review.application.ports import IReviewQueueRepository
from app.review.application.service import ReviewQueueApplicationService
from app.review.domain.enums import EstamentoInstitucional, ReviewDecisionType
from app.review.domain.exceptions import InvalidDecisionError, ReviewQueueDomainError


@pytest.fixture
def mock_repo():
    """Mock que implementa IReviewQueueRepository."""
    return MagicMock(spec=IReviewQueueRepository)


@pytest.fixture
def service(mock_repo):
    """Instancia del servicio de aplicación con mock inyectado."""
    return ReviewQueueApplicationService(mock_repo)


def test_listar_casos_pendientes(service, mock_repo):
    """El servicio delega al repositorio la lista de casos pendientes."""
    dummy_cases = [
        ReviewCaseSummaryDTO(
            id_caso="part-01",
            id_actividad="act-01",
            nombre_actividad="Taller Innovación",
            id_persona="per-01",
            nombre_persona="ANA LOPEZ",
            estamento_actual="DESCONOCIDO",
            tipo_caso="ESTAMENTO_NO_RESUELTO",
            motivo_revision="Estamento ambiguo",
            estado="PENDIENTE",
        )
    ]
    mock_repo.list_pending_cases.return_value = dummy_cases

    resultado = service.listar_casos_pendientes(id_actividad="act-01")
    assert len(resultado) == 1
    assert resultado[0].id_caso == "part-01"
    mock_repo.list_pending_cases.assert_called_once_with(id_actividad="act-01")


def test_obtener_detalle_caso_valido(service, mock_repo):
    """El servicio retorna el detalle completo del caso."""
    dummy_detail = ReviewCaseDetailDTO(
        id_caso="part-01",
        id_actividad="act-01",
        nombre_actividad="Taller Innovación",
        id_persona="per-01",
        nombre_persona="ANA LOPEZ",
        estamento_actual="DESCONOCIDO",
        tipo_caso="ESTAMENTO_NO_RESUELTO",
        motivo_revision="Estamento ambiguo",
        estado="PENDIENTE",
    )
    mock_repo.get_case_detail.return_value = dummy_detail

    resultado = service.obtener_detalle_caso("part-01")
    assert resultado is not None
    assert resultado.id_caso == "part-01"
    mock_repo.get_case_detail.assert_called_once_with("part-01")


def test_obtener_detalle_caso_sin_id_falla(service):
    """Consultar detalle sin ID debe lanzar ValueError."""
    with pytest.raises(ValueError):
        service.obtener_detalle_caso("")


def test_iniciar_revision(service, mock_repo):
    """Iniciar revisión asigna el usuario y transiciona el DTO a EN_REVISION."""
    dummy_detail = ReviewCaseDetailDTO(
        id_caso="part-01",
        id_actividad="act-01",
        nombre_actividad="Taller Innovación",
        id_persona="per-01",
        nombre_persona="ANA LOPEZ",
        estamento_actual="DESCONOCIDO",
        tipo_caso="ESTAMENTO_NO_RESUELTO",
        motivo_revision="Estamento ambiguo",
        estado="PENDIENTE",
    )
    mock_repo.get_case_detail.return_value = dummy_detail

    resultado = service.iniciar_revision("part-01", usuario="operador_bicu")
    assert resultado.estado == "EN_REVISION"
    assert resultado.usuario_resolutor == "operador_bicu"


def test_iniciar_revision_sin_usuario_falla(service):
    """Iniciar revisión sin usuario operador debe lanzar ValueError."""
    with pytest.raises(ValueError):
        service.iniciar_revision("part-01", usuario="")


def test_resolver_estamento_catalogo_oficial(service, mock_repo):
    """El servicio valida el estamento oficial y ejecuta la resolución atómica."""
    mock_repo.execute_atomic_resolution.return_value = ReviewResolutionResultDTO(
        id_caso="part-01",
        exito=True,
        mensaje="Caso procesado exitosamente como RESUELTO.",
        nuevo_estado="RESUELTO",
        matriz_destino="M2",
        id_auditoria="aud-123",
    )

    resultado = service.resolver_estamento(
        id_participacion="part-01",
        nuevo_estamento="ESTUDIANTE",
        justificacion="Acreditado con carné",
        usuario="operador_bicu",
    )

    assert resultado.exito is True
    assert resultado.matriz_destino == "M2"
    mock_repo.execute_atomic_resolution.assert_called_once()
    decision_arg = mock_repo.execute_atomic_resolution.call_args[1]["decision"]
    assert decision_arg.tipo_decision == ReviewDecisionType.CONFIRMAR_ESTAMENTO
    assert decision_arg.nuevo_estamento == EstamentoInstitucional.ESTUDIANTE


def test_resolver_estamento_invalido_falla(service):
    """Intentar resolver con un estamento fuera de catálogo debe ser rechazado."""
    with pytest.raises(InvalidDecisionError):
        service.resolver_estamento(
            id_participacion="part-01",
            nuevo_estamento="ESTUDIANTE?",
            justificacion="Prueba inválida",
            usuario="operador_bicu",
        )


def test_resolver_identidad_persona_existente(service, mock_repo):
    """Resolver identidad asociando a persona existente."""
    mock_repo.execute_atomic_resolution.return_value = ReviewResolutionResultDTO(
        id_caso="part-01",
        exito=True,
        mensaje="Identidad vinculada.",
        nuevo_estado="RESUELTO",
        id_auditoria="aud-456",
    )

    resultado = service.resolver_identidad(
        id_participacion="part-01",
        id_persona_existente="per-existente-01",
        justificacion="Coincidencia plena de nombres y carrera",
        usuario="operador_bicu",
    )

    assert resultado.exito is True
    mock_repo.execute_atomic_resolution.assert_called_once()
    decision = mock_repo.execute_atomic_resolution.call_args[1]["decision"]
    assert decision.id_persona_seleccionada == "per-existente-01"


def test_resolver_identidad_sin_datos_falla(service):
    """Intentar resolver identidad sin persona ni cédula debe lanzar InvalidDecisionError."""
    with pytest.raises(InvalidDecisionError):
        service.resolver_identidad(
            id_participacion="part-01",
            id_persona_existente=None,
            nueva_cedula=None,
            justificacion="Falta evidencia",
            usuario="operador_bicu",
        )


def test_marcar_no_resoluble(service, mock_repo):
    """Declarar caso como NO_RESOLUBLE."""
    mock_repo.execute_atomic_resolution.return_value = ReviewResolutionResultDTO(
        id_caso="part-01",
        exito=True,
        mensaje="Caso declarado NO_RESOLUBLE.",
        nuevo_estado="NO_RESOLUBLE",
        matriz_destino="COLA_REVISION",
        id_auditoria="aud-789",
    )

    resultado = service.marcar_no_resoluble(
        id_participacion="part-01",
        motivo="Sin respuesta del docente responsable",
        usuario="operador_bicu",
    )

    assert resultado.exito is True
    assert resultado.nuevo_estado == "NO_RESOLUBLE"


def test_buscar_candidatos_persona(service, mock_repo):
    """El servicio delega la búsqueda de candidatos potenciales."""
    candidatos_mock = [
        CandidateMatchDTO(
            id_persona="per-99",
            nombre_completo="ANA MARIA LOPEZ",
            cedula="601-111195-0001X",
            estamento_principal="ESTUDIANTE",
            confianza=0.85,
            criterio_coincidencia="Coincidencia parcial de nombres",
        )
    ]
    mock_repo.search_candidates.return_value = candidatos_mock

    resultado = service.buscar_candidatos_persona("ANA LOPEZ", excluir_id_persona="per-01")
    assert len(resultado) == 1
    assert resultado[0].id_persona == "per-99"
