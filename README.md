# BICU — Sistema de Gestión Institucional de Asistencias y Actividades

Sistema de software orientado a la gestión, organización, validación, seguimiento y consolidación de información relacionada con las actividades institucionales de la **Bluefields Indian & Caribbean University (BICU)**.

El sistema proporciona un entorno estructurado, determinista y auditable para procesar informes de ejecución universitaria, asegurar la calidad de datos y soportar la planificación metodológica institucional con generación documental oficial.

---

## 1. Propósito del Sistema

En el entorno universitario, la gestión de actividades comprende múltiples flujos de información: documentación de planificación académica, listas de participantes, evidencias de ejecución e informes de cumplimiento. Tradicionalmente, la consolidación de estos datos requiere procesos manuales propensos a inconsistencias, duplicidad y pérdida de trazabilidad.

Este sistema resuelve dicha problemática mediante:

* **Estandarización y Validación**: Aplicación sistemática de reglas de calidad institucional para verificar la coherencia de datos antes de su consolidación o aprobación.
* **Persistencia Auditable**: Almacenamiento estructurado en base de datos relacional que preserva la trazabilidad completa desde el documento de origen hasta las matrices y documentos oficiales.
* **Generación Documental Oficial**: Emisión automatizada de matrices en hojas de cálculo y documentos metodológicos en formato Word (`.docx`), respetando estrictamente las normas institucionales.
* **Separación de Responsabilidades**: Aislamiento arquitectónico estricto entre los procesos de planificación y los registros de ejecución real.

---

## 2. Alcance del Sistema

El sistema comprende dos dominios funcionales independientes y complementarios:

### 2.1 Procesamiento de Ejecución (Word → Matrices M1–M5)
Procesamiento automatizado de informes de actividades ejecutadas en formato Word (`.docx`), extracción de metadatos y participantes, validación de reglas de calidad, persistencia transaccional y generación de las cinco matrices consolidadas oficiales en hojas de cálculo.

### 2.2 Planificación Institucional y Diseño Metodológico
Modelado estructurado de actividades planificadas, gestión de diseños metodológicos, persistencia dedicada en SQLite V003, validación institucional y renderizado de documentos técnicos institucionales en formato Word (`.docx`).

> **Principio Fundamental de Diseño:**<br>
> **PLANIFICADO ≠ EJECUTADO**<br>
> Una actividad planificada representa una intención formalizada y no constituye evidencia de ejecución real. El procesamiento de un informe de ejecución real no depende de la existencia previa de un diseño metodológico, garantizando la independencia operativa y la integridad de ambas etapas.

---

## 3. Arquitectura del Sistema

El proyecto sigue una arquitectura en capas fundamentada en principios de diseño orientado al dominio (*Domain-Driven Design*) y arquitectura limpia:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           CAPA DE PRESENTACIÓN                          │
│        Interfaz Gráfica de Usuario (CustomTkinter) / CLI / Workers      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                           CAPA DE APLICACIÓN                            │
│           Servicios de Aplicación / Casos de Uso / Orquestadores         │
└───────────────────┬─────────────────────────────────┬───────────────────┘
                    │                                 │
┌───────────────────▼─────────────────┐   ┌───────────▼───────────────────┐
│         DOMINIO DE EJECUCIÓN        │   │    DOMINIO DE PLANIFICACIÓN   │
│  Actividades, Personas, Evidencias, │   │  PlannedActivity, Methodological  │
│  Reglas de Calidad Q-01..Q-20,      │   │  Design, FAQ, Agenda, Matriz     │
│  Enrutamiento Institucional         │   │  Operativa, Reglas V-MD-01..14    │
└───────────────────┬─────────────────┘   └───────────┬───────────────────┘
                    │                                 │
┌───────────────────▼─────────────────────────────────▼───────────────────┐
│                         CAPA DE INFRAESTRUCTURA                         │
│  • Persistencia: SQLite (V001, V002, V003 con migraciones deterministas)│
│  • Extractores: WordActivityExtractor (.docx)                          │
│  • Exportadores: OpenPyXL (M1–M5 con protección patrimonial)           │
│  • Renderizadores: DocxMethodologicalDocumentRenderer (python-docx)    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Flujos Principales de Información

Ambos dominios operan a través de flujos unidireccionales estrictamente separados:

### 4.1 Flujo de Ejecución y Consolidación (Word → M1–M5)

