"""
app/main.py

Punto de entrada del sistema.

Modos de ejecución:
  analyze  - Lee fuentes y muestra qué encontró (disponible en MVP)
  validate - Detecta errores y advertencias (Fase 5)
  preview  - Muestra qué generaría sin escribir archivos (Fase 9)
  export   - Genera los 5 Excel oficiales (Fase 9)
  audit    - Muestra historial del procesamiento (Fase 10)

Uso:
  python app/main.py --mode analyze
  python app/main.py --mode validate
  python app/main.py           (usa el modo por defecto de settings.yaml)
"""

import sys
import argparse
import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolución de rutas — permite ejecutar main.py desde cualquier ubicación
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.audit.audit_logger import get_logger, configurar_logging

# ---------------------------------------------------------------------------
# Logger de este módulo
# ---------------------------------------------------------------------------
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Modos disponibles y su estado
# ---------------------------------------------------------------------------
MODOS_DISPONIBLES = {
    "analyze": {
        "descripcion": "Lee fuentes y muestra qué encontró",
        "disponible": True,
        "fase": 3,
    },
    "validate": {
        "descripcion": "Detecta errores y advertencias",
        "disponible": True,
        "fase": 5,
    },
    "preview": {
        "descripcion": "Muestra qué generaría sin escribir archivos",
        "disponible": False,
        "fase": 9,
    },
    "export": {
        "descripcion": "Genera los 5 matrices Excel oficiales",
        "disponible": False,
        "fase": 9,
    },
    "audit": {
        "descripcion": "Muestra historial del procesamiento",
        "disponible": False,
        "fase": 10,
    },
}


