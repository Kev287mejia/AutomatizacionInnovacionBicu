"""
app.normalization.career_normalizer

Normalizador de carreras y disciplinas académicas (Regla C-12).
Preserva los tres niveles:
1. carrera_original: texto extraído sin modificar.
2. carrera_normalizada: texto limpio, normalizado textualmente.
3. carrera_oficial: None mientras no exista catálogo oficial confirmado.
"""

import re
from typing import Optional, Tuple
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)

# Diccionario de limpiezas puramente textuales / desabreviaciones conocidas preliminares
# NOTA: Esto genera carrera_normalizada, NO afirma carrera_oficial.
ABREVIATURAS_CONOCIDAS = {
    "lic contabil.": ("Lic. Contabilidad", True),
    "lic. contabil.": ("Lic. Contabilidad", True),
    "lic. conta": ("Lic. Contabilidad", True),
    "lic conta": ("Lic. Contabilidad", True),
    "contabilidad": ("Contabilidad", False),
    "ing. sistc.": ("Ing. Sistemas", True),
    "ing sistc": ("Ing. Sistemas", True),
    "sistema": ("Sistemas", True),
    "sistemas": ("Sistemas", False),
    "a. estudiantil": ("A. Estudiantil", False),  # Ambigua
    "atencion estudiantil": ("Atención Estudiantil", False),
}


class CareerNormalizer:
    """
    Gestiona la limpieza textual y detección de abreviaturas/ambigüedades en carreras.
    """

    @classmethod
    def normalizar(
        cls,
        valor_original: Optional[str],
        fuente: Optional[str] = None,
        id_referencia: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[ValidationResult]]:
        """
        Normaliza una carrera.
        Retorna (carrera_normalizada, carrera_oficial, validacion_si_aplica).
        carrera_oficial es SIEMPRE None en esta fase (catálogo no confirmado).
        """
        if not valor_original or not str(valor_original).strip():
            return None, None, None

        raw = str(valor_original).strip()
        raw_lower = raw.lower()

        carrera_norm = raw
        validacion = None

        # 1. Caso especial: término ambiguo "A. estudiantil"
        if raw_lower in ("a. estudiantil", "a estudiantil"):
            carrera_norm = "A. Estudiantil"
            validacion = ValidationResult(
                id_referencia=id_referencia,
                nivel=NivelValidacion.WARNING,
                codigo="VAL_CARRERA_AMBIGUA",
                mensaje=(
                    f"Carrera o área ambigua '{raw}'. Podría corresponder a 'Atención Estudiantil' "
                    "o un área administrativa en lugar de carrera académica. Requiere revisión."
                ),
                fuente_origen=fuente
            )
        elif raw_lower in ABREVIATURAS_CONOCIDAS:
            norm_sugerida, es_abreviada = ABREVIATURAS_CONOCIDAS[raw_lower]
            carrera_norm = norm_sugerida
            if es_abreviada:
                validacion = ValidationResult(
                    id_referencia=id_referencia,
                    nivel=NivelValidacion.WARNING,
                    codigo="VAL_CARRERA_ABREVIADA",
                    mensaje=f"Carrera posiblemente abreviada en la fuente: '{raw}'. Normalizada preliminarmente a '{norm_sugerida}'.",
                    fuente_origen=fuente
                )
        else:
            # Limpieza básica: normalizar mayúsculas de palabras
            carrera_norm = " ".join([p.capitalize() for p in raw.split()])

            # Detección genérica de abreviaturas con puntos intermedios (ej: 'Ing.', 'Lic.')
            if "." in raw or len(raw) <= 4:
                validacion = ValidationResult(
                    id_referencia=id_referencia,
                    nivel=NivelValidacion.WARNING,
                    codigo="VAL_CARRERA_ABREVIADA",
                    mensaje=f"Posible abreviatura detectada en el campo carrera: '{raw}'.",
                    fuente_origen=fuente
                )

        # Regla Fase 3: carrera_oficial es SIEMPRE None sin catálogo confirmado
        carrera_oficial = None

        return carrera_norm, carrera_oficial, validacion
