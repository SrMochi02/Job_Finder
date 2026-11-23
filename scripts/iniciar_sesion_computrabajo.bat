@echo off
chcp 65001 >nul
title Job Finder San Miguel - Iniciar Sesion en Computrabajo
cd /d "%~dp0.."

echo ============================================================================
echo   GUARDAR SESION EN COMPUTRABAJO PARA AUTO-POSTULACION EN 1 CLIC
echo ============================================================================
echo.
.\venv\Scripts\python.exe main.py --login-portales
pause
