# -*- coding: utf-8 -*-
r"""
J.A.R.V.I.S — Veille de sujets
===============================
« Surveille les annonces AMD » — et JARVIS regarde une fois par jour s'il y
a du nouveau, puis le dit au briefing du matin. La veille du ciel et celle
des fusées existaient déjà, chacune codée en dur pour son sujet. Ici c'est
l'utilisateur qui choisit ce qu'on surveille.

UNE FOIS PAR JOUR, PAS PLUS
Une veille qui interroge toutes les cinq minutes finit par déranger sans
rien apprendre, et se fait couper par la source. Chaque sujet garde la date
de son dernier contrôle ; `a_controler()` ne rend que ceux dont vingt-quatre
heures se sont écoulées.

CE QUI EST « NOUVEAU »
Le lien, jamais le titre : deux médias titrent différemment le même fait, et
un même média retitre son article dans la journée. Les liens déjà vus sont
gardés (200 par sujet, les plus récents) — sans cela, chaque contrôle
réannoncerait toute la page comme une nouveauté.

LA SOURCE
Le flux RSS de Google Actualités : pas de clé, pas de quota déclaré, du XML
stable. `controler()` accepte un récupérateur injecté — c'est ce qui permet
de vérifier la déduplication et la cadence sans toucher au réseau.

    venv\Scripts\python.exe veille_sujets.py
"""

import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import config

FICHIER = "veille_sujets.json"
INTERVALLE = 24 * 3600      # un contrôle par sujet et par jour
MEMOIRE_LIENS = 200         # liens retenus par sujet, pour ne pas réannoncer
LIMITE_SUJETS = 20
LIMITE_ANNONCE = 3          # titres cités à voix haute ; le reste est compté
_TIMEOUT = 10
_UA = {"User-Agent": "JARVIS/1.0"}


def url_flux(sujet):
    """Le flux Google Actualités pour ce sujet, en français."""
    return ("https://news.google.com/rss/search?q=%s&hl=fr&gl=FR&ceid=FR:fr"
            % urllib.parse.quote_plus(str(sujet)))


def _recuperer_reseau(url):
    requete = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(requete, timeout=_TIMEOUT) as reponse:
        return reponse.read().decode("utf-8", errors="replace")


def articles(xml_brut):
    """
    [(titre, lien)] à partir du XML du flux. Liste vide si le flux est
    illisible — un XML cassé ne doit pas arrêter la boucle de veille, mais
    il ne doit pas non plus passer pour « aucune actualité » : c'est
    `controler()` qui distingue les deux, avec sa raison.
    """
    try:
        racine = ET.fromstring(xml_brut)
    except ET.ParseError:
        return []
    sortie = []
    for item in racine.iter("item"):
        titre = (item.findtext("title") or "").strip()
        lien = (item.findtext("link") or "").strip()
        if titre and lien:
            sortie.append((titre, lien))
    return sortie


# ── Le fichier des sujets ────────────────────────────────────────────────

def _chemin():
    return config.chemin_donnees(FICHIER, creer_dossier=True)


def _lire_tout():
    try:
        with io.open(str(_chemin()), encoding="utf-8") as f:
            donnees = json.load(f)
        if isinstance(donnees.get("sujets"), list):
            return donnees
    except Exception:
        pass
    return {"sujets": []}


def _ecrire_tout(donnees):
    chemin = str(_chemin())
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(donnees, ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)


def _cle(sujet):
    return " ".join(str(sujet or "").lower().split())


def lister():
    """Les sujets surveillés, sans la liste des liens déjà vus."""
    return [{"sujet": s["sujet"], "ajoute_le": s["ajoute_le"],
             "dernier_controle": s.get("dernier_controle"),
             "vus": len(s.get("liens_vus", []))}
            for s in _lire_tout()["sujets"]]


