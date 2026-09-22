"""
Servicios de Aplicación — Módulo de Planificación y Diseño Metodológico.

Fase 29.5.4 — Integración Controlada Planning V003 → Document Model → DOCX.
Orquesta el flujo técnico entre los puertos de persistencia (repositorios),
el modelo de dominio puro, la transformación a DTO y el puerto de renderizado DOCX.

REGLAS DE AISLAMIENTO:
  - Cero dependencias hacia SQLite o infraestructura concreta (inversión de dependencias).
  - Cero dependencias hacia app.word_consolidator (núcleo protegido).
  - Cero dependencias hacia servicios de IA.
  - Único camino central de exportación: export_design().
"""
from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any, Optional
import uuid

from app.planning.domain.ai_context_builder import AIContextBuilder
from app.planning.domain.dtos import (
    AcceptAIProposalCommand,
    AIProposalDTO,
    FAQTableDTO,
    MethodologicalDesignDTO,
    OperationalActivityDTO,
    PlannedActivityDetailDTO,
    PlannedActivitySummaryDTO,
    PlanningIngestionReportDTO,
    RejectAIProposalCommand,
    RequestAIProposalCommand,
    TimeBlockDTO,
    UpdateMethodologicalDesignCommand,
    ValidationReportDTO,
    ValidationResultDTO,
)
from app.planning.domain.entities import MethodologicalDesign, PlannedActivity
from app.planning.domain.ports import (
    AIAssistancePort,
    MethodologicalDesignRepositoryPort,
    MethodologicalDocumentRendererPort,
    PlanningSourceReaderPort,
    PlanningUnitOfWorkPort,
)
from app.planning.domain.validator import MethodologicalDesignValidator
from app.planning.domain.value_objects import (
    AI_ALLOWED_TARGET_FIELDS,
    AIProposal,
    DesignStatus,
    FAQTable,
    OperationalActivity,
    ParticipantGoals,
    TimeBlock,
)


class MethodologicalDocumentExportService:
    """Servicio de aplicación para exportar Diseños Metodológicos a documentos DOCX.

    Mantiene un único camino central de exportación:
      export_by_id()             ──┐
                                   ├──> export_design() ──> design.to_dto() ──> renderer.render()
      export_by_activity_ref()   ──┘
    """

    def __init__(
        self,
        design_repository: MethodologicalDesignRepositoryPort,
        renderer: MethodologicalDocumentRendererPort,
    ) -> None:
        """Inicializa el servicio inyectando los puertos requeridos.

        Args:
            design_repository: Puerto de acceso a datos para consultar diseños.
            renderer: Puerto para renderizar el DTO en un documento físico.
        """
        self._design_repo = design_repository
        self._renderer = renderer

    def export_design(
        self,
        design: MethodologicalDesign,
        output_path: str,
        objectives_heading: str = "OBJETIVOS DEL TALLER ARTÍSTICO",
        program_section_label: str = "III. PROGRAMA",
        matrix_section_label: str = "VI. MATRIZ DE PLANIFICACIÓN",
    ) -> str:
        """Camino central único: transforma el agregado a DTO y delega al renderer.

        Args:
            design: Agregado de dominio MethodologicalDesign.
            output_path: Ruta de destino en el sistema de archivos.
            objectives_heading: Encabezado del bloque de objetivos.
            program_section_label: Encabezado de la tabla de programa/agenda.
            matrix_section_label: Encabezado de la matriz operativa.

        Returns:
            Ruta canónica del archivo DOCX generado.

        Raises:
            ValueError: Si design es nulo.
            DocumentRenderingError: Si ocurre un error durante el renderizado.
        """
        if design is None:
            raise ValueError("El diseño metodológico a exportar no puede ser nulo.")

        dto = design.to_dto(
            objectives_heading=objectives_heading,
            program_section_label=program_section_label,
            matrix_section_label=matrix_section_label,
        )
        return self._renderer.render(dto, output_path)

    def export_by_id(
        self,
        design_id: uuid.UUID,
        output_path: str,
        objectives_heading: str = "OBJETIVOS DEL TALLER ARTÍSTICO",
        program_section_label: str = "III. PROGRAMA",
        matrix_section_label: str = "VI. MATRIZ DE PLANIFICACIÓN",
    ) -> str:
        """Recupera el diseño por su UUID y delega a export_design()."""
        design = self._design_repo.get_by_id(design_id)
        if design is None:
            raise ValueError(f"No se encontró diseño metodológico con ID '{design_id}'.")

        return self.export_design(
            design=design,
            output_path=output_path,
            objectives_heading=objectives_heading,
            program_section_label=program_section_label,
            matrix_section_label=matrix_section_label,
        )

    def export_by_activity_ref(
        self,
        planned_activity_ref: str,
        output_path: str,
        objectives_heading: str = "OBJETIVOS DEL TALLER ARTÍSTICO",
        program_section_label: str = "III. PROGRAMA",
        matrix_section_label: str = "VI. MATRIZ DE PLANIFICACIÓN",
    ) -> str:
        """Recupera el diseño por la referencia institucional de la actividad y delega a export_design()."""
        design = self._design_repo.get_by_activity_ref(planned_activity_ref)
        if design is None:
            raise ValueError(
                f"No se encontró diseño metodológico para la actividad planificada con referencia '{planned_activity_ref}'."
            )

        return self.export_design(
            design=design,
            output_path=output_path,
            objectives_heading=objectives_heading,
            program_section_label=program_section_label,
            matrix_section_label=matrix_section_label,
        )


