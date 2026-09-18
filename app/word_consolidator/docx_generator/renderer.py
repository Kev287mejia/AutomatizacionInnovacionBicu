"""
app.word_consolidator.docx_generator.renderer

Orquestador principal para la generación y renderizado del documento Word
institucional (.docx) a partir del modelo DocumentoConsolidado.
Fase 14.7 — Capa de presentación visual estricta ("Presentación, No Negocio").
Garantiza:
1. Inmutabilidad absoluta de DocumentoConsolidado (verificación pre y post render).
2. Generación secuencial y ordenada de las 10 secciones documentales.
3. Saltos de página controlados sin páginas vacías.
4. Soporte para rutas en disco (str, Path) o buffers binarios en memoria (io.BytesIO).
"""

from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional, Union

import docx

from app.word_consolidator.document.models import DocumentoConsolidado
from app.word_consolidator.docx_generator.header_footer import HeaderFooterManager
from app.word_consolidator.docx_generator.page_setup import PageSetup
from app.word_consolidator.docx_generator.sections import (
    render_activity_cards,
    render_annexes,
    render_conclusions,
    render_consolidated_table,
    render_cover,
    render_demographics,
    render_estamentos,
    render_executive_summary,
    render_quality_audit,
    render_territory,
)
from app.word_consolidator.docx_generator.style_manager import StyleManager


class DocxGenerator:
    """
    Generador institucional de documentos Word (.docx).
    Convierte un DocumentoConsolidado en un archivo Word final completamente maquetado.
    """

    @classmethod
    def generate(
        cls,
        documento: DocumentoConsolidado,
        output_path: Optional[Union[str, Path, BinaryIO]] = None,
        landscape: bool = True,
    ) -> Union[Path, BinaryIO]:
        """
        Renderiza el DocumentoConsolidado a formato .docx.

        Args:
            documento: Modelo documental intermedio completo con las 10 secciones.
            output_path: Ruta del archivo destino (.docx) o buffer binario en memoria.
                         Si es None, se genera un archivo temporal con nombre estándar.
            landscape: True para orientación horizontal Letter (recomendado para tablas anchas).

        Returns:
            Path al archivo creado o BinaryIO con el contenido binario.

        Raises:
            ValueError: Si el documento no es una instancia de DocumentoConsolidado.
            RuntimeError: Si se detecta que DocumentoConsolidado fue mutado durante el renderizado.
        """
        if not isinstance(documento, DocumentoConsolidado):
            raise ValueError(
                f"Entrada inválida: se esperaba DocumentoConsolidado, recibido {type(documento).__name__}."
            )

        # 1. Snapshot de inmutabilidad (dump lógico previo al renderizado)
        snapshot_antes = documento.model_dump(mode="json")

        # 2. Inicialización del documento Word
        doc = docx.Document()

        # 3. Configuración de geometría de página (Landscape Letter con márgenes de 20 mm)
        PageSetup.initialize_document_geometry(doc, landscape=landscape)

        # 4. Configuración tipográfica y de estilos institucionales
        StyleManager.apply_document_styles(doc)

        # 5. Configuración de encabezados y pies de página (primera página limpia)
        institucion = (
            documento.portada.universidad
            or (documento.metadatos.universidad if documento.metadatos else None)
            or "BICU — Informe Consolidado Institucional"
        )
        periodo_texto = documento.portada.periodo_texto or documento.periodo.etiqueta
        area_texto = (
            documento.portada.area_responsable
            or (documento.metadatos.area_responsable if documento.metadatos else None)
        )
        HeaderFooterManager.setup_headers_and_footers(
            doc,
            institucion=institucion,
            periodo_texto=periodo_texto,
            area_texto=area_texto,
        )

        # 6. Renderizado secuencial de las 10 secciones con saltos de página controlados

        # Sección 1: Portada
        render_cover(doc, documento.portada, documento.periodo, documento.metadatos)
        PageSetup.add_page_break(doc)

        # Sección 2: Resumen Ejecutivo
        render_executive_summary(doc, documento.resumen_ejecutivo)
        PageSetup.add_page_break(doc)

        # Sección 3: Matriz Consolidada General de Actividades
        render_consolidated_table(doc, documento.matriz_general)
        PageSetup.add_page_break(doc)

        # Sección 4: Fichas de Detalle por Actividad
        render_activity_cards(doc, documento.fichas_actividades)
        PageSetup.add_page_break(doc)

        # Sección 5: Análisis Demográfico y Sexo
        render_demographics(doc, documento.demografia)
        PageSetup.add_page_break(doc)

        # Sección 6: Estamentos y Carreras
        render_estamentos(doc, documento.estamentos)
        PageSetup.add_page_break(doc)

        # Sección 7: Territorio / Cobertura
        render_territory(doc, documento.territorio)
        PageSetup.add_page_break(doc)

        # Sección 8: Salud de Datos / Auditoría de Discrepancias
        render_quality_audit(doc, documento.auditoria)
        PageSetup.add_page_break(doc)

        # Sección 9: Conclusiones y Dictamen Técnico
        render_conclusions(doc, documento.conclusiones)
        PageSetup.add_page_break(doc)

        # Sección 10: Anexos y Trazabilidad Criptográfica
        render_annexes(doc, documento.anexos)

        # 7. Verificación de inmutabilidad (Principio de Presentación, No Negocio)
        snapshot_despues = documento.model_dump(mode="json")
        if snapshot_antes != snapshot_despues:
            raise RuntimeError(
                "VIOLACIÓN DE ARQUITECTURA: DocumentoConsolidado fue modificado durante el renderizado DOCX."
            )

        # 8. Almacenamiento o serialización a destino
        if output_path is None:
            carpeta_salida = Path("output")
            carpeta_salida.mkdir(parents=True, exist_ok=True)
            periodo_slug = documento.periodo.etiqueta.lower().replace(" ", "_").replace("-", "_")
            destino = carpeta_salida / f"Informe_Consolidado_{periodo_slug}.docx"
            doc.save(str(destino))
            return destino

        if isinstance(output_path, (str, Path)):
            destino_path = Path(output_path)
            destino_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(destino_path))
            return destino_path

        # Caso BinaryIO (BytesIO u otro stream binario)
        doc.save(output_path)
        if hasattr(output_path, "seek"):
            output_path.seek(0)
        return output_path


# Alias de conveniencia institucional
DocxRenderer = DocxGenerator
