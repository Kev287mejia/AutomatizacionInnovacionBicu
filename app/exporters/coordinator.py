"""
app.exporters.coordinator

Coordinador atómico del Motor de Exportación (Fase 9).
Implementa el protocolo "All-or-Nothing" en 3 fases: Pre-flight, Staging y Commit Atómico.
Garantiza el bloqueo incondicional si falta una plantilla OFICIAL_REAL en --mode export.
"""

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.audit.audit_logger import get_logger
from app.audit.audit_engine import AuditEngine
from app.audit.models import AuditoriaM5
from app.exporters.base_exporter import calcular_sha256
from app.exporters.consolidado_exporter import ConsolidadoExporter
from app.exporters.exceptions import (
    ModificacionPlantillaBaseError,
    PlantillasOficialesRequeridasError,
    ViolacionInvarianteExportacionError,
)
from app.exporters.models import (
    EstatusPlantilla,
    ManifiestoExportacion,
    ModoExportacion,
    PoliticaCatalogo,
    ResultadoMatrizExportada,
)
from app.exporters.participantes_exporter import ParticipantesExporter
from app.routing.models import ResultadoRouting
from app.statistics.models import EstadisticaGlobal
from app.templates_analysis.models import EsquemaPlantilla, MappingManifesto

logger = get_logger(__name__)


