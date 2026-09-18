"""
app.matching.identity_resolver

Motor de resolución de identidad y deduplicación controlada de personas (Fase 4).
Reglas fundamentales e inviolables:
1. REGLA DE ORO E INVARIANTE ABSOLUTA:
   - participaciones_entrada == participaciones_salida en todo momento.
   - Cada participación conserva íntegros sus atributos originales (id_actividad,
     categoria_participacion, observaciones, etc.), actualizando exclusivamente
     el id_persona cuando corresponda a una fusión legítima.
2. JERARQUÍA ESTRICTA:
   - Nivel 1 (Cédula oficial válida): misma cédula -> fusión automática segura. Cédulas distintas -> personas distintas.
   - Nivel 2 (Número único institucional): mismo número -> fusión automática segura. Distintos -> personas distintas.
   - Nivel 3 (Otro ID institucional): NO autoriza fusión automática. Emite MATCH_NIVEL3_REVISION y conserva personas separadas.
   - Nivel 4 (Candidato por evidencia secundaria): NUNCA autoriza fusión automática. Emite MATCH_PERSONA_CANDIDATO y conserva personas separadas.
3. ENRIQUECIMIENTO SIN SOBRESCRITURA SILENCIOSA:
   - No asume 'el más largo' como verdad absoluta ni evidencia de identidad.
   - Solo enriquece cuando no hay conflicto (campo vacío).
   - Ante valores contradictorios, genera DEDUP_CONFLICTO_DATOS y conserva trazabilidad.
"""

from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field

from app.core.models.person import Person
from app.core.models.participation import Participation
from app.core.models.validation_result import ValidationResult
from app.core.constants.participant_types import NivelValidacion, NivelConfianzaIdentidad
from app.matching.person_matcher import (
    PersonMatcher,
    PersonComparisonResult,
    TipoCoincidenciaPersona
)
from app.audit.audit_logger import get_logger

logger = get_logger(__name__)


class FusionRecord(BaseModel):
    """Registro de trazabilidad y auditoría de una fusión de personas."""
    id_persona_canonico: str = Field(
        ...,
        description="ID interno de la persona consolidada final."
    )
    ids_personas_fusionadas: List[str] = Field(
        ...,
        description="IDs internos de todas las instancias de Person absorbidas en la fusión."
    )
    criterio_fusion: str = Field(
        ...,
        description="Justificación técnica de la fusión (ej: 'NIVEL_1_CEDULA: 601-120502-1001A')."
    )
    atributos_origen: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Mapeo de {id_persona: {campo: valor_original}} para auditoría completa."
    )
    conflictos_detectados: List[str] = Field(
        default_factory=list,
        description="Lista de contradicciones registradas entre los registros fusionados."
    )


class CandidatePair(BaseModel):
    """Registro de dos personas identificadas como posibles duplicadas para revisión humana."""
    id_persona_1: str
    id_persona_2: str
    nombre_1: str
    nombre_2: str
    motivo: str
    similitud: float = 0.0
    nivel_jerarquia: int = NivelConfianzaIdentidad.NIVEL_4_CANDIDATO.value


class IdentityResolutionResult(BaseModel):
    """Resultado completo del proceso de resolución de identidad y deduplicación."""
    personas: List[Person] = Field(
        ...,
        description="Lista consolidada de personas deduplicadas/únicas."
    )
    participaciones: List[Participation] = Field(
        ...,
        description="Lista completa de participaciones (conteo idéntico al de entrada)."
    )
    validaciones: List[ValidationResult] = Field(
        default_factory=list,
        description="Validaciones, advertencias e informaciones emitidas durante el proceso."
    )
    fusiones_realizadas: List[FusionRecord] = Field(
        default_factory=list,
        description="Trazabilidad detallada de todas las fusiones efectuadas."
    )
    candidatos_revision: List[CandidatePair] = Field(
        default_factory=list,
        description="Pares de personas que requieren revisión humana (Nivel 3 o Nivel 4)."
    )


