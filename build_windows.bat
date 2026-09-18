@echo off
rem =============================================================================
rem build_windows.bat
rem Script de compilacion y empaquetado Windows para el Consolidador BICU
rem Fase 14.10 -- Distribucion Windows
rem =============================================================================

setlocal enabledelayedexpansion

echo =====================================================================
echo  BICU - Consolidador Institucional de Asistencias
echo  Generador de Paquete Distribuible Windows (.exe)
echo =====================================================================
echo.

rem 1. Verificar Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el PATH del sistema.
    echo Asegurese de tener Python 3.10+ instalado y agregado a PATH.
    pause
    exit /b 1
)

echo [1/4] Verificando version de Python...
python -c "import sys; print('Python detectado:', sys.version)"
echo.

rem 2. Instalar dependencias de empaquetado si es necesario
echo [2/4] Verificando herramientas de build (requirements-build.txt)...
python -m pip install -r requirements-build.txt --quiet
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de herramientas de empaquetado.
    pause
    exit /b 1
)
echo Herramientas de empaquetado listas.
echo.

rem 3. Ejecutar PyInstaller con el archivo spec
echo [3/4] Ejecutando PyInstaller con BICU_Consolidador.spec...
set PYTHONPATH=.
python -m PyInstaller BICU_Consolidador.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo el proceso de compilacion de PyInstaller.
    pause
    exit /b 1
)

echo.
echo [4/4] Verificando resultado de compilacion...
if exist "dist\BICU_Consolidador\BICU_Consolidador.exe" (
    echo.
    echo =====================================================================
    echo  COMPILACION EXITOSA
    echo =====================================================================
    echo  Ejecutable generado en:
    echo  dist\BICU_Consolidador\BICU_Consolidador.exe
    echo.
    echo  Para distribuir, copie toda la carpeta dist\BICU_Consolidador\
    echo =====================================================================
) else (
    echo [ERROR] No se encontro el ejecutable en dist\BICU_Consolidador\BICU_Consolidador.exe
    pause
    exit /b 1
)

echo.
pause
exit /b 0
