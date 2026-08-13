import os
import subprocess
try:
    import psutil
except ImportError:
    psutil = None
import time
import asyncio
import shutil
from config import nom_utilisateur

# MODE BOULOT
# ==========================================

def _boulot_trouver_exe(noms_exe: list, chemins_hints: list = None) -> str:
    """Trouve un exécutable sur n'importe quel Windows.
    Ordre : registre App Paths → PATH système → chemins connus."""
    # 1. Registre Windows (le plus fiable — tous les apps installées y sont)
    try:
        import winreg
        for exe in noms_exe:
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    key = winreg.OpenKey(
                        hive,
                        f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}"
                    )
                    path, _ = winreg.QueryValueEx(key, "")
                    winreg.CloseKey(key)
                    p = os.path.expandvars(path.strip('"'))
                    if os.path.exists(p):
                        return p
                except Exception:
                    pass
    except ImportError:
        pass

    # 2. PATH système
    for exe in noms_exe:
        found = shutil.which(exe)
        if found:
            return found

    # 3. Chemins connus communs
    if chemins_hints:
        for hint in chemins_hints:
            p = os.path.expandvars(hint)
            if os.path.exists(p):
                return p

    return ""


def _boulot_lancer(label: str, noms_exe: list,
                   chemins_hints: list = None, env_key: str = None) -> bool:
    """Lance une application — détection universelle, sans popup d'erreur Windows."""
    # Override via .env (priorité absolue)
    if env_key:
        env_val = os.path.expandvars(os.getenv(env_key, ""))
        if env_val and os.path.exists(env_val):
            try:
                subprocess.Popen([env_val])
                return True
            except Exception:
                pass

    # Détection automatique (registre → PATH → hints)
    exe_path = _boulot_trouver_exe(noms_exe, chemins_hints)
    if exe_path:
        try:
            subprocess.Popen([exe_path])
            return True
        except Exception:
            pass

    # Pas trouvé — on log silencieusement, aucune popup Windows
    print(f"[BOULOT] {label} introuvable sur ce PC (registre, PATH et hints épuisés)")
    return False


def _fermer_app(noms_process: list) -> bool:
    """Termine tous les processus correspondant aux noms donnés (insensible à la casse)."""
    if psutil is None:
        return False
    tues = 0
    noms_lower = [n.lower() for n in noms_process]
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() in noms_lower:
                proc.terminate()
                tues += 1
        except Exception:
            pass
    return tues > 0


