"""Adaptador SQLite para el puerto IActividadRepository.

Implementa la persistencia del agregado Actividad en la tabla relacional `actividad`,
con mapeo explícito bidireccional y manejo tipado de excepciones.
"""

from datetime import date
import sqlite3
from typing import List, Optional, Union

from app.core.models.activity import ActividadMetricaAgregada, Activity
from app.core.ports.actividad_repository import IActividadRepository
from app.infrastructure.persistence.repositories.error_handler import translate_sqlite_errors


class SQLiteActividadRepository(IActividadRepository):
    """Adaptador de persistencia SQLite para el agregado Actividad."""

    VALID_SEDES = {
        "BLUEFIELDS",
        "BILWI",
        "EL_RAMA",
        "CORN_ISLAND",
        "WASPAM",
        "PAIWAS",
        "LAS_MINAS",
        "MANAGUA",
        "OTRA",
    }

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Inicializa el repositorio con una conexión activa a SQLite."""
        self._conn = connection

    def _get_columns(self, table_name: str) -> set:
        """Obtiene el conjunto de columnas existentes en una tabla."""
        cursor = self._conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name});")
            return {row["name"] for row in cursor.fetchall()}
        except Exception:
            return set()

    @translate_sqlite_errors("Actividad")
    def save(self, actividad: Activity) -> None:
        """Inserta o actualiza una entidad Actividad en la tabla `actividad`."""
        # Normalizar sede institucional respetando la restricción CHECK de SQLite
        sede_candidata = (actividad.sede or "OTRA").strip().upper().replace(" ", "_")
        sede_final = sede_candidata if sede_candidata in self.VALID_SEDES else "OTRA"

        fecha_inicio = str(actividad.fecha_evento) if actividad.fecha_evento else date.today().isoformat()
        tipo_evento = actividad.tipo_evento.strip().upper() if actividad.tipo_evento else "TALLER"

        cols = self._get_columns("actividad")
        has_hash = "hash_sha256" in cols
        has_indicador = "codigo_indicador" in cols

        hash_val = actividad.hash_sha256.strip().lower() if actividad.hash_sha256 else None
        indicador_val = actividad.codigo_indicador.strip() if actividad.codigo_indicador else None

        if has_hash and has_indicador:
            query = """
            INSERT INTO actividad (
                id_actividad, nombre_original, nombre_oficial, tipo_evento,
                ambito, eje_estrategico, programa, sede, departamento_geo,
                municipio, fecha_inicio, fecha_fin, departamento_responsable,
                responsable, fuente_financiamiento, estado, es_emergente,
                codigo_indicador, hash_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_actividad) DO UPDATE SET
                nombre_original = excluded.nombre_original,
                nombre_oficial = excluded.nombre_oficial,
                tipo_evento = excluded.tipo_evento,
                ambito = excluded.ambito,
                eje_estrategico = excluded.eje_estrategico,
                programa = excluded.programa,
                sede = excluded.sede,
                departamento_geo = excluded.departamento_geo,
                municipio = excluded.municipio,
                fecha_inicio = excluded.fecha_inicio,
                fecha_fin = excluded.fecha_fin,
                departamento_responsable = excluded.departamento_responsable,
                responsable = excluded.responsable,
                fuente_financiamiento = excluded.fuente_financiamiento,
                estado = excluded.estado,
                es_emergente = excluded.es_emergente,
                codigo_indicador = excluded.codigo_indicador,
                hash_sha256 = excluded.hash_sha256,
                updated_at = CURRENT_TIMESTAMP;
            """
            params = (
                actividad.id_actividad,
                actividad.nombre_actividad_original,
                actividad.nombre_actividad_oficial,
                tipo_evento,
                actividad.ambito,
                actividad.eje_linea_estrategica,
                actividad.programa,
                sede_final,
                actividad.departamento,
                actividad.municipio_evento,
                fecha_inicio,
                None,
                "Innovación y Emprendimiento",
                "Responsable Institucional",
                actividad.informacion_adicional,
                "PLANIFICADA",
                0,
                indicador_val,
                hash_val,
            )
        elif has_indicador:
            query = """
            INSERT INTO actividad (
                id_actividad, nombre_original, nombre_oficial, tipo_evento,
                ambito, eje_estrategico, programa, sede, departamento_geo,
                municipio, fecha_inicio, fecha_fin, departamento_responsable,
                responsable, fuente_financiamiento, estado, es_emergente,
                codigo_indicador
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_actividad) DO UPDATE SET
                nombre_original = excluded.nombre_original,
                nombre_oficial = excluded.nombre_oficial,
                tipo_evento = excluded.tipo_evento,
                ambito = excluded.ambito,
                eje_estrategico = excluded.eje_estrategico,
                programa = excluded.programa,
                sede = excluded.sede,
                departamento_geo = excluded.departamento_geo,
                municipio = excluded.municipio,
                fecha_inicio = excluded.fecha_inicio,
                fecha_fin = excluded.fecha_fin,
                departamento_responsable = excluded.departamento_responsable,
                responsable = excluded.responsable,
                fuente_financiamiento = excluded.fuente_financiamiento,
                estado = excluded.estado,
                es_emergente = excluded.es_emergente,
                codigo_indicador = excluded.codigo_indicador,
                updated_at = CURRENT_TIMESTAMP;
            """
            params = (
                actividad.id_actividad,
                actividad.nombre_actividad_original,
                actividad.nombre_actividad_oficial,
                tipo_evento,
                actividad.ambito,
                actividad.eje_linea_estrategica,
                actividad.programa,
                sede_final,
                actividad.departamento,
                actividad.municipio_evento,
                fecha_inicio,
                None,
                "Innovación y Emprendimiento",
                "Responsable Institucional",
                actividad.informacion_adicional,
                "PLANIFICADA",
                0,
                indicador_val,
            )
        else:
            query = """
            INSERT INTO actividad (
                id_actividad, nombre_original, nombre_oficial, tipo_evento,
                ambito, eje_estrategico, programa, sede, departamento_geo,
                municipio, fecha_inicio, fecha_fin, departamento_responsable,
                responsable, fuente_financiamiento, estado, es_emergente
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_actividad) DO UPDATE SET
                nombre_original = excluded.nombre_original,
                nombre_oficial = excluded.nombre_oficial,
                tipo_evento = excluded.tipo_evento,
                ambito = excluded.ambito,
                eje_estrategico = excluded.eje_estrategico,
                programa = excluded.programa,
                sede = excluded.sede,
                departamento_geo = excluded.departamento_geo,
                municipio = excluded.municipio,
                fecha_inicio = excluded.fecha_inicio,
                fecha_fin = excluded.fecha_fin,
                departamento_responsable = excluded.departamento_responsable,
                responsable = excluded.responsable,
                fuente_financiamiento = excluded.fuente_financiamiento,
                estado = excluded.estado,
                es_emergente = excluded.es_emergente,
                updated_at = CURRENT_TIMESTAMP;
            """
            params = (
                actividad.id_actividad,
                actividad.nombre_actividad_original,
                actividad.nombre_actividad_oficial,
                tipo_evento,
                actividad.ambito,
                actividad.eje_linea_estrategica,
                actividad.programa,
                sede_final,
                actividad.departamento,
                actividad.municipio_evento,
                fecha_inicio,
                None,
                "Innovación y Emprendimiento",
                "Responsable Institucional",
                actividad.informacion_adicional,
                "PLANIFICADA",
                0,
            )

        self._conn.execute(query, params)

        # Si incluye métricas agregadas y la tabla existe, persistirlas
        if actividad.metrica_agregada is not None:
            self.save_metrica_agregada(actividad.metrica_agregada)

    @translate_sqlite_errors("Actividad")
    def get_by_id(self, id_actividad: str) -> Optional[Activity]:
        """Recupera una actividad por su UUID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM actividad WHERE id_actividad = ?;", (id_actividad,))
        row = cursor.fetchone()
        if row is None:
            return None
        act = self._row_to_entity(row)
        act.metrica_agregada = self.get_metrica_agregada(id_actividad)
        return act

    @translate_sqlite_errors("Actividad")
    def get_by_hash(self, hash_sha256: str) -> Optional[Activity]:
        """Recupera una actividad por su hash SHA-256."""
        if not hash_sha256 or not hash_sha256.strip():
            return None
        cols = self._get_columns("actividad")
        if "hash_sha256" not in cols:
            return None

        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM actividad WHERE hash_sha256 = ? LIMIT 1;",
            (hash_sha256.strip().lower(),),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        act = self._row_to_entity(row)
        act.metrica_agregada = self.get_metrica_agregada(act.id_actividad)
        return act

    @translate_sqlite_errors("Actividad")
    def exists(self, id_actividad: str) -> bool:
        """Comprueba existencia por UUID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT 1 FROM actividad WHERE id_actividad = ? LIMIT 1;", (id_actividad,))
        return cursor.fetchone() is not None

    @translate_sqlite_errors("Actividad")
    def list_by_periodo(
        self,
        fecha_inicio: Union[date, str],
        fecha_fin: Union[date, str],
        sede: Optional[str] = None,
    ) -> List[Activity]:
        """Consulta actividades ejecutadas en un rango de fechas."""
        f_inicio_str = str(fecha_inicio)
        f_fin_str = str(fecha_fin)

        if sede is not None:
            sede_norm = sede.strip().upper().replace(" ", "_")
            query = """
            SELECT * FROM actividad
            WHERE fecha_inicio >= ? AND fecha_inicio <= ? AND sede = ?
            ORDER BY fecha_inicio ASC;
            """
            params = (f_inicio_str, f_fin_str, sede_norm)
        else:
            query = """
            SELECT * FROM actividad
            WHERE fecha_inicio >= ? AND fecha_inicio <= ?
            ORDER BY fecha_inicio ASC;
            """
            params = (f_inicio_str, f_fin_str)

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("Actividad")
    def count(self) -> int:
        """Retorna el total de actividades registradas."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM actividad;")
        row = cursor.fetchone()
        return row[0] if row else 0

    @translate_sqlite_errors("ActividadMetricaAgregada")
    def save_metrica_agregada(self, metrica: ActividadMetricaAgregada) -> None:
        """Inserta o actualiza las métricas cuantitativas agregadas de Tabla 2."""
        cols = self._get_columns("actividad_metrica_agregada")
        if not cols:
            return  # Si la tabla no existe en el esquema activo (ej. v001), omitir silenciosamente

        query = """
        INSERT INTO actividad_metrica_agregada (
            id_actividad, total_participantes, total_femenino, total_masculino,
            total_estudiantes, total_docentes, total_administrativos, total_otros,
            total_mestizo, total_creole, total_miskitu, total_mayangna,
            total_ulwa, total_rama, total_garifuna, total_otra_etnia,
            fuente_seccion, presenta_discrepancia_interna
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_actividad) DO UPDATE SET
            total_participantes = excluded.total_participantes,
            total_femenino = excluded.total_femenino,
            total_masculino = excluded.total_masculino,
            total_estudiantes = excluded.total_estudiantes,
            total_docentes = excluded.total_docentes,
            total_administrativos = excluded.total_administrativos,
            total_otros = excluded.total_otros,
            total_mestizo = excluded.total_mestizo,
            total_creole = excluded.total_creole,
            total_miskitu = excluded.total_miskitu,
            total_mayangna = excluded.total_mayangna,
            total_ulwa = excluded.total_ulwa,
            total_rama = excluded.total_rama,
            total_garifuna = excluded.total_garifuna,
            total_otra_etnia = excluded.total_otra_etnia,
            fuente_seccion = excluded.fuente_seccion,
            presenta_discrepancia_interna = excluded.presenta_discrepancia_interna;
        """
        params = (
            metrica.id_actividad,
            metrica.total_participantes,
            metrica.total_femenino,
            metrica.total_masculino,
            metrica.total_estudiantes,
            metrica.total_docentes,
            metrica.total_administrativos,
            metrica.total_otros,
            metrica.total_mestizo,
            metrica.total_creole,
            metrica.total_miskitu,
            metrica.total_mayangna,
            metrica.total_ulwa,
            metrica.total_rama,
            metrica.total_garifuna,
            metrica.total_otra_etnia,
            metrica.fuente_seccion,
            1 if metrica.presenta_discrepancia_interna else 0,
        )
        self._conn.execute(query, params)

    @translate_sqlite_errors("ActividadMetricaAgregada")
    def get_metrica_agregada(self, id_actividad: str) -> Optional[ActividadMetricaAgregada]:
        """Recupera las métricas cuantitativas agregadas de una actividad."""
        cols = self._get_columns("actividad_metrica_agregada")
        if not cols:
            return None

        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM actividad_metrica_agregada WHERE id_actividad = ?;", (id_actividad,))
        row = cursor.fetchone()
        if row is None:
            return None

        return ActividadMetricaAgregada(
            id_actividad=row["id_actividad"],
            total_participantes=row["total_participantes"],
            total_femenino=row["total_femenino"],
            total_masculino=row["total_masculino"],
            total_estudiantes=row["total_estudiantes"],
            total_docentes=row["total_docentes"],
            total_administrativos=row["total_administrativos"],
            total_otros=row["total_otros"],
            total_mestizo=row["total_mestizo"],
            total_creole=row["total_creole"],
            total_miskitu=row["total_miskitu"],
            total_mayangna=row["total_mayangna"],
            total_ulwa=row["total_ulwa"],
            total_rama=row["total_rama"],
            total_garifuna=row["total_garifuna"],
            total_otra_etnia=row["total_otra_etnia"],
            fuente_seccion=row["fuente_seccion"],
            presenta_discrepancia_interna=bool(row["presenta_discrepancia_interna"]),
        )

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Activity:
        """Mapea una fila relacional de SQLite al modelo de dominio Activity."""
        row_keys = row.keys()
        codigo_indicador = row["codigo_indicador"] if "codigo_indicador" in row_keys else None
        hash_sha256 = row["hash_sha256"] if "hash_sha256" in row_keys else None

        return Activity(
            id_actividad=row["id_actividad"],
            nombre_actividad_original=row["nombre_original"],
            nombre_actividad_oficial=row["nombre_oficial"],
            codigo_indicador=codigo_indicador,
            hash_sha256=hash_sha256,
            fecha_evento=row["fecha_inicio"],
            sede=row["sede"],
            departamento=row["departamento_geo"],
            municipio_evento=row["municipio"],
            programa=row["programa"],
            ambito=row["ambito"],
            tipo_evento=row["tipo_evento"],
            eje_linea_estrategica=row["eje_estrategico"],
            informacion_adicional=row["fuente_financiamiento"],
            fuente_origen=None,
        )

