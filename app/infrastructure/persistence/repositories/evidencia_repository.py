"""Adaptador SQLite para el puerto IEvidenciaRepository.

Implementa la persistencia de metadatos de evidencias en la tabla `evidencia`
y la relación asociativa con actividades en `actividad_evidencia`.
"""

import sqlite3
import uuid
from typing import List, Optional, Tuple

from app.core.models.evidence import Evidencia, TipoEvidencia
from app.core.ports.evidencia_repository import IEvidenciaRepository
from app.infrastructure.persistence.repositories.error_handler import translate_sqlite_errors


class SQLiteEvidenciaRepository(IEvidenciaRepository):
    """Adaptador de persistencia SQLite para el agregado Evidencia."""

    VALID_TIPOS = {
        "FOTOGRAFIA",
        "LISTA_FIRMADA",
        "ACTA_RECEPCION",
        "ENLACE_WEB",
        "DOCUMENTO_ADJUNTO",
    }
    VALID_SECCIONES = {"FICHA_TECNICA", "GALERIA", "ANEXO"}

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Inicializa el repositorio con una conexión activa a SQLite."""
        self._conn = connection

    @translate_sqlite_errors("Evidencia")
    def save(self, evidencia: Evidencia) -> None:
        """Inserta o actualiza los metadatos de un activo digital."""
        tipo_str = (
            evidencia.tipo_evidencia.value
            if isinstance(evidencia.tipo_evidencia, TipoEvidencia)
            else str(evidencia.tipo_evidencia)
        ).strip().upper()
        tipo_final = tipo_str if tipo_str in self.VALID_TIPOS else "FOTOGRAFIA"

        query = """
        INSERT INTO evidencia (
            id_evidencia, tipo_evidencia, titulo, descripcion_pie,
            ruta_archivo_relativa, url_externa, hash_sha256,
            tamano_bytes, mime_type, fecha_captura
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_evidencia) DO UPDATE SET
            tipo_evidencia = excluded.tipo_evidencia,
            titulo = excluded.titulo,
            descripcion_pie = excluded.descripcion_pie,
            ruta_archivo_relativa = excluded.ruta_archivo_relativa,
            url_externa = excluded.url_externa,
            hash_sha256 = excluded.hash_sha256,
            tamano_bytes = excluded.tamano_bytes,
            mime_type = excluded.mime_type,
            fecha_captura = excluded.fecha_captura;
        """
        params = (
            evidencia.id_evidencia,
            tipo_final,
            evidencia.titulo,
            evidencia.descripcion_pie,
            evidencia.ruta_archivo_relativa,
            evidencia.url_externa,
            evidencia.hash_sha256,
            evidencia.tamano_bytes,
            evidencia.mime_type,
            str(evidencia.fecha_captura) if evidencia.fecha_captura else None,
        )
        self._conn.execute(query, params)

    @translate_sqlite_errors("Evidencia")
    def get_by_id(self, id_evidencia: str) -> Optional[Evidencia]:
        """Recupera los metadatos de una evidencia por su UUID."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM evidencia WHERE id_evidencia = ?;", (id_evidencia,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    @translate_sqlite_errors("Evidencia")
    def get_by_hash(self, hash_sha256: str) -> Optional[Evidencia]:
        """Recupera una evidencia por su hash SHA-256 para deduplicación."""
        if not hash_sha256 or not hash_sha256.strip():
            return None

        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM evidencia WHERE hash_sha256 = ?;",
            (hash_sha256.strip(),),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    @translate_sqlite_errors("Evidencia")
    def link_actividad(
        self,
        id_actividad: str,
        id_evidencia: str,
        orden: int = 1,
        seccion: str = "GALERIA",
    ) -> None:
        """Asocia una evidencia a una actividad institucional."""
        seccion_norm = seccion.strip().upper()
        seccion_final = seccion_norm if seccion_norm in self.VALID_SECCIONES else "GALERIA"

        query = """
        INSERT INTO actividad_evidencia (
            id_actividad_evidencia, id_actividad, id_evidencia,
            orden_presentacion, seccion_informe
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id_actividad, id_evidencia) DO UPDATE SET
            orden_presentacion = excluded.orden_presentacion,
            seccion_informe = excluded.seccion_informe;
        """
        params = (
            str(uuid.uuid4()),
            id_actividad,
            id_evidencia,
            max(1, orden),
            seccion_final,
        )
        self._conn.execute(query, params)

    @translate_sqlite_errors("Evidencia")
    def unlink_actividad(self, id_actividad: str, id_evidencia: str) -> None:
        """Desvincula una evidencia de una actividad."""
        query = "DELETE FROM actividad_evidencia WHERE id_actividad = ? AND id_evidencia = ?;"
        self._conn.execute(query, (id_actividad, id_evidencia))

    @translate_sqlite_errors("Evidencia")
    def get_by_actividad(
        self, id_actividad: str
    ) -> List[Tuple[Evidencia, int, str]]:
        """Recupera todas las evidencias asociadas a una actividad con su orden y sección."""
        query = """
        SELECT e.*, ae.orden_presentacion, ae.seccion_informe
        FROM evidencia e
        JOIN actividad_evidencia ae ON e.id_evidencia = ae.id_evidencia
        WHERE ae.id_actividad = ?
        ORDER BY ae.orden_presentacion ASC;
        """
        cursor = self._conn.cursor()
        cursor.execute(query, (id_actividad,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            evidencia = self._row_to_entity(r)
            result.append((evidencia, r["orden_presentacion"], r["seccion_informe"]))
        return result

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Evidencia:
        """Mapea una fila relacional de SQLite a la entidad Evidencia."""
        return Evidencia(
            id_evidencia=row["id_evidencia"],
            tipo_evidencia=row["tipo_evidencia"],
            titulo=row["titulo"],
            descripcion_pie=row["descripcion_pie"],
            ruta_archivo_relativa=row["ruta_archivo_relativa"],
            url_externa=row["url_externa"],
            hash_sha256=row["hash_sha256"],
            tamano_bytes=row["tamano_bytes"],
            mime_type=row["mime_type"],
            fecha_captura=row["fecha_captura"],
        )
