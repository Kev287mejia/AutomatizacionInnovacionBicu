"""
app.templates_analysis.inspector

Motor de Inspección Física y Descubrimiento Estructural de Plantillas Excel (Fase 8A).
Opera estrictamente en modo de solo lectura sobre archivos .xlsx sin modificarlos.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import openpyxl
from openpyxl.utils import get_column_letter

from app.audit.audit_logger import get_logger
from app.templates_analysis.models import (
    CeldaProtegida,
    ColumnaDetectada,
    EsquemaPlantilla,
    RangoCombinado,
    ZonaEscribible,
)

logger = get_logger(__name__)


class TemplateInspector:
    """
    Inspector estático de hojas de cálculo con openpyxl (Fase 8A).
    Descubre la anatomía física completa de las plantillas oficiales.
    """

    @classmethod
    def inspeccionar_archivo(
        cls,
        ruta_archivo: Path,
        id_matriz: str,
        nombre_matriz: str,
        es_oficial: bool = False,
        nombre_hoja: Optional[str] = None,
    ) -> EsquemaPlantilla:
        """
        Inspecciona físicamente un archivo de plantilla Excel sin alterar sus bytes en disco.

        Args:
            ruta_archivo: Ruta al archivo .xlsx a inspeccionar.
            id_matriz: Identificador interno de la matriz oficial (1 a 5).
            nombre_matriz: Nombre institucional de la matriz.
            es_oficial: True si es plantilla oficial suministrada, False si es fixture de prueba.
            nombre_hoja: Hoja opcional a inspeccionar (si es None, toma la primera hoja visible).

        Returns:
            EsquemaPlantilla con la anatomía física descubierta.
        """
        if not ruta_archivo.exists():
            msg = f"Archivo de plantilla no encontrado en disco: {ruta_archivo}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        logger.info(f"Iniciando inspección física (Fase 8A) de: {ruta_archivo.name} ({id_matriz})")

        # Cargar libro en modo solo lectura de metadatos (data_only=False preserva fórmulas)
        es_macro = ruta_archivo.suffix.lower() in [".xlsm", ".xltm"]
        wb = openpyxl.load_workbook(str(ruta_archivo), data_only=False, keep_vba=es_macro)

        # 1. Hojas disponibles y visibilidad
        hojas_disponibles = list(wb.sheetnames)
        hojas_ocultas: List[str] = []
        hojas_visibles: List[str] = []

        for nombre_h in hojas_disponibles:
            sh = wb[nombre_h]
            if sh.sheet_state != "visible":
                hojas_ocultas.append(nombre_h)
            else:
                hojas_visibles.append(nombre_h)

        # Determinar hoja objetivo
        if nombre_hoja and nombre_hoja in hojas_disponibles:
            hoja_objetivo = nombre_hoja
        elif hojas_visibles:
            hoja_objetivo = hojas_visibles[0]
        else:
            hoja_objetivo = hojas_disponibles[0]

        sheet = wb[hoja_objetivo]
        max_r = sheet.max_row or 0
        max_c = sheet.max_column or 0

        # 2. Celdas combinadas (Merged Cells)
        celdas_combinadas: List[RangoCombinado] = []
        mapa_celdas_combinadas: Dict[Tuple[int, int], str] = {}

        for merged in sheet.merged_cells.ranges:
            coord = str(merged)
            min_col, min_row, max_col, max_row = (
                merged.min_col,
                merged.min_row,
                merged.max_col,
                merged.max_row,
            )
            top_left_coord = f"{get_column_letter(min_col)}{min_row}"
            bottom_right_coord = f"{get_column_letter(max_col)}{max_row}"
            top_left_cell = sheet.cell(row=min_row, column=min_col)
            val = str(top_left_cell.value).strip() if top_left_cell.value is not None else None

            rango_comb = RangoCombinado(
                rango=coord,
                celda_inicio=top_left_coord,
                celda_fin=bottom_right_coord,
                valor_principal=val,
            )
            celdas_combinadas.append(rango_comb)

            # Indexar todas las celdas del bloque combinado hacia el valor principal
            for r in range(min_row, max_row + 1):
                for c in range(min_col, max_col + 1):
                    if val:
                        mapa_celdas_combinadas[(r, c)] = val

        # 3. Detección de fórmulas y celdas protegidas
        celdas_protegidas: List[CeldaProtegida] = []
        filas_con_formulas: Set[int] = set()

        for row_idx in range(1, max_r + 1):
            for col_idx in range(1, max_c + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)
                val_str = str(cell.value).strip() if cell.value is not None else ""

                es_formula = val_str.startswith("=")
                es_bloqueada = bool(cell.protection and cell.protection.locked)

                if es_formula:
                    filas_con_formulas.add(row_idx)
                    celdas_protegidas.append(
                        CeldaProtegida(
                            coordenada=cell.coordinate,
                            fila=row_idx,
                            columna=col_idx,
                            tipo_proteccion="FORMULA",
                            formula=val_str,
                            valor_actual=None,
                        )
                    )
                elif es_bloqueada and sheet.protection.sheet:
                    celdas_protegidas.append(
                        CeldaProtegida(
                            coordenada=cell.coordinate,
                            fila=row_idx,
                            columna=col_idx,
                            tipo_proteccion="BLOQUEO_ESTRUCTURAL",
                            formula=None,
                            valor_actual=val_str or None,
                        )
                    )

        # 4. Validaciones de Datos
        validaciones_datos: List[str] = []
        if hasattr(sheet, "data_validations") and sheet.data_validations:
            for dv in sheet.data_validations.dataValidation:
                formula_val = dv.formula1 or ""
                tipo_val = dv.type or "lista"
                validaciones_datos.append(f"{tipo_val}: {formula_val} en {dv.sqref}")

        # 5. Detección no rígida de Fila de Encabezados y Fila de Inicio de Datos
        if hasattr(sheet, "tables") and "Tabla1" in sheet.tables:
            fila_encabezados = 1
            subencabezados_filas = []
            fila_inicio_datos = 2
            estado_fila_inicio = "DETERMINADA"
        else:
            fila_encabezados, subencabezados_filas, fila_inicio_datos, estado_fila_inicio = (
                cls._determinar_filas_estructura(sheet, max_r, max_c, mapa_celdas_combinadas)
            )

        # 6. Columnas detectadas
        columnas_detectadas: List[ColumnaDetectada] = []
        if fila_encabezados:
            for c_idx in range(1, max_c + 1):
                letra = get_column_letter(c_idx)
                celda_enc = sheet.cell(row=fila_encabezados, column=c_idx)
                texto_enc = (
                    str(celda_enc.value).strip()
                    if celda_enc.value is not None
                    else mapa_celdas_combinadas.get((fila_encabezados, c_idx), "")
                )

                subtextos: List[str] = []
                for sub_r in subencabezados_filas:
                    sub_cell = sheet.cell(row=sub_r, column=c_idx)
                    sub_val = (
                        str(sub_cell.value).strip()
                        if sub_cell.value is not None
                        else mapa_celdas_combinadas.get((sub_r, c_idx), "")
                    )
                    if sub_val and sub_val != texto_enc:
                        subtextos.append(sub_val)

                columnas_detectadas.append(
                    ColumnaDetectada(
                        indice_columna=c_idx,
                        letra_columna=letra,
                        encabezado_principal=texto_enc,
                        subencabezados=subtextos,
                        tipo_dato_inferido="str",
                    )
                )

        # 7. Zonas escribibles
        zonas_escribibles: List[ZonaEscribible] = []
        if fila_inicio_datos and fila_inicio_datos <= max_r:
            # Buscar si hay fila de fórmulas de totales inferior (ej. =SUM(...))
            fila_limite = None
            for f_formula in sorted(filas_con_formulas):
                if f_formula >= fila_inicio_datos:
                    es_totales = False
                    for c_idx in range(1, max_c + 1):
                        c_val = str(sheet.cell(row=f_formula, column=c_idx).value or "")
                        if "SUM(" in c_val.upper() or "TOTAL" in c_val.upper():
                            es_totales = True
                            break
                    if es_totales:
                        fila_limite = f_formula - 1
                        break

            zonas_escribibles.append(
                ZonaEscribible(
                    fila_inicio=fila_inicio_datos,
                    columna_inicio=1,
                    columna_fin=max_c,
                    fila_fin_estimada=fila_limite,
                )
            )

        tiene_macros = (
            ruta_archivo.suffix.lower() == ".xlsm"
            or getattr(wb, "vba_archive", None) is not None
        )
        tiene_prot = bool(sheet.protection and sheet.protection.sheet)

        # Cierre limpio del libro
        try:
            wb.close()
        except Exception:
            pass

        logger.info(
            f"Inspección física 8A completada: {ruta_archivo.name}. MaxRows={max_r}, "
            f"MaxCols={max_c}, FilaEnc={fila_encabezados}, FilaInicio={fila_inicio_datos}, "
            f"CeldasComb={len(celdas_combinadas)}, Fórmulas={len(celdas_protegidas)}"
        )

        return EsquemaPlantilla(
            id_matriz=id_matriz,
            nombre_matriz=nombre_matriz,
            ruta_archivo=str(ruta_archivo),
            es_oficial=es_oficial,
            hojas_disponibles=hojas_disponibles,
            hojas_ocultas=hojas_ocultas,
            hoja_inspeccionada=hoja_objetivo,
            max_filas=max_r,
            max_columnas=max_c,
            fila_encabezados=fila_encabezados,
            fila_inicio_datos=fila_inicio_datos,
            estado_fila_inicio=estado_fila_inicio,
            columnas_detectadas=columnas_detectadas,
            celdas_combinadas=celdas_combinadas,
            celdas_protegidas=celdas_protegidas,
            validaciones_datos=validaciones_datos,
            tiene_macros=tiene_macros,
            tiene_proteccion_hoja=tiene_prot,
            zonas_escribibles=zonas_escribibles,
        )

    @classmethod
    def _determinar_filas_estructura(
        cls,
        sheet,
        max_r: int,
        max_c: int,
        mapa_combinadas: Dict[Tuple[int, int], str],
    ) -> Tuple[Optional[int], List[int], Optional[int], str]:
        """
        Determina analíticamente la fila de encabezados y la primera fila segura de datos.
        Evita supuestos fijos de 'fila 5' o 'fila 6'. Si hay ambigüedad, emite REQUIERE_REVISION.
        """
        if max_r == 0 or max_c == 0:
            return None, [], None, "REQUIERE_REVISION"

        candidato_encabezado: Optional[int] = None
        mejor_densidad = 0
        subencabezados: List[int] = []

        # Evaluar densidad de textos independientes en las primeras 15 filas
        filas_a_evaluar = min(15, max_r)
        conteo_por_fila: Dict[int, int] = {}

        for r in range(1, filas_a_evaluar + 1):
            textos_unicos_fila = set()
            for c in range(1, max_c + 1):
                val = sheet.cell(row=r, column=c).value
                txt = str(val).strip() if val is not None else mapa_combinadas.get((r, c), "")
                if txt and len(txt) > 0:
                    textos_unicos_fila.add(txt)
            conteo_por_fila[r] = len(textos_unicos_fila)

        # Encontrar la fila con mayor diversidad de encabezados individuales
        for r, conteo in conteo_por_fila.items():
            if conteo > mejor_densidad and conteo >= 2:
                mejor_densidad = conteo
                candidato_encabezado = r

        if not candidato_encabezado:
            # No se detectaron encabezados claros
            return None, [], None, "REQUIERE_REVISION"

        # Verificar si la fila siguiente inmediata es un subencabezado
        fila_inicio_datos = candidato_encabezado + 1
        estado_inicio = "DETERMINADA"

        if candidato_encabezado + 1 <= max_r:
            conteo_siguiente = conteo_por_fila.get(candidato_encabezado + 1, 0)
            # Si la siguiente fila también tiene alta densidad de textos no numéricos, es subencabezado
            if conteo_siguiente >= 2:
                subencabezados.append(candidato_encabezado + 1)
                fila_inicio_datos = candidato_encabezado + 2

        # Si tras el bloque de cabeceras se encuentra vacío o sin estructura evidente, verificar ambigüedad
        if fila_inicio_datos > max_r + 1:
            estado_inicio = "REQUIERE_REVISION"

        return candidato_encabezado, subencabezados, fila_inicio_datos, estado_inicio
