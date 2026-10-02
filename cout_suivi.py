# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Suivi d'usage et de coût des appels modèle
=========================================================
Journal des appels IA : tokens, modèle, coût si connu. Réclamé par la
comparaison avec la roadmap Trillion (« Live cost dashboard ») et par le
Tier 6 du cahier des charges (« une dérive de coût doit être visible tout
de suite »).

PAS DE TABLE DE PRIX INTÉGRÉE
Coder les prix par modèle ici les fige au jour de l'écriture et ment dès
qu'un fournisseur change ses tarifs. `cout_usd` est donc TOUJOURS fourni
par l'appelant, qui connaît le prix exact de l'appel qu'il vient de faire.
Sans lui, l'entrée est journalisée quand même (les tokens comptent déjà),
et `resume()` le dit : « appels_sans_cout » plutôt qu'un total qui aurait
l'air complet sans l'être.

PAS ENCORE BRANCHÉ SUR main2.py
main2.py appelle `generate_content` à une quinzaine d'endroits, et le
fichier avait 735 lignes non validées (git diff) au moment d'écrire ce
module — y toucher aujourd'hui aurait risqué de casser un travail en cours,
sans personne pour vérifier avant le retour de l'utilisateur. Le point
d'intégration recommandé, pour une prochaine session : un seul point de
passage qui enveloppe `client.models.generate_content` et appelle
`enregistrer()` avec `response.usage_metadata`, sur le même principe que
`garde_fous.ouvrir_url()` pour les URLs (une définition, tous les appels).

    venv\\Scripts\\python.exe cout_suivi.py
"""

import io
import json
import os
import time

import config

FICHIER = "cout_usage.json"


def _chemin():
    return config.chemin_donnees(FICHIER, creer_dossier=True)


def _lire_tout():
    try:
        with io.open(str(_chemin()), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"appels": []}


def _ecrire_tout(donnees):
    chemin = str(_chemin())
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(donnees, ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)


def enregistrer(fournisseur, modele, tokens_entree=0, tokens_sortie=0,
                cout_usd=None, contexte=""):
    """
    Journalise un appel modèle. Ne lève jamais : un suivi qui casse l'appel
    qu'il observe serait pire que l'absence de suivi.
    """
    try:
        donnees = _lire_tout()
        donnees.setdefault("appels", []).append({
            "horodatage": time.time(),
            "fournisseur": fournisseur,
            "modele": modele,
            "tokens_entree": int(tokens_entree or 0),
            "tokens_sortie": int(tokens_sortie or 0),
            "cout_usd": float(cout_usd) if cout_usd is not None else None,
            "contexte": contexte,
        })
        _ecrire_tout(donnees)
        return True
    except Exception as e:
        print("[COUT] journalisation ignoree : %r" % (e,))
        return False


def _depuis(appels, depuis_ts):
    if depuis_ts is None:
        return appels
    return [a for a in appels if a["horodatage"] >= depuis_ts]


def resume(depuis_ts=None):
    """
    Totaux : appels, tokens, coût connu, et nombre d'appels sans coût
    renseigné — pour ne jamais laisser croire à un total complet.
    """
    appels = _depuis(_lire_tout().get("appels", []), depuis_ts)
    cout_connu = sum(a["cout_usd"] for a in appels if a["cout_usd"] is not None)
    sans_cout = sum(1 for a in appels if a["cout_usd"] is None)
    par_modele = {}
    for a in appels:
        cle = "%s/%s" % (a["fournisseur"], a["modele"])
        m = par_modele.setdefault(cle, {"appels": 0, "tokens_entree": 0,
                                        "tokens_sortie": 0, "cout_usd": 0.0})
        m["appels"] += 1
        m["tokens_entree"] += a["tokens_entree"]
        m["tokens_sortie"] += a["tokens_sortie"]
        if a["cout_usd"] is not None:
            m["cout_usd"] += a["cout_usd"]
    return {
        "appels": len(appels),
        "tokens_entree": sum(a["tokens_entree"] for a in appels),
        "tokens_sortie": sum(a["tokens_sortie"] for a in appels),
        "cout_usd_connu": round(cout_connu, 4),
        "appels_sans_cout": sans_cout,
        "par_modele": par_modele,
    }


def resume_jour(maintenant=None):
    """Résumé depuis minuit, heure locale (ou celle de `maintenant`, injectable)."""
    t = maintenant or time.localtime()
    minuit = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))
    return resume(depuis_ts=minuit)


def depassement_budget(budget_usd_jour, maintenant=None):
    """
    (depasse, cout_du_jour). `budget_usd_jour` est fourni par l'appelant —
    ce module n'a pas d'avis sur ce qui est un budget raisonnable.
    """
    r = resume_jour(maintenant)
    return r["cout_usd_connu"] > budget_usd_jour, r["cout_usd_connu"]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = resume_jour()
    print()
    print("=" * 74)
    print("JARVIS — USAGE DU JOUR")
    print("=" * 74)
    print("  %d appels, %d tokens entree, %d tokens sortie"
          % (r["appels"], r["tokens_entree"], r["tokens_sortie"]))
    print("  cout connu : %.4f$ (%d appels sans cout renseigne)"
          % (r["cout_usd_connu"], r["appels_sans_cout"]))
    for modele, m in sorted(r["par_modele"].items()):
        print("    %-40s %4d appels  %8d in  %8d out  %.4f$"
              % (modele, m["appels"], m["tokens_entree"], m["tokens_sortie"], m["cout_usd"]))
    print("=" * 74)
