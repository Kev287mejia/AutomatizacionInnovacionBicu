"""
app.word_consolidator.ui.services.error_translator

Traductor de Excepciones Técnicas a Mensajes Accionables Institucionales (Fase 14.9).
Convierte volcados de pila y errores del motor de consolidación en explicaciones
claras, amigables y con instrucciones precisas para el usuario de BICU.
"""

from pathlib import Path
import re
import traceback
from typing import Dict, List, Optional, Tuple

from app.word_consolidator.pipeline import (
    ArchivoMatrizInvalidoError,
    ErrorIntegridadArchivo,
    EstructuraMatrizInvalidaError,
    MatricesFaltantesError,
    MatrixPipelineError,
    MatrizDuplicadaError,
)

NOMBRES_OFICIALES_MATRICES: Dict[str, str] = {
    "M1": "M1 — Consolidado de Actividades",
    "M2": "M2 — Estudiantes",
    "M3": "M3 — Académicos y Administrativos",
    "M4": "M4 — Colaboradores",
    "M5": "M5 — Protagonistas / Beneficiados",
}


class ErrorInstitucionalInfo:
    """Contenedor de información de error formateada para la interfaz de usuario."""

    def __init__(
        self,
        titulo: str,
        mensaje_principal: str,
        accion_sugerida: str,
        detalle_tecnico: str,
        es_bloqueante: bool = True,
    ):
        self.titulo = titulo
        self.mensaje_principal = mensaje_principal
        self.accion_sugerida = accion_sugerida
        self.detalle_tecnico = detalle_tecnico
        self.es_bloqueante = es_bloqueante

    def mensaje_completo(self) -> str:
        """Formatea el mensaje en texto legible para un cuadro de diálogo o tarjeta."""
        partes = [
            f"⚠️ {self.titulo.upper()}",
            "",
            self.mensaje_principal,
            "",
            f"👉 Acción sugerida: {self.accion_sugerida}",
        ]
        return "\n".join(partes)


