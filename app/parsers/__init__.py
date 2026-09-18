"""
app.parsers

Módulo de parsers y extracción de datos desde fuentes heterogéneas:
- WordReportParser: lectura de informes semanales Word (.docx).
- AttendanceParser: lectura y procesamiento de listas de asistencia físicas/escaneadas.
- ExcelAttendanceParser: lectura de archivos Excel (.xlsx).
"""

from app.parsers.base_parser import (
    RawActivityData,
    RawParticipantRow,
    RawAttendanceSheetData,
    ParsedAttendanceResult,
)
from app.parsers.word_parser import WordReportParser
from app.parsers.attendance_parser import AttendanceParser
from app.parsers.excel_parser import ExcelAttendanceParser

__all__ = [
    "RawActivityData",
    "RawParticipantRow",
    "RawAttendanceSheetData",
    "ParsedAttendanceResult",
    "WordReportParser",
    "AttendanceParser",
    "ExcelAttendanceParser",
]