```text
INFORME DE ACTIVIDAD WORD (.docx)
              ↓
          EXTRACCIÓN         (Metadatos de actividad, participantes, evidencias)
              ↓
          VALIDACIÓN         (Reglas de calidad Q-01 a Q-20, detección de duplicados)
              ↓
         PERSISTENCIA        (Registro transaccional en base de datos SQLite)
              ↓
         ENRUTAMIENTO        (Clasificación institucional por perfil y tipo de vínculo)
              ↓
            M1–M5            (Generación de las 5 matrices oficiales en formato Excel)
```

### 4.2 Flujo de Planificación y Generación Documental (Planning → DOCX)

```text
ACTIVIDAD PLANIFICADA
          ↓
DISEÑO METODOLÓGICO          (Estructuración de bloques institucionales: FAQs, Agenda, Matriz)
          ↓
      VALIDACIÓN             (Motor de reglas institucionales V-MD-01 a V-MD-14)
          ↓
      APROBACIÓN             (Transición de estados DRAFT → REVIEW → APPROVED con regla R-08)
          ↓
  PERSISTENCIA V003          (Almacenamiento transaccional segregado en SQLite)
          ↓
  RENDERIZADOR DOCX          (Generación desacoplada del documento oficial .docx)
```

---

## 5. Matrices Institucionales Oficiales

El subsistema de consolidación genera cinco matrices en hojas de cálculo electrónicas (`.xlsx`), empleando plantillas base institucionales certificadas:

* **M1 — Consolidado de Actividades**: Registro general de actividades ejecutadas, fecha, unidad académica, modalidad, tipo de evento y resumen cuantitativo de participación.
* **M2 — Estudiantes**: Padrón detallado de estudiantes participantes, incluyendo carrera, año académico, sexo y desglose demográfico institucional.
* **M3 — Académicos y Administrativos**: Registro de docentes, investigadores y personal administrativo involucrado en las actividades.
* **M4 — Colaboradores**: Registro de personal de apoyo, enlaces comunitarios y facilitadores externos participantes.
* **M5 — Protagonistas Beneficiados**: Detalle de beneficiarios comunitarios, productores, emprendedores o actores sociales atendidos por programas universitarios.

---

## 6. Planificación Institucional y Diseño Metodológico

El módulo de planificación (`app/planning/`) modela la fase preparatoria de las intervenciones universitarias, garantizando rigor técnico, consistencia metodológica y trazabilidad institucional.

### 6.1 Componentes del Dominio
* **`PlannedActivity`**: Entidad raíz que representa una actividad proyectada, con código institucional, título, fechas previstas, responsable y presupuesto estimado.
* **`MethodologicalDesign`**: Entidad agregada que consolida el contenido técnico de la actividad bajo un ciclo de vida controlado (`DRAFT`, `REVIEW`, `APPROVED`, `REJECTED`, `ARCHIVED`).
* **`FAQ`**: Registro estructurado de preguntas frecuentes y respuestas operativas para facilitadores y participantes.
* **`Agenda`**: Cronograma detallado de sesiones, horarios, temas y responsables.
* **`OperationalMatrix`**: Matriz operativa que alinea objetivos específicos, actividades, resultados esperados, indicadores y recursos requeridos.
* **`AIProposal`**: Entidad para el registro auditable de sugerencias metodológicas asistidas (preparada para fases futuras).

### 6.2 Bloques Institucionales del Diseño Metodológico
Los documentos de Diseño Metodológico se estructuran en secciones institucionales normalizadas:

1. **Encabezado y Metadatos**: Identificación institucional, nombre del taller o evento, código de actividad, fecha y responsables.
2. **Introducción y Justificación**: Contexto, antecedentes institucionales y motivación de la intervención.
3. **Objetivos Metodológicos**: Objetivo general y objetivos específicos alineados con las líneas estratégicas de la universidad.
4. **Metodología y Resultados Esperados**: Enfoque pedagógico, dinámicas participativas y entregables previstos.
5. **Preguntas Frecuentes (FAQ)**: Respuestas a dudas operativas clave sobre la actividad.
6. **Programa / Agenda**: Estructura temporal y metodológica de la jornada.
7. **Matriz de Planificación Operativa**: Tabla de articulación entre objetivos, metas, indicadores, fuentes de verificación y responsables.
8. **Pie de Aprobación**: Registro formal de autorización institucional con identificador del aprobador.

---

## 7. Persistencia, Integridad y Generación Documental

