"""tests/test_resource_resolution.py

Pruebas unitarias deterministas para la resolución de recursos institucionales
(Fase 29.25.1 — TEST-RR-01 a TEST-RR-05).
"""

import hashlib
import os
import shutil
import sys
from pathlib import Path
import pytest

from app.core.resources import (
    PLANTILLAS_OFICIALES,
    PROJECT_ROOT,
    resolver_ruta_recurso,
    resolver_ruta_templates,
)

HASHES_PATRIMONIALES = {
    "Matriz_1_Consolidado_Actividades.xlsx": "FDAEBCB36CBCFAF7189CD03056E961BDA1E1D8D1093C501BD4FA3951618AD2AD",
    "Matriz_2_Estudiantes.xlsx": "11419CD22D986E195694F27D15236204AFA22526812F18CB4F2E1B7540F64400",
    "Matriz_3_Academicos_Administrativos.xlsx": "DC1786616CB1A9BC2F82A74CC693EE20AB95B689B658B366164F502201B07C87",
    "Matriz_4_Colaboradores.xlsx": "FD079C5F2BE780E602DC563696A6F157D76C4C20410308037CEC52F3D2654578",
    "Matriz_5_Protagonistas_Beneficiados.xlsx": "A3DFF20EC209DE209F59DD8B1AD1BE84AA7AEBD1536CED406C59453A08973DC3",
}


def _calcular_hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


class TestResourceResolution:
    """Suite de validación formal de resolución de recursos."""

    def test_rr_01_resolucion_entorno_desarrollo(self):
        """TEST-RR-01: Desarrollo normal localiza PROJECT_ROOT/templates/."""
        ruta_res = resolver_ruta_templates()
        assert ruta_res.is_dir(), f"La ruta resuelta debe ser un directorio: {ruta_res}"
        esperada = PROJECT_ROOT / "templates"
        assert ruta_res.resolve() == esperada.resolve(), (
            f"En desarrollo debe resolver a {esperada}, obtuvo {ruta_res}"
        )

        for archivo in PLANTILLAS_OFICIALES:
            p_archivo = ruta_res / archivo
            assert p_archivo.exists(), f"La plantilla oficial {archivo} debe existir en {ruta_res}"

    def test_rr_02_simular_entorno_empaquetado(self, monkeypatch, tmp_path):
        """TEST-RR-02: Simular entorno empaquetado PyInstaller (_MEIPASS y frozen).

        Verifica que se detecta la estructura interna y que la ruta resultante
        existe físicamente y contiene las plantillas válidas.
        """
        # Crear estructura simulada de PyInstaller en tmp_path
        bundle_dir = tmp_path / "pyinstaller_bundle"
        internal_templates = bundle_dir / "templates"
        internal_templates.mkdir(parents=True)

        # Copiar las plantillas reales al directorio simulado
        origen_templates = PROJECT_ROOT / "templates"
        for mat in PLANTILLAS_OFICIALES:
            shutil.copy2(origen_templates / mat, internal_templates / mat)

        # Simular atributos de PyInstaller
        monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)

        # Resolver sin argumentos (como hace el runtime del EXE)
        ruta_res = resolver_ruta_templates()

        assert ruta_res.is_dir()
        assert ruta_res.resolve() == internal_templates.resolve()

        # Verificar que contiene las plantillas válidas
        for mat in PLANTILLAS_OFICIALES:
            p_mat = ruta_res / mat
            assert p_mat.exists()
            assert p_mat.stat().st_size > 0
            assert _calcular_hash(p_mat) == HASHES_PATRIMONIALES[mat]

    def test_rr_03_cinco_plantillas_detectadas_tamano_positivo(self):
        """TEST-RR-03: M1–M5 existen y todas poseen tamaño estrictamente positivo."""
        ruta_res = resolver_ruta_templates()
        assert len(PLANTILLAS_OFICIALES) == 5

        for mat in PLANTILLAS_OFICIALES:
            p = ruta_res / mat
            assert p.exists(), f"No se encontró la plantilla {mat}"
            assert p.stat().st_size > 1000, f"El archivo {mat} está vacío o truncado (<1000 bytes)"

    def test_rr_04_cwd_independiente_directorio_externo(self, monkeypatch, tmp_path):
        """TEST-RR-04: Cambiar CWD a un directorio temporal externo.

        La resolución debe continuar encontrando las 5 plantillas institucionales
        sin afectación por el CWD.
        """
        dir_externo = tmp_path / "directorio_arbitrario"
        dir_externo.mkdir()

        # Cambiar el working directory al directorio temporal externo
        monkeypatch.chdir(dir_externo)
        assert Path.cwd().resolve() == dir_externo.resolve()

        # Resolver plantillas
        ruta_res = resolver_ruta_templates()
        assert ruta_res.is_dir()
        assert ruta_res.resolve() == (PROJECT_ROOT / "templates").resolve()

        # Verificar que todas las plantillas siguen siendo accesibles
        for mat in PLANTILLAS_OFICIALES:
            p = ruta_res / mat
            assert p.exists(), f"No se pudo acceder a {mat} con CWD={dir_externo}"
            assert p.stat().st_size > 0

    def test_rr_05_hashes_patrimoniales_intactos(self):
        """TEST-RR-05: Verificar los cinco hashes criptográficos patrimoniales de M1–M5."""
        ruta_res = resolver_ruta_templates()

        for mat, hash_esperado in HASHES_PATRIMONIALES.items():
            p = ruta_res / mat
            assert p.exists(), f"Plantilla {mat} ausente en {ruta_res}"
            hash_calculado = _calcular_hash(p)
            assert hash_calculado == hash_esperado, (
                f"Alteración detectada en {mat}! Esperado {hash_esperado}, calculado {hash_calculado}"
            )

    def test_rr_caso_a_ruta_explicita_respetada(self, tmp_path):
        """Caso A: Rutas explícitas personalizadas suministradas por el llamador se respetan."""
        custom_dir = tmp_path / "custom_templates"
        custom_dir.mkdir()

        # Ruta explícita vacía para test de testing
        res = resolver_ruta_templates(custom_dir)
        assert res.resolve() == custom_dir.resolve()

    def test_rr_recurso_generico(self):
        """Verifica que resolver_ruta_recurso resuelve correctamente activos y configuración."""
        ruta_assets = resolver_ruta_recurso("assets")
        assert ruta_assets.exists()
        assert (ruta_assets / "bicu_logo.ico").exists()
