"""tests.test_review_domain

Pruebas unitarias de dominio para la Cola de Revisión (Fase 29.22.1).
Valida:
- Ciclo de vida y transiciones estrictas (PENDIENTE -> EN_REVISION -> RESUELTO / NO_RESOLUBLE).
- Invariantes de estado y rechazo de transiciones prohibidas.
- Validación de decisiones periciales (justificación obligatoria, usuario obligatorio).
- Catálogo institucional cerrado y mapeo determinista a matrices M2..M5.
- Aislamiento absoluto e inviolabilidad de registros históricos de M5.
"""

import pytest

from app.review.domain.enums import (
    EstamentoInstitucional,
    ReviewCaseStatus,
    ReviewCaseType,
    ReviewDecisionType,
)
from app.review.domain.exceptions import (
    HistoricalDataProtectionError,
    InvalidDecisionError,
    InvalidStateTransitionError,
)
from app.review.domain.models import ReviewCase, ReviewDecision


def test_catalogo_estamentos_mapeo_oficial():
    """Valida que cada estamento del catálogo cerrado institucional mapea deterministamente a su matriz oficial."""
    assert EstamentoInstitucional.ESTUDIANTE.matriz_destino == "M2"
    assert EstamentoInstitucional.DOCENTE.matriz_destino == "M3"
    assert EstamentoInstitucional.ADMINISTRATIVO.matriz_destino == "M3"
    assert EstamentoInstitucional.COLABORADOR.matriz_destino == "M4"
    assert EstamentoInstitucional.BENEFICIADO.matriz_destino == "M5"


def test_creacion_caso_revision_valido():
    """Un caso válido inicia en estado PENDIENTE."""
    caso = ReviewCase(
        id_caso="part-001",
        id_actividad="act-100",
        id_persona="per-200",
        nombre_persona="JUAN PEREZ",
        estamento_actual="DESCONOCIDO",
        motivo_revision="Estamento no determinable",
        tipo_caso=ReviewCaseType.ESTAMENTO_NO_RESUELTO,
    )
    assert caso.estado == ReviewCaseStatus.PENDIENTE
    assert caso.usuario_resolutor is None
    assert caso.es_historico_preexistente is False


def test_iniciar_revision_transicion_valida():
    """Transición autorizada: PENDIENTE -> EN_REVISION."""
    caso = ReviewCase(
        id_caso="part-001",
        id_actividad="act-100",
        id_persona="per-200",
        nombre_persona="JUAN PEREZ",
        estamento_actual="DESCONOCIDO",
        motivo_revision="Estamento no determinable",
        tipo_caso=ReviewCaseType.ESTAMENTO_NO_RESUELTO,
    )
    caso.iniciar_revision(usuario="operador_bicu")
    assert caso.estado == ReviewCaseStatus.EN_REVISION
    assert caso.usuario_resolutor == "operador_bicu"


def test_iniciar_revision_sin_usuario_falla():
    """Iniciar revisión sin usuario operador debe ser rechazado."""
    caso = ReviewCase(
        id_caso="part-001",
        id_actividad="act-100",
        id_persona="per-200",
        nombre_persona="JUAN PEREZ",
        estamento_actual="DESCONOCIDO",
        motivo_revision="Estamento no determinable",
        tipo_caso=ReviewCaseType.ESTAMENTO_NO_RESUELTO,
    )
    with pytest.raises(InvalidStateTransitionError):
        caso.iniciar_revision(usuario="")


def test_resolver_directo_desde_pendiente_falla():
    """No se puede resolver un caso que no ha pasado a EN_REVISION."""
    caso = ReviewCase(
        id_caso="part-001",
        id_actividad="act-100",
        id_persona="per-200",
        nombre_persona="JUAN PEREZ",
        estamento_actual="DESCONOCIDO",
        motivo_revision="Estamento no determinable",
        tipo_caso=ReviewCaseType.ESTAMENTO_NO_RESUELTO,
    )
    decision = ReviewDecision(
        tipo_decision=ReviewDecisionType.CONFIRMAR_ESTAMENTO,
        nuevo_estamento=EstamentoInstitucional.ESTUDIANTE,
        justificacion="Acreditado con carné",
        usuario_operador="operador_bicu",
        fecha_resolucion="2026-09-22T10:00:00",
    )
    with pytest.raises(InvalidStateTransitionError):
        caso.resolver(decision)


