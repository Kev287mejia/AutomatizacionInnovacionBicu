"""
tests.test_word_consolidator.test_fase_16_7_d

Suite de Pruebas Oficiales para la Fase 16.7-D:
1. Verificación de estados independientes de Producto A y B (SUCCESS, FAILED, NOT_REQUESTED).
2. Botones de apertura granulares e independientes (_on_abrir_tecnico, _on_abrir_institucional).
3. Aislamiento estricto de apertura (cada botón abre únicamente su respectivo documento).
4. Validación defensiva contra rutas vacías, inexistentes o directorios.
5. Retroalimentación visual al usuario en casos de error o archivo no disponible.
6. Validación formal estricta de estados en PipelineExecutionResult.
7. Cumplimiento exhaustivo de la matriz de comportamiento operacional.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import customtkinter as ctk
import pytest

from app.word_consolidator.pipeline import PipelineExecutionResult
from app.word_consolidator.ui.views.result_view import (
    ResultView,
    _abrir_archivo_so,
)


# app_root se hereda con scope='session' desde tests/conftest.py


class TestFase167DResultViewGranular:
    """Pruebas funcionales de apertura granular y estados independientes de ResultView."""

    def test_01_success_success_ambos_habilitados(self, app_root, tmp_path):
        """
        Test 1: SUCCESS + SUCCESS -> Ambos botones habilitados con estado normal,
        etiquetas mostrando '✓ GENERADO' y nombres de archivo.
        """
        p_tec = tmp_path / "Informe_Tecnico.docx"
        p_tec.write_bytes(b"PK01_TECNICO")
        p_inst = tmp_path / "Informe_Institucional.docx"
        p_inst.write_bytes(b"PK02_INSTITUCIONAL")

        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx=str(p_tec),
            tamanio_docx_bytes=len(b"PK01_TECNICO"),
            status_tecnico="SUCCESS",
            ruta_docx_institucional=str(p_inst),
            tamanio_docx_institucional_bytes=len(b"PK02_INSTITUCIONAL"),
            status_institucional="SUCCESS",
        )

        view = ResultView(app_root)
        view.mostrar_resultado(res)

        assert view.btn_abrir_tecnico.cget("state") == "normal"
        assert view.btn_abrir_institucional.cget("state") == "normal"
        assert "✓ GENERADO" in view.lbl_status_tecnico.cget("text")
        assert "✓ GENERADO" in view.lbl_status_institucional.cget("text")
        assert "Informe_Tecnico.docx" in view.lbl_detalles_tecnico.cget("text")
        assert "Informe_Institucional.docx" in view.lbl_detalles_institucional.cget("text")

    def test_02_success_failed_solo_tecnico_habilitado(self, app_root, tmp_path):
        """
        Test 2: SUCCESS + FAILED -> Botón A habilitado, botón B deshabilitado.
        Producto B muestra '✗ ERROR EN GENERACIÓN'.
        """
        p_tec = tmp_path / "Informe_Tecnico.docx"
        p_tec.write_bytes(b"PK01_TECNICO")

        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="PARTIAL_OUTPUT",
            ruta_docx=str(p_tec),
            tamanio_docx_bytes=len(b"PK01_TECNICO"),
            status_tecnico="SUCCESS",
            ruta_docx_institucional=None,
            status_institucional="FAILED",
            error_institucional="Fallo de renderizado institucional",
        )

        view = ResultView(app_root)
        view.mostrar_resultado(res)

        assert view.btn_abrir_tecnico.cget("state") == "normal"
        assert view.btn_abrir_institucional.cget("state") == "disabled"
        assert "✓ GENERADO" in view.lbl_status_tecnico.cget("text")
        assert "✗ ERROR EN GENERACIÓN" in view.lbl_status_institucional.cget("text")
        assert "Fallo de renderizado institucional" in view.lbl_detalles_institucional.cget("text")

    def test_03_failed_success_solo_institucional_habilitado(self, app_root, tmp_path):
        """
        Test 3: FAILED + SUCCESS -> Botón A deshabilitado, botón B habilitado.
        Producto A muestra '✗ ERROR EN GENERACIÓN'.
        """
        p_inst = tmp_path / "Informe_Institucional.docx"
        p_inst.write_bytes(b"PK02_INSTITUCIONAL")

        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="PARTIAL_OUTPUT",
            ruta_docx=None,
            status_tecnico="FAILED",
            error_tecnico="Error transformando tabla técnica",
            ruta_docx_institucional=str(p_inst),
            tamanio_docx_institucional_bytes=len(b"PK02_INSTITUCIONAL"),
            status_institucional="SUCCESS",
        )

        view = ResultView(app_root)
        view.mostrar_resultado(res)

        assert view.btn_abrir_tecnico.cget("state") == "disabled"
        assert view.btn_abrir_institucional.cget("state") == "normal"
        assert "✗ ERROR EN GENERACIÓN" in view.lbl_status_tecnico.cget("text")
        assert "Error transformando tabla técnica" in view.lbl_detalles_tecnico.cget("text")
        assert "✓ GENERADO" in view.lbl_status_institucional.cget("text")

    def test_04_success_not_requested_b_no_muestra_fallo(self, app_root, tmp_path):
        """
        Test 4 (CRÍTICO): SUCCESS + NOT_REQUESTED -> B debe mostrar 'NO SOLICITADO',
        NUNCA 'FALLO EN GENERACIÓN'. Botón B deshabilitado.
        """
        p_tec = tmp_path / "Informe_Tecnico.docx"
        p_tec.write_bytes(b"PK01_TECNICO")

        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx=str(p_tec),
            tamanio_docx_bytes=len(b"PK01_TECNICO"),
            status_tecnico="SUCCESS",
            ruta_docx_institucional=None,
            status_institucional="NOT_REQUESTED",
        )

        view = ResultView(app_root)
        view.mostrar_resultado(res)

        assert view.btn_abrir_tecnico.cget("state") == "normal"
        assert view.btn_abrir_institucional.cget("state") == "disabled"
        assert "✓ GENERADO" in view.lbl_status_tecnico.cget("text")
        assert "NO SOLICITADO" in view.lbl_status_institucional.cget("text")
        assert "FALLO" not in view.lbl_status_institucional.cget("text")
        assert "No se solicitó la generación" in view.lbl_detalles_institucional.cget("text")

    def test_05_not_requested_success_a_no_muestra_fallo(self, app_root, tmp_path):
        """
        Test 5 (CRÍTICO): NOT_REQUESTED + SUCCESS -> A debe mostrar 'NO SOLICITADO',
        NUNCA 'FALLO EN GENERACIÓN'. Botón A deshabilitado.
        """
        p_inst = tmp_path / "Informe_Institucional.docx"
        p_inst.write_bytes(b"PK02_INSTITUCIONAL")

        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx=None,
            status_tecnico="NOT_REQUESTED",
            ruta_docx_institucional=str(p_inst),
            tamanio_docx_institucional_bytes=len(b"PK02_INSTITUCIONAL"),
            status_institucional="SUCCESS",
        )

        view = ResultView(app_root)
        view.mostrar_resultado(res)

        assert view.btn_abrir_tecnico.cget("state") == "disabled"
        assert view.btn_abrir_institucional.cget("state") == "normal"
        assert "NO SOLICITADO" in view.lbl_status_tecnico.cget("text")
        assert "FALLO" not in view.lbl_status_tecnico.cget("text")
        assert "No se solicitó la generación" in view.lbl_detalles_tecnico.cget("text")

    def test_06_apertura_exclusiva_tecnico(self, app_root, tmp_path):
        """
        Test 6: Al invocar _on_abrir_tecnico(), se abre exclusivamente ruta_docx
        y NUNCA ruta_docx_institucional.
        """
        p_tec = tmp_path / "Informe_Tecnico.docx"
        p_tec.write_bytes(b"PK01_TECNICO")
        p_inst = tmp_path / "Informe_Institucional.docx"
        p_inst.write_bytes(b"PK02_INSTITUCIONAL")

        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx=str(p_tec),
            status_tecnico="SUCCESS",
            ruta_docx_institucional=str(p_inst),
            status_institucional="SUCCESS",
        )

        view = ResultView(app_root)
        view.mostrar_resultado(res)

        with patch("app.word_consolidator.ui.views.result_view._abrir_archivo_so", return_value=True) as mock_open:
            view._on_abrir_tecnico()
            mock_open.assert_called_once_with(Path(res.ruta_docx))
            assert mock_open.call_args[0][0] != Path(res.ruta_docx_institucional)

    def test_07_apertura_exclusiva_institucional(self, app_root, tmp_path):
        """
        Test 7: Al invocar _on_abrir_institucional(), se abre exclusivamente ruta_docx_institucional
        y NUNCA ruta_docx.
        """
        p_tec = tmp_path / "Informe_Tecnico.docx"
        p_tec.write_bytes(b"PK01_TECNICO")
        p_inst = tmp_path / "Informe_Institucional.docx"
        p_inst.write_bytes(b"PK02_INSTITUCIONAL")

        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx=str(p_tec),
            status_tecnico="SUCCESS",
            ruta_docx_institucional=str(p_inst),
            status_institucional="SUCCESS",
        )

        view = ResultView(app_root)
        view.mostrar_resultado(res)

        with patch("app.word_consolidator.ui.views.result_view._abrir_archivo_so", return_value=True) as mock_open:
            view._on_abrir_institucional()
            mock_open.assert_called_once_with(Path(res.ruta_docx_institucional))
            assert mock_open.call_args[0][0] != Path(res.ruta_docx)

    def test_08_ruta_vacia_rechazada_sin_abrir(self, app_root):
        """
        Test 8: Ruta vacía o en blanco -> No se ejecuta apertura y se muestra aviso.
        """
        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx="",
            status_tecnico="SUCCESS",
        )

        view = ResultView(app_root)
        view.resultado_actual = res

        with patch("app.word_consolidator.ui.views.result_view._abrir_archivo_so") as mock_open, \
             patch("app.word_consolidator.ui.views.result_view.messagebox.showwarning") as mock_warn:
            view._on_abrir_tecnico()
            mock_open.assert_not_called()
            mock_warn.assert_called_once_with(
                "Archivo No Disponible",
                "El informe solicitado no se encuentra disponible en disco.",
            )

    def test_09_ruta_inexistente_rechazada(self, app_root, tmp_path):
        """
        Test 9: Ruta que no existe físicamente en disco -> No se abre y se muestra aviso.
        """
        p_fantasma = tmp_path / "no_existe.docx"
        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx=str(p_fantasma),
            status_tecnico="SUCCESS",
        )

        view = ResultView(app_root)
        view.resultado_actual = res

        with patch("app.word_consolidator.ui.views.result_view._abrir_archivo_so") as mock_open, \
             patch("app.word_consolidator.ui.views.result_view.messagebox.showwarning") as mock_warn:
            view._on_abrir_tecnico()
            mock_open.assert_not_called()
            mock_warn.assert_called_once_with(
                "Archivo No Disponible",
                "El informe solicitado no se encuentra disponible en disco.",
            )

    def test_10_ruta_directorio_rechazada(self, app_root, tmp_path):
        """
        Test 10: Ruta que apunta a un directorio en lugar de un archivo -> Rechazada.
        """
        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx=str(tmp_path),
            status_tecnico="SUCCESS",
        )

        view = ResultView(app_root)
        view.resultado_actual = res

        with patch("app.word_consolidator.ui.views.result_view._abrir_archivo_so") as mock_open, \
             patch("app.word_consolidator.ui.views.result_view.messagebox.showwarning") as mock_warn:
            view._on_abrir_tecnico()
            mock_open.assert_not_called()
            mock_warn.assert_called_once_with(
                "Archivo No Disponible",
                "El informe solicitado no se encuentra disponible en disco.",
            )

    def test_11_fallo_apertura_so_muestra_error(self, app_root, tmp_path):
        """
        Test 11: Si _abrir_archivo_so retorna False, se muestra mensaje de error al usuario.
        """
        p_tec = tmp_path / "Informe_Tecnico.docx"
        p_tec.write_bytes(b"PK01_TECNICO")

        res = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO_CONCORDANTE",
            ruta_docx=str(p_tec),
            status_tecnico="SUCCESS",
        )

        view = ResultView(app_root)
        view.mostrar_resultado(res)

        with patch("app.word_consolidator.ui.views.result_view._abrir_archivo_so", return_value=False), \
             patch("app.word_consolidator.ui.views.result_view.messagebox.showerror") as mock_err:
            view._on_abrir_tecnico()
            mock_err.assert_called_once_with(
                "Error al Abrir Documento",
                "No fue posible abrir el informe con la aplicación predeterminada.",
            )

    def test_12_abrir_archivo_so_validaciones_defensivas(self, tmp_path):
        """
        Test 12: Comprobación unitaria de la función _abrir_archivo_so ante entradas anómalas.
        """
        assert _abrir_archivo_so("") is False
        assert _abrir_archivo_so("   ") is False
        assert _abrir_archivo_so(None) is False
        assert _abrir_archivo_so(tmp_path) is False  # Es un directorio
        assert _abrir_archivo_so(tmp_path / "archivo_inexistente.docx") is False

    def test_13_validacion_estricta_estados_pipeline_execution_result(self):
        """
        Test 13: PipelineExecutionResult valida estrictamente que solo se admitan
        SUCCESS, FAILED y NOT_REQUESTED, rechazando estados inválidos con ValueError.
        """
        # Estados válidos permitidos
        res_ok = PipelineExecutionResult(
            periodo="Septiembre 2026",
            tipo_periodo="MES",
            estado_final="EXITOSO",
            status_tecnico="SUCCESS",
            status_institucional="NOT_REQUESTED",
        )
        assert res_ok.status_tecnico == "SUCCESS"
        assert res_ok.status_institucional == "NOT_REQUESTED"

        # Rechazo de estado arbitrario en status_tecnico
        with pytest.raises(ValueError) as excinfo_tec:
            PipelineExecutionResult(
                periodo="Septiembre 2026",
                tipo_periodo="MES",
                estado_final="EXITOSO",
                status_tecnico="INVALID_STATUS",
            )
        assert "Estado de producto no válido" in str(excinfo_tec.value)

        # Rechazo de estado arbitrario en status_institucional
        with pytest.raises(ValueError) as excinfo_inst:
            PipelineExecutionResult(
                periodo="Septiembre 2026",
                tipo_periodo="MES",
                estado_final="EXITOSO",
                status_institucional="UNKNOWN",
            )
        assert "Estado de producto no válido" in str(excinfo_inst.value)

    def test_14_matriz_operacional_8_combinaciones(self, app_root, tmp_path):
        """
        Test 14: Verificación exhaustiva de las 8 combinaciones de la matriz de comportamiento.
        """
        p_tec = tmp_path / "M_Tec.docx"
        p_tec.write_bytes(b"TEC")
        p_inst = tmp_path / "M_Inst.docx"
        p_inst.write_bytes(b"INST")

        casos = [
            # (status_a, ruta_a, status_b, ruta_b, esperado_btn_a, esperado_btn_b)
            ("SUCCESS", str(p_tec), "SUCCESS", str(p_inst), "normal", "normal"),
            ("SUCCESS", str(p_tec), "FAILED", None, "normal", "disabled"),
            ("FAILED", None, "SUCCESS", str(p_inst), "disabled", "normal"),
            ("SUCCESS", str(p_tec), "NOT_REQUESTED", None, "normal", "disabled"),
            ("NOT_REQUESTED", None, "SUCCESS", str(p_inst), "disabled", "normal"),
            ("FAILED", None, "NOT_REQUESTED", None, "disabled", "disabled"),
            ("NOT_REQUESTED", None, "FAILED", None, "disabled", "disabled"),
            ("NOT_REQUESTED", None, "NOT_REQUESTED", None, "disabled", "disabled"),
        ]

        view = ResultView(app_root)

        for st_a, r_a, st_b, r_b, exp_a, exp_b in casos:
            res = PipelineExecutionResult(
                periodo="Septiembre 2026",
                tipo_periodo="MES",
                estado_final="PRUEBA_MATRIZ",
                ruta_docx=r_a,
                status_tecnico=st_a,
                ruta_docx_institucional=r_b,
                status_institucional=st_b,
            )
            view.mostrar_resultado(res)
            assert view.btn_abrir_tecnico.cget("state") == exp_a, f"Fallo en combinación A={st_a}, B={st_b} para botón A"
            assert view.btn_abrir_institucional.cget("state") == exp_b, f"Fallo en combinación A={st_a}, B={st_b} para botón B"
