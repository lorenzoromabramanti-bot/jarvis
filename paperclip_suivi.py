# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Où en est Paperclip
=================================
« Jarvis, où en est Paperclip ? » : JARVIS lit l'API locale de Paperclip
(http://127.0.0.1:3100/api) et répond en une phrase faite
pour être DITE : pas d'identifiants « LOR-9 » épelés, des titres courts, des
nombres en lettres quand ils sont petits.

Lecture seule. Garde : capacité « agents » (action get_agents), comme le reste
du suivi des agents de développement.
"""

import json
import re
import urllib.error
import urllib.request

API = "http://127.0.0.1:3100/api"
DELAI = 5

# La reconnaissance vocale écrit aussi « paper clip ».
_PAPERCLIP = re.compile(r"\bpaper\s?clip\b", re.I)
_QUESTION = re.compile(
    r"o[uù] en est|avanc|[ée]tat|statut|quoi de neuf|bilan|fait quoi|fais quoi|travaill|progr|r[ée]sum", re.I)
_PREFIXE = re.compile(r"^\s*\[[^\]]*\]\s*")
_NOMBRES = ["aucune", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix"]


def reconnait_demande(texte):
    """Vrai pour une question sur l'avancement de Paperclip, pas pour une simple mention."""
    return bool(texte and _PAPERCLIP.search(texte) and _QUESTION.search(texte))


def _lire(chemin):
    with urllib.request.urlopen(API + chemin, timeout=DELAI) as r:
        return json.loads(r.read())


def etat():
    """
    {"taches": [...], "agents": [...]} lus dans Paperclip, ou None s'il est éteint.
    Chaque tâche : titre, statut, agent ; chaque agent : nom, statut.
    """
    try:
        societes = _lire("/companies")
        if not societes:
            return None
        sid = societes[0]["id"]
        agents = _lire("/companies/%s/agents" % sid)
        issues = _lire("/companies/%s/issues" % sid)
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None
    noms = {a["id"]: a.get("name", "?") for a in agents}
    return {
        "agents": [{"nom": a.get("name", "?"), "statut": a.get("status", "")} for a in agents],
        "taches": [{"titre": _titre(t.get("title", "")), "statut": t.get("status", ""),
                    "agent": noms.get(t.get("assigneeAgentId"))} for t in issues],
    }


def _titre(titre):
    """« [P1] Memory leak in BACKGROUND_TASKS set » → « Memory leak in BACKGROUND_TASKS set », 60 caractères au plus."""
    titre = _PREFIXE.sub("", titre).strip()
    return titre if len(titre) <= 60 else titre[:59].rstrip() + "…"


def _nombre(n, mot):
    """« deux tâches », « une tâche », « 12 tâches »."""
    dit = _NOMBRES[n] if n < len(_NOMBRES) else str(n)
    return "%s %s%s" % (dit, mot, "s" if n > 1 else "")


def phrase(e, nom="Monsieur"):
    """La réponse à dire, à partir de etat()."""
    if e is None:
        return "Paperclip ne répond pas, %s : il est éteint." % nom
    t = e["taches"]
    en_cours = [x for x in t if x["statut"] == "in_progress"]
    a_faire = [x for x in t if x["statut"] == "todo"]
    relecture = [x for x in t if x["statut"] == "in_review"]
    bloquees = [x for x in t if x["statut"] == "blocked"]
    finies = [x for x in t if x["statut"] == "done"]
    actifs = [a["nom"] for a in e["agents"] if a["statut"] == "running"]

    # Des phrases courtes : à l'oral, une longue liste après deux-points se perd.
    if en_cours:
        detail = " ; ".join("%s%s" % (x["titre"], ", par %s" % x["agent"] if x["agent"] else "") for x in en_cours[:3])
        debut = "%s en cours : %s." % (_nombre(len(en_cours), "tâche"), detail)
    else:
        debut = "aucune tâche en cours."
    comptes = []
    if a_faire:
        comptes.append("%s en attente" % _nombre(len(a_faire), "tâche"))
    if relecture:
        comptes.append("%s attend%s votre relecture" % (_nombre(len(relecture), "tâche"), "ent" if len(relecture) > 1 else ""))
    if bloquees:
        comptes.append("%s bloquée%s" % (_nombre(len(bloquees), "tâche"), "s" if len(bloquees) > 1 else ""))
    comptes.append("%s terminée%s" % (_nombre(len(finies), "tâche"), "s" if len(finies) > 1 else ""))
    milieu = ", ".join(comptes)

    texte = "Paperclip, %s. %s %s." % (nom, debut[0].upper() + debut[1:], milieu[0].upper() + milieu[1:])
    if actifs:
        texte += " %s %s en ce moment." % (" et ".join(actifs), "travaillent" if len(actifs) > 1 else "travaille")
    else:
        texte += " Aucun agent ne travaille en ce moment."
    return texte
