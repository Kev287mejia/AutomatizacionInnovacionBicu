"""app.review.infrastructure

Capa de infraestructura y persistencia para la Cola de Revisión.
"""

from app.review.infrastructure.sqlite_review_repository import (
    SQLiteReviewQueueRepository,
)

__all__ = [
    "SQLiteReviewQueueRepository",
]
