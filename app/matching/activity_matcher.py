"""
app.matching.activity_matcher

Módulo de coincidencia y unificación de actividades entre fuentes (Regla C-06, C-13 y Corrección 2).
Evalúa EVIDENCIA MÚLTIPLE para relacionar:
- Actividad del informe semanal (Word).
- Actividad de la lista de asistencia física/escaneada.

Regla de seguridad:
- ALTA CONFIANZA (múltiples evidencias coincidentes): unifica en una sola Activity con id_actividad único
  y conserva ambos nombres para trazabilidad.
- CONFIANZA INSUFICIENTE: NO unifica automáticamente. Emite ValidationResult(REVISION, 'MATCH_ACTIVIDAD_REVISION').
- NO COINCIDE: mantiene actividades separadas.
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from app.core.models.activity import Activity
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class ActivityMatchResult(BaseModel):
    """Resultado de la evaluación de coincidencia entre dos actividades de diferentes fuentes."""
    coinciden: bool = Field(
        ...,
        description="Indica si se determinó una coincidencia válida para unificación."
    )
    nivel_confianza: str = Field(
        ...,
        description="Nivel de confianza: 'ALTA', 'INSUFICIENTE' o 'NULA'."
    )
    actividad_unificada: Optional[Activity] = Field(
        default=None,
        description="Instancia de Activity unificada si la confianza fue ALTA."
    )
    evidencias: List[str] = Field(
        default_factory=list,
        description="Lista de evidencias concretas que respaldan la decisión."
    )
    validaciones: List[ValidationResult] = Field(
        default_factory=list,
        description="Validaciones y alertas asociadas al proceso de matching."
    )


class ActivityMatcher:
    """
    Evaluador conservador de coincidencias de actividades con evidencia múltiple.
    """

    @classmethod
    def _normalizar_texto_comparacion(cls, texto: str) -> set:
        """Extrae conjunto de palabras significativas para comparar tema/contenido."""
        if not texto:
            return set()
        palabras = re.findall(r"\b[a-záéíóúñ]{4,}\b", texto.lower())
        # Descartar palabras vacías comunes
        stopwords = {"para", "como", "sobre", "desde", "hacia", "entre", "este", "esta", "estos"}
        return set(palabras) - stopwords

    @classmethod
    def _normalizar_sede(cls, sede: Optional[str]) -> str:
        if not sede:
            return ""
        s = sede.lower()
        if "bilwi" in s:
            return "bilwi"
        if "bluefields" in s:
            return "bluefields"
        if "las minas" in s:
            return "las minas"
        return s.strip()

    @classmethod
    def evaluar_coincidencia(
        cls,
        actividad_word: Activity,
        datos_asistencia: Dict[str, Any]
    ) -> ActivityMatchResult:
        """
        Compara la actividad del informe Word con los metadatos de la lista de asistencia.
        Evalúa múltiples atributos:
        - Fecha
        - Sede
        - Municipio
        - Departamento
        - Horario
        - Relación semántica / palabras clave temáticas de los nombres
        """
        evidencias: List[str] = []
        puntos_coincidencia = 0
        puntos_contradictorios = 0

        # 1. Comparar Fecha
        fecha_word = str(actividad_word.fecha_evento or "").strip()
        fecha_asist = str(datos_asistencia.get("fecha_evento") or "").strip()
        if fecha_word and fecha_asist:
            if fecha_word == fecha_asist:
                evidencias.append(f"Misma fecha: '{fecha_word}'")
                puntos_coincidencia += 1
            else:
                puntos_contradictorios += 1
                evidencias.append(f"Discrepancia de fechas: Word='{fecha_word}', Asistencia='{fecha_asist}'")

        # 2. Comparar Sede
        sede_word = cls._normalizar_sede(actividad_word.sede)
        sede_asist = cls._normalizar_sede(datos_asistencia.get("sede"))
        if sede_word and sede_asist:
            if sede_word == sede_asist:
                evidencias.append(f"Misma sede: '{actividad_word.sede}' vs '{datos_asistencia.get('sede')}'")
                puntos_coincidencia += 1
            else:
                puntos_contradictorios += 1
                evidencias.append(f"Discrepancia de sedes: '{sede_word}' vs '{sede_asist}'")

        # 3. Comparar Horario
        horario_word = str(actividad_word.informacion_adicional or "").strip()
        horario_asist = str(datos_asistencia.get("horario") or "").strip()
        if horario_asist and horario_asist in horario_word:
            evidencias.append(f"Mismo horario: '{horario_asist}'")
            puntos_coincidencia += 1
        elif horario_asist and "horario" in datos_asistencia:
            # Si ambos tienen horario especificado explícitamente
            if datos_asistencia.get("horario") == datos_asistencia.get("horario_word"):
                evidencias.append(f"Mismo horario: '{horario_asist}'")
                puntos_coincidencia += 1

        # 4. Comparar Geografía (Municipio / Departamento)
        muni_word = str(actividad_word.municipio_evento or "").lower().strip()
        muni_asist = str(datos_asistencia.get("municipio_evento") or "").lower().strip()
        if muni_word and muni_asist and (muni_word in muni_asist or muni_asist in muni_word):
            evidencias.append(f"Mismo municipio: '{actividad_word.municipio_evento}'")
            puntos_coincidencia += 1

        depto_word = str(actividad_word.departamento or "").lower().strip()
        depto_asist = str(datos_asistencia.get("departamento") or "").lower().strip()
        if depto_word and depto_asist and (depto_word in depto_asist or depto_asist in depto_word):
            evidencias.append(f"Mismo departamento territorial: '{actividad_word.departamento}'")
            puntos_coincidencia += 1

        # 5. Comparar Títulos / Relación semántica del tema
        nombre_word = actividad_word.nombre_actividad_original
        nombre_asist = str(datos_asistencia.get("nombre_actividad_asistencia") or "").strip()

        tokens_word = cls._normalizar_texto_comparacion(nombre_word)
        tokens_asist = cls._normalizar_texto_comparacion(nombre_asist)
        interseccion = tokens_word.intersection(tokens_asist)

        if interseccion:
            evidencias.append(f"Términos temáticos coincidentes ({len(interseccion)}): {sorted(list(interseccion))}")
            if len(interseccion) >= 3:
                puntos_coincidencia += 2
            else:
                puntos_coincidencia += 1
        else:
            puntos_contradictorios += 1
            evidencias.append("No se encontraron términos temáticos clave en común.")

        validaciones: List[ValidationResult] = []

        # Toma de decisión conservadora (Regla de seguridad):
        # Para ALTA CONFIANZA se requiere:
        # - Al menos 3 evidencias concordantes
        # - Cero contradicciones en fecha o sede
        # - Intersección temática positiva
        if puntos_contradictorios == 0 and puntos_coincidencia >= 3 and len(interseccion) >= 2:
            nivel_confianza = "ALTA"
            coinciden = True

            # Crear actividad unificada conservando ambos nombres para trazabilidad
            actividad_unificada = Activity(
                id_actividad=actividad_word.id_actividad,
                nombre_actividad_original=nombre_word,
                nombre_actividad_oficial=actividad_word.nombre_actividad_oficial or nombre_word,
                fecha_evento=actividad_word.fecha_evento,
                sede=actividad_word.sede,
                departamento=actividad_word.departamento,
                municipio_evento=actividad_word.municipio_evento,
                programa=actividad_word.programa,
                ambito=actividad_word.ambito,
                tipo_evento=actividad_word.tipo_evento,
                eje_linea_estrategica=actividad_word.eje_linea_estrategica,
                informacion_adicional=(
                    f"{actividad_word.informacion_adicional or ''} | "
                    f"Nombre en asistencia: '{nombre_asist}' | "
                    f"Horario: {horario_asist}"
                ).strip(" |"),
                fuente_origen=f"{actividad_word.fuente_origen or 'Word'} + {datos_asistencia.get('fuente_origen', 'Asistencia')}"
            )

            # Emitir validación informativa de la unificación
            val_info = ValidationResult(
                id_referencia=actividad_unificada.id_actividad,
                nivel=NivelValidacion.INFO,
                codigo="MATCH_ACTIVIDAD_UNIFICADA",
                mensaje=(
                    f"Actividad unificada con alta confianza por evidencia múltiple. "
                    f"Evidencias: {'; '.join(evidencias)}."
                ),
                fuente_origen=actividad_unificada.fuente_origen
            )
            validaciones.append(val_info)

            # Si los nombres son textualmente distintos, registrar la alerta
            if nombre_word != nombre_asist:
                val_dif = ValidationResult(
                    id_referencia=actividad_unificada.id_actividad,
                    nivel=NivelValidacion.INFO,
                    codigo="VAL_ACTIVIDAD_DIFERENCIA_NOMBRE",
                    mensaje=(
                        f"Diferencia de nombres entre fuentes para la misma actividad. "
                        f"Word: '{nombre_word}'. Asistencia: '{nombre_asist}'."
                    ),
                    fuente_origen=actividad_unificada.fuente_origen
                )
                validaciones.append(val_dif)

            return ActivityMatchResult(
                coinciden=True,
                nivel_confianza=nivel_confianza,
                actividad_unificada=actividad_unificada,
                evidencias=evidencias,
                validaciones=validaciones
            )

        elif puntos_coincidencia >= 1 and (puntos_contradictorios > 0 or len(interseccion) < 2):
            # CONFIANZA INSUFICIENTE: Enviar a REVISIÓN humana
            nivel_confianza = "INSUFICIENTE"
            val_rev = ValidationResult(
                id_referencia=actividad_word.id_actividad,
                nivel=NivelValidacion.REVISION,
                codigo="MATCH_ACTIVIDAD_REVISION",
                mensaje=(
                    "Confianza insuficiente para unificar actividades automáticamente. "
                    f"Se requiere revisión humana. Evidencias: {'; '.join(evidencias)}."
                ),
                fuente_origen=f"Word vs {datos_asistencia.get('fuente_origen', 'Asistencia')}"
            )
            validaciones.append(val_rev)

            return ActivityMatchResult(
                coinciden=False,
                nivel_confianza=nivel_confianza,
                actividad_unificada=None,
                evidencias=evidencias,
                validaciones=validaciones
            )
        else:
            # NO COINCIDE
            return ActivityMatchResult(
                coinciden=False,
                nivel_confianza="NULA",
                actividad_unificada=None,
                evidencias=evidencias,
                validaciones=[]
            )
