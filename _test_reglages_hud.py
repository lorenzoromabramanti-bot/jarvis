# -*- coding: utf-8 -*-
r"""
Le message `settings_data` doit avoir la MEME forme, quel que soit l'endroit
d'où il part.

CE QU'IL GARDE VRAIMENT
Quatre endroits de main2.py envoient la configuration au HUD, et un seul y
ajoutait la liste des micros. Enregistrer ses réglages passait par un des
trois autres : le HUD recevait une configuration sans `mic_list`, en concluait
« aucun micro détecté » et vidait la liste déroulante — juste après que
l'utilisateur y ait choisi son micro. Le réglage était bien enregistré ; seul
l'affichage mentait, ce qui est pire qu'une erreur franche.

Ce test interdit le retour du motif : tout envoi de `settings_data` passe par
`_config_pour_hud()`, et ce constructeur pose toujours `mic_list` et
`pyaudio_available`.

    venv\Scripts\python.exe _test_reglages_hud.py
"""

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RACINE = os.path.dirname(os.path.abspath(__file__))
SOURCE = io.open(os.path.join(RACINE, "main2.py"), encoding="utf-8").read()
LIGNES = SOURCE.split("\n")

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


# ── Tout envoi passe par le constructeur unique ──────────────────────────
envois = [n for n, ligne in enumerate(LIGNES) if '"settings_data"' in ligne]
verifier("les envois de settings_data sont retrouves dans le code", len(envois) >= 4)

sans_constructeur = []
for n in envois:
    # Le dict est ecrit sur une a trois lignes selon l'endroit.
    voisinage = "\n".join(LIGNES[n:n + 4])
    if "_config_pour_hud" not in voisinage:
        sans_constructeur.append(n + 1)
verifier("aucun envoi ne construit sa charge utile dans son coin (%d envoi(s))"
         % len(envois), not sans_constructeur)
if sans_constructeur:
    print("      lignes fautives : %s" % sans_constructeur)

# ── Le constructeur pose bien ce que le HUD attend ───────────────────────
debut = SOURCE.find("def _config_pour_hud(")
verifier("_config_pour_hud existe", debut != -1)
if debut != -1:
    suite = SOURCE[debut:]
    fin = suite.find("\n_MASQUE")
    corps = suite[:fin if fin != -1 else 4000]
    for champ in ("mic_list", "pyaudio_available", "nemotron_asr_enabled",
                  "gpu_available", "api_keys"):
        verifier("le constructeur pose toujours %s" % champ,
                 ('donnees["%s"]' % champ) in corps)
    verifier("les cles API sortent masquees", "_masquer_cle" in corps)
    verifier("la charge utile passe par le filtre a secrets",
             "return _sans_secrets(donnees)" in corps)
    verifier("une enumeration de micros qui echoue est DITE, pas avalee",
             "Enumeration des micros impossible" in corps)

# ── Cote HUD : l'avertissement ne doit pas dependre d'une cle absente ────
chemin_ts = os.path.join(RACINE, "frontend", "src", "main.ts")
if os.path.exists(chemin_ts):
    ts = io.open(chemin_ts, encoding="utf-8", errors="replace").read()
    verifier("le HUD lit bien settings.mic_list", "settings.mic_list" in ts)
    verifier("le HUD affiche un avertissement quand la liste est vide",
             "mic-not-detected-warning" in ts)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Réglages envoyés au HUD : une seule forme, quel que soit l'expéditeur.")
