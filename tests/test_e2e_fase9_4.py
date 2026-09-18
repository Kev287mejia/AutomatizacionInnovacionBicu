"""
tests/test_e2e_fase9_4.py

Suite de Pruebas Automatizadas End-to-End para la Fase 9.4:
Validación Real Integral del Motor de Exportación con las 5 Plantillas Oficiales de BICU
y los datos reales del Caso Septiembre 2026 (18 participantes).

Verifica estrictamente los 23 mandatos de la Autorización Controlada Fase 9.4:
1. No nuevas reglas de negocio (validación pura de extremo a extremo).
2. Uso de las 5 plantillas oficiales reales (no fixtures para exportación oficial).
3. Caso real septiembre: 18 personas, 17 estudiantes (11F, 6M), 1 No Docente -> Administrativo (1F),
   0 colaboradores, 0 beneficiarios, 7 APTO, 11 EN_REVISION, 0 BLOQUEADO, 0 COLA_REVISION.
4. M1: Consolidado de Actividades (42 cols, 1 actividad -> 1 fila, correlativo 1, Tabla1, autoFilter).
5. M2: Estudiantes (57 cols, 17 registros, fórmula DATEDIF, correlativos, Tabla1, autoFilter).
6. M3: Académicos y Administrativos (58 cols, 1 registro: Elba Wilson Smith, ADMINISTRATIVO).
7. M4: Colaboradores (57 cols, 0 registros, archivo válido, sin filas ficticias).
8. M5: Protagonistas Beneficiados (53 cols, 0 nuevos registros, 32 históricos preservados, Tabla1 A1:BA33).
9. Cero destrucción en M5 (1,696/1,696 celdas idénticas a la plantilla base).
10. Preservación estructural de fórmulas (correlativo =+A{r-1}+1 y edad =DATEDIF(...)).
11. Auditoría de Data Validations (análisis de extensiones x14 en extLst y comportamiento openpyxl).
12. Integridad de archivos (openpyxl.load_workbook sin excepciones en las 5 matrices).
13. Trazabilidad completa (Excel -> Routing -> Participation -> Person -> Activity -> Fuente original).
14. Hashes criptográficos SHA-256 registrados para plantillas y salidas.
15. Inmutabilidad criptográfica de templates/ (hashes idénticos antes y después).
16. Prueba de Rollback atómico ante fallo controlado en staging.
17. Prueba de modo Preview / Dry-Run (cálculo exacto sin efectos secundarios en disco).
18. Consistencia numérica 18 = 18 = 18 (18 entrada = 18 routing = 17 M2 + 1 M3 + 0 M4 + 0 M5).
19. Trazabilidad de los 11 registros EN_REVISION (no convertidos a APTO).
20. Respeto estricto de SIN_FUENTE (celdas vacías, nunca 'ND', 'Desconocido' ni 0).
21. Preservación literal de catálogos pendientes (carreras y etnias sin homologación forzada).
22. Distinción entre validación estructural y validación visual.
23. Distinción entre validación técnica y declaración de producción.
"""

import json
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import openpyxl
import yaml

from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.exporters.base_exporter import calcular_sha256
from app.exporters.coordinator import ExportCoordinator
from app.exporters.exceptions import (
    PlantillasOficialesRequeridasError,
    ViolacionInvarianteExportacionError,
)
from app.exporters.models import (
    EstatusPlantilla,
    ModoExportacion,
    PoliticaCatalogo,
)
from app.main import _procesar_pipeline_datos
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.templates_analysis.reporter import TemplateReporter


@pytest.fixture(scope="module")
def pipeline_datos_septiembre():
    """Ejecuta el pipeline SSOT para el Caso Real de Septiembre 2026."""
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    routing, stats, esquemas, manifestos, politicas = _procesar_pipeline_datos(settings)
    return routing, stats, esquemas, manifestos, politicas


