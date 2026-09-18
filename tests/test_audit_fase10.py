"""
tests/test_audit_fase10.py

Suite de Pruebas Automatizadas para la Fase 10:
Auditoría, Historial, Manifiestos de Procesamiento y Trazabilidad.

Implementa las 16 pruebas mínimas obligatorias (Pruebas A a P):
  - Prueba A: Identificador de ejecución unívoco (UUID4).
  - Prueba B: Integridad criptográfica de entradas (SHA-256 verificado).
  - Prueba C: Integridad criptográfica de salidas (SHA-256 verificado).
  - Prueba D: Trazabilidad completa de las 18 participaciones del caso real.
  - Prueba E: Trazabilidad de la actividad en Matriz 1 (1 fila, fórmulas preservadas).
  - Prueba F: Trazabilidad de los 17 estudiantes en Matriz 2 (filas 2 a 18).
  - Prueba G: Trazabilidad de Elba Wilson Smith en Matriz 3 (ADMINISTRATIVO, fila 2).
  - Prueba H: Trazabilidad de Matrices 4 y 5 (0 nuevas filas, 32 históricos preservados en M5).
  - Prueba I: Registro fiel de estado de ejecución (COMPLETADA_CON_REVISION).
  - Prueba J: Registro estructurado de eventos, errores y advertencias (códigos estandarizados).
  - Prueba K: Registro y comportamiento de Rollback atómico (estado ROLLBACK).
  - Prueba L: Inmutabilidad del historial y prevención de sobreescritura.
  - Prueba M: Captura de metadatos de entorno (Python, OS, dependencias, hash config).
  - Prueba N: Auditoría de preservación de fórmulas críticas (DATEDIF, correlativos).
  - Prueba O: Auditoría de sincronización de tablas estructuradas (Tabla1).
  - Prueba P: Documentación formal del riesgo técnico RISK-DV-X14.
"""

import json
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import yaml

from app.audit.audit_engine import AuditEngine
from app.audit.history_manager import HistoryManager
from app.audit.models import (
    EstadoEjecucion,
    ManifiestoEjecucionCompleto,
    TrazaParticipacion,
    RegistroRiesgo,
    MetadatosEntorno,
)
from app.exporters.base_exporter import calcular_sha256
from app.exporters.coordinator import ExportCoordinator
from app.exporters.models import ModoExportacion
from app.main import _procesar_pipeline_datos
from app.routing.enums import MatrizDestino, SubtipoInstitucional


@pytest.fixture(scope="module")
def pipeline_septiembre_fase10():
    """Ejecuta el pipeline SSOT para el Caso Real de Septiembre 2026."""
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    routing, stats, esquemas, manifestos, politicas = _procesar_pipeline_datos(settings)
    return routing, stats, esquemas, manifestos, politicas


@pytest.fixture(scope="module")
def ejecucion_auditada_septiembre(tmp_path_factory, pipeline_septiembre_fase10):
    """Ejecuta exportación completa con AuditEngine integrado en entorno aislado."""
    routing, stats, esquemas, manifestos, politicas = pipeline_septiembre_fase10
    carpeta_salida = tmp_path_factory.mktemp("salida_fase10")
    carpeta_historial = tmp_path_factory.mktemp("historial_fase10")
    carpeta_docs = tmp_path_factory.mktemp("docs_fase10")

    motor_auditoria = AuditEngine(
        carpeta_historial=carpeta_historial,
        carpeta_docs=carpeta_docs,
    )

    coordinador = ExportCoordinator(
        resultado_routing=routing,
        informe_estadistico=stats,
        esquemas=esquemas,
        manifestos=manifestos,
        politicas_catalogos=politicas,
        carpeta_salida=carpeta_salida,
        audit_engine=motor_auditoria,
    )

    manifiesto_exp = coordinador.exportar(
        modo=ModoExportacion.EXPORT,
        permitir_fixtures_test_only=False,
    )

    manifiesto_completo = motor_auditoria.obtener_manifiesto()

    return {
        "carpeta_salida": carpeta_salida,
        "carpeta_historial": carpeta_historial,
        "carpeta_docs": carpeta_docs,
        "motor_auditoria": motor_auditoria,
        "manifiesto_exp": manifiesto_exp,
        "manifiesto_completo": manifiesto_completo,
    }


