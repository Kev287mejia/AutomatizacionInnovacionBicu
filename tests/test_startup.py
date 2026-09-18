"""
tests/test_startup.py

Pruebas de FASE 1 — Estructura del proyecto.

Objetivo: verificar que el proyecto arranca correctamente:
  - Las carpetas necesarias existen.
  - Los archivos de configuración existen y son legibles.
  - El sistema de logging se inicializa sin errores.
  - El módulo main.py es importable sin errores.
  - El logger produce mensajes sin excepciones.

Estas pruebas NO validan lógica de negocio.
Solo verifican que la estructura del proyecto es correcta.
"""

import sys
import logging
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Configurar el path para que pytest encuentre el paquete app/
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


# ===========================================================================
# GRUPO 1: Estructura de carpetas
# ===========================================================================

class TestEstructuraDeCarpetas:
    """Verifica que todas las carpetas del proyecto existen."""

    CARPETAS_REQUERIDAS = [
        "app",
        "app/core",
        "app/core/models",
        "app/core/catalog",
        "app/core/constants",
        "app/core/exceptions",
        "app/parsers",
        "app/normalization",
        "app/matching",
        "app/validation",
        "app/routing",
        "app/statistics",
        "app/review",
        "app/exporters",
        "app/audit",
        "config",
        "config/catalogs",
        "config/sources",
        "input",
        "output",
        "tests",
        "logs",
    ]

    @pytest.mark.parametrize("carpeta", CARPETAS_REQUERIDAS)
    def test_carpeta_existe(self, carpeta):
        """Cada carpeta requerida debe existir en el proyecto."""
        ruta = BASE_DIR / carpeta
        assert ruta.exists(), f"Carpeta faltante: {carpeta}"
        assert ruta.is_dir(), f"Se esperaba un directorio, no un archivo: {carpeta}"


# ===========================================================================
# GRUPO 2: Archivos de configuración
# ===========================================================================

class TestArchivosDeConfiguracion:
    """Verifica que los archivos de configuración existen y son legibles."""

    def test_requirements_txt_existe(self):
        """requirements.txt debe existir."""
        ruta = BASE_DIR / "requirements.txt"
        assert ruta.exists(), "Falta requirements.txt"

    def test_requirements_tiene_contenido(self):
        """requirements.txt no debe estar vacío."""
        ruta = BASE_DIR / "requirements.txt"
        contenido = ruta.read_text(encoding="utf-8")
        assert len(contenido.strip()) > 0, "requirements.txt está vacío"

    def test_readme_existe(self):
        """README.md debe existir."""
        ruta = BASE_DIR / "README.md"
        assert ruta.exists(), "Falta README.md"

    def test_settings_yaml_existe(self):
        """config/settings.yaml debe existir."""
        ruta = BASE_DIR / "config" / "settings.yaml"
        assert ruta.exists(), "Falta config/settings.yaml"

    def test_settings_yaml_es_yaml_valido(self):
        """config/settings.yaml debe ser YAML válido y parseable."""
        ruta = BASE_DIR / "config" / "settings.yaml"
        with open(ruta, encoding="utf-8") as f:
            datos = yaml.safe_load(f)
        assert datos is not None, "settings.yaml está vacío o no es YAML válido"
        assert isinstance(datos, dict), "settings.yaml debe ser un diccionario"

    def test_settings_tiene_seccion_sistema(self):
        """settings.yaml debe tener la sección 'sistema'."""
        ruta = BASE_DIR / "config" / "settings.yaml"
        with open(ruta, encoding="utf-8") as f:
            datos = yaml.safe_load(f)
        assert "sistema" in datos, "Falta la sección 'sistema' en settings.yaml"

    def test_settings_tiene_seccion_logging(self):
        """settings.yaml debe tener la sección 'logging'."""
        ruta = BASE_DIR / "config" / "settings.yaml"
        with open(ruta, encoding="utf-8") as f:
            datos = yaml.safe_load(f)
        assert "logging" in datos, "Falta la sección 'logging' en settings.yaml"

    def test_sex_mappings_json_existe(self):
        """config/sources/sex_mappings.json debe existir."""
        ruta = BASE_DIR / "config" / "sources" / "sex_mappings.json"
        assert ruta.exists(), "Falta config/sources/sex_mappings.json"

    def test_catalogo_carreras_existe(self):
        """config/catalogs/carreras.json debe existir."""
        ruta = BASE_DIR / "config" / "catalogs" / "carreras.json"
        assert ruta.exists(), "Falta config/catalogs/carreras.json"

    def test_catalogo_etnias_existe(self):
        """config/catalogs/etnias.json debe existir."""
        ruta = BASE_DIR / "config" / "catalogs" / "etnias.json"
        assert ruta.exists(), "Falta config/catalogs/etnias.json"


# ===========================================================================
# GRUPO 3: Módulos Python
# ===========================================================================

