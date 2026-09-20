"""
Tests de No Invasion del Nucleo y Aislamiento Arquitectonico — Modulo Planificacion.

Fase 29.3 — Implementacion del Dominio Puro
Fuente: Especificacion §16, §17, §19

Verifica que el paquete app.planning.domain sea un DOMINIO PURO:
  - Cero dependencias de infraestructura (sqlite3, openpyxl, docx, requests, etc.)
  - Cero dependencias de UI (tkinter, customtkinter)
  - Cero dependencias de SDKs de IA (google.generativeai, openai, anthropic, etc.)
  - Cero dependencias del nucleo certificado word_consolidator
  - Pureza de tipos e inmutabilidad en Value Objects
"""
import ast
import os
import pathlib
import pytest

DOMAIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "app" / "planning" / "domain"

FORBIDDEN_MODULES = {
    # Persistencia
    "sqlite3",
    "sqlalchemy",
    # Archivos Office / Formatos
    "openpyxl",
    "docx",
    "python-docx",
    "docxtpl",
    "pandas",
    # Red / HTTP / APIs
    "requests",
    "urllib",
    "http.client",
    "aiohttp",
    "httpx",
    # SDKs de IA
    "google.generativeai",
    "openai",
    "anthropic",
    "ollama",
    # Interfaz Grafica
    "tkinter",
    "customtkinter",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    # Nucleo congelado
    "app.word_consolidator",
    "app.domain",
    "app.application",
    "app.infrastructure",
}


def get_domain_python_files():
    """Retorna todos los archivos .py en app/planning/domain/."""
    return list(DOMAIN_DIR.glob("*.py"))


class ImportExtractor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)


class TestPlanningDomainIsolation:
    """Verifica el aislamiento estricto del dominio de planificacion."""

    def test_domain_directory_exists(self):
        """El directorio app/planning/domain existe."""
        assert DOMAIN_DIR.exists()
        assert DOMAIN_DIR.is_dir()

    def test_domain_files_found(self):
        """Se encuentran los archivos de dominio esperados."""
        files = {f.name for f in get_domain_python_files()}
        expected = {
            "__init__.py",
            "catalogs.py",
            "value_objects.py",
            "entities.py",
            "rules_engine.py",
            "validator.py",
            "dtos.py",
            "ports.py",
        }
        assert expected.issubset(files)

    @pytest.mark.parametrize("py_file", get_domain_python_files(), ids=lambda f: f.name)
    def test_no_forbidden_imports(self, py_file):
        """Ningun archivo de dominio importa modulos prohibidos de infraestructura, UI o IA."""
        with open(py_file, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(py_file))
        extractor = ImportExtractor()
        extractor.visit(tree)

        for imp in extractor.imports:
            # Comprobar contra lista de modulos prohibidos
            for forbidden in FORBIDDEN_MODULES:
                assert not (imp == forbidden or imp.startswith(forbidden + ".")), (
                    f"Violacion de Dominio Puro en {py_file.name}: "
                    f"importa modulo prohibido '{imp}' (regla: no {forbidden})"
                )

    @pytest.mark.parametrize("py_file", get_domain_python_files(), ids=lambda f: f.name)
    def test_no_word_consolidator_coupling(self, py_file):
        """Ningun archivo de dominio importa del nucleo word_consolidator."""
        with open(py_file, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(py_file))
        extractor = ImportExtractor()
        extractor.visit(tree)

        for imp in extractor.imports:
            assert "word_consolidator" not in imp, (
                f"Acoplamiento prohibido en {py_file.name}: "
                f"importa del nucleo word_consolidator '{imp}'"
            )

    def test_domain_only_uses_standard_library_and_own_package(self):
        """El dominio solo depende de la biblioteca estandar de Python y su propio paquete."""
        allowed_prefixes = {
            "__future__",
            "abc",
            "dataclasses",
            "datetime",
            "enum",
            "typing",
            "uuid",
            "re",
            "copy",
            "app.planning.domain",
        }

        for py_file in get_domain_python_files():
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(py_file))
            extractor = ImportExtractor()
            extractor.visit(tree)

            for imp in extractor.imports:
                is_allowed = any(
                    imp == prefix or imp.startswith(prefix + ".")
                    for prefix in allowed_prefixes
                )
                assert is_allowed, (
                    f"Importacion no permitida en {py_file.name}: '{imp}'. "
                    f"El dominio puro solo puede importar libreria estandar y app.planning.domain."
                )
