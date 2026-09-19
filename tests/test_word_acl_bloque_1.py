"""tests.test_word_acl_bloque_1

Tests unitarios e integracion para la capa WordACL — Fase 26.8 Bloque 1.

Cobertura de todos los requerimientos segun plan de implementacion:
    GRUPO 1: Sexo (tests 1–8)
    GRUPO 2: Resultados (tests 9–13)
    GRUPO 3: Cifras (tests 14–18)
    GRUPO 4: Revision (tests 19–24)
    GRUPO 5: Evidencias (tests 25–28)
    GRUPO 6: Arquitectura (tests 29–35)
    GRUPO 7: Integridad (tests 36–39)
    GRUPO 8: Integracion y Contratos Patrimoniales (tests 40–47)
"""

from pathlib import Path
from typing import List, Optional
import pytest

from app.application.word_acl.policies import PoliticaPresentacionRevisionWord
from app.application.word_acl.dtos import (
    FuenteCifras,
    FuenteResultados,
    WordActividadDTO,
    WordEstamentoItemDTO,
    WordEvidenciaItemDTO,
    WordWeeklyReportDataset,
)
from app.application.word_acl.adapters import WordACL
from app.application.dto.export_dtos import PoliticaExportacionRevision
from app.word_consolidator.document.institutional_models import (
    ConteoSexoInstitucional,
    ProtagonistaEstamentoInstitucional,
)


# ===========================================================================
# GRUPO 1: SEXO
# ===========================================================================


class TestSexoTraduccion:
    """Tests 1–8: Politica de sexo canonica y manejo de NULL."""

    def test_01_f_mapea_a_mujeres(self):
        """Test 1: SQLite 'F' -> mujeres += 1; varones sin cambio."""
        dto = WordACL.adaptar_estamento(
            estamento_tipo="ESTUDIANTE",
            participantes_con_sexo=["F"],
            orden_presentacion=1,
        )
        assert dto.mujeres == 1, "F debe mapearse a la columna mujeres."
        assert dto.varones == 0, "varones no debe incrementarse con 'F'."
        assert dto.sin_sexo_disponible == 0

    def test_02_m_mapea_a_varones(self):
        """Test 2: SQLite 'M' -> varones += 1; mujeres sin cambio."""
        dto = WordACL.adaptar_estamento(
            estamento_tipo="ESTUDIANTE",
            participantes_con_sexo=["M"],
            orden_presentacion=1,
        )
        assert dto.varones == 1, "M debe mapearse a la columna varones."
        assert dto.mujeres == 0, "mujeres no debe incrementarse con 'M'."
        assert dto.sin_sexo_disponible == 0

    def test_03_null_no_se_convierte_a_m_ni_v(self):
        """Test 3: NULL no se convierte a mujeres ni a varones."""
        dto = WordACL.adaptar_estamento(
            estamento_tipo="ESTUDIANTE",
            participantes_con_sexo=[None],
            orden_presentacion=1,
        )
        assert dto.mujeres == 0, "NULL no debe ir a mujeres."
        assert dto.varones == 0, "NULL no debe ir a varones."

    def test_04_null_incrementa_sin_sexo_disponible(self):
        """Test 4: NULL incrementa sin_sexo_disponible."""
        dto = WordACL.adaptar_estamento(
            estamento_tipo="ESTUDIANTE",
            participantes_con_sexo=[None, None, "F"],
            orden_presentacion=1,
        )
        assert dto.sin_sexo_disponible == 2, "Dos NULL deben incrementar sin_sexo_disponible a 2."
        assert dto.mujeres == 1

    def test_05_participante_null_no_se_elimina(self):
        """Test 5: Participante con sexo NULL no se elimina del conteo total."""
        dto = WordACL.adaptar_estamento(
            estamento_tipo="COLABORADOR",
            participantes_con_sexo=["F", None, "M", None],
            orden_presentacion=1,
        )
        assert dto.total_participantes == 4, (
            "El total debe incluir a los participantes con sexo NULL; no se eliminan."
        )

    def test_06_invariante_condicional_sin_null(self):
        """Test 6: Cuando sin_sexo_disponible == 0, total == mujeres + varones."""
        dto = WordACL.adaptar_estamento(
            estamento_tipo="ESTUDIANTE",
            participantes_con_sexo=["F", "M", "F"],
            orden_presentacion=1,
        )
        assert dto.sin_sexo_disponible == 0
        assert dto.total_participantes == dto.mujeres + dto.varones
        assert WordACL.verificar_invariante_sexo(
            dto.mujeres, dto.varones, dto.sin_sexo_disponible, dto.total_participantes
        )

    def test_07_invariante_condicional_con_null(self):
        """Test 7: Cuando sin_sexo_disponible > 0, total == mujeres + varones + sin_sexo."""
        dto = WordACL.adaptar_estamento(
            estamento_tipo="ESTUDIANTE",
            participantes_con_sexo=["F", None, "M"],
            orden_presentacion=1,
        )
        assert dto.sin_sexo_disponible == 1
        assert dto.mujeres + dto.varones != dto.total_participantes
        assert dto.total_participantes == dto.mujeres + dto.varones + dto.sin_sexo_disponible
        assert WordACL.verificar_invariante_sexo(
            dto.mujeres, dto.varones, dto.sin_sexo_disponible, dto.total_participantes
        )

    def test_08_observacion_calidad_registrada_por_null(self):
        """Test 8: Se registran observaciones de calidad cuando hay sexo NULL."""
        act = WordACL.adaptar_actividad(
            id_actividad="act-008",
            nombre_actividad="Taller Comunitario",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=["F", None],
        )
        assert any("sin sexo disponible" in obs.lower() for obs in act.observaciones_calidad)


