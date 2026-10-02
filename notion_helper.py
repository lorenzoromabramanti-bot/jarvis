# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Intégration Notion (mission comparaison roadmap, 2026-09-18)
=============================================================================
Même contrat qu'obsidian_helper.py (créer/lire/supprimer/lister/chercher une
note par titre), sur Notion au lieu d'un dossier local — l'idée demandée par
Zara sur la roadmap Trillion. Toutes les notes vivent en pages sous UNE page
parente Notion (`NOTION_PARENT_PAGE_ID`) : pas de base de données Notion,
dont le schéma de propriétés varie d'un espace à l'autre et aurait rendu ce
module correct chez son auteur et cassé ailleurs.

POURQUOI UN INDEX LOCAL (notion_index.json) PLUTÔT QUE L'API DE RECHERCHE
L'API de recherche Notion est documentée comme éventuellement cohérente :
une page qui vient d'être créée peut ne pas apparaître tout de suite dans
`/v1/search`. `lire_note()` juste après `creer_ou_modifier_note()`
échouerait au hasard avec ce chemin. L'index local (titre -> id de page),
écrit au moment de la création, rend la lecture immédiate et déterministe —
même mécanique que `taches_nocturnes.py` pour sa file.

CE QUE CE MODULE NE FAIT PAS
`supprimer_note()` archive la page (`archived: true`) — Notion n'offre pas
de suppression définitive par API, et ce module ne prétend pas mieux faire
que l'API qu'il enveloppe. `rechercher_notes()` ne cherche que dans les
TITRES de l'index local, pas le contenu des pages (contrairement à
obsidian_helper.rechercher_notes qui lit chaque fichier local — ici,
lire le contenu de chaque page coûterait un appel réseau par note ; portée
volontairement réduite plutôt qu'une recherche lente qui se prétendrait
complète).

