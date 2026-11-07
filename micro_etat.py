# -*- coding: utf-8 -*-
"""Le micro de JARVIS est-il coupé dans Windows ? (lecture seule, pycaw)

Le 06/11, « il ne m'entend pas » venait de là : le micro de la webcam était coupé dans Windows depuis la
mise à jour d'un pilote, et rien ne le disait. main2.py vérifie toutes les 5 minutes et prévient une fois.

07/11 : deux arrêts brutaux de JARVIS (0xc0000005 dans _ctypes, 21:57 et 22:26), chacun juste après
ce contrôle. Cause : un CoUninitialize de notre part, alors que comtypes initialise COM lui-même à
l'import et le referme à la sortie ; des pointeurs COM gardés en cache étaient ensuite libérés sur un
COM fermé. Reproduit le même soir : le processus de contrôle plantait (même code) dès le 1er appel.
Donc : plus aucun CoUninitialize ici ; le processus de contrôle sort par os._exit juste après sa
réponse (pas de libération tardive) ; et main2 passe par etat_isole() : un plantage natif, s'il en
reste un, tue ce processus-là, jamais JARVIS.
"""
import json
import os
import subprocess
import sys


def choisir(micros, nom_voulu, defaut_id):
    """(nom, coupé) du micro qu'utilise l'oreille : celui de « mic_device_index » s'il est trouvé, sinon le
    micro par défaut de Windows. micros : [(id, nom, coupé)]. PyAudio tronque les noms : on compare le début."""
    nom_voulu = (nom_voulu or "").strip().lower()
    if nom_voulu:
        for _id, nom, coupe in micros:
            if nom.lower().startswith(nom_voulu) or nom_voulu.startswith(nom.lower()):
                return nom, coupe
    for _id, nom, coupe in micros:
        if _id == defaut_id:
            return nom, coupe
    return None, None


def _nom_pyaudio(index):
    if index is None:
        return ""
    import pyaudio
    p = pyaudio.PyAudio()
    try:
        return p.get_device_info_by_index(int(index)).get("name", "")
    finally:
        p.terminate()


def _lire():
    """La lecture COM elle-même. Ne renvoie que des valeurs Python : aucun pointeur COM ne lui survit."""
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    enum = AudioUtilities.GetDeviceEnumerator()
    defaut = str(enum.GetDefaultAudioEndpoint(1, 0).GetId())  # micro (capture), console
    liste = enum.EnumAudioEndpoints(1, 1)                     # micros actifs
    micros = []
    for i in range(liste.GetCount()):
        dev = liste.Item(i)
        vol = cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
        micros.append((str(dev.GetId()), str(AudioUtilities.CreateDevice(dev).FriendlyName), bool(vol.GetMute())))
    return micros, defaut


def etat(index=None):
    """(coupé, nom) ; coupé vaut None si on ne sait pas lire (pas de micro, pycaw absent).
    À n'appeler que dans le processus de contrôle (python micro_etat.py) : voir etat_isole()."""
    try:
        # PyAudio AVANT tout objet COM : en se fermant, PortAudio referme COM sur ce fil, et un pointeur
        # comtypes encore vivant plantait ensuite à sa libération (cause réelle des arrêts du 07/11).
        nom_voulu = _nom_pyaudio(index)
        import comtypes
        import pycaw.pycaw  # noqa: F401
    except ImportError as e:
        return None, repr(e)
    except Exception as e:  # PyAudio absent ou indice de micro invalide
        return None, repr(e)
    comtypes.CoInitialize()  # sans CoUninitialize, volontairement : voir l'en-tête
    try:
        micros, defaut = _lire()
        nom, coupe = choisir(micros, nom_voulu, defaut)
        return coupe, nom or ""
    except Exception as e:
        return None, repr(e)


def etat_isole(index=None, delai=30):
    """etat() dans un processus à part (python.exe sans fenêtre) : ce que fait main2.
    (coupé, nom), ou (None, raison) si le contrôle échoue ou plante — JARVIS, lui, reste debout."""
    python = os.path.join(os.path.dirname(sys.executable), "python.exe")
    if not os.path.exists(python):
        python = sys.executable
    try:
        r = subprocess.run([python, os.path.abspath(__file__), "" if index is None else str(index)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=delai, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        lignes = r.stdout.strip().splitlines()
        if not lignes:  # une réponse écrite compte même si le processus a planté APRÈS
            return None, f"contrôle du micro interrompu (code {r.returncode})"
        d = json.loads(lignes[-1])
        return d.get("coupe"), d.get("nom", "")
    except Exception as e:  # délai dépassé, JSON illisible…
        return None, repr(e)


if __name__ == "__main__":
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    coupe, nom = etat(int(arg) if arg.lstrip("-").isdigit() else None)
    sys.stdout.write(json.dumps({"coupe": coupe, "nom": nom}, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    os._exit(0)  # pas de fin d'interpréteur : c'est là que les pointeurs COM en cache faisaient planter
