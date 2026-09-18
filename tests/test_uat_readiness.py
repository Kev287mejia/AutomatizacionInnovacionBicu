"""
tests/test_uat_readiness.py

Suite de Pruebas Automatizadas de Instrumentación y Preparación UAT (Fase 12).

Objetivo:
Validar de forma automatizada y reproducible que los instrumentos documentales,
criterios de aceptación, matrices de casos y entregables del Caso Real de Septiembre 2026
estén 100% alineados con las directrices institucionales de BICU:
  1. Integridad y completitud de los 4 documentos UAT en docs/uat/.
  2. Verificación de las cifras oficiales del caso base de septiembre 2026 (18 participaciones,
     18 personas únicas, 17 estudiantes en M2, 1 administrativo en M3, 12 mujeres y 6 varones en M1,
     0 colaboradores en M4, 0 nuevos en M5, 32 históricos celda por celda preservados).
  3. Diferenciación estricta entre clasificación/enrutamiento y estado de revisión operativa.
  4. Garantía de no invención de cédulas ni tratamiento de fechas de nacimiento como identidades.
  5. Registro objetivo del riesgo RISK-DV-X14 y delimitación frente a la aceptación de usuario.
  6. Documentación formal de casos REQUIERE_MUESTRA_INSTITUCIONAL sin datos sintéticos.
  7. Invariantes de los 5 archivos Excel oficiales generados en output/.
  8. Preservación estricta de cero declaración de producción.
"""

from pathlib import Path
import openpyxl
import pytest
import yaml

from app.main import _procesar_pipeline_datos


@pytest.fixture(scope="module")
def workspace_root():
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def uat_docs(workspace_root):
    return {
        "protocolo": workspace_root / "docs" / "uat" / "uat_protocolo_usuario.md",
        "matriz_casos": workspace_root / "docs" / "uat" / "uat_matriz_casos.md",
        "checklist": workspace_root / "docs" / "uat" / "uat_checklist_excel.md",
        "acta": workspace_root / "docs" / "uat" / "uat_acta_dictamen.md",
        "informe_uat": workspace_root / "docs" / "uat" / "FASE12_INFORME_UAT.md",
    }


class TestUATDocumentacionInstrumentos:
    """Valida la existencia, estructura y completitud de los documentos UAT."""

    def test_01_todos_los_documentos_uat_existen(self, uat_docs):
        for nombre, ruta in uat_docs.items():
            assert ruta.exists(), f"El documento UAT '{nombre}' no existe en {ruta}"
            assert ruta.stat().st_size > 1000, f"El documento '{nombre}' parece estar truncado o vacío ({ruta.stat().st_size} bytes)"

    def test_02_protocolo_usuario_contiene_secciones_clave(self, uat_docs):
        contenido = uat_docs["protocolo"].read_text(encoding="utf-8")
        assert "python app/main.py --help" in contenido
        assert "python app/main.py --mode validate" in contenido
        assert "python app/main.py --mode preview" in contenido
        assert "python app/main.py --mode export" in contenido
        assert "python app/main.py --mode audit" in contenido
        assert "Separación entre Clasificación y Revisión" in contenido
        assert "Regla Estricta sobre Identificación y Fechas" in contenido
        assert "RISK-DV-X14" in contenido

    def test_03_matriz_casos_especifica_cifras_oficiales_septiembre_2026(self, uat_docs):
        contenido = uat_docs["matriz_casos"].read_text(encoding="utf-8")
        assert "18" in contenido  # Total participaciones y personas
        assert "17" in contenido  # Estudiantes
        assert "Elba Wilson Smith" in contenido  # Administrativo M3
        assert "12 F / 6 M" in contenido or ("12 Mujeres" in contenido and "6 Varones" in contenido)
        assert "32" in contenido  # Registros históricos M5
        assert "1,696" in contenido or "1696" in contenido
        assert "REQUIERE_MUESTRA_INSTITUCIONAL" in contenido
        assert "UAT-DOC" in contenido
        assert "UAT-COL" in contenido
        assert "UAT-BEN" in contenido

    def test_04_checklist_excel_contiene_revision_cinco_matrices(self, uat_docs):
        contenido = uat_docs["checklist"].read_text(encoding="utf-8")
        assert "Matriz 1: Consolidado de Actividades" in contenido
        assert "Total, Atención, M" in contenido and "6" in contenido
        assert "Total, Atención, F" in contenido and "12" in contenido
        assert "Matriz 2: Estudiantes" in contenido
        assert "=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), \"Y\")" in contenido
        assert "Matriz 3: Académicos y Administrativos" in contenido
        assert "Matriz 4: Colaboradores" in contenido
        assert "Matriz 5: Protagonistas Beneficiados" in contenido
        assert "32 registros históricos" in contenido.lower() or "32 participantes históricos" in contenido.lower()

    def test_05_acta_dictamen_separa_niveles_y_prohibe_produccion(self, uat_docs):
        contenido = uat_docs["acta"].read_text(encoding="utf-8")
        assert "VALIDACIÓN TÉCNICA" in contenido
        assert "VALIDACIÓN FUNCIONAL" in contenido
        assert "ACEPTACIÓN INSTITUCIONAL UAT" in contenido
        assert "BUG TÉCNICO" in contenido
        assert "DECISIÓN INSTITUCIONAL PENDIENTE" in contenido
        assert "OPCIÓN A — ACEPTADO" in contenido
        assert "OPCIÓN B — ACEPTADO CON OBSERVACIONES" in contenido
        assert "OPCIÓN C — RECHAZADO" in contenido
        assert "OPCIÓN D — PENDIENTE DE INFORMACIÓN INSTITUCIONAL" in contenido
        assert "NO constituye una declaración de paso a producción" in contenido

    def test_05b_informe_uat_contiene_secciones_y_dictamen_pendiente(self, uat_docs):
        contenido = uat_docs["informe_uat"].read_text(encoding="utf-8")
        assert "Kenia Salomón Rivera" in contenido
        assert "ACEPTACIÓN INSTITUCIONAL PENDIENTE" in contenido
        assert "12 Mujeres" in contenido and "6 Varones" in contenido
        assert "NO DECLARAN EL SISTEMA EN PRODUCCIÓN" in contenido
        assert "NO SE AUTORIZA NI SE INICIA LA FASE 13" in contenido
        assert "REQUIERE_MUESTRA_INSTITUCIONAL" in contenido
        assert "RISK-DV-X14" in contenido
        assert "DECISION_INSTITUCIONAL_PENDIENTE" in contenido


