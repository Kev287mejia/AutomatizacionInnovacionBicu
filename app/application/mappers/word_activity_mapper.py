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
from app.core.models.activity import ActividadMetricaAgregada, Activity
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

        # GAP-2: Preservar código/indicador institucional proveniente de la Ficha Técnica (Tabla 1)
        codigo_indicador = ficha.indicador.strip() if ficha.indicador else None

        # GAP-3: Hash SHA-256 de los bytes reales del documento Word
        hash_sha256 = extraction_dto.hash_sha256

        # CORRECCIÓN CRÍTICA 02: Construcción de información adicional de trazabilidad
        informacion_adicional = cls._construir_trazabilidad_adicional(extraction_dto)

        id_actividad = str(uuid.uuid4())

        # GAP-1: Mapeo de métricas cuantitativas agregadas oficiales de Tabla 2
        metrica_agregada = cls.to_metrica_agregada(extraction_dto, id_actividad)

        return Activity(
            id_actividad=id_actividad,
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
            codigo_indicador=codigo_indicador,
            hash_sha256=hash_sha256,
            metrica_agregada=metrica_agregada,
        )

    @classmethod
    def to_metrica_agregada(
        cls, extraction_dto: WordActivityExtractionResultDTO, id_actividad: str
    ) -> Optional[ActividadMetricaAgregada]:
        """Extrae la métrica agregada oficial (15 métricas) desde la Tabla 2 del informe Word.

        Reglas:
        - GAP-1: Persistencia formal 1:1 en actividad_metrica_agregada.
        - NO CREA PARTICIPANTES NOMINALES.
        - DETECTAR != CORREGIR: Preserva discrepancias sin alteración matemática.
        - Preserva Nones cuando el dato no fue provisto (no inventar ceros).
        """
        mc = extraction_dto.matriz_cuantitativa
        if mc is None:
            return None

        # Desglose étnico declarado
        etnias = {k.strip().upper(): v for k, v in mc.distribucion_etnica.items()} if mc.distribucion_etnica else {}

        mestizo = etnias.get("MESTIZO")
        creole = etnias.get("CREOLE")
        miskitu = etnias.get("MISKITU") if "MISKITU" in etnias else etnias.get("MISKITO")
        mayangna = etnias.get("MAYANGNA")
        ulwa = etnias.get("ULWA")
        rama = etnias.get("RAMA")
        garifuna = etnias.get("GARÍFUNA") if "GARÍFUNA" in etnias else etnias.get("GARIFUNA")

        # Otras etnias fuera de las 7 oficiales
        etnias_oficiales = {"MESTIZO", "CREOLE", "MISKITU", "MISKITO", "MAYANGNA", "ULWA", "RAMA", "GARÍFUNA", "GARIFUNA"}
        otras_etnias_vals = [v for k, v in etnias.items() if k not in etnias_oficiales]
        if otras_etnias_vals:
            total_otra_etnia = sum(otras_etnias_vals)
        elif "OTRA" in etnias or "OTRO" in etnias or "OTRAS" in etnias:
            total_otra_etnia = etnias.get("OTRA", etnias.get("OTRO", etnias.get("OTRAS")))
        else:
            total_otra_etnia = None

        # Discrepancia interna (aritmética de Tabla 2 o Ficha vs Tabla 2)
        ficha = extraction_dto.ficha_tecnica
        discrepancia_ficha_tabla2 = False
        if ficha and ficha.total_participantes_declarado is not None and mc.total is not None:
            if ficha.total_participantes_declarado != mc.total:
                discrepancia_ficha_tabla2 = True

        presenta_discrepancia = (
            mc.discrepancia_suma_genero
            or mc.discrepancia_suma_estamento
            or discrepancia_ficha_tabla2
        )

        return ActividadMetricaAgregada(
            id_actividad=id_actividad,
            total_participantes=mc.total,
            total_femenino=mc.femenino,
            total_masculino=mc.masculino,
            total_estudiantes=mc.estudiantes,
            total_docentes=mc.docentes,
            total_administrativos=mc.trabajadores_administrativos,
            total_otros=mc.otros,
            total_mestizo=mestizo,
            total_creole=creole,
            total_miskitu=miskitu,
            total_mayangna=mayangna,
            total_ulwa=ulwa,
            total_rama=rama,
            total_garifuna=garifuna,
            total_otra_etnia=total_otra_etnia,
            fuente_seccion="TABLA_2_MATRIZ_CUANTITATIVA",
            presenta_discrepancia_interna=presenta_discrepancia,
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
