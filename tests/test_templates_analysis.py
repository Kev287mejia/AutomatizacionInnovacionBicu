"""
tests/test_templates_analysis.py

Suite de pruebas automatizadas para la Fase 8:
Análisis, Inspección Física (Fase 8A) e Ingeniería de Mapeo (Fase 8B) de Plantillas Oficiales.
Valida el cumplimiento exhaustivo de todos los contratos y directivas institucionales.
"""

import os
from pathlib import Path
import pytest

from app.templates_analysis.inspector import TemplateInspector
from app.templates_analysis.mapping_manifesto import MappingManifestoEngine
from app.templates_analysis.models import (
    EstadoMapeo,
    ReporteInspeccionPlantillas,
    TipoMapeoColumna,
)
from app.templates_analysis.reporter import TemplateReporter
from app.templates_analysis.template_validator import TemplateValidator
from tests.template_fixture_factory import TemplateFixtureFactory


@pytest.fixture(scope="session")
def carpeta_fixtures_templates(tmp_path_factory):
    """Genera los Golden Test Fixtures temporales para la suite de pruebas."""
    dir_fixtures = tmp_path_factory.mktemp("fixtures_templates")
    TemplateFixtureFactory.crear_fixtures_de_prueba(dir_fixtures)
    return dir_fixtures


