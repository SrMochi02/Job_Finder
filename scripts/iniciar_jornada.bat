@echo off
chcp 65001 >nul
title Job Finder San Miguel - Jornada Continua (7:00 AM a 4:00 PM)
cd /d "%~dp0.."

echo ============================================================================
echo   INICIANDO JOB FINDER - SAN MIGUEL (JORNADA AUTOMATICA 7:00 AM - 4:00 PM)
echo ============================================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [1/3] Creando entorno virtual venv...
    python -m venv venv
)

echo [2/3] Verificando dependencias instaladas...
.\venv\Scripts\pip.exe install -q -r requirements.txt
.\venv\Scripts\playwright.exe install chromium

echo.
echo [3/3] Dejando activa la aplicacion...
echo (Para detenerla en cualquier momento presiona Ctrl + C)
echo ============================================================================
echo.

.\venv\Scripts\python.exe main.py --jornada
pause
