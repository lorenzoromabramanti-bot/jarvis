# -*- coding: utf-8 -*-
r"""
J.A.R.V.I.S — Gestionnaire de compétences (plugins)
===================================================
JARVIS sait déjà ÉCRIRE une compétence (`jarvis_creer_competence`) et
l'EXÉCUTER par son nom. Ce qu'il ne savait pas faire : dire lesquelles
existent, laquelle est cassée, et en éteindre une sans la supprimer.

CE QUE CE MODULE AJOUTE
    lister()      inventaire réel du dossier plugins/, avec l'état de chacune
    basculer()    interrupteur ON/OFF persistant, par compétence
    est_actif()   la garde que l'exécution consulte avant de lancer quoi que ce soit

POURQUOI ON N'IMPORTE PAS LE FICHIER POUR LE VALIDER
Importer exécute le code au niveau module. Un plugin généré par un modèle
peut ouvrir une fenêtre, faire un appel réseau, ou boucler — au simple fait
d'AFFICHER la liste. On lit donc la source et on l'analyse (`ast`) : une
erreur de syntaxe et l'absence de point d'entrée `executer` se voient sans
rien exécuter. L'exécution reste là où elle était, à la demande explicite.

UNE COMPÉTENCE CASSÉE N'EST PAS CACHÉE
Elle apparaît dans la liste avec `etat="cassee"` et l'erreur en clair. La
règle du dépôt vaut ici aussi : ce qui ne marche pas le DIT, il ne disparaît
pas de l'inventaire.

ÉTAT PAR DÉFAUT : ACTIF
Une compétence qui vient d'être générée doit répondre tout de suite — sans
détour par un réglage. Le fichier d'état ne retient donc que les extinctions
explicites.

    venv\Scripts\python.exe plugins_manager.py
"""

import ast
import io
import json
import os
import re

import config

DOSSIER = "plugins"
PREFIXE = "competence_"
FICHIER_ETAT = "plugins_etat.json"
POINT_ENTREE = "executer"


def dossier_plugins(creer=False):
    chemin = os.path.join(str(config.RACINE), DOSSIER)
    if creer and not os.path.isdir(chemin):
        os.makedirs(chemin, exist_ok=True)
    return chemin


def normaliser(nom_competence):
    """Le nom parlé -> le nom de fichier. Même règle que main2.jarvis_creer_competence."""
    return re.sub(r"[^a-zA-Z0-9_]", "", str(nom_competence or "").lower().replace(" ", "_"))


def chemin_competence(nom_competence):
    return os.path.join(dossier_plugins(), PREFIXE + normaliser(nom_competence) + ".py")


# ── État ON/OFF ──────────────────────────────────────────────────────────

def _chemin_etat():
    return config.chemin_donnees(FICHIER_ETAT, creer_dossier=True)


def _lire_etat():
    try:
        with io.open(str(_chemin_etat()), encoding="utf-8") as f:
            donnees = json.load(f)
        return {str(k): bool(v) for k, v in donnees.get("eteintes", {}).items()}
    except Exception:
        return {}


def _ecrire_etat(eteintes):
    chemin = str(_chemin_etat())
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps({"eteintes": eteintes}, ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)


def est_actif(nom_competence):
    """Actif sauf extinction explicite — voir « état par défaut » en tête."""
    return not _lire_etat().get(normaliser(nom_competence), False)


def basculer(nom_competence, actif):
    """
    Allume ou éteint une compétence. Renvoie (ok, raison).

    Refuse un nom inconnu : accepter silencieusement écrirait un réglage
    pour un fichier qui n'existe pas, et l'utilisateur croirait avoir
    éteint quelque chose.
    """
    cle = normaliser(nom_competence)
    if not cle:
        return False, "nom de compétence vide"
    if not os.path.exists(chemin_competence(cle)):
        return False, "la compétence « %s » n'est pas installée" % nom_competence
    eteintes = _lire_etat()
    if actif:
        eteintes.pop(cle, None)
    else:
        eteintes[cle] = True
    _ecrire_etat(eteintes)
    return True, "activée" if actif else "désactivée"


# ── Inventaire ───────────────────────────────────────────────────────────