NON VÉRIFIÉ CONTRE LA VRAIE API (à dire, pas à cacher)
Écrit sans NOTION_API_KEY disponible pour cette session — la forme des
requêtes suit la documentation Notion connue à l'écriture, mais le chemin
de succès (créer une vraie page, la relire) n'a pas pu être testé en
conditions réelles. Le test joint ne couvre que la construction des
requêtes et les chemins d'erreur (clé absente, réseau injoignable), comme
_test_notifications.py le fait pour Discord. À la première utilisation
réelle : si Notion répond une erreur mentionnant la version de l'API,
mettre à jour NOTION_VERSION ci-dessous à la valeur courante documentée
sur https://developers.notion.com.

    NOTION_API_KEY        integration interne Notion (notion.so/my-integrations)
    NOTION_PARENT_PAGE_ID id de la page sous laquelle les notes sont créées
                          (partager cette page avec l'intégration créée ci-dessus)
"""

import io
import json
import os

import requests

import config
from config import nom_utilisateur

NOTION_VERSION = "2022-06-28"  # a verifier sur developers.notion.com si Notion la change
_BASE = "https://api.notion.com/v1"
_LIMITE_BLOC = 2000  # limite reelle Notion pour un rich_text.content


def _cle():
    return os.environ.get("NOTION_API_KEY")


def _page_parente():
    return os.environ.get("NOTION_PARENT_PAGE_ID")


def _entetes():
    return {
        "Authorization": "Bearer %s" % _cle(),
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _pret():
    """(ok, raison) : les deux réglages nécessaires sont-ils présents ?"""
    if not _cle():
        return False, "NOTION_API_KEY non configurée"
    if not _page_parente():
        return False, "NOTION_PARENT_PAGE_ID non configurée"
    return True, ""


# ── Index local titre -> id de page ──────────────────────────────────────

def _chemin_index():
    return config.chemin_donnees("notion_index.json", creer_dossier=True)


def _lire_index():
    try:
        with io.open(str(_chemin_index()), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire_index(donnees):
    chemin = str(_chemin_index())
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(donnees, ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)


# ── Construction des blocs ───────────────────────────────────────────────

def _decouper(texte, taille=_LIMITE_BLOC):
    """Découpe `texte` en morceaux <= taille, sans jamais lever sur un texte vide."""
    if not texte:
        return [""]
    return [texte[i:i + taille] for i in range(0, len(texte), taille)] or [""]


def _blocs_paragraphe(contenu):
    """
    Convertit un texte multi-lignes en blocs Notion "paragraph". Une ligne
    vide devient un paragraphe vide plutôt que d'être supprimée : une note
    Obsidian conserve ses lignes vides, celle-ci fait pareil.
    """
    blocs = []
    for ligne in (contenu or "").split("\n"):
        for morceau in _decouper(ligne):
            blocs.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": morceau}}]},
            })
    return blocs


# ── Requêtes ──────────────────────────────────────────────────────────────

def _requete(methode, chemin, corps=None):
    """(ok, donnees_ou_erreur). Ne lève jamais — best-effort, comme notifications.py."""
    try:
        r = requests.request(methode, _BASE + chemin, headers=_entetes(),
                             json=corps, timeout=15)
        if r.status_code >= 400:
            return False, "Notion a répondu %d : %s" % (r.status_code, r.text[:200])
        return True, (r.json() if r.text else {})
    except requests.exceptions.RequestException as e:
        return False, str(e)


_MAX_BLOCS_PAR_APPEL = 100  # limite reelle Notion pour un tableau "children"


def _tous_les_blocs(id_page):
    """
    (ok, liste_ou_raison) — tous les blocs enfants d'une page, en suivant
    la pagination Notion (`has_more`/`next_cursor`) : une note de plus de
    100 blocs ne doit pas se voir tronquée en silence à la lecture, ni à
    la relecture avant remplacement.
    """
    curseur = None
    tous = []
    while True:
        chemin = "/blocks/%s/children?page_size=100" % id_page
        if curseur:
            chemin += "&start_cursor=%s" % curseur
        ok, page = _requete("GET", chemin)
        if not ok:
            return False, page
        tous.extend(page.get("results", []))
        if not page.get("has_more"):
            return True, tous
        curseur = page.get("next_cursor")


def _ajouter_blocs_par_lots(id_page, blocs):
    """
    PATCH /blocks/{id}/children plusieurs fois si `blocs` dépasse la limite
    Notion de 100 éléments par appel. Une note de quelques lignes ne
    l'atteint jamais (100 lignes) ; sans ce découpage, une note plus longue
    échouerait juste sur ce point, silencieusement plausible vu la limite
    de 2000 caractères déjà gérée par `_decouper` juste au-dessus.
    """
    for i in range(0, len(blocs), _MAX_BLOCS_PAR_APPEL):
        lot = blocs[i:i + _MAX_BLOCS_PAR_APPEL]
        ok, res = _requete("PATCH", "/blocks/%s/children" % id_page, {"children": lot})
        if not ok:
            return False, res
    return True, ""


# ── API publique, même forme qu'obsidian_helper.py ───────────────────────

def creer_ou_modifier_note(titre, contenu):
    """Crée la page si le titre est nouveau, sinon remplace son contenu."""
    ok, raison = _pret()
    if not ok:
        return False, raison

    index = _lire_index()
    id_page = index.get(titre)
    blocs = _blocs_paragraphe(contenu)

    if id_page:
        # Remplacer le contenu : Notion n'a pas de "vider la page" direct,
        # on récupère les blocs existants (pagination comprise) et on les
        # archive un par un avant de rajouter le nouveau contenu.
        ok_liste, tous_blocs = _tous_les_blocs(id_page)
        if not ok_liste:
            return False, "lecture des blocs existants impossible : %s" % tous_blocs
        for b in tous_blocs:
            _requete("DELETE", "/blocks/%s" % b["id"])
        ok_ajout, res = _ajouter_blocs_par_lots(id_page, blocs)
        if not ok_ajout:
            return False, "mise à jour du contenu impossible : %s" % res
        return True, "Note « %s » mise à jour sur Notion, %s." % (titre, nom_utilisateur())

    corps = {
        "parent": {"page_id": _page_parente()},
        "properties": {"title": {"title": [{"text": {"content": titre}}]}},
        "children": blocs[:_MAX_BLOCS_PAR_APPEL],
    }
    ok_creation, res = _requete("POST", "/pages", corps)
    if not ok_creation:
        return False, "création impossible : %s" % res
    index[titre] = res["id"]
    _ecrire_index(index)
    if len(blocs) > _MAX_BLOCS_PAR_APPEL:
        ok_reste, res_reste = _ajouter_blocs_par_lots(res["id"], blocs[_MAX_BLOCS_PAR_APPEL:])
        if not ok_reste:
            return False, ("page créée mais contenu tronqué (au-delà de %d blocs) : %s"
                           % (_MAX_BLOCS_PAR_APPEL, res_reste))
    return True, "Note « %s » créée sur Notion, %s." % (titre, nom_utilisateur())


def lire_note(titre):
    """(ok, contenu_ou_message)."""
    ok, raison = _pret()
    if not ok:
        return False, raison
    id_page = _lire_index().get(titre)
    if not id_page:
        return False, "La note « %s » n'existe pas dans l'index Notion, %s." % (titre, nom_utilisateur())
    ok_liste, blocs = _tous_les_blocs(id_page)
    if not ok_liste:
        return False, "lecture impossible : %s" % blocs
    lignes = []
    for b in blocs:
        if b.get("type") == "paragraph":
            textes = b["paragraph"].get("rich_text", [])
            lignes.append("".join(t.get("plain_text", "") for t in textes))
    return True, "\n".join(lignes)


def supprimer_note(titre):
    """Archive la page (Notion n'a pas de suppression définitive par API)."""
    ok, raison = _pret()
    if not ok:
        return False, raison
    index = _lire_index()
    id_page = index.get(titre)
    if not id_page:
        return False, "La note « %s » n'existe pas dans l'index Notion, %s." % (titre, nom_utilisateur())
    ok_archive, res = _requete("PATCH", "/pages/%s" % id_page, {"archived": True})
    if not ok_archive:
        return False, "archivage impossible : %s" % res
    del index[titre]
    _ecrire_index(index)
    return True, "Note « %s » archivée sur Notion, %s." % (titre, nom_utilisateur())


def lister_notes():
    """[{titre, id_page}] — depuis l'index local, pas un appel réseau."""
    return [{"titre": t, "id_page": i} for t, i in sorted(_lire_index().items())]


def rechercher_notes(query):
    """
    [{titre, id_page}] dont le TITRE contient `query` (recherche locale,
    pas le contenu des pages — voir la note de portée en tête de fichier).
    """
    query = (query or "").lower()
    return [n for n in lister_notes() if query in n["titre"].lower()]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok, raison = _pret()
    print("Notion configuré : %s%s" % (ok, "" if ok else " (%s)" % raison))
    if ok:
        print("Notes indexées localement : %d" % len(lister_notes()))
