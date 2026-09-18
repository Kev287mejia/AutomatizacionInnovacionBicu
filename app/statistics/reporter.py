"""
app.statistics.reporter

Formateador de reportes estadísticos para consola y persistencia JSON (Fase 7).
"""

import json
from pathlib import Path
from app.audit.audit_logger import get_logger
from app.statistics.models import EstadisticaGlobal

logger = get_logger(__name__)


class StatisticsReporter:
    """
    Presenta y serializa los indicadores del Motor Estadístico Institucional.
    """

    @classmethod
    def formatear_consola(cls, stats: EstadisticaGlobal) -> str:
        """Genera una salida ejecutiva y legible para terminal."""
        lineas = []
        lineas.append("=" * 72)
        lineas.append("  REPORTE ESTADÍSTICO INSTITUCIONAL Y AGREGACIONES (FASE 7)")
        lineas.append("=" * 72)
        lineas.append("")

        # 1. Resumen Ejecutivo
        lineas.append("  1. RESUMEN EJECUTIVO DEL PERÍODO:")
        lineas.append(f"     * Total de Actividades evaluadas:          {stats.total_actividades}")
        lineas.append(f"     * Total de Asistencias brutas:             {stats.total_asistencias}")
        lineas.append(f"     * Total de Personas únicas (neto):         {stats.total_personas_unicas}")
        lineas.append(f"     * Promedio de asistencias por persona:     {stats.promedio_asistencias_por_persona:.2f}")
        lineas.append(f"     * Personas recurrentes:                    {stats.personas_recurrentes}")
        lineas.append(f"     * Tasa de recurrencia:                     {stats.tasa_recurrencia:.2f}%")
        lineas.append("")

        # 2. Demografía Global
        ds = stats.desglose_sexo_global
        lineas.append("  2. DEMOGRAFÍA GLOBAL POR SEXO:")
        lineas.append(f"     * Femenino:   {ds.femenino:>4} participantes ({ds.porcentaje_femenino:>5.1f}%)")
        lineas.append(f"     * Masculino:  {ds.masculino:>4} participantes ({ds.porcentaje_masculino:>5.1f}%)")
        if ds.indefinido > 0:
            lineas.append(f"     * Indefinido: {ds.indefinido:>4} participantes")
        lineas.append(f"     * Total:      {ds.total:>4} asistencias")
        lineas.append("")

        # 3. Categorías y Roles Institucionales
        lineas.append("  3. DISTRIBUCIÓN POR CATEGORÍAS Y ROLES OPERATIVOS:")
        for cat_k, cat_v in stats.desglose_categorias.items():
            if cat_v.conteo_sexo.total > 0:
                lineas.append(
                    f"     * {cat_v.categoria:<30}: {cat_v.conteo_sexo.total:>3} registros "
                    f"(F: {cat_v.conteo_sexo.femenino}, M: {cat_v.conteo_sexo.masculino} | "
                    f"Aptos: {cat_v.aptos}, En Rev: {cat_v.en_revision})"
                )
        lineas.append("")

        # 4. Estructura de Salida para el Consolidado
        lineas.append("  4. MATRIZ 1 — CONSOLIDADO DE ACTIVIDADES (VISTA PREVIA DE FILAS):")
        for i, act in enumerate(stats.actividades, 1):
            lineas.append(f"     [Fila {i}] {act.nombre_actividad}")
            lineas.append(f"       - Sede: {act.sede or 'N/A'} | Fecha: {act.fecha or 'N/A'} | Eje: {act.eje_linea or 'N/A'}")
            lineas.append(
                f"       - Asistencias: {act.total_asistencias} (Únicas: {act.total_personas_unicas}) | "
                f"Femenino: {act.desglose_sexo_global.femenino}, Masculino: {act.desglose_sexo_global.masculino}"
            )
            lineas.append(
                f"       - Desglose: Estudiantes: {act.estudiantes.conteo_sexo.total} "
                f"(F:{act.estudiantes.conteo_sexo.femenino}, M:{act.estudiantes.conteo_sexo.masculino}) | "
                f"Docentes: {act.docentes.conteo_sexo.total} | "
                f"Admin/NoDoc: {act.administrativos_no_docentes.conteo_sexo.total} "
                f"(F:{act.administrativos_no_docentes.conteo_sexo.femenino}, M:{act.administrativos_no_docentes.conteo_sexo.masculino}) | "
                f"Beneficiados: {act.beneficiados.conteo_sexo.total} | "
                f"Colaboradores: {act.colaboradores.conteo_sexo.total}"
            )
        lineas.append("")

        # 5. Salud y Calidad de Datos
        cal = stats.calidad_datos
        lineas.append("  5. SALUD Y CALIDAD DE DATOS DEL CONJUNTO:")
        lineas.append(f"     * Estado Operativo: [APTO] {cal.registros_aptos} ({cal.porcentaje_aptos}%) | [EN REVISIÓN] {cal.registros_en_revision} ({cal.porcentaje_en_revision}%) | [BLOQUEADO] {cal.registros_bloqueados}")
        lineas.append("     * Métricas de Calidad y Disponibilidad (Auditadas con Denominador):")
        lineas.append(f"       - Cédula disponible:     {cal.cedula_disponible.numerador}/{cal.cedula_disponible.denominador} ({cal.cedula_disponible.porcentaje:.2f}%)")
        lineas.append(f"         Criterio: {cal.cedula_disponible.definicion}")
        lineas.append(f"       - Sexo confirmado:       {cal.sexo_confirmado.numerador}/{cal.sexo_confirmado.denominador} ({cal.sexo_confirmado.porcentaje:.2f}%)")
        lineas.append(f"         Criterio: {cal.sexo_confirmado.definicion}")
        lineas.append(f"       - Edad/Fecha disponible: {cal.edad_disponible.numerador}/{cal.edad_disponible.denominador} ({cal.edad_disponible.porcentaje:.2f}%)")
        lineas.append(f"         Criterio: {cal.edad_disponible.definicion}")
        lineas.append(f"       - Carrera disponible:    {cal.carrera_disponible.numerador}/{cal.carrera_disponible.denominador} ({cal.carrera_disponible.porcentaje:.2f}%)")
        lineas.append(f"         Criterio: {cal.carrera_disponible.definicion}")
        lineas.append("")

        # 6. Invariante Estadística
        inv_str = "[CUMPLIDA: 100% CONSISTENTE Y TRAZABLE]" if stats.invariante_estadistica_valida else "[ERROR DE INVARIANTE]"
        lineas.append(f"  6. VERIFICACIÓN DE INVARIANTE ESTADÍSTICA: {inv_str}")
        lineas.append(f"     * Suma Actividades == Total Entrada == Suma Categorías == Suma Sexos ({stats.total_asistencias})")
        lineas.append("=" * 72)

        return "\n".join(lineas)

    @classmethod
    def guardar_json(cls, stats: EstadisticaGlobal, ruta_archivo: Path) -> Path:
        """Serializa las estadísticas a JSON en disco."""
        ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
        datos = json.loads(stats.model_dump_json())
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        logger.info(f"Reporte estadístico guardado en: {ruta_archivo}")
        return ruta_archivo
