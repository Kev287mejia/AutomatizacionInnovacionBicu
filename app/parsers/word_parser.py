"""
app.parsers.word_parser

Parser para informes semanales institucionales en formato Word (.docx o representaciones estructuradas).
Extrae metadatos institucionales y crea la entidad Activity correspondiente.
Detecta la presencia de imágenes incrustadas (hojas de asistencia escaneadas).
"""

from pathlib import Path
from typing import Optional, Dict, Any, Union
import docx
from app.core.models.activity import Activity
from app.parsers.base_parser import RawActivityData
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class WordReportParser:
    """
    Parser especializado en extraer datos de la actividad y metadatos desde el Informe Semanal.
    """

    @classmethod
    def parse_from_dict(cls, datos: Dict[str, Any], fuente: str = "informe_word") -> Activity:
        """
        Crea una entidad Activity a partir de un diccionario estructurado de informe semanal.
        """
        raw_nombre = datos.get("actividad") or datos.get("nombre_actividad") or ""
        if not raw_nombre:
            raise ValueError("El informe semanal debe contener el nombre de la actividad.")

        info_adicional = []
        if datos.get("departamento_institucional"):
            info_adicional.append(f"Dpto: {datos['departamento_institucional']}")
        if datos.get("mes"):
            info_adicional.append(f"Mes: {datos['mes']}")
        if datos.get("semana"):
            info_adicional.append(f"Semana: {datos['semana']}")
        if datos.get("horario"):
            info_adicional.append(f"Horario: {datos['horario']}")

        actividad = Activity(
            nombre_actividad_original=raw_nombre.strip(),
            fecha_evento=datos.get("fecha"),
            sede=datos.get("sede"),
            departamento=datos.get("departamento_territorial") or datos.get("departamento"),
            municipio_evento=datos.get("municipio"),
            programa=datos.get("departamento_institucional"),
            tipo_evento=datos.get("tipo_actividad"),
            eje_linea_estrategica=datos.get("eje"),
            informacion_adicional=" | ".join(info_adicional) if info_adicional else None,
            fuente_origen=fuente
        )
        return actividad

    @classmethod
    def parse_file(cls, ruta_archivo: Union[str, Path]) -> Activity:
        """
        Lee un archivo Word (.docx) real, extrae párrafos, tablas e imágenes incrustadas.
        """
        path = Path(ruta_archivo)
        if not path.exists():
            raise FileNotFoundError(f"Archivo de informe Word no encontrado: {path}")

        doc = docx.Document(path)

        # 1. Contar imágenes incrustadas (hojas de asistencia escaneadas)
        conteo_imagenes = 0
        try:
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    conteo_imagenes += 1
        except Exception as e:
            logger.debug(f"No se pudieron leer relaciones de imagen: {e}")

        # 2. Extraer texto de párrafos y tablas
        lineas_texto = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for t in doc.tables:
            for fila in t.rows:
                fila_texto = " | ".join([c.text.strip() for c in fila.cells if c.text.strip()])
                if fila_texto:
                    lineas_texto.append(fila_texto)

        # Extraer metadatos heurísticamente de las líneas de texto
        metadatos: Dict[str, Any] = {
            "nombre_actividad": None,
            "departamento_institucional": None,
            "mes": None,
            "semana": None,
            "sede": None,
            "departamento_territorial": None,
            "municipio": None,
            "eje": None,
            "tipo_actividad": None,
            "fecha": None,
            "horario": None,
        }

        texto_completo = "\n".join(lineas_texto)
        logger.info(f"Informe Word leído: {len(lineas_texto)} líneas de texto, {conteo_imagenes} imágenes detectadas.")

        # Buscar claves comunes
        for linea in lineas_texto:
            linea_lower = linea.lower()
            if "actividad:" in linea_lower:
                metadatos["nombre_actividad"] = linea.split(":", 1)[1].strip()
            elif "departamento:" in linea_lower:
                metadatos["departamento_institucional"] = linea.split(":", 1)[1].strip()
            elif "sede:" in linea_lower:
                metadatos["sede"] = linea.split(":", 1)[1].strip()
            elif "municipio:" in linea_lower:
                metadatos["municipio"] = linea.split(":", 1)[1].strip()
            elif "fecha:" in linea_lower:
                metadatos["fecha"] = linea.split(":", 1)[1].strip()
            elif "horario:" in linea_lower:
                metadatos["horario"] = linea.split(":", 1)[1].strip()
            elif "eje:" in linea_lower:
                metadatos["eje"] = linea.split(":", 1)[1].strip()

        # Si no hubo etiqueta explícita 'Actividad:', usar el primer párrafo relevante
        if not metadatos["nombre_actividad"] and lineas_texto:
            metadatos["nombre_actividad"] = lineas_texto[0]

        return cls.parse_from_dict(metadatos, fuente=str(path.name))
