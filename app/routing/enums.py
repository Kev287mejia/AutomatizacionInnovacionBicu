"""
app.routing.enums

Enumeraciones institucionales para el enrutamiento a matrices oficiales:
- MatrizDestino: identifica las matrices oficiales de salida y las cubetas de control.
- SubtipoInstitucional: rol institucional específico dentro de la matriz conjunta Académicos y Administrativos.
"""

from enum import Enum


class MatrizDestino(str, Enum):
    """
    Identificador de las matrices oficiales de salida y las cubetas de control.
    
    Matrices Oficiales:
    - CONSOLIDADO: Matriz 1 (Agregación a nivel de actividad; no de participantes).
    - ESTUDIANTES: Matriz 2 (Participantes en rol estudiantil).
    - ACADEMICOS_ADMINISTRATIVOS: Matriz 3 (Docentes y personal administrativo / no docente).
    - COLABORADORES: Matriz 4 (Aliados, ponentes y colaboradores externos).
    - BENEFICIADOS: Matriz 5 (Protagonistas beneficiados y pobladores generales).
    
    Cubetas de Control / Aislamiento:
    - COLA_REVISION: Participaciones con categoría DESCONOCIDO o no determinable.
    - BLOQUEADOS: Participaciones afectadas por errores críticos o referencias huérfanas.
    """
    CONSOLIDADO = "CONSOLIDADO"
    ESTUDIANTES = "ESTUDIANTES"
    ACADEMICOS_ADMINISTRATIVOS = "ACADEMICOS_ADMINISTRATIVOS"
    COLABORADORES = "COLABORADORES"
    BENEFICIADOS = "BENEFICIADOS"
    COLA_REVISION = "COLA_REVISION"
    BLOQUEADOS = "BLOQUEADOS"


class SubtipoInstitucional(str, Enum):
    """
    Subtipo institucional específico para participantes enrutados hacia la matriz
    conjunta de Académicos y Administrativos.
    """
    ACADEMICO = "ACADEMICO"
    ADMINISTRATIVO = "ADMINISTRATIVO"
    NO_APLICA = "NO_APLICA"
