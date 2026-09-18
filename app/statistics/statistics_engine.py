"""
app.statistics.statistics_engine

Motor determinístico para el cálculo de estadísticas institucionales y agregaciones.
Opera directamente sobre el modelo interno unificado (SSOT) y el ResultadoRouting de Fase 6.
"""

from typing import Dict, List, Optional, Set
from app.audit.audit_logger import get_logger
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.routing.models import EnrutamientoRegistro, ResultadoRouting
from app.statistics.models import (
    DesgloseSexo,
    DesgloseCategoria,
    EstadisticaActividad,
    MetricaCalidadItem,
    EstadisticaCalidad,
    DistribucionEdades,
    EstadisticaGlobal,
)

logger = get_logger(__name__)


class StatisticsEngine:
    """
    Motor institucional de cálculo y agregación estadística.
    """

    @classmethod
    def _calcular_desglose_sexo(cls, registros: List[EnrutamientoRegistro]) -> DesgloseSexo:
        """Calcula el conteo y proporciones porcentuales por sexo para un grupo de registros."""
        total = len(registros)
        if total == 0:
            return DesgloseSexo()

        femenino = sum(1 for r in registros if r.persona.sexo_normalizado == "FEMENINO")
        masculino = sum(1 for r in registros if r.persona.sexo_normalizado == "MASCULINO")
        indefinido = total - femenino - masculino

        pct_f = round((femenino / total) * 100, 2)
        pct_m = round((masculino / total) * 100, 2)

        return DesgloseSexo(
            femenino=femenino,
            masculino=masculino,
            indefinido=indefinido,
            total=total,
            porcentaje_femenino=pct_f,
            porcentaje_masculino=pct_m,
        )

    @classmethod
    def _calcular_desglose_categoria(
        cls, nombre_categoria: str, registros: List[EnrutamientoRegistro]
    ) -> DesgloseCategoria:
        """Genera el desglose completo con trazabilidad de IDs para una categoría específica."""
        conteo_sexo = cls._calcular_desglose_sexo(registros)
        aptos = sum(1 for r in registros if r.estado_operativo == "APTO")
        en_revision = sum(1 for r in registros if r.estado_operativo == "EN_REVISION")
        ids = [r.participacion.id_participacion for r in registros]

        return DesgloseCategoria(
            categoria=nombre_categoria,
            conteo_sexo=conteo_sexo,
            aptos=aptos,
            en_revision=en_revision,
            ids_participaciones=ids,
        )

    @classmethod
    def calcular(
        cls,
        resultado_routing: ResultadoRouting,
        actividades: List[Activity],
        personas: List[Person],
        participaciones: List[Participation],
    ) -> EstadisticaGlobal:
        """
        Calcula todas las métricas estadísticas a nivel de actividad y globales.
        
        Args:
            resultado_routing: Decisiones formales de enrutamiento de Fase 6.
            actividades: Lista de actividades únicas del sistema.
            personas: Lista de personas consolidadas.
            participaciones: Lista de participaciones procesadas.
            
        Returns:
            EstadisticaGlobal con indicadores validados y trazables.
        """
        logger.info("Iniciando cálculo del Motor Estadístico Institucional (Fase 7).")

        # 1. Unificar todos los registros enrutados para indexación rápida
        todos_los_registros: List[EnrutamientoRegistro] = (
            resultado_routing.estudiantes
            + resultado_routing.academicos_administrativos
            + resultado_routing.colaboradores
            + resultado_routing.beneficiados
            + resultado_routing.cola_revision
            + resultado_routing.bloqueados
        )

        mapa_registros_por_actividad: Dict[str, List[EnrutamientoRegistro]] = {}
        for r in todos_los_registros:
            act_id = r.actividad.id_actividad
            if act_id not in mapa_registros_por_actividad:
                mapa_registros_por_actividad[act_id] = []
            mapa_registros_por_actividad[act_id].append(r)

        # 2. Calcular estadísticas por cada actividad (Matriz 1: Consolidado)
        lista_estadisticas_actividades: List[EstadisticaActividad] = []

        for act in actividades:
            regs_act = mapa_registros_por_actividad.get(act.id_actividad, [])

            # Filtrar por destino y subtipo dentro de esta actividad
            regs_est = [r for r in regs_act if r.matriz_destino == MatrizDestino.ESTUDIANTES]
            regs_doc = [
                r
                for r in regs_act
                if r.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
                and r.subtipo_institucional == SubtipoInstitucional.ACADEMICO
            ]
            regs_adm = [
                r
                for r in regs_act
                if r.matriz_destino == MatrizDestino.ACADEMICOS_ADMINISTRATIVOS
                and r.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO
            ]
            regs_ben = [r for r in regs_act if r.matriz_destino == MatrizDestino.BENEFICIADOS]
            regs_col = [r for r in regs_act if r.matriz_destino == MatrizDestino.COLABORADORES]
            regs_rev = [r for r in regs_act if r.matriz_destino == MatrizDestino.COLA_REVISION]
            regs_bloq = [r for r in regs_act if r.matriz_destino == MatrizDestino.BLOQUEADOS]

            # Personas únicas en esta actividad específica
            personas_unicas_act = len(set(r.persona.id_persona_interno for r in regs_act))

            stat_act = EstadisticaActividad(
                id_actividad=act.id_actividad,
                nombre_actividad=act.nombre_actividad_oficial or act.nombre_actividad_original,
                sede=act.sede,
                fecha=str(act.fecha_evento) if act.fecha_evento else None,
                municipio=act.municipio_evento,
                departamento=act.departamento,
                eje_linea=act.eje_linea_estrategica,
                tipo_evento=act.tipo_evento,
                total_asistencias=len(regs_act),
                total_personas_unicas=personas_unicas_act,
                desglose_sexo_global=cls._calcular_desglose_sexo(regs_act),
                estudiantes=cls._calcular_desglose_categoria("ESTUDIANTE", regs_est),
                docentes=cls._calcular_desglose_categoria("DOCENTE (ACADEMICO)", regs_doc),
                administrativos_no_docentes=cls._calcular_desglose_categoria(
                    "ADMINISTRATIVO / NO DOCENTE", regs_adm
                ),
                beneficiados=cls._calcular_desglose_categoria("BENEFICIADO", regs_ben),
                colaboradores=cls._calcular_desglose_categoria("COLABORADOR", regs_col),
                cola_revision=len(regs_rev),
                bloqueados=len(regs_bloq),
            )
            lista_estadisticas_actividades.append(stat_act)
        # 3. Métricas Globales del Período
        total_asistencias = len(participaciones)
        # Personas únicas globales: se identifican por id_persona de las participaciones
        ids_personas_unicas: Set[str] = set(p.id_persona for p in participaciones)
        total_personas_unicas = len(ids_personas_unicas)

        # A) Promedio de asistencias por persona = total_asistencias / personas_unicas
        promedio_asistencias_por_persona = (
            round(total_asistencias / total_personas_unicas, 2)
            if total_personas_unicas > 0
            else 0.0
        )

        # B) Personas recurrentes: persona unificada (Fase 4) que participa en más de una actividad distinta
        # Múltiples participaciones en la misma actividad NO se consideran recurrencia institucional
        mapa_actividades_por_persona: Dict[str, Set[str]] = {}
        for p in participaciones:
            if p.id_persona not in mapa_actividades_por_persona:
                mapa_actividades_por_persona[p.id_persona] = set()
            mapa_actividades_por_persona[p.id_persona].add(p.id_actividad)

        ids_personas_recurrentes = sorted([
            id_pers
            for id_pers, acts in mapa_actividades_por_persona.items()
            if len(acts) > 1
        ])
        personas_recurrentes = len(ids_personas_recurrentes)

        # C) Tasa de recurrencia institucional = (personas_recurrentes / personas_unicas) * 100
        tasa_recurrencia = (
            round((personas_recurrentes / total_personas_unicas) * 100, 2)
            if total_personas_unicas > 0
            else 0.0
        )

        desglose_sexo_global = cls._calcular_desglose_sexo(todos_los_registros)

        # Desglose global por categorías
        regs_doc_global = [
            r
            for r in resultado_routing.academicos_administrativos
            if r.subtipo_institucional == SubtipoInstitucional.ACADEMICO
        ]
        regs_adm_global = [
            r
            for r in resultado_routing.academicos_administrativos
            if r.subtipo_institucional == SubtipoInstitucional.ADMINISTRATIVO
        ]

        desglose_categorias: Dict[str, DesgloseCategoria] = {
            "ESTUDIANTES": cls._calcular_desglose_categoria(
                "ESTUDIANTES", resultado_routing.estudiantes
            ),
            "DOCENTES": cls._calcular_desglose_categoria(
                "DOCENTES (ACADEMICO)", regs_doc_global
            ),
            "ADMINISTRATIVOS_NO_DOCENTES": cls._calcular_desglose_categoria(
                "ADMINISTRATIVOS / NO DOCENTES", regs_adm_global
            ),
            "BENEFICIADOS": cls._calcular_desglose_categoria(
                "PROTAGONISTAS BENEFICIADOS", resultado_routing.beneficiados
            ),
            "COLABORADORES": cls._calcular_desglose_categoria(
                "COLABORADORES", resultado_routing.colaboradores
            ),
            "COLA_REVISION": cls._calcular_desglose_categoria(
                "COLA DE REVISION", resultado_routing.cola_revision
            ),
            "BLOQUEADOS": cls._calcular_desglose_categoria(
                "BLOQUEADOS", resultado_routing.bloqueados
            ),
        }

        # 4. Distribuciones geográficas y académicas
        dist_sedes: Dict[str, int] = {}
        for act in actividades:
            sede_nom = act.sede or "Sin Sede Especificada"
            # Conteo de asistencias en actividades de esta sede
            conteo = sum(
                len(mapa_registros_por_actividad.get(a.id_actividad, []))
                for a in actividades
                if (a.sede or "Sin Sede Especificada") == sede_nom
            )
            dist_sedes[sede_nom] = conteo

        dist_carreras: Dict[str, int] = {}
        for r in resultado_routing.estudiantes:
            carrera_nom = (
                r.persona.carrera_normalizada
                or r.persona.carrera_original
                or "No Especificada"
            )
            dist_carreras[carrera_nom] = dist_carreras.get(carrera_nom, 0) + 1

        # 5. Distribución de Edades
        edades_list: List[int] = []
        menores_18 = 0
        de_18_a_24 = 0
        de_25_a_29 = 0
        de_30_a_mas = 0
        sin_edad = 0

        for r in todos_los_registros:
            edad = r.persona.edad
            if edad is not None and isinstance(edad, int):
                edades_list.append(edad)
                if edad < 18:
                    menores_18 += 1
                elif 18 <= edad <= 24:
                    de_18_a_24 += 1
                elif 25 <= edad <= 29:
                    de_25_a_29 += 1
                else:
                    de_30_a_mas += 1
            else:
                sin_edad += 1

        edad_prom = round(sum(edades_list) / len(edades_list), 2) if edades_list else None
        edad_min = min(edades_list) if edades_list else None
        edad_max = max(edades_list) if edades_list else None

        dist_edades = DistribucionEdades(
            menores_18=menores_18,
            de_18_a_24=de_18_a_24,
            de_25_a_29=de_25_a_29,
            de_30_a_mas=de_30_a_mas,
            sin_edad=sin_edad,
            edad_promedio=edad_prom,
            edad_minima=edad_min,
            edad_maxima=edad_max,
        )

        # 6. Indicadores de Calidad de Datos (Auditados con Numerador y Denominador)
        aptos_tot = sum(1 for r in todos_los_registros if r.estado_operativo == "APTO")
        rev_tot = sum(1 for r in todos_los_registros if r.estado_operativo == "EN_REVISION")
        bloq_tot = sum(1 for r in todos_los_registros if r.estado_operativo == "BLOQUEADO")

        # Cédula disponible
        ced_disp = sum(1 for r in todos_los_registros if r.persona.cedula is not None and r.persona.cedula.strip())
        ced_den = total_asistencias
        ced_pct = round((ced_disp / ced_den) * 100, 2) if ced_den > 0 else 0.0
        metrica_cedula = MetricaCalidadItem(
            numerador=ced_disp,
            denominador=ced_den,
            porcentaje=ced_pct,
            definicion="Registros con valor de cédula presente y no vacío en el perfil unificado de la persona.",
        )

        # Sexo confirmado
        sex_disp = sum(1 for r in todos_los_registros if r.persona.sexo_normalizado in ("FEMENINO", "MASCULINO"))
        sex_den = total_asistencias
        sex_pct = round((sex_disp / sex_den) * 100, 2) if sex_den > 0 else 0.0
        metrica_sexo = MetricaCalidadItem(
            numerador=sex_disp,
            denominador=sex_den,
            porcentaje=sex_pct,
            definicion="Registros con sexo normalizado institucionalmente como FEMENINO o MASCULINO.",
        )

        # Edad o fecha de nacimiento disponible
        edad_disp = sum(1 for r in todos_los_registros if r.persona.edad is not None or r.persona.fecha_nacimiento is not None)
        edad_den = total_asistencias
        edad_pct = round((edad_disp / edad_den) * 100, 2) if edad_den > 0 else 0.0
        metrica_edad = MetricaCalidadItem(
            numerador=edad_disp,
            denominador=edad_den,
            porcentaje=edad_pct,
            definicion="Registros con valor numérico de edad o fecha de nacimiento presente en la fuente original (disponibilidad de dato en origen, no validación institucional de mayoría de edad).",
        )

        # Carrera disponible en estudiantes
        total_est = len(resultado_routing.estudiantes)
        carr_disp = sum(
            1
            for r in resultado_routing.estudiantes
            if r.persona.carrera_original is not None and r.persona.carrera_original.strip()
        )
        carr_den = total_est
        carr_pct = round((carr_disp / carr_den) * 100, 2) if carr_den > 0 else 0.0
        metrica_carrera = MetricaCalidadItem(
            numerador=carr_disp,
            denominador=carr_den,
            porcentaje=carr_pct,
            definicion="Estudiantes con carrera o programa académico registrado en la fuente de origen (disponibilidad de texto, no validación institucional de catálogo oficial).",
        )

        calidad = EstadisticaCalidad(
            total_registros=total_asistencias,
            registros_aptos=aptos_tot,
            registros_en_revision=rev_tot,
            registros_bloqueados=bloq_tot,
            porcentaje_aptos=round((aptos_tot / total_asistencias) * 100, 2) if total_asistencias > 0 else 0.0,
            porcentaje_en_revision=round((rev_tot / total_asistencias) * 100, 2) if total_asistencias > 0 else 0.0,
            cedula_disponible=metrica_cedula,
            sexo_confirmado=metrica_sexo,
            edad_disponible=metrica_edad,
            carrera_disponible=metrica_carrera,
            cedula_disponible_pct=ced_pct,
            sexo_confirmado_pct=sex_pct,
            edad_disponible_pct=edad_pct,
            carrera_disponible_pct=carr_pct,
        )

        # 7. Verificación de Invariantes Numéricas
        suma_asistencias_actividades = sum(a.total_asistencias for a in lista_estadisticas_actividades)
        suma_categorias = sum(cat.conteo_sexo.total for cat in desglose_categorias.values())
        suma_sexos = desglose_sexo_global.total

        invariante_valida = (
            (total_asistencias == suma_asistencias_actividades)
            and (total_asistencias == suma_categorias)
            and (total_asistencias == suma_sexos)
        )

        if not invariante_valida:
            msg = (
                f"FALLO DE INVARIANTE ESTADÍSTICA: Total={total_asistencias}, "
                f"SumaActividades={suma_asistencias_actividades}, "
                f"SumaCategorías={suma_categorias}, SumaSexos={suma_sexos}."
            )
            logger.error(msg)
            raise ValueError(msg)

        logger.info(
            f"Cálculo estadístico completado exitosamente. Asistencias={total_asistencias}, "
            f"PersonasÚnicas={total_personas_unicas}, PromedioAsistencias={promedio_asistencias_por_persona}, "
            f"PersonasRecurrentes={personas_recurrentes}, TasaRecurrencia={tasa_recurrencia}%, "
            f"Actividades={len(actividades)}."
        )

        return EstadisticaGlobal(
            total_actividades=len(actividades),
            total_asistencias=total_asistencias,
            total_personas_unicas=total_personas_unicas,
            promedio_asistencias_por_persona=promedio_asistencias_por_persona,
            personas_recurrentes=personas_recurrentes,
            ids_personas_recurrentes=ids_personas_recurrentes,
            tasa_recurrencia=tasa_recurrencia,
            desglose_sexo_global=desglose_sexo_global,
            desglose_categorias=desglose_categorias,
            distribucion_sedes=dist_sedes,
            distribucion_carreras=dist_carreras,
            distribucion_edades=dist_edades,
            calidad_datos=calidad,
            actividades=lista_estadisticas_actividades,
            invariante_estadistica_valida=invariante_valida,
        )
