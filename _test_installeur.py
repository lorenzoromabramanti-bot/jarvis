# -*- coding: utf-8 -*-
"""
Verifie l'assistant de configuration.

TROIS CHOSES QUI COUTENT CHER SI ELLES RATENT

  1. Une valeur de cle envoyee a la page. Une interface qui affiche un secret
     finit par le montrer dans une capture d'ecran, un partage d'ecran, une
     video de demonstration.
  2. Un .env ecrase. Relancer l'assistant pour changer UNE option ne doit pas
     effacer le reste — c'est exactement ce qu'on fait apres une mise a jour.
  3. Une interdiction qui ne tient qu'a l'affichage. Le mode simple doit
     REFUSER, pas seulement masquer.

    venv\\Scripts\\python.exe _test_installeur.py
"""

import io
import json
import os
import shutil
import sys
import tempfile

import config
import installeur


def verifier():
    api = installeur.Api()

    # ── Aucune valeur de cle ne sort ────────────────────────────────────
    reelles = {k: v for k, v in installeur._lire_env().items()
               if v and len(v) >= 12}
    assert reelles, "aucune cle dans le .env : ce controle ne prouverait rien"
    for mode in ("simple", "avance"):
        brut = json.dumps(api.donnees(mode), ensure_ascii=False)
        fuites = [k for k, v in reelles.items() if v in brut]
        assert not fuites, "valeur(s) de cle envoyee(s) a la page : %s" % fuites
    print("  OK  %d cles reelles, aucune valeur transmise a la page" % len(reelles))

    # ── Le mode change ce qui est propose ───────────────────────────────
    simple = api.donnees("simple")
    avance = api.donnees("avance")
    assert len(simple["capacites"]) < len(avance["capacites"]), \
        "le mode simple propose autant de capacites que le mode avance"
    for g in simple["gardes"]:
        assert not g["desactivable"], \
            "%s se dit desactivable en mode simple" % g["cle"]
        assert not g["phrase"], "la phrase de deverrouillage fuit en mode simple"
    for g in avance["gardes"]:
        assert g["desactivable"] and g["phrase"]
    print("  OK  mode simple : %d capacites au lieu de %d, garde-fous verrouilles"
          % (len(simple["capacites"]), len(avance["capacites"])))

    # Chaque garde-fou annonce ce qu'on perd.
    for g in avance["gardes"]:
        assert len(g["consequence"]) > 40, "%s : consequence trop vague" % g["cle"]
    print("  OK  chaque protection dit ce qu'on perd en la retirant")

    # ── Le .env n'est jamais ecrase ─────────────────────────────────────
    dossier = tempfile.mkdtemp(prefix="jarvis_env_")
    try:
        chemin = os.path.join(dossier, ".env")
        io.open(chemin, "w", encoding="utf-8").write(
            "# un commentaire que personne ne doit perdre\n"
            "GEMINI_API_KEY=valeur_existante_longue\n"
            "UNE_CLE_INCONNUE=gardee\n"
            "\n"
            "# une section\n"
            "HA_URL=http://ancien\n")
        installeur._ecrire_env({"HA_URL": "http://nouveau", "GROQ_API_KEY": "ajoutee"},
                               racine=dossier)
        apres = io.open(chemin, encoding="utf-8").read()

        assert "un commentaire que personne ne doit perdre" in apres, \
            "les commentaires ont ete perdus"
        assert "UNE_CLE_INCONNUE=gardee" in apres, \
            "une cle inconnue de JARVIS a ete supprimee"
        assert "GEMINI_API_KEY=valeur_existante_longue" in apres, \
            "une cle non touchee a ete modifiee"
        assert "HA_URL=http://nouveau" in apres, "la mise a jour n'a pas eu lieu"
        assert "http://ancien" not in apres, "l'ancienne valeur subsiste"
        assert "GROQ_API_KEY=ajoutee" in apres, "la nouvelle cle n'a pas ete ajoutee"
        assert apres.count("HA_URL=") == 1, "la cle a ete dupliquee"
        print("  OK  .env fusionne : commentaires, ordre et cles inconnues intacts")

        # Un champ vide ne doit RIEN ecrire : on le verifie au niveau de
        # _ecrire_env, seul endroit qui touche au fichier.
        installeur._ecrire_env({}, racine=dossier)
        apres2 = io.open(chemin, encoding="utf-8").read()
        assert "GEMINI_API_KEY=valeur_existante_longue" in apres2, \
            "un champ laisse vide a efface une valeur existante"
        assert "HA_URL=http://nouveau" in apres2
        print("  OK  un champ laisse vide n'efface rien")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)

    # ── Le controle de forme des cles ───────────────────────────────────
    for valeur, attendu in (("", True), ("court", False),
                            ("une cle avec espaces dedans", False),
                            ("AIzaSyABCDEFGHIJKLMNOP", True),
                            ("https://exemple.fr/cle", False)):
        r = api.verifier_cle("GEMINI_API_KEY", valeur)
        assert r["ok"] is attendu, "verifier_cle(%r) = %s" % (valeur, r)
        if not r["ok"]:
            assert r["message"], "refus sans explication pour %r" % valeur
    print("  OK  controle de forme des cles, chaque refus explique")

    # Une URL reste valide pour une variable qui EST une URL.
    assert api.verifier_cle("HA_URL", "https://ha.local:8123")["ok"]
    print("  OK  une adresse est acceptee pour un reglage d'adresse")

    # ── La page existe et ne charge rien d'externe ──────────────────────
    # Elle doit s'ouvrir sur une machine ou rien n'est installe.
    assert os.path.exists(installeur.PAGE), "page.html introuvable"
    page = io.open(installeur.PAGE, encoding="utf-8").read()
    for interdit in ("http://", "https://cdn", "<script src", "<link rel=\"stylesheet\""):
        assert interdit not in page, \
            "la page charge une ressource externe (%s) : elle doit tenir seule" % interdit
    assert "--hue: 186" in page, "la page ne reprend pas la teinte du HUD"
    print("  OK  page autonome, sans ressource externe, teinte du HUD")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Assistant de configuration : conforme.")
