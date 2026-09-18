"""Caso de uso CU-PAR-02: IngestarListaAsistenciaUseCase.

Orquesta la ingesta en lote de filas de asistencia externa vinculándolas a una actividad institucional.
Reglas institucionales y de diseño:
- Clean Architecture: La capa de aplicación actúa exclusivamente como orquestadora.
- DETECTAR ≠ CORREGIR: Toda inconsistencia o anomalía se detecta y registra; nunca se corrige
  silenciosamente ni se inventan cédulas ficticias.
- Cédula ausente (RN-C04): La ausencia de cédula no implica duplicidad; la persona se registra
  legítimamente con cedula = None.
- POSIBLE_DUPLICADO: Se reserva para cuando exista evidencia suficiente de coincidencia (nombre
  idéntico/similar y contexto coincidente) pero falta cédula oficial para confirmar con certeza.
- IDENTIDAD_NO_RESUELTA: Cuando la información nominal es insuficiente o genérica.
- Participaciones repetidas: Si la persona ya participó en la actividad, se registra la evidencia,
  se marca para revisión humana y se asienta una discrepancia; no se descarta ni elimina.
- Neutralidad de routing: matriz_destino permanece en None (sin enrutamiento prematuro a M2..M5).
- Transaccionalidad: Coordinada vía IUnitOfWork garantizando commit atómico o rollback integral.
"""

from typing import Dict, List, Optional

from app.application.commands.participacion_commands import (
    IngestarListaAsistenciaCommand,
)
from app.application.dto.output_dtos import IngestaListaAsistenciaResultDTO
from app.core.constants.participant_types import (
    CategoriaParticipacion,
    NivelConfianzaIdentidad,
    NivelValidacion,
)
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.models.discrepancy import (
    Discrepancia,
    EstadoDiscrepancia,
    SeveridadDiscrepancia,
    TipoDiscrepancia,
)
from app.core.models.participation import Participation
from app.core.models.person import Person
from app.core.models.validation_result import ValidationResult
from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.unit_of_work import IUnitOfWork
from app.matching.person_matcher import PersonMatcher, TipoCoincidenciaPersona
from app.normalization.identifier_normalizer import IdentifierNormalizer


