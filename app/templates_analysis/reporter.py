"""
app.templates_analysis.reporter

Formateador y serializador del análisis de plantillas oficiales (Fase 8).
Genera reportes de consola y persiste el contrato técnico en output/reporte_plantillas.json.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.audit.audit_logger import get_logger
from app.templates_analysis.inspector import TemplateInspector
from app.templates_analysis.mapping_manifesto import MappingManifestoEngine
from app.templates_analysis.models import (
    EsquemaPlantilla,
    MappingManifesto,
    ReporteInspeccionPlantillas,
)
from app.templates_analysis.template_validator import TemplateValidator

logger = get_logger(__name__)


class TemplateReporter:
    """
    Coordina, formatea y serializa los resultados de la inspección y mapeo de plantillas.
    """

    # Definición canónica de las 5 matrices institucionales
    MATRICES_DEFINIDAS = [
        ("matriz_1", "Matriz 1: Consolidado de Actividades", "Matriz_1_Consolidado_Actividades.xlsx"),
        ("matriz_2", "Matriz 2: Estudiantes", "Matriz_2_Estudiantes.xlsx"),
        ("matriz_3", "Matriz 3: Académicos y Administrativos", "Matriz_3_Academicos_Administrativos.xlsx"),
        ("matriz_4", "Matriz 4: Colaboradores", "Matriz_4_Colaboradores.xlsx"),
        ("matriz_5", "Matriz 5: Protagonistas Beneficiados", "Matriz_5_Protagonistas_Beneficiados.xlsx"),
    ]

    @classmethod
    def ejecutar_inspeccion_global(
        cls,
        carpeta_templates: Path,
        carpeta_fixtures: Optional[Path] = None,
    ) -> ReporteInspeccionPlantillas:
        """
        Ejecuta la inspección completa de las 5 matrices respetando la jerarquía de prioridad:
        1. Plantilla oficial real en carpeta_templates.
        2. Si no existe en carpeta_templates, busca fixture en carpeta_fixtures (solo para pruebas).
        3. Si no existe en ningún lado, documenta su ausencia formal.

        Args:
            carpeta_templates: Directorio oficial de plantillas (templates/).
            carpeta_fixtures: Directorio opcional de fixtures para pruebas (tests/fixtures/templates/).

        Returns:
            ReporteInspeccionPlantillas auditado.
        """
        logger.info("Iniciando Inspección Global de Plantillas Oficiales (Fase 8).")
        esquemas: Dict[str, EsquemaPlantilla] = {}
        manifestos: Dict[str, MappingManifesto] = {}
        ausentes: List[str] = []
        reales_count = 0

        for id_mat, nom_mat, archivo_defecto in cls.MATRICES_DEFINIDAS:
            ruta_real = carpeta_templates / archivo_defecto
            ruta_a_usar: Optional[Path] = None
            es_oficial = False

            if ruta_real.exists():
                ruta_a_usar = ruta_real
                es_oficial = True
                reales_count += 1
            elif carpeta_fixtures:
                ruta_fixture = carpeta_fixtures / f"fixture_test_{id_mat}.xlsx"
                if ruta_fixture.exists():
                    ruta_a_usar = ruta_fixture
                    es_oficial = False
                else:
                    # Alternativa por nombre de archivo estándar en fixtures
                    ruta_fixture_alt = carpeta_fixtures / archivo_defecto
                    if ruta_fixture_alt.exists():
                        ruta_a_usar = ruta_fixture_alt
                        es_oficial = False

            if ruta_a_usar and ruta_a_usar.exists():
                try:
                    esq = TemplateInspector.inspeccionar_archivo(
                        ruta_archivo=ruta_a_usar,
                        id_matriz=id_mat,
                        nombre_matriz=nom_mat,
                        es_oficial=es_oficial,
                    )
                    man = MappingManifestoEngine.generar_manifesto(esq)
                    TemplateValidator.validar_esquema_y_manifesto(esq, man)

                    esquemas[id_mat] = esq
                    manifestos[id_mat] = man
                except Exception as ex:
                    logger.error(f"Error al inspeccionar '{id_mat}' ({nom_mat}): {ex}")
                    ausentes.append(f"{nom_mat} (Error de lectura: {ex})")
            else:
                logger.warning(f"Plantilla oficial ausente en disco: {nom_mat} ({archivo_defecto})")
                ausentes.append(f"{nom_mat} ({archivo_defecto})")

        total_eval = len(esquemas)
        conformidad = (total_eval > 0 and len(ausentes) == 0) or (total_eval > 0 and len(esquemas) == 5)

        return ReporteInspeccionPlantillas(
            total_plantillas_evaluadas=total_eval,
            plantillas_reales_encontradas=reales_count,
            plantillas_ausentes=ausentes,
            esquemas=esquemas,
            manifestos=manifestos,
            conformidad_global=conformidad,
            timestamp=datetime.now().isoformat(),
        )

    @classmethod
    def formatear_consola(cls, reporte: ReporteInspeccionPlantillas) -> str:
        """Genera un informe técnico estructurado y legible para terminal."""
        lineas = []
        lineas.append("=" * 76)
        lineas.append("  ANÁLISIS, INSPECCIÓN FÍSICA Y MAPPING MANIFESTO DE PLANTILLAS (FASE 8)")
        lineas.append("=" * 76)
        lineas.append("")

        lineas.append("  1. RESUMEN GENERAL DE PLANTILLAS EVALUADAS:")
        lineas.append(f"     * Total evaluadas:                 {reporte.total_plantillas_evaluadas}")
        lineas.append(f"     * Plantillas oficiales reales:     {reporte.plantillas_reales_encontradas}")
        lineas.append(f"     * Plantillas ausentes o no prov.:  {len(reporte.plantillas_ausentes)}")
        if reporte.plantillas_ausentes:
            for aus in reporte.plantillas_ausentes:
                lineas.append(f"       - [PENDIENTE P-04] {aus}")
        lineas.append("")

        lineas.append("  2. DETALLE ESTRUCTURAL POR MATRIZ (FASE 8A & 8B):")
        for id_mat, esq in reporte.esquemas.items():
            man = reporte.manifestos.get(id_mat)
            tipo_origen = "[OFICIAL REAL]" if esq.es_oficial else "[GOLDEN TEST FIXTURE - NO OFICIAL]"

            lineas.append(f"     [+] {esq.nombre_matriz} {tipo_origen}")
            lineas.append(f"         - Archivo: {Path(esq.ruta_archivo).name} | Hoja: {esq.hoja_inspeccionada}")
            lineas.append(f"         - Dimensiones: {esq.max_filas} filas x {esq.max_columnas} columnas")
            lineas.append(f"         - Fila Encabezados: {esq.fila_encabezados or 'N/A'} | Fila Inicio Datos: {esq.fila_inicio_datos or 'N/A'} ({esq.estado_fila_inicio})")
            lineas.append(f"         - Celdas Combinadas: {len(esq.celdas_combinadas)} | Celdas Protegidas / Fórmulas: {len(esq.celdas_protegidas)}")
            lineas.append(f"         - Hojas Ocultas: {len(esq.hojas_ocultas)} | Protección de Hoja: {'Sí' if esq.tiene_proteccion_hoja else 'No'}")

            if man:
                lineas.append(f"         - Mapping Manifesto: {man.total_columnas} cols (Directas: {man.columnas_directas}, Calculadas: {man.columnas_calculadas}, Sin Fuente: {man.columnas_sin_fuente}, Cat. Pendiente: {man.columnas_catalogo_pendiente})")
                lineas.append("         - Columnas Mapeadas:")
                for it in man.items[:8]:  # Mostrar primeras columnas como vista previa
                    sf_tag = f" -> {it.campo_ssot_fuente}" if it.campo_ssot_fuente else ""
                    lineas.append(f"           * Col {it.columna_letra:<2} [{it.tipo_mapeo.value:<10}]: '{it.encabezado_original}'{sf_tag} ({it.estado.value})")
                if len(man.items) > 8:
                    lineas.append(f"           * ... y {len(man.items) - 8} columnas adicionales documentadas en JSON.")
            lineas.append("     " + "-" * 70)

        lineas.append("")
        lineas.append("  3. DIRECTIVAS INSTITUCIONALES PARA FASE 9 (EXPORTACIÓN):")
        lineas.append("     * Cero Sobrescritura: Las celdas protegidas y fórmulas identificadas deben preservarse.")
        lineas.append("     * Regla de No Invención: Las columnas con estado SIN_FUENTE se mantendrán en blanco.")
        lineas.append("     * Inicio de Escritura: Se respetará estrictamente la fila_inicio_datos descubierta.")
        lineas.append("=" * 76)

        return "\n".join(lineas)

    @classmethod
    def guardar_json(cls, reporte: ReporteInspeccionPlantillas, ruta_archivo: Path) -> Path:
        """Serializa los esquemas y manifestos de plantillas en output/reporte_plantillas.json."""
        ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
        datos = json.loads(reporte.model_dump_json())
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        logger.info(f"Reporte de plantillas oficial guardado en: {ruta_archivo}")
        return ruta_archivo
