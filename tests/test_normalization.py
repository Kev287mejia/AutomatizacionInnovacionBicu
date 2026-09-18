"""
tests/test_normalization.py

Pruebas unitarias para el módulo de normalización por fuente (Fase 3):
- Mapeo de sexo dependiente de fuente (Regla C-08).
- Detección de anomalías en identificadores (fecha en cédula, cédula vacía).
- Manejo estricto de edad y fecha de nacimiento (Regla de no invención).
- Preservación de 3 niveles de carrera y detección de abreviaturas/ambigüedades (Regla C-12).
- Categorías compuestas conservando categoría y área original (Regla C-03).
- Normalización básica de nombres.
"""

import pytest
from app.core.constants.participant_types import NivelValidacion, CategoriaParticipacion
from app.normalization.sex_normalizer import SexNormalizer
from app.normalization.identifier_normalizer import IdentifierNormalizer
from app.normalization.age_date_normalizer import AgeDateNormalizer
from app.normalization.career_normalizer import CareerNormalizer
from app.normalization.category_normalizer import CategoryNormalizer
from app.normalization.name_normalizer import NameNormalizer


class TestSexNormalizationBySource:
    """
    Pruebas del mapeo de sexo dependiente de fuente.
    Demuestra que nunca se aplica un reemplazo global M -> Masculino.
    """

    def test_m_en_word_se_interpreta_como_femenino_mujer(self):
        sexo_norm, val = SexNormalizer.normalizar("M", fuente="informe_word")
        assert sexo_norm == "FEMENINO"
        assert val is None

    def test_v_en_word_se_interpreta_como_masculino_varon(self):
        sexo_norm, val = SexNormalizer.normalizar("V", fuente="informe_word")
        assert sexo_norm == "MASCULINO"
        assert val is None

    def test_m_en_asistencia_se_interpreta_como_masculino(self):
        sexo_norm, val = SexNormalizer.normalizar("M", fuente="asistencia_fisica")
        assert sexo_norm == "MASCULINO"
        assert val is None

    def test_f_en_asistencia_se_interpreta_como_femenino(self):
        sexo_norm, val = SexNormalizer.normalizar("F", fuente="asistencia_fisica")
        assert sexo_norm == "FEMENINO"
        assert val is None

    def test_excel_oficial_codigos_uno_y_dos(self):
        sexo_1, _ = SexNormalizer.normalizar("1", fuente="excel_oficial")
        sexo_2, _ = SexNormalizer.normalizar("2", fuente="excel_oficial")
        assert sexo_1 == "FEMENINO"
        assert sexo_2 == "MASCULINO"

    def test_codigo_desconocido_emite_validacion_y_retorna_none(self):
        sexo_norm, val = SexNormalizer.normalizar("X", fuente="asistencia_fisica")
        assert sexo_norm is None
        assert val is not None
        assert val.nivel == NivelValidacion.WARNING
        assert val.codigo == "VAL_SEXO_INCOMPATIBLE"

    def test_sexo_vacio_emite_validacion_y_retorna_none(self):
        sexo_norm, val = SexNormalizer.normalizar(None, fuente="asistencia_fisica")
        assert sexo_norm is None
        assert val is not None
        assert val.codigo == "VAL_SEXO_AUSENTE"

    def test_impedir_reutilizacion_cruzada_de_catalogos_entre_fuentes(self):
        """Impide que una fuente reutilice accidentalmente códigos pertenecientes a otra fuente."""
        # 1. 'V' es válido en informe_word (Masculino), pero INCOMPATIBLE en asistencia_fisica
        norm_asist, val_asist = SexNormalizer.normalizar("V", fuente="asistencia_fisica")
        assert norm_asist is None
        assert val_asist is not None
        assert val_asist.codigo == "VAL_SEXO_INCOMPATIBLE"

        # 2. 'F' es válido en asistencia_fisica (Femenino), pero INCOMPATIBLE en informe_word (donde se usa 'M' para Mujer)
        norm_word, val_word = SexNormalizer.normalizar("F", fuente="informe_word")
        assert norm_word is None
        assert val_word is not None
        assert val_word.codigo == "VAL_SEXO_INCOMPATIBLE"

        # 3. '1' y '2' son exclusivos de excel_oficial, no deben operar en asistencia_fisica ni en informe_word
        norm_num_asist, val_num_asist = SexNormalizer.normalizar("1", fuente="asistencia_fisica")
        assert norm_num_asist is None
        assert val_num_asist is not None
        assert val_num_asist.codigo == "VAL_SEXO_INCOMPATIBLE"

        norm_num_word, val_num_word = SexNormalizer.normalizar("1", fuente="informe_word")
        assert norm_num_word is None
        assert val_num_word is not None
        assert val_num_word.codigo == "VAL_SEXO_INCOMPATIBLE"

        norm_num2_word, val_num2_word = SexNormalizer.normalizar("2", fuente="informe_word")
        assert norm_num2_word is None
        assert val_num2_word is not None
        assert val_num2_word.codigo == "VAL_SEXO_INCOMPATIBLE"

        # 4. 'M' y 'F' deben ser rechazados como códigos de excel_oficial (este usa 1 y 2)
        norm_m_excel, val_m_excel = SexNormalizer.normalizar("M", fuente="excel_oficial")
        assert norm_m_excel is None
        assert val_m_excel is not None
        assert val_m_excel.codigo == "VAL_SEXO_INCOMPATIBLE"

        norm_f_excel, val_f_excel = SexNormalizer.normalizar("F", fuente="excel_oficial")
        assert norm_f_excel is None
        assert val_f_excel is not None
        assert val_f_excel.codigo == "VAL_SEXO_INCOMPATIBLE"


