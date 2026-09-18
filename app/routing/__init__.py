"""
app.routing

Módulo de enrutamiento institucional a matrices oficiales (Fase 6).
Transforma participaciones validadas en decisiones internas de destino institucional.
"""

from app.routing.acl import RoutingACL
from app.routing.enums import MatrizDestino, SubtipoInstitucional
from app.routing.models import EnrutamientoRegistro, ResumenMatriz, ResultadoRouting
from app.routing.participant_router import ParticipantRouter
from app.routing.reporter import RoutingReporter

__all__ = [
    "MatrizDestino",
    "SubtipoInstitucional",
    "EnrutamientoRegistro",
    "ResumenMatriz",
    "ResultadoRouting",
    "ParticipantRouter",
    "RoutingReporter",
    "RoutingACL",
]
