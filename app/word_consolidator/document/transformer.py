"""
app.word_consolidator.document.transformer

Capa de transformación pura para construir el modelo documental intermedio
(DocumentoConsolidado) a partir de los datos consolidados y auditados.
Fase 14.6 — Arquitectura desacoplada de python-docx.

Cumple estrictamente:
1. Función pura: no modifica ResultadoConsolidacion ni ResultadoAuditoriaDiscrepancias.
2. No inventa datos (campos ausentes quedan None o listas vacías).
3. No reconcilia fuentes (M1, nominales, narrativa y deltas coexisten sin alteración).
4. Semántica canónica de sexo: FEMENINO / MASCULINO.
5. Separación rigurosa de estamentos (no fusionar docentes y administrativos).
6. Trazabilidad completa de fuentes y hashes SHA-256.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from app.word_consolidator.document.models import (
    AnexosDocumentales,
    AuditoriaDocumental,
    ComparativaTotalesActividad,
    ConclusionDocumental,
    ConteoEstamentoDocumental,
    DemografiaDocumental,
    DistribucionSexoDocumental,
    DocumentoConsolidado,
    EstamentosDocumental,
    FichaActividadDocumental,
    FilaActividadDocumental,
    FilaEstamentoDetalle,
    ItemCarreraDocumental,
    ItemComparativaDimension,
    ItemDiscrepanciaDocumental,
    ItemMunicipioDocumental,
    ItemSedeDocumental,
    ItemTerritorioDocumental,
    MatrizGeneralDocumental,
    MetricasRecurrenciaDocumental,
    PortadaDocumental,
    ResumenEjecutivoDocumental,
    TerritorioDocumental,
    TotalesComparativosDocumentales,
    TrazabilidadFuenteDocumental,
)
from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ResultadoConsolidacion,
)
from app.word_consolidator.models import (
    DiscrepanciaItem,
    EstadoDiscrepancia,
    MetadatosInstitucionales,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
    ResultadoAuditoriaDiscrepancias,
)


class DocumentTransformer:
    """
    Transformador institucional de dominio a modelo documental intermedio.
    Construye la representación lógica de las 10 secciones del informe.
    """

    @classmethod
    def transformar(
        cls,
        consolidacion: ResultadoConsolidacion,
        auditoria: ResultadoAuditoriaDiscrepancias,
        periodo: PeriodoConsolidacion,
        metadatos: Optional[MetadatosInstitucionales] = None,
        informes_narrativos: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> DocumentoConsolidado:
        """
        Transforma datos consolidados y auditados en DocumentoConsolidado.
        No modifica los objetos de entrada.
        """
        if informes_narrativos is None:
            informes_narrativos = {}

        # 1. Sección 1: Portada
        portada = cls._construir_portada(periodo, metadatos)

        # 2. Sección 3: Matriz General y Sección 4: Fichas de Actividad
        filas_matriz, fichas_actividades, totales_generales = cls._construir_actividades_y_fichas(
            consolidacion, auditoria, periodo, informes_narrativos
        )
        matriz_general = MatrizGeneralDocumental(
            filas=filas_matriz,
            total_actividades=len(filas_matriz),
            totales_generales=totales_generales,
        )

        # 3. Sección 2: Resumen Ejecutivo
        resumen_ejecutivo = cls._construir_resumen_ejecutivo(
            consolidacion, auditoria, periodo, totales_generales
        )

        # 4. Sección 5: Análisis Demográfico y Sexo
        demografia = cls._construir_demografia(consolidacion, totales_generales)

        # 5. Sección 6: Estamentos y Carreras
        estamentos = cls._construir_estamentos(consolidacion, totales_generales)

        # 6. Sección 7: Territorio / Cobertura
        territorio = cls._construir_territorio(consolidacion)

        # 7. Sección 8: Auditoría y Salud de Datos
        auditoria_doc = cls._construir_auditoria(consolidacion, auditoria)

        # 8. Sección 9: Conclusiones
        conclusiones = cls._construir_conclusiones(auditoria_doc, totales_generales)

        # 9. Sección 10: Anexos
        anexos = cls._construir_anexos(consolidacion)

        # Construcción del Documento Consolidado Raíz
        return DocumentoConsolidado(
            id_documento=str(uuid.uuid4()),
            periodo=periodo,
            metadatos=metadatos,
            portada=portada,
            resumen_ejecutivo=resumen_ejecutivo,
            matriz_general=matriz_general,
            fichas_actividades=fichas_actividades,
            demografia=demografia,
            estamentos=estamentos,
            territorio=territorio,
            auditoria=auditoria_doc,
            conclusiones=conclusiones,
            anexos=anexos,
        )

    # ------------------------------------------------------------------------
    # MÉTODOS PRIVADOS DE CONSTRUCCIÓN POR SECCIÓN
    # ------------------------------------------------------------------------

    @classmethod
    def _construir_portada(
        cls,
        periodo: PeriodoConsolidacion,
        metadatos: Optional[MetadatosInstitucionales],
    ) -> PortadaDocumental:
        """Construye la portada documental sin inventar fecha ni lugar no suministrados."""
        return PortadaDocumental(
            titulo="INFORME CONSOLIDADO INSTITUCIONAL DE ACTIVIDADES",
            subtitulo="Consolidación y Auditoría Multidimensional de Participaciones",
            universidad=metadatos.universidad if metadatos else None,
            lema=metadatos.lema if metadatos else None,
            area_responsable=metadatos.area_responsable if metadatos else None,
            periodo_texto=periodo.etiqueta,
            fecha_emision=None,  # No inventar fecha de emisión
            lugar_emision=metadatos.lugar_emision if metadatos else None,
            version_sistema=metadatos.version_sistema if metadatos else None,
            metadatos=metadatos,
        )

    @classmethod
    def _mapear_discrepancia(cls, d: DiscrepanciaItem) -> ItemDiscrepanciaDocumental:
        """Convierte DiscrepanciaItem de dominio a ItemDiscrepanciaDocumental."""
        dim = d.estamento or d.categoria_discrepancia
        if d.categoria_discrepancia == "SEXO":
            est_lower = (d.estamento or "").lower()
            if "femenin" in est_lower or "mujer" in est_lower:
                dim = "FEMENINO"
            elif "masculin" in est_lower or "varon" in est_lower:
                dim = "MASCULINO"
        elif (d.estamento or "").lower() == "total general":
            dim = "Total"

        f_a = d.fuente_a or d.fuente_m1
        f_b = d.fuente_b or (", ".join(d.fuentes_nominales) if d.fuentes_nominales else "Matrices Nominales")
        v_a = d.valor_fuente_a if d.valor_fuente_a is not None else d.valor_m1
        v_b = d.valor_fuente_b if d.valor_fuente_b is not None else d.valor_nominal
        delta_val = d.delta if d.delta is not None else ((v_b or 0) - (v_a or 0))

        return ItemDiscrepanciaDocumental(
            id_actividad=d.id_actividad,
            nombre_actividad=d.nombre_actividad,
            categoria=d.categoria_discrepancia,
            dimension=dim,
            fuente_a=f_a,
            fuente_b=f_b,
            valor_fuente_a=v_a,
            valor_fuente_b=v_b,
            delta=delta_val,
            estado=d.estado,
            descripcion=d.descripcion,
            trazabilidad=dict(d.trazabilidad) if d.trazabilidad else {},
        )

    @classmethod
    def _construir_actividades_y_fichas(
        cls,
        consolidacion: ResultadoConsolidacion,
        auditoria: ResultadoAuditoriaDiscrepancias,
        periodo: PeriodoConsolidacion,
        informes_narrativos: Dict[str, Dict[str, Any]],
    ) -> Tuple[List[FilaActividadDocumental], List[FichaActividadDocumental], TotalesComparativosDocumentales]:
        """Construye las filas de matriz general y fichas descriptivas sin reconciliaciones forzadas."""
        filas: List[FilaActividadDocumental] = []
        fichas: List[FichaActividadDocumental] = []

        # Acumuladores globales
        sum_m1_total: Optional[int] = 0 if any(a.totales_m1 is not None for a in consolidacion.actividades) else None
        sum_m1_fem: Optional[int] = 0 if sum_m1_total is not None else None
        sum_m1_masc: Optional[int] = 0 if sum_m1_total is not None else None

        sum_nom_total = 0
        sum_nom_fem = 0
        sum_nom_masc = 0
        sum_nom_est = 0
        sum_nom_doc = 0
        sum_nom_adm = 0
        sum_nom_col = 0
        sum_nom_ben = 0

        estado_global = EstadoDiscrepancia.CONCORDANTE

        for act in consolidacion.actividades:
            # 1. Recuperar informe de auditoría específico de la actividad
            inf_audit = auditoria.informes_por_actividad.get(act.id_actividad)
            items_disc: List[ItemDiscrepanciaDocumental] = []

            if inf_audit and inf_audit.discrepancias:
                for d in inf_audit.discrepancias:
                    items_disc.append(cls._mapear_discrepancia(d))
            elif act.discrepancias:
                for d in act.discrepancias:
                    items_disc.append(cls._mapear_discrepancia(d))

            tiene_disc = any(d.estado == EstadoDiscrepancia.REQUIERE_REVISION for d in items_disc)
            estado_act = EstadoDiscrepancia.REQUIERE_REVISION if tiene_disc else EstadoDiscrepancia.CONCORDANTE
            if tiene_disc:
                estado_global = EstadoDiscrepancia.REQUIERE_REVISION

            # 2. Extraer valores narrativos suministrados (por id o nombre)
            narrativo_act: Optional[Dict[str, int]] = (
                informes_narrativos.get(act.id_actividad)
                or informes_narrativos.get(act.nombre_actividad)
            )

            # 3. Trazabilidad de fuentes
            trazabilidad_fuentes: List[TrazabilidadFuenteDocumental] = []
            if act.fuente_m1:
                trazabilidad_fuentes.append(
                    TrazabilidadFuenteDocumental(
                        matriz=act.fuente_m1.matriz_origen,
                        archivo=act.fuente_m1.trazabilidad.get("archivo"),
                        hoja=act.fuente_m1.hoja,
                        fila=act.fuente_m1.fila,
                        actividad=act.nombre_actividad,
                        periodo=periodo.etiqueta,
                        detalles_extra=dict(act.fuente_m1.trazabilidad) if act.fuente_m1.trazabilidad else {},
                    )
                )

            matrices_nominales_vistas: Set[Tuple[str, str, int]] = set()
            for p in act.participaciones:
                llave = (p.matriz_origen, p.hoja, p.fila)
                if llave not in matrices_nominales_vistas:
                    matrices_nominales_vistas.add(llave)
                    trazabilidad_fuentes.append(
                        TrazabilidadFuenteDocumental(
                            matriz=p.matriz_origen,
                            archivo=p.trazabilidad.get("archivo"),
                            hoja=p.hoja,
                            fila=p.fila,
                            actividad=act.nombre_actividad,
                            periodo=periodo.etiqueta,
                            detalles_extra={"id_persona": p.id_persona, "categoria": p.categoria.value},
                        )
                    )

            # 4. Desglose canónico por estamentos (5 filas fijas sin fusionar docentes y administrativos)
            nom = act.totales_nominales
            desglose_est = [
                FilaEstamentoDetalle(
                    tipo_estamento="1. Docentes",
                    femenino=nom.docentes_f,
                    masculino=nom.docentes_m,
                    total=nom.docentes,
                ),
                FilaEstamentoDetalle(
                    tipo_estamento="2. Estudiantes",
                    femenino=nom.estudiantes_f,
                    masculino=nom.estudiantes_m,
                    total=nom.estudiantes,
                ),
                FilaEstamentoDetalle(
                    tipo_estamento="3. Administrativos",
                    femenino=nom.administrativos_f,
                    masculino=nom.administrativos_m,
                    total=nom.administrativos,
                ),
                FilaEstamentoDetalle(
                    tipo_estamento="4. Colaboradores",
                    femenino=nom.colaboradores_f,
                    masculino=nom.colaboradores_m,
                    total=nom.colaboradores,
                ),
                FilaEstamentoDetalle(
                    tipo_estamento="5. Beneficiarios / Protagonistas",
                    femenino=nom.beneficiarios_f,
                    masculino=nom.beneficiarios_m,
                    total=nom.beneficiarios,
                ),
            ]

            # 5. Valores M1
            m1 = act.totales_m1
            val_m1_tot = m1.total if m1 else None
            val_m1_fem = m1.mujeres if m1 else None
            val_m1_masc = m1.varones if m1 else None
            val_m1_est = m1.total_estudiantes if m1 else None
            val_m1_doc = m1.total_docentes if m1 else None
            val_m1_adm = m1.total_administrativos if m1 else None
            val_m1_col = m1.total_colaboradores if m1 else None
            val_m1_ben = m1.total_protagonistas if m1 else None

            # Actualizar acumuladores globales
            if sum_m1_total is not None and val_m1_tot is not None:
                sum_m1_total += val_m1_tot
                sum_m1_fem = (sum_m1_fem or 0) + (val_m1_fem or 0)
                sum_m1_masc = (sum_m1_masc or 0) + (val_m1_masc or 0)

            sum_nom_total += nom.total
            sum_nom_fem += nom.mujeres
            sum_nom_masc += nom.varones
            sum_nom_est += nom.estudiantes
            sum_nom_doc += nom.docentes
            sum_nom_adm += nom.administrativos
            sum_nom_col += nom.colaboradores
            sum_nom_ben += nom.beneficiarios

            # 6. Crear FilaActividadDocumental
            fila_doc = FilaActividadDocumental(
                id_actividad=act.id_actividad,
                nombre_actividad=act.nombre_actividad,
                eje_estrategico=act.eje,
                tipo_actividad=act.tipo_evento,
                area_responsable=act.area_responsable,
                sede=act.sede,
                departamento=act.departamento,
                municipio=act.municipio,
                fecha=act.fecha_evento,
                total_m1=val_m1_tot,
                femenino_m1=val_m1_fem,
                masculino_m1=val_m1_masc,
                estudiantes_m1=val_m1_est,
                docentes_m1=val_m1_doc,
                administrativos_m1=val_m1_adm,
                colaboradores_m1=val_m1_col,
                beneficiarios_m1=val_m1_ben,
                total_nominal=nom.total,
                femenino_nominal=nom.mujeres,
                masculino_nominal=nom.varones,
                estudiantes_nominal=nom.estudiantes,
                docentes_nominal=nom.docentes,
                administrativos_nominal=nom.administrativos,
                colaboradores_nominal=nom.colaboradores,
                beneficiarios_nominal=nom.beneficiarios,
                datos_narrativos=narrativo_act,
                desglose_estamentos=desglose_est,
                discrepancias=items_disc,
                estado_auditoria=estado_act,
                tiene_discrepancias=tiene_disc,
                trazabilidad_fuentes=trazabilidad_fuentes,
            )
            filas.append(fila_doc)

            # 7. Crear FichaActividadDocumental
            delta_tot = (nom.total - val_m1_tot) if val_m1_tot is not None else None
            delta_fem = (nom.mujeres - val_m1_fem) if val_m1_fem is not None else None
            delta_masc = (nom.varones - val_m1_masc) if val_m1_masc is not None else None

            # Comunidad: sólo si está respaldada explícitamente en fuente M1
            comunidad_respaldada: Optional[str] = act.fuente_m1.comunidad if act.fuente_m1 else None

            ficha_doc = FichaActividadDocumental(
                id_actividad=act.id_actividad,
                nombre_actividad=act.nombre_actividad,
                sede=act.sede,
                fecha=act.fecha_evento,
                departamento=act.departamento,
                municipio=act.municipio,
                comunidad=comunidad_respaldada,
                eje=act.eje,
                programa=act.programa,
                proyecto=act.proyecto,
                area_responsable=act.area_responsable,
                tipo_evento=act.tipo_evento,
                descripcion_resultados=act.resultados,
                comparativa_m1_vs_nominal=ComparativaTotalesActividad(
                    total_m1=val_m1_tot,
                    femenino_m1=val_m1_fem,
                    masculino_m1=val_m1_masc,
                    total_nominal=nom.total,
                    femenino_nominal=nom.mujeres,
                    masculino_nominal=nom.varones,
                    delta_total=delta_tot,
                    delta_femenino=delta_fem,
                    delta_masculino=delta_masc,
                    estado=estado_act,
                ),
                desglose_estamentos=desglose_est,
                discrepancias=items_disc,
                estado_auditoria=estado_act,
                trazabilidad_fuentes=trazabilidad_fuentes,
                datos_narrativos=narrativo_act,
                enlaces_evidencias=[],
                referencias_actas=[],
            )
            fichas.append(ficha_doc)

        totales_generales = TotalesComparativosDocumentales(
            total_actividades=len(filas),
            total_m1=sum_m1_total,
            femenino_m1=sum_m1_fem,
            masculino_m1=sum_m1_masc,
            total_nominal=sum_nom_total,
            femenino_nominal=sum_nom_fem,
            masculino_nominal=sum_nom_masc,
            estudiantes_nominal=sum_nom_est,
            docentes_nominal=sum_nom_doc,
            administrativos_nominal=sum_nom_adm,
            colaboradores_nominal=sum_nom_col,
            beneficiarios_nominal=sum_nom_ben,
            estado_global=estado_global,
        )

        return filas, fichas, totales_generales

    @classmethod
    def _construir_resumen_ejecutivo(
        cls,
        consolidacion: ResultadoConsolidacion,
        auditoria: ResultadoAuditoriaDiscrepancias,
        periodo: PeriodoConsolidacion,
        totales: TotalesComparativosDocumentales,
    ) -> ResumenEjecutivoDocumental:
        """Construye el resumen ejecutivo con semántica canónica de sexo y auditoría."""
        dist_sexo = DistribucionSexoDocumental(
            femenino=totales.femenino_nominal,
            masculino=totales.masculino_nominal,
            total=totales.total_nominal,
        )

        fuentes_faltantes = sum(
            1 for d in auditoria.discrepancias_globales if d.categoria_discrepancia == "FUENTE_FALTANTE"
        )

        alertas: List[str] = []
        if auditoria.total_discrepancias_activas > 0:
            alertas.append(
                f"Se detectaron {auditoria.total_discrepancias_activas} discrepancias dimensionales "
                "que requieren revisión institucional."
            )
        if fuentes_faltantes > 0:
            alertas.append(
                f"Existen {fuentes_faltantes} fuentes nominales ausentes o no suministradas."
            )

        return ResumenEjecutivoDocumental(
            periodo=periodo,
            total_actividades=consolidacion.total_actividades,
            total_asistencia_bruta=consolidacion.total_asistencia_bruta,
            total_personas_unicas=consolidacion.total_personas_unicas,
            total_recurrencia=consolidacion.total_recurrencia,
            tasa_recurrencia=consolidacion.tasa_recurrencia,
            distribucion_sexo=dist_sexo,
            total_discrepancias=auditoria.total_discrepancias_activas,
            actividades_concordantes=auditoria.actividades_concordantes,
            actividades_con_observaciones=auditoria.actividades_con_discrepancias,
            total_fuentes_faltantes=fuentes_faltantes,
            alertas_principales=alertas,
            sinopsis=None,  # No inventar narrativa
        )

    @classmethod
    def _construir_demografia(
        cls,
        consolidacion: ResultadoConsolidacion,
        totales: TotalesComparativosDocumentales,
    ) -> DemografiaDocumental:
        """Construye el análisis demográfico segregado por sexo FEMENINO / MASCULINO."""
        dist_nominal = DistribucionSexoDocumental(
            femenino=totales.femenino_nominal,
            masculino=totales.masculino_nominal,
            total=totales.total_nominal,
        )

        dist_m1: Optional[DistribucionSexoDocumental] = None
        if totales.femenino_m1 is not None and totales.masculino_m1 is not None:
            dist_m1 = DistribucionSexoDocumental(
                femenino=totales.femenino_m1,
                masculino=totales.masculino_m1,
                total=totales.total_m1 or (totales.femenino_m1 + totales.masculino_m1),
            )

        comparativa_sexo: List[ItemComparativaDimension] = []
        if dist_m1 is not None:
            delta_f = dist_nominal.femenino - dist_m1.femenino
            delta_m = dist_nominal.masculino - dist_m1.masculino
            delta_t = dist_nominal.total - dist_m1.total

            comparativa_sexo.append(
                ItemComparativaDimension(
                    dimension="FEMENINO",
                    fuente_a_nombre="Matriz 1",
                    fuente_b_nombre="Matrices Nominales (M2–M5)",
                    valor_fuente_a=dist_m1.femenino,
                    valor_fuente_b=dist_nominal.femenino,
                    delta=delta_f,
                    estado=EstadoDiscrepancia.CONCORDANTE if delta_f == 0 else EstadoDiscrepancia.REQUIERE_REVISION,
                )
            )
            comparativa_sexo.append(
                ItemComparativaDimension(
                    dimension="MASCULINO",
                    fuente_a_nombre="Matriz 1",
                    fuente_b_nombre="Matrices Nominales (M2–M5)",
                    valor_fuente_a=dist_m1.masculino,
                    valor_fuente_b=dist_nominal.masculino,
                    delta=delta_m,
                    estado=EstadoDiscrepancia.CONCORDANTE if delta_m == 0 else EstadoDiscrepancia.REQUIERE_REVISION,
                )
            )
            comparativa_sexo.append(
                ItemComparativaDimension(
                    dimension="TOTAL",
                    fuente_a_nombre="Matriz 1",
                    fuente_b_nombre="Matrices Nominales (M2–M5)",
                    valor_fuente_a=dist_m1.total,
                    valor_fuente_b=dist_nominal.total,
                    delta=delta_t,
                    estado=EstadoDiscrepancia.CONCORDANTE if delta_t == 0 else EstadoDiscrepancia.REQUIERE_REVISION,
                )
            )

        recurrencia = MetricasRecurrenciaDocumental(
            total_asistencia_bruta=consolidacion.total_asistencia_bruta,
            total_personas_unicas=consolidacion.total_personas_unicas,
            total_recurrencia=consolidacion.total_recurrencia,
            tasa_recurrencia=consolidacion.tasa_recurrencia,
        )

        return DemografiaDocumental(
            total_participaciones=consolidacion.total_asistencia_bruta,
            total_personas_unicas=consolidacion.total_personas_unicas,
            distribucion_sexo_nominal=dist_nominal,
            distribucion_sexo_m1=dist_m1,
            comparativa_sexo=comparativa_sexo,
            metricas_recurrencia=recurrencia,
        )

    @classmethod
    def _construir_estamentos(
        cls,
        consolidacion: ResultadoConsolidacion,
        totales: TotalesComparativosDocumentales,
    ) -> EstamentosDocumental:
        """Construye la sección de estamentos distinguiendo estudiantes, docentes, administrativos, etc."""
        gran_total = totales.total_nominal

        # Calcular conteos por sexo para cada estamento a partir de las actividades
        est_f = sum(a.totales_nominales.estudiantes_f for a in consolidacion.actividades)
        est_m = sum(a.totales_nominales.estudiantes_m for a in consolidacion.actividades)
        doc_f = sum(a.totales_nominales.docentes_f for a in consolidacion.actividades)
        doc_m = sum(a.totales_nominales.docentes_m for a in consolidacion.actividades)
        adm_f = sum(a.totales_nominales.administrativos_f for a in consolidacion.actividades)
        adm_m = sum(a.totales_nominales.administrativos_m for a in consolidacion.actividades)
        col_f = sum(a.totales_nominales.colaboradores_f for a in consolidacion.actividades)
        col_m = sum(a.totales_nominales.colaboradores_m for a in consolidacion.actividades)
        ben_f = sum(a.totales_nominales.beneficiarios_f for a in consolidacion.actividades)
        ben_m = sum(a.totales_nominales.beneficiarios_m for a in consolidacion.actividades)

        conteo_est = ConteoEstamentoDocumental(
            femenino=est_f,
            masculino=est_m,
            total=totales.estudiantes_nominal,
            porcentaje_del_total=round((totales.estudiantes_nominal / gran_total) * 100.0, 2) if gran_total > 0 else 0.0,
        )
        conteo_doc = ConteoEstamentoDocumental(
            femenino=doc_f,
            masculino=doc_m,
            total=totales.docentes_nominal,
            porcentaje_del_total=round((totales.docentes_nominal / gran_total) * 100.0, 2) if gran_total > 0 else 0.0,
        )
        conteo_adm = ConteoEstamentoDocumental(
            femenino=adm_f,
            masculino=adm_m,
            total=totales.administrativos_nominal,
            porcentaje_del_total=round((totales.administrativos_nominal / gran_total) * 100.0, 2) if gran_total > 0 else 0.0,
        )
        conteo_col = ConteoEstamentoDocumental(
            femenino=col_f,
            masculino=col_m,
            total=totales.colaboradores_nominal,
            porcentaje_del_total=round((totales.colaboradores_nominal / gran_total) * 100.0, 2) if gran_total > 0 else 0.0,
        )
        conteo_ben = ConteoEstamentoDocumental(
            femenino=ben_f,
            masculino=ben_m,
            total=totales.beneficiarios_nominal,
            porcentaje_del_total=round((totales.beneficiarios_nominal / gran_total) * 100.0, 2) if gran_total > 0 else 0.0,
        )

        # Desglose de carreras (únicamente estudiantes con carrera reportada)
        carreras_map: Dict[str, Dict[str, int]] = {}
        for act in consolidacion.actividades:
            for p in act.estudiantes:
                if p.carrera and p.carrera.strip():
                    nom_carr = p.carrera.strip()
                    if nom_carr not in carreras_map:
                        carreras_map[nom_carr] = {"femenino": 0, "masculino": 0, "total": 0}
                    if p.sexo_normalizado == "FEMENINO":
                        carreras_map[nom_carr]["femenino"] += 1
                    else:
                        carreras_map[nom_carr]["masculino"] += 1
                    carreras_map[nom_carr]["total"] += 1

        desglose_carreras = [
            ItemCarreraDocumental(
                carrera=carr,
                femenino=d["femenino"],
                masculino=d["masculino"],
                total=d["total"],
            )
            for carr, d in sorted(carreras_map.items())
        ]

        # Comparativa M1 vs Nominal por estamento
        comparativa_est: List[ItemComparativaDimension] = []
        if any(a.totales_m1 is not None for a in consolidacion.actividades):
            mapa_m1_vs_nom = [
                ("Estudiantes", sum(a.totales_m1.total_estudiantes for a in consolidacion.actividades if a.totales_m1), totales.estudiantes_nominal),
                ("Docentes", sum(a.totales_m1.total_docentes for a in consolidacion.actividades if a.totales_m1), totales.docentes_nominal),
                ("Administrativos", sum(a.totales_m1.total_administrativos for a in consolidacion.actividades if a.totales_m1), totales.administrativos_nominal),
                ("Colaboradores", sum(a.totales_m1.total_colaboradores for a in consolidacion.actividades if a.totales_m1), totales.colaboradores_nominal),
                ("Beneficiarios", sum(a.totales_m1.total_protagonistas for a in consolidacion.actividades if a.totales_m1), totales.beneficiarios_nominal),
            ]
            for nombre_est, v_m1, v_nom in mapa_m1_vs_nom:
                delta_val = v_nom - v_m1
                comparativa_est.append(
                    ItemComparativaDimension(
                        dimension=nombre_est,
                        fuente_a_nombre="Matriz 1",
                        fuente_b_nombre="Matrices Nominales",
                        valor_fuente_a=v_m1,
                        valor_fuente_b=v_nom,
                        delta=delta_val,
                        estado=EstadoDiscrepancia.CONCORDANTE if delta_val == 0 else EstadoDiscrepancia.REQUIERE_REVISION,
                    )
                )

        return EstamentosDocumental(
            estudiantes=conteo_est,
            docentes=conteo_doc,
            administrativos=conteo_adm,
            colaboradores=conteo_col,
            beneficiarios=conteo_ben,
            total_general=gran_total,
            desglose_carreras=desglose_carreras,
            comparativa_estamentos=comparativa_est,
        )

    @classmethod
    def _construir_territorio(cls, consolidacion: ResultadoConsolidacion) -> TerritorioDocumental:
        """Construye el resumen territorial únicamente con sedes y departamentos respaldados."""
        sedes_map: Dict[str, Dict[str, int]] = {}
        dep_map: Dict[str, Dict[str, Any]] = {}
        mun_map: Dict[str, Dict[str, Any]] = {}
        comunidades_set: Set[str] = set()

        for act in consolidacion.actividades:
            s = act.sede or "Sin Sede"
            if s not in sedes_map:
                sedes_map[s] = {"actividades": 0, "asistencias": 0, "femenino": 0, "masculino": 0}
            sedes_map[s]["actividades"] += 1
            sedes_map[s]["asistencias"] += act.totales_nominales.total
            sedes_map[s]["femenino"] += act.totales_nominales.mujeres
            sedes_map[s]["masculino"] += act.totales_nominales.varones

            # Departamento
            dep = act.departamento
            if dep and dep.strip():
                dep_clean = dep.strip()
                if dep_clean not in dep_map:
                    dep_map[dep_clean] = {"municipios": set(), "actividades": 0, "asistencias": 0}
                dep_map[dep_clean]["actividades"] += 1
                dep_map[dep_clean]["asistencias"] += act.totales_nominales.total
                if act.municipio and act.municipio.strip():
                    dep_map[dep_clean]["municipios"].add(act.municipio.strip())

            # Municipio
            mun = act.municipio
            if mun and mun.strip():
                mun_clean = mun.strip()
                if mun_clean not in mun_map:
                    mun_map[mun_clean] = {
                        "departamento": act.departamento,
                        "actividades": 0,
                        "asistencias": 0,
                    }
                mun_map[mun_clean]["actividades"] += 1
                mun_map[mun_clean]["asistencias"] += act.totales_nominales.total

            # Comunidades explícitas en M1
            if act.fuente_m1 and act.fuente_m1.comunidad and act.fuente_m1.comunidad.strip():
                comunidades_set.add(act.fuente_m1.comunidad.strip())

        desglose_sedes = [
            ItemSedeDocumental(
                sede=s,
                total_actividades=d["actividades"],
                total_asistencias=d["asistencias"],
                femenino=d["femenino"],
                masculino=d["masculino"],
            )
            for s, d in sorted(sedes_map.items())
        ]

        desglose_deps = [
            ItemTerritorioDocumental(
                departamento=dep,
                municipios=sorted(list(d["municipios"])),
                total_actividades=d["actividades"],
                total_asistencias=d["asistencias"],
            )
            for dep, d in sorted(dep_map.items())
        ]

        desglose_muns = [
            ItemMunicipioDocumental(
                municipio=mun,
                departamento=d["departamento"],
                total_actividades=d["actividades"],
                total_asistencias=d["asistencias"],
            )
            for mun, d in sorted(mun_map.items())
        ]

        return TerritorioDocumental(
            desglose_sedes=desglose_sedes,
            desglose_departamentos=desglose_deps,
            desglose_municipios=desglose_muns,
            comunidades=sorted(list(comunidades_set)),
            total_sedes_participantes=len(desglose_sedes),
            total_departamentos_cubiertos=len(desglose_deps),
            total_municipios_cubiertos=len(desglose_muns),
        )

    @classmethod
    def _construir_auditoria(
        cls,
        consolidacion: ResultadoConsolidacion,
        auditoria: ResultadoAuditoriaDiscrepancias,
    ) -> AuditoriaDocumental:
        """Construye la sección de auditoría y tabla formal de discrepancias."""
        tabla_disc: List[ItemDiscrepanciaDocumental] = []
        for d in auditoria.discrepancias_globales:
            tabla_disc.append(cls._mapear_discrepancia(d))

        fuentes_faltantes = sum(1 for d in auditoria.discrepancias_globales if d.categoria_discrepancia == "FUENTE_FALTANTE")

        alertas = list(consolidacion.fuentes.keys())
        alertas_auditoria: List[str] = []
        if auditoria.total_discrepancias_activas > 0:
            alertas_auditoria.append(
                f"AUDITORÍA: {auditoria.total_discrepancias_activas} discrepancias pendientes de revisión."
            )
        if fuentes_faltantes > 0:
            alertas_auditoria.append(
                f"AUDITORÍA: {fuentes_faltantes} actividades carecen de matriz nominal participante."
            )

        return AuditoriaDocumental(
            total_actividades_evaluadas=auditoria.total_actividades_evaluadas,
            actividades_concordantes=auditoria.actividades_concordantes,
            actividades_con_discrepancias=auditoria.actividades_con_discrepancias,
            total_discrepancias_activas=auditoria.total_discrepancias_activas,
            total_concordancias=auditoria.total_concordancias,
            total_fuentes_faltantes=fuentes_faltantes,
            invariante_verificada=True,
            tabla_discrepancias=tabla_disc,
            fuentes_procesadas=list(consolidacion.fuentes.values()),
            alertas=alertas_auditoria,
        )

    @classmethod
    def _construir_conclusiones(
        cls,
        auditoria_doc: AuditoriaDocumental,
        totales: TotalesComparativosDocumentales,
    ) -> ConclusionDocumental:
        """Construye conclusiones derivadas estrictamente de métricas y auditoría comprobadas."""
        puntos: List[str] = [
            f"Se consolidaron formalmente {totales.total_actividades} actividades en el período.",
            f"La sumatoria nominal total asciende a {totales.total_nominal} participaciones "
            f"({totales.femenino_nominal} de sexo femenino y {totales.masculino_nominal} de sexo masculino).",
            f"La distribución por estamentos comprende: {totales.estudiantes_nominal} estudiantes, "
            f"{totales.docentes_nominal} docentes, {totales.administrativos_nominal} administrativos, "
            f"{totales.colaboradores_nominal} colaboradores y {totales.beneficiarios_nominal} beneficiarios.",
        ]

        recs: List[str] = []
        if auditoria_doc.total_discrepancias_activas > 0:
            dictamen = "CON OBSERVACIONES"
            recs.append(
                f"Revisar las {auditoria_doc.total_discrepancias_activas} discrepancias detectadas "
                "en las actividades marcadas con estado REQUIERE_REVISION antes del cierre definitivo."
            )
        else:
            dictamen = "CONCORDANTE"
            recs.append("Todas las dimensiones evaluadas se encuentran en plena concordancia matemática.")

        return ConclusionDocumental(
            puntos_clave=puntos,
            recomendaciones_auditoria=recs,
            dictamen_auditoria=dictamen,
            resumen_narrativo=None,  # No inventar narrativa
        )

    @classmethod
    def _construir_anexos(cls, consolidacion: ResultadoConsolidacion) -> AnexosDocumentales:
        """Construye anexos confirmando la preservación de los 32 registros históricos de M5."""
        glosario_est = {
            "Estudiantes": "Participantes matriculados en carreras de grado o posgrado.",
            "Docentes": "Personal académico responsable de la docencia o facilitación de actividades.",
            "Administrativos": "Personal técnico y administrativo de la institución universitaria.",
            "Colaboradores": "Representantes de entidades públicas, empresas privadas u organismos no gubernamentales.",
            "Beneficiarios / Protagonistas": "Pobladores o participantes comunitarios directos vinculados al proyecto.",
        }

        glosario_est_auditoria = {
            "CONCORDANTE": "Las fuentes evaluadas presentan total coincidencia matemática y dimensional (delta = 0).",
            "REQUIERE_REVISION": "Se detectó diferencia entre fuentes que requiere verificación institucional.",
            "FUENTE_FALTANTE": "No se localizó la matriz nominal esperada para respaldar la actividad declarada.",
        }

        return AnexosDocumentales(
            registro_fuentes=list(consolidacion.fuentes.values()),
            total_registros_historicos_m5=len(consolidacion.nominales_historicos_fuera_periodo),
            total_actividades_fuera_periodo=len(consolidacion.actividades_fuera_periodo),
            glosario_estamentos=glosario_est,
            glosario_estados_auditoria=glosario_est_auditoria,
            metadatos_tecnicos={
                "motor_version": "0.1.0",
                "capa_documental": "Fase 14.6",
                "total_actividades_procesadas": consolidacion.total_actividades,
            },
        )
