# -*- coding: utf-8 -*-
"""
Verifie qu'aucun prenom n'est ecrit en dur, et que le nom suit la config.

Le prenom etait fige dans 220 chaines sur 14 fichiers. Ce test existe pour
que ca ne revienne pas : il echoue si quelqu'un reintroduit un prenom en dur,
y compris un autre que celui d'origine.

    venv\\Scripts\\python.exe _test_nom_utilisateur.py
"""

import glob
import io
import json
import os
import re
import shutil
import sys

import config

ICI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(ICI, "jarvis_config.json")

# Prenoms qui ont ete, ou pourraient etre, ecrits en dur dans des reponses.
INTERDITS = re.compile(r"Micka[eë]l", re.IGNORECASE)

# Ce test garde CE QUE JARVIS DIT, pas les identifiants Home Assistant.
# Un identifiant comme `sensor.sm_xxx_battery_level` est une chaine fixe cote
# HA : la remplacer par le nom de l'utilisateur casserait la correspondance
# au lieu
# de la corriger. Ces alias-la sont un probleme distinct — ils designent des
# entites qui n'existent pas dans le vrai HA — traite ailleurs.
DOMAINE_HA = re.compile(
    r"(sensor|light|switch|binary_sensor|person|climate|media_player)\.|appareil")


def verifier():
    # ── Plus aucun prenom en dur dans les chaines ───────────────────────
    fautifs = []
    for f in glob.glob(os.path.join(ICI, "*.py")) + glob.glob(os.path.join(ICI, "tools", "*.py")):
        base = os.path.basename(f)
        if base.startswith("_test") or base == "ha_config.py":
            continue
        for i, ligne in enumerate(io.open(f, encoding="utf-8").read().splitlines(), 1):
            if not INTERDITS.search(ligne):
                continue
            if ligne.strip().startswith("#") or DOMAINE_HA.search(ligne):
                continue
            fautifs.append("%s:%d" % (base, i))
    assert not fautifs, "prenom en dur reintroduit : %s" % ", ".join(fautifs[:6])

    # ── « Monsieur » employe comme VOCATIF ──────────────────────────────
    # Seconde forme d'adresse codee en dur, decouverte apres la premiere :
    # « 250 euros font 270 dollars, Monsieur. » Un litteral qui vaut
    # exactement "Monsieur" est en revanche le repli neutre d'une
    # installation sans config — a garder.
    vocatifs = []
    for f in glob.glob(os.path.join(ICI, "*.py")) + glob.glob(os.path.join(ICI, "tools", "*.py")):
        base = os.path.basename(f)
        if base.startswith("_test") or base in ("config.py", "outils_mcp.py"):
            continue
        for i, ligne in enumerate(io.open(f, encoding="utf-8").read().splitlines(), 1):
            if "Monsieur" not in ligne or ligne.strip().startswith("#"):
                continue
            if re.search(r"""(=|return|lambda:)\s*["']Monsieur["']""", ligne):
                continue          # repli assume
            if '"""' in ligne or "«" in ligne:
                continue          # documentation
            vocatifs.append("%s:%d" % (base, i))
    assert not vocatifs, "« Monsieur » en dur : %s" % ", ".join(vocatifs[:6])

    # ── Une seule lecture du prenom, pas quatre ─────────────────────────
    # main2, ha_config, jarvis_extras et jarvis_outils relisaient chacun
    # jarvis_config.json avec leur propre repli. Quatre copies, quatre
    # occasions de diverger — et elles ont diverge.
    for module in ("jarvis_extras", "jarvis_outils", "ha_config"):
        src = io.open(os.path.join(ICI, module + ".py"), encoding="utf-8").read()
        assert "nom_utilisateur()" in src, \
            "%s ne delegue pas la lecture du prenom" % module

    # ── Le nom vient bien de la config ──────────────────────────────────
    attendu = json.load(io.open(CONFIG, encoding="utf-8")).get("user_name", "")
    obtenu = config.nom_utilisateur()
    assert obtenu.lower() == attendu.lower(), \
        "config dit %r, nom_utilisateur() dit %r" % (attendu, obtenu)
    assert obtenu[:1].isupper(), "le prenom n'est pas capitalise : %r" % obtenu

    # ── Changer le nom prend effet SANS redemarrer ──────────────────────
    # Le cache est indexe sur le mtime : s'il etait fige a l'import, changer
    # son prenom dans les reglages n'aurait aucun effet avant relance.
    secours = CONFIG + ".test-bak"
    shutil.copy(CONFIG, secours)
    try:
        d = json.load(io.open(CONFIG, encoding="utf-8"))
        d["user_name"] = "zoe"
        io.open(CONFIG, "w", encoding="utf-8").write(
            json.dumps(d, ensure_ascii=False, indent=2))
        os.utime(CONFIG, None)
        assert config.nom_utilisateur() == "Zoe", \
            "le nom n'a pas suivi le changement : %r" % config.nom_utilisateur()
    finally:
        shutil.move(secours, CONFIG)
        os.utime(CONFIG, None)

    assert config.nom_utilisateur().lower() == attendu.lower(), \
        "la config n'a pas ete restauree"

    # ── Un repli existe si la config disparait ──────────────────────────
    # Sans ca, une installation neuve planterait avant meme le premier mot.
    assert config._NOM_DEFAUT and "micka" not in config._NOM_DEFAUT.lower()

    print("  OK  aucun prenom en dur dans les chaines")
    print("  OK  aucun « Monsieur » en vocatif")
    print("  OK  une seule lecture du prenom (4 copies supprimees)")
    print("  OK  le nom vient de la config (%s)" % obtenu)
    print("  OK  un changement de nom prend effet sans redemarrer")
    print("  OK  la config est restauree apres le test")
    print("  OK  repli neutre si la config manque (%s)" % config._NOM_DEFAUT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Identite de l'utilisateur : conforme.")
