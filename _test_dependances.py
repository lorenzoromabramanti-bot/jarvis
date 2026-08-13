# -*- coding: utf-8 -*-
"""
Verifie que tout module importe est declare quelque part.

POURQUOI CE TEST EXISTE
Neuf paquets etaient importes par le code sans figurer dans
requirements.txt. Une installation neuve suivant le README aurait echoue —
et personne ne s'en apercevait, parce que la machine de developpement les
avait tous depuis longtemps. Le pire, edge_tts, est importe SANS PROTECTION
dans main2.py : son absence empeche JARVIS de demarrer.

Ce test regarde ce que le code importe VRAIMENT, pas ce qu'on croit qu'il
importe. Trois sorties acceptables pour un module :

  1. declare dans requirements.txt          -> installe par defaut
  2. declare dans requirements-voix.txt     -> gros, facultatif, assume
  3. inscrit dans FACULTATIFS ci-dessous    -> son import est protege ET
                                               son absence se signale

Tout le reste est une erreur.

    venv\\Scripts\\python.exe _test_dependances.py
"""

import ast
import glob
import io
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))

# Nom d'import -> nom du paquet PyPI, quand ils different.
PAQUET = {
    "PIL": "pillow", "cv2": "opencv-python", "dotenv": "python-dotenv",
    "speech_recognition": "SpeechRecognition", "google": "google-genai",
    "googleapiclient": "google-api-python-client",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "win32api": "pywin32", "win32com": "pywin32", "win32con": "pywin32",
    "win32gui": "pywin32", "pyaudio": "PyAudio", "webview": "pywebview",
    "edge_tts": "edge-tts", "nemo": "nemo_toolkit", "pyarrow": "pyarrow",
    "screen_brightness_control": "screen-brightness-control",
    "youtube_transcript_api": "youtube-transcript-api",
}

# Modules dont l'absence est PREVUE. Chacun doit avoir son import protege —
# le test le verifie, il ne se contente pas de la promesse.
FACULTATIFS = {
    "pygrabber": "enumeration des cameras",
    "winshell":  "raccourcis Windows",
    "backports": "dependance transitive de setuptools",
    "comfy_client": "module local, pas un paquet",
}


def _modules_importes():
    """{module: [(fichier, ligne, protege)]} pour tout le projet."""
    stdlib = set(sys.stdlib_module_names)
    locaux = {os.path.basename(f)[:-3]
              for f in glob.glob(os.path.join(ICI, "*.py"))} | {"tools"}
    trouves = {}
    fichiers = (glob.glob(os.path.join(ICI, "*.py"))
                + glob.glob(os.path.join(ICI, "tools", "*.py")))
    for f in fichiers:
        base = os.path.basename(f)
        if base.startswith("_test"):
            continue
        try:
            arbre = ast.parse(io.open(f, encoding="utf-8").read())
        except SyntaxError:
            continue
        differes = set()
        for n in ast.walk(arbre):
            if isinstance(n, (ast.Try, ast.FunctionDef, ast.AsyncFunctionDef)):
                for x in ast.walk(n):
                    differes.add(id(x))
        for n in ast.walk(arbre):
            noms = ([a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import)
                    else [(n.module or "").split(".")[0]] if isinstance(n, ast.ImportFrom)
                    else [])
            for m in noms:
                if not m or m in stdlib or m in locaux:
                    continue
                trouves.setdefault(m, []).append((base, n.lineno, id(n) in differes))
    return trouves


def _declares(fichier):
    chemin = os.path.join(ICI, fichier)
    if not os.path.exists(chemin):
        return set()
    noms = set()
    for ligne in io.open(chemin, encoding="utf-8"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        noms.add(re.split(r"[=<>~\[!]", ligne)[0].strip().lower())
    return noms


def verifier():
    importes = _modules_importes()
    base = _declares("requirements.txt")
    voix = _declares("requirements-voix.txt")
    assert base, "requirements.txt est vide ou introuvable"
    assert voix, "requirements-voix.txt est vide ou introuvable"

    non_declares = []
    for module, sites in sorted(importes.items()):
        if module in FACULTATIFS:
            continue
        paquet = PAQUET.get(module, module).lower()
        if paquet in base or module.lower() in base:
            continue
        if paquet in voix or module.lower() in voix:
            continue
        non_declares.append("%s (paquet %s, vu dans %s)"
                            % (module, paquet, sites[0][0]))
    assert not non_declares, ("module importe mais declare nulle part :\n    "
                              + "\n    ".join(non_declares))
    print("  OK  %d modules tiers, tous declares" % len(importes))

    # ── Un module facultatif DOIT etre importe de facon protegee ────────
    # Sinon son absence empeche JARVIS de demarrer, et l'excuse « c'est
    # facultatif » devient fausse.
    mal_protges = []
    for module in FACULTATIFS:
        for fichier, ligne, protege in importes.get(module, []):
            if not protege:
                mal_protges.append("%s:%d %s" % (fichier, ligne, module))
    assert not mal_protges, ("declare facultatif mais importe sans protection : %s"
                             % ", ".join(mal_protges))
    print("  OK  %d modules facultatifs, tous importes sous protection"
          % len(FACULTATIFS))

    # ── Les gros paquets ne doivent pas etre imposes ────────────────────
    # torch et nemo pesent plusieurs gigaoctets. Les remettre dans
    # requirements.txt ferait payer ce telechargement a quelqu'un qui veut
    # seulement taper ses demandes.
    for lourd in ("torch", "nemo_toolkit"):
        assert lourd not in base, \
            "%s est revenu dans requirements.txt (plusieurs Go imposes)" % lourd
        assert lourd in voix, "%s a disparu de requirements-voix.txt" % lourd
    print("  OK  torch et nemo restent facultatifs")

    # ── Aucune version CUDA epinglee ────────────────────────────────────
    # « torch==2.11.0+cu128 » fait echouer l'installation sur toute machine
    # sans ce CUDA exact, et sur macOS et Linux.
    for fichier in ("requirements.txt", "requirements-voix.txt"):
        contenu = io.open(os.path.join(ICI, fichier), encoding="utf-8").read()
        for ligne in contenu.splitlines():
            if ligne.strip().startswith("#"):
                continue
            assert "+cu" not in ligne, \
                "%s epingle une compilation CUDA : %r" % (fichier, ligne.strip())
    print("  OK  aucune compilation CUDA epinglee")

    # ── Ce que le README promet doit exister ────────────────────────────
    readme = io.open(os.path.join(ICI, "README.md"), encoding="utf-8").read()
    for fichier in re.findall(r"`([\w.\-]+\.(?:txt|example|py))`", readme):
        if fichier.startswith("_test"):
            continue
        assert os.path.exists(os.path.join(ICI, fichier)), \
            "le README cite %s, qui n'existe pas" % fichier
    print("  OK  les fichiers cites par le README existent")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Dependances : conforme.")
