@echo off
SETLOCAL EnableDelayedExpansion
TITLE J.A.R.V.I.S - Installation Automatique (www.techenclair.fr)
COLOR 0A
cd /d "%~dp0"

echo ======================================================
echo           INSTALLATION DE J.A.R.V.I.S
echo           Site : www.techenclair.fr
echo ======================================================
echo.

:: 1. Vérification des droits Administrateur
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [^!] ATTENTION : Ce script n'est pas lance en tant qu'Administrateur.
    echo [^!] Pour une installation sans erreurs, il est VIVEMENT recommande de :
    echo     - Faire un clic droit sur 'install.bat'
    echo     - Choisir 'Executer en tant qu'administrateur'
    echo.
    pause
    exit /b
)

:: 1b. Analyse du système (Détection dynamique)
echo [SYSTEME] Analyse de votre configuration...
echo.

set "PY_STATUS=[A INSTALLER]"
set "NODE_STATUS=[A INSTALLER]"
set "VENV_STATUS=[A CREER]"
set "WEB_STATUS=[A INSTALLER]"
set "ROOT_STATUS=NON"
set "CHROME_STATUS=NON"

:: Vérification Racine (présence de main2.py dans le même dossier que le script)
if exist "%~dp0main2.py" (
    set "ROOT_STATUS=OUI"
) else (
    set "ROOT_STATUS=NON"
)

:: Vérification Chrome (Registre et Chemins)
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1 && set "CHROME_STATUS=OUI"
reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1 && set "CHROME_STATUS=OUI"
if "!CHROME_STATUS!"=="NON" (
    if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME_STATUS=OUI"
    if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME_STATUS=OUI"
    if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_STATUS=OUI"
)


:: Détection versions
python --version >nul 2>&1 && set "PY_STATUS=[DEJA PRESENT]"
where npm >nul 2>&1 && set "NODE_STATUS=[DEJA PRESENT]"
if exist "venv" set "VENV_STATUS=[DEJA PRESENT]"
if exist "frontend\node_modules" set "WEB_STATUS=[DEJA PRESENT]"

:: 1c. Récapitulatif et Validation
echo ======================================================
echo           RECAPITULATIF DE L'INSTALLATION
echo ======================================================
echo [CHECK] Fichier a la RACINE du projet : !ROOT_STATUS!
echo [CHECK] Navigateur Chrome installe    : !CHROME_STATUS!
echo.
echo Statut des composants :
echo  - Environnement Python 3.12    : !PY_STATUS!
echo  - Node.js / NPM (Interface)    : !NODE_STATUS!
echo  - Dossier virtuel (venv)       : !VENV_STATUS!
echo  - Modules Web (node_modules)   : !WEB_STATUS!
echo.
if "!ROOT_STATUS!"=="NON" (
    COLOR 0C
    echo.
    echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    echo X               ERREUR D'EMPLACEMENT                 X
    echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    echo.
    echo [^!] LE FICHIER INSTALL.BAT N'EST PAS AU BON ENDROIT.
    echo.
    echo POUR CORRIGER :
    echo 1. Allez dans votre dossier JARVIS (la ou se trouve main2.py^).
    echo 2. Copiez ce fichier 'install.bat' a l'interieur.
    echo 3. Relancez-le depuis ce dossier.
    echo.
    echo L'installation ne peut pas continuer ici.
    pause
    exit /b
)

if "!CHROME_STATUS!"=="NON" (
    echo [^!] ATTENTION : Chrome est introuvable. JARVIS en a besoin.
    echo [^!] Veuillez l'installer avant de continuer.
    echo.
)
echo [INFO] Seuls les elements [A INSTALLER] seront traites.
echo [INFO] Taille approximative max : ~1.5 Go
echo.
echo ------------------------------------------------------
echo  Soutenir TechEnClair : https://www.paypal.com/paypalme/TechEnClair
echo ------------------------------------------------------
echo ======================================================


echo.
echo.
echo Appuyez sur [ENTREE] pour lancer les etapes manquantes...
pause >nul

echo.
echo [SYSTEME] Debut des operations...
echo.