class ErrorTranslator:
    """
    Traduce cualquier excepción de Python o del pipeline a una estructura
    ErrorInstitucionalInfo con redacción formal y orientada al usuario.
    """

    @classmethod
    def traducir(cls, ex: Exception) -> ErrorInstitucionalInfo:
        """Traduce una excepción a un ErrorInstitucionalInfo accionable."""
        detalle_tec = "".join(traceback.format_exception(type(ex), ex, ex.__traceback__))

        # 1. Matrices faltantes
        if isinstance(ex, MatricesFaltantesError):
            raw_msg = str(ex)
            # Buscar códigos M1..M5 en el mensaje
            faltantes = [m for m in ["M1", "M2", "M3", "M4", "M5"] if f"'{m}'" in raw_msg or f"{m}" in raw_msg]
            if not faltantes:
                faltantes_str = "Una o más matrices oficiales requeridas."
            else:
                faltantes_str = "\n".join(f"• {NOMBRES_OFICIALES_MATRICES.get(m, m)}" for m in sorted(faltantes))

            return ErrorInstitucionalInfo(
                titulo="Matrices Oficiales Incompletas",
                mensaje_principal=(
                    "El sistema requiere las cinco (5) matrices oficiales de BICU para realizar la consolidación.\n\n"
                    f"Faltan por identificar:\n{faltantes_str}"
                ),
                accion_sugerida="Seleccione o arrastre los archivos Excel correspondientes a las matrices faltantes y vuelva a validar.",
                detalle_tecnico=detalle_tec,
                es_bloqueante=True,
            )

        # 2. Matrices duplicadas
        if isinstance(ex, MatrizDuplicadaError):
            return ErrorInstitucionalInfo(
                titulo="Archivos Duplicados para la Misma Matriz",
                mensaje_principal=(
                    "Se detectaron múltiples archivos que coinciden con la misma estructura oficial de BICU.\n\n"
                    f"Detalle: {str(ex)}"
                ),
                accion_sugerida="Asegúrese de seleccionar un único archivo por cada matriz (M1 a M5). Retire las copias o versiones duplicadas.",
                detalle_tecnico=detalle_tec,
                es_bloqueante=True,
            )

        # 3. Estructura de matriz inválida
        if isinstance(ex, EstructuraMatrizInvalidaError):
            return ErrorInstitucionalInfo(
                titulo="Estructura de Matriz No Reconocida",
                mensaje_principal=(
                    "Uno de los archivos seleccionados no coincide con la estructura de columnas oficial de BICU.\n\n"
                    f"Detalle técnico: {str(ex)}"
                ),
                accion_sugerida=(
                    "Verifique que el archivo provenga de la plantilla oficial de BICU sin columnas "
                    "eliminadas, renombradas o insertadas en la fila 1 de encabezados."
                ),
                detalle_tecnico=detalle_tec,
                es_bloqueante=True,
            )

        # 4. Archivo inaccesible, dañado o no es Excel
        if isinstance(ex, ArchivoMatrizInvalidoError):
            return ErrorInstitucionalInfo(
                titulo="Archivo No Válido o Inaccesible",
                mensaje_principal=(
                    "No se pudo leer uno de los archivos seleccionados.\n\n"
                    f"Detalle: {str(ex)}"
                ),
                accion_sugerida="Compruebe que el archivo exista en disco, sea un libro Excel (.xlsx / .xlsm) válido y no esté corrupto.",
                detalle_tecnico=detalle_tec,
                es_bloqueante=True,
            )

        # 5. Error de integridad criptográfica SHA-256
        if isinstance(ex, ErrorIntegridadArchivo):
            return ErrorInstitucionalInfo(
                titulo="Alerta Crítica de Integridad",
                mensaje_principal=(
                    "Uno de los archivos Excel fue modificado externamente por otro programa o usuario "
                    "mientras la consolidación estaba en progreso.\n\n"
                    f"Detalle: {str(ex)}"
                ),
                accion_sugerida="No guarde ni edite los archivos Excel fuente mientras el sistema realiza el procesamiento institucional.",
                detalle_tecnico=detalle_tec,
                es_bloqueante=True,
            )

        # 6. Archivo Word bloqueado (PermissionError en Windows) o permisos insuficientes (Fase 16.7-B)
        if isinstance(ex, PermissionError):
            raw_msg = str(ex)
            archivo_afectado: Optional[str] = None

            # Intentar identificar el archivo afectado mediante ex.filename o extracción del mensaje
            if getattr(ex, "filename", None):
                archivo_afectado = Path(ex.filename).name
            else:
                matches = re.findall(r"['\"](.*?)['\"]", raw_msg)
                for m in matches:
                    p = Path(m)
                    if p.suffix.lower() in (".docx", ".xlsx", ".xlsm", ".pdf", ".tmp", ".log") or "\\" in m or "/" in m:
                        archivo_afectado = p.name
                        break

            # Determinar si es bloqueo por archivo en uso vs problema de permisos
            # WinError 32: ERROR_SHARING_VIOLATION (archivo en uso por otro proceso)
            es_archivo_en_uso = (
                "32" in raw_msg
                or "utilizado por otro proceso" in raw_msg.lower()
                or "being used by another process" in raw_msg.lower()
                or "abierto" in raw_msg.lower()
                or (archivo_afectado is not None and archivo_afectado.lower().endswith(".docx"))
            )

            es_permiso_denegado = (
                (
                    "5" in raw_msg
                    or "access is denied" in raw_msg.lower()
                    or "acceso denegado" in raw_msg.lower()
                    or "permission denied" in raw_msg.lower()
                )
                and not es_archivo_en_uso
            )

            if es_permiso_denegado:
                return ErrorInstitucionalInfo(
                    titulo="Permisos Insuficientes en Carpeta o Archivo",
                    mensaje_principal="No se poseen permisos de escritura suficientes en la carpeta o ubicación de destino.",
                    accion_sugerida="Verifique los permisos de escritura en la carpeta de salida seleccionada o elija una carpeta con permisos válidos antes de volver a ejecutar.",
                    detalle_tecnico=detalle_tec,
                    es_bloqueante=True,
                )

            # Caso archivo bloqueado por Word u otro programa
            if archivo_afectado:
                msg_principal = (
                    f"No se pudo guardar el informe '{archivo_afectado}' porque el archivo está actualmente abierto "
                    "o bloqueado por otra aplicación."
                )
            else:
                msg_principal = (
                    "No se pudo guardar el informe porque el archivo está actualmente abierto "
                    "o bloqueado por otra aplicación."
                )

            return ErrorInstitucionalInfo(
                titulo="Archivo Bloqueado por Microsoft Word u Otro Programa",
                mensaje_principal=msg_principal,
                accion_sugerida="Cierre el documento en Microsoft Word si tiene abierto el informe anterior (Cierre Microsoft Word y vuelva a presionar 'Ejecutar Consolidación').",
                detalle_tecnico=detalle_tec,
                es_bloqueante=True,
            )

        # 7. FileNotFoundError
        if isinstance(ex, FileNotFoundError):
            return ErrorInstitucionalInfo(
                titulo="Archivo o Carpeta No Encontrada",
                mensaje_principal=f"No se localizó la ruta física especificada: {str(ex)}",
                accion_sugerida="Compruebe que las rutas seleccionadas no hayan sido movidas o eliminadas.",
                detalle_tecnico=detalle_tec,
                es_bloqueante=True,
            )

        # 8. Errores genéricos del pipeline u otros errores inesperados
        return ErrorInstitucionalInfo(
            titulo="Error Operativo Inesperado",
            mensaje_principal=(
                "Ocurrió un error no previsto durante la ejecución del proceso.\n\n"
                f"Tipo de error: {type(ex).__name__}\n"
                f"Descripción: {str(ex)}"
            ),
            accion_sugerida=(
                "Revise que los archivos fuente sean válidos. Si el problema persiste, contacte a soporte "
                "técnico institucional proporcionando el reporte de auditoría generado."
            ),
            detalle_tecnico=detalle_tec,
            es_bloqueante=True,
        )
