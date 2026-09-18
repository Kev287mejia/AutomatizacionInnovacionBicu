"""
app.word_consolidator.document.institutional_transformer

Transformador documental puro para el Producto B:
ResultadoConsolidacion -> InformeSemanalInstitucional (Fase 16.3).

Garantías de diseño:
1. Función pura sin efectos secundarios: no muta el objeto ResultadoConsolidacion.
2. Cero recálculo: no reclasifica identidades, personas, recurrencia ni discrepancias.
3. Preservación paralela de fuentes: dato_declarado, dato_nominal y discrepancias.
4. Soporte para N >= 0 actividades sin inventar filas artificiales.
5. Evidencias como referencias limpias de datos.
"""

from typing import Dict, List, Optional, Tuple

from app.word_consolidator.models import MetadatosInstitucionales

from app.word_consolidator.document.institutional_models import (
    ActividadInstitucional,
    ConteoSexoInstitucional,
    DiscrepanciaActividadInstitucional,
    DiscrepanciaEstamento,
    InformeSemanalInstitucional,
    ProtagonistaEstamentoInstitucional,
    SeccionEvidenciasActividad,
    TipoEstamentoInstitucional,
    TrazabilidadActividad,
)
from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ResultadoConsolidacion,
)


MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

ORDEN_ESTAMENTOS_DEFAULT = {
    TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS: 1,
    TipoEstamentoInstitucional.ESTUDIANTES: 2,
    TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO: 3,
    TipoEstamentoInstitucional.COLABORADORES: 4,
    TipoEstamentoInstitucional.BENEFICIARIOS_POBLADORES: 5,
}


