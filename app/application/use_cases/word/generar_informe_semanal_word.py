"""app.application.use_cases.word.generar_informe_semanal_word

CU-WORD-02: GenerarInformeSemanalWordUseCase

Orquesta la generación del Informe Semanal Ejecutivo (Producto B) en formato DOCX.

Flujo:
    1. Recibe período (fecha_inicio, fecha_fin) + metadatos institucionales
    2. Obtiene Activities del período desde el repositorio
    3. Para cada actividad: Participations, Personas, Evidencias, Discrepancias
    4. Aplica WordACL → List[WordActividadDTO] → WordWeeklyReportDataset
    5. Delega renderizado al puerto IWordInformeSemanalRenderer
    6. Devuelve BytesIO con el DOCX

REGLA CRÍTICA:
    GENERAR DOCX ≠ CREAR/MODIFICAR INFORME SEMANAL OPERATIVO

    Este caso de uso NUNCA escribe en:
        - informe_semanal
        - detalle_informe_semanal

    La semántica de esas tablas quedó abierta en OPEN-WORD-03 y
    NO debe ser resuelta dentro de este bloque.

    Otras reglas:
    - BLOQUEADO → NO SE PRESENTA.
    - EN_REVISION → respeta PoliticaPresentacionRevisionWord.
    - NULL sexo → sin_sexo_disponible (nunca imputar).
    - Application NO importa sqlite3, openpyxl, python-docx, customtkinter.
"""

import io
from datetime import date
from pathlib import Path
from typing import List, Optional, Union

from app.application.ports.word_document_port import IWordInformeSemanalRenderer
from app.application.word_acl.adapters import WordACL
from app.application.word_acl.dtos import (
    FuenteCifras,
    FuenteResultados,
    WordActividadDTO,
)
from app.application.word_acl.policies import PoliticaPresentacionRevisionWord
from app.core.ports.unit_of_work import IUnitOfWork


class GenerarInformeSemanalWordUseCase:
    """CU-WORD-02: Genera el Informe Semanal Ejecutivo (Producto B) en DOCX.

    Orquesta la cadena:
        SQLite → Repositorios → Application → WordACL → Renderer → DOCX

    No escribe en informe_semanal ni detalle_informe_semanal.
    No calcula estadísticas propias. No duplica lógica de routing.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        renderer: IWordInformeSemanalRenderer,
        politica_revision: PoliticaPresentacionRevisionWord = PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
        evidencias_base_dir: Optional[str] = None,
    ) -> None:
        """Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para acceso transaccional a los repositorios.
            renderer: Puerto de renderizado Word (implementación inyectada).
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
        """Ejecuta la generación del informe semanal ejecutivo.

        Args:
            fecha_inicio: Inicio del período de cobertura.
            fecha_fin: Fin del período de cobertura.
            departamento_responsable: Área responsable del informe.
            mes_planificado: Nombre del mes planificado.
            semana: Número o identificador de semana.
            sede_recinto: Sede o recinto institucional.
            fuente_cifras: DECLARADO o NOMINAL (sin fallback silencioso).
            fuente_resultados: Fuente aprobada para logros (default VACIO).
            output_path: Ruta opcional para persistir el DOCX en disco.

        Returns:
            BytesIO con el contenido del DOCX generado.

        GARANTÍA: Este método NO escribe en informe_semanal
                  ni en detalle_informe_semanal (OPEN-WORD-03 preservado).
        """
        actividades_dto: List[WordActividadDTO] = []

        with self._uow:
            # 1. Obtener actividades del período
            actividades = self._uow.actividades.list_by_periodo(
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                sede=sede_recinto if sede_recinto else None,
            )

            # 2. Para cada actividad construir su DTO vía WordACL
            for orden, actividad in enumerate(actividades, start=1):
                id_act = actividad.id_actividad

                # 2a. Participaciones
                participaciones = self._uow.participaciones.get_by_actividad(id_act)

                # 2b. Personas
                ids_personas = {
                    getattr(p, "id_persona", None)
                    for p in participaciones
                    if getattr(p, "id_persona", None)
                }
                personas: dict = {}
                for pid in ids_personas:
                    persona = self._uow.personas.get_by_id(pid)
                    if persona is not None:
                        personas[pid] = persona

                # 2c. Evidencias (metadatos solamente)
                evidencias_raw = self._uow.evidencias.get_by_actividad(id_act)
                evidencias_obj = [ev for (ev, _, _) in evidencias_raw]

                # 2d. Adaptar vía WordACL
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

            # 3. Construir WordWeeklyReportDataset
            dataset = WordACL.adaptar_para_informe_semanal(
                departamento_responsable=departamento_responsable,
                mes_planificado=mes_planificado,
                semana=semana,
                actividades=actividades_dto,
                sede_recinto=sede_recinto,
                politica_revision=self._politica_revision,
            )

        # VERIFICACIÓN: este método NO ha escrito en informe_semanal ni detalle_informe_semanal.
        # El dataset fue construido exclusivamente desde los repositorios de dominio.
        # La integración con esas tablas queda abierta (OPEN-WORD-03).

        # 4. Renderizar DOCX mediante el puerto (fuera del contexto UoW)
        return self._renderer.render(dataset, output_path=output_path)
