"""
app.parsers.attendance_parser

Parser para listas de asistencia físicas y escaneadas (Regla C-10, C-08, C-09, C-12).
Cumple estrictamente la CORRECCIÓN 1:
- Cada fila de asistencia representa una participación individual y se conserva como registro independiente.
- El parser crea objetos Person y Participation a partir de cada fila, pero NO resuelve identidad de personas.
- NO determina si dos filas pertenecen a la misma persona.
- NO fusiona personas ni elimina duplicados.
- La resolución de identidad y deduplicación quedan reservadas para fases posteriores.
"""

from typing import List, Dict, Any, Optional
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelConfianzaIdentidad, CategoriaParticipacion
from app.normalization.sex_normalizer import SexNormalizer
from app.normalization.identifier_normalizer import IdentifierNormalizer
from app.normalization.career_normalizer import CareerNormalizer
from app.normalization.category_normalizer import CategoryNormalizer
from app.normalization.name_normalizer import NameNormalizer
from app.normalization.age_date_normalizer import AgeDateNormalizer
from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow, ParsedAttendanceResult
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class AttendanceParser:
    """
    Parser para procesar listas de asistencia y transformarlas al modelo interno.
    """

    @classmethod
    def parse_sheet_data(
        cls,
        sheet_data: RawAttendanceSheetData,
        id_actividad: str,
        fuente: str = "asistencia_fisica"
    ) -> ParsedAttendanceResult:
        """
        Transforma datos crudos de una lista de asistencia hacia Person, Participation y ValidationResult.
        
        CORRECCIÓN 1:
        Conserva cada una de las filas como una participación individual.
        Crea un objeto Person por fila sin unificar ni deduplicar personas.
        """
        personas: List[Person] = []
        participaciones: List[Participation] = []
        validaciones: List[ValidationResult] = []

        for row in sheet_data.filas:
            # 1. Normalización de nombre
            nombre_norm, nombres, apellidos = NameNormalizer.normalizar(row.nombre_completo)

            # 2. Normalización de sexo según la fuente 'asistencia_fisica'
            sexo_norm, val_sexo = SexNormalizer.normalizar(
                valor_original=row.sexo,
                fuente=fuente
            )
            if val_sexo:
                validaciones.append(val_sexo)

            # 3. Normalización de cédula y detección de anomalías (ej: fecha en cédula)
            cedula_norm, val_cedula = IdentifierNormalizer.normalizar_cedula(
                valor_original=row.cedula,
                fuente=fuente
            )
            if val_cedula:
                validaciones.append(val_cedula)

            # 4. Normalización de edad y fecha de nacimiento (Regla: no inventar fecha si solo hay edad)
            edad_norm, fecha_norm, val_edad = AgeDateNormalizer.normalizar(
                edad_original=row.edad,
                fecha_nacimiento_original=None,
                fuente=fuente
            )
            if val_edad:
                validaciones.append(val_edad)

            # 5. Normalización de carrera (preservando los 3 niveles)
            carrera_norm, carrera_oficial, val_carrera = CareerNormalizer.normalizar(
                valor_original=row.carrera,
                fuente=fuente
            )
            if val_carrera:
                validaciones.append(val_carrera)

            # 6. Normalización de categoría
            cat_enum, cat_institucional, val_cat = CategoryNormalizer.normalizar(
                categoria_original=row.categoria,
                area_original=row.area,
                fuente=fuente
            )
            if val_cat:
                validaciones.append(val_cat)

            # 7. Crear Person (una por fila - Corrección 1: sin deduplicación)
            persona = Person(
                nombre_completo=nombre_norm or row.nombre_completo,
                nombres=nombres,
                apellidos=apellidos,
                cedula=cedula_norm,  # Si fue fecha o vacía, es None
                sexo_original=row.sexo,
                sexo_fuente=fuente,
                sexo_normalizado=sexo_norm,
                edad=edad_norm,
                fecha_nacimiento=fecha_norm,
                carrera_original=row.carrera,
                carrera_normalizada=carrera_norm,
                carrera_oficial=carrera_oficial,  # None en esta fase
                etnia=row.etnia,
                telefono=row.telefono,
                fuente_origen=row.fuente_origen or fuente
            )
            personas.append(persona)

            # Vincular ID de referencia a las validaciones de la fila
            for v_item in (val_sexo, val_cedula, val_edad, val_carrera, val_cat):
                if v_item and not v_item.id_referencia:
                    v_item.id_referencia = persona.id_persona_interno

            # Determinar nivel de confianza de identidad según jerarquía C-09
            if cedula_norm:
                nivel_confianza = NivelConfianzaIdentidad.NIVEL_1_CEDULA.value
            else:
                nivel_confianza = NivelConfianzaIdentidad.NIVEL_4_CANDIDATO.value

            # Determinar si requiere revisión humana
            requiere_rev = False
            motivos = []
            if val_cedula and val_cedula.codigo in ("VAL_CEDULA_FECHA", "VAL_CEDULA_VACIA", "VAL_CEDULA_FORMATO_DUDOSO"):
                requiere_rev = True
                motivos.append(val_cedula.mensaje)
            if val_carrera and val_carrera.codigo in ("VAL_CARRERA_AMBIGUA", "VAL_CARRERA_ABREVIADA"):
                requiere_rev = True
                motivos.append(val_carrera.mensaje)
            if val_cat and val_cat.codigo in ("VAL_CATEGORIA_DESCONOCIDA", "VAL_CATEGORIA_AUSENTE"):
                requiere_rev = True
                motivos.append(val_cat.mensaje)

            # 8. Crear Participation vinculada a la actividad y a la persona
            obs_part = []
            if row.area:
                obs_part.append(f"Área: {row.area}")
            if row.observaciones:
                obs_part.append(row.observaciones)
            if cat_institucional:
                obs_part.append(f"Clasificación preliminar: {cat_institucional}")

            participacion = Participation(
                id_actividad=id_actividad,
                id_persona=persona.id_persona_interno,
                categoria_participacion=cat_enum,
                nivel_confianza_identidad=nivel_confianza,
                fuente_origen=row.fuente_origen or fuente,
                observaciones=" | ".join(obs_part) if obs_part else None,
                requiere_revision=requiere_rev,
                motivo_revision="; ".join(motivos) if motivos else None
            )
            participaciones.append(participacion)

        datos_asist = {
            "nombre_actividad_asistencia": sheet_data.nombre_actividad,
            "fecha_evento": sheet_data.fecha,
            "horario": sheet_data.horario,
            "sede": sheet_data.sede,
            "departamento": sheet_data.departamento,
            "municipio_evento": sheet_data.municipio,
            "total_participaciones_extraidas": len(participaciones),
            "fuente_origen": sheet_data.fuente_origen or fuente
        }

        return ParsedAttendanceResult(
            datos_asistencia=datos_asist,
            personas=personas,
            participaciones=participaciones,
            validaciones=validaciones
        )