class TestTemplatesAnalysisFase8:
    """Pruebas unitarias y de integración para la Fase 8."""

    def test_01_inspeccion_solo_lectura_sin_modificar_archivo(self, carpeta_fixtures_templates):
        """1. La inspección física no altera el archivo en disco (solo lectura estricta)."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        tamano_antes = ruta_archivo.stat().st_size
        mtime_antes = ruta_archivo.stat().st_mtime

        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )

        tamano_despues = ruta_archivo.stat().st_size
        mtime_despues = ruta_archivo.stat().st_mtime

        assert tamano_antes == tamano_despues
        assert mtime_antes == mtime_despues
        assert esquema.id_matriz == "matriz_1"

    def test_02_deteccion_hojas_visibles_y_ocultas(self, carpeta_fixtures_templates):
        """2. Descubrimiento de hojas visibles y hojas ocultas en la plantilla."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )

        assert "Consolidado" in esquema.hojas_disponibles
        assert "Config_Oculta" in esquema.hojas_disponibles
        assert "Config_Oculta" in esquema.hojas_ocultas
        assert esquema.hoja_inspeccionada == "Consolidado"

    def test_03_deteccion_encabezados_y_dimensiones(self, carpeta_fixtures_templates):
        """3. Detección automática de fila de encabezados y dimensiones físicas."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )

        assert esquema.fila_encabezados == 4
        assert esquema.max_columnas >= 17
        assert len(esquema.columnas_detectadas) == esquema.max_columnas

    def test_04_deteccion_celdas_combinadas(self, carpeta_fixtures_templates):
        """4. Detección precisa de rangos combinados (Merged Cells) con su valor principal."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )

        rangos = [r.rango for r in esquema.celdas_combinadas]
        assert "A1:Q2" in rangos

        rango_a1 = next(r for r in esquema.celdas_combinadas if r.rango == "A1:Q2")
        assert "GOLDEN TEST FIXTURE" in (rango_a1.valor_principal or "")

    def test_05_deteccion_formulas_y_celdas_protegidas(self, carpeta_fixtures_templates):
        """5. Detección exhaustiva de fórmulas existentes para evitar sobrescritura."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )

        formulas_coords = [c.coordenada for c in esquema.celdas_protegidas if c.tipo_proteccion == "FORMULA"]
        assert "I10" in formulas_coords
        assert "J10" in formulas_coords
        assert "K10" in formulas_coords
        assert "L10" in formulas_coords

        celda_i10 = next(c for c in esquema.celdas_protegidas if c.coordenada == "I10")
        assert celda_i10.formula == "=SUM(I5:I9)"

    def test_06_deteccion_validaciones_de_datos(self, carpeta_fixtures_templates):
        """6. Detección de reglas DataValidation y listas desplegables."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_2.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_2",
            nombre_matriz="Matriz 2: Estudiantes",
            es_oficial=False,
        )

        assert len(esquema.validaciones_datos) > 0
        assert any("FEMENINO,MASCULINO" in v for v in esquema.validaciones_datos)

    def test_07_determinacion_no_rigida_fila_inicio_datos(self, carpeta_fixtures_templates):
        """7. Fila de inicio de datos calculada analíticamente sin supuestos rígidos."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )

        # Encabezados en fila 4 -> Fila inicio de datos en fila 5
        assert esquema.fila_encabezados == 4
        assert esquema.fila_inicio_datos == 5
        assert esquema.estado_fila_inicio == "DETERMINADA"

    def test_08_delimitacion_zonas_escribibles_protege_totales(self, carpeta_fixtures_templates):
        """8. La zona escribible delimita filas antes de fórmulas de totales."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )

        assert len(esquema.zonas_escribibles) == 1
        zona = esquema.zonas_escribibles[0]
        assert zona.fila_inicio == 5
        # En fila 10 hay fórmulas de suma, por lo que la fila límite estimada es 9
        assert zona.fila_fin_estimada == 9

    def test_09_mapping_manifesto_resultado_de_inspeccion(self, carpeta_fixtures_templates):
        """9. El Mapping Manifesto es resultado de la inspección física, no de suposiciones."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )
        manifesto = MappingManifestoEngine.generar_manifesto(esquema)

        assert manifesto.id_matriz == "matriz_1"
        assert manifesto.total_columnas == len(esquema.columnas_detectadas)
        assert manifesto.columnas_calculadas > 0

        # Verificar columnas detectadas específicas
        col_asist = next(it for it in manifesto.items if "Total Asistencias" in it.encabezado_original)
        assert col_asist.tipo_mapeo == TipoMapeoColumna.CALCULADO
        assert col_asist.campo_ssot_fuente == "estadistica.total_asistencias"

    def test_10_deteccion_columnas_sin_fuente(self, carpeta_fixtures_templates):
        """10. Columnas sin dato en fuentes originales se marcan como SIN_FUENTE sin inventar."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_2.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_2",
            nombre_matriz="Matriz 2: Estudiantes",
            es_oficial=False,
        )
        manifesto = MappingManifestoEngine.generar_manifesto(esquema)

        item_sf = next((it for it in manifesto.items if "Código Presupuestario" in it.encabezado_original), None)
        assert item_sf is not None
        assert item_sf.tipo_mapeo == TipoMapeoColumna.SIN_FUENTE
        assert item_sf.estado == EstadoMapeo.SIN_FUENTE
        assert item_sf.campo_ssot_fuente is None
        assert "Principio de No Invención" in item_sf.observaciones

    def test_11_deteccion_dependencia_catalogo_pendiente(self, carpeta_fixtures_templates):
        """11. Si una columna depende de catálogo no disponible, se marca CATALOGO_PENDIENTE."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_2.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_2",
            nombre_matriz="Matriz 2: Estudiantes",
            es_oficial=False,
        )
        manifesto = MappingManifestoEngine.generar_manifesto(
            esquema, catalogos_disponibles={"carreras.json": False}
        )

        col_carrera = next(it for it in manifesto.items if "Carrera" in it.encabezado_original)
        assert col_carrera.tipo_mapeo == TipoMapeoColumna.CATALOGO
        assert col_carrera.estado == EstadoMapeo.CATALOGO_PENDIENTE

    def test_12_admision_estados_especiales_mapeo(self, carpeta_fixtures_templates):
        """12. El Mapping Manifesto soporta los diversos estados semánticos obligatorios."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_1",
            nombre_matriz="Matriz 1: Consolidado de Actividades",
            es_oficial=False,
        )
        manifesto = MappingManifestoEngine.generar_manifesto(esquema)

        tipos = set(it.tipo_mapeo for it in manifesto.items)
        assert TipoMapeoColumna.DIRECTO in tipos
        assert TipoMapeoColumna.CALCULADO in tipos
        assert TipoMapeoColumna.DERIVADO in tipos

    def test_13_validacion_estructural_template_validator(self, carpeta_fixtures_templates):
        """13. Validador estructural emite advertencias sobre fórmulas y columnas sin fuente."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_2.xlsx"
        esquema = TemplateInspector.inspeccionar_archivo(
            ruta_archivo=ruta_archivo,
            id_matriz="matriz_2",
            nombre_matriz="Matriz 2: Estudiantes",
            es_oficial=False,
        )
        manifesto = MappingManifestoEngine.generar_manifesto(esquema)
        es_valida, errores, advertencias = TemplateValidator.validar_esquema_y_manifesto(esquema, manifesto)

        assert es_valida is True
        assert len(errores) == 0
        assert any("sin fuente" in adv for adv in advertencias)

    def test_14_prioridad_plantilla_real_y_documentacion_ausentes(self, tmp_path, carpeta_fixtures_templates):
        """14. Prioridad a plantillas reales y documentación de ausencia si no existen."""
        carpeta_templates_vacia = tmp_path / "templates_vacia"
        carpeta_templates_vacia.mkdir()

        # Ejecución apuntando a carpeta templates vacía pero con fixtures disponibles
        reporte_fixtures = TemplateReporter.ejecutar_inspeccion_global(
            carpeta_templates=carpeta_templates_vacia,
            carpeta_fixtures=carpeta_fixtures_templates,
        )

        assert reporte_fixtures.total_plantillas_evaluadas == 5
        assert reporte_fixtures.plantillas_reales_encontradas == 0
        # Todas se marcaron como fixtures no oficiales
        assert all(not esq.es_oficial for esq in reporte_fixtures.esquemas.values())

        # Ejecución sin fixtures ni plantillas
        reporte_vacio = TemplateReporter.ejecutar_inspeccion_global(
            carpeta_templates=carpeta_templates_vacia,
            carpeta_fixtures=None,
        )
        assert len(reporte_vacio.plantillas_ausentes) == 5
        assert all("Matriz" in a for a in reporte_vacio.plantillas_ausentes)

    def test_15_serializacion_json_reporte_plantillas(self, tmp_path, carpeta_fixtures_templates):
        """15. Persistencia y validez del archivo output/reporte_plantillas.json."""
        reporte = TemplateReporter.ejecutar_inspeccion_global(
            carpeta_templates=tmp_path,
            carpeta_fixtures=carpeta_fixtures_templates,
        )
        ruta_salida = tmp_path / "reporte_plantillas.json"
        guardada = TemplateReporter.guardar_json(reporte, ruta_salida)

        assert guardada.exists()
        assert guardada.stat().st_size > 0

        # Formateo consola sin excepciones
        texto = TemplateReporter.formatear_consola(reporte)
        assert "ANÁLISIS, INSPECCIÓN FÍSICA Y MAPPING MANIFESTO DE PLANTILLAS (FASE 8)" in texto
        assert "Matriz 1: Consolidado de Actividades" in texto

    def test_16_ausencia_total_escritura_datos_participantes(self, carpeta_fixtures_templates):
        """16. Fase 8 nunca escribe datos de participantes en las plantillas (cero exportación)."""
        ruta_archivo = carpeta_fixtures_templates / "fixture_test_matriz_1.xlsx"

        # Inspeccionar múltiples veces
        for _ in range(3):
            esq = TemplateInspector.inspeccionar_archivo(
                ruta_archivo=ruta_archivo,
                id_matriz="matriz_1",
                nombre_matriz="Matriz 1: Consolidado de Actividades",
                es_oficial=False,
            )
            man = MappingManifestoEngine.generar_manifesto(esq)
            assert esq.max_filas == 10  # Filas originales fijas del fixture
            assert man.total_columnas > 0
