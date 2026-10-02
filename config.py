# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Configuration et emplacements, par système
========================================================
Point unique où l'on décide OÙ vont les choses et CE QUI est disponible selon
le système. Préalable à un installeur qui vise Windows, macOS et Linux.

POURQUOI CE FICHIER EXISTE
Le code du projet est déjà largement portable : il résout ses chemins par
`os.path.dirname(__file__)`, et seules quatre occurrences de « Program Files »
subsistent hors du venv. Le vrai obstacle n'est pas le chemin d'installation,
c'est ailleurs :

    PowerShell   main2.py, vpn.py
    winget       main2.py
    taskkill     main2.py, vpn.py
    winreg       4 fichiers
    win32 / pywin32   4 fichiers
    pyautogui    5 fichiers
    WebView2     la fenêtre pywebview

Ces morceaux ne se « portent » pas : ils se remplacent, ou se désactivent
proprement. Ce module dit lesquels sont disponibles ici, pour que le code
puisse le demander au lieu de le supposer — et pour qu'une fonctionnalité
absente le DISE, au lieu d'échouer en vol.

DONNÉES UTILISATEUR HORS DU DOSSIER D'INSTALLATION
Aujourd'hui la config, les conversations et le vault vivent dans
`C:\\Program Files\\JARVIS\\`, un emplacement où Windows refuse l'écriture aux
processus non élevés. Ça marche parce que l'installation actuelle est
permissive ; sur une machine propre, ça casserait. `DOSSIER_DONNEES` place ces
fichiers là où le système attend qu'ils soient.

