"""
app.parsers.base_parser

Estructuras de datos y clases base para extracción de fuentes reales:
- Informe Semanal (Word)
- Listas de asistencia físicas / escaneadas
- Matrices oficiales (Excel)
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult


class RawActivityData(BaseModel):
    """Datos crudos extraídos de un informe institucional."""
    nombre_actividad: str
    departamento_institucional: Optional[str] = None
    mes: Optional[str] = None
    semana: Optional[str] = None
    sede: Optional[str] = None
    departamento: Optional[str] = None
    municipio: Optional[str] = None
    eje_estrategico: Optional[str] = None
    tipo_actividad: Optional[str] = None
    fecha: Optional[str] = None
    horario: Optional[str] = None
    fuente_origen: Optional[str] = None
    imagenes_incrustadas_detectadas: int = 0


class RawParticipantRow(BaseModel):
    """Fila cruda individual extraída de una lista de asistencia."""
    numero_fila: int
    hoja: int = 1
    nombre_completo: str
    sexo: Optional[str] = None
    cedula: Optional[str] = None
    edad: Optional[Union[int, str]] = None
    carrera: Optional[str] = None
    categoria: Optional[str] = None
    area: Optional[str] = None
    telefono: Optional[str] = None
    etnia: Optional[str] = None
    firma_presente: bool = False
    observaciones: Optional[str] = None
    fuente_origen: Optional[str] = None


class RawAttendanceSheetData(BaseModel):
    """Datos crudos del encabezado y filas de una lista de asistencia."""
    nombre_actividad: str
    fecha: Optional[str] = None
    horario: Optional[str] = None
    sede: Optional[str] = None
    departamento: Optional[str] = None
    municipio: Optional[str] = None
    filas: List[RawParticipantRow] = Field(default_factory=list)
    fuente_origen: Optional[str] = None


class ParsedAttendanceResult(BaseModel):
    """
    Resultado del parsing y normalización de una lista de asistencia.
    
    Regla obligatoria (Corrección 1):
    Cada fila de asistencia se conserva como una participación y una persona independiente.
    NO hay deduplicación ni unificación de identidades en esta fase.
    """
    datos_asistencia: Dict[str, Any]
    personas: List[Person]
    participaciones: List[Participation]
    validaciones: List[ValidationResult]
