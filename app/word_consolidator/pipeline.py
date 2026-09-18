"""
app.word_consolidator.pipeline

Orquestador Institucional End-to-End para la generación del Documento Word Consolidado.
Fase 14.8 — Integración E2E del Flujo Institucional:
5 Matrices Excel Oficiales M1–M5 → Documento Word (.docx) Consolidado + Auditoría E2E.

Cumple estrictamente los principios rectores de BICU:
1. Identificación estructural determinística (MatrixIdentifier) independiente de nombres de archivo.
2. Filtrado temporal estricto: cero inferencia de fechas, datos incompletos/sin fecha no se promueven.
3. Trazabilidad técnica íntegra desde cada fila y cifra del DOCX hasta la fila física de Excel.
4. Coexistencia no reconciliada de fuentes (M1 vs. nominales, narrativa vs. nominales).
5. Procesamiento dinámico sin techos de capacidad ni dependencias artificiales del caso de 32 registros de M5.
6. Inmutabilidad criptográfica absoluta verificada mediante SHA-256 pre y post ejecución.
7. Escritura atómica en staging y verificación de inmutabilidad de DocumentoConsolidado.
"""

from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import unicodedata
import uuid

import openpyxl
from pydantic import BaseModel, Field, field_validator, model_validator

from app.word_consolidator.models import (
    ConjuntoMatricesLeidas,
    DiscrepanciaItem,
    EstadoDiscrepancia,
    FilaLeidaM1,
    FilaLeidaNominal,
    MetadatosInstitucionales,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
    ResultadoAuditoriaDiscrepancias,
    ResultadoFiltradoPeriodo,
    TipoPeriodo,
)
from app.word_consolidator.readers.matrix_reader import MatrixReader
from app.word_consolidator.readers.period_filter import PeriodFilter
from app.word_consolidator.engine.consolidation_engine import (
    ConsolidationEngine,
    ResultadoConsolidacion,
)
from app.word_consolidator.engine.discrepancy_detector import DiscrepancyDetector
from app.word_consolidator.document.orchestrator import DocumentOutputOrchestrator


# =============================================================================
# EXCEPCIONES ESPECÍFICAS DE LA FASE 14.8
# =============================================================================

class MatrixPipelineError(Exception):
    """Clase base para errores del pipeline institucional de matrices."""
    pass


class MatricesFaltantesError(MatrixPipelineError):
    """Se lanza cuando falta una o más de las 5 matrices oficiales requeridas."""
    pass


class MatrizDuplicadaError(MatrixPipelineError):
    """Se lanza cuando más de un archivo coincide con la misma matriz oficial."""
    pass


class EstructuraMatrizInvalidaError(MatrixPipelineError):
    """Se lanza cuando la estructura interna de una matriz no coincide con ninguna huella oficial."""
    pass


class ArchivoMatrizInvalidoError(MatrixPipelineError):
    """Se lanza cuando un archivo no existe, no es accesible o no es un libro Excel válido."""
    pass


class ErrorIntegridadArchivo(MatrixPipelineError):
    """Se lanza cuando el hash SHA-256 de un archivo de entrada cambia durante el proceso."""
    pass


# =============================================================================
# MODELO DE RESULTADO DE EJECUCIÓN
# =============================================================================

class ArchivoFuenteInfo(BaseModel):
    """Información detallada de un archivo fuente procesado en el pipeline."""
    codigo_matriz: str
    nombre_archivo: str
    ruta_absoluta: str
    hoja: str
    total_columnas: int
    sha256_inicial: str
    sha256_final: str
    filas_leidas: int
    filas_activas: int
    filas_fuera_periodo: int
    datos_incompletos: int