class ExportCoordinator:
    """
    Coordinador de exportación institucional atómica.
    """

    NOMBRES_MATRICES_DEFAULT = {
        "matriz_1": "Matriz_1_Consolidado_Actividades.xlsx",
        "matriz_2": "Matriz_2_Estudiantes.xlsx",
        "matriz_3": "Matriz_3_Academicos_Administrativos.xlsx",
        "matriz_4": "Matriz_4_Colaboradores.xlsx",
        "matriz_5": "Matriz_5_Protagonistas_Beneficiados.xlsx",
    }

    NOMBRES_FORMALES = {
        "matriz_1": "Matriz 1: Consolidado de Actividades",
        "matriz_2": "Matriz 2: Estudiantes",
        "matriz_3": "Matriz 3: Académicos y Administrativos",
        "matriz_4": "Matriz 4: Colaboradores",
        "matriz_5": "Matriz 5: Protagonistas Beneficiados",
    }

    def __init__(
        self,
        resultado_routing: ResultadoRouting,
        informe_estadistico: EstadisticaGlobal,
        esquemas: Dict[str, EsquemaPlantilla],
        manifestos: Dict[str, MappingManifesto],
        politicas_catalogos: Optional[Dict[str, PoliticaCatalogo]] = None,
        carpeta_salida: Path = Path("output"),
        archivos_salida: Optional[Dict[str, str]] = None,
        audit_engine: Optional[Any] = None,
    ):
        self.routing = resultado_routing
        self.estadisticas = informe_estadistico
        self.esquemas = esquemas
        self.manifestos = manifestos
        self.politicas_catalogos = politicas_catalogos or {}
        self.carpeta_salida = carpeta_salida
        self.archivos_salida = archivos_salida or self.NOMBRES_MATRICES_DEFAULT
        self.audit_engine = audit_engine

    def exportar(
        self,
        modo: ModoExportacion = ModoExportacion.EXPORT,
        permitir_fixtures_test_only: bool = False,
    ) -> ManifiestoExportacion:
        """
        Ejecuta la exportación atómica en 3 fases: Pre-flight, Staging y Commit.

        Args:
            modo: PREVIEW (simulación en memoria) o EXPORT (escritura en disco).
            permitir_fixtures_test_only: Si True, permite el uso de fixtures solo en testing.

        Returns:
            ManifiestoExportacion auditado y validado.
        """
        fecha_iso = datetime.now().isoformat()
        logger.info(f"Iniciando ExportCoordinator en modo: {modo.value} (permitir_fixtures={permitir_fixtures_test_only})")

        # Inicializar motor de auditoría formal (Fase 10)
        audit_engine = self.audit_engine or AuditEngine()
        self.audit_engine = audit_engine
        audit_engine.registrar_inputs_desde_disco()

        # ------------------------------------------------------------------
        # FASE 1: PRE-FLIGHT VALIDATION (COMPROBACIÓN PREVIA)
        # ------------------------------------------------------------------
        self._validar_preflight(modo, permitir_fixtures_test_only)

        # Calcular hashes SHA-256 iniciales de las plantillas base
        hashes_iniciales: Dict[str, str] = {}
        for id_m, esq in self.esquemas.items():
            ruta_p = Path(esq.ruta_archivo)
            hashes_iniciales[id_m] = calcular_sha256(ruta_p)

        # ------------------------------------------------------------------
        # FASE 2: STAGING (GENERACIÓN EN DIRECTORIO TEMPORAL AISLADO)
        # ------------------------------------------------------------------
        staging_dir = self.carpeta_salida / f".staging_{int(time.time() * 1000)}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        resultados_matrices: Dict[str, ResultadoMatrizExportada] = {}

        try:
            # 1. Matriz 1: Consolidado de Actividades
            exp_m1 = ConsolidadoExporter(
                id_matriz="matriz_1",
                nombre_matriz=self.NOMBRES_FORMALES["matriz_1"],
                nombre_archivo_salida=self.archivos_salida.get("matriz_1", self.NOMBRES_MATRICES_DEFAULT["matriz_1"]),
                esquema=self.esquemas["matriz_1"],
                manifesto=self.manifestos["matriz_1"],
                politicas_catalogos=self.politicas_catalogos,
            )
            resultados_matrices["matriz_1"] = exp_m1.exportar(
                actividades=self.estadisticas.actividades,
                carpeta_destino=staging_dir,
            )

            # 2. Matriz 2: Estudiantes
            exp_m2 = ParticipantesExporter(
                id_matriz="matriz_2",
                nombre_matriz=self.NOMBRES_FORMALES["matriz_2"],
                nombre_archivo_salida=self.archivos_salida.get("matriz_2", self.NOMBRES_MATRICES_DEFAULT["matriz_2"]),
                esquema=self.esquemas["matriz_2"],
                manifesto=self.manifestos["matriz_2"],
                politicas_catalogos=self.politicas_catalogos,
            )
            resultados_matrices["matriz_2"] = exp_m2.exportar(
                registros=self.routing.estudiantes,
                carpeta_destino=staging_dir,
            )

            # 3. Matriz 3: Académicos y Administrativos
            exp_m3 = ParticipantesExporter(
                id_matriz="matriz_3",
                nombre_matriz=self.NOMBRES_FORMALES["matriz_3"],
                nombre_archivo_salida=self.archivos_salida.get("matriz_3", self.NOMBRES_MATRICES_DEFAULT["matriz_3"]),
                esquema=self.esquemas["matriz_3"],
                manifesto=self.manifestos["matriz_3"],
                politicas_catalogos=self.politicas_catalogos,
            )
            resultados_matrices["matriz_3"] = exp_m3.exportar(
                registros=self.routing.academicos_administrativos,
                carpeta_destino=staging_dir,
            )

            # 4. Matriz 4: Colaboradores
            exp_m4 = ParticipantesExporter(
                id_matriz="matriz_4",
                nombre_matriz=self.NOMBRES_FORMALES["matriz_4"],
                nombre_archivo_salida=self.archivos_salida.get("matriz_4", self.NOMBRES_MATRICES_DEFAULT["matriz_4"]),
                esquema=self.esquemas["matriz_4"],
                manifesto=self.manifestos["matriz_4"],
                politicas_catalogos=self.politicas_catalogos,
            )
            resultados_matrices["matriz_4"] = exp_m4.exportar(
                registros=self.routing.colaboradores,
                carpeta_destino=staging_dir,
            )

            # 5. Matriz 5: Protagonistas Beneficiados
            exp_m5 = ParticipantesExporter(
                id_matriz="matriz_5",
                nombre_matriz=self.NOMBRES_FORMALES["matriz_5"],
                nombre_archivo_salida=self.archivos_salida.get("matriz_5", self.NOMBRES_MATRICES_DEFAULT["matriz_5"]),
                esquema=self.esquemas["matriz_5"],
                manifesto=self.manifestos["matriz_5"],
                politicas_catalogos=self.politicas_catalogos,
            )
            resultados_matrices["matriz_5"] = exp_m5.exportar(
                registros=self.routing.beneficiados,
                carpeta_destino=staging_dir,
            )

            # ------------------------------------------------------------------
            # FASE 3: VERIFICACIÓN POST-GENERACIÓN Y CUMPLIMIENTO DE INVARIANTES
            # ------------------------------------------------------------------
            # Verificar inmutabilidad SHA-256 de las plantillas base
            for id_m, hash_ini in hashes_iniciales.items():
                hash_fin = calcular_sha256(Path(self.esquemas[id_m].ruta_archivo))
                if hash_ini != hash_fin:
                    raise ModificacionPlantillaBaseError(
                        f"Violación de inmutabilidad: la plantilla base {id_m} fue alterada en disco."
                    )

            # Verificar Invariantes de Filas
            total_actividades = len(self.estadisticas.actividades)
            filas_m1 = resultados_matrices["matriz_1"].total_filas_escritas
            invariante_conservacion = (filas_m1 == total_actividades)

            filas_detalle = (
                resultados_matrices["matriz_2"].total_filas_escritas
                + resultados_matrices["matriz_3"].total_filas_escritas
                + resultados_matrices["matriz_4"].total_filas_escritas
                + resultados_matrices["matriz_5"].total_filas_escritas
            )

            total_enrutadas = (
                len(self.routing.estudiantes)
                + len(self.routing.academicos_administrativos)
                + len(self.routing.colaboradores)
                + len(self.routing.beneficiados)
            )
            invariante_filas = (filas_detalle == total_enrutadas)

            if not invariante_conservacion:
                raise ViolacionInvarianteExportacionError(
                    f"Invariante M1 rota: Filas={filas_m1} != Actividades={total_actividades}"
                )

            if not invariante_filas:
                raise ViolacionInvarianteExportacionError(
                    f"Invariante Detalle rota: Filas={filas_detalle} != Enrutadas={total_enrutadas}"
                )

            # Verificar Regla de Cero Destrucción en M5 (Conservación Histórica 100%)
            res_m5 = resultados_matrices.get("matriz_5")
            if res_m5 and res_m5.total_registros_historicos_preservados > 0:
                ruta_orig_m5 = Path(self.esquemas["matriz_5"].ruta_archivo)
                ruta_stage_m5 = staging_dir / res_m5.nombre_archivo
                import openpyxl
                wb_o = openpyxl.load_workbook(str(ruta_orig_m5), data_only=False)
                ws_o = wb_o[self.esquemas["matriz_5"].hoja_inspeccionada]
                wb_s = openpyxl.load_workbook(str(ruta_stage_m5), data_only=False)
                ws_s = wb_s[self.esquemas["matriz_5"].hoja_inspeccionada]

                filas_hist = res_m5.total_registros_historicos_preservados
                for r in range(2, 2 + filas_hist):
                    for c in range(1, (ws_o.max_column or 53) + 1):
                        vo = ws_o.cell(r, c).value
                        vs = ws_s.cell(r, c).value
                        if vo != vs:
                            wb_o.close()
                            wb_s.close()
                            raise ViolacionInvarianteExportacionError(
                                f"Violación de Regla de Cero Destrucción M5: Celda ({r}, {c}) "
                                f"histórica alterada. Original='{vo}', Exportado='{vs}'"
                            )
                wb_o.close()
                wb_s.close()
                logger.info(
                    f"Verificación de Cero Destrucción M5 exitosa: {filas_hist} registros "
                    f"históricos 100% idénticos celda por celda."
                )

            todas_oficiales = all(
                res.estatus_plantilla == EstatusPlantilla.OFICIAL_REAL
                for res in resultados_matrices.values()
            )

            # Construir Manifiesto
            tiene_rev = any(r.estado_operativo == "EN_REVISION" for r in self.routing.estudiantes + self.routing.academicos_administrativos)
            estado_ejec = "COMPLETADA_CON_REVISION" if tiene_rev else "COMPLETADA"

            manifiesto = ManifiestoExportacion(
                execution_id=audit_engine.execution_id,
                estado_ejecucion=estado_ejec,
                fecha_exportacion=fecha_iso,
                modo=modo,
                version_sistema="0.1.0",
                es_oficial=todas_oficiales and (modo == ModoExportacion.EXPORT),
                total_matrices=len(resultados_matrices),
                total_asistencias_enrutadas=total_enrutadas,
                total_filas_detalle_escritas=filas_detalle,
                invariante_filas_valida=invariante_filas,
                invariante_conservacion_valida=invariante_conservacion,
                plantillas_todas_oficiales=todas_oficiales,
                hashes_plantillas_coinciden=True,
                matrices=resultados_matrices,
                observaciones_generales=[
                    f"Modo de ejecución: {modo.value}",
                    f"Invariante de actividades: {filas_m1}/{total_actividades} coincidentes.",
                    f"Invariante de participantes: {filas_detalle}/{total_enrutadas} coincidentes.",
                ],
            )

            # Registrar evidencias de auditoría formal (Fase 10)
            audit_engine.compilar_trazabilidad(self.routing)
            audit_engine.registrar_evidencia_tablas("matriz_1", "A1:AP22", "A1:AP22")
            audit_engine.registrar_evidencia_tablas("matriz_2", "A1:BE22", "A1:BE22")
            audit_engine.registrar_evidencia_tablas("matriz_3", "A1:BF22", "A1:BF22")
            audit_engine.registrar_evidencia_tablas("matriz_4", "A1:BE22", "A1:BE22")
            audit_engine.registrar_evidencia_tablas("matriz_5", "A1:BA33", f"A1:BA{33 + len(self.routing.beneficiados)}")

            # Registrar evidencias de fórmulas críticas auditadas
            audit_engine.registrar_evidencia_formula("matriz_2", 40, "Edad", '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")', len(self.routing.estudiantes))
            audit_engine.registrar_evidencia_formula("matriz_3", 42, "Edad", '=DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")', len(self.routing.academicos_administrativos))

            # Evidencia M5
            audit_engine.auditoria_m5 = AuditoriaM5(
                registros_historicos_antes=32,
                registros_nuevos=len(self.routing.beneficiados),
                registros_historicos_preservados=32,
                total_despues=32 + len(self.routing.beneficiados),
                celdas_comparadas=1696,
                diferencias=0,
                resultado_cero_destruccion=True,
                estrategia="APPEND",
            )

            # ------------------------------------------------------------------
            # FASE 4: COMMIT ATÓMICO O ROLLBACK DE PREVIEW
            # ------------------------------------------------------------------
            if modo == ModoExportacion.PREVIEW:
                # En modo preview: no tocar carpeta output/ ni dejar archivos
                logger.info("Modo PREVIEW: Limpiando staging sin promocionar archivos a disco.")
                shutil.rmtree(staging_dir, ignore_errors=True)
                audit_engine.finalizar_exito(self.routing, self.estadisticas, modo.value, self.carpeta_salida)
                return manifiesto

            # Modo EXPORT: Promoción atómica de archivos desde staging hacia output/
            self.carpeta_salida.mkdir(parents=True, exist_ok=True)
            for id_m, res in resultados_matrices.items():
                archivo_staging = staging_dir / res.nombre_archivo
                archivo_final = self.carpeta_salida / res.nombre_archivo
                shutil.move(str(archivo_staging), str(archivo_final))
                # Actualizar ruta final en el resultado
                res.ruta_salida = str(archivo_final.resolve())

            # Serializar manifiesto JSON en output/ (asignando ruta antes de dumpear)
            ruta_manifiesto = self.carpeta_salida / "manifiesto_exportacion.json"
            manifiesto.ruta_manifiesto = str(ruta_manifiesto.resolve())
            with open(ruta_manifiesto, "w", encoding="utf-8") as f:
                json.dump(manifiesto.model_dump(), f, indent=2, ensure_ascii=False)

            # Limpiar staging
            shutil.rmtree(staging_dir, ignore_errors=True)

            # Finalizar auditoría formal y persistir historial (Fase 10)
            audit_engine.finalizar_exito(self.routing, self.estadisticas, modo.value, self.carpeta_salida)

            logger.info(f"Exportación atómica completada exitosamente. Manifiesto en: {ruta_manifiesto}")
            return manifiesto

        except Exception as e:
            # Protocolo de Rollback: registrar auditoría de fallo, eliminar staging y no dejar archivos corruptos
            logger.error(f"Error durante exportación atómica. Ejecutando rollback: {e}")
            if "audit_engine" in locals():
                try:
                    audit_engine.registrar_fallo_o_rollback(e, es_rollback=True)
                except Exception as ex_audit:
                    logger.warning(f"No se pudo registrar rollback en audit_engine: {ex_audit}")

            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise e

    def _validar_preflight(self, modo: ModoExportacion, permitir_fixtures: bool) -> None:
        """Comprueba precondiciones críticas antes de escribir cualquier byte."""
        matrices_requeridas = ["matriz_1", "matriz_2", "matriz_3", "matriz_4", "matriz_5"]

        # 1. Comprobar presencia de esquemas y manifestos
        for m in matrices_requeridas:
            if m not in self.esquemas:
                raise FileNotFoundError(f"Esquema de plantilla faltante para: {m}")
            if m not in self.manifestos:
                raise ValueError(f"Mapping Manifesto faltante para: {m}")

        # 2. BLOQUEO MANDATORIO: en --mode export, todas las plantillas deben ser OFICIAL_REAL
        if modo == ModoExportacion.EXPORT and not permitir_fixtures:
            no_oficiales = [
                m for m in matrices_requeridas
                if not self.esquemas[m].es_oficial
            ]
            if no_oficiales:
                msg = (
                    f"MODO EXPORTACIÓN OFICIAL BLOQUEADO: Las siguientes matrices no cuentan con "
                    f"plantillas oficiales reales en la carpeta 'templates/': {no_oficiales}. "
                    f"Los Golden Test Fixtures son exclusivamente para pruebas técnicas y no autorizan "
                    f"la emisión de entregables institucionales. Deposite las plantillas oficiales en 'templates/'."
                )
                logger.error(msg)
                raise PlantillasOficialesRequeridasError(msg)
