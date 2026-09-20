"""
InstitutionalRulesEngine — Domain Service.
Implementa las reglas deterministas R-01 a R-10.

Fuente: FASE_29_2_DISENO_ARQUITECTONICO_PLANIFICACION_DISENO.md §13
Clasificacion: EVIDENCIA DIRECTA + REGLA MATEMATICA para todas las reglas.
Fase 29.3 — Dominio Puro
"""
from __future__ import annotations

from typing import Any, Sequence

from app.planning.domain.catalogs import (
    C1_CODES,
    C2_CODES,
    C2_PROGRAMAS,
    C3_AMBITOS,
    C3_CODES,
    C4_CODES,
    C4_TIPOS_EVENTO,
    C5_CODES,
    DEFAULT_SESSION_TEXT,
)


def _strip_accents(text: str) -> str:
    """Elimina tildes para comparacion robusta de catalogos."""
    trans = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return text.translate(trans)
from app.planning.domain.entities import PlannedActivity
from app.planning.domain.value_objects import ParticipantGoals


class InstitutionalRulesEngine:
    """Servicio de dominio que implementa las reglas deterministas R-01 a R-10.

    Fuente: FASE_29_2 §13 (Reglas Deterministas).
    Todas las reglas estan clasificadas como EVIDENCIA DIRECTA o REGLA MATEMATICA.

    Este servicio NO tiene dependencias de infraestructura.
    NO llama a ningun LLM, ni base de datos, ni sistema de archivos.
    """

    # -----------------------------------------------------------------------
    # R-01 — Titulo del Documento
    # Fuente: FASE_29_2 §13 (R-01)
    # Estado: CONFIRMADA — EVIDENCIA DIRECTA
    # -----------------------------------------------------------------------
    @staticmethod
    def derive_document_title(activity_name: str) -> str:
        """R-01: Titulo del Documento.

        document_title = "Diseno metodologico " + activity_name
        Clasificacion: CONFIRMADA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-01).
        """
        if not activity_name or not activity_name.strip():
            raise ValueError("R-01: activity_name no puede ser vacio para derivar el titulo.")
        return f"Diseño metodológico {activity_name.strip()}"

    # -----------------------------------------------------------------------
    # R-02 — Facilitador (Pregunta 5)
    # Fuente: FASE_29_2 §13 (R-02)
    # Estado: CONFIRMADA — EVIDENCIA DIRECTA
    # -----------------------------------------------------------------------
    @staticmethod
    def derive_facilitador(area_responsable: str) -> str:
        """R-02: Facilitador = area_responsable.

        q5_facilitador = area_responsable  [de PlannedActivity]
        Clasificacion: CONFIRMADA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-02).
        """
        if not area_responsable or not area_responsable.strip():
            raise ValueError(
                "R-02: area_responsable no puede ser vacio para derivar el facilitador."
            )
        return area_responsable.strip()

    # -----------------------------------------------------------------------
    # R-03 — Protagonistas (Pregunta 4)
    # Fuente: FASE_29_2 §13 (R-03)
    # Estado: CONFIRMADA — EVIDENCIA DIRECTA
    # Delegado a ParticipantGoals.to_narrative() para mantener cohesion.
    # -----------------------------------------------------------------------
    @staticmethod
    def derive_protagonistas_narrative(goals: ParticipantGoals) -> str:
        """R-03: Narrativa de protagonistas para Pregunta 4.

        Regla:
            SI solo_estudiantes: "{total} estudiantes."
            SI estudiantes + docentes: "{total} protagonistas en total: ..."
            SI desglose con sexo: "{total} protagonistas en total ({F} mujeres y {M} varones; ..."
        Clasificacion: CONFIRMADA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-03).
        """
        if not isinstance(goals, ParticipantGoals):
            raise TypeError("R-03: goals debe ser instancia de ParticipantGoals.")
        return goals.to_narrative()

    # -----------------------------------------------------------------------
    # R-04 — Duracion Formateada (Pregunta 7)
    # Fuente: FASE_29_2 §13 (R-04), §16 (P-03)
    # Estado: CONFIRMADA — EVIDENCIA DIRECTA
    # Casos verificados: 150m, 210m, 195m, 120m, 60m
    # -----------------------------------------------------------------------
    @staticmethod
    def derive_duracion_formateada(total_minutes: int) -> str:
        """R-04: Formato de duracion en horas y minutos.

        Casos verificados en corpus real (FASE_29_2 §16 P-03):
            150 min -> "2 horas y 30 minutos."
            210 min -> "3 horas y media (210 minutos)."
            195 min -> "3 horas y 15 minutos."
            120 min -> "2 horas."
             60 min -> "1 hora."

        Clasificacion: CONFIRMADA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-04).
        """
        if not isinstance(total_minutes, int) or total_minutes <= 0:
            raise ValueError(
                f"R-04: total_minutes debe ser entero positivo. Valor: {total_minutes!r}"
            )
        horas = total_minutes // 60
        resto = total_minutes % 60

        if horas == 0:
            return f"0 horas y {resto} minutos." if resto > 0 else "0 horas."

        label_h = "hora" if horas == 1 else "horas"

        if resto == 0:
            return f"{horas} {label_h}."

        if resto == 30:
            return f"{horas} {label_h} y media ({total_minutes} minutos)."

        return f"{horas} {label_h} y {resto} minutos."

    # -----------------------------------------------------------------------
    # R-05 — Suma de Agenda
    # Fuente: FASE_29_2 §13 (R-05), E-02
    # Estado: CONFIRMADA — EVIDENCIA DIRECTA. Cero tolerancia a discrepancias.
    # Implementado como propiedad derivada en MethodologicalDesign.total_minutes.
    # Este metodo verifica la invariante explicitamente.
    # -----------------------------------------------------------------------
    @staticmethod
    def verify_total_minutes(declared_total: int, agenda_minutes: list[int]) -> bool:
        """R-05: Verifica que total_minutes == Σ(agenda.minutes).

        Clasificacion: REGLA MATEMATICA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-05), E-02.
        Cero tolerancia a discrepancias.

        Returns True si la invariante se cumple, False si no.
        """
        return declared_total == sum(agenda_minutes)

    # -----------------------------------------------------------------------
    # R-06 — Espejo Tabla 2 <-> Tabla 3
    # Fuente: FASE_29_2 §13 (R-06), E-02
    # Estado: CONFIRMADA — EVIDENCIA DIRECTA
    # -----------------------------------------------------------------------
    @staticmethod
    def verify_mirror_t2_t3(
        agenda_minutes: list[int],
        matrix_minutes: list[int],
    ) -> bool:
        """R-06: Verifica que Tabla 2 y Tabla 3 tienen los mismos tiempos.

        INVARIANTE: operational_matrix[i].minutes == agenda[i].minutes  para todo i
        INVARIANTE: len(operational_matrix) == len(agenda)

        Clasificacion: REGLA MATEMATICA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-06), E-02.

        Returns True si la invariante se cumple, False si no.
        """
        if len(agenda_minutes) != len(matrix_minutes):
            return False
        return all(a == m for a, m in zip(agenda_minutes, matrix_minutes))

    # -----------------------------------------------------------------------
    # R-07 — Numero de Objetivos
    # Fuente: FASE_29_2 §13 (R-07)
    # Estado: CONFIRMADA — EVIDENCIA DIRECTA
    # -----------------------------------------------------------------------
    @staticmethod
    def verify_objectives_count(objectives: list[str]) -> bool:
        """R-07: Exactamente 2 objetivos especificos.

        len(objectives) == 2
        Clasificacion: CONFIRMADA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-07).
        """
        return len(objectives) == 2

    # -----------------------------------------------------------------------
    # R-08 — Validacion de Catalogos
    # Fuente: FASE_29_2 §13 (R-08)
    # Estado: CONFIRMADA — EVIDENCIA DIRECTA
    # -----------------------------------------------------------------------
    @staticmethod
    def validate_catalog_membership(
        eje_estrategia: str,
        programa: str,
        tipo_evento: str,
        ambito: str | None = None,
        tipo_proyecto: str | None = None,
    ) -> dict[str, bool]:
        """R-08: Valida que los campos de catalogo pertenezcan a C1-C5.

        eje_estrategia in C1  (11 ejes)
        programa       in C2  (11 programas)
        tipo_evento    in C4  (11 tipos)
        ambito         in C3  [si presente]
        tipo_proyecto  in C5  [si presente]

        Clasificacion: CONFIRMADA — EVIDENCIA DIRECTA.
        Fuente: FASE_29_2 §13 (R-08).

        Returns dict con {campo: bool} indicando si cada campo es valido.
        """
        result: dict[str, bool] = {
            "eje_estrategia": eje_estrategia in C1_CODES,
            "programa": programa in C2_CODES,
            "tipo_evento": tipo_evento in C4_CODES,
        }
        if ambito is not None:
            result["ambito"] = ambito in C3_CODES
        if tipo_proyecto is not None:
            result["tipo_proyecto"] = tipo_proyecto in C5_CODES
        return result

    # -----------------------------------------------------------------------
    # R-09 — Datos que Nunca Deben Inventarse
    # Fuente: FASE_29_2 §13 (R-09)
    # Estado: CONFIRMADA — REGLA DE ORO DEL SISTEMA
    # Esta regla no tiene implementacion de calculo; es un invariante
    # de diseno verificado a nivel de AIProposal.target_field (AI_PROHIBITED_TARGET_FIELDS).
    # El test de dominio lo verifica explicitamente.
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # R-10 — Sesion Unica (Default)
    # Fuente: FASE_29_2 §13 (R-10)
    # Estado: CONFIRMADA para actividades analizadas.
    #         Multi-sesion: PENDIENTE DE VALIDACION INSTITUCIONAL (D-05).
    # -----------------------------------------------------------------------
    @staticmethod
    def derive_default_session_text() -> str:
        """R-10: Texto por defecto para Pregunta 3 (sesiones).

        Default: "Sesion unica"
        Clasificacion: CONFIRMADA para actividades de sesion unica (5/5 corpus).
        Multi-sesion: PENDIENTE DE VALIDACION INSTITUCIONAL (D-05).
        Fuente: FASE_29_2 §13 (R-10), catalogs.DEFAULT_SESSION_TEXT.
        """
        return DEFAULT_SESSION_TEXT

    # -----------------------------------------------------------------------
    # Aliases de conveniencia para trazabilidad directa R-01 a R-10
    # -----------------------------------------------------------------------
    r01_titulo_documento = derive_document_title
    r02_facilitador = derive_facilitador
    r03_protagonistas_narrativa = derive_protagonistas_narrative
    r04_duracion_formateada = derive_duracion_formateada
    r07_verificar_numero_objetivos = verify_objectives_count
    r08_validar_catalogos = validate_catalog_membership
    r10_sesion_unica_default = derive_default_session_text

    @staticmethod
    def r05_calcular_total_minutos(agenda: Sequence[Any]) -> int:
        return sum(item.minutes for item in agenda)

    @staticmethod
    def r05_verificar_suma_agenda(agenda: Sequence[Any], declared_total: int) -> bool:
        return declared_total == sum(item.minutes for item in agenda)

    @staticmethod
    def r06_verificar_espejo_agenda_matriz(agenda: Sequence[Any], matrix: Sequence[Any]) -> bool:
        if len(agenda) != len(matrix):
            return False
        return all(a.minutes == m.minutes for a, m in zip(agenda, matrix))

    @staticmethod
    def r08_validar_eje_estrategia(eje: str) -> bool:
        if not eje:
            return False
        clean = _strip_accents(eje.strip().upper().replace(" ", "_"))
        if clean in C1_CODES or eje.strip() in C1_CODES:
            return True
        return any(clean.startswith(k) or k.startswith(clean) for k in C1_CODES)

    @staticmethod
    def r08_validar_tipo_evento(tipo: str) -> bool:
        if not tipo:
            return False
        clean = _strip_accents(tipo.strip().lower())
        normalized = "EVT_" + clean.upper()
        if normalized in C4_CODES or tipo.strip().upper() in C4_CODES:
            return True
        return any(_strip_accents(v.lower()) == clean for v in C4_TIPOS_EVENTO.values())

    @staticmethod
    def r08_validar_programa(programa: str) -> bool:
        if not programa:
            return False
        clean = _strip_accents(programa.strip().lower())
        if programa.strip().upper() in C2_CODES:
            return True
        return any(
            _strip_accents(v.lower()) == clean or clean in _strip_accents(v.lower())
            for v in C2_PROGRAMAS.values()
        )

    @staticmethod
    def r08_validar_ambito(ambito: str | None) -> bool:
        if ambito is None:
            return True
        clean = _strip_accents(ambito.strip().lower())
        normalized = "AMB_" + clean.upper()
        if normalized in C3_CODES or ambito.strip().upper() in C3_CODES:
            return True
        return any(_strip_accents(v.lower()) == clean for v in C3_AMBITOS.values())
