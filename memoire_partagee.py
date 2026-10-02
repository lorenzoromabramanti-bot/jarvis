# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Vault de mémoire partagée
=======================================
Un endroit où JARVIS et les agents de code (Claude Code, OpenCode) déposent ce
qu'ils apprennent, et où chacun retrouve ce que l'autre a écrit.

Conforme à `docs/proposition_memoire_partagee.md`. Ce qui suit rappelle les
décisions qui ne se devinent pas à la lecture du code.

EMPLACEMENT — `Documents/JARVIS/MemoirePartagee`
Pas dans le dossier d'installation : sous Program Files, Windows refuse
l'écriture sans élévation, et un vault doit s'ouvrir dans Obsidian d'un
double-clic. Pas dans %APPDATA% non plus : ce sont des notes qu'on lit, pas
un cache.

UN FICHIER, UN AUTEUR
Le nom porte la source : `pannes/vpn-ip-info.jarvis.md`. Un agent ne modifie
jamais un `.jarvis.md`, et réciproquement. Deux avis sur le même sujet font
deux fichiers. C'est ce qui permet à JARVIS (qui tourne en permanence) et à un
agent de code d'écrire en même temps sans verrou — et les verrous de fichier
fuient dès qu'un processus meurt mal, ce qu'on a déjà vu sur cette machine.

ÉCRITURE ATOMIQUE
Écriture dans un `.tmp` puis `os.replace()`, atomique sur Windows comme sur
POSIX. Sans ça, un lecteur peut tomber sur un fichier à moitié écrit.

CHEMINS
`os.path.basename()` de l'ancien helper interdisait toute arborescence en
protégeant du path traversal. Ici on vérifie réellement que la cible reste
sous la racine, ce qui est à la fois plus permissif et plus sûr : `../../.env`
est refusé explicitement au lieu d'être transformé en `.env`.

    venv\\Scripts\\python.exe memoire_partagee.py
"""

import io
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

try:
    from config import DOSSIER_DOCUMENTS
    RACINE = Path(DOSSIER_DOCUMENTS) / "MemoirePartagee"
except Exception:                                     # pragma: no cover
    RACINE = Path.home() / "Documents" / "JARVIS" / "MemoirePartagee"

# Cinq dossiers, par nature de contenu. Une arborescence par date répondrait
# à « quand », or la question posée est toujours « quoi ».
DOSSIERS = {
    "decisions":   "on a choisi X plutôt que Y, et pourquoi",
    "pannes":      "une panne constatée, sa cause, son correctif",
    "conventions": "règles du projet qu'un agent doit connaître",
    "etat":        "photographie d'un sous-système à un instant",
    "brouillons":  "en cours, rien de fiable",
}

SOURCES = ("jarvis", "claude-code", "opencode", "codex", "humain")


def _ardoise(texte):
    """Titre libre -> nom de fichier sûr, lisible, sans accents."""
    t = unicodedata.normalize("NFD", str(texte or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return (t or "note")[:60]


def chemin(dossier, id_note, source):
    """
    Chemin d'une note, vérifié.

    Lève plutôt que de corriger en silence : un dossier inconnu ou un
    identifiant qui tente de sortir du vault est une erreur d'appel, pas
    quelque chose à rattraper discrètement.
    """
    if dossier not in DOSSIERS:
        raise ValueError("dossier inconnu : %r (attendus : %s)"
                         % (dossier, ", ".join(DOSSIERS)))
    if source not in SOURCES:
        raise ValueError("source inconnue : %r (attendues : %s)"
                         % (source, ", ".join(SOURCES)))
    nom = "%s.%s.md" % (_ardoise(id_note), source)
    cible = (RACINE / dossier / nom).resolve()
    racine = RACINE.resolve()
    if not str(cible).startswith(str(racine) + os.sep):
        raise ValueError("chemin hors du vault : %s" % cible)
    return cible


def initialiser():
    """Crée la racine et les cinq dossiers. Sans effet s'ils existent."""
    for d in DOSSIERS:
        (RACINE / d).mkdir(parents=True, exist_ok=True)
    return RACINE


def ecrire(dossier, id_note, corps, source="jarvis", sujet=None, titre=None):
    """
    Écrit une note. Écrase seulement une note de LA MÊME source.

    Renvoie le chemin écrit.
    """
    cible = chemin(dossier, id_note, source)
    cible.parent.mkdir(parents=True, exist_ok=True)

    entete = [
        "---",
        "id: %s" % _ardoise(id_note),
        "type: %s" % dossier,
        "source: %s" % source,
        "date: %s" % date.today().isoformat(),
    ]
    if sujet:
        entete.append("sujet: [%s]" % ", ".join(sujet if isinstance(sujet, (list, tuple)) else [sujet]))
    if titre:
        entete.append("titre: %s" % titre)
    entete.append("---")
    contenu = "\n".join(entete) + "\n\n" + str(corps).strip() + "\n"

    # Atomique : personne ne doit lire un fichier a moitie ecrit.
    tmp = cible.with_suffix(".md.tmp")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(contenu)
    os.replace(tmp, cible)
    return cible


