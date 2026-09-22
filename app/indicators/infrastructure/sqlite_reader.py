"""Implementación SQLite de Solo Lectura para Indicadores Institucionales BICU.

Fase 29.19.1–29.19.2 — Auditoría e Implementación Controlada de Indicadores.

PRINCIPIOS:
  - Acceso estrictamente de solo lectura (únicamente sentencias SELECT).
  - Parámetros enlazados en todas las cláusulas WHERE para prevenir inyección SQL.
  - Exclusión forzosa de M5 histórico (es_historico_preexistente = 0).
  - Exclusión de asistencias no efectivas (condicion_asistencia = 'PRESENTE').
  - Cero mutaciones en la base de datos.
"""

import sqlite3
from typing import Any, Dict, List, Tuple

from app.indicators.domain.contracts import IndicatorQuery
from app.indicators.domain.ports import IndicatorReaderPort


class SQLiteIndicatorReader(IndicatorReaderPort):
    """Adaptador de infraestructura que ejecuta consultas de lectura pura sobre SQLite V001–V004."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _execute_query(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        """Ejecuta una consulta SELECT y retorna una lista de diccionarios inmutables."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                return []
            if isinstance(rows[0], sqlite3.Row):
                return [dict(r) for r in rows]
            col_names = [d[0] for d in cursor.description]
            return [dict(zip(col_names, r)) for r in rows]
        finally:
            cursor.close()

    def get_planning_activities(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera actividades planificadas según criterios dimensionales."""
        clauses = ["1=1"]
        params: List[Any] = []

        if query.sede:
            clauses.append("sede = ?")
            params.append(query.sede)
        if query.programa:
            clauses.append("programa = ?")
            params.append(query.programa)
        if query.eje_estrategico:
            clauses.append("eje_estrategia = ?")
            params.append(query.eje_estrategico)
        if query.tipo_evento:
            clauses.append("tipo_evento = ?")
            params.append(query.tipo_evento)
        if query.start_date:
            clauses.append("(fecha_evento IS NULL OR fecha_evento >= ?)")
            params.append(query.start_date)
        if query.end_date:
            clauses.append("(fecha_evento IS NULL OR fecha_evento <= ?)")
            params.append(query.end_date)

        sql = f"""
        SELECT activity_internal_id, planning_id, activity_name, sede, area_responsable,
               eje_estrategia, programa, tipo_evento, dep_sede, mun_sede, fecha_evento,
               est_grado_m, est_grado_f, est_postgrado_m, est_postgrado_f,
               docentes_m, docentes_f, administrativos_m, administrativos_f,
               externos_m, externos_f, created_at
        FROM planning_planned_activities
        WHERE {" AND ".join(clauses)}
        ORDER BY activity_name ASC;
        """
        return self._execute_query(sql, tuple(params))

    def get_executed_activities(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera actividades ejecutadas reales en estados finales."""
        clauses = ["estado IN ('EJECUTADA', 'REPORTADA', 'CERRADA')"]
        params: List[Any] = []

        if query.sede:
            clauses.append("sede = ?")
            params.append(query.sede)
        if query.programa:
            clauses.append("programa = ?")
            params.append(query.programa)
        if query.eje_estrategico:
            clauses.append("eje_estrategico = ?")
            params.append(query.eje_estrategico)
        if query.tipo_evento:
            clauses.append("tipo_evento = ?")
            params.append(query.tipo_evento)
        if query.start_date:
            clauses.append("fecha_inicio >= ?")
            params.append(query.start_date)
        if query.end_date:
            clauses.append("fecha_inicio <= ?")
            params.append(query.end_date)

        sql = f"""
        SELECT id_actividad, codigo_institucional, nombre_original, nombre_oficial,
               codigo_indicador, tipo_evento, ambito, eje_estrategico, programa, proyecto,
               sede, departamento_geo, municipio, fecha_inicio, fecha_fin,
               departamento_responsable, responsable, estado, es_emergente, hash_sha256,
               created_at
        FROM actividad
        WHERE {" AND ".join(clauses)}
        ORDER BY fecha_inicio ASC;
        """
        return self._execute_query(sql, tuple(params))

    def get_execution_links(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera vínculos de trazabilidad Planificación ↔ Ejecución."""
        sql = """
        SELECT pel.link_id, pel.planning_internal_id, pel.id_actividad, pel.linked_by,
               pel.linked_at, pel.link_rationale, pel.numero_sesion, pel.link_status,
               pel.revoked_by, pel.revoked_at, pel.revocation_reason
        FROM planning_execution_links pel
        ORDER BY pel.linked_at ASC;
        """
        return self._execute_query(sql)

    def get_participations(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera participaciones presenciales efectivas del período (excluye M5 histórico)."""
        clauses = [
            "part.condicion_asistencia = 'PRESENTE'",
            "part.es_historico_preexistente = 0",
            "act.estado IN ('EJECUTADA', 'REPORTADA', 'CERRADA')",
        ]
        params: List[Any] = []

        if query.sede:
            clauses.append("act.sede = ?")
            params.append(query.sede)
        if query.programa:
            clauses.append("act.programa = ?")
            params.append(query.programa)
        if query.eje_estrategico:
            clauses.append("act.eje_estrategico = ?")
            params.append(query.eje_estrategico)
        if query.tipo_evento:
            clauses.append("act.tipo_evento = ?")
            params.append(query.tipo_evento)
        if query.start_date:
            clauses.append("act.fecha_inicio >= ?")
            params.append(query.start_date)
        if query.end_date:
            clauses.append("act.fecha_inicio <= ?")
            params.append(query.end_date)

        sql = f"""
        SELECT part.id_participacion, part.id_actividad, part.id_persona,
               part.estamento_declarado, part.es_beneficiado_rol, part.matriz_destino,
               part.rol_en_actividad, part.condicion_asistencia, part.carrera_o_cargo_actividad,
               part.es_historico_preexistente,
               act.sede AS actividad_sede, act.fecha_inicio AS actividad_fecha,
               act.programa AS actividad_programa, act.tipo_evento AS actividad_tipo_evento,
               p.cedula, p.numero_institucional, p.nombre_completo, p.sexo, p.etnia,
               p.edad_declarada, p.municipio_residencia
        FROM participacion part
        INNER JOIN actividad act ON part.id_actividad = act.id_actividad
        LEFT JOIN persona p ON part.id_persona = p.id_persona_interno
        WHERE {" AND ".join(clauses)}
        ORDER BY part.id_participacion ASC;
        """
        return self._execute_query(sql, tuple(params))

    def get_unique_persons(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera personas únicas participantes con recuento de actividades distintas asistidas."""
        clauses = [
            "part.condicion_asistencia = 'PRESENTE'",
            "part.es_historico_preexistente = 0",
            "act.estado IN ('EJECUTADA', 'REPORTADA', 'CERRADA')",
        ]
        params: List[Any] = []

        if query.sede:
            clauses.append("act.sede = ?")
            params.append(query.sede)
        if query.programa:
            clauses.append("act.programa = ?")
            params.append(query.programa)
        if query.start_date:
            clauses.append("act.fecha_inicio >= ?")
            params.append(query.start_date)
        if query.end_date:
            clauses.append("act.fecha_inicio <= ?")
            params.append(query.end_date)

        sql = f"""
        SELECT p.id_persona_interno, p.cedula, p.numero_institucional, p.nombre_completo,
               p.sexo, p.etnia, p.edad_declarada, p.municipio_residencia,
               COUNT(DISTINCT part.id_actividad) AS total_actividades_distintas
        FROM persona p
        INNER JOIN participacion part ON p.id_persona_interno = part.id_persona
        INNER JOIN actividad act ON part.id_actividad = act.id_actividad
        WHERE {" AND ".join(clauses)}
        GROUP BY p.id_persona_interno, p.cedula, p.numero_institucional, p.nombre_completo,
                 p.sexo, p.etnia, p.edad_declarada, p.municipio_residencia
        ORDER BY p.nombre_completo ASC;
        """
        return self._execute_query(sql, tuple(params))

    def get_discrepancies(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera discrepancias detectadas asociadas a actividades del período."""
        clauses = ["act.estado IN ('EJECUTADA', 'REPORTADA', 'CERRADA')"]
        params: List[Any] = []

        if query.sede:
            clauses.append("act.sede = ?")
            params.append(query.sede)
        if query.start_date:
            clauses.append("act.fecha_inicio >= ?")
            params.append(query.start_date)
        if query.end_date:
            clauses.append("act.fecha_inicio <= ?")
            params.append(query.end_date)

        sql = f"""
        SELECT d.id_discrepancia, d.id_actividad, d.tipo_discrepancia, d.severidad,
               d.fuente_a_nombre, d.fuente_a_valor, d.fuente_b_nombre, d.fuente_b_valor,
               d.delta_valor, d.estado, d.justificacion_aclaratoria, d.fecha_deteccion
        FROM discrepancia d
        INNER JOIN actividad act ON d.id_actividad = act.id_actividad
        WHERE {" AND ".join(clauses)}
        ORDER BY d.fecha_deteccion ASC;
        """
        return self._execute_query(sql, tuple(params))

    def get_methodological_designs(self, query: IndicatorQuery) -> List[Dict[str, Any]]:
        """Recupera diseños metodológicos asociados a actividades planificadas."""
        sql = """
        SELECT design_id, planned_activity_internal_id, planned_activity_ref,
               version, status, created_by, created_at, approved_by, approved_at,
               document_hash
        FROM planning_methodological_designs
        ORDER BY created_at ASC;
        """
        return self._execute_query(sql)
