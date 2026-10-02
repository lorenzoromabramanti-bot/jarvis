# -*- coding: utf-8 -*-
"""
Verifie la resolution des noms d'appareils, sur un parc fabrique.

Ce qui compte ici n'est pas le taux de reussite : c'est que le resolveur
REFUSE de deviner. Allumer la mauvaise piece, ou ouvrir le portail quand on
demande la porte de garage, est pire que de poser une question.

    venv\\Scripts\\python.exe _test_ha_resolution.py
"""

import sys

import ha_resolution as hr


def parc(*entrees):
    """Installe un faux parc dans le cache, sans toucher a Home Assistant."""
    liste = []
    for eid, nom, dispo in entrees:
        liste.append({
            "entity_id": eid, "domaine": eid.split(".")[0], "nom": nom,
            "etat": "on" if dispo else "unavailable", "disponible": dispo,
            "_mots": set(hr._mots(nom)) | set(hr._mots(eid.split(".", 1)[-1])),
        })
    hr._CACHE.update({"t": 9e18, "entites": liste})   # jamais perime


def verifier():
    # ── Le mot de nature filtre le domaine ──────────────────────────────
    parc(("light.terrasse", "Terrasse BAR", True),
         ("media_player.tv_salon", "TV Salon SAMSUNG", True))
    r = hr.resoudre("la lumiere de la terrasse")
    assert r["trouve"] and r["entite"]["entity_id"] == "light.terrasse", r

    # « lumiere du salon » ne doit PAS proposer la television du salon,
    # meme si « salon » correspond parfaitement.
    r = hr.resoudre("la lumiere du salon")
    assert not r["trouve"], "une television proposee pour une lumiere : %r" % r

    # ── Synonymes : on dit « tele », l'appareil s'appelle « TV » ─────────
    parc(("media_player.tv_salon", "TV Salon", True),
         ("media_player.ampli_salon", "Ampli Salon", True))
    r = hr.resoudre("la tele du salon")
    assert r["trouve"] and r["entite"]["entity_id"] == "media_player.tv_salon", r

    # ── Ambiguite reelle : deux appareils DIFFERENTS, on demande ────────
    parc(("climate.chambre_a", "Climatiseur Chambre", True),
         ("climate.chambre_b", "Chauffage Chambre", True))
    r = hr.resoudre("la chambre")
    assert not r["trouve"] and r.get("ambigu"), "a tranche seul entre deux appareils : %r" % r
    assert len(r["candidats"]) >= 2

    # ── Doublons HA : meme NOM, ce n'est pas une ambiguite ──────────────
    parc(("media_player.tv_salon", "TV Salon", True),
         ("media_player.tv_salon_2", "TV Salon", True))
    r = hr.resoudre("tele salon")
    assert r["trouve"], "des doublons traites comme une ambiguite : %r" % r
    assert r["entite"]["entity_id"] == "media_player.tv_salon", \
        "doublon : l'identifiant le plus court doit gagner (%r)" % r["entite"]

    # Doublon dont l'original est hors ligne : prendre celui qui repond.
    parc(("media_player.tv_salon", "TV Salon", False),
         ("media_player.tv_salon_2", "TV Salon", True))
    r = hr.resoudre("tele salon")
    assert r["trouve"] and r["entite"]["entity_id"] == "media_player.tv_salon_2", \
        "doublon : le disponible doit gagner (%r)" % r.get("entite")

    # ── Rien de correspondant : dire non, pas proposer au hasard ────────
    parc(("light.cuisine", "Lumiere Cuisine", True))
    r = hr.resoudre("le tracteur de la grange")
    assert not r["trouve"], "a invente une correspondance : %r" % r

    # ── Domaine absent : le dire, sans se rabattre ailleurs ─────────────
    parc(("light.cuisine", "Lumiere Cuisine", True))
    r = hr.resoudre("le volet du salon")
    assert not r["trouve"] and "volet" not in str(r.get("entite", "")), r

    # ── Un appareil hors ligne perd contre un equivalent disponible ─────
    parc(("light.salon_vieux", "Lumiere Salon", False),
         ("light.salon_neuf", "Lumiere Salon Neuf", True))
    r = hr.resoudre("lumiere salon")
    assert r["trouve"] and r["entite"]["disponible"], \
        "a choisi un appareil hors ligne : %r" % r.get("entite")

    print("  OK  le mot de nature filtre le domaine")
    print("  OK  une lumiere n'est jamais une television")
    print("  OK  « tele » trouve un appareil nomme « TV »")
    print("  OK  deux appareils differents -> on demande, on ne tranche pas")
    print("  OK  doublons HA -> un seul appareil, le disponible d'abord")
    print("  OK  aucune correspondance -> refus, pas d'invention")
    print("  OK  hors ligne perd contre disponible")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Resolution : ne devine jamais.")
