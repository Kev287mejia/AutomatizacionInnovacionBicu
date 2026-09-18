"""Puerto de persistencia para el agregado Evidencia (Activos Digitales Institucionales).

Define la interfaz abstracta IEvidenciaRepository desacoplada
de cualquier tecnología física de base de datos o sistema de archivos.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from app.core.models.evidence import Evidencia


class IEvidenciaRepository(ABC):
    """Puerto de repositorio para metadatos y custodia de evidencias digitales.

    Reglas institucionales de diseño:
    - Bipartición de almacenamiento (Fase 24): Metadatos y hash SHA-256 en base de datos;
      archivos pesados residen en el sistema de archivos local.
    - Sin procesamiento binario: El repositorio no ejecuta OCR ni manipulación gráfica;
      persiste y consulta metadatos descriptivos y vínculos con actividades.
    """

    @abstractmethod
    def save(self, evidencia: Evidencia) -> None:
        """Inserta o actualiza los metadatos de un activo digital de evidencia.

        Args:
            evidencia: Entidad Evidencia a persistir.
        """
        ...

    @abstractmethod
    def get_by_id(self, id_evidencia: str) -> Optional[Evidencia]:
        """Recupera los metadatos de una evidencia por su identificador único (UUID).

        Args:
            id_evidencia: Identificador UUID de la evidencia.

        Returns:
            Instancia de Evidencia si existe, None en caso contrario.
        """
        ...

    @abstractmethod
    def get_by_hash(self, hash_sha256: str) -> Optional[Evidencia]:
        """Recupera una evidencia por su hash SHA-256 (utilizado para deduplicación criptográfica).

        Args:
            hash_sha256: Hash criptográfico SHA-256 del archivo.

        Returns:
            Instancia de Evidencia existente si coincide el hash, None en caso contrario.
        """
        ...

    @abstractmethod
    def link_actividad(
        self,
        id_actividad: str,
        id_evidencia: str,
        orden: int = 1,
        seccion: str = "GALERIA",
    ) -> None:
        """Asocia una evidencia digital a una actividad institucional específica.

        Args:
            id_actividad: Identificador de la actividad.
            id_evidencia: Identificador de la evidencia.
            orden: Posición u orden ordinal en el reporte Word.
            seccion: Sección de destino en el informe ('FICHA_TECNICA', 'GALERIA', 'ANEXO').
        """
        ...

    @abstractmethod
    def unlink_actividad(self, id_actividad: str, id_evidencia: str) -> None:
        """Desvincula una evidencia de una actividad.

        Args:
            id_actividad: Identificador de la actividad.
            id_evidencia: Identificador de la evidencia.
        """
        ...

    @abstractmethod
    def get_by_actividad(
        self, id_actividad: str
    ) -> List[Tuple[Evidencia, int, str]]:
        """Recupera la totalidad de evidencias asociadas a una actividad con su orden y sección.

        Args:
            id_actividad: Identificador UUID de la actividad.

        Returns:
            Lista de tuplas conteniendo (Evidencia, orden_presentacion, seccion_informe).
        """
        ...