class TestModulosPython:
    """Verifica que los módulos principales son importables."""

    def test_init_files_existen(self):
        """Todos los paquetes deben tener __init__.py."""
        paquetes = [
            "app",
            "app/core",
            "app/core/models",
            "app/core/catalog",
            "app/core/constants",
            "app/core/exceptions",
            "app/parsers",
            "app/normalization",
            "app/matching",
            "app/validation",
            "app/routing",
            "app/statistics",
            "app/review",
            "app/exporters",
            "app/audit",
            "tests",
        ]
        faltantes = []
        for pkg in paquetes:
            init_path = BASE_DIR / pkg / "__init__.py"
            if not init_path.exists():
                faltantes.append(f"{pkg}/__init__.py")
        assert not faltantes, f"Archivos __init__.py faltantes:\n" + "\n".join(faltantes)

    def test_importar_audit_logger(self):
        """app.audit.audit_logger debe importarse sin errores."""
        from app.audit.audit_logger import get_logger, configurar_logging
        assert callable(get_logger), "get_logger debe ser una función"
        assert callable(configurar_logging), "configurar_logging debe ser una función"

    def test_importar_main(self):
        """app.main debe importarse sin errores."""
        import app.main
        assert hasattr(app.main, "main"), "app.main debe tener una función main()"
        assert hasattr(app.main, "MODOS_DISPONIBLES"), "app.main debe tener MODOS_DISPONIBLES"


# ===========================================================================
# GRUPO 4: Sistema de logging
# ===========================================================================

class TestSistemaDeLogging:
    """Verifica que el sistema de logging funciona correctamente."""

    def test_get_logger_devuelve_logger(self):
        """get_logger() debe devolver un objeto logging.Logger."""
        from app.audit.audit_logger import get_logger
        logger = get_logger("test_startup")
        assert isinstance(logger, logging.Logger), \
            "get_logger() debe devolver un logging.Logger"

    def test_logger_escribe_sin_excepcion(self):
        """El logger debe escribir mensajes sin lanzar excepciones."""
        from app.audit.audit_logger import get_logger
        logger = get_logger("test_startup.escritura")
        try:
            logger.debug("Test DEBUG desde test_startup")
            logger.info("Test INFO desde test_startup")
            logger.warning("Test WARNING desde test_startup")
        except Exception as e:
            pytest.fail(f"El logger lanzó una excepción: {e}")

    def test_archivo_log_se_crea(self):
        """Después de inicializar el logging, debe existir el archivo de log."""
        from app.audit.audit_logger import configurar_logging, get_logger
        configurar_logging()
        logger = get_logger("test_startup.archivo")
        logger.info("Verificando creación del archivo de log.")
        ruta_log = BASE_DIR / "logs" / "sistema.log"
        assert ruta_log.exists(), \
            f"El archivo de log no fue creado en: {ruta_log}"


# ===========================================================================
# GRUPO 5: Modos de ejecución
# ===========================================================================

class TestModosDEjecucion:
    """Verifica que main.py tiene los modos correctamente definidos."""

    def test_modos_disponibles_definidos(self):
        """MODOS_DISPONIBLES debe contener los 5 modos del sistema."""
        from app.main import MODOS_DISPONIBLES
        modos_esperados = {"analyze", "validate", "preview", "export", "audit"}
        modos_actuales = set(MODOS_DISPONIBLES.keys())
        assert modos_esperados == modos_actuales, \
            f"Modos esperados: {modos_esperados}\nModos actuales: {modos_actuales}"

    def test_modos_disponibles_fase_5(self):
        """En Fase 5, 'analyze' y 'validate' están disponibles."""
        from app.main import MODOS_DISPONIBLES
        disponibles = {m for m, info in MODOS_DISPONIBLES.items() if info["disponible"]}
        assert disponibles == {"analyze", "validate"}, \
            f"Modos disponibles esperados en Fase 5: {{'analyze', 'validate'}}, obtenidos: {disponibles}"

    def test_modos_disponibles_fase_6(self):
        """En Fase 6, 'analyze' y 'validate' continúan disponibles con routing integrado."""
        from app.main import MODOS_DISPONIBLES
        disponibles = {m for m, info in MODOS_DISPONIBLES.items() if info["disponible"]}
        assert disponibles == {"analyze", "validate"}, \
            f"Modos disponibles esperados en Fase 6: {{'analyze', 'validate'}}, obtenidos: {disponibles}"

    def test_modos_disponibles_fase_7(self):
        """En Fase 7, 'analyze' y 'validate' continúan disponibles con motor estadístico integrado."""
        from app.main import MODOS_DISPONIBLES
        disponibles = {m for m, info in MODOS_DISPONIBLES.items() if info["disponible"]}
        assert disponibles == {"analyze", "validate"}, \
            f"Modos disponibles esperados en Fase 7: {{'analyze', 'validate'}}, obtenidos: {disponibles}"

    def test_modos_tienen_descripcion(self):
        """Cada modo debe tener una descripción y número de fase."""
        from app.main import MODOS_DISPONIBLES
        for nombre, info in MODOS_DISPONIBLES.items():
            assert "descripcion" in info, f"Modo '{nombre}' no tiene 'descripcion'"
            assert "fase" in info, f"Modo '{nombre}' no tiene 'fase'"
            assert isinstance(info["descripcion"], str), \
                f"La descripción de '{nombre}' debe ser string"
