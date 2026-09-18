"""
app.parsers.excel_parser

Parser para archivos Excel oficiales previamente diligenciados o listas de asistencia en formato Excel (.xlsx).
Preserva los valores originales de la fuente y los mapea al modelo interno.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import openpyxl
from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class ExcelAttendanceParser:
    """
    Parser para hojas de cálculo Excel.
    """

    @classmethod
    def parse_file(
        cls,
        ruta_archivo: Union[str, Path],
        nombre_actividad_default: str = "Actividad desde Excel",
        hoja_nombre: Optional[str] = None
    ) -> RawAttendanceSheetData:
        """
        Lee un archivo Excel y extrae encabezados y filas de participantes.
        """
        path = Path(ruta_archivo)
        if not path.exists():
            raise FileNotFoundError(f"Archivo Excel no encontrado: {path}")

        wb = openpyxl.load_workbook(path, data_only=True)
        sheet = wb[hoja_nombre] if hoja_nombre and hoja_nombre in wb.sheetnames else wb.active

        filas_participantes: List[RawParticipantRow] = []

        # Heurística simple para encontrar cabecera de columnas
        fila_cabecera = 1
        mapa_columnas: Dict[str, int] = {}

        for r_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            row_str = [str(c).strip().lower() if c is not None else "" for c in row]
            # Si encontramos palabras como 'nombre', 'cédula' o 'sexo' en la fila
            if any(k in row_str for k in ("nombre", "nombres", "participante", "nombre completo", "nombres y apellidos")):
                fila_cabecera = r_idx
                for c_idx, val in enumerate(row_str):
                    if "nombre" in val:
                        mapa_columnas["nombre"] = c_idx
                    elif "cédula" in val or "cedula" in val:
                        mapa_columnas["cedula"] = c_idx
                    elif "sexo" in val or "género" in val or "genero" in val:
                        mapa_columnas["sexo"] = c_idx
                    elif "edad" in val:
                        mapa_columnas["edad"] = c_idx
                    elif "carrera" in val or "especialidad" in val:
                        mapa_columnas["carrera"] = c_idx
                    elif "categoria" in val or "categoría" in val or "rol" in val:
                        mapa_columnas["categoria"] = c_idx
                    elif "área" in val or "area" in val:
                        mapa_columnas["area"] = c_idx
                    elif "teléfono" in val or "telefono" in val:
                        mapa_columnas["telefono"] = c_idx
                break

        # Leer filas de datos a partir de fila_cabecera + 1
        num_fila = 1
        for row in sheet.iter_rows(min_row=fila_cabecera + 1, values_only=True):
            if not any(row):
                continue
            
            nombre_idx = mapa_columnas.get("nombre", 0)
            nombre_val = str(row[nombre_idx]).strip() if nombre_idx < len(row) and row[nombre_idx] is not None else ""
            if not nombre_val:
                continue

            fila = RawParticipantRow(
                numero_fila=num_fila,
                hoja=1,
                nombre_completo=nombre_val,
                sexo=str(row[mapa_columnas["sexo"]]).strip() if "sexo" in mapa_columnas and mapa_columnas["sexo"] < len(row) and row[mapa_columnas["sexo"]] is not None else None,
                cedula=str(row[mapa_columnas["cedula"]]).strip() if "cedula" in mapa_columnas and mapa_columnas["cedula"] < len(row) and row[mapa_columnas["cedula"]] is not None else None,
                edad=row[mapa_columnas["edad"]] if "edad" in mapa_columnas and mapa_columnas["edad"] < len(row) and row[mapa_columnas["edad"]] is not None else None,
                carrera=str(row[mapa_columnas["carrera"]]).strip() if "carrera" in mapa_columnas and mapa_columnas["carrera"] < len(row) and row[mapa_columnas["carrera"]] is not None else None,
                categoria=str(row[mapa_columnas["categoria"]]).strip() if "categoria" in mapa_columnas and mapa_columnas["categoria"] < len(row) and row[mapa_columnas["categoria"]] is not None else None,
                area=str(row[mapa_columnas["area"]]).strip() if "area" in mapa_columnas and mapa_columnas["area"] < len(row) and row[mapa_columnas["area"]] is not None else None,
                telefono=str(row[mapa_columnas["telefono"]]).strip() if "telefono" in mapa_columnas and mapa_columnas["telefono"] < len(row) and row[mapa_columnas["telefono"]] is not None else None,
                fuente_origen=str(path.name)
            )
            filas_participantes.append(fila)
            num_fila += 1

        wb.close()

        return RawAttendanceSheetData(
            nombre_actividad=nombre_actividad_default,
            filas=filas_participantes,
            fuente_origen=str(path.name)
        )
