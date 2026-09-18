"""
app.word_consolidator.document.orchestrator

Orquestador de salida para generar múltiples documentos a partir
del mismo ResultadoConsolidacion, garantizando una única consolidación.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

from pydantic import BaseModel

from app.word_consolidator.engine.consolidation_engine import ResultadoConsolidacion
from app.word_consolidator.document.transformer import DocumentTransformer
from app.word_consolidator.docx_generator.renderer import DocxGenerator
from app.word_consolidator.document.institutional_transformer import InstitutionalReportTransformer
from app.word_consolidator.institutional_docx.generator import InstitutionalDocxGenerator
from app.word_consolidator.institutional_docx.spec import ModoFuenteDatosEnum
from app.word_consolidator.models import PeriodoConsolidacion, MetadatosInstitucionales, ResultadoAuditoriaDiscrepancias


class DocumentGenerationResult(BaseModel):
    """Estructura del resultado de generación para un producto individual."""
    status: str  # SUCCESS, FAILED, NOT_REQUESTED
    path: Optional[str] = None
    error: Optional[str] = None


class OrchestratorResult(BaseModel):
    """Resultado global de la orquestación."""
    tecnico: DocumentGenerationResult
    institucional: DocumentGenerationResult
    overall_status: str  # SUCCESS, PARTIAL, FAILED


class DocumentOutputOrchestrator:
    """
    Coordina la generación aislada de Product A (Técnico) y Product B (Institucional).
    """

    @classmethod
    def orchestrate_generation(
        cls,
        consolidacion: ResultadoConsolidacion,
        auditoria: ResultadoAuditoriaDiscrepancias,
        periodo: PeriodoConsolidacion,
        output_dir: Path,
        generar_tecnico: bool = True,
        generar_institucional: bool = True,
        metadatos: Optional[MetadatosInstitucionales] = None,
        informes_narrativos: Optional[Dict] = None,
    ) -> OrchestratorResult:
        """
        Orquesta la generación secuencial y segura de los documentos solicitados.
        Mantiene el aislamiento: si falla uno, se intenta el otro.
        """
        if informes_narrativos is None:
            informes_narrativos = {}
            
        tecnico_res = DocumentGenerationResult(status="NOT_REQUESTED")
        institucional_res = DocumentGenerationResult(status="NOT_REQUESTED")

        # Configurar carpeta
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Nombres sin hashes
        # Ejemplo: Informe_Tecnico_2026_Septiembre_Sem_1.docx
        periodo_slug = periodo.etiqueta.replace(" ", "_").replace("-", "_")
        semana = f"Sem_{periodo.semana}" if periodo.semana else ""
        
        # Base format: 2026_Septiembre_Sem_1
        base_name = f"{periodo.anio}_{periodo_slug}"
        if semana:
            base_name += f"_{semana}"

        if generar_tecnico:
            try:
                # Transformar
                doc_intermedio = DocumentTransformer.transformar(
                    consolidacion=consolidacion,
                    auditoria=auditoria,
                    periodo=periodo,
                    metadatos=metadatos,
                    informes_narrativos=informes_narrativos,
                )
                
                # Generar
                out_path = output_dir / f"Informe_Tecnico_{base_name}.docx"
                DocxGenerator.generate(
                    documento=doc_intermedio,
                    output_path=out_path,
                    landscape=True,
                )
                
                tecnico_res = DocumentGenerationResult(status="SUCCESS", path=str(out_path))
            except Exception as e:
                tecnico_res = DocumentGenerationResult(status="FAILED", error=str(e))

        if generar_institucional:
            try:
                # C1: Propagar departamento_institucional de forma explícita si existe en metadatos
                depto_institucional = (
                    metadatos.departamento_institucional.strip()
                    if (metadatos and metadatos.departamento_institucional and metadatos.departamento_institucional.strip())
                    else None
                )
                # C2: Configurar explícitamente la política DECLARADO_M1 (sin depender del default)
                informe_inst = InstitutionalReportTransformer.transformar(
                    consolidacion=consolidacion,
                    departamento_responsable=depto_institucional,
                    politica_presentacion="DECLARADO_M1",
                    metadatos=metadatos,
                )
                
                # Generar con política DECLARADO_M1 explícita
                out_path = output_dir / f"Informe_Institucional_{base_name}.docx"
                gen = InstitutionalDocxGenerator(modo_fuente=ModoFuenteDatosEnum.DECLARADO_M1)
                gen.generate(
                    informe=informe_inst,
                    output_path=out_path,
                )
                
                institucional_res = DocumentGenerationResult(status="SUCCESS", path=str(out_path))
            except Exception as e:
                institucional_res = DocumentGenerationResult(status="FAILED", error=str(e))

        # Calcular overall_status
        requested = []
        if generar_tecnico: requested.append(tecnico_res.status)
        if generar_institucional: requested.append(institucional_res.status)

        if not requested:
            overall = "SUCCESS"  # Nada pedido, nada falló
        elif all(s == "SUCCESS" for s in requested):
            overall = "SUCCESS"
        elif all(s == "FAILED" for s in requested):
            overall = "FAILED"
        else:
            overall = "PARTIAL"

        return OrchestratorResult(
            tecnico=tecnico_res,
            institucional=institucional_res,
            overall_status=overall
        )