class TestIdentifierNormalization:
    """Pruebas para normalización de cédula y detección de anomalías."""

    def test_fecha_en_campo_cedula_detecta_anomalia_y_retorna_none(self):
        """
        Caso: '20-04-2008' en columna Cédula.
        Debe producir:
        - cédula_normalizada = None
        - WARNING = posible fecha de nacimiento ubicada en campo cédula.
        - NO trasladar automáticamente a fecha de nacimiento.
        """
        cedula_original = "20-04-2008"
        cedula_norm, val = IdentifierNormalizer.normalizar_cedula(
            valor_original=cedula_original,
            fuente="asistencia_fisica"
        )
        assert cedula_norm is None
        assert val is not None
        assert val.nivel == NivelValidacion.REVISION
        assert val.codigo == "VAL_CEDULA_FECHA"
        assert "20-04-2008" in val.mensaje
        assert "No se traslada automáticamente" in val.mensaje

    def test_cedula_vacia_retorna_none_y_alerta_sin_inventar_datos(self):
        cedula_norm, val = IdentifierNormalizer.normalizar_cedula(
            valor_original=None,
            fuente="asistencia_fisica"
        )
        assert cedula_norm is None
        assert val is not None
        assert val.codigo == "VAL_CEDULA_VACIA"

        cedula_guion, val2 = IdentifierNormalizer.normalizar_cedula(
            valor_original="-",
            fuente="asistencia_fisica"
        )
        assert cedula_guion is None
        assert val2.codigo == "VAL_CEDULA_VACIA"

    def test_cedula_valida_formatea_correctamente(self):
        cedula_valida = "601-200408-1002A"
        cedula_norm, val = IdentifierNormalizer.normalizar_cedula(cedula_valida)
        assert cedula_norm == "601-200408-1002A"
        assert val is None

    def test_cedula_sin_guiones_se_estandariza(self):
        cedula_sin_guion = "6012004081002a"
        cedula_norm, val = IdentifierNormalizer.normalizar_cedula(cedula_sin_guion)
        assert cedula_norm == "601-200408-1002A"
        assert val is None


class TestAgeAndDateNormalization:
    """Pruebas de edad y fecha de nacimiento."""

    def test_si_fuente_solo_da_edad_conserva_edad_y_fecha_queda_none(self):
        edad_norm, fecha_norm, val = AgeDateNormalizer.normalizar(
            edad_original=20,
            fecha_nacimiento_original=None
        )
        assert edad_norm == 20
        assert fecha_norm is None
        assert val is None

    def test_fecha_en_campo_edad_genera_alerta_y_no_asume_edad(self):
        edad_norm, fecha_norm, val = AgeDateNormalizer.normalizar(
            edad_original="15/05/2005"
        )
        assert edad_norm is None
        assert val is not None
        assert val.codigo == "VAL_EDAD_FECHA_ANOMALA"


