"""Adaptador SQLite para el puerto IParticipacionRepository.

Implementa la persistencia de la entidad asociativa Participación,
consultas multidireccionales y soporte de transacciones para guardado en lote.
"""

import sqlite3
from typing import List, Optional

from app.core.constants.participant_types import CategoriaParticipacion
from app.core.models.participation import Participation
from app.core.ports.participacion_repository import IParticipacionRepository
from app.infrastructure.persistence.repositories.error_handler import translate_sqlite_errors


class SQLiteParticipacionRepository(IParticipacionRepository):
    """Adaptador de persistencia SQLite para la entidad asociativa Participación."""

    VALID_ESTAMENTOS = {
        "ESTUDIANTE",
        "DOCENTE",
        "ADMINISTRATIVO",
        "COLABORADOR",
        "BENEFICIADO",
    }
    VALID_MATRICES = {"M2", "M3", "M4", "M5", "COLA_REVISION"}

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Inicializa el repositorio con una conexión activa a SQLite."""
        self._conn = connection

    @translate_sqlite_errors("Participacion")
    def save(self, participacion: Participation) -> None:
        """Inserta o actualiza un registro de participación."""
        query, params = self._build_insert_query_and_params(participacion)
        self._conn.execute(query, params)

    @translate_sqlite_errors("Participacion")
    def save_batch(self, participaciones: List[Participation]) -> None:
        """Inserta o actualiza una lista de participaciones de forma transaccional."""
        for p in participaciones:
            self.save(p)

    @translate_sqlite_errors("Participacion")
    def get_by_id(self, id_participacion: str) -> Optional[Participation]:
        """Recupera una participación por su UUID."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM participacion WHERE id_participacion = ?;",
            (id_participacion,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    @translate_sqlite_errors("Participacion")
    def get_by_actividad(self, id_actividad: str) -> List[Participation]:
        """Recupera todas las participaciones asociadas a una actividad."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM participacion WHERE id_actividad = ?;",
            (id_actividad,),
        )
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("Participacion")
    def get_by_persona(self, id_persona: str) -> List[Participation]:
        """Recupera todas las actividades en que ha participado una persona."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM participacion WHERE id_persona = ?;",
            (id_persona,),
        )
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("Participacion")
    def get_by_actividad_and_persona(
        self, id_actividad: str, id_persona: str
    ) -> Optional[Participation]:
        """Recupera el vínculo unívoco entre una actividad y una persona."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM participacion WHERE id_actividad = ? AND id_persona = ?;",
            (id_actividad, id_persona),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    @translate_sqlite_errors("Participacion")
    def list_by_matriz_destino(
        self, matriz_destino: str, id_actividad: Optional[str] = None
    ) -> List[Participation]:
        """Filtra participaciones según la matriz oficial de destino asignada."""
        matriz_norm = matriz_destino.strip().upper()
        if id_actividad is not None:
            query = """
            SELECT * FROM participacion
            WHERE matriz_destino = ? AND id_actividad = ?;
            """
            params = (matriz_norm, id_actividad)
        else:
            query = "SELECT * FROM participacion WHERE matriz_destino = ?;"
            params = (matriz_norm,)

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("Participacion")
    def list_requieren_revision(
        self, id_actividad: Optional[str] = None
    ) -> List[Participation]:
        """Recupera participaciones que requieren aclaración o revisión humana."""
        if id_actividad is not None:
            query = """
            SELECT * FROM participacion
            WHERE requiere_revision = 1 AND id_actividad = ?;
            """
            params = (id_actividad,)
        else:
            query = "SELECT * FROM participacion WHERE requiere_revision = 1;"
            params = ()

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("Participacion")
    def count_by_actividad(self, id_actividad: str) -> int:
        """Retorna la cantidad total de participantes en una actividad."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM participacion WHERE id_actividad = ?;",
            (id_actividad,),
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    def _build_insert_query_and_params(self, p: Participation):
        """Construye la consulta parametrizada y tupla de valores para inserción/actualización."""
        # Normalizar estamento declarado para cumplir CHECK de base de datos
        cat_str = (
            p.categoria_participacion.value
            if isinstance(p.categoria_participacion, CategoriaParticipacion)
            else str(p.categoria_participacion)
        ).strip().upper()

        if cat_str == "DESCONOCIDO" or (p.matriz_destino and p.matriz_destino.strip().upper() == "COLA_REVISION"):
            estamento_final = "BENEFICIADO"
            matriz_dest = "COLA_REVISION"
            req_rev = 1
        elif cat_str in self.VALID_ESTAMENTOS:
            estamento_final = cat_str
            matriz_dest = p.matriz_destino.strip().upper() if p.matriz_destino else None
            req_rev = 1 if p.requiere_revision else 0
        elif cat_str in ("PROTAGONISTA", "BENEFICIARIO", "COMUNIDAD"):
            estamento_final = "BENEFICIADO"
            matriz_dest = p.matriz_destino.strip().upper() if p.matriz_destino else None
            req_rev = 1 if p.requiere_revision else 0
        elif cat_str in ("DOCENTE_HORARIO", "DOCENTE_REGULAR", "PROFESOR"):
            estamento_final = "DOCENTE"
            matriz_dest = p.matriz_destino.strip().upper() if p.matriz_destino else None
            req_rev = 1 if p.requiere_revision else 0
        else:
            estamento_final = "BENEFICIADO"
            matriz_dest = "COLA_REVISION"
            req_rev = 1

        query = """
        INSERT INTO participacion (
            id_participacion, id_actividad, id_persona, estamento_declarado,
            es_beneficiado_rol, matriz_destino, rol_en_actividad, condicion_asistencia,
            carrera_o_cargo_actividad, archivo_fuente_origen, requiere_revision,
            motivo_revision, es_historico_preexistente
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_participacion) DO UPDATE SET
            id_actividad = excluded.id_actividad,
            id_persona = excluded.id_persona,
            estamento_declarado = excluded.estamento_declarado,
            es_beneficiado_rol = excluded.es_beneficiado_rol,
            matriz_destino = excluded.matriz_destino,
            rol_en_actividad = excluded.rol_en_actividad,
            condicion_asistencia = excluded.condicion_asistencia,
            carrera_o_cargo_actividad = excluded.carrera_o_cargo_actividad,
            archivo_fuente_origen = excluded.archivo_fuente_origen,
            requiere_revision = excluded.requiere_revision,
            motivo_revision = excluded.motivo_revision,
            es_historico_preexistente = excluded.es_historico_preexistente;
        """
        params = (
            p.id_participacion,
            p.id_actividad,
            p.id_persona,
            estamento_final,
            1 if p.es_beneficiado_rol else 0,
            matriz_dest,
            "ASISTENTE",
            "PRESENTE",
            p.observaciones,
            p.fuente_origen,
            req_rev,
            p.motivo_revision,
            1 if getattr(p, "es_historico_preexistente", 0) else 0,
        )
        return query, params

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Participation:
        """Mapea una fila relacional de SQLite al modelo de dominio Participation."""
        matriz_dest = row["matriz_destino"]
        if matriz_dest == "COLA_REVISION":
            cat_part = CategoriaParticipacion.DESCONOCIDO
        else:
            cat_part = row["estamento_declarado"]

        return Participation(
            id_participacion=row["id_participacion"],
            id_actividad=row["id_actividad"],
            id_persona=row["id_persona"],
            categoria_participacion=cat_part,
            es_beneficiado_rol=bool(row["es_beneficiado_rol"]) if "es_beneficiado_rol" in row.keys() else False,
            matriz_destino=row["matriz_destino"],
            fuente_origen=row["archivo_fuente_origen"],
            observaciones=row["carrera_o_cargo_actividad"],
            requiere_revision=bool(row["requiere_revision"]),
            motivo_revision=row["motivo_revision"],
            es_historico_preexistente=int(row["es_historico_preexistente"]) if "es_historico_preexistente" in row.keys() else 0,
        )