def test_resolver_caso_desde_en_revision_exitoso():
    """Transición autorizada: EN_REVISION -> RESUELTO."""
    caso = ReviewCase(
        id_caso="part-001",
        id_actividad="act-100",
        id_persona="per-200",
        nombre_persona="JUAN PEREZ",
        estamento_actual="DESCONOCIDO",
        motivo_revision="Estamento no determinable",
        tipo_caso=ReviewCaseType.ESTAMENTO_NO_RESUELTO,
    )
    caso.iniciar_revision(usuario="operador_bicu")

    decision = ReviewDecision(
        tipo_decision=ReviewDecisionType.CONFIRMAR_ESTAMENTO,
        nuevo_estamento=EstamentoInstitucional.ESTUDIANTE,
        justificacion="Acreditado con carné estudiantil",
        usuario_operador="operador_bicu",
        fecha_resolucion="2026-09-22T10:05:00",
    )
    caso.resolver(decision)

    assert caso.estado == ReviewCaseStatus.RESUELTO
    assert caso.usuario_resolutor == "operador_bicu"
    assert caso.fecha_resolucion == "2026-09-22T10:05:00"
    assert caso.observaciones == "Acreditado con carné estudiantil"


def test_marcar_no_resoluble_desde_en_revision():
    """Transición autorizada: EN_REVISION -> NO_RESOLUBLE."""
    caso = ReviewCase(
        id_caso="part-001",
        id_actividad="act-100",
        id_persona="per-200",
        nombre_persona="JUAN PEREZ",
        estamento_actual="DESCONOCIDO",
        motivo_revision="Estamento no determinable",
        tipo_caso=ReviewCaseType.ESTAMENTO_NO_RESUELTO,
    )
    caso.iniciar_revision(usuario="operador_bicu")
    caso.marcar_no_resoluble(
        justificacion="Imposible verificar con el docente organizador",
        usuario="operador_bicu",
        fecha="2026-09-22T10:10:00",
    )

    assert caso.estado == ReviewCaseStatus.NO_RESOLUBLE
    assert caso.observaciones == "Imposible verificar con el docente organizador"


def test_decision_sin_justificacion_falla():
    """Una decisión sin justificación explícita debe ser rechazada."""
    with pytest.raises(InvalidDecisionError):
        ReviewDecision(
            tipo_decision=ReviewDecisionType.CONFIRMAR_ESTAMENTO,
            nuevo_estamento=EstamentoInstitucional.DOCENTE,
            justificacion="",
            usuario_operador="operador_bicu",
            fecha_resolucion="2026-09-22T10:00:00",
        )


def test_decision_estamento_sin_estamento_falla():
    """CONFIRMAR_ESTAMENTO requiere un estamento institucional explícito."""
    with pytest.raises(InvalidDecisionError):
        ReviewDecision(
            tipo_decision=ReviewDecisionType.CONFIRMAR_ESTAMENTO,
            nuevo_estamento=None,
            justificacion="Justificación válida",
            usuario_operador="operador_bicu",
            fecha_resolucion="2026-09-22T10:00:00",
        )


def test_proteccion_m5_historico():
    """Invariante INV-03: Crear un caso con es_historico_preexistente=True debe lanzar excepción inmediata."""
    with pytest.raises(HistoricalDataProtectionError):
        ReviewCase(
            id_caso="part-hist-001",
            id_actividad="act-hist",
            id_persona="per-hist",
            nombre_persona="HISTORICO PREEXISTENTE",
            estamento_actual="BENEFICIADO",
            motivo_revision="Ninguno",
            tipo_caso=ReviewCaseType.DATOS_INCONSISTENTES,
            es_historico_preexistente=True,
        )