def ajouter(sujet):
    """
    Met un sujet sous surveillance. Renvoie (ok, raison).

    Le premier contrôle n'annonce rien : il enregistre ce qui existe DÉJÀ.
    Sans cela, ajouter « AMD » ferait réciter dix articles vieux d'une
    semaine comme autant de nouvelles — l'inverse de ce qu'on demande.
    """
    cle = _cle(sujet)
    if len(cle) < 3:
        return False, "un sujet de veille doit faire au moins trois caractères"
    donnees = _lire_tout()
    if any(_cle(s["sujet"]) == cle for s in donnees["sujets"]):
        return False, "« %s » est déjà sous surveillance" % sujet
    if len(donnees["sujets"]) >= LIMITE_SUJETS:
        return False, ("déjà %d sujets sous surveillance, c'est le maximum"
                       % LIMITE_SUJETS)
    donnees["sujets"].append({
        "sujet": str(sujet).strip(),
        "ajoute_le": time.time(),
        "dernier_controle": None,
        "liens_vus": [],
    })
    _ecrire_tout(donnees)
    return True, "« %s » est sous surveillance" % sujet


def retirer(sujet):
    """Retire un sujet. Renvoie (ok, raison)."""
    cle = _cle(sujet)
    donnees = _lire_tout()
    restants = [s for s in donnees["sujets"] if _cle(s["sujet"]) != cle]
    if len(restants) == len(donnees["sujets"]):
        return False, "« %s » n'était pas sous surveillance" % sujet
    donnees["sujets"] = restants
    _ecrire_tout(donnees)
    return True, "« %s » n'est plus surveillé" % sujet


def a_controler(maintenant=None):
    """Les sujets dont le dernier contrôle remonte à plus de 24 heures."""
    ref = maintenant if maintenant is not None else time.time()
    return [s["sujet"] for s in _lire_tout()["sujets"]
            if s.get("dernier_controle") is None
            or ref - s["dernier_controle"] >= INTERVALLE]


def controler(sujet, recuperateur=None, maintenant=None):
    """
    Interroge la source pour un sujet. Renvoie (nouveaux, raison).

    `nouveaux` : [(titre, lien)] jamais vus. Vide et sans raison = rien de
    neuf, ce qui est le cas normal. `raison` non vide = le contrôle a
    ÉCHOUÉ (réseau, flux illisible) : la date de dernier contrôle n'est
    alors pas mise à jour, pour réessayer au tour suivant plutôt que
    d'attendre un jour de plus après une coupure réseau.
    """
    cle = _cle(sujet)
    donnees = _lire_tout()
    entree = next((s for s in donnees["sujets"] if _cle(s["sujet"]) == cle), None)
    if entree is None:
        return [], "« %s » n'est pas sous surveillance" % sujet

    recuperateur = recuperateur or _recuperer_reseau
    try:
        brut = recuperateur(url_flux(entree["sujet"]))
    except Exception as e:
        return [], "source injoignable : %s" % e

    trouves = articles(brut)
    if not trouves:
        return [], "flux illisible ou vide pour « %s »" % entree["sujet"]

    deja = set(entree.get("liens_vus", []))
    premiere_fois = entree.get("dernier_controle") is None
    nouveaux = [(t, l) for t, l in trouves if l not in deja]

    entree["liens_vus"] = ([l for _, l in trouves] + list(deja))[:MEMOIRE_LIENS]
    entree["dernier_controle"] = maintenant if maintenant is not None else time.time()
    _ecrire_tout(donnees)

    # Premier contrôle : on retient l'existant, on n'annonce rien.
    return ([], "") if premiere_fois else (nouveaux, "")


# ── Ce qui reste à dire ──────────────────────────────────────────────────
#
# La veille tourne pendant que l'utilisateur travaille. L'interrompre pour
# annoncer un article serait le comportement d'une notification, pas d'un
# assistant : ce qui est trouvé est DÉPOSÉ, et dit au briefing suivant.
# Discord, lui, est poussé tout de suite — c'est là qu'on regarde quand on
# n'est pas devant le PC (voir notifications.py).

def deposer_annonce(texte):
    """Met une phrase de côté pour le prochain briefing."""
    if not str(texte or "").strip():
        return False
    donnees = _lire_tout()
    donnees.setdefault("annonces", []).append(
        {"texte": str(texte), "depose_le": time.time()})
    _ecrire_tout(donnees)
    return True


def annonces_en_attente():
    """Les phrases déposées, jamais encore dites. Ne modifie rien."""
    return [a["texte"] for a in _lire_tout().get("annonces", [])]


