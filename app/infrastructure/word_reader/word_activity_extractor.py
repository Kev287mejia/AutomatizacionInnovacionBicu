"""app.infrastructure.word_reader.word_activity_extractor

Implementación concreta de IWordActivityExtractor utilizando python-docx.

Responsabilidad:
    - Leer el archivo Word (.docx) físico.
    - Extraer estructuradamente la Ficha Técnica (Tabla 1: 19 filas x 2 cols).
    - Extraer la Matriz Cuantitativa (Tabla 2: 3 filas x 15 cols).
    - Extraer secciones narrativas del informe técnico.
    - Detectar evidencias gráficas e imágenes de listas de firmas escaneadas.
    - Diagnosticar compatibilidad y clasificar el tipo de documento.

REGLAS DE DOMINIO Y ARQUITECTURA:
    - Clean Architecture: Este módulo pertenece a Infrastructure y es el único
      en este subsistema que importa python-docx.
    - DETECTAR != CORREGIR: Toda inconsistencia o discrepancia se registra como
      advertencia en el diagnóstico; nunca se inventan datos ni se corrigen silenciosamente.
    - TOTAL CUANTITATIVO != PARTICIPANTES NOMINALES: La Tabla 2 provee totales estadísticos
      declarados; NO genera objetos Person ni filas de asistencia individuales.
    - Cero dependencias de SQLite, bases de datos o exportadores.
"""

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import docx
    from docx.opc.exceptions import PackageNotFoundError
except ImportError:  # pragma: no cover
    docx = None
    PackageNotFoundError = Exception

