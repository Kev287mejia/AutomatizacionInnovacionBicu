"""app.reporting.infrastructure.memory_cache

Caché en Memoria Volátil de Corta Duración para Reporting y Dashboard BICU.
Fase 29.20.1 — Implementación Controlada del Núcleo Reporting Service.

PRINCIPIOS:
  - Exclusivamente en memoria RAM (sin SQLite, sin disco, sin archivos).
  - TTL (Time-To-Live) corto y configurable (predeterminado: 60 segundos).
  - Invalidador manual simple y seguro contra concurrencia.
  - Totalmente pasivo: si está deshabilitado o ante fallo, recalcula limpiamente.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, Optional, Tuple

from app.reporting.domain.dto import ReportFilterDTO


class ReportingMemoryCache:
    """Caché analítica en memoria de corta duración para DTOs calculados."""

    def __init__(self, default_ttl_seconds: int = 60, enabled: bool = True) -> None:
        self._default_ttl = default_ttl_seconds
        self._enabled = enabled
        self._storage: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def make_key(self, prefix: str, filters: ReportFilterDTO) -> str:
        """Genera una clave determinista basada en el prefijo y los filtros aplicados."""
        filter_signature = (
            f"yr={filters.period_year}|st={filters.start_date}|en={filters.end_date}|"
            f"sd={filters.sede}|mun={filters.municipio}|dep={filters.departamento}|"
            f"pr={filters.programa}|eje={filters.eje_estrategia}|tp={filters.tipo_evento}|"
            f"mm={filters.multisession_goal_mode}|rv={filters.require_verified_id_for_unique_persons}"
        )
        return f"{prefix}::{filter_signature}"

    def get(self, key: str) -> Optional[Any]:
        """Obtiene un elemento de la caché si no ha expirado."""
        if not self._enabled:
            return None

        with self._lock:
            entry = self._storage.get(key)
            if not entry:
                return None

            value, expires_at = entry
            now = datetime.now(timezone.utc).timestamp()
            if now > expires_at:
                del self._storage[key]
                return None

            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Guarda un elemento en la caché con tiempo de vida limitado."""
        if not self._enabled:
            return

        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = datetime.now(timezone.utc).timestamp() + max(1, ttl)

        with self._lock:
            self._storage[key] = (value, expires_at)

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalida una clave específica o limpia completamente la caché."""
        with self._lock:
            if key is None:
                self._storage.clear()
            else:
                self._storage.pop(key, None)

    def clear(self) -> None:
        """Alias para invalidar todo el almacenamiento."""
        self.invalidate(None)

    @property
    def size(self) -> int:
        """Retorna el número de elementos actualmente en caché."""
        with self._lock:
            return len(self._storage)
