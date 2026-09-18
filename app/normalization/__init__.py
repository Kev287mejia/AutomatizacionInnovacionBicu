"""
app.normalization

Módulo de normalización y limpieza de datos por fuente.
Exporta normalizadores específicos:
- SexNormalizer: normalización dependiente de la fuente (Regla C-08).
- IdentifierNormalizer: normalización y detección de anomalías en cédula.
- CareerNormalizer: preservación de los 3 niveles de carrera y detección de abreviaturas.
- CategoryNormalizer: normalización de categorías de participación.
- NameNormalizer: estandarización de nombres.
- AgeDateNormalizer: manejo estricto de edad y fecha de nacimiento.
"""

from app.normalization.sex_normalizer import SexNormalizer
from app.normalization.identifier_normalizer import IdentifierNormalizer
from app.normalization.career_normalizer import CareerNormalizer
from app.normalization.category_normalizer import CategoryNormalizer
from app.normalization.name_normalizer import NameNormalizer
from app.normalization.age_date_normalizer import AgeDateNormalizer

__all__ = [
    "SexNormalizer",
    "IdentifierNormalizer",
    "CareerNormalizer",
    "CategoryNormalizer",
    "NameNormalizer",
    "AgeDateNormalizer",
]
