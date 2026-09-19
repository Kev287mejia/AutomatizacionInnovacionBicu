"""app.application.export_acl.export_acl

Anti-Corruption Layer (ACL) entre Persistencia/Aplicación y los Exportadores Patrimoniales.

Principios arquitectónicos estrictos:
- Cero dependencias de infraestructura concreta: NO importa sqlite3, NO importa openpyxl,
  NO importa python-docx, NO importa customtkinter.
- NO escribe SQL; opera exclusivamente con modelos de dominio y DTOs de aplicación.
- Respeta la regla SSOT: SQLite es la fuente de verdad inmutable; las matrices son salidas derivadas.
- Aplica la abstracción de política OPEN-02 (PoliticaExportacionRevision).
- Garantiza que registros BLOQUEADOS y COLA_REVISION nunca sean inyectados a las matrices oficiales nominales.
- Prepara los datos adaptados para los contratos patrimoniales exactos: ResultadoRouting y EstadisticaGlobal.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.audit.audit_logger import get_logger
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.routing.models import EnrutamientoRegistro, ResumenMatriz, ResultadoRouting
from app.statistics.models import EstadisticaGlobal
from app.statistics.statistics_engine import StatisticsEngine
from app.templates_analysis.reporter import TemplateReporter
from app.exporters.coordinator import ExportCoordinator
from app.exporters.models import ModoExportacion, ManifiestoExportacion
from app.exporters.base_exporter import calcular_sha256
from app.application.dto.export_dtos import (
    ExportacionPreparadaDTO,
    PoliticaExportacionRevision,
)

logger = get_logger(__name__)


class ExportDataset(BaseModel):
    """Contenedor de datos preparados por el ACL para alimentar el motor patrimonial."""

    actividades: List[Activity] = Field(..., description="Actividades agregadas para Matriz 1.")
    personas: List[Person] = Field(..., description="Personas participantes consolidadas.")
    participaciones_originales: List[Participation] = Field(..., description="Participaciones recibidas del SSOT.")
    resultado_routing_exportable: ResultadoRouting = Field(
        ...,
        description="Estructura de routing depurada según la política OPEN-02 y libre de bloqueados."
    )
    resultado_routing_original: ResultadoRouting = Field(
        ...,
        description="Estructura de routing completa emitida por ParticipantRouter (con bloqueados y cola)."
    )
    estadistica_global: EstadisticaGlobal = Field(
        ...,
        description="Métricas calculadas por StatisticsEngine listas para ConsolidadoExporter (M1)."
    )
    registros_cuarentena: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Registros EN_REVISION retenidos si la política fue RETENER_EN_CUARENTENA."
    )
    registros_bloqueados: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Registros BLOQUEADOS excluidos de forma estricta e incondicional de toda matriz."
    )
    registros_cola_revision: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Registros en COLA_REVISION retenidos por categoría desconocida."
    )
    politica_aplicada: PoliticaExportacionRevision = Field(
        ...,
        description="Política institucional de tratamiento de revisiones aplicada."
    )
    dto: ExportacionPreparadaDTO = Field(
        ...,
        description="Resumen cuantitativo del dataset de exportación preparado."
    )

    model_config = {
        "frozen": True,
        "arbitrary_types_allowed": True,
    }


class ExportACL:
    """Anti-Corruption Layer (ACL) para adaptar datos del sistema hacia los exportadores patrimoniales."""

    @classmethod
    def adaptar_y_preparar(
        cls,
        actividades: List[Activity],
        personas: List[Person],
        participaciones: List[Participation],
        resultado_routing: ResultadoRouting,
        politica_revision: PoliticaExportacionRevision = PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
    ) -> ExportDataset:
        """Adapta el estado de routing y las entidades del SSOT aplicando la política de exportación.

        Args:
            actividades: Lista de actividades a exportar.
            personas: Lista de personas asociadas.
            participaciones: Lista completa de participaciones evaluadas.
            resultado_routing: Clasificación determinista emitida por ParticipantRouter.
            politica_revision: Política OPEN-02 para el tratamiento de registros en revisión.

        Returns:
            ExportDataset con los contratos exactos requeridos por los exportadores v1.0.3.

        Raises:
            ValueError: Si la invariante matemática de routing está violada o no hay actividades.
        """
        if not actividades:
            raise ValueError("No se proporcionaron actividades para la preparación de exportación.")

        # 1. Validar invariante de conservación en el routing de origen
        if not resultado_routing.invariante_valida:
            raise ValueError(
                f"No se puede preparar la exportación: invariante de routing inválida. "
                f"Entrada={resultado_routing.total_entrada} != Clasificadas={resultado_routing.total_clasificadas}."
            )

        logger.info(
            f"ExportACL: Iniciando preparación con política {politica_revision.value}. "
            f"Entrada total={resultado_routing.total_entrada} participaciones."
        )

        # 1.1 Garantizar fuente_origen para trazabilidad patrimonial de auditoría
        for p in participaciones:
            if not p.fuente_origen:
                act_fuente = actividades[0].fuente_origen if actividades else None
                p.fuente_origen = act_fuente or "SQLITE_SSOT"

        for reg in (
            resultado_routing.estudiantes
            + resultado_routing.academicos_administrativos
            + resultado_routing.colaboradores
            + resultado_routing.beneficiados
            + resultado_routing.cola_revision
            + resultado_routing.bloqueados
        ):
            if not reg.participacion.fuente_origen:
                reg.participacion.fuente_origen = reg.actividad.fuente_origen or "SQLITE_SSOT"

        # 2. Segregación y gobernanza de registros nominales según política OPEN-02
        estudiantes_exp: List[EnrutamientoRegistro] = []
        academicos_admin_exp: List[EnrutamientoRegistro] = []
        colaboradores_exp: List[EnrutamientoRegistro] = []
        beneficiados_exp: List[EnrutamientoRegistro] = []
        cuarentena: List[EnrutamientoRegistro] = []

        # Listas de control que NUNCA van a matrices nominales
        bloqueados_excluidos = list(resultado_routing.bloqueados)
        cola_revision_excluidos = list(resultado_routing.cola_revision)

        # Mapeo de listas a procesar
        listas_origen = [
            (resultado_routing.estudiantes, estudiantes_exp),
            (resultado_routing.academicos_administrativos, academicos_admin_exp),
            (resultado_routing.colaboradores, colaboradores_exp),
            (resultado_routing.beneficiados, beneficiados_exp),
        ]

        for origen, destino in listas_origen:
            for reg in origen:
                # Blindaje adicional: asegurar que ningún bloqueado se cuele
                if reg.estado_operativo == "BLOQUEADO" or reg.matriz_destino == MatrizDestino.BLOQUEADOS:
                    logger.warning(
                        f"ExportACL: Registro {reg.participacion.id_participacion} con estado BLOQUEADO "
                        f"detectado en lista nominal; retirando hacia bloqueados_excluidos."
                    )
                    bloqueados_excluidos.append(reg)
                    continue

                esta_en_revision = (
                    reg.estado_operativo == "EN_REVISION"
                    or reg.participacion.requiere_revision
                )

                if esta_en_revision:
                    if politica_revision == PoliticaExportacionRevision.RETENER_EN_CUARENTENA:
                        # Política Cuarentena: se retiene fuera de los libros oficiales
                        cuarentena.append(reg)
                    elif politica_revision == PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION:
                        # Política Defecto v1.0.3: se exporta preservando la observación institucional
                        destino.append(reg)
                    elif politica_revision == PoliticaExportacionRevision.EXPORTAR_CON_MARCA:
                        # Política Con Marca: se exporta anteponiendo etiqueta formal
                        reg_marcado = reg.model_copy(deep=True)
                        prefijo = "[EN_REVISION]"
                        if reg_marcado.motivo_enrutamiento and prefijo not in reg_marcado.motivo_enrutamiento:
                            reg_marcado.motivo_enrutamiento = f"{prefijo} {reg_marcado.motivo_enrutamiento}"
                        destino.append(reg_marcado)
                else:
                    # Registro APTO estándar
                    destino.append(reg)

        # 3. Construir ResultadoRouting depurado (exportable)
        total_exportables_nominales = (
            len(estudiantes_exp)
            + len(academicos_admin_exp)
            + len(colaboradores_exp)
            + len(beneficiados_exp)
        )

        resumenes_depurados: Dict[str, ResumenMatriz] = {
            "M2": ResumenMatriz(
                matriz=MatrizDestino.ESTUDIANTES,
                total_participaciones=len(estudiantes_exp),
                total_aptos=sum(1 for r in estudiantes_exp if r.estado_operativo == "APTO"),
                total_en_revision=sum(1 for r in estudiantes_exp if r.estado_operativo == "EN_REVISION"),
                total_femenino=sum(1 for r in estudiantes_exp if r.persona.sexo_normalizado == "FEMENINO"),
                total_masculino=sum(1 for r in estudiantes_exp if r.persona.sexo_normalizado == "MASCULINO"),
            ),
            "M3": ResumenMatriz(
                matriz=MatrizDestino.ACADEMICOS_ADMINISTRATIVOS,
                total_participaciones=len(academicos_admin_exp),
                total_aptos=sum(1 for r in academicos_admin_exp if r.estado_operativo == "APTO"),
                total_en_revision=sum(1 for r in academicos_admin_exp if r.estado_operativo == "EN_REVISION"),
                total_femenino=sum(1 for r in academicos_admin_exp if r.persona.sexo_normalizado == "FEMENINO"),
                total_masculino=sum(1 for r in academicos_admin_exp if r.persona.sexo_normalizado == "MASCULINO"),
            ),
            "M4": ResumenMatriz(
                matriz=MatrizDestino.COLABORADORES,
                total_participaciones=len(colaboradores_exp),
                total_aptos=sum(1 for r in colaboradores_exp if r.estado_operativo == "APTO"),
                total_en_revision=sum(1 for r in colaboradores_exp if r.estado_operativo == "EN_REVISION"),
                total_femenino=sum(1 for r in colaboradores_exp if r.persona.sexo_normalizado == "FEMENINO"),
                total_masculino=sum(1 for r in colaboradores_exp if r.persona.sexo_normalizado == "MASCULINO"),
            ),
            "M5": ResumenMatriz(
                matriz=MatrizDestino.BENEFICIADOS,
                total_participaciones=len(beneficiados_exp),
                total_aptos=sum(1 for r in beneficiados_exp if r.estado_operativo == "APTO"),
                total_en_revision=sum(1 for r in beneficiados_exp if r.estado_operativo == "EN_REVISION"),
                total_femenino=sum(1 for r in beneficiados_exp if r.persona.sexo_normalizado == "FEMENINO"),
                total_masculino=sum(1 for r in beneficiados_exp if r.persona.sexo_normalizado == "MASCULINO"),
            ),
        }

        resultado_routing_exportable = ResultadoRouting(
            estudiantes=estudiantes_exp,
            academicos_administrativos=academicos_admin_exp,
            colaboradores=colaboradores_exp,
            beneficiados=beneficiados_exp,
            cola_revision=[],  # Excluido de exportación nominal
            bloqueados=[],     # Excluido incondicionalmente de exportación
            actividades=actividades,
            total_entrada=total_exportables_nominales,
            total_clasificadas=total_exportables_nominales,
            invariante_valida=True,
            resumenes=resumenes_depurados,
        )

        # 4. Calcular EstadisticaGlobal utilizando el motor estadístico determinista
        # Participaciones a incluir en la estadística
        participaciones_exportables_ids = {
            r.participacion.id_participacion
            for r in (estudiantes_exp + academicos_admin_exp + colaboradores_exp + beneficiados_exp)
        }
        participaciones_para_stats = [
            p for p in participaciones if p.id_participacion in participaciones_exportables_ids
        ]

        estadistica_global = StatisticsEngine.calcular(
            resultado_routing=resultado_routing_exportable,
            actividades=actividades,
            personas=personas,
            participaciones=participaciones_para_stats,
        )

        # 5. Construir DTO de resumen cuantificado
        actividad_principal_id = actividades[0].id_actividad
        dto = ExportacionPreparadaDTO(
            id_actividad=actividad_principal_id,
            politica_revision=politica_revision,
            total_m1_actividades=len(actividades),
            total_m2_estudiantes=len(estudiantes_exp),
            total_m3_academicos_admin=len(academicos_admin_exp),
            total_m4_colaboradores=len(colaboradores_exp),
            total_m5_beneficiados=len(beneficiados_exp),
            total_exportables_nominales=total_exportables_nominales,
            total_cuarentena=len(cuarentena),
            total_cola_revision_excluidos=len(cola_revision_excluidos),
            total_bloqueados_excluidos=len(bloqueados_excluidos),
            invariante_verificada=True,
        )

        logger.info(
            f"ExportACL: Preparación finalizada con éxito. "
            f"Exportables: M1={len(actividades)}, M2={len(estudiantes_exp)}, M3={len(academicos_admin_exp)}, "
            f"M4={len(colaboradores_exp)}, M5={len(beneficiados_exp)}. "
            f"Excluidos: Cuarentena={len(cuarentena)}, Cola={len(cola_revision_excluidos)}, "
            f"Bloqueados={len(bloqueados_excluidos)}."
        )

        return ExportDataset(
            actividades=actividades,
            personas=personas,
            participaciones_originales=participaciones,
            resultado_routing_exportable=resultado_routing_exportable,
            resultado_routing_original=resultado_routing,
            estadistica_global=estadistica_global,
            registros_cuarentena=cuarentena,
            registros_bloqueados=bloqueados_excluidos,
            registros_cola_revision=cola_revision_excluidos,
            politica_aplicada=politica_revision,
            dto=dto,
        )

    @classmethod
    def exportar_matrices_fisicas(
        cls,
        dataset: ExportDataset,
        carpeta_salida: Path,
        modo: str = "EXPORT",
        carpeta_templates: Optional[Path] = None,
        carpeta_fixtures: Optional[Path] = None,
        politicas_catalogos: Optional[Dict[str, Any]] = None,
        audit_engine: Optional[Any] = None,
        permitir_fixtures_test_only: bool = False,
    ) -> ManifiestoExportacion:
        """Ejecuta la exportación física a los libros Excel oficiales M1–M5 mediante el ExportCoordinator patrimonial.

        Garantiza:
        - Staging seguro y atómico (protocolo All-or-Nothing).
        - Verificación de inmutabilidad SHA-256 de las plantillas base.
        - Preservación íntegra de fórmulas, encabezados y estilos.
        - Preservación 100% celda por celda de los 32 registros históricos de M5 (filas 2..33).
        - Exclusión incondicional de registros BLOQUEADOS y COLA_REVISION.

        Args:
            dataset: ExportDataset preparado y verificado por adaptar_y_preparar().
            carpeta_salida: Directorio de destino final para los archivos generados.
            modo: 'PREVIEW' (simulación en staging sin alterar destino) o 'EXPORT' (escritura final).
            carpeta_templates: Ruta al directorio de plantillas oficiales (por defecto 'templates').
            carpeta_fixtures: Ruta opcional de plantillas fixtures para testing.
            politicas_catalogos: Mapeo de políticas institucionales de catálogos.
            audit_engine: Instancia opcional de AuditEngine (Fase 10).
            permitir_fixtures_test_only: Si True, permite el uso de fixtures en testing.

        Returns:
            ManifiestoExportacion formal generado y auditado por el ExportCoordinator.
        """
        salida_path = Path(carpeta_salida)
        templates_path = Path(carpeta_templates) if carpeta_templates else Path("templates")
        fixtures_path = Path(carpeta_fixtures) if carpeta_fixtures else None

        logger.info(
            f"ExportACL: Ejecutando exportación física modo='{modo}' en destino='{salida_path}'. "
            f"Templates='{templates_path}', Fixtures='{fixtures_path}'."
        )

        reporte_plantillas = TemplateReporter.ejecutar_inspeccion_global(
            carpeta_templates=templates_path,
            carpeta_fixtures=fixtures_path,
        )

        modo_enum = (
            ModoExportacion.PREVIEW
            if str(modo).upper() == "PREVIEW"
            else ModoExportacion.EXPORT
        )

        permitir_fixtures = (
            permitir_fixtures_test_only
            or (modo_enum == ModoExportacion.PREVIEW)
            or bool(fixtures_path)
        )

        coordinador = ExportCoordinator(
            resultado_routing=dataset.resultado_routing_exportable,
            informe_estadistico=dataset.estadistica_global,
            esquemas=reporte_plantillas.esquemas,
            manifestos=reporte_plantillas.manifestos,
            politicas_catalogos=politicas_catalogos or {},
            carpeta_salida=salida_path,
            audit_engine=audit_engine,
        )

        manifiesto: ManifiestoExportacion = coordinador.exportar(
            modo=modo_enum,
            permitir_fixtures_test_only=permitir_fixtures,
        )

        return manifiesto