def _parse_date_safely(raw: Optional[str]) -> tuple[Optional[date], Optional[str]]:
    """Intenta parsear una fecha en formato ISO (YYYY-MM-DD) o estándar (DD/MM/YYYY)."""
    if not raw or not raw.strip():
        return None, None
    s = raw.strip()
    # ISO
    try:
        return date.fromisoformat(s), None
    except ValueError:
        pass
    # DD/MM/YYYY
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date(), None
        except ValueError:
            pass
    return None, f"No se pudo convertir '{raw}' a un formato de fecha válido (ISO YYYY-MM-DD o DD/MM/YYYY)."


class PlannedActivityIngestionService:
    """Servicio de aplicación para la ingestión de actividades del POA en Planning V003.

    Fase 29.7 — Implementación Controlada del Planning Reader Institucional.
    Orquesta:
      - Lectura técnica de la fuente externa mediante PlanningSourceReaderPort.
      - Validación de obligatoriedad de datos institucionales.
      - Normalización determinista y construcción del agregado PlannedActivity.
      - Idempotencia y resolución de duplicados conforme a la regla R-08.
      - Persistencia atómica mediante PlanningUnitOfWorkPort.
      - Emisión de PlanningIngestionReportDTO con trazabilidad pericial.
    """

    def __init__(
        self,
        reader: PlanningSourceReaderPort,
        uow: PlanningUnitOfWorkPort,
    ) -> None:
        """Inicializa el servicio inyectando las dependencias abstractas requeridas.

        Args:
            reader: Puerto para leer el archivo Excel institucional.
            uow: Unidad de trabajo satélite para persistencia transaccional atómica.
        """
        self._reader = reader
        self._uow = uow

    def ingest_planning_source(
        self,
        file_path: str,
        sheet_name: Optional[str] = None,
        default_area_responsable: Optional[str] = None,
        default_eje_estrategia: Optional[str] = None,
        default_programa: Optional[str] = None,
        default_tipo_evento: Optional[str] = None,
    ) -> PlanningIngestionReportDTO:
        """Lee e ingiere actividades desde una matriz POA institucional hacia SQLite V003.

        Args:
            file_path: Ruta al archivo Excel institucional.
            sheet_name: Nombre de hoja específico (opcional).
            default_area_responsable: Valor por defecto si la celda está vacía en el Excel.
            default_eje_estrategia: Valor por defecto para eje si está ausente en la hoja.
            default_programa: Valor por defecto para programa si está ausente.
            default_tipo_evento: Valor por defecto para tipo de evento si está ausente.

        Returns:
            PlanningIngestionReportDTO con métricas y detalle de la operación.
        """
        read_result = self._reader.read_planning_source(file_path=file_path, sheet_name=sheet_name)

        if read_result.structural_errors:
            return PlanningIngestionReportDTO(
                source_file=file_path,
                sheet_name=read_result.sheet_name,
                total_rows_examined=0,
                rows_accepted=0,
                rows_rejected=0,
                errors=read_result.structural_errors,
                warnings=read_result.reading_warnings,
            )

        accepted_count = 0
        rejected_count = 0
        created_ids: list[str] = []
        updated_ids: list[str] = []
        duplicates: list[str] = []
        warnings: list[str] = list(read_result.reading_warnings)
        errors: list[str] = []
        rejections: list[tuple[int, str]] = []

        with self._uow:
            for act_dto in read_result.activities:
                r = act_dto.row_number

                # Incorporar advertencias de lectura a nivel de fila
                for rw in act_dto.reading_warnings:
                    warnings.append(f"Fila {r}: {rw}")

                # Extraer campos aplicando defaults si la celda es nula
                act_name = (act_dto.activity_name or "").strip()
                sede = (act_dto.sede or "").strip()
                area_resp = (act_dto.area_responsable or default_area_responsable or "").strip()
                eje = (act_dto.eje_estrategia or default_eje_estrategia or "").strip()
                prog = (act_dto.programa or default_programa or "").strip()
                evento = (act_dto.tipo_evento or default_tipo_evento or "").strip()

                # Comprobación de campos obligatorios (Evidencia Directa PlannedActivity)
                missing: list[str] = []
                if not act_name:
                    missing.append("Actividad")
                if not sede:
                    missing.append("Sede")
                if not area_resp:
                    missing.append("Área_responsable")
                if not eje:
                    missing.append("Eje_estrategia")
                if not prog:
                    missing.append("Programa")
                if not evento:
                    missing.append("Tipo_Evento/Evento")

                if missing:
                    rejections.append((r, f"Fila {r}: Error de dato obligatorio — Faltan campos: {', '.join(missing)}"))
                    rejected_count += 1
                    continue

                # Parseo de fecha
                fecha_val, date_warn = _parse_date_safely(act_dto.fecha_evento)
                if date_warn:
                    warnings.append(f"Fila {r}: {date_warn}")

                # Construcción y validación de metas de participantes
                negative_goals = []
                for g_name, g_val in [
                    ("est_grado_m", act_dto.est_grado_m),
                    ("est_grado_f", act_dto.est_grado_f),
                    ("est_postgrado_m", act_dto.est_postgrado_m),
                    ("est_postgrado_f", act_dto.est_postgrado_f),
                    ("docentes_m", act_dto.docentes_m),
                    ("docentes_f", act_dto.docentes_f),
                    ("administrativos_m", act_dto.administrativos_m),
                    ("administrativos_f", act_dto.administrativos_f),
                    ("externos_m", act_dto.externos_m),
                    ("externos_f", act_dto.externos_f),
                ]:
                    if g_val is not None and g_val < 0:
                        negative_goals.append(f"{g_name}={g_val}")

                if negative_goals:
                    rejections.append(
                        (r, f"Fila {r}: Error de dato — Metas numéricas no pueden ser negativas: {', '.join(negative_goals)}")
                    )
                    rejected_count += 1
                    continue

                goals = ParticipantGoals(
                    est_grado_m=act_dto.est_grado_m or 0,
                    est_grado_f=act_dto.est_grado_f or 0,
                    est_postgrado_m=act_dto.est_postgrado_m or 0,
                    est_postgrado_f=act_dto.est_postgrado_f or 0,
                    docentes_m=act_dto.docentes_m or 0,
                    docentes_f=act_dto.docentes_f or 0,
                    administrativos_m=act_dto.administrativos_m or 0,
                    administrativos_f=act_dto.administrativos_f or 0,
                    externos_m=act_dto.externos_m or 0,
                    externos_f=act_dto.externos_f or 0,
                )

                # Determinación del planning_id institucional
                if act_dto.planning_id and act_dto.planning_id.strip():
                    pid = act_dto.planning_id.strip()
                elif act_dto.raw_no and act_dto.raw_no.strip():
                    pid = f"POA-{sede}-{act_dto.raw_no.strip()}"
                elif act_dto.codigo_presupuestario and act_dto.codigo_presupuestario.strip():
                    pid = f"POA-{sede}-{act_dto.codigo_presupuestario.strip()}"
                else:
                    clean_slug = re.sub(r"[^a-zA-Z0-9]+", "_", act_name).strip("_")[:24]
                    pid = f"POA-{sede}-{clean_slug}"

                # Idempotencia / Gestión de duplicados
                existing = self._uow.planned_activities.get_by_planning_id(pid)
                if existing is not None:
                    # Verificar si existe diseño asociado en estado APPROVED (R-08)
                    designs = self._uow.methodological_designs.get_by_activity_id(existing.activity_internal_id)
                    has_approved_design = any(d.status == DesignStatus.APPROVED for d in designs)

                    if has_approved_design:
                        duplicates.append(
                            f"Fila {r}: Actividad con planning_id '{pid}' ya existe con diseño metodológico APPROVED "
                            "(inmutable R-08); se conserva la versión existente sin modificaciones."
                        )
                        accepted_count += 1
                        continue

                    # Actualización in-place (D-02)
                    updated_activity = PlannedActivity(
                        activity_internal_id=existing.activity_internal_id,
                        planning_id=pid,
                        activity_name=act_name,
                        sede=sede,
                        dep_sede=act_dto.dep_sede or "",
                        mun_sede=act_dto.mun_sede or "",
                        programa=prog,
                        otro_programa=act_dto.otro_programa,
                        proyecto=act_dto.proyecto,
                        tipo_proyecto=act_dto.tipo_proyecto,
                        ambito=act_dto.ambito,
                        eje_estrategia=eje,
                        codigo_presupuestario=act_dto.codigo_presupuestario,
                        area_responsable=area_resp,
                        departamento_responsable=act_dto.departamento_responsable,
                        tipo_evento=evento,
                        proposito=act_dto.proposito,
                        fecha_evento=fecha_val,
                        convenio=act_dto.convenio,
                        entidades_cooperantes=act_dto.entidades_cooperantes,
                        participant_goals=goals,
                    )
                    self._uow.planned_activities.save(updated_activity)
                    updated_ids.append(pid)
                    duplicates.append(f"Fila {r}: Actividad con planning_id '{pid}' ya existía; actualizada in-place.")
                    accepted_count += 1
                else:
                    # Inserción inicial
                    new_activity = PlannedActivity.create(
                        planning_id=pid,
                        activity_name=act_name,
                        sede=sede,
                        area_responsable=area_resp,
                        eje_estrategia=eje,
                        programa=prog,
                        tipo_evento=evento,
                        participant_goals=goals,
                        dep_sede=act_dto.dep_sede or "",
                        mun_sede=act_dto.mun_sede or "",
                        otro_programa=act_dto.otro_programa,
                        proyecto=act_dto.proyecto,
                        tipo_proyecto=act_dto.tipo_proyecto,
                        ambito=act_dto.ambito,
                        codigo_presupuestario=act_dto.codigo_presupuestario,
                        departamento_responsable=act_dto.departamento_responsable,
                        proposito=act_dto.proposito,
                        fecha_evento=fecha_val,
                        convenio=act_dto.convenio,
                        entidades_cooperantes=act_dto.entidades_cooperantes,
                    )
                    self._uow.planned_activities.save(new_activity)
                    created_ids.append(pid)
                    accepted_count += 1

            self._uow.commit()

        return PlanningIngestionReportDTO(
            source_file=file_path,
            sheet_name=read_result.sheet_name,
            total_rows_examined=len(read_result.activities),
            rows_accepted=accepted_count,
            rows_rejected=rejected_count,
            created_activity_ids=tuple(created_ids),
            updated_activity_ids=tuple(updated_ids),
            duplicates_detected=tuple(duplicates),
            warnings=tuple(warnings),
            errors=tuple(errors),
            rejection_reasons=tuple(rejections),
        )


