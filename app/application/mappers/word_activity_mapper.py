"""app.application.mappers.word_activity_mapper

Mapeador desacoplado entre el DTO de extracción Word y las entidades del modelo de Dominio.

REGLAS DE DOMINIO Y ARQUITECTURA:
- Clean Architecture: No accede a persistencia ni ejecuta consultas SQL.
- INDICADOR != TIPO_EVENTO (Corrección crítica 01):
  El indicador institucional NO se asigna a tipo_evento.
  tipo_evento solo se define si existe mención explícita en el documento; de lo contrario es None.
- INFORMACION_ADICIONAL (Corrección crítica 02):
  Se utiliza exclusivamente como mecanismo de trazabilidad documental compatible con el modelo existente.
  No sustituye un modelo relacional y no normaliza las cifras de Tabla 2.
- TOTAL CUANTITATIVO != PARTICIPANTES NOMINALES:
  No genera objetos Person ni Participation.
- Evidencias:
  No inventa rutas físicas ni archivos en disco.
"""

from typing import List, Optional, Tuple
import uuid

from app.application.dto.word_extraction_dtos import (
    TipoEvidenciaWord,
    WordActivityExtractionResultDTO,
)
from app.core.models.activity import Activity
from app.core.models.evidence import Evidencia, TipoEvidencia


