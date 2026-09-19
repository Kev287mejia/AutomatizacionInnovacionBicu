"""app.quality.rules

Implementación de las 20 reglas Strategy (Q-01 a Q-20) del Motor de Calidad BICU.
Gobernado estrictamente bajo el principio institucional no negociable:
    DETECTAR ≠ CORREGIR (Regla RN-C07).

REGLAS DE DISEÑO:
- Ninguna regla muta ni altera los objetos o colecciones del contexto.
- Q-03: Detecta fecha en cédula, emite advertencia y discrepancia pericial; NUNCA asigna None a Person.cedula.
- Q-20: Detecta posible duplicado nominal sin cédula, alerta y genera discrepancia; NUNCA crea, fusiona ni elimina personas.
- 'REVISION' no es una severidad; solo se utilizan las 4 severidades autorizadas (INFO, WARNING, ERROR, CRITICAL).
"""

from typing import List, Set
from app.core.constants.participant_types import CategoriaParticipacion
from app.matching.person_matcher import PersonMatcher, TipoCoincidenciaPersona
from app.normalization.identifier_normalizer import PATRON_FECHA, PATRON_CEDULA_NI
from app.quality.models import IValidationRule, QualityContext, ValidationFinding


class ReglaQ01CedulaVacia(IValidationRule):
    """Q-01: Detecta participante sin cédula de identidad."""
    codigo_regla = "Q-01"
    nombre_regla = "Cédula Vacía o Nula"
    dimension = "1. Identidad"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for p in ctx.personas:
            if not p.cedula or not p.cedula.strip():
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=p.id_persona_interno,
                        entidad_afectada="PERSONA",
                        campo_origen="cedula",
                        valor_detectado=None,
                        valor_esperado="Cédula oficial (14 dígitos con letra)",
                        mensaje_humano=f"Participante '{p.nombre_completo}' no cuenta con cédula de identidad.",
                        fuente_archivo=p.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ02CedulaFormatoDudoso(IValidationRule):
    """Q-02: Detecta cédula que no cumple formato canónico oficial (14 dígitos y letra)."""
    codigo_regla = "Q-02"
    nombre_regla = "Cédula con Formato Dudoso"
    dimension = "1. Identidad"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for p in ctx.personas:
            if p.cedula and p.cedula.strip():
                val = p.cedula.strip()
                # Si cumple patrón de fecha, es evaluado por Q-03
                if PATRON_FECHA.match(val):
                    continue
                if not PATRON_CEDULA_NI.match(val):
                    findings.append(
                        ValidationFinding(
                            codigo_regla=self.codigo_regla,
                            severidad=self.severidad_por_defecto,
                            id_referencia=p.id_persona_interno,
                            entidad_afectada="PERSONA",
                            campo_origen="cedula",
                            valor_detectado=val,
                            valor_esperado="000-000000-0000X (14 dígitos + letra)",
                            mensaje_humano=f"Cédula '{val}' para '{p.nombre_completo}' no cumple formato canónico nicaragüense.",
                            fuente_archivo=p.fuente_origen,
                            requiere_discrepancia_persistente=False,
                        )
                    )
        return findings


class ReglaQ03FechaEnCedula(IValidationRule):
    """Q-03: Detecta fecha de nacimiento en campo cédula.
    
    GARANTÍA RN-C07:
    - Preserva intacto el valor en Person.cedula (NUNCA lo asigna a None ni lo normaliza).
    - Emite hallazgo pericial y bandera de discrepancia persistente tipo OTRO.
    """
    codigo_regla = "Q-03"
    nombre_regla = "Fecha de Nacimiento en Casilla Cédula"
    dimension = "1. Identidad"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for p in ctx.personas:
            if p.cedula and p.cedula.strip():
                val = p.cedula.strip()
                if PATRON_FECHA.match(val):
                    findings.append(
                        ValidationFinding(
                            codigo_regla=self.codigo_regla,
                            severidad=self.severidad_por_defecto,
                            id_referencia=p.id_persona_interno,
                            entidad_afectada="PERSONA",
                            campo_origen="cedula",
                            valor_detectado=val,
                            valor_esperado="Cédula oficial de identidad (no fecha)",
                            mensaje_humano=(
                                f"Posible fecha de nacimiento en campo cédula: '{val}' "
                                f"para '{p.nombre_completo}'. Requiere revisión."
                            ),
                            fuente_archivo=p.fuente_origen,
                            requiere_discrepancia_persistente=True,
                        )
                    )
        return findings


