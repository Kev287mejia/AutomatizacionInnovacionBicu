"""Especificación del Esquema Físico DDL SQLite - Sistema Institucional BICU.

Fase 25 (Etapa 25.2): Schema, SCHEMA_VERSION y Migración Inicial.
Define las 18 estructuras funcionales de persistencia aprobadas en Fase 24/24.1,
más la tabla técnica de versionado schema_version e índices relacionales B-Tree.
"""

# ---------------------------------------------------------------------------
# TABLA TÉCNICA: CONTROL DE VERSIONES DE ESQUEMA
# ---------------------------------------------------------------------------
SCHEMA_VERSION_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    nombre_migracion TEXT NOT NULL,
    hash_script TEXT NOT NULL,
    fecha_aplicacion TEXT NOT NULL,
    tiempo_ejecucion_ms INTEGER NOT NULL
);
"""

# ---------------------------------------------------------------------------
# ESQUEMA FUNCIONAL: 18 ESTRUCTURAS INSTITUCIONALES (MIGRACIÓN v001)
# ---------------------------------------------------------------------------
INITIAL_SCHEMA_DDL_STATEMENTS = [
    # 1. ACTIVIDAD (Núcleo desacoplado de eventos)
    """
    CREATE TABLE IF NOT EXISTS actividad (
        id_actividad TEXT PRIMARY KEY,
        codigo_institucional TEXT UNIQUE,
        nombre_original TEXT NOT NULL,
        nombre_oficial TEXT,
        codigo_indicador TEXT,
        tipo_evento TEXT NOT NULL,
        ambito TEXT CHECK (ambito IS NULL OR ambito IN ('LOCAL', 'MUNICIPAL', 'REGIONAL', 'NACIONAL', 'INTERNACIONAL')),
        eje_estrategico TEXT,
        programa TEXT,
        proyecto TEXT,
        sede TEXT NOT NULL CHECK (sede IN ('BLUEFIELDS', 'BILWI', 'EL_RAMA', 'CORN_ISLAND', 'WASPAM', 'PAIWAS', 'LAS_MINAS', 'MANAGUA', 'OTRA')),
        departamento_geo TEXT,
        municipio TEXT,
        comunidad_barrio TEXT,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT,
        horario TEXT,
        departamento_responsable TEXT NOT NULL,
        responsable TEXT NOT NULL,
        fuente_financiamiento TEXT,
        estado TEXT NOT NULL DEFAULT 'PLANIFICADA' CHECK (estado IN ('PLANIFICADA', 'DISENADA', 'EN_EJECUCION', 'EJECUTADA', 'REPORTADA', 'CERRADA', 'ANULADA')),
        es_emergente INTEGER NOT NULL DEFAULT 0 CHECK (es_emergente IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
    );
    """,

    # 2. PLANIFICACION (Relación 0..1 : 1 con Actividad)
    """
    CREATE TABLE IF NOT EXISTS planificacion (
        id_planificacion TEXT PRIMARY KEY,
        id_actividad TEXT NOT NULL UNIQUE,
        codigo_poa TEXT,
        meta_participantes INTEGER NOT NULL CHECK (meta_participantes >= 0),
        indicador_comprometido TEXT,
        presupuesto_total REAL CHECK (presupuesto_total IS NULL OR presupuesto_total >= 0.0),
        justificacion_estrategica TEXT,
        fecha_programada TEXT NOT NULL,
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE RESTRICT
    );
    """,

    # 3. PARTIDA_PRESUPUESTARIA (Desglose 1 : N con Planificación)
    """
    CREATE TABLE IF NOT EXISTS partida_presupuestaria (
        id_partida TEXT PRIMARY KEY,
        id_planificacion TEXT NOT NULL,
        rubro TEXT NOT NULL,
        cantidad REAL NOT NULL CHECK (cantidad > 0),
        costo_unitario REAL NOT NULL CHECK (costo_unitario >= 0),
        subtotal REAL NOT NULL CHECK (subtotal >= 0),
        fuente_financiamiento TEXT,
        justificacion_gasto TEXT,
        FOREIGN KEY (id_planificacion) REFERENCES planificacion(id_planificacion) ON DELETE RESTRICT
    );
    """,

    # 4. DISENO_METODOLOGICO (Relación opcional 0..1 : 1 con Actividad)
    """
    CREATE TABLE IF NOT EXISTS diseno_metodologico (
        id_diseno TEXT PRIMARY KEY,
        id_actividad TEXT NOT NULL UNIQUE,
        version_diseno INTEGER NOT NULL DEFAULT 1 CHECK (version_diseno >= 1),
        objetivo_general TEXT NOT NULL,
        objetivos_especificos TEXT,
        contenidos_tematicos TEXT,
        metodologia TEXT,
        materiales_requeridos TEXT,
        agenda_cronograma TEXT,
        facilitadores TEXT,
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE RESTRICT
    );
    """,

    # 5. PERSONA (SSOT de identidad bio-demográfica permanente)
    """
    CREATE TABLE IF NOT EXISTS persona (
        id_persona_interno TEXT PRIMARY KEY,
        cedula TEXT,
        numero_institucional TEXT UNIQUE,
        otro_documento TEXT,
        tipo_otro_documento TEXT CHECK (tipo_otro_documento IS NULL OR tipo_otro_documento IN ('PASAPORTE', 'RESIDENCIA', 'OTRO')),
        nombre_completo TEXT NOT NULL,
        nombres TEXT,
        apellidos TEXT,
        sexo TEXT NOT NULL CHECK (sexo IN ('M', 'F')),
        fecha_nacimiento TEXT,
        edad_declarada INTEGER CHECK (edad_declarada IS NULL OR (edad_declarada >= 5 AND edad_declarada <= 110)),
        etnia TEXT,
        pais_procedencia TEXT NOT NULL DEFAULT 'Nicaragua',
        departamento_residencia TEXT,
        municipio_residencia TEXT,
        comunidad_residencia TEXT,
        condicion_discapacidad TEXT DEFAULT 'Ninguna',
        telefono TEXT,
        email TEXT,
        estado_identidad TEXT NOT NULL DEFAULT 'IDENTIDAD_CONFIRMADA' CHECK (estado_identidad IN ('IDENTIDAD_CONFIRMADA', 'POSIBLE_DUPLICADO', 'IDENTIDAD_NO_RESUELTA'))
    );
    """,

    # 6. PERFIL_ESTUDIANTE (Extensión 1:1 de Persona)
    """
    CREATE TABLE IF NOT EXISTS perfil_estudiante (
        id_perfil_estudiante TEXT PRIMARY KEY,
        id_persona TEXT NOT NULL UNIQUE,
        carne_estudiantil TEXT,
        facultad_escuela TEXT,
        carrera_cursada TEXT,
        nivel_academico TEXT CHECK (nivel_academico IS NULL OR nivel_academico IN ('GRADO', 'POSGRADO', 'TECNICO_SUPERIOR', 'CURSO_LIBRE')),
        anio_academico TEXT,
        turno TEXT,
        sede_estudios TEXT,
        FOREIGN KEY (id_persona) REFERENCES persona(id_persona_interno) ON DELETE CASCADE
    );
    """,

    # 7. PERFIL_PERSONAL (Extensión 1:1 de Persona para Académicos/Administrativos)
    """
    CREATE TABLE IF NOT EXISTS perfil_personal (
        id_perfil_personal TEXT PRIMARY KEY,
        id_persona TEXT NOT NULL UNIQUE,
        numero_empleado TEXT,
        tipo_estamento TEXT NOT NULL CHECK (tipo_estamento IN ('DOCENTE', 'ADMINISTRATIVO')),
        cargo_institucional TEXT,
        departamento_laboral TEXT,
        tipo_contrato TEXT,
        FOREIGN KEY (id_persona) REFERENCES persona(id_persona_interno) ON DELETE CASCADE
    );
    """,

    # 8. PERFIL_COLABORADOR (Extensión 1:1 de Persona para Entidades Externas)
    """
    CREATE TABLE IF NOT EXISTS perfil_colaborador (
        id_perfil_colaborador TEXT PRIMARY KEY,
        id_persona TEXT NOT NULL UNIQUE,
        entidad_empresa TEXT NOT NULL,
        sector TEXT CHECK (sector IS NULL OR sector IN ('PUBLICO', 'PRIVADO', 'COMUNITARIO', 'COOPERACION')),
        cargo_entidad TEXT,
        FOREIGN KEY (id_persona) REFERENCES persona(id_persona_interno) ON DELETE CASCADE
    );
    """,

    # 9. PERFIL_BENEFICIARIO (Extensión 1:1 de Persona para Protagonistas)
    """
    CREATE TABLE IF NOT EXISTS perfil_beneficiario (
        id_perfil_beneficiario TEXT PRIMARY KEY,
        id_persona TEXT NOT NULL UNIQUE,
        sector_comunitario TEXT,
        tipo_beneficio_recibido TEXT,
        FOREIGN KEY (id_persona) REFERENCES persona(id_persona_interno) ON DELETE CASCADE
    );
    """,

    # 10. PARTICIPACION (Asociativa N:M Actividad <-> Persona + Reglas RN-C03 y RN-C06)
    """
    CREATE TABLE IF NOT EXISTS participacion (
        id_participacion TEXT PRIMARY KEY,
        id_actividad TEXT NOT NULL,
        id_persona TEXT NOT NULL,
        estamento_declarado TEXT NOT NULL CHECK (estamento_declarado IN ('ESTUDIANTE', 'DOCENTE', 'ADMINISTRATIVO', 'COLABORADOR', 'BENEFICIADO')),
        es_beneficiado_rol INTEGER NOT NULL DEFAULT 0 CHECK (es_beneficiado_rol IN (0, 1)),
        matriz_destino TEXT CHECK (matriz_destino IN ('M2', 'M3', 'M4', 'M5', 'COLA_REVISION')),
        rol_en_actividad TEXT NOT NULL DEFAULT 'ASISTENTE' CHECK (rol_en_actividad IN ('ASISTENTE', 'FACILITADOR', 'EXPOSITOR', 'MENTOR', 'JURADO', 'ORGANIZADOR')),
        condicion_asistencia TEXT NOT NULL DEFAULT 'PRESENTE' CHECK (condicion_asistencia IN ('PRESENTE', 'AUSENTE', 'JUSTIFICADO')),
        carrera_o_cargo_actividad TEXT,
        entidad_externa_actividad TEXT,
        archivo_fuente_origen TEXT,
        fila_fuente_origen INTEGER,
        requiere_revision INTEGER NOT NULL DEFAULT 0 CHECK (requiere_revision IN (0, 1)),
        motivo_revision TEXT,
        es_historico_preexistente INTEGER NOT NULL DEFAULT 0 CHECK (es_historico_preexistente IN (0, 1)),
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE RESTRICT,
        FOREIGN KEY (id_persona) REFERENCES persona(id_persona_interno) ON DELETE RESTRICT,
        UNIQUE (id_actividad, id_persona)
    );
    """,

    # 11. EVIDENCIA (Activos digitales con metadatos y custodia criptográfica)
    """
    CREATE TABLE IF NOT EXISTS evidencia (
        id_evidencia TEXT PRIMARY KEY,
        tipo_evidencia TEXT NOT NULL CHECK (tipo_evidencia IN ('FOTOGRAFIA', 'LISTA_FIRMADA', 'ACTA_RECEPCION', 'ENLACE_WEB', 'DOCUMENTO_ADJUNTO')),
        titulo TEXT NOT NULL,
        descripcion_pie TEXT,
        ruta_archivo_relativa TEXT,
        url_externa TEXT,
        hash_sha256 TEXT,
        tamano_bytes INTEGER CHECK (tamano_bytes IS NULL OR tamano_bytes > 0),
        mime_type TEXT,
        fecha_captura TEXT
    );
    """,

    # 12. ACTIVIDAD_EVIDENCIA (Asociativa N:M Actividad <-> Evidencia)
    """
    CREATE TABLE IF NOT EXISTS actividad_evidencia (
        id_actividad_evidencia TEXT PRIMARY KEY,
        id_actividad TEXT NOT NULL,
        id_evidencia TEXT NOT NULL,
        orden_presentacion INTEGER NOT NULL DEFAULT 1 CHECK (orden_presentacion >= 1),
        seccion_informe TEXT NOT NULL DEFAULT 'GALERIA' CHECK (seccion_informe IN ('FICHA_TECNICA', 'GALERIA', 'ANEXO')),
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE RESTRICT,
        FOREIGN KEY (id_evidencia) REFERENCES evidencia(id_evidencia) ON DELETE RESTRICT,
        UNIQUE (id_actividad, id_evidencia)
    );
    """,

    # 13. INFORME_ACTIVIDAD (Word individual emitido)
    """
    CREATE TABLE IF NOT EXISTS informe_actividad (
        id_informe TEXT PRIMARY KEY,
        id_actividad TEXT NOT NULL UNIQUE,
        ruta_docx TEXT NOT NULL,
        hash_sha256 TEXT NOT NULL,
        fecha_generacion TEXT NOT NULL,
        version_informe TEXT NOT NULL DEFAULT '1.0',
        plantilla_utilizada TEXT NOT NULL,
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE RESTRICT
    );
    """,

    # 14. INFORME_SEMANAL (Consolidado periódico de recinto)
    """
    CREATE TABLE IF NOT EXISTS informe_semanal (
        id_informe_semanal TEXT PRIMARY KEY,
        anio INTEGER NOT NULL CHECK (anio >= 2020 AND anio <= 2050),
        mes INTEGER NOT NULL CHECK (mes >= 1 AND mes <= 12),
        numero_semana INTEGER NOT NULL CHECK (numero_semana >= 1 AND numero_semana <= 5),
        etiqueta_periodo TEXT NOT NULL,
        departamento_responsable TEXT NOT NULL,
        sede_recinto TEXT NOT NULL,
        ruta_product_a TEXT,
        hash_sha256_product_a TEXT,
        ruta_product_b TEXT,
        hash_sha256_product_b TEXT,
        fecha_generacion TEXT NOT NULL
    );
    """,

    # 15. DETALLE_INFORME_SEMANAL (Asociativa N:M Informe Semanal <-> Actividad)
    """
    CREATE TABLE IF NOT EXISTS detalle_informe_semanal (
        id_detalle TEXT PRIMARY KEY,
        id_informe_semanal TEXT NOT NULL,
        id_actividad TEXT NOT NULL,
        orden_secuencia INTEGER NOT NULL CHECK (orden_secuencia >= 1),
        incluir_product_a INTEGER NOT NULL DEFAULT 1 CHECK (incluir_product_a IN (0, 1)),
        incluir_product_b INTEGER NOT NULL DEFAULT 1 CHECK (incluir_product_b IN (0, 1)),
        FOREIGN KEY (id_informe_semanal) REFERENCES informe_semanal(id_informe_semanal) ON DELETE CASCADE,
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE RESTRICT,
        UNIQUE (id_informe_semanal, id_actividad)
    );
    """,

    # 16. DISCREPANCIA (Gobernanza bajo el principio DETECTAR ≠ CORREGIR)
    """
    CREATE TABLE IF NOT EXISTS discrepancia (
        id_discrepancia TEXT PRIMARY KEY,
        id_actividad TEXT NOT NULL,
        tipo_discrepancia TEXT NOT NULL CHECK (tipo_discrepancia IN ('PLAN_VS_REAL', 'RESUMEN_VS_NOMINAL', 'M1_VS_NOMINALES', 'FECHA_DISCORDANTE', 'OTRO')),
        severidad TEXT NOT NULL DEFAULT 'WARNING' CHECK (severidad IN ('INFO', 'WARNING', 'ERROR')),
        fuente_a_nombre TEXT NOT NULL,
        fuente_a_valor TEXT NOT NULL,
        fuente_b_nombre TEXT NOT NULL,
        fuente_b_valor TEXT NOT NULL,
        delta_valor TEXT,
        estado TEXT NOT NULL DEFAULT 'REQUIERE_REVISION' CHECK (estado IN ('REQUIERE_REVISION', 'EN_REVISION', 'ACLARADO', 'CONCORDANTE')),
        justificacion_aclaratoria TEXT,
        usuario_revisor TEXT,
        fecha_deteccion TEXT NOT NULL,
        fecha_revision TEXT,
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE RESTRICT
    );
    """,

    # 17. SALIDA_INSTITUCIONAL (Certificación de matrices Excel M1–M5 generadas)
    """
    CREATE TABLE IF NOT EXISTS salida_institucional (
        id_salida TEXT PRIMARY KEY,
        id_actividad TEXT,
        codigo_matriz TEXT NOT NULL CHECK (codigo_matriz IN ('M1', 'M2', 'M3', 'M4', 'M5')),
        ruta_archivo_excel TEXT NOT NULL,
        hash_sha256 TEXT NOT NULL,
        filas_totales INTEGER NOT NULL CHECK (filas_totales >= 0),
        filas_historicas_preservadas INTEGER NOT NULL DEFAULT 0 CHECK (filas_historicas_preservadas >= 0),
        fecha_emision TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'GENERADA' CHECK (estado IN ('GENERADA', 'AUDITADA', 'CERTIFICADA')),
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE RESTRICT
    );
    """,

    # 18. AUDITORIA_EVENTO (Trazabilidad forense inmutable)
    """
    CREATE TABLE IF NOT EXISTS auditoria_evento (
        id_auditoria TEXT PRIMARY KEY,
        fecha_hora TEXT NOT NULL,
        usuario_operador TEXT NOT NULL,
        tipo_operacion TEXT NOT NULL CHECK (tipo_operacion IN ('INSERT', 'UPDATE', 'DELETE_LOGIC', 'EXPORT', 'DISCREPANCY_RESOLVE')),
        tabla_afectada TEXT NOT NULL,
        id_registro_afectado TEXT NOT NULL,
        snapshot_previo_json TEXT,
        snapshot_nuevo_json TEXT,
        motivo_modificacion TEXT
    );
    """,
]

# ---------------------------------------------------------------------------
# ÍNDICES RELACIONALES B-TREE JUSTIFICADOS
# ---------------------------------------------------------------------------
INITIAL_INDEXES_DDL_STATEMENTS = [
    # Cédula única parcial (RN-C04: admite múltiples NULLs sin colisión)
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_persona_cedula ON persona(cedula) WHERE cedula IS NOT NULL;",
    
    # Búsquedas frecuentes de actividad
    "CREATE INDEX IF NOT EXISTS idx_actividad_periodo ON actividad(fecha_inicio, fecha_fin);",
    "CREATE INDEX IF NOT EXISTS idx_actividad_sede ON actividad(sede, departamento_geo);",
    "CREATE INDEX IF NOT EXISTS idx_actividad_estado ON actividad(estado);",
    "CREATE INDEX IF NOT EXISTS idx_actividad_indicador ON actividad(codigo_indicador);",

    # Personas y coincidencias
    "CREATE INDEX IF NOT EXISTS idx_persona_nombre ON persona(nombre_completo);",
    "CREATE INDEX IF NOT EXISTS idx_persona_sexo ON persona(sexo);",

    # Participaciones y enrutamiento M1-M5
    "CREATE INDEX IF NOT EXISTS idx_particip_actividad ON participacion(id_actividad);",
    "CREATE INDEX IF NOT EXISTS idx_particip_persona ON participacion(id_persona);",
    "CREATE INDEX IF NOT EXISTS idx_particip_matriz_dest ON participacion(matriz_destino, condicion_asistencia);",
    "CREATE INDEX IF NOT EXISTS idx_particip_historico ON participacion(es_historico_preexistente);",

    # Evidencias
    "CREATE INDEX IF NOT EXISTS idx_evidencia_hash ON evidencia(hash_sha256);",
    "CREATE INDEX IF NOT EXISTS idx_actevid_busqueda ON actividad_evidencia(id_actividad, orden_presentacion);",

    # Informes y discrepancias
    "CREATE INDEX IF NOT EXISTS idx_infsem_periodo ON informe_semanal(anio, mes, numero_semana, sede_recinto);",
    "CREATE INDEX IF NOT EXISTS idx_discrep_estado ON discrepancia(estado, severidad);",
    "CREATE INDEX IF NOT EXISTS idx_salida_matriz ON salida_institucional(codigo_matriz, fecha_emision);",
]

# Catálogo oficial de las 18 tablas funcionales + 1 técnica (v001)
EXPECTED_TABLE_NAMES = {
    "schema_version",
    "actividad",
    "planificacion",
    "partida_presupuestaria",
    "diseno_metodologico",
    "persona",
    "perfil_estudiante",
    "perfil_personal",
    "perfil_colaborador",
    "perfil_beneficiario",
    "participacion",
    "evidencia",
    "actividad_evidencia",
    "informe_actividad",
    "informe_semanal",
    "detalle_informe_semanal",
    "discrepancia",
    "salida_institucional",
    "auditoria_evento",
}

# ---------------------------------------------------------------------------
# ESQUEMA V002: HASH SHA-256 E IDEMPOTENCIA, MÉTRICAS AGREGADAS (GAP-1, GAP-2, GAP-3)
# ---------------------------------------------------------------------------
V002_SCHEMA_DDL_STATEMENTS = [
    # 1. Agregar columna hash_sha256 a la tabla actividad (GAP-3)
    "ALTER TABLE actividad ADD COLUMN hash_sha256 TEXT;",

    # 2. Crear tabla actividad_metrica_agregada para las 15 métricas de Tabla 2 (GAP-1)
    """
    CREATE TABLE IF NOT EXISTS actividad_metrica_agregada (
        id_actividad TEXT PRIMARY KEY,
        total_participantes INTEGER,
        total_femenino INTEGER,
        total_masculino INTEGER,
        total_estudiantes INTEGER,
        total_docentes INTEGER,
        total_administrativos INTEGER,
        total_otros INTEGER,
        total_mestizo INTEGER,
        total_creole INTEGER,
        total_miskitu INTEGER,
        total_mayangna INTEGER,
        total_ulwa INTEGER,
        total_rama INTEGER,
        total_garifuna INTEGER,
        total_otra_etnia INTEGER,
        fuente_seccion TEXT NOT NULL,
        presenta_discrepancia_interna INTEGER NOT NULL DEFAULT 0 CHECK (presenta_discrepancia_interna IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        FOREIGN KEY (id_actividad) REFERENCES actividad(id_actividad) ON DELETE CASCADE
    );
    """,
]

V002_INDEXES_DDL_STATEMENTS = [
    # Índice único parcial para hash_sha256: garantiza unicidad cuando el hash existe,
    # permitiendo múltiples filas NULL sin colisión (idempotencia y concurrencia).
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_actividad_hash_sha256 ON actividad(hash_sha256) WHERE hash_sha256 IS NOT NULL;",

    # Índice para búsquedas por código de indicador institucional (GAP-2).
    "CREATE INDEX IF NOT EXISTS idx_actividad_indicador ON actividad(codigo_indicador);",
]

# Catálogo ampliado de tablas en v002 (19 funcionales + 1 técnica)
EXPECTED_TABLE_NAMES_V002 = EXPECTED_TABLE_NAMES | {"actividad_metrica_agregada"}

