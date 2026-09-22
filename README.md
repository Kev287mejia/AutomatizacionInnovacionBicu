# BICU — Sistema Institucional de Gestión, Planificación, Consolidación y Reporting

Sistema institucional de software para la gestión, organización, validación, seguimiento, consolidación y análisis de información de actividades académicas, de extensión e innovación de la **Bluefields Indian & Caribbean University (BICU)**.

El sistema proporciona un entorno determinista, reproducible y auditable que abarca desde la planificación metodológica y la captura de evidencias en informes de ejecución, hasta la consolidación de matrices oficiales y la emisión de analítica institucional mediante dashboards y reportes ejecutivos.

---

## 1. Propósito del Sistema y Alcance Institucional

En el ámbito universitario, la gestión operativa y estratégica comprende flujos complejos de información: diseño metodológico de actividades, convocatorias, listas de asistencia de participantes, evidencias documentales de ejecución y balances de cumplimiento del Plan Operativo Anual (POA).

Tradicionalmente, la integración de estos datos entre sedes, recintos y áreas de conocimiento dependía de procesos manuales dispersos, vulnerables a duplicidades, inconsistencias demográficas y desarticulación entre lo planificado y lo efectivamente ejecutado.

Este sistema resuelve dicha problemática mediante una solución técnica estructurada que garantiza:

1. **Estandarización y Validación Sistemática**: Evaluación rigurosa de datos mediante motores de reglas institucionales tanto en la fase de planificación (reglas V-MD) como en la fase de ejecución (reglas Q-01 a Q-20).
2. **Persistencia Relacional Auditable**: Base de datos relacional local (SQLite) estructurada con migraciones deterministas y trazabilidad desde el documento fuente de origen hasta los consolidados y reportes finales.
3. **Generación Documental Oficial Desacoplada**: Emisión automatizada de las cinco matrices institucionales en hojas de cálculo (`.xlsx`) y documentos metodológicos en Word (`.docx`) respetando especificaciones institucionales.
4. **Inteligencia y Analítica Institucional**: Cálculo centralizado de indicadores de gestión, visualización ejecutiva en cinco niveles de dashboard y exportación de reportes periciales en formatos XLSX, DOCX y CSV.
5. **Gobernanza Rigurosa del Dato**: Preservación estricta de valores ausentes (NULL sin imputaciones arbitrarias), aislamiento de registros históricos preexistentes y no contaminación de metas planificadas por eventos emergentes.

---

## 2. Flujo Funcional Completo del Sistema

El sistema implementa una cadena de valor analítica unidireccional y estrictamente gobernada:

```text
       PLANIFICACIÓN INSTITUCIONAL
                   ↓
          DISEÑO METODOLÓGICO             (Objetivos, Agenda, Matriz Operativa, FAQs)
                   ↓
            EJECUCIÓN REAL                (Desarrollo en sedes, recintos y comunidades)
                   ↓
         INFORME WORD REAL (.docx)        (Listas de asistencia, evidencias y firmas)
                   ↓
               EXTRACCIÓN                 (Lectura de metadatos, participantes y roles)
                   ↓
               VALIDACIÓN                 (Reglas de calidad Q-01 a Q-20, desduplicación)
                   ↓
              PERSISTENCIA                (Almacenamiento transaccional en SQLite)
                   ↓
              ENRUTAMIENTO                (Clasificación a matrices oficiales por estamento)
                   ↓
       MATRICES OFICIALES M1–M5           (Productos patrimoniales primarios en Excel)
                   ↓
          CÁLCULO DE INDICADORES          (IndicatorCalculationService: lógica matemática pura)
                   ↓
             REPORTING DOMAIN             (ReportingService: estructuración analítica)
                   ↓
    ┌──────────────┴──────────────┐
    ↓                             ↓
DASHBOARD INSTITUCIONAL    REPORTES OFICIALES (REP-01..05)
(5 Niveles de KPIs)        (Exportación derivada en XLSX, DOCX, CSV)
```

### Principio Rector: PLANIFICADO ≠ EJECUTADO
* **Planificado**: Representa la programación formalizada en el POA y formalizada en diseños metodológicos aprobados.
* **Ejecutado**: Representa la evidencia documental comprobada de intervenciones realizadas, validada y almacenada en el repositorio.
* **Separación de responsabilidades**: Una actividad planificada no incrementa el cumplimiento real por el solo hecho de existir; requiere el procesamiento de su informe de ejecución. A su vez, una actividad ejecutada no planificada (emergente) se registra para fines de cobertura y volumen, pero **no incrementa artificialmente el porcentaje de cumplimiento del POA**.

---

## 3. Arquitectura del Sistema

