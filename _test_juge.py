# -*- coding: utf-8 -*-
"""Le juge (juge.py) : commandes vocales, conditions, lecture du modèle, rythme des remarques. Sans webcam ni Ollama.

    venv\\Scripts\\python.exe _test_juge.py
"""
import json
import os
import tempfile
from datetime import datetime

import numpy as np

import juge

# --- Commandes : bornes de mot, accents, « arrêter » avant « activer »
assert juge.commande("JARVIS, juge-moi") is True and juge.commande("juge moi stp") is True
assert juge.commande("Active le mode juge") is True and juge.commande("active le juge") is True
assert juge.commande("Arrête de me juger !") is False and juge.commande("désactive le juge") is False
assert juge.commande("ne me juge plus") is False and juge.commande("stop le juge") is False
assert juge.commande("je juge moins vite que toi") is None, "« juge moins » n'est pas « juge-moi »"
assert juge.commande("le juge a rendu son verdict") is None and juge.commande("") is None and juge.commande(None) is None

# --- Activé ou non, partie en cours, heures : relus à chaque tour, dans des fichiers temporaires
with tempfile.TemporaryDirectory() as t:
    vrai_cfg, vrai_jeu = juge.FICHIER_CONFIG, juge.ACTIF_JEU
    juge.FICHIER_CONFIG, juge.ACTIF_JEU = os.path.join(t, "cfg.json"), os.path.join(t, "actif.json")
    try:
        midi = datetime(2026, 10, 24, 12, 0)
        assert not juge.actif() and not juge.doit_regarder(midi), "désactivé tant qu'on ne l'a pas demandé"
        with open(juge.FICHIER_CONFIG, "w", encoding="utf-8") as f:
            json.dump({"autre_reglage": 1}, f)
        juge.activer(True)
        with open(juge.FICHIER_CONFIG, encoding="utf-8") as f:
            assert json.load(f) == {"autre_reglage": 1, "juge_actif": True}, "les autres réglages restent"
        assert juge.doit_regarder(midi)
        assert not juge.doit_regarder(datetime(2026, 10, 24, 23, 0)) and not juge.doit_regarder(datetime(2026, 10, 24, 6, 0))
        with open(juge.ACTIF_JEU, "w", encoding="utf-8") as f:
            json.dump({"jeu": "Geometry Dash", "pid": 1}, f)
        assert juge.jeu_en_cours() and not juge.doit_regarder(midi), "pendant une partie : rien"
        os.remove(juge.ACTIF_JEU)
        juge.activer(False)
        assert not juge.doit_regarder(midi)
    finally:
        juge.FICHIER_CONFIG, juge.ACTIF_JEU = vrai_cfg, vrai_jeu

# --- Lecture de la réponse du modèle : JSON propre, entouré de texte, ou n'importe quoi
assert juge.lire('{"present": true, "activite": "fixe le plafond", "inactif": true, "remarque": "Le plafond vous remercie."}') == \
    {"present": True, "activite": "fixe le plafond", "inactif": True, "remarque": "Le plafond vous remercie."}
assert juge.lire('Voici : {"present": true, "activite": "code", "inactif": false, "remarque": ""} fin')["inactif"] is False
assert juge.lire("pas du json") is None and juge.lire(None) is None and juge.lire("[1, 2]") is None
assert juge.lire('{"present": true, "inactif": true, "remarque": ""}')["inactif"] is False, "rien à dire : on ne parle pas"
assert juge.lire('{"present": false, "inactif": true, "remarque": "x"}')["inactif"] is False, "personne : pas de remarque"
assert juge.lire('{"present": "oui", "inactif": "oui", "remarque": "x"}')["inactif"] is False, "seul true compte"

# --- Rythme : 2 « rien » de suite, puis 15 min de pause, piquant qui monte, retour à zéro s'il s'y remet
RIEN = {"present": True, "activite": "téléphone", "inactif": True, "remarque": "Fascinant, ce téléphone."}
TRAVAIL = {"present": True, "activite": "code", "inactif": False, "remarque": ""}
ABSENT = {"present": False, "activite": "", "inactif": False, "remarque": ""}
j = juge.Juge()
assert j.niveau() == 1 and not j.observer(RIEN, 0) and j.observer(RIEN, 180), "remarque au 2e coup d'œil"
assert j.niveau() == 2
assert not j.observer(RIEN, 360) and not j.observer(RIEN, 540) and not j.observer(RIEN, 1000), "15 min de pause"
assert j.observer(RIEN, 1080) and j.niveau() == 3 and j.remarques == 2
assert not j.observer(None, 1100) and j.remarques == 2, "modèle muet : rien ne change"
assert not j.observer(ABSENT, 1200) and j.niveau() == 3, "absent : le piquant reste"
assert not j.observer(TRAVAIL, 1300) and j.niveau() == 1 and j.de_suite == 0, "il s'y remet : on repart en taquin"

# --- Un vrai coup d'œil, avec un faux Ollama : modèle local, sans réflexion, déchargé après, deux images réduites
envoye = {}


def faux_ollama(corps):
    envoye.update(corps)
    return json.dumps(RIEN)


image = np.zeros((720, 1280, 3), dtype=np.uint8)
obs = juge.regarder(image, "Alex", 2, ecran="QUJD", envoyer=faux_ollama)
assert obs == RIEN, obs
assert envoye["model"] == "gemma4:e4b" and envoye["keep_alive"] == 0 and envoye["think"] is False and envoye["format"] == "json"
images = envoye["messages"][1]["images"]
assert len(images) == 2 and images[1] == "QUJD", "webcam puis écran"
import base64, cv2  # noqa: E401,E402
reduite = cv2.imdecode(np.frombuffer(base64.b64decode(images[0]), np.uint8), cv2.IMREAD_COLOR)
assert reduite.shape[1] == juge.LARGEUR, reduite.shape
assert "Alex" in envoye["messages"][0]["content"] and "Piquant 2/3" in envoye["messages"][0]["content"]
assert "4 à 12 mots" in envoye["messages"][0]["content"], "répliques courtes, comme Luna"
assert juge.regarder(image, "L", 1, ecran=None, envoyer=faux_ollama) and len(envoye["messages"][1]["images"]) == 1

# --- Clavier et fenêtre : il tape = occupé (ni webcam ni modèle), sauf sur un site à défilement sans fin
assert juge.occupe(30, "main2.py - Visual Studio Code") and not juge.occupe(300, "main2.py - Visual Studio Code")
assert not juge.occupe(5, "Shorts - YouTube - Opera") and not juge.occupe(5, "TikTok - Make Your Day")
assert not juge.occupe(None, "") and juge.occupe(0, "")
assert juge.contexte(185, "YouTube") == "Dernière touche ou souris : il y a 3 min. Fenêtre au premier plan : « YouTube »."
assert juge.contexte(None, "") == ""
juge.regarder(image, "L", 1, envoyer=faux_ollama, infos=juge.contexte(600, "Netflix"))
assert "il y a 10 min" in envoye["messages"][0]["content"] and "Netflix" in envoye["messages"][0]["content"]
s = juge.secondes_sans_clavier()
assert s is None or s >= 0, s
assert isinstance(juge.fenetre_active(), str)
j = juge.Juge()
j.observer(RIEN, 0)
assert not j.observer(juge.OCCUPE, 180) and j.de_suite == 0 and j.niveau() == 1, "il tape : on repart de zéro"

print("OK : le juge est vérifié")