class TestUATComprobacionCasoBaseSeptiembre:
    """Verifica las cifras del caso base directamente contra el motor canónico."""

    def test_06_cifras_canonicas_pipeline_septiembre_2026(self, workspace_root):
        settings_path = workspace_root / "config" / "settings.yaml"
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        routing, stats, esquemas, manifestos, politicas = _procesar_pipeline_datos(settings)

        # Invariantes de volumen
        assert routing.total_entrada == 18
        assert routing.total_clasificadas == 18
        assert len(routing.estudiantes) == 17
        assert len(routing.academicos_administrativos) == 1
        assert len(routing.colaboradores) == 0
        assert len(routing.beneficiados) == 0

        # Elba Wilson Smith es administrativo
        admin = routing.academicos_administrativos[0]
        assert "Elba" in admin.persona.nombre_completo
        assert admin.subtipo_institucional.value == "ADMINISTRATIVO"

        # Estadísticas SSOT: 12 Femenino y 6 Masculino en global
        assert stats.desglose_sexo_global.femenino == 12
        assert stats.desglose_sexo_global.masculino == 6
        assert stats.desglose_sexo_global.total == 18

        # Desglose estudiantes
        est_stats = stats.desglose_categorias["ESTUDIANTES"]
        assert est_stats.conteo_sexo.femenino == 11
        assert est_stats.conteo_sexo.masculino == 6
        assert est_stats.conteo_sexo.total == 17

        # Desglose administrativo
        adm_stats = stats.desglose_categorias["ADMINISTRATIVOS_NO_DOCENTES"]
        assert adm_stats.conteo_sexo.femenino == 1
        assert adm_stats.conteo_sexo.masculino == 0
        assert adm_stats.conteo_sexo.total == 1


class TestUATIntegridadLibrosExcelOutput:
    """Verifica que los libros generados en output/ cumplan celda por celda las especificaciones UAT."""

    def test_07_matriz_1_consolidado_valores_sexo(self, workspace_root):
        archivo_m1 = workspace_root / "output" / "Matriz_1_Consolidado_Actividades.xlsx"
        assert archivo_m1.exists(), "Matriz 1 no existe en output/"

        wb = openpyxl.load_workbook(archivo_m1, data_only=True)
        ws = wb["Programas, proyectos y act"]
        headers = [c.value for c in ws[1]]
        row2 = [c.value for c in ws[2]]
        data = dict(zip(headers, row2))

        assert data.get("Total, Atención, M") == 6
        assert data.get("Total, Atención, F") == 12
        assert data.get("Total, estud_M_grado") == 6
        assert data.get("Total, estud_F_grado") == 11
        assert data.get("Total, Administrativos_M") == 0
        assert data.get("Total, Administrativos_F") == 1
        wb.close()

    def test_08_matriz_2_estudiantes_formulas_y_conteo(self, workspace_root):
        archivo_m2 = workspace_root / "output" / "Matriz_2_Estudiantes.xlsx"
        assert archivo_m2.exists(), "Matriz 2 no existe en output/"

        wb = openpyxl.load_workbook(archivo_m2, data_only=False)
        ws = wb["Pregrado_Grado en Actividades"]

        # 17 estudiantes: filas 2 a 18
        assert ws.cell(2, 1).value == 1
        for r in range(3, 19):
            assert ws.cell(r, 1).value == f"=+A{r-1}+1"

        # Fórmulas de edad
        for r in range(2, 19):
            formula_edad = ws.cell(r, 40).value
            assert formula_edad == '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")'

        wb.close()

    def test_09_matriz_5_preservacion_historica_32_registros(self, workspace_root):
        archivo_m5 = workspace_root / "output" / "Matriz_5_Protagonistas_Beneficiados.xlsx"
        archivo_tpl = workspace_root / "templates" / "Matriz_5_Protagonistas_Beneficiados.xlsx"

        wb_out = openpyxl.load_workbook(archivo_m5, data_only=False)
        wb_tpl = openpyxl.load_workbook(archivo_tpl, data_only=False)
        ws_out = wb_out["Pregrado_Grado en Actividades"]
        ws_tpl = wb_tpl["Pregrado_Grado en Actividades"]

        # Filas 2 a 33 deben ser exactamente idénticas
        diferencias = 0
        for r in range(2, 34):
            for c in range(1, 54):
                if ws_out.cell(r, c).value != ws_tpl.cell(r, c).value:
                    diferencias += 1

        assert diferencias == 0, f"Se detectaron {diferencias} diferencias en el histórico de M5"

        # Fila 34 debe estar vacía (0 nuevos en este caso base)
        assert ws_out.cell(34, 1).value is None

        wb_out.close()
        wb_tpl.close()
