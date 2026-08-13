# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Ce que JARVIS sait de la machine ou il tourne
===========================================================
Adresse IP, espace disque, nom d'hote, version du systeme, memoire, reseau.

POURQUOI CE FICHIER EXISTE
Mesure du 12/08/2026, questions posees au vrai JARVIS :

    « quelle est ma version de windows »   14 988 ms  « mes capteurs ne me
                                                        permettent pas »
    « quelle est mon adresse ip »          13 412 ms  « je ne peux pas lire
                                                        directement »
    « combien de place libre sur le disque » 7 974 ms « pas d'acces direct »
    « combien de memoire vive utilisee »     6 355 ms « pas d'acces direct »
    « quel est mon wifi »                    6 140 ms « pas d'acces direct »
    « quel est mon nom d ordinateur »        4 562 ms « je ne peux pas lire »
    « suis-je connecte a internet »          3 183 ms « puisque nous
                                                        conversons... »

Sept questions sur la machine, sept refus, jusqu'a QUINZE SECONDES pour dire
non. Pendant ce temps le HUD affichait le CPU et la RAM en direct : psutil
etait installe et deja utilise ailleurs. Il ne manquait que le raccordement.

La derniere reponse est la pire : « puisque nous conversons en temps reel,
la reponse est oui » est un sophisme. JARVIS et le navigateur sont sur la
MEME machine ; leur dialogue ne prouve rien sur Internet.

PORTABILITE
psutil, platform et socket fonctionnent partout. Le SSID du Wi-Fi est la
seule information qui demande une commande propre au systeme ; elle est
donc isolee, et son absence se dit au lieu de faire echouer le reste.
"""

import os
import platform
import shutil
import socket
import subprocess
import sys

from . import outil, contient
from config import nom_utilisateur

try:
    import psutil
except Exception:                                       # pragma: no cover
    psutil = None


def _go(octets):
    return octets / (1024 ** 3)


def _ip_locale():
    """
    L'adresse de cette machine sur le reseau local.

    On ouvre un socket UDP vers une adresse externe SANS RIEN ENVOYER : cela
    force le systeme a choisir l'interface de sortie, dont on lit l'adresse.
    gethostbyname(gethostname()) renvoie souvent 127.0.0.1 sur une machine a
    plusieurs interfaces, ce qui serait faux sans le dire.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.4)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None
    finally:
        s.close()


def _internet(delai=1.5):
    """Vraie tentative de connexion sortante, pas une deduction."""
    for hote, port in (("1.1.1.1", 53), ("8.8.8.8", 53)):
        s = socket.socket()
        s.settimeout(delai)
        try:
            if s.connect_ex((hote, port)) == 0:
                return True
        except Exception:
            pass
        finally:
            s.close()
    return False


def _ssid():
    """(ssid, raison). Seule information qui demande une commande systeme."""
    if sys.platform == "win32":
        if not shutil.which("netsh"):
            return None, "netsh est introuvable"
        try:
            sortie = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, timeout=6,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.decode("utf-8", "replace")
        except Exception as e:
            return None, "netsh a echoue (%s)" % type(e).__name__
        for ligne in sortie.splitlines():
            gauche, _, droite = ligne.partition(":")
            g = gauche.strip().lower()
            if g in ("ssid", "nom du ssid") and droite.strip():
                return droite.strip(), ""
        return None, "aucun reseau sans fil connecte"
    if sys.platform == "darwin":
        try:
            sortie = subprocess.run(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/"
                 "Current/Resources/airport", "-I"],
                capture_output=True, timeout=6).stdout.decode("utf-8", "replace")
            for ligne in sortie.splitlines():
                if ligne.strip().startswith("SSID:"):
                    return ligne.split(":", 1)[1].strip(), ""
        except Exception:
            pass
        return None, "impossible de lire le reseau sans fil"
    if shutil.which("iwgetid"):
        try:
            s = subprocess.run(["iwgetid", "-r"], capture_output=True,
                               timeout=6).stdout.decode().strip()
            if s:
                return s, ""
        except Exception:
            pass
    return None, "aucun outil de lecture du Wi-Fi sur ce systeme"


def _nom_systeme():
    """Nom lisible du systeme, y compris la vraie edition de Windows."""
    if sys.platform == "win32":
        version = platform.version()          # ex. 10.0.26200
        edition = platform.win32_edition() if hasattr(platform, "win32_edition") else ""
        # Windows 11 se declare toujours 10.0 ; c'est le numero de build qui
        # les separe. Sans ce test, JARVIS annoncerait « Windows 10 » sur un
        # Windows 11 — faux avec l'air d'etre juste.
        try:
            build = int(version.split(".")[-1])
        except Exception:
            build = 0
        nom = "Windows 11" if build >= 22000 else "Windows 10"
        return "%s%s (build %s)" % (nom, " " + edition if edition else "", version)
    if sys.platform == "darwin":
        return "macOS %s" % platform.mac_ver()[0]
    try:
        import distro                                     # facultatif
        return distro.name(pretty=True)
    except Exception:
        return "%s %s" % (platform.system(), platform.release())


