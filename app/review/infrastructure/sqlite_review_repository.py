"""app.review.infrastructure.sqlite_review_repository

Adaptador relacional SQLite para el módulo de Cola de Revisión.
Gobernado bajo:
- Transaccionalidad atómica estricta (BEGIN IMMEDIATE / COMMIT / ROLLBACK).
- Registro mandatorio en auditoria_evento con tipo_operacion = 'DISCREPANCY_RESOLVE'.
- Exclusión e inviolabilidad incondicional de los 32 registros patrimoniales de M5.
- Preservación estricta de V004 sin necesidad de V005.
"""

from datetime import datetime
import json
import sqlite3
from typing import Any, Dict, List, Optional
import uuid

from app.audit.audit_logger import get_logger
from app.normalization.identifier_normalizer import IdentifierNormalizer
from app.review.application.dto import (
    CandidateMatchDTO,
    ReviewCaseDetailDTO,
    ReviewCaseSummaryDTO,
    ReviewHistoryItemDTO,
    ReviewResolutionResultDTO,
)
from app.review.domain.enums import (
    EstamentoInstitucional,
    ReviewCaseType,
    ReviewDecisionType,
)
from app.review.domain.exceptions import (
    HistoricalDataProtectionError,
    InvalidDecisionError,
    ReviewQueueDomainError,
)
from app.review.domain.models import ReviewDecision
from app.review.application.ports import IReviewQueueRepository

logger = get_logger(__name__)


