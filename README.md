# BICU — Sistema de Gestión Institucional de Asistencias y Actividades

Sistema de software orientado a la gestión, organización, validación, seguimiento y consolidación de información relacionada con las actividades institucionales de la **Bluefields Indian & Caribbean University (BICU)**.

El sistema proporciona un entorno estructurado, determinista y auditable para procesar informes de ejecución universitaria, asegurar la calidad de datos y soportar la planificación metodológica institucional con generación documental.

---

## 1. Propósito del Sistema

En el entorno universitario, la gestión de actividades comprende múltiples flujos de información: documentación de planificación, listas de participantes, evidencias de ejecución e informes de cumplimiento. Tradicionalmente, la consolidación de estos datos requiere procesos manuales propensos a inconsistencias, duplicidad y pérdida de trazabilidad.

Este sistema resuelve dicha problemática mediante:

* **Estandarización y Validación**: Aplicación sistemática de reglas de calidad institucional para verificar la coherencia de datos antes de su consolidación.
* **Persistencia Auditable**: Almacenamiento estructurado que preserva la trazabilidad completa desde el documento de origen hasta las matrices consolidadas.
* **Generación Documental Oficial**: Emisión automatizada de matrices en hojas de cálculo y documentos metodológicos en formato Word (`.docx`), respetando estrictamente las normas institucionales.
* **Separación de Responsabilidades**: Aislamiento arquitectónico estricto entre los procesos de planificación y los registros de ejecución real.

---

## 2. Alcance del Sistema

El sistema comprende dos dominios funcionales independientes y complementarios:

### 2.1 Procesamiento de Ejecución (Word → Matrices M1–M5)
Procesamiento automatizado de informes de actividades ejecutadas en formato Word (`.docx`), extracción de metadatos y participantes, validación de reglas de calidad, persistencia transaccional y generación de las cinco matrices consolidadas oficiales en Excel.

### 2.2 Planificación Institucional y Diseño Metodológico
Modelado estructurado de actividades planificadas, gestión de diseños metodológicos, persistencia dedicada en SQLite V003 y renderizado de documentos técnicos institucionales en formato Word (`.docx`).

> **Principio de Aislamiento Institucional:**  
> **PLANIFICADO ≠ EJECUTADO**  
> Una actividad planificada representa una intención formalizada que no genera automáticamente registros de ejecución. El procesamiento de un informe de ejecución real no depende de la existencia previa de un diseño metodológico, garantizando la independencia operativa de ambas etapas.

---

## 3. Arquitectura del Sistema

El proyecto sigue una arquitectura en capas inspirada en principios de arquitectura limpia (*Clean Architecture*) y diseño guiado por el dominio (*Domain-Driven Design*):

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
│  Enrutamiento Institucional         │   │  Operativa, Validadores           │
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

### 4.1 Flujo de Ejecución y Consolidación

```text
INFORME WORD (.docx)
         ↓
    EXTRACCIÓN        (Metadatos de actividad, participantes, evidencias)
         ↓
    VALIDACIÓN        (Reglas de calidad Q-01 a Q-20, detección de duplicados)
         ↓
   PERSISTENCIA       (Registro transaccional en base de datos SQLite)
         ↓
   ENRUTAMIENTO       (Clasificación institucional por perfil y tipo de vínculo)
         ↓
      M1–M5           (Generación de las 5 matrices oficiales en formato Excel)
```

### 4.2 Flujo de Planificación y Generación Documental

```text
ACTIVIDAD PLANIFICADA (Definición de metadatos, metas y responsables)
         ↓
DISEÑO METODOLÓGICO   (Estructuración de los cinco bloques institucionales)
         ↓
  PERSISTENCIA V003   (Almacenamiento segregado en SQLite V003)
         ↓
  RENDERIZADOR DOCX   (Generación desacoplada del documento oficial .docx)
```

---

## 5. Matrices Institucionales Oficiales

