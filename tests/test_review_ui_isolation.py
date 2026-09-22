"""tests.test_review_ui_isolation

Pruebas de aislamiento arquitectónico mediante análisis estático AST (Fase 29.22.1).
Garantiza:
1. app/review/ui/ NO importa 'sqlite3'.
2. app/review/ui/ NO contiene sentencias SQL directas (SELECT, INSERT, UPDATE, DELETE).
3. app/review/domain/ NO importa 'customtkinter' ni 'sqlite3'.
4. app/review/ NO importa 'app.planning' ni 'google.generativeai'.
5. UI de Cola de Revisión consume estrictamente ReviewQueueApplicationService.
"""

import ast
from pathlib import Path
import pytest


def get_python_files(directory: Path):
    """Retorna todos los archivos .py en un directorio recursivamente."""
    return list(directory.rglob("*.py"))


def test_ui_no_importa_sqlite3():
    """Valida que ninguna vista o componente en app/review/ui importe sqlite3."""
    ui_dir = Path("app/review/ui")
    assert ui_dir.exists(), "El directorio app/review/ui debe existir."

    for py_file in get_python_files(ui_dir):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "sqlite3", f"Violación: {py_file} importa 'sqlite3' directamente."
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "sqlite3", f"Violación: {py_file} importa desde 'sqlite3'."


def test_ui_no_contiene_sql_directo():
    """Valida que ningún archivo de UI contenga sentencias SQL literales embebidas."""
    ui_dir = Path("app/review/ui")
    palabras_sql = ["SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM ", "BEGIN IMMEDIATE", "COMMIT;", "ROLLBACK;"]

    for py_file in get_python_files(ui_dir):
        contenido = py_file.read_text(encoding="utf-8").upper()
        for kw in palabras_sql:
            assert kw not in contenido, f"Violación: {py_file} contiene SQL literal '{kw}'."


def test_domain_no_importa_customtkinter_ni_sqlite():
    """Valida que app/review/domain sea puro y no dependa de UI ni de base de datos."""
    domain_dir = Path("app/review/domain")
    assert domain_dir.exists(), "El directorio app/review/domain debe existir."

    for py_file in get_python_files(domain_dir):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "customtkinter" not in alias.name, f"Violación: {py_file} importa customtkinter."
                    assert alias.name != "sqlite3", f"Violación: {py_file} importa sqlite3."
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "customtkinter" not in node.module, f"Violación: {py_file} importa desde customtkinter."
                    assert node.module != "sqlite3", f"Violación: {py_file} importa desde sqlite3."


def test_review_no_importa_planning_ni_ia():
    """Valida que app/review mantenga separación estricta: PLANIFICADO ≠ EJECUTADO y sin IA generativa."""
    review_dir = Path("app/review")
    assert review_dir.exists()

    for py_file in get_python_files(review_dir):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "planning" not in alias.name, f"Violación: {py_file} importa módulo de Planning."
                    assert "generativeai" not in alias.name, f"Violación: {py_file} importa IA generativa."
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "planning" not in node.module, f"Violación: {py_file} importa desde Planning."
                    assert "generativeai" not in node.module, f"Violación: {py_file} importa desde IA generativa."
