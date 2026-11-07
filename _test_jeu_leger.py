# -*- coding: utf-8 -*-
"""jeu_leger.actif : vrai seulement si le mode jeu tourne ET demande l'allègement."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jeu_leger

d = tempfile.mkdtemp()
f = os.path.join(d, "actif.json")
assert jeu_leger.actif(f) is False, "pas de fichier = pas de jeu"
json.dump({"jeu": "Geometry Dash", "pid": os.getpid(), "jarvis_leger": True}, open(f, "w"))
assert jeu_leger.actif(f) is True
json.dump({"jeu": "Geometry Dash", "pid": os.getpid(), "jarvis_leger": False}, open(f, "w"))
assert jeu_leger.actif(f) is False, "option décochée"
json.dump({"jeu": "Geometry Dash", "pid": 999999, "jarvis_leger": True}, open(f, "w"))
assert jeu_leger.actif(f) is False, "mode jeu mort : actif.json périmé"
open(f, "w").write("{abîmé")
assert jeu_leger.actif(f) is False
print("  OK  JARVIS léger : conforme")