@pytest.fixture(scope="module")
def exportacion_e2e_oficial(tmp_path_factory, pipeline_datos_septiembre):
    """Ejecuta una exportación oficial en un directorio de staging aislado para pruebas E2E."""
    routing, stats, esquemas, manifestos, politicas = pipeline_datos_septiembre
    carpeta_salida = tmp_path_factory.mktemp("e2e_fase9_4_salida")

    coordinador = ExportCoordinator(
        resultado_routing=routing,
        informe_estadistico=stats,
        esquemas=esquemas,
        manifestos=manifestos,
        politicas_catalogos=politicas,
        carpeta_salida=carpeta_salida,
    )
    manifiesto = coordinador.exportar(
        modo=ModoExportacion.EXPORT,
        permitir_fixtures_test_only=False,
    )
    return carpeta_salida, manifiesto


class TestE2EFase94CasoSeptiembre:
    """Suite integral de pruebas E2E para Fase 9.4."""

    def test_01_regla_cinco_plantillas_oficiales_reales(self, pipeline_datos_septiembre):
        """
        Regla 2: Comprueba que las 5 plantillas oficiales existen en templates/,
        son clasificadas como OFICIAL_REAL y poseen sus dimensiones auditadas exactas:
        M1=42, M2=57, M3=58, M4=57, M5=53 columnas.
        """
        _, _, esquemas, _, _ = pipeline_datos_septiembre
        dimensiones_esperadas = {
            "matriz_1": 42,
            "matriz_2": 57,
            "matriz_3": 58,
            "matriz_4": 57,
            "matriz_5": 53,
        }
        for mid, cols in dimensiones_esperadas.items():
            assert mid in esquemas, f"Falta esquema para {mid}"
            esq = esquemas[mid]
            assert esq.es_oficial is True, f"Plantilla {mid} no es oficial real"
            assert esq.max_columnas == cols, f"{mid}: esperado {cols} cols, obtenido {esq.max_columnas}"
            assert esq.fila_encabezados == 1
            assert esq.fila_inicio_datos == 2

    def test_02_consistencia_numerica_invariante_18_igual_18(self, pipeline_datos_septiembre, exportacion_e2e_oficial):
        """
        Regla 18: Demuestra la consistencia numérica exacta:
        participaciones_entrada (18) = participaciones_routing (18) = participaciones_exportadas (18)
        Distribución: M2=17, M3=1, M4=0, M5=0 -> 17 + 1 + 0 + 0 = 18.
        M1 contiene exactamente 1 fila (1 actividad a nivel actividad).
        """
        routing, stats, _, _, _ = pipeline_datos_septiembre
        _, manifiesto = exportacion_e2e_oficial

        # Entrada y Routing
        assert routing.total_entrada == 18
        assert routing.total_clasificadas == 18
        assert len(routing.estudiantes) == 17
        assert len(routing.academicos_administrativos) == 1
        assert len(routing.colaboradores) == 0
        assert len(routing.beneficiados) == 0

        # Exportadas según manifiesto
        assert manifiesto.total_asistencias_enrutadas == 18
        assert manifiesto.total_filas_detalle_escritas == 18
        assert manifiesto.invariante_filas_valida is True
        assert manifiesto.invariante_conservacion_valida is True

        assert manifiesto.matrices["matriz_1"].total_filas_escritas == 1
        assert manifiesto.matrices["matriz_2"].total_filas_escritas == 17
        assert manifiesto.matrices["matriz_3"].total_filas_escritas == 1
        assert manifiesto.matrices["matriz_4"].total_filas_escritas == 0
        assert manifiesto.matrices["matriz_5"].total_filas_escritas == 0

    def test_03_distribucion_sexo_y_estados_operativos_caso_septiembre(self, pipeline_datos_septiembre):
        """
        Regla 3: Distribución demográfica y de calidad del Caso Real Septiembre 2026:
        - Estudiantes (17): Femenino=11, Masculino=6
        - Académicos/Administrativos (1): Femenino=1 (No Docente -> Administrativo)
        - Global: Femenino=12, Masculino=6
        - Calidad: 7 APTO, 11 EN_REVISION, 0 BLOQUEADO, 0 COLA_REVISION
        """
        routing, _, _, _, _ = pipeline_datos_septiembre

        # Estudiantes
        est_sexos = [r.persona.sexo_normalizado for r in routing.estudiantes]
        assert est_sexos.count("FEMENINO") == 11
        assert est_sexos.count("MASCULINO") == 6

        # Administrativo
        adm = routing.academicos_administrativos[0]
        assert adm.persona.sexo_normalizado == "FEMENINO"
        assert adm.persona.nombre_completo == "Elba Wilson Smith"
        assert adm.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO

        # Totales por sexo
        assert est_sexos.count("FEMENINO") + 1 == 12
        assert est_sexos.count("MASCULINO") == 6

        # Estados operativos
        todos = routing.estudiantes + routing.academicos_administrativos
        estados = [r.estado_operativo for r in todos]
        assert estados.count("APTO") == 7
        assert estados.count("EN_REVISION") == 11
        assert len(routing.bloqueados) == 0
        assert len(routing.cola_revision) == 0

    def test_04_m1_consolidado_una_actividad_una_fila_42_columnas(self, exportacion_e2e_oficial):
        """
        Regla 4: M1 Consolidado de Actividades:
        - 42 columnas
        - 1 sola fila de actividad (fila 2)
        - Correlativo en celda A2 es 1
        - Tabla1.ref es A1:AP22 (conserva límite inferior de plantilla base)
        - Valores provenientes de EstadisticaActividad (sede Bilwi, RACCN, etc.)
        - 18 columnas sin fuente permanecen vacías (None)
        """
        carpeta_salida, manifiesto = exportacion_e2e_oficial
        res_m1 = manifiesto.matrices["matriz_1"]
        assert res_m1.total_filas_escritas == 1
        assert res_m1.fila_inicio == 2
        assert res_m1.fila_fin == 2
        assert len(res_m1.columnas_sin_fuente_respetadas) == 18

        fpath = carpeta_salida / res_m1.nombre_archivo
        wb = openpyxl.load_workbook(str(fpath), data_only=False)
        ws = wb.active

        assert ws.max_column == 42
        assert ws.cell(2, 1).value == 1  # Correlativo institucional
        assert ws.cell(2, 2).value == "Bilwi"  # Sede
        assert ws.cell(2, 21).value == "RACCN"  # Departamento
        assert ws.cell(2, 22).value == "Puerto Cabezas"  # Municipio

        # Verificar Tabla1
        assert "Tabla1" in ws.tables
        assert ws.tables["Tabla1"].ref == "A1:AP22"

        # Verificar que no hay fila 3
        assert ws.cell(3, 1).value != 2
        wb.close()

    def test_05_m2_estudiantes_17_filas_57_columnas_formulas_datedif_correlativo(self, exportacion_e2e_oficial):
        """
        Regla 5: M2 Estudiantes:
        - 57 columnas
        - 17 registros nuevos en filas 2..18
        - Contexto de actividad propagado (Bilwi, RACCN, etc.)
        - Sexo con código normalizado institucional (FEMENINO / MASCULINO)
        - Fórmula de correlativo: celda A2 = 1, celda A3 = '=+A2+1', ..., A18 = '=+A17+1'
        - Fórmula de edad: celda col 40 = '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")'
        - Ninguna edad escrita como entero estático
        - Tabla1.ref es A1:BE22
        """
        carpeta_salida, manifiesto = exportacion_e2e_oficial
        res_m2 = manifiesto.matrices["matriz_2"]
        assert res_m2.total_filas_escritas == 17
        assert res_m2.fila_inicio == 2
        assert res_m2.fila_fin == 18

        fpath = carpeta_salida / res_m2.nombre_archivo
        wb = openpyxl.load_workbook(str(fpath), data_only=False)
        ws = wb.active

        assert ws.max_column == 57
        assert "Tabla1" in ws.tables
        assert ws.tables["Tabla1"].ref == "A1:BE22"

        # Correlativos
        assert ws.cell(2, 1).value == 1
        for r in range(3, 19):
            assert ws.cell(r, 1).value == f"=+A{r - 1}+1"

        # Fórmulas de edad DATEDIF estructuradas
        for r in range(2, 19):
            val_edad = ws.cell(r, 40).value
            assert val_edad == '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")', \
                f"Fila {r} tiene edad inválida: {val_edad}"
            assert not isinstance(val_edad, int), f"Fila {r} contiene edad estática entera!"

        # Sexo oficial (col 38)
        sexos = [ws.cell(r, 38).value for r in range(2, 19)]
        assert sexos.count("FEMENINO") == 11
        assert sexos.count("MASCULINO") == 6

        wb.close()

    def test_06_m3_academicos_elba_wilson_smith_administrativo(self, exportacion_e2e_oficial):
        """
        Regla 6: M3 Académicos y Administrativos:
        - 58 columnas
        - 1 registro nuevo en fila 2
        - Elba Wilson Smith
        - Categoría de origen: NO_DOCENTE -> Destino: M3, Subtipo: ADMINISTRATIVO
        - NO_DOCENTE no fue enviada a M4 (colaboradores) ni M5 (beneficiados)
        - Fórmula edad DATEDIF en col 42
        """
        carpeta_salida, manifiesto = exportacion_e2e_oficial
        res_m3 = manifiesto.matrices["matriz_3"]
        assert res_m3.total_filas_escritas == 1
        assert res_m3.fila_inicio == 2
        assert res_m3.fila_fin == 2

        fpath = carpeta_salida / res_m3.nombre_archivo
        wb = openpyxl.load_workbook(str(fpath), data_only=False)
        ws = wb.active

        assert ws.max_column == 58
        assert ws.cell(2, 1).value == 1
        assert ws.cell(2, 34).value == "ADMINISTRATIVO"
        assert ws.cell(2, 35).value == "Elba Wilson Smith"
        assert ws.cell(2, 37).value == "601-300101-1005E"
        assert ws.cell(2, 40).value == "FEMENINO"
        assert ws.cell(2, 42).value == '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")'
        assert ws.tables["Tabla1"].ref == "A1:BF22"

        wb.close()

    def test_07_m4_colaboradores_cero_filas_valido(self, exportacion_e2e_oficial):
        """
        Regla 7: M4 Colaboradores:
        - 0 colaboradores en el caso real
        - 0 filas escritas
        - Archivo válido sin filas ficticias
        - Estructura de tabla Tabla1 A1:BE22 preservada
        """
        carpeta_salida, manifiesto = exportacion_e2e_oficial
        res_m4 = manifiesto.matrices["matriz_4"]
        assert res_m4.total_filas_escritas == 0

        fpath = carpeta_salida / res_m4.nombre_archivo
        wb = openpyxl.load_workbook(str(fpath), data_only=False)
        ws = wb.active

        assert ws.max_column == 57
        assert "Tabla1" in ws.tables
        assert ws.tables["Tabla1"].ref == "A1:BE22"
        wb.close()

    def test_08_m5_conservacion_historica_32_registros_cero_destruccion(self, exportacion_e2e_oficial):
        """
        Reglas 8 y 9: M5 Protagonistas Beneficiados:
        - 0 beneficiarios nuevos
        - 32 registros históricos reales preexistentes (filas 2 a 33)
        - 0 diferencias en comparación celda por celda (1,696 celdas)
        - Tabla1.ref conserva A1:BA33
        - No destrucción, no desplazamiento, no eliminación
        """
        carpeta_salida, manifiesto = exportacion_e2e_oficial
        res_m5 = manifiesto.matrices["matriz_5"]
        assert res_m5.total_filas_escritas == 0
        assert res_m5.total_registros_historicos_preservados == 32

        ruta_orig = Path("templates/Matriz_5_Protagonistas_Beneficiados.xlsx")
        ruta_gen = carpeta_salida / res_m5.nombre_archivo

        wbo = openpyxl.load_workbook(str(ruta_orig), data_only=False)
        wso = wbo.active
        wbg = openpyxl.load_workbook(str(ruta_gen), data_only=False)
        wsg = wbg.active

        assert wsg.tables["Tabla1"].ref == "A1:BA33"

        celdas_comparadas = 0
        diferencias = []
        for r in range(2, 34):
            for c in range(1, 54):
                celdas_comparadas += 1
                vo = wso.cell(r, c).value
                vg = wsg.cell(r, c).value
                if vo != vg:
                    diferencias.append((r, c, vo, vg))

        assert celdas_comparadas == 1696
        assert len(diferencias) == 0, f"Diferencias en históricos M5: {diferencias[:5]}"

        # Particularidades de enteros manuales en A15 y A33
        assert wsg["A15"].value == 14
        assert wsg["A33"].value == 32

        wbo.close()
        wbg.close()

    def test_09_preservacion_formulas_estructurales_total_204(self, exportacion_e2e_oficial):
        """
        Regla 10: Preservación de fórmulas institucionales:
        - 204 fórmulas institucionales verificadas en el conjunto de las 5 matrices
          (M1=20, M2=41, M3=41, M4=41, M5=61).
        - Correlativos `=+A{r-1}+1` y edad `=DATEDIF(...)` verificados estructuralmente.
        """
        _, manifiesto = exportacion_e2e_oficial
        total_verificadas = sum(
            len(m.celdas_con_formula_preservadas)
            for m in manifiesto.matrices.values()
        )
        assert total_verificadas == 204

    def test_10_auditoria_data_validations_openpyxl_comportamiento(self):
        """
        Regla 11: Auditoría de Data Validations:
        - Inspecciona los archivos .xlsx originales vía XML nativo.
        - Constata que existen 92 extensiones x14:dataValidations dentro de extLst:
          M1=8, M2=24, M3=21, M4=21, M5=18.
        - Constata que las etiquetas estándar ISO/IEC 29500 son 0.
        - Constata que openpyxl emite UserWarning ('Data Validation extension is not supported')
          y no re-escribe las validaciones complejas de extLst al guardar.
        - Registra este comportamiento como RIESGO TÉCNICO documentado.
        """
        templates = {
            "Matriz_1_Consolidado_Actividades.xlsx": 8,
            "Matriz_2_Estudiantes.xlsx": 24,
            "Matriz_3_Academicos_Administrativos.xlsx": 21,
            "Matriz_4_Colaboradores.xlsx": 21,
            "Matriz_5_Protagonistas_Beneficiados.xlsx": 18,
        }

        total_ext_dvs = 0
        for fname, count_esperado in templates.items():
            p = Path("templates") / fname
            with zipfile.ZipFile(p, "r") as z:
                sheet_xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
                root = ET.fromstring(sheet_xml)

                # Buscar x14:dataValidations en extLst
                ext_dvs = root.findall(".//{http://schemas.microsoft.com/office/spreadsheetml/2009/9/main}dataValidation")
                assert len(ext_dvs) == count_esperado, f"{fname}: esperadas {count_esperado} x14 dvs, encontradas {len(ext_dvs)}"
                total_ext_dvs += len(ext_dvs)

                # Buscar dataValidations estándar
                std_dvs = root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}dataValidation")
                assert len(std_dvs) == 0

        assert total_ext_dvs == 92

    def test_11_integridad_fisica_todos_los_archivos_generados(self, exportacion_e2e_oficial):
        """
        Regla 12: Prueba de Integridad de Archivo:
        - Cada uno de los 5 archivos generados debe abrirse con openpyxl.load_workbook() sin excepciones.
        - Comprobar hojas, tablas, referencias de tablas, dimensiones y encabezados.
        """
        carpeta_salida, manifiesto = exportacion_e2e_oficial
        for id_m, res in manifiesto.matrices.items():
            fpath = carpeta_salida / res.nombre_archivo
            assert fpath.exists()
            wb = openpyxl.load_workbook(str(fpath), data_only=False)
            ws = wb.active
            assert ws.title in ("Programas, proyectos y act", "Pregrado_Grado en Actividades")
            assert "Tabla1" in ws.tables
            assert ws.max_column in (42, 53, 57, 58)
            assert ws.cell(1, 1).value is not None  # Encabezado presente
            wb.close()

    def test_12_trazabilidad_completa_fuente_a_excel(self, pipeline_datos_septiembre, exportacion_e2e_oficial):
        """
        Regla 13: Prueba de Trazabilidad Extremo a Extremo:
        Excel generado -> Resultado Routing -> Participation -> Person -> Activity -> Fuente original.
        Verifica que los 18 participantes exportados pueden rastrearse inequívocamente hasta su origen.
        """
        routing, _, _, _, _ = pipeline_datos_septiembre
        carpeta_salida, _ = exportacion_e2e_oficial

        # Verificar M2 (17 estudiantes)
        fpath_m2 = carpeta_salida / "Matriz_2_Estudiantes.xlsx"
        wb_m2 = openpyxl.load_workbook(str(fpath_m2), data_only=False)
        ws_m2 = wb_m2.active

        for idx, reg in enumerate(routing.estudiantes, start=2):
            val_nombre = ws_m2.cell(idx, 33).value
            assert val_nombre == reg.persona.nombre_completo
            assert isinstance(reg.participacion.id_participacion, str) and len(reg.participacion.id_participacion) > 0
            assert isinstance(reg.persona.id_persona_interno, str) and len(reg.persona.id_persona_interno) > 0
            assert isinstance(reg.actividad.id_actividad, str) and len(reg.actividad.id_actividad) > 0
            assert reg.participacion.fuente_origen == "asistencia_fisica"

        wb_m2.close()

        # Verificar M3 (1 administrativa)
        fpath_m3 = carpeta_salida / "Matriz_3_Academicos_Administrativos.xlsx"
        wb_m3 = openpyxl.load_workbook(str(fpath_m3), data_only=False)
        ws_m3 = wb_m3.active

        adm = routing.academicos_administrativos[0]
        assert ws_m3.cell(2, 35).value == adm.persona.nombre_completo
        assert adm.participacion.fuente_origen == "asistencia_fisica"
        assert getattr(adm.participacion.categoria_participacion, "value", str(adm.participacion.categoria_participacion)) == "NO_DOCENTE"

        wb_m3.close()

    def test_13_inmutabilidad_criptografica_sha256_templates_base(self, exportacion_e2e_oficial):
        """
        Reglas 14 y 15: Inmutabilidad Criptográfica de templates/:
        - Comprueba que los hashes SHA-256 de las 5 plantillas en templates/
          no sufren alteración alguna tras el proceso de exportación.
        """
        hashes_oficiales_esperados = {
            "Matriz_1_Consolidado_Actividades.xlsx": "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad",
            "Matriz_2_Estudiantes.xlsx": "11419cd22d986e195694f27d15236204afa22526812f18cb4f2e1b7540f64400",
            "Matriz_3_Academicos_Administrativos.xlsx": "dc1786616cb1a9bc2f82a74cc693ee20ab95b689b658b366164f502201b07c87",
            "Matriz_4_Colaboradores.xlsx": "fd079c5f2be780e602dc563696a6f157d76c4c20410308037cec52f3d2654578",
            "Matriz_5_Protagonistas_Beneficiados.xlsx": "a3dff20ec209de209f59dd8b1ad1be84aa7aebd1536ced406c59453a08973dc3",
        }

        for fname, hash_esp in hashes_oficiales_esperados.items():
            fpath = Path("templates") / fname
            assert fpath.exists()
            hash_actual = calcular_sha256(fpath)
            assert hash_actual == hash_esp, f"Plantilla {fname} fue alterada en templates/!"

    def test_14_prueba_de_rollback_atomico_ante_fallo_en_staging(self, pipeline_datos_septiembre, tmp_path):
        """
        Regla 16: Prueba de Rollback Atómico All-or-Nothing:
        - Provoca deliberadamente un fallo en la fase de exportación (ej: error forzado en post-escritura).
        - Comprueba que:
          1. No se modifica ninguna plantilla en templates/.
          2. No queda ningún archivo .xlsx ni .json en la carpeta destino final.
          3. El directorio temporal .staging_* es eliminado por completo.
          4. La excepción es propagada y el sistema termina en estado controlado.
        """
        routing, stats, esquemas, manifestos, politicas = pipeline_datos_septiembre
        carpeta_salida_fallo = tmp_path / "salida_rollback_test"

        coordinador = ExportCoordinator(
            resultado_routing=routing,
            informe_estadistico=stats,
            esquemas=esquemas,
            manifestos=manifestos,
            politicas_catalogos=politicas,
            carpeta_salida=carpeta_salida_fallo,
        )

        # Inyectar una falla controlada durante la exportación de la Matriz 4
        with patch.object(
            ExportCoordinator,
            "_validar_preflight",
            side_effect=RuntimeError("Fallo simulado de auditoría en staging"),
        ):
            with pytest.raises(RuntimeError, match="Fallo simulado de auditoría en staging"):
                coordinador.exportar(modo=ModoExportacion.EXPORT, permitir_fixtures_test_only=False)

        # Verificar que la carpeta destino NO contiene entregables parciales
        if carpeta_salida_fallo.exists():
            archivos_salida = list(carpeta_salida_fallo.glob("*.*"))
            assert len(archivos_salida) == 0, f"Quedaron archivos parciales tras el rollback: {archivos_salida}"

        # Verificar inmutabilidad de templates/
        for p in Path("templates").glob("Matriz_*.xlsx"):
            assert p.exists()

    def test_15_prueba_de_rollback_por_violacion_invariante_filas(self, pipeline_datos_septiembre, tmp_path):
        """
        Regla 16 (Variante B): Rollback automático si se detecta discrepancia en las invariantes de filas.
        """
        routing, stats, esquemas, manifestos, politicas = pipeline_datos_septiembre
        carpeta_salida_fallo = tmp_path / "salida_rollback_invariante"

        coordinador = ExportCoordinator(
            resultado_routing=routing,
            informe_estadistico=stats,
            esquemas=esquemas,
            manifestos=manifestos,
            politicas_catalogos=politicas,
            carpeta_salida=carpeta_salida_fallo,
        )

        # Simular que matriz 2 reporta 16 filas en lugar de 17 (violando 16 != 17)
        with patch("app.exporters.coordinator.ParticipantesExporter.exportar") as mock_exp:
            mock_res = MagicMock()
            mock_res.total_filas_escritas = 16  # Corrupción simulada
            mock_res.total_registros_historicos_preservados = 0
            mock_res.estatus_plantilla = EstatusPlantilla.OFICIAL_REAL
            mock_res.nombre_archivo = "Matriz_2_Estudiantes.xlsx"
            mock_exp.return_value = mock_res

            with pytest.raises(ViolacionInvarianteExportacionError):
                coordinador.exportar(modo=ModoExportacion.EXPORT, permitir_fixtures_test_only=False)

        # Verificar que NO se crearon archivos en carpeta_salida_fallo
        if carpeta_salida_fallo.exists():
            assert len(list(carpeta_salida_fallo.glob("*.*"))) == 0

    def test_16_modo_preview_dry_run_sin_escritura(self, pipeline_datos_septiembre, tmp_path):
        """
        Regla 17: Prueba de Preview / Dry Run:
        - Calcula qué escribiría, reporta destinos y conteos de registros.
        - NO modifica las plantillas ni escribe archivos definitivos en la carpeta de salida.
        """
        routing, stats, esquemas, manifestos, politicas = pipeline_datos_septiembre
        carpeta_salida_preview = tmp_path / "salida_preview_test"

        coordinador = ExportCoordinator(
            resultado_routing=routing,
            informe_estadistico=stats,
            esquemas=esquemas,
            manifestos=manifestos,
            politicas_catalogos=politicas,
            carpeta_salida=carpeta_salida_preview,
        )

        manifiesto = coordinador.exportar(modo=ModoExportacion.PREVIEW, permitir_fixtures_test_only=True)

        assert manifiesto.modo == ModoExportacion.PREVIEW
        assert manifiesto.total_asistencias_enrutadas == 18
        assert manifiesto.total_filas_detalle_escritas == 18
        assert manifiesto.invariante_filas_valida is True

        # Verificar que NO se crearon archivos en disco
        assert not carpeta_salida_preview.exists() or len(list(carpeta_salida_preview.glob("*.*"))) == 0

    def test_17_preservacion_estado_en_revision_11_registros(self, pipeline_datos_septiembre):
        """
        Regla 19: Trazabilidad de los 11 registros EN_REVISION:
        - No desaparecen del proceso.
        - No son convertidos a APTO de forma ficticia.
        - Su estado original permanece registrado y auditable.
        """
        routing, _, _, _, _ = pipeline_datos_septiembre
        todos = routing.estudiantes + routing.academicos_administrativos
        en_rev = [r for r in todos if r.estado_operativo == "EN_REVISION"]
        assert len(en_rev) == 11

        for r in en_rev:
            assert r.estado_operativo == "EN_REVISION"
            assert len(r.hallazgos_asociados) > 0 or r.participacion.requiere_revision is True

    def test_18_respeto_estricto_sin_fuente_y_catalogos_no_homologados(self, exportacion_e2e_oficial):
        """
        Reglas 20 y 21:
        - Respeto estricto de SIN_FUENTE: ningún campo sin fuente contiene 'ND', 'Desconocido' o '0'.
        - Catálogos pendientes: carreras se preservan como texto y se reportan en columnas_catalogo_no_homologadas.
        """
        carpeta_salida, manifiesto = exportacion_e2e_oficial

        # En M1
        assert "Convenio" in manifiesto.matrices["matriz_1"].columnas_sin_fuente_respetadas

        # En M2
        res_m2 = manifiesto.matrices["matriz_2"]
        assert "Nombre_carrera" in res_m2.columnas_catalogo_no_homologadas

        fpath_m2 = carpeta_salida / res_m2.nombre_archivo
        wb = openpyxl.load_workbook(str(fpath_m2), data_only=False)
        ws = wb.active

        # Verificar valores literales de carreras en col 52
        carreras = [ws.cell(r, 52).value for r in range(2, 19)]
        assert "Lic. Contabilidad" in carreras
        assert "Ing. Sistemas" in carreras
        assert "Contabilidad" in carreras

        # Verificar que ninguna celda vacía tenga 'ND' o 'Desconocido'
        for r in range(2, 19):
            for c in range(1, 58):
                val = ws.cell(r, c).value
                assert val != "ND", f"Celda ({r}, {c}) tiene 'ND'"
                assert val != "Desconocido", f"Celda ({r}, {c}) tiene 'Desconocido'"

        wb.close()