:: 2. Détection / Installation de Python
set "PYTHON_CMD="
python --version >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    py --version >nul 2>&1 && set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
    echo [SYSTEME] Python est introuvable. Telechargement de Python 3.12...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe' -OutFile 'python_installer.exe'"
    echo [SYSTEME] Installateur telecharge. Lancement...
    echo [IMPORTANT] COCHEZ BIEN LA CASE 'ADD PYTHON TO PATH' AU DEBUT ^!
    start /wait python_installer.exe
    del python_installer.exe
    echo [SYSTEME] Python doit être installe maintenant. Veuillez RELANCER ce fichier install.bat.
    pause && exit /b
)

echo [SYSTEME] Python detecte : 
%PYTHON_CMD% --version

:: Validation de la version Python (3.10 minimum requis, 3.13 experimental)
for /f "tokens=2 delims= " %%V in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%V"
for /f "tokens=1,2 delims=." %%A in ("%PY_VER%") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)
if !PY_MAJOR! LSS 3 (
    echo.
    echo [^!] ATTENTION : Python !PY_VER! n'est pas supporte ^(minimum requis : 3.10^).
    echo [^!] Veuillez installer Python 3.12 depuis https://www.python.org/downloads/
    echo.
) else if !PY_MINOR! LSS 10 (
    echo.
    echo [^!] ATTENTION : Python !PY_VER! n'est pas supporte ^(minimum requis : 3.10^).
    echo [^!] Veuillez installer Python 3.12 depuis https://www.python.org/downloads/
    echo.
) else if !PY_MINOR! GEQ 13 (
    echo [INFO] Python !PY_VER! detecte ^(version experimentale^).
    echo [INFO] PyAudio peut ne pas etre disponible sur cette version.
    echo [INFO] JARVIS utilisera audioop-lts comme remplacement automatique.
    set "PY_IS_313_PLUS=1"
) else (
    echo [OK] Version Python !PY_VER! compatible.
)

:: 3. Détection / Installation de Node.js
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [SYSTEME] Node.js est manquant. Telechargement...
    powershell -Command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v20.12.2/node-v20.12.2-x64.msi' -OutFile 'node_installer.msi'"
    echo [SYSTEME] Installation de Node.js en cours...
    start /wait node_installer.msi
    del node_installer.msi
    echo [SYSTEME] Node.js installe (un redemarrage de l'ordinateur peut être requis si npm n'est toujours pas detecte^).
)

:: 4. Création de l'environnement virtuel
if not exist "venv" (
    echo [SYSTEME] Preparation de l'environnement virtuel (venv^)...
    "%PYTHON_CMD%" -m venv venv
    if %errorlevel% neq 0 (
        echo [^!] Erreur lors de la creation du venv. Verifiez vos droits.
        pause && exit /b
    )
)

set "V_PY=.\venv\Scripts\python.exe"

:: 5. Mise à jour des outils de base (EVITE LES ERREURS DE COMPILATION)
echo [SYSTEME] Mise a jour des outils d'installation (pip, setuptools, wheel)...
"%V_PY%" -m pip install --upgrade pip setuptools wheel --quiet
"%V_PY%" -m pip install --upgrade pipwin --quiet 2>nul

:: 6. Installation des modules
echo [SYSTEME] Installation des composants IA, Audio et Reseau...

:: Installation par étapes pour isoler les erreurs
echo [1/3] Installation des modules IA (Gemini, Groq, OpenAI, Google Auth)...
"%V_PY%" -m pip install python-dotenv google-genai google-generativeai groq openai flask flask-cors requests websockets colorama tenacity google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client psutil
if %errorlevel% neq 0 (
    echo [^!] Erreur lors de l'installation des modules IA. Verifiez votre connexion internet.
)

echo [2/3] Installation des modules Audio, Vision et Interface Native...
:: SpeechRecognition installe en premier, seul, pour ne pas etre bloque par pyaudio
"%V_PY%" -m pip install SpeechRecognition edge-tts pyttsx3 pyautogui Pillow screeninfo opencv-python

:: --- PYWEBVIEW : fenetre native (remplace Chrome) ---
echo [SYSTEME] Installation de PyWebView (fenetre application native)...
"%V_PY%" -m pip install pywebview
if !errorlevel! neq 0 (
    echo [INFO] PyWebView non installe. JARVIS s'ouvrira dans le navigateur Chrome.
)

:: --- Edge WebView2 Runtime (moteur requis par PyWebView sur Windows) ---
echo [SYSTEME] Verification de Edge WebView2 Runtime...
set "WEBVIEW2_OK=0"

