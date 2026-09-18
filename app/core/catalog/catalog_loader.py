"""
app.core.catalog.catalog_loader

Cargador de catálogos institucionales externos (archivos JSON en config/).
Responsabilidades:
- Cargar listas de valores oficiales (carreras, etnias, municipios).
- Cargar mapeos de códigos de sexo por fuente específica (config/sources/sex_mappings.json).
- Regla C-19: Los catálogos están desacoplados del código para permitir su edición sin programar.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from app.audit.audit_logger import get_logger
from app.core.exceptions.system_exceptions import CatalogNotFoundError

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
CATALOGS_DIR = CONFIG_DIR / "catalogs"
SOURCES_DIR = CONFIG_DIR / "sources"


class CatalogLoader:
    """
    Carga y gestiona el acceso a los catálogos en formato JSON.
    """

    @staticmethod
    def cargar_json(ruta: Path) -> dict | list:
        """Carga un archivo JSON garantizando UTF-8 y manejo de excepciones."""
        if not ruta.exists():
            logger.warning(f"Catálogo no encontrado en ruta: {ruta}")
            raise CatalogNotFoundError(f"No se encontró el archivo de catálogo: {ruta}")
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error al decodificar catálogo {ruta}: {e}")
            raise

    @classmethod
    def obtener_catalogo_carreras(cls) -> List[str]:
        """Obtiene la lista de carreras oficiales del catálogo."""
        ruta = CATALOGS_DIR / "carreras.json"
        try:
            datos = cls.cargar_json(ruta)
            if isinstance(datos, list):
                return datos
            return datos.get("carreras", [])
        except CatalogNotFoundError:
            return []

    @classmethod
    def obtener_catalogo_etnias(cls) -> List[str]:
        """Obtiene la lista de etnias o pueblos originarios del catálogo."""
        ruta = CATALOGS_DIR / "etnias.json"
        try:
            datos = cls.cargar_json(ruta)
            if isinstance(datos, list):
                return datos
            return datos.get("etnias", [])
        except CatalogNotFoundError:
            return []

    @classmethod
    def obtener_mapeos_sexo(cls) -> Dict[str, Dict[str, str]]:
        """
        Obtiene los mapeos de sexo específicos por fuente (Regla C-08).
        Ejemplo: {"fuente_A": {"M": "FEMENINO", "V": "MASCULINO"}}
        """
        ruta = SOURCES_DIR / "sex_mappings.json"
        try:
            datos = cls.cargar_json(ruta)
            if isinstance(datos, dict):
                return datos.get("mapeos", datos)
            return {}
        except CatalogNotFoundError:
            return {}

    @classmethod
    def normalizar_sexo_segun_fuente(cls, valor_original: Optional[str], fuente: str) -> Optional[str]:
        """
        Interpreta un código de sexo según la fuente de origen específica.
        Si la fuente o el código no existen, devuelve None (sin inventar).
        """
        if not valor_original:
            return None
        mapeos = cls.obtener_mapeos_sexo()
        mapeo_fuente = mapeos.get(fuente, {})
        clave = valor_original.strip().upper()
        return mapeo_fuente.get(clave, None)
