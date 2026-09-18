"""
tests.test_word_consolidator.test_fase_16_7_b

Suite de Pruebas Oficiales para la Fase 16.7-B:
1. Validación Preflight reactiva respecto a la selección de productos (Técnico / Institucional).
2. Defensa en profundidad: bloqueo estricto antes de iniciar lectura o consolidación si ambos productos son False.
3. Verificación obligatoria de no-ejecución de ConsolidationEngine.consolidar mediante mock.
4. Manejo humanizado de PermissionError para archivos bloqueados por Word vs permisos insuficientes de directorio.
5. Reactividad de checkboxes en ValidationView.
6. Preservación de modos de generación: Solo Técnico, Solo Institucional y Ambos.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import customtkinter as ctk
import pytest

from app.word_consolidator.engine.consolidation_engine import ConsolidationEngine
from app.word_consolidator.models import PeriodoConsolidacion, TipoPeriodo
from app.word_consolidator.pipeline import WordConsolidationPipeline
from app.word_consolidator.readers.matrix_reader import MatrixReader
from app.word_consolidator.ui.services.application_service import (
    ConsolidationAppService,
    PreflightStatus,
)
from app.word_consolidator.ui.services.error_translator import (
    ErrorInstitucionalInfo,
    ErrorTranslator,
)
from app.word_consolidator.ui.views.validation_view import ValidationView

OUTPUT_DIR = Path("output")


class DummyWidget:
    """Widget simulado para probar lógica de vistas sin inicializar ventanas nativas."""
    def __init__(self, **kwargs):
        self._props = kwargs

    def configure(self, **kwargs):
        self._props.update(kwargs)

    def cget(self, key):
        return self._props.get(key)

    def pack(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):
        pass


class DummyVar:
    """Variable reactiva simulada con interfaz get/set idéntica a tk.BooleanVar."""
    def __init__(self, value=True):
        self._val = value

    def get(self):
        return self._val

    def set(self, val):
        self._val = val


@pytest.fixture
def rutas_oficiales():
    return {
        "M1": OUTPUT_DIR / "Matriz_1_Consolidado_Actividades.xlsx",
        "M2": OUTPUT_DIR / "Matriz_2_Estudiantes.xlsx",
        "M3": OUTPUT_DIR / "Matriz_3_Academicos_Administrativos.xlsx",
        "M4": OUTPUT_DIR / "Matriz_4_Colaboradores.xlsx",
        "M5": OUTPUT_DIR / "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }


@pytest.fixture
def periodo_septiembre():
    return ConsolidationAppService.construir_periodo(
        tipo=TipoPeriodo.SEMANA,
        anio=2026,
        mes=9,
        semana=1,
    )


class TestFase167BPreflightYDefensaEnProfundidad:
    """Pruebas para preflight, reactividad y defensa en profundidad (Fase 16.7-B)."""

    def test_01_preflight_rechaza_ambos_productos_false(self, rutas_oficiales, periodo_septiembre, tmp_path):
        """
        Test 1: Ambos productos False -> preflight bloqueado, listo_para_procesar=False,
        y mensaje de error bloqueante indicando seleccionar al menos un informe.
        """
        status: PreflightStatus = ConsolidationAppService.validar_preflight(
            matrices=rutas_oficiales,
            periodo=periodo_septiembre,
            carpeta_salida=tmp_path,
            generar_tecnico=False,
            generar_institucional=False,
        )

        assert status.listo_para_procesar is False
        assert status.productos_seleccionados is False
        assert status.matrices_completas is True
        assert status.periodo_valido is True
        assert status.carpeta_salida_valida is True
        assert any(
            "Seleccione al menos un informe para generar" in err
            for err in status.errores_bloqueantes
        )

    def test_02_preflight_permite_solo_tecnico(self, rutas_oficiales, periodo_septiembre, tmp_path):
        """
        Test 2: Técnico=True, Institucional=False -> preflight listo_para_procesar=True.
        """
        status: PreflightStatus = ConsolidationAppService.validar_preflight(
            matrices=rutas_oficiales,
            periodo=periodo_septiembre,
            carpeta_salida=tmp_path,
            generar_tecnico=True,
            generar_institucional=False,
        )

        assert status.listo_para_procesar is True
        assert status.productos_seleccionados is True
        assert len(status.errores_bloqueantes) == 0

    def test_03_preflight_permite_solo_institucional(self, rutas_oficiales, periodo_septiembre, tmp_path):
        """
        Test 3: Técnico=False, Institucional=True -> preflight listo_para_procesar=True.
        """
        status: PreflightStatus = ConsolidationAppService.validar_preflight(
            matrices=rutas_oficiales,
            periodo=periodo_septiembre,
            carpeta_salida=tmp_path,
            generar_tecnico=False,
            generar_institucional=True,
        )

        assert status.listo_para_procesar is True
        assert status.productos_seleccionados is True
        assert len(status.errores_bloqueantes) == 0

    def test_04_defensa_en_profundidad_consolidation_engine_no_se_ejecuta(
        self, rutas_oficiales, periodo_septiembre, tmp_path
    ):
        """
        Test 4 (CRÍTICO): Demostrar que con ambos productos desactivados,
        la ejecución es rechazada con ValueError ANTES de leer matrices o consolidar,
        garantizando que ConsolidationEngine.consolidar NUNCA es invocado.
        """
        pipeline = WordConsolidationPipeline(output_dir=tmp_path)

        with patch.object(ConsolidationEngine, "consolidar") as mock_consolidar, \
             patch.object(MatrixReader, "leer_conjunto_matrices") as mock_lector:

            # 1. Validación en pipeline.ejecutar
            with pytest.raises(ValueError) as excinfo_pipeline:
                pipeline.ejecutar(
                    fuentes=rutas_oficiales,
                    periodo=periodo_septiembre,
                    salida_dir=tmp_path,
                    generar_tecnico=False,
                    generar_institucional=False,
                )

            assert "debe seleccionar al menos un producto a generar" in str(excinfo_pipeline.value)
            mock_consolidar.assert_not_called()
            mock_lector.assert_not_called()

            # 2. Validación en ConsolidationAppService.ejecutar_consolidacion
            with pytest.raises(ValueError) as excinfo_service:
                ConsolidationAppService.ejecutar_consolidacion(
                    fuentes=rutas_oficiales,
                    periodo=periodo_septiembre,
                    salida_dir=tmp_path,
                    generar_tecnico=False,
                    generar_institucional=False,
                )

            assert "debe seleccionar al menos un producto a generar" in str(excinfo_service.value)
            mock_consolidar.assert_not_called()
            mock_lector.assert_not_called()


class TestFase167BErrorHumanizadoPermissionError:
    """Pruebas para el manejo humanizado y discriminado de PermissionError."""

    def test_05a_permission_error_archivo_bloqueado_word(self):
        """
        Test 5a: Archivo bloqueado en Windows (WinError 32 / .docx).
        Debe orientar al usuario a cerrar Microsoft Word, incluir el nombre del archivo si existe,
        evitar traceback o códigos técnicos en el mensaje principal y preservar detalle técnico.
        """
        ex = PermissionError(
            13,
            "[WinError 32] El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso: 'Informe_Semanal_Septiembre_2026.docx'",
            "C:\\output\\Informe_Semanal_Septiembre_2026.docx",
        )

        info: ErrorInstitucionalInfo = ErrorTranslator.traducir(ex)

        assert isinstance(info, ErrorInstitucionalInfo)
        assert info.titulo == "Archivo Bloqueado por Microsoft Word u Otro Programa"
        assert info.es_bloqueante is True

        # Mensaje principal humanizado
        assert "Informe_Semanal_Septiembre_2026.docx" in info.mensaje_principal
        assert "abierto o bloqueado por otra aplicación" in info.mensaje_principal
        assert "[WinError 32]" not in info.mensaje_principal
        assert "Traceback" not in info.mensaje_principal

        # Acción sugerida
        assert "Cierre el documento en Microsoft Word" in info.accion_sugerida
        assert "Ejecutar Consolidación" in info.accion_sugerida

        # Detalle técnico preservado
        assert len(info.detalle_tecnico) > 0
        assert "PermissionError" in info.detalle_tecnico

    def test_05b_permission_error_archivo_bloqueado_sin_filename_explicito(self):
        """
        Test 5b: Archivo bloqueado con mensaje que contiene el archivo entre comillas pero sin filename attribute.
        """
        ex = PermissionError(
            "[WinError 32] El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso: 'C:\\Docs\\Informe_Tecnico_2026.docx'"
        )

        info = ErrorTranslator.traducir(ex)
        assert info.titulo == "Archivo Bloqueado por Microsoft Word u Otro Programa"
        assert "Informe_Tecnico_2026.docx" in info.mensaje_principal
        assert "[WinError 32]" not in info.mensaje_principal
        assert "Cierre el documento en Microsoft Word" in info.accion_sugerida

    def test_05c_permission_error_permisos_insuficientes_carpeta(self):
        """
        Test 5c: Denegación de permisos de carpeta (WinError 5 / Access denied).
        NO debe culpar a Word; debe orientar sobre permisos de carpeta.
        """
        ex = PermissionError(
            5,
            "[WinError 5] Acceso denegado: 'C:\\Program Files\\BICU_Output'",
            "C:\\Program Files\\BICU_Output",
        )

        info = ErrorTranslator.traducir(ex)
        assert info.titulo == "Permisos Insuficientes en Carpeta o Archivo"
        assert "No se poseen permisos de escritura suficientes" in info.mensaje_principal
        assert "Microsoft Word" not in info.mensaje_principal
        assert "Verifique los permisos de escritura" in info.accion_sugerida
        assert "[WinError 5]" not in info.mensaje_principal
        assert len(info.detalle_tecnico) > 0


class TestFase167BUIReactivity:
    """Pruebas para reactividad de checkboxes en ValidationView."""

    def test_06_reactividad_checkboxes_validation_view(self, rutas_oficiales, periodo_septiembre):
        """
        Test 6:
        1. Ambos seleccionados -> botón habilitado, estado LISTO.
        2. Desmarcar ambos -> botón deshabilitado, estado NO LISTO.
        3. Marcar Técnico -> botón vuelve a habilitarse, estado LISTO.
        4. Desmarcar Técnico y marcar Institucional -> botón habilitado, estado LISTO.
        5. Ambos desmarcados nuevamente -> botón deshabilitado.
        """
        view = ValidationView.__new__(ValidationView)
        view.carpeta_salida = OUTPUT_DIR
        view.matrices_actuales = {}
        view.periodo_actual = None
        view._en_ejecucion = False
        view.chk_var_tecnico = DummyVar(True)
        view.chk_var_institucional = DummyVar(True)
        view.chk_tecnico = DummyWidget()
        view.chk_institucional = DummyWidget()
        view.btn_ejecutar = DummyWidget(state="disabled")
        view.btn_validar = DummyWidget()
        view.btn_cambiar_salida = DummyWidget()
        view.lbl_chk_matrices = DummyWidget()
        view.lbl_det_matrices = DummyWidget()
        view.lbl_chk_periodo = DummyWidget()
        view.lbl_det_periodo = DummyWidget()
        view.lbl_chk_salida = DummyWidget()
        view.lbl_det_salida = DummyWidget()
        view.lbl_estado_aptitud = DummyWidget()

        # 1. Ambos seleccionados por defecto -> botón normal, estado LISTO
        view.actualizar_estado(rutas_oficiales, periodo_septiembre)
        assert view.chk_var_tecnico.get() is True
        assert view.chk_var_institucional.get() is True
        assert view.btn_ejecutar.cget("state") == "normal"
        assert "LISTO PARA PROCESAR" in view.lbl_estado_aptitud.cget("text")

        # 2. Desmarcar ambos reactivamente
        view.chk_var_tecnico.set(False)
        view.chk_var_institucional.set(False)
        view._on_opciones_generacion_cambiadas()

        assert view.btn_ejecutar.cget("state") == "disabled"
        assert "NO LISTO — SELECCIONE AL MENOS UN INFORME" in view.lbl_estado_aptitud.cget("text")

        # 3. Marcar solo Técnico reactivamente
        view.chk_var_tecnico.set(True)
        view._on_opciones_generacion_cambiadas()

        assert view.btn_ejecutar.cget("state") == "normal"
        assert "LISTO PARA PROCESAR" in view.lbl_estado_aptitud.cget("text")

        # 4. Desmarcar Técnico y marcar Institucional
        view.chk_var_tecnico.set(False)
        view.chk_var_institucional.set(True)
        view._on_opciones_generacion_cambiadas()

        assert view.btn_ejecutar.cget("state") == "normal"
        assert "LISTO PARA PROCESAR" in view.lbl_estado_aptitud.cget("text")

        # 5. Desmarcar ambos nuevamente
        view.chk_var_institucional.set(False)
        view._on_opciones_generacion_cambiadas()

        assert view.btn_ejecutar.cget("state") == "disabled"
        assert "NO LISTO — SELECCIONE AL MENOS UN INFORME" in view.lbl_estado_aptitud.cget("text")


class TestFase167BGeneracionPreservada:
    """Pruebas de no-regresión para los modos de generación del pipeline."""

    def test_07_modos_de_generacion_a_b_ab(self, rutas_oficiales, periodo_septiembre, tmp_path):
        """
        Test 7:
        - Solo Técnico -> Genera Product A (Informe Técnico) y NO Product B.
        - Solo Institucional -> Genera Product B (Informe Institucional) y NO Product A.
        - Ambos -> Genera ambos informes.
        """
        pipeline = WordConsolidationPipeline(output_dir=tmp_path)

        # Caso 1: Solo Técnico
        out_tec = tmp_path / "out_tec"
        res_tec = pipeline.ejecutar(
            fuentes=rutas_oficiales,
            periodo=periodo_septiembre,
            salida_dir=out_tec,
            generar_tecnico=True,
            generar_institucional=False,
        )
        assert res_tec.ruta_docx is not None
        assert Path(res_tec.ruta_docx).exists()
        assert res_tec.ruta_docx_institucional is None

        # Caso 2: Solo Institucional
        out_inst = tmp_path / "out_inst"
        res_inst = pipeline.ejecutar(
            fuentes=rutas_oficiales,
            periodo=periodo_septiembre,
            salida_dir=out_inst,
            generar_tecnico=False,
            generar_institucional=True,
        )
        assert res_inst.ruta_docx is None
        assert res_inst.ruta_docx_institucional is not None
        assert Path(res_inst.ruta_docx_institucional).exists()

        # Caso 3: Ambos
        out_ambos = tmp_path / "out_ambos"
        res_ambos = pipeline.ejecutar(
            fuentes=rutas_oficiales,
            periodo=periodo_septiembre,
            salida_dir=out_ambos,
            generar_tecnico=True,
            generar_institucional=True,
        )
        assert res_ambos.ruta_docx is not None
        assert Path(res_ambos.ruta_docx).exists()
        assert res_ambos.ruta_docx_institucional is not None
        assert Path(res_ambos.ruta_docx_institucional).exists()
