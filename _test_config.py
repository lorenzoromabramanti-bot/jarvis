r"""
.env.example et config.REGLAGES doivent lister exactement les memes
variables : l'installeur propose REGLAGES, l'utilisateur copie .env.example.
Si l'un diverge, une variable devient introuvable d'un des deux cotes.

    venv\Scripts\python.exe _test_config.py
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

modele = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.example"),
                 encoding="utf-8").read()
dans_exemple = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", modele, re.M))
dans_reglages = {cle for cles, *_ in config.REGLAGES for cle in cles}

manque_exemple = sorted(dans_reglages - dans_exemple)
manque_reglages = sorted(dans_exemple - dans_reglages)
if manque_exemple:
    print("ECHEC absentes de .env.example :", manque_exemple)
if manque_reglages:
    print("ECHEC absentes de config.REGLAGES :", manque_reglages)
vides = [l for l in modele.splitlines() if re.match(r"^[A-Z][A-Z0-9_]*=\S", l)]
if vides:
    print("ECHEC .env.example contient des valeurs :", [l.split("=")[0] for l in vides])
if manque_exemple or manque_reglages or vides:
    sys.exit(1)
print("OK %d variables, identiques des deux cotes, toutes vides" % len(dans_reglages))
