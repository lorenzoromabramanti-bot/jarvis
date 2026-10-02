# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Amorceur d'installation
=====================================
Le petit programme qu'on télécharge et qu'on lance. Il installe JARVIS.

CE QU'IL FAIT, DANS L'ORDRE
    1. trouve un Python utilisable, ou dit où le prendre
    2. télécharge la dernière version publiée depuis GitHub
    3. crée l'environnement et installe les dépendances
    4. passe la main à l'assistant de configuration, qui est beau
    5. pose un raccourci

CONTRAINTE QUI DICTE TOUT LE RESTE
Ce fichier tourne AVANT que quoi que ce soit soit installé. Bibliothèque
standard uniquement : pas de requests, pas de pywebview, pas de config.py.
Tout ce qu'il importe doit exister dans un Python nu. C'est aussi ce qui
permet à l'exécutable compilé de rester petit.

POURQUOI PAS UN GROS EXÉCUTABLE AUTONOME
Embarquer JARVIS entier ferait plusieurs centaines de mégaoctets, et sur
macOS un exécutable non signé refuse de s'ouvrir — la signature Apple coûte
99 $ par an. Un amorceur léger qui télécharge marche partout, et laisse le
code lisible par qui l'installe : ça compte pour un programme qui pilote la
machine de quelqu'un.

    python amorceur.py            interface graphique
    python amorceur.py --console  sans fenêtre, pour un serveur
"""

import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile

DEPOT = "lorenzoromabramanti-bot/jarvis"
NOM = "J.A.R.V.I.S"

# JARVIS est développé sur 3.12. 3.10 et 3.11 conviennent. 3.13 n'est pas
# éprouvé mais devrait passer. 3.14 est trop récent : plusieurs dépendances
# n'ont pas encore de roue compilée pour lui, et pip essaierait de compiler
# depuis les sources — ce qui échoue sans outils de compilation.
VERSIONS_BONNES = ((3, 12), (3, 11), (3, 10), (3, 13))
VERSION_MINIMALE = (3, 10)

CACHE = "\x1b"          # inutilisé, garde-fou contre les copier-coller


def dossier_defaut():
    """%LOCALAPPDATA%\\JARVIS — pas Program Files, qui exige l'élévation."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "JARVIS")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Applications/JARVIS")
    return os.path.expanduser("~/.local/share/jarvis")


def verifier_dossier(chemin):
    """
    (ok, avertissement) sur le dossier choisi.

    LA LONGUEUR DU CHEMIN COMPTE, et c'est contre-intuitif. Windows plafonne
    à 260 caractères par défaut, et une installation Python creuse
    profondément : venv/Lib/site-packages/<paquet>/<sous-module>/… ajoute
    facilement 120 caractères. Mesuré : le même `python -m venv` réussit dans
    un chemin de 19 caractères et échoue dans un de 140, avec pour seule
    trace « ensurepip returned non-zero exit status 15 » — rien qui désigne
    la cause.

    Sans cet avertissement, quelqu'un qui installe dans un dossier profond
    obtiendrait un échec inexplicable.
    """
    chemin = os.path.abspath(chemin or "")
    if not chemin:
        return False, "Aucun dossier indiqué."
    if sys.platform == "win32" and len(chemin) > 90:
        return False, ("Ce chemin fait %d caractères. Windows limite les "
                       "chemins à 260, et l'installation en ajoute environ "
                       "120 : elle échouerait sans dire pourquoi. Choisissez "
                       "un dossier plus court." % len(chemin))
    parent = chemin
    while parent and not os.path.exists(parent):
        nouveau = os.path.dirname(parent)
        if nouveau == parent:
            break
        parent = nouveau
    if parent and not os.access(parent, os.W_OK):
        return False, "Écriture impossible dans %s." % parent
    try:
        libre = shutil.disk_usage(parent or os.path.abspath(os.sep)).free
        if libre < 2 * 1024 ** 3:
            return False, ("Il reste %.1f Go sur ce disque. Prévoyez au moins "
                           "2 Go." % (libre / 1024 ** 3))
    except Exception:
        pass
    return True, ""


# ── 1. Trouver un Python utilisable ──────────────────────────────────────

