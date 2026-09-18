"""Implementación Fake en memoria del patrón Unit of Work (IUnitOfWork).

Proporciona frontera transaccional atómica simulada para pruebas de Application sin SQLite:
- Coordina los seis repositorios en memoria.
- Simula ciclo transaccional: __enter__, __exit__, commit() y rollback().
- Soporta reversión automática (rollback) mediante instantáneas en memoria ante excepciones.
- Requiere acceso a repositorios dentro del contexto 'with uow:', lanzando TransactionError en caso contrario.
- No implementa lógica de negocio institucional ni de ruteo.
"""

from copy import deepcopy
from typing import Dict, List, Optional, Tuple, Type
from types import TracebackType

from app.core.exceptions.persistence_exceptions import TransactionError
from app.core.ports.unit_of_work import IUnitOfWork
from app.core.ports.actividad_repository import IActividadRepository
from app.core.ports.persona_repository import IPersonaRepository
from app.core.ports.participacion_repository import IParticipacionRepository
from app.core.ports.evidencia_repository import IEvidenciaRepository
from app.core.ports.informe_semanal_repository import IInformeSemanalRepository
from app.core.ports.discrepancia_repository import IDiscrepanciaRepository

from app.application.fakes.in_memory_actividad_repo import InMemoryActividadRepository
from app.application.fakes.in_memory_persona_repo import InMemoryPersonaRepository
from app.application.fakes.in_memory_participacion_repo import InMemoryParticipacionRepository
from app.application.fakes.in_memory_evidencia_repo import InMemoryEvidenciaRepository
from app.application.fakes.in_memory_informe_semanal_repo import InMemoryInformeSemanalRepository
from app.application.fakes.in_memory_discrepancia_repo import InMemoryDiscrepanciaRepository


class InMemoryUnitOfWork(IUnitOfWork):
    """Implementación en memoria de IUnitOfWork para pruebas de la capa Application."""

    def __init__(
        self,
        actividades: Optional[InMemoryActividadRepository] = None,
        personas: Optional[InMemoryPersonaRepository] = None,
        participaciones: Optional[InMemoryParticipacionRepository] = None,
        evidencias: Optional[InMemoryEvidenciaRepository] = None,
        informes_semanales: Optional[InMemoryInformeSemanalRepository] = None,
        discrepancias: Optional[InMemoryDiscrepanciaRepository] = None,
    ) -> None:
        """Inicializa el Unit of Work con repositorios en memoria aislados o inyectados."""
        self._repo_actividades = actividades if actividades is not None else InMemoryActividadRepository()
        self._repo_personas = personas if personas is not None else InMemoryPersonaRepository()
        self._repo_participaciones = participaciones if participaciones is not None else InMemoryParticipacionRepository()
        self._repo_evidencias = evidencias if evidencias is not None else InMemoryEvidenciaRepository()
        self._repo_informes = informes_semanales if informes_semanales is not None else InMemoryInformeSemanalRepository()
        self._repo_discrepancias = discrepancias if discrepancias is not None else InMemoryDiscrepanciaRepository()

        self._in_transaction: bool = False
        self._snapshot: Optional[Tuple[object, ...]] = None

    @property
    def actividades(self) -> IActividadRepository:
        """Acceso al repositorio de Actividades dentro de la transacción."""
        if not self._in_transaction:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._repo_actividades

    @property
    def personas(self) -> IPersonaRepository:
        """Acceso al repositorio de Personas dentro de la transacción."""
        if not self._in_transaction:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._repo_personas

    @property
    def participaciones(self) -> IParticipacionRepository:
        """Acceso al repositorio de Participaciones dentro de la transacción."""
        if not self._in_transaction:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._repo_participaciones

    @property
    def evidencias(self) -> IEvidenciaRepository:
        """Acceso al repositorio de Evidencias dentro de la transacción."""
        if not self._in_transaction:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._repo_evidencias

    @property
    def informes_semanales(self) -> IInformeSemanalRepository:
        """Acceso al repositorio de Informes Semanales dentro de la transacción."""
        if not self._in_transaction:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._repo_informes

    @property
    def discrepancias(self) -> IDiscrepanciaRepository:
        """Acceso al repositorio de Discrepancias dentro de la transacción."""
        if not self._in_transaction:
            raise TransactionError(
                "UnitOfWork no inicializado. Debe utilizarse dentro de un bloque 'with'."
            )
        return self._repo_discrepancias

    def _capture_snapshot(self) -> Tuple[object, ...]:
        """Toma una instantánea inmutable del estado actual de todos los repositorios."""
        return (
            deepcopy(self._repo_actividades._actividades),
            deepcopy(self._repo_personas._personas),
            deepcopy(self._repo_participaciones._participaciones),
            deepcopy(self._repo_participaciones._matriz_map),
            deepcopy(self._repo_evidencias._evidencias),
            deepcopy(self._repo_evidencias._vinculos),
            deepcopy(self._repo_informes._informes),
            deepcopy(self._repo_informes._detalles),
            deepcopy(self._repo_discrepancias._discrepancias),
        )

    def _restore_snapshot(self, snapshot: Tuple[object, ...]) -> None:
        """Restaura el estado de todos los repositorios a partir de una instantánea."""
        (
            self._repo_actividades._actividades,
            self._repo_personas._personas,
            self._repo_participaciones._participaciones,
            self._repo_participaciones._matriz_map,
            self._repo_evidencias._evidencias,
            self._repo_evidencias._vinculos,
            self._repo_informes._informes,
            self._repo_informes._detalles,
            self._repo_discrepancias._discrepancias,
        ) = deepcopy(snapshot)

    def __enter__(self) -> "InMemoryUnitOfWork":
        """Inicia el ámbito transaccional tomando la instantánea base."""
        self._in_transaction = True
        self._snapshot = self._capture_snapshot()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Finaliza el ámbito transaccional, ejecutando rollback si ocurrió error."""
        try:
            if exc_type is not None and self._in_transaction:
                self.rollback()
        finally:
            self._in_transaction = False
            self._snapshot = None

    def commit(self) -> None:
        """Confirma atómicamente la transacción actualizando la instantánea confirmada."""
        if not self._in_transaction:
            raise TransactionError("No existe una transacción activa para confirmar.")
        self._snapshot = self._capture_snapshot()
        self._in_transaction = False

    def rollback(self) -> None:
        """Revierte los cambios en memoria restaurando la instantánea previa."""
        if not self._in_transaction or self._snapshot is None:
            return
        self._restore_snapshot(self._snapshot)
        self._in_transaction = False