class ReglaQ04NombreVacio(IValidationRule):
    """Q-04: Detecta nombre de participante vacío o ausente (Error bloqueante)."""
    codigo_regla = "Q-04"
    nombre_regla = "Nombre Completo Ausente o Vacío"
    dimension = "1. Identidad"
    severidad_por_defecto = "ERROR"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for p in ctx.personas:
            if not p.nombre_completo or not p.nombre_completo.strip():
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=p.id_persona_interno,
                        entidad_afectada="PERSONA",
                        campo_origen="nombre_completo",
                        valor_detectado="",
                        valor_esperado="Nombres y apellidos completos",
                        mensaje_humano="Nombre completo del participante vacío o ausente. Bloquea la exportación del registro.",
                        fuente_archivo=p.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ05SexoIncompatible(IValidationRule):
    """Q-05: Detecta código de sexo no reconocido según catálogo de fuente."""
    codigo_regla = "Q-05"
    nombre_regla = "Sexo No Normalizado o Incompatible"
    dimension = "5. Datos Demográficos"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for p in ctx.personas:
            if p.sexo_original and not p.sexo_normalizado:
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=p.id_persona_interno,
                        entidad_afectada="PERSONA",
                        campo_origen="sexo",
                        valor_detectado=p.sexo_original,
                        valor_esperado="MASCULINO o FEMENINO según fuente",
                        mensaje_humano=(
                            f"Sexo no normalizado o incompatible ('{p.sexo_original}') "
                            f"para '{p.nombre_completo}' en fuente '{p.sexo_fuente or p.fuente_origen}'."
                        ),
                        fuente_archivo=p.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ06SexoAusente(IValidationRule):
    """Q-06: Detecta sexo ausente en la fuente sin inferir por nombre."""
    codigo_regla = "Q-06"
    nombre_regla = "Sexo Ausente"
    dimension = "5. Datos Demográficos"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for p in ctx.personas:
            if not p.sexo_original and not p.sexo_normalizado:
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=p.id_persona_interno,
                        entidad_afectada="PERSONA",
                        campo_origen="sexo",
                        valor_detectado=None,
                        valor_esperado="Sexo declarado en fuente",
                        mensaje_humano=f"Sexo no especificado para '{p.nombre_completo}'. No se infiere por nombre.",
                        fuente_archivo=p.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ07EdadAusente(IValidationRule):
    """Q-07: Detecta edad no reportada sin inventar número."""
    codigo_regla = "Q-07"
    nombre_regla = "Edad Ausente"
    dimension = "5. Datos Demográficos"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for p in ctx.personas:
            if p.edad is None:
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=p.id_persona_interno,
                        entidad_afectada="PERSONA",
                        campo_origen="edad",
                        valor_detectado=None,
                        valor_esperado="Edad en años cumplidos",
                        mensaje_humano=f"Edad no especificada para '{p.nombre_completo}'.",
                        fuente_archivo=p.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ08EdadAtipicaEstamento(IValidationRule):
    """Q-08: Detecta edad menor de 16 años reportada en categoría Docente o Administrativo."""
    codigo_regla = "Q-08"
    nombre_regla = "Edad Atípica para Estamento"
    dimension = "5. Datos Demográficos"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        mapa_personas = {p.id_persona_interno: p for p in ctx.personas}

        for part in ctx.participaciones:
            p = mapa_personas.get(part.id_persona)
            if p and p.edad is not None and p.edad < 16:
                cat = part.categoria_participacion
                cat_val = cat.value if hasattr(cat, "value") else str(cat)
                if cat_val in ("DOCENTE", "ADMINISTRATIVO"):
                    findings.append(
                        ValidationFinding(
                            codigo_regla=self.codigo_regla,
                            severidad=self.severidad_por_defecto,
                            id_referencia=part.id_participacion,
                            entidad_afectada="PARTICIPACION",
                            campo_origen="edad",
                            valor_detectado=str(p.edad),
                            valor_esperado=">= 16 años para estamento laboral",
                            mensaje_humano=(
                                f"Edad reportada ({p.edad} años) para '{p.nombre_completo}' "
                                f"es atípica para la categoría '{cat_val}'. Requiere confirmación humana. "
                                "No se asume error institucional."
                            ),
                            fuente_archivo=part.fuente_origen,
                            requiere_discrepancia_persistente=False,
                        )
                    )
        return findings