# ===========================================================================
# GRUPO 2: RESULTADOS
# ===========================================================================


class TestResultados:
    """Tests 9–13: Politica de fuente de resultados / logros."""

    def test_09_fuente_resultados_vacio_produce_cadena_vacia(self):
        """Test 9: VACIO -> descripcion_logros == ''."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-009",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=[],
            fuente_resultados=FuenteResultados.VACIO,
        )
        assert dto.descripcion_logros == ""
        assert dto.fuente_resultados == FuenteResultados.VACIO

    def test_10_resultados_registrados_se_conserva(self):
        """Test 10: RESULTADOS_REGISTRADOS se conserva sin inventar ni modificar."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-010",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=["F", "M"],
            fuente_resultados=FuenteResultados.RESULTADOS_REGISTRADOS,
            valor_resultados="Se alcanzaron los objetivos de formación.",
        )
        assert dto.fuente_resultados == FuenteResultados.RESULTADOS_REGISTRADOS
        assert dto.descripcion_logros == "Se alcanzaron los objetivos de formación."

    def test_11_objetivo_general_no_es_logro_sin_politica(self):
        """Test 11: OBJETIVO_GENERAL sin valor suministrado produce vacio."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-011",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=[],
            fuente_resultados=FuenteResultados.OBJETIVO_GENERAL,
            valor_resultados=None,
        )
        assert dto.descripcion_logros == ""
        assert dto.fuente_resultados == FuenteResultados.OBJETIVO_GENERAL

    def test_12_justificacion_no_es_logro_sin_politica(self):
        """Test 12: JUSTIFICACION_ESTRATEGICA sin valor suministrado produce vacio."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-012",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=[],
            fuente_resultados=FuenteResultados.JUSTIFICACION_ESTRATEGICA,
            valor_resultados=None,
        )
        assert dto.descripcion_logros == ""
        assert dto.fuente_resultados == FuenteResultados.JUSTIFICACION_ESTRATEGICA

    def test_13_observacion_calidad_logros_vacios(self):
        """Test 13: observaciones_calidad contiene aviso de columna sin fuente."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-013",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=[],
            fuente_resultados=FuenteResultados.VACIO,
        )
        assert any("logros" in obs.lower() or "descripción" in obs.lower() for obs in dto.observaciones_calidad)


# ===========================================================================
# GRUPO 3: CIFRAS
# ===========================================================================


class TestCifras:
    """Tests 14–18: Politica explicita de fuente de cifras."""

    def test_14_cifras_declarado_permanece_declarado(self):
        """Test 14: DECLARADO permanece DECLARADO en el DTO."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-014",
            nombre_actividad="Capacitación",
            fuente_cifras=FuenteCifras.DECLARADO,
            participantes_sexos=["F", "M"],
        )
        assert dto.fuente_cifras == FuenteCifras.DECLARADO
        assert "Declarada" in dto.etiqueta_fuente_cifras

    def test_15_cifras_nominal_permanece_nominal(self):
        """Test 15: NOMINAL permanece NOMINAL en el DTO."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-015",
            nombre_actividad="Charla",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=["F"],
        )
        assert dto.fuente_cifras == FuenteCifras.NOMINAL
        assert "Efectiva" in dto.etiqueta_fuente_cifras or "Registrada" in dto.etiqueta_fuente_cifras

    def test_16_nominal_nunca_etiquetado_como_declarado(self):
        """Test 16: NOMINAL nunca se etiqueta como Declarado."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-016",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=["M", "F"],
        )
        assert "Declarada" not in dto.etiqueta_fuente_cifras

    def test_17_no_existe_fallback_silencioso(self):
        """Test 17: No existe fallback silencioso entre DECLARADO y NOMINAL."""
        dto_n = WordACL.adaptar_actividad(
            id_actividad="act-017a",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=[],
        )
        dto_d = WordACL.adaptar_actividad(
            id_actividad="act-017b",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.DECLARADO,
            participantes_sexos=[],
        )
        assert dto_n.fuente_cifras != dto_d.fuente_cifras
        assert dto_n.fuente_cifras == FuenteCifras.NOMINAL
        assert dto_d.fuente_cifras == FuenteCifras.DECLARADO

    def test_18_etiqueta_fuente_diferenciada(self):
        """Test 18: Las etiquetas de NOMINAL y DECLARADO son distintas."""
        dto_n = WordACL.adaptar_actividad(
            id_actividad="act-018a",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=[],
        )
        dto_d = WordACL.adaptar_actividad(
            id_actividad="act-018b",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.DECLARADO,
            participantes_sexos=[],
        )
        assert dto_n.etiqueta_fuente_cifras != dto_d.etiqueta_fuente_cifras


