"""
app.routing.models

Modelos de datos para representar decisiones de enrutamiento institucional,
agrupaciones hacia matrices oficiales y resúmenes de control.
"""

from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.routing.enums import MatrizDestino, SubtipoInstitucional


class EnrutamientoRegistro(BaseModel):
    """
    Representa la decisión de routing institucional tomada para una participación específica.
    
    Conserva referencias inmutables a las entidades originales de entrada, vinculando
    el destino oficial, subtipo, estado operativo y trazabilidad de hallazgos.
    """
    id_enrutamiento: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único de la decisión de enrutamiento."
    )
    participacion: Participation = Field(
        ...,
        description="Instancia inmutable de la participación evaluada."
    )
    persona: Person = Field(
        ...,
        description="Instancia inmutable de la persona asociada a la participación."
    )
    actividad: Activity = Field(
        ...,
        description="Instancia inmutable de la actividad en la que se participó."
    )
    matriz_destino: MatrizDestino = Field(
        ...,
        description="Matriz oficial de destino o cubeta de control/aislamiento asignada."
    )
    subtipo_institucional: SubtipoInstitucional = Field(
        default=SubtipoInstitucional.NO_APLICA,
        description="Subtipo de clasificación dentro de matrices compuestas (Académico vs Administrativo)."
    )
    estado_operativo: str = Field(
        ...,
        description="Estado operativo de la participación ('APTO', 'EN_REVISION', 'BLOQUEADO')."
    )
    motivo_enrutamiento: str = Field(
        ...,
        description="Explicación auditable de la regla que determinó el destino institucional."
    )
    hallazgos_asociados: List[ValidationResult] = Field(
        default_factory=list,
        description="Hallazgos de validación asociados a esta participación o sus entidades."
    )

    model_config = {
        "validate_assignment": True,
    }


class ResumenMatriz(BaseModel):
    """
    Resumen cuantitativo de control para una matriz o cubeta específica.
    """
    matriz: MatrizDestino = Field(..., description="Matriz evaluada.")
    total_participaciones: int = Field(default=0, description="Total de registros asignados.")
    total_aptos: int = Field(default=0, description="Registros con estado APTO.")
    total_en_revision: int = Field(default=0, description="Registros con estado EN_REVISION.")
    total_femenino: int = Field(default=0, description="Participantes de sexo femenino.")
    total_masculino: int = Field(default=0, description="Participantes de sexo masculino.")
    total_sexo_indefinido: int = Field(default=0, description="Participantes sin sexo normalizado confirmado.")
    subtipos: Dict[str, int] = Field(
        default_factory=dict,
        description="Desglose por subtipo institucional (ej. {'ACADEMICO': x, 'ADMINISTRATIVO': y})."
    )


class ResultadoRouting(BaseModel):
    """
    Contenedor global de las decisiones de routing para un lote de datos procesado.
    
    Garantiza formalmente la invariante:
    total_entrada == len(estudiantes) + len(academicos_administrativos) +
                     len(beneficiados) + len(colaboradores) +
                     len(cola_revision) + len(bloqueados)
    """
    estudiantes: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Participaciones asignadas a Matriz Oficial de Estudiantes."
    )
    academicos_administrativos: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Participaciones asignadas a Matriz Oficial de Académicos y Administrativos."
    )
    colaboradores: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Participaciones asignadas a Matriz Oficial de Colaboradores."
    )
    beneficiados: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Participaciones asignadas a Matriz Oficial de Protagonistas Beneficiados."
    )
    cola_revision: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Participaciones con categoría DESCONOCIDO o no clasificable (no se adivina matriz)."
    )
    bloqueados: List[EnrutamientoRegistro] = Field(
        default_factory=list,
        description="Participaciones con error crítico o inconsistencia referencial aisladas."
    )
    actividades: List[Activity] = Field(
        default_factory=list,
        description="Actividades evaluadas (una fila por actividad para Consolidado; no participan en la suma)."
    )
    total_entrada: int = Field(default=0, description="Total de participaciones recibidas a la entrada.")
    total_clasificadas: int = Field(default=0, description="Suma de participaciones en todas las cubetas.")
    invariante_valida: bool = Field(default=False, description="True si total_entrada == total_clasificadas.")
    resumenes: Dict[str, ResumenMatriz] = Field(
        default_factory=dict,
        description="Resúmenes cuantitativos indexados por nombre de matriz."
    )
