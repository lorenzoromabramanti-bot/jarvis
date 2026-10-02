# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Notification push (Slack)
==========================================
Même besoin que notifications.py (Discord), pour qui préfère Slack :
« Reach her where you are » de la roadmap Trillion demandait les deux, pas
un seul. Un webhook entrant Slack suffit, pas de bot à enregistrer (côté
Slack : app Slack -> Incoming Webhooks -> Add New Webhook to Workspace).

Séparé de notifications.py plutôt que fusionné dans un `envoyer(canal=...)`
générique : les deux API ont des formats de payload et des codes de succès
différents (Discord : 200/204 ; Slack : 200 avec un corps texte "ok"), les
mélanger dans une fonction à branches aurait été plus dur à lire que deux
fichiers courts et parallèles. `en_heures_calmes()` reste défini une seule
fois, dans notifications.py, et réutilisé ici — pas dupliqué.

Best-effort, jamais bloquant, mêmes garanties que notifications.py.
"""

import os
import requests

import notifications as _discord  # réutilise en_heures_calmes(), pas de doublon

_LIMITE_SLACK = 40000  # limite réelle des messages Slack (texte brut)


def _webhook_url():
    return os.environ.get("SLACK_WEBHOOK_URL")


def envoyer(message):
    """Pousse `message` sur le webhook Slack configuré. Renvoie (ok, raison)."""
    url = _webhook_url()
    if not url:
        return False, "SLACK_WEBHOOK_URL non configurée"

    contenu = message if len(message) <= _LIMITE_SLACK else message[:_LIMITE_SLACK - 1] + "…"
    try:
        r = requests.post(url, json={"text": contenu}, timeout=5)
        # L'API webhook Slack renvoie 200 avec le corps "ok" en succès, pas
        # de code 204 comme Discord — vérifier le corps évite de prendre
        # une erreur 200-avec-message-d'erreur pour un succès.
        if r.status_code == 200 and r.text.strip().lower() == "ok":
            return True, "ok"
        return False, "Slack a répondu %d : %s" % (r.status_code, r.text[:120])
    except requests.exceptions.RequestException as e:
        return False, str(e)


def envoyer_tache_terminee(message, critique=False, maintenant=None):
    """Même contrat que notifications.envoyer_tache_terminee(), pour Slack."""
    if not critique and _discord.en_heures_calmes(maintenant):
        # _reglage_heure (pas .environ.get(cle, defaut)) : une variable
        # presente mais vide - exactement ce que .env.example ship - ne doit
        # pas ecraser le defaut. Voir sa docstring dans notifications.py.
        debut = _discord._reglage_heure("JARVIS_HEURES_CALMES_DEBUT", _discord.HEURE_CALME_DEBUT)
        fin = _discord._reglage_heure("JARVIS_HEURES_CALMES_FIN", _discord.HEURE_CALME_FIN)
        return False, "heures calmes (%s-%s) — reporte au prochain briefing" % (debut, fin)
    return envoyer(message)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok, raison = envoyer("Essai de la notification Slack.")
    print("envoi : %s (%s)" % (ok, raison))
