@echo off
chcp 65001 > nul
title Compilador de Ejecutable e Instalador - Job Finder Desktop (Windows 10/11)
cd /d "%~dp0"

echo ============================================================================
echo   GENERANDO EJECUTABLE (.EXE) PARA WINDOWS 10 Y WINDOWS 11
echo ============================================================================
echo.

if not exist "venv\Scripts\pyinstaller.exe" (
    echo Instalando PyInstaller en el entorno virtual...
    venv\Scripts\pip.exe install pyinstaller
)

echo [1/3] Compilando JobFinderPC.exe con CustomTkinter y Playwright...
venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed ^
    --name "JobFinderPC" ^
    --collect-all customtkinter ^
    --collect-all darkdetect ^
    --collect-all playwright ^
    --hidden-import config ^
    --hidden-import database ^
    --hidden-import parser ^
    --hidden-import scraper ^
    --hidden-import mailer ^
    --hidden-import whatsapp ^
    --hidden-import main ^
    interfaz_pc.py

echo.
echo [2/3] Copiando plantilla limpia (.env.example) y creando instalador de acceso directo...
if exist ".env.example" (
    copy /Y ".env.example" "dist\JobFinderPC\.env.example" > nul
)

(
echo @echo off
echo chcp 65001 ^> nul
echo title Instalador de Job Finder Desktop ^(Windows 10 y 11^)
echo cd /d "%%~dp0"
echo echo ============================================================================
echo echo   INSTALANDO JOB FINDER DESKTOP EN TU PC ^(WINDOWS 10 / 11^)
echo echo ============================================================================
echo echo.
echo if not exist ".env" ^(
echo     if exist ".env.example" copy /Y ".env.example" ".env" ^> nul
echo ^)
echo set "APP_DIR=%%~dp0"
echo set "EXE_PATH=%%APP_DIR%%JobFinderPC.exe"
echo powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Job Finder PC.lnk'); $s.TargetPath='%%EXE_PATH%%'; $s.WorkingDirectory='%%APP_DIR%%'; $s.Description='Buscador y Auto-Postulador Inteligente de Empleo'; $s.Save()"
echo echo.
echo echo [OK] Se ha creado el acceso directo 'Job Finder PC' en tu Escritorio.
echo echo [OK] Abriendo Job Finder Desktop...
echo start "" "%%EXE_PATH%%"
echo pause
) > "dist\JobFinderPC\Instalar_Acceso_Directo.bat"

echo.
echo [3/3] Empaquetando archivo distribuible ZIP (sin tus datos privados)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path 'dist\JobFinderPC_Windows10_11.zip') { Remove-Item 'dist\JobFinderPC_Windows10_11.zip' -Force }; Compress-Archive -Path 'dist\JobFinderPC\*' -DestinationPath 'dist\JobFinderPC_Windows10_11.zip' -Force"

echo.
echo ============================================================================
echo   COMPILACION EXITOSA PARA WINDOWS 10 Y WINDOWS 11
echo ============================================================================
echo   1. Ejecutable directo: dist\JobFinderPC\JobFinderPC.exe
echo   2. Instalador de Escritorio: dist\JobFinderPC\Instalar_Acceso_Directo.bat
echo   3. Paquete ZIP para compartir: dist\JobFinderPC_Windows10_11.zip
echo ============================================================================
pause