El subsistema de consolidación genera cinco matrices en hojas de cálculo electrónicas (`.xlsx`), empleando plantillas base certificadas:

* **M1 — Consolidado de Actividades**: Registro general de actividades ejecutadas, fecha, unidad académica, modalidad, tipo de evento y resumen cuantitativo de participación.
* **M2 — Estudiantes**: Padrón detallado de estudiantes participantes, incluyendo carrera, año académico, sexo y desglose demográfico institucional.
* **M3 — Académicos y Administrativos**: Registro de docentes, investigadores y personal administrativo involucrado en las actividades.
* **M4 — Colaboradores**: Registro de personal de apoyo, enlaces comunitarios y facilitadores externos participantes.
* **M5 — Protagonistas Beneficiados**: Detalle de beneficiarios comunitarios, productores, emprendedores o actores sociales atendidos por programas universitarios.

---

## 6. Planificación Institucional y Diseño Metodológico

El módulo de planificación (`app/planning/`) modela la fase preparatoria de las intervenciones universitarias, garantizando rigor técnico y coherencia operativa.

### 6.1 Componentes del Dominio
* **`PlannedActivity`**: Entidad raíz que representa una actividad proyectada, con código institucional, título, fechas previstas, responsable y presupuesto estimado.
* **`MethodologicalDesign`**: Entidad agregada que consolida el contenido técnico de la actividad bajo un estado de diseño (`DRAFT`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `ARCHIVED`).
* **`FAQ`**: Registro estructurado de preguntas frecuentes y respuestas operativas para facilitadores y participantes.
* **`Agenda`**: Cronograma detallado de sesiones, horarios, temas e instructores responsables.
* **`OperationalMatrix`**: Matriz operativa que alinea objetivos específicos, actividades, resultados esperados, indicadores y recursos requeridos.
* **`AIProposal`**: Registro auditable de sugerencias y estructuraciones metodológicas asistidas, con trazabilidad de aceptación o rechazo por el usuario.

### 6.2 Los Cinco Bloques Institucionales del Diseño Metodológico
Los documentos de Diseño Metodológico se estructuran en cinco bloques oficiales:

1. **Introducción**: Contexto, justificación institucional y antecedentes de la intervención.
2. **Objetivos**: Objetivo general y objetivos específicos alineados con las líneas estratégicas de la universidad.
3. **Preguntas Frecuentes (FAQ)**: Respuestas a dudas operativas clave sobre la actividad.
4. **Programa / Agenda**: Estructura temporal y metodológica de la jornada.
5. **Matriz de Planificación Operativa**: Tabla de articulación entre objetivos, metas, indicadores y responsables.

> *Nota Técnica:* El título del diseño metodológico y sus metadatos de encabezado se gestionan como elementos documentales independientes, garantizando que el cuerpo técnico preserve intactos sus cinco bloques institucionales.

---

## 7. Persistencia y Generación Documental DOCX

### 7.1 Persistencia SQLite V003
El módulo de planificación incorpora un esquema relacional segregado en SQLite (`schema_v003`), gestionado mediante un mecanismo de migraciones transaccionales y deterministas (`MigrationRunner`).

Las tablas de planificación (`planning_activity`, `methodological_design`, `methodological_design_section`, `operational_matrix_row`, etc.) operan de forma estrictamente aislada respecto a las tablas de ejecución y matrices, impidiendo la contaminación cruzada entre lo planificado y lo ejecutado.

### 7.2 Generador Documental DOCX Desacoplado
La generación del documento Word (`.docx`) se realiza a través de un flujo unidireccional y desacoplado:

```text
SQLite V003
    ↓
Repositorio (MethodologicalDesignRepository)
    ↓
Entidad de Dominio (MethodologicalDesign)
    ↓
Objeto de Transferencia (MethodologicalDesignDTO)
    ↓
Renderizador Documental (DocxMethodologicalDocumentRenderer)
    ↓
Documento Institucional DOCX
```