class ReglaQ09CarreraAbreviadaAmbigua(IValidationRule):
    """Q-09: Detecta carreras abreviadas o denominaciones ambiguas."""
    codigo_regla = "Q-09"
    nombre_regla = "Carrera Abreviada o Ambigua"
    dimension = "6. Datos Académicos"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for p in ctx.personas:
            if p.carrera_original:
                c_raw = p.carrera_original.strip()
                c_lower = c_raw.lower()
                if c_lower in ("a. estudiantil", "a estudiantil"):
                    findings.append(
                        ValidationFinding(
                            codigo_regla=self.codigo_regla,
                            severidad=self.severidad_por_defecto,
                            id_referencia=p.id_persona_interno,
                            entidad_afectada="PERSONA",
                            campo_origen="carrera_original",
                            valor_detectado=c_raw,
                            valor_esperado="Denominación académica no ambigua",
                            mensaje_humano=f"Carrera o área ambigua '{c_raw}' para '{p.nombre_completo}'.",
                            fuente_archivo=p.fuente_origen,
                            requiere_discrepancia_persistente=False,
                        )
                    )
                elif "." in c_raw or len(c_raw) <= 4:
                    findings.append(
                        ValidationFinding(
                            codigo_regla=self.codigo_regla,
                            severidad=self.severidad_por_defecto,
                            id_referencia=p.id_persona_interno,
                            entidad_afectada="PERSONA",
                            campo_origen="carrera_original",
                            valor_detectado=c_raw,
                            valor_esperado="Nombre completo de carrera",
                            mensaje_humano=f"Carrera posiblemente abreviada '{c_raw}' para '{p.nombre_completo}'.",
                            fuente_archivo=p.fuente_origen,
                            requiere_discrepancia_persistente=False,
                        )
                    )
        return findings


class ReglaQ10CarreraNoHomologada(IValidationRule):
    """Q-10: Detecta carrera fuera de catálogo oficial (OPEN-01).
    
    GARANTÍA RN-C07: Conserva texto crudo; marca revisión pericial sin forzar homologación.
    """
    codigo_regla = "Q-10"
    nombre_regla = "Carrera Fuera de Catálogo Oficial"
    dimension = "6. Datos Académicos"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        catalogo = [c.strip().upper() for c in ctx.catalogo_carreras] if ctx.catalogo_carreras else []

        for p in ctx.personas:
            if p.carrera_original and p.carrera_original.strip():
                c_nom = p.carrera_original.strip().upper()
                no_esta_en_catalogo = catalogo and (c_nom not in catalogo)
                no_homologada = p.carrera_oficial is None

                if no_esta_en_catalogo or no_homologada:
                    findings.append(
                        ValidationFinding(
                            codigo_regla=self.codigo_regla,
                            severidad=self.severidad_por_defecto,
                            id_referencia=p.id_persona_interno,
                            entidad_afectada="PERSONA",
                            campo_origen="carrera_original",
                            valor_detectado=p.carrera_original,
                            valor_esperado="Carrera homologada en catálogo institucional (OPEN-01)",
                            mensaje_humano=(
                                f"Carrera '{p.carrera_original}' de '{p.nombre_completo}' "
                                "pendiente de homologación pericial oficial."
                            ),
                            fuente_archivo=p.fuente_origen,
                            requiere_discrepancia_persistente=False,
                        )
                    )
        return findings


class ReglaQ11EtniaNoCatalogada(IValidationRule):
    """Q-11: Detecta etnia no listada en catálogo oficial (OPEN-04).
    
    GARANTÍA RN-C07: Preserva la autodefinición comunitaria; no sustituye automáticamente.
    """
    codigo_regla = "Q-11"
    nombre_regla = "Etnia Fuera de Catálogo Oficial"
    dimension = "5. Datos Demográficos"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        if not ctx.catalogo_etnias:
            return findings

        cat_etnias = {e.strip().upper() for e in ctx.catalogo_etnias}
        for p in ctx.personas:
            if p.etnia and p.etnia.strip():
                if p.etnia.strip().upper() not in cat_etnias:
                    findings.append(
                        ValidationFinding(
                            codigo_regla=self.codigo_regla,
                            severidad=self.severidad_por_defecto,
                            id_referencia=p.id_persona_interno,
                            entidad_afectada="PERSONA",
                            campo_origen="etnia",
                            valor_detectado=p.etnia,
                            valor_esperado="Etnia oficial según catálogo institucional (OPEN-04)",
                            mensaje_humano=(
                                f"Etnia declarada '{p.etnia}' para '{p.nombre_completo}' no listada en catálogo. "
                                "Se preserva autodefinición comunitaria legítima sin bloquear."
                            ),
                            fuente_archivo=p.fuente_origen,
                            requiere_discrepancia_persistente=False,
                        )
                    )
        return findings