# ===========================================================================
# GRUPO 4: REVISION
# ===========================================================================


class TestRevision:
    """Tests 19–24: Politica de presentacion de revision Word."""

    def test_19_bloqueado_siempre_excluido(self):
        """Test 19: Participante BLOQUEADO siempre excluido."""
        class MockParticipacion:
            def __init__(self, estado, id_pers):
                self.estado_operativo = estado
                self.id_persona = id_pers
                self.requiere_revision = 0

        class MockPersona:
            def __init__(self, sexo):
                self.sexo_normalizado = sexo

        p_bloqueado = MockParticipacion("BLOQUEADO", "p1")
        p_valido = MockParticipacion("CONFIRMADO", "p2")
        personas = {"p1": MockPersona("F"), "p2": MockPersona("M")}

        dto = WordACL.adaptar_actividad_para_informe_semanal(
            actividad={"id": "act-019", "nombre": "Actividad"},
            participaciones=[p_bloqueado, p_valido],
            personas=personas,
            evidencias_vinculadas=[],
            politica_revision=PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
            fuente_cifras=FuenteCifras.NOMINAL,
        )
        assert dto.total_participantes == 1
        assert dto.total_varones == 1
        assert dto.total_mujeres == 0

    def test_20_bloqueado_excluido_independientemente_de_politica(self):
        """Test 20: Configurar PRESENTAR_CON_OBSERVACION no incluye a BLOQUEADO."""
        class MockParticipacion:
            def __init__(self, estado, id_pers):
                self.estado_operativo = estado
                self.id_persona = id_pers
                self.requiere_revision = 0

        class MockPersona:
            def __init__(self, sexo):
                self.sexo_normalizado = sexo

        p_bloqueado = MockParticipacion("BLOQUEADO", "p1")
        personas = {"p1": MockPersona("F")}

        dto = WordACL.adaptar_actividad_para_informe_semanal(
            actividad={"id": "act-020", "nombre": "Actividad"},
            participaciones=[p_bloqueado],
            personas=personas,
            evidencias_vinculadas=[],
            politica_revision=PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
            fuente_cifras=FuenteCifras.NOMINAL,
        )
        assert dto.total_participantes == 0
        assert dto.total_mujeres == 0

    def test_21_en_revision_respeta_politica_presentar(self):
        """Test 21: PRESENTAR_CON_OBSERVACION incluye EN_REVISION en cifras."""
        dto = WordACL.adaptar_actividad(
            id_actividad="act-021",
            nombre_actividad="Taller",
            fuente_cifras=FuenteCifras.NOMINAL,
            participantes_sexos=["F", "M"],
            politica_revision=PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
            participantes_en_revision_count=1,
        )
        assert dto.total_participantes == 2
        assert len(dto.observaciones_revision) > 0
        assert "EN_REVISION" in dto.observaciones_revision[0]

    def test_22_en_revision_respeta_politica_excluir(self):
        """Test 22: EXCLUIR_DE_PRESENTACION excluye EN_REVISION de cifras."""
        class MockParticipacion:
            def __init__(self, estado, id_pers):
                self.estado_operativo = estado
                self.id_persona = id_pers
                self.requiere_revision = 1

        class MockPersona:
            def __init__(self, sexo):
                self.sexo_normalizado = sexo

        p_rev = MockParticipacion("EN_REVISION", "p1")
        personas = {"p1": MockPersona("F")}

        dto = WordACL.adaptar_actividad_para_informe_semanal(
            actividad={"id": "act-022", "nombre": "Actividad"},
            participaciones=[p_rev],
            personas=personas,
            evidencias_vinculadas=[],
            politica_revision=PoliticaPresentacionRevisionWord.EXCLUIR_DE_PRESENTACION,
            fuente_cifras=FuenteCifras.NOMINAL,
        )
        assert dto.total_participantes == 0
        assert any("excluidos" in obs.lower() for obs in dto.observaciones_revision)

    def test_23_politica_word_independiente_de_excel(self):
        """Test 23: PoliticaPresentacionRevisionWord es tipo distinto de PoliticaExportacionRevision."""
        assert PoliticaPresentacionRevisionWord is not PoliticaExportacionRevision
        valores_word = {e.value for e in PoliticaPresentacionRevisionWord}
        valores_excel = {e.value for e in PoliticaExportacionRevision}
        assert valores_word.isdisjoint(valores_excel)

    def test_24_politica_word_no_hereda_de_excel(self):
        """Test 24: No existe relacion de herencia entre las politicas."""
        assert not issubclass(PoliticaPresentacionRevisionWord, PoliticaExportacionRevision)
        assert not issubclass(PoliticaExportacionRevision, PoliticaPresentacionRevisionWord)