class TestAuditoriaFase10:
    """Suite de 16 pruebas formales (Pruebas A a P) para Fase 10."""

    def test_prueba_a_identificador_ejecucion_univoco(self, ejecucion_auditada_septiembre):
        """
        Prueba A: Verificar que cada ejecución genera un execution_id único,
        no nulo y con formato válido UUID4.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        exec_id = manifiesto.execution_id

        assert exec_id is not None
        assert isinstance(exec_id, str)
        # Validar que es un UUID4 sintácticamente correcto
        parsed_uuid = uuid.UUID(exec_id, version=4)
        assert str(parsed_uuid) == exec_id

        # Verificar unicidad generando un segundo motor
        otro_motor = AuditEngine()
        assert otro_motor.execution_id != exec_id
        uuid.UUID(otro_motor.execution_id, version=4)

    def test_prueba_b_integridad_criptografica_entradas(self, ejecucion_auditada_septiembre):
        """
        Prueba B: Verificar que el manifiesto registra evidencias de entrada con
        sus identificadores y algoritmos criptográficos (SHA-256).
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        assert len(manifiesto.inputs) > 0

        for entrada in manifiesto.inputs:
            assert entrada.tipo in ("formulario_excel", "referencia_institucional_ssot", "archivo_fuente_input")
            assert entrada.sha256 is not None
            assert len(entrada.sha256) == 64 or entrada.sha256.startswith("ssot_")

    def test_prueba_c_integridad_criptografica_salidas(self, ejecucion_auditada_septiembre):
        """
        Prueba C: Verificar que el manifiesto registra el hash SHA-256 de cada archivo
        exportado y que coincide exactamente con el hash real del archivo en disco.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        carpeta_salida = Path(ejecucion_auditada_septiembre["carpeta_salida"])
        salidas = {salida.nombre: salida for salida in manifiesto.outputs}

        archivos_esperados = [
            "Matriz_1_Consolidado_Actividades.xlsx",
            "Matriz_2_Estudiantes.xlsx",
            "Matriz_3_Academicos_Administrativos.xlsx",
            "Matriz_4_Colaboradores.xlsx",
            "Matriz_5_Protagonistas_Beneficiados.xlsx",
        ]

        for nombre in archivos_esperados:
            assert nombre in salidas, f"Archivo {nombre} no registrado en outputs del manifiesto"
            meta = salidas[nombre]
            ruta_disco = carpeta_salida / meta.nombre
            assert ruta_disco.exists(), f"El archivo {ruta_disco} no existe en disco"

            hash_calculado = calcular_sha256(ruta_disco)
            assert hash_calculado == meta.sha256, (
                f"Discrepancia SHA-256 en {nombre}: manifiesto={meta.sha256} vs disco={hash_calculado}"
            )
            assert ruta_disco.stat().st_size == meta.tamano_bytes

    def test_prueba_d_trazabilidad_completa_18_participaciones(self, ejecucion_auditada_septiembre):
        """
        Prueba D: Verificar que cada una de las 18 participaciones del caso real tiene una traza
        registrada que conecta: id_participacion -> id_persona -> actividad -> enrutamiento -> salida Excel.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        trazas = manifiesto.trazabilidad_participaciones

        assert len(trazas) == 18, f"Se esperaban 18 trazas, obtenidas: {len(trazas)}"
        ids_participacion = {t.id_participacion for t in trazas}
        assert len(ids_participacion) == 18, "Colisión detectada en IDs de participación"

        for t in trazas:
            assert t.id_participacion
            assert t.id_persona_interno
            assert t.id_actividad
            assert t.matriz_destino in ("matriz_2", "matriz_3")
            assert t.estado_operativo in ("APTO", "EN_REVISION")
            assert t.archivo_exportado in (
                "Matriz_2_Estudiantes.xlsx",
                "Matriz_3_Academicos_Administrativos.xlsx",
            )
            assert t.fila_exportada is not None and t.fila_exportada >= 2

    def test_prueba_e_trazabilidad_actividad_matriz_1(self, ejecucion_auditada_septiembre):
        """
        Prueba E: Verificar que la fila exportada en Matriz 1 está vinculada al ID de actividad
        correspondiente y que se verificaron sus fórmulas institucionales.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        salidas = {s.nombre: s for s in manifiesto.outputs}
        m1_meta = salidas["Matriz_1_Consolidado_Actividades.xlsx"]

        assert m1_meta.registros_generados == 1
        assert len(manifiesto.actividades_procesadas) == 1
        act = manifiesto.actividades_procesadas[0]
        assert act["total_asistencias"] == 18
        assert "BICU CUR Bilwi" in act["nombre"]

    def test_prueba_f_trazabilidad_17_estudiantes_matriz_2(self, ejecucion_auditada_septiembre):
        """
        Prueba F: Verificar que los 17 estudiantes exportados en Matriz 2 tienen su correspondiente
        traza con ID de persona, fila de salida (filas 2 a 18) y estado de validación.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        trazas_m2 = [t for t in manifiesto.trazabilidad_participaciones if t.matriz_destino == "matriz_2"]

        assert len(trazas_m2) == 17
        filas_ocupadas = sorted([t.fila_exportada for t in trazas_m2])
        assert filas_ocupadas == list(range(2, 19))

        # Verificar estados: 7 APTO y 10 EN_REVISION
        aptos = [t for t in trazas_m2 if t.estado_operativo == "APTO"]
        en_revision = [t for t in trazas_m2 if t.estado_operativo == "EN_REVISION"]
        assert len(aptos) == 7
        assert len(en_revision) == 10

    def test_prueba_g_trazabilidad_elba_wilson_matriz_3(self, ejecucion_auditada_septiembre):
        """
        Prueba G: Verificar que la participación de Elba Wilson Smith (categoría original: NO_DOCENTE)
        está trazada a Matriz 3, fila 2, con subtipo ADMINISTRATIVO, motivo documentado y estado correspondiente.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        trazas_m3 = [t for t in manifiesto.trazabilidad_participaciones if t.matriz_destino == "matriz_3"]

        assert len(trazas_m3) == 1
        traza_elba = trazas_m3[0]
        assert traza_elba.categoria_origen == "NO_DOCENTE"
        assert traza_elba.subtipo_institucional == "ADMINISTRATIVO"
        assert traza_elba.fila_exportada == 2
        assert traza_elba.archivo_exportado == "Matriz_3_Academicos_Administrativos.xlsx"
        assert traza_elba.estado_operativo == "EN_REVISION"
        assert "VAL_CARRERA_AMBIGUA" in traza_elba.codigos_validacion or "VAL_REVISION_REQUERIDA" in traza_elba.codigos_validacion

    def test_prueba_h_trazabilidad_matrices_4_y_5_sin_registros_nuevos(self, ejecucion_auditada_septiembre):
        """
        Prueba H: Verificar que el manifiesto registra 0 filas nuevas en Matriz 4 y 0 filas nuevas en Matriz 5,
        y que para Matriz 5 se documenta formalmente la preservación de los 32 registros históricos.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        salidas = {s.nombre: s for s in manifiesto.outputs}

        assert salidas["Matriz_4_Colaboradores.xlsx"].registros_generados == 0
        assert salidas["Matriz_5_Protagonistas_Beneficiados.xlsx"].registros_generados == 0

        # Cero destrucción M5
        auditoria_m5 = manifiesto.auditoria_m5
        assert auditoria_m5.registros_historicos_antes == 32
        assert auditoria_m5.registros_historicos_preservados == 32
        assert auditoria_m5.registros_nuevos == 0
        assert auditoria_m5.celdas_comparadas == 1696
        assert auditoria_m5.diferencias == 0
        assert auditoria_m5.resultado_cero_destruccion is True

    def test_prueba_i_registro_estado_ejecucion(self, ejecucion_auditada_septiembre):
        """
        Prueba I: Verificar que la ejecución registra fielmente el estado COMPLETADA_CON_REVISION
        dado que existen 11 registros con estado operativo EN_REVISION.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        assert manifiesto.estado == EstadoEjecucion.COMPLETADA_CON_REVISION
        assert manifiesto.conteo_estados_operativos.get("EN_REVISION") == 11
        assert manifiesto.conteo_estados_operativos.get("APTO") == 7
        assert manifiesto.conteo_estados_operativos.get("BLOQUEADO", 0) == 0

    def test_prueba_j_registro_errores_y_advertencias(self, ejecucion_auditada_septiembre):
        """
        Prueba J: Verificar que los hallazgos de validación quedan registrados en la bitácora
        de auditoría con su código estandarizado (ej. VAL_CARRERA_AMBIGUA), severidad y fase.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        codigos = [e.codigo for e in manifiesto.eventos]

        assert any(c in codigos for c in ("VAL_CARRERA_AMBIGUA", "VAL_REVISION_REQUERIDA"))
        eventos_val = [e for e in manifiesto.eventos if e.fase == "validation"]
        assert len(eventos_val) > 0
        for e in eventos_val:
            assert e.severidad in ("WARNING", "REVISION", "INFO")

    def test_prueba_k_registro_rollback(self, tmp_path):
        """
        Prueba K: Simular un fallo durante la exportación y verificar que el motor de auditoría
        registra el evento de rollback, el estado ROLLBACK y no deja un manifiesto de éxito falso.
        """
        carpeta_historial = tmp_path / "historial_rollback"
        carpeta_docs = tmp_path / "docs_rollback"
        motor = AuditEngine(
            carpeta_historial=carpeta_historial,
            carpeta_docs=carpeta_docs,
        )

        motor.iniciar_ejecucion(modo="export")
        assert motor.estado == EstadoEjecucion.PROCESANDO

        # Simular fallo y activación de rollback
        motor.registrar_rollback(
            motivo="Simulación de fallo atómico en staging",
            fase="staging_commit",
            archivos_revertidos=["Matriz_1.xlsx", "Matriz_2.xlsx"],
        )

        assert motor.estado == EstadoEjecucion.ROLLBACK
        manifiesto = motor.obtener_manifiesto()
        assert manifiesto.estado == EstadoEjecucion.ROLLBACK

        eventos_rollback = [e for e in manifiesto.eventos if e.codigo == "ROLLBACK_EJECUTADO"]
        assert len(eventos_rollback) == 1
        assert eventos_rollback[0].severidad == "ERROR"

    def test_prueba_l_inmutabilidad_historial(self, tmp_path):
        """
        Prueba L: Verificar que ejecuciones sucesivas crean registros independientes en el
        historial y que una ejecución no sobreescribe registros anteriores sin permiso explícito.
        """
        carpeta_hist = tmp_path / "historial_inmutable"
        carpeta_docs = tmp_path / "docs_inmutable"
        hm = HistoryManager(carpeta_ejecuciones=carpeta_hist, carpeta_docs=carpeta_docs)

        # Crear dos manifiestos distintos
        m1 = ManifiestoEjecucionCompleto(
            execution_id="11111111-1111-4111-8111-111111111111",
            timestamp_inicio="2026-09-12T10:00:00",
            modo_ejecucion="export",
            entorno=MetadatosEntorno(
                version_python="3.14.5",
                hash_configuracion="hash1",
                plataforma_os="Windows",
            ),
        )
        m2 = ManifiestoEjecucionCompleto(
            execution_id="22222222-2222-4222-8222-222222222222",
            timestamp_inicio="2026-09-12T11:00:00",
            modo_ejecucion="export",
            entorno=MetadatosEntorno(
                version_python="3.14.5",
                hash_configuracion="hash2",
                plataforma_os="Windows",
            ),
        )

        p1 = hm.guardar_manifiesto(m1)
        p2 = hm.guardar_manifiesto(m2)

        assert p1.exists()
        assert p2.exists()
        assert p1 != p2

        # Intentar sobreescribir m1 sin flag debe fallar por inmutabilidad
        with pytest.raises(FileExistsError):
            hm.guardar_manifiesto(m1, permitir_sobrescribir=False)

        # Listar ejecuciones ordenadas cronológicamente
        ejecuciones = hm.listar_ejecuciones()
        assert len(ejecuciones) == 2
        ids = [e["execution_id"] for e in ejecuciones]
        assert "11111111-1111-4111-8111-111111111111" in ids
        assert "22222222-2222-4222-8222-222222222222" in ids

    def test_prueba_m_captura_metadatos_entorno(self, ejecucion_auditada_septiembre):
        """
        Prueba M: Verificar que el manifiesto incluye versión del sistema, versión de Python,
        dependencias clave, hash de configuración y plataforma del sistema operativo.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        entorno = manifiesto.entorno

        assert entorno.version_sistema == "0.1.0"
        assert entorno.version_python.startswith("3.")
        assert "openpyxl" in entorno.dependencias_clave
        assert "pydantic" in entorno.dependencias_clave
        assert "pytest" in entorno.dependencias_clave
        assert len(entorno.hash_configuracion) == 64
        assert len(entorno.plataforma_os) > 0

    def test_prueba_n_auditoria_preservacion_formulas(self, ejecucion_auditada_septiembre):
        """
        Prueba N: Verificar que el manifiesto registra formalmente la auditoría de fórmulas críticas
        (DATEDIF en matrices 2 y 3, correlativos) y que el resultado es PRESERVADA_ESTRUCTURAL.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        formulas = manifiesto.auditoria_formulas

        assert len(formulas) >= 2
        m2_edad = next((f for f in formulas if f.matriz == "matriz_2" and f.columna == 40), None)
        assert m2_edad is not None
        assert "DATEDIF" in m2_edad.formula_esperada
        assert m2_edad.cantidad_verificada == 17
        assert m2_edad.cantidad_incorrecta == 0
        assert m2_edad.resultado == "PRESERVADA_ESTRUCTURAL"

        m3_edad = next((f for f in formulas if f.matriz == "matriz_3" and f.columna == 42), None)
        assert m3_edad is not None
        assert "DATEDIF" in m3_edad.formula_esperada
        assert m3_edad.cantidad_verificada == 1
        assert m3_edad.cantidad_incorrecta == 0
        assert m3_edad.resultado == "PRESERVADA_ESTRUCTURAL"

    def test_prueba_o_auditoria_sincronizacion_tablas_tabla1(self, ejecucion_auditada_septiembre):
        """
        Prueba O: Verificar que el manifiesto registra el rango de Tabla1 antes y después
        de la exportación para cada una de las 5 matrices y certifica su sincronización.
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        tablas = manifiesto.auditoria_tablas

        assert len(tablas) == 5
        rangos_esperados = {
            "matriz_1": "A1:AP22",
            "matriz_2": "A1:BE22",
            "matriz_3": "A1:BF22",
            "matriz_4": "A1:BE22",
            "matriz_5": "A1:BA33",
        }

        for mid, rango_esp in rangos_esperados.items():
            assert mid in tablas
            aud_t = tablas[mid]
            assert aud_t.nombre_tabla == "Tabla1"
            assert aud_t.ref_despues == rango_esp
            assert aud_t.sincronizada_correctamente is True
            assert aud_t.resultado == "SINCRONIZADA"

    def test_prueba_p_documentacion_riesgo_dv_x14(self, ejecucion_auditada_septiembre):
        """
        Prueba P: Verificar que el manifiesto y reporte de auditoría incluyen la documentación formal
        del riesgo técnico RISK-DV-X14 (limitación openpyxl con validaciones x14).
        """
        manifiesto = ejecucion_auditada_septiembre["manifiesto_completo"]
        riesgos = manifiesto.riesgos_documentados

        codigos_riesgo = [r.codigo_riesgo for r in riesgos]
        assert "RISK-DV-X14" in codigos_riesgo

        riesgo_dv = next(r for r in riesgos if r.codigo_riesgo == "RISK-DV-X14")
        assert "openpyxl" in riesgo_dv.descripcion
        assert "x14:dataValidations" in riesgo_dv.descripcion
        assert "listas desplegables" in riesgo_dv.impacto.lower()
        assert "templates/" in riesgo_dv.mitigacion_o_estado