def analyser_source(source):
    """
    (etat, erreur) pour un code source, SANS l'exécuter.

    etat vaut "ok" ou "cassee". Une compétence sans `executer` est cassée :
    l'exécuteur ne saurait pas par où l'appeler, autant le dire ici plutôt
    qu'au moment où on la réclame à la voix.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError as e:
        return "cassee", "erreur de syntaxe ligne %s : %s" % (e.lineno, e.msg)
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.name == POINT_ENTREE:
            return "ok", ""
    return "cassee", "aucune fonction « %s() » dans le fichier" % POINT_ENTREE


def inspecter(nom_competence):
    """Fiche d'une compétence : nom, fichier, actif, état, erreur."""
    cle = normaliser(nom_competence)
    fichier = chemin_competence(cle)
    fiche = {"nom": cle, "fichier": fichier, "actif": est_actif(cle),
             "etat": "cassee", "erreur": "", "taille": 0}
    if not os.path.exists(fichier):
        fiche["erreur"] = "fichier absent"
        return fiche
    try:
        source = io.open(fichier, encoding="utf-8", errors="replace").read()
    except OSError as e:
        fiche["erreur"] = "lecture impossible : %s" % e
        return fiche
    fiche["taille"] = len(source)
    fiche["etat"], fiche["erreur"] = analyser_source(source)
    return fiche


def lister():
    """Toutes les compétences présentes dans plugins/, triées par nom."""
    chemin = dossier_plugins()
    if not os.path.isdir(chemin):
        return []
    noms = [f[len(PREFIXE):-3] for f in sorted(os.listdir(chemin))
            if f.startswith(PREFIXE) and f.endswith(".py")]
    return [inspecter(n) for n in noms]


def _sans_accents(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower())
                   if unicodedata.category(c) != "Mn")


_INVENTAIRES = ("liste des competences", "liste tes competences", "mes competences",
                "quelles competences", "quelle competence", "competences installees",
                "competences disponibles")

_EXTINCTIONS = ("desactive la competence", "eteins la competence",
                "coupe la competence", "arrete la competence")

_ALLUMAGES = ("active la competence", "reactive la competence",
              "rallume la competence", "remets la competence")


def analyser_demande(texte):
    """
    (action, nom) pour une phrase. action vaut None, "lister", "activer"
    ou "desactiver".

    NE reconnaît PAS créer / supprimer / exécuter : ces trois-là sont déjà
    traités dans main2.resoudre_commandes_locales, et les dupliquer ici
    ferait deux chemins pour un même ordre — le premier à répondre
    gagnerait, selon l'ordre du fichier.
    """
    t = _sans_accents(texte)
    if any(m in t for m in _INVENTAIRES):
        return "lister", ""
    for motif in _EXTINCTIONS:
        if motif in t:
            return "desactiver", t.split(motif, 1)[1].strip(" .!?,;:«»\"'")
    for motif in _ALLUMAGES:
        if motif in t:
            return "activer", t.split(motif, 1)[1].strip(" .!?,;:«»\"'")
    return None, ""


def resume():
    """La phrase qui décrit l'inventaire. Dit les cassées, ne les cache pas."""
    fiches = lister()
    if not fiches:
        return "Aucune compétence n'est installée pour l'instant."
    actives = [f["nom"] for f in fiches if f["actif"] and f["etat"] == "ok"]
    eteintes = [f["nom"] for f in fiches if not f["actif"]]
    cassees = [f for f in fiches if f["etat"] == "cassee"]
    morceaux = []
    if actives:
        morceaux.append("%d active%s : %s" % (len(actives), "s" if len(actives) > 1 else "",
                                              ", ".join(actives)))
    if eteintes:
        morceaux.append("%d désactivée%s : %s" % (len(eteintes), "s" if len(eteintes) > 1 else "",
                                                  ", ".join(eteintes)))
    for f in cassees:
        morceaux.append("« %s » est cassée : %s" % (f["nom"], f["erreur"]))
    return "%d compétence%s installée%s. %s." % (
        len(fiches), "s" if len(fiches) > 1 else "", "s" if len(fiches) > 1 else "",
        " ; ".join(morceaux))


def refus(nom_competence):
    """Le message à donner quand une compétence éteinte est réclamée."""
    return ("La compétence « %s » est installée mais désactivée. "
            "Vous pouvez la réactiver dans le gestionnaire de compétences."
            % nom_competence)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    fiches = lister()
    print()
    print("=" * 70)
    print("COMPÉTENCES INSTALLÉES — %s" % dossier_plugins())
    print("=" * 70)
    if not fiches:
        print("  aucune compétence dans plugins/")
    for f in fiches:
        marque = "x" if f["actif"] else " "
        detail = "" if f["etat"] == "ok" else "   <-- CASSÉE : %s" % f["erreur"]
        print("  [%s] %-32s %s%s" % (marque, f["nom"], f["etat"], detail))
    print("=" * 70)
