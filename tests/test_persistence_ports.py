"""tests/test_persistence_ports.py

Pruebas unitarias y arquitectónicas de los puertos de persistencia (Subetapa 25.3.2):
- Comprobación de independencia absoluta respecto a SQLite e Infrastructure.
- Verificación de la condición abstracta de las interfaces.
- Verificación de jerarquía de excepciones de dominio de persistencia.
- Verificación de implementación simulada (Mock/In-Memory) para pruebas de Application.
"""

import sys
import inspect
import pytest

from app.core.exceptions.system_exceptions import SistemaBaseException
from app.core.exceptions.persistence_exceptions import (
    PersistenceError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    ReferentialIntegrityError,
    TransactionError,
)
from app.core.ports import (
    IActividadRepository,
    IPersonaRepository,
    IParticipacionRepository,
    IEvidenciaRepository,
    IInformeSemanalRepository,
    IDiscrepanciaRepository,
    IUnitOfWork,
)
from app.core.models import (
    Activity,
    Person,
    Participation,
    Evidencia,
    InformeSemanal,
    Discrepancia,
)


class TestPersistencePortsArchitectureAndIndependence:
    """Verificación de independencia arquitectónica de los puertos."""

    def test_ports_do_not_import_sqlite3(self):
        """Comprueba que los módulos de puertos no importen sqlite3."""
        port_modules = [
            "app.core.ports",
            "app.core.ports.actividad_repository",
            "app.core.ports.persona_repository",
            "app.core.ports.participacion_repository",
            "app.core.ports.evidencia_repository",
            "app.core.ports.informe_semanal_repository",
            "app.core.ports.discrepancia_repository",
            "app.core.ports.unit_of_work",
            "app.core.exceptions.persistence_exceptions",
        ]

        for mod_name in port_modules:
            assert mod_name in sys.modules, f"El módulo {mod_name} debería estar cargado."
            mod = sys.modules[mod_name]
            # Inspeccionar el código fuente del módulo para asegurar que 'sqlite3' no figure
            source = inspect.getsource(mod)
            assert "sqlite3" not in source, f"El módulo {mod_name} contiene referencias a sqlite3."
            assert "PRAGMA" not in source, f"El módulo {mod_name} contiene referencias a PRAGMA."
            assert "schema_version" not in source, f"El módulo {mod_name} contiene referencias a schema_version."

    def test_ports_do_not_depend_on_infrastructure(self):
        """Verifica que ningún puerto importe código de app.infrastructure."""
        port_modules = [
            "app.core.ports.actividad_repository",
            "app.core.ports.persona_repository",
            "app.core.ports.participacion_repository",
            "app.core.ports.evidencia_repository",
            "app.core.ports.informe_semanal_repository",
            "app.core.ports.discrepancia_repository",
            "app.core.ports.unit_of_work",
        ]

        for mod_name in port_modules:
            mod = sys.modules[mod_name]
            source = inspect.getsource(mod)
            assert "app.infrastructure" not in source, (
                f"El puerto {mod_name} viola la inversión de dependencias importando app.infrastructure."
            )


class TestAbstractContracts:
    """Verifica que los contratos sean estrictamente abstractos."""

    def test_cannot_instantiate_abstract_ports(self):
        """Garantiza que ninguna de las 7 interfaces pueda instanciarse directamente."""
        abstract_classes = [
            IActividadRepository,
            IPersonaRepository,
            IParticipacionRepository,
            IEvidenciaRepository,
            IInformeSemanalRepository,
            IDiscrepanciaRepository,
            IUnitOfWork,
        ]

        for cls in abstract_classes:
            with pytest.raises(TypeError, match="Can't instantiate abstract class"):
                cls()  # type: ignore

    def test_persistence_exceptions_hierarchy(self):
        """Verifica que las excepciones de persistencia deriven de SistemaBaseException."""
        assert issubclass(PersistenceError, SistemaBaseException)
        assert issubclass(EntityNotFoundError, PersistenceError)
        assert issubclass(EntityAlreadyExistsError, PersistenceError)
        assert issubclass(ReferentialIntegrityError, PersistenceError)
        assert issubclass(TransactionError, PersistenceError)

        err = EntityNotFoundError("Persona", "uuid-123")
        assert "Persona" in str(err)
        assert "uuid-123" in str(err)


class TestMockImplementationPossibility:
    """Demuestra que los contratos pueden implementarse en memoria para pruebas de Application."""

    def test_in_memory_repository_implements_contract(self):
        """Prueba una implementación en memoria de IPersonaRepository sin tocar base de datos."""

        class InMemoryPersonaRepository(IPersonaRepository):
            def __init__(self):
                self._storage = {}

            def save(self, persona: Person) -> None:
                self._storage[persona.id_persona_interno] = persona

            def get_by_id(self, id_persona_interno: str):
                return self._storage.get(id_persona_interno)

            def get_by_cedula(self, cedula: str):
                if not cedula:
                    return None
                for p in self._storage.values():
                    if p.cedula == cedula:
                        return p
                return None

            def get_by_numero_institucional(self, numero: str):
                for p in self._storage.values():
                    if p.numero_unico == numero:
                        return p
                return None

            def search_by_nombre(self, nombre_query: str, limite: int = 10):
                matches = [
                    p for p in self._storage.values()
                    if nombre_query.lower() in p.nombre_completo.lower()
                ]
                return matches[:limite]

            def exists(self, id_persona_interno: str) -> bool:
                return id_persona_interno in self._storage

            def count(self) -> int:
                return len(self._storage)

        repo = InMemoryPersonaRepository()
        p1 = Person(nombre_completo="Ana Ruiz", cedula="001-010190-0001A")
        p2 = Person(nombre_completo="Carlos Dixon", cedula=None)  # RN-C04: cedula NULL permitida

        repo.save(p1)
        repo.save(p2)

        assert repo.count() == 2
        assert repo.exists(p1.id_persona_interno) is True
        assert repo.get_by_id(p2.id_persona_interno).nombre_completo == "Carlos Dixon"
        assert repo.get_by_cedula("001-010190-0001A").nombre_completo == "Ana Ruiz"
        assert repo.get_by_cedula(None) is None
        assert len(repo.search_by_nombre("dixon")) == 1
