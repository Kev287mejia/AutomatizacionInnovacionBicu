"""DTOs de entrada (Input Models) para la capa de Aplicación - Sistema BICU.

Modelos de transporte de datos agnósticos a fuentes externas (Excel, Word, GUI),
diseñados para ingresar información a los casos de uso sin contener lógica de negocio.
"""

from typing import Optional
from pydantic import BaseModel, Field


class FilaParticipanteIngestaDTO(BaseModel):
    """Representa una fila leída en bruto desde una lista de asistencia externa.

    Contiene exclusivamente los valores textuales tal como figuran en el documento de origen.
    No ejecuta normalización ni ruteo de negocio.
    """

    nombre_fuente: str = Field(
        ...,
        description="Nombre del participante tal como figura en la lista externa."
    )
    cedula_fuente: Optional[str] = Field(
        default=None,
        description="Cédula provista en la lista (nullable; si no existe, permanece en None)."
    )
    numero_institucional_fuente: Optional[str] = Field(
        default=None,
        description="Carné o número de registro institucional provisto."
    )
    sexo_fuente: Optional[str] = Field(
        default=None,
        description="Dato textual de sexo registrado en la lista."
    )
    carrera_cargo_fuente: Optional[str] = Field(
        default=None,
        description="Carrera, departamento o cargo declarado."
    )
    etnia_fuente: Optional[str] = Field(
        default=None,
        description="Etnia o pueblo originario declarado."
    )
    categoria_sugerida: Optional[str] = Field(
        default=None,
        description="Categoría preliminar inferida por la fuente (ej. Estudiante, Docente)."
    )
    observaciones_fuente: Optional[str] = Field(
        default=None,
        description="Anotaciones marginales de la lista de asistencia."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class PartidaPresupuestariaDTO(BaseModel):
    """Línea de presupuesto asociada a la planificación de una actividad."""

    rubro: str = Field(
        ...,
        description="Denominación del rubro o gasto presupuestario."
    )
    cantidad: int = Field(
        default=1,
        ge=0,
        description="Cantidad de unidades presupuestadas."
    )
    costo_unitario: float = Field(
        default=0.0,
        ge=0.0,
        description="Costo unitario en moneda institucional."
    )
    subtotal: float = Field(
        default=0.0,
        ge=0.0,
        description="Subtotal calculado para este rubro."
    )
    fuente_financiamiento: Optional[str] = Field(
        default=None,
        description="Origen de los fondos (ej. Fondos Propios, Cooperación Externa)."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class DetalleActividadInformeDTO(BaseModel):
    """Parámetros de asociación de una actividad a un informe semanal."""

    id_actividad: str = Field(
        ...,
        description="Identificador UUID de la actividad a incluir."
    )
    orden_secuencia: int = Field(
        default=1,
        ge=1,
        description="Posición u orden de presentación en el documento."
    )
    incluir_product_a: bool = Field(
        default=True,
        description="Bandera de inclusión en Product A (Técnico Horizontal)."
    )
    incluir_product_b: bool = Field(
        default=True,
        description="Bandera de inclusión en Product B (Ejecutivo Vertical)."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
