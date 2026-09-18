"""Adaptador SQLite para el puerto IDiscrepanciaRepository.

Implementa la persistencia de hallazgos periciales bajo el principio
inviolable DETECTAR ≠ CORREGIR (Regla RN-C07).
"""

from datetime import datetime
import sqlite3
from typing import List, Optional

from app.core.models.discrepancy import (
    Discrepancia,
    EstadoDiscrepancia,
    SeveridadDiscrepancia,
    TipoDiscrepancia,
)
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository
from app.infrastructure.persistence.repositories.error_handler import translate_sqlite_errors


class SQLiteDiscrepanciaRepository(IDiscrepanciaRepository):
    """Adaptador de persistencia SQLite para el agregado Discrepancia."""

    VALID_TIPOS = {
        "PLAN_VS_REAL",
        "RESUMEN_VS_NOMINAL",
        "M1_VS_NOMINALES",
        "FECHA_DISCORDANTE",
        "OTRO",
    }
    VALID_SEVERIDADES = {"INFO", "WARNING", "ERROR"}
    VALID_ESTADOS = {"REQUIERE_REVISION", "EN_REVISION", "ACLARADO", "CONCORDANTE"}

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Inicializa el repositorio con una conexión activa a SQLite."""
        self._conn = connection

    @translate_sqlite_errors("Discrepancia")
    def save(self, discrepancia: Discrepancia) -> None:
        """Inserta o actualiza un registro de discrepancia."""
        tipo_str = (
            discrepancia.tipo_discrepancia.value
            if isinstance(discrepancia.tipo_discrepancia, TipoDiscrepancia)
            else str(discrepancia.tipo_discrepancia)
        ).strip().upper()
        tipo_final = tipo_str if tipo_str in self.VALID_TIPOS else "OTRO"

        sev_str = (
            discrepancia.severidad.value
            if isinstance(discrepancia.severidad, SeveridadDiscrepancia)
            else str(discrepancia.severidad)
        ).strip().upper()
        sev_final = sev_str if sev_str in self.VALID_SEVERIDADES else "WARNING"

        est_str = (
            discrepancia.estado.value
            if isinstance(discrepancia.estado, EstadoDiscrepancia)
            else str(discrepancia.estado)
        ).strip().upper()
        est_final = est_str if est_str in self.VALID_ESTADOS else "REQUIERE_REVISION"

        query = """
        INSERT INTO discrepancia (
            id_discrepancia, id_actividad, tipo_discrepancia, severidad,
            fuente_a_nombre, fuente_a_valor, fuente_b_nombre, fuente_b_valor,
            delta_valor, estado, justificacion_aclaratoria, usuario_revisor,
            fecha_deteccion, fecha_revision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_discrepancia) DO UPDATE SET
            id_actividad = excluded.id_actividad,
            tipo_discrepancia = excluded.tipo_discrepancia,
            severidad = excluded.severidad,
            fuente_a_nombre = excluded.fuente_a_nombre,
            fuente_a_valor = excluded.fuente_a_valor,
            fuente_b_nombre = excluded.fuente_b_nombre,
            fuente_b_valor = excluded.fuente_b_valor,
            delta_valor = excluded.delta_valor,
            estado = excluded.estado,
            justificacion_aclaratoria = excluded.justificacion_aclaratoria,
            usuario_revisor = excluded.usuario_revisor,
            fecha_revision = excluded.fecha_revision;
        """
        params = (
            discrepancia.id_discrepancia,
            discrepancia.id_actividad,
            tipo_final,
            sev_final,
            discrepancia.fuente_a_nombre,
            discrepancia.fuente_a_valor,
            discrepancia.fuente_b_nombre,
            discrepancia.fuente_b_valor,
            discrepancia.delta_valor,
            est_final,
            discrepancia.justificacion_aclaratoria,
            discrepancia.usuario_revisor,
            str(discrepancia.fecha_deteccion),
            str(discrepancia.fecha_revision) if discrepancia.fecha_revision else None,
        )
        self._conn.execute(query, params)

    @translate_sqlite_errors("Discrepancia")
    def save_batch(self, discrepancias: List[Discrepancia]) -> None:
        """Inserta o actualiza una colección de discrepancias."""
        for d in discrepancias:
            self.save(d)

    @translate_sqlite_errors("Discrepancia")
    def get_by_id(self, id_discrepancia: str) -> Optional[Discrepancia]:
        """Recupera una discrepancia por su UUID."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM discrepancia WHERE id_discrepancia = ?;",
            (id_discrepancia,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    @translate_sqlite_errors("Discrepancia")
    def list_by_actividad(self, id_actividad: str) -> List[Discrepancia]:
        """Recupera todas las discrepancias detectadas en una actividad."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM discrepancia
            WHERE id_actividad = ?
            ORDER BY fecha_deteccion DESC;
            """,
            (id_actividad,),
        )
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("Discrepancia")
    def list_pendientes(
        self, severidad: Optional[str] = None
    ) -> List[Discrepancia]:
        """Recupera discrepancias activas pendientes de revisión humana."""
        if severidad is not None:
            sev_norm = severidad.strip().upper()
            query = """
            SELECT * FROM discrepancia
            WHERE estado IN ('REQUIERE_REVISION', 'EN_REVISION') AND severidad = ?
            ORDER BY fecha_deteccion DESC;
            """
            params = (sev_norm,)
        else:
            query = """
            SELECT * FROM discrepancia
            WHERE estado IN ('REQUIERE_REVISION', 'EN_REVISION')
            ORDER BY fecha_deteccion DESC;
            """
            params = ()

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("Discrepancia")
    def registrar_revision(
        self,
        id_discrepancia: str,
        nuevo_estado: str,
        justificacion: str,
        usuario_revisor: str,
    ) -> None:
        """Asienta la resolución o aclaración humana de la discrepancia.

        Conserva estrictamente inalterados los datos de fuente_a_valor y fuente_b_valor.
        """
        est_norm = nuevo_estado.strip().upper()
        est_final = est_norm if est_norm in self.VALID_ESTADOS else "ACLARADO"

        query = """
        UPDATE discrepancia
        SET estado = ?,
            justificacion_aclaratoria = ?,
            usuario_revisor = ?,
            fecha_revision = ?
        WHERE id_discrepancia = ?;
        """
        params = (
            est_final,
            justificacion,
            usuario_revisor,
            datetime.now().isoformat(),
            id_discrepancia,
        )
        self._conn.execute(query, params)

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Discrepancia:
        """Mapea una fila relacional a la entidad Discrepancia."""
        return Discrepancia(
            id_discrepancia=row["id_discrepancia"],
            id_actividad=row["id_actividad"],
            tipo_discrepancia=row["tipo_discrepancia"],
            severidad=row["severidad"],
            fuente_a_nombre=row["fuente_a_nombre"],
            fuente_a_valor=row["fuente_a_valor"],
            fuente_b_nombre=row["fuente_b_nombre"],
            fuente_b_valor=row["fuente_b_valor"],
            delta_valor=row["delta_valor"],
            estado=row["estado"],
            justificacion_aclaratoria=row["justificacion_aclaratoria"],
            usuario_revisor=row["usuario_revisor"],
            fecha_deteccion=row["fecha_deteccion"],
            fecha_revision=row["fecha_revision"],
        )