# ===========================================================================
# GRUPO 5: EVIDENCIAS
# ===========================================================================


class TestEvidencias:
    """Tests 25–28: Adaptacion y custodia de evidencias."""

    def test_25_evidencia_ruta_relativa_se_conserva(self):
        """Test 25: ruta_relativa_original conserva el valor del SSOT exactamente."""
        dto = WordACL.adaptar_evidencia(
            id_evidencia="ev-025",
            id_actividad="act-025",
            titulo="Foto",
            tipo_evidencia="FOTO",
            ruta_relativa="fotos/ev_25.jpg",
        )
        assert dto.ruta_relativa == "fotos/ev_25.jpg"
        assert dto.ruta_relativa_original == "fotos/ev_25.jpg"

    def test_26_evidencia_base_configurable(self, tmp_path):
        """Test 26: La resolucion usa base configurable, no hard-codeada."""
        evidencia_dir = tmp_path / "boveda"
        evidencia_dir.mkdir()
        archivo = evidencia_dir / "taller.jpg"
        archivo.write_bytes(b"test_bytes")

        dto = WordACL.adaptar_evidencia(
            id_evidencia="ev-026",
            id_actividad="act-026",
            titulo="Foto",
            tipo_evidencia="FOTO",
            ruta_relativa="taller.jpg",
            evidencias_base_dir=str(evidencia_dir),
        )
        assert dto.existe_fisicamente is True
        assert dto.estado_disponibilidad == "VINCULADO"
        assert dto.ruta_absoluta_resuelta == str(archivo)

    def test_27_evidencia_inexistente_no_se_inventa(self, tmp_path):
        """Test 27: Archivo inexistente -> ruta_absoluta_resuelta = None, NO_DISPONIBLE."""
        base_dir = str(tmp_path / "boveda_vacia")
        dto = WordACL.adaptar_evidencia(
            id_evidencia="ev-027",
            id_actividad="act-027",
            titulo="Foto Inexistente",
            tipo_evidencia="FOTO",
            ruta_relativa="no_existe.jpg",
            evidencias_base_dir=base_dir,
        )
        assert dto.existe_fisicamente is False
        assert dto.estado_disponibilidad == "NO_DISPONIBLE"
        assert dto.ruta_absoluta_resuelta is None

    def test_28_evidencia_binarios_no_en_dto(self):
        """Test 28: WordEvidenciaItemDTO no contiene bytes ni binarios."""
        dto = WordACL.adaptar_evidencia(
            id_evidencia="ev-028",
            id_actividad="act-028",
            titulo="Documento",
            tipo_evidencia="DOCUMENTO",
            hash_sha256="hash123",
        )
        for key, value in dto.model_dump().items():
            assert not isinstance(value, (bytes, bytearray)), f"Campo {key} contiene binarios."