class ReglaQ12CategoriaDesconocida(IValidationRule):
    """Q-12: Detecta categoría de participación no determinable (Enruta a COLA_REVISION)."""
    codigo_regla = "Q-12"
    nombre_regla = "Categoría de Participación Desconocida"
    dimension = "2. Participación"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for part in ctx.participaciones:
            cat = part.categoria_participacion
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            if cat == CategoriaParticipacion.DESCONOCIDO or cat_val == "DESCONOCIDO":
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=part.id_participacion,
                        entidad_afectada="PARTICIPACION",
                        campo_origen="categoria_participacion",
                        valor_detectado="DESCONOCIDO",
                        valor_esperado="Categoría institucional válida (ESTUDIANTE, DOCENTE, etc.)",
                        mensaje_humano="Participación con categoría DESCONOCIDO. Asignado a COLA_REVISION para resolución pericial.",
                        fuente_archivo=part.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ13ParticipacionRepetida(IValidationRule):
    """Q-13: Detecta segunda o ulterior asistencia de una persona en la misma actividad (RN-C06).
    
    GARANTÍA RN-C07:
    - No crea una segunda fila física en SQLite.
    - No elimina ni sobreescribe observaciones anteriores.
    - Emite hallazgo pericial y bandera de discrepancia persistente tipo OTRO.
    """
    codigo_regla = "Q-13"
    nombre_regla = "Participación Repetida en Actividad"
    dimension = "2. Participación"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        vistos: Set[str] = set()

        for part in ctx.participaciones:
            clave = (part.id_actividad, part.id_persona)
            if clave in vistos:
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=part.id_participacion,
                        entidad_afectada="PARTICIPACION",
                        campo_origen="id_persona",
                        valor_detectado=part.id_persona,
                        valor_esperado="Asistencia única por participante en actividad",
                        mensaje_humano=(
                            f"Participación repetida detectada en la misma actividad para id_persona '{part.id_persona}'. "
                            "Se enriquece evidencia pericial sin duplicar registro ni eliminar datos."
                        ),
                        fuente_archivo=part.fuente_origen,
                        requiere_discrepancia_persistente=True,
                    )
                )
            else:
                vistos.add(clave)
        return findings


