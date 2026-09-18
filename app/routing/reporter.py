"""
app.routing.reporter

Generador de reportes de enrutamiento institucional para consola y exportación JSON.
"""

import json
from pathlib import Path
from typing import Dict, Any

from app.audit.audit_logger import get_logger
from app.routing.models import ResultadoRouting
from app.routing.enums import MatrizDestino

logger = get_logger(__name__)


class RoutingReporter:
    """
    Formatea y serializa el resultado oficial de la Fase 6 (Routing).
    """

    @classmethod
    def formatear_consola(cls, resultado: ResultadoRouting) -> str:
        """
        Genera una presentación estructurada, clara y profesional para terminal.
        """
        lineas = []
        lineas.append("=" * 70)
        lineas.append("  REPORTE OFICIAL DE ENRUTAMIENTO INSTITUCIONAL (FASE 6)")
        lineas.append("=" * 70)
        lineas.append("")

        # 1. Verificación de Invariante Formal
        inv_str = "[CUMPLIDA: 100% CONSERVADO]" if resultado.invariante_valida else "[FALLO DE CONSERVACIÓN]"
        lineas.append("  1. TOTALES Y VERIFICACIÓN DE INVARIANTE:")
        lineas.append(f"     * Participaciones de entrada:    {resultado.total_entrada}")
        lineas.append(f"     * Participaciones clasificadas:  {resultado.total_clasificadas}")
        lineas.append(f"     * Estado de la invariante:       {inv_str}")
        lineas.append(
            f"     * Fórmula: Entrada ({resultado.total_entrada}) == "
            f"Estudiantes ({len(resultado.estudiantes)}) + "
            f"Académicos/Admin ({len(resultado.academicos_administrativos)}) + "
            f"Beneficiados ({len(resultado.beneficiados)}) + "
            f"Colaboradores ({len(resultado.colaboradores)}) + "
            f"ColaRevisión ({len(resultado.cola_revision)}) + "
            f"Bloqueados ({len(resultado.bloqueados)})"
        )
        lineas.append("")

        # 2. Distribución a Matrices Oficiales
        lineas.append("  2. ASIGNACIÓN A MATRICES OFICIALES DE SALIDA:")
        
        # Estudiantes
        res_est = resultado.resumenes.get(MatrizDestino.ESTUDIANTES.value)
        lineas.append(f"     [Matriz 2] Estudiantes:                   {len(resultado.estudiantes)} registros")
        if res_est and res_est.total_participaciones > 0:
            lineas.append(
                f"       - Estados:  [APTO] {res_est.total_aptos} | [EN REVISIÓN] {res_est.total_en_revision}"
            )
            lineas.append(
                f"       - Sexo:     Femenino: {res_est.total_femenino} | Masculino: {res_est.total_masculino} | Indefinido: {res_est.total_sexo_indefinido}"
            )

        # Académicos y Administrativos
        res_acad = resultado.resumenes.get(MatrizDestino.ACADEMICOS_ADMINISTRATIVOS.value)
        lineas.append(f"     [Matriz 3] Académicos y Administrativos:  {len(resultado.academicos_administrativos)} registros")
        if res_acad and res_acad.total_participaciones > 0:
            subt_acad = res_acad.subtipos.get("ACADEMICO", 0)
            subt_admin = res_acad.subtipos.get("ADMINISTRATIVO", 0)
            lineas.append(
                f"       - Estados:  [APTO] {res_acad.total_aptos} | [EN REVISIÓN] {res_acad.total_en_revision}"
            )
            lineas.append(
                f"       - Subtipos: Rol Académico (Docente): {subt_acad} | Rol Administrativo (Admin/No Docente): {subt_admin}"
            )
            lineas.append(
                f"       - Sexo:     Femenino: {res_acad.total_femenino} | Masculino: {res_acad.total_masculino} | Indefinido: {res_acad.total_sexo_indefinido}"
            )

        # Colaboradores
        res_colab = resultado.resumenes.get(MatrizDestino.COLABORADORES.value)
        lineas.append(f"     [Matriz 4] Colaboradores:                 {len(resultado.colaboradores)} registros")
        if res_colab and res_colab.total_participaciones > 0:
            lineas.append(
                f"       - Estados:  [APTO] {res_colab.total_aptos} | [EN REVISIÓN] {res_colab.total_en_revision}"
            )

        # Beneficiados
        res_ben = resultado.resumenes.get(MatrizDestino.BENEFICIADOS.value)
        lineas.append(f"     [Matriz 5] Protagonistas Beneficiados:    {len(resultado.beneficiados)} registros")
        if res_ben and res_ben.total_participaciones > 0:
            lineas.append(
                f"       - Estados:  [APTO] {res_ben.total_aptos} | [EN REVISIÓN] {res_ben.total_en_revision}"
            )
        lineas.append("")

        # 3. Cubetas Desacopladas de Control
        lineas.append("  3. CUBETAS DESACOPLADAS (NO ENTRAN A MATRICES OFICIALES):")
        lineas.append(f"     * Cola de Revisión (categoría no determinable): {len(resultado.cola_revision)} registros")
        lineas.append(f"     * Aislamiento de Bloqueados (error crítico):     {len(resultado.bloqueados)} registros")
        lineas.append("")

        # 4. Contexto de Actividades (Consolidado)
        lineas.append("  4. CONTEXTO DE ACTIVIDADES (MATRIZ 1 - CONSOLIDADO):")
        lineas.append(f"     * Actividades analizadas para consolidación:    {len(resultado.actividades)}")
        lineas.append("       (Nota: El consolidado agrega a nivel de actividad, sin duplicación de registros).")
        lineas.append("")

        # Notas institucionales
        lineas.append("  DIRECTIVAS APLICADAS:")
        lineas.append("  - La categoría original 'NO_DOCENTE' permanece inmutable en el modelo.")
        lineas.append("    Su equivalencia institucional se asigna formalmente como subtipo 'ADMINISTRATIVO'.")
        lineas.append("  - Registros con estado 'EN_REVISION' permanecen en su matriz oficial correspondiente.")
        lineas.append("  - Las 5 matrices Excel oficiales se generarán en la fase posterior de exportación.")
        lineas.append("=" * 70)

        return "\n".join(lineas)

    @classmethod
    def guardar_json(cls, resultado: ResultadoRouting, ruta_archivo: Path) -> Path:
        """
        Serializa el resultado de routing a JSON y lo guarda en disco.
        """
        ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
        datos = json.loads(resultado.model_dump_json())
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        logger.info(f"Reporte de routing guardado exitosamente en: {ruta_archivo}")
        return ruta_archivo
