# -*- coding: utf-8 -*-
"""
Verifie la regle d'intrusion sur des etats fabriques.

Les capteurs reels sont tous hors ligne : impossible de valider la regle sur
l'installation. On la valide donc sur des etats synthetiques, pour qu'elle
soit juste le jour ou les capteurs reviennent.

Les pieges couverts sont ceux qui font crier au loup :
  - une personne 'unknown' n'est pas une personne absente
  - un capteur 'unavailable' n'est pas un capteur ferme
  - ouvrir le frigo n'est pas entrer par effraction

    venv\\Scripts\\python.exe _test_surveillance.py
"""

import sys

import surveillance


def capteur(eid, cls, etat, nom=None):
    return {"entity_id": "binary_sensor." + eid,
            "state": etat,
            "attributes": {"device_class": cls, "friendly_name": nom or eid}}


def personne(eid, etat):
    return {"entity_id": "person." + eid, "state": etat,
            "attributes": {"friendly_name": eid}}


def verifier():
    # 1. Ouverture + maison vide = intrusion
    e = surveillance.etat([capteur("porte", "door", "on"),
                           personne("lorenzo", "not_home")])
    assert e["intrusion"], "ouverture maison vide non detectee"

    # 2. Ouverture mais quelqu'un est la = pas d'intrusion
    e = surveillance.etat([capteur("porte", "door", "on"),
                           personne("lorenzo", "home")])
    assert not e["intrusion"], "fausse alerte alors que quelqu'un est present"

    # 3. Une seule personne presente suffit a annuler l'alerte
    e = surveillance.etat([capteur("porte", "door", "on"),
                           personne("lorenzo", "not_home"),
                           personne("sylvie", "home")])
    assert not e["intrusion"], "fausse alerte : une personne est bien la"

    # 4. 'unknown' n'est pas 'absent'. Conclure l'inverse ferait sonner
    #    l'alarme des qu'un telephone perd le reseau.
    e = surveillance.etat([capteur("porte", "door", "on"),
                           personne("eva", "unknown")])
    assert not e["maison_vide"], "'unknown' traite comme une absence"
    assert not e["intrusion"], "fausse alerte sur une presence indeterminee"

    # 5. Un capteur hors ligne n'est pas un capteur ferme : il doit apparaitre
    #    en angle mort, jamais etre compte comme rassurant.
    e = surveillance.etat([capteur("porte", "door", "unavailable"),
                           personne("lorenzo", "not_home")])
    assert len(e["aveugles"]) == 1, "capteur hors ligne absent des angles morts"
    assert not e["intrusion"], "intrusion deduite d'un capteur muet"
    assert e["fiabilite"] == 0.0, "fiabilite %r au lieu de 0" % e["fiabilite"]

    # 6. Le frigo n'est pas une porte d'entree
    e = surveillance.etat([capteur("frigo_fridge_door", "door", "on"),
                           personne("lorenzo", "not_home")])
    assert not e["capteurs"], "le frigo est compte comme une ouverture"
    assert not e["intrusion"], "alerte declenchee par le frigo"

    # 7. Fiabilite partielle correctement calculee
    e = surveillance.etat([capteur("a", "door", "off"),
                           capteur("b", "window", "unavailable"),
                           personne("lorenzo", "home")])
    assert e["fiabilite"] == 0.5, "fiabilite %r au lieu de 0.5" % e["fiabilite"]

    # 8. Aucune personne connue : on ne conclut pas a une maison vide
    e = surveillance.etat([capteur("porte", "door", "on")])
    assert not e["maison_vide"], "maison declaree vide sans aucune personne connue"

    print("  OK  ouverture + maison vide -> intrusion")
    print("  OK  presence -> pas d'alerte (meme partielle)")
    print("  OK  'unknown' n'est pas une absence")
    print("  OK  capteur hors ligne -> angle mort, jamais rassurant")
    print("  OK  le frigo n'est pas une effraction")
    print("  OK  fiabilite calculee juste")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Regle d'intrusion : correcte sur les 8 cas.")
