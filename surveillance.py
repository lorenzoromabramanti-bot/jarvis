# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Surveillance d'intrusion
======================================
Détecte une ouverture pendant que personne n'est là, à partir de Home
Assistant. Et surtout : dit la vérité sur ce qu'il peut voir.

POURQUOI CE MODULE COMMENCE PAR SES ANGLES MORTS
Au moment de l'écrire, 6 des 8 capteurs d'ouverture de l'installation
étaient `unavailable` : porte d'entrée, porte de sous-sol et quatre
fenêtres. Une alarme bâtie là-dessus aurait affiché « RAS » en permanence,
y compris porte grande ouverte. Un détecteur qui ignore sa propre cécité
est pire qu'aucun détecteur : il rassure à tort.

`etat()` renvoie donc toujours DEUX choses : ce qui est surveillé, et ce qui
ne l'est pas.

LE JOURNAL SÉCURITÉ DE WINDOWS N'EST PAS UTILISÉ
Les échecs de connexion (event 4625) exigent des droits administrateur, que
JARVIS n'a pas. Plutôt que de lancer un scan qui échouerait en silence, on
s'appuie sur ce qui est réellement lisible : Home Assistant.

    venv\\Scripts\\python.exe surveillance.py
"""

import os
import sys
import time

import requests

# Réutilise la configuration Home Assistant déjà en place, pas une seconde.
try:
    from ha_config import HA_URL, HA_TOKEN
except Exception:                                   # pragma: no cover
    HA_URL = os.getenv("HA_URL", "")
    HA_TOKEN = os.getenv("HA_TOKEN", "")

# Ce qui compte comme une ouverture surveillée.
CLASSES_OUVERTURE = ("door", "window", "opening", "garage_door")
CLASSES_PRESENCE = ("motion", "occupancy")

# Portes d'électroménager : elles portent device_class "door" mais ouvrir le
# frigo n'est pas une intrusion.
EXCLUS = ("frigo", "fridge", "freezer", "congelateur", "lave_", "four", "oven")


def _etats():
    """Tous les états HA. Lève si HA est injoignable — l'appelant décide."""
    r = requests.get("%s/api/states" % HA_URL.rstrip("/"),
                     headers={"Authorization": "Bearer %s" % HA_TOKEN},
                     timeout=15)
    r.raise_for_status()
    return r.json()


def _pertinent(e):
    eid = e.get("entity_id", "")
    if not eid.startswith("binary_sensor."):
        return None
    if any(x in eid for x in EXCLUS):
        return None
    cls = (e.get("attributes") or {}).get("device_class", "")
    if cls in CLASSES_OUVERTURE:
        return "ouverture"
    if cls in CLASSES_PRESENCE:
        return "presence"
    return None


def etat(etats=None):
    """
    Photographie de la surveillance.

    Renvoie :
        capteurs      [{entity_id, nom, genre, etat, disponible}]
        aveugles      les capteurs indisponibles — la partie qu'on ne voit PAS
        personnes     [{entity_id, nom, etat}]
        maison_vide   True si AUCUNE personne n'est 'home'
        ouvertures    capteurs ouverts A CET INSTANT (disponibles seulement)
        intrusion     True si une ouverture est detectee maison vide
        fiabilite     part des capteurs disponibles, 0 a 1
    """
    if etats is None:
        etats = _etats()

    capteurs, personnes = [], []
    for e in etats:
        genre = _pertinent(e)
        if genre:
            attrs = e.get("attributes") or {}
            capteurs.append({
                "entity_id": e["entity_id"],
                "nom": attrs.get("friendly_name") or e["entity_id"],
                "genre": genre,
                "etat": e.get("state"),
                "disponible": e.get("state") not in ("unavailable", "unknown", None),
            })
        elif e.get("entity_id", "").startswith("person."):
            personnes.append({
                "entity_id": e["entity_id"],
                "nom": (e.get("attributes") or {}).get("friendly_name") or e["entity_id"],
                "etat": e.get("state"),
            })

    aveugles = [c for c in capteurs if not c["disponible"]]
    ouvertures = [c for c in capteurs
                  if c["disponible"] and c["etat"] == "on"]
    # 'unknown' n'est pas une absence : ne pas conclure "maison vide" sur un
    # etat indetermine, ce serait la meilleure facon de crier au loup.
    connus = [p for p in personnes if p["etat"] in ("home", "not_home")]
    maison_vide = bool(connus) and all(p["etat"] != "home" for p in connus)

    return {
        "capteurs": capteurs,
        "aveugles": aveugles,
        "personnes": personnes,
        "maison_vide": maison_vide,
        "ouvertures": ouvertures,
        "intrusion": bool(maison_vide and ouvertures),
        "fiabilite": (round((len(capteurs) - len(aveugles)) / len(capteurs), 2)
                      if capteurs else 0.0),
        "horodatage": int(time.time()),
    }


def resume(e=None):
    """Une phrase, pour la voix ou une pastille."""
    e = e or etat()
    if e["intrusion"]:
        return "ALERTE : %s ouvert alors que personne n'est là." % \
               ", ".join(c["nom"] for c in e["ouvertures"])
    if e["aveugles"]:
        return ("Rien à signaler, mais %d capteur(s) sur %d sont hors ligne : "
                "la surveillance est partielle."
                % (len(e["aveugles"]), len(e["capteurs"])))
    return "Tous les capteurs répondent, aucune ouverture."


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        e = etat()
    except Exception as exc:
        print("  Home Assistant injoignable : %r" % (exc,))
        sys.exit(1)

    print()
    print("=" * 72)
    print("SURVEILLANCE — fiabilité %.0f%%" % (e["fiabilite"] * 100))
    print("=" * 72)
    print("  %s" % resume(e))
    print()
    print("  SURVEILLÉ (%d) :" % (len(e["capteurs"]) - len(e["aveugles"])))
    for c in e["capteurs"]:
        if c["disponible"]:
            print("    %-46s %-10s %s" % (c["nom"][:46], c["genre"], c["etat"]))
    if e["aveugles"]:
        print()
        print("  ANGLE MORT (%d) — ces ouvertures ne sont PAS surveillées :" % len(e["aveugles"]))
        for c in e["aveugles"]:
            print("    %-46s %-10s %s" % (c["nom"][:46], c["genre"], c["etat"]))
    print()
    print("  PRÉSENCE :")
    for p in e["personnes"]:
        print("    %-46s %s" % (p["nom"][:46], p["etat"]))
    print("    maison vide : %s" % e["maison_vide"])
    print("=" * 72)