# ---------------------------------------------------------------------------
# MethodologicalDesignService — Servicio de Aplicación del Diseño Metodológico
# ---------------------------------------------------------------------------
class MethodologicalDesignService:
    """Servicio de aplicación para gestionar el ciclo operativo del Diseño Metodológico.

    Fase 29.9 — Implementación Controlada del Servicio de Gestión del Diseño Metodológico.
    Flujo gestionado:
      PLANNED ACTIVITY -> SIN DISEÑO -> CREATE DRAFT -> DRAFT -> UPDATE DRAFT -> VALIDATE -> APPROVE -> APPROVED -> INMUTABLE

    Principios y Reglas:
      - R-08: Inmutabilidad estricta de diseños en estado APPROVED. Toda modificación es rechazada antes de persistir.
      - D-04: Referencia a activity_internal_id (UUID) y planning_id (clave institucional).
      - R-01, R-05, R-06, R-07, R-10: Invariantes y derivaciones institucionales del dominio.
      - Aislamiento: No importa sqlite3, openpyxl, python-docx, ni app.word_consolidator.
      - Sin IA: Cero dependencias hacia modelos generativos o servicios de IA.
    """

    def __init__(
        self,
        uow: PlanningUnitOfWorkPort,
        validator: Optional[MethodologicalDesignValidator] = None,
        ai_assistance_port: Optional[AIAssistancePort] = None,
    ) -> None:
        """Inicializa el servicio inyectando la unidad de trabajo, el validador institucional y opcionalmente el puerto de IA."""
        self._uow = uow
        self._validator = validator or MethodologicalDesignValidator()
        self._ai_port = ai_assistance_port

    def list_activities_with_design_status(
        self,
        sede: Optional[str] = None,
        status: Optional[str] = None,
        search_term: Optional[str] = None,
    ) -> tuple[PlannedActivitySummaryDTO, ...]:
        """Obtiene actividades planificadas con su estado de diseño metodológico (DRAFT, GENERATED, APPROVED, SIN_DISENO).

        Args:
            sede: Filtro opcional por sede institucional.
            status: Filtro opcional por estado de diseño ('SIN_DISENO', 'DRAFT', 'GENERATED', 'APPROVED').
            search_term: Término de búsqueda opcional en nombre de actividad o planning_id.

        Returns:
            Tupla inmutable de PlannedActivitySummaryDTO.
        """
        with self._uow:
            activities = self._uow.planned_activities.list_all()
            summaries: list[PlannedActivitySummaryDTO] = []

            for act in activities:
                # 1. Filtro por sede si se especifica
                if sede and act.sede.strip().lower() != sede.strip().lower():
                    continue

                # 2. Filtro por término de búsqueda en nombre o código institucional
                if search_term:
                    term = search_term.strip().lower()
                    act_name = (act.activity_name or "").lower()
                    pid = (act.planning_id or "").lower()
                    if term not in act_name and term not in pid:
                        continue

                # 3. Determinar estado de diseño
                designs = self._uow.methodological_designs.get_by_activity_id(act.activity_internal_id)
                if designs:
                    design = designs[0]
                    design_status = design.status.value
                    design_id = design.design_id
                    design_version = design.version
                else:
                    design_status = "SIN_DISENO"
                    design_id = None
                    design_version = None

                # 4. Filtro por estado de diseño si se especifica
                if status and design_status.upper() != status.strip().upper():
                    continue

                summaries.append(
                    PlannedActivitySummaryDTO(
                        activity_internal_id=act.activity_internal_id,
                        planning_id=act.planning_id,
                        activity_name=act.activity_name,
                        sede=act.sede,
                        area_responsable=act.area_responsable,
                        total_participants=act.participant_goals.total() if act.participant_goals else 0,
                        design_status=design_status,
                        design_id=design_id,
                        design_version=design_version,
                    )
                )

            return tuple(summaries)

    def get_activity_detail(
        self,
        activity_ref: str,
    ) -> Optional[PlannedActivityDetailDTO]:
        """Obtiene el detalle completo de una actividad planificada y el estado de su diseño metodológico.

        Args:
            activity_ref: planning_id o string de UUID técnico.

        Returns:
            PlannedActivityDetailDTO si existe, o None si no se localiza.
        """
        if not activity_ref or not activity_ref.strip():
            return None

        clean_ref = activity_ref.strip()

        with self._uow:
            act = self._uow.planned_activities.get_by_planning_id(clean_ref)
            if act is None:
                try:
                    uid = uuid.UUID(clean_ref)
                    act = self._uow.planned_activities.get_by_internal_id(uid)
                except ValueError:
                    pass

            if act is None:
                return None

            designs = self._uow.methodological_designs.get_by_activity_id(act.activity_internal_id)
            if designs:
                design = designs[0]
                design_id = design.design_id
                design_status = design.status.value
                design_version = design.version
            else:
                design_id = None
                design_status = "SIN_DISENO"
                design_version = None

            return PlannedActivityDetailDTO(
                activity_internal_id=act.activity_internal_id,
                planning_id=act.planning_id,
                activity_name=act.activity_name,
                sede=act.sede,
                area_responsable=act.area_responsable,
                eje_estrategia=act.eje_estrategia,
                programa=act.programa,
                tipo_evento=act.tipo_evento,
                dep_sede=act.dep_sede,
                mun_sede=act.mun_sede,
                otro_programa=act.otro_programa,
                proyecto=act.proyecto,
                tipo_proyecto=act.tipo_proyecto,
                ambito=act.ambito,
                codigo_presupuestario=act.codigo_presupuestario,
                departamento_responsable=act.departamento_responsable,
                proposito=act.proposito,
                fecha_evento=act.fecha_evento,
                convenio=act.convenio,
                entidades_cooperantes=act.entidades_cooperantes,
                participant_goals=act.participant_goals,
                design_id=design_id,
                design_status=design_status,
                design_version=design_version,
            )

    def create_design_draft(
        self,
        activity_ref: str,
        created_by: str,
    ) -> MethodologicalDesignDTO:
        """Inicializa un borrador DRAFT de diseño metodológico de forma determinista e idempotente.

        Args:
            activity_ref: Referencia institucional (planning_id) de la actividad planificada.
            created_by: Identificación del usuario creador para auditoría.

        Returns:
            MethodologicalDesignDTO del diseño creado o existente.

        Raises:
            ValueError: Si activity_ref o created_by están vacíos, o si la actividad no existe.
            RuntimeError: Si la actividad ya cuenta con un diseño en estado APPROVED (R-08).
        """
        if not activity_ref or not activity_ref.strip():
            raise ValueError("activity_ref es obligatorio.")
        if not created_by or not created_by.strip():
            raise ValueError("created_by es obligatorio.")

        clean_ref = activity_ref.strip()
        clean_author = created_by.strip()

        with self._uow:
            act = self._uow.planned_activities.get_by_planning_id(clean_ref)
            if act is None:
                raise ValueError(f"No existe actividad planificada con referencia '{clean_ref}'.")

            existing = self._uow.methodological_designs.get_by_activity_ref(act.planning_id)
            if existing is not None:
                if existing.status == DesignStatus.DRAFT:
                    return existing.to_dto()
                elif existing.status == DesignStatus.GENERATED:
                    raise ValueError(
                        f"La actividad con referencia '{clean_ref}' ya tiene un diseño metodológico en estado GENERATED."
                    )
                elif existing.status == DesignStatus.APPROVED:
                    raise RuntimeError(
                        f"La actividad con referencia '{clean_ref}' ya tiene un diseño metodológico APPROVED (inmutable R-08)."
                    )
                else:
                    return existing.to_dto()

            # Prellenado de FAQ Table conforme a la validación de la Fase 29.8.1
            goals_summary = ""
            if act.participant_goals and act.participant_goals.total() > 0:
                goals_summary = f"{act.participant_goals.total()} participantes planificados"

            faq = FAQTable(
                q1_que_es=act.activity_name,
                q2_para_que=act.proposito or "",
                q3_sesiones="Sesión única",
                q4_protagonistas=goals_summary,
                q5_facilitador=act.area_responsable,
                q6_materiales="",
                q7_duracion="Por definir",
            )

            design = MethodologicalDesign.create_draft(
                planned_activity_ref=act.planning_id,
                created_by=clean_author,
            )
            design.planned_activity_internal_id = act.activity_internal_id
            design.activity_name = act.activity_name
            design.faq_table = faq

            self._uow.methodological_designs.save(design)
            self._uow.commit()

            return design.to_dto()

    def update_design_draft(
        self,
        command: UpdateMethodologicalDesignCommand,
    ) -> MethodologicalDesignDTO:
        """Actualiza los bloques de un diseño metodológico en estado DRAFT protegiendo estrictamente R-08.

        Args:
            command: UpdateMethodologicalDesignCommand con los campos a modificar.

        Returns:
            MethodologicalDesignDTO actualizado.

        Raises:
            ValueError: Si command es nulo o el diseño no existe.
            RuntimeError: Si el diseño está en estado APPROVED (R-08).
        """
        if command is None:
            raise ValueError("El comando de actualización no puede ser nulo.")

        with self._uow:
            design = self._uow.methodological_designs.get_by_id(command.design_id)
            if design is None:
                raise ValueError(f"No existe diseño metodológico con ID '{command.design_id}'.")

            # Regla R-08: Inmutabilidad estricta
            if design.status == DesignStatus.APPROVED:
                raise RuntimeError(
                    "No se puede modificar un diseño metodológico en estado APPROVED "
                    "(Regla R-08 de inmutabilidad institucional)."
                )

            # Actualizar campos del comando si se especifican
            if command.introduction_text is not None:
                design.introduction_text = command.introduction_text.strip()
            if command.methodological_approach is not None:
                design.methodological_approach = command.methodological_approach.strip()

            if command.objectives is not None:
                design.objectives = [obj.strip() for obj in command.objectives]

            if command.faq is not None:
                faq_dto = command.faq
                design.faq_table = FAQTable(
                    q1_que_es=faq_dto.q1_que_es,
                    q2_para_que=faq_dto.q2_para_que,
                    q3_sesiones=faq_dto.q3_sesiones,
                    q4_protagonistas=faq_dto.q4_protagonistas,
                    q5_facilitador=faq_dto.q5_facilitador,
                    q6_materiales=faq_dto.q6_materiales,
                    q7_duracion=faq_dto.q7_duracion,
                )

            if command.agenda is not None:
                design.agenda = [
                    TimeBlock(sequence=tb.sequence, label=tb.label, minutes=tb.minutes)
                    for tb in command.agenda
                ]
                # Sincronizar automáticamente q7_duracion si total_minutes > 0
                if design.total_minutes > 0 and design.faq_table is not None:
                    design.faq_table = FAQTable(
                        q1_que_es=design.faq_table.q1_que_es,
                        q2_para_que=design.faq_table.q2_para_que,
                        q3_sesiones=design.faq_table.q3_sesiones,
                        q4_protagonistas=design.faq_table.q4_protagonistas,
                        q5_facilitador=design.faq_table.q5_facilitador,
                        q6_materiales=design.faq_table.q6_materiales,
                        q7_duracion=f"{design.total_minutes} minutos",
                    )

            if command.operational_matrix is not None:
                design.operational_matrix = [
                    OperationalActivity(
                        step_number=oa.step_number,
                        phase_label=oa.phase_label,
                        operative_goal=oa.operative_goal,
                        procedure=oa.procedure,
                        materials=oa.materials,
                        minutes=oa.minutes,
                    )
                    for oa in command.operational_matrix
                ]

            # Invariante R-06 si ambas tablas están pobladas
            if design.agenda and design.operational_matrix:
                if len(design.agenda) != len(design.operational_matrix):
                    raise ValueError(
                        f"R-06: La agenda tiene {len(design.agenda)} bloques y la matriz operativa tiene "
                        f"{len(design.operational_matrix)}. Deben coincidir en cantidad y minutos."
                    )

            self._uow.methodological_designs.save(design)
            self._uow.commit()

            return design.to_dto()

    def validate_design(
        self,
        design_id: uuid.UUID,
    ) -> ValidationReportDTO:
        """Ejecuta las validaciones institucionales V-MD-01 a V-MD-12 retornando el reporte estructurado.

        Args:
            design_id: UUID del diseño metodológico.

        Returns:
            ValidationReportDTO con los resultados y severidades.

        Raises:
            ValueError: Si design_id es nulo o no existe.
        """
        if design_id is None:
            raise ValueError("design_id es obligatorio.")

        with self._uow:
            design = self._uow.methodological_designs.get_by_id(design_id)
            if design is None:
                raise ValueError(f"No existe diseño metodológico con ID '{design_id}'.")

            act = self._uow.planned_activities.get_by_planning_id(design.planned_activity_ref)

            report = self._validator.validate(design, act)

            errors = tuple(
                ValidationResultDTO(
                    rule_id=r.rule_id,
                    severity=r.severity.value,
                    message=r.message,
                    field=r.field,
                )
                for r in report.errors
            )
            warnings = tuple(
                ValidationResultDTO(
                    rule_id=r.rule_id,
                    severity=r.severity.value,
                    message=r.message,
                    field=r.field,
                )
                for r in report.warnings
            )
            all_results = tuple(
                ValidationResultDTO(
                    rule_id=r.rule_id,
                    severity=r.severity.value,
                    message=r.message,
                    field=r.field,
                )
                for r in report.results
            )

            return ValidationReportDTO(
                is_valid=report.is_valid,
                errors=errors,
                warnings=warnings,
                results=all_results,
            )

    def approve_design(
        self,
        design_id: uuid.UUID,
        approved_by: str,
    ) -> MethodologicalDesignDTO:
        """Aprueba formalmente el diseño metodológico tras verificar la ausencia de errores bloqueantes.

        Args:
            design_id: UUID del diseño metodológico a aprobar.
            approved_by: Identificación del aprobador institucional.

        Returns:
            MethodologicalDesignDTO en estado APPROVED.

        Raises:
            ValueError: Si design_id o approved_by son inválidos, o si el diseño tiene errores bloqueantes.
            RuntimeError: Si el diseño ya se encuentra en estado APPROVED (R-08).
        """
        if design_id is None:
            raise ValueError("design_id es obligatorio.")
        if not approved_by or not approved_by.strip():
            raise ValueError("approved_by es obligatorio para la aprobación formal.")

        clean_approver = approved_by.strip()

        with self._uow:
            design = self._uow.methodological_designs.get_by_id(design_id)
            if design is None:
                raise ValueError(f"No existe diseño metodológico con ID '{design_id}'.")

            if design.status == DesignStatus.APPROVED:
                raise RuntimeError(
                    "El diseño metodológico ya se encuentra en estado APPROVED (inmutable R-08)."
                )

            act = self._uow.planned_activities.get_by_planning_id(design.planned_activity_ref)

            # Validación formal obligatoria antes de aprobar
            report = self._validator.validate(design, act)
            if not report.is_valid:
                error_msgs = "; ".join(e.message for e in report.errors)
                raise ValueError(
                    f"No se puede aprobar el diseño metodológico '{design_id}': "
                    f"contiene errores bloqueantes: {error_msgs}"
                )

            design.approve(approved_by=clean_approver)
            self._uow.methodological_designs.save(design)
            self._uow.commit()

            return design.to_dto()

    def request_ai_proposal(
        self,
        command: RequestAIProposalCommand,
        ai_port: Optional[AIAssistancePort] = None,
    ) -> AIProposalDTO:
        """Solicita una propuesta de asistencia de IA para un campo permitido.

        Args:
            command: RequestAIProposalCommand con design_id, target_field y parámetros opcionales.
            ai_port: Puerto de asistencia de IA opcional (si no se inyectó en el constructor).

        Returns:
            AIProposalDTO con la propuesta generada en estado pendiente de revisión humana.

        Raises:
            ValueError: Si el comando es nulo, el diseño o actividad no existen, o target_field es inválido.
            RuntimeError: Si el diseño está en estado APPROVED (R-08) o no hay puerto de IA configurado.
        """
        if command is None:
            raise ValueError("El comando de solicitud de propuesta no puede ser nulo.")

        port = ai_port or self._ai_port
        if port is None:
            raise RuntimeError(
                "No se ha configurado un puerto de asistencia de IA (AIAssistancePort)."
            )

        with self._uow:
            design = self._uow.methodological_designs.get_by_id(command.design_id)
            if design is None:
                raise ValueError(f"No existe diseño metodológico con ID '{command.design_id}'.")

            if design.status == DesignStatus.APPROVED:
                raise RuntimeError(
                    "No se pueden generar propuestas de IA para un diseño metodológico en estado APPROVED "
                    "(Regla R-08 de inmutabilidad institucional)."
                )

            act = self._uow.planned_activities.get_by_planning_id(design.planned_activity_ref)
            if act is None:
                raise ValueError(
                    f"No existe actividad planificada con referencia '{design.planned_activity_ref}'."
                )

            # Validar y construir contexto con sanitización estricta (whitelisting)
            context = AIContextBuilder.build_context(
                activity=act,
                target_field=command.target_field,
                step_number=command.step_number,
                phase_label=command.phase_label,
            )

            # Generar propuesta a través del puerto
            proposal = port.generate_narrative_proposal(
                target_field=command.target_field,
                source_inputs=context,
            )

            # Invariante de seguridad: requires_review debe ser True
            if not proposal.requires_review:
                raise RuntimeError("Invariante violada: AIProposal.requires_review debe ser True.")

            design.add_ai_proposal(proposal)
            self._uow.methodological_designs.save(design)
            self._uow.commit()

            return AIProposalDTO.from_domain(proposal, design.design_id)

    def accept_ai_proposal(
        self,
        command: AcceptAIProposalCommand,
    ) -> MethodologicalDesignDTO:
        """Acepta formalmente una propuesta de IA y vuelca su contenido al campo correspondiente.

        IMPORTANTE: Aceptar una propuesta NO aprueba el diseño (el diseño permanece en DRAFT).

        Args:
            command: AcceptAIProposalCommand con design_id, proposal_id y reviewer.

        Returns:
            MethodologicalDesignDTO actualizado con el texto aplicado y la propuesta auditada.

        Raises:
            ValueError: Si el comando es nulo, el diseño o propuesta no existen, o ya fue revisada.
            RuntimeError: Si el diseño está en estado APPROVED (R-08).
        """
        if command is None:
            raise ValueError("El comando de aceptación no puede ser nulo.")
        if not command.reviewer or not command.reviewer.strip():
            raise ValueError("El revisor (reviewer) es obligatorio al aceptar una propuesta.")

        with self._uow:
            design = self._uow.methodological_designs.get_by_id(command.design_id)
            if design is None:
                raise ValueError(f"No existe diseño metodológico con ID '{command.design_id}'.")

            if design.status == DesignStatus.APPROVED:
                raise RuntimeError(
                    "No se puede modificar un diseño metodológico en estado APPROVED "
                    "(Regla R-08 de inmutabilidad institucional)."
                )

            # Localizar propuesta en el agregado
            target_prop: Optional[AIProposal] = None
            for p in design.ai_proposals:
                if p.proposal_id == command.proposal_id:
                    target_prop = p
                    break

            if target_prop is None:
                raise ValueError(
                    f"No existe propuesta con ID '{command.proposal_id}' en el diseño metodológico."
                )

            if not target_prop.is_pending_review:
                raise ValueError(
                    f"La propuesta '{command.proposal_id}' ya fue revisada previamente "
                    f"(accepted={target_prop.accepted})."
                )

            # Registrar aceptación humana
            target_prop.accept(reviewer=command.reviewer.strip())

            # Volcar contenido al campo correspondiente
            field_name = target_prop.target_field
            content = target_prop.proposed_content

            if field_name == "introduction":
                design.introduction_text = content
            elif field_name == "methodological_approach":
                design.methodological_approach = content
            elif field_name == "objective_1":
                if not design.objectives:
                    design.objectives = [content, ""]
                else:
                    design.objectives[0] = content
            elif field_name == "objective_2":
                if len(design.objectives) < 2:
                    if len(design.objectives) == 0:
                        design.objectives = ["", content]
                    else:
                        design.objectives.append(content)
                else:
                    design.objectives[1] = content
            elif field_name in ("procedure", "operative_goal"):
                step_no = target_prop.source_inputs.get("step_number")
                if step_no is not None:
                    # Reemplazar la OperationalActivity correspondiente preservando tiempos y orden
                    new_matrix = []
                    found = False
                    for op in design.operational_matrix:
                        if op.step_number == step_no:
                            found = True
                            new_op = OperationalActivity(
                                step_number=op.step_number,
                                phase_label=op.phase_label,
                                operative_goal=content if field_name == "operative_goal" else op.operative_goal,
                                procedure=content if field_name == "procedure" else op.procedure,
                                materials=op.materials,
                                minutes=op.minutes,
                            )
                            new_matrix.append(new_op)
                        else:
                            new_matrix.append(op)
                    if found:
                        design.operational_matrix = new_matrix

            self._uow.methodological_designs.save(design)
            self._uow.commit()

            return design.to_dto()

    def reject_ai_proposal(
        self,
        command: RejectAIProposalCommand,
    ) -> MethodologicalDesignDTO:
        """Rechaza formalmente una propuesta de IA registrando el motivo obligatorio.

        El contenido del diseño NO se modifica. La propuesta se conserva como evidencia histórica.

        Args:
            command: RejectAIProposalCommand con design_id, proposal_id, reviewer y rejection_reason.

        Returns:
            MethodologicalDesignDTO con la propuesta marcada como rechazada.

        Raises:
            ValueError: Si el comando es nulo, el diseño o propuesta no existen, o la razón está vacía.
            RuntimeError: Si el diseño está en estado APPROVED (R-08).
        """
        if command is None:
            raise ValueError("El comando de rechazo no puede ser nulo.")
        if not command.reviewer or not command.reviewer.strip():
            raise ValueError("El revisor (reviewer) es obligatorio al rechazar una propuesta.")
        if not command.rejection_reason or not command.rejection_reason.strip():
            raise ValueError("El motivo de rechazo (rejection_reason) es obligatorio.")

        with self._uow:
            design = self._uow.methodological_designs.get_by_id(command.design_id)
            if design is None:
                raise ValueError(f"No existe diseño metodológico con ID '{command.design_id}'.")

            if design.status == DesignStatus.APPROVED:
                raise RuntimeError(
                    "No se puede modificar un diseño metodológico en estado APPROVED "
                    "(Regla R-08 de inmutabilidad institucional)."
                )

            target_prop: Optional[AIProposal] = None
            for p in design.ai_proposals:
                if p.proposal_id == command.proposal_id:
                    target_prop = p
                    break

            if target_prop is None:
                raise ValueError(
                    f"No existe propuesta con ID '{command.proposal_id}' en el diseño metodológico."
                )

            if not target_prop.is_pending_review:
                raise ValueError(
                    f"La propuesta '{command.proposal_id}' ya fue revisada previamente "
                    f"(accepted={target_prop.accepted})."
                )

            # Registrar rechazo humano con motivo obligatorio
            target_prop.reject(
                reviewer=command.reviewer.strip(),
                reason=command.rejection_reason.strip(),
            )

            # NO se modifica ningún campo del diseño
            self._uow.methodological_designs.save(design)
            self._uow.commit()

            return design.to_dto()

    def list_ai_proposals(
        self,
        design_id: uuid.UUID,
    ) -> tuple[AIProposalDTO, ...]:
        """Lista todas las propuestas de IA asociadas a un diseño metodológico."""
        if design_id is None:
            raise ValueError("design_id es obligatorio.")

        with self._uow:
            design = self._uow.methodological_designs.get_by_id(design_id)
            if design is None:
                raise ValueError(f"No existe diseño metodológico con ID '{design_id}'.")

            return tuple(
                AIProposalDTO.from_domain(p, design.design_id)
                for p in design.ai_proposals
            )
