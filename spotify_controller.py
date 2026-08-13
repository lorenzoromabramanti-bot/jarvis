try:
    import pyautogui
except ImportError:
    pyautogui = None
import time
import pyperclip
import asyncio
try:
    import psutil
except ImportError:
    psutil = None
try:
    import requests
except ImportError:
    requests = None
import json
import os
import re
import subprocess
from config import nom_utilisateur

# SPOTIFY
# ==========================================

def _focus_spotify():
    """Met la fenêtre Spotify au premier plan. Retourne True si trouvé."""
    import win32gui, win32con
    candidats = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            titre = win32gui.GetWindowText(hwnd)
            if "Spotify" in titre:
                candidats.append(hwnd)
    win32gui.EnumWindows(_cb, None)
    if not candidats:
        return False
    hwnd = candidats[0]
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception:
        return False

async def spotify_ouvrir():
    """Lance Spotify s'il n'est pas déjà ouvert."""
    try:
        # Déjà ouvert ?
        if _focus_spotify():
            return f"Spotify est déjà ouvert, {nom_utilisateur()}, je l'ai mis au premier plan."
        chemin = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
        if os.path.exists(chemin):
            subprocess.Popen([chemin])
        else:
            # Version Microsoft Store
            subprocess.Popen(["explorer", "spotify:"], shell=False)
        time.sleep(4)
        _focus_spotify()
        return f"Spotify lancé, {nom_utilisateur()}."
    except Exception as e:
        return f"Je n'ai pas réussi à ouvrir Spotify : {e}"

async def spotify_lecture_pause():
    """Basculer lecture / pause via la touche média globale."""
    pyautogui.press('playpause')
    return f"Lecture/Pause, {nom_utilisateur()}."

async def spotify_suivant():
    """Piste suivante via la touche média globale."""
    pyautogui.press('nexttrack')
    return f"Piste suivante, {nom_utilisateur()}."

async def spotify_precedent():
    """Piste précédente via la touche média globale."""
    pyautogui.press('prevtrack')
    return f"Piste précédente, {nom_utilisateur()}."

async def spotify_stop():
    """Met en pause (Spotify n'a pas de vrai stop)."""
    _focus_spotify()
    time.sleep(0.2)
    pyautogui.press('playpause')
    return f"Musique mise en pause, {nom_utilisateur()}."

def spotify_lancer_playlist(playlist_uri: str = "") -> bool:
    """Ouvre Spotify et lance une playlist/piste par son URI ou son URL web.
    Utilisable depuis du code synchrone (executer_action_pc).
    Retourne True si réussi."""
    try:
        # Convertir URL web open.spotify.com → URI native spotify:
        if playlist_uri.startswith("https://open.spotify.com/"):
            m = re.search(r'/(track|playlist|album|artist)/([A-Za-z0-9]+)', playlist_uri)
            if m:
                playlist_uri = f"spotify:{m.group(1)}:{m.group(2)}"

        deja_ouvert = False
        try:
            deja_ouvert = _focus_spotify()
        except Exception:
            pass

        if playlist_uri:
            # Le protocole spotify: est géré par Windows → ouvre l'app et navigue
            subprocess.Popen(["explorer", playlist_uri], shell=False)
            time.sleep(3)
        elif not deja_ouvert:
            chemin = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
            if os.path.exists(chemin):
                subprocess.Popen([chemin])
            else:
                subprocess.Popen(["explorer", "spotify:"], shell=False)
            time.sleep(4)

        try:
            _focus_spotify()
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[SPOTIFY] Erreur lancement playlist : {e}")
        return False

async def spotify_volume(direction, paliers=4):
    """Monte ou baisse le volume Spotify via Ctrl+Haut/Bas."""
    if not _focus_spotify():
        return f"Spotify ne semble pas ouvert, {nom_utilisateur()}."
    time.sleep(0.2)
    for _ in range(int(paliers)):
        if direction in ("monter", "up", "augmenter", "plus"):
            pyautogui.hotkey('ctrl', 'up')
        else:
            pyautogui.hotkey('ctrl', 'down')
        time.sleep(0.05)
    msg = "Volume monté" if direction in ("monter", "up", "augmenter", "plus") else "Volume baissé"
    return f"{msg} sur Spotify, {nom_utilisateur()}."

async def spotify_rechercher(recherche):
    """Ouvre la barre de recherche Spotify, tape la requête et valide."""
    import pyperclip
    # Spotify doit être ouvert
    if not _focus_spotify():
        await spotify_ouvrir()
        time.sleep(3)
        _focus_spotify()
    time.sleep(0.5)

    # Raccourci Ctrl+L pour aller dans la barre de recherche (toutes versions)
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.5)
    # Fallback Ctrl+K (nouvelle interface Spotify)
    pyautogui.hotkey('ctrl', 'k')
    time.sleep(0.4)

    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(recherche)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('enter')
    
    # On attend un peu plus pour être sûr que les résultats sont chargés
    time.sleep(2.0)
    
    # On appuie sur Entrée pour valider la recherche (ouvre l'album/artiste si c'est le cas)
    pyautogui.press('enter')
    time.sleep(1.0)
    
    # On appuie une deuxième fois sur Entrée pour lancer la lecture du premier élément
    # C'est plus fiable que Tab+Entrée qui peut dériver sur d'autres boutons
    pyautogui.press('enter')
    time.sleep(0.5)
    
    # Sécurité supplémentaire : si c'était déjà sélectionné mais en pause
    # (Note: l'appui sur 'space' peut être risqué si on n'est pas focus, mais Entrée est safe)
    pyautogui.press('enter')
    
    return f"C'est fait {nom_utilisateur()}, je lance la lecture de '{recherche}' sur Spotify."

