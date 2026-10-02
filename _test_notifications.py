# -*- coding: utf-8 -*-
"""Vérifie notifications.py sans jamais toucher le vrai réseau Discord."""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import notifications as notif

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


_sauvegarde = os.environ.pop("DISCORD_WEBHOOK_URL", None)

try:
    ok, raison = notif.envoyer("test")
    verifier("sans URL configurée -> pas d'erreur, juste désactivé",
              not ok and "non configurée" in raison)

    # Message trop long : tronqué, jamais envoyé tel quel à l'API (qui le
    # rejetterait). Vérifié sur la construction, pas sur un vrai POST.
    long_msg = "x" * 3000
    tronque = long_msg if len(long_msg) <= notif._LIMITE_DISCORD else long_msg[:notif._LIMITE_DISCORD - 1] + "…"
    verifier("troncature respecte la limite Discord (2000)", len(tronque) <= notif._LIMITE_DISCORD)

    os.environ["DISCORD_WEBHOOK_URL"] = "http://127.0.0.1:1/inexistant"
    ok2, raison2 = notif.envoyer("test réseau")
    verifier("URL injoignable -> échec propre, jamais d'exception", not ok2 and bool(raison2))

    os.environ.pop("DISCORD_WEBHOOK_URL", None)
    ok3, raison3 = notif.envoyer_photo("chemin_qui_n_existe_pas.jpg")
    verifier("envoyer_photo sans URL -> desactive, pas d'erreur", not ok3 and "non configurée" in raison3)

    os.environ["DISCORD_WEBHOOK_URL"] = "http://127.0.0.1:1/inexistant"
    ok4, raison4 = notif.envoyer_photo("chemin_qui_n_existe_pas.jpg")
    verifier("envoyer_photo, fichier absent -> echec propre avant tout POST",
              not ok4 and "introuvable" in raison4)

    # Heures calmes : plage 22:00-08:00, traverse minuit.
    import time as _time
    minuit_passe = _time.struct_time((2026, 1, 1, 2, 30, 0, 0, 0, -1))   # 02:30
    milieu_journee = _time.struct_time((2026, 1, 1, 14, 0, 0, 0, 0, -1))  # 14:00
    juste_avant_fin = _time.struct_time((2026, 1, 1, 7, 59, 0, 0, 0, -1))  # 07:59
    pile_fin = _time.struct_time((2026, 1, 1, 8, 0, 0, 0, 0, -1))         # 08:00
    verifier("02:30 est en heures calmes", notif.en_heures_calmes(minuit_passe))
    verifier("14:00 n'est pas en heures calmes", not notif.en_heures_calmes(milieu_journee))
    verifier("07:59 est encore en heures calmes", notif.en_heures_calmes(juste_avant_fin))
    verifier("08:00 pile n'est plus en heures calmes (borne exclusive)",
              not notif.en_heures_calmes(pile_fin))

    # Bug trouve en revue de code : .env.example ship les cles presentes
    # mais VIDES ("JARVIS_HEURES_CALMES_DEBUT="). Une fois copie en .env,
    # os.environ.get(cle, defaut) renvoie "" (la cle existe) au lieu du
    # defaut -> les heures calmes ne s'activaient plus jamais, en silence.
    os.environ["JARVIS_HEURES_CALMES_DEBUT"] = ""
    os.environ["JARVIS_HEURES_CALMES_FIN"] = ""
    try:
        verifier("variable d'env presente mais VIDE -> retombe quand meme sur le defaut 22:00-08:00",
                  notif.en_heures_calmes(minuit_passe) and not notif.en_heures_calmes(milieu_journee))
    finally:
        os.environ.pop("JARVIS_HEURES_CALMES_DEBUT", None)
        os.environ.pop("JARVIS_HEURES_CALMES_FIN", None)

    os.environ.pop("DISCORD_WEBHOOK_URL", None)
    ok5, raison5 = notif.envoyer_tache_terminee("non critique la nuit", critique=False,
                                                 maintenant=minuit_passe)
    verifier("non critique + heures calmes -> reporte (pas d'erreur DISCORD_WEBHOOK_URL)",
              not ok5 and "heures calmes" in raison5)

    ok6, raison6 = notif.envoyer_tache_terminee("critique la nuit", critique=True,
                                                 maintenant=minuit_passe)
    verifier("critique + heures calmes -> tente quand meme l'envoi (echoue ici faute d'URL)",
              not ok6 and "non configurée" in raison6)

    ok7, raison7 = notif.envoyer_tache_terminee("en journee", critique=False,
                                                 maintenant=milieu_journee)
    verifier("non critique + heures normales -> tente l'envoi normalement",
              not ok7 and "non configurée" in raison7)
finally:
    if _sauvegarde is not None:
        os.environ["DISCORD_WEBHOOK_URL"] = _sauvegarde
    else:
        os.environ.pop("DISCORD_WEBHOOK_URL", None)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Notifications Discord : conforme.")
