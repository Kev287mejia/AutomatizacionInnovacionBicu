"""app.infrastructure.word.institutional_docx_adapter

Adaptadores de infraestructura que implementan los puertos Word de la capa Application,
delegando la renderización a los generadores patrimoniales existentes.

REGLAS ARQUITECTÓNICAS:
    - Este módulo SÍ puede importar python-docx (docx), word_consolidator, etc.
    - La capa Application NUNCA importa desde este módulo directamente.
    - La inyección de dependencias se realiza via los puertos abstractos.
    - NO modificar los renderizadores patrimoniales (word_consolidator/*).
    - NO modificar institutional_models.py ni ningún modelo patrimonial.
    - El adaptador es un traductor puro: WordACL DTOs → InformeSemanalInstitucional.

MAPEO DE DTOs (WordACL → Patrimonial):
    WordWeeklyReportDataset
        → InformeSemanalInstitucional
            departamento_responsable   ← dataset.departamento_responsable
            mes_planificado            ← dataset.mes_planificado
            semana                     ← dataset.semana
            actividades                ← [mapear cada WordActividadDTO]

    WordActividadDTO
        → ActividadInstitucional
            protagonistas              ← [WordEstamentoItemDTO → ProtagonistaEstamentoInstitucional]
            totales_actividad          ← ConteoSexoInstitucional(mujeres, varones, total=m+v)
            evidencias                 ← SeccionEvidenciasActividad

    NOTA CRÍTICA sobre sin_sexo_disponible:
        ConteoSexoInstitucional valida estrictamente total == mujeres + varones.
        El campo sin_sexo_disponible existe en el WordACL DTO pero NO en el modelo
        patrimonial (que solo tiene M, V, Total = M+V).
        POR DISEÑO: la pérdida de desagregación de sin_sexo_disponible al pasar al
        modelo patrimonial es intencional y documentada. Se preserva en el DTO de
        transporte. El conteo patrimonial solo refleja los participantes con sexo confirmado.
        Esta decisión está documentada en WordACL.construir_protagonista_institucional().
"""

import io
import uuid
from pathlib import Path
from typing import List, Optional, Union

from app.application.ports.word_document_port import (
    IWordActividadRenderer,
    IWordDossierRenderer,
    IWordInformeSemanalRenderer,
)
from app.application.word_acl.adapters import WordACL
from app.application.word_acl.dtos import (
    WordActividadDTO,
    WordEvidenciaItemDTO,
    WordWeeklyReportDataset,
)
from app.word_consolidator.document.institutional_models import (
    ActividadInstitucional,
    ConteoSexoInstitucional,
    EstadoEvidenciaEnum,
    InformeSemanalInstitucional,
    ItemEvidenciaInstitucional,
    SeccionEvidenciasActividad,
    TipoEvidenciaEnum,
    TrazabilidadActividad,
)
from app.word_consolidator.institutional_docx.generator import InstitutionalDocxGenerator
from app.word_consolidator.institutional_docx.spec import ModoFuenteDatosEnum


def _mapear_tipo_evidencia(tipo_str: str) -> TipoEvidenciaEnum:
    """Traduce el tipo textual de evidencia del DTO al enum patrimonial."""
    tipo_upper = tipo_str.strip().upper()
    if tipo_upper in ("FOTOGRAFIA", "FOTO", "IMAGE", "JPG", "PNG"):
        return TipoEvidenciaEnum.FOTOGRAFIA
    if tipo_upper in ("LISTA_FIRMADA", "REGISTRO_ASISTENCIA", "ASISTENCIA"):
        return TipoEvidenciaEnum.REGISTRO_ASISTENCIA
    if tipo_upper in ("ENLACE_WEB", "ENLACE_MEDIOS", "URL", "WEB"):
        return TipoEvidenciaEnum.ENLACE_MEDIOS
    return TipoEvidenciaEnum.FOTOGRAFIA  # default conservador


def _mapear_estado_evidencia(estado_str: str) -> EstadoEvidenciaEnum:
    """Traduce el estado de disponibilidad del DTO al enum patrimonial."""
    if estado_str.strip().upper() == "NO_DISPONIBLE":
        return EstadoEvidenciaEnum.NO_DISPONIBLE
    if estado_str.strip().upper() == "VINCULADO":
        return EstadoEvidenciaEnum.VINCULADO
    return EstadoEvidenciaEnum.PENDIENTE


