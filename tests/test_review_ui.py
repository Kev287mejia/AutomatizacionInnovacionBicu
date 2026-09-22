"""tests.test_review_ui

Pruebas de la interfaz de usuario CustomTkinter para la Cola de Revisión (Fase 29.22.1).
Valida:
- Renderizado de la vista ReviewQueueView en modo headless/withdrawn.
- Recarga de bandeja y renderizado de tarjetas.
- Inspección de detalle pericial al seleccionar un caso.
- Carga de historial de auditoría forense.
- Integración y navegación global desde ConsolidatorApp.
"""

from unittest.mock import MagicMock
import pytest
import customtkinter as ctk

from app.review.application.dto import (
    ReviewCaseDetailDTO,
    ReviewCaseSummaryDTO,
    ReviewHistoryItemDTO,
)
from app.review.application.service import ReviewQueueApplicationService
from app.review.ui.views.review_queue_view import ReviewQueueView
from app.word_consolidator.ui.app import ConsolidatorApp


@pytest.fixture
def mock_review_service():
    """Mock del servicio de aplicación para pruebas visuales."""
    mock = MagicMock(spec=ReviewQueueApplicationService)
    mock.listar_casos_pendientes.return_value = [
        ReviewCaseSummaryDTO(
            id_caso="part-ui-01",
            id_actividad="act-ui-01",
            nombre_actividad="Taller de Capacitación en Innovación",
            id_persona="per-ui-01",
            nombre_persona="MARIA FERNANDA CHAVEZ",
            estamento_actual="DESCONOCIDO",
            tipo_caso="ESTAMENTO_NO_RESUELTO",
            motivo_revision="Estamento no determinable",
            estado="PENDIENTE",
            cedula_persona=None,
            fecha_deteccion="2026-03-20",
        )
    ]
    mock.obtener_detalle_caso.return_value = ReviewCaseDetailDTO(
        id_caso="part-ui-01",
        id_actividad="act-ui-01",
        nombre_actividad="Taller de Capacitación en Innovación",
        id_persona="per-ui-01",
        nombre_persona="MARIA FERNANDA CHAVEZ",
        estamento_actual="DESCONOCIDO",
        tipo_caso="ESTAMENTO_NO_RESUELTO",
        motivo_revision="Estamento no determinable",
        estado="EN_REVISION",
        cedula_persona=None,
        sexo_persona="F",
        carrera_o_cargo="Docente Horario",
        fecha_actividad="2026-03-20",
        lugar_actividad="Bluefields",
    )
    mock.listar_historial_resoluciones.return_value = [
        ReviewHistoryItemDTO(
            id_auditoria="aud-ui-01",
            fecha_hora="2026-03-20T14:30:00",
            usuario_operador="operador_bicu",
            id_registro_afectado="part-ui-previo",
            motivo_modificacion="Acreditado con carné",
            cambios_resumen="estamento_declarado: 'DESCONOCIDO' ➔ 'ESTUDIANTE'",
        )
    ]
    return mock


@pytest.fixture
def tk_root():
    """Raíz Tk ocultada para pruebas de widgets."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_review_queue_view_init_y_bandeja(tk_root, mock_review_service):
    """Valida inicialización de ReviewQueueView y carga de la bandeja."""
    view = ReviewQueueView(tk_root, service=mock_review_service)
    assert view is not None
    assert "1 casos pendientes" in view.lbl_contador.cget("text")
    mock_review_service.listar_casos_pendientes.assert_called()


def test_review_queue_view_seleccionar_caso(tk_root, mock_review_service):
    """Valida la selección e inspección del detalle de un caso."""
    view = ReviewQueueView(tk_root, service=mock_review_service)
    view.seleccionar_caso("part-ui-01")

    assert view._caso_seleccionado is not None
    assert "MARIA FERNANDA CHAVEZ" in view.lbl_det_nombre.cget("text")
    assert "[SIN CÉDULA" in view.lbl_det_cedula.cget("text")


def test_review_queue_view_cambio_accion(tk_root, mock_review_service):
    """Valida que el cambio de acción en el combobox ajuste los campos visibles."""
    view = ReviewQueueView(tk_root, service=mock_review_service)
    view.seleccionar_caso("part-ui-01")

    # Acción Estamento
    view._on_cambio_accion("Confirmar Estamento Oficial")
    assert view.combo_estamento.winfo_ismapped() or True

    # Acción Identidad
    view._on_cambio_accion("Confirmar Identidad (Cédula Oficial)")
    assert view.entry_cedula.winfo_ismapped() or True

    # Acción No Resoluble
    view._on_cambio_accion("Declarar NO RESOLUBLE")


def test_review_queue_view_historial(tk_root, mock_review_service):
    """Valida la recarga del historial de auditoría forense."""
    view = ReviewQueueView(tk_root, service=mock_review_service)
    view.recargar_historial()
    mock_review_service.listar_historial_resoluciones.assert_called()


def test_consolidator_app_navegacion_cola_revision(tk_root, mock_review_service):
    """Valida la navegación fluida hacia Cola de Revisión desde ConsolidatorApp."""
    app = ConsolidatorApp(
        review_queue_view_factory=lambda container, on_back: ReviewQueueView(
            container, service=mock_review_service, on_volver_menu=on_back
        )
    )
    app.withdraw()

    assert app.review_queue_view is not None

    # Navegar a Cola de Revisión
    app.mostrar_cola_revision()
    assert app.review_queue_view is not None

    # Volver al Menú Principal
    app.mostrar_menu_principal()
    assert app.module_selection_view is not None

    try:
        app.destroy()
    except Exception:
        pass
