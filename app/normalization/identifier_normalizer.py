"""
app.normalization.identifier_normalizer

Normalizador de identificadores personales (Cédula de Identidad).
Reglas:
- C-09: Jerarquía de identidad. Cédula es Nivel 1.
- C-10: Regla de no invención. Si está vacía, no crearla.
- Detectar anomalías (ej. fechas de nacimiento escritas en la columna de cédula)
  sin trasladar automáticamente los datos a otros campos.
"""

import re
from typing import Optional, Tuple
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)

# Expresión para detectar fechas en formatos DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, etc.
PATRON_FECHA = re.compile(
    r"^(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})$"
)

# Patrón de cédula nicaragüense estándar: 3 dígitos, 6 dígitos (DDMMAA), 4 dígitos secuenciales y 1 letra
PATRON_CEDULA_NI = re.compile(
    r"^(\d{3})[-]?(\d{6})[-]?(\d{4}[A-Za-z])$"
)


class IdentifierNormalizer:
    """
    Normalizador y detector de anomalías para cédulas de identidad.
    """

    @classmethod
    def normalizar_cedula(
        cls,
        valor_original: Optional[str],
        fuente: Optional[str] = None,
        id_referencia: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[ValidationResult]]:
        """
        Evalúa y normaliza una cédula.
        Retorna (cedula_normalizada, validacion_si_aplica).

        Casos:
        1. Vacía o nula:
           - cedula_normalizada = None
           - ValidationResult(WARNING, 'VAL_CEDULA_VACIA')
        2. Fecha en campo cédula (ej. '20-04-2008'):
           - cedula_normalizada = None
           - ValidationResult(WARNING, 'VAL_CEDULA_FECHA', 'Posible fecha de nacimiento en campo cédula')
           - No traslada el valor a fecha de nacimiento.
        3. Cédula nicaragüense válida:
           - Formatea como XXX-XXXXXX-XXXXL en mayúsculas.
           - None en validación.
        4. Otro formato dudoso o incompleto:
           - Retorna None o valor preliminar + ValidationResult(WARNING/REVISION, 'VAL_CEDULA_INVALIDA').
        """
        if valor_original is None:
            val = ValidationResult(
                id_referencia=id_referencia,
                nivel=NivelValidacion.WARNING,
                codigo="VAL_CEDULA_VACIA",
                mensaje="Cédula no proporcionada (campo vacío).",
                fuente_origen=fuente
            )
            return None, val

        val_limpio = str(valor_original).strip()
        if not val_limpio or val_limpio in ("-", "--", "N/A", "NO TIENE", "S/C"):
            val = ValidationResult(
                id_referencia=id_referencia,
                nivel=NivelValidacion.WARNING,
                codigo="VAL_CEDULA_VACIA",
                mensaje=f"Cédula vacía o no válida ('{valor_original}').",
                fuente_origen=fuente
            )
            return None, val

        # Detectar si es una fecha colocada en el campo cédula
        if PATRON_FECHA.match(val_limpio):
            val = ValidationResult(
                id_referencia=id_referencia,
                nivel=NivelValidacion.REVISION,
                codigo="VAL_CEDULA_FECHA",
                mensaje=(
                    f"Posible fecha de nacimiento ubicada en campo cédula: '{val_limpio}'. "
                    "Requiere revisión humana. No se traslada automáticamente a fecha_nacimiento."
                ),
                fuente_origen=fuente
            )
            return None, val

        # Validar si cumple formato de cédula de Nicaragua
        match = PATRON_CEDULA_NI.match(val_limpio)
        if match:
            prefijo, fecha_parte, sufijo = match.groups()
            cedula_formateada = f"{prefijo}-{fecha_parte}-{sufijo.upper()}"
            return cedula_formateada, None

        # Si tiene texto pero no cumple patrón estándar
        val = ValidationResult(
            id_referencia=id_referencia,
            nivel=NivelValidacion.WARNING,
            codigo="VAL_CEDULA_FORMATO_DUDOSO",
            mensaje=f"Cédula '{val_limpio}' no cumple con el formato estándar de cédula nicaragüense (XXX-XXXXXX-XXXXL).",
            fuente_origen=fuente
        )
        return None, val
