"""app.application.commands.calidad_commands

Comandos de intención para el contexto de Calidad Institucional BICU.
Gobernado bajo el principio inviolable DETECTAR ≠ CORREGIR (Regla RN-C07).
"""

from typing import Optional
from pydantic import BaseModel, Field


class EvaluarCalidadActividadCommand(BaseModel):
    """Comando para ordenar la evaluación exhaustiva de calidad sobre una actividad.
    
    CONTRATO DRY_RUN VS PERSISTENCIA:
    - dry_run = True: Evaluación puramente diagnóstica en memoria.
      CERO operaciones de escritura (INSERT/UPDATE) en SQLite. Prevalece sobre persistir_discrepancias.
    - dry_run = False y persistir_discrepancias = True: Persiste discrepancias detectadas en la tabla 'discrepancia'
      y actualiza marcas operativas en 'participacion' dentro de una transacción atómica.
    - dry_run = False y persistir_discrepancias = False: Actualiza marcas operativas en 'participacion'
      sin insertar filas en la tabla 'discrepancia'.
    """
    id_actividad: str = Field(..., description="UUID de la actividad anfitriona a evaluar.")
    persistir_discrepancias: bool = Field(
        default=True,
        description="Si True y dry_run=False, persiste hallazgos elegibles en la tabla 'discrepancia'."
    )
    dry_run: bool = Field(
        default=False,
        description="Si True, ejecuta la evaluación puramente en memoria garantizando CERO escrituras."
    )
    fuente_archivo_asistencia: Optional[str] = Field(
        default=None,
        description="Ruta o nombre del archivo de lista de asistencia para contextualización."
    )
    fuente_archivo_informe: Optional[str] = Field(
        default=None,
        description="Ruta o nombre del archivo de informe narrativo para contrastar fuentes."
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
    }