class IngestarListaAsistenciaUseCase:
    """Caso de uso para orquestar la ingesta masiva de listas de asistencia."""

    def __init__(
        self,
        actividad_repo: Optional[IActividadRepository] = None,
        persona_repo: Optional[IPersonaRepository] = None,
        participacion_repo: Optional[IParticipacionRepository] = None,
        discrepancia_repo: Optional[IDiscrepanciaRepository] = None,
        uow: Optional[IUnitOfWork] = None,
    ) -> None:
        """Inicializa el caso de uso con sus puertos de persistencia requeridos.

        Args:
            actividad_repo: Puerto para validar la existencia de la actividad anfitriona.
            persona_repo: Puerto para consultar y registrar personas en el SSOT.
            participacion_repo: Puerto para persistir las asistencias/participaciones.
            discrepancia_repo: Puerto opcional para registrar discrepancias detectadas.
            uow: Puerto opcional de Unit of Work para coordinar transacciones atómicas.
        """
        self._actividad_repo = actividad_repo
        self._persona_repo = persona_repo
        self._participacion_repo = participacion_repo
        self._discrepancia_repo = discrepancia_repo
        self._uow = uow

    def execute(
        self,
        command: IngestarListaAsistenciaCommand,
        uow: Optional[IUnitOfWork] = None,
    ) -> IngestaListaAsistenciaResultDTO:
        """Ejecuta la ingesta masiva de participantes aplicando las reglas de dominio.

        Args:
            command: Comando con el ID de actividad, nombre de archivo y filas crudas.
            uow: Instancia opcional de IUnitOfWork si se invoca dentro de un contexto transaccional.

        Returns:
            IngestaListaAsistenciaResultDTO con el consolidado y hallazgos del lote.

        Raises:
            EntityNotFoundError: Si la actividad receptora no existe en el repositorio.
        """
        active_uow = uow or self._uow

        # Si se suministra un UoW
        if active_uow is not None:
            # Si ya se encuentra dentro de un bloque 'with' (transacción activa externa)
            if getattr(active_uow, "_in_transaction", False):
                return self._execute_core(
                    command=command,
                    act_repo=active_uow.actividades,
                    per_repo=active_uow.personas,
                    part_repo=active_uow.participaciones,
                    disc_repo=active_uow.discrepancias,
                )

            # Si no está activo el contexto transaccional, abrirlo y confirmar al finalizar
            with active_uow:
                result = self._execute_core(
                    command=command,
                    act_repo=active_uow.actividades,
                    per_repo=active_uow.personas,
                    part_repo=active_uow.participaciones,
                    disc_repo=active_uow.discrepancias,
                )
                active_uow.commit()
            return result

        if (
            self._actividad_repo is None
            or self._persona_repo is None
            or self._participacion_repo is None
        ):
            raise ValueError(
                "Debe proporcionarse una instancia de IUnitOfWork o los repositorios requeridos."
            )

        # Ejecución directa contra los repositorios inyectados
        return self._execute_core(
            command=command,
            act_repo=self._actividad_repo,
            per_repo=self._persona_repo,
            part_repo=self._participacion_repo,
            disc_repo=self._discrepancia_repo,
        )

    def _execute_core(
        self,
        command: IngestarListaAsistenciaCommand,
        act_repo: IActividadRepository,
        per_repo: IPersonaRepository,
        part_repo: IParticipacionRepository,
        disc_repo: Optional[IDiscrepanciaRepository],
    ) -> IngestaListaAsistenciaResultDTO:
        """Lógica central de orquestación de la lista de asistencia."""
        # 1. Precondición vital: La actividad debe existir en la base de datos
        if not act_repo.exists(command.id_actividad):
            raise EntityNotFoundError("Actividad", command.id_actividad)

        total_procesados = 0
        nuevas_personas_registradas = 0
        personas_existentes_vinculadas = 0
        participaciones_creadas = 0
        participaciones_en_revision = 0
        hallazgos_validacion: List[ValidationResult] = []

        # Rastrear participaciones ya registradas en la actividad (id_persona -> id_participacion)
        participaciones_en_actividad: Dict[str, str] = {}
        for p_existente in part_repo.get_by_actividad(command.id_actividad):
            participaciones_en_actividad[p_existente.id_persona] = (
                p_existente.id_participacion
            )

        # 2. Iterar las filas del documento externo
        for fila in command.filas_participantes:
            total_procesados += 1
            nombre_crudo = fila.nombre_fuente.strip() if fila.nombre_fuente else ""

            # 2.1 ERROR DE DATOS: Nombre vacío o ausente
            if not nombre_crudo:
                hallazgos_validacion.append(
                    ValidationResult(
                        id_referencia=command.id_actividad,
                        nivel=NivelValidacion.ERROR,
                        codigo="VAL_NOMBRE_VACIO",
                        mensaje=f"Fila {total_procesados}: Nombre del participante vacío o ausente.",
                        fuente_origen=command.fuente_archivo,
                    )
                )
                continue  # Renglón rechazado: no se persiste, pero no detiene las demás filas

            # 2.2 Normalización de Cédula y Detección de Anomalías (DETECTAR ≠ CORREGIR)
            cedula_norm, val_cedula = IdentifierNormalizer.normalizar_cedula(
                fila.cedula_fuente,
                fuente=command.fuente_archivo,
            )

            inconsistencia_cedula = False
            if val_cedula is not None:
                hallazgos_validacion.append(val_cedula)
                if val_cedula.codigo in (
                    "VAL_CEDULA_FECHA",
                    "VAL_CEDULA_FORMATO_DUDOSO",
                ):
                    inconsistencia_cedula = True

            # 2.3 Búsqueda de coincidencia exacta por identificador primario
            persona: Optional[Person] = None
            posible_duplicado = False
            candidato_duplicado_id: Optional[str] = None
            identidad_no_resuelta = False

            if cedula_norm:
                persona = per_repo.get_by_cedula(cedula_norm)
            elif (
                fila.numero_institucional_fuente
                and fila.numero_institucional_fuente.strip()
            ):
                persona = per_repo.get_by_numero_institucional(
                    fila.numero_institucional_fuente.strip()
                )

            # 2.4 Si no hubo coincidencia por cédula/carné, evaluar candidatos o nueva persona
            if persona is not None:
                personas_existentes_vinculadas += 1
            else:
                # Evaluar si la información nominal es insuficiente (IDENTIDAD_NO_RESUELTA)
                tokens = nombre_crudo.split()
                if len(tokens) <= 1 or nombre_crudo.upper() in (
                    "ESTUDIANTE",
                    "PARTICIPANTE",
                    "DOCENTE",
                    "ANONIMO",
                    "INVITADO",
                ):
                    identidad_no_resuelta = True

                # Búsqueda de posibles duplicados candidatos en el repositorio
                if not identidad_no_resuelta:
                    candidatos = per_repo.search_by_nombre(nombre_crudo)
                    for cand in candidatos:
                        comp = PersonMatcher.comparar_personas(
                            Person(
                                nombre_completo=nombre_crudo,
                                fuente_origen=command.fuente_archivo,
                            ),
                            cand,
                        )
                        if comp.tipo_coincidencia in (
                            TipoCoincidenciaPersona.CANDIDATO_REVISION,
                            TipoCoincidenciaPersona.FUSION_AUTOMATICA,
                        ):
                            posible_duplicado = True
                            candidato_duplicado_id = cand.id_persona_interno
                            break

                # Crear la nueva entidad Person en el SSOT
                # Regla RN-C04: Si no posee cédula válida, permanece estrictamente en None
                persona = Person(
                    nombre_completo=nombre_crudo,
                    cedula=cedula_norm,  # None si no tiene o si hubo anomalía (ej. fecha)
                    numero_unico=(
                        fila.numero_institucional_fuente.strip()
                        if fila.numero_institucional_fuente
                        else None
                    ),
                    sexo_original=fila.sexo_fuente,
                    sexo_fuente=command.fuente_archivo,
                    carrera_original=fila.carrera_cargo_fuente,
                    etnia=fila.etnia_fuente,
                    fuente_origen=command.fuente_archivo,
                )
                per_repo.save(persona)
                nuevas_personas_registradas += 1

            # 2.5 Determinar nivel de confianza y condiciones de revisión
            requiere_revision = False
            motivos_revision: List[str] = []

            if inconsistencia_cedula:
                requiere_revision = True
                if val_cedula:
                    motivos_revision.append(val_cedula.mensaje)
                # Registrar discrepancia pericial preservando el valor original crudo de fuente
                if disc_repo is not None:
                    disc_cedula = Discrepancia(
                        id_actividad=command.id_actividad,
                        tipo_discrepancia=TipoDiscrepancia.OTRO,
                        severidad=SeveridadDiscrepancia.WARNING,
                        fuente_a_nombre=f"fila_{total_procesados}.cedula_fuente",
                        fuente_a_valor=str(fila.cedula_fuente),
                        fuente_b_nombre="persona.cedula",
                        fuente_b_valor="None (formato incompatible)",
                        delta_valor=(
                            val_cedula.mensaje
                            if val_cedula
                            else "Inconsistencia de cédula en fuente"
                        ),
                        estado=EstadoDiscrepancia.REQUIERE_REVISION,
                    )
                    disc_repo.save(disc_cedula)

            if identidad_no_resuelta:
                requiere_revision = True
                motivos_revision.append(
                    "Identidad no resuelta: información nominal insuficiente sin identificadores secundarios."
                )

            if posible_duplicado:
                requiere_revision = True
                motivos_revision.append(
                    f"Posible duplicado con persona existente (ID: {candidato_duplicado_id}) por coincidencia de nombre y contexto."
                )
                if disc_repo is not None:
                    disc_dup = Discrepancia(
                        id_actividad=command.id_actividad,
                        tipo_discrepancia=TipoDiscrepancia.OTRO,
                        severidad=SeveridadDiscrepancia.WARNING,
                        fuente_a_nombre=f"fila_{total_procesados}.nombre_fuente",
                        fuente_a_valor=nombre_crudo,
                        fuente_b_nombre="persona_existente.id_persona_interno",
                        fuente_b_valor=str(candidato_duplicado_id),
                        delta_valor="Posible duplicado detectado por coincidencia nominal sin cédula.",
                        estado=EstadoDiscrepancia.REQUIERE_REVISION,
                    )
                    disc_repo.save(disc_dup)

            # 2.6 PARTICIPACIONES REPETIDAS (DETECTAR ≠ CORREGIR / OPCIÓN A)
            # Evaluar si la persona ya cuenta con una asistencia en esta actividad
            id_per = persona.id_persona_interno
            es_participacion_repetida = id_per in participaciones_en_actividad

            if es_participacion_repetida:
                id_part_existente = participaciones_en_actividad[id_per]
                part_existente = part_repo.get_by_id(id_part_existente)
                if part_existente is None:
                    part_existente = part_repo.get_by_actividad_and_persona(
                        command.id_actividad, id_per
                    )

                motivo_rep = (
                    f"Participación repetida detectada en la misma actividad (fila {total_procesados} en '{command.fuente_archivo}')."
                )

                if part_existente is not None:
                    # Si no estaba marcada previamente en revisión, marcarla e incrementar contador
                    if not part_existente.requiere_revision:
                        part_existente.requiere_revision = True
                        participaciones_en_revision += 1

                    # Concatenar motivo de repetición sin borrar motivos previos
                    if part_existente.motivo_revision:
                        if motivo_rep not in part_existente.motivo_revision:
                            part_existente.motivo_revision = (
                                f"{part_existente.motivo_revision} | {motivo_rep}"
                            )
                    else:
                        part_existente.motivo_revision = motivo_rep

                    # Conservar evidencia en observaciones sin borrar anteriores
                    obs_extra_parts = [
                        f"[Aparición repetida: fila {total_procesados} en '{command.fuente_archivo}']"
                    ]
                    if fila.observaciones_fuente:
                        obs_extra_parts.append(f"Obs fila: '{fila.observaciones_fuente}'")
                    if inconsistencia_cedula and fila.cedula_fuente:
                        obs_extra_parts.append(
                            f"[Cédula anómala en fuente: '{fila.cedula_fuente}']"
                        )
                    obs_extra = " - ".join(obs_extra_parts)

                    if part_existente.observaciones:
                        if obs_extra not in part_existente.observaciones:
                            part_existente.observaciones = (
                                f"{part_existente.observaciones}; {obs_extra}"
                            )
                    else:
                        part_existente.observaciones = obs_extra

                    # Guardar la participación existente enriquecida (UPSERT en SQLite / in-place en InMemory)
                    part_repo.save(part_existente)

                # Registrar Discrepancia formal con evidencia de fuente
                if disc_repo is not None:
                    disc_rep = Discrepancia(
                        id_actividad=command.id_actividad,
                        tipo_discrepancia=TipoDiscrepancia.OTRO,
                        severidad=SeveridadDiscrepancia.WARNING,
                        fuente_a_nombre=f"fila_{total_procesados}.asistencia",
                        fuente_a_valor=f"Persona: {persona.nombre_completo} (ID: {id_per})",
                        fuente_b_nombre="participacion_previa.id_participacion",
                        fuente_b_valor=id_part_existente,
                        delta_valor=motivo_rep,
                        estado=EstadoDiscrepancia.REQUIERE_REVISION,
                    )
                    disc_repo.save(disc_rep)

                # Registrar hallazgo en el resultado del lote
                hallazgos_validacion.append(
                    ValidationResult(
                        id_referencia=command.id_actividad,
                        nivel=NivelValidacion.WARNING,
                        codigo="VAL_PARTICIPACION_REPETIDA",
                        mensaje=motivo_rep,
                        fuente_origen=command.fuente_archivo,
                    )
                )

                # La segunda aparición NO crea una nueva participación física (Opción A / UNIQUE)
                continue

            # 2.7 Construcción y persistencia de la entidad Participation
            # Preservar evidencia de la cédula cruda en observaciones si hubo anomalía
            observaciones_list = []
            if fila.observaciones_fuente:
                observaciones_list.append(fila.observaciones_fuente)
            if inconsistencia_cedula and fila.cedula_fuente:
                observaciones_list.append(
                    f"[Cédula original en fuente: '{fila.cedula_fuente}']"
                )

            observaciones_final = (
                "; ".join(observaciones_list) if observaciones_list else None
            )

            # Nivel de certeza de identidad según jerarquía
            if cedula_norm:
                nivel_confianza = NivelConfianzaIdentidad.NIVEL_1_CEDULA.value
            elif persona.numero_unico:
                nivel_confianza = NivelConfianzaIdentidad.NIVEL_2_NUMERO_UNICO.value
            else:
                nivel_confianza = NivelConfianzaIdentidad.NIVEL_4_CANDIDATO.value

            categoria = (
                fila.categoria_sugerida.strip().upper()
                if fila.categoria_sugerida
                else CategoriaParticipacion.DESCONOCIDO.value
            )

            participacion = Participation(
                id_actividad=command.id_actividad,
                id_persona=persona.id_persona_interno,
                categoria_participacion=categoria,
                nivel_confianza_identidad=nivel_confianza,
                fuente_origen=command.fuente_archivo,
                observaciones=observaciones_final,
                requiere_revision=requiere_revision,
                motivo_revision=(
                    " | ".join(motivos_revision) if motivos_revision else None
                ),
            )

            # Persistir la participación
            part_repo.save(participacion)
            participaciones_creadas += 1

            if requiere_revision:
                participaciones_en_revision += 1

            # Registrar la participación para detectar repeticiones dentro del mismo lote
            if id_per not in participaciones_en_actividad:
                participaciones_en_actividad[id_per] = participacion.id_participacion

        # 3. Construcción del resultado consolidado
        return IngestaListaAsistenciaResultDTO(
            id_actividad=command.id_actividad,
            total_procesados=total_procesados,
            nuevas_personas_registradas=nuevas_personas_registradas,
            personas_existentes_vinculadas=personas_existentes_vinculadas,
            participaciones_creadas=participaciones_creadas,
            participaciones_en_revision=participaciones_en_revision,
            hallazgos_validacion=hallazgos_validacion,
        )
