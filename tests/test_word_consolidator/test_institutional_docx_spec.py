"""
tests.test_word_consolidator.test_institutional_docx_spec

Pruebas unitarias de especificación y diseño para el maquetado DOCX institucional
(Producto B - Fase 16.4).

Valida los 9 escenarios conceptuales exigidos:
1. Informe sin actividades (N = 0)
2. Una actividad (con solo estudiantes)
3. Actividad con estudiantes + administrativos
4. Actividad con todos los estamentos
5. Múltiples actividades (N >= 2)
6. Caso real septiembre de 2026 (M1 vs Nominal vs Discrepancias)
7. Evidencias vacías (política de no-invención)
8. Evidencias referenciadas (fotos, asistencias, enlaces)
9. Invariante de 13 columnas y reglas de paginación (cantSplit, tblHeader, landscape)
"""

import pytest

from app.word_consolidator.document.institutional_models import (
    InformeSemanalInstitucional,
    ActividadInstitucional,
    ProtagonistaEstamentoInstitucional,
    ConteoSexoInstitucional,
    DiscrepanciaActividadInstitucional,
    DiscrepanciaEstamento,
    SeccionEvidenciasActividad,
    ItemEvidenciaInstitucional,
    TrazabilidadActividad,
    TipoEstamentoInstitucional,
    TipoEvidenciaEnum,
    EstadoEvidenciaEnum,
)
from app.word_consolidator.institutional_docx.constants import (
    PAGE_ORIENTATION,
    PAGE_WIDTH_PT,
    PAGE_HEIGHT_PT,
    MARGIN_TOP_PT,
    MARGIN_BOTTOM_PT,
    MARGIN_LEFT_PT,
    MARGIN_RIGHT_PT,
    TOTAL_TABLE_WIDTH_TWIPS,
)
from app.word_consolidator.institutional_docx.spec import (
    ModoFuenteDatosEnum,
    TipoFilaEnum,
    VMergeType,
    RowLayoutSpec,
    CellLayoutSpec,
    CellMergeSpec,
    build_table_layout_spec,
    build_evidencias_spec,
    build_document_layout_spec,
)


# ============================================================================
# FIXTURES AUXILIARES
# ============================================================================

def _crear_actividad_base(
    id_act: str = "act-01",
    num: int = 1,
    nombre: str = "Capacitación en IA",
    estamentos: list = None,
    total_m: int = 0,
    total_v: int = 0,
    evidencias: SeccionEvidenciasActividad = None,
    discrepancias: list = None,
) -> ActividadInstitucional:
    if estamentos is None:
        estamentos = []
    if evidencias is None:
        evidencias = SeccionEvidenciasActividad(
            id_actividad=id_act,
            numero_actividad=num,
            nombre_actividad=nombre,
        )
    if discrepancias is None:
        discrepancias = []

    return ActividadInstitucional(
        id_actividad=id_act,
        numero_orden=num,
        nombre_actividad=nombre,
        eje_vinculado="11.41.67",
        descripcion="Descripción de prueba",
        sede="Bilwi",
        departamento="RACCN",
        municipio="Puerto Cabezas",
        tipo_actividad="7. Creatividad, Ciencias e Innovación",
        protagonistas=estamentos,
        totales_actividad=ConteoSexoInstitucional(mujeres=total_m, varones=total_v, total=total_m + total_v),
        discrepancias=discrepancias,
        evidencias=evidencias,
        trazabilidad=TrazabilidadActividad(
            id_actividad=id_act,
            matriz_m1_origen="M1.xlsx",
        ),
    )


# ============================================================================
# TEST SUITE
# ============================================================================

