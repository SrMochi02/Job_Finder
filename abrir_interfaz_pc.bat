@echo off
chcp 65001 > nul
title Job Finder Desktop - Aplicacion para PC
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [1/2] Creando entorno virtual por primera vez...
    python -m venv venv
    venv\Scripts\pip.exe install -r requirements.txt
    venv\Scripts\playwright.exe install chromium
)

echo Abriendo interfaz grafica de Job Finder Desktop...
start "" "venv\Scripts\pythonw.exe" interfaz_pc.py
