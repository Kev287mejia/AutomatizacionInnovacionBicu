"""
app.audit.history_manager

Gestor inmutable del historial de ejecuciones y generador de manifiestos humanos (Fase 10).
Almacena evidencias estructuradas en logs/executions/<execution_id>.json y resúmenes legibles
en docs/audit/<execution_id>.md, garantizando inmutabilidad lógica sin bases de datos (Reglas 2, 12, 13 y 30).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.audit.audit_logger import get_logger
from app.audit.models import ManifiestoEjecucionCompleto

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
EXECUTIONS_DIR = BASE_DIR / "logs" / "executions"
AUDIT_DOCS_DIR = BASE_DIR / "docs" / "audit"


class HistoryManager:
    """Administrador de persistencia del historial de auditoría de ejecuciones."""

    def __init__(
        self,
        carpeta_ejecuciones: Path = EXECUTIONS_DIR,
        carpeta_docs: Path = AUDIT_DOCS_DIR,
    ):
        self.carpeta_ejecuciones = carpeta_ejecuciones
        self.carpeta_docs = carpeta_docs
        self.carpeta_ejecuciones.mkdir(parents=True, exist_ok=True)
        self.carpeta_docs.mkdir(parents=True, exist_ok=True)

    def guardar_ejecucion(
        self,
        manifiesto: ManifiestoEjecucionCompleto,
        sobrescribir: bool = False,
    ) -> Path:
        """
        Persiste el manifiesto completo de ejecución de forma inmutable en logs/executions/.
        También genera el resumen humano en Markdown en docs/audit/.

        Args:
            manifiesto: Modelo ManifiestoEjecucionCompleto verificado.
            sobrescribir: False por defecto para proteger la inmutabilidad histórica (Regla 12).

        Returns:
            Ruta del archivo JSON generado.
        """
        archivo_json = self.carpeta_ejecuciones / f"{manifiesto.execution_id}.json"

        if archivo_json.exists() and not sobrescribir:
            msg = f"Violación de inmutabilidad: La ejecución {manifiesto.execution_id} ya existe en el historial."
            logger.error(msg)
            raise FileExistsError(msg)

        # 1. Persistir JSON estructurado
        data = manifiesto.model_dump(mode="json")
        with open(archivo_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Historial de ejecución persistido exitosamente en: {archivo_json.name}")

        # 2. Generar representación humana en Markdown (Regla 30)
        self._generar_resumen_markdown(manifiesto)

        return archivo_json

    def guardar_manifiesto(
        self,
        manifiesto: ManifiestoEjecucionCompleto,
        permitir_sobrescribir: bool = False,
    ) -> Path:
        """Alias de compatibilidad para guardar_ejecucion."""
        return self.guardar_ejecucion(manifiesto, sobrescribir=permitir_sobrescribir)

    def _generar_resumen_markdown(self, m: ManifiestoEjecucionCompleto) -> Path:
        """Genera el manifiesto legible para humanos en docs/audit/<execution_id>.md."""
        archivo_md = self.carpeta_docs / f"{m.execution_id}.md"

        filas_inputs = "\n".join(
            f"| `{inp.nombre}` | {inp.tipo} | {inp.tamano_bytes:,} B | `{inp.sha256[:16]}...` |"
            for inp in m.inputs
        ) or "| *(Sin archivos físicos de entrada registrados)* | - | - | - |"

        filas_outputs = "\n".join(
            f"| `{out.nombre}` | {out.matriz or '-'} | {out.registros_generados} | {out.tamano_bytes:,} B | `{out.sha256[:16]}...` |"
            for out in m.outputs
        ) or "| *(Sin entregables generados en disco)* | - | - | - | - |"

        filas_trazas = "\n".join(
            f"| `{t.id_participacion[:8]}...` | {t.categoria_origen} | {t.matriz_destino} | {t.subtipo_institucional} | **{t.estado_operativo}** | {t.archivo_exportado or '-'} (Fila {t.fila_exportada or '-'}) |"
            for t in m.trazabilidad_participaciones[:25]
        )
        if len(m.trazabilidad_participaciones) > 25:
            filas_trazas += f"\n| ... y {len(m.trazabilidad_participaciones) - 25} trazas adicionales | | | | | |"

        filas_tablas = "\n".join(
            f"| {mid} | `{t.nombre_tabla}` | `{t.ref_antes}` | `{t.ref_despues}` | **{t.resultado}** |"
            for mid, t in m.auditoria_tablas.items()
        )

        filas_formulas = "\n".join(
            f"| {f.matriz} | Col {f.columna} ({f.nombre_columna}) | `{f.formula_esperada}` | {f.cantidad_verificada} | **{f.resultado}** |"
            for f in m.auditoria_formulas
        )

        filas_riesgos = "\n".join(
            f"| `{r.codigo_riesgo}` | {r.descripcion} | {r.impacto} | **{r.mitigacion_o_estado}** |"
            for r in m.riesgos_documentados
        ) or "| *(Ningún riesgo formal registrado)* | - | - | - |"

        contenido_md = f"""# Manifiesto Institucional de Ejecución — Auditoría Formal

