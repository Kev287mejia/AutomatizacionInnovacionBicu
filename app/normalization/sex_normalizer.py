"""
app.normalization.sex_normalizer

Normalizador de códigos de sexo dependiente de la fuente (Regla C-08).
El significado del código depende de la fuente de origen. NUNCA aplicar reemplazo global.
"""

from typing import Optional, Tuple
from app.core.catalog.catalog_loader import CatalogLoader
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class SexNormalizer:
    """
    Normalizador de sexo específico por fuente.
    Garantiza que:
    - 'M' en informe Word se interpreta como 'FEMENINO' (Mujer).
    - 'V' en informe Word se interpreta como 'MASCULINO' (Varón).
    - 'M' en asistencia física se interpreta como 'MASCULINO'.
    - 'F' en asistencia física se interpreta como 'FEMENINO'.
    - '1' en excel oficial se interpreta como 'FEMENINO'.
    - '2' en excel oficial se interpreta como 'MASCULINO'.
    """

    @classmethod
    def normalizar(
        cls,
        valor_original: Optional[str],
        fuente: str,
        id_referencia: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[ValidationResult]]:
        """
        Normaliza el sexo según la fuente dada.
        Retorna (sexo_normalizado, validacion_si_aplica).
        Si valor_original es vacío o nulo, retorna (None, ValidationResult con WARNING).
        Si el código no tiene mapeo en la fuente, retorna (None, ValidationResult con WARNING/REVISION).
        """
        if valor_original is None or not str(valor_original).strip():
            val = ValidationResult(
                id_referencia=id_referencia,
                nivel=NivelValidacion.WARNING,
                codigo="VAL_SEXO_AUSENTE",
                mensaje="El campo sexo no fue proporcionado en la fuente.",
                fuente_origen=fuente
            )
            return None, val

        val_limpio = str(valor_original).strip().upper()
        sexo_norm = CatalogLoader.normalizar_sexo_segun_fuente(val_limpio, fuente)

        if sexo_norm is None:
            # Si no se encontró mapeo en el archivo de configuración
            val = ValidationResult(
                id_referencia=id_referencia,
                nivel=NivelValidacion.WARNING,
                codigo="VAL_SEXO_INCOMPATIBLE",
                mensaje=f"Código de sexo '{valor_original}' no reconocido o incompatible para la fuente '{fuente}'.",
                fuente_origen=fuente
            )
            return None, val

        return sexo_norm, None
