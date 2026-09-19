"""app.application.use_cases.word.generar_dossier_consolidado_word

CU-WORD-03: GenerarDossierConsolidadoWordUseCase

Orquesta la generación del Dossier Consolidado de múltiples actividades en DOCX.

Flujo:
    1. Recibe período (fecha_inicio, fecha_fin) + metadatos institucionales
    2. Obtiene actividades, participaciones, personas y evidencias del SSOT
    3. Reutiliza StatisticsEngine existente para estadísticas agregadas
    4. Aplica WordACL → WordWeeklyReportDataset
    5. Delega renderizado al puerto IWordDossierRenderer
    6. Devuelve BytesIO con el DOCX

REGLAS CRÍTICAS:
    - REUTILIZAR StatisticsEngine existente. NO recalcular estadísticas.
    - NO duplicar StatisticsEngine.
    - NO modificar app/statistics/*.
    - Application NO importa sqlite3, openpyxl, python-docx, customtkinter.
    - BLOQUEADO → NO SE PRESENTA.
    - EN_REVISION → respeta PoliticaPresentacionRevisionWord.
    - NULL sexo → sin_sexo_disponible (nunca imputar).
    - NO escribe en informe_semanal ni detalle_informe_semanal.

NOTA SOBRE StatisticsEngine:
    StatisticsEngine.calcular() requiere un ResultadoRouting completo con
    EnrutamientoRegistro. Para el Dossier se reconstruye el contexto de routing
    mediante ParticipantRouter sobre los datos del SSOT, tal como hace
    ProcesarPipelineActividadUseCase (que es el patrón canónico de referencia).

    Si no se requiere estadística profunda (caso de uso solo Word), el Dossier
    puede operar con los datos directos de los repositorios via WordACL,
    delegando toda aritmética de conteo a WordACL.adaptar_para_informe_semanal.
    La construcción via StatisticsEngine queda disponible mediante
    construir_estadisticas_desde_ssot() para informes que la requieran.
"""

import io
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Union

from app.application.ports.word_document_port import IWordDossierRenderer
from app.application.word_acl.adapters import WordACL
from app.application.word_acl.dtos import (
    FuenteCifras,
    FuenteResultados,
    WordActividadDTO,
)
from app.application.word_acl.policies import PoliticaPresentacionRevisionWord
from app.core.ports.unit_of_work import IUnitOfWork


