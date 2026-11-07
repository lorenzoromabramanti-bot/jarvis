# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Le juge : quand tu ne fais rien, JARVIS te le fait remarquer
==========================================================================
Seulement si tu le demandes (« JARVIS, juge-moi » ; « arrête de me juger » pour couper) et si la capacité « juge »
est activée. Toutes les 3 minutes : clavier ou souris utilisés dans les 2 dernières minutes (hors YouTube, TikTok…)
= il fait quelque chose, rien de plus. Sinon, un coup d'œil à la webcam et à l'écran : les deux images vont au modèle
LOCAL d'Ollama (gemma4:e4b, le modèle installé qui voit les images). Elles ne sont jamais enregistrées ni envoyées
hors du PC. Deux coups d'œil « il ne fait rien » de suite (≈ 6 min) -> une réplique courte (comme un pote franc), plus
piquante s'il continue, au plus une toutes les 15 minutes, RGB du PC en rouge pendant 20 s (idée de Luna,
@subject_shinji). Rien pendant une partie (mode jeu : jouer, c'est faire quelque chose,
et 6 Go de modèle feraient ramer le jeu), ni la nuit.

    venv\\Scripts\\python.exe _test_juge.py
"""
import base64
import ctypes
import io
import json
import os
import re
import unicodedata
import urllib.request
from datetime import datetime

import config

FICHIER_CONFIG = os.path.join(config.RACINE, "jarvis_config.json")
CLE_ACTIVE = "juge_actif"
ACTIF_JEU = os.path.expanduser(r"~\mode-jeu\actif.json")  # écrit par le mode jeu pendant une partie
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODELE = "gemma4:e4b"
INTERVALLE = 180   # secondes entre deux coups d'œil
SEUIL = 2          # coups d'œil « rien » de suite avant une remarque
PAUSE = 900        # secondes minimum entre deux remarques
HEURES = ("07:30", "22:00")
LARGEUR = 640      # assez pour voir ce qu'il fait ; peu de calcul pour le modèle
CLAVIER_ACTIF = 120  # secondes : une touche ou la souris plus récente = il fait quelque chose, pas besoin de regarder
OCCUPE = {"present": True, "activite": "clavier ou souris", "inactif": False, "remarque": ""}
DUREE_ROUGE = 20     # secondes de RGB rouge (Prisme) pendant une remarque, puis l'effet d'avant revient
# Fenêtre au premier plan qui peut cacher un défilement sans fin, même en bougeant la souris : là, on regarde quand même.
DISTRACTIONS = ("youtube", "shorts", "tiktok", "instagram", "netflix", "twitch", "reddit", "prime video",
                "disney+", "crunchyroll", "snapchat")

# Sans accents, en minuscules (voir _sa). Bornes de mot : « je juge moins » ne doit pas allumer la webcam.
ARRETER = re.compile(r"\b(arrete de me juger|ne me juge plus|desactive (le )?(mode )?juge|stop(pe)? (le )?(mode )?juge|"
                     r"coupe (le )?(mode )?juge)\b")
ACTIVER = re.compile(r"\b(juge[- ]moi|active (le )?(mode )?juge)\b")


def _sa(texte):
    return "".join(c for c in unicodedata.normalize("NFD", (texte or "").lower()) if unicodedata.category(c) != "Mn")


def commande(texte):
    """True : « juge-moi » ; False : « arrête de me juger » ; None : pas une commande du juge."""
    t = _sa(texte)
    if ARRETER.search(t):
        return False
    if ACTIVER.search(t):
        return True
    return None


def actif():
    """Relu à chaque tour : « arrête de me juger » prend effet au coup d'œil suivant, sans redémarrer."""
    try:
        with open(FICHIER_CONFIG, encoding="utf-8") as f:
            return bool(json.load(f).get(CLE_ACTIVE, False))
    except (OSError, ValueError):
        return False


def activer(oui):
    try:
        with open(FICHIER_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg[CLE_ACTIVE] = bool(oui)
    tmp = FICHIER_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FICHIER_CONFIG)


def jeu_en_cours():
    try:
        with open(ACTIF_JEU, encoding="utf-8") as f:
            return bool(json.load(f).get("jeu"))
    except (OSError, ValueError, AttributeError):
        return False


def doit_regarder(maintenant=None):
    h = (maintenant or datetime.now()).strftime("%H:%M")
    return actif() and HEURES[0] <= h < HEURES[1] and not jeu_en_cours()


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def secondes_sans_clavier():
    """Secondes depuis la dernière touche ou le dernier mouvement de souris (Windows), ou None."""
    try:
        info = _LASTINPUTINFO(ctypes.sizeof(_LASTINPUTINFO), 0)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000
    except Exception:
        return None


def fenetre_active():
    """Titre de la fenêtre au premier plan, ou ""."""
    try:
        h = ctypes.windll.user32.GetForegroundWindow()
        tampon = ctypes.create_unicode_buffer(300)
        ctypes.windll.user32.GetWindowTextW(h, tampon, 300)
        return tampon.value
    except Exception:
        return ""


def occupe(sans_clavier, fenetre):
    """Vrai s'il est clairement en train de faire quelque chose : clavier ou souris à l'instant, hors site à défilement.
    Alors pas de webcam ni de modèle (économie : la plupart du temps, il code)."""
    return (sans_clavier is not None and sans_clavier < CLAVIER_ACTIF
            and not any(d in (fenetre or "").lower() for d in DISTRACTIONS))


def jpeg_b64(image_bgr):
    """Image OpenCV (webcam) -> JPEG base64 réduit, ou None."""
    import cv2
    h, w = image_bgr.shape[:2]
    if w > LARGEUR:
        image_bgr = cv2.resize(image_bgr, (LARGEUR, int(h * LARGEUR / w)))
    ok, tampon = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(tampon.tobytes()).decode("ascii") if ok else None


def ecran_b64():
    """L'écran principal en JPEG base64 réduit, ou None (sans écran, le juge regarde seulement la webcam)."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=False).convert("RGB")
        img.thumbnail((LARGEUR, LARGEUR))
        tampon = io.BytesIO()
        img.save(tampon, format="JPEG", quality=70)
        return base64.b64encode(tampon.getvalue()).decode("ascii")
    except Exception:
        return None


def consigne(nom, niveau, contexte=""):
    return (f"Tu es JARVIS, l'assistant de {nom}, un collégien de 12 ans. Tu reçois l'image de sa webcam, "
            "puis celle de son écran s'il y en a une.\n"
            + (f"{contexte}\n" if contexte else "")
            + "Décide s'il ne fait RIEN : il fixe le vide, traîne sur son téléphone, est affalé, n'est pas devant son "
            "écran alors qu'il est là, ou fait défiler des vidéos sans fin. Coder, réviser, faire ses devoirs, lire, "
            "jouer, dessiner, manger, parler à quelqu'un ou téléphoner : il fait quelque chose. Dans le doute, il "
            "fait quelque chose.\n"
            "S'il ne fait rien, écris UNE réplique en français, en le tutoyant, comme un pote franc un peu moqueur "
            "(pas comme une IA) : 4 à 12 mots, un constat puis un ordre, comme « Le téléphone. Pose-le. » ou "
            f"« Trois heures sans bouger. Debout. » ou « Le plafond a pas besoin de toi. Au boulot. ». Piquant {niveau}/3 (1 taquin, 2 sec, "
            "3 théâtral). Jamais méchant, rien sur son physique ni ses vêtements, pas d'émoji ni de markdown : "
            "la réplique est lue à voix haute.\n"
            'Réponds seulement en JSON : {"present": true ou false, "activite": "ce qu\'il fait, en quelques mots", '
            '"inactif": true ou false, "remarque": "la réplique, ou une chaîne vide"}')


def contexte(sans_clavier, fenetre):
    """Ce que le PC sait sans caméra, pour aider le modèle."""
    morceaux = []
    if sans_clavier is not None:
        morceaux.append(f"Dernière touche ou souris : il y a {int(sans_clavier // 60)} min.")
    if fenetre:
        morceaux.append(f"Fenêtre au premier plan : « {fenetre[:80]} ».")
    return " ".join(morceaux)


def _envoyer(corps):
    requete = urllib.request.Request(OLLAMA, json.dumps(corps).encode("utf-8"), {"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=120) as r:
        return json.loads(r.read())["message"]["content"]


def lire(brut):
    """Réponse du modèle -> {present, activite, inactif, remarque}, ou None si illisible.
    « inactif » sans remarque à dire ne compte pas : le juge ne parle jamais pour ne rien dire."""
    try:
        d = json.loads(brut)
    except (TypeError, ValueError):
        m = re.search(r"\{.*\}", brut or "", re.S)
        try:
            d = json.loads(m.group(0)) if m else None
        except ValueError:
            d = None
    if not isinstance(d, dict):
        return None
    remarque = " ".join(str(d.get("remarque") or "").split())[:300]
    present = d.get("present") is True
    return {"present": present, "activite": " ".join(str(d.get("activite") or "").split())[:120],
            "inactif": present and d.get("inactif") is True and bool(remarque), "remarque": remarque}


def regarder(image_bgr, nom, niveau, ecran=None, envoyer=_envoyer, infos=""):
    """Un coup d'œil (webcam + écran) au modèle local. keep_alive 0 : les 6 Go quittent la carte graphique après."""
    images = [b for b in (jpeg_b64(image_bgr), ecran) if b]
    corps = {"model": MODELE, "stream": False, "think": False, "format": "json", "keep_alive": 0,
             "options": {"temperature": 0.8},
             "messages": [{"role": "system", "content": consigne(nom, niveau, infos)},
                          {"role": "user", "content": "Webcam, puis écran :", "images": images}]}
    return lire(envoyer(corps))


class Juge:
    """Compte les coups d'œil « il ne fait rien » de suite ; dit quand parler et avec quel piquant."""

    def __init__(self):
        self.de_suite, self.remarques, self.derniere = 0, 0, None

    def niveau(self):
        return min(self.remarques + 1, 3)

    def observer(self, obs, maintenant):
        """True s'il faut dire obs["remarque"] maintenant. obs None (modèle muet) : rien ne change."""
        if obs is None:
            return False
        if not obs["inactif"]:
            self.de_suite = 0
            if obs["present"]:
                self.remarques = 0  # il s'est remis au travail : la prochaine fois, on repart en taquin
            return False
        self.de_suite += 1
        if self.de_suite < SEUIL or (self.derniere is not None and maintenant - self.derniere < PAUSE):
            return False
        self.de_suite, self.derniere = 0, maintenant
        self.remarques += 1
        return True