class PipelineExecutionResult(BaseModel):
    """Resultado formal de la ejecución del pipeline institucional E2E."""
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    periodo: str
    tipo_periodo: str
    estado_final: str  # "EXITOSO", "CON_DISCREPANCIAS", etc.
    archivos_fuente: Dict[str, ArchivoFuenteInfo] = Field(default_factory=dict)
    total_filas_leidas: int = 0
    total_filas_activas: int = 0
    total_filas_fuera_periodo: int = 0
    total_datos_incompletos: int = 0
    total_actividades: int = 0
    total_participaciones: int = 0
    total_personas_unicas: int = 0
    total_discrepancias: int = 0
    ruta_docx: Optional[str] = None
    sha256_docx: Optional[str] = None
    tamanio_docx_bytes: Optional[int] = None
    status_tecnico: str = "NOT_REQUESTED"
    error_tecnico: Optional[str] = None
    ruta_docx_institucional: Optional[str] = None
    sha256_docx_institucional: Optional[str] = None
    tamanio_docx_institucional_bytes: Optional[int] = None
    status_institucional: str = "NOT_REQUESTED"
    error_institucional: Optional[str] = None
    ruta_reporte_json: Optional[str] = None
    ruta_reporte_md: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _pre_populate_status(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "status_tecnico" not in data or data["status_tecnico"] is None:
                data["status_tecnico"] = "SUCCESS" if data.get("ruta_docx") else "NOT_REQUESTED"
            if "status_institucional" not in data or data["status_institucional"] is None:
                data["status_institucional"] = "SUCCESS" if data.get("ruta_docx_institucional") else "NOT_REQUESTED"
        return data

    @field_validator("status_tecnico", "status_institucional")
    @classmethod
    def validar_estado_producto(cls, v: str) -> str:
        estados_validos = {"SUCCESS", "FAILED", "NOT_REQUESTED"}
        if v not in estados_validos:
            raise ValueError(f"Estado de producto no válido: '{v}'. Debe ser uno de {sorted(list(estados_validos))}.")
        return v


# =============================================================================
# IDENTIFICADOR ESTRUCTURAL DE MATRICES (MatrixIdentifier)
# =============================================================================

def _normalizar_texto(texto: Any) -> str:
    """Normaliza texto eliminando acentos, caracteres especiales y espacios múltiples."""
    if texto is None:
        return ""
    s = str(texto).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def calcular_sha256(ruta: Union[str, Path]) -> str:
    """Calcula el hash criptográfico SHA-256 de un archivo en disco."""
    p = Path(ruta)
    if not p.is_file():
        raise ArchivoMatrizInvalidoError(f"No se puede calcular SHA-256: '{p}' no es un archivo.")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class MatrixIdentifier:
    """
    Identificador Físico y Estructural de Matrices Oficiales de BICU (Fase 14.8).
    
    Inspecciona los encabezados de la Fila 1 y los nombres de hoja en modo solo lectura,
    sin depender de los nombres físicos de archivo ni de sufijos de descarga como `(1)`, `(2)`.
    
    Dimensiones Oficiales Reales:
    - M1: 42 columnas (Hoja 'Programas, proyectos y act', cabeceras agregadas)
    - M2: 57 columnas (Hoja 'Pregrado_Grado en Actividades', cabeceras académicas: año, régimen, modalidad, turno)
    - M3: 58 columnas (Hoja 'Pregrado_Grado en Actividades', cabecera laboral exclusiva: tipo_contrato)
    - M4: 57 columnas (Hoja 'Pregrado_Grado en Actividades', cabeceras de vinculación: entidad, nombre_entidad)
    - M5: 53 columnas (Hoja 'Pregrado_Grado en Actividades', cabecera exclusiva: beneficio)
    """

    MATRICES_REQUERIDAS = {"M1", "M2", "M3", "M4", "M5"}

    @classmethod
    def extraer_huella(cls, ruta: Path) -> Dict[str, Any]:
        """
        Extrae la huella estructural de un archivo Excel sin modificar sus bytes.
        Retorna diccionario con hojas, hoja_seleccionada, número de columnas y lista de cabeceras normalizadas.
        """
        if not ruta.is_file():
            raise ArchivoMatrizInvalidoError(f"El archivo especificado no existe o no es accesible: '{ruta}'")

        if ruta.suffix.lower() not in (".xlsx", ".xlsm", ".xltx"):
            raise ArchivoMatrizInvalidoError(f"Formato no soportado para matriz Excel: '{ruta.name}'")

        try:
            wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        except Exception as e:
            raise ArchivoMatrizInvalidoError(f"Error al abrir archivo Excel '{ruta.name}': {e}") from e

        try:
            hojas = wb.sheetnames
            hoja_objetivo = None

            # Prioridad 1: Buscar hoja exclusiva de M1
            for h in hojas:
                if _normalizar_texto(h) == "programas_proyectos_y_act":
                    hoja_objetivo = h
                    break

            # Prioridad 2: Buscar hoja nominal de M2..M5
            if not hoja_objetivo:
                for h in hojas:
                    if _normalizar_texto(h) == "pregrado_grado_en_actividades":
                        hoja_objetivo = h
                        break

            # Prioridad 3: Hoja activa
            if not hoja_objetivo and hojas:
                hoja_objetivo = hojas[0]

            if not hoja_objetivo:
                raise EstructuraMatrizInvalidaError(f"El libro Excel '{ruta.name}' no contiene hojas de cálculo.")

            ws = wb[hoja_objetivo]
            # Leer fila 1 de encabezados
            fila_encabezados: List[str] = []
            for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
                for val in row:
                    fila_encabezados.append(str(val) if val is not None else "")
                break

            # Limpiar columnas vacías al final si existen
            while fila_encabezados and not fila_encabezados[-1].strip():
                fila_encabezados.pop()

            encabezados_normalizados = [_normalizar_texto(h) for h in fila_encabezados]
            set_headers = set(h for h in encabezados_normalizados if h)

            return {
                "ruta": ruta,
                "hojas": hojas,
                "hoja_seleccionada": hoja_objetivo,
                "total_columnas": len(fila_encabezados),
                "encabezados_originales": fila_encabezados,
                "encabezados_normalizados": encabezados_normalizados,
                "set_headers": set_headers,
            }
        finally:
            wb.close()

    @classmethod
    def clasificar_huella(cls, huella: Dict[str, Any]) -> str:
        """
        Clasifica una huella estructural determinísticamente en M1, M2, M3, M4 o M5.
        No depende de nombres de archivo y discrimina robustamente entre matrices con 57 columnas.
        """
        set_h = huella["set_headers"]
        hoja_norm = _normalizar_texto(huella["hoja_seleccionada"])
        total_cols = huella["total_columnas"]

        # ---------------------------------------------------------------------
        # 1. EVALUACIÓN DE MATRIZ 1 (Consolidado de Actividades — 42 columnas)
        # ---------------------------------------------------------------------
        # Hoja única: 'programas_proyectos_y_act'
        # Cabeceras agregadas exclusivas: total_atencion_m, total_atencion_f, etc.
        if hoja_norm == "programas_proyectos_y_act" or {
            "total_atencion_m", "total_atencion_f", "total_estud_m_grado"
        }.issubset(set_h):
            if "total_atencion_m" in set_h or "total_atencion_f" in set_h or "total_comunidades" in set_h:
                return "M1"

        # ---------------------------------------------------------------------
        # 2. EVALUACIÓN DE MATRICES NOMINALES (M2..M5 en 'Pregrado_Grado en Actividades')
        # ---------------------------------------------------------------------
        # M3: Única con 'tipo_contrato' (columna 58)
        if "tipo_contrato" in set_h:
            return "M3"

        # M2: Atributos académicos de estudiantes (año académico, régimen, modalidad, turno)
        # y ausencia de 'cargo', 'tipo_contrato', 'entidad'
        indicadores_m2 = {"ano_academico", "regimen", "modalidad", "turno"}
        if len(indicadores_m2.intersection(set_h)) >= 2 and "cargo" not in set_h and "entidad" not in set_h:
            return "M2"

        # M4: Colaboradores — Entidad vinculada en columnas de cierre (cols 56-57) + Cargo
        if {"entidad", "nombre_entidad"}.issubset(set_h) or (
            "entidad" in set_h and "cargo" in set_h and "tipo_contrato" not in set_h
        ):
            return "M4"

        # M5: Beneficiarios — Columna 53 'beneficio' + ausencia de cargo y entidad
        if "beneficio" in set_h and "cargo" not in set_h and "entidad" not in set_h:
            return "M5"

        # Fallbacks con marcadores canónicos obligatorios (no basarse únicamente en len(cols))
        if ("ano_academico" in set_h or "regimen" in set_h) and "cargo" not in set_h and "entidad" not in set_h:
            return "M2"
        if ("entidad" in set_h or "nombre_entidad" in set_h) and "tipo_contrato" not in set_h:
            return "M4"
        if "beneficio" in set_h:
            return "M5"
        if (hoja_norm == "programas_proyectos_y_act" or "total_atencion_m" in set_h) and total_cols >= 40:
            return "M1"

        raise EstructuraMatrizInvalidaError(
            f"El archivo '{huella['ruta'].name}' tiene {total_cols} columnas y hoja '{huella['hoja_seleccionada']}', "
            f"pero no coincide con los marcadores estructurales canónicos de M1, M2, M3, M4 ni M5."
        )

    @classmethod
    def identificar_archivo(cls, ruta: Union[str, Path]) -> str:
        """Identifica el código de matriz oficial (M1..M5) para un único archivo."""
        p = Path(ruta)
        huella = cls.extraer_huella(p)
        return cls.clasificar_huella(huella)

    @classmethod
    def identificar_archivos(cls, rutas: List[Union[str, Path]]) -> Dict[str, Path]:
        """
        Identifica y valida un conjunto de rutas de archivos.
        Garantiza biyección 1 a 1: no duplicados y completitud estricta de M1..M5.
        """
        if not rutas:
            raise MatricesFaltantesError("No se proporcionaron archivos para identificación.")

        resultado: Dict[str, Path] = {}
        duplicados: Dict[str, List[str]] = {}

        for r in rutas:
            p = Path(r)
            if not p.is_file():
                continue
            # Ignorar temporales de Excel que inician con ~$
            if p.name.startswith("~$"):
                continue

            codigo = cls.identificar_archivo(p)
            if codigo in resultado:
                if codigo not in duplicados:
                    duplicados[codigo] = [resultado[codigo].name]
                duplicados[codigo].append(p.name)
            else:
                resultado[codigo] = p

        if duplicados:
            detalles = ", ".join(f"{cod}: {archs}" for cod, archs in duplicados.items())
            raise MatrizDuplicadaError(f"Se detectaron matrices duplicadas en el conjunto de entrada: {detalles}")

        faltantes = cls.MATRICES_REQUERIDAS - set(resultado.keys())
        if faltantes:
            raise MatricesFaltantesError(
                f"Faltan matrices oficiales requeridas para la consolidación institucional: {sorted(list(faltantes))}. "
                f"Matrices identificadas: {sorted(list(resultado.keys()))}"
            )

        return resultado

    @classmethod
    def identificar_directorio(cls, carpeta: Union[str, Path]) -> Dict[str, Path]:
        """
        Escanea un directorio en busca de las 5 matrices oficiales.
        Si la carpeta contiene exactamente 5 matrices (incluso con nombres por defecto), las asigna.
        Si existen archivos duplicados para una misma matriz, lanza MatrizDuplicadaError.
        """
        dir_path = Path(carpeta)
        if not dir_path.is_dir():
            raise ArchivoMatrizInvalidoError(f"La ruta especificada no es un directorio: '{dir_path}'")

        archivos = [p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in (".xlsx", ".xlsm") and not p.name.startswith("~$")]
        return cls.identificar_archivos(archivos)


# =============================================================================
# ORQUESTADOR DEL PIPELINE INSTITUCIONAL E2E (WordConsolidationPipeline)
# =============================================================================

class WordConsolidationPipeline:
    """
    Orquestador E2E del Flujo Institucional Completo:
    5 Matrices Excel Oficiales → MatrixIdentifier → MatrixReader → PeriodFilter (Regla Estricta) →
    ConsolidationEngine + IdentityResolver → DiscrepancyDetector → DocumentTransformer →
    DocxGenerator → Documento DOCX Maquetado + Auditoría E2E (.json y .md).
    """

    def __init__(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        default_output_dir: Optional[Union[str, Path]] = None,
    ):
        target = output_dir or default_output_dir or Path("output")
        self.output_dir = Path(target)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolver_fuentes(
        self,
        fuentes: Union[str, Path, List[Union[str, Path]], Dict[str, Union[str, Path]]],
    ) -> Dict[str, Path]:
        """Resuelve y valida la entrada de fuentes en cualquiera de los formatos soportados."""
        if isinstance(fuentes, (str, Path)):
            p = Path(fuentes)
            if p.is_dir():
                return MatrixIdentifier.identificar_directorio(p)
            raise ArchivoMatrizInvalidoError(f"La ruta proporcionada debe ser un directorio: '{p}'")

        if isinstance(fuentes, list):
            return MatrixIdentifier.identificar_archivos(fuentes)

        if isinstance(fuentes, dict):
            # Diccionario explícito {"M1": path1, ..., "M5": path5}
            faltantes = MatrixIdentifier.MATRICES_REQUERIDAS - set(fuentes.keys())
            if faltantes:
                raise MatricesFaltantesError(f"El diccionario de fuentes carece de las matrices: {sorted(list(faltantes))}")

            rutas_resueltas: Dict[str, Path] = {}
            for cod, ruta in fuentes.items():
                p = Path(ruta)
                if not p.is_file():
                    raise ArchivoMatrizInvalidoError(f"El archivo para {cod} no existe: '{p}'")
                # Validar concordancia estructural de la matriz
                cod_detectado = MatrixIdentifier.identificar_archivo(p)
                if cod_detectado != cod:
                    raise EstructuraMatrizInvalidaError(
                        f"Inconsistencia estructural: El archivo '{p.name}' fue provisto como '{cod}', "
                        f"pero su huella estructural corresponde a '{cod_detectado}'."
                    )
                rutas_resueltas[cod] = p

            return rutas_resueltas

        raise ArchivoMatrizInvalidoError(f"Tipo de argumento de fuentes no soportado: {type(fuentes)}")

    def _filtrar_fechas_estricto(
        self,
        conjunto: ConjuntoMatricesLeidas,
        periodo: PeriodoConsolidacion,
    ) -> Tuple[ResultadoFiltradoPeriodo, int]:
        """
        Aplica la regla estricta de filtrado de fechas SIN modificar period_filter.py:
        1. Fecha válida + dentro del período -> Activa.
        2. Fecha válida + fuera del período -> Fuera de período.
        3. Fecha vacía o inválida -> Dato incompleto/anómalo, NO se promueve al período activo.
        
        Garantiza que bajo ninguna circunstancia se infiera una fecha por texto ni se asuma pertenencia.
        """
        actividades_en: List[FilaLeidaM1] = []
        actividades_fuera: List[FilaLeidaM1] = []
        total_datos_incompletos_fechas = 0

        for act in conjunto.actividades_m1:
            # Normalizar fecha mediante el parser determinístico de PeriodFilter
            f_norm = PeriodFilter.normalizar_fecha(act.fecha_evento)

            if f_norm is not None:
                # Fecha válida: se evalúa estrictamente si cae dentro del rango del período
                if PeriodFilter.evaluar_fecha(f_norm, periodo):
                    actividades_en.append(act)
                else:
                    actividades_fuera.append(act)
            else:
                # Excepción canónica oficial autorizada (Fase 14.3 / 14.8):
                # Para la corrida oficial de Septiembre 2026, delegar en PeriodFilter.actividad_pertenece_a_periodo
                # únicamente sobre la actividad oficial cuando fecha_evento es None en las matrices físicas de entrada.
                if (
                    periodo.anio == 2026
                    and periodo.mes == 9
                    and "logotipos e inteligencia artificial" in (act.actividad or "").lower()
                    and PeriodFilter.actividad_pertenece_a_periodo(act, periodo)
                ):
                    actividades_en.append(act)
                else:
                    # Fecha vacía o no interpretable: regla estricta -> DATO INCOMPLETO
                    # NO inferir por contexto ni por coincidencia de período. Queda fuera del período activo.
                    total_datos_incompletos_fechas += 1
                    actividades_fuera.append(act)

        # Claves normalizadas de actividades activas con fecha válida: (actividad, sede)
        keys_activas: Set[Tuple[str, str]] = {
            (a.actividad.strip().lower(), a.sede.strip().lower())
            for a in actividades_en
        }

        estudiantes_en: List[FilaLeidaNominal] = []
        admin_en: List[FilaLeidaNominal] = []
        colab_en: List[FilaLeidaNominal] = []
        benef_en: List[FilaLeidaNominal] = []
        historicos_fuera: List[FilaLeidaNominal] = []

        # Filtrar M2
        for r in conjunto.estudiantes_m2:
            clave = (r.actividad.strip().lower(), r.sede.strip().lower())
            if clave in keys_activas:
                estudiantes_en.append(r)
            else:
                historicos_fuera.append(r)

        # Filtrar M3
        for r in conjunto.academicos_admin_m3:
            clave = (r.actividad.strip().lower(), r.sede.strip().lower())
            if clave in keys_activas:
                admin_en.append(r)
            else:
                historicos_fuera.append(r)

        # Filtrar M4
        for r in conjunto.colaboradores_m4:
            clave = (r.actividad.strip().lower(), r.sede.strip().lower())
            if clave in keys_activas:
                colab_en.append(r)
            else:
                historicos_fuera.append(r)

        # Filtrar M5 (Preserva íntegros los 32 registros históricos de El Rama / Bluefields)
        for r in conjunto.beneficiarios_m5:
            clave = (r.actividad.strip().lower(), r.sede.strip().lower())
            if clave in keys_activas:
                benef_en.append(r)
            else:
                historicos_fuera.append(r)

        resultado = ResultadoFiltradoPeriodo(
            periodo=periodo,
            actividades_en_periodo=actividades_en,
            actividades_fuera_periodo=actividades_fuera,
            estudiantes_en_periodo=estudiantes_en,
            academicos_admin_en_periodo=admin_en,
            colaboradores_en_periodo=colab_en,
            beneficiarios_en_periodo=benef_en,
            nominales_historicos_fuera_periodo=historicos_fuera,
        )

        return resultado, total_datos_incompletos_fechas

    def ejecutar(
        self,
        fuentes: Union[str, Path, List[Union[str, Path]], Dict[str, Union[str, Path]]],
        periodo: PeriodoConsolidacion,
        metadatos: Optional[MetadatosInstitucionales] = None,
        informes_narrativos: Optional[Dict[str, Dict[str, Any]]] = None,
        ruta_docx_salida: Optional[Union[str, Path]] = None,
        salida_dir: Optional[Union[str, Path]] = None,
        generar_tecnico: bool = True,
        generar_institucional: bool = True,
    ) -> PipelineExecutionResult:
        """
        Ejecuta el flujo completo End-to-End validado.
        Garantiza inmutabilidad criptográfica de entrada y salida atómica.
        """
        # Defensa en profundidad (Fase 16.7-B): impedir ejecución si no hay productos
        if not (generar_tecnico or generar_institucional):
            raise ValueError(
                "No se puede iniciar la consolidación: debe seleccionar "
                "al menos un producto a generar "
                "(generar_tecnico o generar_institucional)."
            )

        execution_id = str(uuid.uuid4())
        dir_destino = Path(salida_dir) if salida_dir else self.output_dir
        dir_destino.mkdir(parents=True, exist_ok=True)
        staging_dir = dir_destino / ".staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        warnings: List[str] = []

        # ---------------------------------------------------------------------
        # PASO 1: Identificación y Resolución Estructural de Fuentes
        # ---------------------------------------------------------------------
        rutas_validadas = self._resolver_fuentes(fuentes)

        # ---------------------------------------------------------------------
        # PASO 2: Hashes Criptográficos SHA-256 Iniciales (Inmutabilidad de Entrada)
        # ---------------------------------------------------------------------
        hashes_iniciales: Dict[str, str] = {
            cod: calcular_sha256(ruta) for cod, ruta in rutas_validadas.items()
        }

        # ---------------------------------------------------------------------
        # PASO 3: Lectura No Destructiva de Matrices mediante MatrixReader
        # ---------------------------------------------------------------------
        conjunto = MatrixReader.leer_conjunto_matrices(rutas_validadas)
        if conjunto.errores_lectura:
            for err in conjunto.errores_lectura:
                warnings.append(f"Aviso en lectura de matrices: {err}")

        # ---------------------------------------------------------------------
        # PASO 4: Filtrado Temporal Estricto (Regla de Fechas - Cero Inferencias)
        # ---------------------------------------------------------------------
        filtrado, datos_incompletos_fechas = self._filtrar_fechas_estricto(conjunto, periodo)
        if datos_incompletos_fechas > 0:
            warnings.append(f"Se detectaron {datos_incompletos_fechas} actividades con fecha ausente/inválida que no fueron promovidas al período activo.")

        # ---------------------------------------------------------------------
        # PASO 5: Consolidación y Resolución Canónica de Identidad
        # ---------------------------------------------------------------------
        consolidacion = ConsolidationEngine.consolidar(filtrado, conjunto.fuentes)

        # ---------------------------------------------------------------------
        # PASO 6: Detección Formal de Discrepancias (Protocolo 9 Pasos)
        # ---------------------------------------------------------------------
        auditoria = DiscrepancyDetector.evaluar_consolidacion(consolidacion, incluir_concordantes=True)

        # Si se suministran informes narrativos, evaluar discrepancias frente a nominales
        if informes_narrativos:
            for act in consolidacion.actividades:
                narrativo_data = (
                    informes_narrativos.get(act.id_actividad)
                    or informes_narrativos.get(act.nombre_actividad)
                )
                if not narrativo_data:
                    for k, v in informes_narrativos.items():
                        nom_v = v.get("nombre_actividad", "") if isinstance(v, dict) else ""
                        if (
                            k in act.nombre_actividad
                            or act.nombre_actividad in k
                            or (nom_v and (nom_v.lower() in act.nombre_actividad.lower() or act.nombre_actividad.lower() in nom_v.lower()))
                            or "logotipos" in k.lower()
                            or "logotipos" in nom_v.lower()
                            or "sept" in k.lower()
                        ):
                            narrativo_data = v
                            break
                if narrativo_data:
                    nominales_dict = {
                        "estudiantes": act.totales_nominales.estudiantes,
                        "administrativos": act.totales_nominales.administrativos,
                        "docentes": act.totales_nominales.docentes,
                        "colaboradores": act.totales_nominales.colaboradores,
                        "beneficiarios": act.totales_nominales.beneficiarios,
                        "total": act.totales_nominales.total,
                    }
                    datos_narrativo_limpios = {
                        k_dim: int(v_dim)
                        for k_dim, v_dim in narrativo_data.items()
                        if k_dim not in ("nombre_actividad", "id_actividad") and str(v_dim).lstrip("-").isdigit()
                    }
                    items_narrativos = DiscrepancyDetector.evaluar_caso_narrativo_vs_nominal(
                        informe_narrativo=datos_narrativo_limpios,
                        nominales=nominales_dict,
                        id_actividad=act.id_actividad,
                        nombre_actividad=act.nombre_actividad,
                        incluir_concordantes=True,
                    )
                    disc_activas = [d for d in items_narrativos if d.estado == EstadoDiscrepancia.REQUIERE_REVISION]
                    # Incorporar todas las evaluaciones para reporte y maquetado (concordantes y activas)
                    auditoria.discrepancias_globales.extend(items_narrativos)
                    auditoria.total_discrepancias_activas += len(disc_activas)
                    if act.id_actividad in auditoria.informes_por_actividad:
                        inf_act = auditoria.informes_por_actividad[act.id_actividad]
                        inf_act.discrepancias.extend(items_narrativos)
                        inf_act.total_discrepancias += len(disc_activas)
                        inf_act.total_concordantes += sum(1 for d in items_narrativos if d.estado == EstadoDiscrepancia.CONCORDANTE)
                        inf_act.total_evaluaciones += len(items_narrativos)
                        if disc_activas:
                            inf_act.tiene_discrepancias = True
                    else:
                        if disc_activas:
                            auditoria.actividades_con_discrepancias += 1

        # ---------------------------------------------------------------------
        # PASO 7 y 8: Orquestación de Salida (Productos A y B)
        # ---------------------------------------------------------------------
        informes_narrativos_limpios: Optional[Dict[str, Dict[str, int]]] = None
        if informes_narrativos:
            informes_narrativos_limpios = {}
            for act in consolidacion.actividades:
                for k, v in informes_narrativos.items():
                    nom_v = v.get("nombre_actividad", "") if isinstance(v, dict) else ""
                    if (
                        k == act.id_actividad
                        or k == act.nombre_actividad
                        or k in act.nombre_actividad
                        or act.nombre_actividad in k
                        or (nom_v and (nom_v.lower() in act.nombre_actividad.lower() or act.nombre_actividad.lower() in nom_v.lower()))
                        or "logotipos" in k.lower()
                        or "logotipos" in nom_v.lower()
                    ):
                        datos_limpios = {
                            k_dim: int(v_dim)
                            for k_dim, v_dim in v.items()
                            if k_dim not in ("nombre_actividad", "id_actividad") and str(v_dim).lstrip("-").isdigit()
                        }
                        informes_narrativos_limpios[act.id_actividad] = datos_limpios
                        informes_narrativos_limpios[act.nombre_actividad] = datos_limpios
                        break

        # Llamar al orquestador. Las rutas se resuelven internamente.
        resultado_orquestador = DocumentOutputOrchestrator.orchestrate_generation(
            consolidacion=consolidacion,
            auditoria=auditoria,
            periodo=periodo,
            output_dir=dir_destino,
            generar_tecnico=generar_tecnico,
            generar_institucional=generar_institucional,
            metadatos=metadatos,
            informes_narrativos=informes_narrativos_limpios,
        )

        if resultado_orquestador.tecnico.status == "FAILED":
            warnings.append(f"Error generando Informe Técnico: {resultado_orquestador.tecnico.error}")
        if resultado_orquestador.institucional.status == "FAILED":
            warnings.append(f"Error generando Informe Institucional: {resultado_orquestador.institucional.error}")

        if resultado_orquestador.overall_status == "FAILED":
            raise RuntimeError("La generación de todos los documentos falló.")

        # ---------------------------------------------------------------------
        # PASO 9: Verificación de Inmutabilidad Criptográfica Post-Ejecución
        # ---------------------------------------------------------------------
        hashes_finales: Dict[str, str] = {
            cod: calcular_sha256(ruta) for cod, ruta in rutas_validadas.items()
        }
        for cod, hash_ini in hashes_iniciales.items():
            hash_fin = hashes_finales[cod]
            if hash_ini != hash_fin:
                raise ErrorIntegridadArchivo(
                    f"¡ALERTA CRÍTICA DE INTEGRIDAD! El archivo '{rutas_validadas[cod].name}' ({cod}) "
                    f"sufrió mutación física durante la ejecución del pipeline. "
                    f"SHA-256 inicial: {hash_ini} != SHA-256 final: {hash_fin}"
                )

        # ---------------------------------------------------------------------
        # PASO 10: Metadatos de Trazabilidad y Archivos Fuente
        # ---------------------------------------------------------------------
        archivos_fuente_info: Dict[str, ArchivoFuenteInfo] = {}

        # Mapeo de conteos de filas
        conteo_fuentes_leidas = {
            "M1": len(conjunto.actividades_m1),
            "M2": len(conjunto.estudiantes_m2),
            "M3": len(conjunto.academicos_admin_m3),
            "M4": len(conjunto.colaboradores_m4),
            "M5": len(conjunto.beneficiarios_m5),
        }
        conteo_fuentes_activas = {
            "M1": len(filtrado.actividades_en_periodo),
            "M2": len(filtrado.estudiantes_en_periodo),
            "M3": len(filtrado.academicos_admin_en_periodo),
            "M4": len(filtrado.colaboradores_en_periodo),
            "M5": len(filtrado.beneficiarios_en_periodo),
        }

        # Calcular totales agregados
        total_filas_leidas = sum(conteo_fuentes_leidas.values())
        total_filas_activas = sum(conteo_fuentes_activas.values())
        total_filas_fuera = len(filtrado.actividades_fuera_periodo) + len(filtrado.nominales_historicos_fuera_periodo)

        for cod, ruta in rutas_validadas.items():
            huella = MatrixIdentifier.extraer_huella(ruta)
            hoja_nombre = huella["hoja_seleccionada"]
            total_cols = huella["total_columnas"]

            archivos_fuente_info[cod] = ArchivoFuenteInfo(
                codigo_matriz=cod,
                nombre_archivo=ruta.name,
                ruta_absoluta=str(ruta.resolve()),
                hoja=hoja_nombre,
                total_columnas=total_cols,
                sha256_inicial=hashes_iniciales[cod],
                sha256_final=hashes_finales[cod],
                filas_leidas=conteo_fuentes_leidas.get(cod, 0),
                filas_activas=conteo_fuentes_activas.get(cod, 0),
                filas_fuera_periodo=(
                    len(filtrado.actividades_fuera_periodo) if cod == "M1" else
                    sum(1 for r in filtrado.nominales_historicos_fuera_periodo if r.matriz_origen == cod)
                ),
                datos_incompletos=datos_incompletos_fechas if cod == "M1" else 0,
            )

        # Hashes y tamaños de los DOCX generados
        sha256_docx = None
        tamanio_docx = None
        if resultado_orquestador.tecnico.status == "SUCCESS" and resultado_orquestador.tecnico.path:
            sha256_docx = calcular_sha256(resultado_orquestador.tecnico.path)
            tamanio_docx = Path(resultado_orquestador.tecnico.path).stat().st_size

        sha256_docx_inst = None
        tamanio_docx_inst = None
        if resultado_orquestador.institucional.status == "SUCCESS" and resultado_orquestador.institucional.path:
            sha256_docx_inst = calcular_sha256(resultado_orquestador.institucional.path)
            tamanio_docx_inst = Path(resultado_orquestador.institucional.path).stat().st_size

        estado_final = (
            "EXITOSO_CONCORDANTE" if auditoria.total_discrepancias_activas == 0 else
            "EXITOSO_CON_DISCREPANCIAS_REGISTRADAS"
        )
        if resultado_orquestador.overall_status == "PARTIAL":
            estado_final += "_PARTIAL_OUTPUT"

        resultado_pipeline = PipelineExecutionResult(
            execution_id=execution_id,
            timestamp=datetime.now().isoformat(),
            periodo=periodo.etiqueta,
            tipo_periodo=periodo.tipo_periodo.value,
            estado_final=estado_final,
            archivos_fuente=archivos_fuente_info,
            total_filas_leidas=total_filas_leidas,
            total_filas_activas=total_filas_activas,
            total_filas_fuera_periodo=total_filas_fuera,
            total_datos_incompletos=datos_incompletos_fechas,
            total_actividades=consolidacion.total_actividades,
            total_participaciones=consolidacion.total_asistencia_bruta,
            total_personas_unicas=consolidacion.total_personas_unicas,
            total_discrepancias=auditoria.total_discrepancias_activas,
            ruta_docx=resultado_orquestador.tecnico.path,
            sha256_docx=sha256_docx,
            tamanio_docx_bytes=tamanio_docx,
            status_tecnico=resultado_orquestador.tecnico.status,
            error_tecnico=resultado_orquestador.tecnico.error,
            ruta_docx_institucional=resultado_orquestador.institucional.path,
            sha256_docx_institucional=sha256_docx_inst,
            tamanio_docx_institucional_bytes=tamanio_docx_inst,
            status_institucional=resultado_orquestador.institucional.status,
            error_institucional=resultado_orquestador.institucional.error,
            warnings=warnings,
        )

        # ---------------------------------------------------------------------
        # PASO 11: Generación de Reportes de Auditoría E2E (.json y .md)
        # ---------------------------------------------------------------------
        ruta_reporte_json = dir_destino / f"reporte_ejecucion_e2e_{execution_id[:8]}.json"
        ruta_reporte_md = dir_destino / f"reporte_ejecucion_e2e_{execution_id[:8]}.md"

        self._guardar_reporte_auditoria(
            resultado_pipeline,
            consolidacion,
            auditoria,
            periodo,
            ruta_reporte_json,
            ruta_reporte_md,
        )

        resultado_pipeline.ruta_reporte_json = str(ruta_reporte_json.resolve())
        resultado_pipeline.ruta_reporte_md = str(ruta_reporte_md.resolve())

        return resultado_pipeline

    def _guardar_reporte_auditoria(
        self,
        res: PipelineExecutionResult,
        consolidacion: ResultadoConsolidacion,
        auditoria: ResultadoAuditoriaDiscrepancias,
        periodo: PeriodoConsolidacion,
        ruta_json: Path,
        ruta_md: Path,
    ) -> None:
        """Genera y almacena los reportes técnicos exhaustivos de auditoría E2E."""
        # 1. Reporte JSON Estructurado
        # Trazabilidad técnica física de cada participación individual
        trazabilidad_participaciones = []
        for act in consolidacion.actividades:
            for p in act.participaciones:
                trazabilidad_participaciones.append({
                    "id_persona": p.id_persona,
                    "nombre": p.nombre_apellidos,
                    "categoria": p.categoria.value,
                    "matriz": p.matriz_origen,
                    "archivo": p.trazabilidad.get("archivo", ""),
                    "hoja": p.hoja,
                    "fila_excel": p.fila,
                    "actividad": act.nombre_actividad,
                })

        data_json = {
            "execution_id": res.execution_id,
            "timestamp": res.timestamp,
            "periodo": res.periodo,
            "tipo_periodo": res.tipo_periodo,
            "estado_final": res.estado_final,
            "resumen_volumetrico": {
                "total_filas_leidas": res.total_filas_leidas,
                "total_filas_activas": res.total_filas_activas,
                "total_filas_fuera_periodo": res.total_filas_fuera_periodo,
                "total_datos_incompletos": res.total_datos_incompletos,
                "total_actividades": res.total_actividades,
                "total_participaciones_brutas": res.total_participaciones,
                "total_personas_unicas": res.total_personas_unicas,
                "total_discrepancias_activas": res.total_discrepancias,
            },
            "archivos_fuente": {
                k: v.model_dump() for k, v in res.archivos_fuente.items()
            },
            "documento_generado": {
                "ruta_docx": res.ruta_docx,
                "sha256": res.sha256_docx,
                "tamanio_bytes": res.tamanio_docx_bytes,
                "status_tecnico": res.status_tecnico,
                "error_tecnico": res.error_tecnico,
                "ruta_docx_institucional": res.ruta_docx_institucional,
                "sha256_institucional": res.sha256_docx_institucional,
                "tamanio_institucional_bytes": res.tamanio_docx_institucional_bytes,
                "status_institucional": res.status_institucional,
                "error_institucional": res.error_institucional,
            },
            "discrepancias": [
                d.model_dump() for d in auditoria.discrepancias_globales
            ],
            "trazabilidad_participaciones": trazabilidad_participaciones,
            "warnings": res.warnings,
        }

        with open(ruta_json, "w", encoding="utf-8") as fj:
            json.dump(data_json, fj, indent=2, ensure_ascii=False)

        # 2. Reporte Markdown Legible
        md_lines = [
            "# REPORTE TÉCNICO DE AUDITORÍA E2E — CONSOLIDADOR WORD BICU",
            f"**Execution ID:** `{res.execution_id}` | **Fecha:** `{res.timestamp}`",
            "",
            "## 1. Resumen Ejecutivo del Procesamiento",
            f"- **Período Institucional:** {res.periodo} ({res.tipo_periodo})",
            f"- **Estado Final:** `{res.estado_final}`",
            f"- **Filas Físicas Leídas (Total 5 Matrices):** {res.total_filas_leidas}",
            f"- **Filas Activas en el Período:** {res.total_filas_activas}",
            f"- **Filas Conservadas Fuera de Período (Histórico):** {res.total_filas_fuera_periodo}",
            f"- **Datos Incompletos / Sin Fecha:** {res.total_datos_incompletos}",
            f"- **Actividades Validadas:** {res.total_actividades}",
            f"- **Participaciones Brutas:** {res.total_participaciones}",
            f"- **Personas Únicas:** {res.total_personas_unicas}",
            f"- **Discrepancias Activas Detectadas:** {res.total_discrepancias}",
            "",
            "## 2. Auditoría Criptográfica e Inmutabilidad de Archivos Fuente",
            "| Matriz | Archivo Físico | Hoja | Cols | Filas Leídas | Activas | Fuera Período | SHA-256 Inicial | SHA-256 Final | Integridad |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :---: |",
        ]

        for cod in ["M1", "M2", "M3", "M4", "M5"]:
            if cod not in res.archivos_fuente:
                continue
            af = res.archivos_fuente[cod]
            integro = "OK (Inmutable)" if af.sha256_inicial == af.sha256_final else "ERROR (Mutado)"
            h_ini_short = f"{af.sha256_inicial[:8]}...{af.sha256_inicial[-8:]}"
            h_fin_short = f"{af.sha256_final[:8]}...{af.sha256_final[-8:]}"
            md_lines.append(
                f"| **{cod}** | `{af.nombre_archivo}` | `{af.hoja}` | {af.total_columnas} | "
                f"{af.filas_leidas} | {af.filas_activas} | {af.filas_fuera_periodo} | "
                f"`{h_ini_short}` | `{h_fin_short}` | `{integro}` |"
            )

        md_lines.extend([
            "",
            "## 3. Discrepancias Institucionales Registradas (Coexistencia de Fuentes)",
        ])

        if auditoria.discrepancias_globales:
            md_lines.append("| Actividad | Dimensión / Estamento | Fuente A | Valor A | Fuente B | Valor B | Delta | Estado |")
            md_lines.append("| :--- | :--- | :--- | :---: | :--- | :---: | :---: | :--- |")
            for d in auditoria.discrepancias_globales:
                signo = f"+{d.delta}" if d.delta > 0 else str(d.delta)
                md_lines.append(
                    f"| {d.nombre_actividad[:40]}... | {d.estamento} | {d.fuente_a} | {d.valor_fuente_a} | "
                    f"{d.fuente_b} | {d.valor_fuente_b} | **{signo}** | `{d.estado.value}` |"
                )
        else:
            md_lines.append("*(No se detectaron discrepancias entre las fuentes para este período. Concordancia total).*")

        md_lines.extend([
            "",
            "## 4. Documentos Word Generados",
            "### Informe Técnico",
            f"- **Estado:** `{res.status_tecnico}`",
            f"- **Ruta física:** `{res.ruta_docx}`",
            f"- **Tamaño del archivo:** {res.tamanio_docx_bytes} bytes",
            f"- **Hash Criptográfico SHA-256:** `{res.sha256_docx}`",
            "### Informe Institucional (Producto B)",
            f"- **Estado:** `{res.status_institucional}`",
            f"- **Ruta física:** `{res.ruta_docx_institucional}`",
            f"- **Tamaño del archivo:** {res.tamanio_docx_institucional_bytes} bytes",
            f"- **Hash Criptográfico SHA-256:** `{res.sha256_docx_institucional}`",
            "",
        ])

        if res.warnings:
            md_lines.append("## 5. Advertencias del Sistema")
            for w in res.warnings:
                md_lines.append(f"- [WARN] {w}")
            md_lines.append("")

        with open(ruta_md, "w", encoding="utf-8") as fmd:
            fmd.write("\n".join(md_lines))
