# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Bac à sable des chemins de l'agent de fichiers
=============================================================
Résout un chemin donné par un MODÈLE sous une racine de projet, ou dit
pourquoi non. Séparé de agent_fichiers.py : c'est la seule partie dont
dépend la sécurité, elle doit se relire seule.

Un chemin donné par un modèle est une ENTRÉE NON FIABLE, même sans
malveillance (un modèle hallucine « ../../ » ou « C:/Windows »). On refuse
d'abord la FORME (absolu, « .. », « : » — qui ouvre les flux NTFS —, noms
réservés Windows, noms courts ~1, point/espace final), puis on résout les liens et jonctions
avec realpath et on vérifie que le RÉSULTAT reste sous la racine : c'est ce
deuxième contrôle qui attrape une jonction posée dans le projet et pointant
dehors. La liste noire (.git, secrets) est rejouée sur le chemin RÉSOLU, sinon
un lien « doc -> .git » la contournerait.
"""

import fnmatch
import os
import re

# Où on n'écrit jamais.
# Dont .vscode/.idea/.husky/.githooks : ce qui s'y trouve s'exécute tout seul
# (ouverture du dossier, commit) sans que personne relise.
ECRITURE_INTERDITE = {".git", "node_modules", "venv", ".venv", "__pycache__",
                      ".vscode", ".idea", ".husky", ".githooks"}
# Noms de fichiers sensibles : refusés en lecture COMME en écriture.
MOTIFS_SECRETS = (
    ".env", ".env.*", "*.env", "*.pem", "*.key", "*.pfx", "*.p12", "*.kdbx",
    "*.jks", "*.keystore", "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*",
    "credentials*", "*credentials*.json", "*secret*", "*.token",
    "token*.pickle", "token*.json", ".netrc", ".npmrc", ".pypirc",
    ".ssh", ".aws", ".gnupg", ".kube", ".docker",
)
_RESERVES_WINDOWS = ({"con", "prn", "aux", "nul", "conin$", "conout$"}
                     | {"com%d" % i for i in range(1, 10)}
                     | {"lpt%d" % i for i in range(1, 10)}
                     | {"com¹", "com²", "com³", "lpt¹", "lpt²", "lpt³"})


class Bac:
    """Résout des chemins RELATIFS sous une racine, ou dit pourquoi non."""

    def __init__(self, racine):
        if not racine or not os.path.isdir(racine):
            raise ValueError("dossier de projet introuvable : %r" % (racine,))
        self.racine = os.path.realpath(racine)
        self._racine_nc = os.path.normcase(self.racine)

    @staticmethod
    def _decouper(rel):
        """(morceaux, None) si la FORME est acceptable, sinon (None, raison)."""
        if not isinstance(rel, str):
            return None, "chemin invalide (texte attendu)"
        rel = rel.strip()
        if rel in ("", "."):
            return [], None
        if len(rel) > 240:
            return None, "chemin trop long"
        if any(ord(c) < 32 for c in rel):
            return None, "caractère de contrôle interdit dans le chemin"
        if re.match(r"^[A-Za-z]:", rel) or rel.startswith(("/", "\\")):
            return None, "chemin absolu interdit : donne un chemin RELATIF à la racine du projet"
        morceaux = [p for p in re.split(r"[\\/]+", rel) if p not in ("", ".")]
        for p in morceaux:
            if p == "..":
                return None, "« .. » interdit : reste dans le projet"
            if any(c in p for c in '<>:"|?*'):
                return None, "caractère interdit dans « %s »" % p
            if p != p.rstrip(" ."):
                return None, "nom invalide (point ou espace final) : %s" % p
            if p.split(".")[0].rstrip(" ").lower() in _RESERVES_WINDOWS:
                return None, "nom réservé par Windows : %s" % p
            # « GIT~1 » désigne « .git » (nom court 8.3) : la liste noire, qui lit les
            # noms, ne le verrait pas. Aucun projet n'a besoin d'écrire un tel nom.
            if re.search(r"~\d", p):
                return None, "nom court Windows (~1) interdit : %s" % p
        return morceaux, None

    @staticmethod
    def _refus_liste_noire(morceaux, ecriture):
        bas = [m.lower() for m in morceaux]
        if ".git" in bas:
            return "le dossier .git est interdit"
        if ecriture and any(m in ECRITURE_INTERDITE for m in bas):
            return "écriture interdite dans %s" % ", ".join(sorted(set(bas) & ECRITURE_INTERDITE))
        # TOUS les composants, pas seulement le dernier : « secrets/notes.txt »
        # ou « .ssh/config » sont sensibles par leur DOSSIER.
        if any(fnmatch.fnmatch(m, p) for m in bas for p in MOTIFS_SECRETS):
            return "fichier ou dossier sensible (secrets) : refusé"
        return None

    def dans_racine(self, reel):
        try:
            return os.path.commonpath([os.path.normcase(reel), self._racine_nc]) == self._racine_nc
        except ValueError:            # autre lecteur
            return False

    def resoudre(self, rel, ecriture=False):
        """(chemin_reel, None) ou (None, raison)."""
        morceaux, err = self._decouper(rel)
        if err:
            return None, err
        err = self._refus_liste_noire(morceaux, ecriture)
        if err:
            return None, err
        reel = os.path.realpath(os.path.join(self.racine, *morceaux))
        if not self.dans_racine(reel):
            return None, "hors du projet (lien symbolique ou jonction ?)"
        # La liste noire rejouée sur le chemin RÉSOLU : « doc -> .git » ne la contourne pas.
        relreel = os.path.relpath(reel, self.racine)
        if relreel != ".":
            err = self._refus_liste_noire(relreel.split(os.sep), ecriture)
            if err:
                return None, err + " (via un lien)"
        return reel, None

    def relatif(self, reel):
        return os.path.relpath(reel, self.racine).replace(os.sep, "/")