class ReglaQ14PrevalenciaBeneficiario(IValidationRule):
    """Q-14: Informativo de prevalencia de rol beneficiario sobre estamento estudiante (RN-C03)."""
    codigo_regla = "Q-14"
    nombre_regla = "Prevalencia de Estudiante Beneficiario"
    dimension = "2. Participación"
    severidad_por_defecto = "INFO"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        for part in ctx.participaciones:
            cat = part.categoria_participacion
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            if (cat == CategoriaParticipacion.ESTUDIANTE or cat_val == "ESTUDIANTE") and getattr(part, "es_beneficiado_rol", False):
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=part.id_participacion,
                        entidad_afectada="PARTICIPACION",
                        campo_origen="es_beneficiado_rol",
                        valor_detectado="True",
                        valor_esperado="Enrutamiento oficial a M5 (Protagonistas Beneficiados)",
                        mensaje_humano=(
                            "Estudiante actuando contextualmente como beneficiario directo. "
                            "Enrutado a M5 por regla RN-C03 preservando estamento Estudiante."
                        ),
                        fuente_archivo=part.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ15IntegridadReferencialHuerfana(IValidationRule):
    """Q-15: Detecta claves foráneas huérfanas en participación (Error bloqueante)."""
    codigo_regla = "Q-15"
    nombre_regla = "Integridad Referencial Huérfana"
    dimension = "2. Participación"
    severidad_por_defecto = "ERROR"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        ids_personas = {p.id_persona_interno for p in ctx.personas}
        id_actividad = ctx.actividad.id_actividad if ctx.actividad else None

        for part in ctx.participaciones:
            # Validar id_actividad
            if id_actividad and part.id_actividad != id_actividad:
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=part.id_participacion,
                        entidad_afectada="PARTICIPACION",
                        campo_origen="id_actividad",
                        valor_detectado=part.id_actividad,
                        valor_esperado=id_actividad,
                        mensaje_humano=(
                            f"La participación '{part.id_participacion}' referencia a un id_actividad "
                            f"huérfano ('{part.id_actividad}'). Estado asignado: BLOQUEADO."
                        ),
                        fuente_archivo=part.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
            # Validar id_persona
            if ids_personas and part.id_persona not in ids_personas:
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=part.id_participacion,
                        entidad_afectada="PARTICIPACION",
                        campo_origen="id_persona",
                        valor_detectado=part.id_persona,
                        valor_esperado="Persona existente registrada en el SSOT",
                        mensaje_humano=(
                            f"La participación '{part.id_participacion}' referencia a un id_persona "
                            f"inexistente ('{part.id_persona}'). Estado asignado: BLOQUEADO."
                        ),
                        fuente_archivo=part.fuente_origen,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ16TituloDiscordanteWordVsAsistencia(IValidationRule):
    """Q-16: Detecta diferencia textual de título entre informe Word y lista física."""
    codigo_regla = "Q-16"
    nombre_regla = "Título Discordante Word vs Asistencia"
    dimension = "10. Documentación"
    severidad_por_defecto = "INFO"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        if ctx.actividad and ctx.titulo_informe:
            tit_act = ctx.actividad.nombre_actividad_original.strip()
            tit_inf = ctx.titulo_informe.strip()
            if tit_act != tit_inf:
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=ctx.actividad.id_actividad,
                        entidad_afectada="ACTIVIDAD",
                        campo_origen="nombre_actividad_original",
                        valor_detectado=tit_inf,
                        valor_esperado=tit_act,
                        mensaje_humano=(
                            f"Diferencia textual entre título en informe Word ('{tit_inf}') "
                            f"y lista de asistencia ('{tit_act}'). Unificados por evidencia múltiple sin alterar origen."
                        ),
                        fuente_archivo=ctx.fuente_archivo_informe,
                        requiere_discrepancia_persistente=False,
                    )
                )
        return findings


class ReglaQ17FechaDiscordanteWordVsAsistencia(IValidationRule):
    """Q-17: Detecta contradicción de fechas entre informe narrativo y firmas."""
    codigo_regla = "Q-17"
    nombre_regla = "Fecha Discordante Word vs Asistencia"
    dimension = "10. Documentación"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        fecha_act = str(ctx.actividad.fecha_evento).strip() if ctx.actividad and ctx.actividad.fecha_evento else None
        fecha_asist = str(ctx.fecha_asistencia_declarada).strip() if ctx.fecha_asistencia_declarada else fecha_act
        fecha_inf = str(ctx.fecha_informe).strip() if ctx.fecha_informe else None

        if fecha_inf and fecha_asist and fecha_inf != fecha_asist:
            act_id = ctx.actividad.id_actividad if ctx.actividad else "ACTIVIDAD"
            findings.append(
                ValidationFinding(
                    codigo_regla=self.codigo_regla,
                    severidad=self.severidad_por_defecto,
                    id_referencia=act_id,
                    entidad_afectada="ACTIVIDAD",
                    campo_origen="fecha_evento",
                    valor_detectado=fecha_inf,
                    valor_esperado=fecha_asist,
                    mensaje_humano=(
                        f"Fecha discordante entre informe narrativo ('{fecha_inf}') "
                        f"y firmas de asistencia ('{fecha_asist}'). Requiere revisión."
                    ),
                    fuente_archivo=ctx.fuente_archivo_informe,
                    requiere_discrepancia_persistente=True,
                )
            )
        return findings