# ===========================================================================
# GRUPO 6: ARQUITECTURA
# ===========================================================================


class TestArquitectura:
    """Tests 29–35: Restricciones arquitectonicas de la capa WordACL."""

    _MODULOS = ["adapters.py", "policies.py", "dtos.py", "__init__.py"]

    def _source_de(self, archivo: str) -> str:
        base = Path("c:/Users/LENOVO X1 YOGA/OneDrive/Desktop/AUTOMATIZACION PROFE KENIA/app/application/word_acl")
        return (base / archivo).read_text(encoding="utf-8")

    def test_29_word_acl_no_importa_sqlite3(self):
        """Test 29: Ningun modulo importa sqlite3."""
        for archivo in self._MODULOS:
            source = self._source_de(archivo)
            assert "import sqlite3" not in source
            assert "sqlite3" not in source

    def test_30_word_acl_no_importa_openpyxl(self):
        """Test 30: Ningun modulo importa openpyxl."""
        for archivo in self._MODULOS:
            source = self._source_de(archivo)
            assert "openpyxl" not in source

    def test_31_word_acl_no_importa_docx(self):
        """Test 31: Ningun modulo importa docx / python-docx."""
        for archivo in self._MODULOS:
            source = self._source_de(archivo)
            assert "import docx" not in source
            assert "from docx" not in source

    def test_32_word_acl_no_importa_customtkinter(self):
        """Test 32: Ningun modulo importa customtkinter."""
        for archivo in self._MODULOS:
            source = self._source_de(archivo)
            assert "customtkinter" not in source

    def test_33_word_acl_no_implementa_statistics_engine(self):
        """Test 33: WordACL no instancia ni implementa calculos estadisticos."""
        source = self._source_de("adapters.py")
        assert "StatisticsEngine" not in source
        for palabra in ["media", "mediana", "desviacion", "varianza", "percentil"]:
            assert palabra not in source.lower()

    def test_34_word_acl_no_implementa_routing(self):
        """Test 34: WordACL no implementa logica de router."""
        source = self._source_de("adapters.py")
        assert "MatrizDestino" not in source
        assert "ParticipantRouter" not in source

    def test_35_word_acl_no_implementa_identity_resolution(self):
        """Test 35: WordACL no resuelve identidades."""
        source = self._source_de("adapters.py")
        assert "IdentityResolver" not in source
        assert "resolver_identidad" not in source.lower()


# ===========================================================================
# GRUPO 7: INTEGRIDAD
# ===========================================================================