MIGRATION : ce module n'impose rien. `chemin_donnees()` renvoie l'ancien
emplacement tant que le fichier y existe, le nouveau sinon. Rien ne bouge
sans décision explicite.
"""

import os
import platform
import shutil
import sys
from pathlib import Path

# ── Système ──────────────────────────────────────────────────────────────

# ── Version ──────────────────────────────────────────────────────────────
# Source unique. Il en existait deux, divergentes et toutes deux fausses :
# l'en-tête du HUD affichait « v0.4.2 » en dur (héritage du gabarit openclaw)
# et package.json disait « 1.0.3 ». Aucune ne décrivait JARVIS.
#
# Un numéro de version n'est pas décoratif : sans lui, la vérification de
# mise à jour n'a rien à comparer. Il doit monter à chaque publication.
VERSION = "1.2.0"

SYSTEME = platform.system()            # 'Windows' | 'Darwin' | 'Linux'
EST_WINDOWS = SYSTEME == "Windows"
EST_MACOS = SYSTEME == "Darwin"
EST_LINUX = SYSTEME == "Linux"

RACINE = Path(__file__).resolve().parent


def _dossier_donnees():
    """
    Où écrire config, conversations, vault. Convention de chaque système.

        Windows  %APPDATA%\\JARVIS
        macOS    ~/Library/Application Support/JARVIS
        Linux    $XDG_CONFIG_HOME/jarvis, sinon ~/.config/jarvis
    """
    if EST_WINDOWS:
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / "JARVIS"
    if EST_MACOS:
        return Path.home() / "Library" / "Application Support" / "JARVIS"
    return Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "jarvis"


DOSSIER_DONNEES = _dossier_donnees()


def _dossier_documents():
    """
    Où vont les contenus que l'utilisateur OUVRE lui-même.

    Distinct de DOSSIER_DONNEES : la config et les caches n'ont rien à faire
    sous les yeux de quelqu'un, alors qu'un vault Obsidian doit se trouver là
    où on pense à le chercher — et où Obsidian propose de l'ouvrir. Mettre un
    vault dans %APPDATA% reviendrait à le cacher.
    """
    if EST_WINDOWS:
        # OneDrive redirige souvent Documents ; on suit la redirection plutôt
        # que de créer un second dossier orphelin à côté.
        for var in ("OneDrive", "OneDriveConsumer"):
            base = os.environ.get(var)
            if base and (Path(base) / "Documents").is_dir():
                return Path(base) / "Documents" / "JARVIS"
        return Path.home() / "Documents" / "JARVIS"
    if EST_MACOS:
        return Path.home() / "Documents" / "JARVIS"
    return Path.home() / "Documents" / "JARVIS"


DOSSIER_DOCUMENTS = _dossier_documents()


def chemin_donnees(nom, creer_dossier=False):
    """
    Emplacement d'un fichier de données.

    Renvoie l'ancien emplacement (à côté du code) TANT QUE le fichier s'y
    trouve — une mise à jour ne doit pas faire disparaître les données de
    quelqu'un. Le nouvel emplacement ne sert qu'aux fichiers qui n'existent
    pas encore, donc aux installations neuves.
    """
    ancien = RACINE / nom
    if ancien.exists():
        return ancien
    nouveau = DOSSIER_DONNEES / nom
    if creer_dossier:
        nouveau.parent.mkdir(parents=True, exist_ok=True)
    return nouveau


# ── Modules absents selon le système ─────────────────────────────────────

class ModuleAbsent:
    """
    Remplace un module qui n'existe pas ici, et DIT pourquoi au premier usage.

    Trois fichiers importaient `winreg` sans condition : sur macOS ou Linux,
    JARVIS s'arrêtait à l'import, avant d'avoir pu afficher quoi que ce soit.
    Le remplacer par `None` aurait déplacé le problème sans le résoudre —
    `winreg.OpenKey(...)` produit alors « 'NoneType' object has no attribute
    'OpenKey' », qui n'apprend rien à personne.

    Ce substitut laisse l'import réussir et lève, au premier accès réel, une
    erreur qui nomme le module, le système et la raison. Les 61 sites
    d'utilisation répartis dans le projet n'ont pas à être modifiés un par un.
    """

    def __init__(self, nom, raison=""):
        object.__setattr__(self, "_nom", nom)
        object.__setattr__(self, "_raison", raison)

    def _plainte(self):
        # Le systeme n'est PAS ajoute d'office : ce substitut ne sert pas
        # qu'aux modules Windows. « comfy_client n'est pas disponible sur
        # Windows : le dossier video_gen/ n'est pas dans ce depot » melangeait
        # deux causes sans rapport. La raison porte le systeme quand il
        # compte — « le registre est propre a Windows » le dit deja.
        return RuntimeError(
            "%s n'est pas disponible ici%s"
            % (self._nom, " : " + self._raison if self._raison else
               " (systeme : %s)" % SYSTEME))

    def __getattr__(self, attribut):
        raise self._plainte()

    def __call__(self, *a, **k):
        raise self._plainte()

    def __bool__(self):
        return False           # `if winreg:` répond non, sans lever

    def __repr__(self):
        return "<absent: %s>" % self._nom


def module_ou_substitut(nom, raison=""):
    """
    Importe le module, ou renvoie un substitut qui expliquera son absence.

    BaseException et non ImportError : un module peut appeler sys.exit() à
    l'import (pyautogui le fait sur Linux sans tkinter), ce qui tuerait le
    processus au lieu de produire un substitut.
    """
    try:
        return __import__(nom)
    except KeyboardInterrupt:
        raise
    except BaseException:
        return ModuleAbsent(nom, raison)


def api_windows(nom_dll):
    """user32, kernel32... ou un substitut hors Windows."""
    if not EST_WINDOWS:
        return ModuleAbsent(nom_dll, "API Windows")
    import ctypes
    try:
        return getattr(ctypes.windll, nom_dll)
    except Exception as e:
        return ModuleAbsent(nom_dll, repr(e))


# ── Identité de l'utilisateur ────────────────────────────────────────────
# Le prénom était écrit EN DUR dans 220 chaînes réparties sur 14 fichiers.
# JARVIS s'adressait donc à tout le monde sous le même prénom, alors
# que get_user_name() existait et lisait la vraie valeur — presque personne
# ne l'appelait. Invisible tant qu'une seule personne l'utilise ; intenable
# dès qu'il y en a deux.
#
# Relu depuis le fichier plutôt que figé à l'import : changer son nom dans
# les réglages doit prendre effet sans redémarrer. Le cache sur mtime évite
# de relire à chaque phrase prononcée.

_NOM_DEFAUT = "Monsieur"
_nom_cache = (None, 0.0)


def nom_utilisateur():
    """Le prénom à employer pour s'adresser à l'utilisateur."""
    global _nom_cache
    chemin = RACINE / "jarvis_config.json"
    try:
        mtime = chemin.stat().st_mtime
    except OSError:
        return _NOM_DEFAUT
    valeur, vu = _nom_cache
    if valeur is not None and vu == mtime:
        return valeur
    try:
        import json
        with open(chemin, encoding="utf-8") as f:
            brut = (json.load(f).get("user_name") or "").strip()
        nom = (brut[:1].upper() + brut[1:]) if brut else _NOM_DEFAUT
    except Exception:
        nom = _NOM_DEFAUT
    _nom_cache = (nom, mtime)
    return nom


def racine_inscriptible():
    """
    Le dossier d'installation accepte-t-il l'écriture ?

    Sous Program Files sans élévation, la réponse est non — et c'est là que
    JARVIS écrit aujourd'hui sa config et ses conversations.
    """
    try:
        temoin = RACINE / ".ecriture_test"
        temoin.write_text("x", encoding="utf-8")
        temoin.unlink()
        return True
    except Exception:
        return False


# ── Écran : dimensions LOGIQUES, pour positionner les fenêtres ───────────

def _resolution_physique():
    """(largeur, hauteur) en vrais pixels, lus depuis le pilote d'affichage.

    EnumDisplaySettings et pas GetSystemMetrics : le second ment selon la
    « conscience DPI » du processus qui appelle (il renvoie la taille
    virtualisée dans un processus non conscient), alors que le mode
    d'affichage courant vient du pilote et vaut la même chose partout.
    Même résultat depuis un processus conscient du DPI ou non.
    """
    if not EST_WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes

    class _DEVMODE(ctypes.Structure):
        _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
                    ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
                    ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                    ("dmOrientation", ctypes.c_short), ("dmPaperSize", ctypes.c_short),
                    ("dmPaperLength", ctypes.c_short), ("dmPaperWidth", ctypes.c_short),
                    ("dmScale", ctypes.c_short), ("dmCopies", ctypes.c_short),
                    ("dmDefaultSource", ctypes.c_short), ("dmPrintQuality", ctypes.c_short),
                    ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                    ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
                    ("dmCollate", ctypes.c_short), ("dmFormName", wintypes.WCHAR * 32),
                    ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
                    ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD),
                    ("dmDisplayFlags", wintypes.DWORD), ("dmDisplayFrequency", wintypes.DWORD),
                    ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
                    ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
                    ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
                    ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]

    dm = _DEVMODE()
    dm.dmSize = ctypes.sizeof(_DEVMODE)
    if not ctypes.windll.user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
        return None
    if not dm.dmPelsWidth or not dm.dmPelsHeight:
        return None
    return int(dm.dmPelsWidth), int(dm.dmPelsHeight)


def ecran_logique(defaut=(1920, 1080)):
    """
    (largeur, hauteur) de l'écran en pixels LOGIQUES — l'unité qu'attend
    pywebview pour `width`/`height`/`x`/`y` (il les multiplie lui-même par
    l'échelle avant de les donner à WinForms, voir platforms/winforms.py).

    POURQUOI CETTE FONCTION EXISTE
    Bug réel : le HUD et la barre rapide se calculaient depuis les pixels
    PHYSIQUES (screeninfo, ou webview.screens dans un processus conscient
    du DPI). Exemple : à 225 %, 4096 pixels physiques valent 1820 logiques ;
    pywebview remultipliait par 2,25 et demandait une fenêtre de 7832 px de
    large, positionnée hors de l'écran — contenu coupé à droite.

    Ni screeninfo ni webview.screens ne sont fiables ici : les deux
    renvoient du physique ou du logique SELON la conscience DPI du
    processus, qui diffère entre un test isolé et JARVIS lancé. Pire,
    `webview.screens[0].scale` vaut 2,25 dans un test isolé mais 1,0 dans
    JARVIS lancé — alors que pywebview applique bel et bien 2,25 à la
    fenêtre (mesuré : une barre demandée à 720 fait 1620 px réels). Se
    fier à cette échelle-là redonnait exactement le bug d'origine.

    On lit donc l'échelle dans le registre (le réglage d'affichage de
    Windows, une valeur stockée : elle ne dépend d'aucun contexte
    d'exécution) et la résolution dans le pilote. Deux sources stables,
    identiques quel que soit le processus qui les interroge.
    """
    physique = _resolution_physique()
    if not physique:
        return defaut
    echelle = _echelle_affichage()
    return int(physique[0] / echelle), int(physique[1] / echelle)


def _echelle_affichage():
    """Facteur d'agrandissement de Windows (1,0 = 100 % ; 2,25 = 225 %).

    Lu dans le registre plutôt que via les API DPI : GetDpiForMonitor et
    consorts répondent 96 ppp à un processus « non conscient du DPI » et
    la vraie valeur à un processus conscient. Le réglage stocké, lui, est
    le même pour tout le monde.
    """
    if not EST_WINDOWS:
        return 1.0
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Control Panel\Desktop\WindowMetrics") as cle:
            ppp, _ = winreg.QueryValueEx(cle, "AppliedDPI")
        echelle = float(ppp) / 96.0
        # Garde-fou : une valeur aberrante (registre absent, clé exotique)
        # ne doit pas produire une fenêtre minuscule ou géante.
        return echelle if 0.5 <= echelle <= 6.0 else 1.0
    except Exception:
        return 1.0


# ── Capacités : ce qui est réellement disponible ici ─────────────────────

def _port_ouvert(port, hote="127.0.0.1", delai=0.3):
    import socket
    s = socket.socket()
    s.settimeout(delai)
    try:
        return s.connect_ex((hote, port)) == 0
    finally:
        s.close()


def _commande(nom):
    return shutil.which(nom) is not None


def _importable(module):
    """
    Le module se charge-t-il ici ?

    On attrape BaseException, pas seulement Exception, et ce n'est pas de la
    prudence excessive : certains paquets appellent sys.exit() À L'IMPORT.
    Mesuré sur Ubuntu 26.04 sans tkinter, `import pyautogui` lève SystemExit
    — qui n'hérite PAS de Exception. Le processus entier mourait donc en
    silence au milieu de capacites(), et comme cette fonction est appelée par
    l'installeur, le catalogue et config lui-même, JARVIS ne démarrait pas.

    KeyboardInterrupt reste transmis : interrompre doit toujours interrompre.
    """
    try:
        __import__(module)
        return True
    except KeyboardInterrupt:
        raise
    except BaseException:
        return False


def capacites():
    """
    Inventaire de ce qui marche sur CETTE machine.

    Le code doit interroger ce dictionnaire plutôt que tester `platform` :
    « winget est-il là ? » est la bonne question, « suis-je sous Windows ? »
    ne l'est pas — winget peut manquer sur un Windows.
    """
    return {
        # Fenêtre native
        "fenetre_native": _importable("webview"),
        "webview2": EST_WINDOWS,          # le moteur, fourni par le système

        # Système
        "powershell": _commande("powershell") or _commande("pwsh"),
        "winget": _commande("winget"),
        # Le Planificateur de tâches : c'est lui qui fait survivre un rappel
        # à la fermeture de JARVIS (rappels_os.py). Question posée à la
        # commande, pas au système — schtasks peut manquer d'un PATH réduit.
        "planificateur_taches": _commande("schtasks"),
        "registre_windows": _importable("winreg"),
        "pywin32": _importable("win32api"),

        # Entrée/écran
        "automation_clavier": _importable("pyautogui"),
        "capture_ecran": _importable("pyautogui") or _importable("mss"),
        "webcam": _importable("cv2"),
        "info_ecrans": _importable("screeninfo"),

        # Voix
        "synthese_edge": _importable("edge_tts"),
        "micro": _importable("sounddevice") or _importable("pyaudio"),

        # Modèles locaux. On distingue « installé » de « répond » : le binaire
        # peut être là et le service éteint. Annoncer « ollama : oui » dans ce cas serait faux au moment
        # exact où l'information compte — quand le réseau tombe et qu'on
        # comptait sur le repli hors ligne.
        "ollama_installe": _commande("ollama"),
        "ollama_repond": _port_ouvert(11434),
    }



# Fonctionnalités JARVIS et ce dont chacune a besoin. Sert à répondre
# « pourquoi ce panneau est-il vide ? » sans faire lire le code à personne.
BESOINS = {
    "Fenêtre native (HUD)":      ["fenetre_native"],
    "Antivirus, désinstalleur":  ["registre_windows", "powershell"],
    "Mises à jour logicielles":  ["winget"],
    "VPN":                       ["powershell"],
    "Lancement d'applications":  ["pywin32"],
    "Contrôle Spotify/Deezer":   ["automation_clavier"],
    "Vision écran":              ["capture_ecran"],
    "Webcam":                    ["webcam"],
    "Voix (synthèse)":           ["synthese_edge"],
    "Voix (écoute)":             ["micro"],
    "Modèles hors ligne":        ["ollama_installe", "ollama_repond"],
}


# ── Ce qui est CONFIGURÉ (distinct de ce qui est installé) ───────────────
# capacites() dit quels modules sont présents. Sur une installation neuve il
# répond « 13 sur 14 », rassurant — alors qu'il n'y a aucune clé d'API et que
# JARVIS ne peut répondre à rien. Les deux questions sont distinctes et il
# faut les poser toutes les deux.
#
# `requis` marque ce sans quoi JARVIS n'a pas de sens. L'installeur demande
# ceux-là au premier lancement ; les autres attendent qu'on en ait besoin.

REGLAGES = (
    # (variables, requis, à quoi ça sert, où l'obtenir)
    (("GEMINI_API_KEY",), True,
     "Le modèle principal. Sans lui, JARVIS ne répond qu'avec ses outils locaux.",
     "https://aistudio.google.com/apikey"),
    (("JARVIS_ACCESS_TOKEN",), True,
     "Protège le WebSocket, qui exécute les commandes système.",
     "à inventer : une longue chaîne aléatoire"),
    (("HA_URL", "HA_TOKEN"), False,
     "Domotique Home Assistant.",
     "Profil → Jetons d'accès de longue durée, dans Home Assistant"),
    (("GROQ_API_KEY",), False, "Modèle de secours, rapide.", "https://console.groq.com/keys"),
    (("OPENAI_API_KEY",), False, "Modèles OpenAI.", "https://platform.openai.com/api-keys"),
    (("ANTHROPIC_API_KEY",), False, "Modèles Claude.", "https://console.anthropic.com/settings/keys"),
    (("MISTRAL_API_KEY",), False, "Modèles Mistral.", "https://console.mistral.ai/api-keys"),
    (("SERPAPI_API_KEY",), False, "Recherche web.", "https://serpapi.com/manage-api-key"),
    (("YOUTUBE_API_KEY",), False, "Recherche YouTube.", "https://console.cloud.google.com/apis"),
    (("DISCORD_WEBHOOK_URL",), False,
     "Notification push (tâches nocturnes terminées/échouées).",
     "Discord → Paramètres du salon → Intégrations → Webhooks → Nouveau webhook"),
    (("DISCORD_BOT_TOKEN", "DISCORD_USER_ID"), False,
     "Bot Discord : discuter avec JARVIS et lui donner des commandes à distance.",
     "https://discord.com/developers/applications → New Application → Bot → activer "
     "Message Content Intent ; DISCORD_USER_ID = votre ID Discord (mode développeur → "
     "clic droit sur votre pseudo → Copier l'ID)"),
    (("SLACK_WEBHOOK_URL",), False,
     "Notification push (tâches nocturnes terminées/échouées), même usage que le webhook "
     "Discord mais sur Slack — voir notifications_slack.py.",
     "Slack → créer une app → Incoming Webhooks → Add New Webhook to Workspace"),
    (("PRONOTE_SENSOR_PREFIX",), False,
     "Emploi du temps et révisions Pronote : début du nom des capteurs de l'intégration "
     "hass-pronote, par exemple pronote_dupont_alex.",
     "Home Assistant → Paramètres → Entités, chercher « pronote » : "
     "sensor.<préfixe>_homework"),
    (("JARVIS_NIVEAU_SCOLAIRE",), False,
     "Révisions : la classe de l'élève, pour adapter les quiz (par exemple « 4e »).",
     "à saisir"),
    (("NOTION_API_KEY", "NOTION_PARENT_PAGE_ID"), False,
     "Notes Notion : jeton de l'intégration et ID de la page qui contiendra les notes.",
     "https://www.notion.so/my-integrations"),
    (("GODSEYE_DIR",), False,
     "Carte OSINT : dossier où God's Eye View est installé.",
     "chemin du dossier sur cette machine"),
    (("SHADOWBROKER_DIR",), False,
     "Carte OSINT : dossier où ShadowBroker est installé.",
     "chemin du dossier sur cette machine"),
    # Réglages lus par le code mais facultatifs : vide = valeur par défaut ou
    # fonction refusée poliment. Listés ici pour que l'installeur les propose.
    (("XAI_API_KEY",), False, "Modèles Grok (xAI).", "https://console.x.ai"),
    (("EXCHANGERATE_API_KEY",), False,
     "Conversion de devises. Vide = source publique sans clé.",
     "https://www.exchangerate-api.com"),
    (("EXTRA_LLM_1_URL", "EXTRA_LLM_1_KEY", "EXTRA_LLM_1_MODEL"), False,
     "Fournisseur supplémentaire compatible OpenAI (routeur local, par exemple) : "
     "adresse /v1, clé et modèle.",
     "la documentation du fournisseur"),
    (("JARVIS_HEURES_CALMES_DEBUT", "JARVIS_HEURES_CALMES_FIN"), False,
     "Heures calmes des notifications push, au format HH:MM. Vide = 22:00-08:00.",
     "à saisir"),
    (("JARVIS_REVISIONS_MODELE",), False,
     "Révisions : modèle Ollama qui écrit les quiz. Vide = modèle par défaut.", "ollama list"),
    (("JARVIS_REVISIONS_JUGE",), False,
     "Révisions : modèle Ollama qui corrige. Vide = le même que JARVIS_REVISIONS_MODELE.",
     "ollama list"),
    (("HA_ALARME_ENTITY",), False,
     "Domotique : alarme (ex. alarm_control_panel.maison). Vide = commande refusée.",
     "Home Assistant → Paramètres → Entités"),
    (("HA_VERROU_ENTITY",), False,
     "Domotique : serrure (ex. lock.porte_entree). Vide = commande refusée.",
     "Home Assistant → Paramètres → Entités"),
    (("HA_ASPIRATEUR_ENTITY",), False,
     "Domotique : aspirateur (ex. vacuum.robot). Vide = commande refusée.",
     "Home Assistant → Paramètres → Entités"),
    (("HA_LINKY_PREFIX",), False,
     "Domotique : préfixe des capteurs du compteur (ex. sensor.compteur_linky).",
     "Home Assistant → Paramètres → Entités"),
    (("HA_WEATHER_ENTITY",), False,
     "Domotique : entité météo. Vide = weather.home.",
     "Home Assistant → Paramètres → Entités"),
    (("GODSEYE_URL",), False,
     "Carte OSINT : adresse de God's Eye View. Vide = http://localhost:4173/.", "à saisir"),
    (("SHADOWBROKER_API_URL",), False,
     "Carte OSINT : adresse de l'API ShadowBroker. Vide = http://localhost:8000.", "à saisir"),
    (("SHADOWBROKER_HMAC_SECRET",), False,
     "Carte OSINT : secret partagé avec ShadowBroker, s'il en exige un.",
     "la configuration de ShadowBroker"),
    (("SHADOWBROKER_AUTOSTART",), False,
     "Carte OSINT : 1 = la démarrer avec JARVIS. Vide ou 0 = jamais.", "à saisir"),
    (("JARVIS_DOSSIERS_AUTORISES",), False,
     "Dossiers que JARVIS peut lire et écrire, et où il accepte des projets de code, "
     "séparés par « ; ». Vide = Bureau, Documents, Téléchargements... du profil.",
     "chemins sur cette machine"),
    (("JARVIS_OPENCODE_MODELE",), False,
     "Délégation de code : modèle passé à OpenCode (fournisseur/modèle). "
     "Vide = OpenCode n'est pas essayé.",
     "opencode models"),
    (("JARVIS_OPENCODE_PROXY",), False,
     "Délégation de code : proxy local (hôte:port) qui doit répondre avant de lancer "
     "OpenCode. Vide = aucune vérification.",
     "à saisir"),
    (("JARVIS_DEPOT",), False,
     "Mises à jour : dépôt GitHub (propriétaire/nom) interrogé au lancement. "
     "Vide = aucune vérification.",
     "à saisir"),
    (("JARVIS_INTERFACE_DIR",), False,
     "Interface : dossier servi. Vide = frontend/ livré avec JARVIS.", "à saisir"),
    (("JARVIS_INTERFACE_PORT",), False, "Interface : port. Vide = 5173.", "à saisir"),
    (("JARVIS_OLLAMA_BASE_URL",), False,
     "Ollama local : adresse. Vide = http://localhost:11434/v1.", "à saisir"),
    (("JARVIS_OLLAMA_MODEL",), False, "Ollama local : modèle par défaut.", "ollama list"),
    (("SPOTIFY_MUSIQUE_URI",), False,
     "Musique : playlist Spotify lancée sur demande (spotify:playlist:...).",
     "Spotify → Partager → Copier l'URI"),
    (("YOUTUBE_MUSIQUE_URL",), False,
     "Musique : vidéo YouTube lancée sur demande.", "adresse de la vidéo"),
    (("CHROME_PATH",), False,
     "Chemin de chrome.exe s'il n'est pas trouvé tout seul.", "chemin sur cette machine"),
    (("ANTIGRAVITY_PATH",), False,
     "Chemin d'Antigravity.exe s'il n'est pas trouvé tout seul.", "chemin sur cette machine"),
)


def _charger_env():
    """
    Charge le .env si personne ne l'a fait.

    main2 appelle load_dotenv à son démarrage, mais l'installeur, le panneau
    de santé et les scripts appellent configuration() sans passer par lui.
    Sans ceci, l'inventaire annonçait « GEMINI_API_KEY manquante » sur une
    machine où elle est renseignée depuis toujours — un faux négatif qui
    aurait fait redemander à l'utilisateur des clés qu'il a déjà.

    override=False : une variable déjà posée dans l'environnement l'emporte
    sur le fichier, comme le veut la convention.
    """
    fichier = RACINE / ".env"
    if not fichier.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(fichier, override=False)
    except ImportError:
        # Lecture minimale plutôt que rien : python-dotenv peut manquer sur
        # une installation partielle, et c'est justement là qu'on interroge
        # la configuration.
        import io as _io
        for ligne in _io.open(fichier, encoding="utf-8", errors="replace"):
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, _, valeur = ligne.partition("=")
            os.environ.setdefault(cle.strip(),
                                  valeur.strip().strip('"').strip("'"))


def configuration():
    """
    [(variables, present, requis, role, ou_obtenir)] — l'état des réglages.

    Ne renvoie JAMAIS les valeurs, seulement leur présence : cette liste finit
    dans une interface et dans des journaux.
    """
    _charger_env()
    etat = []
    for variables, requis, role, source in REGLAGES:
        present = all((os.environ.get(v) or "").strip() for v in variables)
        etat.append((variables, present, requis, role, source))
    return etat


def reglages_manquants(requis_seulement=True):
    """Ce qu'il reste à renseigner. Vide = prêt à servir."""
    return [(v, r, role, source) for v, p, r, role, source in configuration()
            if not p and (r or not requis_seulement)]


def premier_demarrage():
    """
    Vrai si rien n'a encore été configuré.

    Sert à l'installeur et au premier lancement : proposer l'assistant de
    configuration plutôt que de laisser JARVIS échouer sans expliquer.
    """
    return not any(p for _, p, _, _, _ in configuration())


def fonctionnalites_indisponibles():
    """[(fonctionnalité, [capacités manquantes])] — vide si tout est là."""
    dispo = capacites()
    manques = []
    for nom, requis in BESOINS.items():
        absents = [r for r in requis if not dispo.get(r)]
        if absents:
            manques.append((nom, absents))
    return manques


def resume():
    dispo = capacites()
    return {
        "systeme": SYSTEME,
        "python": "%d.%d.%d" % sys.version_info[:3],
        "racine": str(RACINE),
        "dossier_donnees": str(DOSSIER_DONNEES),
        "racine_inscriptible": racine_inscriptible(),
        "capacites_ok": sum(1 for v in dispo.values() if v),
        "capacites_total": len(dispo),
        "fonctionnalites_degradees": len(fonctionnalites_indisponibles()),
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = resume()
    print()
    print("=" * 74)
    print("JARVIS — CONFIGURATION DU SYSTÈME")
    print("=" * 74)
    print("  système             %s, Python %s" % (r["systeme"], r["python"]))
    print("  installation        %s" % r["racine"])
    print("  inscriptible        %s%s" % (
        r["racine_inscriptible"],
        "" if r["racine_inscriptible"] else "   <-- config et données à déplacer"))
    print("  données utilisateur %s" % r["dossier_donnees"])
    print()
    print("  CAPACITÉS (%d/%d)" % (r["capacites_ok"], r["capacites_total"]))
    for nom, ok in sorted(capacites().items()):
        print("    %s %s" % ("oui" if ok else "NON", nom))
    manques = fonctionnalites_indisponibles()
    print()
    if manques:
        print("  FONCTIONNALITÉS DÉGRADÉES (%d) :" % len(manques))
        for nom, absents in manques:
            print("    %-28s manque : %s" % (nom, ", ".join(absents)))
    else:
        print("  Toutes les fonctionnalités ont ce qu'il leur faut.")
    print("=" * 74)
