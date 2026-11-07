# -*- coding: utf-8 -*-
r"""
Vérifie l'orbe flottante sans ouvrir de fenêtre.

CE QU'IL GARDE VRAIMENT
1. JARVIS_ORBE=0 la désactive vraiment : rien ne démarre.
2. L'image n'a AUCUN pixel à demi transparent visible : coins vides, particules
   opaques, et seul le disque invisible (alpha 1) qui attrape la souris. Un
   dégradé ou un halo laisserait un voile (le « petit fond » du 15/10).
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
for intensite in (0.0, 1.0):
    img = o.rendu(297, 3.7, intensite)
    alphas = set(img.getchannel("A").tobytes())
    verifier("intensité %.0f : coins entièrement transparents" % intensite,
             all(img.getpixel(c)[3] == 0 for c in ((0, 0), (296, 0), (0, 296), (296, 296))))
    verifier("intensité %.0f : des particules opaques" % intensite, 255 in alphas)
    verifier("intensité %.0f : aucun pixel à demi transparent (seulement 0, 1 et 255)" % intensite,
             alphas <= {0, 1, 255})
verifier("le disque qui attrape la souris est au centre", o.rendu(297, 0, 0).getpixel((148, 148))[3] in (1, 255))

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