class TestIntegridad:
    """Tests 36–39: Integridad de DTOs y ausencia de mutaciones."""

    def test_36_dto_no_muta_entidad_original(self):
        """Test 36: Los DTOs son frozen; intentar mutarlos lanza excepcion."""
        dto = WordEstamentoItemDTO(
            estamento_tipo="ESTUDIANTE",
            denominacion_visible="Estudiantes",
            mujeres=3,
            varones=2,
            sin_sexo_disponible=0,
            total_participantes=5,
            orden_presentacion=1,
        )
        with pytest.raises(Exception):
            dto.mujeres = 99

        assert dto.mujeres == 3

    def test_37_none_se_conserva(self):
        """Test 37: None se conserva sin imputacion silenciosa."""
        dto_ev = WordACL.adaptar_evidencia(
            id_evidencia="ev-037",
            id_actividad="act-037",
            titulo="Sin ruta",
            tipo_evidencia="FOTO",
            ruta_relativa=None,
            hash_sha256=None,
        )
        assert dto_ev.ruta_relativa is None
        assert dto_ev.hash_sha256 is None
        assert dto_ev.existe_fisicamente is None

    def test_38_sin_escritura_sqlite(self):
        """Test 38: WordACL no contiene instrucciones SQL INSERT/UPDATE/DELETE."""
        ruta = Path("c:/Users/LENOVO X1 YOGA/OneDrive/Desktop/AUTOMATIZACION PROFE KENIA/app/application/word_acl/adapters.py")
        source = ruta.read_text(encoding="utf-8")
        assert "INSERT " not in source.upper()
        assert "UPDATE " not in source.upper()
        assert "DELETE " not in source.upper()

    def test_39_sin_modificacion_templates(self):
        """Test 39: WordACL no importa ni modifica templates."""
        base = Path("c:/Users/LENOVO X1 YOGA/OneDrive/Desktop/AUTOMATIZACION PROFE KENIA/app/application/word_acl")
        for archivo in ["adapters.py", "policies.py", "dtos.py", "__init__.py"]:
            source = (base / archivo).read_text(encoding="utf-8")
            assert "templates" not in source.lower() or "# templates" in source.lower()


# ===========================================================================
# GRUPO 8: INTEGRACION Y CONTRATOS PATRIMONIALES
# ===========================================================================


