"""
tests.test_word_consolidator.test_ui_service

Pruebas unitarias para la capa de servicios de aplicación y traducción de errores (Fase 14.9).
Valida:
1. ErrorTranslator: traducción precisa de excepciones técnicas a mensajes humanos accionables.
2. ConsolidationAppService: resolución de carpetas, análisis estructural de matrices,
   construcción de períodos y preflight check.
"""

from datetime import date
from pathlib import Path
import pytest

from app.word_consolidator.models import PeriodoConsolidacion, TipoPeriodo
from app.word_consolidator.pipeline import (
    ArchivoMatrizInvalidoError,
    ErrorIntegridadArchivo,
    EstructuraMatrizInvalidaError,
    MatricesFaltantesError,
    MatrizDuplicadaError,
)
from app.word_consolidator.ui.services.application_service import (
    ConsolidationAppService,
    PreflightStatus,
)
from app.word_consolidator.ui.services.error_translator import (
    ErrorInstitucionalInfo,
    ErrorTranslator,
)


class TestErrorTranslator:
    """Suite de pruebas para ErrorTranslator."""

    def test_01_traduccion_matrices_faltantes(self):
        ex = MatricesFaltantesError("Faltan matrices oficiales: ['M3', 'M4']. Identificadas: ['M1', 'M2', 'M5']")
        info = ErrorTranslator.traducir(ex)
        assert isinstance(info, ErrorInstitucionalInfo)
        assert info.titulo == "Matrices Oficiales Incompletas"
        assert info.es_bloqueante is True
        assert "M3" in info.mensaje_principal
        assert "M4" in info.mensaje_principal
        assert "Seleccione o arrastre" in info.accion_sugerida
        assert len(info.detalle_tecnico) > 0

    def test_02_traduccion_matriz_duplicada(self):
        ex = MatrizDuplicadaError("Se detectaron matrices duplicadas: M2: ['est1.xlsx', 'est2.xlsx']")
        info = ErrorTranslator.traducir(ex)
        assert info.titulo == "Archivos Duplicados para la Misma Matriz"
        assert info.es_bloqueante is True
        assert "est1.xlsx" in info.mensaje_principal
        assert "Retire las copias" in info.accion_sugerida

    def test_03_traduccion_estructura_invalida(self):
        ex = EstructuraMatrizInvalidaError("El archivo 'lista.xlsx' tiene 10 columnas y no coincide con BICU")
        info = ErrorTranslator.traducir(ex)
        assert info.titulo == "Estructura de Matriz No Reconocida"
        assert "plantilla oficial" in info.accion_sugerida

    def test_04_traduccion_archivo_invalido(self):
        ex = ArchivoMatrizInvalidoError("El archivo especificado no existe o no es accesible")
        info = ErrorTranslator.traducir(ex)
        assert info.titulo == "Archivo No Válido o Inaccesible"
        assert "Compruebe que el archivo exista" in info.accion_sugerida

    def test_05_traduccion_integridad_sha256(self):
        ex = ErrorIntegridadArchivo("¡ALERTA CRÍTICA DE INTEGRIDAD! M1 sufrió mutación física")
        info = ErrorTranslator.traducir(ex)
        assert info.titulo == "Alerta Crítica de Integridad"
        assert "modificado externamente" in info.mensaje_principal

    def test_06_traduccion_permission_error_docx(self):
        ex = PermissionError("[WinError 32] El proceso no tiene acceso al archivo porque está siendo utilizado")
        info = ErrorTranslator.traducir(ex)
        assert info.titulo == "Archivo Bloqueado por Microsoft Word u Otro Programa"
        assert "Cierre Microsoft Word" in info.accion_sugerida

    def test_07_traduccion_error_generico(self):
        ex = RuntimeError("Fallo inesperado de conexión de memoria")
        info = ErrorTranslator.traducir(ex)
        assert info.titulo == "Error Operativo Inesperado"
        assert "RuntimeError" in info.mensaje_principal
        assert "soporte técnico" in info.accion_sugerida