### 7.1 Persistencia Relacional en SQLite
El sistema utiliza SQLite como motor de persistencia relacional local, estructurado en esquemas versionados y gobernados por migraciones deterministas (`MigrationRunner`):
* **Migración V001**: Tablas fundamentales de actividades ejecutadas, personas, perfiles institucionales, asistencias, evidencias, informes de actividades y auditoría de eventos de consolidación.
* **Migración V002**: Agregación métrica y tablas de soporte analítico.
* **Migración V003**: Esquema segregado de planificación (`planning_planned_activities`, `planning_methodological_designs`, `planning_design_faqs`, `planning_design_agenda`, `planning_design_operational_matrix`, `planning_ai_proposals`).

La segregación de esquemas asegura que las operaciones del módulo de planificación no inserten, modifiquen ni consulten registros en las tablas de ejecución histórica, garantizando el principio `PLANIFICADO ≠ EJECUTADO`.

### 7.2 Garantías de Integridad del Sistema
* **Validación de Reglas de Calidad**:
  - Dominio de Ejecución: Reglas Q-01 a Q-20 para validación de datos de entrada, consistencia demográfica y no duplicación.
  - Dominio de Planificación: Reglas V-MD-01 a V-MD-14 para completitud metodológica, coherencia de objetivos (R-07) y requisitos de estructura antes de transiciones de estado.
* **Transaccionalidad (Unit of Work)**: Todas las operaciones de guardado y actualización se ejecutan bajo transacciones atómicas con reversión automática en caso de error.
* **Idempotencia**: La creación de borradores para una actividad existente y la re-exportación de documentos son operaciones idempotentes que impiden estados inconsistentes.
* **Reconstrucción desde Persistencia**: Los agregados de dominio pueden ser reconstituidos íntegramente desde SQLite mediante nuevas conexiones independientes sin pérdida de relaciones hijas (FAQs, agenda, matriz operativa).
* **Inmutabilidad de Estados Aprobados (Regla R-08)**: Un diseño metodológico en estado `APPROVED` queda permanentemente congelado; cualquier intento de modificación de contenido, retroceso de estado o segunda aprobación es rechazado a nivel de servicio y dominio.
* **Trazabilidad Integral**: Cada entidad registra identificadores de autoría, modificación, fechas y usuario aprobador institucional.

### 7.3 Generador Documental DOCX Desacoplado
La exportación a documento Word (`.docx`) se realiza mediante un motor de renderizado independiente (`DocxMethodologicalDocumentRenderer`):
* **Aislamiento Total**: No posee dependencias con la base de datos ni con el consolidador de matrices (`app.word_consolidator`). Opera exclusivamente a partir de objetos de transferencia de datos (`MethodologicalDesignDTO`).
* **Estándar Visual Institucional**: Aplica especificaciones tipográficas, jerarquías de títulos, estilos de tablas y metadatos de aprobación conforme a la normativa de la universidad.
* **Verificación de 11 Criterios**: Todo documento generado satisface 11 criterios estructurales, incluyendo integridad ZIP/OpenXML, presencia de metadatos, justificación, objetivos, tablas de agenda y matriz operativa, y pie de aprobación.

---

## 8. Checkpoint Certificado: Fase 29.12

### Integración Operativa Planificación → Diseño → Validación → Aprobación → DOCX

* **Objetivo:** Demostrar y certificar la integración operativa de extremo a extremo del flujo institucional completo de planificación académica utilizando capacidades públicas certificadas, sin mocks y sobre bases de datos reales.
* **Alcance:** Creación de actividad planificada, estructuración del diseño metodológico, validación institucional con reglas bloqueantes, transición a revisión, aprobación formal con congelamiento, reconstrucción limpia desde SQLite y renderizado del documento oficial en formato Word (`.docx`).
* **Capacidades Verificadas:**
  1. Flujo operativo secuencial de 19 pasos completado con éxito de punta a punta.
  2. Idempotencia en la inicialización de borradores y exportación documental.
  3. Aplicación estricta de la regla R-08 (inmutabilidad de diseños aprobados ante intentos de edición o transición).
  4. Reconstrucción completa del diseño desde una conexión SQLite limpia e independiente.
  5. Verificación pericial de los 11 criterios físicos y semánticos del archivo DOCX generado.
  6. Cumplimiento estricto de `PLANIFICADO ≠ EJECUTADO`: 0 registros insertados en las 18 tablas funcionales de ejecución e histórico.
  7. Aislamiento de auditoría: 0 registros insertados en `auditoria_evento`.
  8. Aislamiento estático (AST): 0 importaciones cruzadas entre `app.word_consolidator` y `app.planning`.