La arquitectura está construida siguiendo principios de Diseño Guiado por el Dominio (*Domain-Driven Design*, DDD) y Arquitectura Limpia, manteniendo un aislamiento estricto entre capas:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        CAPA DE PRESENTACIÓN (UI)                       │
│  CustomTkinter: Menú de Módulos (Grid 2x2), Consolidadores, Vistas de   │
│  Planificación, y Módulo 4: Reporting y Dashboard Institucional         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Inyección desacoplada
┌───────────────────────────────────▼────────────────────────────────────┐
│                         COMPOSITION ROOT                               │
│  run_consolidator.py: Fábricas de vistas (planning_view_factory,       │
│  reporting_view_factory). Resuelve dependencias sin acoplar paquetes. │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                        CAPA DE APLICACIÓN                              │
│  • WordConsolidationEngine / PipelineCoordinator                       │
│  • PlanningService / MethodologicalDesignService                       │
│  • IndicatorCalculationService (Cálculo puro de indicadores)           │
│  • ReportingService (Orquestación de reportes y dashboard)             │
│  • ReportingUIService (Fachada síncrona para la capa visual)           │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
┌───────────────────▼────────────────┐   ┌───────────▼───────────────────┐
│        DOMINIO DE EJECUCIÓN        │   │    DOMINIO DE PLANIFICACIÓN   │
│  Actividades, Personas, Evidencias,│   │  PlannedActivity, Design,     │
│  Participaciones, Enrutamiento,    │   │  Agenda, OperationalMatrix,   │
│  Reglas de Calidad Q-01..Q-20      │   │  Trazabilidad V004            │
└───────────────────┬────────────────┘   └───────────┬───────────────────┘
                    │                                │
┌───────────────────▼────────────────────────────────▼───────────────────┐
│                     CAPA DE INFRAESTRUCTURA                            │
│  • Persistencia: SQLite relacional gobernado por migraciones           │
│    (V001: Ejecución, V002: Hashes, V003: Planning, V004: Enlaces)      │
│  • Extractores: WordActivityExtractor (.docx con tablas institucionales)│
│  • Generadores Patrimoniales: OpenPyXL (Matrices M1–M5 protegidas)     │
│  • Exportadores Analíticos:                                            │
│    - XLSXReportExporter (openpyxl con estilos institucionales)         │
│    - DOCXReportExporter (python-docx con tablas y notas periciales)    │
│    - CSVReportExporter  (estándar utf-8-sig estructurado)              │
│  • Asistencia IA (restringida a Planning): GeminiAdapter vía Factory   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Módulos del Sistema

El sistema se organiza en cuatro módulos principales accesibles desde la ventana inicial:

### Módulo 1: Procesamiento de Informes Word → Matrices Excel (M1–M5)
Procesa lotes de informes Word (`.docx`), extrae datos de la actividad y nóminas de participantes, valida consistencia con reglas Q-01 a Q-20, persiste transaccionalmente en SQLite y distribuye a las matrices oficiales correspondientes.

### Módulo 2: Consolidación Inversa Matrices Excel → Informes Word
Herramienta de soporte para generar informes resumidos a partir de matrices consolidadas previas.

### Módulo 3: Planificación y Diseño Metodológico
Modelado de actividades planificadas del POA, gestión técnica de diseños metodológicos (objetivos, metodología, agenda cronometrada, matriz de planificación operativa, preguntas frecuentes), validación de reglas V-MD, transiciones de estado (`DRAFT` → `REVIEW` → `APPROVED`), congelamiento de diseños aprobados y exportación a documento formal Word (`.docx`).

### Módulo 4: Reporting y Dashboard Institucional
Centro de inteligencia institucional. Visualiza KPIs analíticos en cinco niveles jerárquicos y emite los reportes ejecutivos oficiales de la universidad (REP-01 a REP-05) con exportación derivada en XLSX, DOCX y CSV.

---

## 5. Matrices Institucionales Oficiales (M1–M5)

Las cinco matrices en formato Excel (`.xlsx`) son los **productos primarios oficiales** de la gestión universitaria. Reporting y Dashboard son capas analíticas que consumen estos datos consolidados; **en ningún caso sustituyen las matrices patrimoniales**.

* **M1 — Consolidado de Actividades**: Catálogo general de actividades ejecutadas, fecha, unidad académica, modalidad, tipo de evento y resumen cuantitativo de participación.
* **M2 — Estudiantes**: Padrón de participantes clasificados como estudiantes universitarios, carrera, año académico y desglose demográfico.
* **M3 — Académicos y Administrativos**: Registro de docentes, investigadores y colaboradores administrativos.
* **M4 — Colaboradores**: Personal de apoyo técnico, enlaces comunitarios y facilitadores externos.
* **M5 — Protagonistas Beneficiados**: Padrón de protagonistas comunitarios, productores, emprendedores y actores territoriales atendidos por programas universitarios.

