# CHECKPOINT DE PUBLICACIÓN EN GITHUB — BASELINE CERTIFICADO Y SEGUNDO COMMIT

**Fecha:** 18 de Septiembre de 2026  
**Documento:** `CHECKPOINT_GITHUB_BASELINE_1.md`  
**Estado:** `PUBLICACIÓN CERRADA — CONTROL ESTRICTO`  
**Versión Base Estable:** `v1.0.3` (Congelada, Certificada e Inmutable)  

---

## 1. REPOSITORIO

* **URL Remota Oficial:** `https://github.com/Kev287mejia/AutomatizacionInnovacionBicu.git`
* **Rama Principal:** `main`
* **Commit Inicial:** `6253301` — *"Establece la base del proyecto de gestión institucional BICU"*
* **Segundo Commit:** `e4831dc` — *"Ajusta la lectura de archivos de entrada del sistema"*
* **Estado Final del Working Tree:** `clean` (`nothing to commit, working tree clean`)
* **Resultado del Push:** Exitoso y normal (`6253301..e4831dc main -> main`), sin uso de force push ni rebase.
* **Alineación Remota:** `origin/main` sincronizado exactamente con `e4831dcac68bac3386829954ed9246479a8292fe`.

---

## 2. BASELINE FUNCIONAL CERTIFICADO

Se ejecutó la suite completa de pruebas automatizadas sobre el entorno de producción local previo al commit:

```text
============================== test session starts ==============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: c:\Users\LENOVO X1 YOGA\OneDrive\Desktop\AUTOMATIZACION PROFE KENIA
configfile: pytest.ini
collected 722 items

============================== warnings summary ===============================
25 warnings (openpyxl Data Validation extension warnings)

================ 722 passed, 25 warnings in 305.13s (0:05:05) =================
```

* **Total de tests colectados:** `722`
* **Passed:** `722`
* **Failures:** `0`
* **Errors:** `0`
* **Warnings:** `25` (advertencias benignas de compatibilidad de openpyxl)
* **Tests Patrimoniales:** `544 passed (100% de la suite histórica v1.0.3 intacta)`

---

## 3. INTEGRIDAD PATRIMONIAL DEL BINARIO v1.0.3

Comprobación criptográfica del artefacto oficial compilado:
```powershell
Get-FileHash "release\BICU_Consolidador.exe" -Algorithm SHA256 | Select-Object -ExpandProperty Hash
```
* **SHA-256 Oficial Esperado:** `0A94BE44DE80079FFCEEE8ABE34025CB6F604BC8A3126E209D221E4828DF214B`
* **SHA-256 Obtenido en Disco:** `0A94BE44DE80079FFCEEE8ABE34025CB6F604BC8A3126E209D221E4828DF214B`
* **Dictamen:** **EXACTO / INALTERADO (100% INTEGRIDAD GARANTIZADA)**

---

## 4. CORRECCIÓN DE INPUT Y CONTROL DE ARTEFACTOS

* **Preservación de `.gitkeep`:** El archivo `input/.gitkeep` permanece en el repositorio para preservar la jerarquía de directorios en Git.
* **Aislamiento de control:** `input/.gitkeep` ya no es interpretado como un archivo o documento institucional de entrada por los modos CLI (`analyze`, `validate`).
* **Detección normal de archivos reales:** Todos los archivos regulares y legítimos de entrada (`.docx`, `.xlsx`, etc.) continúan siendo detectados y procesados con normalidad.
* **Alcance mínimo:** `app/main.py` contiene el único cambio funcional de esta etapa (filtro que excluye archivos de control con prefijo `.` y valida `is_file()`).

---

## 5. AUDITORÍA DE SEGURIDAD Y PRIVACIDAD

Se certifica que en este checkpoint NO se incluyeron ni publicaron:
* Cédulas de identidad o números de carné institucionales.
* Nombres, apellidos ni datos personales de participantes o docentes.
* Listas de asistencia físicas, escaneadas o digitales.
* Archivos reales de actividades de BICU.
* Informes Word institucionales ni matrices Excel con datos de prueba real.
* Documentos PDF internos ni bitácoras de auditoría interna de desarrollo.
* Bases de datos SQLite físicas ni archivos `.env`.
* Contraseñas, API keys, tokens o credenciales de ningún tipo.
* Archivos temporales o de sincronización en la nube (OneDrive).

El repositorio público conserva únicamente el código fuente auditado, la estructura base y la documentación descriptiva de propósito institucional aprobada en `README.md`.

---

```text
======================================================================
CHECKPOINT GITHUB — COMPLETADO
======================================================================

BASELINE: 722/722
PATRIMONIALES: 544/544
SHA v1.0.3: EXACTO
GITHUB: PUBLICADO
WORKING TREE: LIMPIO
SEGUNDO COMMIT: CREADO
PUSH: COMPLETADO

FASE 26.6.1: NO INICIADA

STOP GATE: ACTIVADO
======================================================================
```
