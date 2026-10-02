# -*- coding: utf-8 -*-
"""
Vérifie notion_helper.py — construction des requêtes et chemins d'erreur.

Ne couvre PAS un vrai aller-retour contre l'API Notion (pas de clé
disponible pour écrire ce module, voir sa docstring) : ce test valide la
logique locale (index, découpage en blocs) et les échecs propres (pas de
clé, réseau injoignable), comme _test_notifications.py le fait pour
Discord sans jamais poster pour de vrai.
"""

import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import notion_helper as nh

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


_sauv_cle = os.environ.pop("NOTION_API_KEY", None)
_sauv_parent = os.environ.pop("NOTION_PARENT_PAGE_ID", None)

_chemin_index = nh._chemin_index()
_sauv_index = None
if os.path.exists(_chemin_index):
    _sauv_index = io.open(_chemin_index, encoding="utf-8").read()

try:
    # ── Découpage en blocs : pas de réseau nécessaire ──────────────────
    verifier("texte vide -> un seul morceau vide", nh._decouper("") == [""])
    long_texte = "x" * 5000
    morceaux = nh._decouper(long_texte)
    verifier("texte long découpé sous la limite Notion (2000)",
              all(len(m) <= nh._LIMITE_BLOC for m in morceaux))
    verifier("découpage reconstitue le texte d'origine", "".join(morceaux) == long_texte)

    blocs = nh._blocs_paragraphe("ligne 1\n\nligne 3")
    verifier("3 lignes (dont 1 vide) -> 3 blocs paragraph", len(blocs) == 3)
    verifier("chaque bloc a la forme attendue par l'API Notion",
              all(b["type"] == "paragraph" and "rich_text" in b["paragraph"] for b in blocs))
    verifier("ligne vide -> bloc avec contenu vide, pas supprimé",
              blocs[1]["paragraph"]["rich_text"][0]["text"]["content"] == "")

    # ── Pagination : has_more/next_cursor suivi jusqu'au bout ──────────
    _pages_simulees = {
        None: {"results": [{"id": "a"}, {"id": "b"}], "has_more": True, "next_cursor": "curseur1"},
        "curseur1": {"results": [{"id": "c"}], "has_more": False, "next_cursor": None},
    }

    def _fausse_requete(methode, chemin, corps=None):
        if "start_cursor=" in chemin:
            curseur = chemin.split("start_cursor=")[1]
        else:
            curseur = None
        return True, _pages_simulees[curseur]

    _vraie_requete = nh._requete
    nh._requete = _fausse_requete
    try:
        ok_pag, tous = nh._tous_les_blocs("page-test")
        verifier("_tous_les_blocs suit has_more sur plusieurs pages",
                  ok_pag and [b["id"] for b in tous] == ["a", "b", "c"])
    finally:
        nh._requete = _vraie_requete

    # ── Lots de 100 blocs max par appel PATCH ───────────────────────────
    appels_captures = []

    def _requete_qui_compte(methode, chemin, corps=None):
        appels_captures.append(len(corps["children"]))
        return True, {}

    nh._requete = _requete_qui_compte
    try:
        gros_lot = [{"n": i} for i in range(250)]
        ok_lot, _ = nh._ajouter_blocs_par_lots("page-test", gros_lot)
        verifier("250 blocs -> 3 appels PATCH (100, 100, 50)",
                  ok_lot and appels_captures == [100, 100, 50])
    finally:
        nh._requete = _vraie_requete

    # ── Pas configuré : échoue proprement, jamais d'appel réseau ───────
    ok, raison = nh.creer_ou_modifier_note("essai", "contenu")
    verifier("sans NOTION_API_KEY -> échec propre, pas d'exception",
              not ok and "NOTION_API_KEY" in raison)

    os.environ["NOTION_API_KEY"] = "faux_token_de_test"
    ok2, raison2 = nh.creer_ou_modifier_note("essai", "contenu")
    verifier("clé posée mais pas de page parente -> échec propre",
              not ok2 and "NOTION_PARENT_PAGE_ID" in raison2)

    os.environ["NOTION_PARENT_PAGE_ID"] = "id-de-test"

    # ── Index local : lecture d'une note absente ───────────────────────
    nh._ecrire_index({})
    ok3, raison3 = nh.lire_note("note_qui_n_existe_pas")
    verifier("lire une note absente de l'index -> message clair, pas d'appel réseau",
              not ok3 and "n'existe pas" in raison3)

    ok4, raison4 = nh.supprimer_note("note_qui_n_existe_pas")
    verifier("supprimer une note absente de l'index -> message clair",
              not ok4 and "n'existe pas" in raison4)

    verifier("lister_notes sur un index vide -> liste vide", nh.lister_notes() == [])

    # ── Index local : round-trip lecture/écriture/recherche ────────────
    nh._ecrire_index({"projet alpha": "id-1", "courses": "id-2"})
    verifier("lister_notes reflète l'index, trié par titre",
              [n["titre"] for n in nh.lister_notes()] == ["courses", "projet alpha"])
    verifier("rechercher_notes filtre sur le titre, insensible à la casse",
              [n["titre"] for n in nh.rechercher_notes("ALPHA")] == ["projet alpha"])
    verifier("rechercher_notes sans correspondance -> liste vide",
              nh.rechercher_notes("inexistant") == [])

    # ── Requête réseau injoignable : échec propre, jamais d'exception ──
    _base_reelle = nh._BASE
    nh._BASE = "http://127.0.0.1:1"
    try:
        ok5, res5 = nh._requete("GET", "/blocks/x/children")
        verifier("hôte injoignable -> (False, raison), jamais de levée", not ok5 and bool(res5))
    finally:
        nh._BASE = _base_reelle
finally:
    if _sauv_cle is not None:
        os.environ["NOTION_API_KEY"] = _sauv_cle
    else:
        os.environ.pop("NOTION_API_KEY", None)
    if _sauv_parent is not None:
        os.environ["NOTION_PARENT_PAGE_ID"] = _sauv_parent
    else:
        os.environ.pop("NOTION_PARENT_PAGE_ID", None)
    if _sauv_index is not None:
        io.open(_chemin_index, "w", encoding="utf-8").write(_sauv_index)
    elif os.path.exists(_chemin_index):
        os.remove(_chemin_index)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Notion (logique locale + chemins d'erreur) : conforme. "
      "Aller-retour reel jamais teste, voir la docstring du module.")