class TestIntegracionYContratos:
    """Tests 40–47: Adaptacion hacia contratos patrimoniales y dataset semanal."""

    def test_40_construir_protagonista_institucional_sin_null(self):
        """Test 40: Adapta hacia ProtagonistaEstamentoInstitucional sin nulls."""
        item = WordEstamentoItemDTO(
            estamento_tipo="ESTUDIANTE",
            denominacion_visible="Estudiantes",
            mujeres=10,
            varones=5,
            sin_sexo_disponible=0,
            total_participantes=15,
            orden_presentacion=1,
        )
        protagonista = WordACL.construir_protagonista_institucional(item)
        assert isinstance(protagonista, ProtagonistaEstamentoInstitucional)
        assert protagonista.conteo_presentacion.mujeres == 10
        assert protagonista.conteo_presentacion.varones == 5
        assert protagonista.conteo_presentacion.total == 15

    def test_41_construir_protagonista_institucional_con_null_no_rompe_validador(self):
        """Test 41: sin_sexo_disponible > 0 no viola validador estricto patrimonial."""
        item = WordEstamentoItemDTO(
            estamento_tipo="ESTUDIANTE",
            denominacion_visible="Estudiantes",
            mujeres=10,
            varones=5,
            sin_sexo_disponible=3,
            total_participantes=18,
            orden_presentacion=1,
        )
        # No debe lanzar ValueError de ConteoSexoInstitucional
        protagonista = WordACL.construir_protagonista_institucional(item)
        assert isinstance(protagonista, ProtagonistaEstamentoInstitucional)
        assert protagonista.conteo_presentacion.mujeres == 10
        assert protagonista.conteo_presentacion.varones == 5
        assert protagonista.conteo_presentacion.total == 15  # 10 + 5 (excluye NULL para satisfacer contrato patrimonial)

    def test_42_dataset_agrega_totales_correctamente(self):
        """Test 42: WordWeeklyReportDataset suma correctamente todas las actividades."""
        act1 = WordACL.adaptar_actividad("a1", "Act 1", FuenteCifras.NOMINAL, ["F", "F", "M"])
        act2 = WordACL.adaptar_actividad("a2", "Act 2", FuenteCifras.NOMINAL, ["M", None, "F"])
        act3 = WordACL.adaptar_actividad("a3", "Act 3", FuenteCifras.NOMINAL, ["F"])

        dataset = WordACL.adaptar_para_informe_semanal(
            departamento_responsable="Extensión",
            mes_planificado="Septiembre",
            semana="3",
            actividades=[act1, act2, act3],
        )
        assert dataset.gran_total_mujeres == 4
        assert dataset.gran_total_varones == 2
        assert dataset.gran_total_sin_sexo == 1
        assert dataset.gran_total_participantes == 7
        assert dataset.gran_total_actividades == 3

    def test_43_dataset_registra_observacion_sin_sexo(self):
        """Test 43: Se registran observaciones globales de calidad por sin_sexo."""
        act = WordACL.adaptar_actividad("a1", "Act 1", FuenteCifras.NOMINAL, ["F", None])
        dataset = WordACL.adaptar_para_informe_semanal(
            departamento_responsable="Extensión",
            mes_planificado="Septiembre",
            semana="3",
            actividades=[act],
        )
        assert any("sin sexo disponible" in obs.lower() for obs in dataset.observaciones_calidad)

    def test_44_dataset_registra_observacion_logros_vacios(self):
        """Test 44: Se registran observaciones globales de calidad por logros vacios."""
        act = WordACL.adaptar_actividad(
            "a1", "Act 1", FuenteCifras.NOMINAL, ["F"], fuente_resultados=FuenteResultados.VACIO
        )
        dataset = WordACL.adaptar_para_informe_semanal(
            departamento_responsable="Extensión",
            mes_planificado="Septiembre",
            semana="3",
            actividades=[act],
        )
        assert any("logros" in obs.lower() or "descripción" in obs.lower() for obs in dataset.observaciones_calidad)

    def test_45_dataset_id_informe_semanal_es_none_por_defecto(self):
        """Test 45: id_informe_semanal es None por defecto (no escritura en SQLite)."""
        dataset = WordACL.adaptar_para_informe_semanal(
            departamento_responsable="Extensión",
            mes_planificado="Septiembre",
            semana="3",
            actividades=[],
        )
        assert dataset.id_informe_semanal is None

    def test_46_dataset_politica_revision_es_independiente_de_excel(self):
        """Test 46: Politica en dataset es de tipo Word, no Excel."""
        dataset = WordACL.adaptar_para_informe_semanal(
            departamento_responsable="Extensión",
            mes_planificado="Septiembre",
            semana="3",
            actividades=[],
            politica_revision=PoliticaPresentacionRevisionWord.PRESENTAR_CON_OBSERVACION,
        )
        assert isinstance(dataset.politica_revision_aplicada, PoliticaPresentacionRevisionWord)
        assert not isinstance(dataset.politica_revision_aplicada, PoliticaExportacionRevision)

    def test_47_invariante_global_siempre_se_cumple(self):
        """Test 47: La invariante global total = M + V + SinSexo siempre se cumple."""
        actividades = [
            WordACL.adaptar_actividad("a1", "Act 1", FuenteCifras.NOMINAL, ["F", "F", "M", None]),
            WordACL.adaptar_actividad("a2", "Act 2", FuenteCifras.NOMINAL, ["M", "M"]),
            WordACL.adaptar_actividad("a3", "Act 3", FuenteCifras.NOMINAL, [None, None]),
        ]
        dataset = WordACL.adaptar_para_informe_semanal(
            departamento_responsable="Extensión",
            mes_planificado="Septiembre",
            semana="4",
            actividades=actividades,
        )
        assert dataset.gran_total_participantes == (
            dataset.gran_total_mujeres + dataset.gran_total_varones + dataset.gran_total_sin_sexo
        )
