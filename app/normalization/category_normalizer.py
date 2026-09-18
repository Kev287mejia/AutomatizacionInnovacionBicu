"""
app.normalization.category_normalizer

Normalizador de categorías de participación (Regla C-03).
Mantiene separados:
1. categoria_escrita_fuente: texto original de la columna categoría/rol.
2. area_escrita_fuente: texto original de la columna área/dependencia (ej. 'ACCES').
3. categoria_participacion: valor de la enumeración CategoriaParticipacion.
4. categoria_institucional_final: clasificación final según reglas institucionales.
"""

from typing import Optional, Tuple
from app.core.constants.participant_types import CategoriaParticipacion, NivelValidacion
from app.core.models.validation_result import ValidationResult
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)

# Mapeo de valores comunes en listas a la enumeración CategoriaParticipacion
MAPEO_CATEGORIAS = {
    "estudiante": CategoriaParticipacion.ESTUDIANTE,
    "estudiantes": CategoriaParticipacion.ESTUDIANTE,
    "alumno": CategoriaParticipacion.ESTUDIANTE,
    "docente": CategoriaParticipacion.DOCENTE,
    "profesor": CategoriaParticipacion.DOCENTE,
    "administrativo": CategoriaParticipacion.ADMINISTRATIVO,
    "no docente": CategoriaParticipacion.NO_DOCENTE,
    "no-docente": CategoriaParticipacion.NO_DOCENTE,
    "nodocente": CategoriaParticipacion.NO_DOCENTE,
    "colaborador": CategoriaParticipacion.COLABORADOR,
    "beneficiado": CategoriaParticipacion.BENEFICIADO,
    "protagonista": CategoriaParticipacion.BENEFICIADO,
    "poblador": CategoriaParticipacion.POBLADOR_GENERAL,
    "poblador general": CategoriaParticipacion.POBLADOR_GENERAL,
}


class CategoryNormalizer:
    """
    Normaliza el rol o categoría de una participación conservando los valores de fuente.
    """

    @classmethod
    def normalizar(
        cls,
        categoria_original: Optional[str],
        area_original: Optional[str] = None,
        fuente: Optional[str] = None,
        id_referencia: Optional[str] = None
    ) -> Tuple[CategoriaParticipacion, Optional[str], Optional[ValidationResult]]:
        """
        Normaliza la categoría.
        Retorna (categoria_participacion, categoria_institucional_final, validacion_si_aplica).

        Ejemplo:
        categoria_original='No Docente', area_original='ACCES'
        -> (CategoriaParticipacion.NO_DOCENTE, 'ADMINISTRATIVO/NO DOCENTE', None)
        """
        if not categoria_original or not str(categoria_original).strip():
            # Si no hay categoría explícita, no usar solo 'area' para inventar categoría
            val = ValidationResult(
                id_referencia=id_referencia,
                nivel=NivelValidacion.WARNING,
                codigo="VAL_CATEGORIA_AUSENTE",
                mensaje=f"Categoría no especificada en la fuente. Área reportada: '{area_original or 'Ninguna'}'.",
                fuente_origen=fuente
            )
            return CategoriaParticipacion.DESCONOCIDO, None, val

        cat_raw = str(categoria_original).strip()
        cat_key = cat_raw.lower()

        if cat_key in MAPEO_CATEGORIAS:
            cat_enum = MAPEO_CATEGORIAS[cat_key]
            
            # Clasificación institucional preliminar
            if cat_enum in (CategoriaParticipacion.NO_DOCENTE, CategoriaParticipacion.ADMINISTRATIVO):
                institucional_final = "ADMINISTRATIVO / NO DOCENTE"
            elif cat_enum == CategoriaParticipacion.DOCENTE:
                institucional_final = "ACADÉMICO / DOCENTE"
            elif cat_enum == CategoriaParticipacion.ESTUDIANTE:
                institucional_final = "ESTUDIANTE"
            elif cat_enum in (CategoriaParticipacion.BENEFICIADO, CategoriaParticipacion.POBLADOR_GENERAL):
                institucional_final = "PROTAGONISTA BENEFICIADO"
            elif cat_enum == CategoriaParticipacion.COLABORADOR:
                institucional_final = "COLABORADOR"
            else:
                institucional_final = None

            return cat_enum, institucional_final, None

        # Categoría no reconocida
        val = ValidationResult(
            id_referencia=id_referencia,
            nivel=NivelValidacion.WARNING,
            codigo="VAL_CATEGORIA_DESCONOCIDA",
            mensaje=f"Categoría '{categoria_original}' no reconocida en catálogo estándar. Requiere revisión humana.",
            fuente_origen=fuente
        )
        return CategoriaParticipacion.DESCONOCIDO, None, val
