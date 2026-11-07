# -*- coding: utf-8 -*-
"""Le micro de JARVIS est-il coupé dans Windows ? (lecture seule, pycaw)

Le 06/11, « il ne m'entend pas » venait de là : le micro de la webcam était coupé dans Windows depuis la
mise à jour d'un pilote, et rien ne le disait. main2.py vérifie toutes les 5 minutes et prévient une fois.
"""


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


def etat(index=None):
    """(coupé, nom) ; coupé vaut None si on ne sait pas lire (pas de micro, pycaw absent)."""
    try:
        from ctypes import POINTER, cast

        import comtypes
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError as e:
        return None, repr(e)
    comtypes.CoInitialize()
    try:
        enum = AudioUtilities.GetDeviceEnumerator()
        defaut = enum.GetDefaultAudioEndpoint(1, 0).GetId()  # micro (capture), console
        liste = enum.EnumAudioEndpoints(1, 1)                # micros actifs
        micros = []
        for i in range(liste.GetCount()):
            dev = liste.Item(i)
            vol = cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
            micros.append((dev.GetId(), AudioUtilities.CreateDevice(dev).FriendlyName, bool(vol.GetMute())))
        nom, coupe = choisir(micros, _nom_pyaudio(index), defaut)
        return coupe, nom or ""
    except Exception as e:
        return None, repr(e)
    finally:
        comtypes.CoUninitialize()
