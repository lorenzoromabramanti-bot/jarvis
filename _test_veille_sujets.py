# -*- coding: utf-8 -*-
r"""
Vérifie la veille de sujets sans jamais toucher au réseau : le récupérateur
est injecté, comme raffinement.py injecte son horloge.

CE QU'IL GARDE VRAIMENT
1. Le PREMIER contrôle n'annonce rien. Sinon, ajouter un sujet réciterait
   dix articles de la semaine passée comme autant de nouvelles.
2. Un article déjà vu ne revient pas — même si son titre a changé, parce
   que la comparaison porte sur le lien.
3. Un contrôle qui ÉCHOUE ne compte pas comme fait : après une coupure
   réseau, on réessaie au tour suivant au lieu d'attendre un jour de plus.

    venv\Scripts\python.exe _test_veille_sujets.py
"""

import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import veille_sujets as v

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


def flux(*couples):
    items = "".join("<item><title>%s</title><link>%s</link></item>" % c for c in couples)
    return "<?xml version='1.0'?><rss><channel>%s</channel></rss>" % items


dossier = tempfile.mkdtemp(prefix="jarvis_veille_")
_vrai_chemin = v._chemin
v._chemin = lambda: os.path.join(dossier, "veille.json")

try:
    # ── Ajout / retrait ─────────────────────────────────────────────────
    ok, _ = v.ajouter("processeurs AMD")
    verifier("ajout accepté", ok)
    ok2, raison = v.ajouter("Processeurs AMD")
    verifier("doublon refusé, casse ignorée", not ok2 and "déjà" in raison)
    ok3, raison = v.ajouter("ab")
    verifier("sujet trop court refusé", not ok3 and "trois" in raison)
    ok4, raison = v.retirer("jamais surveillé")
    verifier("retrait d'un sujet absent refusé, avec la raison",
             not ok4 and "n'était pas" in raison)

    # ── Premier contrôle : on enregistre, on n'annonce pas ──────────────
    depart = 1_000_000.0
    nouveaux, raison = v.controler(
        "processeurs AMD",
        recuperateur=lambda url: flux(("Zen 6 annoncé", "https://a/1"),
                                      ("Prix en baisse", "https://a/2")),
        maintenant=depart)
    verifier("premier contrôle : rien annoncé", nouveaux == [] and raison == "")
    verifier("premier contrôle : les articles existants sont mémorisés",
             v.lister()[0]["vus"] == 2)

    # ── Deuxième contrôle : seul le nouveau lien remonte ────────────────
    nouveaux, raison = v.controler(
        "processeurs AMD",
        recuperateur=lambda url: flux(("Zen 6 annoncé", "https://a/1"),
                                      ("Zen 6 : tout savoir", "https://a/3")),
        maintenant=depart + v.INTERVALLE)
    verifier("un seul article nouveau remonte", len(nouveaux) == 1)
    verifier("c'est bien le lien inédit", nouveaux[0][1] == "https://a/3")
    verifier("un article déjà vu ne revient pas",
             all(l != "https://a/1" for _, l in nouveaux))

    # Le titre change, le lien non : ce n'est pas une nouveauté.
    nouveaux, _ = v.controler(
        "processeurs AMD",
        recuperateur=lambda url: flux(("Zen 6 : le dossier complet", "https://a/3")),
        maintenant=depart + 2 * v.INTERVALLE)
    verifier("un titre réécrit sur le même lien n'est pas une nouveauté",
             nouveaux == [])

    # ── Cadence ─────────────────────────────────────────────────────────
    verifier("contrôlé à l'instant -> pas à contrôler",
             v.a_controler(depart + 2 * v.INTERVALLE + 60) == [])
    verifier("24 h plus tard -> à contrôler",
             v.a_controler(depart + 3 * v.INTERVALLE + 60) == ["processeurs AMD"])

    # ── Échecs : ne comptent pas comme un contrôle fait ─────────────────
    avant = [s["dernier_controle"] for s in v._lire_tout()["sujets"]][0]

    def coupure(url):
        raise OSError("réseau injoignable")

    nouveaux, raison = v.controler("processeurs AMD", recuperateur=coupure)
    verifier("réseau coupé -> raison explicite, pas d'exception",
             nouveaux == [] and "injoignable" in raison)
    verifier("un contrôle échoué NE met PAS à jour la date de contrôle",
             v._lire_tout()["sujets"][0]["dernier_controle"] == avant)

    nouveaux, raison = v.controler("processeurs AMD", recuperateur=lambda url: "pas du xml")
    verifier("flux illisible -> raison, jamais « aucune actualité »",
             nouveaux == [] and "illisible" in raison)
    verifier("un flux illisible ne met pas à jour la date non plus",
             v._lire_tout()["sujets"][0]["dernier_controle"] == avant)

    nouveaux, raison = v.controler("sujet jamais ajouté", recuperateur=lambda url: flux())
    verifier("contrôler un sujet non surveillé est refusé",
             nouveaux == [] and "pas sous surveillance" in raison)

    # ── Plafond ─────────────────────────────────────────────────────────
    for i in range(v.LIMITE_SUJETS):
        v.ajouter("sujet numero %d" % i)
    ok5, raison = v.ajouter("un de trop")
    verifier("le nombre de sujets est plafonné, et le dit",
             not ok5 and "maximum" in raison)

    # ── Phrase dite ─────────────────────────────────────────────────────
    lot = [("Titre %d" % i, "https://x/%d" % i) for i in range(6)]
    dit = v.phrase("AMD", lot)
    verifier("la phrase cite %d titres au plus" % v.LIMITE_ANNONCE,
             dit.count(" ; ") == v.LIMITE_ANNONCE - 1)
    verifier("et compte le reste au lieu de le taire", "3 autres" in dit)
    verifier("rien de neuf -> aucune phrase", v.phrase("AMD", []) == "")

    verifier("l'URL du flux encode le sujet",
             "processeurs+AMD" in v.url_flux("processeurs AMD"))

    # ── Ce qui reste à dire ─────────────────────────────────────────────
    verifier("aucune annonce au départ", v.annonces_en_attente() == [])
    v.deposer_annonce("Sur « AMD » : Zen 6 annoncé.")
    verifier("une annonce déposée est retrouvée",
             v.annonces_en_attente() == ["Sur « AMD » : Zen 6 annoncé."])
    verifier("lire les annonces ne les consomme PAS (le briefing peut échouer)",
             len(v.annonces_en_attente()) == 1)
    verifier("déposer du vide ne dépose rien", not v.deposer_annonce("   "))
    v.vider_annonces()
    verifier("vidées une fois dites", v.annonces_en_attente() == [])
    verifier("vider les annonces ne perd pas les sujets surveillés",
             len(v.lister()) >= 1)

    # ── Compréhension de la demande parlée ──────────────────────────────
    verifier("« surveille les annonces AMD » -> ajouter AMD",
             v.analyser_demande("Jarvis, surveille les annonces AMD") == ("ajouter", "amd"))
    verifier("« fais une veille sur le Zen 6 » -> ajouter zen 6",
             v.analyser_demande("fais une veille sur le Zen 6") == ("ajouter", "zen 6"))
    verifier("« tiens-moi au courant de la Ligue 1 » -> ajouter ligue 1",
             v.analyser_demande("tiens-moi au courant de la Ligue 1") == ("ajouter", "ligue 1"))
    # Le piège : « arrête de surveiller » CONTIENT « surveille ».
    verifier("« arrête de surveiller AMD » -> retirer, pas ajouter",
             v.analyser_demande("arrête de surveiller AMD") == ("retirer", "amd"))
    verifier("« ne surveille plus la Ligue 1 » -> retirer ligue 1",
             v.analyser_demande("ne surveille plus la Ligue 1") == ("retirer", "ligue 1"))
    verifier("« qu'est-ce que tu surveilles ? » -> lister",
             v.analyser_demande("qu'est-ce que tu surveilles ?") == ("lister", ""))
    verifier("une phrase sans rapport ne déclenche rien",
             v.analyser_demande("quel temps fait-il demain ?") == (None, ""))
    verifier("« surveille » sans sujet ne crée pas une veille vide",
             v.analyser_demande("surveille") == (None, ""))
    verifier("la ponctuation finale ne fait pas partie du sujet",
             v.analyser_demande("surveille le sujet Tesla.") == ("ajouter", "tesla"))
finally:
    v._chemin = _vrai_chemin
    shutil.rmtree(dossier, ignore_errors=True)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Veille de sujets : conforme.")
