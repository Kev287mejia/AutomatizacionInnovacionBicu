"""Adaptador SQLite para el puerto IActividadRepository.

Implementa la persistencia del agregado Actividad en la tabla relacional `actividad`,
con mapeo explícito bidireccional y manejo tipado de excepciones.
"""

from datetime import date
import sqlite3
from typing import List, Optional, Union

from app.core.models.activity import Activity
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

    @translate_sqlite_errors("Actividad")
    def save(self, actividad: Activity) -> None:
        """Inserta o actualiza una entidad Actividad en la tabla `actividad`."""
        # Normalizar sede institucional respetando la restricción CHECK de SQLite
        sede_candidata = (actividad.sede or "OTRA").strip().upper().replace(" ", "_")
        sede_final = sede_candidata if sede_candidata in self.VALID_SEDES else "OTRA"

        fecha_inicio = str(actividad.fecha_evento) if actividad.fecha_evento else date.today().isoformat()
        tipo_evento = actividad.tipo_evento.strip().upper() if actividad.tipo_evento else "TALLER"

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
            None,  # fecha_fin opcional
            "Innovación y Emprendimiento",  # departamento_responsable por defecto
            "Responsable Institucional",     # responsable por defecto
            actividad.informacion_adicional, # almacenado como notas/financiamiento
            "PLANIFICADA",
            0,
        )
        self._conn.execute(query, params)

    @translate_sqlite_errors("Actividad")
    def get_by_id(self, id_actividad: str) -> Optional[Activity]:
        """Recupera una actividad por su UUID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM actividad WHERE id_actividad = ?;", (id_actividad,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

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

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Activity:
        """Mapea una fila relacional de SQLite al modelo de dominio Activity."""
        return Activity(
            id_actividad=row["id_actividad"],
            nombre_actividad_original=row["nombre_original"],
            nombre_actividad_oficial=row["nombre_oficial"],
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
