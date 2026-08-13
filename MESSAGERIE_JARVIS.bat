@echo off
rem =====================================================================
rem  J.A.R.V.I.S Mail — lanceur "application" (fenetre dediee, sans onglets)
rem  Ouvre la messagerie unifiee comme une vraie app de bureau.
rem  Lance mail_server.py tout seul si besoin : pas besoin de JARVIS complet.
rem  Cree un raccourci de ce fichier sur le Bureau pour un acces direct.
rem =====================================================================
set "URL=http://localhost:8090"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"

rem -- Demarre le serveur mail seul si rien n'ecoute deja sur le port 8090 --
powershell -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue)) { Start-Process -FilePath '%~dp0venv\Scripts\python.exe' -ArgumentList '%~dp0mail_server.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden }"
timeout /t 2 /nobreak >nul

if exist "%EDGE%" (
    start "" "%EDGE%" --app=%URL%
) else if exist "%CHROME%" (
    start "" "%CHROME%" --app=%URL%
) else (
    start "" "%URL%"
)