**Execution ID:** `{m.execution_id}`  
**Estado:** **{m.estado.value}**  
**Modo:** `{m.modo_ejecucion}`  
**Fecha de Inicio:** `{m.timestamp_inicio}`  
**Fecha de Fin:** `{m.timestamp_fin or 'En curso / Interrumpida'}`  
**Versión del Sistema:** `{m.version_sistema}`  

---

## 1. Reproducibilidad Técnica y Entorno
* **Python:** `{m.entorno.version_python}`
* **Plataforma OS:** `{m.entorno.plataforma_os}`
* **Configuración SHA-256:** `{m.entorno.hash_configuracion}`
* **Dependencias Clave:**
{json.dumps(m.entorno.dependencias_clave, indent=2)}

---

## 2. Archivos de Entrada Auditados
| Archivo | Tipo | Tamaño | SHA-256 (Prefijo) |
| :--- | :--- | :--- | :--- |
{filas_inputs}

---

## 3. Entregables Oficiales Generados
| Archivo de Salida | Matriz | Filas Escritas | Tamaño | SHA-256 (Prefijo) |
| :--- | :--- | :--- | :--- | :--- |
{filas_outputs}

---

## 4. Consistencia Numérica e Invariantes
* **Total Participaciones Entrada:** {m.total_participaciones_entrada}
* **Total Participaciones Enrutadas:** {m.total_participaciones_enrutadas}
* **Distribución por Matriz:**
{json.dumps(m.conteo_por_matriz, indent=2)}
* **Estados Operativos de Control:**
{json.dumps(m.conteo_estados_operativos, indent=2)}
* **Invariantes Matemáticas:**
{json.dumps(m.invariantes, indent=2)}

---

## 5. Auditoría de Integridad M5 (Cero Destrucción)
* **Registros Históricos Previos:** {m.auditoria_m5.registros_historicos_antes}
* **Registros Históricos Confirmados:** {m.auditoria_m5.registros_historicos_preservados}
* **Nuevos Beneficiarios:** {m.auditoria_m5.registros_nuevos}
* **Celdas Comparadas Celda por Celda:** {m.auditoria_m5.celdas_comparadas}
* **Diferencias:** {m.auditoria_m5.diferencias}
* **Dictamen Cero Destrucción:** **{'CUMPLIDO' if m.auditoria_m5.resultado_cero_destruccion else 'VIOLADO'}**

---

## 6. Auditoría de Tablas Estructuradas (Tabla1)
| Matriz | Tabla | Ref Antes | Ref Después | Estado |
| :--- | :--- | :--- | :--- | :--- |
{filas_tablas}

---

## 7. Auditoría de Fórmulas Críticas
| Matriz | Columna | Fórmula | Celdas Verificadas | Dictamen |
| :--- | :--- | :--- | :--- | :--- |
{filas_formulas}

---

## 8. Riesgos y Limitaciones Técnicas Documentadas
| Código | Descripción | Impacto | Estado |
| :--- | :--- | :--- | :--- |
{filas_riesgos}

---

## 9. Muestra de Trazabilidad por Participación (Cadena Extremo a Extremo)
| ID Participación | Categoría Origen | Destino | Subtipo | Estado | Salida Generada |
| :--- | :--- | :--- | :--- | :--- | :--- |
{filas_trazas}

---

*Documento autogenerado por el Motor de Auditoría y Trazabilidad de Fase 10.*
"""
        with open(archivo_md, "w", encoding="utf-8") as f:
            f.write(contenido_md)

        return archivo_md

    def obtener_ejecucion(self, execution_id: str) -> Optional[ManifiestoEjecucionCompleto]:
        """Recupera y deserializa una ejecución específica a partir de su execution_id."""
        archivo = self.carpeta_ejecuciones / f"{execution_id}.json"
        if not archivo.exists():
            return None
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ManifiestoEjecucionCompleto(**data)
        except Exception as e:
            logger.error(f"Error al leer ejecución {execution_id}: {e}")
            return None

    def listar_ejecuciones(self) -> List[Dict[str, Any]]:
        """
        Retorna la lista ordenada cronológicamente de todas las ejecuciones registradas.
        """
        archivos = sorted(self.carpeta_ejecuciones.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        resumenes = []
        for arch in archivos:
            try:
                with open(arch, "r", encoding="utf-8") as f:
                    data = json.load(f)
                resumenes.append({
                    "execution_id": data.get("execution_id", arch.stem),
                    "timestamp_inicio": data.get("timestamp_inicio"),
                    "timestamp_fin": data.get("timestamp_fin"),
                    "modo": data.get("modo_ejecucion"),
                    "estado": data.get("estado"),
                    "total_participaciones": data.get("total_participaciones_entrada", 0),
                    "total_enrutadas": data.get("total_participaciones_enrutadas", 0),
                    "archivo_historial": arch.name,
                })
            except Exception as e:
                logger.warning(f"No se pudo leer resumen de {arch.name}: {e}")
        return resumenes

    def obtener_ultima_ejecucion(self) -> Optional[ManifiestoEjecucionCompleto]:
        """Obtiene el manifiesto de la ejecución más reciente en disco."""
        archivos = sorted(self.carpeta_ejecuciones.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not archivos:
            return None
        return self.obtener_ejecucion(archivos[0].stem)
