"""Garde chaque phrase que l'utilisateur dit ou tape à JARVIS (jarvis_phrases.jsonl), pour entraîner un classifieur.

jarvis_conversations.json ne garde que les derniers échanges (100 phrases uniques le 06/11) : trop peu pour
entraîner un classifieur (environ 30 exemples par catégorie). Ici, une ligne JSON par phrase, sans limite :
{"t": "2026-11-06T19:40:00", "texte": "...", "canal": "voix|texte|mobile|discord"}.

Fichier personnel : dans .gitignore. Désactivé par défaut : « garder_phrases »: true dans jarvis_config.json pour l'activer.
Jamais bloquant : une erreur d'écriture est affichée, jamais levée.
"""
import json
import os
import threading
import time

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_phrases.jsonl")
_verrou = threading.Lock()


def noter(texte, canal, actif=True, fichier=None):
    """Ajoute la phrase au journal. Vrai si elle est écrite."""
    texte = " ".join(str(texte or "").split())
    if not actif or not texte:
        return False
    ligne = json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "texte": texte[:1000], "canal": canal},
                       ensure_ascii=False)
    try:
        with _verrou, open(fichier or FICHIER, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
        return True
    except OSError as e:
        print(f"[PHRASES] phrase non gardée : {e}")
        return False
