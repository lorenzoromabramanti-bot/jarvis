# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Résolution d'un nom parlé vers une entité Home Assistant
======================================================================
« Allume le climatiseur de Lorenzo » -> `climate.lorenzo`.

POURQUOI REMPLACER LES TABLES CODÉES EN DUR
`ha_config.py` déclare 64 entités dans six dictionnaires. **Les 64 sont
absentes** de l'installation réelle : elles décrivent une maison qui n'existe
plus. Home Assistant, lui, connaît le nom de chacun de ses appareils —
« Climatiseur Lorenzo », « TV Salon SAMSUNG 75 », « Porte de garage ». Ce sont
déjà les mots qu'on emploie à voix haute.

Une table écrite à la main redevient fausse dès qu'un appareil est renommé,
remplacé ou ajouté. Lire les noms de HA, non. Les tables restent utilisables
comme surcouche (`ha_config` gagne s'il pointe sur une entité qui existe),
mais elles ne sont plus la source de vérité.

NE JAMAIS DEVINER
Se tromper d'appareil est pire que ne rien faire : personne ne veut ouvrir le
portail en demandant la porte de garage. Quand deux candidats sont proches, on
renvoie une ambiguïté et l'appelant demande — il ne choisit pas à la place de
l'utilisateur.

    venv\\Scripts\\python.exe ha_resolution.py "climatiseur de lorenzo"
"""

import re
import sys
import time
import unicodedata

import requests

try:
    from ha_config import HA_URL, HA_TOKEN
except Exception:                                    # pragma: no cover
    HA_URL = HA_TOKEN = ""

# Les états changent souvent, les NOMS quasiment jamais : 60 s de cache
# suffisent à éviter un aller-retour par phrase prononcée.
_CACHE = {"t": 0.0, "entites": []}
DUREE_CACHE = 60.0

# Mots vides du langage parlé. Les garder ferait gagner « la » ou « de »
# contre le vrai nom de l'appareil.
_VIDES = {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "au",
          "aux", "a", "the", "dans", "sur", "et", "en", "mon", "ma", "mes",
          "allume", "allumer", "eteins", "eteindre", "ferme", "fermer",
          "ouvre", "ouvrir", "mets", "mettre", "lance", "lancer", "coupe",
          "arrete", "arreter", "demarre", "monte", "baisse", "stp", "jarvis"}

DOMAINES_PILOTABLES = ("light", "switch", "climate", "media_player", "cover",
                       "vacuum", "fan", "lock", "scene")

# Le mot qui désigne la NATURE de l'appareil restreint la recherche, puis
# disparaît du calcul de score.
#
# Sans ça, « la lumière du salon » proposait une télévision : « salon »
# correspondait au téléviseur du salon tandis que « lumière » ne
# correspondait à rien. Et « la lumière de la terrasse » échouait, faute
# d'un seul mot utile sur deux. Le nom de la nature n'est pas un critère de
# ressemblance, c'est un filtre.
NATURES = {
    "light":        ("lumiere", "lumieres", "lampe", "lampes", "eclairage",
                     "plafonnier", "led", "leds", "spot", "spots"),
    "switch":       ("prise", "prises", "interrupteur", "interrupteurs"),
    "climate":      ("clim", "climatiseur", "climatisation", "chauffage",
                     "thermostat", "radiateur"),
    "media_player": ("tele", "television", "tv", "ampli", "enceinte",
                     "enceintes", "musique", "lecteur"),
    "cover":        ("volet", "volets", "store", "stores", "portail",
                     "garage", "rideau", "rideaux"),
    "vacuum":       ("aspirateur", "robot"),
    "lock":         ("serrure", "verrou"),
    "fan":          ("ventilateur", "ventilo"),
}


# Familles de synonymes DANS un domaine. Le filtre par domaine ne suffit pas
# a departager : « la tele du salon » et « l'ampli du salon » sont tous deux
# des media_player, mais seul l'un s'appelle « TV Salon ». Sans ces familles,
# dire « tele » ne privilegiait pas le televiseur, parce que l'appareil
# s'appelle « TV » et pas « tele ».
FAMILLES = (
    ("tele", "television", "tv"),
    ("ampli", "amplificateur"),
    ("enceinte", "enceintes", "haut-parleur"),
    ("lumiere", "lumieres", "lampe", "lampes", "eclairage", "led", "leds"),
    ("clim", "climatiseur", "climatisation"),
    ("volet", "volets", "store", "stores"),
)


def _synonymes(mot):
    for f in FAMILLES:
        if mot in f:
            return f
    return (mot,)


def _nature(mots):
    """(domaine, mots restants) — ou (None, mots) si aucune nature nommée."""
    for domaine, indices in NATURES.items():
        presents = [m for m in mots if m in indices]
        if presents:
            # « portail » et « garage » nomment la nature ET l'appareil :
            # les retirer ne laisserait rien à chercher.
            restants = [m for m in mots if m not in presents]
            return domaine, (restants or mots)
    return None, mots


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


def _mots(texte):
    """Mots significatifs, sans accents ni ponctuation, sans mots vides."""
    t = _sans_accents(str(texte or "").lower())
    bruts = [m for m in re.split(r"[^a-z0-9]+", t) if m]
    utiles = [m for m in bruts if m not in _VIDES and len(m) > 1]
    # Si tout a été filtré, garder les mots bruts : mieux vaut chercher avec
    # « la » que ne rien chercher du tout.
    return utiles or bruts


def entites(forcer=False):
    """Entités pilotables de HA, avec cache court."""
    if not forcer and _CACHE["entites"] and time.time() - _CACHE["t"] < DUREE_CACHE:
        return _CACHE["entites"]
    r = requests.get("%s/api/states" % HA_URL.rstrip("/"),
                     headers={"Authorization": "Bearer %s" % HA_TOKEN}, timeout=15)
    r.raise_for_status()
    liste = []
    for e in r.json():
        eid = e.get("entity_id", "")
        if eid.split(".")[0] not in DOMAINES_PILOTABLES:
            continue
        nom = (e.get("attributes") or {}).get("friendly_name") or eid.split(".", 1)[-1]
        liste.append({
            "entity_id": eid,
            "domaine": eid.split(".")[0],
            "nom": nom,
            "etat": e.get("state"),
            "disponible": e.get("state") not in ("unavailable", "unknown"),
            "_mots": set(_mots(nom)) | set(_mots(eid.split(".", 1)[-1])),
        })
    _CACHE.update({"t": time.time(), "entites": liste})
    return liste


def _score(demandes, candidat, natures=()):
    """
    Score de 0 à 1. Chaque mot demandé qui figure dans le nom compte ; un
    préfixe compte moitié moins (« clim » pour « climatiseur »).

    `natures` sert de départage, pas de critère : « la télé du salon » et
    « l'ampli du salon » ont le même score sur « salon », mais seul le
    téléviseur s'appelle « TV Salon ». Un petit bonus suffit à trancher, sans
    permettre à la nature seule de faire gagner un appareil.
    """
    if not demandes:
        return 0.0
    total = 0.0
    for d in demandes:
        if d in candidat["_mots"]:
            total += 1.0
        elif any(m.startswith(d) or d.startswith(m) for m in candidat["_mots"]):
            total += 0.5
    base = total / len(demandes)
    if natures:
        proches = {s for n in natures for s in _synonymes(n)}
        if proches & candidat["_mots"]:
            # PAS de plafond a 1.0 ici : « la tele du salon » et « l'ampli du
            # salon » atteignent tous deux 1.0 sur le mot « salon », et un
            # bonus ecrete ne departage plus rien. C'est un classement, pas
            # une note sur vingt.
            base += 0.25
    # Un appareil hors ligne reste proposable, mais après un équivalent
    # disponible : l'utilisateur préfère celui qui répondra.
    return base if candidat["disponible"] else base * 0.6


def resoudre(phrase, domaine=None, seuil=0.5, ecart_ambigu=0.15):
    """
    Trouve l'entité désignée par une phrase.

    Renvoie {trouve, entite, score, ambigu, candidats, raison}.

    `ambigu` est vrai quand le deuxième candidat est presque aussi bon : dans
    ce cas l'appelant DOIT demander, jamais trancher seul. Allumer la mauvaise
    pièce est plus embêtant que poser une question.
    """
    demandes = _mots(phrase)
    # La nature citée ("lumière", "clim"...) restreint AVANT de comparer.
    devine, demandes = _nature(demandes)
    natures_citees = [m for m in _mots(phrase) if m not in demandes]
    domaine = domaine or devine
    try:
        pool = entites()
    except Exception as e:
        return {"trouve": False, "raison": "Home Assistant injoignable : %r" % (e,),
                "candidats": []}
    if domaine:
        pool = [c for c in pool if c["domaine"] == domaine]
    if not pool:
        return {"trouve": False,
                "raison": "aucun appareil de type %r dans Home Assistant" % domaine,
                "candidats": []}

    notes = sorted(((_score(demandes, c, natures_citees), c) for c in pool),
                   key=lambda x: -x[0])
    meilleur, entite = notes[0]
    second = notes[1][0] if len(notes) > 1 else 0.0

    if meilleur < seuil:
        return {
            "trouve": False,
            "raison": "aucune correspondance sûre pour %r" % phrase,
            "score": round(meilleur, 2),
            "candidats": [{"nom": c["nom"], "entity_id": c["entity_id"],
                           "score": round(s, 2)} for s, c in notes[:5] if s > 0],
        }
    # Doublons de Home Assistant. L'installation contient le meme appareil
    # enregistre plusieurs fois : « TV Salon SAMSUNG 75 » existe en deux
    # entites dont les identifiants ne different que par un suffixe _2. Ce
    # n'est pas une ambiguite : c'est le meme televiseur. On garde celui qui
    # repond, et a defaut l'identifiant le plus court (l'original).
    proches = [c for s_, c in notes if meilleur - s_ < ecart_ambigu]
    if len(proches) > 1 and len({c["nom"] for c in proches}) == 1:
        entite = sorted(proches, key=lambda c: (not c["disponible"],
                                                len(c["entity_id"])))[0]
        return {
            "trouve": True, "ambigu": False, "doublons": len(proches),
            "entite": {k: v for k, v in entite.items() if k != "_mots"},
            "score": round(meilleur, 2),
            "candidats": [{"nom": c["nom"], "entity_id": c["entity_id"]}
                          for c in proches if c is not entite],
        }

    if meilleur - second < ecart_ambigu:
        return {
            "trouve": False, "ambigu": True,
            "raison": "plusieurs appareils correspondent autant",
            "candidats": [{"nom": c["nom"], "entity_id": c["entity_id"],
                           "score": round(s, 2)}
                          for s, c in notes if meilleur - s < ecart_ambigu],
        }
    return {
        "trouve": True, "ambigu": False,
        "entite": {k: v for k, v in entite.items() if k != "_mots"},
        "score": round(meilleur, 2),
        "candidats": [{"nom": c["nom"], "entity_id": c["entity_id"],
                       "score": round(s, 2)} for s, c in notes[1:4] if s > 0],
    }


def couverture():
    """
    Compare les tables de ha_config à ce que HA possède vraiment.

    Sert à répondre « peut-on jeter les tables ? » avec des chiffres plutôt
    qu'une impression.
    """
    import ha_config as hc
    reels = {c["entity_id"] for c in entites()}
    tables, valides, mortes = 0, 0, []
    for nom_table, table in vars(hc).items():
        if not (nom_table.isupper() and isinstance(table, dict)):
            continue
        for cle, val in table.items():
            if isinstance(val, str) and "." in val:
                tables += 1
                if val in reels:
                    valides += 1
                else:
                    mortes.append((nom_table, cle, val))
    resolus = sum(1 for _, cle, _ in mortes if resoudre(cle).get("trouve"))
    return {"declarees": tables, "encore_valides": valides,
            "mortes": len(mortes), "rattrapees_par_resolution": resolus}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1:
        r = resoudre(" ".join(sys.argv[1:]))
        print()
        if r.get("trouve"):
            e = r["entite"]
            print("  TROUVE  %s  ->  %s  (score %.2f, etat %s)"
                  % (e["nom"], e["entity_id"], r["score"], e["etat"]))
        else:
            print("  NON RESOLU : %s" % r["raison"])
        for c in r.get("candidats", [])[:5]:
            print("     candidat  %-40s %-40s %.2f" % (c["nom"][:40], c["entity_id"][:40], c["score"]))
        sys.exit(0)

    print()
    print("=" * 78)
    print("RESOLUTION HOME ASSISTANT — essais sur des phrases reelles")
    print("=" * 78)
    for phrase in ("le climatiseur de lorenzo", "clim eva", "la tele du salon",
                   "ampli salon", "ouvre le portail", "la porte de garage",
                   "les jets du spa", "la lumiere de la terrasse",
                   "la lumiere du salon", "allume tout"):
        r = resoudre(phrase)
        if r.get("trouve"):
            print("  %-30s -> %-42s %.2f" % (phrase, r["entite"]["entity_id"], r["score"]))
        else:
            marque = "AMBIGU" if r.get("ambigu") else "non resolu"
            noms = ", ".join(c["entity_id"] for c in r.get("candidats", [])[:3])
            print("  %-30s -> %-12s %s" % (phrase, marque, noms or r["raison"][:44]))
    print()
    c = couverture()
    print("  TABLES ha_config : %d declarees, %d encore valides, %d mortes"
          % (c["declarees"], c["encore_valides"], c["mortes"]))
    print("  dont %d rattrapees par la resolution automatique"
          % c["rattrapees_par_resolution"])
    print("=" * 78)
