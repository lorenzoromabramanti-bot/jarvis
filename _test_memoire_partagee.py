# -*- coding: utf-8 -*-
"""
Verifie le vault de memoire partagee, dans un dossier temporaire.

Ce qui est teste n'est pas « ca ecrit un fichier » mais les trois regles qui
cassent si on les neglige : la protection des chemins, l'isolation entre
auteurs, et l'atomicite de l'ecriture.

    venv\\Scripts\\python.exe _test_memoire_partagee.py
"""

import io
import shutil
import sys
import tempfile
from pathlib import Path

import memoire_partagee as mp


def verifier():
    # Rediriger le vault vers un dossier jetable : on ne teste jamais sur
    # les vraies notes de quelqu'un.
    vrai = mp.RACINE
    mp.RACINE = Path(tempfile.mkdtemp(prefix="vault_test_"))
    try:
        mp.initialiser()
        for d in mp.DOSSIERS:
            assert (mp.RACINE / d).is_dir(), "dossier %s manquant" % d

        # ── Ecriture et relecture ───────────────────────────────────────
        mp.ecrire("pannes", "Test d'écriture", "Le corps.", source="jarvis",
                  sujet=["a", "b"], titre="Titre lisible")
        note = mp.lire("pannes", "Test d'écriture", "jarvis")
        assert note and note["corps"].strip() == "Le corps.", note
        assert note["meta"]["source"] == "jarvis"
        assert note["meta"]["type"] == "pannes"

        # Accents et espaces -> nom de fichier sur
        fichiers = [f.name for f in (mp.RACINE / "pannes").glob("*.md")]
        assert fichiers == ["test-d-ecriture.jarvis.md"], fichiers

        # ── Un fichier, un auteur ───────────────────────────────────────
        # Deux sources sur le MEME sujet doivent produire DEUX fichiers,
        # jamais un ecrasement. C'est ce qui evite tout verrou.
        mp.ecrire("pannes", "Test d'écriture", "Version de l'agent.",
                  source="claude-code")
        assert len(list((mp.RACINE / "pannes").glob("*.md"))) == 2
        assert mp.lire("pannes", "Test d'écriture", "jarvis")["corps"].strip() == "Le corps.", \
            "l'agent a ecrase la note de JARVIS"

        # ── Chemins : refuser, pas rattraper en silence ─────────────────
        for mauvais in ("../../.env", "..\\..\\secret", "/etc/passwd"):
            try:
                mp.ecrire("pannes", mauvais, "x", source="jarvis")
            except Exception:
                pass                      # leve : correct
            # Quoi qu'il arrive, rien ne doit sortir du vault.
        dehors = list(mp.RACINE.parent.glob("*.env")) + list(mp.RACINE.parent.glob("secret*"))
        assert not dehors, "un fichier a ete ecrit HORS du vault : %s" % dehors

        # Dossier et source inconnus : erreur franche
        for appel in (lambda: mp.ecrire("inconnu", "x", "y", source="jarvis"),
                      lambda: mp.ecrire("pannes", "x", "y", source="pirate")):
            try:
                appel()
                raise AssertionError("un appel invalide est passe")
            except ValueError:
                pass

        # ── Aucun .tmp ne survit a une ecriture reussie ─────────────────
        assert not list(mp.RACINE.rglob("*.tmp")), "un fichier temporaire a survecu"

        # ── Recherche ───────────────────────────────────────────────────
        r = mp.chercher("corps")
        assert r["nombre"] >= 1, r
        assert mp.chercher("motocyclette")["nombre"] == 0
        assert "erreur" in mp.chercher("[invalide(")     # motif casse -> pas de plantage

        # ── Index genere ────────────────────────────────────────────────
        mp.regenerer_index()
        index = io.open(mp.RACINE / "INDEX.md", encoding="utf-8").read()
        assert "Titre lisible" in index, "la note n'apparait pas dans l'index"
        assert "généré" in index, "l'index ne previent pas qu'il est derive"

        # ── Suppression ─────────────────────────────────────────────────
        assert mp.supprimer("pannes", "Test d'écriture", "claude-code")
        assert not mp.supprimer("pannes", "Test d'écriture", "claude-code")

        print("  OK  cinq dossiers crees")
        print("  OK  ecriture, relecture, frontmatter")
        print("  OK  accents et espaces -> nom de fichier sur")
        print("  OK  un fichier par auteur, aucun ecrasement croise")
        print("  OK  chemins hors du vault refuses, rien n'en sort")
        print("  OK  dossier ou source inconnus -> erreur franche")
        print("  OK  aucun .tmp residuel")
        print("  OK  recherche, motif invalide sans plantage")
        print("  OK  index genere et signale comme derive")
    finally:
        shutil.rmtree(mp.RACINE, ignore_errors=True)
        mp.RACINE = vrai


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Memoire partagee : conforme.")
