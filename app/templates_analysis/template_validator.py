"""
app.templates_analysis.template_validator

Validador de compatibilidad estructural de plantillas Excel (Fase 8).
Verifica que las plantillas descubiertas cumplan con el contrato necesario para
que la futura Fase 9 (Exportación) pueda escribir de manera segura.
"""

from typing import List, Tuple
from app.audit.audit_logger import get_logger
from app.templates_analysis.models import (
    EsquemaPlantilla,
    EstadoMapeo,
    MappingManifesto,
)

logger = get_logger(__name__)


class TemplateValidator:
    """
    Valida la idoneidad técnica y estructural de una plantilla analizada.
    """

    @classmethod
    def validar_esquema_y_manifesto(
        cls, esquema: EsquemaPlantilla, manifesto: MappingManifesto
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Evalúa si el esquema físico y el mapping manifesto son válidos para la operación institucional.

        Args:
            esquema: Esquema físico descubierto por Fase 8A.
            manifesto: Mapping Manifesto generado por Fase 8B.

        Returns:
            Tuple (es_valida, lista_errores, lista_advertencias)
        """
        errores: List[str] = []
        advertencias: List[str] = []

        # 1. Validación de fila de inicio
        if esquema.estado_fila_inicio == "REQUIERE_REVISION" or not esquema.fila_inicio_datos:
            advertencias.append(
                f"La fila de inicio de datos en '{esquema.nombre_matriz}' requiere revisión humana "
                "(no se pudo determinar con certeza automática)."
            )

        # 2. Validación de columnas
        if not esquema.columnas_detectadas or manifesto.total_columnas == 0:
            errores.append(
                f"No se detectaron columnas válidas en la hoja '{esquema.hoja_inspeccionada}' "
                f"de la matriz '{esquema.nombre_matriz}'."
            )

        # 3. Zonas escribibles
        if not esquema.zonas_escribibles:
            advertencias.append(
                f"No se pudo delimitar una zona escribible segura para '{esquema.nombre_matriz}'."
            )

        # 4. Alerta de fórmulas protegidas
        if esquema.celdas_protegidas:
            num_formulas = sum(1 for c in esquema.celdas_protegidas if c.tipo_proteccion == "FORMULA")
            advertencias.append(
                f"Se detectaron {num_formulas} celdas con fórmulas protegidas en '{esquema.nombre_matriz}'. "
                "Fase 9 deberá proteger estas celdas contra sobrescritura."
            )

        # 5. Columnas sin fuente
        if manifesto.columnas_sin_fuente > 0:
            cols_sf = [it.encabezado_original for it in manifesto.items if it.estado == EstadoMapeo.SIN_FUENTE]
            advertencias.append(
                f"Existen {manifesto.columnas_sin_fuente} columnas sin fuente en '{esquema.nombre_matriz}': "
                f"{', '.join(cols_sf)}. Se conservarán en blanco conforme a la Regla de No Invención."
            )

        # 6. Catálogos pendientes
        if manifesto.columnas_catalogo_pendiente > 0:
            advertencias.append(
                f"Existen {manifesto.columnas_catalogo_pendiente} columnas en '{esquema.nombre_matriz}' con "
                "CATALOGO_PENDIENTE. Se mantendrán los valores originales de la fuente."
            )

        es_valida = len(errores) == 0
        logger.info(
            f"Validación de plantilla '{esquema.id_matriz}': Válida={es_valida}, "
            f"Errores={len(errores)}, Advertencias={len(advertencias)}"
        )

        return es_valida, errores, advertencias
