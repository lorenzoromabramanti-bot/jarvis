# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — « JARVIS léger » pendant les jeux (2026-10-17)
===========================================================
Un outil de mode jeu peut écrire ~/mode-jeu/actif.json pendant une
partie, avec "jarvis_leger": true si l'option est cochée. Les boucles de fond lourdes de JARVIS
(antivirus en direct toutes les 3 s, surveillance du ciel qui peut PARLER en pleine partie) sautent
alors leur tour. La voix et les commandes restent actives. Windows Defender continue de protéger.
"""
import json
import os
import time

import psutil

FICHIER = os.path.join(os.path.expanduser("~"), "mode-jeu", "actif.json")
_cache = [0.0, False]


def actif(fichier=None, maintenant=None, delai=5.0):
    """Vrai si le mode jeu tourne (son PID est vivant) et demande à JARVIS de s'alléger. Relu au plus toutes les 5 s."""
    t = time.monotonic() if maintenant is None else maintenant
    if fichier is None and t - _cache[0] < delai:
        return _cache[1]
    etat = False
    try:
        with open(fichier or FICHIER, encoding="utf-8") as f:
            d = json.load(f)
        etat = bool(d.get("jarvis_leger")) and psutil.pid_exists(int(d.get("pid") or 0))
    except (OSError, ValueError, TypeError):
        pass
    if fichier is None:
        _cache[:] = [t, etat]
    return etat
