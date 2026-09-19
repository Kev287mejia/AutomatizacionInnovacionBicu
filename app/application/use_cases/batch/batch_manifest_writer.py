"""app.application.use_cases.batch.batch_manifest_writer

Generador y escritor del manifiesto pericial JSON externo para lotes de procesamiento Word.

Decisión P-04 aprobada:
- Manifest JSON externo persistente para trazabilidad técnica del lote.
- No sustituye la base de datos SQLite; provee trazabilidad y auditoría.
- Contiene balances, resumen de calidad, routing, matrices exportadas, advertencias y errores.
- GAP-3: Documenta claramente qué archivos generaron actividades y advertencias de coincidencia.
- Dry-run: Cuando dry_run=True, por diseño estricto NO escribe en disco (cero mutaciones).
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from app.application.dto.batch_dtos import BatchResultadoDTO
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class BatchManifestWriter:
    """Escritor pericial de auditoría y trazabilidad en JSON para el procesamiento por lote."""

    @staticmethod
    def construir_payload(resultado: BatchResultadoDTO) -> Dict[str, Any]:
        """Construye la estructura de datos serializable completa del manifest."""
        # Agrupar métricas de calidad y routing desde los archivos individuales
        calidad_resumen: Dict[str, int] = {}
        total_participaciones_enrutadas = 0

        for r in resultado.resultados_por_archivo:
            if r.calidad_estado:
                calidad_resumen[r.calidad_estado] = calidad_resumen.get(r.calidad_estado, 0) + 1
            total_participaciones_enrutadas += r.total_participaciones_enrutadas

        return {
            "metadata_lote": {
                "batch_id": resultado.batch_id,
                "carpeta_origen": resultado.carpeta_origen,
                "patron_glob": resultado.patron_glob,
                "timestamp_inicio": resultado.timestamp_inicio,
                "timestamp_fin": resultado.timestamp_fin,
                "dry_run": resultado.dry_run,
                "invariante_ok": resultado.invariante_ok,
            },
            "balance_archivos": {
                "encontrados": resultado.archivos_encontrados,
                "aceptados": resultado.archivos_aceptados,
                "con_advertencias": resultado.archivos_con_advertencias,
                "rechazados": resultado.archivos_rechazados,
                "fallidos": resultado.archivos_fallidos,
            },
            "entidades_generadas": {
                "total_actividades": len(resultado.actividades_creadas),
                "actividades_ids": resultado.actividades_creadas,
                "total_evidencias": resultado.evidencias_registradas_total,
            },
            "calidad": {
                "distribucion_estados": calidad_resumen,
                "nota": "Reglas de calidad Q-01..Q-20 ejecutadas por QualityValidator.",
            },
            "routing": {
                "total_participaciones_nominales": total_participaciones_enrutadas,
                "nota": (
                    "0 participaciones nominales es el comportamiento esperado en actividades "
                    "extraídas exclusivamente de Word (Decisión P-02). Cifras de Tabla 2 no nominalizadas."
                ),
            },
            "exportacion": {
                "exportacion_ejecutada": resultado.exportacion_ejecutada,
                "carpeta_salida": resultado.carpeta_batch_salida,
                "matrices_generadas": resultado.matrices_generadas,
                "hashes_sha256": resultado.hashes_matrices,
                "estrategia": "CONSOLIDADA_AL_FINAL_DEL_LOTE (P-01)",
            },
            "gap3_trazabilidad_duplicados": {
                "actividades_con_posible_duplicado_count": len(resultado.actividades_con_posible_duplicado),
                "referencias": resultado.actividades_con_posible_duplicado,
                "nota_pericial": (
                    "Advertencia heurística basada en coincidencia de nombres de archivo. "
                    "No constituye garantía de identidad documental ni mecanismo formal de idempotencia. "
                    "Schema v001 permanece inalterado sin restricción UNIQUE por documento."
                ),
            },
            "advertencias_lote": resultado.advertencias_lote,
            "errores_criticos": resultado.errores_criticos,
            "archivos_detalle": [
                archivo.model_dump() for archivo in resultado.resultados_por_archivo
            ],
        }

    @classmethod
    def escribir(
        cls,
        resultado: BatchResultadoDTO,
        ruta_directorio_salida: Union[str, Path],
        nombre_archivo: str = "manifest.json",
        permitir_en_dry_run: bool = False,
    ) -> Optional[Path]:
        """Escribe físicamente el manifest.json en el directorio de salida.

        Regla estricta: Si resultado.dry_run=True y permitir_en_dry_run=False,
        NO se realiza escritura física en disco y se retorna None.

        Args:
            resultado: DTO con los datos del lote.
            ruta_directorio_salida: Carpeta donde se creará el manifest.
            nombre_archivo: Nombre del archivo JSON (default 'manifest.json').
            permitir_en_dry_run: Si True, fuerza la escritura incluso en dry_run.

        Returns:
            Path absoluto del archivo generado o None si no se escribió.
        """
        if resultado.dry_run and not permitir_en_dry_run:
            logger.info("BatchManifestWriter: dry_run=True activo. Omitiendo escritura física del manifest.")
            return None

        directorio = Path(ruta_directorio_salida)
        directorio.mkdir(parents=True, exist_ok=True)
        destino = directorio / nombre_archivo

        payload = cls.construir_payload(resultado)

        with open(destino, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        logger.info(f"BatchManifestWriter: Manifest guardado exitosamente en '{destino}'.")
        return destino.resolve()
