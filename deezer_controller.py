try:
    import pyautogui
except ImportError:
    pyautogui = None
import time
import pyperclip
import asyncio
import subprocess
import os
from config import nom_utilisateur

# DEEZER
# ==========================================

def _focus_deezer():
    """Met la fenêtre Deezer au premier plan. Retourne True si trouvé."""
    import win32gui, win32con
    candidats = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            titre = win32gui.GetWindowText(hwnd)
            if "Deezer" in titre:
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

async def deezer_ouvrir():
    """Lance Deezer s'il n'est pas déjà ouvert."""
    try:
        if _focus_deezer():
            return f"Deezer est déjà ouvert, {nom_utilisateur()}, je l'ai mis au premier plan."
        
        # Le protocole Windows de base pour Deezer
        subprocess.Popen(["explorer", "deezer:"], shell=False)
        time.sleep(4)
        _focus_deezer()
        return f"Deezer lancé, {nom_utilisateur()}."
    except Exception as e:
        return f"Je n'ai pas réussi à ouvrir Deezer : {e}"

async def deezer_lecture_pause():
    """Basculer lecture / pause via la touche média globale."""
    pyautogui.press('playpause')
    return f"Lecture/Pause, {nom_utilisateur()}."

async def deezer_suivant():
    """Piste suivante via la touche média globale."""
    pyautogui.press('nexttrack')
    return f"Piste suivante sur Deezer, {nom_utilisateur()}."

async def deezer_precedent():
    """Piste précédente via la touche média globale."""
    pyautogui.press('prevtrack')
    return f"Piste précédente sur Deezer, {nom_utilisateur()}."

async def deezer_stop():
    """Met en pause."""
    _focus_deezer()
    time.sleep(0.2)
    pyautogui.press('playpause')
    return f"Musique mise en pause sur Deezer, {nom_utilisateur()}."

async def deezer_volume(direction, paliers=4):
    """Monte ou baisse le volume général du PC puisque Deezer n'a pas de raccourci volume universel simple."""
    time.sleep(0.2)
    for _ in range(int(paliers)):
        if direction in ("monter", "up", "augmenter", "plus"):
            pyautogui.press('volumeup')
        else:
            pyautogui.press('volumedown')
        time.sleep(0.05)
    msg = "Volume monté" if direction in ("monter", "up", "augmenter", "plus") else "Volume baissé"
    return f"{msg}, {nom_utilisateur()}."

async def deezer_rechercher(recherche):
    """Ouvre la recherche Deezer, tape la requête et valide."""
    if not _focus_deezer():
        await deezer_ouvrir()
        time.sleep(3)
        _focus_deezer()
    time.sleep(0.5)

    # Ctrl+F est le raccourci classique de recherche sur beaucoup d'apps
    pyautogui.hotkey('ctrl', 'f')
    time.sleep(0.5)

    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(recherche)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('enter')
    
    time.sleep(2.0)
    
    # Valider le premier resultat
    pyautogui.press('enter')
    time.sleep(0.5)
    
    # Essayer d'appuyer sur la barre espace pour jouer s'il est focus, 
    # sinon les touches media reprennent le relais
    pyautogui.press('enter')
    
    return f"C'est fait {nom_utilisateur()}, je cherche '{recherche}' sur Deezer."
