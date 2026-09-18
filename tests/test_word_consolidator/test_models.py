"""
tests.test_word_consolidator.test_models

Pruebas unitarias para los modelos de datos del generador Word consolidado (Fase 14.2).
Valida creación, tipado, inmutabilidad, consistencia aritmética, rechazo de datos inválidos
y compatibilidad con los modelos existentes de app.statistics.models.
"""

from datetime import date
import pytest
from pydantic import ValidationError

from app.word_consolidator.models import (
    TipoPeriodo,
    EstadoDiscrepancia,
    PeriodoConsolidacion,
    DiscrepanciaItem,
    RegistroFuenteArchivo,
    MetadatosInstitucionales,
    DesgloseEstamentoWord,
    FilaActividadWord,
    ReporteAuditoriaWord,
    ContextoConsolidadoDocx,
)
from app.statistics.models import (
    EstadisticaGlobal,
    DesgloseSexo,
    EstadisticaCalidad,
    MetricaCalidadItem,
    DistribucionEdades,
)


class TestPeriodoConsolidacion:
    """Pruebas para el modelo PeriodoConsolidacion."""

    def test_01_creacion_valida_periodo_semanal(self):
        p = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            fecha_inicio=date(2026, 9, 1),
            fecha_fin=date(2026, 9, 7),
            etiqueta="Septiembre 2026 - Semana 1"
        )
        assert p.tipo_periodo == TipoPeriodo.SEMANA
        assert p.anio == 2026
        assert p.mes == 9
        assert p.semana == 1
        assert p.etiqueta == "Septiembre 2026 - Semana 1"

    def test_02_inmutabilidad_periodo(self):
        p = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026"
        )
        with pytest.raises(ValidationError):
            p.anio = 2027  # frozen=True

    def test_03_rechazo_anio_o_mes_invalido(self):
        with pytest.raises(ValidationError):
            PeriodoConsolidacion(
                tipo_periodo=TipoPeriodo.MES,
                anio=1990,  # < 2000
                etiqueta="Año Inválido"
            )
        with pytest.raises(ValidationError):
            PeriodoConsolidacion(
                tipo_periodo=TipoPeriodo.MES,
                anio=2026,
                mes=13,  # > 12
                etiqueta="Mes Inválido"
            )

    def test_04_rechazo_etiqueta_vacia(self):
        with pytest.raises(ValidationError):
            PeriodoConsolidacion(
                tipo_periodo=TipoPeriodo.MES,
                anio=2026,
                etiqueta="   "
            )


class TestDiscrepanciaItem:
    """Pruebas para el modelo DiscrepanciaItem y la Regla de Discrepancias."""

    def test_01_creacion_valida_discrepancia_septiembre(self):
        # Caso real de Septiembre 2026: 15 reportados en M1 vs 17 nominales en M2 -> delta = -2
        disc = DiscrepanciaItem(
            id_actividad="act-uuid-001",
            nombre_actividad="Capacitación en Logotipos e IA",
            estamento="Estudiantes",
            fuente_m1="Matriz 1: Consolidado de Actividades",
            fuentes_nominales=["Matriz 2: Estudiantes"],
            valor_m1=15,
            valor_nominal=17,
            diferencia=-2,
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
            descripcion="El informe preliminar indicó 15 estudiantes pero la lista nominal contiene 17.",
            trazabilidad={"columna_m1": "AA+AB", "filas_m2": [2, 18]}
        )
        assert disc.valor_m1 == 15
        assert disc.valor_nominal == 17
        assert disc.diferencia == -2
        assert disc.estado == EstadoDiscrepancia.REQUIERE_REVISION

    def test_02_rechazo_diferencia_aritmetica_inconsistente(self):
        with pytest.raises(ValidationError, match="Inconsistencia en diferencia aritmética"):
            DiscrepanciaItem(
                id_actividad="act-uuid-001",
                nombre_actividad="Actividad Prueba",
                estamento="Docentes",
                valor_m1=10,
                valor_nominal=8,
                diferencia=5,  # Incorrecto: 10 - 8 = 2 != 5
                descripcion="Diferencia errónea"
            )

    def test_03_inmutabilidad_discrepancia(self):
        disc = DiscrepanciaItem(
            id_actividad="act-uuid-001",
            nombre_actividad="Actividad",
            estamento="Estudiantes",
            valor_m1=10,
            valor_nominal=10,
            diferencia=0,
            estado=EstadoDiscrepancia.CONCORDANTE,
            descripcion="Concordante"
        )
        with pytest.raises(ValidationError):
            disc.valor_m1 = 12  # frozen=True


class TestRegistroFuenteArchivo:
    """Pruebas para el modelo RegistroFuenteArchivo de auditoría."""

    def test_01_creacion_valida_con_hash_sha256(self):
        h = "fdaebcb36cbcfaf7189cd03056e961bda1e1d8d1093c501bd4fa3951618ad2ad"
        reg = RegistroFuenteArchivo(
            codigo_matriz="M1",
            nombre_archivo="Matriz_1_Consolidado_Actividades.xlsx",
            ruta_archivo="templates/Matriz_1_Consolidado_Actividades.xlsx",
            hash_sha256=h,
            total_filas_leidas=1,
            filas_en_periodo=1
        )
        assert reg.codigo_matriz == "M1"
        assert len(reg.hash_sha256) == 64

    def test_02_rechazo_hash_incompleto(self):
        with pytest.raises(ValidationError):
            RegistroFuenteArchivo(
                codigo_matriz="M1",
                nombre_archivo="archivo.xlsx",
                ruta_archivo="/path",
                hash_sha256="hash_corto"  # min_length=64
            )