from app.application.dto.word_extraction_dtos import (
    DiagnosticoExtraccionDTO,
    EvidenciaDetectadaDTO,
    EvidenciasAnexosDTO,
    FichaTecnicaDTO,
    MatrizCuantitativaDTO,
    NarrativaSeccionesDTO,
    TipoDocumentoWord,
    TipoEvidenciaWord,
    WordActivityExtractionResultDTO,
)
from app.application.ports.word_activity_extractor import IWordActivityExtractor
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class WordActivityExtractor(IWordActivityExtractor):
    """Extractor físico de actividades institucionales desde archivos DOCX."""

    def extract(self, file_path: Union[str, Path]) -> WordActivityExtractionResultDTO:
        """Extrae la información estructurada del documento Word.

        Args:
            file_path: Ruta al archivo .docx en el disco.

        Returns:
            WordActivityExtractionResultDTO con todos los componentes extraídos.
        """
        path = Path(file_path)
        nombre_archivo = path.name

        # 1. Validar existencia física del archivo
        if not path.exists() or not path.is_file():
            return WordActivityExtractionResultDTO(
                ruta_archivo=str(path.resolve()) if path.exists() else str(path),
                nombre_archivo=nombre_archivo,
                hash_sha256=None,
                tamano_bytes=0,
                diagnostico=DiagnosticoExtraccionDTO(
                    es_valido=False,
                    tipo_documento=TipoDocumentoWord.NO_COMPATIBLE,
                    compatible_flujo_principal=False,
                    errores=[f"Archivo no encontrado o ruta no válida: '{path}'"],
                ),
            )

        # 2. Calcular hash SHA-256 e inspeccionar tamaño
        try:
            with open(path, "rb") as f:
                content_bytes = f.read()
            hash_sha256 = hashlib.sha256(content_bytes).hexdigest()
            tamano_bytes = len(content_bytes)
        except Exception as e:
            return WordActivityExtractionResultDTO(
                ruta_archivo=str(path.resolve()),
                nombre_archivo=nombre_archivo,
                hash_sha256=None,
                tamano_bytes=0,
                diagnostico=DiagnosticoExtraccionDTO(
                    es_valido=False,
                    tipo_documento=TipoDocumentoWord.NO_COMPATIBLE,
                    compatible_flujo_principal=False,
                    errores=[f"No se pudo leer el archivo físico para hash: {e}"],
                ),
            )

        # 3. Abrir documento con python-docx
        if docx is None:  # pragma: no cover
            return WordActivityExtractionResultDTO(
                ruta_archivo=str(path.resolve()),
                nombre_archivo=nombre_archivo,
                hash_sha256=hash_sha256,
                tamano_bytes=tamano_bytes,
                diagnostico=DiagnosticoExtraccionDTO(
                    es_valido=False,
                    tipo_documento=TipoDocumentoWord.NO_COMPATIBLE,
                    compatible_flujo_principal=False,
                    errores=["Librería python-docx no se encuentra instalada en el entorno."],
                ),
            )

        try:
            doc = docx.Document(path)
        except (PackageNotFoundError, Exception) as e:
            return WordActivityExtractionResultDTO(
                ruta_archivo=str(path.resolve()),
                nombre_archivo=nombre_archivo,
                hash_sha256=hash_sha256,
                tamano_bytes=tamano_bytes,
                diagnostico=DiagnosticoExtraccionDTO(
                    es_valido=False,
                    tipo_documento=TipoDocumentoWord.NO_COMPATIBLE,
                    compatible_flujo_principal=False,
                    errores=[f"Archivo DOCX corrupto o formato no válido: {e}"],
                ),
            )

        advertencias: List[str] = []
        errores: List[str] = []

        # 4. Extraer narrativa y párrafos
        narrativa, evidencias_anexos = self._extraer_narrativa_y_evidencias(doc)

        # 5. Extraer tablas (Tabla 1 y Tabla 2)
        ficha_tecnica, t1_encontrada = self._extraer_ficha_tecnica(doc, advertencias)
        matriz_cuantitativa, t2_encontrada = self._extraer_matriz_cuantitativa(doc, advertencias)

        # 6. Clasificar tipo de documento y compatibilidad
        es_semanal = self._es_informe_semanal(doc)

        if es_semanal:
            tipo_doc = TipoDocumentoWord.INFORME_SEMANAL
            compatible = False
            advertencias.append("El documento corresponde a un Informe Semanal Ejecutivo, no a un informe individual de actividad.")
        elif t1_encontrada or t2_encontrada:
            tipo_doc = TipoDocumentoWord.INFORME_ACTIVIDAD
            compatible = True
            if not t1_encontrada:
                advertencias.append("No se encontró la Ficha Técnica (Tabla 1). Se extrajo únicamente la Matriz Cuantitativa.")
            if not t2_encontrada:
                advertencias.append("No se encontró la Matriz Cuantitativa (Tabla 2). Se extrajo únicamente la Ficha Técnica.")
        else:
            tipo_doc = TipoDocumentoWord.NO_COMPATIBLE
            compatible = False
            errores.append("El documento no contiene la Ficha Técnica (Tabla 1) ni la Matriz Cuantitativa (Tabla 2) institucional.")

        diagnostico = DiagnosticoExtraccionDTO(
            es_valido=len(errores) == 0,
            tipo_documento=tipo_doc,
            compatible_flujo_principal=compatible,
            tabla_1_encontrada=t1_encontrada,
            tabla_2_encontrada=t2_encontrada,
            advertencias=advertencias,
            errores=errores,
        )

        return WordActivityExtractionResultDTO(
            ruta_archivo=str(path.resolve()),
            nombre_archivo=nombre_archivo,
            hash_sha256=hash_sha256,
            tamano_bytes=tamano_bytes,
            diagnostico=diagnostico,
            ficha_tecnica=ficha_tecnica,
            matriz_cuantitativa=matriz_cuantitativa,
            narrativa=narrativa,
            evidencias=evidencias_anexos,
        )

    # ---------------------------------------------------------------------------
    # Métodos privados de extracción
    # ---------------------------------------------------------------------------

    def _es_informe_semanal(self, doc: Any) -> bool:
        """Verifica si el documento corresponde a un informe semanal consolidado."""
        for p in doc.paragraphs[:10]:
            p_lower = p.text.strip().lower()
            if "informe semanal" in p_lower and "mecanismo institucional" in p_lower:
                return True

        for t in doc.tables:
            txt_t = " ".join(c.text.strip().lower() for row in t.rows[:3] for c in row.cells)
            if "mes planificado" in txt_t and "actividad mensual" in txt_t:
                return True

        return False

    def _extraer_narrativa_y_evidencias(self, doc: Any) -> Tuple[NarrativaSeccionesDTO, EvidenciasAnexosDTO]:
        """Extrae las secciones narrativas y cataloga las evidencias fotográficas y de firmas."""
        seccion_actual = ""
        objetivo_general: Optional[str] = None
        objetivos_especificos: List[str] = []
        diseno_metodologico_partes: List[str] = []
        desarrollo_partes: List[str] = []
        conclusiones: List[str] = []
        recomendaciones: List[str] = []
        enlaces: List[str] = []

        tiene_anexo_asistencia = False
        tiene_anexo_fotos = False
        evidencias_detectadas: List[EvidenciaDetectadaDTO] = []
        conteo_asistencia = 0
        conteo_fotos = 0

        # Mapeo de imágenes globales en relaciones
        img_rels = []
        try:
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    img_rels.append(rel.target_ref)
        except Exception:
            pass

        conteo_total_imagenes = len(img_rels)

        for i, p in enumerate(doc.paragraphs):
            texto = p.text.strip()

            # Detectar cambios de sección por encabezado
            texto_lower = texto.lower()
            if "objetivo de la actividad" in texto_lower or "objetivos de la actividad" in texto_lower:
                seccion_actual = "OBJETIVO"
                continue
            elif "diseño metodológico" in texto_lower or "diseno metodologico" in texto_lower:
                seccion_actual = "DISENO"
                continue
            elif "desarrollo de la actividad" in texto_lower:
                seccion_actual = "DESARROLLO"
                continue
            elif "conclusiones" in texto_lower or "conclusión" in texto_lower:
                seccion_actual = "CONCLUSIONES"
                continue
            elif "recomendaciones" in texto_lower or "recomendación" in texto_lower:
                seccion_actual = "RECOMENDACIONES"
                continue
            elif "divulgación de la actividad" in texto_lower or "divulgacion de la actividad" in texto_lower:
                seccion_actual = "DIVULGACION"
                continue
            elif "anexo 2" in texto_lower and "asistencia" in texto_lower:
                seccion_actual = "ANEXO_ASISTENCIA"
                tiene_anexo_asistencia = True
            elif "anexo 3" in texto_lower or "fotografía" in texto_lower or "fotografia" in texto_lower:
                seccion_actual = "ANEXO_FOTOS"
                tiene_anexo_fotos = True

            # Detectar imágenes en el párrafo
            num_imagenes_parrafo = p._element.xml.count("<a:graphic") + p._element.xml.count("<w:drawing")
            if num_imagenes_parrafo > 0:
                if seccion_actual == "ANEXO_ASISTENCIA":
                    conteo_asistencia += num_imagenes_parrafo
                    for img_idx in range(num_imagenes_parrafo):
                        evidencias_detectadas.append(
                            EvidenciaDetectadaDTO(
                                tipo=TipoEvidenciaWord.LISTA_FIRMADA,
                                seccion_origen="Anexo 2. Lista de Asistencia",
                                indice_imagen=len(evidencias_detectadas) + 1,
                            )
                        )
                elif seccion_actual == "ANEXO_FOTOS" or "foto" in texto_lower:
                    conteo_fotos += num_imagenes_parrafo
                    for img_idx in range(num_imagenes_parrafo):
                        evidencias_detectadas.append(
                            EvidenciaDetectadaDTO(
                                tipo=TipoEvidenciaWord.FOTOGRAFIA,
                                seccion_origen="Anexo 3. Fotografía",
                                indice_imagen=len(evidencias_detectadas) + 1,
                            )
                        )
                else:
                    for img_idx in range(num_imagenes_parrafo):
                        evidencias_detectadas.append(
                            EvidenciaDetectadaDTO(
                                tipo=TipoEvidenciaWord.OTRO,
                                seccion_origen=seccion_actual or "Documento",
                                indice_imagen=len(evidencias_detectadas) + 1,
                            )
                        )

            # Acumular texto según sección activa
            if not texto:
                continue

            if seccion_actual == "OBJETIVO":
                if re.match(r"^\d+\.\d+", texto):
                    objetivos_especificos.append(texto)
                elif objetivo_general is None:
                    objetivo_general = texto
                else:
                    objetivos_especificos.append(texto)
            elif seccion_actual == "DISENO":
                diseno_metodologico_partes.append(texto)
            elif seccion_actual == "DESARROLLO":
                desarrollo_partes.append(texto)
            elif seccion_actual == "CONCLUSIONES":
                conclusiones.append(texto)
            elif seccion_actual == "RECOMENDACIONES":
                recomendaciones.append(texto)
            elif seccion_actual == "DIVULGACION":
                if "http" in texto:
                    enlaces.append(texto)

        narrativa = NarrativaSeccionesDTO(
            objetivo_general=objetivo_general,
            objetivos_especificos=objetivos_especificos,
            diseno_metodologico="\n".join(diseno_metodologico_partes) if diseno_metodologico_partes else None,
            desarrollo_actividad="\n".join(desarrollo_partes) if desarrollo_partes else None,
            conclusiones=conclusiones,
            recomendaciones=recomendaciones,
            enlaces_divulgacion=enlaces,
        )

        evidencias = EvidenciasAnexosDTO(
            conteo_total_imagenes=conteo_total_imagenes,
            imagenes_asistencia_count=conteo_asistencia,
            imagenes_fotografia_count=conteo_fotos,
            evidencias=evidencias_detectadas,
            tiene_anexo_asistencia=tiene_anexo_asistencia or conteo_asistencia > 0,
            tiene_anexo_fotografias=tiene_anexo_fotos or conteo_fotos > 0,
        )

        return narrativa, evidencias

    def _extraer_ficha_tecnica(self, doc: Any, advertencias: List[str]) -> Tuple[Optional[FichaTecnicaDTO], bool]:
        """Extrae los pares etiqueta-valor y datos normalizados de la Tabla 1 (Ficha Técnica)."""
        tabla_candidata = None

        for t in doc.tables:
            txt_t = " ".join(c.text.strip().lower() for row in t.rows[:4] for c in row.cells)
            if "actividad general" in txt_t or "ficha técnica" in txt_t or "línea estratégica" in txt_t or "linea estrategica" in txt_t:
                tabla_candidata = t
                break

        if tabla_candidata is None:
            return None, False

        mapa_etiquetas: Dict[str, List[str]] = {}
        for r in tabla_candidata.rows:
            if len(r.cells) < 2:
                continue
            lbl = r.cells[0].text.strip()
            val = r.cells[1].text.strip()
            if not lbl and not val:
                continue
            mapa_etiquetas.setdefault(lbl, []).append(val)

        # Extraer campos canónicos mediante coincidencias difusas de etiqueta
        actividad_general = self._obtener_primer_valor(mapa_etiquetas, ["actividad general", "nombre de la actividad", "actividad"])
        linea_estrategica = self._obtener_primer_valor(
            mapa_etiquetas,
            ["línea estratégica de la actividad", "linea estrategica de la actividad", "línea estratégica", "linea estrategica", "eje"]
        )
        indicador = self._obtener_primer_valor(mapa_etiquetas, ["indicador al que aporta", "indicador"])
        lugar = self._obtener_primer_valor(mapa_etiquetas, ["lugar", "sede", "recinto"])
        fecha_realizacion = self._obtener_primer_valor(mapa_etiquetas, ["fecha de realización", "fecha de realizacion", "fecha"])

        # Intentar parsear fecha a ISO (DD/MM/AAAA)
        fecha_iso = self._normalizar_fecha_iso(fecha_realizacion)

        # Extraer resultados, dificultades, acuerdos
        resultados = self._obtener_todos_valores(mapa_etiquetas, ["principales resultados", "resultados"])
        dificultades = self._obtener_todos_valores(mapa_etiquetas, ["principales dificultades", "dificultades"])
        acuerdos = self._obtener_todos_valores(mapa_etiquetas, ["acuerdos de la acción", "acuerdos de la accion", "acuerdos"])

        # Extraer totales declarados en el texto de Participantes
        total_part, masc_part, fem_part, etnias_declaradas = self._extraer_participantes_de_ficha(mapa_etiquetas)

        ficha_dto = FichaTecnicaDTO(
            actividad_general=actividad_general,
            linea_estrategica=linea_estrategica,
            indicador=indicador,
            lugar=lugar,
            fecha_realizacion=fecha_realizacion,
            fecha_iso=fecha_iso,
            total_participantes_declarado=total_part,
            masculino_declarado=masc_part,
            femenino_declarado=fem_part,
            distribucion_etnica_declarada=etnias_declaradas,
            resultados=resultados,
            dificultades=dificultades,
            acuerdos=acuerdos,
            mapa_etiquetas_crudo=mapa_etiquetas,
        )

        return ficha_dto, True

    def _extraer_matriz_cuantitativa(self, doc: Any, advertencias: List[str]) -> Tuple[Optional[MatrizCuantitativaDTO], bool]:
        """Extrae la Matriz Cuantitativa Desagregada (Tabla 2)."""
        tabla_candidata = None

        for t in doc.tables:
            # Buscar tabla con columnas de género F y M
            for r_idx, r in enumerate(t.rows[:3]):
                c_texts = [c.text.strip().upper() for c in r.cells]
                if "F" in c_texts and "M" in c_texts and ("TOTAL" in c_texts or any("ESTUDIANTE" in x for x in c_texts)):
                    tabla_candidata = t
                    break
            if tabla_candidata is not None:
                break

        if tabla_candidata is None:
            return None, False

        # Encontrar la fila de subcabeceras (la que contiene F, M, Total)
        fila_cabecera_idx = -1
        for r_idx, r in enumerate(tabla_candidata.rows[:3]):
            c_texts = [c.text.strip().upper() for c in r.cells]
            if "F" in c_texts and "M" in c_texts:
                fila_cabecera_idx = r_idx
                break

        if fila_cabecera_idx == -1 or fila_cabecera_idx + 1 >= len(tabla_candidata.rows):
            advertencias.append("Tabla 2 identificada pero no se pudo localizar la fila de datos numéricos.")
            return None, True

        fila_cab = tabla_candidata.rows[fila_cabecera_idx]
        fila_val = tabla_candidata.rows[fila_cabecera_idx + 1]

        headers = [c.text.strip().replace("\n", " ") for c in fila_cab.cells]
        values = [c.text.strip().replace("\n", " ") for c in fila_val.cells]

        # Extraer campos alineando por cabecera
        actividad_declarada: Optional[str] = None
        femenino: Optional[int] = None
        masculino: Optional[int] = None
        total: Optional[int] = None
        estudiantes: Optional[int] = None
        docentes: Optional[int] = None
        trabajadores_admo: Optional[int] = None
        otros: Optional[int] = None
        etnias: Dict[str, int] = {}
        columnas_detectadas: List[str] = []

        for h, v in zip(headers, values):
            h_clean = h.strip()
            if not h_clean:
                continue
            columnas_detectadas.append(h_clean)
            h_upper = h_clean.upper()

            # Actividad
            if "ACTIVIDAD" in h_upper and actividad_declarada is None:
                actividad_declarada = v
                continue

            val_int = self._parsear_entero(v)

            # Género
            if h_upper == "F" and femenino is None:
                femenino = val_int
            elif h_upper == "M" and masculino is None:
                masculino = val_int
            elif h_upper == "TOTAL" and total is None:
                total = val_int
            # Estamentos
            elif "ESTUDIANTE" in h_upper and estudiantes is None:
                estudiantes = val_int
            elif "DOCENTE" in h_upper and docentes is None:
                docentes = val_int
            elif ("TRAB" in h_upper or "ADMO" in h_upper or "ADMINISTRATIVO" in h_upper) and trabajadores_admo is None:
                trabajadores_admo = val_int
            elif "OTROS" in h_upper and otros is None:
                otros = val_int
            # Etnias
            elif any(e in h_upper for e in ["CREOLE", "MZT", "MESTIZO", "MISKITO", "RAMA", "ULWA", "MAYAGNA", "MAYANGNA", "GARÍFUNA", "GARIFUNA"]):
                etnia_nombre = self._normalizar_nombre_etnia(h_clean)
                if val_int is not None:
                    etnias[etnia_nombre] = val_int

        # Validaciones de consistencia (DETECTAR != CORREGIR)
        disc_genero = False
        if total is not None and femenino is not None and masculino is not None:
            if total != femenino + masculino:
                disc_genero = True
                advertencias.append(
                    f"Discrepancia aritmética en Tabla 2: Total ({total}) != Femenino ({femenino}) + Masculino ({masculino})."
                )

        disc_estamento = False
        if total is not None and (estudiantes is not None or docentes is not None or trabajadores_admo is not None or otros is not None):
            suma_estamentos = sum(x for x in [estudiantes, docentes, trabajadores_admo, otros] if x is not None)
            if total != suma_estamentos:
                disc_estamento = True
                advertencias.append(
                    f"Discrepancia aritmética en Tabla 2: Total ({total}) != Suma estamentos ({suma_estamentos})."
                )

        matriz_dto = MatrizCuantitativaDTO(
            actividad_declarada=actividad_declarada,
            femenino=femenino,
            masculino=masculino,
            total=total,
            estudiantes=estudiantes,
            docentes=docentes,
            trabajadores_administrativos=trabajadores_admo,
            otros=otros,
            distribucion_etnica=etnias,
            columnas_detectadas=columnas_detectadas,
            discrepancia_suma_genero=disc_genero,
            discrepancia_suma_estamento=disc_estamento,
        )

        return matriz_dto, True

    # ---------------------------------------------------------------------------
    # Utilidades auxiliares seguras
    # ---------------------------------------------------------------------------

    def _obtener_primer_valor(self, mapa: Dict[str, List[str]], claves_buscadas: List[str]) -> Optional[str]:
        """Busca el primer valor que coincida con alguna de las claves buscadas, respetando orden de prioridad."""
        # Fase 1: Coincidencia exacta de etiqueta
        for c in claves_buscadas:
            c_clean = c.lower().strip()
            for lbl, vals in mapa.items():
                lbl_clean = self._limpiar_etiqueta(lbl)
                if lbl_clean == c_clean:
                    for v in vals:
                        v_str = v.strip()
                        if v_str:
                            return v_str
                    # Si la etiqueta exacta existe en el documento pero está vacía, no buscar coincidencias espurias
                    return None

        # Fase 2: Coincidencia por prefijo o contención específica (evitando palabras genéricas cortas)
        for c in claves_buscadas:
            c_clean = c.lower().strip()
            for lbl, vals in mapa.items():
                lbl_clean = self._limpiar_etiqueta(lbl)
                if lbl_clean.startswith(c_clean) or (len(c_clean) > 8 and c_clean in lbl_clean):
                    for v in vals:
                        v_str = v.strip()
                        if v_str:
                            return v_str
                    return None

        return None

    def _obtener_todos_valores(self, mapa: Dict[str, List[str]], claves_buscadas: List[str]) -> List[str]:
        """Obtiene todos los valores no vacíos asociados a las claves buscadas."""
        resultado = []
        for c in claves_buscadas:
            c_clean = c.lower().strip()
            for lbl, vals in mapa.items():
                lbl_clean = self._limpiar_etiqueta(lbl)
                if lbl_clean == c_clean or lbl_clean.startswith(c_clean) or (len(c_clean) > 8 and c_clean in lbl_clean):
                    for v in vals:
                        v_str = v.strip()
                        if v_str and v_str not in resultado:
                            resultado.append(v_str)
        return resultado

    def _limpiar_etiqueta(self, texto: str) -> str:
        """Normaliza una etiqueta para comparación eliminando numeración y caracteres especiales."""
        t = re.sub(r"^\d+[\.\)]\s*", "", texto)  # elimina '3. ' o '8. '
        t = t.lower().strip()
        return t

    def _normalizar_fecha_iso(self, fecha_raw: Optional[str]) -> Optional[str]:
        """Intenta normalizar DD/MM/AAAA o DD-MM-AAAA a AAAA-MM-DD."""
        if not fecha_raw:
            return None
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", fecha_raw)
        if m:
            dia, mes, anio = m.groups()
            return f"{int(anio):04d}-{int(mes):02d}-{int(dia):02d}"
        return None

    def _parsear_entero(self, val: str) -> Optional[int]:
        """Extrae de forma segura el primer entero presente en la celda."""
        if not val:
            return None
        m = re.search(r"\d+", val)
        if m:
            return int(m.group())
        return None

    def _normalizar_nombre_etnia(self, texto: str) -> str:
        """Normaliza el nombre de la etnia a su forma canónica."""
        t_upper = texto.upper()
        if "CREOLE" in t_upper:
            return "Creole"
        elif "MZT" in t_upper or "MESTIZO" in t_upper:
            return "Mestizo"
        elif "MISKITO" in t_upper:
            return "Miskito"
        elif "RAMA" in t_upper:
            return "Rama"
        elif "ULWA" in t_upper:
            return "Ulwa"
        elif "MAYAGNA" in t_upper or "MAYANGNA" in t_upper:
            return "Mayangna"
        elif "GARIFUNA" in t_upper or "GARÍFUNA" in t_upper:
            return "Garífuna"
        return texto.strip().title()

    def _extraer_participantes_de_ficha(self, mapa: Dict[str, List[str]]) -> Tuple[Optional[int], Optional[int], Optional[int], Dict[str, int]]:
        """Extrae los valores numéricos del campo 'Participantes' de la Tabla 1 si están en corchetes."""
        total = None
        masc = None
        fem = None
        etnias: Dict[str, int] = {}

        for lbl, vals in mapa.items():
            if "participante" in lbl.lower():
                for v in vals:
                    v_clean = v.strip()
                    # Total: [15]
                    m_tot = re.search(r"total\s*:\s*\[?(\d+)\]?", v_clean, re.IGNORECASE)
                    if m_tot and total is None:
                        total = int(m_tot.group(1))

                    # Masculino: [8]
                    m_masc = re.search(r"masculino\s*:\s*\[?(\d+)\]?", v_clean, re.IGNORECASE)
                    if m_masc and masc is None:
                        masc = int(m_masc.group(1))

                    # Femenino: [7]
                    m_fem = re.search(r"femenino\s*:\s*\[?(\d+)\]?", v_clean, re.IGNORECASE)
                    if m_fem and fem is None:
                        fem = int(m_fem.group(1))

                    # Etnias tipo: Creole [1]   Mestizos [4] Miskito [10]
                    matches_etnias = re.findall(r"([a-zA-ZáéíóúÁÉÍÓÚ]+)\s*\[\s*(\d+)\s*\]", v_clean)
                    for e_nom, e_cant in matches_etnias:
                        if e_nom.lower() not in ["total", "masculino", "femenino"]:
                            etnia_norm = self._normalizar_nombre_etnia(e_nom)
                            etnias[etnia_norm] = int(e_cant)

        return total, masc, fem, etnias
