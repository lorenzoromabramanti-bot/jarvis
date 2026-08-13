@echo off
SETLOCAL EnableDelayedExpansion
TITLE JARVIS - Vider le Cache
COLOR 0C
cd /d "%~dp0"

echo.
echo  ============================================================
echo   J.A.R.V.I.S -- NETTOYAGE DU CACHE WEBVIEW2
echo   www.techenclair.fr
echo  ============================================================
echo.
echo  [!] FERMEZ JARVIS avant de continuer !
echo.
echo  Ce script supprime le cache WebView2 de JARVIS.
echo  Cela force le rechargement complet de l'interface
echo  au prochain lancement.
echo.
echo  ============================================================
echo.
pause

echo.
echo  [1/3] Verification que JARVIS n'est pas en cours...
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if %errorLevel% equ 0 (
    echo.
    echo  [!] JARVIS tourne encore (python.exe detecte).
    echo      Fermez JARVIS completement puis relancez ce script.
    echo.
    pause
    exit /b 1
)
echo  [OK] JARVIS n'est pas en cours.

echo.
echo  [1.5/3] Libération des verrous (fermeture de msedgewebview2.exe)...
taskkill /F /IM msedgewebview2.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo  [2/3] Suppression du cache WebView2...

set "CACHE_DIR=%APPDATA%\pywebview\EBWebView\Default"

if not exist "%CACHE_DIR%" (
    echo  [INFO] Dossier cache introuvable - deja vide ou jamais utilise.
    goto reset_marker
)

set "ERREUR=0"

rd /S /Q "%CACHE_DIR%\Cache"               >nul 2>&1
rd /S /Q "%CACHE_DIR%\Code Cache"          >nul 2>&1
rd /S /Q "%CACHE_DIR%\Service Worker"      >nul 2>&1
rd /S /Q "%CACHE_DIR%\GPUCache"            >nul 2>&1
rd /S /Q "%CACHE_DIR%\DawnGraphiteCache"   >nul 2>&1
rd /S /Q "%CACHE_DIR%\DawnWebGPUCache"     >nul 2>&1
rd /S /Q "%CACHE_DIR%\blob_storage"        >nul 2>&1
rd /S /Q "%CACHE_DIR%\Session Storage"     >nul 2>&1
rd /S /Q "%CACHE_DIR%\Local Storage"       >nul 2>&1
rd /S /Q "%CACHE_DIR%\IndexedDB"           >nul 2>&1

echo  [OK] Cache supprime.

:reset_marker
echo.
echo  [3/3] Reset du marqueur de version...

if exist "%~dp0.jarvis_cache_version" (
    del /F /Q "%~dp0.jarvis_cache_version" >nul 2>&1
    echo  [OK] Marqueur reinitialise.
) else (
    echo  [INFO] Marqueur absent - rien a faire.
)

echo.
echo  ============================================================
echo   NETTOYAGE TERMINE !
echo.
echo   JARVIS rechargera l'interface proprement
echo   au prochain lancement.
echo  ============================================================
echo.
pause