class TestInstitutionalDocxSpec:

    def test_01_informe_sin_actividades_n0(self):
        """Valida que un informe con N=0 actividades construya una tabla con fila informativa y conserve 13 columnas."""
        informe = InformeSemanalInstitucional(
            departamento_responsable="Innovación y Emprendimiento",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[],
        )

        doc_spec = build_document_layout_spec(informe)
        tabla = doc_spec.tabla_ejecutiva

        assert tabla.actividades_count == 0
        assert tabla.total_filas == 5  # MetaDepto, MetaMesSemana, Superheader, Subheader, EmptyState
        assert tabla.filas[4].tipo_fila == TipoFilaEnum.EMPTY_STATE
        assert tabla.filas[4].celdas[0].merge.grid_span == 13
        assert "No se registraron actividades" in tabla.filas[4].celdas[0].texto

        # Validar que todas las filas cumplen exactamente 13 columnas de span
        for fila in tabla.filas:
            assert fila.total_span == 13

        assert doc_spec.seccion_evidencias.total_evidencias == 0
        assert len(doc_spec.seccion_evidencias.actividades) == 0

    def test_02_una_actividad_con_solo_estudiantes(self):
        """Valida tabla para 1 actividad con 1 solo estamento (Estudiantes)."""
        est = ProtagonistaEstamentoInstitucional(
            estamento_tipo=TipoEstamentoInstitucional.ESTUDIANTES,
            denominacion_visible="2. Estudiantes",
            conteo_presentacion=ConteoSexoInstitucional(mujeres=10, varones=5, total=15),
        )
        act = _crear_actividad_base(estamentos=[est], total_m=10, total_v=5)
        informe = InformeSemanalInstitucional(
            departamento_responsable="Innovación y Emprendimiento",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[act],
        )

        tabla = build_table_layout_spec(informe)

        # 4 filas de encabezados + 1 fila de datos = 5 filas
        assert tabla.total_filas == 5
        data_row = tabla.filas[4]
        assert data_row.tipo_fila == TipoFilaEnum.DATA_ROW
        assert len(data_row.celdas) == 11

        # Como es un solo estamento, vMerge debe ser NONE (no requiere fusión multi-fila)
        assert data_row.celdas[0].merge.v_merge == VMergeType.NONE
        assert data_row.celdas[7].texto == "2. Estudiantes"
        assert data_row.celdas[8].texto == "10"  # M
        assert data_row.celdas[9].texto == "5"   # V
        assert data_row.celdas[10].texto == "15" # Total
        assert data_row.total_span == 13

    def test_03_actividad_con_estudiantes_y_administrativos(self):
        """Valida fusión vertical (vMerge=restart y continue) para 2 estamentos."""
        est1 = ProtagonistaEstamentoInstitucional(
            estamento_tipo=TipoEstamentoInstitucional.ESTUDIANTES,
            denominacion_visible="2. Estudiantes",
            conteo_presentacion=ConteoSexoInstitucional(mujeres=10, varones=5, total=15),
        )
        est2 = ProtagonistaEstamentoInstitucional(
            estamento_tipo=TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO,
            denominacion_visible="3. Personal administrativo",
            conteo_presentacion=ConteoSexoInstitucional(mujeres=2, varones=0, total=2),
        )
        act = _crear_actividad_base(estamentos=[est1, est2], total_m=12, total_v=5)
        informe = InformeSemanalInstitucional(
            departamento_responsable="Innovación y Emprendimiento",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[act],
        )

        tabla = build_table_layout_spec(informe)

        # 4 encabezados + 2 filas de datos = 6 filas
        assert tabla.total_filas == 6

        row_estudiantes = tabla.filas[4]
        row_admin = tabla.filas[5]

        # Fila 4: primer estamento -> vMerge=restart en columnas compartidas 0..6
        for c_idx in range(7):
            assert row_estudiantes.celdas[c_idx].merge.v_merge == VMergeType.RESTART
        assert row_estudiantes.celdas[0].texto == act.nombre_actividad
        assert row_estudiantes.celdas[7].texto == "2. Estudiantes"
        assert row_estudiantes.celdas[7].merge.v_merge == VMergeType.NONE

        # Fila 5: segundo estamento -> vMerge=continue en columnas compartidas 0..6 con texto vacío
        for c_idx in range(7):
            assert row_admin.celdas[c_idx].merge.v_merge == VMergeType.CONTINUE
            assert row_admin.celdas[c_idx].texto == ""
        assert row_admin.celdas[7].texto == "3. Personal administrativo"
        assert row_admin.celdas[7].merge.v_merge == VMergeType.NONE
        assert row_admin.celdas[8].texto == "2"
        assert row_admin.celdas[9].texto == "0"
        assert row_admin.celdas[10].texto == "2"

        # Ambas filas suman 13
        assert row_estudiantes.total_span == 13
        assert row_admin.total_span == 13

    def test_04_actividad_con_todos_los_estamentos(self):
        """Valida una actividad con los 5 estamentos institucionales."""
        estamentos = [
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.ESTUDIANTES,
                denominacion_visible="2. Estudiantes",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=10, varones=5, total=15),
            ),
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO,
                denominacion_visible="3. Personal administrativo",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=2, varones=1, total=3),
            ),
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS,
                denominacion_visible="1. Maestras y maestros",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=1, varones=1, total=2),
            ),
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.COLABORADORES,
                denominacion_visible="4. Colaboradores",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=1, varones=0, total=1),
            ),
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.BENEFICIARIOS_POBLADORES,
                denominacion_visible="5. Población general",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=5, varones=5, total=10),
            ),
        ]
        act = _crear_actividad_base(estamentos=estamentos, total_m=19, total_v=12)
        informe = InformeSemanalInstitucional(
            departamento_responsable="Extensión Universitaria",
            mes_planificado="Octubre",
            semana="2",
            actividades=[act],
        )

        tabla = build_table_layout_spec(informe)

        # 4 encabezados + 5 datos = 9 filas
        assert tabla.total_filas == 9
        for r_idx in range(4, 9):
            fila = tabla.filas[r_idx]
            assert fila.total_span == 13
            if r_idx == 4:
                assert fila.celdas[0].merge.v_merge == VMergeType.RESTART
            else:
                assert fila.celdas[0].merge.v_merge == VMergeType.CONTINUE

    def test_05_multiples_actividades(self):
        """Valida que N=3 actividades se construyan secuencialmente en la misma tabla sin mezclar datos."""
        est_a1 = [
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.ESTUDIANTES,
                denominacion_visible="Estudiantes A1",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=5, varones=5, total=10),
            ),
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO,
                denominacion_visible="Admin A1",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=1, varones=0, total=1),
            ),
        ]
        act1 = _crear_actividad_base("act-1", 1, "Actividad 1", est_a1, total_m=6, total_v=5)

        est_a2 = [
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.ESTUDIANTES,
                denominacion_visible="Estudiantes A2",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=20, varones=10, total=30),
            ),
        ]
        act2 = _crear_actividad_base("act-2", 2, "Actividad 2", est_a2, total_m=20, total_v=10)

        est_a3 = [
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS,
                denominacion_visible="Docentes A3",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=3, varones=2, total=5),
            ),
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.ESTUDIANTES,
                denominacion_visible="Estudiantes A3",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=7, varones=3, total=10),
            ),
            ProtagonistaEstamentoInstitucional(
                estamento_tipo=TipoEstamentoInstitucional.COLABORADORES,
                denominacion_visible="Colaboradores A3",
                conteo_presentacion=ConteoSexoInstitucional(mujeres=1, varones=1, total=2),
            ),
        ]
        act3 = _crear_actividad_base("act-3", 3, "Actividad 3", est_a3, total_m=11, total_v=6)

        informe = InformeSemanalInstitucional(
            departamento_responsable="Secretaría Académica",
            mes_planificado="Noviembre",
            semana="3",
            actividades=[act1, act2, act3],
        )

        tabla = build_table_layout_spec(informe)

        # Filas: 4 encabezados + 2 (act1) + 1 (act2) + 3 (act3) = 10 filas
        assert tabla.total_filas == 10
        assert tabla.actividades_count == 3

        # Verificar independencia de los bloques
        assert tabla.filas[4].actividad_id == "act-1"
        assert tabla.filas[4].celdas[0].merge.v_merge == VMergeType.RESTART
        assert tabla.filas[5].actividad_id == "act-1"
        assert tabla.filas[5].celdas[0].merge.v_merge == VMergeType.CONTINUE

        assert tabla.filas[6].actividad_id == "act-2"
        assert tabla.filas[6].celdas[0].merge.v_merge == VMergeType.NONE

        assert tabla.filas[7].actividad_id == "act-3"
        assert tabla.filas[7].celdas[0].merge.v_merge == VMergeType.RESTART
        assert tabla.filas[8].actividad_id == "act-3"
        assert tabla.filas[8].celdas[0].merge.v_merge == VMergeType.CONTINUE
        assert tabla.filas[9].actividad_id == "act-3"
        assert tabla.filas[9].celdas[0].merge.v_merge == VMergeType.CONTINUE

        for fila in tabla.filas:
            assert fila.total_span == 13

    def test_06_caso_real_septiembre_2026_conserva_discrepancias_y_ambas_fuentes(self):
        """
        Valida el CASO REAL institucional de Septiembre 2026:
        - M1 declarado: 12 M, 6 V, Total 18 (15 estudiantes, 2 admin, 1 docente).
        - Nominal: 12 M, 6 V, Total 18 (17 estudiantes, 1 admin, 0 docentes).
        - 3 discrepancias conservadas: estudiantes +2, admin -1, docentes -1, total delta 0.
        Verifica que el renderer puede proyectar M1 o Nominal sin mutar el modelo ni forzar conciliación.
        """
        # Estamento Estudiantes: M1 (10, 5, 15) vs Nominal (12, 5, 17) -> delta +2
        est_estudiantes = ProtagonistaEstamentoInstitucional(
            estamento_tipo=TipoEstamentoInstitucional.ESTUDIANTES,
            denominacion_visible="2. Estudiantes",
            conteo_presentacion=ConteoSexoInstitucional(mujeres=10, varones=5, total=15),
            dato_declarado=ConteoSexoInstitucional(mujeres=10, varones=5, total=15),
            dato_nominal=ConteoSexoInstitucional(mujeres=12, varones=5, total=17),
            tiene_discrepancia=True,
            discrepancia_detalle=DiscrepanciaEstamento(
                delta_mujeres=2, delta_varones=0, delta_total=2, descripcion="Estudiantes +2 nominal"
            ),
        )
        # Estamento Administrativo: M1 (2, 0, 2) vs Nominal (0, 1, 1) -> delta -1
        est_admin = ProtagonistaEstamentoInstitucional(
            estamento_tipo=TipoEstamentoInstitucional.PERSONAL_ADMINISTRATIVO,
            denominacion_visible="3. Personal administrativo",
            conteo_presentacion=ConteoSexoInstitucional(mujeres=2, varones=0, total=2),
            dato_declarado=ConteoSexoInstitucional(mujeres=2, varones=0, total=2),
            dato_nominal=ConteoSexoInstitucional(mujeres=0, varones=1, total=1),
            tiene_discrepancia=True,
            discrepancia_detalle=DiscrepanciaEstamento(
                delta_mujeres=-2, delta_varones=1, delta_total=-1, descripcion="Administrativos -1 nominal"
            ),
        )
        # Estamento Docentes: M1 (0, 1, 1) vs Nominal (0, 0, 0) -> delta -1
        est_docentes = ProtagonistaEstamentoInstitucional(
            estamento_tipo=TipoEstamentoInstitucional.MAESTRAS_Y_MAESTROS,
            denominacion_visible="1. Maestras y maestros",
            conteo_presentacion=ConteoSexoInstitucional(mujeres=0, varones=1, total=1),
            dato_declarado=ConteoSexoInstitucional(mujeres=0, varones=1, total=1),
            dato_nominal=ConteoSexoInstitucional(mujeres=0, varones=0, total=0),
            tiene_discrepancia=True,
            discrepancia_detalle=DiscrepanciaEstamento(
                delta_mujeres=0, delta_varones=-1, delta_total=-1, descripcion="Docentes -1 nominal"
            ),
        )

        discrepancias_act = [
            DiscrepanciaActividadInstitucional(
                estamento="ESTUDIANTES",
                fuente_declarada="Matriz 1",
                fuente_nominal="Matriz 2",
                declarado_m=10, declarado_v=5, declarado_total=15,
                nominal_m=12, nominal_v=5, nominal_total=17,
                delta_total=2, delta_m=2, delta_v=0,
                descripcion="Diferencia en estudiantes (+2 nominal)",
            ),
            DiscrepanciaActividadInstitucional(
                estamento="PERSONAL_ADMINISTRATIVO",
                fuente_declarada="Matriz 1",
                fuente_nominal="Matriz 3",
                declarado_m=2, declarado_v=0, declarado_total=2,
                nominal_m=0, nominal_v=1, nominal_total=1,
                delta_total=-1, delta_m=-2, delta_v=1,
                descripcion="Diferencia en administrativos (-1 nominal)",
            ),
            DiscrepanciaActividadInstitucional(
                estamento="MAESTRAS_Y_MAESTROS",
                fuente_declarada="Matriz 1",
                fuente_nominal="Matriz 4",
                declarado_m=0, declarado_v=1, declarado_total=1,
                nominal_m=0, nominal_v=0, nominal_total=0,
                delta_total=-1, delta_m=0, delta_v=-1,
                descripcion="Diferencia en docentes (-1 nominal)",
            ),
        ]

        act_real = _crear_actividad_base(
            id_act="act-real-sept-2026",
            num=1,
            nombre="BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial",
            estamentos=[est_estudiantes, est_admin, est_docentes],
            total_m=12,
            total_v=6,
            discrepancias=discrepancias_act,
        )

        informe = InformeSemanalInstitucional(
            departamento_responsable="Innovación y Emprendimiento",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[act_real],
        )

        # 1. Validación en Modo DECLARADO_M1
        tabla_m1 = build_table_layout_spec(informe, modo_fuente=ModoFuenteDatosEnum.DECLARADO_M1)
        assert tabla_m1.total_mujeres == 12
        assert tabla_m1.total_varones == 6
        assert tabla_m1.total_participantes == 18

        # Fila estudiantes M1
        row_m1_est = tabla_m1.filas[4]
        assert row_m1_est.celdas[8].texto == "10"
        assert row_m1_est.celdas[9].texto == "5"
        assert row_m1_est.celdas[10].texto == "15"

        # Fila admin M1
        row_m1_adm = tabla_m1.filas[5]
        assert row_m1_adm.celdas[8].texto == "2"
        assert row_m1_adm.celdas[9].texto == "0"
        assert row_m1_adm.celdas[10].texto == "2"

        # Fila docentes M1
        row_m1_doc = tabla_m1.filas[6]
        assert row_m1_doc.celdas[8].texto == "0"
        assert row_m1_doc.celdas[9].texto == "1"
        assert row_m1_doc.celdas[10].texto == "1"

        # 2. Validación en Modo NOMINAL
        tabla_nom = build_table_layout_spec(informe, modo_fuente=ModoFuenteDatosEnum.NOMINAL)
        assert tabla_nom.total_mujeres == 12
        assert tabla_nom.total_varones == 6
        assert tabla_nom.total_participantes == 18

        # Fila estudiantes Nominal (12, 5, 17)
        row_nom_est = tabla_nom.filas[4]
        assert row_nom_est.celdas[8].texto == "12"
        assert row_nom_est.celdas[9].texto == "5"
        assert row_nom_est.celdas[10].texto == "17"

        # Fila admin Nominal (0, 1, 1)
        row_nom_adm = tabla_nom.filas[5]
        assert row_nom_adm.celdas[8].texto == "0"
        assert row_nom_adm.celdas[9].texto == "1"
        assert row_nom_adm.celdas[10].texto == "1"

        # Fila docentes Nominal (0, 0, 0)
        row_nom_doc = tabla_nom.filas[6]
        assert row_nom_doc.celdas[8].texto == "0"
        assert row_nom_doc.celdas[9].texto == "0"
        assert row_nom_doc.celdas[10].texto == "0"

        # Las discrepancias persisten intactas en el modelo sin reconciliación silenciosa
        assert informe.tiene_discrepancias is True
        assert len(informe.actividades[0].discrepancias) == 3

    def test_07_evidencias_vacias(self):
        """Valida que actividades sin evidencias generen la estructura formal sin inventar contenido."""
        sec_vacia = SeccionEvidenciasActividad(
            id_actividad="act-vacia",
            numero_actividad=1,
            nombre_actividad="Taller sin anexos",
            fotografias=[],
            registros_asistencia=[],
            enlaces_publicaciones=[],
        )
        act = _crear_actividad_base("act-vacia", 1, "Taller sin anexos", evidencias=sec_vacia)
        informe = InformeSemanalInstitucional(
            departamento_responsable="Dpto Test",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[act],
        )

        ev_spec = build_evidencias_spec(informe)
        assert ev_spec.titulo == "EVIDENCIAS ANEXAS"
        assert ev_spec.requiere_salto_pagina_previo is True
        assert ev_spec.total_evidencias == 0
        assert len(ev_spec.actividades) == 1
        act_ev = ev_spec.actividades[0]
        assert act_ev.heading_text == "1. Taller sin anexos"
        assert act_ev.tiene_evidencias is False
        assert len(act_ev.fotografias) == 0
        assert len(act_ev.registros_asistencia) == 0
        assert len(act_ev.enlaces_publicaciones) == 0

    def test_08_evidencias_referenciadas_completas(self):
        """Valida la especificación de evidencias cuando existen fotos, asistencias y enlaces."""
        fotos = [
            ItemEvidenciaInstitucional(
                tipo=TipoEvidenciaEnum.FOTOGRAFIA,
                titulo="Estudiantes en laboratorio",
                referencia="C:/evidencias/foto1.jpg",
                estado=EstadoEvidenciaEnum.VINCULADO,
                orden=1,
            ),
            ItemEvidenciaInstitucional(
                tipo=TipoEvidenciaEnum.FOTOGRAFIA,
                titulo="Demostración de logotipo",
                referencia="C:/evidencias/foto2.jpg",
                estado=EstadoEvidenciaEnum.VINCULADO,
                orden=2,
            ),
        ]
        asistencias = [
            ItemEvidenciaInstitucional(
                tipo=TipoEvidenciaEnum.REGISTRO_ASISTENCIA,
                titulo="Lista de asistencia física firmada",
                referencia="C:/evidencias/asistencia.pdf",
                estado=EstadoEvidenciaEnum.PENDIENTE,
                orden=1,
            ),
        ]
        enlaces = [
            ItemEvidenciaInstitucional(
                tipo=TipoEvidenciaEnum.ENLACE_MEDIOS,
                titulo="Publicación en Facebook",
                referencia="https://www.facebook.com/share/1J19aqgr3U/",
                estado=EstadoEvidenciaEnum.VINCULADO,
                orden=1,
            ),
        ]
        sec = SeccionEvidenciasActividad(
            id_actividad="act-ev-comp",
            numero_actividad=1,
            nombre_actividad="Actividad Completa",
            fotografias=fotos,
            registros_asistencia=asistencias,
            enlaces_publicaciones=enlaces,
        )
        act = _crear_actividad_base("act-ev-comp", 1, "Actividad Completa", evidencias=sec)
        informe = InformeSemanalInstitucional(
            departamento_responsable="Dpto Test",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[act],
        )

        ev_spec = build_evidencias_spec(informe)
        assert ev_spec.total_evidencias == 4
        act_ev = ev_spec.actividades[0]
        assert act_ev.tiene_evidencias is True
        assert len(act_ev.fotografias) == 2
        assert len(act_ev.registros_asistencia) == 1
        assert len(act_ev.enlaces_publicaciones) == 1
        assert act_ev.enlaces_publicaciones[0].referencia == "https://www.facebook.com/share/1J19aqgr3U/"

    def test_09_invariante_geometrico_13_columnas_y_twips(self):
        """Valida que la suma de twips sea 14878 y que cualquier fila con span != 13 arroje error."""
        assert TOTAL_TABLE_WIDTH_TWIPS == 14878

        # Validar que una fila con span != 13 arroje ValueError
        celda_invalida = CellLayoutSpec(
            col_grid_idx=0,
            texto="Error",
            merge=CellMergeSpec(grid_span=5),
            ancho_twips=1000,
        )
        with pytest.raises(ValueError, match="Invariante de tabla violado"):
            RowLayoutSpec(
                row_idx=0,
                tipo_fila=TipoFilaEnum.DATA_ROW,
                celdas=[celda_invalida],
                total_span=13,
            )

    def test_10_paginacion_cantSplit_tblHeader_y_geometria_pagina(self):
        """Valida reglas de paginación: landscape letter, márgenes 3cm/2.5cm, cantSplit y tblHeader."""
        act = _crear_actividad_base()
        informe = InformeSemanalInstitucional(
            departamento_responsable="Área de Innovación",
            mes_planificado="Septiembre",
            semana="1",
            actividades=[act],
        )

        doc_spec = build_document_layout_spec(informe)

        # Geometría de página Letter Landscape
        assert doc_spec.orientacion == PAGE_ORIENTATION
        assert doc_spec.page_width_pt == PAGE_WIDTH_PT    # 792.0 pt (11.0 in)
        assert doc_spec.page_height_pt == PAGE_HEIGHT_PT  # 612.0 pt (8.5 in)
        assert doc_spec.margen_superior_pt == MARGIN_TOP_PT  # 85.05 pt (3.0 cm)
        assert doc_spec.margen_inferior_pt == MARGIN_BOTTOM_PT
        assert doc_spec.margen_izquierdo_pt == MARGIN_LEFT_PT # 70.9 pt (2.5 cm)
        assert doc_spec.margen_derecho_pt == MARGIN_RIGHT_PT

        # Paginación en tabla: cantSplit=True en todas las filas
        for fila in doc_spec.tabla_ejecutiva.filas:
            assert fila.cant_split is True

        # tblHeader=True en filas de encabezado (Superheader y Subheader)
        assert doc_spec.tabla_ejecutiva.filas[2].tbl_header is True
        assert doc_spec.tabla_ejecutiva.filas[3].tbl_header is True
        # Filas de datos no son tblHeader
        assert doc_spec.tabla_ejecutiva.filas[4].tbl_header is False
