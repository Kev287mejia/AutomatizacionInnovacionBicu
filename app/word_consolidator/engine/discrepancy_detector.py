"""
app.word_consolidator.engine.discrepancy_detector

Detector Formal de Discrepancias Institucionales de BICU (Fase 14.5).
Implementa rigurosamente el Protocolo de 9 Pasos para contrastar las fuentes de datos:
M1 agregada vs. sumatoria nominal de M2–M5, e Informes Narrativos vs. Listas Nominales.

Principios rectores inviolables:
1. NO modificar, sobrescribir, corregir, fusionar ni reconciliar automáticamente ninguna fuente.
2. M1 debe conservar exactamente sus valores originales.
3. M2–M5 deben conservar exactamente sus valores originales.
4. Cuando exista diferencia:
   - conservar valor fuente A;
   - conservar valor fuente B;
   - calcular delta (Fuente B - Fuente A);
   - identificar ambas fuentes;
   - conservar trazabilidad detallada;
   - asignar estado REQUIERE_REVISION.
5. Cuando no exista diferencia:
   - estado CONCORDANTE (delta 0).
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from app.word_consolidator.engine.consolidation_engine import ActividadConsolidada, ResultadoConsolidacion
from app.word_consolidator.models import (
    DiscrepanciaItem,
    EstadoDiscrepancia,
    InformeDiscrepanciasActividad,
    ResultadoAuditoriaDiscrepancias,
)


class DiscrepancyDetector:
    """
    Detector Formal de Discrepancias Institucionales de BICU (Fase 14.5).
    Desacoplado de la persistencia y de la generación de documentos.
    No altera bajo ninguna circunstancia los datos de entrada.
    """

    FUENTE_M1_OFICIAL = "Matriz 1: Consolidado de Actividades"
    FUENTE_M2_ESTUDIANTES = "Matriz 2: Estudiantes"
    FUENTE_M3_ACADEMICOS = "Matriz 3: Académicos y Administrativos"
    FUENTE_M4_COLABORADORES = "Matriz 4: Colaboradores"
    FUENTE_M5_BENEFICIARIOS = "Matriz 5: Protagonistas y Beneficiados"
    FUENTE_NOMINALES_GLOBAL = "Matrices Nominales M2–M5"
    FUENTE_INFORME_NARRATIVO = "Informe Narrativo Preliminar"

    @classmethod
    def evaluar_dimension(
        cls,
        id_actividad: str,
        nombre_actividad: str,
        estamento_o_dimension: str,
        valor_a: int,
        valor_b: int,
        fuente_a_nombre: str,
        fuente_b_nombre: str,
        categoria: str = "ESTAMENTO",
        descripcion_contexto: Optional[str] = None,
        trazabilidad: Optional[Dict[str, Any]] = None,
    ) -> DiscrepanciaItem:
        """
        Evalúa una dimensión o estamento individual entre dos fuentes de información.
        Calcula delta = valor_b - valor_a y asigna CONCORDANTE o REQUIERE_REVISION.
        Conserva fielmente ambos valores originales.
        """
        val_a = max(0, int(valor_a))
        val_b = max(0, int(valor_b))
        delta = val_b - val_a
        diferencia_m1 = val_a - val_b

        if delta == 0:
            estado = EstadoDiscrepancia.CONCORDANTE
            signo_delta = "0"
            desc_default = (
                f"Concordancia confirmada en {estamento_o_dimension}: "
                f"ambas fuentes ({fuente_a_nombre} y {fuente_b_nombre}) reportan {val_a} participantes (delta 0)."
            )
        else:
            estado = EstadoDiscrepancia.REQUIERE_REVISION
            signo_delta = f"+{delta}" if delta > 0 else str(delta)
            desc_default = (
                f"Discrepancia detectada en {estamento_o_dimension}: "
                f"{fuente_b_nombre} registra {val_b} ({signo_delta} respecto a {fuente_a_nombre} que reporta {val_a}). "
                f"Requiere revisión institucional."
            )

        descripcion = descripcion_contexto or desc_default

        traza_dict = {
            "fuente_a": fuente_a_nombre,
            "fuente_b": fuente_b_nombre,
            "valor_fuente_a": val_a,
            "valor_fuente_b": val_b,
            "delta": delta,
            "categoria": categoria,
        }
        if trazabilidad:
            traza_dict.update(trazabilidad)

        fuentes_nom_list = [fuente_b_nombre] if fuente_b_nombre != fuente_a_nombre else [fuente_b_nombre]

        return DiscrepanciaItem(
            id_actividad=id_actividad,
            nombre_actividad=nombre_actividad,
            estamento=estamento_o_dimension,
            fuente_m1=fuente_a_nombre,
            fuentes_nominales=fuentes_nom_list,
            fuente_a=fuente_a_nombre,
            fuente_b=fuente_b_nombre,
            valor_m1=val_a,
            valor_nominal=val_b,
            valor_fuente_a=val_a,
            valor_fuente_b=val_b,
            diferencia=diferencia_m1,
            delta=delta,
            estado=estado,
            categoria_discrepancia=categoria,
            descripcion=descripcion,
            trazabilidad=traza_dict,
        )

    @classmethod
    def evaluar_actividad(
        cls,
        actividad: ActividadConsolidada,
        incluir_concordantes: bool = True,
        evaluar_desglose_sexo_cruzado: bool = False,
    ) -> InformeDiscrepanciasActividad:
        """
        Evalúa integralmente una actividad consolidada aplicando el Protocolo de 9 Pasos.
        Contrasta:
        - M1 vs. totales nominales M2–M5
        - Distribución por estamento (Estudiantes, Docentes, Administrativos, Colaboradores, Beneficiarios)
        - Distribución por sexo (Mujeres, Varones)
        - Total general
        - Detección de fuente faltante si M1 o nominales están ausentes
        """
        items: List[DiscrepanciaItem] = []
        id_act = actividad.id_actividad
        nom_act = actividad.nombre_actividad
        clave_act = actividad.clave_negocio

        # ---------------------------------------------------------------------
        # CASO 1: Fuente M1 ausente (actividad existe sólo en registros nominales)
        # ---------------------------------------------------------------------
        if actividad.totales_m1 is None:
            total_nom = actividad.totales_nominales.total
            item_m1_faltante = cls.evaluar_dimension(
                id_actividad=id_act,
                nombre_actividad=nom_act,
                estamento_o_dimension="Fuente Agregada M1",
                valor_a=0,
                valor_b=total_nom,
                fuente_a_nombre="Matriz 1: Consolidado de Actividades (No reportada)",
                fuente_b_nombre=cls.FUENTE_NOMINALES_GLOBAL,
                categoria="FUENTE_FALTANTE",
                descripcion_contexto=(
                    f"Actividad reportada en registros nominales ({total_nom} participantes) "
                    f"pero ausente en Matriz 1. Requiere revisión institucional."
                ),
                trazabilidad={
                    "tipo_anomalia": "FUENTE_M1_FALTANTE",
                    "clave_negocio": list(clave_act),
                    "participaciones_nominales": len(actividad.participaciones),
                },
            )
            items.append(item_m1_faltante)

            total_disc = 1
            total_conc = 0
            actividad.discrepancias = [item_m1_faltante]
            return InformeDiscrepanciasActividad(
                id_actividad=id_act,
                nombre_actividad=nom_act,
                clave_negocio=clave_act,
                total_evaluaciones=1,
                total_discrepancias=total_disc,
                total_concordantes=total_conc,
                tiene_discrepancias=True,
                discrepancias=items,
            )

        # ---------------------------------------------------------------------
        # CASO 2: M1 presente pero sin registros nominales de soporte
        # ---------------------------------------------------------------------
        tot_m1 = actividad.totales_m1
        tot_nom = actividad.totales_nominales
        traza_m1_base = actividad.trazabilidad.get("fuente_m1", {})

        if tot_nom.total == 0 and tot_m1.total > 0:
            item_nom_faltante = cls.evaluar_dimension(
                id_actividad=id_act,
                nombre_actividad=nom_act,
                estamento_o_dimension="Registros Nominales de Soporte",
                valor_a=tot_m1.total,
                valor_b=0,
                fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
                fuente_b_nombre="Matrices Nominales M2–M5 (Ausentes)",
                categoria="FUENTE_FALTANTE",
                descripcion_contexto=(
                    f"Actividad declarada en Matriz 1 con {tot_m1.total} participantes, "
                    f"pero carece de registros nominales de soporte en M2–M5. Requiere revisión institucional."
                ),
                trazabilidad={
                    "tipo_anomalia": "REGISTROS_NOMINALES_FALTANTES",
                    "columna_m1": "Total",
                    "valor_declarado_m1": tot_m1.total,
                    "fuente_m1": traza_m1_base,
                },
            )
            items.append(item_nom_faltante)

        # ---------------------------------------------------------------------
        # DIMENSIÓN 1: Total General
        # ---------------------------------------------------------------------
        item_total = cls.evaluar_dimension(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            estamento_o_dimension="Total General",
            valor_a=tot_m1.total,
            valor_b=tot_nom.total,
            fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
            fuente_b_nombre=cls.FUENTE_NOMINALES_GLOBAL,
            categoria="TOTAL",
            trazabilidad={
                "columna_m1": "Z+Y (Gran Total)",
                "valor_m1": tot_m1.total,
                "valor_nominal": tot_nom.total,
                "total_asistencias_nominales": actividad.total_asistencia_bruta,
                "personas_unicas": actividad.total_personas_unicas,
            },
        )
        items.append(item_total)

        # ---------------------------------------------------------------------
        # DIMENSIÓN 2: Distribución por Estamento
        # ---------------------------------------------------------------------
        # Estudiantes
        item_est = cls.evaluar_dimension(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            estamento_o_dimension="Estudiantes",
            valor_a=tot_m1.total_estudiantes,
            valor_b=tot_nom.estudiantes,
            fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
            fuente_b_nombre=cls.FUENTE_M2_ESTUDIANTES,
            categoria="ESTAMENTO",
            trazabilidad={
                "columnas_m1": "AA+AB (Estudiantes Grado y Posgrado)",
                "matriz_nominal": "M2",
                "participaciones_m2": len(actividad.estudiantes),
            },
        )
        items.append(item_est)

        # Docentes
        item_doc = cls.evaluar_dimension(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            estamento_o_dimension="Docentes",
            valor_a=tot_m1.total_docentes,
            valor_b=tot_nom.docentes,
            fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
            fuente_b_nombre=cls.FUENTE_M3_ACADEMICOS,
            categoria="ESTAMENTO",
            trazabilidad={
                "columnas_m1": "AC+AD (Docentes)",
                "matriz_nominal": "M3",
                "participaciones_docentes": len(actividad.docentes),
            },
        )
        items.append(item_doc)

        # Administrativos
        item_adm = cls.evaluar_dimension(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            estamento_o_dimension="Administrativos",
            valor_a=tot_m1.total_administrativos,
            valor_b=tot_nom.administrativos,
            fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
            fuente_b_nombre=cls.FUENTE_M3_ACADEMICOS,
            categoria="ESTAMENTO",
            trazabilidad={
                "columnas_m1": "AE+AF (Administrativos)",
                "matriz_nominal": "M3",
                "participaciones_administrativos": len(actividad.administrativos),
                "participaciones_no_docentes": len(actividad.no_docentes),
            },
        )
        items.append(item_adm)

        # Colaboradores
        item_col = cls.evaluar_dimension(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            estamento_o_dimension="Colaboradores",
            valor_a=tot_m1.total_colaboradores,
            valor_b=tot_nom.colaboradores,
            fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
            fuente_b_nombre=cls.FUENTE_M4_COLABORADORES,
            categoria="ESTAMENTO",
            trazabilidad={
                "columnas_m1": "AG-AL (Inst. Pública, Privada, ONG)",
                "matriz_nominal": "M4",
                "participaciones_colaboradores": len(actividad.colaboradores),
            },
        )
        items.append(item_col)

        # Beneficiarios / Protagonistas
        item_ben = cls.evaluar_dimension(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            estamento_o_dimension="Beneficiarios",
            valor_a=tot_m1.total_protagonistas,
            valor_b=tot_nom.beneficiarios,
            fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
            fuente_b_nombre=cls.FUENTE_M5_BENEFICIARIOS,
            categoria="ESTAMENTO",
            trazabilidad={
                "columnas_m1": "AM+AN (Protagonistas)",
                "matriz_nominal": "M5",
                "participaciones_beneficiarios": len(actividad.beneficiarios),
            },
        )
        items.append(item_ben)

        # ---------------------------------------------------------------------
        # DIMENSIÓN 3: Distribución por Sexo
        # ---------------------------------------------------------------------
        # Mujeres
        item_muj = cls.evaluar_dimension(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            estamento_o_dimension="Sexo: Femenino (Mujeres)",
            valor_a=tot_m1.mujeres,
            valor_b=tot_nom.mujeres,
            fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
            fuente_b_nombre=cls.FUENTE_NOMINALES_GLOBAL,
            categoria="SEXO",
            trazabilidad={
                "columna_m1": "Columna Z (Femenino)",
                "conteo_nominal_mujeres": tot_nom.mujeres,
            },
        )
        items.append(item_muj)

        # Varones
        item_var = cls.evaluar_dimension(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            estamento_o_dimension="Sexo: Masculino (Varones)",
            valor_a=tot_m1.varones,
            valor_b=tot_nom.varones,
            fuente_a_nombre=cls.FUENTE_M1_OFICIAL,
            fuente_b_nombre=cls.FUENTE_NOMINALES_GLOBAL,
            categoria="SEXO",
            trazabilidad={
                "columna_m1": "Columna Y (Masculino)",
                "conteo_nominal_varones": tot_nom.varones,
            },
        )
        items.append(item_var)

        # Desglose cruzado por sexo cuando aplique
        if evaluar_desglose_sexo_cruzado:
            # Estudiantes Mujeres y Varones
            items.append(cls.evaluar_dimension(
                id_actividad=id_act, nombre_actividad=nom_act,
                estamento_o_dimension="Estudiantes Mujeres",
                valor_a=tot_m1.estudiantes_f, valor_b=tot_nom.estudiantes_f,
                fuente_a_nombre=cls.FUENTE_M1_OFICIAL, fuente_b_nombre=cls.FUENTE_M2_ESTUDIANTES,
                categoria="SEXO_CRUZADO"
            ))
            items.append(cls.evaluar_dimension(
                id_actividad=id_act, nombre_actividad=nom_act,
                estamento_o_dimension="Estudiantes Varones",
                valor_a=tot_m1.estudiantes_m, valor_b=tot_nom.estudiantes_m,
                fuente_a_nombre=cls.FUENTE_M1_OFICIAL, fuente_b_nombre=cls.FUENTE_M2_ESTUDIANTES,
                categoria="SEXO_CRUZADO"
            ))

        # ---------------------------------------------------------------------
        # Filtrado y conteo de discrepancias
        # ---------------------------------------------------------------------
        discrepancias_activas = [it for it in items if it.estado == EstadoDiscrepancia.REQUIERE_REVISION]
        actividad.discrepancias = discrepancias_activas

        salida_items = items if incluir_concordantes else discrepancias_activas

        total_disc = len(discrepancias_activas)
        total_conc = sum(1 for it in items if it.estado == EstadoDiscrepancia.CONCORDANTE)

        return InformeDiscrepanciasActividad(
            id_actividad=id_act,
            nombre_actividad=nom_act,
            clave_negocio=clave_act,
            total_evaluaciones=len(items),
            total_discrepancias=total_disc,
            total_concordantes=total_conc,
            tiene_discrepancias=(total_disc > 0),
            discrepancias=salida_items,
        )

    @classmethod
    def evaluar_consolidacion(
        cls,
        consolidacion: ResultadoConsolidacion,
        incluir_concordantes: bool = True,
    ) -> ResultadoAuditoriaDiscrepancias:
        """
        Ejecuta la auditoría integral de discrepancias sobre todas las actividades del período consolidado.
        Puebla el inventario global de discrepancias sin alterar ninguna estructura ni archivo.
        """
        informes: Dict[str, InformeDiscrepanciasActividad] = {}
        discrepancias_globales: List[DiscrepanciaItem] = []
        actividades_con_disc = 0
        actividades_conc = 0
        total_disc_activas = 0
        total_concordancias = 0

        for act in consolidacion.actividades:
            inf = cls.evaluar_actividad(act, incluir_concordantes=incluir_concordantes)
            informes[act.id_actividad] = inf

            # Acumular conteos
            if inf.tiene_discrepancias:
                actividades_con_disc += 1
            else:
                actividades_conc += 1

            total_disc_activas += inf.total_discrepancias
            total_concordancias += inf.total_concordantes

            for disc in inf.discrepancias:
                discrepancias_globales.append(disc)

        # Asignar discrepancias activas al resultado consolidado
        consolidacion.discrepancias = [
            d for d in discrepancias_globales if d.estado == EstadoDiscrepancia.REQUIERE_REVISION
        ]

        return ResultadoAuditoriaDiscrepancias(
            total_actividades_evaluadas=len(consolidacion.actividades),
            actividades_con_discrepancias=actividades_con_disc,
            actividades_concordantes=actividades_conc,
            total_discrepancias_activas=total_disc_activas,
            total_concordancias=total_concordancias,
            informes_por_actividad=informes,
            discrepancias_globales=discrepancias_globales,
        )

    @classmethod
    def evaluar_fuentes(
        cls,
        fuente_a_nombre: str,
        fuente_a_datos: Dict[str, int],
        fuente_b_nombre: str,
        fuente_b_datos: Dict[str, int],
        id_actividad: str = "act-manual",
        nombre_actividad: str = "Actividad Institucional Evaluada",
        trazabilidad: Optional[Dict[str, Any]] = None,
        incluir_concordantes: bool = True,
    ) -> List[DiscrepanciaItem]:
        """
        Compara directamente dos fuentes arbitrarias estructuradas como diccionarios de métricas.
        Ejemplo: Informe narrativo vs. Lista nominal.
        """
        claves_ordenadas: List[str] = []
        # Mantener orden institucional canónico
        orden_canonico = [
            "estudiantes", "docentes", "administrativos", "colaboradores",
            "beneficiarios", "mujeres", "varones", "total"
        ]
        todas_claves = set(fuente_a_datos.keys()) | set(fuente_b_datos.keys())
        for k in orden_canonico:
            if k in todas_claves:
                claves_ordenadas.append(k)
        for k in sorted(todas_claves):
            if k not in claves_ordenadas:
                claves_ordenadas.append(k)

        items: List[DiscrepanciaItem] = []
        for clave in claves_ordenadas:
            val_a = fuente_a_datos.get(clave, 0)
            val_b = fuente_b_datos.get(clave, 0)

            categoria = "TOTAL" if clave.lower() == "total" else (
                "SEXO" if clave.lower() in ("mujeres", "varones", "femenino", "masculino") else "ESTAMENTO"
            )

            etiqueta = clave.capitalize()
            traza_local = {"clave_metrica": clave}
            if trazabilidad:
                traza_local.update(trazabilidad)

            item = cls.evaluar_dimension(
                id_actividad=id_actividad,
                nombre_actividad=nombre_actividad,
                estamento_o_dimension=etiqueta,
                valor_a=val_a,
                valor_b=val_b,
                fuente_a_nombre=fuente_a_nombre,
                fuente_b_nombre=fuente_b_nombre,
                categoria=categoria,
                trazabilidad=traza_local,
            )

            if incluir_concordantes or item.estado == EstadoDiscrepancia.REQUIERE_REVISION:
                items.append(item)

        return items

    @classmethod
    def evaluar_caso_narrativo_vs_nominal(
        cls,
        informe_narrativo: Dict[str, int],
        nominales: Dict[str, int],
        id_actividad: str = "caso-real-sept-2026",
        nombre_actividad: str = "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e IA",
        trazabilidad: Optional[Dict[str, Any]] = None,
        incluir_concordantes: bool = True,
    ) -> List[DiscrepanciaItem]:
        """
        Método formal para evaluar el Caso Real obligatorio:
        Informe narrativo preliminar vs. Lista nominal M2–M5.

        Caso de referencia:
        Informe narrativo:
          estudiantes: 15
          administrativos: 2
          docentes: 1
          total: 18
        Nominal:
          estudiantes: 17
          administrativos: 1
          docentes: 0
          total: 18

        Resultado esperado:
          estudiantes: delta +2 → REQUIERE_REVISION
          administrativos: delta -1 → REQUIERE_REVISION
          docentes: delta -1 → REQUIERE_REVISION
          total: delta 0 → CONCORDANTE
        """
        return cls.evaluar_fuentes(
            fuente_a_nombre=cls.FUENTE_INFORME_NARRATIVO,
            fuente_a_datos=informe_narrativo,
            fuente_b_nombre=cls.FUENTE_NOMINALES_GLOBAL,
            fuente_b_datos=nominales,
            id_actividad=id_actividad,
            nombre_actividad=nombre_actividad,
            trazabilidad=trazabilidad or {"contexto": "Auditoría Caso Real Septiembre 2026"},
            incluir_concordantes=incluir_concordantes,
        )
