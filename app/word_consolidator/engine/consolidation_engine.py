"""
app.word_consolidator.engine.consolidation_engine

Motor de Consolidación Institucional para el Generador Word (Fase 14.4).
Toma los datos extraídos de las 5 matrices oficiales (M1 agregada y M2..M5 nominales)
filtrados por período y construye una estructura de dominio consolidada en memoria.

Principios rectores inviolables:
1. No sobrescribir M1 con M2–M5: se conservan ambas fuentes separadas e intactas.
2. Clave de negocio para actividades: (Nombre_Actividad_Normalizado, Sede_Normalizada, Fecha_Evento).
3. Relación de dominio: Actividad -> Participaciones (por estamento).
4. Reutilización canónica del dominio existente: Person, Participation, IdentityResolver.
5. Distinción rigurosa:
   - Asistencia bruta (total registros de participación)
   - Personas únicas (individuos distintos tras resolución de identidad)
   - Recurrencia (participaciones adicionales de la misma persona en el período)
6. Preservación estricta de históricos: los 32 registros de M5 permanecen fuera del período.
7. Desacoplamiento total: no abre ni modifica archivos Excel directamente.
"""

from datetime import date, datetime
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid

from pydantic import BaseModel, Field

from app.core.constants.participant_types import CategoriaParticipacion, NivelConfianzaIdentidad
from app.core.models.person import Person
from app.core.models.participation import Participation
from app.matching.person_matcher import PersonMatcher
from app.matching.identity_resolver import IdentityResolver, IdentityResolutionResult
from app.word_consolidator.models import (
    ConjuntoMatricesLeidas,
    DiscrepanciaItem,
    FilaLeidaM1,
    FilaLeidaNominal,
    PeriodoConsolidacion,
    RegistroFuenteArchivo,
    ResultadoFiltradoPeriodo,
)
from app.word_consolidator.readers.period_filter import PeriodFilter


class ParticipacionConsolidada(BaseModel):
    """
    Representa una participación individual en una actividad consolidada.
    Preserva todos los atributos nominales de origen y la trazabilidad exacta de coordenadas.
    """
    id_participacion: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único técnico de la participación (UUID v4)."
    )
    id_actividad: str = Field(..., description="Identificador unívoco de la actividad vinculada.")
    id_persona: str = Field(..., description="Identificador canónico de la persona.")
    nombre_apellidos: str = Field(..., description="Nombre completo tal como figura en la matriz.")
    identificacion: Optional[str] = Field(default=None, description="Cédula o carné (verbatim).")
    sexo_original: Optional[str] = Field(default=None, description="Valor textual de sexo en la celda.")
    sexo_normalizado: Optional[str] = Field(default=None, description="Sexo normalizado (FEMENINO / MASCULINO).")
    categoria: CategoriaParticipacion = Field(..., description="Estamento institucional del participante.")
    carrera: Optional[str] = Field(default=None, description="Carrera universitaria reportada.")
    cargo: Optional[str] = Field(default=None, description="Cargo institucional reportado.")
    entidad: Optional[str] = Field(default=None, description="Entidad pública, privada u ONG reportada.")
    departamento: Optional[str] = Field(default=None, description="Departamento geográfico reportado.")
    municipio: Optional[str] = Field(default=None, description="Municipio geográfico reportado.")
    comunidad: Optional[str] = Field(default=None, description="Comunidad geográfica reportada.")
    matriz_origen: str = Field(..., description="Código de la matriz origen (M2, M3, M4, M5).")
    hoja: str = Field(..., description="Nombre de la hoja de cálculo de origen.")
    fila: int = Field(..., ge=2, description="Número de fila física en el libro Excel.")
    actividad_asociada: str = Field(..., description="Nombre de la actividad reportada en la fila.")
    sede: str = Field(..., description="Sede universitaria de la actividad.")
    trazabilidad: Dict[str, Any] = Field(default_factory=dict, description="Metadatos técnicos de trazabilidad.")
    fila_nominal_origen: Optional[FilaLeidaNominal] = Field(default=None, description="Fila nominal completa leída.")
    programa: Optional[str] = Field(default=None, description="Programa institucional reportado en la fila nominal.")

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