def _mapear_evidencias_dto_a_seccion(
    id_actividad: str,
    numero_actividad: int,
    nombre_actividad: str,
    evidencias_dto: List[WordEvidenciaItemDTO],
) -> SeccionEvidenciasActividad:
    """Convierte la lista de WordEvidenciaItemDTO a SeccionEvidenciasActividad patrimonial.

    Clasifica cada evidencia en:
        - fotografias (FOTOGRAFIA)
        - registros_asistencia (LISTA_FIRMADA / REGISTRO_ASISTENCIA)
        - enlaces_publicaciones (ENLACE_WEB / URL)
    """
    fotografias: List[ItemEvidenciaInstitucional] = []
    registros: List[ItemEvidenciaInstitucional] = []
    enlaces: List[ItemEvidenciaInstitucional] = []

    for ev in evidencias_dto:
        tipo_patrimonial = _mapear_tipo_evidencia(ev.tipo_evidencia)
        estado_patrimonial = _mapear_estado_evidencia(ev.estado_disponibilidad)
        referencia = (
            ev.ruta_absoluta_resuelta
            or ev.ruta_relativa
            or ev.ruta_relativa_original
            or ev.id_evidencia
        )
        item = ItemEvidenciaInstitucional(
            id_evidencia=ev.id_evidencia,
            tipo=tipo_patrimonial,
            titulo=ev.titulo or "(Sin título)",
            referencia=referencia or "",
            orden=ev.orden_presentacion,
            descripcion=ev.descripcion_pie,
            estado=estado_patrimonial,
            origen="SSOT_SQLITE",
        )
        if tipo_patrimonial == TipoEvidenciaEnum.FOTOGRAFIA:
            fotografias.append(item)
        elif tipo_patrimonial == TipoEvidenciaEnum.REGISTRO_ASISTENCIA:
            registros.append(item)
        else:
            enlaces.append(item)

    return SeccionEvidenciasActividad(
        id_actividad=id_actividad,
        numero_actividad=numero_actividad,
        nombre_actividad=nombre_actividad,
        fotografias=fotografias,
        registros_asistencia=registros,
        enlaces_publicaciones=enlaces,
    )


def _mapear_actividad_dto_a_institucional(
    actividad_dto: WordActividadDTO,
) -> ActividadInstitucional:
    """Convierte un WordActividadDTO al modelo inmutable ActividadInstitucional.

    NOTA CRÍTICA: ConteoSexoInstitucional valida total == mujeres + varones.
    La cifra sin_sexo_disponible del DTO WordACL NO puede trasladarse al patrimonial
    sin romper la invariante. Por diseño, totales_actividad solo refleja
    mujeres + varones (sin NULL imputados). Esta pérdida de desagregación es
    documentada e intencional (ver WordACL.construir_protagonista_institucional).
    """
    # Protagonistas por estamento
    protagonistas = [
        WordACL.construir_protagonista_institucional(est)
        for est in actividad_dto.estamentos
    ]

    # Totales de actividad: solo mujeres + varones (sin_sexo excluido del patrimonial)
    total_con_sexo = actividad_dto.total_mujeres + actividad_dto.total_varones
    totales = ConteoSexoInstitucional(
        mujeres=actividad_dto.total_mujeres,
        varones=actividad_dto.total_varones,
        total=total_con_sexo,
    )

    # Evidencias
    seccion_evidencias = _mapear_evidencias_dto_a_seccion(
        id_actividad=actividad_dto.id_actividad,
        numero_actividad=actividad_dto.numero_orden,
        nombre_actividad=actividad_dto.nombre_actividad,
        evidencias_dto=list(actividad_dto.evidencias),
    )

    # Trazabilidad mínima desde el DTO
    trazabilidad = TrazabilidadActividad(
        id_actividad=actividad_dto.id_actividad,
        detalles={
            k: str(v)
            for k, v in actividad_dto.trazabilidad.items()
            if isinstance(v, (str, int, float, bool))
        },
    )

    return ActividadInstitucional(
        id_actividad=actividad_dto.id_actividad,
        numero_orden=actividad_dto.numero_orden,
        nombre_actividad=actividad_dto.nombre_actividad,
        eje_vinculado=actividad_dto.eje_vinculado or "",
        descripcion=actividad_dto.descripcion_logros or "",
        sede=actividad_dto.sede or "",
        departamento=actividad_dto.departamento_territorial or "",
        municipio=actividad_dto.municipio_territorial or "",
        tipo_actividad=actividad_dto.tipo_actividad or "",
        protagonistas=protagonistas,
        totales_actividad=totales,
        discrepancias=[],
        evidencias=seccion_evidencias,
        trazabilidad=trazabilidad,
    )