class TestCareerNormalization:
    """Pruebas de carreras preservando los tres niveles."""

    def test_carreras_abreviadas_conservan_original_y_normalizada(self):
        carreras_probar = [
            ("contabilidad", "Contabilidad", None),
            ("Contabilidad", "Contabilidad", None),
            ("Lic Contabil.", "Lic. Contabilidad", "VAL_CARRERA_ABREVIADA"),
            ("Lic. Conta", "Lic. Contabilidad", "VAL_CARRERA_ABREVIADA"),
            ("Ing. sistc.", "Ing. Sistemas", "VAL_CARRERA_ABREVIADA"),
            ("Sistema", "Sistemas", "VAL_CARRERA_ABREVIADA"),
        ]

        for original, esperado_norm, codigo_esperado in carreras_probar:
            norm, oficial, val = CareerNormalizer.normalizar(original)
            assert norm == esperado_norm
            # Regla de oro: carrera_oficial es None mientras no haya catálogo institucional confirmado
            assert oficial is None
            if codigo_esperado:
                assert val is not None
                assert val.codigo == codigo_esperado

    def test_carrera_ambigua_a_estudiantil(self):
        norm, oficial, val = CareerNormalizer.normalizar("A. estudiantil")
        assert norm == "A. Estudiantil"
        assert oficial is None
        assert val is not None
        assert val.codigo == "VAL_CARRERA_AMBIGUA"

    def test_carreras_casos_incompletos_y_no_determinables(self):
        """Evalúa abreviaturas genéricas, valores incompletos y carreras desconocidas sin inventar datos."""
        # 1. Valor incompleto / abreviatura genérica con punto
        norm_inc, oficial_inc, val_inc = CareerNormalizer.normalizar("Adm.")
        assert norm_inc == "Adm."
        assert oficial_inc is None
        assert val_inc is not None
        assert val_inc.codigo == "VAL_CARRERA_ABREVIADA"

        # 2. Valor corto posiblemente incompleto (len <= 4)
        norm_corto, oficial_corto, val_corto = CareerNormalizer.normalizar("Sist")
        assert norm_corto == "Sist"
        assert oficial_corto is None
        assert val_corto is not None
        assert val_corto.codigo == "VAL_CARRERA_ABREVIADA"

        # 3. Valor completo pero que no está en catálogo confirmado
        norm_no_cat, oficial_no_cat, val_no_cat = CareerNormalizer.normalizar("Biotecnología Marina")
        assert norm_no_cat == "Biotecnología Marina"
        assert oficial_no_cat is None  # Sin inventar catálogo oficial
        assert val_no_cat is None

        # 4. Valor vacío o nulo
        norm_vacio, oficial_vacio, val_vacio = CareerNormalizer.normalizar(None)
        assert norm_vacio is None
        assert oficial_vacio is None
        assert val_vacio is None


class TestCategoryNormalization:
    """Pruebas de categoría de participación y roles."""

    def test_no_docente_con_area_acces(self):
        cat_enum, inst_final, val = CategoryNormalizer.normalizar(
            categoria_original="No Docente",
            area_original="ACCES"
        )
        assert cat_enum == CategoriaParticipacion.NO_DOCENTE
        assert inst_final == "ADMINISTRATIVO / NO DOCENTE"
        assert val is None

    def test_no_utiliza_solo_el_area_para_inventar_categoria(self):
        cat_enum, inst_final, val = CategoryNormalizer.normalizar(
            categoria_original="",
            area_original="ACCES"
        )
        assert cat_enum == CategoriaParticipacion.DESCONOCIDO
        assert val is not None
        assert val.codigo == "VAL_CATEGORIA_AUSENTE"


class TestNameNormalization:
    """Pruebas de normalización de nombres."""

    def test_limpieza_espacios_y_separacion(self):
        nombre_norm, nombres, apellidos = NameNormalizer.normalizar("  JOHNNY   MELVIN  ")
        assert nombre_norm == "Johnny Melvin"
        assert nombres == "Johnny"
        assert apellidos == "Melvin"
