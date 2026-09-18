"""
Pruebas para el DocumentOutputOrchestrator.
Fase 16.6-B: Integración Product A + Product B
Garantiza que existe UNA SOLA ejecución de consolidación y que 
el mismo objeto fluye hacia los dos generadores.
"""

from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from docx import Document

from app.word_consolidator.document.orchestrator import (
    DocumentOutputOrchestrator,
    OrchestratorResult,
)
from app.word_consolidator.engine.consolidation_engine import (
    ResultadoConsolidacion,
)
from app.word_consolidator.models import (
    PeriodoConsolidacion,
    TipoPeriodo,
    ResultadoAuditoriaDiscrepancias,
)
from app.word_consolidator.document.models import DocumentoConsolidado
from app.word_consolidator.document.institutional_models import InformeSemanalInstitucional


@pytest.fixture
def consolidacion_mock(periodo_mock) -> ResultadoConsolidacion:
    return ResultadoConsolidacion(
        actividades=[],
        fuentes={},
        total_actividades=0,
        total_asistencia_bruta=0,
        total_personas_unicas=0,
        total_recurrencia=0,
        tasa_recurrencia=1.0,
        periodo=periodo_mock,
    )


@pytest.fixture
def auditoria_mock() -> ResultadoAuditoriaDiscrepancias:
    return ResultadoAuditoriaDiscrepancias(
        total_actividades_evaluadas=0,
        actividades_concordantes=0,
        actividades_con_discrepancias=0,
        total_discrepancias_activas=0,
        total_concordancias=0,
        invariante_verificada=True,
        informes_por_actividad={},
        discrepancias_globales=[],
    )


@pytest.fixture
def periodo_mock() -> PeriodoConsolidacion:
    return PeriodoConsolidacion(
        tipo_periodo=TipoPeriodo.SEMANA,
        anio=2026,
        mes=9,
        semana=1,
        etiqueta="Septiembre 2026 — Semana 1",
    )


class TestDocumentOutputOrchestrator:
    @patch("app.word_consolidator.document.orchestrator.DocumentTransformer.transformar")
    @patch("app.word_consolidator.document.orchestrator.DocxGenerator.generate")
    @patch("app.word_consolidator.document.orchestrator.InstitutionalReportTransformer.transformar")
    @patch("app.word_consolidator.document.orchestrator.InstitutionalDocxGenerator.generate")
    def test_una_sola_consolidacion_usada_en_ambos_productos(
        self,
        mock_inst_gen,
        mock_inst_trans,
        mock_tec_gen,
        mock_tec_trans,
        consolidacion_mock,
        auditoria_mock,
        periodo_mock,
        tmp_path,
    ):
        """
        Prueba crítica: Asegura que el Orquestador llama a los transformadores con 
        el MISMO objeto consolidacion_mock y que no recalcula nada.
        """
        mock_tec_trans.return_value = MagicMock(spec=DocumentoConsolidado)
        mock_inst_trans.return_value = MagicMock(spec=InformeSemanalInstitucional)

        resultado = DocumentOutputOrchestrator.orchestrate_generation(
            consolidacion=consolidacion_mock,
            auditoria=auditoria_mock,
            periodo=periodo_mock,
            output_dir=tmp_path,
        )

        assert resultado.overall_status == "SUCCESS"
        assert resultado.tecnico.status == "SUCCESS"
        assert resultado.institucional.status == "SUCCESS"

        # Verificar que el mismo objeto se pasó a ambos transformers
        mock_tec_trans.assert_called_once()
        mock_inst_trans.assert_called_once()
        
        args_tec, kwargs_tec = mock_tec_trans.call_args
        assert kwargs_tec["consolidacion"] is consolidacion_mock

        args_inst, kwargs_inst = mock_inst_trans.call_args
        assert kwargs_inst["consolidacion"] is consolidacion_mock

        # Los generadores se llamaron una vez
        mock_tec_gen.assert_called_once()
        mock_inst_gen.assert_called_once()

    def test_archivos_creados_con_nombres_correctos(self, consolidacion_mock, auditoria_mock, periodo_mock, tmp_path):
        """
        Prueba real (sin mocks) que genera documentos Word vacíos.
        """
        resultado = DocumentOutputOrchestrator.orchestrate_generation(
            consolidacion=consolidacion_mock,
            auditoria=auditoria_mock,
            periodo=periodo_mock,
            output_dir=tmp_path,
        )

        assert resultado.overall_status == "SUCCESS"
        assert Path(resultado.tecnico.path).exists()
        assert Path(resultado.institucional.path).exists()
        
        assert "Informe_Tecnico_2026_Septiembre_2026_Semana_1_Sem_1.docx" in resultado.tecnico.path or "Informe_Tecnico_" in resultado.tecnico.path
        assert "Informe_Institucional_" in resultado.institucional.path

    @patch("app.word_consolidator.document.orchestrator.InstitutionalReportTransformer.transformar")
    def test_aislamiento_de_fallos_si_falla_b_genera_a(self, mock_inst_trans, consolidacion_mock, auditoria_mock, periodo_mock, tmp_path):
        """
        Si la transformación del informe institucional falla, el técnico debe generarse con éxito.
        """
        mock_inst_trans.side_effect = Exception("Fallo forzado en Institucional")

        resultado = DocumentOutputOrchestrator.orchestrate_generation(
            consolidacion=consolidacion_mock,
            auditoria=auditoria_mock,
            periodo=periodo_mock,
            output_dir=tmp_path,
        )

        assert resultado.overall_status == "PARTIAL"
        assert resultado.tecnico.status == "SUCCESS"
        assert Path(resultado.tecnico.path).exists()
        
        assert resultado.institucional.status == "FAILED"
        assert "Fallo forzado en Institucional" in resultado.institucional.error
        assert resultado.institucional.path is None