El renderizador documental implementa las siguientes garantías arquitectónicas:
* **Desacoplamiento total**: No depende de SQLite ni del consolidador de matrices (`app.word_consolidator`).
* **Estándar visual institucional**: Utiliza un catálogo de estilos tipográficos, espaciados y paletas cromáticas alineadas con la identidad visual de la universidad.
* **Comprobación de no contaminación**: Las pruebas automatizadas verifican pericialmente que la generación de un documento DOCX no modifique ninguna tabla de ejecución ni altere los consolidados existentes.

---

## 8. Calidad y Certificación Técnica

El proyecto se rige por la directiva técnica:  
**EXTEND before MODIFY · ISOLATE before INTEGRATE · TEST before ADVANCE**

### 8.1 Resultados de Pruebas Automatizadas
* **1120 pruebas automatizadas ejecutadas**, con **0 fallos y 0 errores**.
* **Estado de advertencias**: 39 advertencias preexistentes asociadas a la biblioteca de lectura de hojas de cálculo (`openpyxl`), 0 advertencias nuevas.

### 8.2 Integridad Patrimonial Certificada
El sistema custodia seis componentes patrimoniales certificados cuyas sumas de verificación criptográfica (SHA-256) son auditadas continuamente:
* Plantilla M1 (Consolidado de Actividades)
* Plantilla M2 (Estudiantes)
* Plantilla M3 (Académicos y Administrativos)
* Plantilla M4 (Colaboradores)
* Plantilla M5 (Protagonistas Beneficiados)
* Ejecutable institucional certificado (`BICU_Consolidador.exe`)

Los seis componentes han sido verificados y permanecen íntegros y conformes a sus valores certificados de referencia.

---

## 9. Seguridad y Privacidad de la Información

* **Protección de Datos Institucionales**: Los documentos institucionales reales, listas de asistencia de participantes, cédulas, números telefónicos y bases de datos con información real de la universidad **no forman parte del repositorio público**.
* **Exclusión Rigurosa**: El archivo `.gitignore` excluye formalmente todos los directorios de validación interna, corpus real, bases de datos locales (`*.db`, `*.sqlite`), exportaciones intermedias y registros de auditoría local.
* **Pruebas con Datos Sintéticos**: La totalidad de las pruebas automatizadas públicas opera exclusivamente sobre datos sintéticos y estructuras anonimizadas.
* **Gestión de Credenciales**: El repositorio no almacena credenciales, claves criptográficas, certificados privados, variables de entorno sensibles (`.env`) ni llaves de acceso a servicios externos.

---

## 10. Evolución del Proyecto y Roadmap

### 10.1 Hitos Completados
* **Consolidación Word → M1–M5**: Extracción, validación de reglas Q-01 a Q-20, enrutamiento por perfil y generación de matrices consolidadas.
* **Validación y Certificación de Matrices**: Verificación pericial de no alteración de plantillas oficiales y preservación patrimonial.
* **Diseño del Dominio de Planificación**: Implementación del modelo de dominio para actividades planificadas y diseños metodológicos.
* **Persistencia SQLite V003**: Esquema relacional segregado con soporte para transacciones y migraciones deterministas.
* **Renderer Documental DOCX**: Motor de renderizado en `python-docx` para emisión de diseños metodológicos institucionales.
* **Integración y Aislamiento**: Integración end-to-end certificada entre repositorio de planificación, DTOs y generador DOCX, con verificación de aislamiento pericial.

### 10.2 En Desarrollo
* Interfaz gráfica de usuario para la edición y visualización de actividades planificadas.
* Módulo de revisión institucional y flujo de aprobación de diseños metodológicos.

### 10.3 Pendiente
* Generación de informes comparativos de cumplimiento entre actividades planificadas y actividades efectivamente ejecutadas.
* Exportación de reportes institucionales consolidados por período académico.

---

**BICU — Bluefields Indian & Caribbean University**  
*Desarrollado con disciplina de ingeniería de software, arquitectura limpia y resguardo de la integridad institucional.*
