"""Paquete app.indicators.infrastructure — Adaptadores de persistencia y lectura."""

from app.indicators.infrastructure.sqlite_reader import SQLiteIndicatorReader

__all__ = ["SQLiteIndicatorReader"]