---

## 6. Catálogo de Reportes Oficiales (REP-01 a REP-05)

El subsistema de reportes implementa exclusivamente los cinco reportes normalizados por la gobernanza de la institución:

| Código | Denominación Oficial | Propósito y Contenido Técnico |
|---|---|---|
| **REP-01** | Balance Ejecutivo de Gestión Institucional | Cumplimiento global, presupuesto ejecutado, volumen general de actividades y cobertura de personas por estamento. |
| **REP-02** | Evaluación de Cumplimiento del POA | Cumplimiento de metas planificadas por área de conocimiento, diferenciando estrictamente las actividades emergentes. |
| **REP-03** | Cobertura Demográfica y Atención de Protagonistas | Desglose demográfico de participantes por sexo, pueblos originarios/étnicos y condición de vulnerabilidad. |
| **REP-04** | Extensión y Descentralización Territorial | Cobertura territorial desagregada por sedes, municipios, comunidades y recintos de la Costa Caribe. |
| **REP-05** | Auditoría de Trazabilidad, Gobernanza y Salud del Dato | Integridad de identificaciones, estado de vinculación POA (V004), discrepancias y notas periciales de calidad. |

---

## 7. Dashboard Institucional de 5 Niveles

El Dashboard consume de manera directa y exclusiva el contrato `DashboardDataDTO`, estructurado en cinco niveles de supervisión:

1. **Nivel 1 — Resumen Ejecutivo**: Indicador Global de Gestión (% ponderado), cobertura total de personas atendidas, ratio de eficiencia territorial y semáforo de salud del repositorio.
2. **Nivel 2 — Actividades y Cumplimiento POA**: Volumen de actividades ejecutadas, índice de cumplimiento de metas POA y contabilización separada de eventos emergentes.
3. **Nivel 3 — Participación y Demografía**: Protagonistas únicos (desduplicados por identificación verificada), índice de equidad de género (% mujeres) y porcentaje de inclusión étnica.
4. **Nivel 4 — Cobertura Territorial**: Sedes activas, municipios impactados y tasa de descentralización territorial fuera del campus principal.
5. **Nivel 5 — Trazabilidad y Salud del Dato**: Porcentaje de registros con cédula verificada, tasa de enlace planificación-ejecución (V004) y estado de completitud de datos en M5.

---

## 8. Stack Tecnológico

### Tecnologías Utilizadas
* **Lenguaje**: Python 3.11+ (certificado y validado en Python 3.14.5).
* **Interfaz de Usuario**: CustomTkinter (interfaz nativa de escritorio, paleta institucional `#0B3C5D`, soporte para modo claro/oscuro).
* **Persistencia Relacional**: SQLite3 (base de datos local ACID, esquemas versionados V001 a V004 con transacciones controladas).
* **Procesamiento de Hojas de Cálculo**: `openpyxl` (para lectura y escritura de matrices oficiales M1–M5 y exportador analítico XLSX).
* **Procesamiento Documental Word**: `python-docx` (para extracción de tablas de asistencia, renderizado de diseños metodológicos y exportador DOCX).
* **Manipulación de Datos**: `pandas` (apoyo en agregaciones y normalización).
* **Aseguramiento de Calidad**: `pytest`, `pytest-cov`, `anyio` (batería de pruebas automatizadas y análisis estático).
* **Control de Versiones**: Git y GitHub (control estricto de procedencia, trazabilidad e integridad de cambios).

### Decisiones Arquitectónicas: Tecnologías Deliberadamente No Utilizadas
* **Matplotlib / Gráficos Pesados**: No utilizado en el aplicativo de escritorio para preservar la velocidad de respuesta y evitar dependencias complejas de renderizado gráfico; los KPIs se representan mediante tarjetas nativas semaforizadas.
* **Motores PDF (ReportLab, wkhtmltopdf)**: No utilizados. La exportación institucional se enfoca en XLSX, DOCX y CSV para permitir auditoría, edición y procesamiento por las instancias académicas.
* **Modelos de IA en Reporting y Dashboard**: No se utiliza IA en el cálculo de indicadores, dashboard ni reportes oficiales. Las cifras institucionales son 100% deterministas y auditables.
* **Migración V005**: No implementada. La base de datos opera sobre las migraciones certificadas V001 a V004 sin alterar las estructuras vigentes.

---

## 9. Calidad de Software y Gobernanza del Dato

