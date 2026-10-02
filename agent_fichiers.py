# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Agent de fichiers intégré (mission D3)
=====================================================
JARVIS travaille dans un projet comme le fait Claude Code — explorer, lire,
chercher, modifier, vérifier — SANS lancer d'outil externe. Ce module ne
connaît aucun fournisseur d'IA : l'appel modèle est INJECTÉ (`modele`), comme
dans orchestrateur.py. agent_gemini.py fournit celui de Gemini.

CE QUE L'AGENT PEUT FAIRE
Six outils, tous confinés au dossier du projet : lister, lire, chercher,
ecrire, remplacer, verifier (+ terminer pour rendre la main).

CE QU'IL NE PEUT PAS FAIRE — voulu, pas un oubli
  - Aucune commande shell, aucun lancement de code. Un agent qui exécute ce
    qu'il vient d'écrire, sans personne devant l'écran, est le contraire d'un
    garde-fou. verifier() contrôle la SYNTAXE (.py, .json) sans rien exécuter.
  - Aucune suppression. Renommer/supprimer se fait à la main.
  - Aucun accès hors du projet, .git, ni aux secrets (.env, clés, jetons...).
    Le contenu lu part vers le modèle : un secret lu est un secret envoyé.

LE BAC À SABLE — bac_fichiers.py
Chaque chemin donné par le modèle passe par Bac.resoudre() : forme refusée,
liens résolus, résultat confiné à la racine, .git et secrets exclus. C'est
la seule partie dont dépend la sécurité, d'où son fichier.

LIRE AVANT D'ÉCRIRE
Écraser ou remplacer un fichier exige de l'avoir lu dans cette session, et
inchangé depuis (taille + date). Sans ça, un modèle réécrit de mémoire un
fichier qu'il n'a jamais vu.

Vérifié par _test_agent_fichiers.py (bac à sable, outils, boucle — modèle
factice, aucun appel réseau) et par un essai réel contre Gemini.
"""

import ast
import codecs
import fnmatch
import json
import os
import re
import time

from agent_contrat import DECLARATIONS, SYSTEME
from bac_fichiers import Bac, MOTIFS_SECRETS

# ── Limites ──────────────────────────────────────────────────────────────
MAX_TOURS = 25
DELAI_TOTAL_S = 420
MAX_ENTREES_LISTE = 300
MAX_LIGNES_LECTURE = 400
MAX_OCTETS_LECTURE_FICHIER = 2 * 1024 * 1024
MAX_OCTETS_LUS_TOTAL = 800 * 1024
MAX_OCTETS_ECRITURE = 1024 * 1024
MAX_OCTETS_ECRITS_TOTAL = 3 * 1024 * 1024
MAX_FICHIERS_CREES = 40
MAX_RESULTATS_RECHERCHE = 60
MAX_OCTETS_FICHIER_RECHERCHE = 1024 * 1024
DELAI_RECHERCHE_S = 5.0
MAX_CARACTERES_RESULTAT = 8000
SEUIL_ELAGAGE = 300_000

# Dossiers qu'on ne détaille pas (lister/chercher) : bruit, pas du projet.
IGNORES = {".git", "node_modules", "venv", ".venv", "__pycache__", ".mypy_cache",
           ".pytest_cache", "dist", "build", ".idea", ".vscode"}
# Backtracking exponentiel : un groupe quantifie, meme sans quantificateur dedans
# ((a|aa)+ gele autant que (a+)+), ou une retroreference. Sans groupe quantifie et avec
# peu de quantificateurs, le pire cas reste polynomial : n^3 sur <= 300 caracteres.
_REGEX_DANGEREUSE = re.compile(r"\)[+*{?]|\\[1-9]")
_QUANTIFICATEUR = re.compile(r"[*+]|\{\d")
MAX_QUANTIFICATEURS_REGEX = 3
MAX_LIGNE_REGEX = 300
MAX_LIGNE_LITTERAL = 1000

def _entier(valeur, defaut, bas, haut):
    try:
        n = int(valeur)
    except (TypeError, ValueError):
        return defaut
    return max(bas, min(haut, n))


def _booleen(valeur):
    """Un modèle envoie parfois « false » en TEXTE : bool("false") vaut True."""
    if isinstance(valeur, str):
        return valeur.strip().lower() in ("true", "1", "oui", "vrai", "yes")
    return bool(valeur)


def _borner(texte, limite=MAX_CARACTERES_RESULTAT):
    texte = str(texte)
    if len(texte) <= limite:
        return texte
    return texte[:limite] + "\n[… tronqué : %d caractères de plus …]" % (len(texte) - limite)


# ── Les outils ───────────────────────────────────────────────────────────

def _est_lien(entree):
    try:
        return entree.is_symlink() or getattr(entree, "is_junction", lambda: False)()
    except OSError:
        return True


def _ecrire_atomique(reel, octets):
    """Écrit puis remplace d'un coup : un plantage ne laisse pas un fichier à moitié écrit."""
    tmp = reel + ".jarvis-tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(octets)
        os.replace(tmp, reel)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


