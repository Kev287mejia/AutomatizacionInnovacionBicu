"""
app.exporters.reporter

Formateador y reportero en consola para el Motor de Exportación (Fase 9).
Diseñado con caracteres ASCII seguros compatibles con codepage cp1252 en Windows.
"""

from typing import List
from app.exporters.models import EstatusPlantilla, ManifiestoExportacion, ModoExportacion


class ExporterReporter:
    """Genera reportes de auditoría en texto plano seguro para consola."""

    @classmethod
    def generar_reporte_texto(cls, manifiesto: ManifiestoExportacion) -> str:
        """Formatea el ManifiestoExportacion en un informe legible para consola."""
        lineas: List[str] = []
        es_preview = (manifiesto.modo == ModoExportacion.PREVIEW)
        titulo_modo = "VISTA PREVIA DE EXPORTACIÓN (PREVIEW)" if es_preview else "REPORTE DE EXPORTACIÓN INSTITUCIONAL (EXPORT)"

        lineas.append("=" * 76)
        lineas.append(f"  {titulo_modo} — FASE 9")
        lineas.append("=" * 76)
        lineas.append("")

        # 1. Metadatos de la corrida
        tipo_entrega = "OFICIAL INSTITUCIONAL" if manifiesto.es_oficial else "PRUEBA TÉCNICA (NO OFICIAL)"
        lineas.append("  1. METADATOS DE LA OPERACIÓN:")
        lineas.append(f"     * Modo de ejecución:            {manifiesto.modo.value.upper()}")
        lineas.append(f"     * Fecha y hora:                 {manifiesto.fecha_exportacion}")
        lineas.append(f"     * Clasificación de entrega:     {tipo_entrega}")
        lineas.append(f"     * Total matrices procesadas:    {manifiesto.total_matrices}")
        lineas.append(f"     * Total asistencias enrutadas:  {manifiesto.total_asistencias_enrutadas}")
        lineas.append(f"     * Total filas detalle escritas: {manifiesto.total_filas_detalle_escritas}")
        lineas.append("")

        # 2. Detalle por Matriz
        lineas.append("  2. DETALLE POR MATRIZ OFICIAL:")
        for id_m in sorted(manifiesto.matrices.keys()):
            res = manifiesto.matrices[id_m]
            etiqueta_estatus = (
                "[OFICIAL REAL]"
                if res.estatus_plantilla == EstatusPlantilla.OFICIAL_REAL
                else "[GOLDEN TEST FIXTURE - NO OFICIAL]"
            )
            rango_filas = f"filas {res.fila_inicio} a {res.fila_fin}" if res.fila_inicio else "0 filas añadidas"

            lineas.append(f"     [+] {res.nombre_matriz} {etiqueta_estatus}")
            lineas.append(f"         - Archivo:             {res.nombre_archivo}")
            lineas.append(f"         - Plantilla base:      {res.plantilla_utilizada}")
            lineas.append(f"         - Filas escritas:      {res.total_filas_escritas} ({rango_filas})")
            lineas.append(f"         - Fórmulas verificadas:{len(res.celdas_con_formula_preservadas)} preservadas intactas")
            lineas.append(f"         - Plantilla inalterada: {'SI (SHA-256 consistente)' if res.plantilla_inalterada else 'NO (ERROR)'}")

            if res.columnas_sin_fuente_respetadas:
                lineas.append(f"         - Celdas sin fuente:   {len(res.columnas_sin_fuente_respetadas)} columna(s) dejada(s) en blanco")
            if res.columnas_catalogo_no_homologadas:
                lineas.append(f"         - Catálogo no homolog: {', '.join(res.columnas_catalogo_no_homologadas)} (EN_REVISION)")
            lineas.append("     " + "-" * 70)
        lineas.append("")

        # 3. Verificación de Invariantes
        lineas.append("  3. VERIFICACIÓN DE INVARIANTES INSTITUCIONALES:")
        inv_m1 = "CUMPLIDA" if manifiesto.invariante_conservacion_valida else "FALLIDA"
        inv_filas = "CUMPLIDA" if manifiesto.invariante_filas_valida else "FALLIDA"
        inv_hashes = "CUMPLIDA (100% inalteradas)" if manifiesto.hashes_plantillas_coinciden else "FALLIDA"

        lineas.append(f"     * Invariante Matriz 1 (Actividades):  [{inv_m1}] Filas M1 == Total Actividades")
        lineas.append(f"     * Invariante Matrices 2-5 (Detalle):  [{inv_filas}] Suma(M2..M5) == Total Asistencias Enrutadas")
        lineas.append(f"     * Invariante Criptográfica SHA-256:   [{inv_hashes}]")
        lineas.append("")

        if manifiesto.ruta_manifiesto:
            lineas.append(f"  Manifiesto JSON generado en: {manifiesto.ruta_manifiesto}")
        elif es_preview:
            lineas.append("  [INFO] Modo PREVIEW finalizado sin escribir archivos en output/.")

        lineas.append("=" * 76)
        return "\n".join(lineas)

    @classmethod
    def imprimir_reporte(cls, manifiesto: ManifiestoExportacion) -> None:
        """Imprime el informe en la salida estándar."""
        print(cls.generar_reporte_texto(manifiesto))