class TestDesgloseEstamentoWord:
    """Pruebas para DesgloseEstamentoWord y verificación semántica de género."""

    def test_01_creacion_valida_con_mujeres_y_varones(self):
        est = DesgloseEstamentoWord(
            tipo_protagonistas="2. Estudiantes",
            mujeres=11,  # Columna 'M'
            varones=6,   # Columna 'V'
            total=17
        )
        assert est.mujeres == 11
        assert est.varones == 6
        assert est.total == 17

    def test_02_rechazo_suma_invalida(self):
        with pytest.raises(ValidationError, match="no coincide con la suma de mujeres"):
            DesgloseEstamentoWord(
                tipo_protagonistas="2. Estudiantes",
                mujeres=10,
                varones=5,
                total=20  # Incorrecto: 10 + 5 = 15 != 20
            )


class TestFilaActividadWord:
    """Pruebas para FilaActividadWord y sincronización de subtotales."""

    def test_01_sincronizacion_automatica_de_totales(self):
        sub1 = DesgloseEstamentoWord(tipo_protagonistas="2. Estudiantes", mujeres=11, varones=6, total=17)
        sub2 = DesgloseEstamentoWord(tipo_protagonistas="3. Personal administrativo", mujeres=1, varones=0, total=1)

        fila = FilaActividadWord(
            id_actividad="act-1",
            nombre_actividad="Taller de IA",
            sede="Bilwi",
            desglose_estamentos=[sub1, sub2]
        )
        # Debe sincronizar automáticamente:
        assert fila.total_mujeres == 12
        assert fila.total_varones == 6
        assert fila.gran_total == 18


class TestContextoConsolidadoDocx:
    """Pruebas para el modelo agregador ContextoConsolidadoDocx."""

    @pytest.fixture
    def estadistica_global_fixture(self) -> EstadisticaGlobal:
        """Crea una instancia válida de EstadisticaGlobal de app.statistics.models."""
        ds = DesgloseSexo(femenino=12, masculino=6, total=18, porcentaje_femenino=66.67, porcentaje_masculino=33.33)
        item_cal = MetricaCalidadItem(numerador=18, denominador=18, porcentaje=100.0, definicion="Disponibilidad 100%")
        cal = EstadisticaCalidad(
            total_registros=18,
            registros_aptos=18,
            cedula_disponible=item_cal,
            sexo_confirmado=item_cal,
            edad_disponible=item_cal,
            carrera_disponible=item_cal
        )
        return EstadisticaGlobal(
            total_actividades=1,
            total_asistencias=18,
            total_personas_unicas=18,
            desglose_sexo_global=ds,
            distribucion_edades=DistribucionEdades(),
            calidad_datos=cal,
            invariante_estadistica_valida=True
        )

    def test_01_creacion_completa_contexto(self, estadistica_global_fixture):
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.SEMANA,
            anio=2026,
            mes=9,
            semana=1,
            etiqueta="Septiembre 2026 - Semana 1"
        )
        auditoria = ReporteAuditoriaWord(
            timestamp_generacion="2026-09-13T00:00:00Z",
            total_actividades=1,
            total_participaciones_brutas=18,
            total_personas_unicas=18,
            total_discrepancias=0
        )
        ctx = ContextoConsolidadoDocx(
            periodo=periodo,
            estadisticas_globales=estadistica_global_fixture,
            auditoria=auditoria
        )
        assert ctx.institucion.universidad == "Bluefields Indian & Caribbean University (BICU)"
        assert ctx.periodo.etiqueta == "Septiembre 2026 - Semana 1"
        assert ctx.estadisticas_globales.total_asistencias == 18
        assert not ctx.tiene_discrepancias

    def test_02_deteccion_discrepancias_activas(self, estadistica_global_fixture):
        periodo = PeriodoConsolidacion(
            tipo_periodo=TipoPeriodo.MES,
            anio=2026,
            mes=9,
            etiqueta="Septiembre 2026"
        )
        disc = DiscrepanciaItem(
            id_actividad="act-1",
            nombre_actividad="Actividad",
            estamento="Estudiantes",
            valor_m1=15,
            valor_nominal=17,
            diferencia=-2,
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
            descripcion="Diferencia de 2 estudiantes"
        )
        auditoria = ReporteAuditoriaWord(
            timestamp_generacion="2026-09-13T00:00:00Z",
            total_actividades=1,
            total_participaciones_brutas=18,
            total_personas_unicas=18,
            total_discrepancias=1,
            discrepancias=[disc]
        )
        ctx = ContextoConsolidadoDocx(
            periodo=periodo,
            estadisticas_globales=estadistica_global_fixture,
            auditoria=auditoria,
            discrepancias_globales=[disc]
        )
        assert ctx.tiene_discrepancias is True
        assert len(ctx.discrepancias_globales) == 1
        assert ctx.discrepancias_globales[0].diferencia == -2