def _version_de(executable):
    try:
        sortie = subprocess.run(
            [executable, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if sortie.returncode:
            return None
        a, b = sortie.stdout.strip().split(".")
        return (int(a), int(b))
    except Exception:
        return None


def pythons_disponibles():
    """[(version, chemin)] triés du plus adapté au moins adapté."""
    candidats = []

    if sys.platform == "win32":
        # `py -0p` liste toutes les installations connues du lanceur.
        try:
            sortie = subprocess.run(["py", "-0p"], capture_output=True, text=True,
                                    timeout=15,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for ligne in sortie.stdout.splitlines():
                morceaux = ligne.split()
                chemin = next((m for m in morceaux if m.lower().endswith("python.exe")), None)
                if chemin and os.path.exists(chemin):
                    candidats.append(chemin)
        except Exception:
            pass

    for nom in ("python3.12", "python3.11", "python3.10", "python3", "python"):
        chemin = shutil.which(nom)
        if chemin:
            candidats.append(chemin)

    vus, trouves = set(), []
    for chemin in candidats:
        reel = os.path.normcase(os.path.abspath(chemin))
        if reel in vus:
            continue
        vus.add(reel)
        v = _version_de(chemin)
        if v and v >= VERSION_MINIMALE:
            trouves.append((v, chemin))

    def rang(couple):
        v = couple[0]
        return VERSIONS_BONNES.index(v) if v in VERSIONS_BONNES else 99
    trouves.sort(key=rang)
    return trouves


def meilleur_python():
    """(chemin, version, avertissement). (None, None, raison) si rien ne va."""
    trouves = pythons_disponibles()
    if not trouves:
        return None, None, ("Aucun Python 3.10 ou plus récent n'a été trouvé "
                            "sur cette machine.")
    version, chemin = trouves[0]
    if version not in VERSIONS_BONNES:
        return chemin, version, (
            "Python %d.%d est plus récent que ce qui a été éprouvé. Certaines "
            "dépendances n'ont peut-être pas encore de version compilée pour "
            "lui." % version)
    return chemin, version, ""


# ── 2. Télécharger ───────────────────────────────────────────────────────

def derniere_version(depot=DEPOT, delai=15):
    """(tag, url_archive) de la dernière publication. Lève en cas d'échec."""
    url = "https://api.github.com/repos/%s/releases/latest" % depot
    requete = urllib.request.Request(url, headers={
        "User-Agent": "JARVIS-amorceur", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(requete, timeout=delai) as reponse:
        donnees = json.loads(reponse.read().decode("utf-8"))
    tag = donnees.get("tag_name") or "main"
    return tag, "https://github.com/%s/archive/refs/tags/%s.zip" % (depot, tag)


def telecharger(url, destination, progression=None, delai=90):
    """Télécharge en signalant l'avancement. Renvoie le chemin écrit."""
    requete = urllib.request.Request(url, headers={"User-Agent": "JARVIS-amorceur"})
    with urllib.request.urlopen(requete, timeout=delai) as reponse:
        total = int(reponse.headers.get("Content-Length") or 0)
        recu = 0
        with open(destination, "wb") as f:
            while True:
                bloc = reponse.read(65536)
                if not bloc:
                    break
                f.write(bloc)
                recu += len(bloc)
                if progression:
                    progression(recu, total)
    return destination


def extraire(archive, cible, progression=None):
    """
    Extrait l'archive GitHub, en retirant son dossier racine.

    Une archive GitHub contient tout sous « depot-tag/ ». Sans ce
    retranchement, on obtiendrait JARVIS/jarvis-1.0.0/main2.py.
    """
    os.makedirs(cible, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        noms = z.namelist()
        racine = noms[0].split("/")[0] + "/" if noms else ""
        for i, nom in enumerate(noms):
            if not nom.startswith(racine) or nom.endswith("/"):
                continue
            relatif = nom[len(racine):]
            if not relatif or ".." in relatif:
                continue                       # rien ne sort du dossier cible
            destination = os.path.join(cible, relatif.replace("/", os.sep))
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with z.open(nom) as source, open(destination, "wb") as f:
                shutil.copyfileobj(source, f)
            if progression:
                progression(i + 1, len(noms))
    return cible


# ── 3. Environnement et dépendances ──────────────────────────────────────

def python_du_venv(dossier):
    return os.path.join(dossier, "venv",
                        "Scripts" if sys.platform == "win32" else "bin",
                        "python.exe" if sys.platform == "win32" else "python")


def _venv_utilisable(dossier):
    """L'environnement répond-il vraiment ? On teste, on ne suppose pas."""
    py = python_du_venv(dossier)
    if not os.path.exists(py):
        return False
    try:
        r = subprocess.run([py, "-m", "pip", "--version"], capture_output=True,
                           text=True, timeout=40,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0
    except Exception:
        return False


def _venv_sans_ensurepip(python, dossier, journal=None):
    """
    Crée l'environnement puis amorce pip à la main. (ok, detail).

    POURQUOI CE DÉTOUR EXISTE
    Debian et Ubuntu retirent `ensurepip` du paquet Python de base ; `python3
    -m venv` échoue alors en réclamant `sudo apt install python3-venv`.
    Exiger les droits d'administration pour installer un programme dans son
    propre dossier personnel est disproportionné, et beaucoup de gens ne les
    ont pas sur la machine qu'ils utilisent.

    get-pip.py vient de bootstrap.pypa.io en HTTPS : c'est la source
    officielle de l'équipe qui publie pip, et la méthode qu'elle recommande
    pour exactement ce cas. On l'exécute avec le Python de l'environnement
    qu'on vient de créer, pas avec celui du système.
    """
    venv = os.path.join(dossier, "venv")
    shutil.rmtree(venv, ignore_errors=True)
    r = subprocess.run([python, "-m", "venv", "--without-pip", venv],
                       capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    py = python_du_venv(dossier)
    if not os.path.exists(py):
        return False, "création sans pip impossible"

    amorce = os.path.join(dossier, "get-pip.py")
    try:
        telecharger("https://bootstrap.pypa.io/get-pip.py", amorce, delai=60)
    except Exception as e:
        return False, "téléchargement de get-pip impossible (%s)" % type(e).__name__
    try:
        r = subprocess.run([py, amorce, "--quiet"], capture_output=True, text=True,
                           timeout=300,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if journal and r.stderr.strip():
            journal("  " + r.stderr.strip().splitlines()[-1][:140])
    except Exception as e:
        return False, "amorçage de pip impossible (%s)" % type(e).__name__
    finally:
        try:
            os.remove(amorce)
        except OSError:
            pass
    return (True, "") if _venv_utilisable(dossier) else (False, "pip ne répond pas")


def creer_environnement(python, dossier, journal=None):
    """
    Crée le venv. Renvoie (ok, message).

    ON VÉRIFIE LE RÉSULTAT, PAS LE CODE DE RETOUR.
    Mesuré sur cette machine : `python -m venv` sort en erreur parce que son
    étape `ensurepip` renvoie 15 — et pourtant l'environnement est complet et
    pip répond. Se fier au code aurait fait échouer une installation qui
    marche. À l'inverse, un code 0 ne garantit pas qu'on puisse installer
    quoi que ce soit.

    Dans les deux sens, la seule réponse fiable est d'essayer.
    """
    venv = os.path.join(dossier, "venv")
    if _venv_utilisable(dossier):
        return True, "environnement déjà en place"

    r = subprocess.run([python, "-m", "venv", venv], capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if _venv_utilisable(dossier):
        if r.returncode and journal:
            journal("  (venv a signalé une erreur, mais l'environnement "
                    "répond — on continue)")
        return True, "environnement créé"

    # Là seulement, c'est un vrai échec.
    #
    # On lit stdout AUTANT que stderr : `python -m venv` ecrit son explication
    # sur la SORTIE STANDARD. En ne regardant que stderr, le message d'echec
    # etait « Création de l'environnement impossible. » — sans un mot de plus,
    # alors que Python venait de donner la commande exacte a taper.
    sortie = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    if journal and sortie:
        journal(sortie[:600])

    # Sur Debian et Ubuntu, ensurepip est retire du paquet Python de base.
    # Plutot que d'exiger sudo — que beaucoup n'ont pas, et qu'on ne devrait
    # pas reclamer pour installer un programme dans son propre dossier — on
    # cree l'environnement SANS pip et on amorce pip nous-memes.
    m = re.search(r"apt install (python[\d.]*-venv)", sortie)
    if m or "ensurepip is not available" in sortie:
        if journal:
            journal("  ensurepip absent — création sans pip, puis amorçage.")
        ok, detail = _venv_sans_ensurepip(python, dossier, journal)
        if ok:
            return True, "environnement créé (pip amorcé séparément)"
        paquet = m.group(1) if m else "python3-venv"
        return False, ("Il manque le module venv de Python, et l'amorçage de "
                       "pip a échoué (%s).\n"
                       "Sur Debian ou Ubuntu :  sudo apt install %s\n"
                       "Puis relancez cette installation." % (detail, paquet))

    lignes = [l for l in sortie.splitlines() if l.strip()]
    return False, ("Création de l'environnement impossible%s"
                   % (" :\n" + "\n".join(lignes[-4:]) if lignes else "."))


def installer_dependances(dossier, journal=None, avec_voix=False):
    """
    pip install. Renvoie (ok, message).

    La reconnaissance vocale est SÉPARÉE : torch et nemo pèsent plusieurs
    gigaoctets. Les imposer ferait payer ce téléchargement à quelqu'un qui
    veut seulement taper ses demandes.
    """
    py = python_du_venv(dossier)
    fichiers = [os.path.join(dossier, "requirements.txt")]
    if avec_voix:
        fichiers.append(os.path.join(dossier, "requirements-voix.txt"))
    for fichier in fichiers:
        if not os.path.exists(fichier):
            continue
        commande = [py, "-m", "pip", "install", "--disable-pip-version-check",
                    "-r", fichier]
        # On GARDE les dernières lignes. Un échec qui ne dit pas pourquoi est
        # inexploitable : la première version renvoyait « l'installation a
        # échoué » avec zéro ligne de journal, et il a fallu relancer la
        # commande à la main pour apprendre quoi que ce soit.
        dernieres = []
        try:
            processus = subprocess.Popen(
                commande, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            return False, "pip n'a pas pu être lancé : %s" % e
        for ligne in processus.stdout:
            ligne = ligne.rstrip()
            if not ligne:
                continue
            dernieres.append(ligne)
            del dernieres[:-12]
            if journal:
                journal(ligne[:160])
        code = processus.wait()
        if code != 0:
            # UN PAQUET QUI NE SE COMPILE PAS NE DOIT PAS TOUT ARRÊTER.
            # Mesuré sur Ubuntu 26.04 : pygame n'a pas de version compilée
            # pour Python 3.14 et sa compilation réclame les en-têtes SDL.
            # pip s'arrête alors sur CE paquet, et les quarante-huit autres
            # ne sont jamais installés — JARVIS devient inutilisable à cause
            # d'une bibliothèque qui ne sert qu'à jouer du son.
            #
            # On reprend donc un par un. Les échecs sont nommés, pas tus.
            if journal:
                journal("  pip s'est arrêté (code %s). Reprise paquet par "
                        "paquet pour n'écarter que ce qui bloque…" % code)
            manques = _installer_un_par_un(py, fichier, journal)
            essentiels = [m for m in manques
                          if _nom_paquet(m).lower() in INDISPENSABLES]
            if essentiels:
                return False, ("Ces paquets sont indispensables et n'ont pas pu "
                               "être installés :\n  %s\n\n%s"
                               % ("\n  ".join(essentiels),
                                  "\n".join(dernieres[-4:])))
            if manques:
                self_msg = ("dépendances installées, sauf %d : %s"
                            % (len(manques), ", ".join(_nom_paquet(m) for m in manques)))
                if journal:
                    journal("  " + self_msg)
                return True, self_msg
    return True, "dépendances installées"


# Sans eux, JARVIS ne démarre pas du tout : leur import n'est pas protégé,
# ou bien ils portent le cœur du fonctionnement.
INDISPENSABLES = {"edge-tts", "python-dotenv", "websockets", "requests",
                  "google-genai", "psutil", "pywebview"}


def _nom_paquet(ligne):
    return re.split(r"[<>=!;\s\[]", ligne.strip())[0]


def _installer_un_par_un(py, fichier, journal=None):
    """Installe chaque ligne séparément. Renvoie celles qui ont échoué."""
    manques = []
    for ligne in io.open(fichier, encoding="utf-8", errors="replace"):
        exigence = ligne.split("#")[0].strip()
        if not exigence:
            continue
        r = subprocess.run(
            [py, "-m", "pip", "install", "--disable-pip-version-check", exigence],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=1800,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            manques.append(exigence)
            if journal:
                journal("    échec : %s" % _nom_paquet(exigence))
    return manques


# ── 4. Raccourci ─────────────────────────────────────────────────────────

def poser_raccourci(dossier):
    """Raccourci dans le menu Démarrer. Sans échec bloquant : c'est un confort."""
    if sys.platform != "win32":
        return False, "raccourci non posé (hors Windows)"
    try:
        menu = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows",
                            "Start Menu", "Programs")
        lien = os.path.join(menu, "JARVIS.lnk")
        cible = python_du_venv(dossier)
        script = (
            "$s=(New-Object -COM WScript.Shell).CreateShortcut('%s');"
            "$s.TargetPath='%s';$s.Arguments='main2.py';"
            "$s.WorkingDirectory='%s';$s.Save()"
            % (lien.replace("'", "''"), cible.replace("'", "''"),
               dossier.replace("'", "''")))
        r = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode:
            return False, "raccourci non posé"
        return True, "raccourci ajouté au menu Démarrer"
    except Exception as e:
        return False, "raccourci non posé (%s)" % type(e).__name__


# ── Enchaînement ─────────────────────────────────────────────────────────

def installer(dossier, avec_voix=False, journal=print, avancement=None):
    """
    Fait tout, dans l'ordre. Renvoie (ok, message).

    `journal` reçoit chaque ligne, `avancement` une fraction entre 0 et 1.
    """
    def etape(fraction, texte):
        journal(texte)
        if avancement:
            avancement(fraction, texte)

    ok, souci = verifier_dossier(dossier)
    if not ok:
        return False, souci

    etape(0.02, "Recherche d'un Python utilisable…")
    python, version, avertissement = meilleur_python()
    if not python:
        return False, avertissement
    journal("  Python %d.%d — %s" % (version[0], version[1], python))
    if avertissement:
        journal("  ATTENTION : " + avertissement)

    etape(0.08, "Recherche de la dernière version publiée…")
    try:
        tag, url = derniere_version()
    except urllib.error.HTTPError as e:
        return False, ("GitHub a répondu %s. Aucune version publiée ?" % e.code)
    except Exception as e:
        return False, ("Impossible de joindre GitHub (%s)." % type(e).__name__)
    journal("  version %s" % tag)

    temporaire = tempfile.mkdtemp(prefix="jarvis_amorce_")
    try:
        archive = os.path.join(temporaire, "jarvis.zip")
        etape(0.12, "Téléchargement…")
        telecharger(url, archive, lambda recu, total:
                    avancement and total and
                    avancement(0.12 + 0.28 * recu / total, "Téléchargement…"))

        etape(0.42, "Extraction…")
        os.makedirs(dossier, exist_ok=True)
        extraire(archive, dossier)
        journal("  installé dans %s" % dossier)
    finally:
        shutil.rmtree(temporaire, ignore_errors=True)

    etape(0.50, "Création de l'environnement…")
    ok, message = creer_environnement(python, dossier, journal)
    if not ok:
        return False, message

    etape(0.58, "Installation des dépendances (plusieurs minutes)…")
    ok, message = installer_dependances(dossier, journal, avec_voix)
    if not ok:
        return False, message

    etape(0.94, "Finalisation…")
    pose, message = poser_raccourci(dossier)
    journal("  " + message)

    etape(1.0, "Terminé.")
    return True, dossier


def lancer_assistant(dossier):
    """Passe la main à l'assistant de configuration, qui est graphique."""
    script = os.path.join(dossier, "installeur.py")
    if not os.path.exists(script):
        return False
    subprocess.Popen([python_du_venv(dossier), script], cwd=dossier,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


def _console(cible=None, avec_voix=False):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cible = cible or dossier_defaut()
    ok, souci = verifier_dossier(cible)
    if not ok:
        print("Impossible : %s" % souci)
        return 1
    print("Installation de %s dans %s" % (NOM, cible))
    ok, message = installer(cible, avec_voix=avec_voix)
    print(("OK : " if ok else "ECHEC : ") + str(message))
    return 0 if ok else 1


if __name__ == "__main__":
    voix = "--voix" in sys.argv
    if "--console" in sys.argv:
        raise SystemExit(_console(avec_voix=voix))

    # tkinter n'est PAS garanti. Sur Ubuntu il vit dans un paquet separe
    # (python3-tk) qui n'est pas installe par defaut : mesure sur Ubuntu
    # 26.04, `import tkinter` echoue sur une machine neuve. Un amorceur qui
    # planterait la n'installerait jamais rien.
    try:
        import tkinter                                   # noqa: F401
        from fenetre import ouvrir
    except Exception as e:
        print("Interface graphique indisponible (%s)." % type(e).__name__)
        if sys.platform.startswith("linux"):
            print("Sur Debian ou Ubuntu :  sudo apt install python3-tk")
        print("Installation en mode texte.\n")
        raise SystemExit(_console(avec_voix=voix))
    ouvrir()
