# -*- coding: utf-8 -*-
"""
Verifie que JARVIS peut au moins DEMARRER hors de Windows.

Ce test ne prouve pas que tout fonctionne sur macOS ou Linux — il n'y a pas
de machine pour le dire. Il verifie la seule chose verifiable d'ici : qu'aucun
module ne s'arrete a l'import. Un import qui echoue tue JARVIS avant qu'il
puisse afficher la moindre explication ; une fonctionnalite absente, elle, se
signale et le reste continue.

Prealable a l'installeur multi-systemes : inutile d'installer proprement un
programme qui ne se lance pas.

    venv\\Scripts\\python.exe _test_portabilite.py
"""

import ast
import glob
import io
import os
import sys

import config

ICI = os.path.dirname(os.path.abspath(__file__))

# Modules qui n'existent QUE sous Windows.
WINDOWS = {"winreg", "win32api", "win32gui", "win32con", "win32com",
           "win32process", "win32clipboard", "pywintypes", "winshell",
           "win32file", "win32event", "win32security", "win32ui", "pythoncom"}


def _fichiers():
    for f in sorted(glob.glob(os.path.join(ICI, "*.py"))
                    + glob.glob(os.path.join(ICI, "tools", "*.py"))):
        if not os.path.basename(f).startswith("_test"):
            yield f


def _protege(arbre):
    """Ids des noeuds sous un try ou dans une fonction : imports differes."""
    ids = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Try, ast.FunctionDef, ast.AsyncFunctionDef)):
            for x in ast.walk(n):
                ids.add(id(x))
    return ids


def verifier():
    durs, windll = [], []
    for f in _fichiers():
        try:
            arbre = ast.parse(io.open(f, encoding="utf-8").read())
        except SyntaxError as e:
            raise AssertionError("%s ne compile pas : %s" % (os.path.basename(f), e))
        differes = _protege(arbre)
        for n in ast.walk(arbre):
            noms = ([a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import)
                    else [(n.module or "").split(".")[0]] if isinstance(n, ast.ImportFrom)
                    else [])
            for m in noms:
                if m in WINDOWS and id(n) not in differes:
                    durs.append("%s:%d %s" % (os.path.basename(f), n.lineno, m))
            # ctypes.windll evalue au chargement du module : meme effet
            # qu'un import Windows en dur.
            if (isinstance(n, ast.Attribute) and n.attr == "windll"
                    and id(n) not in differes):
                windll.append("%s:%d" % (os.path.basename(f), n.lineno))

    assert not durs, ("import Windows inconditionnel — JARVIS ne demarrerait "
                      "pas ailleurs : %s" % ", ".join(durs))
    assert not windll, ("ctypes.windll evalue a l'import : %s" % ", ".join(windll))
    print("  OK  aucun import Windows inconditionnel")
    print("  OK  aucun ctypes.windll evalue au chargement")

    # ── Le substitut explique au lieu de laisser un NoneType ────────────
    faux = config.ModuleAbsent("winreg", "le registre est propre a Windows")
    assert bool(faux) is False, "`if winreg:` doit repondre non sans lever"
    for essai in (lambda: faux.OpenKey("x"), lambda: faux()):
        try:
            essai()
            raise AssertionError("le substitut n'a pas leve")
        except RuntimeError as e:
            texte = str(e)
            assert "winreg" in texte and "registre" in texte, \
                "l'erreur n'explique rien : %r" % texte
    print("  OK  le substitut nomme le module et la raison")

    # ── config sait dire ce qui manque ──────────────────────────────────
    caps = config.capacites()
    assert caps, "aucune capacite listee"
    assert "ollama_installe" in caps and "ollama_repond" in caps, \
        "installe et repond doivent rester distincts"
    manques = config.fonctionnalites_indisponibles()
    print("  OK  %d capacites inventoriees, %d fonctionnalite(s) degradee(s)"
          % (len(caps), len(manques)))
    for nom, absents in manques:
        print("      %-28s manque : %s" % (nom, ", ".join(absents)))

    # ── Les donnees ne doivent pas vivre dans le dossier d'installation ─
    # Sous Program Files, Windows refuse l'ecriture sans elevation. Ca marche
    # aujourd'hui parce que cette installation est permissive.
    assert str(config.DOSSIER_DONNEES) != str(config.RACINE), \
        "les donnees utilisateur pointent sur le dossier d'installation"
    print("  OK  donnees utilisateur separees du code (%s)"
          % config.DOSSIER_DONNEES)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Portabilite : le demarrage ne depend plus de Windows.")