class ReglaQ18MetaPlanificadaVsAsistenciasReales(IValidationRule):
    """Q-18: Detecta divergencia entre meta planificada y participantes reales."""
    codigo_regla = "Q-18"
    nombre_regla = "Meta Planificada vs Asistencias Reales"
    dimension = "4. Planificación"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        if ctx.meta_planificada is not None:
            total_real = len(ctx.participaciones)
            if total_real != ctx.meta_planificada:
                act_id = ctx.actividad.id_actividad if ctx.actividad else "ACTIVIDAD"
                delta = total_real - ctx.meta_planificada
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=act_id,
                        entidad_afectada="ACTIVIDAD",
                        campo_origen="meta_participantes",
                        valor_detectado=str(total_real),
                        valor_esperado=str(ctx.meta_planificada),
                        mensaje_humano=(
                            f"Divergencia entre participantes reales ({total_real}) "
                            f"y meta planificada ({ctx.meta_planificada}). Delta: {delta}."
                        ),
                        fuente_archivo=ctx.fuente_archivo_asistencia,
                        requiere_discrepancia_persistente=True,
                    )
                )
        return findings


class ReglaQ19ConteoNarrativoVsFilasNominales(IValidationRule):
    """Q-19: Detecta divergencia entre total de participantes en informe narrativo y firmas reales."""
    codigo_regla = "Q-19"
    nombre_regla = "Conteo Narrativo vs Filas Nominales"
    dimension = "11. Consolidación"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        if ctx.total_asistentes_declarados_informe is not None:
            total_nominal = len(ctx.participaciones)
            if total_nominal != ctx.total_asistentes_declarados_informe:
                act_id = ctx.actividad.id_actividad if ctx.actividad else "ACTIVIDAD"
                delta = total_nominal - ctx.total_asistentes_declarados_informe
                findings.append(
                    ValidationFinding(
                        codigo_regla=self.codigo_regla,
                        severidad=self.severidad_por_defecto,
                        id_referencia=act_id,
                        entidad_afectada="INFORME",
                        campo_origen="total_participantes_declarados",
                        valor_detectado=str(ctx.total_asistentes_declarados_informe),
                        valor_esperado=str(total_nominal),
                        mensaje_humano=(
                            f"Divergencia cuantitativa entre participantes declarados en informe narrativo "
                            f"({ctx.total_asistentes_declarados_informe}) y firmas nominales ({total_nominal}). "
                            f"Delta: {delta}."
                        ),
                        fuente_archivo=ctx.fuente_archivo_informe,
                        requiere_discrepancia_persistente=True,
                    )
                )
        return findings


class ReglaQ20PosibleDuplicadoPersona(IValidationRule):
    """Q-20: Detecta coincidencia nominal o fonética alta entre personas sin cédula (C-09).
    
    GARANTÍA RN-C07:
    - NO crea personas.
    - NO fusiona personas.
    - NO elimina personas.
    - NO altera la identidad ni confianza de ninguna persona.
    - Emite hallazgo pericial y bandera de discrepancia tipo OTRO.
    """
    codigo_regla = "Q-20"
    nombre_regla = "Posible Duplicado de Persona sin Cédula"
    dimension = "1. Identidad"
    severidad_por_defecto = "WARNING"

    def evaluar(self, ctx: QualityContext) -> List[ValidationFinding]:
        findings = []
        personas = ctx.personas
        n = len(personas)

        # Evaluar pares sin cédula
        for i in range(n):
            p1 = personas[i]
            if p1.cedula and p1.cedula.strip():
                continue
            for j in range(i + 1, n):
                p2 = personas[j]
                if p2.cedula and p2.cedula.strip():
                    continue

                # Comparación mediante PersonMatcher
                comp = PersonMatcher.comparar_personas(p1, p2)
                if comp.tipo_coincidencia in (
                    TipoCoincidenciaPersona.CANDIDATO_REVISION,
                    TipoCoincidenciaPersona.FUSION_AUTOMATICA,
                ):
                    findings.append(
                        ValidationFinding(
                            codigo_regla=self.codigo_regla,
                            severidad=self.severidad_por_defecto,
                            id_referencia=p1.id_persona_interno,
                            entidad_afectada="PERSONA",
                            campo_origen="nombre_completo",
                            valor_detectado=p1.nombre_completo,
                            valor_esperado=f"Candidato: {p2.nombre_completo} ({p2.id_persona_interno})",
                            mensaje_humano=(
                                f"Posible duplicado detectado entre '{p1.nombre_completo}' ({p1.id_persona_interno}) "
                                f"y '{p2.nombre_completo}' ({p2.id_persona_interno}) sin cédula. "
                                "Regla C-09: NUNCA fusionar automáticamente; requiere revisión pericial."
                            ),
                            fuente_archivo=p1.fuente_origen,
                            requiere_discrepancia_persistente=True,
                        )
                    )
        return findings
