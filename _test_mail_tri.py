# -*- coding: utf-8 -*-
"""
Verifie le tri du courrier et le nettoyage des brouillons, hors ligne.

Ce qui est teste n'est pas « le modele repond bien » — ca depend du modele —
mais les gardes qui doivent tenir MEME quand le modele se trompe : un
expediteur no-reply ne peut pas attendre de reponse, et le raisonnement du
modele ne doit pas partir avec l'e-mail.

    venv\\Scripts\\python.exe _test_mail_tri.py
"""

import sys

import mail_tri as mt


def verifier():
    # ── Nettoyage du brouillon ──────────────────────────────────────────
    # Cas reel observe : le modele annonce sa demarche avant de repondre.
    prefixe = ("Brouillon :\nJe vais demander la date.\n\n---\n\n"
               "Bonjour,\n\nQuelle est la date ?\n\nLorenzo")
    assert mt.nettoyer_brouillon(prefixe).startswith("Bonjour"), \
        "le preambule du modele n'a pas ete retire"

    # Une reponse COURTE derriere un preambule doit aussi etre retrouvee :
    # c'est le cas qu'un critere de longueur ratait.
    court = "Analyse : rien a ajouter.\n\n---\n\nBonjour,\n\nC'est note.\n\nLorenzo"
    assert mt.nettoyer_brouillon(court).startswith("Bonjour"), \
        "une reponse courte a ete prise pour une signature"

    # Un `---` de signature est legitime : ne rien couper.
    signature = "Bonjour,\n\nMerci pour votre retour.\n\n---\nLorenzo"
    assert mt.nettoyer_brouillon(signature).startswith("Bonjour"), \
        "une signature a ete prise pour un preambule"
    assert "Lorenzo" in mt.nettoyer_brouillon(signature), \
        "la signature a ete perdue"

    # Sans separateur, on ne touche a rien.
    nu = "Bonjour,\n\nMerci.\n\nLorenzo"
    assert mt.nettoyer_brouillon(nu) == nu

    # Ambigu (aucune salutation nulle part) : on laisse tel quel plutot que
    # de deviner et de tronquer un message.
    ambigu = "Premiere partie.\n\n---\n\nSeconde partie."
    assert mt.nettoyer_brouillon(ambigu) == ambigu, \
        "un texte ambigu a ete tronque"

    assert mt.nettoyer_brouillon("") == ""
    assert mt.nettoyer_brouillon(None) == ""

    # ── Le prenom sert a signer ─────────────────────────────────────────
    p = mt._prenom()
    assert p and p[0].isupper(), "prenom absent ou non capitalise : %r" % p

    # ── Garde dure : un no-reply n'attend pas de reponse ────────────────
    # Meme si le modele le classe la, la garde doit reprendre la main.
    faux = [{"id": "1", "compte": "T", "de": "Truc <no-reply@exemple.com>",
             "sujet": "Merci de repondre a ce message", "date": ""}]
    for m in mt.classer(faux, utiliser_modele=False):
        assert m["categorie"] != "a_repondre", \
            "un expediteur no-reply a ete classe a_repondre"

    # ── L'origine du classement est declaree, jamais supposee ───────────
    for m in mt.classer(faux, utiliser_modele=False):
        assert m.get("source") == "heuristique", \
            "l'heuristique se fait passer pour le modele : %r" % m.get("source")
        assert m.get("categorie") in mt.CATEGORIES

    print("  OK  preambule du modele retire")
    print("  OK  reponse courte retrouvee derriere un preambule")
    print("  OK  signature legitime conservee")
    print("  OK  texte ambigu laisse intact plutot que tronque")
    print("  OK  prenom lu depuis la config")
    print("  OK  no-reply jamais classe 'a repondre'")
    print("  OK  origine du classement declaree")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Tri du courrier : conforme.")