class TotalesM1(BaseModel):
    """
    Totales agregados declarados formalmente en Matriz 1 para una actividad.
    """
    mujeres: int = Field(default=0, ge=0, description="Total de mujeres reportado en M1 (Columna Z).")
    varones: int = Field(default=0, ge=0, description="Total de varones reportado en M1 (Columna Y).")
    total: int = Field(default=0, ge=0, description="Total general reportado en M1 (Varones + Mujeres).")
    estudiantes_m: int = Field(default=0, ge=0, description="Estudiantes masculinos reportados en M1.")
    estudiantes_f: int = Field(default=0, ge=0, description="Estudiantes femeninos reportados en M1.")
    docentes_m: int = Field(default=0, ge=0, description="Docentes masculinos reportados en M1.")
    docentes_f: int = Field(default=0, ge=0, description="Docentes femeninos reportados en M1.")
    administrativos_m: int = Field(default=0, ge=0, description="Administrativos masculinos en M1.")
    administrativos_f: int = Field(default=0, ge=0, description="Administrativos femeninos en M1.")
    colaboradores_m: int = Field(default=0, ge=0, description="Colaboradores masculinos en M1.")
    colaboradores_f: int = Field(default=0, ge=0, description="Colaboradores femeninos en M1.")
    protagonistas_m: int = Field(default=0, ge=0, description="Beneficiarios masculinos en M1.")
    protagonistas_f: int = Field(default=0, ge=0, description="Beneficiarios femeninos en M1.")
    fila_m1: Optional[FilaLeidaM1] = Field(default=None, description="Instancia original de la fila M1.")

    model_config = {
        "validate_assignment": True,
    }

    @property
    def total_estudiantes(self) -> int:
        return self.estudiantes_m + self.estudiantes_f

    @property
    def total_docentes(self) -> int:
        return self.docentes_m + self.docentes_f

    @property
    def total_administrativos(self) -> int:
        return self.administrativos_m + self.administrativos_f

    @property
    def total_colaboradores(self) -> int:
        return self.colaboradores_m + self.colaboradores_f

    @property
    def total_protagonistas(self) -> int:
        return self.protagonistas_m + self.protagonistas_f


class TotalesNominales(BaseModel):
    """
    Totales agregados calculados matemáticamente a partir de las participaciones nominales (M2..M5).
    """
    mujeres: int = Field(default=0, ge=0, description="Participantes de sexo femenino calculados.")
    varones: int = Field(default=0, ge=0, description="Participantes de sexo masculino calculados.")
    total: int = Field(default=0, ge=0, description="Total de participantes nominales.")
    estudiantes: int = Field(default=0, ge=0, description="Total de estudiantes (M2).")
    docentes: int = Field(default=0, ge=0, description="Total de docentes (M3).")
    administrativos: int = Field(default=0, ge=0, description="Total de administrativos (M3).")
    no_docentes: int = Field(default=0, ge=0, description="Total de personal no docente (M3).")
    colaboradores: int = Field(default=0, ge=0, description="Total de colaboradores externos (M4).")
    beneficiarios: int = Field(default=0, ge=0, description="Total de protagonistas/beneficiarios (M5).")

    # Desglose cruzado por estamento y sexo
    estudiantes_f: int = Field(default=0, ge=0)
    estudiantes_m: int = Field(default=0, ge=0)
    docentes_f: int = Field(default=0, ge=0)
    docentes_m: int = Field(default=0, ge=0)
    administrativos_f: int = Field(default=0, ge=0)
    administrativos_m: int = Field(default=0, ge=0)
    no_docentes_f: int = Field(default=0, ge=0)
    no_docentes_m: int = Field(default=0, ge=0)
    colaboradores_f: int = Field(default=0, ge=0)
    colaboradores_m: int = Field(default=0, ge=0)
    beneficiarios_f: int = Field(default=0, ge=0)
    beneficiarios_m: int = Field(default=0, ge=0)

    model_config = {
        "validate_assignment": True,
    }


