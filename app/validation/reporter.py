"""
app.validation.reporter

Generador de reportes de validación y calidad de datos (Fase 5).
Estructura y consolida:
- Totales de actividades, personas y participaciones.
- Conteo de hallazgos por severidad (ERROR, WARNING, INFO, REVISION).
- Clasificación de participaciones:
  * APTO: Pasó las validaciones de Fase 5 (sin error bloqueante ni revisión pendiente).
  * EN_REVISION: Requiere confirmación humana (por bandera propia o hallazgo REVISION).
  * BLOQUEADO: Con error a nivel de registro que impide exportación.
- Distribución preliminar por categoría / matriz destino.
- Serialización a JSON y formateo legible en consola.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion, CategoriaParticipacion
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class ValidationSummaryReport(BaseModel):
    """Modelo estructurado del reporte de validación global."""
    total_actividades: int = Field(default=0, description="Total de actividades evaluadas.")
    total_personas: int = Field(default=0, description="Total de personas evaluadas.")
    total_participaciones: int = Field(default=0, description="Total de participaciones evaluadas.")
    conteo_por_severidad: Dict[str, int] = Field(
        default_factory=lambda: {"ERROR": 0, "WARNING": 0, "INFO": 0, "REVISION": 0},
        description="Conteo de hallazgos clasificados por severidad."
    )
    registros_aptos: int = Field(default=0, description="Participaciones que superaron validaciones sin reparos.")
    registros_en_revision: int = Field(default=0, description="Participaciones con advertencias que requieren revisión humana.")
    registros_bloqueados: int = Field(default=0, description="Participaciones con errores críticos bloqueantes.")
    distribucion_categorias: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribución de participaciones por categoría de origen/normalizada (sin transformación a matrices)."
    )
    distribucion_preliminar: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribución preliminar por categoría o matriz oficial destino."
    )
    detalles_participaciones: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Estado y motivos de cada participación individual."
    )
    validaciones: List[ValidationResult] = Field(
        default_factory=list,
        description="Lista completa de todas las validaciones generadas."
    )


class ValidationReporter:
    """
    Consolidador y generador de reportes de validación de Fase 5.
    """

    @classmethod
    def clasificar_participacion(
        cls,
        part: Participation,
        hallazgos_part: List[ValidationResult]
    ) -> Dict[str, Any]:
        """
        Determina el estado operativo de una participación individual:
        - BLOQUEADO: Tiene al menos un hallazgo de nivel ERROR.
        - EN_REVISION: Tiene part.requiere_revision == True o al menos un hallazgo de nivel REVISION.
        - APTO: No tiene errores ni revisiones pendientes.
        """
        tiene_error = any(h.nivel == NivelValidacion.ERROR for h in hallazgos_part)
        tiene_revision = part.requiere_revision or any(h.nivel == NivelValidacion.REVISION for h in hallazgos_part)

        if tiene_error:
            estado = "BLOQUEADO"
            motivos = list(dict.fromkeys([h.mensaje for h in hallazgos_part if h.nivel == NivelValidacion.ERROR]))
        elif tiene_revision:
            estado = "EN_REVISION"
            motivos_rev = [h.mensaje for h in hallazgos_part if h.nivel == NivelValidacion.REVISION]
            if part.motivo_revision and part.motivo_revision not in motivos_rev:
                motivos_rev.append(part.motivo_revision)
            motivos = list(dict.fromkeys(motivos_rev))
        else:
            estado = "APTO"
            motivos = []

        return {
            "id_participacion": part.id_participacion,
            "id_actividad": part.id_actividad,
            "id_persona": part.id_persona,
            "categoria": part.categoria_participacion.value if hasattr(part.categoria_participacion, "value") else str(part.categoria_participacion),
            "estado": estado,
            "motivos": motivos
        }

    @classmethod
    def generar_reporte(
        cls,
        actividades: List[Activity],
        personas: List[Person],
        participaciones: List[Participation],
        validaciones: List[ValidationResult]
    ) -> ValidationSummaryReport:
        """
        Construye el reporte consolidado calculando métricas, distribución y clasificación de estados.
        """
        # 1. Conteo por severidad
        conteo_sev = {"ERROR": 0, "WARNING": 0, "INFO": 0, "REVISION": 0}
        for v in validaciones:
            nivel_str = v.nivel.value if hasattr(v.nivel, "value") else str(v.nivel)
            if nivel_str in conteo_sev:
                conteo_sev[nivel_str] += 1
            else:
                conteo_sev[nivel_str] = 1

        # 2. Mapear validaciones por ID de referencia
        mapa_val: Dict[str, List[ValidationResult]] = {}
        for v in validaciones:
            if v.id_referencia:
                mapa_val.setdefault(v.id_referencia, []).append(v)

        # 3. Clasificar cada participación
        detalles = []
        aptos = 0
        en_rev = 0
        bloqueados = 0

        # Distribución de categorías directas
        distribucion_cat: Dict[str, int] = {}

        # Distribución preliminar por matriz
        distribucion: Dict[str, int] = {
            "Estudiantes": 0,
            "Académicos y Administrativos": 0,
            "Protagonistas Beneficiados": 0,
            "Colaboradores": 0,
            "Pendiente de Asignación (Desconocido)": 0
        }

        for part in participaciones:
            # Hallazgos asociados tanto a la participación como a la persona referenciada
            hallazgos_asociados = list(mapa_val.get(part.id_participacion, []))
            if part.id_persona in mapa_val:
                hallazgos_asociados.extend(mapa_val[part.id_persona])

            info = cls.clasificar_participacion(part, hallazgos_asociados)
            detalles.append(info)

            if info["estado"] == "APTO":
                aptos += 1
            elif info["estado"] == "EN_REVISION":
                en_rev += 1
            elif info["estado"] == "BLOQUEADO":
                bloqueados += 1

            # Conteo de categorías puras de participación
            cat_nombre = part.categoria_participacion.value if hasattr(part.categoria_participacion, "value") else str(part.categoria_participacion)
            distribucion_cat[cat_nombre] = distribucion_cat.get(cat_nombre, 0) + 1

            # Asignación preliminar por categoría a matriz destino
            cat = part.categoria_participacion
            if cat == CategoriaParticipacion.ESTUDIANTE:
                distribucion["Estudiantes"] += 1
            elif cat in (CategoriaParticipacion.DOCENTE, CategoriaParticipacion.ADMINISTRATIVO, CategoriaParticipacion.NO_DOCENTE):
                distribucion["Académicos y Administrativos"] += 1
            elif cat in (CategoriaParticipacion.POBLADOR_GENERAL, CategoriaParticipacion.BENEFICIADO):
                distribucion["Protagonistas Beneficiados"] += 1
            elif cat == CategoriaParticipacion.COLABORADOR:
                distribucion["Colaboradores"] += 1
            else:
                distribucion["Pendiente de Asignación (Desconocido)"] += 1

        return ValidationSummaryReport(
            total_actividades=len(actividades),
            total_personas=len(personas),
            total_participaciones=len(participaciones),
            conteo_por_severidad=conteo_sev,
            registros_aptos=aptos,
            registros_en_revision=en_rev,
            registros_bloqueados=bloqueados,
            distribucion_categorias=distribucion_cat,
            distribucion_preliminar=distribucion,
            detalles_participaciones=detalles,
            validaciones=validaciones
        )

    @classmethod
    def formatear_consola(cls, reporte: ValidationSummaryReport) -> str:
        """Formatea el reporte en texto estructurado y legible para terminal."""
        lineas = []
        lineas.append("=" * 68)
        lineas.append("  REPORTE DE VALIDACIÓN Y CALIDAD DE DATOS (FASE 5)")
        lineas.append("=" * 68)
        lineas.append("")
        lineas.append("  1. TOTALES DEL CONJUNTO DE DATOS:")
        lineas.append(f"     * Actividades analizadas:    {reporte.total_actividades}")
        lineas.append(f"     * Personas evaluadas:        {reporte.total_personas}")
        lineas.append(f"     * Participaciones evaluadas: {reporte.total_participaciones}")
        lineas.append("")
        lineas.append("  2. RESUMEN DE HALLAZGOS POR SEVERIDAD:")
        lineas.append(f"     * ERROR (bloqueantes):       {reporte.conteo_por_severidad.get('ERROR', 0)}")
        lineas.append(f"     * REVISION (revisión humana):{reporte.conteo_por_severidad.get('REVISION', 0)}")
        lineas.append(f"     * WARNING (advertencias):    {reporte.conteo_por_severidad.get('WARNING', 0)}")
        lineas.append(f"     * INFO (informativos):       {reporte.conteo_por_severidad.get('INFO', 0)}")
        lineas.append("")
        lineas.append("  3. ESTADO OPERATIVO DE PARTICIPACIONES:")
        lineas.append(f"     * [APTO]                     {reporte.registros_aptos} participaciones")
        lineas.append(f"     * [EN REVISIÓN]              {reporte.registros_en_revision} participaciones")
        lineas.append(f"     * [BLOQUEADO]                {reporte.registros_bloqueados} participaciones")
        lineas.append("")
        lineas.append("  4. DISTRIBUCIÓN POR CATEGORÍA (FASE 5):")
        for cat_k, cat_v in reporte.distribucion_categorias.items():
            lineas.append(f"     * {cat_k:<38}: {cat_v} registros")
        lineas.append("")
        lineas.append("  5. ESTIMACIÓN PRELIMINAR HACIA MATRICES (NO ES ROUTING OFICIAL):")
        for matriz, conteo in reporte.distribucion_preliminar.items():
            lineas.append(f"     * {matriz:<38}: {conteo} registros")
        lineas.append("")
        lineas.append("  NOTA: La categoría 'NO_DOCENTE' se conserva íntegra en Fase 5.")
        lineas.append("  El routing definitivo hacia matrices oficiales corresponde a Fase 6.")
        lineas.append("  El estado 'APTO' indica únicamente que la participación superó")
        lineas.append("  las validaciones de Fase 5. No representa la exportación definitiva.")
        lineas.append("=" * 68)
        return "\n".join(lineas)

    @classmethod
    def guardar_json(cls, reporte: ValidationSummaryReport, ruta_archivo: Path) -> Path:
        """Serializa el reporte a JSON y lo guarda en disco."""
        ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
        # Convertir reporte a dict serializable
        datos = json.loads(reporte.model_dump_json())
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        logger.info(f"Reporte de validación guardado en: {ruta_archivo}")
        return ruta_archivo