### Calidad de Software
* **Batería de Pruebas Automatizadas**: 1,378 pruebas unitarias, de integración, E2E y de aislamiento arquitectónico aprobadas (100% PASS, 0 fallos, 0 errores, 1 prueba omitida por configuración).
* **Aislamiento Arquitectónico Estático (AST)**: Pruebas automatizadas inspeccionan el árbol de sintaxis abstracta para garantizar que:
  - `app.reporting` no contenga dependencias de interfaz gráfica (`customtkinter`), motores gráficos (`matplotlib`) ni servicios de IA.
  - `app.reporting_ui` no contenga llamadas directas a `sqlite3` ni sentencias SQL.
  - `app.word_consolidator` no importe componentes de `app.reporting_ui` (desacoplamiento total vía Composition Root).
* **Inmutabilidad y Preservación Patrimonial**: Verificación criptográfica permanente mediante SHA-256 de las cinco plantillas patrimoniales de Excel y del binario ejecutable oficial (**6/6 hashes MATCH**).
* **Idempotencia y Transaccionalidad**: Operaciones de inserción y exportación diseñadas para ser reproducibles sin generar duplicados ni corromper estados previos.

### Gobernanza de Datos Institucionales
* **Prohibición de Fabricación de Datos**: No se crean ni se infieren registros inexistentes.
* **Preservación Estricta de Nulos (NULL)**: La información ausente se conserva como `NULL` o se etiqueta con categorías normalizadas (`No Especificado`, `Municipio No Especificado`, `Sin Fecha en POA`, `No Aplica`). Queda terminantemente prohibida la imputación estadística automática.
* **Aislamiento de Registros Históricos**: Los 32 registros preexistentes de la Matriz M5 marcados como `es_historico_preexistente = 1` permanecen aislados del período analítico actual.
* **Cómputo Metodológico Multisesión**: En modo `COHORT_UNIQUE` (predeterminado), una actividad planificada con N sesiones operativas computa como 1 cumplimiento de meta sobre la cohorte atendida, evitando inflaciones artificiales del porcentaje de cumplimiento.

---

## 10. Estado Actual del Proyecto

| Módulo / Componente | Estado | Alcance y Certificación |
|---|---|---|
| **Pipeline Word → Matrices M1–M5** | **Implementado y Validado** | Certificado en Fase 29.20.2 (casos D-01 a D-10, extracción, validación Q-01..Q-20 y routing). |
| **Consolidación Matrices → Word** | **Implementado y Validado** | Módulo 2 operativo para generación documental a partir de consolidados. |
| **Planificación Institucional** | **Implementado y Validado** | Certificado en Fases 29.12 a 29.19 (V003, V004, validación V-MD, renderizado DOCX). |
| **Asistencia IA en Planificación** | **Implementado y Validado** | Asistencia controlada para redacción metodológica (Gemini API / Mock fallback). |
| **Motor de Indicadores Institucionales** | **Implementado y Validado** | `IndicatorCalculationService` certificado con cálculo matemático puro sobre SQLite. |
| **Reporting Oficial (REP-01 a REP-05)** | **Implementado y Validado** | Certificado en Fase 29.20.3 (generación y exportación a XLSX, DOCX y CSV). |
| **Dashboard Institucional (5 Niveles)** | **Implementado y Validado** | Certificado en Fase 29.20.3 (visualización jerárquica con filtros de período y sede). |
| **Integración UI Módulo 4** | **Implementado y Validado** | Certificado en Fase 29.20.3.1 (Composition Root en `run_consolidator.py`, menú en grid 2x2). |
| **Exportador PDF** | **Fuera de Alcance** | Deliberadamente descartado por política institucional de formatos editables. |

---

## 11. Información de Release

* **Versión del Sistema**: BICU Consolidador & Reporting Institucional — Release Consolidado Fase 29.20.3.
* **Ejecución y Despliegue**:
  ```bash
  # Iniciar la aplicación desde el Composition Root
  python run_consolidator.py
  ```
* **Ejecución de Pruebas**:
  ```bash
  # Ejecutar suite de pruebas de Reporting y Dashboard
  python -m pytest tests/test_fase_29_20_3_reporting_dashboard.py -v

  # Ejecutar suite completa de regresión
  python -m pytest -q
  ```
* **Requisitos**: Python 3.11+ con dependencias listadas en el entorno institucional (`customtkinter`, `openpyxl`, `python-docx`, `pandas`, `pydantic`, `pytest`).

---

**Bluefields Indian & Caribbean University (BICU)**  
*Desarrollado bajo estándares de ingeniería de software, arquitectura limpia, trazabilidad institucional y resguardo patrimonial del dato.*