# `bloquant` : _ssid() lance netsh et _internet() ouvre des sockets. En mode
# `sync` ces appels bloqueraient la boucle asyncio de JARVIS — la famille de
# bugs la plus frequente de ce projet.
@outil(nom="machine", priorite=25, mode="bloquant",
       description="IP, disque, memoire, nom d'hote, version du systeme, Wi-Fi")
def resoudre_machine(texte):
    """Repond sur la machine elle-meme, sans passer par le modele."""
    t = texte.lower().replace("?", "").replace("'", " ").strip()
    moi = nom_utilisateur()

    # ── Adresse IP ───────────────────────────────────────────────────────
    if "ip" in t.split() or contient(t, ("adresse ip", "addresse ip")):
        publique = contient(t, ("publique", "public", "externe", "exterieure"))
        if publique:
            try:
                import urllib.request
                ip = urllib.request.urlopen("https://api.ipify.org",
                                            timeout=4).read().decode().strip()
                return f"Votre adresse IP publique est {ip}, {moi}."
            except Exception:
                return (f"Je n'ai pas pu joindre le service qui donne l'adresse "
                        f"publique, {moi}. La connexion sortante est peut-etre coupee.")
        ip = _ip_locale()
        if not ip:
            return f"Je ne parviens pas a lire l'adresse de cette machine, {moi}."
        return (f"L'adresse de cette machine sur le reseau local est {ip}, {moi}. "
                f"Demandez l'adresse publique si c'est celle-la qu'il vous faut.")

    # ── Espace disque ────────────────────────────────────────────────────
    if contient(t, ("place libre", "espace libre", "espace disque",
                            "place sur le disque", "disque dur plein",
                            "reste de la place", "stockage")):
        cible = os.path.abspath(os.sep)
        try:
            u = shutil.disk_usage(cible)
        except Exception as e:
            return f"Je ne parviens pas a lire le disque, {moi} ({type(e).__name__})."
        pct = 100 * u.free / u.total if u.total else 0
        return (f"Il reste {_go(u.free):.0f} gigaoctets libres sur "
                f"{_go(u.total):.0f}, soit {pct:.0f} pour cent, {moi}.")

    # (Pas de branche memoire vive ici : infos_systeme, priorite 20, la traite
    #  deja et passe en premier. Elle ne repondait pas parce qu'elle comparait
    #  « mémoire vive » accentue a un texte sans accents — corrige la-bas avec
    #  tools.contient(). En ajouter une copie ici n'aurait servi qu'a masquer
    #  la vraie cause et a laisser deux reponses divergentes s'installer.)

    # ── Nom de la machine ────────────────────────────────────────────────
    if contient(t, ("nom d ordinateur", "nom de l ordinateur",
                            "nom de la machine", "nom d hote", "hostname",
                            "comment s appelle ce pc")):
        return f"Cette machine s'appelle {socket.gethostname()}, {moi}."

    # ── Version du systeme ───────────────────────────────────────────────
    if contient(t, ("version de windows", "version windows",
                            "quel windows", "version du systeme",
                            "version de macos", "quelle version d os",
                            "quel systeme d exploitation", "version de linux")):
        return f"Cette machine tourne sous {_nom_systeme()}, {moi}."

    # ── Processeur (le modele, pas la charge) ────────────────────────────
    if contient(t, ("quel processeur", "quel est mon processeur",
                            "modele de processeur", "quel cpu ai-je")):
        nom = platform.processor() or "inconnu"
        coeurs = psutil.cpu_count(logical=False) if psutil else None
        fils = psutil.cpu_count(logical=True) if psutil else None
        detail = ""
        if coeurs and fils:
            detail = f", {coeurs} coeurs et {fils} fils d'execution"
        return f"Le processeur est un {nom}{detail}, {moi}."

    # ── Connexion Internet ───────────────────────────────────────────────
    if contient(t, ("connecte a internet", "connecte a internet",
                            "y a t il internet", "internet fonctionne",
                            "la connexion marche", "j ai internet")):
        if _internet():
            return f"Oui, la connexion sortante fonctionne, {moi}."
        return (f"Non, aucune connexion sortante ne repond, {moi}. "
                f"Les fonctions qui dependent du reseau vont echouer.")

    # ── Wi-Fi ────────────────────────────────────────────────────────────
    if contient(t, ("mon wifi", "quel wifi", "reseau wifi", "wi-fi",
                            "nom du reseau", "quel reseau sans fil")):
        ssid, raison = _ssid()
        if ssid:
            return f"Vous etes connecte au reseau {ssid}, {moi}."
        return f"Je ne peux pas lire le reseau sans fil, {moi} : {raison}."

    return None