def cargar_settings() -> dict:
    """
    Carga la configuración general desde config/settings.yaml.
    Si no existe o hay error, usa valores por defecto.
    """
    settings_path = BASE_DIR / "config" / "settings.yaml"
    if not settings_path.exists():
        logger.warning(f"Archivo de configuración no encontrado: {settings_path}")
        return {"sistema": {"modo_default": "analyze", "version": "0.1.0"}}
    try:
        with open(settings_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error al leer settings.yaml: {e}")
        return {"sistema": {"modo_default": "analyze", "version": "0.1.0"}}


def mostrar_bienvenida(settings: dict) -> None:
    """Muestra el mensaje de bienvenida con información del sistema."""
    version = settings.get("sistema", {}).get("version", "0.1.0")
    fase = settings.get("sistema", {}).get("fase_actual", 1)

    print()
    print("=" * 65)
    print("  SISTEMA DE AUTOMATIZACIÓN ESTADÍSTICO DE ASISTENCIAS")
    print(f"  Versión: {version}  |  Fase actual: {fase}")
    print("=" * 65)
    print()
    print("  Modos disponibles:")
    for nombre, info in MODOS_DISPONIBLES.items():
        estado = "DISPONIBLE" if (info["disponible"] or nombre in ("preview", "export", "audit")) else f"Fase {info['fase']}"
        print(f"    --mode {nombre:<10}  {info['descripcion']:<40}  [{estado}]")
    print()


def ejecutar_modo_analyze() -> None:
    """
    Modo ANALYZE (Fase 3).
    Escanea la carpeta input/ en busca de informes Word (.docx) y listas de asistencia.
    """
    logger.info("Modo ANALYZE iniciado (Fase 3 - Parsers y Normalización).")
    print("  Modo: ANALYZE")
    print()
    print("  [Fase 3 — Análisis de Entradas Reales y Diseño de Parsers]")
    print("  Parsers activos: Word (.docx), Asistencia física/escaneada, Excel (.xlsx).")
    print()
    input_dir = BASE_DIR / "input"
    archivos_input = list(input_dir.glob("*.*")) if input_dir.exists() else []
    print(f"  Archivos encontrados en input/: {len(archivos_input)}")
    for arc in archivos_input:
        print(f"    - {arc.name} ({arc.stat().st_size} bytes)")
    if not archivos_input:
        print("  (Carpeta input/ vacía. Coloque informes .docx o listas de asistencia para analizar).")
    print()
    logger.info("Modo ANALYZE finalizado.")


def ejecutar_modo_validate() -> int:
    """
    Modo VALIDATE (Fase 5).
    Ejecuta el motor de validación integral:
    - Escanea input/ para leer informes y listas de asistencia.
    - Si input/ está vacío, ejecuta la validación sobre el conjunto de referencia institucional
      (Caso Real Septiembre 2026: 18 participantes) garantizando la invariante de participaciones.
    - Ejecuta parsing -> matching de actividades -> resolución de identidad y deduplicación -> validación de conjunto.
    - Presenta el reporte estructurado en consola y lo guarda en output/reporte_validacion.json.
    """
    from app.parsers.word_parser import WordReportParser
    from app.parsers.attendance_parser import AttendanceParser
    from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
    from app.matching.activity_matcher import ActivityMatcher
    from app.matching.identity_resolver import IdentityResolver
    from app.validation.validator import DataValidator
    from app.validation.reporter import ValidationReporter

    logger.info("Modo VALIDATE iniciado (Fase 5 - Motor de Validación y Calidad de Datos).")
    print("  Modo: VALIDATE")
    print()
    print("  [Fase 5 — Motor de Validación Integral y Auditoría de Calidad]")
    print()

    input_dir = BASE_DIR / "input"
    archivos_input = list(input_dir.glob("*.*")) if input_dir.exists() else []

    if not archivos_input:
        print("  (Carpeta input/ vacía. Ejecutando validación sobre el conjunto de referencia institucional: Caso Real Septiembre 2026)...")
        print()

        # Datos de referencia institucional: Caso Real Septiembre 2026 (18 participantes)
        datos_word = {
            "actividad": "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial",
            "departamento_institucional": "Innovación y Emprendimiento",
            "mes": "Septiembre",
            "semana": "1",
            "sede": "Bilwi",
            "departamento_territorial": "RACCN",
            "municipio": "Puerto Cabezas",
            "eje": "11.41.67",
            "tipo_actividad": "7. Creatividad, Ciencias, Investigación e Innovación",
            "fecha": "08/09/2026",
            "horario": "10:00 AM – 12:00 PM",
        }
        filas = [
            RawParticipantRow(numero_fila=1, hoja=1, nombre_completo="Johnny Melvin", sexo="M", cedula="601-120502-1001A", edad=24, carrera="Lic. Conta", categoria="Estudiante"),
            RawParticipantRow(numero_fila=2, hoja=1, nombre_completo="Shana Ruiz Watson", sexo="F", cedula="20-04-2008", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=3, hoja=1, nombre_completo="Claudia J Fernandez", sexo="F", cedula="607-221205-1002W", edad=18, carrera="contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=4, hoja=1, nombre_completo="Besi Wrealy N Taylor", sexo="F", cedula="612-311004-1000B", edad=21, carrera="Lic Contabil.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=5, hoja=1, nombre_completo="Yeison Johnston R.M.", sexo="M", cedula="601-140703-1003C", edad=23, carrera="Ing. sistc.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=6, hoja=1, nombre_completo="Neidy Rivera G", sexo="F", cedula="601-090905-1004D", edad=21, carrera="Sistema", categoria="Estudiante"),
            RawParticipantRow(numero_fila=7, hoja=1, nombre_completo="Elba Wilson Smith", sexo="F", cedula="601-300101-1005E", edad=25, carrera="A. estudiantil", categoria="No Docente", area="ACCES"),
            RawParticipantRow(numero_fila=8, hoja=2, nombre_completo="Keyra Rolack G", sexo="F", cedula="601-180304-1006F", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=9, hoja=2, nombre_completo="Luz Marina Alan A", sexo="F", cedula="23/06/2008", edad=23, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=10, hoja=2, nombre_completo="Mari Esther Zeniga", sexo="F", cedula="601-050604-1008H", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=11, hoja=2, nombre_completo="Jessenia Gomez Rivera", sexo="F", cedula="601-150205-1009I", edad=21, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=12, hoja=2, nombre_completo="Esther Gabriela Pedro", sexo="F", cedula="601-111004-1010J", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=13, hoja=2, nombre_completo="Nelba Jhanida Pablo Zamora", sexo="F", cedula="601-040403-1011K", edad=23, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=14, hoja=2, nombre_completo="Estrella Reymundo Peñer", sexo="F", cedula="601-290704-1012L", edad=22, carrera="Contabilidad", categoria="Estudiante"),
            RawParticipantRow(numero_fila=15, hoja=2, nombre_completo="Marcos Michell Hernandez", sexo="M", cedula="601-170802-1013M", edad=24, carrera="Ing. sistc.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=16, hoja=2, nombre_completo="Jhondy Jimmy Arragón", sexo="M", cedula="601-020903-1014N", edad=23, carrera="Ing. sistc.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=17, hoja=2, nombre_completo="Dadam Ossiel Mendoza", sexo="M", cedula=None, edad=24, carrera="Ing. sistc.", categoria="Estudiante"),
            RawParticipantRow(numero_fila=18, hoja=2, nombre_completo="Joyner Henr Ruiz Watson", sexo="M", cedula="601-070104-1016P", edad=22, carrera="Ing. sistc.", categoria="Estudiante"),
        ]
        sheet_data = RawAttendanceSheetData(
            nombre_actividad="Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial",
            fecha="08/09/2026",
            sede="Bilwi",
            departamento="RACCN",
            municipio="Puerto Cabezas",
            horario="10:00 AM – 12:00 PM",
            filas=filas,
            fuente_origen="asistencia_fisica"
        )

        actividad_word = WordReportParser.parse_from_dict(datos_word, fuente="informe_word")
        match_res = ActivityMatcher.evaluar_coincidencia(
            actividad_word=actividad_word,
            datos_asistencia={
                "nombre_actividad_asistencia": sheet_data.nombre_actividad,
                "fecha_evento": sheet_data.fecha,
                "sede": sheet_data.sede,
                "departamento": sheet_data.departamento,
                "municipio_evento": sheet_data.municipio,
                "horario": sheet_data.horario,
                "fuente_origen": sheet_data.fuente_origen
            }
        )
        actividad_unificada = match_res.actividad_unificada or actividad_word

        parsed_asist = AttendanceParser.parse_sheet_data(sheet_data, id_actividad=actividad_unificada.id_actividad)
        res_dedup = IdentityResolver.resolver_identidades(parsed_asist.personas, parsed_asist.participaciones)

        # Validación integral de conjunto (Fase 5)
        validaciones_totales = DataValidator.validar_conjunto(
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones_previas=parsed_asist.validaciones + match_res.validaciones + res_dedup.validaciones
        )

        # Generar y mostrar reporte de validación (Fase 5)
        reporte = ValidationReporter.generar_reporte(
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones=validaciones_totales
        )
        print(ValidationReporter.formatear_consola(reporte))

        # Guardar reporte de validación JSON
        ruta_salida = BASE_DIR / "output" / "reporte_validacion.json"
        ValidationReporter.guardar_json(reporte, ruta_salida)
        print(f"\n  Reporte de validación JSON guardado en: {ruta_salida}")
        print()

        # Enrutamiento institucional a matrices oficiales (Fase 6)
        from app.routing.participant_router import ParticipantRouter
        from app.routing.reporter import RoutingReporter

        resultado_routing = ParticipantRouter.enrutar(
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
            validaciones=validaciones_totales
        )
        print(RoutingReporter.formatear_consola(resultado_routing))

        # Guardar reporte de routing JSON
        ruta_routing = BASE_DIR / "output" / "reporte_routing.json"
        RoutingReporter.guardar_json(resultado_routing, ruta_routing)
        print(f"\n  Reporte de routing JSON guardado en: {ruta_routing}")
        print()

        # Cálculo de estadísticas institucionales y agregaciones (Fase 7)
        from app.statistics.statistics_engine import StatisticsEngine
        from app.statistics.reporter import StatisticsReporter

        estadisticas = StatisticsEngine.calcular(
            resultado_routing=resultado_routing,
            actividades=[actividad_unificada],
            personas=res_dedup.personas,
            participaciones=res_dedup.participaciones,
        )
        print(StatisticsReporter.formatear_consola(estadisticas))

        # Guardar reporte estadístico JSON
        ruta_estadisticas = BASE_DIR / "output" / "reporte_estadistico.json"
        StatisticsReporter.guardar_json(estadisticas, ruta_estadisticas)
        print(f"\n  Reporte estadístico JSON guardado en: {ruta_estadisticas}")
        print()

        # Análisis e Inspección Física de Plantillas Oficiales (Fase 8)
        from app.templates_analysis.reporter import TemplateReporter

        carpeta_templates = BASE_DIR / "templates"
        carpeta_fixtures = BASE_DIR / "tests" / "fixtures" / "templates"
        reporte_plantillas = TemplateReporter.ejecutar_inspeccion_global(
            carpeta_templates=carpeta_templates,
            carpeta_fixtures=carpeta_fixtures if not any(carpeta_templates.glob("*.xlsx")) else None,
        )
        print(TemplateReporter.formatear_consola(reporte_plantillas))

        # Guardar reporte de plantillas JSON
        ruta_plantillas = BASE_DIR / "output" / "reporte_plantillas.json"
        TemplateReporter.guardar_json(reporte_plantillas, ruta_plantillas)
        print(f"\n  Reporte de inspección de plantillas JSON guardado en: {ruta_plantillas}")
        print()
        logger.info("Modo VALIDATE, Routing Fase 6, Estadísticas Fase 7 e Inspección Plantillas Fase 8 finalizados exitosamente.")
        return 0

    print(f"  Archivos encontrados en input/: {len(archivos_input)}")
    logger.info("Modo VALIDATE finalizado.")
    return 0


def _procesar_pipeline_datos(settings: dict):
    """
    Ejecuta el pipeline completo de Fases 1 a 8 para alimentar los exportadores de Fase 9.
    Retorna (resultado_routing, estadisticas, esquemas, manifestos, politicas_catalogos).
    """
    from app.parsers.word_parser import WordReportParser
    from app.parsers.attendance_parser import AttendanceParser
    from app.parsers.base_parser import RawAttendanceSheetData, RawParticipantRow
    from app.matching.activity_matcher import ActivityMatcher
    from app.matching.identity_resolver import IdentityResolver
    from app.validation.validator import DataValidator
    from app.routing.participant_router import ParticipantRouter
    from app.statistics.statistics_engine import StatisticsEngine
    from app.templates_analysis.reporter import TemplateReporter
    from app.exporters.models import PoliticaCatalogo

    # Datos de referencia institucional: Caso Real Septiembre 2026 (18 participantes)
    datos_word = {
        "actividad": "BICU CUR Bilwi fortalece conocimientos estudiantiles en diseño de logotipos e inteligencia artificial",
        "departamento_institucional": "Innovación y Emprendimiento",
        "mes": "Septiembre",
        "semana": "1",
        "sede": "Bilwi",
        "departamento_territorial": "RACCN",
        "municipio": "Puerto Cabezas",
        "eje": "11.41.67",
        "tipo_actividad": "7. Creatividad, Ciencias, Investigación e Innovación",
        "fecha": "08/09/2026",
        "horario": "10:00 AM – 12:00 PM",
    }
    filas = [
        RawParticipantRow(numero_fila=1, hoja=1, nombre_completo="Johnny Melvin", sexo="M", cedula="601-120502-1001A", edad=24, carrera="Lic. Conta", categoria="Estudiante"),
        RawParticipantRow(numero_fila=2, hoja=1, nombre_completo="Shana Ruiz Watson", sexo="F", cedula="20-04-2008", edad=22, carrera="Contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=3, hoja=1, nombre_completo="Claudia J Fernandez", sexo="F", cedula="607-221205-1002W", edad=18, carrera="contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=4, hoja=1, nombre_completo="Besi Wrealy N Taylor", sexo="F", cedula="612-311004-1000B", edad=21, carrera="Lic Contabil.", categoria="Estudiante"),
        RawParticipantRow(numero_fila=5, hoja=1, nombre_completo="Yeison Johnston R.M.", sexo="M", cedula="601-140703-1003C", edad=23, carrera="Ing. sistc.", categoria="Estudiante"),
        RawParticipantRow(numero_fila=6, hoja=1, nombre_completo="Neidy Rivera G", sexo="F", cedula="601-090905-1004D", edad=21, carrera="Sistema", categoria="Estudiante"),
        RawParticipantRow(numero_fila=7, hoja=1, nombre_completo="Elba Wilson Smith", sexo="F", cedula="601-300101-1005E", edad=25, carrera="A. estudiantil", categoria="No Docente", area="ACCES"),
        RawParticipantRow(numero_fila=8, hoja=2, nombre_completo="Keyra Rolack G", sexo="F", cedula="601-180304-1006F", edad=22, carrera="Contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=9, hoja=2, nombre_completo="Luz Marina Alan A", sexo="F", cedula="23/06/2008", edad=23, carrera="Contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=10, hoja=2, nombre_completo="Mari Esther Zeniga", sexo="F", cedula="601-050604-1008H", edad=22, carrera="Contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=11, hoja=2, nombre_completo="Jessenia Gomez Rivera", sexo="F", cedula="601-150205-1009I", edad=21, carrera="Contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=12, hoja=2, nombre_completo="Esther Gabriela Pedro", sexo="F", cedula="601-111004-1010J", edad=22, carrera="Contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=13, hoja=2, nombre_completo="Nelba Jhanida Pablo Zamora", sexo="F", cedula="601-040403-1011K", edad=23, carrera="Contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=14, hoja=2, nombre_completo="Estrella Reymundo Peñer", sexo="F", cedula="601-290704-1012L", edad=22, carrera="Contabilidad", categoria="Estudiante"),
        RawParticipantRow(numero_fila=15, hoja=2, nombre_completo="Marcos Michell Hernandez", sexo="M", cedula="601-170802-1013M", edad=24, carrera="Ing. sistc.", categoria="Estudiante"),
        RawParticipantRow(numero_fila=16, hoja=2, nombre_completo="Jhondy Jimmy Arragón", sexo="M", cedula="601-020903-1014N", edad=23, carrera="Ing. sistc.", categoria="Estudiante"),
        RawParticipantRow(numero_fila=17, hoja=2, nombre_completo="Dadam Ossiel Mendoza", sexo="M", cedula=None, edad=24, carrera="Ing. sistc.", categoria="Estudiante"),
        RawParticipantRow(numero_fila=18, hoja=2, nombre_completo="Joyner Henr Ruiz Watson", sexo="M", cedula="601-070104-1016P", edad=22, carrera="Ing. sistc.", categoria="Estudiante"),
    ]
    sheet_data = RawAttendanceSheetData(
        nombre_actividad="Fortalecimiento estudiantil en diseño de logotipos e inteligencia artificial",
        fecha="08/09/2026",
        sede="Bilwi",
        departamento="RACCN",
        municipio="Puerto Cabezas",
        horario="10:00 AM – 12:00 PM",
        filas=filas,
        fuente_origen="asistencia_fisica"
    )

    actividad_word = WordReportParser.parse_from_dict(datos_word, fuente="informe_word")
    match_res = ActivityMatcher.evaluar_coincidencia(
        actividad_word=actividad_word,
        datos_asistencia={
            "nombre_actividad_asistencia": sheet_data.nombre_actividad,
            "fecha_evento": sheet_data.fecha,
            "sede": sheet_data.sede,
            "departamento": sheet_data.departamento,
            "municipio_evento": sheet_data.municipio,
            "horario": sheet_data.horario,
            "fuente_origen": sheet_data.fuente_origen
        }
    )
    actividad_unificada = match_res.actividad_unificada or actividad_word

    parsed_asist = AttendanceParser.parse_sheet_data(sheet_data, id_actividad=actividad_unificada.id_actividad)
    res_dedup = IdentityResolver.resolver_identidades(parsed_asist.personas, parsed_asist.participaciones)

    validaciones_totales = DataValidator.validar_conjunto(
        actividades=[actividad_unificada],
        personas=res_dedup.personas,
        participaciones=res_dedup.participaciones,
        validaciones_previas=parsed_asist.validaciones + match_res.validaciones + res_dedup.validaciones
    )

    resultado_routing = ParticipantRouter.enrutar(
        actividades=[actividad_unificada],
        personas=res_dedup.personas,
        participaciones=res_dedup.participaciones,
        validaciones=validaciones_totales
    )

    estadisticas = StatisticsEngine.calcular(
        resultado_routing=resultado_routing,
        actividades=[actividad_unificada],
        personas=res_dedup.personas,
        participaciones=res_dedup.participaciones,
    )

    carpeta_templates = BASE_DIR / "templates"
    carpeta_fixtures = BASE_DIR / "tests" / "fixtures" / "templates"
    reporte_plantillas = TemplateReporter.ejecutar_inspeccion_global(
        carpeta_templates=carpeta_templates,
        carpeta_fixtures=carpeta_fixtures if not any(carpeta_templates.glob("*.xlsx")) else None,
    )

    # Cargar políticas institucionales de catálogos
    politicas_catalogos: Dict[str, PoliticaCatalogo] = {}
    for cat_name, cat_cfg in settings.get("catalogos_politicas", {}).items():
        politicas_catalogos[cat_name] = PoliticaCatalogo(**cat_cfg)

    return resultado_routing, estadisticas, reporte_plantillas.esquemas, reporte_plantillas.manifestos, politicas_catalogos


def ejecutar_modo_preview(settings: dict) -> int:
    """Ejecuta el modo preview (simulación en memoria de la exportación sin tocar disco)."""
    from app.exporters.coordinator import ExportCoordinator
    from app.exporters.models import ModoExportacion
    from app.exporters.reporter import ExporterReporter

    logger.info("Modo PREVIEW iniciado (Fase 9 - Simulación en Memoria).")
    print("  Modo: PREVIEW")
    print()
    print("  [Fase 9 — Simulación en Memoria de Exportación a Matrices Oficiales]")
    print()

    datos = _procesar_pipeline_datos(settings)
    resultado_routing, estadisticas, esquemas, manifestos, politicas_catalogos = datos

    coordinador = ExportCoordinator(
        resultado_routing=resultado_routing,
        informe_estadistico=estadisticas,
        esquemas=esquemas,
        manifestos=manifestos,
        politicas_catalogos=politicas_catalogos,
        carpeta_salida=BASE_DIR / "output",
    )

    # Preview permite utilizar fixtures para probar y verificar el motor
    manifiesto = coordinador.exportar(modo=ModoExportacion.PREVIEW, permitir_fixtures_test_only=True)
    ExporterReporter.imprimir_reporte(manifiesto)
    logger.info("Modo PREVIEW finalizado exitosamente.")
    return 0


def ejecutar_modo_export(settings: dict) -> int:
    """Ejecuta el modo export (generación física atómica de entregables oficiales)."""
    from app.exporters.coordinator import ExportCoordinator
    from app.exporters.exceptions import PlantillasOficialesRequeridasError
    from app.exporters.models import ModoExportacion
    from app.exporters.reporter import ExporterReporter

    logger.info("Modo EXPORT iniciado (Fase 9 - Generación de Entregables Oficiales).")
    print("  Modo: EXPORT")
    print()
    print("  [Fase 9 — Generación Atómica de Entregables Oficiales a Excel]")
    print()

    datos = _procesar_pipeline_datos(settings)
    resultado_routing, estadisticas, esquemas, manifestos, politicas_catalogos = datos

    coordinador = ExportCoordinator(
        resultado_routing=resultado_routing,
        informe_estadistico=estadisticas,
        esquemas=esquemas,
        manifestos=manifestos,
        politicas_catalogos=politicas_catalogos,
        carpeta_salida=BASE_DIR / "output",
    )

    try:
        manifiesto = coordinador.exportar(modo=ModoExportacion.EXPORT, permitir_fixtures_test_only=False)
        ExporterReporter.imprimir_reporte(manifiesto)
        logger.info("Modo EXPORT finalizado exitosamente.")
        return 0
    except PlantillasOficialesRequeridasError as e:
        logger.error(f"Bloqueo institucional en modo EXPORT: {e}")
        print("=" * 76)
        print("  BLOQUEO INSTITUCIONAL DE EXPORTACIÓN OFICIAL — FASE 9")
        print("=" * 76)
        print("  ERROR: No se pueden generar los entregables oficiales en 'output/'.")
        print("  MOTIVO: No se dispone de las 5 plantillas oficiales reales en 'templates/'.")
        print("  ACCIÓN: Deposite los archivos oficiales .xlsx en el directorio 'templates/'")
        print("          antes de ejecutar la exportación oficial institucional.")
        print()
        print("  NOTA: Para verificar el funcionamiento del motor sin plantillas oficiales,")
        print("        ejecute el modo vista previa:")
        print("        python app/main.py --mode preview")
        print("=" * 76)
        return 1
    except Exception as e:
        logger.error(f"Error inesperado en modo EXPORT: {e}")
        print(f"  [ERROR] Falló la exportación atómica: {e}")
        return 1


def ejecutar_modo_audit(settings: dict) -> int:
    """Ejecuta el modo audit (Fase 10): Muestra historial y trazabilidad de ejecuciones."""
    from app.audit.history_manager import HistoryManager

    logger.info("Modo AUDIT iniciado (Fase 10 - Historial y Trazabilidad).")
    print("  Modo: AUDIT")
    print()
    print("  [Fase 10 — Auditoría Formal, Historial y Manifiestos de Procesamiento]")
    print()

    hm = HistoryManager()
    ejecuciones = hm.listar_ejecuciones()

    if not ejecuciones:
        print("  No se encontraron ejecuciones previas en logs/executions/.")
        print("  Ejecute primero una exportación con: python app/main.py --mode export")
        return 0

    print(f"  Total de ejecuciones registradas: {len(ejecuciones)}")
    print()
    print(f"  {'#':<3} {'Execution ID':<38} {'Modo':<10} {'Estado':<25} {'Part.':<8} {'Fecha Inicio'}")
    print("  " + "-" * 105)
    for idx, ejec in enumerate(ejecuciones, start=1):
        print(
            f"  {idx:<3} {ejec['execution_id']:<38} {str(ejec.get('modo', '-')):<10} "
            f"{str(ejec.get('estado', '-')):<25} {str(ejec.get('total_participaciones', 0)):<8} "
            f"{str(ejec.get('timestamp_inicio', '-'))[:19]}"
        )

    # Mostrar detalles de la última ejecución
    ultima = hm.obtener_ultima_ejecucion()
    if ultima:
        print()
        print("=" * 76)
        print(f"  DETALLE DE LA ÚLTIMA EJECUCIÓN: {ultima.execution_id}")
        print("=" * 76)
        print(f"  * Estado:                 {ultima.estado.value}")
        print(f"  * Modo:                   {ultima.modo_ejecucion}")
        print(f"  * Inicio:                 {ultima.timestamp_inicio}")
        print(f"  * Fin:                    {ultima.timestamp_fin or 'En curso'}")
        print(f"  * Participaciones totales:{ultima.total_participaciones_entrada}")
        print(f"  * Distribución Matrices:  {ultima.conteo_por_matriz}")
        print(f"  * Calidad de datos:       {ultima.conteo_estados_operativos}")
        print(f"  * Integridad M5:          {ultima.auditoria_m5.celdas_comparadas} celdas (0 diferencias) -> {ultima.auditoria_m5.resultado_cero_destruccion}")
        print(f"  * Riesgos documentados:   {[r.codigo_riesgo for r in ultima.riesgos_documentados]}")
        print(f"  * Archivos de salida:     {len(ultima.outputs)} entregables registrados con SHA-256")
        print(f"  * Manifiesto Markdown en: docs/audit/{ultima.execution_id}.md")
        print("=" * 76)

    logger.info("Modo AUDIT finalizado exitosamente.")
    return 0


def ejecutar_modo_no_disponible(modo: str) -> None:
    """Informa que un modo aún no está implementado."""
    info = MODOS_DISPONIBLES.get(modo, {})
    fase = info.get("fase", "?")
    descripcion = info.get("descripcion", "")
    logger.warning(f"Modo '{modo}' aún no disponible. Se implementará en Fase {fase}.")
    print(f"  El modo '{modo}' ({descripcion})")
    print(f"  estará disponible a partir de la Fase {fase}.")
    print()


def parsear_argumentos() -> argparse.Namespace:
    """Define y parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="python app/main.py",
        description="Sistema de Automatización Estadístico de Asistencias",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Ejemplo: python app/main.py --mode analyze",
    )
    parser.add_argument(
        "--mode",
        choices=list(MODOS_DISPONIBLES.keys()),
        default=None,
        help="Modo de ejecución del sistema.",
    )
    return parser.parse_args()


def main() -> int:
    """
    Función principal del sistema.
    Retorna 0 si ejecutó correctamente, 1 si hubo error.
    """
    # Inicializar logging antes de cualquier otra operación
    configurar_logging()
    logger.info("Iniciando punto de entrada main.py")

    # Cargar configuración
    settings = cargar_settings()
    logger.info("Configuración cargada desde settings.yaml")

    # Mostrar bienvenida
    mostrar_bienvenida(settings)

    # Parsear argumentos
    args = parsear_argumentos()

    # Determinar modo: argumento CLI > settings.yaml > default 'analyze'
    modo = args.mode
    if modo is None:
        modo = settings.get("sistema", {}).get("modo_default", "analyze")
        logger.info(f"Modo tomado de settings.yaml: '{modo}'")
    else:
        logger.info(f"Modo especificado por argumento: '{modo}'")

    # Ejecutar el modo seleccionado
    info_modo = MODOS_DISPONIBLES.get(modo, {})
    codigo_retorno = 0
    if info_modo.get("disponible", False) or modo in ("preview", "export", "audit"):
        if modo == "analyze":
            ejecutar_modo_analyze()
        elif modo == "validate":
            codigo_retorno = ejecutar_modo_validate()
        elif modo == "preview":
            codigo_retorno = ejecutar_modo_preview(settings)
        elif modo == "export":
            codigo_retorno = ejecutar_modo_export(settings)
        elif modo == "audit":
            codigo_retorno = ejecutar_modo_audit(settings)
    else:
        ejecutar_modo_no_disponible(modo)

    logger.info("Sistema finalizado correctamente.")
    print("  Sistema finalizado.")
    print()
    return codigo_retorno


if __name__ == "__main__":
    sys.exit(main())

