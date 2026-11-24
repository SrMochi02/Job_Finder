@echo off
chcp 65001 > nul
title Compilador de Ejecutable e Instalador - Job Finder Desktop (Windows 10/11)
cd /d "%~dp0.."

echo ============================================================================
echo   GENERANDO EJECUTABLE (.EXE) PARA WINDOWS 10 Y WINDOWS 11
echo ============================================================================
echo.

if not exist "venv\Scripts\pyinstaller.exe" (
    echo Instalando PyInstaller en el entorno virtual...
    venv\Scripts\pip.exe install pyinstaller
)

echo [1/3] Compilando JobFinderPC.exe con CustomTkinter y Playwright...
venv\Scripts\pyinstaller.exe --noconfirm --windowed ^
    --workpath "%TEMP%\jobfinder_build" ^
    --distpath "release_windows" ^
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
    copy /Y ".env.example" "release_windows\JobFinderPC\.env.example" > nul
)
if exist "README.md" (
    copy /Y "README.md" "release_windows\JobFinderPC\LEEME_INSTRUCCIONES.txt" > nul
)
if exist "MANUAL_USUARIO.md" (
    copy /Y "MANUAL_USUARIO.md" "release_windows\JobFinderPC\MANUAL_COMPLETO_DE_USUARIO.md" > nul
)

(
echo @echo off
echo chcp 65001 ^> nul
echo title Instalador de Job Finder PC ^(Windows 10 y 11^)
echo cd /d "%%~dp0"
echo echo ============================================================================
echo echo   INSTALANDO JOB FINDER PC EN TU COMPUTADORA ^(WINDOWS 10 / 11^)
echo echo ============================================================================
echo echo.
echo if not exist ".env" ^(
echo     if exist ".env.example" copy /Y ".env.example" ".env" ^> nul
echo ^)
echo set "APP_DIR=%%~dp0"
echo set "EXE_PATH=%%APP_DIR%%JobFinderPC.exe"
echo powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Job Finder PC.lnk'); $s.TargetPath='%%EXE_PATH%%'; $s.WorkingDirectory='%%APP_DIR%%'; $s.Description='Asistente Automatico para Buscar Empleo'; $s.Save()"
echo echo.
echo echo [OK] Se ha creado el acceso directo 'Job Finder PC' en tu Escritorio.
echo echo [OK] Abriendo Job Finder PC...
echo start "" "%%EXE_PATH%%"
) > "release_windows\JobFinderPC\Instalar_Acceso_Directo.bat"

echo.
echo [3/3] Limpiando archivos temporales y empaquetando archivo distribuible ZIP (100%% libre de datos personales)...
if exist "JobFinderPC.spec" del /F /Q "JobFinderPC.spec"
if exist "release_windows\JobFinderPC\.env" del /F /Q "release_windows\JobFinderPC\.env"
if exist "release_windows\JobFinderPC\*.pdf" del /F /Q "release_windows\JobFinderPC\*.pdf"
if exist "release_windows\JobFinderPC\*.db" del /F /Q "release_windows\JobFinderPC\*.db"
if exist "release_windows\JobFinderPC\*.csv" del /F /Q "release_windows\JobFinderPC\*.csv"
if exist "release_windows\JobFinderPC\*.log" del /F /Q "release_windows\JobFinderPC\*.log"
if exist "release_windows\JobFinderPC\portal_session" rmdir /S /Q "release_windows\JobFinderPC\portal_session"
if exist "release_windows\JobFinderPC\whatsapp_session" rmdir /S /Q "release_windows\JobFinderPC\whatsapp_session"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path 'release_windows\JobFinderPC_Windows10_11.zip') { Remove-Item 'release_windows\JobFinderPC_Windows10_11.zip' -Force }; Compress-Archive -Path 'release_windows\JobFinderPC\*' -DestinationPath 'release_windows\JobFinderPC_Windows10_11.zip' -Force"

echo.
echo ============================================================================
echo   COMPILACION EXITOSA PARA WINDOWS 10 Y WINDOWS 11
echo ============================================================================
echo   1. Ejecutable directo: release_windows\JobFinderPC\JobFinderPC.exe
echo   2. Instalador de Escritorio: release_windows\JobFinderPC\Instalar_Acceso_Directo.bat
echo   3. Paquete ZIP para compartir: release_windows\JobFinderPC_Windows10_11.zip
echo ============================================================================
pause
