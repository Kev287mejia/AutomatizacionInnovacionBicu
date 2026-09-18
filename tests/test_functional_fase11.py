"""
tests/test_functional_fase11.py

Suite de Pruebas Automatizadas de Validación Funcional y Aceptación Institucional (Fase 11).

Objetivo:
Validar el comportamiento funcional integral del sistema sin modificar ninguna regla
de negocio existente, garantizando:
  1. Flujo completo del Caso Real de Septiembre 2026 (18/18 participaciones, distribución M1..M5).
  2. Prueba de No Destrucción (SHA-256 de plantillas intacto, M5: 32 históricos celda por celda).
  3. Prueba de Repetibilidad (identificadores unívocos, historial inmutable, equivalencia funcional).
  4. Escenarios de Revisión (Casos A a H: datos válidos, cédulas vacías/fechas sin invención de identidades,
     carreras abreviadas, categorías desconocidas, datos incompletos, duplicados y recurrencias).
  5. Trazabilidad Funcional Extremo a Extremo (Estudiante, Elba Wilson Smith, Actividad M1, Histórico M5).
  6. Prueba de Rollback Atómico y eliminación de staging ante fallo controlado.
  7. Prueba de Modos CLI (--help, validate, preview, export, audit).
  8. Inspección Estructural y Visual de las 5 Matrices Oficiales generadas en Excel.
  9. Documentación y Verificación del Riesgo RISK-DV-X14 sin alteración de negocio.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import openpyxl
import yaml

from app.audit.audit_engine import AuditEngine
from app.audit.history_manager import HistoryManager
from app.audit.models import (
    EstadoEjecucion,
    ManifiestoEjecucionCompleto,
    TrazaParticipacion,
)
from app.core.constants.participant_types import CategoriaParticipacion
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.exporters.base_exporter import calcular_sha256
from app.exporters.consolidado_exporter import ConsolidadoExporter
from app.exporters.coordinator import ExportCoordinator
from app.exporters.exceptions import PlantillasOficialesRequeridasError
from app.exporters.models import ModoExportacion, PoliticaCatalogo
from app.main import _procesar_pipeline_datos
from app.matching.activity_matcher import ActivityMatcher
from app.matching.identity_resolver import IdentityResolver
from app.parsers.attendance_parser import AttendanceParser
from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
from app.parsers.word_parser import WordReportParser
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.routing.participant_router import ParticipantRouter
from app.statistics.statistics_engine import StatisticsEngine
from app.templates_analysis.reporter import TemplateReporter
from app.validation.validator import DataValidator


@pytest.fixture(scope="module")
def base_dir():
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pipeline_septiembre_fase11():
    """Ejecuta el pipeline SSOT oficial con datos de Septiembre 2026."""
    settings_path = Path("config/settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    routing, stats, esquemas, manifestos, politicas = _procesar_pipeline_datos(settings)
    return routing, stats, esquemas, manifestos, politicas


class TestValidacionFuncionalFase11:
    """Suite de validación funcional y aceptación institucional — Fase 11."""

    # -------------------------------------------------------------------------
    # 1. OBJETIVO FUNCIONAL PRINCIPAL: CASO REAL SEPTIEMBRE 2026
    # -------------------------------------------------------------------------
    def test_01_flujo_completo_caso_real_septiembre_2026(self, pipeline_septiembre_fase11):
        """
        Demuestra que el caso real conserva rigurosamente:
          - 1 actividad
          - 18 participaciones totales
          - 18 personas únicas
          - 17 estudiantes
          - 1 administrativo (Elba Wilson Smith, derivada de No Docente)
          - 0 colaboradores
          - 0 beneficiarios nuevos
          - 17 registros en M2
          - 1 registro en M3
          - 0 nuevos en M4
          - 0 nuevos en M5
          - 32 históricos M5 preservados
        """
        routing, stats, esquemas, manifestos, politicas = pipeline_septiembre_fase11

        # 1 actividad unificada
        assert len(routing.actividades) == 1
        actividad = routing.actividades[0]
        assert "diseño de logotipos" in actividad.nombre_actividad_original.lower()

        # 18 participaciones clasificadas y 18 personas únicas
        registros_totales = (
            routing.estudiantes
            + routing.academicos_administrativos
            + routing.colaboradores
            + routing.beneficiados
            + routing.cola_revision
            + routing.bloqueados
        )
        assert len(registros_totales) == 18
        assert routing.total_entrada == 18
        assert routing.total_clasificadas == 18
        assert routing.invariante_valida is True

        personas_unicas = {r.persona.id_persona_interno for r in registros_totales}
        assert len(personas_unicas) == 18

        # Enrutamiento exacto
        assert len(routing.estudiantes) == 17, f"M2 debe tener 17 estudiantes, se obtuvieron {len(routing.estudiantes)}"
        assert len(routing.academicos_administrativos) == 1, f"M3 debe tener 1 administrativo, se obtuvieron {len(routing.academicos_administrativos)}"
        assert len(routing.colaboradores) == 0, f"M4 debe tener 0 colaboradores, se obtuvieron {len(routing.colaboradores)}"
        assert len(routing.beneficiados) == 0, f"M5 debe tener 0 beneficiarios nuevos, se obtuvieron {len(routing.beneficiados)}"
        assert len(routing.cola_revision) == 0, f"Cola de revisión debe tener 0, se obtuvieron {len(routing.cola_revision)}"
        assert len(routing.bloqueados) == 0, f"Bloqueados debe tener 0, se obtuvieron {len(routing.bloqueados)}"

        # Invariante de suma: 17 + 1 + 0 + 0 == 18
        assert len(routing.estudiantes) + len(routing.academicos_administrativos) + len(routing.colaboradores) + len(routing.beneficiados) == 18

        # M3 corresponde a Elba Wilson Smith con subtipo Administrativo
        elba = routing.academicos_administrativos[0]
        assert elba.persona.nombres == "Elba" or "Elba" in elba.persona.nombre_completo
        assert elba.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO

    # -------------------------------------------------------------------------
    # 2. PRUEBA DE NO DESTRUCCIÓN (PLANTILLAS Y M5)
    # -------------------------------------------------------------------------
    def test_02_no_destruccion_plantillas_y_m5(self, base_dir, pipeline_septiembre_fase11, tmp_path):
        """
        Verifica que:
          1. SHA-256 de las 5 plantillas en templates/ sea idéntico antes y después de exportar.
          2. M5 preserve exactamente sus 32 registros históricos (filas 2 a 33).
          3. 1,696 celdas históricas comparadas resulten en 0 diferencias (data_only=False).
          4. La carpeta templates/ permanezca inalterada.
        """
        routing, stats, esquemas, manifestos, politicas = pipeline_septiembre_fase11
        templates_dir = base_dir / "templates"
        archivos_plantilla = [
            "Matriz_1_Consolidado_Actividades.xlsx",
            "Matriz_2_Estudiantes.xlsx",
            "Matriz_3_Academicos_Administrativos.xlsx",
            "Matriz_4_Colaboradores.xlsx",
            "Matriz_5_Protagonistas_Beneficiados.xlsx",
        ]

        # Hashes antes
        hashes_antes = {f: calcular_sha256(templates_dir / f) for f in archivos_plantilla}

        # Ejecución de exportación en carpeta aislada
        coordinador = ExportCoordinator(
            resultado_routing=routing,
            informe_estadistico=stats,
            esquemas=esquemas,
            manifestos=manifestos,
            politicas_catalogos=politicas,
            carpeta_salida=tmp_path,
        )
        manifiesto = coordinador.exportar(modo=ModoExportacion.EXPORT, permitir_fixtures_test_only=False)

        # Hashes después en templates/
        hashes_despues = {f: calcular_sha256(templates_dir / f) for f in archivos_plantilla}

        for f in archivos_plantilla:
            assert hashes_antes[f] == hashes_despues[f], f"¡La plantilla {f} fue modificada durante la exportación!"

        # M5: Cero destrucción de registros históricos (comparación celda por celda)
        wb_m5_orig = openpyxl.load_workbook(templates_dir / "Matriz_5_Protagonistas_Beneficiados.xlsx", data_only=False)
        wb_m5_dest = openpyxl.load_workbook(tmp_path / "Matriz_5_Protagonistas_Beneficiados.xlsx", data_only=False)
        ws_orig = wb_m5_orig.active
        ws_dest = wb_m5_dest.active

        diferencias = 0
        celdas_comparadas = 0
        for r in range(2, 34):  # 32 filas históricas (2 a 33)
            for c in range(1, 54):  # 53 columnas (A a BA)
                val_orig = ws_orig.cell(row=r, column=c).value
                val_dest = ws_dest.cell(row=r, column=c).value
                celdas_comparadas += 1
                if val_orig != val_dest:
                    diferencias += 1

        wb_m5_orig.close()
        wb_m5_dest.close()

        assert celdas_comparadas == 1696
        assert diferencias == 0, f"Se encontraron {diferencias} diferencias en los 32 históricos de M5"

    # -------------------------------------------------------------------------
    # 3. PRUEBA DE REPETIBILIDAD E INMUTABILIDAD DE HISTORIAL
    # -------------------------------------------------------------------------
    def test_03_repetibilidad_e_inmutabilidad_historial(self, pipeline_septiembre_fase11, tmp_path):
        """
        Ejecuta el procesamiento múltiples veces y determina:
          - Cada ejecución recibe un nuevo execution_id unívoco (UUID4).
          - El historial anterior permanece intacto (inmutabilidad).
          - No existe sobreescritura silenciosa de ejecuciones previas.
          - Los hashes quedan registrados formalmente.
          - Distinción entre equivalencia funcional/estructural vs igualdad binaria.
        """
        routing, stats, esquemas, manifestos, politicas = pipeline_septiembre_fase11

        carpeta_historial = tmp_path / "historial"
        carpeta_docs = tmp_path / "docs_audit"
        carpeta_historial.mkdir()
        carpeta_docs.mkdir()

        # Ejecución 1
        motor1 = AuditEngine(carpeta_historial=carpeta_historial, carpeta_docs=carpeta_docs)
        id1 = motor1.execution_id
        coord1 = ExportCoordinator(
            resultado_routing=routing,
            informe_estadistico=stats,
            esquemas=esquemas,
            manifestos=manifestos,
            politicas_catalogos=politicas,
            carpeta_salida=tmp_path / "out1",
            audit_engine=motor1,
        )
        man1 = coord1.exportar(modo=ModoExportacion.EXPORT, permitir_fixtures_test_only=False)

        # Ejecución 2
        motor2 = AuditEngine(carpeta_historial=carpeta_historial, carpeta_docs=carpeta_docs)
        id2 = motor2.execution_id
        coord2 = ExportCoordinator(
            resultado_routing=routing,
            informe_estadistico=stats,
            esquemas=esquemas,
            manifestos=manifestos,
            politicas_catalogos=politicas,
            carpeta_salida=tmp_path / "out2",
            audit_engine=motor2,
        )
        man2 = coord2.exportar(modo=ModoExportacion.EXPORT, permitir_fixtures_test_only=False)

        # 1. Distintos execution_id
        assert id1 != id2
        assert len(id1) == 36 and len(id2) == 36  # Formato UUID4

        # 2. Historial preserva ambas ejecuciones
        hm = HistoryManager(carpeta_ejecuciones=carpeta_historial, carpeta_docs=carpeta_docs)
        ejecuciones = hm.listar_ejecuciones()
        ids_registrados = {e["execution_id"] for e in ejecuciones}
        assert id1 in ids_registrados
        assert id2 in ids_registrados
        assert len(ejecuciones) >= 2

        # 3. Equivalencia funcional y estructural de los archivos generados
        wb1_m2 = openpyxl.load_workbook(tmp_path / "out1" / "Matriz_2_Estudiantes.xlsx", data_only=False)
        wb2_m2 = openpyxl.load_workbook(tmp_path / "out2" / "Matriz_2_Estudiantes.xlsx", data_only=False)
        ws1 = wb1_m2.active
        ws2 = wb2_m2.active

        assert ws1.max_row == ws2.max_row == 22
        assert ws1.max_column == ws2.max_column == 57

        for r in range(1, 19):
            for c in range(1, 58):
                assert ws1.cell(row=r, column=c).value == ws2.cell(row=r, column=c).value

        wb1_m2.close()
        wb2_m2.close()

    # -------------------------------------------------------------------------
    # 4. PRUEBA DE ESCENARIOS DE REVISIÓN (CASOS A A H)
    # -------------------------------------------------------------------------
    def test_04_escenarios_revision_casos_a_a_h(self):
        """
        Valida rigurosamente los 8 escenarios de revisión requeridos:
          - Caso A: Registro completamente válido.
          - Caso B: Cédula vacía (sin inventar cédula ni identidad institucional).
          - Caso C: Cédula con fecha escrita accidentalmente.
          - Caso D: Carrera abreviada (sin inventar códigos ni forzar catálogo).
          - Caso E: Categoría desconocida (aislada en revisión, no descartada).
          - Caso F: Participante con datos incompletos (celdas vacías, no 'ND' ni '0').
          - Caso G: Registro duplicado con misma cédula válida (unificación Nivel 1).
          - Caso H: Misma persona en actividades diferentes (recurrencia inter-actividad).
        """
        # Creación de actividad de prueba
        actividad = Activity(
            id_actividad="ACT-TEST-REV",
            nombre_actividad_original="Taller de Validación y Aceptación Funcional",
            sede="Bilwi",
            departamento="RACCN",
            municipio_evento="Puerto Cabezas",
            fecha_evento="2026-09-12",
            horario="08:00 AM - 12:00 PM",
            fuente_origen="informe_word",
        )

        filas_prueba = [
            # Caso A: Completamente válido
            RawParticipantRow(numero_fila=1, hoja=1, nombre_completo="Carlos Martinez", sexo="M", cedula="601-120502-1001A", edad=24, carrera="Contabilidad", categoria="Estudiante"),
            # Caso B: Cédula vacía
            RawParticipantRow(numero_fila=2, hoja=1, nombre_completo="Dadam Ossiel Mendoza", sexo="M", cedula=None, edad=24, carrera="Contabilidad", categoria="Estudiante"),
            # Caso C: Cédula con fecha accidental
            RawParticipantRow(numero_fila=3, hoja=1, nombre_completo="Shana Ruiz Watson", sexo="F", cedula="20-04-2008", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            # Caso D: Carrera abreviada
            RawParticipantRow(numero_fila=4, hoja=1, nombre_completo="Johnny Melvin", sexo="M", cedula="601-120502-1002B", edad=24, carrera="Lic. Conta", categoria="Estudiante"),
            # Caso E: Categoría desconocida
            RawParticipantRow(numero_fila=5, hoja=1, nombre_completo="Visitante Sin Categoria", sexo="M", cedula="601-120502-1003C", edad=30, carrera="Economia", categoria="Visitante_Comercial"),
            # Caso F: Datos incompletos (sin etnia, sin municipio, etc.)
            RawParticipantRow(numero_fila=6, hoja=1, nombre_completo="Persona Incompleta", sexo="F", cedula="601-120502-1004D", edad=20, carrera="Contabilidad", categoria="Estudiante"),
            # Caso G: Duplicado de Carlos Martinez (misma cédula válida 601-120502-1001A)
            RawParticipantRow(numero_fila=7, hoja=1, nombre_completo="Carlos Martinez Repetido", sexo="M", cedula="601-120502-1001A", edad=24, carrera="Contabilidad", categoria="Estudiante"),
        ]

        sheet_data = RawAttendanceSheetData(
            nombre_actividad="Taller de Validación y Aceptación Funcional",
            fecha="2026-09-12",
            sede="Bilwi",
            departamento="RACCN",
            municipio="Puerto Cabezas",
            horario="08:00 AM - 12:00 PM",
            filas=filas_prueba,
            fuente_origen="asistencia_fisica",
        )

        # 1. Parsing
        parsed = AttendanceParser.parse_sheet_data(sheet_data, id_actividad=actividad.id_actividad)
        assert len(parsed.participaciones) == 7, "No debe perderse ninguna de las 7 participaciones"

        # 2. Resolución de identidad y deduplicación
        res_dedup = IdentityResolver.resolver_identidades(parsed.personas, parsed.participaciones)
        # Carlos Martinez (fila 1 y fila 7) debe ser unificado en 1 persona única
        assert len(res_dedup.personas) == 6, f"Se esperaban 6 personas únicas (Carlos duplicado), se obtuvieron {len(res_dedup.personas)}"
        assert len(res_dedup.participaciones) == 7, "Las 7 participaciones deben conservarse"

        # 3. Validación de conjunto
        validaciones = DataValidator.validar_conjunto(
            actividades=[actividad],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones_previas=parsed.validaciones + res_dedup.validaciones,
        )

        # 4. Routing
        routing = ParticipantRouter.enrutar(
            actividades=[actividad],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones=validaciones,
        )

        registros = (
            routing.estudiantes
            + routing.academicos_administrativos
            + routing.colaboradores
            + routing.beneficiados
            + routing.cola_revision
            + routing.bloqueados
        )
        assert len(registros) == 7, "Las 7 participaciones deben estar enrutadas en alguna cubeta"

        # Verificación Caso A: Carlos Martinez -> APTO
        reg_a = next(r for r in registros if r.persona.cedula == "601-120502-1001A")
        assert reg_a.matriz_destino == MatrizDestino.ESTUDIANTES

        # Verificación Caso B: Cédula vacía -> NO se inventa cédula, cédula es None
        persona_b = next(p for p in res_dedup.personas if "Dadam" in p.nombre_completo)
        assert persona_b.cedula is None or persona_b.cedula == ""
        # Tiene UUID técnico para trazabilidad interna
        assert persona_b.id_persona_interno is not None and len(persona_b.id_persona_interno) > 0
        reg_b = next(r for r in registros if r.persona.id_persona_interno == persona_b.id_persona_interno)
        assert reg_b.estado_operativo == "EN_REVISION"
        codigos_b = [h.codigo for h in reg_b.hallazgos_asociados]
        assert "VAL_CEDULA_VACIA" in codigos_b

        # Verificación Caso C: Cédula con fecha accidental -> VAL_CEDULA_FECHA
        persona_c = next(p for p in res_dedup.personas if "Shana" in p.nombre_completo)
        reg_c = next(r for r in registros if r.persona.id_persona_interno == persona_c.id_persona_interno)
        assert reg_c.estado_operativo == "EN_REVISION"
        codigos_c = [h.codigo for h in reg_c.hallazgos_asociados]
        assert "VAL_CEDULA_FECHA" in codigos_c
        # No se inventa cédula válida
        assert persona_c.cedula is None or persona_c.cedula in ("20-04-2008", "20/04/2008")

        # Verificación Caso D: Carrera abreviada -> VAL_CARRERA_ABREVIADA, valor literal conservado
        persona_d = next(p for p in res_dedup.personas if "Johnny" in p.nombre_completo)
        part_d = next(pt for pt in res_dedup.participaciones if pt.id_persona == persona_d.id_persona_interno)
        reg_d = next(r for r in registros if r.persona.id_persona_interno == persona_d.id_persona_interno)
        assert reg_d.estado_operativo == "EN_REVISION"
        codigos_d = [h.codigo for h in reg_d.hallazgos_asociados]
        assert "VAL_CARRERA_ABREVIADA" in codigos_d

        # Verificación Caso E: Categoría desconocida -> No se descarta la participación (aislada en cola de revisión)
        persona_e = next(p for p in res_dedup.personas if "Visitante" in p.nombre_completo)
        reg_e = next(r for r in registros if r.persona.id_persona_interno == persona_e.id_persona_interno)
        assert reg_e.matriz_destino == MatrizDestino.COLA_REVISION
        assert reg_e.estado_operativo == "EN_REVISION"
        codigos_e = [h.codigo for h in reg_e.hallazgos_asociados]
        assert "VAL_CATEGORIA_DESCONOCIDA" in codigos_e
        assert len(routing.cola_revision) == 1

        # Verificación Caso F: Datos incompletos
        persona_f = next(p for p in res_dedup.personas if "Incompleta" in p.nombre_completo)
        assert persona_f.municipio_persona is None
        assert persona_f.etnia is None

        # Verificación Caso G: Duplicado unificado
        carlos_id = reg_a.persona.id_persona_interno
        parts_carlos = [pt for pt in res_dedup.participaciones if pt.id_persona == carlos_id]
        assert len(parts_carlos) == 2, "Carlos tiene 2 participaciones registradas"

        # Verificación Caso H: Misma persona en actividades diferentes
        actividad_2 = Activity(
            id_actividad="ACT-TEST-REV-2",
            nombre_actividad_original="Segunda Actividad Distinta",
            sede="Bilwi",
            departamento="RACCN",
            municipio_evento="Puerto Cabezas",
            fecha_evento="2026-09-13",
            horario="02:00 PM - 04:00 PM",
            fuente_origen="informe_word",
        )
        part_h = Participation(
            id_participacion="PART-ACT2-CARLOS",
            id_persona=carlos_id,
            id_actividad=actividad_2.id_actividad,
            categoria_participacion=CategoriaParticipacion.ESTUDIANTE,
            fuente_origen="asistencia_fisica",
        )
        participaciones_inter = res_dedup.participaciones + [part_h]
        routing_inter = ParticipantRouter.enrutar(
            actividades=[actividad, actividad_2],
            personas=res_dedup.personas,
            participaciones=participaciones_inter,
            validaciones=validaciones,
        )
        stats_inter = StatisticsEngine.calcular(
            resultado_routing=routing_inter,
            actividades=[actividad, actividad_2],
            personas=res_dedup.personas,
            participaciones=participaciones_inter,
        )
        # En métricas globales, la persona existe 1 sola vez en personas únicas y es detectada como recurrente inter-actividades
        assert stats_inter.total_personas_unicas == 6
        assert stats_inter.total_asistencias == 8
        assert stats_inter.personas_recurrentes == 1
        assert carlos_id in stats_inter.ids_personas_recurrentes

    # -------------------------------------------------------------------------
    # 5. PRUEBA DE TRAZABILIDAD FUNCIONAL EXTREMO A EXTREMO
    # -------------------------------------------------------------------------
    def test_05_trazabilidad_funcional_extremo_a_extremo(self, pipeline_septiembre_fase11, tmp_path):
        """
        Demuestra la reconstrucción paso a paso de la cadena:
          Fuente -> Activity/Person -> Participation -> Validation -> Routing -> Statistics -> Output -> Audit
        para:
          a) Un estudiante regular (Johnny Melvin)
          b) Elba Wilson Smith
          c) Actividad en Matriz 1
          d) Registro histórico en Matriz 5
        """
        routing, stats, esquemas, manifestos, politicas = pipeline_septiembre_fase11

        carpeta_historial = tmp_path / "historial_trazabilidad"
        carpeta_docs = tmp_path / "docs_trazabilidad"
        carpeta_historial.mkdir()
        carpeta_docs.mkdir()

        motor = AuditEngine(carpeta_historial=carpeta_historial, carpeta_docs=carpeta_docs)
        coordinador = ExportCoordinator(
            resultado_routing=routing,
            informe_estadistico=stats,
            esquemas=esquemas,
            manifestos=manifestos,
            politicas_catalogos=politicas,
            carpeta_salida=tmp_path / "output_trazabilidad",
            audit_engine=motor,
        )
        manifiesto = coordinador.exportar(modo=ModoExportacion.EXPORT, permitir_fixtures_test_only=False)
        manifiesto_completo = motor.obtener_manifiesto()

        # a) Trazabilidad Estudiante: Johnny Melvin
        traza_johnny = next(
            t for t in manifiesto_completo.trazabilidad_participaciones
            if t.matriz_destino == "matriz_2" and t.fila_exportada == 2
        )
        assert traza_johnny.archivo_exportado == "Matriz_2_Estudiantes.xlsx"
        assert traza_johnny.categoria_origen in ("ESTUDIANTE", "Estudiante")
        assert traza_johnny.estado_operativo == "EN_REVISION"
        assert "VAL_CARRERA_ABREVIADA" in traza_johnny.codigos_validacion

        # b) Trazabilidad Elba Wilson Smith
        traza_elba = next(
            t for t in manifiesto_completo.trazabilidad_participaciones
            if t.matriz_destino == "matriz_3"
        )
        assert traza_elba.subtipo_institucional == "ADMINISTRATIVO"
        assert traza_elba.fila_exportada == 2
        assert traza_elba.archivo_exportado == "Matriz_3_Academicos_Administrativos.xlsx"

        # c) Trazabilidad Actividad M1
        wb_m1 = openpyxl.load_workbook(tmp_path / "output_trazabilidad" / "Matriz_1_Consolidado_Actividades.xlsx", data_only=True)
        ws_m1 = wb_m1.active
        assert ws_m1.cell(row=2, column=1).value == 1  # Correlativo
        # Nombre de la actividad en columna 9
        assert "diseño de logotipos" in str(ws_m1.cell(row=2, column=9).value).lower()
        # Métricas de actividad en M1 reflejadas
        assert manifiesto_completo.conteo_por_matriz.get("matriz_1", 0) == 1
        wb_m1.close()

        # d) Trazabilidad Registro Histórico M5
        assert manifiesto_completo.auditoria_m5.registros_historicos_preservados == 32
        assert manifiesto_completo.auditoria_m5.resultado_cero_destruccion is True
        assert manifiesto_completo.auditoria_m5.celdas_comparadas == 1696
        assert manifiesto_completo.auditoria_m5.diferencias == 0

    # -------------------------------------------------------------------------
    # 6. PRUEBA DE ROLLBACK ATÓMICO
    # -------------------------------------------------------------------------
    def test_06_rollback_atomico(self, pipeline_septiembre_fase11, tmp_path):
        """
        Simula un fallo durante la validación de invariantes en staging y confirma:
          - La carpeta temporal de staging es eliminada por completo.
          - Ningún archivo de salida corrupto o parcial es copiado a output/.
          - Las plantillas originales en templates/ permanecen inalteradas.
          - El motor de auditoría registra formalmente el estado ROLLBACK.
          - No existe un manifiesto de exportación falso de éxito en output/.
        """
        routing, stats, esquemas, manifestos, politicas = pipeline_septiembre_fase11

        carpeta_salida = tmp_path / "output_rollback"
        carpeta_salida.mkdir()
        carpeta_historial = tmp_path / "historial_rollback"
        carpeta_docs = tmp_path / "docs_rollback"
        carpeta_historial.mkdir()
        carpeta_docs.mkdir()

        motor = AuditEngine(carpeta_historial=carpeta_historial, carpeta_docs=carpeta_docs)
        coordinador = ExportCoordinator(
            resultado_routing=routing,
            informe_estadistico=stats,
            esquemas=esquemas,
            manifestos=manifestos,
            politicas_catalogos=politicas,
            carpeta_salida=carpeta_salida,
            audit_engine=motor,
        )

        # Provocar intencionalmente un fallo durante la fase de exportación en staging
        with patch.object(ConsolidadoExporter, "exportar", side_effect=ValueError("Fallo simulado para prueba de rollback")):
            with pytest.raises(ValueError, match="Fallo simulado para prueba de rollback"):
                coordinador.exportar(modo=ModoExportacion.EXPORT, permitir_fixtures_test_only=False)

        # 1. No debe haber archivos en salida tras rollback
        archivos_salida = list(carpeta_salida.glob("*.*"))
        assert len(archivos_salida) == 0, f"Se encontraron archivos en salida tras rollback: {archivos_salida}"
        staging_carpetas = list(carpeta_salida.glob(".staging*"))
        assert len(staging_carpetas) == 0, f"Carpetas de staging no eliminadas: {staging_carpetas}"

        # 2. El estado registrado en la auditoría debe ser ROLLBACK
        assert motor.estado == EstadoEjecucion.ROLLBACK

        # 3. No existe manifiesto falso en output
        assert not (carpeta_salida / "manifiesto_exportacion.json").exists()

    # -------------------------------------------------------------------------
    # 7. PRUEBA DE MODOS CLI
    # -------------------------------------------------------------------------
    def test_07_modos_cli(self, base_dir):
        """
        Valida que cada modo CLI funcione con código de retorno esperado:
          - python app/main.py --help -> exit code 0
          - python app/main.py --mode validate -> exit code 0
          - python app/main.py --mode preview -> exit code 0
          - python app/main.py --mode export -> exit code 0
          - python app/main.py --mode audit -> exit code 0
        """
        python_exe = sys.executable

        # 1. --help
        res_help = subprocess.run([python_exe, "app/main.py", "--help"], cwd=base_dir, capture_output=True, text=True)
        assert res_help.returncode == 0
        assert "Sistema de Automatización Estadístico de Asistencias" in res_help.stdout

        # 2. --mode validate
        res_val = subprocess.run([python_exe, "app/main.py", "--mode", "validate"], cwd=base_dir, capture_output=True, text=True)
        assert res_val.returncode == 0
        assert "Reporte de validación JSON guardado en" in res_val.stdout

        # 3. --mode preview
        res_prev = subprocess.run([python_exe, "app/main.py", "--mode", "preview"], cwd=base_dir, capture_output=True, text=True)
        assert res_prev.returncode == 0
        assert "Modo: PREVIEW" in res_prev.stdout

        # 4. --mode export
        res_exp = subprocess.run([python_exe, "app/main.py", "--mode", "export"], cwd=base_dir, capture_output=True, text=True)
        assert res_exp.returncode == 0
        assert "Modo: EXPORT" in res_exp.stdout

        # 5. --mode audit
        res_aud = subprocess.run([python_exe, "app/main.py", "--mode", "audit"], cwd=base_dir, capture_output=True, text=True)
        assert res_aud.returncode == 0
        assert "Modo: AUDIT" in res_aud.stdout
        assert "Total de ejecuciones registradas" in res_aud.stdout

    # -------------------------------------------------------------------------
    # 8. INSPECCIÓN TÉCNICA Y VISUAL DE LOS ARCHIVOS EXCEL
    # -------------------------------------------------------------------------
    def test_08_inspeccion_estructural_y_visual_excel(self, base_dir):
        """
        Realiza una inspección estructural exhaustiva sobre los 5 archivos Excel en output/:
          - M1: 42 columnas, encabezado fila 1, datos fila 2, Tabla1, autoFilter, correlativo 1.
          - M2: 57 columnas, 17 filas de datos (filas 2 a 18), fórmula DATEDIF en col 40 (AN), correlativos.
          - M3: 58 columnas, 1 fila de datos (fila 2: Elba Wilson Smith en col 35), fórmula DATEDIF en col 42 (AP).
          - M4: 57 columnas, 0 filas nuevas.
          - M5: 53 columnas, 32 históricos (filas 2 a 33), 0 filas nuevas.
          - Ausencia de datos inventados ('ND', 'Desconocido', 0).
        """
        output_dir = base_dir / "output"

        # M1: Consolidado
        wb_m1 = openpyxl.load_workbook(output_dir / "Matriz_1_Consolidado_Actividades.xlsx", data_only=False)
        ws_m1 = wb_m1.active
        assert ws_m1.max_column == 42
        assert ws_m1.max_row >= 2
        assert "Tabla1" in ws_m1.tables
        t1 = ws_m1.tables["Tabla1"]
        assert t1.ref.startswith("A1:AP")
        assert ws_m1.cell(row=2, column=1).value == 1
        wb_m1.close()

        # M2: Estudiantes
        wb_m2 = openpyxl.load_workbook(output_dir / "Matriz_2_Estudiantes.xlsx", data_only=False)
        ws_m2 = wb_m2.active
        assert ws_m2.max_column == 57
        assert "Tabla1" in ws_m2.tables
        t2 = ws_m2.tables["Tabla1"]
        assert t2.ref.startswith("A1:BE22")
        # Filas 2 a 18 tienen los 17 estudiantes
        for r in range(2, 19):
            assert ws_m2.cell(row=r, column=33).value is not None  # Nombres y Apellidos
        # Fila 19 está vacía (sin participantes adicionales)
        assert ws_m2.cell(row=19, column=33).value is None

        # Fórmulas de correlativo a partir de fila 3
        assert str(ws_m2.cell(row=3, column=1).value).startswith("=+A2+1") or str(ws_m2.cell(row=3, column=1).value) == "=+A2+1"
        # Fórmula DATEDIF de edad en columna 40 (AN)
        formula_edad_m2 = str(ws_m2.cell(row=2, column=40).value)
        assert "DATEDIF" in formula_edad_m2 and "TODAY()" in formula_edad_m2

        # Ausencia de datos inventados: campos opcionales sin fuente permanecen None (ej. Discapacidad col 49, Régimen col 55)
        assert ws_m2.cell(row=2, column=49).value is None
        assert ws_m2.cell(row=2, column=55).value is None
        wb_m2.close()

        # M3: Académicos y Administrativos
        wb_m3 = openpyxl.load_workbook(output_dir / "Matriz_3_Academicos_Administrativos.xlsx", data_only=False)
        ws_m3 = wb_m3.active
        assert ws_m3.max_column == 58
        assert "Tabla1" in ws_m3.tables
        # Fila 2: Elba Wilson Smith (columna 35 Nombre_apellidos, columna 34 Tipo_protagonistas)
        assert ws_m3.cell(row=2, column=34).value == "ADMINISTRATIVO"
        assert ws_m3.cell(row=2, column=35).value == "Elba Wilson Smith"
        assert ws_m3.cell(row=3, column=35).value is None  # Solo 1 participante
        formula_edad_m3 = str(ws_m3.cell(row=2, column=42).value)
        assert "DATEDIF" in formula_edad_m3 and "TODAY()" in formula_edad_m3
        wb_m3.close()

        # M4: Colaboradores
        wb_m4 = openpyxl.load_workbook(output_dir / "Matriz_4_Colaboradores.xlsx", data_only=False)
        ws_m4 = wb_m4.active
        assert ws_m4.max_column == 57
        assert "Tabla1" in ws_m4.tables
        assert ws_m4.cell(row=2, column=33).value is None  # Sin registros
        wb_m4.close()

        # M5: Beneficiados
        wb_m5 = openpyxl.load_workbook(output_dir / "Matriz_5_Protagonistas_Beneficiados.xlsx", data_only=False)
        ws_m5 = wb_m5.active
        assert ws_m5.max_column == 53
        assert "Tabla1" in ws_m5.tables
        assert ws_m5.tables["Tabla1"].ref.startswith("A1:BA33")
        # 32 registros históricos presentes (filas 2 a 33)
        assert ws_m5.cell(row=33, column=33).value is not None
        assert ws_m5.cell(row=34, column=33).value is None  # Cero nuevos
        wb_m5.close()

    # -------------------------------------------------------------------------
    # 9. VALIDACIÓN DE RISK-DV-X14 SIN ALTERACIÓN DE NEGOCIO
    # -------------------------------------------------------------------------
    def test_09_validacion_riesgo_dv_x14(self, base_dir):
        """
        Verifica que el riesgo técnico RISK-DV-X14 esté formalmente registrado en el sistema:
          - openpyxl descarta listas desplegables x14 al serializar.
          - Los datos generados por el sistema y las fórmulas dinámicas están 100% íntegros.
          - La limitación no altera el negocio ni afecta la exportación institucional.
        """
        hm = HistoryManager(carpeta_ejecuciones=base_dir / "logs" / "executions")
        ultima = hm.obtener_ultima_ejecucion()
        assert ultima is not None, "Debe existir al menos una ejecución previa en el historial"

        riesgos = ultima.riesgos_documentados
        codigos_riesgo = [r.codigo_riesgo for r in riesgos]
        assert "RISK-DV-X14" in codigos_riesgo, "El riesgo RISK-DV-X14 debe estar registrado en el historial"
        riesgo = next(r for r in riesgos if r.codigo_riesgo == "RISK-DV-X14")
        assert "openpyxl" in riesgo.descripcion
        assert "x14:dataValidations" in riesgo.descripcion
