"""
tests.test_word_consolidator.test_institutional_models

Suite completa de pruebas unitarias para el Producto B:
Modelos documentales intermedios y Transformador del Informe Semanal Institucional BICU (Fase 16.3).

Verifica:
1. 12 Escenarios de la Fase 16.2.
2. Test A: Total inconsistente rechazado con ValidationError (no corrección silenciosa).
3. Test B: Total correcto válido (M + V == Total).
4. Test C: Informe sin actividades (N >= 0).
5. Test D: Inmutabilidad estricta (frozen=True en todos los modelos).
6. Test E: Transformación pura sin mutación de ResultadoConsolidacion.
7. Fixture del Caso Real Septiembre 2026 con 3 discrepancias conservadas.
"""

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import List

from pydantic import ValidationError
import pytest

from app.word_consolidator.document.institutional_models import (
    ActividadInstitucional,
    ConteoSexoInstitucional,
    DiscrepanciaActividadInstitucional,
    DiscrepanciaEstamento,
    EstadoEvidenciaEnum,
    InformeSemanalInstitucional,
    ItemEvidenciaInstitucional,
    ProtagonistaEstamentoInstitucional,
    SeccionEvidenciasActividad,
    TipoEstamentoInstitucional,
    TipoEvidenciaEnum,
    TrazabilidadActividad,
)
from app.word_consolidator.document.institutional_transformer import (
    InstitutionalReportTransformer,
)
from app.word_consolidator.engine.consolidation_engine import (
    ActividadConsolidada,
    ParticipacionConsolidada,
    ResultadoConsolidacion,
    TotalesM1,
    TotalesNominales,
)
from app.word_consolidator.models import (
    DiscrepanciaItem,
    EstadoDiscrepancia,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
    TipoPeriodo,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def periodo_septiembre():
    return PeriodoConsolidacion(
        tipo_periodo=TipoPeriodo.SEMANA,
        anio=2026,
        mes=9,
        semana=1,
        fecha_inicio=date(2026, 9, 1),
        fecha_fin=date(2026, 9, 7),
        etiqueta="Semana 1 - Septiembre 2026",
    )


@pytest.fixture
def actividad_caso_real_septiembre():
    """Actividad oficial representativa del caso real septiembre 2026."""
    tot_m1 = TotalesM1(
        mujeres=12,
        varones=6,
        total=18,
        estudiantes_m=5,
        estudiantes_f=10,
        docentes_m=1,
        docentes_f=0,
        administrativos_m=0,
        administrativos_f=2,
        colaboradores_m=0,
        colaboradores_f=0,
        protagonistas_m=0,
        protagonistas_f=0,
    )
    tot_nom = TotalesNominales(
        mujeres=12,
        varones=6,
        total=18,
        estudiantes=17,
        docentes=0,
        administrativos=1,
        no_docentes=0,
        colaboradores=0,
        beneficiarios=0,
        estudiantes_f=12,
        estudiantes_m=5,
        docentes_f=0,
        docentes_m=0,
        administrativos_f=0,
        administrativos_m=1,
        colaboradores_f=0,
        colaboradores_m=0,
        beneficiarios_f=0,
        beneficiarios_m=0,
    )

    discrepancias = [
        DiscrepanciaItem(
            id_actividad="act-real-001",
            nombre_actividad="BICU CUR Bilwi fortalece conocimientos en diseño de logotipos e IA",
            estamento="Estudiantes",
            fuente_m1="Matriz 1",
            fuentes_nominales=["Matriz 2"],
            valor_m1=15,
            valor_nominal=17,
            delta=2,
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
            descripcion="Estudiantes: Declarado=15 vs Nominal=17 (delta=+2)",
        ),
        DiscrepanciaItem(
            id_actividad="act-real-001",
            nombre_actividad="BICU CUR Bilwi fortalece conocimientos en diseño de logotipos e IA",
            estamento="Administrativos",
            fuente_m1="Matriz 1",
            fuentes_nominales=["Matriz 3"],
            valor_m1=2,
            valor_nominal=1,
            delta=-1,
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
            descripcion="Administrativos: Declarado=2 vs Nominal=1 (delta=-1)",
        ),
        DiscrepanciaItem(
            id_actividad="act-real-001",
            nombre_actividad="BICU CUR Bilwi fortalece conocimientos en diseño de logotipos e IA",
            estamento="Docentes",
            fuente_m1="Matriz 1",
            fuentes_nominales=["Matriz 3"],
            valor_m1=1,
            valor_nominal=0,
            delta=-1,
            estado=EstadoDiscrepancia.REQUIERE_REVISION,
            descripcion="Docentes: Declarado=1 vs Nominal=0 (delta=-1)",
        ),
    ]

    return ActividadConsolidada(
        id_actividad="act-real-001",
        clave_negocio=("BICU CUR Bilwi fortalece conocimientos", "Bilwi", "2026-09-03"),
        nombre_actividad="BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial",
        sede="Bilwi",
        departamento="RACCN",
        municipio="Puerto Cabezas",
        area_responsable="Innovación y Emprendimiento",
        programa="Innovación y Emprendimiento",
        eje="11.41.67",
        tipo_evento="Capacitación",
        resultados="Capacitación en diseño de logotipos e IA.",
        totales_m1=tot_m1,
        totales_nominales=tot_nom,
        total_asistencia_bruta=18,
        total_personas_unicas=18,
        discrepancias=discrepancias,
    )


@pytest.fixture
def consolidacion_caso_real(periodo_septiembre, actividad_caso_real_septiembre):
    fuentes = {
        "M1": RegistroFuenteArchivo(
            codigo_matriz="M1",
            nombre_archivo="Matriz_1.xlsx",
            ruta_archivo=str(Path("output/Matriz_1.xlsx").resolve()),
            hash_sha256="a" * 64,
            total_filas_leidas=1,
            filas_en_periodo=1,
        )
    }
    return ResultadoConsolidacion(
        periodo=periodo_septiembre,
        actividades=[actividad_caso_real_septiembre],
        total_actividades=1,
        total_asistencia_bruta=18,
        total_personas_unicas=18,
        total_recurrencia=0,
        tasa_recurrencia=0.0,
        fuentes=fuentes,
        discrepancias=actividad_caso_real_septiembre.discrepancias,
    )


# ============================================================================
# TESTS REQUERIDOS ESPECÍFICOS: A, B, C, D, E
# ============================================================================

class TestCorreccionesArquitectonicasFase16_3:
    """Verificación de las correcciones críticas requeridas para Fase 16.3."""

    def test_A_total_inconsistente_produce_validation_error_y_no_autocorrige(self):
        """Test A: Total inconsistente (M=10, V=5, Total=20) debe lanzar ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ConteoSexoInstitucional(mujeres=10, varones=5, total=20)
        err_msg = str(exc_info.value)
        assert "Inconsistencia en conteo de sexo" in err_msg
        assert "Total declarado (20)" in err_msg
        assert "suma de mujeres (10) + varones (5) = 15" in err_msg

    def test_B_total_correcto_es_valido(self):
        """Test B: Total exacto (M=10, V=5, Total=15) debe construirse válidamente."""
        conteo = ConteoSexoInstitucional(mujeres=10, varones=5, total=15)
        assert conteo.mujeres == 10
        assert conteo.varones == 5
        assert conteo.total == 15
        assert conteo.M == 10
        assert conteo.V == 5

    def test_C_informe_sin_actividades_es_valido_N_mayor_igual_cero(self, periodo_septiembre):
        """Test C: Cardinalidad N >= 0 permite InformeSemanalInstitucional con actividades=[]."""
        informe = InformeSemanalInstitucional(
            departamento_responsable="Dirección Académica",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[],
            observaciones="Sin actividades reportadas en la semana.",
        )
        assert informe.total_actividades == 0
        assert informe.total_mujeres == 0
        assert informe.total_varones == 0
        assert informe.total_participantes == 0
        assert not informe.tiene_discrepancias

    def test_D_inmutabilidad_estricta_rechaza_mutaciones(self, consolidacion_caso_real):
        """Test D: Intentar modificar atributos de informe, actividad o conteo debe fallar."""
        informe = InstitutionalReportTransformer.transformar(consolidacion_caso_real)
        actividad = informe.actividades[0]
        conteo = actividad.totales_actividad

        # 1. Modificar informe
        with pytest.raises(ValidationError):
            informe.departamento_responsable = "Otro Departamento"  # type: ignore

        with pytest.raises(ValidationError):
            informe.actividades = []  # type: ignore

        # 2. Modificar actividad
        with pytest.raises(ValidationError):
            actividad.nombre_actividad = "Nombre Alterado"  # type: ignore

        # 3. Modificar conteo
        with pytest.raises(ValidationError):
            conteo.total = 999  # type: ignore

    def test_E_transformacion_pura_sin_mutacion_en_resultado_consolidacion(self, consolidacion_caso_real):
        """Test E: Comparar ResultadoConsolidacion antes y después de transformar."""
        copia_previa = consolidacion_caso_real.model_dump()

        # Ejecutar transformación
        informe = InstitutionalReportTransformer.transformar(consolidacion_caso_real)
        assert informe is not None

        # Verificar que el objeto original no ha sufrido mutación alguna
        copia_posterior = consolidacion_caso_real.model_dump()
        assert copia_previa == copia_posterior


# ============================================================================
# TESTS DE LOS 12 ESCENARIOS DE DISEÑO (FASE 16.2)
# ============================================================================

class TestEscenariosInstitucionales:
    """Validación de los 12 escenarios funcionales y de modelado institucional."""

    def test_01_informe_una_actividad(self, consolidacion_caso_real):
        """Escenario 1: Informe con 1 sola actividad."""
        informe = InstitutionalReportTransformer.transformar(consolidacion_caso_real)
        assert informe.total_actividades == 1
        assert len(informe.actividades) == 1
        act = informe.actividades[0]
        assert act.numero_orden == 1
        assert act.sede == "Bilwi"
        assert act.departamento == "RACCN"
        assert act.municipio == "Puerto Cabezas"
        assert act.eje_vinculado == "11.41.67"

    def test_02_informe_multiples_actividades(self, periodo_septiembre, actividad_caso_real_septiembre):
        """Escenario 2: Informe con N actividades (N=3)."""
        act2 = actividad_caso_real_septiembre.model_copy(update={
            "id_actividad": "act-002",
            "nombre_actividad": "Segunda Actividad Institucional",
        })
        act3 = actividad_caso_real_septiembre.model_copy(update={
            "id_actividad": "act-003",
            "nombre_actividad": "Tercera Actividad Institucional",
        })

        consolidacion = ResultadoConsolidacion(
            periodo=periodo_septiembre,
            actividades=[actividad_caso_real_septiembre, act2, act3],
            total_actividades=3,
        )

        informe = InstitutionalReportTransformer.transformar(consolidacion)
        assert informe.total_actividades == 3
        assert [a.numero_orden for a in informe.actividades] == [1, 2, 3]
        assert informe.actividades[1].nombre_actividad == "Segunda Actividad Institucional"
        assert informe.actividades[2].nombre_actividad == "Tercera Actividad Institucional"

    def test_03_actividad_solo_estudiantes(self, periodo_septiembre):
        """Escenario 3: Actividad donde únicamente participaron estudiantes."""
        tot_nom = TotalesNominales(
            estudiantes=20,
            estudiantes_f=12,
            estudiantes_m=8,
            mujeres=12,
            varones=8,
            total=20,
        )
        act = ActividadConsolidada(
            id_actividad="act-est-only",
            clave_negocio=("Taller Estudiantes", "Bilwi", "2026-09-02"),
            nombre_actividad="Taller Exclusivo de Estudiantes",
            sede="Bilwi",
            totales_nominales=tot_nom,
        )
        consolidacion = ResultadoConsolidacion(periodo=periodo_septiembre, actividades=[act])

        informe = InstitutionalReportTransformer.transformar(consolidacion)
        protags = informe.actividades[0].protagonistas

        # Solo debe haber 1 fila en la tabla de estamentos (sin filas artificiales de 0)
        assert len(protags) == 1
        assert protags[0].estamento_tipo == TipoEstamentoInstitucional.ESTUDIANTES
        assert protags[0].conteo_presentacion.total == 20
        assert protags[0].conteo_presentacion.mujeres == 12
        assert protags[0].conteo_presentacion.varones == 8

    def test_04_actividad_estudiantes_y_administrativos(self, periodo_septiembre):
        """Escenario 4: Actividad con estudiantes y personal administrativo."""
        tot_nom = TotalesNominales(
            estudiantes=10,
            estudiantes_f=6,
            estudiantes_m=4,
            administrativos=2,
            administrativos_f=1,
            administrativos_m=1,
            mujeres=7,
            varones=5,
            total=12,
        )
        act = ActividadConsolidada(
            id_actividad="act-est-adm",
            clave_negocio=("Inducción", "Bluefields", "2026-09-04"),
            nombre_actividad="Inducción Institucional",
            sede="Bluefields",
            totales_nominales=tot_nom,
        )
        consolidacion = ResultadoConsolidacion(periodo=periodo_septiembre, actividades=[act])

        informe = InstitutionalReportTransformer.transformar(consolidacion)
        protags = informe.actividades[0].protagonistas

        assert len(protags) == 2
        tipos = [p.estamento_tipo for p in protags]
        assert TipoEstamentoInstitucional.ESTUDIANTES in tipos
        assert TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO in tipos
        assert TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS not in tipos

    def test_05_actividad_todos_los_estamentos(self, periodo_septiembre):
        """Escenario 5: Actividad con todos los estamentos participantes."""
        tot_nom = TotalesNominales(
            docentes=2, docentes_f=1, docentes_m=1,
            estudiantes=10, estudiantes_f=6, estudiantes_m=4,
            administrativos=3, administrativos_f=2, administrativos_m=1,
            colaboradores=4, colaboradores_f=2, colaboradores_m=2,
            beneficiarios=5, beneficiarios_f=3, beneficiarios_m=2,
            mujeres=14, varones=10, total=24,
        )
        act = ActividadConsolidada(
            id_actividad="act-all",
            clave_negocio=("Feria Comunitaria", "Waspam", "2026-09-05"),
            nombre_actividad="Feria Comunitaria General",
            sede="Waspam",
            totales_nominales=tot_nom,
        )
        consolidacion = ResultadoConsolidacion(periodo=periodo_septiembre, actividades=[act])

        informe = InstitutionalReportTransformer.transformar(consolidacion)
        protags = informe.actividades[0].protagonistas

        assert len(protags) == 5
        tipos = [p.estamento_tipo for p in protags]
        assert tipos == [
            TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS,
            TipoEstamentoInstitucional.ESTUDIANTES,
            TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO,
            TipoEstamentoInstitucional.COLABORADORES,
            TipoEstamentoInstitucional.BENEFICIARIOS_POBLADORES,
        ]

    def test_06_actividad_sin_colaboradores(self, periodo_septiembre):
        """Escenario 6: Actividad sin colaboradores no genera fila artificial."""
        tot_nom = TotalesNominales(
            estudiantes=15, estudiantes_f=10, estudiantes_m=5,
            colaboradores=0, colaboradores_f=0, colaboradores_m=0,
            mujeres=10, varones=5, total=15,
        )
        act = ActividadConsolidada(
            id_actividad="act-sin-colab",
            clave_negocio=("Taller", "Las Minas", "2026-09-03"),
            nombre_actividad="Taller sin colaboradores",
            sede="Las Minas",
            totales_nominales=tot_nom,
        )
        consolidacion = ResultadoConsolidacion(periodo=periodo_septiembre, actividades=[act])
        informe = InstitutionalReportTransformer.transformar(consolidacion)
        protags = informe.actividades[0].protagonistas
        assert all(p.estamento_tipo != TipoEstamentoInstitucional.COLABORADORES for p in protags)

    def test_07_actividad_sin_beneficiarios(self, periodo_septiembre):
        """Escenario 7: Actividad sin beneficiarios no genera fila artificial."""
        tot_nom = TotalesNominales(
            docentes=5, docentes_f=3, docentes_m=2,
            beneficiarios=0, beneficiarios_f=0, beneficiarios_m=0,
            mujeres=3, varones=2, total=5,
        )
        act = ActividadConsolidada(
            id_actividad="act-sin-ben",
            clave_negocio=("Consejo", "Bilwi", "2026-09-01"),
            nombre_actividad="Consejo de Facultad",
            sede="Bilwi",
            totales_nominales=tot_nom,
        )
        consolidacion = ResultadoConsolidacion(periodo=periodo_septiembre, actividades=[act])
        informe = InstitutionalReportTransformer.transformar(consolidacion)
        protags = informe.actividades[0].protagonistas
        assert all(p.estamento_tipo != TipoEstamentoInstitucional.BENEFICIARIOS_POBLADORES for p in protags)

    def test_08_actividad_discrepancia_narrativa_vs_nominal(self, consolidacion_caso_real):
        """Escenario 8: Preservación simultánea de dato declarado, nominal y delta."""
        informe = InstitutionalReportTransformer.transformar(consolidacion_caso_real)
        act = informe.actividades[0]
        assert act.tiene_discrepancias
        assert len(act.discrepancias) == 3

        # Buscar estamento Estudiantes
        est_protag = next(p for p in act.protagonistas if p.estamento_tipo == TipoEstamentoInstitucional.ESTUDIANTES)
        assert est_protag.tiene_discrepancia
        assert est_protag.dato_declarado.total == 15
        assert est_protag.dato_nominal.total == 17
        assert est_protag.discrepancia_detalle.delta_total == 2
        assert est_protag.discrepancia_detalle.estado == "REQUIERE_REVISION"

        # Buscar estamento Administrativos
        adm_protag = next(p for p in act.protagonistas if p.estamento_tipo == TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO)
        assert adm_protag.tiene_discrepancia
        assert adm_protag.dato_declarado.total == 2
        assert adm_protag.dato_nominal.total == 1
        assert adm_protag.discrepancia_detalle.delta_total == -1

        # Buscar estamento Maestras y maestros
        doc_protag = next(p for p in act.protagonistas if p.estamento_tipo == TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS)
        assert doc_protag.tiene_discrepancia
        assert doc_protag.dato_declarado.total == 1
        assert doc_protag.dato_nominal.total == 0
        assert doc_protag.discrepancia_detalle.delta_total == -1

    def test_09_evidencias_vacias(self, consolidacion_caso_real):
        """Escenario 9: Evidencias vacías presentes como estructura limpia sin excepciones."""
        informe = InstitutionalReportTransformer.transformar(consolidacion_caso_real)
        evidencias = informe.actividades[0].evidencias
        assert evidencias.numero_actividad == 1
        assert len(evidencias.fotografias) == 0
        assert len(evidencias.registros_asistencia) == 0
        assert len(evidencias.enlaces_publicaciones) == 0
        assert evidencias.total_evidencias == 0

    def test_10_evidencias_con_referencias(self, consolidacion_caso_real):
        """Escenario 10: Evidencias cargadas con referencias a fotos, asistencias y URLs."""
        sec_evidencias = SeccionEvidenciasActividad(
            id_actividad="act-real-001",
            numero_actividad=1,
            nombre_actividad="Actividad con evidencias",
            fotografias=[
                ItemEvidenciaInstitucional(
                    tipo=TipoEvidenciaEnum.FOTOGRAFIA,
                    titulo="Foto inicio de capacitación",
                    referencia="C:/evidencias/foto_01.jpg",
                    orden=1,
                )
            ],
            registros_asistencia=[
                ItemEvidenciaInstitucional(
                    tipo=TipoEvidenciaEnum.REGISTRO_ASISTENCIA,
                    titulo="Lista de firmas página 1",
                    referencia="C:/evidencias/asistencia_p1.png",
                    orden=1,
                )
            ],
            enlaces_publicaciones=[
                ItemEvidenciaInstitucional(
                    tipo=TipoEvidenciaEnum.ENLACE_MEDIOS,
                    titulo="Publicación oficial de Facebook",
                    referencia="https://www.facebook.com/share/1J19aqgr3U/",
                    orden=1,
                )
            ],
        )

        informe = InstitutionalReportTransformer.transformar(
            consolidacion=consolidacion_caso_real,
            evidencias_por_actividad={"act-real-001": sec_evidencias},
        )

        evid = informe.actividades[0].evidencias
        assert evid.total_evidencias == 3
        assert evid.fotografias[0].referencia == "C:/evidencias/foto_01.jpg"
        assert evid.registros_asistencia[0].referencia == "C:/evidencias/asistencia_p1.png"
        assert evid.enlaces_publicaciones[0].referencia == "https://www.facebook.com/share/1J19aqgr3U/"

    def test_11_modelo_inmutable(self):
        """Escenario 11: Inmutabilidad en todos los sub-modelos."""
        conteo = ConteoSexoInstitucional(mujeres=5, varones=5, total=10)
        with pytest.raises(ValidationError):
            conteo.mujeres = 6  # type: ignore

        item = ItemEvidenciaInstitucional(
            tipo=TipoEvidenciaEnum.FOTOGRAFIA,
            titulo="Foto",
            referencia="path/foto.jpg",
        )
        with pytest.raises(ValidationError):
            item.titulo = "Nueva Foto"  # type: ignore

    def test_12_transformacion_sin_modificar_resultado_consolidacion(self, consolidacion_caso_real):
        """Escenario 12: Asegurar que el objeto original mantiene exactamente sus valores."""
        hash_inicial = consolidacion_caso_real.fuentes["M1"].hash_sha256
        len_actividades_inicial = len(consolidacion_caso_real.actividades)

        _ = InstitutionalReportTransformer.transformar(consolidacion_caso_real)

        assert consolidacion_caso_real.fuentes["M1"].hash_sha256 == hash_inicial
        assert len(consolidacion_caso_real.actividades) == len_actividades_inicial


# ============================================================================
# TEST CASO REAL SEPTIEMBRE 2026 (REQUERIDO EN SECCIÓN 11 Y 14 DEL PROMPT)
# ============================================================================

def test_caso_real_septiembre_2026_metricas_exactas(consolidacion_caso_real):
    """
    Verificación formal de las métricas exactas del caso real septiembre 2026:
    M1: 12F / 6M / 18
    Nominal: 12F / 6M / 18
    Estamentos: 17 estudiantes, 1 administrativo, 0 docentes
    Discrepancias: 3
    Estado: REQUIERE_REVISION
    """
    informe = InstitutionalReportTransformer.transformar(consolidacion_caso_real)
    act = informe.actividades[0]

    # Totales declarados vs nominales a nivel de informe
    assert act.totales_actividad.mujeres == 12
    assert act.totales_actividad.varones == 6
    assert act.totales_actividad.total == 18

    # Desglose de estamentos
    est_dict = {p.estamento_tipo: p for p in act.protagonistas}
    assert est_dict[TipoEstamentoInstitucional.ESTUDIANTES].conteo_presentacion.total == 17
    assert est_dict[TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO].conteo_presentacion.total == 1
    assert est_dict[TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS].conteo_presentacion.total in (0, 1)

    # Discrepancias preservadas
    assert len(act.discrepancias) == 3
    for d in act.discrepancias:
        assert d.estado == "REQUIERE_REVISION"
