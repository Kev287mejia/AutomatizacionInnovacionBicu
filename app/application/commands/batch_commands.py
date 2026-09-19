"""app.application.commands.batch_commands

Comando para el procesamiento por lote de carpetas de documentos Word (.docx)
de actividades institucionales BICU.

Reglas arquitectónicas:
- Application Layer. No importa sqlite3, python-docx ni openpyxl.
- Inmutable (frozen=True) por diseño CQRS.
- Decisiones aprobadas en Fase 26.9 Bloque 3:
  * P-01: Exportación consolidada al final del lote.
  * P-02: M2–M5 como plantillas limpias si no hay nominales.
  * P-03: Advertir posibles duplicados (heurística GAP-3) sin bloquear.
  * P-04: Manifest JSON externo persistente.
  * P-06: Sin migraciones; schema v001 permanece intacto.
  * P-07: Subcarpeta output/<batch_id>/ por ejecución.
"""

from pathlib import Path
from typing import Optional, Union
from pydantic import BaseModel, Field

from app.application.dto.export_dtos import PoliticaExportacionRevision


class IngestarCarpetaWordCommand(BaseModel):
    """Comando para iniciar el procesamiento por lote de una carpeta de DOCX.

    Orchestra:
      1. Extracción e ingesta individual de cada DOCX (IngestarActividadDesdeWordUseCase).
      2. Pipeline Quality + Routing (ProcesarPipelineActividadUseCase) por actividad.
      3. Exportación consolidada al final del lote (ExportarMatricesPeriodoUseCase).

    Comportamiento de atomicidad:
      - Por archivo: transacción individual. Fallo → rollback de ESE archivo.
      - Por lote: éxito parcial. Un fallo no detiene los demás archivos.

    Nota GAP-3 (idempotencia):
      Si advertir_posibles_duplicados=True, el sistema emitirá una advertencia
      heurística cuando detecte que el nombre de un archivo ya existe en el
      historial del lote. Esto NO es idempotencia formal; el schema v001 no
      tiene restricción UNIQUE por documento. No se bloquea ningún archivo
      automáticamente por esta razón.

    Nota dry_run:
      Cuando dry_run=True, se garantiza:
        - cero escrituras en SQLite (actividades, personas, participaciones,
          evidencias, discrepancias);
        - cero archivos XLSX generados;
        - cero manifest persistente.
      El BatchResultadoDTO se produce normalmente en memoria.
    """
    carpeta_origen: Union[str, Path] = Field(
        ...,
        description="Ruta a la carpeta que contiene los archivos DOCX a procesar."
    )
    patron_glob: str = Field(
        default="*.docx",
        description="Patrón de búsqueda de archivos. Por defecto '*.docx' (no recursivo)."
    )
    recursivo: bool = Field(
        default=False,
        description="Si True, explora subcarpetas. Por defecto False."
    )
    # --- Exportación (P-01: consolidada al final del lote) ---
    exportar_matrices: bool = Field(
        default=True,
        description=(
            "Si True, ejecuta ExportarMatricesPeriodoUseCase al finalizar el lote "
            "con todas las actividades ingresadas (decisión P-01: exportación consolidada)."
        )
    )
    carpeta_salida: Union[str, Path] = Field(
        default="output",
        description=(
            "Directorio raíz de destino. Los XLSX se guardarán en una subcarpeta "
            "output/<batch_id>/ exclusiva de este lote (decisión P-07)."
        )
    )
    politica_revision: PoliticaExportacionRevision = Field(
        default=PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION,
        description="Política OPEN-02 de tratamiento de registros en revisión."
    )
    # --- Control y simulación ---
    dry_run: bool = Field(
        default=False,
        description=(
            "Si True, ejecuta el flujo completo en memoria sin ninguna escritura persistente "
            "(cero SQLite, cero XLSX, cero manifest físico)."
        )
    )
    permitir_fixtures_test_only: bool = Field(
        default=False,
        description="Bandera de testing para entornos con fixtures simuladas."
    )
    carpeta_templates: Optional[str] = Field(
        default=None,
        description="Ruta personalizada a plantillas oficiales. None = usar ruta por defecto."
    )
    carpeta_fixtures: Optional[str] = Field(
        default=None,
        description="Ruta personalizada a fixtures (solo para testing)."
    )
    # --- GAP-3 workaround ---
    advertir_posibles_duplicados: bool = Field(
        default=True,
        description=(
            "Si True, emite advertencia heurística cuando el nombre de un archivo "
            "coincide con el de otro archivo ya procesado en este lote. "
            "No bloquea el procesamiento. No modifica el schema. "
            "No garantiza idempotencia formal (GAP-3 abierto)."
        )
    )

    model_config = {
        "frozen": True,
        "str_strip_whitespace": True,
        "arbitrary_types_allowed": True,
    }