reg query "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if !errorlevel! equ 0 set "WEBVIEW2_OK=1"

if "!WEBVIEW2_OK!"=="0" (
    reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
    if !errorlevel! equ 0 set "WEBVIEW2_OK=1"
)

if "!WEBVIEW2_OK!"=="0" (
    if exist "%ProgramFiles(x86)%\Microsoft\EdgeWebView\Application" set "WEBVIEW2_OK=1"
)
if "!WEBVIEW2_OK!"=="0" (
    if exist "%ProgramFiles%\Microsoft\EdgeWebView\Application" set "WEBVIEW2_OK=1"
)

if "!WEBVIEW2_OK!"=="1" (
    echo [OK] Edge WebView2 Runtime deja installe.
) else (
    echo [SYSTEME] Edge WebView2 absent - telechargement en cours...
    powershell -Command "try { Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile 'MicrosoftEdgeWebview2Setup.exe' -UseBasicParsing } catch { exit 1 }"
    if exist "MicrosoftEdgeWebview2Setup.exe" (
        echo [SYSTEME] Installation de Edge WebView2 Runtime...
        start /wait MicrosoftEdgeWebview2Setup.exe /silent /install
        del MicrosoftEdgeWebview2Setup.exe 2>nul
        echo [OK] Edge WebView2 Runtime installe.
    ) else (
        echo [INFO] Impossible de telecharger Edge WebView2.
        echo [INFO] JARVIS s'ouvrira dans Chrome si WebView2 est absent.
    )
)

:: --- PYGAME : installation avec wheel pre-compile (PAS de compilation C++) ---
echo [SYSTEME] Installation de Pygame (wheel pre-compile)...
"%V_PY%" -m pip install pygame --only-binary :all:
if !errorlevel! neq 0 (
    echo [AVERTISSEMENT] Pygame wheel introuvable pour cette version de Python.
    echo [SYSTEME] Tentative avec une version compatible...
    "%V_PY%" -m pip install pygame>=2.5.0 --only-binary :all:
    if !errorlevel! neq 0 (
        echo [INFO] Pygame n'a pas pu etre installe. JARVIS fonctionnera sans son audio.
    )
)

:: --- PYAUDIO : installation avec wheel pre-compile, fallback pipwin, puis audioop-lts ---
echo [SYSTEME] Installation de PyAudio (wheel pre-compile)...
"%V_PY%" -m pip install pyaudio --only-binary :all: --quiet
if !errorlevel! neq 0 (
    echo [SYSTEME] Wheel PyAudio introuvable, tentative via pipwin...
    "%V_PY%" -m pipwin install pyaudio 2>nul
    if !errorlevel! neq 0 (
        echo [INFO] PyAudio n'a pas pu etre installe nativement.
        if defined PY_IS_313_PLUS (
            echo [SYSTEME] Python 3.13+ detecte : installation de audioop-lts comme remplacement...
            "%V_PY%" -m pip install audioop-lts>=0.2.1 --quiet
            if !errorlevel! equ 0 (
                echo [OK] audioop-lts installe. SpeechRecognition restera fonctionnel.
            ) else (
                echo [INFO] audioop-lts non installe. La reconnaissance vocale sera limitee.
            )
        ) else (
            echo [INFO] Pour l'installer plus tard : pip install pipwin ^&^& pipwin install pyaudio
        )
    )
)

:: --- Controle volume + luminosite (fonctions locales JARVIS) ---
echo [SYSTEME] Installation des modules volume et luminosite...
"%V_PY%" -m pip install pycaw screen-brightness-control 2>nul

echo [3/3] Finalisation avec le fichier requirements.txt...
if exist "requirements.txt" (
    "%V_PY%" -m pip install -r requirements.txt
)

:: 7. Interface Web
where npm >nul 2>&1
if %errorlevel% equ 0 (
    if exist "frontend\package.json" (
        echo [SYSTEME] Installation de l'interface Web...
        pushd frontend && call npm install & popd
    )
)

