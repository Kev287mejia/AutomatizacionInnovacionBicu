"""Capa de adaptacion (ACL) hacia contratos de presentacion Word.

Modulo que transforma datos de dominio/aplicacion hacia los contratos
consumibles por los renderizadores de documentos institucionales.
Opera como adaptador puro: no persiste, no rutea, no resuelve identidades.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.application.word_acl.policies import PoliticaPresentacionRevisionWord
from app.application.word_acl.dtos import (
    FuenteCifras,
    FuenteResultados,
    WordEstamentoItemDTO,
    WordEvidenciaItemDTO,
    WordActividadDTO,
    WordWeeklyReportDataset,
)
from app.word_consolidator.document.institutional_models import (
    TipoEstamentoInstitucional,
    ConteoSexoInstitucional,
    ProtagonistaEstamentoInstitucional,
)

# Etiquetas visibles diferenciadas por origen de cifras
_ETIQUETAS_FUENTE_CIFRAS: Dict[FuenteCifras, str] = {
    FuenteCifras.DECLARADO: "Cifra Declarada (M1)",
    FuenteCifras.NOMINAL: "Asistencia Efectiva Registrada",
}

# Denominaciones institucionales visibles para estamentos
_DENOMINACIONES_ESTAMENTO: Dict[str, str] = {
    "ESTUDIANTE": "Estudiantes",
    "ESTUDIANTES": "Estudiantes",
    "ACADEMICO": "Académicos",
    "ADMINISTRATIVO": "Administrativos",
    "PERSONAL_ADMINISTRATIVO": "Personal Administrativo",
    "ACADEMICO_ADMINISTRATIVO": "Académicos y Administrativos",
    "MAESTRAS_Y_MAESTROS": "Maestras y Maestros",
    "COLABORADOR": "Colaboradores",
    "COLABORADORES": "Colaboradores",
    "BENEFICIADO": "Protagonistas Beneficiados",
    "BENEFICIARIOS_POBLADORES": "Beneficiarios Pobladores",
}

_MAPEO_TIPO_ESTAMENTO_INSTITUCIONAL: Dict[str, TipoEstamentoInstitucional] = {
    "ESTUDIANTE": TipoEstamentoInstitucional.ESTUDIANTES,
    "ESTUDIANTES": TipoEstamentoInstitucional.ESTUDIANTES,
    "ADMINISTRATIVO": TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO,
    "PERSONAL_ADMINISTRATIVO": TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO,
    "ACADEMICO": TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS,
    "MAESTRAS_Y_MAESTROS": TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS,
    "COLABORADOR": TipoEstamentoInstitucional.COLABORADORES,
    "COLABORADORES": TipoEstamentoInstitucional.COLABORADORES,
    "BENEFICIADO": TipoEstamentoInstitucional.BENEFICIARIOS_POBLADORES,
    "BENEFICIARIOS_POBLADORES": TipoEstamentoInstitucional.BENEFICIARIOS_POBLADORES,
}


class WordACL:
    """Adaptador de integracion hacia la presentacion institucional Word.

    Adapta estructuras de aplicacion a contratos de presentacion sin mutar
    las entidades originales ni modificar datos de almacenamiento.
    """

    @staticmethod
    def traducir_sexo_sqlite_a_word(sexo_valor: Optional[str]) -> str:
        """Traduce el valor de sexo al dominio de presentacion.

        Regla canonica:
          'F' o 'FEMENINO' -> 'MUJERES'
          'M' o 'MASCULINO' -> 'VARONES'
          None u otro -> 'SIN_SEXO'
        """
        if not sexo_valor:
            return "SIN_SEXO"
        s = str(sexo_valor).strip().upper()
        if s in ("F", "FEMENINO"):
            return "MUJERES"
        if s in ("M", "MASCULINO"):
            return "VARONES"
        return "SIN_SEXO"

    @classmethod
    def adaptar_estamento(
        cls,
        estamento_tipo: str,
        participantes_con_sexo: List[Optional[str]],
        orden_presentacion: int = 1,
        denominacion_visible: Optional[str] = None,
        politica_revision: PoliticaPresentacionRevisionWord = PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
        sexos_excluidos_por_revision: Optional[List[Optional[str]]] = None,
    ) -> WordEstamentoItemDTO:
        """Adapta una agrupacion de participantes a WordEstamentoItemDTO.

        Aplica la traduccion canonica:
          F -> mujeres
          M -> varones
          None -> sin_sexo_disponible
        """
        mujeres = 0
        varones = 0
        sin_sexo = 0

        for sexo in participantes_con_sexo:
            cat = cls.traducir_sexo_sqlite_a_word(sexo)
            if cat == "MUJERES":
                mujeres += 1
            elif cat == "VARONES":
                varones += 1
            else:
                sin_sexo += 1

        total = mujeres + varones + sin_sexo
        denom = denominacion_visible or _DENOMINACIONES_ESTAMENTO.get(
            estamento_tipo.upper(), estamento_tipo
        )

        return WordEstamentoItemDTO(
            estamento_tipo=estamento_tipo,
            denominacion_visible=denom,
            mujeres=mujeres,
            varones=varones,
            sin_sexo_disponible=sin_sexo,
            total_participantes=total,
            orden_presentacion=orden_presentacion,
        )

    @classmethod
    def construir_protagonista_institucional(
        cls,
        word_estamento_item: WordEstamentoItemDTO,
    ) -> ProtagonistaEstamentoInstitucional:
        """Construye un ProtagonistaEstamentoInstitucional a partir de WordEstamentoItemDTO.

        Respeta el contrato patrimonial: ConteoSexoInstitucional valida
        que total == mujeres + varones. Por ello, la cifra sin_sexo_disponible
        se excluye de dicho desglose para preservar la consistencia aritmetica
        estricta requerida por el modelo patrimonial.
        """
        tipo_enum = _MAPEO_TIPO_ESTAMENTO_INSTITUCIONAL.get(
            word_estamento_item.estamento_tipo.upper(),
            TipoEstamentoInstitucional.COLABORADORES,
        )

        conteo = ConteoSexoInstitucional(
            mujeres=word_estamento_item.mujeres,
            varones=word_estamento_item.varones,
            total=word_estamento_item.mujeres + word_estamento_item.varones,
        )

        return ProtagonistaEstamentoInstitucional(
            estamento_tipo=tipo_enum,
            denominacion_visible=word_estamento_item.denominacion_visible,
            conteo_presentacion=conteo,
            orden_presentacion=word_estamento_item.orden_presentacion,
        )

    @classmethod
    def adaptar_evidencia(
        cls,
        id_evidencia: str,
        id_actividad: Optional[str] = "",
        titulo: str = "",
        tipo_evidencia: str = "FOTO",
        ruta_relativa: Optional[str] = None,
        hash_sha256: Optional[str] = None,
        orden_presentacion: int = 1,
        seccion_informe: str = "GALERIA",
        evidencias_base_dir: Optional[str] = None,
    ) -> WordEvidenciaItemDTO:
        """Adapta metadatos de evidencia a WordEvidenciaItemDTO.

        Sin binarios. La ruta relativa original se preserva. La ruta absoluta
        se resuelve unicamente si se especifica la base configurable.
        """
        existe_fisicamente: Optional[bool] = None
        ruta_abs_str: Optional[str] = None
        estado = "VINCULADO"

        if ruta_relativa is not None and evidencias_base_dir is not None:
            try:
                p = Path(evidencias_base_dir) / ruta_relativa
                existe_fisicamente = p.exists()
                if existe_fisicamente:
                    ruta_abs_str = str(p)
                    estado = "VINCULADO"
                else:
                    estado = "NO_DISPONIBLE"
            except Exception:
                existe_fisicamente = False
                estado = "NO_DISPONIBLE"

        return WordEvidenciaItemDTO(
            id_evidencia=id_evidencia,
            id_actividad=id_actividad or "",
            titulo=titulo,
            tipo_evidencia=tipo_evidencia,
            orden_presentacion=orden_presentacion,
            seccion_informe=seccion_informe,
            ruta_relativa=ruta_relativa,
            ruta_relativa_original=ruta_relativa,
            ruta_absoluta_resuelta=ruta_abs_str,
            hash_sha256=hash_sha256,
            estado_disponibilidad=estado,
            existe_fisicamente=existe_fisicamente,
        )

    @classmethod
    def adaptar_actividad(
        cls,
        id_actividad: str,
        nombre_actividad: str,
        fuente_cifras: FuenteCifras,
        participantes_sexos: List[Optional[str]],
        numero_orden: int = 1,
        eje_vinculado: Optional[str] = None,
        sede: Optional[str] = None,
        departamento_territorial: Optional[str] = None,
        municipio_territorial: Optional[str] = None,
        tipo_actividad: Optional[str] = None,
        fuente_resultados: FuenteResultados = FuenteResultados.VACIO,
        valor_resultados: Optional[str] = None,
        estamentos: Optional[List[WordEstamentoItemDTO]] = None,
        evidencias: Optional[List[WordEvidenciaItemDTO]] = None,
        tiene_discrepancias: bool = False,
        discrepancias_resumen: Optional[List[str]] = None,
        politica_revision: PoliticaPresentacionRevisionWord = PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
        participantes_en_revision_count: int = 0,
        trazabilidad: Optional[Dict[str, Any]] = None,
    ) -> WordActividadDTO:
        """Adapta una actividad con sus politicas explicitas hacia WordActividadDTO."""
        etiqueta_fuente = _ETIQUETAS_FUENTE_CIFRAS[fuente_cifras]

        if fuente_resultados == FuenteResultados.VACIO:
            descripcion_logros = ""
        else:
            descripcion_logros = valor_resultados or ""

        total_mujeres = 0
        total_varones = 0
        total_sin_sexo = 0
        for sexo in participantes_sexos:
            cat = cls.traducir_sexo_sqlite_a_word(sexo)
            if cat == "MUJERES":
                total_mujeres += 1
            elif cat == "VARONES":
                total_varones += 1
            else:
                total_sin_sexo += 1
        total_participantes = total_mujeres + total_varones + total_sin_sexo

        observaciones_calidad: List[str] = []
        if total_sin_sexo > 0:
            observaciones_calidad.append(
                f"{total_sin_sexo} participante(s) sin sexo disponible en actividad '{nombre_actividad}'."
            )
        if fuente_resultados == FuenteResultados.VACIO:
            observaciones_calidad.append(
                f"Columna DESCRIPCIÓN/LOGROS sin fuente aprobada en actividad '{nombre_actividad}'."
            )

        observaciones_revision: List[str] = []
        if participantes_en_revision_count > 0:
            if politica_revision == PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION:
                observaciones_revision.append(
                    f"{participantes_en_revision_count} participante(s) con marca EN_REVISION "
                    f"incluidos en cifras segun politica {politica_revision.value}."
                )
            elif politica_revision == PoliticaPresentacionRevisionWord.EXCLUIR_DE_PRESENTACION:
                observaciones_revision.append(
                    f"{participantes_en_revision_count} participante(s) con marca EN_REVISION "
                    f"excluidos de cifras segun politica {politica_revision.value}."
                )

        traz = dict(trazabilidad or {})
        traz.setdefault("timestamp_word_acl", datetime.now(tz=timezone.utc).isoformat())
        traz.setdefault("origen", "REPOSITORIO_DOMINIO")

        return WordActividadDTO(
            id_actividad=id_actividad,
            numero_orden=numero_orden,
            nombre_actividad=nombre_actividad,
            eje_vinculado=eje_vinculado or "",
            descripcion_logros=descripcion_logros,
            fuente_resultados=fuente_resultados,
            sede=sede or "",
            departamento_territorial=departamento_territorial or "",
            municipio_territorial=municipio_territorial or "",
            tipo_actividad=tipo_actividad or "",
            fuente_cifras=fuente_cifras,
            etiqueta_fuente_cifras=etiqueta_fuente,
            total_mujeres=total_mujeres,
            total_varones=total_varones,
            sin_sexo_disponible=total_sin_sexo,
            total_participantes=total_participantes,
            estamentos=estamentos or [],
            evidencias=evidencias or [],
            tiene_discrepancias=tiene_discrepancias,
            discrepancias_resumen=discrepancias_resumen or [],
            observaciones_calidad=observaciones_calidad,
            observaciones_revision=observaciones_revision,
            trazabilidad=traz,
        )

    @classmethod
    def adaptar_actividad_para_informe_semanal(
        cls,
        actividad: Any,
        participaciones: List[Any],
        personas: Dict[str, Any],
        evidencias_vinculadas: List[Any],
        politica_revision: PoliticaPresentacionRevisionWord,
        fuente_cifras: FuenteCifras,
        fuente_resultados: FuenteResultados = FuenteResultados.VACIO,
        valor_resultados: Optional[str] = None,
        evidencias_base_dir: Optional[str] = None,
        numero_orden: int = 1,
    ) -> WordActividadDTO:
        """Adapta entidades completas de una actividad para informe semanal."""
        # Filtrar BLOQUEADOS incondicionalmente
        participantes_validos = []
        rev_count = 0
        for p in participaciones:
            estado = getattr(p, "estado_operativo", None)
            req_rev = getattr(p, "requiere_revision", 0)
            if estado == "BLOQUEADO":
                continue
            if estado == "EN_REVISION" or req_rev == 1:
                rev_count += 1
                if politica_revision == PoliticaPresentacionRevisionWord.EXCLUIR_DE_PRESENTACION:
                    continue
            participantes_validos.append(p)

        sexos = []
        for p in participantes_validos:
            p_id = getattr(p, "id_persona", None)
            persona = personas.get(p_id) if p_id else None
            sexo = getattr(persona, "sexo_normalizado", None) or getattr(persona, "sexo", None)
            sexos.append(sexo)

        ev_dtos = []
        for ev in evidencias_vinculadas:
            ev_dtos.append(
                cls.adaptar_evidencia(
                    id_evidencia=str(getattr(ev, "id_evidencia", getattr(ev, "id", ""))),
                    id_actividad=str(getattr(actividad, "id_actividad", getattr(actividad, "id", ""))),
                    titulo=getattr(ev, "titulo", ""),
                    tipo_evidencia=str(getattr(ev, "tipo_evidencia", "FOTO")),
                    ruta_relativa=getattr(ev, "ruta_relativa", getattr(ev, "ruta_archivo_relativa", None)),
                    hash_sha256=getattr(ev, "hash_sha256", None),
                    evidencias_base_dir=evidencias_base_dir,
                )
            )

        return cls.adaptar_actividad(
            id_actividad=str(getattr(actividad, "id_actividad", getattr(actividad, "id", ""))),
            nombre_actividad=getattr(actividad, "nombre", getattr(actividad, "nombre_actividad", "")),
            fuente_cifras=fuente_cifras,
            participantes_sexos=sexos,
            numero_orden=numero_orden,
            eje_vinculado=getattr(actividad, "eje_estrategico", getattr(actividad, "eje_vinculado", "")),
            sede=getattr(actividad, "sede", ""),
            departamento_territorial=getattr(actividad, "departamento", getattr(actividad, "departamento_territorial", "")),
            municipio_territorial=getattr(actividad, "municipio", getattr(actividad, "municipio_territorial", "")),
            tipo_actividad=getattr(actividad, "tipo_actividad", ""),
            fuente_resultados=fuente_resultados,
            valor_resultados=valor_resultados,
            evidencias=ev_dtos,
            politica_revision=politica_revision,
            participantes_en_revision_count=rev_count,
        )

    @classmethod
    def adaptar_para_informe_semanal(
        cls,
        departamento_responsable: str,
        mes_planificado: str,
        semana: str,
        actividades: List[WordActividadDTO],
        sede_recinto: str = "",
        id_informe_semanal: Optional[str] = None,
        politica_revision: PoliticaPresentacionRevisionWord = PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
        trazabilidad_global: Optional[Dict[str, str]] = None,
    ) -> WordWeeklyReportDataset:
        """Compone el WordWeeklyReportDataset agregado para Producto B."""
        gran_total_mujeres = sum(a.total_mujeres for a in actividades)
        gran_total_varones = sum(a.total_varones for a in actividades)
        gran_total_sin_sexo = sum(a.sin_sexo_disponible for a in actividades)
        gran_total_participantes = gran_total_mujeres + gran_total_varones + gran_total_sin_sexo
        gran_total_actividades = len(actividades)

        observaciones_calidad: List[str] = []
        for act in actividades:
            if act.sin_sexo_disponible > 0:
                observaciones_calidad.append(
                    f"{act.sin_sexo_disponible} participante(s) sin sexo disponible "
                    f"en actividad '{act.nombre_actividad}' (id={act.id_actividad})."
                )
            if act.fuente_resultados == FuenteResultados.VACIO:
                observaciones_calidad.append(
                    f"Columna DESCRIPCIÓN/LOGROS sin fuente aprobada "
                    f"en actividad '{act.nombre_actividad}' (OPEN-WORD-02 pendiente)."
                )

        traz = dict(trazabilidad_global or {})
        traz.setdefault("timestamp_word_acl_semanal", datetime.now(tz=timezone.utc).isoformat())
        traz.setdefault("fuente", "DOMINIO_INSTITUCIONAL")

        return WordWeeklyReportDataset(
            id_informe_semanal=id_informe_semanal,
            departamento_responsable=departamento_responsable,
            mes_planificado=mes_planificado,
            semana=semana,
            sede_recinto=sede_recinto,
            actividades=actividades,
            gran_total_actividades=gran_total_actividades,
            gran_total_mujeres=gran_total_mujeres,
            gran_total_varones=gran_total_varones,
            gran_total_sin_sexo=gran_total_sin_sexo,
            gran_total_participantes=gran_total_participantes,
            observaciones_calidad=observaciones_calidad,
            politica_revision_aplicada=politica_revision,
            trazabilidad_global=traz,
        )

    @staticmethod
    def verificar_invariante_sexo(
        mujeres: int,
        varones: int,
        sin_sexo_disponible: int,
        total_participantes: int,
    ) -> bool:
        """Verifica la invariante aritmetica: total == mujeres + varones + sin_sexo."""
        return total_participantes == mujeres + varones + sin_sexo_disponible
