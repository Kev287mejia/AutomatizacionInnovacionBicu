"""
app.word_consolidator.readers.matrix_reader

Lector oficial, fuertemente tipado y estrictamente no destructivo para las cinco
matrices Excel institucionales de BICU (M1 a M5).
Abre los archivos en modo read_only=True y data_only=True, garantiza la trazabilidad
de coordenadas (matriz, hoja, fila) y nunca modifica las fuentes.
"""

from datetime import date, datetime
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import openpyxl

from app.word_consolidator.models import (
    ConjuntoMatricesLeidas,
    FilaLeidaM1,
    FilaLeidaNominal,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
    ResultadoFiltradoPeriodo,
)
from app.word_consolidator.readers.period_filter import PeriodFilter


def _clean_str(val: Any) -> Optional[str]:
    """Retorna cadena limpia o None si está vacía o es None."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _clean_int(val: Any, default: int = 0) -> int:
    """Convierte un valor de celda a entero seguro sin lanzar excepciones."""
    if val is None:
        return default
    try:
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if not s:
            return default
        # Si tiene punto decimal por formato numérico
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _calcular_sha256(ruta: Path) -> str:
    """Calcula el hash criptográfico SHA-256 de un archivo en disco."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class MatrixReader:
    """
    Lector oficial no destructivo para las cinco matrices institucionales de BICU.
    """

    HOJAS_OFICIALES = {
        "M1": "Programas, proyectos y act",
        "M2": "Pregrado_Grado en Actividades",
        "M3": "Pregrado_Grado en Actividades",
        "M4": "Pregrado_Grado en Actividades",
        "M5": "Pregrado_Grado en Actividades",
    }

    @classmethod
    def _abrir_libro_seguro(cls, ruta: Path) -> openpyxl.Workbook:
        """Abre un libro de trabajo en modo solo lectura y solo datos (sin evaluar fórmulas)."""
        if not ruta.exists():
            raise FileNotFoundError(f"Archivo de matriz oficial no encontrado: {ruta}")
        
        try:
            wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
            # Salvaguarda de integridad: confirmar que es de solo lectura
            if not wb.read_only:
                raise RuntimeError("El libro no fue cargado en modo de solo lectura.")
            return wb
        except Exception as e:
            if isinstance(e, (FileNotFoundError, RuntimeError)):
                raise
            raise ValueError(f"Error al abrir archivo Excel {ruta.name}: {e}") from e

    @classmethod
    def _obtener_hoja(cls, wb: openpyxl.Workbook, codigo_matriz: str) -> Any:
        """Obtiene la hoja oficial esperada o recurre a la activa emitiendo registro."""
        nombre_esperado = cls.HOJAS_OFICIALES.get(codigo_matriz)
        if nombre_esperado and nombre_esperado in wb.sheetnames:
            return wb[nombre_esperado]
        return wb.active

    @classmethod
    def leer_matriz_1(cls, ruta_archivo: Union[str, Path]) -> Tuple[List[FilaLeidaM1], RegistroFuenteArchivo]:
        """
        Lee la Matriz 1 (Consolidado de Actividades) extrayendo las filas agregadas oficiales.
        """
        path = Path(ruta_archivo)
        sha256 = _calcular_sha256(path)
        wb = cls._abrir_libro_seguro(path)

        ws = cls._obtener_hoja(wb, "M1")
        filas_m1: List[FilaLeidaM1] = []

        # Leer primera fila para validar columnas clave
        iter_rows = ws.iter_rows(values_only=True)
        try:
            cabecera = next(iter_rows, None)
        except Exception as e:
            wb.close()
            raise ValueError(f"No se pudieron leer encabezados de {path.name}: {e}") from e

        if not cabecera:
            wb.close()
            raise ValueError(f"La hoja {ws.title} de M1 está vacía o sin encabezados.")

        # Construir mapa de encabezados a índices (1-based)
        mapa_cols = {str(c).strip().lower(): idx for idx, c in enumerate(cabecera, 1) if c is not None}
        
        # Validar columnas imprescindibles
        if "actividad" not in mapa_cols and len(cabecera) < 9:
            wb.close()
            raise ValueError(f"Estructura incompatible en M1: no se encontró columna 'Actividad'.")

        def col_val(row_tuple: tuple, col_name: str, fallback_idx: int) -> Any:
            idx = mapa_cols.get(col_name.lower(), fallback_idx)
            return row_tuple[idx - 1] if idx <= len(row_tuple) else None

        num_fila = 2
        for row in iter_rows:
            if not any(c is not None for c in row):
                num_fila += 1
                continue

            act_nombre = _clean_str(col_val(row, "actividad", 9))
            sede = _clean_str(col_val(row, "sede", 2))
            
            # Si no hay nombre de actividad, omitir fila
            if not act_nombre:
                num_fila += 1
                continue

            # Si sede está vacía pero hay actividad, asignar 'Sede Central / No especificada'
            if not sede:
                sede = "No especificada"

            fecha_ev = col_val(row, "fecha_evento", 15)
            if isinstance(fecha_ev, datetime):
                fecha_ev = fecha_ev.date()

            trazabilidad = {
                "matriz": "M1",
                "archivo": path.name,
                "hoja": ws.title,
                "fila": num_fila,
            }

            fila_obj = FilaLeidaM1(
                matriz_origen="M1",
                hoja=ws.title,
                fila=num_fila,
                no=_clean_int(col_val(row, "no", 1), default=num_fila - 1),
                sede=sede,
                dep_sede=_clean_str(col_val(row, "dep_sede", 3)),
                mun_sede=_clean_str(col_val(row, "mun_sede", 4)),
                programa=_clean_str(col_val(row, "programa", 5)),
                otro_programa=_clean_str(col_val(row, "otro_programa", 6)),
                proyecto=_clean_str(col_val(row, "proyecto", 7)),
                ambito=_clean_str(col_val(row, "ámbito", 8)),
                actividad=act_nombre,
                area_responsable=_clean_str(col_val(row, "área_responsable", 10)),
                financiamiento=_clean_str(col_val(row, "financiamiento", 11)),
                nombre_area=_clean_str(col_val(row, "nombre_área", 12)),
                evento=_clean_str(col_val(row, "evento", 13)),
                evento_otros=_clean_str(col_val(row, "evento_otros", 14)),
                fecha_evento=fecha_ev,
                resultados=_clean_str(col_val(row, "resultados", 16)),
                convenio=_clean_str(col_val(row, "convenio", 17)),
                tipo_convenio=_clean_str(col_val(row, "tipo_convenio", 18)),
                nombre_convenio=_clean_str(col_val(row, "nombre_convenio", 19)),
                region_atendida=_clean_str(col_val(row, "región_atendida", 20)),
                departamento=_clean_str(col_val(row, "departamento", 21)),
                municipio=_clean_str(col_val(row, "municipio", 22)),
                comunidad=_clean_str(col_val(row, "comunidad", 23)),
                total_comunidades=_clean_int(col_val(row, "total_comunidades", 24), default=0),
                total_atencion_m=_clean_int(col_val(row, "total, atención, m", 25), default=0),
                total_atencion_f=_clean_int(col_val(row, "total, atención, f", 26), default=0),
                total_estud_m_grado=_clean_int(col_val(row, "total, estud_m_grado", 27), default=0),
                total_estud_f_grado=_clean_int(col_val(row, "total, estud_f_grado", 28), default=0),
                total_estud_m_posgrado=_clean_int(col_val(row, "total, estud_m_posgrado", 29), default=0),
                total_estud_f_posgrado=_clean_int(col_val(row, "total, estud_f_posgrado", 30), default=0),
                total_docente_m=_clean_int(col_val(row, "total, docente_m", 31), default=0),
                total_docente_f=_clean_int(col_val(row, "total, docente_f", 32), default=0),
                total_administrativos_m=_clean_int(col_val(row, "total, administrativos_m", 33), default=0),
                total_administrativos_f=_clean_int(col_val(row, "total, administrativos_f", 34), default=0),
                total_partic_m_inst_publica=_clean_int(col_val(row, "total, partic_m_inst_pública", 35), default=0),
                total_partic_f_inst_publica=_clean_int(col_val(row, "total, partic_f_inst_pública", 36), default=0),
                total_partic_m_inst_privada=_clean_int(col_val(row, "total, partic_m_inst_privada", 37), default=0),
                total_partic_f_inst_privada=_clean_int(col_val(row, "total, partic_f_inst_privada", 38), default=0),
                total_partic_m_ong=_clean_int(col_val(row, "total, partic_m_ong", 39), default=0),
                total_partic_f_ong=_clean_int(col_val(row, "total, partic_f_ong", 40), default=0),
                total_protagonistas_m=_clean_int(col_val(row, "total, protagonistas_m", 41), default=0),
                total_protagonistas_f=_clean_int(col_val(row, "total, protagonistas_f", 42), default=0),
                trazabilidad=trazabilidad,
            )
            filas_m1.append(fila_obj)
            num_fila += 1

        wb.close()

        registro_fuente = RegistroFuenteArchivo(
            codigo_matriz="M1",
            nombre_archivo=path.name,
            ruta_archivo=str(path.resolve()),
            hash_sha256=sha256,
            total_filas_leidas=len(filas_m1),
            filas_en_periodo=len(filas_m1),
        )

        return filas_m1, registro_fuente

    @classmethod
    def leer_matriz_nominal(
        cls,
        ruta_archivo: Union[str, Path],
        codigo_matriz: str
    ) -> Tuple[List[FilaLeidaNominal], RegistroFuenteArchivo]:
        """
        Lee una matriz nominal (M2, M3, M4 o M5) extrayendo sus filas de participantes.
        Preserva valores verbatim (cédula, carrera abreviada) y traza matriz, hoja y fila.
        """
        if codigo_matriz not in ("M2", "M3", "M4", "M5"):
            raise ValueError(f"Código de matriz nominal inválido: {codigo_matriz}")

        path = Path(ruta_archivo)
        sha256 = _calcular_sha256(path)
        wb = cls._abrir_libro_seguro(path)

        ws = cls._obtener_hoja(wb, codigo_matriz)
        filas_nominales: List[FilaLeidaNominal] = []

        iter_rows = ws.iter_rows(values_only=True)
        try:
            cabecera = next(iter_rows, None)
        except Exception as e:
            wb.close()
            raise ValueError(f"No se pudieron leer encabezados de {path.name}: {e}") from e

        if not cabecera:
            wb.close()
            raise ValueError(f"La hoja {ws.title} de {codigo_matriz} está vacía o sin encabezados.")

        mapa_cols = {str(c).strip().lower(): idx for idx, c in enumerate(cabecera, 1) if c is not None}

        # Localizar columnas clave por nombre o por posición canónica
        # Columna de nombres según matriz:
        # M2: AG (33) | M3: AI (35) | M4: AI (35) | M5: AH (34)
        col_pos_default = {
            "M2": {"nombre": 33, "cedula": 35, "sexo": 38, "nacimiento": 39, "edad": 40, "carrera": 52, "nivel": 51, "tipo": None},
            "M3": {"nombre": 35, "cedula": 37, "sexo": 40, "nacimiento": 41, "edad": 42, "carrera": 53, "nivel": 52, "tipo": 34},
            "M4": {"nombre": 35, "cedula": 37, "sexo": 40, "nacimiento": 41, "edad": 42, "carrera": None, "nivel": None, "tipo": 34},
            "M5": {"nombre": 34, "cedula": 36, "sexo": 39, "nacimiento": 40, "edad": 41, "carrera": 52, "nivel": 51, "tipo": None},
        }[codigo_matriz]

        def get_val(row_t: tuple, key_name: str, def_idx: Optional[int]) -> Any:
            # Buscar en mapa de nombres
            for k in [key_name, key_name.replace("_", " ")]:
                if k in mapa_cols:
                    idx = mapa_cols[k]
                    return row_t[idx - 1] if idx <= len(row_t) else None
            # Fallback por posición
            if def_idx and def_idx <= len(row_t):
                return row_t[def_idx - 1]
            return None

        num_fila = 2
        for row in iter_rows:
            if not any(c is not None for c in row):
                num_fila += 1
                continue

            nombre = _clean_str(get_val(row, "nombre_apellidos", col_pos_default["nombre"]))
            # Si no hay nombre de participante, omitir fila vacía
            if not nombre:
                num_fila += 1
                continue

            actividad = _clean_str(get_val(row, "actividad", 9)) or "Actividad no especificada"
            sede = _clean_str(get_val(row, "sede", 2)) or "No especificada"

            # Cédula: preserva el valor literal de la celda (sin normalizar aquí)
            cedula_raw = get_val(row, "no_cédula", col_pos_default["cedula"])
            cedula_str = _clean_str(cedula_raw)

            # Sexo
            sexo_str = _clean_str(get_val(row, "sexo", col_pos_default["sexo"]))

            # Fecha de nacimiento
            f_nac = get_val(row, "fecha_nacimiento", col_pos_default["nacimiento"])
            if isinstance(f_nac, datetime):
                f_nac = f_nac.date()

            # Edad
            edad_val = get_val(row, "edad", col_pos_default["edad"])

            # Carrera y otros específicos
            carrera_str = _clean_str(get_val(row, "nombre_carrera", col_pos_default.get("carrera")))
            tipo_prot = _clean_str(get_val(row, "tipo_protagonistas", col_pos_default.get("tipo")))

            trazabilidad = {
                "matriz": codigo_matriz,
                "archivo": path.name,
                "hoja": ws.title,
                "fila": num_fila,
            }

            fila_nom = FilaLeidaNominal(
                matriz_origen=codigo_matriz,
                hoja=ws.title,
                fila=num_fila,
                no=_clean_int(get_val(row, "no", 1), default=num_fila - 1),
                sede=sede,
                dep_sede=_clean_str(get_val(row, "dep_sede", 3)),
                mun_sede=_clean_str(get_val(row, "mun_sede", 4)),
                programa=_clean_str(get_val(row, "programa", 5)),
                otro_programa=_clean_str(get_val(row, "otro_programa", 6)),
                proyecto=_clean_str(get_val(row, "proyecto", 7)),
                ambito=_clean_str(get_val(row, "ámbito", 8)),
                actividad=actividad,
                proposito=_clean_str(get_val(row, "proposito", 10)),
                evento=_clean_str(get_val(row, "evento", 11)),
                eje_estrategia=_clean_str(get_val(row, "eje_estrategia", 15)),
                nombre_apellidos=nombre,
                no_cedula=cedula_str,
                sexo=sexo_str,
                fecha_nacimiento=f_nac,
                edad=edad_val,
                tipo_protagonistas=tipo_prot,
                carrera=carrera_str,
                nivel_form=_clean_str(get_val(row, "nivel_form", col_pos_default.get("nivel"))),
                cargo=_clean_str(get_val(row, "cargo", 54 if codigo_matriz == "M4" else 56)),
                entidad=_clean_str(get_val(row, "entidad", 56 if codigo_matriz == "M4" else None)),
                beneficio=_clean_str(get_val(row, "beneficio", 53 if codigo_matriz == "M5" else None)),
                trazabilidad=trazabilidad,
            )
            filas_nominales.append(fila_nom)
            num_fila += 1

        wb.close()

        registro_fuente = RegistroFuenteArchivo(
            codigo_matriz=codigo_matriz,
            nombre_archivo=path.name,
            ruta_archivo=str(path.resolve()),
            hash_sha256=sha256,
            total_filas_leidas=len(filas_nominales),
            filas_en_periodo=len(filas_nominales),
        )

        return filas_nominales, registro_fuente

    @classmethod
    def leer_conjunto_matrices(
        cls,
        rutas: Dict[str, Union[str, Path]]
    ) -> ConjuntoMatricesLeidas:
        """
        Lee el paquete completo de las cinco matrices oficiales (M1 a M5).
        Retorna el modelo ConjuntoMatricesLeidas sin filtrado temporal.
        """
        codigos_requeridos = ["M1", "M2", "M3", "M4", "M5"]
        for c in codigos_requeridos:
            if c not in rutas:
                raise ValueError(f"Falta la ruta obligatoria para la matriz '{c}'.")

        fuentes: Dict[str, RegistroFuenteArchivo] = {}
        errores: List[str] = []
        observaciones: List[str] = []

        # 1. Leer M1
        actividades_m1, fuente_m1 = cls.leer_matriz_1(rutas["M1"])
        fuentes["M1"] = fuente_m1

        # 2. Leer M2 (Estudiantes)
        estudiantes_m2, fuente_m2 = cls.leer_matriz_nominal(rutas["M2"], "M2")
        fuentes["M2"] = fuente_m2

        # 3. Leer M3 (Académicos y Administrativos)
        admin_m3, fuente_m3 = cls.leer_matriz_nominal(rutas["M3"], "M3")
        fuentes["M3"] = fuente_m3

        # 4. Leer M4 (Colaboradores)
        colab_m4, fuente_m4 = cls.leer_matriz_nominal(rutas["M4"], "M4")
        fuentes["M4"] = fuente_m4

        # 5. Leer M5 (Beneficiarios y Pobladores)
        benef_m5, fuente_m5 = cls.leer_matriz_nominal(rutas["M5"], "M5")
        fuentes["M5"] = fuente_m5

        if len(benef_m5) >= 32:
            observaciones.append(f"M5 contiene {len(benef_m5)} registros (incluye histórico preservado).")

        return ConjuntoMatricesLeidas(
            fuentes=fuentes,
            actividades_m1=actividades_m1,
            estudiantes_m2=estudiantes_m2,
            academicos_admin_m3=admin_m3,
            colaboradores_m4=colab_m4,
            beneficiarios_m5=benef_m5,
            errores_lectura=errores,
            observaciones=observaciones,
        )

    @classmethod
    def leer_y_filtrar(
        cls,
        rutas: Dict[str, Union[str, Path]],
        periodo: PeriodoConsolidacion
    ) -> Tuple[ConjuntoMatricesLeidas, ResultadoFiltradoPeriodo]:
        """
        Punto de entrada integral: lee las 5 matrices y aplica el filtro de período seleccionado.
        """
        conjunto = cls.leer_conjunto_matrices(rutas)
        filtrado = PeriodFilter.filtrar(conjunto, periodo)
        return conjunto, filtrado
