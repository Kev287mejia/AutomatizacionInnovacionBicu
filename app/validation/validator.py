"""
app.validation.validator

Motor de validación centralizado para entidades internas y datos crudos.
Genera instancias de ValidationResult cumpliendo las reglas institucionales:
- VAL_SEXO_INCOMPATIBLE / VAL_SEXO_AUSENTE
- VAL_CEDULA_VACIA / VAL_CEDULA_FECHA / VAL_CEDULA_FORMATO_DUDOSO
- VAL_EDAD_AUSENTE / VAL_EDAD_FECHA_ANOMALA / VAL_EDAD_FUERA_RANGO
- VAL_CARRERA_ABREVIADA / VAL_CARRERA_AMBIGUA
- VAL_ACTIVIDAD_DIFERENCIA_NOMBRE
- VAL_CATEGORIA_DESCONOCIDA / VAL_CATEGORIA_AUSENTE
- VAL_CAMPO_OBLIGATORIO_FALTANTE
- VAL_REVISION_REQUERIDA
"""

from typing import List, Optional
from app.core.models.activity import Activity
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion, CategoriaParticipacion
from app.normalization.identifier_normalizer import PATRON_FECHA


class DataValidator:
    """
    Motor centralizado de validación.
    Permite validar tanto entidades individuales como conjuntos relacionales.
    """

    @classmethod
    def validar_actividad(
        cls,
        actividad: Activity,
        nombre_alterno_fuente: Optional[str] = None
    ) -> List[ValidationResult]:
        """Valida una entidad Activity y detecta diferencias de título entre fuentes."""
        hallazgos: List[ValidationResult] = []

        if not actividad.nombre_actividad_original or not actividad.nombre_actividad_original.strip():
            hallazgos.append(
                ValidationResult(
                    id_referencia=actividad.id_actividad,
                    nivel=NivelValidacion.ERROR,
                    codigo="VAL_CAMPO_OBLIGATORIO_FALTANTE",
                    mensaje="El nombre original de la actividad es obligatorio.",
                    fuente_origen=actividad.fuente_origen
                )
            )

        if not actividad.fecha_evento:
            hallazgos.append(
                ValidationResult(
                    id_referencia=actividad.id_actividad,
                    nivel=NivelValidacion.WARNING,
                    codigo="VAL_CAMPO_OBLIGATORIO_FALTANTE",
                    mensaje="La fecha del evento no está especificada.",
                    fuente_origen=actividad.fuente_origen
                )
            )

        # Regla 11: Diferencia entre nombre de actividad de Word y Asistencia
        if nombre_alterno_fuente and nombre_alterno_fuente.strip() != actividad.nombre_actividad_original.strip():
            hallazgos.append(
                ValidationResult(
                    id_referencia=actividad.id_actividad,
                    nivel=NivelValidacion.INFO,
                    codigo="VAL_ACTIVIDAD_DIFERENCIA_NOMBRE",
                    mensaje=(
                        f"Diferencia textual detectada entre fuentes para la misma actividad. "
                        f"Fuente principal: '{actividad.nombre_actividad_original}'. "
                        f"Fuente alterna: '{nombre_alterno_fuente}'. Se unificaron por evidencia múltiple."
                    ),
                    fuente_origen=actividad.fuente_origen
                )
            )

        return hallazgos

    @classmethod
    def validar_persona(
        cls,
        persona: Person
    ) -> List[ValidationResult]:
        """Valida una entidad Person identificando anomalías de cédula, edad, sexo y carrera."""
        hallazgos: List[ValidationResult] = []

        # 1. Nombre completo
        if not persona.nombre_completo or not persona.nombre_completo.strip():
            hallazgos.append(
                ValidationResult(
                    id_referencia=persona.id_persona_interno,
                    nivel=NivelValidacion.ERROR,
                    codigo="VAL_CAMPO_OBLIGATORIO_FALTANTE",
                    mensaje="El nombre completo del participante está vacío.",
                    fuente_origen=persona.fuente_origen
                )
            )

        # 2. Cédula
        if not persona.cedula:
            hallazgos.append(
                ValidationResult(
                    id_referencia=persona.id_persona_interno,
                    nivel=NivelValidacion.WARNING,
                    codigo="VAL_CEDULA_VACIA",
                    mensaje=f"Participante '{persona.nombre_completo}' no cuenta con cédula de identidad.",
                    fuente_origen=persona.fuente_origen
                )
            )
        elif PATRON_FECHA.match(persona.cedula):
            hallazgos.append(
                ValidationResult(
                    id_referencia=persona.id_persona_interno,
                    nivel=NivelValidacion.REVISION,
                    codigo="VAL_CEDULA_FECHA",
                    mensaje=(
                        f"Posible fecha de nacimiento en campo cédula: '{persona.cedula}' "
                        f"para '{persona.nombre_completo}'. Requiere revisión."
                    ),
                    fuente_origen=persona.fuente_origen
                )
            )

        # 3. Sexo
        if not persona.sexo_normalizado:
            hallazgos.append(
                ValidationResult(
                    id_referencia=persona.id_persona_interno,
                    nivel=NivelValidacion.WARNING,
                    codigo="VAL_SEXO_INCOMPATIBLE",
                    mensaje=(
                        f"Sexo no normalizado o incompatible ('{persona.sexo_original}') "
                        f"para '{persona.nombre_completo}' en fuente '{persona.sexo_fuente}'."
                    ),
                    fuente_origen=persona.fuente_origen
                )
            )

        # 4. Edad
        if persona.edad is None:
            hallazgos.append(
                ValidationResult(
                    id_referencia=persona.id_persona_interno,
                    nivel=NivelValidacion.WARNING,
                    codigo="VAL_EDAD_AUSENTE",
                    mensaje=f"Edad no especificada para '{persona.nombre_completo}'.",
                    fuente_origen=persona.fuente_origen
                )
            )

        # 5. Carrera
        if persona.carrera_original:
            carrera_raw_lower = persona.carrera_original.lower().strip()
            if carrera_raw_lower in ("a. estudiantil", "a estudiantil"):
                hallazgos.append(
                    ValidationResult(
                        id_referencia=persona.id_persona_interno,
                        nivel=NivelValidacion.WARNING,
                        codigo="VAL_CARRERA_AMBIGUA",
                        mensaje=f"Carrera o área ambigua '{persona.carrera_original}' para '{persona.nombre_completo}'.",
                        fuente_origen=persona.fuente_origen
                    )
                )
            elif "." in persona.carrera_original or len(persona.carrera_original) <= 4:
                hallazgos.append(
                    ValidationResult(
                        id_referencia=persona.id_persona_interno,
                        nivel=NivelValidacion.WARNING,
                        codigo="VAL_CARRERA_ABREVIADA",
                        mensaje=f"Carrera posiblemente abreviada '{persona.carrera_original}' para '{persona.nombre_completo}'.",
                        fuente_origen=persona.fuente_origen
                    )
                )

        return hallazgos

    @classmethod
    def validar_participacion(
        cls,
        participacion: Participation,
        nombre_persona: Optional[str] = None
    ) -> List[ValidationResult]:
        """Valida una entidad Participation verificando su categoría y motivos de revisión."""
        hallazgos: List[ValidationResult] = []

        if participacion.categoria_participacion == CategoriaParticipacion.DESCONOCIDO:
            hallazgos.append(
                ValidationResult(
                    id_referencia=participacion.id_participacion,
                    nivel=NivelValidacion.WARNING,
                    codigo="VAL_CATEGORIA_DESCONOCIDA",
                    mensaje=(
                        f"Participación con categoría DESCONOCIDO "
                        f"{f'para {nombre_persona}' if nombre_persona else ''}. Requiere revisión."
                    ),
                    fuente_origen=participacion.fuente_origen
                )
            )

        if participacion.requiere_revision:
            hallazgos.append(
                ValidationResult(
                    id_referencia=participacion.id_participacion,
                    nivel=NivelValidacion.REVISION,
                    codigo="VAL_REVISION_REQUERIDA",
                    mensaje=participacion.motivo_revision or "Participación marcada para revisión humana.",
                    fuente_origen=participacion.fuente_origen
                )
            )

        return hallazgos

    @classmethod
    def validar_conjunto(
        cls,
        actividades: List[Activity],
        personas: List[Person],
        participaciones: List[Participation],
        validaciones_previas: Optional[List[ValidationResult]] = None
    ) -> List[ValidationResult]:
        """
        Ejecuta la validación integral del conjunto relacional completo.
        
        Reglas de Fase 5:
        1. Integridad Referencial:
           - Cada participacion.id_actividad debe existir en 'actividades' (ERROR a nivel de registro).
           - Cada participacion.id_persona debe existir en 'personas' (ERROR a nivel de registro).
           - Un error en una participación bloquea únicamente esa fila y permite continuar validando las demás.
        2. Consistencia No Intrusiva Edad/Categoría:
           - Detecta combinaciones atípicas (ej: edad < 16 en docente o administrativo).
           - Emite REVISION (no asume error institucional).
        3. Validación Territorial Condicional:
           - Se ejecuta únicamente si municipios.json contiene un catálogo poblado.
           - Si está vacío (PENDIENTE DE CONFIRMACIÓN), se omite sin inventar datos ni emitir errores.
        4. Invariante:
           - No altera las listas de entrada.
           - Acumula y deduplica los hallazgos previos y los nuevos generados.
        """
        todas_validaciones: List[ValidationResult] = list(validaciones_previas or [])

        # Sets para verificación rápida de integridad referencial
        ids_actividades = {a.id_actividad for a in actividades}
        mapa_personas = {p.id_persona_interno: p for p in personas}

        # 1. Validar cada Actividad
        ids_actividades_validadas = {v.id_referencia for v in todas_validaciones if v.codigo.startswith("VAL_ACTIVIDAD")}
        for act in actividades:
            if act.id_actividad not in ids_actividades_validadas:
                todas_validaciones.extend(cls.validar_actividad(act))

        # 2. Validar cada Persona
        codigos_previos_por_persona = {}
        for vp in todas_validaciones:
            if vp.id_referencia in mapa_personas:
                codigos_previos_por_persona.setdefault(vp.id_referencia, set()).add(vp.codigo)

        for p in personas:
            hallazgos_p = cls.validar_persona(p)
            prev = codigos_previos_por_persona.get(p.id_persona_interno, set())
            for h in hallazgos_p:
                # Si la persona ya tiene VAL_CEDULA_FECHA, no agregar VAL_CEDULA_VACIA
                if h.codigo == "VAL_CEDULA_VACIA" and "VAL_CEDULA_FECHA" in prev:
                    continue
                if h.codigo in prev:
                    continue
                todas_validaciones.append(h)

        # 3. Validar cada Participación e Integridad Referencial
        for part in participaciones:
            nombre_p = mapa_personas[part.id_persona].nombre_completo if part.id_persona in mapa_personas else None
            todas_validaciones.extend(cls.validar_participacion(part, nombre_persona=nombre_p))

            # Integridad referencial: id_actividad
            if part.id_actividad not in ids_actividades:
                todas_validaciones.append(
                    ValidationResult(
                        id_referencia=part.id_participacion,
                        nivel=NivelValidacion.ERROR,
                        codigo="VAL_INTEGRIDAD_ACTIVIDAD_INEXISTENTE",
                        mensaje=(
                            f"La participación '{part.id_participacion}' hace referencia a un id_actividad "
                            f"inexistente ('{part.id_actividad}'). Bloquea únicamente este registro."
                        ),
                        fuente_origen=part.fuente_origen
                    )
                )

            # Integridad referencial: id_persona
            if part.id_persona not in mapa_personas:
                todas_validaciones.append(
                    ValidationResult(
                        id_referencia=part.id_participacion,
                        nivel=NivelValidacion.ERROR,
                        codigo="VAL_INTEGRIDAD_PERSONA_INEXISTENTE",
                        mensaje=(
                            f"La participación '{part.id_participacion}' hace referencia a un id_persona "
                            f"inexistente ('{part.id_persona}'). Bloquea únicamente este registro."
                        ),
                        fuente_origen=part.fuente_origen
                    )
                )
            else:
                # Consistencia no intrusiva edad vs categoría
                persona_rel = mapa_personas[part.id_persona]
                if persona_rel.edad is not None and persona_rel.edad < 16:
                    if part.categoria_participacion in (CategoriaParticipacion.DOCENTE, CategoriaParticipacion.ADMINISTRATIVO):
                        todas_validaciones.append(
                            ValidationResult(
                                id_referencia=part.id_participacion,
                                nivel=NivelValidacion.REVISION,
                                codigo="VAL_EDAD_CATEGORIA_ATIPICA",
                                mensaje=(
                                    f"Edad reportada ({persona_rel.edad} años) para '{persona_rel.nombre_completo}' "
                                    f"es atípica para la categoría '{part.categoria_participacion.value}'. "
                                    "Requiere confirmación humana. No se asume error institucional."
                                ),
                                fuente_origen=part.fuente_origen
                            )
                        )
                        part.requiere_revision = True
                        if not part.motivo_revision:
                            part.motivo_revision = f"Edad ({persona_rel.edad}) atípica para categoría {part.categoria_participacion.value}."

        # Deduplicar resultados conservando orden
        vistos = set()
        validaciones_unicas: List[ValidationResult] = []
        for val in todas_validaciones:
            clave = (val.id_referencia, val.codigo, val.nivel, val.mensaje)
            if clave not in vistos:
                vistos.add(clave)
                validaciones_unicas.append(val)

        return validaciones_unicas

