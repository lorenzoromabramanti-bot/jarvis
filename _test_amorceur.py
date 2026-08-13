# -*- coding: utf-8 -*-
"""
Verifie l'amorceur d'installation.

CE QUI EST GARDE ICI
Pas « ca telecharge » — ca demande le reseau et une publication. Mais les
quatre decisions qui font echouer une installation chez quelqu'un d'autre,
sans qu'il puisse comprendre pourquoi :

  1. Choisir la bonne version de Python. Cette machine en a SIX, dont trois
     en 3.14, trop recent pour les dependances. Prendre la premiere venue
     ferait echouer pip a la compilation.
  2. Refuser un chemin trop long. Mesure : `python -m venv` reussit dans 19
     caracteres et echoue dans 140, avec pour seule trace « ensurepip
     returned non-zero exit status 15 ».
  3. Ne dependre que de la bibliotheque standard. L'amorceur tourne avant
     que quoi que ce soit soit installe.
  4. Extraire sans laisser sortir un fichier du dossier cible.

    venv\\Scripts\\python.exe _test_amorceur.py
"""

import ast
import io
import os
import shutil
import sys
import tempfile
import zipfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "amorceur"))
import amorceur as am


def verifier():
    # ── Bibliotheque standard uniquement ────────────────────────────────
    # Un seul import de trop et l'amorceur ne demarre pas sur une machine nue.
    standard = set(sys.stdlib_module_names)
    for fichier in ("amorceur.py", "fenetre.py"):
        chemin = os.path.join(ICI, "amorceur", fichier)
        arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
        for n in ast.walk(arbre):
            noms = ([a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import)
                    else [(n.module or "").split(".")[0]] if isinstance(n, ast.ImportFrom)
                    else [])
            for m in noms:
                if m and m not in standard and m not in ("amorceur", "fenetre"):
                    raise AssertionError(
                        "%s importe %s, qui n'est pas dans la bibliotheque "
                        "standard : l'amorceur doit tourner sur un Python nu"
                        % (fichier, m))
    print("  OK  amorceur et fenetre : bibliotheque standard uniquement")

    # ── Choix de la version de Python ───────────────────────────────────
    trouves = am.pythons_disponibles()
    assert trouves, "aucun Python detecte, alors que ce test tourne sous Python"
    chemin, version, avertissement = am.meilleur_python()
    assert chemin and os.path.exists(chemin)
    assert version >= am.VERSION_MINIMALE
    # Le premier retenu doit etre le plus adapte, pas le plus recent.
    versions = [v for v, _ in trouves]
    if any(v in am.VERSIONS_BONNES for v in versions):
        assert version in am.VERSIONS_BONNES, \
            "une version eprouvee existe (%s) mais %s a ete choisie" % (versions, version)
        assert not avertissement
    print("  OK  %d Python detectes, %d.%d retenu parmi %s"
          % (len(trouves), version[0], version[1],
             sorted({"%d.%d" % v for v in versions})))

    # ── Chemin trop long ────────────────────────────────────────────────
    court = os.path.join(os.path.expanduser("~"), "JARVIS")
    ok, _ = am.verifier_dossier(court)
    assert ok, "un chemin court et normal a ete refuse : %s" % court
    long = os.path.join(os.path.expanduser("~"), "a" * 120, "JARVIS")
    ok, raison = am.verifier_dossier(long)
    assert not ok, "un chemin de %d caracteres a ete accepte" % len(long)
    assert "caracteres" in raison or "caractères" in raison, \
        "le refus n'explique pas la vraie cause : %r" % raison
    print("  OK  chemin trop long refuse, avec la raison")

    # ── Extraction : rien ne sort du dossier ────────────────────────────
    dossier = tempfile.mkdtemp(prefix="jarvis_extr_")
    try:
        archive = os.path.join(dossier, "essai.zip")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("jarvis-1.0.0/main2.py", "# faux\n")
            z.writestr("jarvis-1.0.0/tools/machine.py", "# faux\n")
            z.writestr("jarvis-1.0.0/../evade.txt", "ne doit pas sortir\n")
        cible = os.path.join(dossier, "cible")
        am.extraire(archive, cible)

        assert os.path.exists(os.path.join(cible, "main2.py")), \
            "le dossier racine de l'archive GitHub n'a pas ete retranche"
        assert os.path.exists(os.path.join(cible, "tools", "machine.py")), \
            "l'arborescence n'a pas ete conservee"
        assert not os.path.exists(os.path.join(cible, "jarvis-1.0.0")), \
            "le dossier racine subsiste : on obtiendrait JARVIS/jarvis-1.0.0/main2.py"
        dehors = os.path.join(dossier, "evade.txt")
        assert not os.path.exists(dehors), "un fichier est sorti du dossier cible"
        print("  OK  extraction : racine retranchee, rien ne sort du dossier")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)

    # ── L'environnement est juge sur PIEECE, pas sur le code de retour ──
    # Mesure sur cette machine : `python -m venv` renvoie 1 (ensurepip sort
    # en 15) et pourtant l'environnement repond. Se fier au code aurait fait
    # echouer une installation qui marche.
    source = io.open(os.path.join(ICI, "amorceur", "amorceur.py"),
                     encoding="utf-8").read()
    assert "_venv_utilisable" in source, \
        "la verification par l'usage a disparu de creer_environnement"
    i_appel = source.index("_venv_utilisable(dossier)")
    i_retour = source.index("r.returncode", source.index("def creer_environnement"))
    assert i_appel < i_retour, \
        "le code de retour est consulte avant d'avoir teste l'environnement"
    print("  OK  l'environnement est juge en l'essayant, pas sur son code de retour")

    # ── Un paquet qui ne se compile pas ne doit pas TOUT arreter ────────
    # Mesure sur Ubuntu 26.04 : pygame n'a pas de version compilee pour
    # Python 3.14, et sa compilation reclame les en-tetes SDL. pip s'arretait
    # sur CE paquet, et les quarante-huit autres n'etaient jamais installes —
    # JARVIS devenait inutilisable a cause d'une bibliotheque qui ne sert
    # qu'a jouer du son.
    assert "_installer_un_par_un" in source, "la reprise paquet par paquet a disparu"
    assert "dernieres" in source, "les lignes d'erreur ne sont plus conservees"
    for vital in ("edge-tts", "python-dotenv", "websockets"):
        assert vital in am.INDISPENSABLES, \
            "%s devrait etre indispensable : sans lui JARVIS ne demarre pas" % vital
    assert "pygame" not in am.INDISPENSABLES, \
        "pygame ne sert qu'a jouer du son : il ne doit pas bloquer l'installation"
    print("  OK  reprise paquet par paquet, %d paquets juges indispensables"
          % len(am.INDISPENSABLES))

    # ── Le depot vise est bien celui publie ─────────────────────────────
    assert "/" in am.DEPOT and am.DEPOT.count("/") == 1, \
        "DEPOT mal forme : %r" % am.DEPOT
    print("  OK  depot vise : %s" % am.DEPOT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Amorceur : conforme.")
