@echo off
chcp 65001 >nul
title Job Finder San Miguel - Vincular WhatsApp Web (Escaneo QR)
cd /d "%~dp0.."

echo ============================================================================
echo   VINCULAR SESION DE WHATSAPP WEB PARA ENVIO AUTOMATICO DE CV
echo ============================================================================
echo.
.\venv\Scripts\python.exe main.py --login-whatsapp
pause
