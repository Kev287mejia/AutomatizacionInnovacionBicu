"""
app.normalization.name_normalizer

Normalizador básico de nombres y apellidos de personas.
Preserva el nombre original y limpia espacios repetidos y formatos irregulares.
"""

import re
from typing import Optional, Tuple


class NameNormalizer:
    """
    Limpieza y estandarización básica de nombres de personas.
    """

    @classmethod
    def normalizar(
        cls,
        nombre_completo_original: str
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Normaliza el nombre completo y separa preliminarmente nombres y apellidos.
        Retorna (nombre_completo_normalizado, nombres, apellidos).
        """
        if not nombre_completo_original:
            return "", None, None

        # Quitar espacios múltiples y extremos
        limpio = re.sub(r"\s+", " ", str(nombre_completo_original).strip())
        
        # Capitalizar adecuadamente cada componente
        palabras = limpio.split()
        palabras_capitalizadas = [
            p.capitalize() if p.isupper() or p.islower() else p
            for p in palabras
        ]
        nombre_normalizado = " ".join(palabras_capitalizadas)

        # División heurística: si son 3 o 4 palabras, los 2 primeros suelen ser nombres y los restantes apellidos
        nombres = None
        apellidos = None
        if len(palabras_capitalizadas) == 2:
            nombres = palabras_capitalizadas[0]
            apellidos = palabras_capitalizadas[1]
        elif len(palabras_capitalizadas) == 3:
            nombres = palabras_capitalizadas[0]
            apellidos = " ".join(palabras_capitalizadas[1:])
        elif len(palabras_capitalizadas) >= 4:
            nombres = " ".join(palabras_capitalizadas[:2])
            apellidos = " ".join(palabras_capitalizadas[2:])

        return nombre_normalizado, nombres, apellidos
