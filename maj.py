# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Vérification des mises à jour
===========================================
Au lancement, JARVIS demande à GitHub s'il existe une version plus récente.

CE MODULE NE MET RIEN À JOUR. Il regarde et il rapporte.

Pourquoi cette séparation : remplacer le code d'un programme pendant qu'il
tourne est une action irréversible, faite sur la machine de quelqu'un
d'autre. Elle demande un accord explicite, comme l'envoi d'un e-mail. Ce
fichier fournit la moitié qu'on peut faire sans rien demander.

CE QUI NE DOIT JAMAIS ARRIVER
Un échec de vérification ne doit pas retarder ni empêcher le démarrage. Pas
de réseau, GitHub en panne, dépôt privé, quota dépassé : dans tous ces cas on
renvoie une raison lisible et JARVIS démarre normalement. C'est pour ça que
le délai est court et que rien n'est réessayé en boucle.

COMPARAISON DES VERSIONS
Numérique, composant par composant. Comparer « 1.10.0 » et « 1.9.0 » comme du
texte donnerait 1.10.0 < 1.9.0 — l'erreur classique, qui bloque les mises à
jour pile au moment où le projet dépasse la version 9.

    venv\\Scripts\\python.exe maj.py
"""

import json
import os
import re
import urllib.error
import urllib.request

from config import VERSION

# Dépôt public interrogé. Modifiable sans toucher au code : une installation
# peut suivre un fork, et les essais ne doivent pas viser le vrai dépôt.
DEPOT = os.getenv("JARVIS_DEPOT", "").strip()

DELAI = 6            # secondes. Court : on démarre, on ne négocie pas.
UA = "JARVIS/%s (verification de mise a jour)" % VERSION


def _numeros(version):
    """« v1.10.2-beta » -> (1, 10, 2). Ce qui n'est pas un nombre est ignoré."""
    trouves = re.findall(r"\d+", str(version or ""))
    return tuple(int(x) for x in trouves[:3]) or (0,)


def comparer(locale, distante):
    """
    -1 si la locale est plus ancienne, 0 si égales, 1 si la locale est devant.

    Comparaison NUMÉRIQUE. En texte, « 1.10.0 » passe avant « 1.9.0 » et la
    mise à jour ne serait jamais proposée à partir de la version 10.
    """
    a, b = _numeros(locale), _numeros(distante)
    taille = max(len(a), len(b))
    a += (0,) * (taille - len(a))
    b += (0,) * (taille - len(b))
    return (a > b) - (a < b)


def verifier(depot=None, delai=DELAI):
    """
    Interroge GitHub. Renvoie un dictionnaire, jamais une exception.

        {"ok": True,  "a_jour": bool, "locale": str, "distante": str,
         "url": str, "notes": str, "publiee": str}
        {"ok": False, "raison": str}
    """
    depot = (depot or DEPOT).strip()
    if not depot:
        return {"ok": False, "raison": "aucun dépôt configuré (JARVIS_DEPOT)"}

    url = "https://api.github.com/repos/%s/releases/latest" % depot
    requete = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(requete, timeout=delai) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False,
                    "raison": "dépôt ou publication introuvable (%s)" % depot}
        if e.code == 403:
            return {"ok": False,
                    "raison": "GitHub limite les requêtes ; réessayer plus tard"}
        return {"ok": False, "raison": "GitHub a répondu %s" % e.code}
    except urllib.error.URLError as e:
        return {"ok": False, "raison": "réseau indisponible (%s)" % (e.reason,)}
    except Exception as e:
        return {"ok": False, "raison": "%s" % type(e).__name__}

    distante = (donnees.get("tag_name") or donnees.get("name") or "").strip()
    if not distante:
        return {"ok": False, "raison": "la publication ne porte pas de version"}

    return {
        "ok": True,
        "a_jour": comparer(VERSION, distante) >= 0,
        "locale": VERSION,
        "distante": distante.lstrip("vV"),
        "url": donnees.get("html_url") or "",
        "notes": (donnees.get("body") or "").strip()[:600],
        "publiee": (donnees.get("published_at") or "")[:10],
    }


def phrase(resultat=None):
    """Une phrase à dire ou à afficher. Vide si rien ne mérite d'être dit."""
    r = resultat if resultat is not None else verifier()
    if not r.get("ok"):
        # Ne pas déranger pour un problème de réseau : la vérification est un
        # confort, pas une fonction attendue. Le journal en garde trace.
        print("[MAJ] verification impossible : %s" % r.get("raison"))
        return ""
    if r["a_jour"]:
        return ""
    return ("Une version %s est disponible ; vous utilisez la %s."
            % (r["distante"], r["locale"]))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print()
    print("=" * 70)
    print("VERIFICATION DE MISE A JOUR")
    print("=" * 70)
    print("  version locale : %s" % VERSION)
    print("  depot          : %s" % (DEPOT or "(non configure)"))
    r = verifier()
    for cle, valeur in r.items():
        print("  %-14s %s" % (cle, str(valeur)[:70]))
    p = phrase(r)
    print("  a annoncer     : %s" % (p or "(rien)"))
    print("=" * 70)
