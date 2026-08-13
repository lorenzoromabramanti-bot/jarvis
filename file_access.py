# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Lecture / écriture de fichiers, sous liste blanche
================================================================

`file_manager.py` sait déjà lister, créer un dossier, renommer, déplacer et
chercher. Il ne sait NI lire NI écrire le contenu d'un fichier. Ce module
ajoute ces deux capacités — les plus dangereuses — donc sous contrôle strict.

MODÈLE DE MENACE
----------------
Ces fonctions seront atteignables depuis le WebSocket, lui-même exposé par un
tunnel. Un chemin non contrôlé permettrait de lire `.env` (clés API, mots de
passe e-mail, jeton d'accès) ou d'écrire dans un dossier de démarrage.

TROIS BARRIÈRES, dans cet ordre :
  1. Résolution RÉELLE du chemin (`os.path.realpath`) AVANT tout contrôle.
     Sans cela, `..\\..\\` et les liens symboliques contournent la liste blanche.
  2. Liste blanche de dossiers. Jamais `C:\\` entier.
  3. Refus par nom de fichier, même à l'intérieur d'un dossier autorisé.

Chaque refus est explicite : on renvoie la raison, jamais un silence.
"""

import os
from pathlib import Path

# ── Barrière 2 : dossiers autorisés ─────────────────────────────────────────
# Modifiable via JARVIS_DOSSIERS_AUTORISES dans .env (séparés par ;).
_PROFIL = os.environ.get("USERPROFILE", "")
_DEFAUT = [
    os.path.join(_PROFIL, "Desktop"),
    os.path.join(_PROFIL, "Documents"),
    os.path.join(_PROFIL, "Downloads"),
    os.path.join(_PROFIL, "Pictures"),
    os.path.join(_PROFIL, "Music"),
    os.path.join(_PROFIL, "Videos"),
]

# ── Barrière 3 : jamais, même dans un dossier autorisé ──────────────────────
_NOMS_INTERDITS = {
    ".env", "jarvis_config.json", "credentials.json", "token.json",
    "id_rsa", "id_ed25519", ".htpasswd", "ntuser.dat",
}
_EXTENSIONS_INTERDITES = {".key", ".pem", ".pfx", ".p12", ".keystore"}
_FRAGMENTS_INTERDITS = ("\\venv\\", "\\.git\\", "\\node_modules\\",
                        "\\appdata\\", "\\.ssh\\", ".bak-avant-secrets")

# Lecture plafonnée : un binaire de plusieurs Go saturerait la mémoire et la
# réponse WebSocket.
TAILLE_MAX_LECTURE = 2 * 1024 * 1024  # 2 Mo


def _taille_lisible(octets: int) -> str:
    """Taille avec l'unité adaptée — « 500 o » et non « 0.0 Mo »."""
    for unite, seuil in (("Mo", 1e6), ("Ko", 1e3)):
        if octets >= seuil:
            return f"{octets / seuil:.1f} {unite}"
    return f"{octets} o"


def dossiers_autorises():
    """Liste blanche effective, chemins réels et normalisés."""
    brut = os.environ.get("JARVIS_DOSSIERS_AUTORISES", "")
    dossiers = [d.strip() for d in brut.split(";") if d.strip()] if brut else list(_DEFAUT)
    resultat = []
    for d in dossiers:
        try:
            if os.path.isdir(d):
                resultat.append(os.path.realpath(d))
        except OSError:
            continue
    return resultat


def _sous_dossier_autorise(reel: str):
    """Le chemin réel est-il DANS un dossier autorisé ? Renvoie (bool, raison)."""
    autorises = dossiers_autorises()
    if not autorises:
        return False, "Aucun dossier autorisé n'est configuré."
    for racine in autorises:
        try:
            # commonpath compare segment par segment : contrairement à
            # startswith, « C:\\Users\\Bob2 » ne passe pas pour « C:\\Users\\Bob ».
            if os.path.commonpath([reel, racine]) == racine:
                return True, ""
        except ValueError:
            continue  # disques différents
    return False, "Chemin hors des dossiers autorisés."


def verifier(chemin: str, pour_ecriture: bool = False):
    """Valide un chemin. Renvoie (chemin_reel, None) ou (None, raison_du_refus)."""
    if not chemin or not str(chemin).strip():
        return None, "Chemin vide."

    # Barrière 1 — le chemin RÉEL avant tout contrôle. Pour une écriture, le
    # fichier peut ne pas exister : on résout alors son dossier parent, sinon
    # realpath renverrait un chemin non résolu et les liens passeraient.
    try:
        brut = os.path.abspath(os.path.expandvars(str(chemin).strip().strip('"').strip("'")))
        if pour_ecriture and not os.path.exists(brut):
            parent = os.path.realpath(os.path.dirname(brut))
            reel = os.path.join(parent, os.path.basename(brut))
        else:
            reel = os.path.realpath(brut)
    except (OSError, ValueError) as e:
        return None, f"Chemin illisible : {e}"

    ok, raison = _sous_dossier_autorise(reel)
    if not ok:
        return None, raison

    # Barrière 3 — nom, extension, fragment de chemin
    nom = os.path.basename(reel).lower()
    if nom in _NOMS_INTERDITS:
        return None, f"Fichier protégé : {os.path.basename(reel)}"
    if os.path.splitext(nom)[1] in _EXTENSIONS_INTERDITES:
        return None, "Type de fichier protégé (clé ou certificat)."
    minuscule = reel.lower()
    if any(f in minuscule for f in _FRAGMENTS_INTERDITS):
        return None, "Dossier système ou technique protégé."

    return reel, None


def lire_fichier(chemin: str, max_octets: int = TAILLE_MAX_LECTURE):
    """Lit un fichier texte. Renvoie un dict {ok, contenu|erreur, …}."""
    reel, refus = verifier(chemin)
    if refus:
        return {"ok": False, "erreur": refus}
    if not os.path.isfile(reel):
        return {"ok": False, "erreur": "Fichier introuvable."}

    taille = os.path.getsize(reel)
    if taille > max_octets:
        return {"ok": False,
                "erreur": f"Fichier trop volumineux ({_taille_lisible(taille)}, "
                          f"limite {_taille_lisible(max_octets)})."}
    try:
        with open(reel, "r", encoding="utf-8", errors="replace") as f:
            contenu = f.read()
        return {"ok": True, "chemin": reel, "taille": taille, "contenu": contenu}
    except Exception as e:
        return {"ok": False, "erreur": f"Lecture impossible : {e}"}


def ecrire_fichier(chemin: str, contenu: str, ecraser: bool = False):
    """Crée ou remplace un fichier texte.

    `ecraser=False` par défaut : écraser un fichier existant doit être un acte
    explicite, pas un effet de bord d'une phrase mal comprise.
    """
    reel, refus = verifier(chemin, pour_ecriture=True)
    if refus:
        return {"ok": False, "erreur": refus}
    if os.path.exists(reel) and not ecraser:
        return {"ok": False,
                "erreur": "Le fichier existe déjà. Demande explicitement de le remplacer."}

    try:
        os.makedirs(os.path.dirname(reel), exist_ok=True)
        # Sauvegarde avant écrasement : une erreur de l'assistant ne doit pas
        # détruire un fichier de l'utilisateur.
        if os.path.exists(reel):
            secours = reel + ".bak-jarvis"
            try:
                with open(reel, "r", encoding="utf-8", errors="replace") as src, \
                     open(secours, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            except Exception:
                pass
        with open(reel, "w", encoding="utf-8") as f:
            f.write(contenu if contenu is not None else "")
        return {"ok": True, "chemin": reel, "taille": os.path.getsize(reel)}
    except Exception as e:
        return {"ok": False, "erreur": f"Écriture impossible : {e}"}


def ajouter_au_fichier(chemin: str, contenu: str):
    """Ajoute à la fin d'un fichier (le crée s'il n'existe pas)."""
    reel, refus = verifier(chemin, pour_ecriture=True)
    if refus:
        return {"ok": False, "erreur": refus}
    try:
        os.makedirs(os.path.dirname(reel), exist_ok=True)
        with open(reel, "a", encoding="utf-8") as f:
            f.write(contenu if contenu is not None else "")
        return {"ok": True, "chemin": reel, "taille": os.path.getsize(reel)}
    except Exception as e:
        return {"ok": False, "erreur": f"Écriture impossible : {e}"}


def lister(chemin: str):
    """Liste un dossier autorisé, avec nom, type et taille."""
    reel, refus = verifier(chemin)
    if refus:
        return {"ok": False, "erreur": refus}
    if not os.path.isdir(reel):
        return {"ok": False, "erreur": "Ce n'est pas un dossier."}
    try:
        entrees = []
        for e in sorted(os.scandir(reel), key=lambda x: (not x.is_dir(), x.name.lower())):
            entrees.append({
                "nom": e.name,
                "type": "dossier" if e.is_dir() else "fichier",
                "taille": e.stat().st_size if e.is_file() else None,
            })
        return {"ok": True, "chemin": reel, "entrees": entrees}
    except Exception as e:
        return {"ok": False, "erreur": f"Lecture du dossier impossible : {e}"}
