"""
app.templates_analysis.mapping_manifesto

Motor de Ingeniería de Mapeo de Plantillas (Fase 8B).
Transforma la estructura física descubierta en Fase 8A en un Mapping Manifesto
multidimensional, auditable y respetuoso de la regla de no invención.
"""

import re
from typing import Dict, List, Optional
from app.audit.audit_logger import get_logger
from app.templates_analysis.models import (
    EsquemaPlantilla,
    EstadoMapeo,
    ItemMappingManifesto,
    MappingManifesto,
    TipoMapeoColumna,
)

logger = get_logger(__name__)


class MappingManifestoEngine:
    """
    Generador del Mapping Manifesto basado estrictamente en la inspección física (Fase 8B).
    """

    # Diccionario de reconocimiento semántico de encabezados institucionales
    # Relaciona términos clave detectados en la plantilla física con atributos del modelo SSOT
    PATRONES_SEMANTICOS = {
        # Identificadores y datos personales
        "no": ("numero_secuencial", TipoMapeoColumna.DERIVADO, "Secuencial de fila en matriz", "Ninguna", None),
        "n°": ("numero_secuencial", TipoMapeoColumna.DERIVADO, "Secuencial de fila en matriz", "Ninguna", None),
        "num": ("numero_secuencial", TipoMapeoColumna.DERIVADO, "Secuencial de fila en matriz", "Ninguna", None),
        "cedula": ("persona.cedula", TipoMapeoColumna.DIRECTO, "Cédula de identidad oficial", "Asistencia_Física", None),
        "identificacion": ("persona.cedula", TipoMapeoColumna.DIRECTO, "Documento de identidad", "Asistencia_Física", None),
        "nombre": ("persona.nombre_completo", TipoMapeoColumna.DIRECTO, "Nombres y apellidos completos", "Asistencia_Física", None),
        "nombres": ("persona.nombres", TipoMapeoColumna.DIRECTO, "Nombres del participante", "Asistencia_Física", None),
        "apellidos": ("persona.apellidos", TipoMapeoColumna.DIRECTO, "Apellidos del participante", "Asistencia_Física", None),
        "sexo": ("persona.sexo_normalizado", TipoMapeoColumna.DIRECTO, "Sexo normalizado institucional", "Asistencia_Física", None),
        "genero": ("persona.sexo_normalizado", TipoMapeoColumna.DIRECTO, "Sexo normalizado institucional", "Asistencia_Física", None),
        "edad": ("persona.edad", TipoMapeoColumna.DIRECTO, "Edad en años cumplidos", "Asistencia_Física", None),
        "telefono": ("persona.telefono", TipoMapeoColumna.DIRECTO, "Número telefónico o celular", "Asistencia_Física", None),
        "celular": ("persona.telefono", TipoMapeoColumna.DIRECTO, "Número telefónico o celular", "Asistencia_Física", None),
        "etnia": ("persona.etnia", TipoMapeoColumna.CATALOGO, "Pueblo o etnia de autoidentificación", "Asistencia_Física", "etnias.json"),
        "discapacidad": ("persona.discapacidad", TipoMapeoColumna.DIRECTO, "Condición de discapacidad", "Asistencia_Física", None),

        # Campos académicos e institucionales
        "carrera": ("persona.carrera_normalizada", TipoMapeoColumna.CATALOGO, "Carrera o programa académico", "Asistencia_Física", "carreras.json"),
        "carrera / programa": ("persona.carrera_normalizada", TipoMapeoColumna.CATALOGO, "Carrera o programa académico", "Asistencia_Física", "carreras.json"),
        "facultad": ("persona.area", TipoMapeoColumna.DIRECTO, "Facultad o área universitaria", "Asistencia_Física", None),
        "area": ("persona.area", TipoMapeoColumna.DIRECTO, "Área o dependencia universitaria", "Asistencia_Física", None),
        "cargo": ("persona.cargo", TipoMapeoColumna.DIRECTO, "Cargo o puesto laboral", "Asistencia_Física", None),
        "rol": ("participacion.categoria_participacion", TipoMapeoColumna.DERIVADO, "Rol o subtipo institucional", "Fase6_Routing", None),
        "tipo": ("participacion.categoria_participacion", TipoMapeoColumna.DERIVADO, "Categoría institucional del participante", "Fase6_Routing", None),
        "institucion": ("persona.institucion_procedencia", TipoMapeoColumna.DIRECTO, "Institución u organización externa", "Asistencia_Física", None),
        "organizacion": ("persona.institucion_procedencia", TipoMapeoColumna.DIRECTO, "Institución u organización de procedencia", "Asistencia_Física", None),

        # Campos de actividad y territorio
        "actividad": ("actividad.nombre_actividad_oficial", TipoMapeoColumna.DIRECTO, "Nombre formal de la actividad", "Word/Asistencia", None),
        "nombre de la actividad": ("actividad.nombre_actividad_oficial", TipoMapeoColumna.DIRECTO, "Nombre formal de la actividad", "Word/Asistencia", None),
        "fecha": ("actividad.fecha_evento", TipoMapeoColumna.DIRECTO, "Fecha de realización del evento", "Word/Asistencia", None),
        "sede": ("actividad.sede", TipoMapeoColumna.DIRECTO, "Sede o campus institucional", "Word/Asistencia", None),
        "municipio": ("actividad.municipio_evento", TipoMapeoColumna.CATALOGO, "Municipio territorial", "Word/Asistencia", "municipios.json"),
        "departamento": ("actividad.departamento", TipoMapeoColumna.DIRECTO, "Departamento territorial", "Word/Asistencia", None),
        "comunidad": ("persona.comunidad", TipoMapeoColumna.DIRECTO, "Comunidad o barrio de procedencia", "Asistencia_Física", None),
        "eje": ("actividad.eje_linea_estrategica", TipoMapeoColumna.DIRECTO, "Eje o línea estratégica", "Word", "ambitos.json"),
        "linea": ("actividad.eje_linea_estrategica", TipoMapeoColumna.DIRECTO, "Eje o línea estratégica", "Word", "ambitos.json"),
        "tipo de evento": ("actividad.tipo_evento", TipoMapeoColumna.DIRECTO, "Tipo de actividad o evento", "Word", None),

        # Campos estadísticos agregados (Consolidado de Actividades - Fase 7)
        "total": ("estadistica.total_asistencias", TipoMapeoColumna.CALCULADO, "Total de asistencias en la actividad", "Fase7_Statistics", None),
        "total asistencias": ("estadistica.total_asistencias", TipoMapeoColumna.CALCULADO, "Total de asistencias brutas", "Fase7_Statistics", None),
        "personas unicas": ("estadistica.total_personas_unicas", TipoMapeoColumna.CALCULADO, "Personas únicas netas participantes", "Fase7_Statistics", None),
        "femenino": ("estadistica.desglose_sexo_global.femenino", TipoMapeoColumna.CALCULADO, "Conteo de participación femenina", "Fase7_Statistics", None),
        "masculino": ("estadistica.desglose_sexo_global.masculino", TipoMapeoColumna.CALCULADO, "Conteo de participación masculina", "Fase7_Statistics", None),
        "estudiantes": ("estadistica.estudiantes.conteo_sexo.total", TipoMapeoColumna.CALCULADO, "Conteo total de estudiantes participantes", "Fase7_Statistics", None),
        "docentes": ("estadistica.docentes.conteo_sexo.total", TipoMapeoColumna.CALCULADO, "Conteo total de docentes (rol académico)", "Fase7_Statistics", None),
        "administrativos": ("estadistica.administrativos_no_docentes.conteo_sexo.total", TipoMapeoColumna.CALCULADO, "Conteo de personal administrativo y no docente", "Fase7_Statistics", None),
        "beneficiados": ("estadistica.beneficiados.conteo_sexo.total", TipoMapeoColumna.CALCULADO, "Conteo de protagonistas beneficiados / pobladores", "Fase7_Statistics", None),
        "colaboradores": ("estadistica.colaboradores.conteo_sexo.total", TipoMapeoColumna.CALCULADO, "Conteo de colaboradores y aliados institucionales", "Fase7_Statistics", None),

        # Observaciones y control
        "observaciones": ("enrutamiento.observaciones", TipoMapeoColumna.DERIVADO, "Estado operativo y advertencias no bloqueantes", "Fase6_Routing", None),
        "estado": ("enrutamiento.estado_operativo", TipoMapeoColumna.DERIVADO, "Estado operativo: APTO o EN_REVISION", "Fase6_Routing", None),
    }

    @classmethod
    def generar_manifesto(
        cls,
        esquema: EsquemaPlantilla,
        catalogos_disponibles: Optional[Dict[str, bool]] = None,
    ) -> MappingManifesto:
        """
        Genera el Mapping Manifesto a partir de la anatomía física descubierta por Fase 8A.

        Args:
            esquema: Esquema descubierto por TemplateInspector.
            catalogos_disponibles: Diccionario que indica si un catálogo JSON está cargado y no vacío.

        Returns:
            MappingManifesto estructurado y auditable.
        """
        if catalogos_disponibles is None:
            # Por defecto verificar si carreras.json o etnias.json están activos
            catalogos_disponibles = {
                "carreras.json": False,  # Vacío hasta confirmación oficial P-06
                "etnias.json": True,
                "municipios.json": False,
                "ambitos.json": False,
            }

        logger.info(f"Construyendo Mapping Manifesto para: {esquema.nombre_matriz} ({esquema.id_matriz})")

        items: List[ItemMappingManifesto] = []
        col_dir = 0
        col_calc = 0
        col_sin = 0
        col_cat_pend = 0

        # Identificar coordenadas de columnas que tienen fórmulas existentes (PROTEGIDO)
        columnas_con_formulas = set(c.columna for c in esquema.celdas_protegidas if c.tipo_proteccion == "FORMULA")

        for col in esquema.columnas_detectadas:
            enc_orig = col.encabezado_principal.strip()
            enc_norm = enc_orig.lower()

            # Revisar si la columna contiene fórmulas estructuradas de edad (DATEDIF) que deben protegerse
            tiene_datedif = any(
                cp.columna == col.indice_columna and "DATEDIF" in (cp.formula or "").upper()
                for cp in esquema.celdas_protegidas
            )
            if tiene_datedif or (esquema.es_oficial and enc_norm == "edad"):
                item = ItemMappingManifesto(
                    matriz=esquema.nombre_matriz,
                    hoja=esquema.hoja_inspeccionada,
                    columna_letra=col.letra_columna,
                    columna_indice=col.indice_columna,
                    encabezado_original=enc_orig,
                    significado_interpretado="Edad Dinámica (Fórmula DATEDIF)",
                    campo_ssot_fuente="FORMULA_NATIVA",
                    tipo_mapeo=TipoMapeoColumna.PROTEGIDO,
                    transformacion='Preservar intacta fórmula =DATEDIF(Tabla1[[#This Row],[Fecha_nacimiento]], TODAY(), "Y")',
                    catalogo_requerido=None,
                    obligatoriedad=False,
                    fuente_del_dato="Plantilla_Excel",
                    estado=EstadoMapeo.VALIDADO,
                    nivel_confianza="ALTO",
                    observaciones="Fórmula estructurada nativa de Excel. No sobrescribir con entero estático.",
                )
                items.append(item)
                continue

            # Revisar si toda la columna es una fórmula preexistente de totales
            if col.indice_columna in columnas_con_formulas and not enc_orig:
                item = ItemMappingManifesto(
                    matriz=esquema.nombre_matriz,
                    hoja=esquema.hoja_inspeccionada,
                    columna_letra=col.letra_columna,
                    columna_indice=col.indice_columna,
                    encabezado_original=enc_orig or f"Columna {col.letra_columna}",
                    significado_interpretado="Fórmula o Total Preexistente Protegido",
                    campo_ssot_fuente=None,
                    tipo_mapeo=TipoMapeoColumna.PROTEGIDO,
                    transformacion=None,
                    catalogo_requerido=None,
                    obligatoriedad=False,
                    fuente_del_dato="Plantilla_Excel",
                    estado=EstadoMapeo.VALIDADO,
                    nivel_confianza="ALTO",
                    observaciones="Celda o columna con fórmula detectada. Preservar intacta sin sobrescribir.",
                )
                items.append(item)
                continue

            # Buscar coincidencia semántica en el diccionario institucional
            patron_encontrado = None
            if enc_norm in cls.PATRONES_SEMANTICOS:
                patron_encontrado = cls.PATRONES_SEMANTICOS[enc_norm]
            else:
                for clave_patron in sorted(cls.PATRONES_SEMANTICOS.keys(), key=len, reverse=True):
                    if clave_patron in ("no", "n°", "no.", "num"):
                        if (
                            enc_norm == clave_patron
                            or enc_norm.startswith(f"{clave_patron}.")
                            or enc_norm.startswith(f"{clave_patron} ")
                        ):
                            patron_encontrado = cls.PATRONES_SEMANTICOS[clave_patron]
                            break
                    else:
                        patron_regex = r"(?:^|\b|\s)" + re.escape(clave_patron) + r"(?:$|\b|\s)"
                        if re.search(patron_regex, enc_norm):
                            patron_encontrado = cls.PATRONES_SEMANTICOS[clave_patron]
                            break

            if patron_encontrado:
                ssot_campo, tipo_map, significado, fuente, cat_req = patron_encontrado

                estado_item = EstadoMapeo.VALIDADO
                obs = "Mapeo semántico identificado conforme a especificación institucional."

                # Validar disponibilidad de catálogo
                if tipo_map == TipoMapeoColumna.CATALOGO and cat_req:
                    if not catalogos_disponibles.get(cat_req, False):
                        estado_item = EstadoMapeo.CATALOGO_PENDIENTE
                        col_cat_pend += 1
                        obs = (
                            f"Depende del catálogo institucional '{cat_req}'. Actualmente pendiente de "
                            "confirmación oficial; se conserva valor original sin inventar homologaciones."
                        )

                if tipo_map == TipoMapeoColumna.DIRECTO:
                    col_dir += 1
                elif tipo_map == TipoMapeoColumna.CALCULADO:
                    col_calc += 1

                item = ItemMappingManifesto(
                    matriz=esquema.nombre_matriz,
                    hoja=esquema.hoja_inspeccionada,
                    columna_letra=col.letra_columna,
                    columna_indice=col.indice_columna,
                    encabezado_original=enc_orig,
                    significado_interpretado=significado,
                    campo_ssot_fuente=ssot_campo,
                    tipo_mapeo=tipo_map,
                    transformacion=f"Asignación desde {ssot_campo}",
                    catalogo_requerido=cat_req,
                    obligatoriedad=True if tipo_map in (TipoMapeoColumna.DIRECTO, TipoMapeoColumna.CALCULADO) else False,
                    fuente_del_dato=fuente,
                    estado=estado_item,
                    nivel_confianza="ALTO",
                    observaciones=obs,
                )
            else:
                # Campo no reconocido o sin fuente en los documentos de entrada
                col_sin += 1
                item = ItemMappingManifesto(
                    matriz=esquema.nombre_matriz,
                    hoja=esquema.hoja_inspeccionada,
                    columna_letra=col.letra_columna,
                    columna_indice=col.indice_columna,
                    encabezado_original=enc_orig or f"Columna {col.letra_columna}",
                    significado_interpretado=f"Campo no identificado en fuentes estándar: '{enc_orig}'",
                    campo_ssot_fuente=None,
                    tipo_mapeo=TipoMapeoColumna.SIN_FUENTE,
                    transformacion=None,
                    catalogo_requerido=None,
                    obligatoriedad=False,
                    fuente_del_dato="Ninguna",
                    estado=EstadoMapeo.SIN_FUENTE,
                    nivel_confianza="BAJO",
                    observaciones=(
                        "Principio de No Invención: No existe fuente identificada en Word ni en listas físicas. "
                        "El sistema conservará esta celda en blanco y se remitirá a REQUIERE_REVISION si es obligatoria."
                    ),
                )

            items.append(item)

        total_cols = len(items)
        logger.info(
            f"Mapping Manifesto generado: {esquema.id_matriz} - Total={total_cols}, Directas={col_dir}, "
            f"Calculadas={col_calc}, SinFuente={col_sin}, CatPendiente={col_cat_pend}"
        )

        return MappingManifesto(
            id_matriz=esquema.id_matriz,
            nombre_matriz=esquema.nombre_matriz,
            hoja=esquema.hoja_inspeccionada,
            items=items,
            total_columnas=total_cols,
            columnas_directas=col_dir,
            columnas_calculadas=col_calc,
            columnas_sin_fuente=col_sin,
            columnas_catalogo_pendiente=col_cat_pend,
        )
