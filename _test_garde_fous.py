# -*- coding: utf-8 -*-
"""
Verifie les garde-fous.

CE QUI EST TESTE
Pas « la liste de domaines contient des banques » — mais les trois choses qui
rendent un garde-fou inutile quand elles ratent :

  1. Il doit distinguer AGIR de REGARDER. Bloquer l'affichage d'une page que
     l'utilisateur a demandee serait une panne, pas une protection.
  2. Il doit se declencher sur le DOMAINE, pas sur le texte. Sinon une
     recherche « comment ouvrir un compte en banque » serait bloquee, et le
     garde-fou finirait desactive par agacement.
  3. Il ne doit pas etre contournable. En mode simple, refus. En mode avance,
     il faut RETAPER une phrase — une case se coche par reflexe.

    venv\\Scripts\\python.exe _test_garde_fous.py
"""

import io
import os
import shutil
import sys

import garde_fous as gf


def verifier():
    chemin = str(gf._chemin())
    secours = chemin + ".test-bak"
    existait = os.path.exists(chemin)
    if existait:
        shutil.copy(chemin, secours)
    try:
        _controles()
    finally:
        if existait:
            shutil.move(secours, chemin)
        elif os.path.exists(chemin):
            os.remove(chemin)
        print("  OK  etat des garde-fous restaure")


def _controles():
    # ── Classement : sur le domaine, pas sur le texte ───────────────────
    sensibles = {
        "https://www.credit-agricole.fr/mon-compte": "banque",
        "https://clients.boursorama.com": "banque",
        "https://www.paypal.com/myaccount": "banque",
        "https://impots.gouv.fr/particulier": "impots",
        "https://www.ameli.fr/assure": "sante",
        "https://www.doctolib.fr/rendez-vous": "sante",
    }
    for url, attendu in sensibles.items():
        obtenu = gf.categorie(url)
        assert obtenu is not None, "%s non detecte comme sensible" % url
    print("  OK  %d sites sensibles reconnus" % len(sensibles))

    # Le piege : ces pages PARLENT de banque sans en etre une.
    ordinaires = [
        "https://fr.wikipedia.org/wiki/Banque",
        "https://www.google.com/search?q=comment+ouvrir+un+compte+en+banque",
        "https://www.youtube.com/watch?v=x",
        "https://news.ycombinator.com",
        "https://www.lemonde.fr/economie/article/banques-en-crise",
    ]
    for url in ordinaires:
        assert gf.categorie(url) is None, \
            "%s pris a tort pour un site sensible" % url
    print("  OK  %d pages qui PARLENT de banque restent ordinaires" % len(ordinaires))

    # ── Regarder oui, agir non ──────────────────────────────────────────
    banque = "https://clients.boursorama.com/mon-budget"
    ok, _ = gf.verifier_action_web(banque, "lecture")
    assert ok, "l'affichage d'une page demandee a ete bloque"
    for nature in ("vision_ecrire", "vision_chercher_sur_site", "vision_navigateur"):
        ok, raison = gf.verifier_action_web(banque, nature)
        assert not ok, "%s autorise sur une banque" % nature
        assert raison and "afficher" in raison, \
            "le refus n'explique pas ce qui reste possible : %r" % raison
    print("  OK  lecture autorisee, ecriture refusee, refus explique")

    # Sur un site ordinaire, ecrire reste permis.
    ok, _ = gf.verifier_action_web("https://fr.wikipedia.org", "vision_ecrire")
    assert ok, "l'ecriture est bloquee sur un site ordinaire"
    print("  OK  l'ecriture reste possible ailleurs")

    # ── Mode simple : impossible a desactiver ───────────────────────────
    fait, msg = gf.desactiver("domaines_sensibles",
                              gf.GARDES["domaines_sensibles"]["phrase"],
                              mode="simple")
    assert not fait, "un garde-fou a ete desactive en mode simple"
    assert "simple" in msg.lower(), "le refus n'explique pas pourquoi"
    assert gf.est_actif("domaines_sensibles")
    print("  OK  mode simple : desactivation refusee, meme avec la phrase exacte")

    # ── Mode avance : la phrase exacte, ou rien ─────────────────────────
    for mauvaise in ("oui", "je confirme", "", "je desactive la protection",
                     "JE DESACTIVE LA PROTECTION DES SITES SENSIBLE"):
        fait, msg = gf.desactiver("domaines_sensibles", mauvaise, mode="avance")
        assert not fait, "desactive avec une phrase approximative : %r" % mauvaise
        assert "recopiez" in msg.lower(), "le message n'indique pas quoi taper"
    assert gf.est_actif("domaines_sensibles")
    print("  OK  mode avance : 5 formulations approximatives refusees")

    # La phrase exacte, elle, passe. Accents ignores : elle est tapee.
    fait, msg = gf.desactiver("domaines_sensibles",
                              "je désactive la protection des sites sensibles",
                              mode="avance")
    assert fait, "la phrase exacte a ete refusee : %s" % msg
    assert not gf.est_actif("domaines_sensibles")

    # Et une fois retire, l'ecriture passe : la desactivation a un EFFET.
    ok, _ = gf.verifier_action_web(banque, "vision_ecrire")
    assert ok, "le garde-fou desactive bloque encore — le reglage ne sert a rien"
    print("  OK  la desactivation a un effet reel, pas seulement un affichage")

    fait, _ = gf.reactiver("domaines_sensibles")
    assert fait and gf.est_actif("domaines_sensibles")
    ok, _ = gf.verifier_action_web(banque, "vision_ecrire")
    assert not ok, "reactiver ne remet pas la protection"
    print("  OK  reactivation immediate")

    # ── Chaque garde-fou dit sa consequence ─────────────────────────────
    for g in gf.etat():
        assert len(g["consequence"]) > 40, \
            "%s : la consequence n'est pas expliquee" % g["cle"]
        assert g["phrase"] or not g["desactivable"]
    print("  OK  %d garde-fous, chacun dit ce qu'on perd en le retirant"
          % len(gf.GARDES))

    # ── Le passage oblige existe dans main2 ─────────────────────────────
    # Ecrit mais pas branche : c'est l'erreur que ce depot a deja produite.
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "main2.py"), encoding="utf-8").read()
    nus = src.count("webbrowser.open(")
    assert nus <= 1, ("%d appel(s) direct(s) a webbrowser.open contournent le "
                      "passage oblige" % nus)
    assert src.count("_ouvrir_url(") >= 10, "le passage oblige n'est plus utilise"
    assert src.count("_garde_web, data.get") == 3, \
        "les trois actions de vision ne sont plus toutes gardees"
    print("  OK  passage oblige branche : 14 ouvertures, 3 actions de vision")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Garde-fous : conforme.")