class Session:
    """L'état d'UNE exécution : ce qui a été lu, écrit, et les budgets."""

    def __init__(self, racine):
        self.bac = Bac(racine)
        self.lus = {}             # chemin réel -> (mtime_ns, taille) à la lecture
        self.ecrits = []          # chemins relatifs, dans l'ordre
        self.fichiers_crees = 0
        self.octets_lus = 0
        self.octets_ecrits = 0
        self.termine = None
        self.trace = []           # (outil, chemin) — pour le journal

    def appeler(self, nom, args):
        """Toujours une CHAÎNE : une erreur est renvoyée AU MODÈLE, qui s'y adapte."""
        if not isinstance(nom, str) or nom not in {d["nom"] for d in DECLARATIONS}:
            return "ERREUR : outil inconnu %r. Outils : %s" % (
                nom, ", ".join(d["nom"] for d in DECLARATIONS))
        if not isinstance(args, dict):
            args = {}
        try:
            sortie = getattr(self, "outil_" + nom)(**args)
        except TypeError as e:
            return "ERREUR : arguments invalides pour %s (%s)" % (nom, e)
        except Exception as e:
            return "ERREUR : %s : %s" % (type(e).__name__, e)
        self.trace.append((nom, str(args.get("chemin", ""))[:80]))
        return _borner(sortie)

    # -- lecture ---------------------------------------------------------
    def outil_lister(self, chemin=".", profondeur=2):
        reel, err = self.bac.resoudre(chemin)
        if err:
            return "ERREUR : " + err
        if not os.path.isdir(reel):
            return "ERREUR : pas un dossier : %s" % chemin
        prof = _entier(profondeur, 2, 1, 3)
        lignes = []

        def marcher(dossier, niveau):
            try:
                entrees = sorted(os.scandir(dossier),
                                 key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
            except OSError as e:
                lignes.append("  " * niveau + "[illisible : %s]" % e)
                return
            for e in entrees:
                if len(lignes) >= MAX_ENTREES_LISTE:
                    return
                marge = "  " * niveau
                if _est_lien(e):
                    lignes.append("%s%s  [lien, non suivi]" % (marge, e.name))
                elif e.is_dir(follow_symlinks=False):
                    if e.name.lower() in IGNORES:
                        lignes.append("%s%s/  [non exploré]" % (marge, e.name))
                    else:
                        lignes.append("%s%s/" % (marge, e.name))
                        if niveau + 1 < prof:
                            marcher(e.path, niveau + 1)
                else:
                    try:
                        taille = e.stat(follow_symlinks=False).st_size
                    except OSError:
                        taille = -1
                    lignes.append("%s%s  (%d o)" % (marge, e.name, taille))

        marcher(reel, 0)
        if len(lignes) >= MAX_ENTREES_LISTE:
            lignes.append("[… liste tronquée à %d entrées : précise un sous-dossier …]" % MAX_ENTREES_LISTE)
        return "\n".join(lignes) or "(dossier vide)"

    def outil_lire(self, chemin, debut=1, fin=None):
        reel, err = self.bac.resoudre(chemin)
        if err:
            return "ERREUR : " + err
        if not os.path.isfile(reel):
            return "ERREUR : fichier introuvable : %s" % chemin
        st = os.stat(reel)
        if st.st_size > MAX_OCTETS_LECTURE_FICHIER:
            return "ERREUR : fichier trop gros (%d Ko) — utilise chercher" % (st.st_size // 1024)
        if self.octets_lus >= MAX_OCTETS_LUS_TOTAL:
            return "ERREUR : budget de lecture épuisé — termine avec ce que tu sais"
        with open(reel, "rb") as f:
            donnees = f.read()
        if b"\x00" in donnees[:8192]:
            return "ERREUR : fichier binaire, non lisible : %s" % chemin
        lignes = donnees.decode("utf-8", errors="replace").splitlines()
        total = len(lignes)
        if total == 0:
            self.lus[reel] = (st.st_mtime_ns, st.st_size)
            return "%s — fichier vide" % self.bac.relatif(reel)
        debut = _entier(debut, 1, 1, max(1, total))
        fin_max = debut + MAX_LIGNES_LECTURE - 1
        fin = _entier(fin, fin_max, debut, fin_max) if fin is not None else fin_max
        fin = min(fin, total)
        extrait = "\n".join("%d\t%s" % (i, l) for i, l in enumerate(lignes[debut - 1:fin], start=debut))
        self.octets_lus += len(extrait)
        self.lus[reel] = (st.st_mtime_ns, st.st_size)
        suite = "" if fin >= total else "\n[… suite : lire(debut=%d) …]" % (fin + 1)
        return "%s — lignes %d-%d sur %d\n%s%s" % (self.bac.relatif(reel), debut, fin, total, extrait, suite)

    def _marcher_fichiers(self, reel, glob):
        """Les fichiers d'un dossier, sans suivre les liens ni les dossiers ignorés."""
        pile = [reel]
        while pile:
            dossier = pile.pop()
            try:
                entrees = sorted(os.scandir(dossier), key=lambda e: e.name.lower())
            except OSError:
                continue
            for e in entrees:
                if _est_lien(e):
                    continue
                nom = e.name.lower()
                if any(fnmatch.fnmatch(nom, m) for m in MOTIFS_SECRETS):
                    continue                    # fichier OU dossier sensible
                if e.is_dir(follow_symlinks=False):
                    if nom not in IGNORES:
                        pile.append(e.path)
                    continue
                if fnmatch.fnmatch(nom, str(glob).lower()):
                    yield e.path

    def outil_chercher(self, motif, chemin=".", glob="*", regex=False):
        if not isinstance(motif, str) or not motif or len(motif) > 200:
            return "ERREUR : motif vide ou trop long (200 caractères max)"
        reel, err = self.bac.resoudre(chemin)
        if err:
            return "ERREUR : " + err
        if not os.path.isdir(reel):
            return "ERREUR : pas un dossier : %s" % chemin
        if _booleen(regex):
            if _REGEX_DANGEREUSE.search(motif) or len(_QUANTIFICATEUR.findall(motif)) > MAX_QUANTIFICATEURS_REGEX:
                return ("ERREUR : expression régulière refusée (groupe quantifié ou plus de %d quantificateurs : "
                        "risque de blocage). Simplifie-la ou cherche un mot exact." % MAX_QUANTIFICATEURS_REGEX)
            try:
                trouve = re.compile(motif, re.IGNORECASE).search
            except re.error as e:
                return "ERREUR : expression régulière invalide : %s" % e
        else:
            bas = motif.lower()
            trouve = lambda ligne: bas in ligne.lower()
        coupe = MAX_LIGNE_REGEX if _booleen(regex) else MAX_LIGNE_LITTERAL
        resultats, echeance, interrompu = [], time.monotonic() + DELAI_RECHERCHE_S, False
        for fichier in self._marcher_fichiers(reel, glob):
            if interrompu:
                break
            try:
                if os.path.getsize(fichier) > MAX_OCTETS_FICHIER_RECHERCHE:
                    continue
                with open(fichier, "rb") as f:
                    donnees = f.read()
            except OSError:
                continue
            if b"\x00" in donnees[:4096]:
                continue
            for i, ligne in enumerate(donnees.decode("utf-8", errors="replace").splitlines(), 1):
                if time.monotonic() > echeance:
                    interrompu = True
                    break
                if trouve(ligne[:coupe]):
                    resultats.append("%s:%d: %s" % (self.bac.relatif(fichier), i, ligne.strip()[:200]))
                    if len(resultats) >= MAX_RESULTATS_RECHERCHE:
                        resultats.append("[… %d résultats affichés, il y en a peut-être d'autres : affine le motif …]"
                                         % MAX_RESULTATS_RECHERCHE)
                        return "\n".join(resultats)
        if interrompu:
            resultats.append("[… recherche interrompue : délai de %ds …]" % DELAI_RECHERCHE_S)
        return "\n".join(resultats) or "aucun résultat"

    # -- écriture --------------------------------------------------------
    def _verifier_ecrasement(self, reel, chemin):
        """None si on peut écraser, sinon la raison. Lu, et inchangé depuis."""
        if reel not in self.lus:
            return "le fichier existe déjà : lis-le d'abord (lire) avant de le modifier"
        st = os.stat(reel)
        if (st.st_mtime_ns, st.st_size) != self.lus[reel]:
            return "le fichier a changé depuis ta lecture : relis-le (lire)"
        return None

    def _noter_ecriture(self, reel):
        st = os.stat(reel)
        self.lus[reel] = (st.st_mtime_ns, st.st_size)      # relire n'est pas nécessaire ensuite
        rel = self.bac.relatif(reel)
        if rel not in self.ecrits:
            self.ecrits.append(rel)

    def outil_ecrire(self, chemin, contenu):
        if not isinstance(contenu, str):
            return "ERREUR : contenu invalide (texte attendu)"
        octets = contenu.encode("utf-8")
        if len(octets) > MAX_OCTETS_ECRITURE:
            return "ERREUR : fichier trop gros (%d Ko, max %d Ko)" % (len(octets) // 1024, MAX_OCTETS_ECRITURE // 1024)
        reel, err = self.bac.resoudre(chemin, ecriture=True)
        if err:
            return "ERREUR : " + err
        if os.path.isdir(reel):
            return "ERREUR : %s est un dossier" % chemin
        if self.octets_ecrits + len(octets) > MAX_OCTETS_ECRITS_TOTAL:
            return "ERREUR : budget d'écriture épuisé — termine"
        if os.path.exists(reel):
            raison = self._verifier_ecrasement(reel, chemin)
            if raison:
                return "ERREUR : " + raison
            with open(reel, "rb") as f:
                ancien = f.read()
            try:
                ancien.decode("utf-8")
            except UnicodeDecodeError:
                return "ERREUR : le fichier existant n'est pas en UTF-8 : je ne l'écrase pas (les accents seraient abîmés)"
            if b"\r\n" in ancien and b"\n" not in ancien.replace(b"\r\n", b""):
                octets = contenu.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")   # garde les fins de ligne
            if ancien.startswith(codecs.BOM_UTF8) and not octets.startswith(codecs.BOM_UTF8):
                octets = codecs.BOM_UTF8 + octets                # garde la signature UTF-8
            nouveau = False
        else:
            if self.fichiers_crees >= MAX_FICHIERS_CREES:
                return "ERREUR : trop de fichiers créés (max %d)" % MAX_FICHIERS_CREES
            os.makedirs(os.path.dirname(reel), exist_ok=True)
            nouveau = True
        _ecrire_atomique(reel, octets)
        if nouveau:
            self.fichiers_crees += 1
        self.octets_ecrits += len(octets)
        self._noter_ecriture(reel)
        return "OK : %s écrit (%d octets)" % (self.bac.relatif(reel), len(octets))

    def outil_remplacer(self, chemin, ancien, nouveau, tout=False):
        if not isinstance(ancien, str) or not isinstance(nouveau, str) or not ancien:
            return "ERREUR : « ancien » et « nouveau » doivent être du texte, « ancien » non vide"
        if ancien == nouveau:
            return "ERREUR : « ancien » et « nouveau » sont identiques"
        reel, err = self.bac.resoudre(chemin, ecriture=True)
        if err:
            return "ERREUR : " + err
        if not os.path.isfile(reel):
            return "ERREUR : fichier introuvable : %s" % chemin
        raison = self._verifier_ecrasement(reel, chemin)
        if raison:
            return "ERREUR : " + raison
        with open(reel, "rb") as f:
            donnees = f.read()
        if b"\x00" in donnees[:8192]:
            return "ERREUR : fichier binaire"
        try:
            texte = donnees.decode("utf-8")
        except UnicodeDecodeError:
            return "ERREUR : fichier non UTF-8 : je ne le modifie pas (les accents seraient abîmés)"
        crlf_pur = "\r\n" in texte and "\n" not in texte.replace("\r\n", "")
        base = texte.replace("\r\n", "\n") if crlf_pur else texte
        cherche, remplace = (ancien.replace("\r\n", "\n"), nouveau.replace("\r\n", "\n")) if crlf_pur else (ancien, nouveau)
        n = base.count(cherche)
        if n == 0:
            return "ERREUR : texte introuvable — il doit être identique caractère pour caractère (indentation comprise). Relis le fichier."
        if n > 1 and not _booleen(tout):
            return "ERREUR : %d occurrences — ajoute du contexte autour, ou passe tout=true" % n
        resultat = base.replace(cherche, remplace)
        if crlf_pur:
            resultat = resultat.replace("\n", "\r\n")
        sortie = resultat.encode("utf-8")
        if len(sortie) > MAX_OCTETS_ECRITURE or self.octets_ecrits + len(sortie) > MAX_OCTETS_ECRITS_TOTAL:
            return "ERREUR : budget d'écriture dépassé"
        _ecrire_atomique(reel, sortie)
        self.octets_ecrits += len(sortie)
        self._noter_ecriture(reel)
        return "OK : %d remplacement(s) dans %s" % (n, self.bac.relatif(reel))

    def outil_verifier(self, chemin):
        reel, err = self.bac.resoudre(chemin)
        if err:
            return "ERREUR : " + err
        if not os.path.isfile(reel):
            return "ERREUR : fichier introuvable : %s" % chemin
        ext = os.path.splitext(reel)[1].lower()
        if ext not in (".py", ".json"):
            return "aucun vérificateur pour %s (seuls .py et .json sont contrôlés)" % (ext or "ce type")
        with open(reel, "rb") as f:
            source = f.read().decode("utf-8", errors="replace")
        try:
            if ext == ".py":
                ast.parse(source, filename=os.path.basename(reel))
            else:
                json.loads(source)
        except SyntaxError as e:
            return "ERREUR de syntaxe ligne %s : %s" % (e.lineno, e.msg)
        except json.JSONDecodeError as e:
            return "ERREUR JSON ligne %d : %s" % (e.lineno, e.msg)
        except (RecursionError, MemoryError):
            return "ERREUR : fichier trop imbriqué pour être contrôlé"
        return "OK : syntaxe valide (rien n'a été exécuté)"

    def outil_terminer(self, resume):
        if not isinstance(resume, str) or not resume.strip():
            return "ERREUR : « resume » doit être un texte non vide"
        self.termine = resume.strip()
        return "OK"


# ── La boucle ────────────────────────────────────────────────────────────

def _elaguer(historique):
    """Le contexte grossit à chaque outil : on vide les plus vieux résultats au-delà du seuil."""
    total = sum(len(m.get("resultat", "")) for m in historique if m["role"] == "outil")
    for m in historique[:-8]:
        if total <= SEUIL_ELAGAGE:
            return
        if m["role"] == "outil" and len(m["resultat"]) > 80:
            total -= len(m["resultat"]) - 32
            m["resultat"] = "[ancien résultat élagué]"


def _bilan(succes, resume, session, tours, erreur=None):
    return {"succes": succes, "resume": resume, "erreur": erreur, "tours": tours,
            "ecrits": list(session.ecrits) if session else [],
            "actions": list(session.trace) if session else []}


def executer_agent(racine, tache, modele, *, max_tours=MAX_TOURS, delai_total=DELAI_TOTAL_S,
                   horloge=time.monotonic, pause=time.sleep, journal=None):
    """
    Boucle agentique : le modèle appelle des outils jusqu'à `terminer`.

    modele(systeme, historique, declarations) -> {"texte": str, "appels":
        [{"id", "nom", "args"}], "brut": <libre>}.  Doit lever en cas d'échec.
    Renvoie {"succes", "resume", "erreur", "tours", "ecrits", "actions"}.
    Ne lève jamais.
    """
    journal = journal or (lambda ligne: None)
    try:
        session = Session(racine)
    except ValueError as e:
        return _bilan(False, "", None, 0, str(e))
    if not isinstance(tache, str) or not tache.strip():
        return _bilan(False, "", session, 0, "tâche vide")

    historique = [{"role": "user", "texte": "TÂCHE : " + tache.strip()}]
    debut = horloge()
    for tour in range(1, max_tours + 1):
        if horloge() - debut > delai_total:
            return _bilan(False, "", session, tour - 1, "délai dépassé (%d s)" % delai_total)
        reponse, derniere = None, None
        for essai in (1, 2):           # un seul nouvel essai : une panne réseau passagère ne doit pas tout perdre
            try:
                reponse = modele(SYSTEME, historique, DECLARATIONS)
                derniere = None
                break
            except Exception as e:
                derniere = e
                if essai == 1:
                    pause(2)
        if derniere is not None:
            return _bilan(False, "", session, tour - 1,
                          "le modèle a échoué au tour %d : %s" % (tour, _borner(derniere, 300)))
        if not isinstance(reponse, dict):
            return _bilan(False, "", session, tour - 1, "réponse invalide du modèle (un dict était attendu)")
        texte = str(reponse.get("texte") or "").strip()
        appels = [a for a in (reponse.get("appels") or []) if isinstance(a, dict)]
        historique.append({"role": "assistant", "texte": texte, "appels": appels,
                           "brut": reponse.get("brut")})
        if not appels:
            if texte:
                return _bilan(True, texte, session, tour)
            return _bilan(False, "", session, tour, "réponse vide du modèle")
        for a in appels:
            resultat = session.appeler(a.get("nom"), a.get("args"))
            journal("[AGENT] tour %d : %s(%s) -> %s" % (
                tour, a.get("nom"), str((a.get("args") or {}).get("chemin", ""))[:60], resultat[:60].replace("\n", " ")))
            historique.append({"role": "outil", "id": a.get("id"), "nom": a.get("nom"),
                               "resultat": resultat})
        if session.termine is not None:
            return _bilan(True, session.termine, session, tour)
        _elaguer(historique)
    return _bilan(False, "", session, max_tours, "pas terminé après %d tours" % max_tours)
