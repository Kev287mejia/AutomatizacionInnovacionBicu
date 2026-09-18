"""DTOs de salida (Output Models / Proyecciones) para la capa de Aplicación - Sistema BICU.

Estructuras de transporte para comunicar resultados de casos de uso y consultas hacia
canales de presentación (GUI, reportes, bandejas de auditoría) sin acoplamiento a persistencia.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.models.validation_result import ValidationResult
from app.application.dto.input_dtos import DetalleActividadInformeDTO


class IngestaListaAsistenciaResultDTO(BaseModel):
    """Resultado consolidado del caso de uso de ingesta masiva de asistencias."""

    id_actividad: str = Field(
        ...,
        description="Identificador de la actividad procesada."
    )
    total_procesados: int = Field(
        ...,
        ge=0,
        description="Total de filas leídas de la lista de asistencia."
    )
    nuevas_personas_registradas: int = Field(
        ...,
        ge=0,
        description="Personas incorporadas por primera vez al SSOT."
    )
    personas_existentes_vinculadas: int = Field(
        ...,
        ge=0,
        description="Personas reconocidas previamente y asociadas a esta actividad."
    )
    participaciones_creadas: int = Field(
        ...,
        ge=0,
        description="Total de registros de participación persistidos."
    )
    participaciones_en_revision: int = Field(
        ...,
        ge=0,
        description="Participaciones marcadas con bandera de revisión humana."
    )
    hallazgos_validacion: List[ValidationResult] = Field(
        default_factory=list,
        description="Colección de advertencias o inconsistencias detectadas en la ingesta."
    )

    model_config = {
        "frozen": True,
    }


class EnrutarParticipacionesResultDTO(BaseModel):
    """Resultado consolidado del caso de uso de routing de una actividad."""

    id_actividad: str = Field(..., description="UUID de la actividad procesada.")
    total_participaciones: int = Field(..., ge=0, description="Total de participaciones evaluadas.")
    total_m2_estudiantes: int = Field(default=0, ge=0, description="Enrutados a M2 Estudiantes.")
    total_m3_academicos_admin: int = Field(default=0, ge=0, description="Enrutados a M3 Académicos y Administrativos.")
    total_m4_colaboradores: int = Field(default=0, ge=0, description="Enrutados a M4 Colaboradores.")
    total_m5_beneficiados: int = Field(default=0, ge=0, description="Enrutados a M5 Protagonistas Beneficiados.")
    total_cola_revision: int = Field(default=0, ge=0, description="Asignados a COLA_REVISION por categoría no determinable.")
    total_bloqueados: int = Field(default=0, ge=0, description="Aislados con estado BLOQUEADO por error crítico o referencia huérfana.")
    invariante_conservacion_valida: bool = Field(default=True, description="True si total_participaciones == suma de todas las categorías y bloqueados.")

    model_config = {
        "frozen": True,
    }


class ActividadResumenDTO(BaseModel):
    """Proyección ligera de actividad para listados y selectores de interfaz."""

    id_actividad: str = Field(..., description="UUID de la actividad.")
    nombre_actividad: str = Field(..., description="Nombre descriptivo de la actividad.")
    fecha_evento: Optional[str] = Field(default=None, description="Fecha de realización.")
    sede: Optional[str] = Field(default=None, description="Sede o recinto institucional.")
    total_participantes: int = Field(default=0, ge=0, description="Total de participantes registrados.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ActividadDetalleDTO(BaseModel):
    """Proyección exhaustiva de actividad para visualización completa."""

    id_actividad: str = Field(..., description="UUID de la actividad.")
    nombre_actividad_original: str = Field(..., description="Nombre original de origen.")
    nombre_actividad_oficial: Optional[str] = Field(default=None, description="Nombre normalizado u oficial.")
    fecha_evento: Optional[str] = Field(default=None, description="Fecha de ejecución.")
    sede: Optional[str] = Field(default=None, description="Sede o recinto.")
    departamento: Optional[str] = Field(default=None, description="Departamento geográfico.")
    municipio_evento: Optional[str] = Field(default=None, description="Municipio del evento.")
    programa: Optional[str] = Field(default=None, description="Programa institucional responsable.")
    ambito: Optional[str] = Field(default=None, description="Ámbito territorial.")
    tipo_evento: Optional[str] = Field(default=None, description="Tipo de evento.")
    eje_linea_estrategica: Optional[str] = Field(default=None, description="Línea estratégica.")
    informacion_adicional: Optional[str] = Field(default=None, description="Notas complementarias.")
    fuente_origen: Optional[str] = Field(default=None, description="Fuente documental de origen.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class PersonaResumenDTO(BaseModel):
    """Proyección básica de persona para autocompletado y coincidencias preliminares."""

    id_persona_interno: str = Field(..., description="UUID interno de la persona.")
    nombre_completo: str = Field(..., description="Nombre completo de la persona.")
    cedula: Optional[str] = Field(default=None, description="Cédula oficial (nullable).")
    numero_unico: Optional[str] = Field(default=None, description="Carné o código institucional.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class PersonaDetalleDTO(BaseModel):
    """Proyección completa bio-demográfica de una persona en el SSOT."""

    id_persona_interno: str = Field(..., description="UUID interno de la persona.")
    nombre_completo: str = Field(..., description="Nombre completo.")
    nombres: Optional[str] = Field(default=None, description="Nombres de pila.")
    apellidos: Optional[str] = Field(default=None, description="Apellidos.")
    cedula: Optional[str] = Field(default=None, description="Cédula oficial (nullable).")
    numero_unico: Optional[str] = Field(default=None, description="Carné institucional.")
    otro_id_institucional: Optional[str] = Field(default=None, description="Identificador secundario.")
    sexo_normalizado: Optional[str] = Field(default=None, description="Sexo normalizado (M/F).")
    fecha_nacimiento: Optional[str] = Field(default=None, description="Fecha de nacimiento.")
    edad: Optional[int] = Field(default=None, description="Edad en años.")
    etnia: Optional[str] = Field(default=None, description="Etnia o pueblo originario.")
    telefono: Optional[str] = Field(default=None, description="Teléfono de contacto.")
    departamento_persona: Optional[str] = Field(default=None, description="Departamento de procedencia.")
    municipio_persona: Optional[str] = Field(default=None, description="Municipio de procedencia.")
    discapacidad: Optional[str] = Field(default=None, description="Condición de discapacidad.")
    carrera_oficial: Optional[str] = Field(default=None, description="Carrera oficial estandarizada.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class ParticipacionDetalleDTO(BaseModel):
    """Proyección tabular de participante en una actividad con su clasificación y estado."""

    id_participacion: str = Field(..., description="UUID de la participación.")
    id_actividad: str = Field(..., description="UUID de la actividad asociada.")
    id_persona: str = Field(..., description="UUID de la persona asociada.")
    nombre_completo: str = Field(..., description="Nombre del participante.")
    cedula: Optional[str] = Field(default=None, description="Cédula oficial (nullable).")
    categoria: str = Field(..., description="Categoría en esta actividad (ej. ESTUDIANTE, BENEFICIADO).")
    matriz_destino: Optional[str] = Field(default=None, description="Matriz oficial asignada (M2..M5).")
    requiere_revision: bool = Field(default=False, description="Bandera de revisión humana.")
    motivo_revision: Optional[str] = Field(default=None, description="Motivo de la marca de revisión.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class EvidenciaVinculadaDTO(BaseModel):
    """Proyección de evidencia fotográfica o documental vinculada a una actividad."""

    id_evidencia: str = Field(..., description="UUID de la evidencia.")
    id_actividad: str = Field(..., description="UUID de la actividad asociada.")
    titulo: str = Field(..., description="Título de la evidencia.")
    tipo_evidencia: str = Field(..., description="Tipo de evidencia institucional.")
    orden_presentacion: int = Field(default=1, ge=1, description="Secuencia en informe Word.")
    seccion_informe: str = Field(default="GALERIA", description="Sección de destino ('FICHA_TECNICA', 'GALERIA').")
    ruta_archivo_relativa: Optional[str] = Field(default=None, description="Ruta relativa en bóveda.")
    hash_sha256: Optional[str] = Field(default=None, description="Hash de inalterabilidad SHA-256.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class DiscrepanciaDetalleDTO(BaseModel):
    """Proyección para la bandeja de auditoría pericial de discrepancias (DETECTAR ≠ CORREGIR)."""

    id_discrepancia: str = Field(..., description="UUID de la discrepancia.")
    id_actividad: str = Field(..., description="UUID de la actividad involucrada.")
    tipo: str = Field(..., description="Tipo estructural del hallazgo.")
    severidad: str = Field(..., description="Severidad (INFO, WARNING, ERROR).")
    fuente_a: str = Field(..., description="Nombre de la Fuente A.")
    valor_a: str = Field(..., description="Valor asentado en Fuente A.")
    fuente_b: str = Field(..., description="Nombre de la Fuente B.")
    valor_b: str = Field(..., description="Valor asentado en Fuente B.")
    delta: Optional[str] = Field(default=None, description="Divergencia matemática o cualitativa.")
    estado: str = Field(..., description="Estado pericial (REQUIERE_REVISION, ACLARADO, etc.).")
    justificacion: Optional[str] = Field(default=None, description="Aclaración humana asentada.")
    usuario_revisor: Optional[str] = Field(default=None, description="Identificador del auditor revisor.")
    fecha_deteccion: Optional[str] = Field(default=None, description="Momento de detección.")
    fecha_revision: Optional[str] = Field(default=None, description="Momento de revisión humana.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class InformeSemanalCompletoDTO(BaseModel):
    """Proyección de informe semanal consolidado con su secuencia de actividades."""

    id_informe_semanal: str = Field(..., description="UUID del informe semanal.")
    anio: int = Field(..., description="Año de ejecución.")
    mes: int = Field(..., description="Mes calendario.")
    numero_semana: int = Field(..., description="Semana operativa (1..5).")
    etiqueta_periodo: str = Field(..., description="Etiqueta del período.")
    departamento_responsable: str = Field(..., description="Área responsable.")
    sede_recinto: str = Field(..., description="Sede o recinto emisor.")
    detalles: List[DetalleActividadInformeDTO] = Field(
        default_factory=list,
        description="Secuencia ordenada de actividades asignadas."
    )
    ruta_product_a: Optional[str] = Field(default=None, description="Ruta Word Product A.")
    hash_sha256_product_a: Optional[str] = Field(default=None, description="Hash SHA-256 Product A.")
    ruta_product_b: Optional[str] = Field(default=None, description="Ruta Word Product B.")
    hash_sha256_product_b: Optional[str] = Field(default=None, description="Hash SHA-256 Product B.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class PlanificacionAsignadaDTO(BaseModel):
    """Proyección de planificación y presupuesto asignado a una actividad."""

    id_actividad: str = Field(..., description="UUID de la actividad asociada.")
    anio: int = Field(..., description="Año operativo.")
    mes: int = Field(..., description="Mes operativo (1..12).")
    semana: int = Field(..., description="Semana operativa (1..5).")
    meta_participantes: Optional[int] = Field(default=None, description="Meta proyectada de participantes.")
    total_presupuesto: float = Field(default=0.0, description="Presupuesto total calculado.")
    cantidad_partidas: int = Field(default=0, description="Cantidad de partidas presupuestarias desglosadas.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class DisenoMetodologicoAsignadoDTO(BaseModel):
    """Proyección de diseño metodológico asociado a una actividad formativa."""

    id_actividad: str = Field(..., description="UUID de la actividad asociada.")
    objetivo_general: str = Field(..., description="Objetivo pedagógico general.")
    horas_duracion: Optional[int] = Field(default=None, description="Duración en horas reloj.")
    facilitadores: Optional[str] = Field(default=None, description="Facilitadores o instructores asignados.")

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }


class InformeActividadRegistradoDTO(BaseModel):
    """Proyección de informe individual Word registrado para custodia institucional."""

    id_actividad: str = Field(..., description="UUID de la actividad asociada.")
    ruta_archivo_word: str = Field(..., description="Ruta de almacenamiento del informe Word.")
    hash_sha256: str = Field(..., description="Hash criptográfico SHA-256 de custodia.")
    total_participantes_declarados: Optional[int] = Field(
        default=None,
        description="Total de participantes reportados en el informe."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }

