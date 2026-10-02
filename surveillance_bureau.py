# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Détection automatique de présence (webcam)
=============================================================
Désactivée par défaut — c'est une caméra de surveillance, pas une feature
anodine. À activer explicitement (jarvis_config.json:
"surveillance_bureau_active": true, ou commande vocale/Discord "active la
surveillance").

Détection locale (Haar cascade OpenCV) — pas d'appel modèle par frame :
un appel Gemini Vision toutes les quelques secondes coûterait cher et
serait lent, alors que la seule question posée en boucle est binaire
("y a-t-il quelqu'un ?"). Gemini Vision n'intervient qu'UNE fois, sur la
frame retenue, pour la description envoyée avec la photo.

PLAFOND CONNU (ponytail) : Haar cascade frontal — détecte un visage de
face, pas de profil ni de dos. Filet raisonnable pour un bureau (on
regarde généralement l'écran/la caméra en s'approchant), pas une garantie
de détecter toute présence.
"""

import json
import os
import time

try:
    import cv2
except ImportError:
    cv2 = None

FICHIER_CONFIG = "jarvis_config.json"
CLE_ACTIVE = "surveillance_bureau_active"

INTERVALLE_VERIFICATION = 60       # secondes entre deux captures
DEBOUNCE_ALERTE = 300              # secondes minimum entre deux alertes

_dernier_visage_detecte = 0.0

_detecteur = None
if cv2 is not None:
    _chemin_cascade = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    if os.path.exists(_chemin_cascade):
        _detecteur = cv2.CascadeClassifier(_chemin_cascade)


def surveillance_active():
    """Lit le flag depuis jarvis_config.json à chaque appel — pas de cache,
    pour qu'un /activer ou /désactiver prenne effet au cycle suivant, pas
    au prochain redémarrage."""
    try:
        with open(FICHIER_CONFIG, encoding="utf-8") as f:
            return bool(json.load(f).get(CLE_ACTIVE, False))
    except Exception:
        return False


def activer(actif):
    try:
        with open(FICHIER_CONFIG, encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = {}
    config[CLE_ACTIVE] = bool(actif)
    with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def detecter_visage(frame):
    """True si au moins un visage est détecté dans cette frame OpenCV."""
    if _detecteur is None or frame is None:
        return False
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    visages = _detecteur.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    return len(visages) > 0


def alerte_due(maintenant=None):
    """Le debounce est-il passé depuis la dernière alerte envoyée ?"""
    maintenant = maintenant if maintenant is not None else time.time()
    return (maintenant - _dernier_visage_detecte) >= DEBOUNCE_ALERTE


def marquer_alerte_envoyee(maintenant=None):
    global _dernier_visage_detecte
    _dernier_visage_detecte = maintenant if maintenant is not None else time.time()