# Catalogue d'applications ouvrables / fermables par commande vocale
_APPS_CATALOGUE = {
    # ── Navigateurs ──────────────────────────────────────────
    "chrome": {
        "label": "Google Chrome", "noms": ["chrome.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        ],
    },
    "firefox": {
        "label": "Firefox", "noms": ["firefox.exe"],
        "hints": [r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe", r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe"],
    },
    "edge": {
        "label": "Microsoft Edge", "noms": ["msedge.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
        ],
    },
    "opera": {
        "label": "Opera", "noms": ["opera.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
            r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe",
            r"%APPDATA%\Opera Software\Opera Stable\opera.exe",
            r"%APPDATA%\Opera Software\Opera GX Stable\opera.exe",
        ],
    },
    "brave": {
        "label": "Brave", "noms": ["brave.exe"],
        "hints": [
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
    },
    # ── Jeux / Launchers ─────────────────────────────────────
    "steam": {
        "label": "Steam", "noms": ["steam.exe"],
        "hints": [r"%PROGRAMFILES(X86)%\Steam\steam.exe", r"%PROGRAMFILES%\Steam\steam.exe"],
    },
    "epic": {
        "label": "Epic Games", "noms": ["EpicGamesLauncher.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
            r"%PROGRAMFILES%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
        ],
    },
    "origin": {
        "label": "Origin", "noms": ["Origin.exe"],
        "hints": [r"%PROGRAMFILES(X86)%\Origin\Origin.exe", r"%PROGRAMFILES%\Origin\Origin.exe"],
    },
    "ea": {
        "label": "EA App", "noms": ["EADesktop.exe", "EA.exe"],
        "hints": [
            r"%PROGRAMFILES%\Electronic Arts\EA Desktop\EA Desktop.exe",
            r"%PROGRAMFILES(X86)%\Electronic Arts\EA Desktop\EA Desktop.exe",
        ],
    },
    "ubisoft": {
        "label": "Ubisoft Connect", "noms": ["UbisoftConnect.exe", "upc.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe",
            r"%PROGRAMFILES%\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe",
        ],
    },
    "gog": {
        "label": "GOG Galaxy", "noms": ["GalaxyClient.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\GOG Galaxy\GalaxyClient.exe",
            r"%PROGRAMFILES%\GOG Galaxy\GalaxyClient.exe",
        ],
    },
    "minecraft": {
        "label": "Minecraft", "noms": ["Minecraft.exe", "MinecraftLauncher.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Minecraft Launcher\MinecraftLauncher.exe",
            r"%LOCALAPPDATA%\Packages\Microsoft.4297127D64EC6_8wekyb3d8bbwe\Minecraft.exe",
        ],
    },
    # ── Communication ────────────────────────────────────────
    "discord": {
        "label": "Discord", "noms": ["Discord.exe", "Update.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Discord\Update.exe",
            r"%LOCALAPPDATA%\Discord\app-*\Discord.exe",
            r"%APPDATA%\Discord\Update.exe",
        ],
    },
    "teams": {
        "label": "Microsoft Teams", "noms": ["ms-teams.exe", "Teams.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\ms-teams.exe",
            r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe",
            r"%PROGRAMFILES%\Microsoft\Teams\current\Teams.exe",
        ],
    },
    "whatsapp": {
        "label": "WhatsApp", "noms": ["WhatsApp.exe"],
        "hints": [
            r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe",
            r"%LOCALAPPDATA%\Programs\WhatsApp\WhatsApp.exe",
        ],
    },
    "telegram": {
        "label": "Telegram", "noms": ["Telegram.exe"],
        "hints": [
            r"%APPDATA%\Telegram Desktop\Telegram.exe",
            r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe",
        ],
    },
    "zoom": {
        "label": "Zoom", "noms": ["Zoom.exe"],
        "hints": [
            r"%APPDATA%\Zoom\bin\Zoom.exe",
            r"%PROGRAMFILES%\Zoom\bin\Zoom.exe",
            r"%PROGRAMFILES(X86)%\Zoom\bin\Zoom.exe",
        ],
    },
    "skype": {
        "label": "Skype", "noms": ["Skype.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Skype.exe",
            r"%PROGRAMFILES(X86)%\Microsoft\Skype for Desktop\Skype.exe",
        ],
    },
    # ── Bureautique / Office ─────────────────────────────────
    "word": {
        "label": "Microsoft Word", "noms": ["WINWORD.EXE", "winword.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\WINWORD.EXE",
        ],
    },
    "excel": {
        "label": "Microsoft Excel", "noms": ["EXCEL.EXE", "excel.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\EXCEL.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\EXCEL.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\EXCEL.EXE",
        ],
    },
    "powerpoint": {
        "label": "Microsoft PowerPoint", "noms": ["POWERPNT.EXE", "powerpnt.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\POWERPNT.EXE",
        ],
    },
    "outlook": {
        "label": "Outlook", "noms": ["OUTLOOK.EXE", "outlook.exe", "olk.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\olk.exe",
        ],
    },
    "onenote": {
        "label": "OneNote", "noms": ["ONENOTE.EXE", "onenote.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\ONENOTE.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\ONENOTE.EXE",
        ],
    },
    # ── Créatif / Design ─────────────────────────────────────
    "photoshop": {
        "label": "Photoshop", "noms": ["Photoshop.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2024\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2025\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop CC 2023\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        ],
    },
    "premiere": {
        "label": "Premiere Pro", "noms": ["Adobe Premiere Pro.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro CC 2023\Adobe Premiere Pro.exe",
        ],
    },
    "after effects": {
        "label": "After Effects", "noms": ["AfterFX.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2023\Support Files\AfterFX.exe",
        ],
    },
    "illustrator": {
        "label": "Illustrator", "noms": ["Illustrator.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows\Illustrator.exe",
        ],
    },
    "capcut": {
        "label": "CapCut", "noms": ["CapCut.exe"],
        "hints": [
            r"%LOCALAPPDATA%\CapCut\Apps\CapCut.exe",
            r"%PROGRAMFILES%\CapCut\CapCut.exe",
        ],
    },
    "obs": {
        "label": "OBS Studio", "noms": ["obs64.exe", "obs32.exe"],
        "hints": [
            r"%PROGRAMFILES%\obs-studio\bin\64bit\obs64.exe",
            r"%PROGRAMFILES(X86)%\obs-studio\bin\64bit\obs64.exe",
        ],
    },
    "blender": {
        "label": "Blender", "noms": ["blender.exe"],
        "hints": [
            r"%PROGRAMFILES%\Blender Foundation\Blender 4.0\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender 3.6\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender\blender.exe",
        ],
    },
    "gimp": {
        "label": "GIMP", "noms": ["gimp-2.10.exe", "gimp.exe"],
        "hints": [
            r"%PROGRAMFILES%\GIMP 2\bin\gimp-2.10.exe",
            r"%PROGRAMFILES(X86)%\GIMP 2\bin\gimp-2.10.exe",
        ],
    },
    # ── Développement ────────────────────────────────────────
    "vscode": {
        "label": "Visual Studio Code", "noms": ["Code.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"%PROGRAMFILES%\Microsoft VS Code\Code.exe",
        ],
    },
    "claude": {
        "label": "Claude", "noms": ["claude.exe", "Claude.exe"],
        "hints": [
            r"%LOCALAPPDATA%\AnthropicClaude\claude.exe",
            r"%PROGRAMFILES%\AnthropicClaude\claude.exe",
            r"%APPDATA%\AnthropicClaude\claude.exe",
        ],
    },
    "terminal": {
        "label": "Terminal", "noms": ["wt.exe", "WindowsTerminal.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe",
        ],
    },
    # ── Multimédia ───────────────────────────────────────────
    "vlc": {
        "label": "VLC", "noms": ["vlc.exe"],
        "hints": [
            r"%PROGRAMFILES%\VideoLAN\VLC\vlc.exe",
            r"%PROGRAMFILES(X86)%\VideoLAN\VLC\vlc.exe",
        ],
    },
    "spotify": {
        "label": "Spotify", "noms": ["Spotify.exe"],
        "hints": [
            r"%APPDATA%\Spotify\Spotify.exe",
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
        ],
    },
    # ── Utilitaires ──────────────────────────────────────────
    "filezilla": {
        "label": "FileZilla", "noms": ["filezilla.exe"],
        "hints": [
            r"%PROGRAMFILES%\FileZilla FTP Client\filezilla.exe",
            r"%PROGRAMFILES(X86)%\FileZilla FTP Client\filezilla.exe",
        ],
    },
    "winrar": {
        "label": "WinRAR", "noms": ["WinRAR.exe"],
        "hints": [
            r"%PROGRAMFILES%\WinRAR\WinRAR.exe",
            r"%PROGRAMFILES(X86)%\WinRAR\WinRAR.exe",
        ],
    },
    "7zip": {
        "label": "7-Zip", "noms": ["7zFM.exe"],
        "hints": [
            r"%PROGRAMFILES%\7-Zip\7zFM.exe",
            r"%PROGRAMFILES(X86)%\7-Zip\7zFM.exe",
        ],
    },
    "antigravity": {
        "label": "Antigravity", "noms": ["Antigravity.exe", "antigravity.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES(X86)%\Antigravity\Antigravity.exe",
            r"%APPDATA%\Antigravity\Antigravity.exe",
            r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe",
        ],
    },
}
# Alias — plusieurs façons de nommer la même app
_APPS_CATALOGUE["ea app"]          = _APPS_CATALOGUE["ea"]
_APPS_CATALOGUE["microsoft edge"]  = _APPS_CATALOGUE["edge"]
_APPS_CATALOGUE["opera gx"]        = _APPS_CATALOGUE["opera"]
_APPS_CATALOGUE["google chrome"]   = _APPS_CATALOGUE["chrome"]
_APPS_CATALOGUE["epic games"]      = _APPS_CATALOGUE["epic"]
_APPS_CATALOGUE["epic game"]       = _APPS_CATALOGUE["epic"]
_APPS_CATALOGUE["ubisoft connect"] = _APPS_CATALOGUE["ubisoft"]
_APPS_CATALOGUE["uplay"]          = _APPS_CATALOGUE["ubisoft"]
_APPS_CATALOGUE["gog galaxy"]     = _APPS_CATALOGUE["gog"]
_APPS_CATALOGUE["visual studio code"] = _APPS_CATALOGUE["vscode"]
_APPS_CATALOGUE["vs code"]        = _APPS_CATALOGUE["vscode"]
_APPS_CATALOGUE["code"]           = _APPS_CATALOGUE["vscode"]
_APPS_CATALOGUE["premiere pro"]   = _APPS_CATALOGUE["premiere"]
_APPS_CATALOGUE["adobe premiere"] = _APPS_CATALOGUE["premiere"]
_APPS_CATALOGUE["adobe photoshop"]= _APPS_CATALOGUE["photoshop"]
_APPS_CATALOGUE["adobe after effects"] = _APPS_CATALOGUE["after effects"]
_APPS_CATALOGUE["adobe illustrator"] = _APPS_CATALOGUE["illustrator"]
_APPS_CATALOGUE["microsoft word"] = _APPS_CATALOGUE["word"]
_APPS_CATALOGUE["microsoft excel"]= _APPS_CATALOGUE["excel"]
_APPS_CATALOGUE["microsoft powerpoint"] = _APPS_CATALOGUE["powerpoint"]
_APPS_CATALOGUE["powerpoint"]     = _APPS_CATALOGUE["powerpoint"]
_APPS_CATALOGUE["ppt"]            = _APPS_CATALOGUE["powerpoint"]
_APPS_CATALOGUE["microsoft outlook"] = _APPS_CATALOGUE["outlook"]
_APPS_CATALOGUE["microsoft teams"]= _APPS_CATALOGUE["teams"]
_APPS_CATALOGUE["obs studio"]     = _APPS_CATALOGUE["obs"]
_APPS_CATALOGUE["sept zip"]       = _APPS_CATALOGUE["7zip"]
_APPS_CATALOGUE["7 zip"]          = _APPS_CATALOGUE["7zip"]

def _charger_custom_apps():
    """Charge les applications dynamiques depuis jarvis_config.json et les ajoute a _APPS_CATALOGUE."""
    import json
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if not os.path.exists(config_path):
            return
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            custom_apps = config.get("custom_apps", [])
            
            keys_to_remove = [k for k, v in _APPS_CATALOGUE.items() if v.get("is_custom")]
            for k in keys_to_remove:
                del _APPS_CATALOGUE[k]
                
            for app in custom_apps:
                app_id = app.get("id")
                app_label = app.get("label")
                app_path = app.get("exe_path")
                if app_id and app_path:
                    exe_name = os.path.basename(app_path.replace("\\", "/"))
                    new_app = {
                        "label": app_label,
                        "noms": [exe_name],
                        "hints": [app_path],
                        "is_custom": True
                    }
                    _APPS_CATALOGUE[app_id] = new_app
                    if app_label:
                        _APPS_CATALOGUE[app_label.lower()] = new_app
    except Exception as e:
        print(f"[BOULOT] Erreur chargement custom apps : {e}")

_charger_custom_apps()


async def mode_boulot():
    """Lance Spotify, ouvre Documents, Téléchargements, Chrome et Antigravity
    en disposition quadrants sur l'écran."""
    try:
        import win32gui, win32con, win32api
    except ImportError:
        return "pywin32 manquant — installez-le pour la disposition des fenêtres."

    await parler("Bien, je prépare votre espace de travail.")

    # ── 1. Spotify en fond (PRIORITE — lancé en premier) ────
    spotify_lancer_playlist(SPOTIFY_MUSIQUE_URI)
    time.sleep(0.5)

    # ── 2. Ouverture des dossiers ────────────────────────────
    # Documents (ira en haut à gauche)
    chemin_documents = resoudre_chemin("documents")
    subprocess.Popen(["explorer", chemin_documents])
    time.sleep(0.3)

    # Téléchargements (ira en haut à droite)
    chemin_telechargements = resoudre_chemin("downloads")
    subprocess.Popen(["explorer", chemin_telechargements])
    time.sleep(0.3)

    # ── 3. Chrome (ira en bas à gauche) ──────────────────────
    _boulot_lancer(
        "Chrome", ["chrome.exe"],
        chemins_hints=[
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        ],
        env_key="CHROME_PATH"
    )
    time.sleep(0.3)

    # ── 4. Antigravity (ira en bas à droite) ─────────────────
    _boulot_lancer(
        "Antigravity", ["Antigravity.exe", "antigravity.exe"],
        chemins_hints=[
            r"%LOCALAPPDATA%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES(X86)%\Antigravity\Antigravity.exe",
            r"%APPDATA%\Antigravity\Antigravity.exe",
            r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe",
        ],
        env_key="ANTIGRAVITY_PATH"
    )
    time.sleep(0.3)

    await parler("Applications lancées, j'arrange votre espace dans quelques secondes.")
    time.sleep(7)

    # ── 5. Disposition en 4 quadrants ────────────────────────
    screen_w = win32api.GetSystemMetrics(0)
    screen_h = win32api.GetSystemMetrics(1)
    work_h   = screen_h - 48
    hw = screen_w // 2
    hh = work_h  // 2

    #  ┌──────────────────┬──────────────────┐
    #  │   Documents      │  Téléchargements │
    #  │   (haut gauche)  │  (haut droite)   │
    #  ├──────────────────┼──────────────────┤
    #  │   Chrome         │  Antigravity     │
    #  │   (bas gauche)   │  (bas droite)    │
    #  └──────────────────┴──────────────────┘
    disposition = [
        {"titres": ["Documents"],                           "pos": (0,  0,  hw, hh)},
        {"titres": ["Téléchargements", "Telechargements",
                    "Downloads"],                           "pos": (hw, 0,  hw, hh)},
        {"titres": ["Chrome", "Google Chrome"],             "pos": (0,  hh, hw, hh)},
        {"titres": ["Antigravity"],                         "pos": (hw, hh, hw, hh)},
    ]

    def _trouver_hwnd(titres):
        found = [None]
        def cb(hwnd, _):
            if found[0]:
                return
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if any(mot.lower() in t.lower() for mot in titres):
                    found[0] = hwnd
        win32gui.EnumWindows(cb, None)
        return found[0]

    ok = 0
    for item in disposition:
        hwnd = _trouver_hwnd(item["titres"])
        if hwnd:
            x, y, w, h = item["pos"]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOP, x, y, w, h,
                win32con.SWP_SHOWWINDOW
            )
            time.sleep(0.2)
            ok += 1

    if ok == 4:
        return f"Votre espace de travail est prêt, {nom_utilisateur()}. Bonne journée !"
    return f"Espace prêt — {ok}/4 fenêtres positionnées. Musique lancée en fond."

