"""
app.matching.person_matcher

Módulo de comparación controlada de personas y evaluación de jerarquía de identidad.
Cumple estrictamente las reglas de la Fase 4:
- Regla C-09: Jerarquía de identidad de 4 niveles.
  * Nivel 1: Cédula oficial válida (FUSIÓN AUTOMÁTICA SEGURA / DISTINTAS).
  * Nivel 2: Número único institucional (FUSIÓN AUTOMÁTICA SEGURA / DISTINTAS).
  * Nivel 3: Otro identificador institucional (NO autoriza fusión automática; genera REVISIÓN).
  * Nivel 4: Candidato a duplicado basado en evidencia secundaria (NUNCA autoriza fusión automática).
- No asume "el nombre más largo" como verdad absoluta ni evidencia de identidad.
- Detecta y alerta conflictos de datos (DEDUP_CONFLICTO_DATOS).
"""

import difflib
import re
from enum import Enum
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field

from app.core.models.person import Person
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion, NivelConfianzaIdentidad
from app.normalization.identifier_normalizer import PATRON_CEDULA_NI, PATRON_FECHA
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class TipoCoincidenciaPersona(str, Enum):
    """Clasificación del resultado de comparar dos personas."""
    FUSION_AUTOMATICA = "FUSION_AUTOMATICA"  # Autorizado exclusivamente por Nivel 1 o Nivel 2 idéntico
    DISTINTAS = "DISTINTAS"                  # Identificadores Nivel 1 o Nivel 2 válidos pero diferentes
    CANDIDATO_REVISION = "CANDIDATO_REVISION" # Nivel 3 o Nivel 4 (evidencia secundaria); requiere confirmación humana
    SIN_COINCIDENCIA = "SIN_COINCIDENCIA"    # Sin relación aparente


class PersonComparisonResult(BaseModel):
    """Resultado de la evaluación comparativa entre dos entidades Person."""
    tipo_coincidencia: TipoCoincidenciaPersona = Field(
        ...,
        description="Tipo de relación determinada entre las dos personas."
    )
    nivel_jerarquia: Optional[int] = Field(
        default=None,
        description="Nivel de la jerarquía de identidad que determinó la decisión (1 a 4)."
    )
    similitud_nombre: float = Field(
        default=0.0,
        description="Puntaje de similitud entre nombres normalizados (0.0 a 1.0)."
    )
    evidencias: List[str] = Field(
        default_factory=list,
        description="Lista de evidencias que respaldan el veredicto."
    )
    validaciones: List[ValidationResult] = Field(
        default_factory=list,
        description="Validaciones y alertas emitidas durante la comparación."
    )
    conflictos: List[str] = Field(
        default_factory=list,
        description="Detalle de atributos contradictorios entre ambos registros si los hubiere."
    )


