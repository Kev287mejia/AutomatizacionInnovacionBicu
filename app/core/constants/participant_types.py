"""
app.core.constants.participant_types

Definición de enumeraciones y constantes institucionales del sistema:
- Categorías de participación (base para el routing a las 5 matrices).
- Niveles de validación (ERROR, WARNING, INFO, REVISION).
- Niveles de jerarquía de identidad (Niveles 1 a 4).
"""

from enum import Enum


class CategoriaParticipacion(str, Enum):
    """
    Categoría del protagonista para UNA participación específica.
    Determina a qué matriz Excel oficial se enruta esta fila.
    
    Reglas de routing:
    - ESTUDIANTE -> Matriz de Estudiantes
    - DOCENTE -> Matriz de Académicos y Administrativos (subtipo Académico)
    - ADMINISTRATIVO -> Matriz de Académicos y Administrativos (subtipo Administrativo)
    - NO_DOCENTE -> Matriz de Académicos y Administrativos (subtipo Administrativo)
    - POBLADOR_GENERAL -> Matriz de Protagonistas Beneficiados
    - BENEFICIADO -> Matriz de Protagonistas Beneficiados
    - COLABORADOR -> Matriz de Colaboradores
    - DESCONOCIDO -> Cola de REVISIÓN humana
    """
    ESTUDIANTE = "ESTUDIANTE"
    DOCENTE = "DOCENTE"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    NO_DOCENTE = "NO_DOCENTE"
    POBLADOR_GENERAL = "POBLADOR_GENERAL"
    BENEFICIADO = "BENEFICIADO"
    COLABORADOR = "COLABORADOR"
    DESCONOCIDO = "DESCONOCIDO"


class NivelValidacion(str, Enum):
    """
    Nivel de severidad de un hallazgo o resultado de validación.
    """
    ERROR = "ERROR"        # Bloquea exportación de esa fila o entidad
    WARNING = "WARNING"    # Permite continuar pero alerta falta de dato o inconsistencia
    INFO = "INFO"          # Informativo (trazabilidad)
    REVISION = "REVISION"  # Requiere decisión o confirmación de un operador humano


class NivelConfianzaIdentidad(int, Enum):
    """
    Jerarquía de identificación de personas (Regla C-09):
    1: Cédula oficial (Identificación definitiva)
    2: Número único institucional (Identificación definitiva)
    3: Otro ID institucional confirmado (Identificación definitiva)
    4: Coincidencia candidata por datos secundarios (Nunca fusión automática)
    """
    NIVEL_1_CEDULA = 1
    NIVEL_2_NUMERO_UNICO = 2
    NIVEL_3_OTRO_ID = 3
    NIVEL_4_CANDIDATO = 4
