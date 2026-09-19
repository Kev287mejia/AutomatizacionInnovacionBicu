"""app.application.use_cases.calidad.gestionar_discrepancias

Casos de uso para la consulta y resolución pericial de discrepancias institucionales.
Gobernado bajo el principio inviolable DETECTAR ≠ CORREGIR (Regla RN-C07).
"""

from typing import List, Optional

from app.application.commands.discrepancia_commands import ResolverRevisionDiscrepanciaCommand
from app.application.dto.output_dtos import DiscrepanciaDetalleDTO
from app.application.queries.discrepancia_queries import ConsultarDiscrepanciasPendientesQuery
from app.core.exceptions.persistence_exceptions import EntityNotFoundError
from app.core.models.discrepancy import Discrepancia
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository
from app.core.ports.unit_of_work import IUnitOfWork


class ConsultarDiscrepanciasPendientesUseCase:
    """Caso de uso de lectura para recuperar discrepancias activas no resueltas."""

    def __init__(
        self,
        discrepancia_repo: Optional[IDiscrepanciaRepository] = None,
        uow: Optional[IUnitOfWork] = None,
    ) -> None:
        self._discrepancia_repo = discrepancia_repo
        self._uow = uow

    def execute(
        self,
        query: ConsultarDiscrepanciasPendientesQuery,
        uow: Optional[IUnitOfWork] = None,
    ) -> List[DiscrepanciaDetalleDTO]:
        """Recupera la lista de discrepancias pendientes filtradas opcionalmente por severidad."""
        active_uow = uow or self._uow
        disc_repo = active_uow.discrepancias if active_uow is not None else self._discrepancia_repo

        if disc_repo is None:
            raise ValueError("Debe suministrarse un repositorio de discrepancias o Unit of Work.")

        discrepancias: List[Discrepancia] = disc_repo.list_pendientes(severidad=query.severidad)

        return [
            DiscrepanciaDetalleDTO(
                id_discrepancia=d.id_discrepancia,
                id_actividad=d.id_actividad,
                tipo=d.tipo_discrepancia.value if hasattr(d.tipo_discrepancia, "value") else str(d.tipo_discrepancia),
                severidad=d.severidad.value if hasattr(d.severidad, "value") else str(d.severidad),
                fuente_a=d.fuente_a_nombre,
                valor_a=d.fuente_a_valor,
                fuente_b=d.fuente_b_nombre,
                valor_b=d.fuente_b_valor,
                delta=d.delta_valor,
                estado=d.estado.value if hasattr(d.estado, "value") else str(d.estado),
                justificacion=d.justificacion_aclaratoria,
                usuario_revisor=d.usuario_revisor,
                fecha_deteccion=str(d.fecha_deteccion) if d.fecha_deteccion else None,
                fecha_revision=str(d.fecha_revision) if d.fecha_revision else None,
            )
            for d in discrepancias
        ]


class ResolverRevisionDiscrepanciaUseCase:
    """Caso de uso para registrar formalmente la resolución humana de una discrepancia.
    
    GARANTÍA RN-C07:
    - Preserva rigurosamente intactos fuente_a_valor, fuente_b_valor y delta_valor.
    - Asienta únicamente la justificación pericial, usuario revisor y fecha de revisión.
    """

    def __init__(
        self,
        discrepancia_repo: Optional[IDiscrepanciaRepository] = None,
        uow: Optional[IUnitOfWork] = None,
    ) -> None:
        self._discrepancia_repo = discrepancia_repo
        self._uow = uow

    def execute(
        self,
        command: ResolverRevisionDiscrepanciaCommand,
        uow: Optional[IUnitOfWork] = None,
    ) -> DiscrepanciaDetalleDTO:
        """Registra la aclaración pericial de la discrepancia."""
        active_uow = uow or self._uow

        if active_uow is not None:
            with active_uow:
                result = self._execute_core(command, active_uow.discrepancias)
                active_uow.commit()
            return result

        if self._discrepancia_repo is None:
            raise ValueError("Debe suministrarse un repositorio de discrepancias o Unit of Work.")

        return self._execute_core(command, self._discrepancia_repo)

    def _execute_core(
        self,
        command: ResolverRevisionDiscrepanciaCommand,
        disc_repo: IDiscrepanciaRepository,
    ) -> DiscrepanciaDetalleDTO:
        discrepancia = disc_repo.get_by_id(command.id_discrepancia)
        if discrepancia is None:
            raise EntityNotFoundError("Discrepancia", command.id_discrepancia)

        nuevo_estado_str = (
            command.nuevo_estado.value
            if hasattr(command.nuevo_estado, "value")
            else str(command.nuevo_estado)
        )

        disc_repo.registrar_revision(
            id_discrepancia=command.id_discrepancia,
            nuevo_estado=nuevo_estado_str,
            justificacion=command.justificacion_aclaratoria,
            usuario_revisor=command.usuario_revisor,
        )

        actualizada = disc_repo.get_by_id(command.id_discrepancia)
        if actualizada is None:
            raise EntityNotFoundError("Discrepancia", command.id_discrepancia)

        return DiscrepanciaDetalleDTO(
            id_discrepancia=actualizada.id_discrepancia,
            id_actividad=actualizada.id_actividad,
            tipo=actualizada.tipo_discrepancia.value if hasattr(actualizada.tipo_discrepancia, "value") else str(actualizada.tipo_discrepancia),
            severidad=actualizada.severidad.value if hasattr(actualizada.severidad, "value") else str(actualizada.severidad),
            fuente_a=actualizada.fuente_a_nombre,
            valor_a=actualizada.fuente_a_valor,
            fuente_b=actualizada.fuente_b_nombre,
            valor_b=actualizada.fuente_b_valor,
            delta=actualizada.delta_valor,
            estado=actualizada.estado.value if hasattr(actualizada.estado, "value") else str(actualizada.estado),
            justificacion=actualizada.justificacion_aclaratoria,
            usuario_revisor=actualizada.usuario_revisor,
            fecha_deteccion=str(actualizada.fecha_deteccion) if actualizada.fecha_deteccion else None,
            fecha_revision=str(actualizada.fecha_revision) if actualizada.fecha_revision else None,
        )
