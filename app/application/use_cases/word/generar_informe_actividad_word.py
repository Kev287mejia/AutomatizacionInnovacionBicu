"""app.application.use_cases.word.generar_informe_actividad_word

CU-WORD-01: GenerarInformeActividadWordUseCase

Orquesta la generación del informe individual de una actividad en formato DOCX.

Flujo:
    1. Recibe id_actividad
    2. Obtiene Activity, Participations, Personas, Evidencias, Discrepancias
       desde los repositorios (via UoW)
    3. Aplica WordACL → WordActividadDTO
    4. Delega renderizado al puerto IWordActividadRenderer
    5. Devuelve BytesIO con el DOCX

REGLAS CRÍTICAS:
    - Application NO importa sqlite3, openpyxl, python-docx, customtkinter.
    - BLOQUEADO → NO SE PRESENTA (filtrado en WordACL.adaptar_actividad_para_informe_semanal).
    - EN_REVISION → respeta PoliticaPresentacionRevisionWord.
    - NULL sexo → sin_sexo_disponible (nunca imputar).
    - NO escribe en informe_semanal ni detalle_informe_semanal.
    - NO recalcula estadísticas; usa datos directos de los repositorios.
"""

import io
from pathlib import Path
from typing import Optional, Union

from app.application.ports.word_document_port import IWordActividadRenderer
from app.application.word_acl.adapters import WordACL
from app.application.word_acl.dtos import FuenteCifras, FuenteResultados
from app.application.word_acl.policies import PoliticaPresentacionRevisionWord
from app.core.ports.unit_of_work import IUnitOfWork


class ActividadNoEncontradaError(Exception):
    """Error semántico: la actividad solicitada no existe en el SSOT."""
    pass


class GenerarInformeActividadWordUseCase:
    """CU-WORD-01: Genera el informe individual de actividad en formato DOCX.

    Orquesta la cadena:
        SQLite → Repositorios → Application → WordACL → Renderer → DOCX

    No persiste nada. No modifica tablas institucionales.
    No calcula estadísticas propias. No duplica lógica de routing.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        renderer: IWordActividadRenderer,
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
        id_actividad: str,
        fuente_cifras: FuenteCifras = FuenteCifras.NOMINAL,
        fuente_resultados: FuenteResultados = FuenteResultados.VACIO,
        valor_resultados: Optional[str] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> io.BytesIO:
        """Ejecuta la generación del informe individual de actividad.

        Args:
            id_actividad: Identificador UUID de la actividad en el SSOT.
            fuente_cifras: DECLARADO o NOMINAL (sin fallback silencioso).
            fuente_resultados: Fuente aprobada para la columna de logros.
            valor_resultados: Texto de logros si fuente_resultados != VACIO.
            output_path: Ruta opcional para persistir el DOCX en disco.

        Returns:
            BytesIO con el contenido del DOCX generado.

        Raises:
            ActividadNoEncontradaError: Si el id_actividad no existe en el SSOT.
        """
        with self._uow:
            # 1. Obtener la actividad
            actividad = self._uow.actividades.get_by_id(id_actividad)
            if actividad is None:
                raise ActividadNoEncontradaError(
                    f"La actividad '{id_actividad}' no existe en el SSOT."
                )

            # 2. Obtener participaciones
            participaciones = self._uow.participaciones.get_by_actividad(id_actividad)

            # 3. Obtener personas involucradas en la actividad
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

            # 4. Obtener evidencias vinculadas (metadatos solamente)
            evidencias_vinculadas_raw = self._uow.evidencias.get_by_actividad(id_actividad)
            # get_by_actividad retorna List[Tuple[Evidencia, orden, seccion]]
            evidencias_obj = [ev for (ev, _, _) in evidencias_vinculadas_raw]

            # 5. Obtener discrepancias / calidad
            discrepancias = self._uow.discrepancias.list_by_actividad(id_actividad)
            tiene_discrepancias = len(discrepancias) > 0
            discrepancias_resumen = [
                getattr(d, "descripcion", str(d)) for d in discrepancias
            ]

            # 6. Adaptar mediante WordACL → WordActividadDTO
            actividad_dto = WordACL.adaptar_actividad_para_informe_semanal(
                actividad=actividad,
                participaciones=participaciones,
                personas=personas,
                evidencias_vinculadas=evidencias_obj,
                politica_revision=self._politica_revision,
                fuente_cifras=fuente_cifras,
                fuente_resultados=fuente_resultados,
                valor_resultados=valor_resultados,
                evidencias_base_dir=self._evidencias_base_dir,
                numero_orden=1,
            )

            # 7. Enriquecer con discrepancias si las hay
            if tiene_discrepancias and not actividad_dto.tiene_discrepancias:
                # Reconstruir con discrepancias (DTO es frozen; usar adaptar_actividad directo)
                actividad_dto = WordACL.adaptar_actividad(
                    id_actividad=actividad_dto.id_actividad,
                    nombre_actividad=actividad_dto.nombre_actividad,
                    fuente_cifras=actividad_dto.fuente_cifras,
                    participantes_sexos=[],  # ya procesados en actividad_dto
                    numero_orden=actividad_dto.numero_orden,
                    eje_vinculado=actividad_dto.eje_vinculado,
                    sede=actividad_dto.sede,
                    departamento_territorial=actividad_dto.departamento_territorial,
                    municipio_territorial=actividad_dto.municipio_territorial,
                    tipo_actividad=actividad_dto.tipo_actividad,
                    fuente_resultados=actividad_dto.fuente_resultados,
                    valor_resultados=actividad_dto.descripcion_logros or None,
                    estamentos=list(actividad_dto.estamentos),
                    evidencias=list(actividad_dto.evidencias),
                    tiene_discrepancias=True,
                    discrepancias_resumen=discrepancias_resumen,
                    politica_revision=self._politica_revision,
                    participantes_en_revision_count=0,
                    trazabilidad=dict(actividad_dto.trazabilidad),
                )

        # 8. Renderizar DOCX mediante el puerto (fuera del contexto UoW)
        return self._renderer.render(actividad_dto, output_path=output_path)
