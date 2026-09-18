"""
app.routing.participant_router

Motor determinístico de enrutamiento institucional a matrices oficiales.

Aplica estrictamente las reglas aprobadas:
- Regla R6-01: Routing determinado EXCLUSIVAMENTE por Participation.categoria_participacion.
- Regla R6-02: Mapeo estricto a las 5 matrices oficiales y cubetas de control.
- Regla R6-03: Separación conceptual estricta: EN_REVISION != COLA_REVISION != BLOQUEADO.
- Regla R6-04: Unicidad de destino: cada participación tiene exactamente un destino.
- Regla R6-05: Invariante matemática estricta (sin incluir CONSOLIDADO):
  Entrada == Estudiantes + Academicos/Admin + Beneficiados + Colaboradores + ColaRevision + Bloqueados
- Regla R6-06: Conservación y no mutación de entidades originales.
"""

from typing import Dict, List, Optional
from app.audit.audit_logger import get_logger
from app.core.constants.participant_types import CategoriaParticipacion, NivelValidacion
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.routing.models import EnrutamientoRegistro, ResumenMatriz, ResultadoRouting

logger = get_logger(__name__)


class ParticipantRouter:
    """
    Motor central de enrutamiento institucional.
    
    Toma las entidades validadas del sistema (SSOT) y produce un ResultadoRouting
    con todas las participaciones distribuidas formalmente en sus matrices oficiales.
    """

    @classmethod
    def enrutar(
        cls,
        actividades: List[Activity],
        personas: List[Person],
        participaciones: List[Participation],
        validaciones: Optional[List[ValidationResult]] = None
    ) -> ResultadoRouting:
        """
        Clasifica cada participación en exactamente un destino institucional.
        
        Args:
            actividades: Lista de actividades unificadas.
            personas: Lista de personas consolidadas.
            participaciones: Lista de participaciones a enrutar.
            validaciones: Lista de hallazgos acumulados de validación.
            
        Returns:
            ResultadoRouting con las listas clasificadas, resúmenes y validación de invariante.
        """
        validaciones = validaciones or []
        logger.info(
            f"Iniciando routing institucional: {len(participaciones)} participaciones, "
            f"{len(personas)} personas, {len(actividades)} actividades."
        )

        # 1. Indexación relacional para acceso O(1)
        mapa_actividades: Dict[str, Activity] = {act.id_actividad: act for act in actividades}
        mapa_personas: Dict[str, Person] = {p.id_persona_interno: p for p in personas}

        # Indexar hallazgos de validación por referencia
        mapa_validaciones: Dict[str, List[ValidationResult]] = {}
        for val in validaciones:
            ref = val.id_referencia or "SISTEMA"
            if ref not in mapa_validaciones:
                mapa_validaciones[ref] = []
            mapa_validaciones[ref].append(val)

        # Estructuras de acumulación (destinos disjuntos)
        estudiantes: List[EnrutamientoRegistro] = []
        academicos_admin: List[EnrutamientoRegistro] = []
        colaboradores: List[EnrutamientoRegistro] = []
        beneficiados: List[EnrutamientoRegistro] = []
        cola_revision: List[EnrutamientoRegistro] = []
        bloqueados: List[EnrutamientoRegistro] = []

        ids_clasificados = set()

        for part in participaciones:
            # Recopilar hallazgos asociados a la participación y a la persona
            hallazgos: List[ValidationResult] = []
            if part.id_participacion in mapa_validaciones:
                hallazgos.extend(mapa_validaciones[part.id_participacion])
            if part.id_persona in mapa_validaciones:
                hallazgos.extend(mapa_validaciones[part.id_persona])

            # Verificar integridad referencial
            persona = mapa_personas.get(part.id_persona)
            actividad = mapa_actividades.get(part.id_actividad)

            # Error crítico asociado directamente
            tiene_error_critico = any(
                h.nivel in (NivelValidacion.ERROR, "ERROR") for h in hallazgos
            )

            # A. Evaluación de condición de BLOQUEO
            if persona is None or actividad is None or tiene_error_critico:
                # Si falta persona o actividad, crear entidad placeholder inmutable para trazabilidad
                persona_ref = persona or Person(
                    id_persona_interno=part.id_persona,
                    nombre_completo="[PERSONA_NO_ENCONTRADA]"
                )
                actividad_ref = actividad or Activity(
                    id_actividad=part.id_actividad,
                    nombre_actividad_original="[ACTIVIDAD_NO_ENCONTRADA]"
                )

                motivo = "Bloqueado por error crítico o inconsistencia referencial."
                if persona is None:
                    motivo = f"Referencia huérfana: id_persona '{part.id_persona}' no encontrado."
                elif actividad is None:
                    motivo = f"Referencia huérfana: id_actividad '{part.id_actividad}' no encontrado."

                reg_bloqueado = EnrutamientoRegistro(
                    participacion=part,
                    persona=persona_ref,
                    actividad=actividad_ref,
                    matriz_destino=MatrizDestino.BLOQUEADOS,
                    subtipo_institucional=SubtipoInstitucional.NO_APLICA,
                    estado_operativo="BLOQUEADO",
                    motivo_enrutamiento=motivo,
                    hallazgos_asociados=hallazgos
                )
                bloqueados.append(reg_bloqueado)
                ids_clasificados.add(part.id_participacion)
                continue

            # B. Determinación de estado operativo (APTO vs EN_REVISION)
            tiene_revision = (
                part.requiere_revision
                or any(h.nivel in (NivelValidacion.REVISION, "REVISION") for h in hallazgos)
            )
            estado_operativo = "EN_REVISION" if tiene_revision else "APTO"

            # C. Routing exclusivo por categoria_participacion
            cat = part.categoria_participacion

            # Normalizar para comparación sin alterar el objeto original
            cat_val = cat.value if hasattr(cat, "value") else str(cat)

            if cat == CategoriaParticipacion.ESTUDIANTE or cat_val == "ESTUDIANTE":
                if getattr(part, "es_beneficiado_rol", False):
                    # RN-C03: Estudiante con rol contextual de beneficiario prevalece hacia M5 (BENEFICIADOS)
                    reg = EnrutamientoRegistro(
                        participacion=part,
                        persona=persona,
                        actividad=actividad,
                        matriz_destino=MatrizDestino.BENEFICIADOS,
                        subtipo_institucional=SubtipoInstitucional.NO_APLICA,
                        estado_operativo=estado_operativo,
                        motivo_enrutamiento="Enrutado a Protagonistas Beneficiados por regla RN-C03 (Estudiante actuando contextualmente como beneficiario directo).",
                        hallazgos_asociados=hallazgos
                    )
                    beneficiados.append(reg)
                else:
                    reg = EnrutamientoRegistro(
                        participacion=part,
                        persona=persona,
                        actividad=actividad,
                        matriz_destino=MatrizDestino.ESTUDIANTES,
                        subtipo_institucional=SubtipoInstitucional.NO_APLICA,
                        estado_operativo=estado_operativo,
                        motivo_enrutamiento="Enrutado a Estudiantes por categoría ESTUDIANTE.",
                        hallazgos_asociados=hallazgos
                    )
                    estudiantes.append(reg)

            elif cat == CategoriaParticipacion.DOCENTE or cat_val == "DOCENTE":
                reg = EnrutamientoRegistro(
                    participacion=part,
                    persona=persona,
                    actividad=actividad,
                    matriz_destino=MatrizDestino.ACADEMICOS_ADMINISTRATIVOS,
                    subtipo_institucional=SubtipoInstitucional.ACADEMICO,
                    estado_operativo=estado_operativo,
                    motivo_enrutamiento="Enrutado a Académicos y Administrativos (subtipo Académico) por categoría DOCENTE.",
                    hallazgos_asociados=hallazgos
                )
                academicos_admin.append(reg)

            elif cat == CategoriaParticipacion.ADMINISTRATIVO or cat_val == "ADMINISTRATIVO":
                reg = EnrutamientoRegistro(
                    participacion=part,
                    persona=persona,
                    actividad=actividad,
                    matriz_destino=MatrizDestino.ACADEMICOS_ADMINISTRATIVOS,
                    subtipo_institucional=SubtipoInstitucional.ADMINISTRATIVO,
                    estado_operativo=estado_operativo,
                    motivo_enrutamiento="Enrutado a Académicos y Administrativos (subtipo Administrativo) por categoría ADMINISTRATIVO.",
                    hallazgos_asociados=hallazgos
                )
                academicos_admin.append(reg)

            elif cat == CategoriaParticipacion.NO_DOCENTE or cat_val == "NO_DOCENTE":
                # REGLA CRÍTICA: categoria_participacion permanece inmutable (NO_DOCENTE).
                # Su equivalencia institucional se expresa únicamente en subtipo_institucional.
                reg = EnrutamientoRegistro(
                    participacion=part,
                    persona=persona,
                    actividad=actividad,
                    matriz_destino=MatrizDestino.ACADEMICOS_ADMINISTRATIVOS,
                    subtipo_institucional=SubtipoInstitucional.ADMINISTRATIVO,
                    estado_operativo=estado_operativo,
                    motivo_enrutamiento="Enrutado a Académicos y Administrativos (subtipo Administrativo) por categoría institucional NO_DOCENTE.",
                    hallazgos_asociados=hallazgos
                )
                academicos_admin.append(reg)

            elif (
                cat in (CategoriaParticipacion.BENEFICIADO, CategoriaParticipacion.POBLADOR_GENERAL)
                or cat_val in ("BENEFICIADO", "POBLADOR_GENERAL", "BENEFICIARIO", "EMPRENDEDOR")
            ):
                reg = EnrutamientoRegistro(
                    participacion=part,
                    persona=persona,
                    actividad=actividad,
                    matriz_destino=MatrizDestino.BENEFICIADOS,
                    subtipo_institucional=SubtipoInstitucional.NO_APLICA,
                    estado_operativo=estado_operativo,
                    motivo_enrutamiento=f"Enrutado a Protagonistas Beneficiados por categoría {cat_val}.",
                    hallazgos_asociados=hallazgos
                )
                beneficiados.append(reg)

            elif cat == CategoriaParticipacion.COLABORADOR or cat_val == "COLABORADOR":
                reg = EnrutamientoRegistro(
                    participacion=part,
                    persona=persona,
                    actividad=actividad,
                    matriz_destino=MatrizDestino.COLABORADORES,
                    subtipo_institucional=SubtipoInstitucional.NO_APLICA,
                    estado_operativo=estado_operativo,
                    motivo_enrutamiento="Enrutado a Colaboradores por categoría COLABORADOR.",
                    hallazgos_asociados=hallazgos
                )
                colaboradores.append(reg)

            else:
                # Categoría DESCONOCIDO o valor no mapeable
                reg = EnrutamientoRegistro(
                    participacion=part,
                    persona=persona,
                    actividad=actividad,
                    matriz_destino=MatrizDestino.COLA_REVISION,
                    subtipo_institucional=SubtipoInstitucional.NO_APLICA,
                    estado_operativo="EN_REVISION",
                    motivo_enrutamiento=f"Categoría '{cat_val}' no determinable institucionalmente. Asignado a Cola de Revisión Humana.",
                    hallazgos_asociados=hallazgos
                )
                cola_revision.append(reg)

            ids_clasificados.add(part.id_participacion)

        # 2. Verificación de la invariante formal de conservación
        total_entrada = len(participaciones)
        total_clasificadas = (
            len(estudiantes)
            + len(academicos_admin)
            + len(colaboradores)
            + len(beneficiados)
            + len(cola_revision)
            + len(bloqueados)
        )
        invariante_valida = (total_entrada == total_clasificadas) and (len(ids_clasificados) == total_entrada)

        if not invariante_valida:
            msg = (
                f"FALLO DE INVARIANTE: Entrada={total_entrada}, Clasificadas={total_clasificadas}, "
                f"Únicas={len(ids_clasificados)}. Las participaciones de entrada no coinciden exactamente."
            )
            logger.error(msg)
            raise ValueError(msg)

        # 3. Generación de resúmenes cuantitativos por matriz
        resumenes: Dict[str, ResumenMatriz] = {}
        for m_nombre, lista in [
            (MatrizDestino.ESTUDIANTES.value, estudiantes),
            (MatrizDestino.ACADEMICOS_ADMINISTRATIVOS.value, academicos_admin),
            (MatrizDestino.COLABORADORES.value, colaboradores),
            (MatrizDestino.BENEFICIADOS.value, beneficiados),
            (MatrizDestino.COLA_REVISION.value, cola_revision),
            (MatrizDestino.BLOQUEADOS.value, bloqueados),
        ]:
            total_m = len(lista)
            aptos_m = sum(1 for r in lista if r.estado_operativo == "APTO")
            rev_m = sum(1 for r in lista if r.estado_operativo == "EN_REVISION")
            fem_m = sum(1 for r in lista if r.persona.sexo_normalizado == "FEMENINO")
            masc_m = sum(1 for r in lista if r.persona.sexo_normalizado == "MASCULINO")
            indef_m = total_m - fem_m - masc_m

            # Desglose de subtipos
            subtipos_m: Dict[str, int] = {}
            for r in lista:
                if r.subtipo_institucional != SubtipoInstitucional.NO_APLICA:
                    st_val = r.subtipo_institucional.value
                    subtipos_m[st_val] = subtipos_m.get(st_val, 0) + 1

            resumenes[m_nombre] = ResumenMatriz(
                matriz=MatrizDestino(m_nombre),
                total_participaciones=total_m,
                total_aptos=aptos_m,
                total_en_revision=rev_m,
                total_femenino=fem_m,
                total_masculino=masc_m,
                total_sexo_indefinido=indef_m,
                subtipos=subtipos_m
            )

        logger.info(
            f"Routing completado exitosamente: {total_clasificadas} registros clasificados. "
            f"Estudiantes={len(estudiantes)}, Académicos/Admin={len(academicos_admin)}, "
            f"Beneficiados={len(beneficiados)}, Colaboradores={len(colaboradores)}, "
            f"ColaRevisión={len(cola_revision)}, Bloqueados={len(bloqueados)}."
        )

        return ResultadoRouting(
            estudiantes=estudiantes,
            academicos_administrativos=academicos_admin,
            colaboradores=colaboradores,
            beneficiados=beneficiados,
            cola_revision=cola_revision,
            bloqueados=bloqueados,
            actividades=actividades,
            total_entrada=total_entrada,
            total_clasificadas=total_clasificadas,
            invariante_valida=invariante_valida,
            resumenes=resumenes
        )
