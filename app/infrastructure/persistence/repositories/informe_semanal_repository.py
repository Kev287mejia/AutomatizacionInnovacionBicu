"""Adaptador SQLite para el puerto IInformeSemanalRepository.

Implementa la persistencia de informes consolidados periódicos de recinto
y sus secuencias de actividades incluidas en `detalle_informe_semanal`.
"""

import sqlite3
from typing import List, Optional

from app.core.models.weekly_report import DetalleInformeSemanal, InformeSemanal
from app.core.ports.informe_semanal_repository import IInformeSemanalRepository
from app.infrastructure.persistence.repositories.error_handler import translate_sqlite_errors


class SQLiteInformeSemanalRepository(IInformeSemanalRepository):
    """Adaptador de persistencia SQLite para el agregado Informe Semanal."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Inicializa el repositorio con una conexión activa a SQLite."""
        self._conn = connection

    @translate_sqlite_errors("InformeSemanal")
    def save(
        self,
        informe: InformeSemanal,
        detalles: Optional[List[DetalleInformeSemanal]] = None,
    ) -> None:
        """Inserta o actualiza un informe semanal y opcionalmente sus detalles."""
        query_informe = """
        INSERT INTO informe_semanal (
            id_informe_semanal, anio, mes, numero_semana, etiqueta_periodo,
            departamento_responsable, sede_recinto, ruta_product_a,
            hash_sha256_product_a, ruta_product_b, hash_sha256_product_b,
            fecha_generacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_informe_semanal) DO UPDATE SET
            anio = excluded.anio,
            mes = excluded.mes,
            numero_semana = excluded.numero_semana,
            etiqueta_periodo = excluded.etiqueta_periodo,
            departamento_responsable = excluded.departamento_responsable,
            sede_recinto = excluded.sede_recinto,
            ruta_product_a = excluded.ruta_product_a,
            hash_sha256_product_a = excluded.hash_sha256_product_a,
            ruta_product_b = excluded.ruta_product_b,
            hash_sha256_product_b = excluded.hash_sha256_product_b,
            fecha_generacion = excluded.fecha_generacion;
        """
        params_informe = (
            informe.id_informe_semanal,
            informe.anio,
            informe.mes,
            informe.numero_semana,
            informe.etiqueta_periodo,
            informe.departamento_responsable,
            informe.sede_recinto,
            informe.ruta_product_a,
            informe.hash_sha256_product_a,
            informe.ruta_product_b,
            informe.hash_sha256_product_b,
            str(informe.fecha_generacion),
        )
        self._conn.execute(query_informe, params_informe)

        if detalles is not None:
            query_detalle = """
            INSERT INTO detalle_informe_semanal (
                id_detalle, id_informe_semanal, id_actividad,
                orden_secuencia, incluir_product_a, incluir_product_b
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_informe_semanal, id_actividad) DO UPDATE SET
                orden_secuencia = excluded.orden_secuencia,
                incluir_product_a = excluded.incluir_product_a,
                incluir_product_b = excluded.incluir_product_b;
            """
            for d in detalles:
                params_detalle = (
                    d.id_detalle,
                    informe.id_informe_semanal,
                    d.id_actividad,
                    d.orden_secuencia,
                    1 if d.incluir_product_a else 0,
                    1 if d.incluir_product_b else 0,
                )
                self._conn.execute(query_detalle, params_detalle)

    @translate_sqlite_errors("InformeSemanal")
    def get_by_id(self, id_informe_semanal: str) -> Optional[InformeSemanal]:
        """Recupera un informe semanal por su UUID."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM informe_semanal WHERE id_informe_semanal = ?;",
            (id_informe_semanal,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        detalles = self.get_detalles(id_informe_semanal)
        return self._row_to_entity(row, detalles)

    @translate_sqlite_errors("InformeSemanal")
    def get_by_periodo(
        self, anio: int, mes: int, numero_semana: int, sede: str
    ) -> Optional[InformeSemanal]:
        """Recupera el informe semanal de un período y sede específicos."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM informe_semanal
            WHERE anio = ? AND mes = ? AND numero_semana = ? AND sede_recinto = ?;
            """,
            (anio, mes, numero_semana, sede.strip()),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        detalles = self.get_detalles(row["id_informe_semanal"])
        return self._row_to_entity(row, detalles)

    @translate_sqlite_errors("InformeSemanal")
    def list_all(self) -> List[InformeSemanal]:
        """Lista todos los informes semanales ordenados cronológicamente."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM informe_semanal ORDER BY fecha_generacion DESC;")
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("InformeSemanal")
    def get_detalles(
        self, id_informe_semanal: str
    ) -> List[DetalleInformeSemanal]:
        """Recupera los detalles ordenados de actividades de un informe semanal."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM detalle_informe_semanal
            WHERE id_informe_semanal = ?
            ORDER BY orden_secuencia ASC;
            """,
            (id_informe_semanal,),
        )
        rows = cursor.fetchall()
        return [
            DetalleInformeSemanal(
                id_detalle=r["id_detalle"],
                id_informe_semanal=r["id_informe_semanal"],
                id_actividad=r["id_actividad"],
                orden_secuencia=r["orden_secuencia"],
                incluir_product_a=bool(r["incluir_product_a"]),
                incluir_product_b=bool(r["incluir_product_b"]),
            )
            for r in rows
        ]

    @staticmethod
    def _row_to_entity(
        row: sqlite3.Row, detalles: Optional[List[DetalleInformeSemanal]] = None
    ) -> InformeSemanal:
        """Mapea una fila relacional a la entidad InformeSemanal."""
        return InformeSemanal(
            id_informe_semanal=row["id_informe_semanal"],
            anio=row["anio"],
            mes=row["mes"],
            numero_semana=row["numero_semana"],
            etiqueta_periodo=row["etiqueta_periodo"],
            departamento_responsable=row["departamento_responsable"],
            sede_recinto=row["sede_recinto"],
            ruta_product_a=row["ruta_product_a"],
            hash_sha256_product_a=row["hash_sha256_product_a"],
            ruta_product_b=row["ruta_product_b"],
            hash_sha256_product_b=row["hash_sha256_product_b"],
            fecha_generacion=row["fecha_generacion"],
            detalles=detalles,
        )
