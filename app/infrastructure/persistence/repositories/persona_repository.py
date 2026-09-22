"""Adaptador SQLite para el puerto IPersonaRepository.

Implementa la persistencia del agregado Persona (SSOT bio-demográfico)
respetando estrictamente la regla RN-C04 (cedula nullable sin colisión de unicidad).
"""

import sqlite3
from typing import List, Optional

from app.core.models.person import Person
from app.core.ports.persona_repository import IPersonaRepository
from app.infrastructure.persistence.repositories.error_handler import translate_sqlite_errors


class SQLitePersonaRepository(IPersonaRepository):
    """Adaptador de persistencia SQLite para el agregado Persona."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Inicializa el repositorio con una conexión activa a SQLite."""
        self._conn = connection

    @translate_sqlite_errors("Persona")
    def save(self, persona: Person) -> None:
        """Inserta o actualiza una entidad Persona en la tabla `persona`."""
        # Regla RN-C04: Si no posee cédula o es cadena vacía, debe almacenarse estrictamente como NULL
        cedula_sql = persona.cedula.strip() if (persona.cedula and persona.cedula.strip()) else None

        # Regla RN-C05: Sexo debe ser 'M' o 'F'
        sexo_candidato = (
            persona.sexo_normalizado
            or persona.sexo_original
            or ""
        ).strip().upper()
        if sexo_candidato in ("M", "MASCULINO", "VARON", "HOMBRE"):
            sexo_sql = "M"
            estado_id = "IDENTIDAD_CONFIRMADA"
        elif sexo_candidato in ("F", "FEMENINO", "MUJER"):
            sexo_sql = "F"
            estado_id = "IDENTIDAD_CONFIRMADA"
        else:
            sexo_sql = "M"  # Fallback técnico para satisfacer CHECK(sexo IN ('M', 'F'))
            estado_id = "IDENTIDAD_NO_RESUELTA"

        query = """
        INSERT INTO persona (
            id_persona_interno, cedula, numero_institucional, otro_documento,
            nombre_completo, nombres, apellidos, sexo, fecha_nacimiento,
            edad_declarada, etnia, departamento_residencia, municipio_residencia,
            condicion_discapacidad, telefono, estado_identidad
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_persona_interno) DO UPDATE SET
            cedula = excluded.cedula,
            numero_institucional = excluded.numero_institucional,
            otro_documento = excluded.otro_documento,
            nombre_completo = excluded.nombre_completo,
            nombres = excluded.nombres,
            apellidos = excluded.apellidos,
            sexo = excluded.sexo,
            fecha_nacimiento = excluded.fecha_nacimiento,
            edad_declarada = excluded.edad_declarada,
            etnia = excluded.etnia,
            departamento_residencia = excluded.departamento_residencia,
            municipio_residencia = excluded.municipio_residencia,
            condicion_discapacidad = excluded.condicion_discapacidad,
            telefono = excluded.telefono,
            estado_identidad = excluded.estado_identidad;
        """
        params = (
            persona.id_persona_interno,
            cedula_sql,
            persona.numero_unico,
            persona.otro_id_institucional,
            persona.nombre_completo,
            persona.nombres,
            persona.apellidos,
            sexo_sql,
            str(persona.fecha_nacimiento) if persona.fecha_nacimiento else None,
            persona.edad,
            persona.etnia,
            persona.departamento_persona,
            persona.municipio_persona,
            persona.discapacidad or "Ninguna",
            persona.telefono,
            estado_id,
        )
        self._conn.execute(query, params)

    @translate_sqlite_errors("Persona")
    def get_by_id(self, id_persona_interno: str) -> Optional[Person]:
        """Recupera una persona por su UUID interno."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM persona WHERE id_persona_interno = ?;",
            (id_persona_interno,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    @translate_sqlite_errors("Persona")
    def get_by_cedula(self, cedula: str) -> Optional[Person]:
        """Recupera una persona por su cédula oficial. Si es None o vacía, retorna None."""
        if not cedula or not cedula.strip():
            return None

        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM persona WHERE cedula = ?;", (cedula.strip(),))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    @translate_sqlite_errors("Persona")
    def get_by_numero_institucional(self, numero: str) -> Optional[Person]:
        """Recupera una persona por su carné institucional o código de empleado."""
        if not numero or not numero.strip():
            return None

        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM persona WHERE numero_institucional = ?;",
            (numero.strip(),),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    @translate_sqlite_errors("Persona")
    def search_by_nombre(self, nombre_query: str, limite: int = 10) -> List[Person]:
        """Busca personas cuyo nombre completo contenga la cadena provista."""
        if not nombre_query or not nombre_query.strip():
            return []

        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM persona WHERE nombre_completo LIKE ? LIMIT ?;",
            (f"%{nombre_query.strip()}%", limite),
        )
        rows = cursor.fetchall()
        return [self._row_to_entity(r) for r in rows]

    @translate_sqlite_errors("Persona")
    def exists(self, id_persona_interno: str) -> bool:
        """Comprueba existencia por UUID interno."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT 1 FROM persona WHERE id_persona_interno = ? LIMIT 1;",
            (id_persona_interno,),
        )
        return cursor.fetchone() is not None

    @translate_sqlite_errors("Persona")
    def count(self) -> int:
        """Retorna el total de personas en la base de datos."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM persona;")
        row = cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Person:
        """Mapea una fila relacional de SQLite al modelo de dominio Person."""
        estado_id = row["estado_identidad"] if "estado_identidad" in row.keys() else "IDENTIDAD_CONFIRMADA"
        sexo_val = None if estado_id == "IDENTIDAD_NO_RESUELTA" else row["sexo"]

        return Person(
            id_persona_interno=row["id_persona_interno"],
            nombre_completo=row["nombre_completo"],
            nombres=row["nombres"],
            apellidos=row["apellidos"],
            cedula=row["cedula"],  # Preserva None estricto si en SQLite es NULL (RN-C04)
            numero_unico=row["numero_institucional"],
            otro_id_institucional=row["otro_documento"],
            sexo_original=sexo_val,
            sexo_fuente="SQLITE_SSOT",
            sexo_normalizado=sexo_val,
            fecha_nacimiento=row["fecha_nacimiento"],
            edad=row["edad_declarada"],
            etnia=row["etnia"],
            telefono=row["telefono"],
            departamento_persona=row["departamento_residencia"],
            municipio_persona=row["municipio_residencia"],
            discapacidad=row["condicion_discapacidad"],
            carrera_original=None,
            carrera_normalizada=None,
            carrera_oficial=None,
            fuente_origen=None,
        )