class IdentityResolver:
    """
    Motor centralizado de resolución de identidad y deduplicación controlada.
    """

    @classmethod
    def _fusionar_entidades_persona(
        cls,
        personas_cluster: List[Person],
        criterio: str,
        validaciones: List[ValidationResult]
    ) -> Tuple[Person, FusionRecord]:
        """
        Fusiona dos o más registros de Person correspondientes a la misma persona física.
        Reglas de enriquecimiento:
        - Conserva el id_persona_interno del primer registro como canónico.
        - Enriquecimiento no destructivo: solo llena campos cuando el canónico tiene None.
        - Ante contradicciones sustantivas (ej: sexos distintos), emite DEDUP_CONFLICTO_DATOS
          y no sobreescribe silenciosamente.
        - Trazabilidad: guarda todos los valores originales en el FusionRecord.
        """
        canonico = personas_cluster[0].model_copy(deep=True)
        ids_fusionadas = [p.id_persona_interno for p in personas_cluster]
        atributos_origen: Dict[str, Dict[str, Any]] = {}
        conflictos_totales: List[str] = []

        for p in personas_cluster:
            atributos_origen[p.id_persona_interno] = {
                "nombre_completo": p.nombre_completo,
                "cedula": p.cedula,
                "numero_unico": p.numero_unico,
                "sexo_normalizado": p.sexo_normalizado,
                "sexo_original": p.sexo_original,
                "sexo_fuente": p.sexo_fuente,
                "edad": p.edad,
                "fecha_nacimiento": str(p.fecha_nacimiento) if p.fecha_nacimiento else None,
                "carrera_original": p.carrera_original,
                "carrera_normalizada": p.carrera_normalizada,
                "telefono": p.telefono,
                "etnia": p.etnia,
                "departamento_persona": p.departamento_persona,
                "municipio_persona": p.municipio_persona,
                "fuente_origen": p.fuente_origen
            }

        # Iterar sobre las demás personas del cluster para enriquecer sin sobrescritura destructiva
        for secundario in personas_cluster[1:]:
            # Detectar conflictos
            conflictos = PersonMatcher.detectar_conflictos_atributos(canonico, secundario)
            if conflictos:
                conflictos_totales.extend(conflictos)
                for conf in conflictos:
                    validaciones.append(
                        ValidationResult(
                            id_referencia=canonico.id_persona_interno,
                            nivel=NivelValidacion.WARNING,
                            codigo="DEDUP_CONFLICTO_DATOS",
                            mensaje=(
                                f"Conflicto de datos durante fusión ({criterio}) entre "
                                f"'{canonico.nombre_completo}' y '{secundario.nombre_completo}': {conf}."
                            ),
                            fuente_origen=canonico.fuente_origen
                        )
                    )

            # Nombre para presentación: si el secundario contiene el nombre canónico o es más completo
            # (ej: 'Johnny Melvin' frente a 'Johnny M'), se utiliza como forma de presentación consolidada,
            # pero la trazabilidad conserva ambos nombres en atributos_origen.
            if len(secundario.nombre_completo.strip()) > len(canonico.nombre_completo.strip()):
                sim = PersonMatcher.calcular_similitud_nombre(canonico.nombre_completo, secundario.nombre_completo)
                if sim >= 0.80:
                    canonico.nombre_completo = secundario.nombre_completo
                    if secundario.nombres and not canonico.nombres:
                        canonico.nombres = secundario.nombres
                    if secundario.apellidos and not canonico.apellidos:
                        canonico.apellidos = secundario.apellidos

            # Cédula
            if not canonico.cedula and secundario.cedula:
                canonico.cedula = secundario.cedula

            # Número único
            if not canonico.numero_unico and secundario.numero_unico:
                canonico.numero_unico = secundario.numero_unico

            # Otro ID institucional
            if not canonico.otro_id_institucional and secundario.otro_id_institucional:
                canonico.otro_id_institucional = secundario.otro_id_institucional

            # Sexo (solo enriquecer si canonico no tiene)
            if not canonico.sexo_normalizado and secundario.sexo_normalizado:
                canonico.sexo_normalizado = secundario.sexo_normalizado
                canonico.sexo_original = secundario.sexo_original
                canonico.sexo_fuente = secundario.sexo_fuente

            # Edad
            if canonico.edad is None and secundario.edad is not None:
                canonico.edad = secundario.edad

            # Fecha de nacimiento
            if not canonico.fecha_nacimiento and secundario.fecha_nacimiento:
                canonico.fecha_nacimiento = secundario.fecha_nacimiento

            # Carrera
            if not canonico.carrera_original and secundario.carrera_original:
                canonico.carrera_original = secundario.carrera_original
            if not canonico.carrera_normalizada and secundario.carrera_normalizada:
                canonico.carrera_normalizada = secundario.carrera_normalizada
            if not canonico.carrera_oficial and secundario.carrera_oficial:
                canonico.carrera_oficial = secundario.carrera_oficial

            # Teléfono
            if not canonico.telefono and secundario.telefono:
                canonico.telefono = secundario.telefono

            # Etnia
            if not canonico.etnia and secundario.etnia:
                canonico.etnia = secundario.etnia

            # Ubicación
            if not canonico.departamento_persona and secundario.departamento_persona:
                canonico.departamento_persona = secundario.departamento_persona
            if not canonico.municipio_persona and secundario.municipio_persona:
                canonico.municipio_persona = secundario.municipio_persona

            # Discapacidad
            if not canonico.discapacidad and secundario.discapacidad:
                canonico.discapacidad = secundario.discapacidad

        record = FusionRecord(
            id_persona_canonico=canonico.id_persona_interno,
            ids_personas_fusionadas=ids_fusionadas,
            criterio_fusion=criterio,
            atributos_origen=atributos_origen,
            conflictos_detectados=conflictos_totales
        )

        validaciones.append(
            ValidationResult(
                id_referencia=canonico.id_persona_interno,
                nivel=NivelValidacion.INFO,
                codigo="MATCH_PERSONA_FUSIONADA",
                mensaje=(
                    f"Fusión automática autorizada de {len(personas_cluster)} registros para "
                    f"'{canonico.nombre_completo}' bajo criterio {criterio}. "
                    f"IDs consolidados: {ids_fusionadas}. "
                    f"Todas sus participaciones se conservan independientes."
                ),
                fuente_origen=canonico.fuente_origen
            )
        )

        return canonico, record

    @classmethod
    def resolver_identidades(
        cls,
        personas: List[Person],
        participaciones: List[Participation]
    ) -> IdentityResolutionResult:
        """
        Ejecuta el pipeline completo de deduplicación controlada y resolución de identidad.
        
        Garantías inviolables:
        1. participaciones_entrada == participaciones_salida
        2. No altera atributos de participación excepto id_persona cuando corresponda a una fusión.
        3. Solo fusiona por Nivel 1 o Nivel 2 idéntico y válido.
        4. Nivel 3 y Nivel 4 se conservan como personas independientes y emiten REVISIÓN.
        """
        conteo_participaciones_inicial = len(participaciones)
        participaciones_copia = [p.model_copy(deep=True) for p in participaciones]
        personas_copia = [p.model_copy(deep=True) for p in personas]

        validaciones: List[ValidationResult] = []
        fusiones_realizadas: List[FusionRecord] = []
        candidatos_revision: List[CandidatePair] = []

        # ---------------------------------------------------------------------
        # PASO 1: Agrupación por identificadores duros autorizados para fusión
        # (Nivel 1: Cédula oficial válida, Nivel 2: Número único institucional)
        # ---------------------------------------------------------------------
        # Mapeo de id_persona_original -> id_persona_destino
        mapeo_reemplazo_id: Dict[str, str] = {}

        # 1.1 Agrupación por Nivel 1: Cédula oficial válida
        grupos_cedula: Dict[str, List[Person]] = {}
        personas_sin_cedula_valida: List[Person] = []

        for p in personas_copia:
            if PersonMatcher.es_cedula_valida(p.cedula):
                key = p.cedula.strip().upper()
                grupos_cedula.setdefault(key, []).append(p)
            else:
                personas_sin_cedula_valida.append(p)

        personas_nivel1_consolidadas: List[Person] = []
        for cedula_key, grupo in grupos_cedula.items():
            if len(grupo) > 1:
                # Fusión automática por Nivel 1
                criterio = f"NIVEL_1_CEDULA: {cedula_key}"
                canonico, record = cls._fusionar_entidades_persona(grupo, criterio, validaciones)
                personas_nivel1_consolidadas.append(canonico)
                fusiones_realizadas.append(record)
                for p_orig in grupo:
                    mapeo_reemplazo_id[p_orig.id_persona_interno] = canonico.id_persona_interno
            else:
                personas_nivel1_consolidadas.append(grupo[0])

        # 1.2 Agrupación por Nivel 2: Número único institucional
        grupos_numero_unico: Dict[str, List[Person]] = {}
        personas_restantes: List[Person] = []

        for p in personas_sin_cedula_valida:
            if PersonMatcher.es_numero_unico_valido(p.numero_unico):
                key = p.numero_unico.strip().upper()
                grupos_numero_unico.setdefault(key, []).append(p)
            else:
                personas_restantes.append(p)

        personas_nivel2_consolidadas: List[Person] = []
        for num_key, grupo in grupos_numero_unico.items():
            if len(grupo) > 1:
                # Fusión automática por Nivel 2
                criterio = f"NIVEL_2_NUMERO_UNICO: {num_key}"
                canonico, record = cls._fusionar_entidades_persona(grupo, criterio, validaciones)
                personas_nivel2_consolidadas.append(canonico)
                fusiones_realizadas.append(record)
                for p_orig in grupo:
                    mapeo_reemplazo_id[p_orig.id_persona_interno] = canonico.id_persona_interno
            else:
                personas_nivel2_consolidadas.append(grupo[0])

        # Personas resultantes tras fusiones autorizadas (Nivel 1 y Nivel 2)
        personas_activas: List[Person] = (
            personas_nivel1_consolidadas +
            personas_nivel2_consolidadas +
            personas_restantes
        )

        # ---------------------------------------------------------------------
        # PASO 2: Actualización legítima de id_persona en Participaciones
        # (Conservación íntegra de participaciones - Regla de Oro)
        # ---------------------------------------------------------------------
        for part in participaciones_copia:
            if part.id_persona in mapeo_reemplazo_id:
                part.id_persona = mapeo_reemplazo_id[part.id_persona]

        # ---------------------------------------------------------------------
        # PASO 3: Evaluación de Nivel 3 y Nivel 4 (Candidatos a revisión)
        # Entre las personas que quedaron separadas. NUNCA fusiona.
        # ---------------------------------------------------------------------
        n = len(personas_activas)
        ids_personas_con_alerta_revision: Set[str] = set()

        for i in range(n):
            for j in range(i + 1, n):
                p_a = personas_activas[i]
                p_b = personas_activas[j]

                resultado_comp = PersonMatcher.comparar_personas(p_a, p_b)

                if resultado_comp.tipo_coincidencia == TipoCoincidenciaPersona.CANDIDATO_REVISION:
                    # Incorporar validaciones emitidas
                    validaciones.extend(resultado_comp.validaciones)
                    motivo_cand = "; ".join(resultado_comp.evidencias)
                    candidatos_revision.append(
                        CandidatePair(
                            id_persona_1=p_a.id_persona_interno,
                            id_persona_2=p_b.id_persona_interno,
                            nombre_1=p_a.nombre_completo,
                            nombre_2=p_b.nombre_completo,
                            motivo=motivo_cand,
                            similitud=resultado_comp.similitud_nombre,
                            nivel_jerarquia=resultado_comp.nivel_jerarquia or 4
                        )
                    )
                    ids_personas_con_alerta_revision.add(p_a.id_persona_interno)
                    ids_personas_con_alerta_revision.add(p_b.id_persona_interno)

        # Marcar revisión en las participaciones asociadas a personas en revisión
        for part in participaciones_copia:
            if part.id_persona in ids_personas_con_alerta_revision:
                part.requiere_revision = True
                # Agregar motivo si no lo tenía
                if not part.motivo_revision:
                    part.motivo_revision = "Persona vinculada a posible coincidencia candidata (Nivel 3 o 4) pendiente de confirmación humana."

        # ---------------------------------------------------------------------
        # PASO 4: Verificación estricta de la Invariante Absoluta
        # ---------------------------------------------------------------------
        assert len(participaciones_copia) == conteo_participaciones_inicial, (
            f"VIOLACIÓN DE REGLA DE ORO: Las participaciones cambiaron de conteo! "
            f"Entraron {conteo_participaciones_inicial} y salieron {len(participaciones_copia)}."
        )

        for p_in, p_out in zip(participaciones, participaciones_copia):
            assert p_in.id_participacion == p_out.id_participacion
            assert p_in.id_actividad == p_out.id_actividad
            assert p_in.categoria_participacion == p_out.categoria_participacion
            assert p_in.observaciones == p_out.observaciones
            assert p_in.fuente_origen == p_out.fuente_origen

        logger.info(
            f"Resolución de identidad finalizada: "
            f"Personas iniciales={len(personas)}, Personas finales={len(personas_activas)}, "
            f"Participaciones={len(participaciones_copia)} (100% conservadas), "
            f"Fusiones realizadas={len(fusiones_realizadas)}, "
            f"Candidatos revisión={len(candidatos_revision)}."
        )

        return IdentityResolutionResult(
            personas=personas_activas,
            participaciones=participaciones_copia,
            validaciones=validaciones,
            fusiones_realizadas=fusiones_realizadas,
            candidatos_revision=candidatos_revision
        )
