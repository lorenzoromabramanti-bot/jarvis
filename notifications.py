# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Notification push (Discord)
============================================
JARVIS finit des tâches en arrière-plan (mission B2/E) mais ne le dit qu'au
prochain briefing — si l'utilisateur n'est pas devant le PC, il ne sait rien
tant qu'il ne redemande pas. Un webhook Discord pousse le résultat dès qu'il
existe, sans bot à enregistrer : juste une URL (côté Discord : Paramètres du
salon -> Intégrations -> Webhooks -> Nouveau webhook).

Best-effort, jamais bloquant : une panne Discord (URL absente, réseau,
timeout) ne doit jamais faire échouer la tâche elle-même — ne lève jamais,
renvoie juste ok/pas ok, comme le reste de ce dépôt.

HEURES CALMES (mission comparaison roadmap, 2026-09-18)
Avant ceci, une tâche terminée à 3h du matin poussait un ping Discord
immédiat — rien ne distinguait l'heure. `envoyer_tache_terminee()` reporte
les résultats non critiques aux heures calmes : rien n'est perdu, la tâche
reste dans `taches_nocturnes.a_signaler()` pour le prochain briefing, seule
la notification immédiate est retardée. `envoyer()` lui-même ne change pas
de comportement — les 5 appels existants dans main2.py continuent de
pousser tout de suite tant qu'ils n'ont pas migré vers la nouvelle fonction.
"""

import json
import os
import time
import requests

_LIMITE_DISCORD = 2000  # limite réelle de l'API Discord par message

HEURE_CALME_DEBUT = "22:00"
HEURE_CALME_FIN = "08:00"


def _webhook_url():
    return os.environ.get("DISCORD_WEBHOOK_URL")


def _heure_hm(maintenant=None):
    t = maintenant or time.localtime()
    return "%02d:%02d" % (t.tm_hour, t.tm_min)


def _reglage_heure(nom_env, defaut):
    """
    `os.environ.get(nom_env, defaut)` NE retombe PAS sur `defaut` quand la
    variable existe mais est vide — exactement ce que `.env.example` ship
    (`JARVIS_HEURES_CALMES_DEBUT=`) : copié tel quel en `.env`, la clé
    existe avec la valeur "", et `.get()` la renvoie au lieu du défaut. Le
    `or` couvre ce cas en plus de la variable absente.
    """
    return os.environ.get(nom_env) or defaut


def en_heures_calmes(maintenant=None):
    """
    Vrai si l'heure actuelle (ou `maintenant`, un struct_time injectable
    pour les tests) tombe dans la plage calme. La plage traverse minuit
    (22:00 -> 08:00) : une comparaison directe début<=x<=fin échouerait,
    donc on teste les deux sens selon que début précède ou suit fin.
    """
    debut = _reglage_heure("JARVIS_HEURES_CALMES_DEBUT", HEURE_CALME_DEBUT)
    fin = _reglage_heure("JARVIS_HEURES_CALMES_FIN", HEURE_CALME_FIN)
    maintenant_hm = _heure_hm(maintenant)
    if debut <= fin:
        return debut <= maintenant_hm < fin
    return maintenant_hm >= debut or maintenant_hm < fin


def envoyer_tache_terminee(message, critique=False, maintenant=None):
    """
    Pousse le résultat d'une tâche de fond, sauf en heures calmes si elle
    n'est pas `critique`. Renvoie (ok, raison) comme envoyer() ; en heures
    calmes et non critique, ok=False avec une raison qui le dit explicitement
    (à ne pas confondre avec un échec réseau).
    """
    if not critique and en_heures_calmes(maintenant):
        return False, ("heures calmes (%s-%s) — reporte au prochain briefing"
                       % (_reglage_heure("JARVIS_HEURES_CALMES_DEBUT", HEURE_CALME_DEBUT),
                          _reglage_heure("JARVIS_HEURES_CALMES_FIN", HEURE_CALME_FIN)))
    return envoyer(message)


def envoyer(message):
    """
    Pousse `message` sur le webhook Discord configuré. Renvoie (ok, raison).

    Pas de DISCORD_WEBHOOK_URL configurée = désactivé silencieusement pour
    l'utilisateur (pas d'erreur vocale) — mais la raison reste dans le
    retour pour qui veut logger, jamais un échec muet.
    """
    url = _webhook_url()
    if not url:
        return False, "DISCORD_WEBHOOK_URL non configurée"

    contenu = message if len(message) <= _LIMITE_DISCORD else message[:_LIMITE_DISCORD - 1] + "…"
    try:
        r = requests.post(url, json={"content": contenu}, timeout=5)
        if r.status_code in (200, 204):
            return True, "ok"
        return False, "Discord a répondu %d" % r.status_code
    except requests.exceptions.RequestException as e:
        return False, str(e)


def envoyer_photo(chemin_image, legende=""):
    """
    Pousse une image sur le webhook Discord, avec une légende optionnelle.
    Renvoie (ok, raison) — mêmes garanties que envoyer() : jamais bloquant,
    ne lève jamais.
    """
    url = _webhook_url()
    if not url:
        return False, "DISCORD_WEBHOOK_URL non configurée"
    if not os.path.exists(chemin_image):
        return False, "fichier introuvable : %s" % chemin_image

    try:
        # Multipart Discord : le JSON (content, embeds...) va dans le champ
        # "payload_json", le fichier dans "files[0]" -- un champ "file" nu
        # + un "data" a part est accepte (200) mais Discord ne relie pas
        # le contenu a la piece jointe correctement, elle s'affiche cassee.
        with open(chemin_image, "rb") as f:
            fichiers = {
                "payload_json": (None, json.dumps({"content": legende[:_LIMITE_DISCORD]}),
                                  "application/json"),
                "files[0]": (os.path.basename(chemin_image), f, "image/jpeg"),
            }
            r = requests.post(url, files=fichiers, timeout=15)
        if r.status_code in (200, 204):
            return True, "ok"
        return False, "Discord a répondu %d" % r.status_code
    except requests.exceptions.RequestException as e:
        return False, str(e)