class ActividadConsolidada(BaseModel):
    """
    Representa una actividad institucional consolidada.
    Conserva fielmente la fuente agregada (M1) y el conjunto de participaciones nominales (M2..M5).
    """
    id_actividad: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador unívoco técnico de la actividad (UUID v4)."
    )
    clave_negocio: Tuple[str, str, Optional[str]] = Field(
        ...,
        description="Clave de negocio: (Nombre_Normalizado, Sede_Normalizada, Fecha_Evento_ISO)."
    )
    nombre_actividad: str = Field(..., description="Nombre formal o visible de la actividad.")
    sede: str = Field(..., description="Sede universitaria de realización.")
    fecha_evento: Optional[Union[date, str]] = Field(default=None, description="Fecha de realización reportada.")
    departamento: Optional[str] = Field(default=None, description="Departamento territorial.")
    municipio: Optional[str] = Field(default=None, description="Municipio territorial.")
    programa: Optional[str] = Field(default=None, description="Programa institucional responsable.")
    proyecto: Optional[str] = Field(default=None, description="Proyecto institucional vinculado.")
    eje: Optional[str] = Field(default=None, description="Eje o ámbito institucional.")
    tipo_evento: Optional[str] = Field(default=None, description="Tipo de evento institucional.")
    resultados: Optional[str] = Field(default=None, description="Resultados cualitativos alcanzados.")
    area_responsable: Optional[str] = Field(default=None, description="Área institucional responsable.")
    fuente_m1: Optional[FilaLeidaM1] = Field(default=None, description="Fila original leída de M1 si existe.")
    totales_m1: Optional[TotalesM1] = Field(default=None, description="Totales declarados formalmente en M1.")
    participaciones: List[ParticipacionConsolidada] = Field(
        default_factory=list,
        description="Listado completo de participaciones nominales asociadas a esta actividad."
    )
    totales_nominales: TotalesNominales = Field(
        default_factory=TotalesNominales,
        description="Totales agregados calculados desde las filas nominales."
    )
    total_asistencia_bruta: int = Field(default=0, ge=0, description="Total de asistencias en esta actividad.")
    total_personas_unicas: int = Field(default=0, ge=0, description="Total de personas únicas en esta actividad.")
    trazabilidad: Dict[str, Any] = Field(default_factory=dict, description="Metadatos técnicos de procedencia.")
    discrepancias: List[DiscrepanciaItem] = Field(
        default_factory=list,
        description="Discrepancias institucionales detectadas en esta actividad."
    )

    model_config = {
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }

    @property
    def estudiantes(self) -> List[ParticipacionConsolidada]:
        return [p for p in self.participaciones if p.categoria == CategoriaParticipacion.ESTUDIANTE]

    @property
    def docentes(self) -> List[ParticipacionConsolidada]:
        return [p for p in self.participaciones if p.categoria == CategoriaParticipacion.DOCENTE]

    @property
    def administrativos(self) -> List[ParticipacionConsolidada]:
        return [p for p in self.participaciones if p.categoria == CategoriaParticipacion.ADMINISTRATIVO]

    @property
    def no_docentes(self) -> List[ParticipacionConsolidada]:
        return [p for p in self.participaciones if p.categoria == CategoriaParticipacion.NO_DOCENTE]

    @property
    def colaboradores(self) -> List[ParticipacionConsolidada]:
        return [p for p in self.participaciones if p.categoria == CategoriaParticipacion.COLABORADOR]

    @property
    def beneficiarios(self) -> List[ParticipacionConsolidada]:
        return [
            p for p in self.participaciones
            if p.categoria in (CategoriaParticipacion.BENEFICIADO, CategoriaParticipacion.POBLADOR_GENERAL)
        ]