class InstitutionalReportTransformer:
    """
    Transformador puro que proyecta ResultadoConsolidacion hacia InformeSemanalInstitucional.
    No muta el estado del pipeline ni altera la integridad de Producto A.
    """

    @classmethod
    def _obtener_programas_nominales_actividad(cls, act: ActividadConsolidada) -> List[str]:
        """
        Extrae los valores de 'Programa' únicos reportados exclusivamente en las participaciones
        nominales de M2 y M3 asociadas a la actividad consolidada.
        Garantiza estricto aislamiento entre actividades (no contamina una actividad con otra).
        """
        programas: List[str] = []
        for p in act.participaciones:
            mat_orig = p.matriz_origen.upper() if p.matriz_origen else ""
            if mat_orig in ("M2", "M3"):
                prog = None
                if getattr(p, "programa", None) and str(p.programa).strip():
                    prog = str(p.programa).strip()
                elif p.fila_nominal_origen and p.fila_nominal_origen.programa and str(p.fila_nominal_origen.programa).strip():
                    prog = str(p.fila_nominal_origen.programa).strip()
                elif p.trazabilidad and p.trazabilidad.get("programa"):
                    prog = str(p.trazabilidad["programa"]).strip()

                if prog and prog not in programas:
                    programas.append(prog)

        if "programas_nominales" in act.trazabilidad:
            for pr in act.trazabilidad["programas_nominales"]:
                pr_limpio = str(pr).strip()
                if pr_limpio and pr_limpio not in programas:
                    programas.append(pr_limpio)

        return programas

    @classmethod
    def resolver_departamento_responsable(
        cls,
        consolidacion: ResultadoConsolidacion,
        departamento_responsable: Optional[str] = None,
        metadatos: Optional[MetadatosInstitucionales] = None,
    ) -> Tuple[str, str, Optional[str]]:
        """
        Aplica rigurosamente la jerarquía oficial de 5 niveles para determinar el departamento
        responsable que figura en la cabecera de Product B ('Nombre del Depto:'):

        1. Nivel 1 — Metadatos explícitos:
           Si departamento_responsable o metadatos.departamento_institucional existe y tiene texto válido.
        2. Nivel 2 — M1:
           area_responsable -> nombre_area -> programa de la actividad en M1.
        3. Nivel 3 — Contexto nominal M2/M3:
           Valores de Programa inequívocos en las filas de M2/M3 asociadas a las actividades del período.
           Si hay ambigüedad (valores divergentes), NO elige arbitrariamente; documenta discrepancia.
        4. Nivel 4 — Configuración institucional:
           metadatos.programa si existiere en MetadatosInstitucionales.
        5. Nivel 5 — Fallback:
           'Área No Especificada'.

        :return: Tupla (departamento_resuelto, nivel_origen, observacion_o_motivo)
        """
        # Nivel 1 — Metadatos explícitos
        if departamento_responsable and departamento_responsable.strip():
            return (departamento_responsable.strip(), "NIVEL_1_METADATOS_EXPLICITOS", None)

        if metadatos and metadatos.departamento_institucional and metadatos.departamento_institucional.strip():
            return (metadatos.departamento_institucional.strip(), "NIVEL_1_METADATOS_EXPLICITOS", None)

        # Nivel 2 — M1
        for act in consolidacion.actividades:
            if act.fuente_m1:
                if act.fuente_m1.area_responsable and act.fuente_m1.area_responsable.strip():
                    return (act.fuente_m1.area_responsable.strip(), "NIVEL_2_M1", None)
                if act.fuente_m1.nombre_area and act.fuente_m1.nombre_area.strip():
                    return (act.fuente_m1.nombre_area.strip(), "NIVEL_2_M1", None)
                if act.fuente_m1.programa and act.fuente_m1.programa.strip():
                    return (act.fuente_m1.programa.strip(), "NIVEL_2_M1", None)
            else:
                if act.area_responsable and act.area_responsable.strip():
                    return (act.area_responsable.strip(), "NIVEL_2_M1", None)
                if act.programa and act.programa.strip():
                    return (act.programa.strip(), "NIVEL_2_M1", None)

        # Nivel 3 — Contexto nominal M2/M3 asociado a las actividades
        todos_programas_nominales: List[str] = []
        for act in consolidacion.actividades:
            progs_act = cls._obtener_programas_nominales_actividad(act)
            for pr in progs_act:
                if pr not in todos_programas_nominales:
                    todos_programas_nominales.append(pr)

        obs_ambiguedad: Optional[str] = None
        if len(todos_programas_nominales) == 1:
            prog_inferido = todos_programas_nominales[0]
            return (
                prog_inferido,
                "NIVEL_3_CONTEXTO_NOMINAL",
                f"Valor inferido desde contexto nominal M2/M3 inequívoco: '{prog_inferido}'",
            )
        elif len(todos_programas_nominales) > 1:
            obs_ambiguedad = (
                f"DISCREPANCIA INSTITUCIONAL: Se detectaron múltiples programas en contexto nominal M2/M3 "
                f"({', '.join(sorted(todos_programas_nominales))}). No se realiza inferencia automática por ambigüedad."
            )

        # Nivel 4 — Configuración institucional
        if metadatos and metadatos.programa and metadatos.programa.strip():
            return (metadatos.programa.strip(), "NIVEL_4_CONFIGURACION_INSTITUCIONAL", obs_ambiguedad)

        # Nivel 5 — Fallback
        return ("Área No Especificada", "NIVEL_5_FALLBACK", obs_ambiguedad)

    @classmethod
    def transformar(
        cls,
        consolidacion: ResultadoConsolidacion,
        departamento_responsable: Optional[str] = None,
        observaciones: Optional[str] = None,
        evidencias_por_actividad: Optional[Dict[str, SeccionEvidenciasActividad]] = None,
        politica_presentacion: str = "NOMINAL",
        metadatos: Optional[MetadatosInstitucionales] = None,
    ) -> InformeSemanalInstitucional:
        """
        Proyecta ResultadoConsolidacion en un InformeSemanalInstitucional inmutable.

        :param consolidacion: Resultado formal completo del pipeline de consolidación.
        :param departamento_responsable: Nombre opcional explícito del departamento/área responsable.
        :param observaciones: Notas institucionales complementarias.
        :param evidencias_por_actividad: Diccionario de evidencias indexado por id_actividad.
        :param politica_presentacion: Estrategia para conteo_presentacion ('NOMINAL_CON_FALLBACK', 'NOMINAL', 'DECLARADO_M1').
        :param metadatos: Metadatos institucionales oficiales opcionales.
        :return: Instancia inmutable de InformeSemanalInstitucional.
        """
        # 1. Determinación jerárquica de 5 niveles del departamento responsable
        depto, nivel_origen, obs_inferencia = cls.resolver_departamento_responsable(
            consolidacion=consolidacion,
            departamento_responsable=departamento_responsable,
            metadatos=metadatos,
        )

        obs_final = observaciones
        if obs_inferencia and "DISCREPANCIA INSTITUCIONAL" in obs_inferencia:
            obs_final = f"{observaciones}\n{obs_inferencia}" if observaciones else obs_inferencia

        # 2. Determinación de mes planificado y semana
        mes_num = consolidacion.periodo.mes
        if mes_num in MESES_ES:
            mes_texto = MESES_ES[mes_num]
        else:
            mes_texto = consolidacion.periodo.etiqueta.strip() if consolidacion.periodo.etiqueta else "Septiembre"

        semana_texto = str(consolidacion.periodo.semana) if consolidacion.periodo.semana is not None else "1"

        # 3. Transformación de actividades (N >= 0)
        actividades_doc: List[ActividadInstitucional] = []
        for idx, act in enumerate(consolidacion.actividades):
            act_doc = cls._transformar_actividad(
                act=act,
                numero_orden=idx + 1,
                evidencias_dict=evidencias_por_actividad,
                fuentes_consolidacion=consolidacion.fuentes,
                politica_presentacion=politica_presentacion,
            )
            actividades_doc.append(act_doc)

        # 4. Trazabilidad global
        traz_global: Dict[str, str] = {}
        for k, reg in consolidacion.fuentes.items():
            traz_global[k] = reg.hash_sha256
        traz_global["total_asistencia_bruta"] = str(consolidacion.total_asistencia_bruta)
        traz_global["total_personas_unicas"] = str(consolidacion.total_personas_unicas)
        traz_global["total_recurrencia"] = str(consolidacion.total_recurrencia)
        traz_global["departamento_responsable_origen"] = nivel_origen
        if nivel_origen == "NIVEL_3_CONTEXTO_NOMINAL":
            traz_global["departamento_responsable_inferido"] = depto
            traz_global["procedencia_departamento"] = "M2/M3_NOMINAL_UNIVOCO"
            traz_global["motivo_inferencia"] = "M1_SIN_PROGRAMA_INFERENCIA_PRESENTACION"
        elif obs_inferencia and "DISCREPANCIA INSTITUCIONAL" in obs_inferencia:
            traz_global["discrepancia_departamento"] = obs_inferencia

        return InformeSemanalInstitucional(
            departamento_responsable=depto,
            mes_planificado=mes_texto,
            semana=semana_texto,
            actividades=actividades_doc,
            observaciones=obs_final,
            trazabilidad_global=traz_global,
        )

    @classmethod
    def _transformar_actividad(
        cls,
        act: ActividadConsolidada,
        numero_orden: int,
        evidencias_dict: Optional[Dict[str, SeccionEvidenciasActividad]],
        fuentes_consolidacion: Dict[str, Any],
        politica_presentacion: str,
    ) -> ActividadInstitucional:
        # A. Datos generales
        # C4: La descripción proviene exclusivamente del campo resultados de M1 (col P).
        # FilaLeidaM1 no tiene atributo 'descripcion'; si resultados es None, permanece vacío.
        descripcion = act.resultados.strip() if act.resultados and act.resultados.strip() else ""

        # B. Protagonistas por estamento (solo estamentos con participación o declaración)
        protagonistas = cls._construir_protagonistas(act, politica_presentacion)

        # C. Totales cuantitativos de la actividad
        m_tot = sum(p.conteo_presentacion.mujeres for p in protagonistas)
        v_tot = sum(p.conteo_presentacion.varones for p in protagonistas)
        totales_act = ConteoSexoInstitucional(mujeres=m_tot, varones=v_tot, total=m_tot + v_tot)

        # D. Discrepancias institucionales
        discrepancias_doc = cls._construir_discrepancias_actividad(act)

        # E. Evidencias
        if evidencias_dict and act.id_actividad in evidencias_dict:
            evidencias_sec = evidencias_dict[act.id_actividad]
        else:
            evidencias_sec = SeccionEvidenciasActividad(
                id_actividad=act.id_actividad,
                numero_actividad=numero_orden,
                nombre_actividad=act.nombre_actividad,
                fotografias=[],
                registros_asistencia=[],
                enlaces_publicaciones=[],
            )

        # F. Trazabilidad
        m1_arch = getattr(act.fuente_m1, "archivo_origen", None) if act.fuente_m1 else None
        m1_fila = getattr(act.fuente_m1, "fila_origen", None) if act.fuente_m1 else None
        matrices_nom = sorted(list({p.matriz_origen for p in act.participaciones if p.matriz_origen}))
        hash_m1 = fuentes_consolidacion.get("M1").hash_sha256 if "M1" in fuentes_consolidacion else None

        detalles_traz = {"clave_negocio": str(act.clave_negocio)}
        if act.trazabilidad.get("eje_complementario_nominal"):
            detalles_traz["eje_complementario_nominal"] = str(act.trazabilidad["eje_complementario_nominal"])
            detalles_traz["procedencia_eje_complementario"] = str(
                act.trazabilidad.get("procedencia_eje_complementario", "NOMINAL_AUDITORIA")
            )
        if act.fuente_m1 and act.fuente_m1.ambito is None:
            detalles_traz["m1_ambito_declarado"] = "AUSENTE"

        # Trazabilidad y procedencia de programa institucional
        progs_act = cls._obtener_programas_nominales_actividad(act)
        m1_prog = (
            (act.fuente_m1.area_responsable or act.fuente_m1.nombre_area or act.fuente_m1.programa)
            if act.fuente_m1 else (act.area_responsable or act.programa)
        )
        if m1_prog and str(m1_prog).strip():
            detalles_traz["programa_origen"] = "M1"
            detalles_traz["programa_declarado"] = str(m1_prog).strip()
        elif len(progs_act) == 1:
            detalles_traz["programa_inferido_nominal"] = progs_act[0]
            detalles_traz["procedencia_programa"] = "M2/M3_NOMINAL_UNIVOCO"
            detalles_traz["motivo_inferencia"] = "M1_SIN_PROGRAMA_INFERENCIA_PRESENTACION"
        elif len(progs_act) > 1:
            detalles_traz["discrepancia_programa_nominal"] = (
                f"Ambigüedad M2/M3: {', '.join(sorted(progs_act))}"
            )

        traz = TrazabilidadActividad(
            id_actividad=act.id_actividad,
            matriz_m1_origen=m1_arch,
            fila_m1_origen=m1_fila,
            matrices_nominales=matrices_nom,
            total_filas_nominales=len(act.participaciones),
            hash_m1=hash_m1,
            detalles=detalles_traz,
        )

        return ActividadInstitucional(
            id_actividad=act.id_actividad,
            numero_orden=numero_orden,
            nombre_actividad=act.nombre_actividad,
            eje_vinculado=act.eje.strip() if act.eje else "",
            descripcion=descripcion,
            sede=act.sede,
            departamento=act.departamento.strip() if act.departamento else "",
            municipio=act.municipio.strip() if act.municipio else "",
            tipo_actividad=act.tipo_evento.strip() if act.tipo_evento else "",
            protagonistas=protagonistas,
            totales_actividad=totales_act,
            discrepancias=discrepancias_doc,
            evidencias=evidencias_sec,
            trazabilidad=traz,
        )

    @classmethod
    def _construir_protagonistas(
        cls,
        act: ActividadConsolidada,
        politica_presentacion: str,
    ) -> List[ProtagonistaEstamentoInstitucional]:
        resultado: List[ProtagonistaEstamentoInstitucional] = []

        # Definición de estamentos y extracción de cifras
        estamentos_def = [
            (
                TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS,
                "Maestras y maestros",
                (act.totales_nominales.docentes_f, act.totales_nominales.docentes_m, act.totales_nominales.docentes),
                (
                    (act.totales_m1.docentes_f, act.totales_m1.docentes_m, act.totales_m1.total_docentes)
                    if act.totales_m1 else None
                ),
            ),
            (
                TipoEstamentoInstitucional.ESTUDIANTES,
                "Estudiantes",
                (act.totales_nominales.estudiantes_f, act.totales_nominales.estudiantes_m, act.totales_nominales.estudiantes),
                (
                    (act.totales_m1.estudiantes_f, act.totales_m1.estudiantes_m, act.totales_m1.total_estudiantes)
                    if act.totales_m1 else None
                ),
            ),
            (
                TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO,
                "Personal administrativo",
                (
                    act.totales_nominales.administrativos_f + act.totales_nominales.no_docentes_f,
                    act.totales_nominales.administrativos_m + act.totales_nominales.no_docentes_m,
                    act.totales_nominales.administrativos + act.totales_nominales.no_docentes,
                ),
                (
                    (act.totales_m1.administrativos_f, act.totales_m1.administrativos_m, act.totales_m1.total_administrativos)
                    if act.totales_m1 else None
                ),
            ),
            (
                TipoEstamentoInstitucional.COLABORADORES,
                "Colaboradores",
                (act.totales_nominales.colaboradores_f, act.totales_nominales.colaboradores_m, act.totales_nominales.colaboradores),
                (
                    (act.totales_m1.colaboradores_f, act.totales_m1.colaboradores_m, act.totales_m1.total_colaboradores)
                    if act.totales_m1 else None
                ),
            ),
            (
                TipoEstamentoInstitucional.BENEFICIARIOS_POBLADORES,
                "Beneficiarios / Pobladores",
                (act.totales_nominales.beneficiarios_f, act.totales_nominales.beneficiarios_m, act.totales_nominales.beneficiarios),
                (
                    (act.totales_m1.protagonistas_f, act.totales_m1.protagonistas_m, act.totales_m1.total_protagonistas)
                    if act.totales_m1 else None
                ),
            ),
        ]

        for est_tipo, denom, nom_tup, decl_tup in estamentos_def:
            m_nom, v_nom, tot_nom = nom_tup
            m_decl, v_decl, tot_decl = decl_tup if decl_tup else (0, 0, 0)
            tiene_declarado = decl_tup is not None

            # C7: Regla de inclusión según política institucional
            participo_efectivo = (tot_nom > 0)
            declarado_positivo = (tiene_declarado and tot_decl > 0)

            if politica_presentacion in ("DECLARADO", "DECLARADO_M1"):
                # Bajo DECLARADO_M1, solo incluir si M1 declaró participantes positivos
                if not declarado_positivo:
                    continue
            else:
                # Política NOMINAL o NOMINAL_CON_FALLBACK: mantener comportamiento existente
                if not (participo_efectivo or declarado_positivo):
                    continue

            # Objeto de dato nominal
            dato_nominal = ConteoSexoInstitucional(
                mujeres=m_nom,
                varones=v_nom,
                total=m_nom + v_nom,
            )

            # Objeto de dato declarado
            dato_declarado = (
                ConteoSexoInstitucional(
                    mujeres=m_decl,
                    varones=v_decl,
                    total=m_decl + v_decl,
                )
                if tiene_declarado
                else None
            )

            # Discrepancia a nivel de estamento
            tiene_disc = False
            disc_detalle = None
            if dato_declarado is not None:
                delta_m = dato_nominal.mujeres - dato_declarado.mujeres
                delta_v = dato_nominal.varones - dato_declarado.varones
                delta_tot = dato_nominal.total - dato_declarado.total
                if delta_tot != 0 or delta_m != 0 or delta_v != 0:
                    tiene_disc = True
                    disc_detalle = DiscrepanciaEstamento(
                        delta_mujeres=delta_m,
                        delta_varones=delta_v,
                        delta_total=delta_tot,
                        estado="REQUIERE_REVISION",
                        descripcion=(
                            f"Discrepancia en {denom}: Nominal={dato_nominal.total} "
                            f"(M={dato_nominal.mujeres}, V={dato_nominal.varones}) vs "
                            f"Declarado={dato_declarado.total} "
                            f"(M={dato_declarado.mujeres}, V={dato_declarado.varones})."
                        ),
                    )

            # Determinación de conteo_presentacion según política
            if politica_presentacion in ("DECLARADO", "DECLARADO_M1"):
                if dato_declarado is not None:
                    conteo_pres = dato_declarado
                else:
                    conteo_pres = ConteoSexoInstitucional(mujeres=0, varones=0, total=0)
            elif politica_presentacion == "NOMINAL":
                conteo_pres = dato_nominal
            else:  # "NOMINAL_CON_FALLBACK"
                if dato_nominal.total > 0:
                    conteo_pres = dato_nominal
                elif dato_declarado is not None and dato_declarado.total > 0:
                    conteo_pres = dato_declarado
                else:
                    conteo_pres = dato_nominal

            protagonista = ProtagonistaEstamentoInstitucional(
                estamento_tipo=est_tipo,
                denominacion_visible=denom,
                conteo_presentacion=conteo_pres,
                dato_declarado=dato_declarado,
                dato_nominal=dato_nominal,
                tiene_discrepancia=tiene_disc,
                discrepancia_detalle=disc_detalle,
                orden_presentacion=ORDEN_ESTAMENTOS_DEFAULT.get(est_tipo, 10),
            )
            resultado.append(protagonista)

        return resultado

    @classmethod
    def _construir_discrepancias_actividad(
        cls,
        act: ActividadConsolidada,
    ) -> List[DiscrepanciaActividadInstitucional]:
        resultado: List[DiscrepanciaActividadInstitucional] = []
        for d in act.discrepancias:
            delta_total = d.delta if d.delta is not None else (d.valor_nominal - d.valor_m1)
            traz = d.trazabilidad if isinstance(d.trazabilidad, dict) else {}
            decl_m = traz.get("m1_mujeres", 0)
            decl_v = traz.get("m1_varones", 0)
            nom_m = traz.get("nominal_mujeres", 0)
            nom_v = traz.get("nominal_varones", 0)

            item = DiscrepanciaActividadInstitucional(
                estamento=d.estamento,
                fuente_declarada=d.fuente_m1 or "Matriz 1: Consolidado de Actividades",
                fuente_nominal=", ".join(d.fuentes_nominales) if d.fuentes_nominales else "Matrices Nominales",
                declarado_m=decl_m,
                declarado_v=decl_v,
                declarado_total=d.valor_m1,
                nominal_m=nom_m,
                nominal_v=nom_v,
                nominal_total=d.valor_nominal,
                delta_total=delta_total,
                delta_m=nom_m - decl_m,
                delta_v=nom_v - decl_v,
                estado=d.estado.value if hasattr(d.estado, "value") else str(d.estado),
                descripcion=d.descripcion,
            )
            resultado.append(item)
        return resultado
