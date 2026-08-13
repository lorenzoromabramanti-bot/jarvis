@echo off
chcp 65001 >nul 2>&1
TITLE J.A.R.V.I.S - www.techenclair.fr
COLOR 0B
cd /d "%~dp0"

if not exist ".\venv\Scripts\python.exe" goto repair
".\venv\Scripts\python.exe" -c "import sys; sys.exit(0)" >nul 2>&1
if %errorlevel% neq 0 goto repair

".\venv\Scripts\python.exe" "main2.py"
pause
exit /b

:repair
echo =====================================================================
echo [ATTENTION] L'environnement de JARVIS est absent ou endommage.
echo             Cela arrive si Python a ete desinstalle ou mis a jour
echo             ou si le dossier d'installation a ete deplace.
echo =====================================================================
echo.
echo Nous allons tenter de le reparer automatiquement en reinstallant
echo les composants requis via install.bat en mode Administrateur.
echo.
echo Veuillez autoriser la demande d'elevation de droits UAC...
echo.
pause
powershell -Command "Start-Process -FilePath '%~dp0install.bat' -WorkingDirectory '%~dp0' -Verb RunAs"
exit /b