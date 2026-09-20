"""app.word_consolidator.ui.services.word_batch_service

Servicio de Aplicación para la Fachada UI del Procesamiento de Lotes Word (Fase 28.2).
Proporciona análisis previo (preflight check), descubrimiento no destructivo de archivos,
resolución de directorios y fábrica del orquestador batch sin acoplar la UI a la capa de infraestructura.
"""

from pathlib import Path
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.application.use_cases.batch.ingestar_carpeta_word import (
    IngestarCarpetaWordUseCase,
)
from app.application.use_cases.batch.procesar_pipeline_desde_word import (
    ProcesarPipelineDesdeWordUseCase,
)
from app.application.use_cases.exportacion.exportar_matrices_periodo import (
    ExportarMatricesPeriodoUseCase,
)
from app.application.use_cases.ingestar_actividad_desde_word import (
    IngestarActividadDesdeWordUseCase,
)
from app.application.use_cases.pipeline.procesar_pipeline_actividad import (
    ProcesarPipelineActividadUseCase,
)
from app.core.ports.unit_of_work import IUnitOfWork
from app.infrastructure.persistence.config import DatabaseConfig
from app.infrastructure.persistence.connection import SQLiteConnectionManager
from app.infrastructure.persistence.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)
from app.infrastructure.word_reader.word_activity_extractor import (
    WordActivityExtractor,
)


class WordBatchPreflightStatus(BaseModel):
    """Resultado de la verificación pre-vuelo antes de ejecutar el procesamiento por lote."""
    listo_para_procesar: bool = False
    carpeta_origen_valida: bool = False
    carpeta_salida_valida: bool = True
    total_archivos_encontrados: int = 0
    total_temporales_excluidos: int = 0
    total_candidatos: int = 0
    errores_bloqueantes: List[str] = Field(default_factory=list)
    advertencias: List[str] = Field(default_factory=list)


class WordBatchAppService:
    """Fachada de servicio de aplicación para la interfaz gráfica del flujo Word → Matrices."""

    @classmethod
    def resolver_directorio_salida_predeterminado(cls) -> Path:
        """Resuelve el directorio de salida predeterminado para las matrices generadas.

        Ruta estándar: %USERPROFILE%\\Documents\\BICU_Consolidados
        Fallback: Carpeta 'output' en la raíz del proyecto.
        """
        try:
            home = Path.home()
            docs = home / "Documents"
            if not docs.exists() and (home / "Documentos").exists():
                docs = home / "Documentos"

            salida = docs / "BICU_Consolidados"
            salida.mkdir(parents=True, exist_ok=True)
            return salida
        except Exception:
            fallback = Path("output").resolve()
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    @classmethod
    def analizar_carpeta_origen(
        cls,
        carpeta_origen: Union[str, Path],
        patron_glob: str = "*.docx",
    ) -> WordBatchPreflightStatus:
        """Analiza la carpeta seleccionada de forma no destructiva.

        - Verifica existencia y permisos de lectura.
        - Descubre archivos coincidentes con el patrón glob.
        - Identifica y excluye archivos de bloqueo temporal de Word (~$*).
        - Evalúa si el lote contiene al menos un documento apto.
        """
        if not carpeta_origen or not str(carpeta_origen).strip():
            return WordBatchPreflightStatus(
                listo_para_procesar=False,
                carpeta_origen_valida=False,
                errores_bloqueantes=["Debe seleccionar una carpeta de origen con documentos Word."],
            )

        p = Path(carpeta_origen)
        if not p.exists():
            return WordBatchPreflightStatus(
                listo_para_procesar=False,
                carpeta_origen_valida=False,
                errores_bloqueantes=[f"La carpeta '{p.name}' no existe en la ruta especificada."],
            )

        if not p.is_dir():
            return WordBatchPreflightStatus(
                listo_para_procesar=False,
                carpeta_origen_valida=False,
                errores_bloqueantes=[f"La ruta '{p.name}' no corresponde a un directorio accesible."],
            )

        try:
            todos = sorted(list(p.glob(patron_glob)))
            temporales = [f for f in todos if f.name.startswith("~$")]
            candidatos = [f for f in todos if not f.name.startswith("~$")]
            total_encontrados = len(todos)
            total_temporales = len(temporales)
            total_candidatos = len(candidatos)

            errores = []
            advertencias = []

            if total_candidatos == 0:
                errores.append(
                    f"No se encontraron documentos Word válidos ('{patron_glob}') en la carpeta."
                )

            if total_temporales > 0:
                advertencias.append(
                    f"Se excluyeron {total_temporales} archivo(s) temporal(es) de Word (~$*)."
                )

            listo = len(errores) == 0 and total_candidatos > 0

            return WordBatchPreflightStatus(
                listo_para_procesar=listo,
                carpeta_origen_valida=True,
                carpeta_salida_valida=True,
                total_archivos_encontrados=total_encontrados,
                total_temporales_excluidos=total_temporales,
                total_candidatos=total_candidatos,
                errores_bloqueantes=errores,
                advertencias=advertencias,
            )
        except Exception as exc:
            return WordBatchPreflightStatus(
                listo_para_procesar=False,
                carpeta_origen_valida=False,
                errores_bloqueantes=[f"Error al examinar la carpeta: {exc}"],
            )

    @classmethod
    def crear_batch_orchestrator(
        cls,
        uow: Optional[IUnitOfWork] = None,
    ) -> IngestarCarpetaWordUseCase:
        """Fábrica institucional para construir el orquestador IngestarCarpetaWordUseCase.

        Conecta los casos de uso atómicos respetando la arquitectura de capas.
        """
        if uow is None:
            config = DatabaseConfig()
            manager = SQLiteConnectionManager(config)
            uow = SQLiteUnitOfWork(connection_manager=manager, db_path=config.db_path)

        extractor = WordActivityExtractor()
        ingesta_uc = IngestarActividadDesdeWordUseCase(extractor=extractor, uow=uow)
        pipeline_uc = ProcesarPipelineActividadUseCase(uow=uow)
        pipeline_word_uc = ProcesarPipelineDesdeWordUseCase(
            ingesta_use_case=ingesta_uc,
            pipeline_use_case=pipeline_uc,
            uow=uow,
        )
        exportar_periodo_uc = ExportarMatricesPeriodoUseCase(
            pipeline_use_case=pipeline_uc,
            uow=uow,
        )
        return IngestarCarpetaWordUseCase(
            pipeline_word_use_case=pipeline_word_uc,
            exportar_periodo_use_case=exportar_periodo_uc,
            uow=uow,
        )
