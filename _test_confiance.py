# -*- coding: utf-8 -*-
"""Vérifie confiance.py — journal et lecture de maturité, jamais sur le vrai fichier."""

import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import confiance as cf

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


_chemin_reel = cf._chemin()
_sauvegarde = None
if os.path.exists(_chemin_reel):
    _sauvegarde = io.open(_chemin_reel, encoding="utf-8").read()

try:
    cf._ecrire_tout({"decisions": []})

    m_vide = cf.maturite("envoyer_mail")
    verifier("aucune decision -> pas assez de donnees", not m_vide["assez_de_donnees"])
    verifier("aucune decision -> pas constant", not m_vide["constant"])

    for _ in range(10):
        cf.enregistrer("envoyer_mail", True, detail="brouillon approuve")
    m = cf.maturite("envoyer_mail")
    verifier("10 approbations -> assez de donnees", m["assez_de_donnees"])
    verifier("10/10 approuve -> taux 1.0", m["taux"] == 1.0)
    verifier("10/10 approuve, aucun refus recent -> constant", m["constant"])

    cf.enregistrer("envoyer_mail", False, detail="mauvais destinataire")
    m2 = cf.maturite("envoyer_mail")
    verifier("un refus recent casse 'constant' meme avec un bon taux global",
              not m2["constant"])
    verifier("le refus compte dans le taux", m2["taux"] < 1.0)

    verifier("un type d'action distinct reste isole (pas de fuite)",
              cf.maturite("desinstaller_logiciel")["appels"] == 0)

    h = cf.historique("envoyer_mail")
    verifier("historique renvoie toutes les decisions dans l'ordre", len(h) == 11 and h[0]["approuve"] is True)
finally:
    if _sauvegarde is not None:
        io.open(_chemin_reel, "w", encoding="utf-8").write(_sauvegarde)
    elif os.path.exists(_chemin_reel):
        os.remove(_chemin_reel)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Confiance par type d'action : conforme.")