:: 8. Creation du demarreur
echo [SYSTEME] Generation du fichier de lancement 'DEMARRER_JARVIS.bat'...
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo TITLE J.A.R.V.I.S - www.techenclair.fr
echo COLOR 0B
echo cd /d "%%~dp0"
echo.
echo if not exist ".\venv\Scripts\python.exe" goto repair
echo ".\venv\Scripts\python.exe" -c "import sys; sys.exit(0)" ^>nul 2^>^&1
echo if %%errorlevel%% neq 0 goto repair
echo.
echo ".\venv\Scripts\python.exe" "main2.py"
echo pause
echo exit /b
echo.
echo :repair
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
echo pause
echo powershell -Command "Start-Process -FilePath '%%~dp0install.bat' -WorkingDirectory '%%~dp0' -Verb RunAs"
echo exit /b
) > "DEMARRER_JARVIS.bat"


:: 9. Création du modèle .env si absent
if not exist ".env" (
    echo [SYSTEME] Creation du fichier de configuration .env...
    (
    echo GEMINI_API_KEY=VOTRE_CLE_ICI
    echo YOUTUBE_API_KEY=VOTRE_CLE_ICI
    echo XAI_API_KEY=VOTRE_CLE_ICI
    echo HA_URL=http://192.168.1.XX:8123
    echo HA_TOKEN=VOTRE_TOKEN_ICI
    echo SERPAPI_API_KEY=VOTRE_CLE_ICI
    echo GROQ_API_KEY=VOTRE_CLE_ICI
    echo MISTRAL_API_KEY=VOTRE_CLE_ICI
    ) > ".env"
)

:: 10. Personnalisation du Prénom
echo.
echo ------------------------------------------------------
echo  PERSONNALISATION DE VOTRE IA
echo ------------------------------------------------------
echo Par defaut, JARVIS est configure pour s'adresser a 'Monsieur'.
echo Si vous voulez qu'il utilise VOTRE prenom, ecrivez-le ici :
echo (Ou appuyez simplement sur [ENTREE] pour garder 'Monsieur'^)
echo.
set "PN="
set /p "PN=[?] Votre prenom : "

:: ── Validation de l'input avec !PN! (EnableDelayedExpansion requis) ──────────

:: 1. Vide ou non renseigne -> on garde Monsieur
if "!PN!"=="" goto skip_name

:: 2. Deja Monsieur -> rien a faire
if /i "!PN!"=="Monsieur" goto skip_name

:: 3. Longueur max 30 caracteres (securite)
set "PN_TEST=!PN:~30!"
if not "!PN_TEST!"=="" (
    echo [^!] Prenom trop long ^(max 30 caracteres^). Conserve 'Monsieur'.
    goto skip_name
)

:: 4. Refus des caracteres dangereux pour le batch et Python
::    On teste chaque caractere interdit en cherchant s'il est present dans !PN!
set "PN_INVALIDE=0"
for %%C in ("!" "%" "^" "&" "|" "<" ">" "(" ")" ";" "," "@" "#" "$" "`" "~" "\" "/" "*" "?" "{" "}" "[" "]") do (
    set "PN_CHK=!PN:%%~C=!"
    if not "!PN_CHK!"=="!PN!" set "PN_INVALIDE=1"
)
:: Tester le guillemet separement (ne peut pas etre dans la liste FOR)
set "PN_CHK2=!PN:"=!"
if not "!PN_CHK2!"=="!PN!" set "PN_INVALIDE=1"

if "!PN_INVALIDE!"=="1" (
    echo [^!] Prenom invalide ^(caractere interdit detecte^). Conserve 'Monsieur'.
    goto skip_name
)

:: 5. Appliquer la personnalisation
echo.
echo [SYSTEME] Transformation de JARVIS en cours...
echo Remplacement de 'Monsieur' par '!PN!' dans le code source...

".\venv\Scripts\python.exe" "_setup\rename_user.py" "!PN!"

echo [OK] Personnalisation terminee pour '!PN!'.

:skip_name
echo.




echo.
echo ======================================================
echo           INSTALLATION TERMINEE ^!
echo ======================================================
echo.
echo ETAPES SUIVANTES :
echo 1. Ouvre le fichier '.env' et ajoute tes cles API (Gemini, etc.).
echo 2. Si tu as eu des erreurs rouges, installe les "Build Tools C++".
echo 3. Lance 'DEMARRER_JARVIS.bat' pour demarrer ton IA.
echo.
echo ------------------------------------------------------
echo  Soutenir le projet JARVIS :
echo  Si tu aimes mon travail, tu peux m'offrir un cafe ici :
echo  https://www.paypal.com/paypalme/TechEnClair
echo ------------------------------------------------------
echo.
echo Aide et support : www.techenclair.fr
echo ======================================================
pause