def _frontmatter(texte):
    if not texte.startswith("---"):
        return {}, texte
    fin = texte.find("\n---", 3)
    if fin == -1:
        return {}, texte
    meta = {}
    for ligne in texte[3:fin].strip().splitlines():
        if ":" in ligne:
            k, v = ligne.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, texte[fin + 4:].lstrip("\n")


def lire(dossier, id_note, source):
    cible = chemin(dossier, id_note, source)
    if not cible.exists():
        return None
    brut = io.open(cible, encoding="utf-8").read()
    meta, corps = _frontmatter(brut)
    return {"chemin": str(cible), "meta": meta, "corps": corps}


def lister(dossier=None, source=None):
    """Toutes les notes, avec leur frontmatter. Ne lit pas les corps."""
    notes = []
    for d in ([dossier] if dossier else DOSSIERS):
        for f in sorted((RACINE / d).glob("*.md")):
            try:
                meta, _ = _frontmatter(io.open(f, encoding="utf-8").read(1200))
            except Exception:
                meta = {}
            if source and meta.get("source") != source:
                continue
            notes.append({"dossier": d, "fichier": f.name,
                          "chemin": str(f), **meta})
    return notes


def chercher(motif, insensible=True):
    """
    Recherche par mot, dans les titres et les corps.

    Pas d'embeddings : à cette échelle, quelques dizaines de notes, une
    recherche textuelle est plus rapide, plus prévisible et plus facile à
    corriger quand elle se trompe. On ajoutera de la sémantique le jour où
    celle-ci échouera vraiment.
    """
    drapeaux = re.IGNORECASE if insensible else 0
    try:
        rx = re.compile(motif, drapeaux)
    except re.error as e:
        return {"erreur": "motif invalide : %s" % e, "resultats": []}
    trouves = []
    for d in DOSSIERS:
        for f in sorted((RACINE / d).glob("*.md")):
            try:
                brut = io.open(f, encoding="utf-8").read()
            except Exception:
                continue
            if not rx.search(brut):
                continue
            meta, corps = _frontmatter(brut)
            extrait = ""
            m = rx.search(corps)
            if m:
                a, b = max(0, m.start() - 60), min(len(corps), m.end() + 60)
                extrait = corps[a:b].replace("\n", " ")
            trouves.append({"dossier": d, "fichier": f.name,
                            "source": meta.get("source", "?"),
                            "date": meta.get("date", ""), "extrait": extrait})
    return {"resultats": trouves, "nombre": len(trouves)}


def supprimer(dossier, id_note, source):
    cible = chemin(dossier, id_note, source)
    if not cible.exists():
        return False
    cible.unlink()
    return True


def regenerer_index():
    """
    Réécrit INDEX.md à partir des frontmatters.

    Dérivé, jamais édité à la main : deux processus qui l'écriraient en même
    temps seraient la première chose à casser.
    """
    initialiser()
    notes = lister()
    lignes = ["# Mémoire partagée", "",
              "Index **généré** par `memoire_partagee.py`. Ne pas l'éditer : "
              "il est réécrit à chaque régénération.", "",
              "%d note(s)." % len(notes), ""]
    for d, description in DOSSIERS.items():
        dedans = [n for n in notes if n["dossier"] == d]
        lignes.append("## %s — %s" % (d, description))
        lignes.append("")
        if not dedans:
            lignes += ["_vide_", ""]
            continue
        for n in dedans:
            lignes.append("- [%s](%s/%s) · %s · %s"
                          % (n.get("titre") or n.get("id") or n["fichier"],
                             d, n["fichier"], n.get("source", "?"), n.get("date", "")))
        lignes.append("")
    tmp = RACINE / "INDEX.md.tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write("\n".join(lignes))
    os.replace(tmp, RACINE / "INDEX.md")
    return RACINE / "INDEX.md"


def resume():
    notes = lister()
    par_source = {}
    for n in notes:
        par_source[n.get("source", "?")] = par_source.get(n.get("source", "?"), 0) + 1
    return {"racine": str(RACINE), "existe": RACINE.exists(),
            "notes": len(notes), "par_source": par_source,
            "par_dossier": {d: sum(1 for n in notes if n["dossier"] == d)
                            for d in DOSSIERS}}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    initialiser()
    regenerer_index()
    r = resume()
    print()
    print("=" * 74)
    print("MEMOIRE PARTAGEE")
    print("=" * 74)
    print("  racine : %s" % r["racine"])
    print("  notes  : %d" % r["notes"])
    for d, n in r["par_dossier"].items():
        print("    %-14s %d" % (d, n))
    if r["par_source"]:
        print("  par source : %s" % r["par_source"])
    print("=" * 74)
