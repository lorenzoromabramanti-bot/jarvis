# -*- coding: utf-8 -*-
"""
Verifie le catalogue des capacites.

CE QU'IL GARDE VRAIMENT
Pas « le catalogue contient des choses » — mais qu'il ne se DECONNECTE pas du
code. Une liste ecrite a la main diverge des la premiere fonction ajoutee, et
personne ne s'en apercoit : la nouvelle capacite n'apparait simplement jamais
a l'installation, sans erreur nulle part.

Le controle central compare les 142 points d'entree presents dans main2.py
aux actions declarees. Ajouter une action sans l'inscrire au catalogue fait
echouer ce test.

    venv\\Scripts\\python.exe _test_catalogue.py
"""

import io
import json
import os
import shutil
import sys

import catalogue as cat
import config


def verifier():
    # ── Le catalogue colle au code ──────────────────────────────────────
    orphelines, fantomes = cat.verifier_coherence()
    assert not orphelines, (
        "%d action(s) dans main2.py que le catalogue ne reclame pas : %s\n"
        "    Inscris-les dans catalogue.CAPACITES, sinon elles n'apparaitront "
        "jamais a l'installation." % (len(orphelines), ", ".join(orphelines[:8])))
    assert not fantomes, (
        "%d action(s) declaree(s) mais absente(s) du code : %s"
        % (len(fantomes), ", ".join(fantomes[:8])))
    print("  OK  %d points d'entree, tous rattaches a une capacite"
          % len(cat.actions_du_code()))

    # Le controle doit ATTRAPER une orpheline, sinon il ne prouve rien.
    sauv = cat.CAPACITES["vpn"]["actions"]
    cat.CAPACITES["vpn"] = dict(cat.CAPACITES["vpn"],
                                actions=[a for a in sauv if a != "vpn_connect"])
    try:
        o, _ = cat.verifier_coherence()
        assert "vpn_connect" in o, "le controle ne detecte pas une orpheline"
    finally:
        cat.CAPACITES["vpn"] = dict(cat.CAPACITES["vpn"], actions=sauv)
    assert not cat.verifier_coherence()[0], "l'etat n'a pas ete retabli"
    print("  OK  le controle detecte reellement une action orpheline")

    # ── Chaque capacite est complete ────────────────────────────────────
    for cle, c in cat.CAPACITES.items():
        for champ in ("titre", "description", "actions", "niveau"):
            assert c.get(champ) or champ == "actions", \
                "%s : champ %s manquant" % (cle, champ)
        assert 1 <= c["niveau"] <= 10, "%s : niveau hors echelle" % cle
        assert len(c["description"]) > 20, \
            "%s : description trop courte pour le mode simple" % cle
        # Le mode simple affiche ces textes tels quels.
        for mot in ("API", "token", "WebSocket", "handler", "endpoint"):
            assert mot not in c["description"], \
                "%s : « %s » est du jargon, le mode simple lit ce texte" % (cle, mot)
    print("  OK  %d capacites, toutes decrites sans jargon" % len(cat.CAPACITES))

    # Une action ne doit appartenir qu'a UNE capacite : sinon la decocher
    # d'un cote la laisserait active de l'autre.
    vues = {}
    for cle, c in cat.CAPACITES.items():
        for a in c["actions"]:
            assert a not in vues, \
                "%s appartient a la fois a %s et %s" % (a, vues[a], cle)
            vues[a] = cle
    print("  OK  aucune action partagee entre deux capacites")

    # ── Mode simple : les capacites avancees sont ABSENTES ──────────────
    simple = {c["cle"] for c in cat.catalogue("simple")}
    avance = {c["cle"] for c in cat.catalogue("avance")}
    reservees = {c for c, v in cat.CAPACITES.items() if v.get("avance")}
    assert reservees, "aucune capacite n'est reservee au mode avance"
    assert not (simple & reservees), \
        "le mode simple expose %s" % (simple & reservees)
    assert reservees <= avance, "le mode avance n'expose pas tout"
    print("  OK  %d capacite(s) reservee(s) absente(s) du mode simple : %s"
          % (len(reservees), ", ".join(sorted(reservees))))

    # ── L'interdiction ne tient pas qu'a l'affichage ────────────────────
    # Sauvegarder le vrai choix : ce test ecrit dans le fichier reel.
    chemin = str(cat._chemin_choix())
    secours = chemin + ".test-bak"
    existait = os.path.exists(chemin)
    if existait:
        shutil.copy(chemin, secours)
    try:
        retenues, refusees = cat.definir_activees(["agents", "courrier"], mode="simple")
        assert "agents" not in retenues, \
            "une capacite avancee a ete activee en mode simple"
        assert any("agents" in r for r in refusees), "le refus n'est pas explique"
        assert "courrier" in retenues, "une capacite normale a ete refusee a tort"
        print("  OK  mode simple : l'activation d'une capacite avancee est refusee")

        # Les obligatoires reviennent toujours.
        retenues, _ = cat.definir_activees([], mode="avance")
        obligatoires = {c for c, v in cat.CAPACITES.items() if v.get("obligatoire")}
        assert obligatoires <= set(retenues), \
            "une capacite obligatoire a pu etre retiree : %s" % obligatoires
        print("  OK  les capacites obligatoires ne peuvent pas etre retirees")

        # Decocher doit rendre INOPERANT, pas seulement invisible.
        cat.definir_activees(["essentiel"], mode="avance")
        assert not cat.action_autorisee("vpn_connect"), \
            "une action d'une capacite decochee reste autorisee"
        assert cat.action_autorisee("user_input"), \
            "une action essentielle est bloquee"
        cat.definir_activees(["essentiel", "vpn"], mode="avance")
        assert cat.action_autorisee("vpn_connect"), \
            "reactiver la capacite ne debloque pas son action"
        print("  OK  decocher une capacite rend ses actions inoperantes")
    finally:
        if existait:
            shutil.move(secours, chemin)
        elif os.path.exists(chemin):
            os.remove(chemin)

    # ── Disponibilite : une raison, pas un silence ──────────────────────
    for c in cat.catalogue():
        if not c["disponible"]:
            assert c["manques"], "%s indisponible sans raison" % c["cle"]
    indispo = [c for c in cat.catalogue() if not c["disponible"]]
    print("  OK  %d capacite(s) indisponible(s), toutes avec leur raison"
          % len(indispo))
    for c in indispo:
        print("      %-30s %s" % (c["titre"], c["manques"][0]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Catalogue : conforme.")
