"""app.quality.validator

Domain Service QualityValidator para el Motor de Calidad Institucional BICU.
Orquesta la ejecución de las reglas Strategy Q-01 a Q-20 sobre el contexto de evaluación
y sintetiza el Value Object QualityAssessment puramente en memoria sin dependencias
de persistencia ni bibliotecas externas (Clean Architecture).
"""

from typing import Dict, List, Optional, Set
from app.audit.audit_logger import get_logger
from app.core.constants.participant_types import CategoriaParticipacion
from app.core.models.activity import Activity
from app.core.models.participation import Participation
from app.core.models.person import Person
from app.quality.models import (
    EstadoGeneralCalidad,
    IValidationRule,
    QualityAssessment,
    QualityContext,
    ValidationFinding,
)
from app.quality.rules import (
    ReglaQ01CedulaVacia,
    ReglaQ02CedulaFormatoDudoso,
    ReglaQ03FechaEnCedula,
    ReglaQ04NombreVacio,
    ReglaQ05SexoIncompatible,
    ReglaQ06SexoAusente,
    ReglaQ07EdadAusente,
    ReglaQ08EdadAtipicaEstamento,
    ReglaQ09CarreraAbreviadaAmbigua,
    ReglaQ10CarreraNoHomologada,
    ReglaQ11EtniaNoCatalogada,
    ReglaQ12CategoriaDesconocida,
    ReglaQ13ParticipacionRepetida,
    ReglaQ14PrevalenciaBeneficiario,
    ReglaQ15IntegridadReferencialHuerfana,
    ReglaQ16TituloDiscordanteWordVsAsistencia,
    ReglaQ17FechaDiscordanteWordVsAsistencia,
    ReglaQ18MetaPlanificadaVsAsistenciasReales,
    ReglaQ19ConteoNarrativoVsFilasNominales,
    ReglaQ20PosibleDuplicadoPersona,
)

logger = get_logger(__name__)


