# -*- coding: utf-8 -*-
"""Vérifie cout_suivi.py — journalisation et résumés, jamais sur le vrai fichier."""

import io
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import cout_suivi as cs

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


_chemin_reel = cs._chemin()
_sauvegarde = None
if os.path.exists(_chemin_reel):
    _sauvegarde = io.open(_chemin_reel, encoding="utf-8").read()

try:
    cs._ecrire_tout({"appels": []})

    ok = cs.enregistrer("gemini", "gemini-3.1-flash-lite", tokens_entree=100,
                        tokens_sortie=50, cout_usd=0.002, contexte="test")
    verifier("enregistrer renvoie True", ok is True)

    cs.enregistrer("gemini", "gemini-3.1-flash-lite", tokens_entree=200, tokens_sortie=80)
    cs.enregistrer("groq", "llama-3", tokens_entree=10, tokens_sortie=5, cout_usd=0.0001)

    r = cs.resume()
    verifier("3 appels comptes", r["appels"] == 3)
    verifier("tokens entree cumules", r["tokens_entree"] == 310)
    verifier("cout connu = somme des deux appels avec cout", abs(r["cout_usd_connu"] - 0.0021) < 1e-9)
    verifier("1 appel sans cout renseigne (pas ignore, juste marque)", r["appels_sans_cout"] == 1)
    verifier("regroupement par modele : 2 cles distinctes", len(r["par_modele"]) == 2)
    verifier("le modele gemini cumule ses 2 appels",
              r["par_modele"]["gemini/gemini-3.1-flash-lite"]["appels"] == 2)

    # Un appel dont enregistrer() echoue silencieusement ne doit jamais lever.
    leve = False
    try:
        cs.enregistrer("x", "y", cout_usd="pas_un_nombre")
    except Exception:
        leve = True
    verifier("cout_usd invalide -> ne leve pas (best-effort)", not leve)

    # resume_jour : un appel d'hier ne doit pas compter dans aujourd'hui.
    cs._ecrire_tout({"appels": []})
    maintenant = time.localtime()
    hier_ts = time.mktime(maintenant[:3] + (0, 0, 0, 0, 0, -1)) - 3600  # 23h la veille
    donnees = cs._lire_tout()
    donnees["appels"].append({"horodatage": hier_ts, "fournisseur": "gemini", "modele": "x",
                              "tokens_entree": 999, "tokens_sortie": 0, "cout_usd": 5.0, "contexte": ""})
    cs._ecrire_tout(donnees)
    cs.enregistrer("gemini", "x", tokens_entree=1, cout_usd=0.01)
    rj = cs.resume_jour(maintenant)
    verifier("resume_jour exclut l'appel d'hier", rj["appels"] == 1 and rj["tokens_entree"] == 1)

    depasse, cout = cs.depassement_budget(0.005, maintenant)
    verifier("depassement_budget detecte un budget depasse (0.01$ > 0.005$)", depasse is True)
    depasse2, _ = cs.depassement_budget(1.0, maintenant)
    verifier("depassement_budget ne signale rien sous le budget (0.01$ < 1$)", depasse2 is False)
finally:
    if _sauvegarde is not None:
        io.open(_chemin_reel, "w", encoding="utf-8").write(_sauvegarde)
    elif os.path.exists(_chemin_reel):
        os.remove(_chemin_reel)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Suivi de cout : conforme.")