class ResultadoConsolidacion(BaseModel):
    """
    Resultado formal completo de la consolidación institucional para el período seleccionado.
    """
    periodo: PeriodoConsolidacion = Field(..., description="Definición formal del período consolidado.")
    actividades: List[ActividadConsolidada] = Field(default_factory=list, description="Actividades consolidadas.")
    total_actividades: int = Field(default=0, ge=0, description="Cantidad total de actividades consolidadas.")
    total_asistencia_bruta: int = Field(default=0, ge=0, description="Total de registros de asistencia en el período.")
    total_personas_unicas: int = Field(default=0, ge=0, description="Total de personas únicas netas en el período.")
    total_recurrencia: int = Field(default=0, ge=0, description="Participaciones recurrentes de personas ya contadas.")
    tasa_recurrencia: float = Field(default=0.0, ge=0.0, description="Tasa porcentual de recurrencia en el período.")
    personas_consolidadas: List[Person] = Field(default_factory=list, description="Personas consolidadas en dominio.")
    participaciones_consolidadas: List[Participation] = Field(default_factory=list, description="Participaciones en dominio.")
    resolucion_identidad: Optional[IdentityResolutionResult] = Field(default=None, description="Detalle del IdentityResolver.")
    nominales_historicos_fuera_periodo: List[FilaLeidaNominal] = Field(
        default_factory=list,
        description="Registros históricos conservados fuera del período (ej. las 32 filas de M5)."
    )
    actividades_fuera_periodo: List[FilaLeidaM1] = Field(
        default_factory=list,
        description="Actividades de M1 fuera del período."
    )
    fuentes: Dict[str, RegistroFuenteArchivo] = Field(
        default_factory=dict,
        description="Metadatos y hashes SHA-256 de las matrices procesadas."
    )
    discrepancias: List[DiscrepanciaItem] = Field(
        default_factory=list,
        description="Listado global de discrepancias institucionales detectadas en el período."
    )

    model_config = {
        "validate_assignment": True,
    }

    def obtener_actividad_por_id(self, id_actividad: str) -> Optional[ActividadConsolidada]:
        for act in self.actividades:
            if act.id_actividad == id_actividad:
                return act
        return None

    def obtener_actividad_por_clave(self, clave: Tuple[str, str, Optional[str]]) -> Optional[ActividadConsolidada]:
        for act in self.actividades:
            if act.clave_negocio == clave:
                return act
        return None