class PersonMatcher:
    """
    Comparador controlado de personas basado en la jerarquía de 4 niveles.
    """

    @classmethod
    def es_cedula_valida(cls, cedula: Optional[str]) -> bool:
        """
        Verifica si una cédula es un identificador oficial válido:
        - No es None ni vacía.
        - No es una fecha accidental (ej: '20-04-2008').
        - Cumple con el formato oficial nicaragüense (XXX-XXXXXX-XXXXL).
        """
        if not cedula:
            return False
        val_limpio = cedula.strip()
        if PATRON_FECHA.match(val_limpio):
            return False
        return bool(PATRON_CEDULA_NI.match(val_limpio))

    @classmethod
    def es_numero_unico_valido(cls, numero_unico: Optional[str]) -> bool:
        """
        Verifica si un número único institucional es válido:
        - No es None ni vacío.
        - No es placeholder de ausencia ('-', 'N/A', etc.).
        - Tiene longitud y caracteres sustantivos.
        """
        if not numero_unico:
            return False
        val_limpio = numero_unico.strip()
        if val_limpio.upper() in ("-", "--", "N/A", "NO TIENE", "S/C", "0"):
            return False
        return len(val_limpio) >= 3

    @classmethod
    def calcular_similitud_nombre(cls, nombre_a: Optional[str], nombre_b: Optional[str]) -> float:
        """
        Calcula la similitud textual y por tokens entre dos nombres.
        Maneja casos como 'Johnny Melvin' vs 'Johnny M' o diferencias de espaciado.
        """
        if not nombre_a or not nombre_b:
            return 0.0

        n1 = re.sub(r"\s+", " ", nombre_a.strip().lower())
        n2 = re.sub(r"\s+", " ", nombre_b.strip().lower())

        if n1 == n2:
            return 1.0

        # Similitud secuencial
        seq_ratio = difflib.SequenceMatcher(None, n1, n2).ratio()

        # Similitud por tokens
        tokens1 = n1.split()
        tokens2 = n2.split()

        # Coincidencia si uno es prefijo/inicial de otro (ej: 'Johnny M' con 'Johnny Melvin')
        if tokens1 and tokens2 and tokens1[0] == tokens2[0]:
            # Mismo primer nombre
            if len(tokens1) > 1 and len(tokens2) > 1:
                t2_0 = tokens2[1]
                t1_0 = tokens1[1]
                # Una es inicial de la otra (ej: 'm' con 'melvin')
                if (len(t2_0) == 1 and t1_0.startswith(t2_0)) or (len(t1_0) == 1 and t2_0.startswith(t1_0)):
                    return max(seq_ratio, 0.85)

        return seq_ratio

    @classmethod
    def detectar_conflictos_atributos(cls, p1: Person, p2: Person) -> List[str]:
        """
        Compara atributos secundarios para detectar contradicciones entre dos registros.
        No sobreescribe silenciosamente: documenta el conflicto.
        """
        conflictos: List[str] = []

        # 1. Conflicto de sexo normalizado
        if p1.sexo_normalizado and p2.sexo_normalizado:
            if p1.sexo_normalizado.strip().upper() != p2.sexo_normalizado.strip().upper():
                conflictos.append(
                    f"Conflicto de sexo: '{p1.sexo_normalizado}' (fuente: {p1.sexo_fuente or p1.fuente_origen}) "
                    f"vs '{p2.sexo_normalizado}' (fuente: {p2.sexo_fuente or p2.fuente_origen})"
                )

        # 2. Conflicto de edad (diferencia mayor a 1 año biológico)
        if p1.edad is not None and p2.edad is not None:
            if abs(p1.edad - p2.edad) > 1:
                conflictos.append(
                    f"Conflicto de edad: {p1.edad} años vs {p2.edad} años"
                )

        # 3. Conflicto de fecha de nacimiento
        if p1.fecha_nacimiento and p2.fecha_nacimiento:
            if str(p1.fecha_nacimiento).strip() != str(p2.fecha_nacimiento).strip():
                conflictos.append(
                    f"Conflicto de fecha de nacimiento: '{p1.fecha_nacimiento}' vs '{p2.fecha_nacimiento}'"
                )

        # 4. Conflicto de teléfono (si ambos tienen y difieren completamente)
        if p1.telefono and p2.telefono:
            t1 = re.sub(r"\D", "", p1.telefono)
            t2 = re.sub(r"\D", "", p2.telefono)
            if t1 and t2 and t1 != t2:
                conflictos.append(f"Conflicto de teléfono: '{p1.telefono}' vs '{p2.telefono}'")

        return conflictos

    @classmethod
    def comparar_personas(cls, p1: Person, p2: Person) -> PersonComparisonResult:
        """
        Aplica la jerarquía estricta de 4 niveles para evaluar la relación entre p1 y p2:
        - Nivel 1: Cédula oficial válida
        - Nivel 2: Número único institucional
        - Nivel 3: Otro ID institucional
        - Nivel 4: Evidencia secundaria (candidato a duplicado)
        """
        evidencias: List[str] = []
        validaciones: List[ValidationResult] = []
        similitud_nombre = cls.calcular_similitud_nombre(p1.nombre_completo, p2.nombre_completo)

        # ---------------------------------------------------------------------
        # NIVEL 1 — CÉDULA OFICIAL VÁLIDA
        # ---------------------------------------------------------------------
        c1_valida = cls.es_cedula_valida(p1.cedula)
        c2_valida = cls.es_cedula_valida(p2.cedula)

        if c1_valida and c2_valida:
            if p1.cedula.strip().upper() == p2.cedula.strip().upper():
                # Misma cédula válida -> Misma persona -> Fusión automática segura
                evidencias.append(f"Nivel 1: Misma cédula oficial válida ('{p1.cedula.strip().upper()}')")
                conflictos = cls.detectar_conflictos_atributos(p1, p2)
                for conf in conflictos:
                    validaciones.append(
                        ValidationResult(
                            id_referencia=p1.id_persona_interno,
                            nivel=NivelValidacion.WARNING,
                            codigo="DEDUP_CONFLICTO_DATOS",
                            mensaje=(
                                f"Fusión por Nivel 1 autorizada pero con datos contradictorios entre "
                                f"'{p1.nombre_completo}' y '{p2.nombre_completo}': {conf}."
                            ),
                            fuente_origen=p1.fuente_origen
                        )
                    )
                return PersonComparisonResult(
                    tipo_coincidencia=TipoCoincidenciaPersona.FUSION_AUTOMATICA,
                    nivel_jerarquia=NivelConfianzaIdentidad.NIVEL_1_CEDULA.value,
                    similitud_nombre=similitud_nombre,
                    evidencias=evidencias,
                    validaciones=validaciones,
                    conflictos=conflictos
                )
            else:
                # Cédulas válidas diferentes -> PERSONAS DISTINTAS (no contradicho por nombres)
                evidencias.append(
                    f"Nivel 1: Cédulas oficiales válidas diferentes ('{p1.cedula}' vs '{p2.cedula}'). "
                    f"Son personas distintas independientemente de la similitud de nombres ({similitud_nombre:.2f})."
                )
                return PersonComparisonResult(
                    tipo_coincidencia=TipoCoincidenciaPersona.DISTINTAS,
                    nivel_jerarquia=NivelConfianzaIdentidad.NIVEL_1_CEDULA.value,
                    similitud_nombre=similitud_nombre,
                    evidencias=evidencias,
                    validaciones=validaciones
                )

        # ---------------------------------------------------------------------
        # NIVEL 2 — NÚMERO ÚNICO INSTITUCIONAL
        # ---------------------------------------------------------------------
        num1_valido = cls.es_numero_unico_valido(p1.numero_unico)
        num2_valido = cls.es_numero_unico_valido(p2.numero_unico)

        if num1_valido and num2_valido:
            if p1.numero_unico.strip().upper() == p2.numero_unico.strip().upper():
                evidencias.append(f"Nivel 2: Mismo número único institucional ('{p1.numero_unico.strip().upper()}')")
                conflictos = cls.detectar_conflictos_atributos(p1, p2)
                for conf in conflictos:
                    validaciones.append(
                        ValidationResult(
                            id_referencia=p1.id_persona_interno,
                            nivel=NivelValidacion.WARNING,
                            codigo="DEDUP_CONFLICTO_DATOS",
                            mensaje=(
                                f"Fusión por Nivel 2 autorizada pero con datos contradictorios entre "
                                f"'{p1.nombre_completo}' y '{p2.nombre_completo}': {conf}."
                            ),
                            fuente_origen=p1.fuente_origen
                        )
                    )
                return PersonComparisonResult(
                    tipo_coincidencia=TipoCoincidenciaPersona.FUSION_AUTOMATICA,
                    nivel_jerarquia=NivelConfianzaIdentidad.NIVEL_2_NUMERO_UNICO.value,
                    similitud_nombre=similitud_nombre,
                    evidencias=evidencias,
                    validaciones=validaciones,
                    conflictos=conflictos
                )
            else:
                evidencias.append(
                    f"Nivel 2: Números únicos institucionales diferentes ('{p1.numero_unico}' vs '{p2.numero_unico}'). "
                    "Son personas distintas."
                )
                return PersonComparisonResult(
                    tipo_coincidencia=TipoCoincidenciaPersona.DISTINTAS,
                    nivel_jerarquia=NivelConfianzaIdentidad.NIVEL_2_NUMERO_UNICO.value,
                    similitud_nombre=similitud_nombre,
                    evidencias=evidencias,
                    validaciones=validaciones
                )

        # ---------------------------------------------------------------------
        # NIVEL 3 — OTRO IDENTIFICADOR INSTITUCIONAL
        # ---------------------------------------------------------------------
        # Regla C-09 y Corrección 1:
        # otro_id_institucional NO autoriza por sí mismo una fusión automática.
        # Conservar personas separadas, registrar evidencia, emitir MATCH_NIVEL3_REVISION.
        if p1.otro_id_institucional and p2.otro_id_institucional:
            if p1.otro_id_institucional.strip().upper() == p2.otro_id_institucional.strip().upper():
                id3 = p1.otro_id_institucional.strip()
                evidencias.append(
                    f"Nivel 3: Coincidencia en otro_id_institucional ('{id3}'). "
                    "Por regla institucional estricta, NO se autoriza fusión automática. Requiere revisión humana."
                )
                validaciones.append(
                    ValidationResult(
                        id_referencia=p1.id_persona_interno,
                        nivel=NivelValidacion.REVISION,
                        codigo="MATCH_NIVEL3_REVISION",
                        mensaje=(
                            f"Identificador institucional Nivel 3 coincidente ('{id3}') entre "
                            f"'{p1.nombre_completo}' y '{p2.nombre_completo}'. Se conservan personas separadas "
                            "y se envía a revisión humana por falta de especificación institucional."
                        ),
                        fuente_origen=p1.fuente_origen
                    )
                )
                return PersonComparisonResult(
                    tipo_coincidencia=TipoCoincidenciaPersona.CANDIDATO_REVISION,
                    nivel_jerarquia=NivelConfianzaIdentidad.NIVEL_3_OTRO_ID.value,
                    similitud_nombre=similitud_nombre,
                    evidencias=evidencias,
                    validaciones=validaciones
                )

        # ---------------------------------------------------------------------
        # NIVEL 4 — CANDIDATO A DUPLICADO (EVIDENCIA SECUNDARIA)
        # ---------------------------------------------------------------------
        # Evalúa: nombre normalizado, teléfono, carrera, edad.
        # NUNCA autoriza fusión automática. Mantiene personas separadas.
        es_candidato = False
        razones_candidato: List[str] = []

        # 1. Similitud de nombres alta
        if similitud_nombre >= 0.85:
            es_candidato = True
            razones_candidato.append(
                f"Similitud alta de nombre ({similitud_nombre:.2f}): '{p1.nombre_completo}' vs '{p2.nombre_completo}'"
            )

        # 2. Mismo teléfono no vacío
        if p1.telefono and p2.telefono:
            t1 = re.sub(r"\D", "", p1.telefono)
            t2 = re.sub(r"\D", "", p2.telefono)
            if t1 and t2 and t1 == t2 and len(t1) >= 7:
                es_candidato = True
                razones_candidato.append(f"Mismo número de teléfono: '{p1.telefono}'")

        # 3. Nombre moderadamente similar (>= 0.70) + misma edad y misma carrera
        if similitud_nombre >= 0.70:
            misma_edad = p1.edad is not None and p2.edad is not None and p1.edad == p2.edad
            misma_carrera = (
                p1.carrera_normalizada and p2.carrera_normalizada and
                p1.carrera_normalizada.strip().lower() == p2.carrera_normalizada.strip().lower()
            )
            if misma_edad and misma_carrera:
                es_candidato = True
                razones_candidato.append(
                    f"Similitud de nombre ({similitud_nombre:.2f}) combinada con misma edad ({p1.edad}) "
                    f"y misma carrera ('{p1.carrera_normalizada}')"
                )

        if es_candidato:
            evidencias.extend(razones_candidato)
            evidencias.append(
                "Nivel 4: Coincidencia candidata por evidencia secundaria. NO se autoriza fusión automática. "
                "Se mantienen como personas independientes."
            )
            validaciones.append(
                ValidationResult(
                    id_referencia=p1.id_persona_interno,
                    nivel=NivelValidacion.REVISION,
                    codigo="MATCH_PERSONA_CANDIDATO",
                    mensaje=(
                        f"Posible duplicado candidato detectado entre '{p1.nombre_completo}' y '{p2.nombre_completo}'. "
                        f"Evidencia: {'; '.join(razones_candidato)}. Requiere confirmación humana."
                    ),
                    fuente_origen=p1.fuente_origen
                )
            )
            return PersonComparisonResult(
                tipo_coincidencia=TipoCoincidenciaPersona.CANDIDATO_REVISION,
                nivel_jerarquia=NivelConfianzaIdentidad.NIVEL_4_CANDIDATO.value,
                similitud_nombre=similitud_nombre,
                evidencias=evidencias,
                validaciones=validaciones
            )

        # ---------------------------------------------------------------------
        # SIN COINCIDENCIA
        # ---------------------------------------------------------------------
        return PersonComparisonResult(
            tipo_coincidencia=TipoCoincidenciaPersona.SIN_COINCIDENCIA,
            nivel_jerarquia=None,
            similitud_nombre=similitud_nombre,
            evidencias=["Sin evidencias suficientes de coincidencia."]
        )
