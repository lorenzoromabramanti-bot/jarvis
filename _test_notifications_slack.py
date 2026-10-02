# -*- coding: utf-8 -*-
"""Vérifie notifications_slack.py sans jamais toucher le vrai réseau Slack."""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import notifications_slack as slack

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


_sauvegarde = os.environ.pop("SLACK_WEBHOOK_URL", None)

try:
    ok, raison = slack.envoyer("test")
    verifier("sans URL configurée -> pas d'erreur, juste désactivé",
              not ok and "non configurée" in raison)

    long_msg = "x" * 41000
    tronque = long_msg if len(long_msg) <= slack._LIMITE_SLACK else long_msg[:slack._LIMITE_SLACK - 1] + "…"
    verifier("troncature respecte la limite Slack (40000)", len(tronque) <= slack._LIMITE_SLACK)

    os.environ["SLACK_WEBHOOK_URL"] = "http://127.0.0.1:1/inexistant"
    ok2, raison2 = slack.envoyer("test réseau")
    verifier("URL injoignable -> échec propre, jamais d'exception", not ok2 and bool(raison2))

    os.environ.pop("SLACK_WEBHOOK_URL", None)
    minuit_passe = time.struct_time((2026, 1, 1, 2, 30, 0, 0, 0, -1))
    ok3, raison3 = slack.envoyer_tache_terminee("non critique la nuit", critique=False,
                                                maintenant=minuit_passe)
    verifier("non critique + heures calmes -> reporte, reutilise notifications.en_heures_calmes",
              not ok3 and "heures calmes" in raison3)

    ok4, raison4 = slack.envoyer_tache_terminee("critique la nuit", critique=True,
                                                maintenant=minuit_passe)
    verifier("critique + heures calmes -> tente quand meme (echoue ici faute d'URL)",
              not ok4 and "non configurée" in raison4)
finally:
    if _sauvegarde is not None:
        os.environ["SLACK_WEBHOOK_URL"] = _sauvegarde
    else:
        os.environ.pop("SLACK_WEBHOOK_URL", None)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Notifications Slack : conforme.")