* **Pruebas Realizadas:**
  - Suite E2E de Integración Operativa (`tests/test_planning_operational_integration_e2e.py`): 3/3 PASS.
  - Suite de Persistencia de Planificación (`tests/test_planning_persistence.py`): 20/20 PASS.
  - Suite de Interfaz de Planificación (`tests/test_planning_ui.py`): 17/17 PASS.
  - Suite Completa de Planificación (`tests/test_planning/`): 147/147 PASS.
  - Suite Global de Regresión: 1,183/1,183 PASS.
* **Resultado General:** **1,183 pruebas aprobadas, 0 fallos, 0 errores**.
* **Restricciones:** Operación libre de modelos de inteligencia artificial en esta fase; preservación de la arquitectura Word $\rightarrow$ M1–M5 y plantillas patrimoniales.
* **Estado del Módulo:** **Certificado e Integrado Operativamente.**

---

## 9. Calidad y Control de Pruebas Automatizadas

El proyecto aplica una directiva estricta de aseguramiento de calidad:
**EXTEND before MODIFY · ISOLATE before INTEGRATE · TEST before ADVANCE**

### 9.1 Resultados Agregados de Pruebas
```text
============================== test session starts ==============================
Total de pruebas automatizadas: 1,183 passed
Fallos (Failures):             0
Errores (Errors):              0
Warnings:                      39 (compatibilidad openpyxl preexistentes)
Tiempo de ejecución:           ~392s
Estado de la suite:            100% PASS
=================================================================================
```

### 9.2 Integridad Patrimonial Certificada
El sistema custodia seis componentes patrimoniales institucionales cuya integridad criptográfica se audita de forma continua:
* Plantilla M1 (Consolidado de Actividades)
* Plantilla M2 (Estudiantes)
* Plantilla M3 (Académicos y Administrativos)
* Plantilla M4 (Colaboradores)
* Plantilla M5 (Protagonistas Beneficiados)
* Ejecutable institucional certificado (`BICU_Consolidador.exe`)

Los seis componentes han sido verificados y permanecen íntegros, inalterados y conformes con sus especificaciones de referencia.

---

## 10. Seguridad y Privacidad de la Información

* **Protección de Datos Institucionales**: Los documentos institucionales reales, listas de asistencia de participantes, identificadores personales, números telefónicos y bases de datos con información institucional sensible **no forman parte del repositorio público**.
* **Exclusión Rigurosa en `.gitignore`**: Se excluyen de forma irrestricta bases de datos locales (`*.db`, `*.sqlite`), hojas de cálculo institucionales, informes Word, archivos temporales, ejecutables, logs y variables de entorno (`.env`).
* **Pruebas con Datos Sintéticos**: La totalidad de las pruebas automatizadas públicas opera exclusivamente sobre fixtures controlados, datos sintéticos y estructuras anonimizadas.
* **Gestión de Credenciales**: El repositorio no almacena credenciales, claves criptográficas, certificados privados, llaves de API ni contraseñas de ningún tipo.

---

## 11. Evolución del Proyecto y Roadmap

### 11.1 Hitos Completados
* **Consolidación Word → M1–M5**: Extracción, validación de reglas Q-01 a Q-20, enrutamiento por perfil y generación de matrices consolidadas.
* **Validación y Certificación de Matrices**: Verificación de no alteración de plantillas oficiales y preservación patrimonial.
* **Dominio de Planificación y Reglas Institucionales**: Entidades, value objects, catálogo institucional y reglas V-MD-01 a V-MD-14.
* **Persistencia Relacional SQLite V003**: Esquema segregado, transacciones atómicas, Unit of Work y repositorios especializados.
* **Motor de Renderizado DOCX**: Generación desacoplada de documentos Word institucionales conforme a especificación visual oficial.
* **Capa de Interfaz de Usuario de Planificación**: Interfaz gráfica en CustomTkinter con vistas de catálogo, detalle, editor y diálogos de validación/aprobación.
* **Integración Operativa E2E (Fase 29.12)**: Certificación de punta a punta del flujo Planificación $\rightarrow$ Diseño $\rightarrow$ Validación $\rightarrow$ Aprobación $\rightarrow$ DOCX sin mocks y con aislamiento total.

### 11.2 En Planificación (Fases Futuras)
* Integración de servicios asistenciales para sugerencias metodológicas controladas (Fase 29.13).
* Generación de informes comparativos de cumplimiento entre actividades planificadas y actividades efectivamente ejecutadas.
* Exportación de reportes institucionales consolidados por período académico.

---

**BICU — Bluefields Indian & Caribbean University**  
*Desarrollado con disciplina de ingeniería de software, arquitectura limpia y resguardo de la integridad institucional.*