class QualityValidator:
    """Domain Service para orquestar la evaluación pericial de calidad."""

    REGLAS_POR_DEFECTO: List[IValidationRule] = [
        ReglaQ01CedulaVacia(),
        ReglaQ02CedulaFormatoDudoso(),
        ReglaQ03FechaEnCedula(),
        ReglaQ04NombreVacio(),
        ReglaQ05SexoIncompatible(),
        ReglaQ06SexoAusente(),
        ReglaQ07EdadAusente(),
        ReglaQ08EdadAtipicaEstamento(),
        ReglaQ09CarreraAbreviadaAmbigua(),
        ReglaQ10CarreraNoHomologada(),
        ReglaQ11EtniaNoCatalogada(),
        ReglaQ12CategoriaDesconocida(),
        ReglaQ13ParticipacionRepetida(),
        ReglaQ14PrevalenciaBeneficiario(),
        ReglaQ15IntegridadReferencialHuerfana(),
        ReglaQ16TituloDiscordanteWordVsAsistencia(),
        ReglaQ17FechaDiscordanteWordVsAsistencia(),
        ReglaQ18MetaPlanificadaVsAsistenciasReales(),
        ReglaQ19ConteoNarrativoVsFilasNominales(),
        ReglaQ20PosibleDuplicadoPersona(),
    ]

    def __init__(self, reglas: Optional[List[IValidationRule]] = None) -> None:
        """Inicializa el validador con la colección de reglas configuradas."""
        self._reglas = list(reglas) if reglas is not None else list(self.REGLAS_POR_DEFECTO)

    def evaluar_contexto(self, ctx: QualityContext) -> QualityAssessment:
        """Ejecuta todas las reglas registradas sobre el contexto y sintetiza el QualityAssessment."""
        id_actividad = ctx.actividad.id_actividad if ctx.actividad else "ACTIVIDAD_DESCONOCIDA"
        logger.info(f"Iniciando evaluación de calidad para actividad '{id_actividad}' con {len(self._reglas)} reglas.")

        todos_hallazgos: List[ValidationFinding] = []
        for regla in self._reglas:
            try:
                hallazgos_regla = regla.evaluar(ctx)
                todos_hallazgos.extend(hallazgos_regla)
            except Exception as e:
                logger.error(f"Error ejecutando regla {regla.codigo_regla}: {e}")
                todos_hallazgos.append(
                    ValidationFinding(
                        codigo_regla=regla.codigo_regla,
                        severidad="CRITICAL",
                        id_referencia=id_actividad,
                        entidad_afectada="ACTIVIDAD",
                        campo_origen="sistema",
                        valor_detectado=str(e),
                        valor_esperado="Ejecución limpia de regla",
                        mensaje_humano=f"Falla crítica ejecutando regla {regla.codigo_regla}: {e}",
                    )
                )

        # 1. Resumen por severidad
        tot_criticos = sum(1 for h in todos_hallazgos if h.severidad == "CRITICAL")
        tot_errores = sum(1 for h in todos_hallazgos if h.severidad == "ERROR")
        tot_advertencias = sum(1 for h in todos_hallazgos if h.severidad == "WARNING")
        tot_informativos = sum(1 for h in todos_hallazgos if h.severidad == "INFO")

        # 2. Clasificación operativa de participaciones
        # Mapear hallazgos por id_participacion e id_persona
        mapa_hallazgos_part: Dict[str, List[ValidationFinding]] = {}
        for h in todos_hallazgos:
            if h.id_referencia:
                mapa_hallazgos_part.setdefault(h.id_referencia, []).append(h)

        total_aptas = 0
        total_en_revision = 0
        total_cola_revision = 0
        total_bloqueadas = 0

        # Reglas que marcan revisión operativa
        REGLAS_REVISION = {"Q-02", "Q-03", "Q-08", "Q-09", "Q-10", "Q-13", "Q-17", "Q-18", "Q-19", "Q-20"}

        for part in ctx.participaciones:
            h_asoc = mapa_hallazgos_part.get(part.id_participacion, [])
            h_persona = mapa_hallazgos_part.get(part.id_persona, [])
            h_totales = h_asoc + h_persona

            # A. ¿Bloqueado? (Cualquier error crítico o clave huérfana Q-04, Q-15)
            es_bloqueado = any(h.severidad in ("ERROR", "CRITICAL") for h in h_totales)
            if es_bloqueado:
                total_bloqueadas += 1
                continue

            # B. ¿Cola de revisión? (Categoría desconocida Q-12)
            cat = part.categoria_participacion
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            if cat == CategoriaParticipacion.DESCONOCIDO or cat_val == "DESCONOCIDO":
                total_cola_revision += 1
                continue

            # C. ¿En revisión? (Tiene observaciones de revisión)
            tiene_revision = (
                part.requiere_revision
                or any(h.codigo_regla in REGLAS_REVISION for h in h_totales)
            )
            if tiene_revision:
                total_en_revision += 1
            else:
                total_aptas += 1

        total_revisiones = total_en_revision + total_cola_revision

        # 3. Estado general de calidad
        if tot_criticos > 0 or tot_errores > 0 or total_bloqueadas > 0:
            estado_general = EstadoGeneralCalidad.BLOQUEADO
        elif total_revisiones > 0 or any(h.requiere_discrepancia_persistente for h in todos_hallazgos):
            estado_general = EstadoGeneralCalidad.REQUIERE_ACCION
        elif tot_advertencias > 0:
            estado_general = EstadoGeneralCalidad.CON_OBSERVACIONES
        else:
            estado_general = EstadoGeneralCalidad.CONFORME

        return QualityAssessment(
            id_actividad=id_actividad,
            total_actividades_evaluadas=1 if ctx.actividad else 0,
            total_personas_evaluadas=len(ctx.personas),
            total_participaciones_evaluadas=len(ctx.participaciones),
            total_reglas_ejecutadas=len(self._reglas),
            total_criticos=tot_criticos,
            total_errores=tot_errores,
            total_advertencias=tot_advertencias,
            total_revisiones=total_revisiones,
            total_informativos=tot_informativos,
            total_aptas=total_aptas,
            total_en_revision=total_en_revision,
            total_cola_revision=total_cola_revision,
            total_bloqueadas=total_bloqueadas,
            hallazgos=todos_hallazgos,
            estado_general_calidad=estado_general,
        )

    @classmethod
    def evaluar(
        cls,
        actividad: Optional[Activity] = None,
        personas: Optional[List[Person]] = None,
        participaciones: Optional[List[Participation]] = None,
        meta_planificada: Optional[int] = None,
        total_asistentes_declarados_informe: Optional[int] = None,
        titulo_informe: Optional[str] = None,
        fecha_informe: Optional[str] = None,
        fecha_asistencia_declarada: Optional[str] = None,
        catalogo_carreras: Optional[List[str]] = None,
        catalogo_etnias: Optional[List[str]] = None,
        mapeos_sexo: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> QualityAssessment:
        """Punto de entrada estático conveniente para evaluación pericial."""
        ctx = QualityContext(
            actividad=actividad,
            personas=personas or [],
            participaciones=participaciones or [],
            meta_planificada=meta_planificada,
            total_asistentes_declarados_informe=total_asistentes_declarados_informe,
            titulo_informe=titulo_informe,
            fecha_informe=fecha_informe,
            fecha_asistencia_declarada=fecha_asistencia_declarada,
            catalogo_carreras=catalogo_carreras,
            catalogo_etnias=catalogo_etnias,
            mapeos_sexo=mapeos_sexo,
        )
        validator = cls()
        return validator.evaluar_contexto(ctx)
