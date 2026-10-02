# -*- coding: utf-8 -*-
"""Vérifie surveillance_bureau.py : flag config, détection, debounce. Aucun accès caméra."""

import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import surveillance_bureau as sb

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


_sauvegarde = None
if os.path.exists(sb.FICHIER_CONFIG):
    _sauvegarde = io.open(sb.FICHIER_CONFIG, encoding="utf-8").read()

try:
    io.open(sb.FICHIER_CONFIG, "w", encoding="utf-8").write("{}")

    verifier("désactivée par défaut (config vide)", sb.surveillance_active() is False)

    sb.activer(True)
    verifier("activer(True) -> lu comme actif", sb.surveillance_active() is True)

    sb.activer(False)
    verifier("activer(False) -> lu comme inactif", sb.surveillance_active() is False)

    # Fichier corrompu -> jamais planter, jamais se croire actif par erreur.
    io.open(sb.FICHIER_CONFIG, "w", encoding="utf-8").write("{ceci n'est pas du json")
    verifier("config corrompue -> desactive (fail-safe), pas d'exception",
              sb.surveillance_active() is False)

    # activer() doit reussir a ecrire par-dessus une config corrompue, pas
    # juste echouer silencieusement.
    sb.activer(True)
    verifier("activer() repare une config corrompue au passage", sb.surveillance_active() is True)

    verifier("detecter_visage(None) -> False, pas d'exception", sb.detecter_visage(None) is False)

    # ── Debounce ──────────────────────────────────────────────────────────
    sb._dernier_visage_detecte = 0.0
    verifier("alerte due au tout debut", sb.alerte_due(maintenant=1000.0))

    sb.marquer_alerte_envoyee(maintenant=1000.0)
    verifier("pas due juste apres une alerte", not sb.alerte_due(maintenant=1000.0 + 10))
    verifier("toujours pas due avant le delai", not sb.alerte_due(maintenant=1000.0 + sb.DEBOUNCE_ALERTE - 1))
    verifier("due une fois le delai ecoule", sb.alerte_due(maintenant=1000.0 + sb.DEBOUNCE_ALERTE + 1))

finally:
    if _sauvegarde is not None:
        io.open(sb.FICHIER_CONFIG, "w", encoding="utf-8").write(_sauvegarde)
    elif os.path.exists(sb.FICHIER_CONFIG):
        os.remove(sb.FICHIER_CONFIG)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Surveillance bureau (détection + debounce) : conforme.")