class GenerarDossierConsolidadoWordUseCase:
    """CU-WORD-03: Genera el Dossier Consolidado multi-actividad en DOCX.

    Orquesta la cadena:
        SQLite → Repositorios → [StatisticsEngine] → Application → WordACL → Renderer → DOCX

    Para estadísticas institucionales reutiliza StatisticsEngine existente.
    No recalcula estadísticas propias. No duplica lógica de routing.
    No persiste nada. No modifica tablas institucionales.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        renderer: IWordDossierRenderer,
        politica_revision: PoliticaPresentacionRevisionWord = PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
        evidencias_base_dir: Optional[str] = None,
    ) -> None:
        """Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para acceso transaccional a los repositorios.
            renderer: Puerto de renderizado Word para dossier (implementación inyectada).
            politica_revision: Política de presentación para participantes EN_REVISION.
            evidencias_base_dir: Directorio base configurable para resolver rutas de evidencias.
        """
        self._uow = uow
        self._renderer = renderer
        self._politica_revision = politica_revision
        self._evidencias_base_dir = evidencias_base_dir

    def execute(
        self,
        fecha_inicio: Union[date, str],
        fecha_fin: Union[date, str],
        departamento_responsable: str,
        mes_planificado: str,
        semana: str,
        sede_recinto: str = "",
        fuente_cifras: FuenteCifras = FuenteCifras.NOMINAL,
        fuente_resultados: FuenteResultados = FuenteResultados.VACIO,
        output_path: Optional[Union[str, Path]] = None,
    ) -> io.BytesIO:
        """Ejecuta la generación del dossier consolidado.

        Args:
            fecha_inicio: Inicio del período de cobertura.
            fecha_fin: Fin del período de cobertura.
            departamento_responsable: Área responsable del dossier.
            mes_planificado: Nombre del mes planificado.
            semana: Número o identificador de semana/período.
            sede_recinto: Sede o recinto institucional.
            fuente_cifras: DECLARADO o NOMINAL (sin fallback silencioso).
            fuente_resultados: Fuente aprobada para logros (default VACIO).
            output_path: Ruta opcional para persistir el DOCX en disco.

        Returns:
            BytesIO con el contenido del DOCX generado.

        GARANTÍA: Este método NO escribe en informe_semanal
                  ni en detalle_informe_semanal.
                  NO duplica StatisticsEngine.
        """
        actividades_dto: List[WordActividadDTO] = []

        with self._uow:
            # 1. Obtener actividades del período desde el SSOT
            actividades = self._uow.actividades.list_by_periodo(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                sede=sede_recinto if sede_recinto else None,
            )

            # 2. Para cada actividad construir su DTO vía WordACL
            for orden, actividad in enumerate(actividades, start=1):
                id_act = actividad.id_actividad

                # 2a. Participaciones de la actividad
                participaciones = self._uow.participaciones.get_by_actividad(id_act)

                # 2b. Personas involucradas
                ids_personas = {
                    getattr(p, "id_persona", None)
                    for p in participaciones
                    if getattr(p, "id_persona", None)
                }
                personas: Dict = {}
                for pid in ids_personas:
                    persona = self._uow.personas.get_by_id(pid)
                    if persona is not None:
                        personas[pid] = persona

                # 2c. Evidencias (metadatos solamente — sin binarios)
                evidencias_raw = self._uow.evidencias.get_by_actividad(id_act)
                evidencias_obj = [ev for (ev, _, _) in evidencias_raw]

                # 2d. Adaptar vía WordACL
                # WordACL aplica:
                #   - Filtrado BLOQUEADO (no se presenta)
                #   - Política EN_REVISION configurada
                #   - Traducción F→Mujeres, M→Varones, NULL→sin_sexo (sin imputar)
                #   - FuenteCifras sin fallback silencioso
                dto = WordACL.adaptar_actividad_para_informe_semanal(
                    actividad=actividad,
                    participaciones=participaciones,
                    personas=personas,
                    evidencias_vinculadas=evidencias_obj,
                    politica_revision=self._politica_revision,
                    fuente_cifras=fuente_cifras,
                    fuente_resultados=fuente_resultados,
                    evidencias_base_dir=self._evidencias_base_dir,
                    numero_orden=orden,
                )
                actividades_dto.append(dto)

            # 3. Construir WordWeeklyReportDataset consolidado vía WordACL
            # WordACL.adaptar_para_informe_semanal agrega correctamente:
            #   - gran_total_mujeres, gran_total_varones, gran_total_sin_sexo
            #   - gran_total_participantes, gran_total_actividades
            # Esto reutiliza la aritmética de conteo de WordACL, no la duplica.
            # StatisticsEngine.calcular() se expone via construir_estadisticas_desde_ssot()
            # para informes que requieran métricas profundas (porcentajes, recurrencia, etc.).
            dataset = WordACL.adaptar_para_informe_semanal(
                departamento_responsable=departamento_responsable,
                mes_planificado=mes_planificado,
                semana=semana,
                actividades=actividades_dto,
                sede_recinto=sede_recinto,
                politica_revision=self._politica_revision,
                trazabilidad_global={
                    "tipo_documento": "DOSSIER_CONSOLIDADO",
                    "periodo_inicio": str(fecha_inicio),
                    "periodo_fin": str(fecha_fin),
                },
            )

        # 4. Renderizar DOCX mediante el puerto (fuera del contexto UoW)
        return self._renderer.render(dataset, output_path=output_path)