class SQLiteReviewQueueRepository(IReviewQueueRepository):
    """Adaptador de persistencia SQLite para la gestión pericial de Cola de Revisión."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Inicializa el repositorio con una conexión activa a SQLite."""
        self._conn = connection
        self._conn.row_factory = sqlite3.Row

    def list_pending_cases(
        self, id_actividad: Optional[str] = None
    ) -> List[ReviewCaseSummaryDTO]:
        """Lista todas las participaciones en COLA_REVISION o con requiere_revision=1.

        REGLA PATRIMONIAL INNEGOCIABLE:
        Excluye obligatoriamente es_historico_preexistente = 1.
        """
        cursor = self._conn.cursor()

        base_sql = """
        SELECT 
            p.id_participacion,
            p.id_actividad,
            COALESCE(a.nombre_original, '[ACTIVIDAD_SIN_TITULO]') AS nombre_actividad,
            p.id_persona,
            COALESCE(per.nombre_completo, '[PERSONA_SIN_NOMBRE]') AS nombre_persona,
            per.cedula AS cedula_persona,
            p.estamento_declarado,
            p.matriz_destino,
            p.requiere_revision,
            p.motivo_revision,
            p.archivo_fuente_origen,
            p.fila_fuente_origen,
            a.fecha_inicio AS fecha_deteccion,
            p.es_historico_preexistente
        FROM participacion p
        JOIN persona per ON p.id_persona = per.id_persona_interno
        LEFT JOIN actividad a ON p.id_actividad = a.id_actividad
        WHERE p.es_historico_preexistente = 0
          AND (p.requiere_revision = 1 OR p.matriz_destino = 'COLA_REVISION')
        """

        params: List[Any] = []
        if id_actividad:
            base_sql += " AND p.id_actividad = ?"
            params.append(id_actividad)

        base_sql += " ORDER BY a.fecha_inicio DESC, p.fila_fuente_origen ASC;"

        cursor.execute(base_sql, params)
        rows = cursor.fetchall()

        casos: List[ReviewCaseSummaryDTO] = []
        for r in rows:
            tipo_caso = self._deducir_tipo_caso(r["estamento_declarado"], r["cedula_persona"], r["motivo_revision"])
            casos.append(
                ReviewCaseSummaryDTO(
                    id_caso=r["id_participacion"],
                    id_actividad=r["id_actividad"],
                    nombre_actividad=r["nombre_actividad"],
                    id_persona=r["id_persona"],
                    nombre_persona=r["nombre_persona"],
                    estamento_actual=r["estamento_declarado"],
                    tipo_caso=tipo_caso.value,
                    motivo_revision=r["motivo_revision"] or "Requiere validación institucional",
                    estado="PENDIENTE",
                    cedula_persona=r["cedula_persona"],
                    archivo_fuente=r["archivo_fuente_origen"],
                    fecha_deteccion=r["fecha_deteccion"],
                )
            )
        return casos

    def get_case_detail(self, id_participacion: str) -> Optional[ReviewCaseDetailDTO]:
        """Obtiene el detalle completo de un caso en revisión.

        Lanza HistoricalDataProtectionError si se intenta consultar un registro histórico.
        """
        cursor = self._conn.cursor()
        query = """
        SELECT 
            p.id_participacion,
            p.id_actividad,
            COALESCE(a.nombre_original, '[ACTIVIDAD_SIN_TITULO]') AS nombre_actividad,
            a.fecha_inicio AS fecha_actividad,
            a.sede AS lugar_actividad,
            p.id_persona,
            COALESCE(per.nombre_completo, '[PERSONA_SIN_NOMBRE]') AS nombre_persona,
            per.cedula AS cedula_persona,
            per.sexo AS sexo_persona,
            p.estamento_declarado,
            p.matriz_destino,
            p.carrera_o_cargo_actividad,
            p.entidad_externa_actividad,
            p.requiere_revision,
            p.motivo_revision,
            p.archivo_fuente_origen,
            p.fila_fuente_origen,
            p.es_historico_preexistente
        FROM participacion p
        JOIN persona per ON p.id_persona = per.id_persona_interno
        LEFT JOIN actividad a ON p.id_actividad = a.id_actividad
        WHERE p.id_participacion = ?;
        """
        cursor.execute(query, (id_participacion,))
        r = cursor.fetchone()
        if not r:
            return None

        # Protección patrimonial M5
        if r["es_historico_preexistente"] == 1:
            raise HistoricalDataProtectionError(
                f"El registro '{id_participacion}' es patrimonio histórico preexistente M5 y no puede revisarse."
            )

        tipo_caso = self._deducir_tipo_caso(r["estamento_declarado"], r["cedula_persona"], r["motivo_revision"])

        # Buscar candidatos sugeridos en el agregado Persona (EVIDENCIA ≠ SUPOSICIÓN)
        candidatos = self.search_candidates(r["nombre_persona"], r["id_persona"])

        return ReviewCaseDetailDTO(
            id_caso=r["id_participacion"],
            id_actividad=r["id_actividad"],
            nombre_actividad=r["nombre_actividad"],
            id_persona=r["id_persona"],
            nombre_persona=r["nombre_persona"],
            estamento_actual=r["estamento_declarado"],
            tipo_caso=tipo_caso.value,
            motivo_revision=r["motivo_revision"] or "Requiere validación institucional",
            estado="EN_REVISION" if r["requiere_revision"] else "RESUELTO",
            cedula_persona=r["cedula_persona"],
            sexo_persona=r["sexo_persona"],
            carrera_o_cargo=r["carrera_o_cargo_actividad"],
            entidad_externa=r["entidad_externa_actividad"],
            archivo_fuente=r["archivo_fuente_origen"],
            fila_fuente=r["fila_fuente_origen"],
            fecha_actividad=r["fecha_actividad"],
            lugar_actividad=r["lugar_actividad"],
            usuario_resolutor=None,
            fecha_resolucion=None,
            observaciones=None,
            candidatos_sugeridos=candidatos,
        )

    def search_candidates(
        self, nombre: str, excluir_id_persona: str, limite: int = 5
    ) -> List[CandidateMatchDTO]:
        """Busca candidatos potenciales por nombre para asistencia al operador (sin fusionar automáticamente)."""
        if not nombre or len(nombre.strip()) < 3:
            return []

        cursor = self._conn.cursor()
        palabras = [p.strip() for p in nombre.strip().split() if len(p.strip()) > 2]
        if not palabras:
            return []

        like_clauses = " OR ".join(["nombre_completo LIKE ?"] * len(palabras))
        params = [f"%{p}%" for p in palabras]
        params.append(excluir_id_persona)
        params.append(limite)

        sql = f"""
        SELECT 
            id_persona_interno,
            nombre_completo,
            cedula
        FROM persona
        WHERE ({like_clauses})
          AND id_persona_interno != ?
        LIMIT ?;
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        candidatos: List[CandidateMatchDTO] = []
        for row in rows:
            candidatos.append(
                CandidateMatchDTO(
                    id_persona=row["id_persona_interno"],
                    nombre_completo=row["nombre_completo"],
                    cedula=row["cedula"],
                    estamento_principal="REGISTRADO",
                    confianza=0.75,  # Valor informativo de similitud
                    criterio_coincidencia="Coincidencia léxica parcial de nombres/apellidos",
                )
            )
        return candidatos

    def execute_atomic_resolution(
        self,
        id_participacion: str,
        decision: ReviewDecision,
    ) -> ReviewResolutionResultDTO:
        """Ejecuta atómicamente la resolución de un caso de revisión.

        Pasos transaccionales (BEGIN IMMEDIATE ... COMMIT):
        1. Verificar que el registro exista y NO sea histórico preexistente.
        2. Obtener snapshots previos (participacion + persona).
        3. Actualizar participacion según la decisión adoptada.
        4. Actualizar persona si la decisión incluye confirmación de cédula válida.
        5. Registrar asiento forense inmutable en auditoria_evento (tipo_operacion = 'DISCREPANCY_RESOLVE').
        6. Confirmar la transacción atómicamente (COMMIT) o revertir (ROLLBACK) ante cualquier fallo.
        """
        cursor = self._conn.cursor()

        # Iniciar transacción inmediata atómica
        self._conn.execute("BEGIN IMMEDIATE;")
        try:
            # 1. Verificar estado actual
            cursor.execute(
                """
                SELECT 
                    p.id_participacion, p.id_actividad, p.id_persona,
                    p.estamento_declarado, p.matriz_destino, p.requiere_revision,
                    p.motivo_revision, p.es_historico_preexistente,
                    per.cedula, per.estado_identidad, per.nombre_completo
                FROM participacion p
                JOIN persona per ON p.id_persona = per.id_persona_interno
                WHERE p.id_participacion = ?;
                """,
                (id_participacion,),
            )
            current_row = cursor.fetchone()
            if not current_row:
                raise ReviewQueueDomainError(f"No existe la participación con ID '{id_participacion}'.")

            if current_row["es_historico_preexistente"] == 1:
                raise HistoricalDataProtectionError(
                    f"El registro '{id_participacion}' es patrimonio histórico preexistente M5 y no puede ser resuelto."
                )

            snapshot_previo: Dict[str, Any] = {
                "id_participacion": current_row["id_participacion"],
                "id_persona": current_row["id_persona"],
                "estamento_declarado": current_row["estamento_declarado"],
                "matriz_destino": current_row["matriz_destino"],
                "requiere_revision": current_row["requiere_revision"],
                "motivo_revision": current_row["motivo_revision"],
                "cedula": current_row["cedula"],
                "estado_identidad": current_row["estado_identidad"],
            }

            snapshot_nuevo: Dict[str, Any] = dict(snapshot_previo)
            nueva_matriz: Optional[str] = None
            nuevo_estado_caso: str = "RESUELTO"

            # 2. Aplicar lógica según decisión
            if decision.tipo_decision == ReviewDecisionType.CONFIRMAR_ESTAMENTO:
                if not decision.nuevo_estamento:
                    raise InvalidDecisionError("Debe suministrarse un estamento oficial válido.")

                nueva_matriz = decision.nuevo_estamento.matriz_destino
                nuevo_estamento = decision.nuevo_estamento.value

                cursor.execute(
                    """
                    UPDATE participacion
                    SET estamento_declarado = ?,
                        matriz_destino = ?,
                        requiere_revision = 0,
                        motivo_revision = ?
                    WHERE id_participacion = ?;
                    """,
                    (
                        nuevo_estamento,
                        nueva_matriz,
                        f"Resuelto: Estamento confirmado como {nuevo_estamento} ({decision.justificacion})",
                        id_participacion,
                    ),
                )
                snapshot_nuevo["estamento_declarado"] = nuevo_estamento
                snapshot_nuevo["matriz_destino"] = nueva_matriz
                snapshot_nuevo["requiere_revision"] = 0
                snapshot_nuevo["motivo_revision"] = f"Resuelto: {nuevo_estamento}"

            elif decision.tipo_decision == ReviewDecisionType.CONFIRMAR_IDENTIDAD:
                # Opción A: Asociar a persona existente seleccionada explícitamente
                if decision.id_persona_seleccionada:
                    # Validar existencia de la persona seleccionada
                    cursor.execute(
                        "SELECT id_persona_interno, cedula FROM persona WHERE id_persona_interno = ?;",
                        (decision.id_persona_seleccionada,),
                    )
                    persona_row = cursor.fetchone()
                    if not persona_row:
                        raise InvalidDecisionError(
                            f"La persona seleccionada '{decision.id_persona_seleccionada}' no existe en la base de datos."
                        )

                    cursor.execute(
                        """
                        UPDATE participacion
                        SET id_persona = ?,
                            requiere_revision = 0,
                            motivo_revision = ?
                        WHERE id_participacion = ?;
                        """,
                        (
                            decision.id_persona_seleccionada,
                            f"Resuelto: Identidad vinculada a persona existente ({decision.justificacion})",
                            id_participacion,
                        ),
                    )
                    snapshot_nuevo["id_persona"] = decision.id_persona_seleccionada
                    snapshot_nuevo["requiere_revision"] = 0
                    snapshot_nuevo["motivo_revision"] = "Resuelto: Identidad confirmada existente"

                # Opción B: Asignar nueva cédula validada
                elif decision.nueva_cedula:
                    cedula_norm, err_val = IdentifierNormalizer.normalizar_cedula(
                        decision.nueva_cedula,
                        id_referencia=current_row["id_persona"],
                        fuente="RESOLUCION_HUMANA",
                    )
                    if not cedula_norm:
                        msg_err = err_val.mensaje if err_val else "Cédula no cumple el formato nicaragüense."
                        raise InvalidDecisionError(f"Cédula inválida: {msg_err}")

                    # Verificar unicidad parcial (RN-C04): no debe pertenecer a otra persona
                    cursor.execute(
                        "SELECT id_persona_interno FROM persona WHERE cedula = ? AND id_persona_interno != ?;",
                        (cedula_norm, current_row["id_persona"]),
                    )
                    colision = cursor.fetchone()
                    if colision:
                        raise InvalidDecisionError(
                            f"La cédula '{cedula_norm}' ya está asignada a otra persona (ID '{colision['id_persona_interno']}'). "
                            "No se permite colisión de cédulas activas."
                        )

                    cursor.execute(
                        """
                        UPDATE persona
                        SET cedula = ?,
                            estado_identidad = 'IDENTIDAD_CONFIRMADA'
                        WHERE id_persona_interno = ?;
                        """,
                        (cedula_norm, current_row["id_persona"]),
                    )
                    cursor.execute(
                        """
                        UPDATE participacion
                        SET requiere_revision = 0,
                            motivo_revision = ?
                        WHERE id_participacion = ?;
                        """,
                        (
                            f"Resuelto: Cédula validada institucionalmente ({decision.justificacion})",
                            id_participacion,
                        ),
                    )
                    snapshot_nuevo["cedula"] = cedula_norm
                    snapshot_nuevo["estado_identidad"] = "IDENTIDAD_CONFIRMADA"
                    snapshot_nuevo["requiere_revision"] = 0

            elif decision.tipo_decision == ReviewDecisionType.MARCAR_NO_RESOLUBLE:
                nuevo_estado_caso = "NO_RESOLUBLE"
                nueva_matriz = "COLA_REVISION"
                cursor.execute(
                    """
                    UPDATE participacion
                    SET requiere_revision = 1,
                        matriz_destino = 'COLA_REVISION',
                        motivo_revision = ?
                    WHERE id_participacion = ?;
                    """,
                    (
                        f"NO_RESOLUBLE: {decision.justificacion}",
                        id_participacion,
                    ),
                )
                snapshot_nuevo["motivo_revision"] = f"NO_RESOLUBLE: {decision.justificacion}"

            # 3. Registrar auditoría forense inmutable (tipo_operacion = 'DISCREPANCY_RESOLVE')
            id_auditoria = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO auditoria_evento (
                    id_auditoria, fecha_hora, usuario_operador, tipo_operacion,
                    tabla_afectada, id_registro_afectado, snapshot_previo_json,
                    snapshot_nuevo_json, motivo_modificacion
                ) VALUES (?, ?, ?, 'DISCREPANCY_RESOLVE', 'participacion', ?, ?, ?, ?);
                """,
                (
                    id_auditoria,
                    decision.fecha_resolucion,
                    decision.usuario_operador,
                    id_participacion,
                    json.dumps(snapshot_previo, ensure_ascii=False),
                    json.dumps(snapshot_nuevo, ensure_ascii=False),
                    decision.justificacion,
                ),
            )

            # Confirmar la transacción atómica
            self._conn.execute("COMMIT;")

            return ReviewResolutionResultDTO(
                id_caso=id_participacion,
                exito=True,
                mensaje=f"Caso procesado exitosamente como {nuevo_estado_caso}.",
                nuevo_estado=nuevo_estado_caso,
                matriz_destino=nueva_matriz or current_row["matriz_destino"],
                id_auditoria=id_auditoria,
            )

        except Exception as e:
            # Revertir integralmente ante cualquier excepción
            self._conn.execute("ROLLBACK;")
            logger.error(f"Fallo en resolución atómica de caso '{id_participacion}': {e}")
            raise

    def list_history(self, limite: int = 50) -> List[ReviewHistoryItemDTO]:
        """Recupera los eventos de resolución de discrepancias asentados en auditoria_evento."""
        cursor = self._conn.cursor()
        query = """
        SELECT 
            id_auditoria,
            fecha_hora,
            usuario_operador,
            id_registro_afectado,
            motivo_modificacion,
            snapshot_previo_json,
            snapshot_nuevo_json
        FROM auditoria_evento
        WHERE tipo_operacion = 'DISCREPANCY_RESOLVE'
        ORDER BY fecha_hora DESC
        LIMIT ?;
        """
        cursor.execute(query, (limite,))
        rows = cursor.fetchall()

        historial: List[ReviewHistoryItemDTO] = []
        for r in rows:
            prev = json.loads(r["snapshot_previo_json"]) if r["snapshot_previo_json"] else {}
            new = json.loads(r["snapshot_nuevo_json"]) if r["snapshot_nuevo_json"] else {}

            resumen_cambios = []
            for k in ("estamento_declarado", "matriz_destino", "cedula", "motivo_revision"):
                v_prev = prev.get(k)
                v_new = new.get(k)
                if v_prev != v_new:
                    resumen_cambios.append(f"{k}: '{v_prev}' ➔ '{v_new}'")

            texto_cambios = "; ".join(resumen_cambios) if resumen_cambios else "Actualización pericial"

            historial.append(
                ReviewHistoryItemDTO(
                    id_auditoria=r["id_auditoria"],
                    fecha_hora=r["fecha_hora"],
                    usuario_operador=r["usuario_operador"],
                    id_registro_afectado=r["id_registro_afectado"],
                    motivo_modificacion=r["motivo_modificacion"] or "Sin justificación detallada",
                    cambios_resumen=texto_cambios,
                    snapshot_previo=prev,
                    snapshot_nuevo=new,
                )
            )
        return historial

    @staticmethod
    def _deducir_tipo_caso(
        estamento: str, cedula: Optional[str], motivo: Optional[str]
    ) -> ReviewCaseType:
        """Deduce el tipo de discrepancia determinista."""
        motivo_upper = (motivo or "").upper()
        if "CEDULA" in motivo_upper or "FORMATO_DUDOSO" in motivo_upper:
            return ReviewCaseType.CONFLICTO_CEDULA
        if not cedula and ("IDENTIDAD" in motivo_upper or "PERSONA" in motivo_upper):
            return ReviewCaseType.IDENTIDAD_NO_RESUELTA
        if (
            estamento == "DESCONOCIDO"
            or not estamento
            or "CATEGORIA" in motivo_upper
            or "ESTAMENTO" in motivo_upper
        ):
            return ReviewCaseType.ESTAMENTO_NO_RESUELTO
        return ReviewCaseType.DATOS_INCONSISTENTES
