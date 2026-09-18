"""
app.normalization.age_date_normalizer

Normalizador de edad y fecha de nacimiento (Regla C-10 y Reglas 5 y 6 de Fase 3).
Reglas:
- Si la fuente únicamente proporciona edad: conservar edad y fecha_nacimiento = None.
- NUNCA reconstruir una fecha de nacimiento a partir de la edad.
- Si aparece una fecha en el campo edad, marcarla para REVISIÓN y no inventar edad.
"""

import re
from typing import Optional, Tuple, Union
from datetime import date, datetime
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)

PATRON_FECHA = re.compile(
    r"^(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})$"
)


class AgeDateNormalizer:
    """
    Normaliza y valida edad y fecha de nacimiento.
    """

    @classmethod
    def normalizar(
        cls,
        edad_original: Optional[Union[int, str]],
        fecha_nacimiento_original: Optional[Union[date, str]] = None,
        fuente: Optional[str] = None,
        id_referencia: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[Union[date, str]], Optional[ValidationResult]]:
        """
        Normaliza edad y fecha de nacimiento.
        Retorna (edad_normalizada, fecha_nacimiento_normalizada, validacion_si_aplica).
        """
        edad_norm: Optional[int] = None
        fecha_norm: Optional[Union[date, str]] = None
        validacion: Optional[ValidationResult] = None

        # 1. Procesar edad_original
        if edad_original is not None:
            edad_str = str(edad_original).strip()
            if PATRON_FECHA.match(edad_str):
                # Caso anómalo: fecha escrita en el campo de edad
                validacion = ValidationResult(
                    id_referencia=id_referencia,
                    nivel=NivelValidacion.WARNING,
                    codigo="VAL_EDAD_FECHA_ANOMALA",
                    mensaje=(
                        f"Se detectó posible fecha '{edad_str}' en la columna de edad. "
                        "Requiere revisión. No se reconstruye edad ni fecha automáticamente."
                    ),
                    fuente_origen=fuente
                )
                edad_norm = None
            else:
                try:
                    edad_val = int(edad_str)
                    if 0 <= edad_val <= 125:
                        edad_norm = edad_val
                    else:
                        validacion = ValidationResult(
                            id_referencia=id_referencia,
                            nivel=NivelValidacion.WARNING,
                            codigo="VAL_EDAD_FUERA_RANGO",
                            mensaje=f"Edad {edad_val} fuera de rango plausible.",
                            fuente_origen=fuente
                        )
                except ValueError:
                    if edad_str not in ("", "-", "N/A"):
                        validacion = ValidationResult(
                            id_referencia=id_referencia,
                            nivel=NivelValidacion.WARNING,
                            codigo="VAL_EDAD_INVALIDA",
                            mensaje=f"Valor de edad no numérico: '{edad_str}'.",
                            fuente_origen=fuente
                        )

        # 2. Si no hay edad
        if edad_norm is None and validacion is None:
            validacion = ValidationResult(
                id_referencia=id_referencia,
                nivel=NivelValidacion.WARNING,
                codigo="VAL_EDAD_AUSENTE",
                mensaje="Edad no proporcionada en la fuente.",
                fuente_origen=fuente
            )

        # 3. Procesar fecha_nacimiento_original (Regla crítica: NO inferir a partir de edad)
        if fecha_nacimiento_original is not None:
            if isinstance(fecha_nacimiento_original, (date, datetime)):
                fecha_norm = fecha_nacimiento_original
            else:
                fecha_str = str(fecha_nacimiento_original).strip()
                if fecha_str and fecha_str not in ("-", "N/A"):
                    fecha_norm = fecha_str
        else:
            # Si solo se proporcionó edad, fecha_nacimiento queda estrictamente en None
            fecha_norm = None

        return edad_norm, fecha_norm, validacion
