@echo off
chcp 65001 >nul
title Job Finder San Miguel - Directorio de Empresas y Entrevistas
cd /d "%~dp0"

.\venv\Scripts\python.exe main.py --empresas
echo.
pause