class TestConsolidationAppServicePeriodos:
    """Suite de pruebas para la construcción inmutable de períodos."""

    def test_08_construir_periodo_semana_valido(self):
        p = ConsolidationAppService.construir_periodo(
            tipo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
        )
        assert p.tipo_periodo == TipoPeriodo.SEMANA
        assert p.anio == 2026
        assert p.mes == 9
        assert p.semana == 1
        assert p.etiqueta == "Septiembre 2026 — Semana 1"

    def test_09_construir_periodo_semana_invalido_mes_o_semana(self):
        with pytest.raises(ValueError, match="mes válido"):
            ConsolidationAppService.construir_periodo(
                tipo=TipoPeriodo.SEMANA,
                anio=2026,
                mes=13,
                semana=1,
            )

        with pytest.raises(ValueError, match="semana válida"):
            ConsolidationAppService.construir_periodo(
                tipo=TipoPeriodo.SEMANA,
                anio=2026,
                mes=9,
                semana=6,
            )

    def test_10_construir_periodo_mes(self):
        p = ConsolidationAppService.construir_periodo(
            tipo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
        )
        assert p.tipo_periodo == TipoPeriodo.MES
        assert p.etiqueta == "Septiembre 2026"

    def test_11_construir_periodo_trimestre(self):
        p = ConsolidationAppService.construir_periodo(
            tipo=TipoPeriodo.TRIMESTRE,
            anio=2026,
            trimestre=3,
        )
        assert p.tipo_periodo == TipoPeriodo.TRIMESTRE
        assert p.mes == 9
        assert "Trimestre III" in p.etiqueta

    def test_12_construir_periodo_semestre(self):
        p = ConsolidationAppService.construir_periodo(
            tipo=TipoPeriodo.SEMESTRE,
            anio=2026,
            semestre=2,
        )
        assert p.tipo_periodo == TipoPeriodo.SEMESTRE
        assert p.mes == 12
        assert "Semestre II" in p.etiqueta

    def test_13_construir_periodo_anio(self):
        p = ConsolidationAppService.construir_periodo(
            tipo=TipoPeriodo.ANIO,
            anio=2026,
        )
        assert p.tipo_periodo == TipoPeriodo.ANIO
        assert p.etiqueta == "Año Institucional 2026"

    def test_14_construir_periodo_personalizado(self):
        ini = date(2026, 9, 1)
        fin = date(2026, 9, 15)
        p = ConsolidationAppService.construir_periodo(
            tipo=TipoPeriodo.PERSONALIZADO,
            anio=2026,
            fecha_inicio=ini,
            fecha_fin=fin,
        )
        assert p.tipo_periodo == TipoPeriodo.PERSONALIZADO
        assert "01/09/2026 al 15/09/2026" in p.etiqueta

    def test_15_rechazo_fechas_invertidas_personalizado(self):
        ini = date(2026, 9, 15)
        fin = date(2026, 9, 1)
        with pytest.raises(ValueError, match="no puede ser anterior"):
            ConsolidationAppService.construir_periodo(
                tipo=TipoPeriodo.PERSONALIZADO,
                anio=2026,
                fecha_inicio=ini,
                fecha_fin=fin,
            )


class TestConsolidationAppServicePreflight:
    """Suite de pruebas para validación pre-vuelo."""

    def test_16_directorio_salida_predeterminado_existe(self):
        salida = ConsolidationAppService.resolver_directorio_salida_predeterminado()
        assert salida.exists()
        assert salida.is_dir()
        assert "BICU_Consolidados" in salida.name

    def test_17_preflight_bloqueado_sin_matrices(self, tmp_path):
        status = ConsolidationAppService.validar_preflight(
            matrices={},
            periodo=None,
            carpeta_salida=tmp_path,
        )
        assert status.listo_para_procesar is False
        assert status.matrices_completas is False
        assert len(status.errores_bloqueantes) > 0

    def test_18_preflight_bloqueado_matrices_incompletas(self, tmp_path):
        p_m1 = tmp_path / "m1.xlsx"
        p_m1.write_text("fake")
        matrices = {"M1": p_m1}

        status = ConsolidationAppService.validar_preflight(
            matrices=matrices,
            periodo=None,
            carpeta_salida=tmp_path,
        )
        assert status.listo_para_procesar is False
        assert status.matrices_completas is False
        assert any("Faltan matrices" in err for err in status.errores_bloqueantes)

    def test_19_preflight_listo_para_procesar(self, tmp_path):
        # Crear 5 archivos dummy existentes
        matrices = {}
        for m in ["M1", "M2", "M3", "M4", "M5"]:
            f = tmp_path / f"{m}.xlsx"
            f.write_text("dummy")
            matrices[m] = f

        periodo = ConsolidationAppService.construir_periodo(
            tipo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
        )

        status = ConsolidationAppService.validar_preflight(
            matrices=matrices,
            periodo=periodo,
            carpeta_salida=tmp_path,
        )
        assert status.listo_para_procesar is True
        assert status.matrices_completas is True
        assert status.periodo_valido is True
        assert status.carpeta_salida_valida is True
        assert len(status.errores_bloqueantes) == 0

    def test_20_recuperacion_informes_narrativos_institucionales_sept_2026(self):
        periodo = ConsolidationAppService.construir_periodo(
            tipo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
        )
        narrativos = ConsolidationAppService.obtener_informes_narrativos_institucionales(periodo=periodo)
        assert narrativos is not None
        assert "caso_real_sept_2026" in narrativos
        caso = narrativos["caso_real_sept_2026"]
        assert caso["estudiantes"] == 15
        assert caso["administrativos"] == 2
        assert caso["docentes"] == 1
        assert caso["total"] == 18

    def test_21_recuperacion_informes_narrativos_archivo_externo(self, tmp_path):
        import json
        json_file = tmp_path / "informes_narrativos.json"
        datos_custom = {
            "actividad_custom": {
                "nombre_actividad": "Taller Regional",
                "estudiantes": 20,
                "administrativos": 5,
                "docentes": 3,
                "total": 28,
            }
        }
        json_file.write_text(json.dumps(datos_custom), encoding="utf-8")

        narrativos = ConsolidationAppService.obtener_informes_narrativos_institucionales(
            periodo=None,
            carpeta_matrices=tmp_path,
        )
        assert narrativos is not None
        assert "actividad_custom" in narrativos
        assert narrativos["actividad_custom"]["total"] == 28
