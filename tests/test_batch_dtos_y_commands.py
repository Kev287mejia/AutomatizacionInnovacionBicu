"""tests.test_batch_dtos_y_commands

Suite de tests para los contratos del Subbloque 3.1:
  - batch_dtos.py: BatchArchivoResultadoDTO, BatchResultadoDTO, PipelineDesdeWordResultDTO
  - batch_commands.py: IngestarCarpetaWordCommand

Reglas:
- Cero imports de sqlite3, python-docx, openpyxl en este módulo.
- Verificar inmutabilidad del command (frozen=True).
- Verificar construcción y validación pydantic de cada DTO.
- Verificar invariantes de conteo en BatchResultadoDTO.
- Verificar documentación de GAP-3 (posibles duplicados = advertencia heurística).
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from app.application.dto.batch_dtos import (
    BatchArchivoResultadoDTO,
    BatchResultadoDTO,
    PipelineDesdeWordResultDTO,
)
from app.application.commands.batch_commands import IngestarCarpetaWordCommand
from app.application.dto.export_dtos import PoliticaExportacionRevision


# ===========================================================================
# Fixtures auxiliares
# ===========================================================================

@pytest.fixture
def archivo_aceptado() -> BatchArchivoResultadoDTO:
    return BatchArchivoResultadoDTO(
        nombre_archivo="Actividad_01.docx",
        ruta_archivo="/datos/Actividad_01.docx",
        estado="ACEPTADO",
        tipo_documento="INFORME_ACTIVIDAD",
        id_actividad="uuid-act-001",
        evidencias_registradas=2,
        calidad_estado="CONFORME",
        total_hallazgos_calidad=0,
        total_participaciones_enrutadas=0,
    )


@pytest.fixture
def archivo_rechazado() -> BatchArchivoResultadoDTO:
    return BatchArchivoResultadoDTO(
        nombre_archivo="Informe_Semanal.docx",
        ruta_archivo="/datos/Informe_Semanal.docx",
        estado="RECHAZADO",
        tipo_documento="INFORME_SEMANAL",
        motivo_rechazo="Tipo INFORME_SEMANAL no genera actividad.",
    )


@pytest.fixture
def archivo_fallido() -> BatchArchivoResultadoDTO:
    return BatchArchivoResultadoDTO(
        nombre_archivo="Corrupto.docx",
        ruta_archivo="/datos/Corrupto.docx",
        estado="FALLIDO",
        errores=["PackageNotFoundError: archivo no es un ZIP válido."],
    )


# ===========================================================================
# Tests: BatchArchivoResultadoDTO
# ===========================================================================

class TestBatchArchivoResultadoDTO:

    def test_construccion_aceptado_minimo(self):
        """DTO se construye correctamente para archivo aceptado."""
        dto = BatchArchivoResultadoDTO(
            nombre_archivo="Acto.docx",
            ruta_archivo="/ruta/Acto.docx",
            estado="ACEPTADO",
        )
        assert dto.estado == "ACEPTADO"
        assert dto.id_actividad is None
        assert dto.tipo_documento is None
        assert dto.evidencias_registradas == 0
        assert dto.advertencias == []
        assert dto.errores == []
        assert dto.posible_duplicado_advertido is False

    def test_construccion_rechazado_con_motivo(self, archivo_rechazado):
        """DTO de rechazo contiene el motivo correctamente."""
        assert archivo_rechazado.estado == "RECHAZADO"
        assert archivo_rechazado.motivo_rechazo is not None
        assert "INFORME_SEMANAL" in archivo_rechazado.motivo_rechazo

    def test_construccion_fallido_con_errores(self, archivo_fallido):
        """DTO de fallo registra la lista de errores."""
        assert archivo_fallido.estado == "FALLIDO"
        assert len(archivo_fallido.errores) == 1
        assert "ZIP" in archivo_fallido.errores[0]

    def test_estado_invalido_falla_validacion(self):
        """Pydantic rechaza estados no permitidos."""
        with pytest.raises(ValidationError):
            BatchArchivoResultadoDTO(
                nombre_archivo="Acto.docx",
                ruta_archivo="/ruta/Acto.docx",
                estado="INVALIDO",  # no existe en el Literal
            )

    def test_evidencias_no_negativas(self):
        """evidencias_registradas no puede ser negativo."""
        with pytest.raises(ValidationError):
            BatchArchivoResultadoDTO(
                nombre_archivo="Acto.docx",
                ruta_archivo="/ruta/Acto.docx",
                estado="ACEPTADO",
                evidencias_registradas=-1,
            )

    def test_gap3_advertencia_no_bloquea(self):
        """GAP-3: posible duplicado se registra pero no bloquea ni cambia el estado."""
        dto = BatchArchivoResultadoDTO(
            nombre_archivo="Repetido.docx",
            ruta_archivo="/datos/Repetido.docx",
            estado="ACEPTADO",  # estado sigue siendo ACEPTADO
            id_actividad="uuid-dup",
            advertencias=["[GAP-3] Posible duplicado heurístico: nombre ya visto en este lote."],
            posible_duplicado_advertido=True,
        )
        assert dto.estado == "ACEPTADO"
        assert dto.posible_duplicado_advertido is True
        assert len(dto.advertencias) == 1

    def test_frozen_no_permite_mutacion(self, archivo_aceptado):
        """BatchArchivoResultadoDTO es inmutable (frozen=True)."""
        with pytest.raises((TypeError, ValueError)):
            archivo_aceptado.estado = "FALLIDO"

    def test_participaciones_cero_es_valido(self):
        """0 participaciones enrutadas es comportamiento esperado en flujo Word sin nominales."""
        dto = BatchArchivoResultadoDTO(
            nombre_archivo="SinNominales.docx",
            ruta_archivo="/datos/SinNominales.docx",
            estado="ACEPTADO",
            total_participaciones_enrutadas=0,  # esperado y válido
            id_actividad="uuid-sin-nominales",
        )
        assert dto.total_participaciones_enrutadas == 0


# ===========================================================================
# Tests: PipelineDesdeWordResultDTO
# ===========================================================================

class TestPipelineDesdeWordResultDTO:

    def test_construccion_exitosa_minima(self):
        """DTO se construye para flujo exitoso."""
        dto = PipelineDesdeWordResultDTO(
            nombre_archivo="Actividad.docx",
            exitoso=True,
            id_actividad="uuid-001",
            ingesta_exitosa=True,
            pipeline_ejecutado=True,
            calidad_estado="CONFORME",
            tipo_documento="INFORME_ACTIVIDAD",
        )
        assert dto.exitoso is True
        assert dto.id_actividad == "uuid-001"
        assert dto.pipeline_ejecutado is True
        assert dto.total_participaciones == 0  # default

    def test_construccion_ingesta_fallida(self):
        """DTO refleja fallo de ingesta con pipeline no ejecutado."""
        dto = PipelineDesdeWordResultDTO(
            nombre_archivo="Invalido.docx",
            exitoso=False,
            ingesta_exitosa=False,
            motivo_rechazo="Extracción sin datos mínimos.",
        )
        assert dto.exitoso is False
        assert dto.pipeline_ejecutado is False
        assert dto.id_actividad is None
        assert dto.calidad_estado is None

    def test_participaciones_cero_es_esperado(self):
        """0 participaciones es comportamiento normal en flujo Word."""
        dto = PipelineDesdeWordResultDTO(
            nombre_archivo="Actividad.docx",
            exitoso=True,
            ingesta_exitosa=True,
            pipeline_ejecutado=True,
            total_participaciones=0,  # correcto
        )
        assert dto.total_participaciones == 0

    def test_frozen_inmutabilidad(self):
        """PipelineDesdeWordResultDTO es inmutable."""
        dto = PipelineDesdeWordResultDTO(
            nombre_archivo="Actividad.docx",
            exitoso=True,
        )
        with pytest.raises((TypeError, ValueError)):
            dto.exitoso = False


# ===========================================================================
# Tests: BatchResultadoDTO
# ===========================================================================

class TestBatchResultadoDTO:

    def test_construccion_batch_minima(self):
        """BatchResultadoDTO se construye correctamente en mínimo."""
        dto = BatchResultadoDTO(
            batch_id="batch-uuid-001",
            carpeta_origen="/datos/actividades",
            timestamp_inicio="2026-09-18T21:00:00",
        )
        assert dto.batch_id == "batch-uuid-001"
        assert dto.archivos_encontrados == 0
        assert dto.archivos_aceptados == 0
        assert dto.archivos_rechazados == 0
        assert dto.archivos_fallidos == 0
        assert dto.actividades_creadas == []
        assert dto.invariante_ok is True
        assert dto.dry_run is False
        assert dto.exportacion_ejecutada is False

    def test_actividades_creadas_es_lista(self):
        """actividades_creadas contiene los UUIDs correctamente."""
        dto = BatchResultadoDTO(
            batch_id="batch-002",
            carpeta_origen="/datos",
            timestamp_inicio="2026-09-18T21:00:00",
            actividades_creadas=["uuid-1", "uuid-2", "uuid-3"],
            archivos_aceptados=3,
            archivos_encontrados=4,
            archivos_rechazados=1,
        )
        assert len(dto.actividades_creadas) == 3

    def test_gap3_lista_posibles_duplicados(self):
        """actividades_con_posible_duplicado se registra sin afectar invariante_ok."""
        dto = BatchResultadoDTO(
            batch_id="batch-003",
            carpeta_origen="/datos",
            timestamp_inicio="2026-09-18T21:00:00",
            actividades_creadas=["uuid-dup"],
            actividades_con_posible_duplicado=["uuid-dup"],
            advertencias_lote=["[GAP-3] 1 archivo con nombre heurísticamente duplicado."],
            invariante_ok=True,  # sigue True (no hubo errores FALLIDOS)
        )
        assert len(dto.actividades_con_posible_duplicado) == 1
        assert dto.invariante_ok is True  # no se cambia por GAP-3

    def test_invariante_ok_false_si_hay_fallidos(self):
        """invariante_ok debe ser False cuando hay archivos FALLIDOS."""
        dto = BatchResultadoDTO(
            batch_id="batch-004",
            carpeta_origen="/datos",
            timestamp_inicio="2026-09-18T21:00:00",
            archivos_fallidos=1,
            invariante_ok=False,
            errores_criticos=["Archivo Corrupto.docx: PackageNotFoundError."],
        )
        assert dto.invariante_ok is False
        assert len(dto.errores_criticos) == 1

    def test_dry_run_no_tiene_exportacion(self):
        """En dry_run, exportacion_ejecutada debe ser False."""
        dto = BatchResultadoDTO(
            batch_id="batch-dry",
            carpeta_origen="/datos",
            timestamp_inicio="2026-09-18T21:00:00",
            dry_run=True,
            exportacion_ejecutada=False,
            matrices_generadas={},
            manifest_path=None,
        )
        assert dto.dry_run is True
        assert dto.exportacion_ejecutada is False
        assert dto.matrices_generadas == {}
        assert dto.manifest_path is None

    def test_matrices_generadas_dict(self):
        """matrices_generadas contiene rutas por clave de matriz."""
        dto = BatchResultadoDTO(
            batch_id="batch-005",
            carpeta_origen="/datos",
            timestamp_inicio="2026-09-18T21:00:00",
            exportacion_ejecutada=True,
            carpeta_batch_salida="output/batch-005",
            matrices_generadas={
                "matriz_1": "output/batch-005/Matriz_1_Consolidado_Actividades.xlsx",
                "matriz_2": "output/batch-005/Matriz_2_Estudiantes.xlsx",
                "matriz_3": "output/batch-005/Matriz_3_Academicos_Administrativos.xlsx",
                "matriz_4": "output/batch-005/Matriz_4_Colaboradores.xlsx",
                "matriz_5": "output/batch-005/Matriz_5_Protagonistas_Beneficiados.xlsx",
            },
        )
        assert len(dto.matrices_generadas) == 5
        assert "matriz_5" in dto.matrices_generadas

    def test_resultados_por_archivo(self, archivo_aceptado, archivo_rechazado, archivo_fallido):
        """resultados_por_archivo contiene los DTOs individuales."""
        dto = BatchResultadoDTO(
            batch_id="batch-006",
            carpeta_origen="/datos",
            timestamp_inicio="2026-09-18T21:00:00",
            archivos_encontrados=3,
            archivos_aceptados=1,
            archivos_rechazados=1,
            archivos_fallidos=1,
            invariante_ok=False,
            resultados_por_archivo=[archivo_aceptado, archivo_rechazado, archivo_fallido],
        )
        assert len(dto.resultados_por_archivo) == 3
        estados = {r.estado for r in dto.resultados_por_archivo}
        assert "ACEPTADO" in estados
        assert "RECHAZADO" in estados
        assert "FALLIDO" in estados


# ===========================================================================
# Tests: IngestarCarpetaWordCommand
# ===========================================================================

class TestIngestarCarpetaWordCommand:

    def test_construccion_minima(self, tmp_path):
        """Command se construye con solo carpeta_origen."""
        cmd = IngestarCarpetaWordCommand(carpeta_origen=tmp_path)
        assert cmd.carpeta_origen == tmp_path
        assert cmd.patron_glob == "*.docx"
        assert cmd.recursivo is False
        assert cmd.exportar_matrices is True
        assert cmd.carpeta_salida == "output"
        assert cmd.dry_run is False
        assert cmd.advertir_posibles_duplicados is True
        assert cmd.politica_revision == PoliticaExportacionRevision.EXPORTAR_CON_OBSERVACION

    def test_frozen_inmutable(self, tmp_path):
        """IngestarCarpetaWordCommand es inmutable (frozen=True)."""
        cmd = IngestarCarpetaWordCommand(carpeta_origen=tmp_path)
        with pytest.raises((TypeError, ValueError)):
            cmd.dry_run = True

    def test_dry_run_true(self, tmp_path):
        """Command acepta dry_run=True."""
        cmd = IngestarCarpetaWordCommand(carpeta_origen=tmp_path, dry_run=True)
        assert cmd.dry_run is True

    def test_politica_revision_enum(self, tmp_path):
        """politica_revision acepta PoliticaExportacionRevision válida."""
        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=tmp_path,
            politica_revision=PoliticaExportacionRevision.RETENER_EN_CUARENTENA,
        )
        assert cmd.politica_revision == PoliticaExportacionRevision.RETENER_EN_CUARENTENA

    def test_advertir_posibles_duplicados_false(self, tmp_path):
        """advertir_posibles_duplicados puede desactivarse."""
        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=tmp_path,
            advertir_posibles_duplicados=False,
        )
        assert cmd.advertir_posibles_duplicados is False

    def test_gap3_no_bloquea_en_command(self, tmp_path):
        """El command nunca bloquea por GAP-3; solo lo informa."""
        # El command se construye aunque advertir_posibles_duplicados=True;
        # el bloqueo no existe a nivel de command.
        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=tmp_path,
            advertir_posibles_duplicados=True,
        )
        assert cmd.advertir_posibles_duplicados is True  # advertencia, nunca bloqueo

    def test_fixtures_test_only(self, tmp_path):
        """El command acepta el flag de fixtures para testing."""
        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=tmp_path,
            permitir_fixtures_test_only=True,
        )
        assert cmd.permitir_fixtures_test_only is True

    def test_carpeta_templates_opcional(self, tmp_path):
        """carpeta_templates es None por defecto (usa ruta institucional)."""
        cmd = IngestarCarpetaWordCommand(carpeta_origen=tmp_path)
        assert cmd.carpeta_templates is None

    def test_carpeta_salida_personalizada(self, tmp_path):
        """carpeta_salida puede ser personalizada."""
        cmd = IngestarCarpetaWordCommand(
            carpeta_origen=tmp_path,
            carpeta_salida="mi_output",
        )
        assert cmd.carpeta_salida == "mi_output"


# ===========================================================================
# Tests: Importabilidad desde __init__.py
# ===========================================================================

class TestImportabilidadDesdeInit:

    def test_import_batch_dtos_desde_paquete(self):
        """BatchArchivoResultadoDTO, BatchResultadoDTO, PipelineDesdeWordResultDTO
        son importables desde app.application.dto."""
        from app.application.dto import (
            BatchArchivoResultadoDTO as A,
            BatchResultadoDTO as B,
            PipelineDesdeWordResultDTO as C,
        )
        assert A is BatchArchivoResultadoDTO
        assert B is BatchResultadoDTO
        assert C is PipelineDesdeWordResultDTO

    def test_import_batch_command_desde_paquete(self):
        """IngestarCarpetaWordCommand es importable desde app.application.commands."""
        from app.application.commands import IngestarCarpetaWordCommand as CMD
        assert CMD is IngestarCarpetaWordCommand


# ===========================================================================
# Tests: Aislamiento Clean Architecture
# ===========================================================================

class TestAislamientoBatchDtos:

    def test_batch_dtos_no_importa_sqlite3(self):
        """batch_dtos.py no debe importar sqlite3."""
        import ast, pathlib
        src = pathlib.Path(
            "app/application/dto/batch_dtos.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                for name in names:
                    assert "sqlite3" not in name, "batch_dtos importa sqlite3"
                assert "sqlite3" not in module, "batch_dtos importa sqlite3"

    def test_batch_dtos_no_importa_docx(self):
        """batch_dtos.py no debe importar python-docx."""
        import ast, pathlib
        src = pathlib.Path(
            "app/application/dto/batch_dtos.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                names = [a.name for a in getattr(node, "names", [])]
                for n in [module] + names:
                    assert "docx" not in n.lower(), "batch_dtos importa docx"

    def test_batch_dtos_no_importa_openpyxl(self):
        """batch_dtos.py no debe importar openpyxl."""
        import ast, pathlib
        src = pathlib.Path(
            "app/application/dto/batch_dtos.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                names = [a.name for a in getattr(node, "names", [])]
                for n in [module] + names:
                    assert "openpyxl" not in n.lower(), "batch_dtos importa openpyxl"

    def test_batch_command_no_importa_sqlite3(self):
        """batch_commands.py no debe importar sqlite3."""
        import ast, pathlib
        src = pathlib.Path(
            "app/application/commands/batch_commands.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                names = [a.name for a in getattr(node, "names", [])]
                for n in [module] + names:
                    assert "sqlite3" not in n, "batch_commands importa sqlite3"
