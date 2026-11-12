# -*- coding: utf-8 -*-
r"""
Vérifie l'orbe flottante sans ouvrir de fenêtre.

CE QU'IL GARDE VRAIMENT
1. JARVIS_ORBE=0 la désactive vraiment : rien ne démarre.
2. Pas de voile (le « petit fond » du 15/10) : coins vides, sphère de verre
   opaque, le disque invisible (alpha 1) qui attrape la souris, et du demi
   transparent SEULEMENT sur le bord de la sphère (un pixel adouci) — rien
   au-delà. Le voile venait d'un alpha non prémultiplié : _octets_bgra le
   prémultiplie, c'est vérifié aussi.
3. Le flux d'événements du HUD est lu comme le HUD le lit : agent-state:…,
   réponse en cours, réponse finie ; le reste ne change pas l'état.

    venv\Scripts\python.exe _test_orbe_flottante.py
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import orbe_flottante as o  # noqa: E402

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


print("Interrupteur")
os.environ["JARVIS_ORBE"] = "0"
verifier("JARVIS_ORBE=0 : rien n'est préparé", o.creer("http://localhost:8001") is None)
verifier("demarrer() le dit au lieu d'échouer", o.demarrer()[0] is False)
os.environ.pop("JARVIS_ORBE")
verifier("activée : l'adresse des événements du HUD", o.creer("http://localhost:8001/") == "http://localhost:8001/api/events")

print("Image")
import numpy as np  # noqa: E402

for theme in ("clair", "sombre"):
    for intensite in (0.0, 1.0):
        img = o.rendu(297, 3.7, intensite, theme=theme)
        a = np.asarray(img.getchannel("A"))
        nom = "%s, intensité %.0f" % (theme, intensite)
        verifier("%s : coins entièrement transparents" % nom,
                 all(img.getpixel(c)[3] == 0 for c in ((0, 0), (296, 0), (0, 296), (296, 296))))
        verifier("%s : la sphère est opaque au centre" % nom, img.getpixel((148, 148))[3] == 255)
        yy, xx = np.nonzero((a > 1) & (a < 255))
        r = o.rayon(297, 3.7, intensite)
        ecart = np.abs(np.hypot(xx + .5 - 148.5, yy + .5 - 148.5) - r)
        verifier("%s : demi-transparence seulement sur le bord de la sphère (pas de voile)" % nom,
                 len(ecart) > 0 and float(ecart.max()) <= 2.0)
verifier("le disque qui attrape la souris entoure la sphère", o.rendu(297, 0, 0, theme="clair").getpixel((148, 40))[3] == 1)  # rayon 89, disque 120 : y=40 est entre les deux

print("Transparence prémultipliée")
from PIL import Image  # noqa: E402
octets = o._octets_bgra(Image.new("RGBA", (1, 1), (200, 100, 50, 128)))
verifier("BGRA prémultiplié : la couleur est multipliée par l'alpha", tuple(octets) == (25, 50, 100, 128))
verifier("pixel opaque inchangé", tuple(o._octets_bgra(Image.new("RGBA", (1, 1), (10, 20, 30, 255)))) == (30, 20, 10, 255))

print("Thème")
os.environ.pop("JARVIS_ORBE_THEME", None)
verifier("7 h : claire", o.theme_du_moment(7) == "clair")
verifier("22 h : sombre", o.theme_du_moment(22) == "sombre")
os.environ["JARVIS_ORBE_THEME"] = "sombre"
verifier("JARVIS_ORBE_THEME l'impose", o.theme_du_moment(12) == "sombre")
os.environ.pop("JARVIS_ORBE_THEME")

print("Flux d'événements")
verifier("agent-state:thinking", o.lire_evenement('data: {"type": "agent-state:thinking"}') == "thinking")
verifier("réponse en cours", o.lire_evenement('data: {"role": "assistant", "text": "Bonjour"}') == "responding")
verifier("réponse finie", o.lire_evenement('data: {"role": "assistant", "text": "Bonjour", "done": true}') == "idle")
verifier("battement de cœur ignoré", o.lire_evenement('data: {"type": "heartbeat"}') is None)
verifier("message de l'utilisateur ignoré", o.lire_evenement('data: {"role": "user", "text": "salut"}') is None)
verifier("ligne illisible ignorée", o.lire_evenement("data: {pas du json") is None and o.lire_evenement(": ping") is None)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Orbe flottante : conforme.")
