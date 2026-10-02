# -*- coding: utf-8 -*-
r"""
Vérifie le gestionnaire de compétences.

CE QU'IL GARDE VRAIMENT
Qu'une compétence cassée soit VISIBLE et nommée cassée, au lieu de
disparaître de l'inventaire — et qu'analyser la liste n'exécute jamais le
code des plugins. Un plugin écrit par un modèle peut faire n'importe quoi
au niveau module ; afficher la liste ne doit pas le déclencher.

    venv\Scripts\python.exe _test_plugins_manager.py
"""

import io
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import plugins_manager as pm

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


BON = "def executer(texte_utilisateur=None):\n    return 'bonjour'\n"
CASSE = "def executer(:\n    return 'jamais'\n"
SANS_ENTREE = "def autre_chose():\n    return 1\n"
# Poserait un fichier temoin si le module etait importe pour etre inventorie.
EFFET_DE_BORD = (
    "import pathlib\n"
    "pathlib.Path(__file__).with_name('TEMOIN_EXECUTION').write_text('x')\n"
    "def executer(texte_utilisateur=None):\n    return 'ok'\n"
)

dossier = tempfile.mkdtemp(prefix="jarvis_plugins_")
etat = os.path.join(dossier, "etat.json")
_vrai_dossier, _vrai_etat = pm.dossier_plugins, pm._chemin_etat
pm.dossier_plugins = lambda creer=False: dossier
pm._chemin_etat = lambda: etat

try:
    for nom, source in (("bonne", BON), ("cassee", CASSE),
                        ("sans_entree", SANS_ENTREE), ("effet", EFFET_DE_BORD)):
        io.open(os.path.join(dossier, pm.PREFIXE + nom + ".py"),
                "w", encoding="utf-8").write(source)

    fiches = {f["nom"]: f for f in pm.lister()}
    verifier("les 4 compétences du dossier sont inventoriées", len(fiches) == 4)
    verifier("une compétence valide est « ok »", fiches["bonne"]["etat"] == "ok")

    # Le point qui compte : une compétence cassée reste DANS la liste, avec
    # sa raison. La faire disparaître serait le silence que le dépôt refuse.
    verifier("une erreur de syntaxe -> état « cassee », présente dans la liste",
             fiches["cassee"]["etat"] == "cassee" and "syntaxe" in fiches["cassee"]["erreur"])
    verifier("l'erreur de syntaxe donne la ligne", "ligne" in fiches["cassee"]["erreur"])
    verifier("sans fonction executer() -> cassée, et le dit",
             fiches["sans_entree"]["etat"] == "cassee"
             and "executer" in fiches["sans_entree"]["erreur"])

    verifier("inventorier n'EXÉCUTE pas le code des plugins",
             not os.path.exists(os.path.join(dossier, "TEMOIN_EXECUTION")))

    # ── Interrupteur ────────────────────────────────────────────────────
    verifier("active par défaut, sans réglage préalable", pm.est_actif("bonne"))
    ok, _ = pm.basculer("bonne", False)
    verifier("extinction acceptée", ok)
    verifier("éteinte -> est_actif() dit non", not pm.est_actif("bonne"))
    verifier("le fichier d'état a bien été écrit", os.path.exists(etat))
    verifier("éteindre n'efface pas le fichier de la compétence",
             os.path.exists(pm.chemin_competence("bonne")))
    verifier("elle reste dans l'inventaire, marquée inactive",
             any(f["nom"] == "bonne" and not f["actif"] for f in pm.lister()))
    pm.basculer("bonne", True)
    verifier("rallumée -> active de nouveau", pm.est_actif("bonne"))

    ok_inconnu, raison = pm.basculer("nexiste_pas", False)
    verifier("éteindre une compétence absente est refusé, avec la raison",
             not ok_inconnu and "installée" in raison)

    verifier("le nom parlé est normalisé comme dans main2",
             pm.normaliser("Météo Détaillée !") == "mto_dtaille_")

    verifier("refus() nomme la compétence", "bonne" in pm.refus("bonne"))

    # ── Compréhension de la demande parlée ──────────────────────────────
    verifier("« liste des compétences » -> lister",
             pm.analyser_demande("Jarvis, liste des compétences") == ("lister", ""))
    verifier("« désactive la compétence météo » -> desactiver météo",
             pm.analyser_demande("désactive la compétence météo") == ("desactiver", "meteo"))
    verifier("« réactive la compétence météo » -> activer météo",
             pm.analyser_demande("réactive la compétence météo") == ("activer", "meteo"))
    # Ces trois-là appartiennent déjà à resoudre_commandes_locales : les
    # reprendre ici créerait deux chemins pour le même ordre.
    for deja_traitee in ("crée la compétence x pour y", "supprime la compétence x",
                         "exécute la compétence x"):
        verifier("« %s » reste à main2" % deja_traitee[:24],
                 pm.analyser_demande(deja_traitee) == (None, ""))

    # ── Résumé parlé ────────────────────────────────────────────────────
    pm.basculer("bonne", False)
    dit = pm.resume()
    verifier("le résumé compte les compétences", dit.startswith("4 compétences"))
    verifier("le résumé nomme la désactivée", "désactivée" in dit and "bonne" in dit)
    verifier("le résumé DIT les cassées au lieu de les taire",
             "cassee" in dit and "cassée" in dit)
    pm.basculer("bonne", True)
finally:
    pm.dossier_plugins, pm._chemin_etat = _vrai_dossier, _vrai_etat
    shutil.rmtree(dossier, ignore_errors=True)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Gestionnaire de compétences : conforme.")
