# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Journal de confiance par type d'action (autonomie méritée)
===========================================================================
Idée reprise de la roadmap Trillion (« Earned Autonomy », proposée par
Thanasis L.) : la confiance se gagne action par action, sur preuve, pas
d'un coup pour tout l'agent. Ce module fait UNE chose : compter combien de
fois chaque type d'action a été approuvé ou refusé, et donner une lecture
de maturité pour AIDER une décision humaine.

CE QUE CE MODULE NE FAIT JAMAIS
Il ne désactive aucun garde-fou et n'autorise rien tout seul.
`garde_fous.desactiver()` reste le seul chemin, avec sa phrase exacte à
retaper. Un historique d'approbations n'est pas un consentement permanent
— le Tier 6 du cahier des charges est explicite : chaque action
conséquente redemande, rien ici ne doit devenir un contournement déguisé.
`maturite()` PROPOSE de reconsidérer manuellement un garde-fou ; il ne le
fait, ni ne le suggère à voix haute, jamais lui-même.

PAS ENCORE BRANCHÉ NULLE PART
Comme cout_suivi.py : le point d'appel naturel est dans main2.py, là où
une confirmation est demandée et sa réponse connue — zone du fichier non
validée (git diff) au moment d'écrire ce module. `enregistrer()` est prêt
à recevoir cet appel dès que main2.py sera stabilisé.

    venv\\Scripts\\python.exe confiance.py
"""

import io
import json
import os
import time

import config

FICHIER = "confiance.json"


def _chemin():
    return config.chemin_donnees(FICHIER, creer_dossier=True)


def _lire_tout():
    try:
        with io.open(str(_chemin()), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"decisions": []}


def _ecrire_tout(donnees):
    chemin = str(_chemin())
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(donnees, ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)


def enregistrer(type_action, approuve, detail=""):
    """
    Journalise une décision humaine sur un type d'action.
    `approuve` : True (a confirmé), False (a refusé/annulé).
    """
    donnees = _lire_tout()
    donnees.setdefault("decisions", []).append({
        "horodatage": time.time(),
        "type_action": str(type_action),
        "approuve": bool(approuve),
        "detail": detail,
    })
    _ecrire_tout(donnees)


def historique(type_action, limite=10_000):
    tout = _lire_tout().get("decisions", [])
    filtres = [d for d in tout if d["type_action"] == type_action]
    return filtres[-limite:]


def maturite(type_action, seuil_appels=10, seuil_taux=0.9):
    """
    Lecture qualitative, PAS une autorisation.

    `constant` n'est True que si TOUTES ces conditions tiennent :
      - assez de décisions pour que le taux veuille dire quelque chose
      - le taux d'approbation atteint le seuil
      - aucun refus dans les 3 dernières décisions — un refus récent doit
        peser plus lourd qu'une moyenne ancienne qui le noierait.
    """
    h = historique(type_action)
    appels = len(h)
    approuves = sum(1 for d in h if d["approuve"])
    taux = (approuves / appels) if appels else 0.0
    refus_recent = any(not d["approuve"] for d in h[-3:])
    constant = appels >= seuil_appels and taux >= seuil_taux and not refus_recent
    return {
        "type_action": type_action,
        "appels": appels,
        "approuves": approuves,
        "taux": round(taux, 3),
        "assez_de_donnees": appels >= seuil_appels,
        "constant": constant,
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tout = _lire_tout().get("decisions", [])
    types = sorted(set(d["type_action"] for d in tout))
    print()
    print("=" * 74)
    print("JARVIS — CONFIANCE PAR TYPE D'ACTION")
    print("=" * 74)
    if not types:
        print("  Aucune décision journalisée pour l'instant.")
    for t in types:
        m = maturite(t)
        print("  %-30s %3d decisions  %5.1f%% approuve%s"
              % (t, m["appels"], m["taux"] * 100,
                 "  -> pourrait etre reconsidere manuellement" if m["constant"] else ""))
    print("=" * 74)