class WordActivityDTOMapper:
    """Mapeador responsable de traducir DTOs de extracción Word a entidades de dominio."""

    SEDES_VALIDAS = {
        "BLUEFIELDS",
        "BILWI",
        "EL_RAMA",
        "CORN_ISLAND",
        "WASPAM",
        "PAIWAS",
        "LAS_MINAS",
        "MANAGUA",
    }

    @classmethod
    def to_activity(cls, extraction_dto: WordActivityExtractionResultDTO) -> Activity:
        """Transforma un WordActivityExtractionResultDTO a una entidad de dominio Activity.

        Args:
            extraction_dto: DTO estructurado producto de IWordActivityExtractor.

        Returns:
            Instancia de Activity lista para ser persistida por los repositorios.
        """
        ficha = extraction_dto.ficha_tecnica
        if ficha is None or not ficha.actividad_general:
            raise ValueError("El DTO de extracción debe contener una Ficha Técnica con actividad_general.")

        nombre_original = ficha.actividad_general.strip()
        fecha_evento = ficha.fecha_iso or ficha.fecha_realizacion
        sede = cls.normalizar_sede(ficha.lugar)
        eje_estrategico = ficha.linea_estrategica.strip() if ficha.linea_estrategica else None

        # CORRECCIÓN CRÍTICA 01: INDICADOR != TIPO_EVENTO
        # No mapear ficha.indicador a tipo_evento.
        # Determinar tipo_evento únicamente si existe evidencia explícita en la denominación de la actividad.
        tipo_evento = cls._detectar_tipo_evento_explicito(nombre_original)

        # CORRECCIÓN CRÍTICA 02: Construcción de información adicional de trazabilidad
        informacion_adicional = cls._construir_trazabilidad_adicional(extraction_dto)

        return Activity(
            id_actividad=str(uuid.uuid4()),
            nombre_actividad_original=nombre_original,
            nombre_actividad_oficial=None,
            fecha_evento=fecha_evento,
            sede=sede,
            departamento=None,
            municipio_evento=None,
            programa=None,
            ambito=None,
            tipo_evento=tipo_evento,
            eje_linea_estrategica=eje_estrategico,
            informacion_adicional=informacion_adicional,
            fuente_origen=extraction_dto.nombre_archivo,
        )

    @classmethod
    def to_evidencias(
        cls, extraction_dto: WordActivityExtractionResultDTO, id_actividad: str
    ) -> List[Tuple[Evidencia, int, str]]:
        """Extrae las evidencias detectadas compatibles para vincularlas a la actividad.

        Args:
            extraction_dto: DTO de extracción estructurado.
            id_actividad: UUID de la actividad ya generada.

        Returns:
            Lista de tuplas (Evidencia, orden_presentacion, seccion_informe).
        """
        if extraction_dto.evidencias is None:
            return []

        resultado: List[Tuple[Evidencia, int, str]] = []

        for ev_dto in extraction_dto.evidencias.evidencias:
            if ev_dto.tipo == TipoEvidenciaWord.LISTA_FIRMADA:
                tipo = TipoEvidencia.LISTA_FIRMADA
                seccion = "ANEXO"
            elif ev_dto.tipo == TipoEvidenciaWord.FOTOGRAFIA:
                tipo = TipoEvidencia.FOTOGRAFIA
                seccion = "GALERIA"
            else:
                tipo = TipoEvidencia.DOCUMENTO_ADJUNTO
                seccion = "GALERIA"

            evidencia = Evidencia(
                id_evidencia=str(uuid.uuid4()),
                tipo_evidencia=tipo,
                titulo=ev_dto.seccion_origen,
                descripcion_pie=f"Evidencia detectada en {ev_dto.seccion_origen} (imagen #{ev_dto.indice_imagen})",
                ruta_archivo_relativa=None,  # Regla: No inventar rutas físicas ni archivos en disco
                url_externa=None,
                hash_sha256=None,
                tamano_bytes=None,
                mime_type=None,
                fecha_captura=None,
            )
            resultado.append((evidencia, ev_dto.indice_imagen, seccion))

        return resultado

    @classmethod
    def normalizar_sede(cls, lugar: Optional[str]) -> str:
        """Normaliza el texto de lugar o recinto al catálogo institucional de sedes."""
        if not lugar:
            return "OTRA"

        lugar_upper = lugar.strip().upper()
        for s in cls.SEDES_VALIDAS:
            s_espacios = s.replace("_", " ")
            if s in lugar_upper or s_espacios in lugar_upper:
                return s

        return "OTRA"

    @classmethod
    def _detectar_tipo_evento_explicito(cls, nombre: str) -> Optional[str]:
        """Detecta si el nombre de la actividad contiene explícitamente el tipo de evento institucional."""
        n_upper = nombre.upper()
        if "CAPACITACIÓN" in n_upper or "CAPACITACION" in n_upper:
            return "CAPACITACION"
        elif "FERIA" in n_upper:
            return "FERIA"
        elif "TALLER" in n_upper:
            return "TALLER"
        elif "ENTREGA DE CERTIFICADOS" in n_upper:
            return "ENTREGA DE CERTIFICADOS"
        elif "RALLY" in n_upper:
            return "RALLY"
        elif "JORNADA" in n_upper or "JORNA " in n_upper:
            return "JORNADA"
        elif "PRESENTACIÓN" in n_upper or "PRESENTACION" in n_upper:
            return "PRESENTACION"
        return None

    @classmethod
    def _construir_trazabilidad_adicional(cls, dto: WordActivityExtractionResultDTO) -> Optional[str]:
        """Construye un registro textual de metadatos para fines exclusivos de trazabilidad."""
        partes = []

        if dto.ficha_tecnica:
            if dto.ficha_tecnica.indicador:
                partes.append(f"Indicador: {dto.ficha_tecnica.indicador}")
            if dto.ficha_tecnica.resultados:
                partes.append(f"Resultados: {' | '.join(dto.ficha_tecnica.resultados)}")
            if dto.ficha_tecnica.dificultades:
                partes.append(f"Dificultades: {' | '.join(dto.ficha_tecnica.dificultades)}")
            if dto.ficha_tecnica.acuerdos:
                partes.append(f"Acuerdos: {' | '.join(dto.ficha_tecnica.acuerdos)}")

        if dto.matriz_cuantitativa:
            mc = dto.matriz_cuantitativa
            partes.append(
                f"Cifras Declaradas Tabla 2 (Total={mc.total}, F={mc.femenino}, M={mc.masculino}, "
                f"Estudiantes={mc.estudiantes}, Docentes={mc.docentes}, Admo={mc.trabajadores_administrativos}, "
                f"Otros={mc.otros})"
            )

        if dto.hash_sha256:
            partes.append(f"Hash Fuente: {dto.hash_sha256}")

        return " \n".join(partes) if partes else None