class ConsolidationEngine:
    """
    Motor de Consolidación Institucional de BICU.
    Toma los datos de entrada ya leídos y filtrados, y construye la estructura consolidada en memoria.
    No realiza lecturas ni modificaciones directas de archivos Excel.
    """

    @classmethod
    def normalizar_texto_actividad(cls, texto: Optional[str]) -> str:
        """Normaliza el texto de una actividad para comparación determinística."""
        if not texto:
            return ""
        return re.sub(r"\s+", " ", str(texto).strip().lower())

    @classmethod
    def normalizar_sede(cls, sede: Optional[str]) -> str:
        """Normaliza la denominación de la sede para comparación determinística."""
        if not sede:
            return "no especificada"
        s = re.sub(r"\s+", " ", str(sede).strip().lower())
        if "bilwi" in s:
            return "bilwi"
        if "bluefields" in s:
            return "bluefields"
        if "las minas" in s:
            return "las minas"
        if "el rama" in s or "rama" in s:
            return "el rama"
        return s

    @classmethod
    def normalizar_fecha_str(cls, fecha: Any) -> Optional[str]:
        """Normaliza un valor de fecha a cadena ISO (YYYY-MM-DD) o cadena limpia si no es convertible."""
        if fecha is None:
            return None
        d = PeriodFilter.normalizar_fecha(fecha)
        if d is not None:
            return d.isoformat()
        s = str(fecha).strip()
        return s if s else None

    @classmethod
    def generar_clave_negocio(
        cls,
        actividad: str,
        sede: str,
        fecha: Any = None
    ) -> Tuple[str, str, Optional[str]]:
        """
        Genera la clave de negocio obligatoria: (Nombre_Normalizado, Sede_Normalizada, Fecha_Evento_ISO).
        """
        act_norm = cls.normalizar_texto_actividad(actividad)
        sede_norm = cls.normalizar_sede(sede)
        fecha_norm = cls.normalizar_fecha_str(fecha)
        return (act_norm, sede_norm, fecha_norm)

    @classmethod
    def clasificar_categoria_nominal(cls, fila_nom: FilaLeidaNominal) -> CategoriaParticipacion:
        """
        Determina la CategoriaParticipacion institucional correspondiente a una fila nominal.
        """
        matriz = fila_nom.matriz_origen.upper()

        if matriz == "M2":
            return CategoriaParticipacion.ESTUDIANTE

        if matriz == "M3":
            # Evaluar tipo_protagonistas
            tipo = str(fila_nom.tipo_protagonistas or "").strip().lower()
            if "no docente" in tipo:
                return CategoriaParticipacion.NO_DOCENTE
            if "admin" in tipo:
                return CategoriaParticipacion.ADMINISTRATIVO
            if any(k in tipo for k in ("docente", "acad", "maestr", "profesor")):
                return CategoriaParticipacion.DOCENTE

            # Si tipo_protagonistas no fue concluyente, evaluar cargo
            cargo = str(fila_nom.cargo or "").strip().lower()
            if "admin" in cargo:
                return CategoriaParticipacion.ADMINISTRATIVO
            if any(k in cargo for k in ("docente", "profesor")):
                return CategoriaParticipacion.DOCENTE

            # Default para M3 si no especifica: ADMINISTRATIVO si hay indicios o DOCENTE
            return CategoriaParticipacion.ADMINISTRATIVO if "admin" in tipo else CategoriaParticipacion.DOCENTE

        if matriz == "M4":
            return CategoriaParticipacion.COLABORADOR

        if matriz == "M5":
            return CategoriaParticipacion.BENEFICIADO

        return CategoriaParticipacion.DESCONOCIDO

    @classmethod
    def normalizar_sexo_nominal(cls, sexo_raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Mapea el código de sexo de la matriz física preservando el valor original verbatim.
        Retorna (sexo_original, sexo_normalizado).
        Convención matrices:
          'F' o '1' -> 'FEMENINO'
          'M' o '2' -> 'MASCULINO'
        """
        if sexo_raw is None:
            return None, None
        s_orig = str(sexo_raw).strip()
        if not s_orig:
            return None, None
        s_upper = s_orig.upper()
        if s_upper in ("F", "FEMENINO", "1", "MUJER"):
            return s_orig, "FEMENINO"
        if s_upper in ("M", "MASCULINO", "2", "VARON", "VARÓN"):
            return s_orig, "MASCULINO"
        return s_orig, None

    @classmethod
    def consolidar(
        cls,
        filtrado: ResultadoFiltradoPeriodo,
        fuentes: Optional[Dict[str, RegistroFuenteArchivo]] = None
    ) -> ResultadoConsolidacion:
        """
        Consolida los datos de un ResultadoFiltradoPeriodo en la estructura consolidada en memoria.
        No modifica los archivos Excel ni altera las fuentes originales.
        """
        fuentes_dict = fuentes or {}
        actividades_dict: Dict[Tuple[str, str, Optional[str]], ActividadConsolidada] = {}

        # ---------------------------------------------------------------------
        # PASO 1: Registrar actividades de M1 en el período
        # ---------------------------------------------------------------------
        for act_m1 in filtrado.actividades_en_periodo:
            clave = cls.generar_clave_negocio(act_m1.actividad, act_m1.sede, act_m1.fecha_evento)

            totales_m1 = TotalesM1(
                mujeres=act_m1.total_atencion_f,
                varones=act_m1.total_atencion_m,
                total=act_m1.gran_total_m1,
                estudiantes_m=act_m1.total_estud_m_grado + act_m1.total_estud_m_posgrado,
                estudiantes_f=act_m1.total_estud_f_grado + act_m1.total_estud_f_posgrado,
                docentes_m=act_m1.total_docente_m,
                docentes_f=act_m1.total_docente_f,
                administrativos_m=act_m1.total_administrativos_m,
                administrativos_f=act_m1.total_administrativos_f,
                colaboradores_m=(
                    act_m1.total_partic_m_inst_publica
                    + act_m1.total_partic_m_inst_privada
                    + act_m1.total_partic_m_ong
                ),
                colaboradores_f=(
                    act_m1.total_partic_f_inst_publica
                    + act_m1.total_partic_f_inst_privada
                    + act_m1.total_partic_f_ong
                ),
                protagonistas_m=act_m1.total_protagonistas_m,
                protagonistas_f=act_m1.total_protagonistas_f,
                fila_m1=act_m1,
            )
            # C5/C8: Concatenar evento y evento_otros exclusivamente de M1 si existen
            _partes_evento = [v.strip() for v in [act_m1.evento, act_m1.evento_otros] if v and v.strip()]
            _tipo_evento = " / ".join(_partes_evento) if _partes_evento else None

            act_cons = ActividadConsolidada(
                clave_negocio=clave,
                nombre_actividad=act_m1.actividad,
                sede=act_m1.sede,
                fecha_evento=act_m1.fecha_evento,
                departamento=act_m1.departamento or act_m1.dep_sede,
                municipio=act_m1.municipio or act_m1.mun_sede,
                programa=act_m1.programa,
                proyecto=act_m1.proyecto,
                eje=act_m1.ambito,
                tipo_evento=_tipo_evento,
                resultados=act_m1.resultados,
                area_responsable=act_m1.area_responsable or act_m1.nombre_area,
                fuente_m1=act_m1,
                totales_m1=totales_m1,
                trazabilidad={
                    "fuente_m1": act_m1.trazabilidad,
                    "fuentes_nominales": {}
                }
            )
            actividades_dict[clave] = act_cons

        # ---------------------------------------------------------------------
        # PASO 2: Recolectar y asociar filas nominales en el período
        # ---------------------------------------------------------------------
        filas_nominales_periodo: List[FilaLeidaNominal] = (
            filtrado.estudiantes_en_periodo
            + filtrado.academicos_admin_en_periodo
            + filtrado.colaboradores_en_periodo
            + filtrado.beneficiarios_en_periodo
        )

        # Mapeo temporal de participantes para resolución de identidad posterior
        personas_temp: List[Person] = []
        participaciones_temp: List[Participation] = []
        participaciones_cons_temp: List[ParticipacionConsolidada] = []

        for r in filas_nominales_periodo:
            nom_fecha = getattr(r, "fecha_evento", None)
            clave_nom = cls.generar_clave_negocio(r.actividad, r.sede, nom_fecha)

            # Buscar la actividad destino
            target_act: Optional[ActividadConsolidada] = None

            # 1. Búsqueda exacta por clave de negocio
            if clave_nom in actividades_dict:
                target_act = actividades_dict[clave_nom]
            elif clave_nom[2] is None:
                # 2. Si la fila nominal no tiene fecha explícita, buscar en actividades M1 con igual nombre y sede
                candidatos = [
                    act for act in actividades_dict.values()
                    if (act.clave_negocio[0] == clave_nom[0] and act.clave_negocio[1] == clave_nom[1])
                ]
                if len(candidatos) == 1:
                    target_act = candidatos[0]
                elif len(candidatos) > 1:
                    # Múltiples actividades con igual nombre y sede pero fechas distintas:
                    # no fusionar arbitrariamente; registrar actividad separada
                    target_act = ActividadConsolidada(
                        clave_negocio=clave_nom,
                        nombre_actividad=r.actividad,
                        sede=r.sede,
                        fecha_evento=None,
                        departamento=r.dep_sede,
                        municipio=r.mun_sede,
                        programa=r.programa,
                        proyecto=r.proyecto,
                        eje=r.eje_estrategia,
                        tipo_evento=r.evento,
                        trazabilidad={"fuentes_nominales": {}}
                    )
                    actividades_dict[clave_nom] = target_act
                else:
                    # No existía en M1: crear actividad consolidada desde evidencia nominal
                    target_act = ActividadConsolidada(
                        clave_negocio=clave_nom,
                        nombre_actividad=r.actividad,
                        sede=r.sede,
                        fecha_evento=None,
                        departamento=r.dep_sede,
                        municipio=r.mun_sede,
                        programa=r.programa,
                        proyecto=r.proyecto,
                        eje=r.eje_estrategia,
                        tipo_evento=r.evento,
                        trazabilidad={"fuentes_nominales": {}}
                    )
                    actividades_dict[clave_nom] = target_act
            else:
                # Clave con fecha específica que no estaba en M1
                target_act = ActividadConsolidada(
                    clave_negocio=clave_nom,
                    nombre_actividad=r.actividad,
                    sede=r.sede,
                    fecha_evento=nom_fecha,
                    departamento=r.dep_sede,
                    municipio=r.mun_sede,
                    programa=r.programa,
                    proyecto=r.proyecto,
                    eje=r.eje_estrategia,
                    tipo_evento=r.evento,
                    trazabilidad={"fuentes_nominales": {}}
                )
                actividades_dict[clave_nom] = target_act

            # C3: Registrar eje nominal como metadata complementaria de auditoría si M1 no declaró ámbito
            if target_act.fuente_m1 is not None and target_act.eje is None and getattr(r, "eje_estrategia", None):
                if "eje_complementario_nominal" not in target_act.trazabilidad:
                    target_act.trazabilidad["eje_complementario_nominal"] = r.eje_estrategia
                    target_act.trazabilidad["procedencia_eje_complementario"] = "NOMINAL_AUDITORIA"

            # Clasificación de categoría y sexo
            categoria = cls.clasificar_categoria_nominal(r)
            sexo_orig, sexo_norm = cls.normalizar_sexo_nominal(r.sexo)

            # Instancia Persona (modelo SSOT)
            id_persona_nuevo = str(uuid.uuid4())
            persona_obj = Person(
                id_persona_interno=id_persona_nuevo,
                nombre_completo=r.nombre_apellidos,
                cedula=r.no_cedula,
                sexo_original=sexo_orig,
                sexo_normalizado=sexo_norm,
                fecha_nacimiento=r.fecha_nacimiento,
                edad=int(r.edad) if isinstance(r.edad, (int, float)) else None,
                carrera_original=r.carrera,
                carrera_normalizada=r.carrera,
                departamento_persona=r.dep_sede,
                municipio_persona=r.mun_sede,
                fuente_origen=f"{r.matriz_origen} fila {r.fila}"
            )

            # Instancia Participación (modelo SSOT)
            id_part_nuevo = str(uuid.uuid4())
            es_ced_val = PersonMatcher.es_cedula_valida(r.no_cedula)
            nivel_conf = NivelConfianzaIdentidad.NIVEL_1_CEDULA.value if es_ced_val else NivelConfianzaIdentidad.NIVEL_4_CANDIDATO.value
            part_obj = Participation(
                id_participacion=id_part_nuevo,
                id_actividad=target_act.id_actividad,
                id_persona=id_persona_nuevo,
                categoria_participacion=categoria,
                nivel_confianza_identidad=nivel_conf,
                fuente_origen=f"{r.matriz_origen} fila {r.fila}"
            )

            # Instancia ParticipacionConsolidada
            part_cons = ParticipacionConsolidada(
                id_participacion=id_part_nuevo,
                id_actividad=target_act.id_actividad,
                id_persona=id_persona_nuevo,
                nombre_apellidos=r.nombre_apellidos,
                identificacion=r.no_cedula,
                sexo_original=sexo_orig,
                sexo_normalizado=sexo_norm,
                categoria=categoria,
                carrera=r.carrera,
                cargo=r.cargo,
                entidad=r.entidad,
                departamento=r.dep_sede,
                municipio=r.mun_sede,
                comunidad=None,
                matriz_origen=r.matriz_origen,
                hoja=r.hoja,
                fila=r.fila,
                actividad_asociada=target_act.nombre_actividad,
                sede=target_act.sede,
                trazabilidad=r.trazabilidad,
                fila_nominal_origen=r,
                programa=r.programa,
            )

            personas_temp.append(persona_obj)
            participaciones_temp.append(part_obj)
            participaciones_cons_temp.append(part_cons)
            target_act.participaciones.append(part_cons)

            # Trazabilidad de fuentes nominales en la actividad
            mat_key = r.matriz_origen
            fn_dict = target_act.trazabilidad.setdefault("fuentes_nominales", {})
            fn_dict.setdefault(mat_key, []).append({
                "hoja": r.hoja,
                "fila": r.fila,
                "nombre": r.nombre_apellidos,
                "sexo": r.sexo,
            })
            if getattr(r, "programa", None) and str(r.programa).strip():
                prog_limpio = str(r.programa).strip()
                progs_nominales = target_act.trazabilidad.setdefault("programas_nominales", [])
                if prog_limpio not in progs_nominales:
                    progs_nominales.append(prog_limpio)

        # ---------------------------------------------------------------------
        # PASO 3: Resolución de Identidad dentro del período (Deduplicación)
        # ---------------------------------------------------------------------
        resolucion_id: Optional[IdentityResolutionResult] = None
        if personas_temp and participaciones_temp:
            resolucion_id = IdentityResolver.resolver_identidades(personas_temp, participaciones_temp)
            personas_ssot = resolucion_id.personas
            participaciones_ssot = resolucion_id.participaciones

            # Actualizar id_persona canónico en las participaciones consolidadas
            # construyendo un mapa de id_participacion -> id_persona canónico
            mapa_part_to_canonical = {p.id_participacion: p.id_persona for p in participaciones_ssot}
            for p_cons in participaciones_cons_temp:
                if p_cons.id_participacion in mapa_part_to_canonical:
                    p_cons.id_persona = mapa_part_to_canonical[p_cons.id_participacion]
        else:
            personas_ssot = []
            participaciones_ssot = []

        # ---------------------------------------------------------------------
        # PASO 4: Calcular Totales Nominales y Métricas de Actividad
        # ---------------------------------------------------------------------
        for act in actividades_dict.values():
            parts = act.participaciones
            mujeres = sum(1 for p in parts if p.sexo_normalizado == "FEMENINO")
            varones = sum(1 for p in parts if p.sexo_normalizado == "MASCULINO")
            total = len(parts)

            est = act.estudiantes
            doc = act.docentes
            adm = act.administrativos
            no_doc = act.no_docentes
            col = act.colaboradores
            ben = act.beneficiarios

            totales_nom = TotalesNominales(
                mujeres=mujeres,
                varones=varones,
                total=total,
                estudiantes=len(est),
                docentes=len(doc),
                administrativos=len(adm),
                no_docentes=len(no_doc),
                colaboradores=len(col),
                beneficiarios=len(ben),
                estudiantes_f=sum(1 for p in est if p.sexo_normalizado == "FEMENINO"),
                estudiantes_m=sum(1 for p in est if p.sexo_normalizado == "MASCULINO"),
                docentes_f=sum(1 for p in doc if p.sexo_normalizado == "FEMENINO"),
                docentes_m=sum(1 for p in doc if p.sexo_normalizado == "MASCULINO"),
                administrativos_f=sum(1 for p in adm if p.sexo_normalizado == "FEMENINO"),
                administrativos_m=sum(1 for p in adm if p.sexo_normalizado == "MASCULINO"),
                no_docentes_f=sum(1 for p in no_doc if p.sexo_normalizado == "FEMENINO"),
                no_docentes_m=sum(1 for p in no_doc if p.sexo_normalizado == "MASCULINO"),
                colaboradores_f=sum(1 for p in col if p.sexo_normalizado == "FEMENINO"),
                colaboradores_m=sum(1 for p in col if p.sexo_normalizado == "MASCULINO"),
                beneficiarios_f=sum(1 for p in ben if p.sexo_normalizado == "FEMENINO"),
                beneficiarios_m=sum(1 for p in ben if p.sexo_normalizado == "MASCULINO"),
            )

            act.totales_nominales = totales_nom
            act.total_asistencia_bruta = len(parts)
            act.total_personas_unicas = len({p.id_persona for p in parts})

        # ---------------------------------------------------------------------
        # PASO 5: Ensamblado del Resultado Consolidado Global
        # ---------------------------------------------------------------------
        lista_actividades = list(actividades_dict.values())
        asistencia_bruta = len(participaciones_cons_temp)
        personas_unicas = len(personas_ssot)
        recurrencia = max(0, asistencia_bruta - personas_unicas)
        tasa_rec = round((recurrencia / asistencia_bruta * 100.0), 2) if asistencia_bruta > 0 else 0.0

        return ResultadoConsolidacion(
            periodo=filtrado.periodo,
            actividades=lista_actividades,
            total_actividades=len(lista_actividades),
            total_asistencia_bruta=asistencia_bruta,
            total_personas_unicas=personas_unicas,
            total_recurrencia=recurrencia,
            tasa_recurrencia=tasa_rec,
            personas_consolidadas=personas_ssot,
            participaciones_consolidadas=participaciones_ssot,
            resolucion_identidad=resolucion_id,
            nominales_historicos_fuera_periodo=filtrado.nominales_historicos_fuera_periodo,
            actividades_fuera_periodo=filtrado.actividades_fuera_periodo,
            fuentes=fuentes_dict,
        )

    @classmethod
    def consolidar_conjunto(
        cls,
        conjunto: ConjuntoMatricesLeidas,
        periodo: PeriodoConsolidacion
    ) -> ResultadoConsolidacion:
        """
        Punto de entrada directo que toma un ConjuntoMatricesLeidas y un PeriodoConsolidacion,
        aplica el PeriodFilter y ejecuta la consolidación completa en memoria.
        """
        filtrado = PeriodFilter.filtrar(conjunto, periodo)
        return cls.consolidar(filtrado, fuentes=conjunto.fuentes)