def _dataset_a_informe_institucional(
    dataset: WordWeeklyReportDataset,
) -> InformeSemanalInstitucional:
    """Convierte un WordWeeklyReportDataset al modelo raíz InformeSemanalInstitucional.

    Este es el punto de integración principal entre WordACL y el renderizador patrimonial.
    """
    actividades_institucionales = [
        _mapear_actividad_dto_a_institucional(act_dto)
        for act_dto in dataset.actividades
    ]

    trazabilidad_global = {
        k: str(v)
        for k, v in dataset.trazabilidad_global.items()
        if isinstance(v, (str, int, float, bool))
    }

    return InformeSemanalInstitucional(
        id_informe=dataset.id_informe_semanal or str(uuid.uuid4()),
        departamento_responsable=dataset.departamento_responsable,
        mes_planificado=dataset.mes_planificado,
        semana=dataset.semana,
        actividades=actividades_institucionales,
        trazabilidad_global=trazabilidad_global,
    )


class InstitutionalDocxActividadAdapter(IWordActividadRenderer):
    """Adaptador de infraestructura: renderiza un WordActividadDTO como DOCX individual.

    Envuelve el InstitutionalDocxGenerator patrimonial en un informe
    de una sola actividad. Compatible con la restricción: no modifica el renderer.
    """

    def __init__(
        self,
        modo_fuente: ModoFuenteDatosEnum = ModoFuenteDatosEnum.DECLARADO_M1,
    ) -> None:
        self._generator = InstitutionalDocxGenerator(modo_fuente=modo_fuente)

    def render(
        self,
        actividad_dto: WordActividadDTO,
        output_path: Optional[Union[str, Path]] = None,
    ) -> io.BytesIO:
        """Genera el DOCX de informe individual para una actividad."""
        # Construir un informe de actividad única
        dataset_individual = WordWeeklyReportDataset(
            departamento_responsable=actividad_dto.sede or "BICU",
            mes_planificado="",
            semana="1",
            sede_recinto=actividad_dto.sede or "",
            actividades=[actividad_dto],
            gran_total_actividades=1,
            gran_total_mujeres=actividad_dto.total_mujeres,
            gran_total_varones=actividad_dto.total_varones,
            gran_total_sin_sexo=actividad_dto.sin_sexo_disponible,
            gran_total_participantes=actividad_dto.total_participantes,
        )
        informe = _dataset_a_informe_institucional(dataset_individual)
        return self._generator.generate(informe, output_path=output_path)


class InstitutionalDocxInformeSemanalAdapter(IWordInformeSemanalRenderer):
    """Adaptador de infraestructura: renderiza un WordWeeklyReportDataset como DOCX (Producto B).

    Delega al InstitutionalDocxGenerator patrimonial sin modificarlo.
    """

    def __init__(
        self,
        modo_fuente: ModoFuenteDatosEnum = ModoFuenteDatosEnum.DECLARADO_M1,
    ) -> None:
        self._generator = InstitutionalDocxGenerator(modo_fuente=modo_fuente)

    def render(
        self,
        dataset: WordWeeklyReportDataset,
        output_path: Optional[Union[str, Path]] = None,
    ) -> io.BytesIO:
        """Genera el DOCX del informe semanal ejecutivo (Producto B)."""
        informe = _dataset_a_informe_institucional(dataset)
        return self._generator.generate(informe, output_path=output_path)


class InstitutionalDocxDossierAdapter(IWordDossierRenderer):
    """Adaptador de infraestructura: renderiza un dossier consolidado como DOCX.

    Reutiliza el mismo generator patrimonial con el dataset completo.
    El dossier es conceptualmente un informe semanal multi-actividad ampliado.
    """

    def __init__(
        self,
        modo_fuente: ModoFuenteDatosEnum = ModoFuenteDatosEnum.DECLARADO_M1,
    ) -> None:
        self._generator = InstitutionalDocxGenerator(modo_fuente=modo_fuente)

    def render(
        self,
        dataset: WordWeeklyReportDataset,
        output_path: Optional[Union[str, Path]] = None,
    ) -> io.BytesIO:
        """Genera el DOCX del dossier consolidado."""
        informe = _dataset_a_informe_institucional(dataset)
        return self._generator.generate(informe, output_path=output_path)