def vider_annonces():
    """
    À appeler UNE FOIS les annonces réellement prononcées.

    Séparé de la lecture, comme taches_nocturnes.marquer_vue : si le
    briefing échoue entre les deux, la nouvelle est encore là au prochain
    lancement au lieu d'avoir disparu sans être dite.
    """
    donnees = _lire_tout()
    donnees["annonces"] = []
    _ecrire_tout(donnees)


def _sans_accents(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower())
                   if unicodedata.category(c) != "Mn")


# Les tournures qui ouvrent une veille. Ordre important : les plus longues
# d'abord, sinon « surveille » couperait « surveille les actualites sur ».
_OUVERTURES = (
    "surveille les actualites sur", "surveille les actualites de",
    "surveille les annonces sur", "surveille les annonces de",
    "surveille les nouvelles sur", "surveille les nouvelles de",
    "tiens moi au courant de", "tiens-moi au courant de",
    "tiens moi au courant sur", "tiens-moi au courant sur",
    "surveille le sujet", "surveille l'actualite de", "surveille l actualite de",
    "fais une veille sur", "veille sur", "surveille",
)

_FERMETURES = (
    "arrete de surveiller", "arrete la veille sur", "arrete la veille de",
    "ne surveille plus", "retire la veille sur", "retire la veille de",
    "supprime la veille sur", "supprime la veille de",
)

_INVENTAIRES = (
    "quelles veilles", "quelle veille", "mes veilles", "liste des veilles",
    "liste tes veilles", "qu'est-ce que tu surveilles", "qu est ce que tu surveilles",
    "que surveilles-tu", "que surveilles tu", "sujets surveilles",
)


def analyser_demande(texte):
    """
    (action, sujet) pour une phrase. action vaut None, "lister", "ajouter"
    ou "retirer".

    Séparé de main2.py pour une raison précise : c'est la partie qui peut
    se tromper de sujet (« surveille les annonces AMD » -> « les annonces
    AMD » au lieu d'« AMD »), donc celle qui doit être vérifiable seule.

    Les fermetures sont examinées AVANT les ouvertures : « arrête de
    surveiller AMD » contient « surveille », et serait sinon compris
    comme une demande d'ajout.
    """
    t = _sans_accents(texte)
    if any(m in t for m in _INVENTAIRES):
        return "lister", ""
    for motif in _FERMETURES:
        if motif in t:
            return "retirer", _nettoyer_sujet(t.split(motif, 1)[1])
    for motif in _OUVERTURES:
        if motif in t:
            sujet = _nettoyer_sujet(t.split(motif, 1)[1])
            return ("ajouter", sujet) if sujet else (None, "")
    return None, ""


_MOTS_VIDES = ("les ", "le ", "la ", "l'", "des ", "de ", "du ", "sur ", "pour ",
               "actualites ", "annonces ", "nouvelles ", "infos ", "sujet ")


def _nettoyer_sujet(brut):
    """Le sujet seul : sans ponctuation finale ni article de tête."""
    sujet = str(brut or "").strip(" .!?,;:«»\"'")
    change = True
    while change:
        change = False
        for mot in _MOTS_VIDES:
            if sujet.startswith(mot):
                sujet = sujet[len(mot):].lstrip()
                change = True
    return sujet.strip()


def phrase(sujet, nouveaux):
    """La phrase à dire pour un lot de nouveautés. Vide si rien à dire."""
    if not nouveaux:
        return ""
    titres = [t for t, _ in nouveaux[:LIMITE_ANNONCE]]
    reste = len(nouveaux) - len(titres)
    texte = "Sur « %s » : %s" % (sujet, " ; ".join(titres))
    if reste > 0:
        texte += ", et %d autre%s" % (reste, "s" if reste > 1 else "")
    return texte + "."


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sujets = lister()
    print()
    print("=" * 70)
    print("VEILLE DE SUJETS")
    print("=" * 70)
    if not sujets:
        print("  aucun sujet sous surveillance")
    for s in sujets:
        quand = ("jamais" if not s["dernier_controle"]
                 else time.strftime("%d/%m %H:%M", time.localtime(s["dernier_controle"])))
        print("  %-30s dernier contrôle : %-12s (%d liens connus)"
              % (s["sujet"], quand, s["vus"]))
    print("  à contrôler maintenant : %s" % (", ".join(a_controler()) or "aucun"))
    print("=" * 70)
