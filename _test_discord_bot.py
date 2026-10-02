# -*- coding: utf-8 -*-
"""Vérifie discord_bot.py : filtre de risque + état de confirmation. Aucun réseau."""

import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import discord_bot as db

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


# ── Détection de risque ──────────────────────────────────────────────────
for phrase in ["désinstalle Chrome", "supprime le dossier téléchargements",
               "efface tous mes fichiers", "formate le disque D",
               "éteins le pc", "redémarre l'ordinateur",
               "déverrouille la porte d'entrée", "vide la corbeille"]:
    verifier("détecte comme risqué : %r" % phrase, db.est_risque(phrase))

for phrase in ["quelle heure il est", "mets de la musique",
               "code-moi un script", "allume la lumière du salon"]:
    verifier("PAS détecté comme risqué : %r" % phrase, not db.est_risque(phrase))

# ── État de confirmation ─────────────────────────────────────────────────
uid = 12345

verifier("aucune confirmation en attente au départ", db.confirmation_en_attente(uid) is None)

db.demande_confirmation(uid, "désinstalle Chrome")
verifier("confirmation en attente après demande",
          db.confirmation_en_attente(uid) == "désinstalle Chrome")

db.annuler_confirmation(uid)
verifier("plus rien en attente après annulation", db.confirmation_en_attente(uid) is None)

# Expiration : on retro-date artificiellement, comme les autres tests de
# ce dépôt qui ne dépendent jamais de vrais délais d'attente.
db.demande_confirmation(uid, "supprime tout")
db._EN_ATTENTE[uid]["depuis"] = time.time() - db.TIMEOUT_CONFIRMATION - 1
verifier("confirmation expirée après le délai -> None", db.confirmation_en_attente(uid) is None)

for mot in ("confirme", "Confirmé", "OUI", "vas-y", "vas y"):
    verifier("reconnu comme confirmation : %r" % mot, db.est_confirmation(mot))

for mot in ("non", "annule", "peut-être", ""):
    verifier("PAS reconnu comme confirmation : %r" % mot, not db.est_confirmation(mot))

# « confirme » exécute la demande MISE EN ATTENTE, par utilisateur ET salon,
# et n'est jamais transmis tel quel au pipeline (il y validerait autre chose).
for phrase in ("désarme l'alarme", "coupe l'alarme"):
    verifier("détecte comme risqué : %r" % phrase, db.est_risque(phrase))
db.demande_confirmation((uid, 1), "désinstalle Chrome")
verifier("un autre salon ne tranche pas la demande",
          db.resoudre_confirmation((uid, 2), "confirme") == (False, None))
verifier("« confirme » renvoie la demande en attente, pas le mot",
          db.resoudre_confirmation((uid, 1), "confirme") == (True, "désinstalle Chrome"))
verifier("la demande est consommée", db.confirmation_en_attente((uid, 1)) is None)
db.demande_confirmation((uid, 1), "supprime tout")
verifier("autre chose annule", db.resoudre_confirmation((uid, 1), "non") == (True, None))


# Message privé : pas de serveur (guild None), « quitte le vocal » ne plante pas.
class _Salon:
    def __init__(self):
        self.envoye = []

    async def send(self, texte):
        self.envoye.append(texte)


class _MessagePrive:
    guild = None
    channel = _Salon()


import asyncio  # noqa: E402
asyncio.run(db._quitter_vocal(_MessagePrive))
verifier("quitter le vocal en message privé répond sans erreur",
          _MessagePrive.channel.envoye == ["Je ne suis dans aucun salon vocal Discord."])

# ── Détection de la commande photo ───────────────────────────────────────
for phrase in ["montre-moi mon bureau", "Montre moi mon bureau",
               "montre-moi la caméra", "montre-moi la webcam",
               "montre-moi ce que tu vois", "montre moi ton bureau"]:
    verifier("détecte comme demande de photo : %r" % phrase, bool(db._MOTIF_PHOTO.search(phrase)))

for phrase in ["montre-moi mon planning", "mon bureau est en désordre",
               "désinstalle Chrome", "quelle heure il est"]:
    verifier("PAS détecté comme demande de photo : %r" % phrase, not db._MOTIF_PHOTO.search(phrase))

# ── Détection des commandes surveillance on/off ──────────────────────────
verifier("détecte 'active la surveillance'",
          bool(db._MOTIF_SURVEILLANCE_ON.search("active la surveillance")))
verifier("détecte 'désactive la surveillance'",
          bool(db._MOTIF_SURVEILLANCE_OFF.search("désactive la surveillance")))
verifier("'active la surveillance' NE matche PAS le motif OFF",
          not db._MOTIF_SURVEILLANCE_OFF.search("active la surveillance"))
verifier("'désactive la surveillance' NE matche PAS le motif ON",
          not db._MOTIF_SURVEILLANCE_ON.search("désactive la surveillance"))

# ── Détection rejoindre/quitter le vocal ─────────────────────────────────
for phrase in ["rejoins le vocal", "rejoins-moi dans le vocal",
               "viens dans le vocal", "Rejoins le vocal stp",
               "Rejoin le salon vocal", "Rejoins le salon vocal discord",
               "rejoins le canal vocal"]:
    verifier("détecte comme rejoindre le vocal : %r" % phrase,
              bool(db._MOTIF_REJOINDRE_VOCAL.search(phrase)))

for phrase in ["quitte le vocal", "déconnecte-toi du vocal",
               "quitte le salon vocal", "quitte le canal vocal"]:
    verifier("détecte comme quitter le vocal : %r" % phrase,
              bool(db._MOTIF_QUITTER_VOCAL.search(phrase)))

verifier("'rejoins le vocal' NE matche PAS le motif quitter",
          not db._MOTIF_QUITTER_VOCAL.search("rejoins le vocal"))
verifier("'quitte le vocal' NE matche PAS le motif rejoindre",
          not db._MOTIF_REJOINDRE_VOCAL.search("quitte le vocal"))

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Bot Discord (filtre de risque + confirmation) : conforme.")
