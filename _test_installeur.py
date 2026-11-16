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
import re
import shutil
import sys
import tempfile

import config
import installeur


def verifier():
    api = installeur.Api()

    # ── Rien de public n'est un objet (pywebview le parcourrait sans fin) ─
    # pywebview liste TOUS les attributs publics de l'API, objets compris, en profondeur. La fenetre y est un
    # objet .NET dont chaque propriete en renvoie un neuf : le parcours ne finissait jamais et la page de
    # l'assistant restait sans API, a jamais (constate le 16/11/2026, pywebview 6.2.1). « _fenetre » est ignore.
    import inspect
    for nom in dir(api):
        if nom.startswith("_"):
            continue
        valeur = getattr(api, nom)
        assert callable(valeur) or isinstance(valeur, (str, int, float, bool, type(None))), \
            "Api.%s est un objet public : pywebview le parcourrait en profondeur" % nom
    assert "api.fenetre" not in inspect.getsource(installeur.lancer), "lancer() range la fenetre dans un attribut public"
    print("  OK  aucun attribut public de l'API n'est un objet (la fenetre est en « _fenetre »)")

    # ── Aucune valeur de cle ne sort ────────────────────────────────────
    # Sur une machine sans .env (clone neuf), des cles factices dans un .env
    # temporaire : sinon ce controle ne prouverait rien.
    reelles = {k: v for k, v in installeur._lire_env().items()
               if v and len(v) >= 12}
    if not reelles:
        installeur.RACINE = tempfile.mkdtemp(prefix="jarvis_env_")
        reelles = {"GEMINI_API_KEY": "cle_factice_gemini_0123456789",
                   "JARVIS_ACCESS_TOKEN": "jeton_factice_0123456789"}
        installeur._ecrire_env(reelles)
        os.environ.update(reelles)
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

    # ── Cerveaux : presence seulement, liste fermee, pas d'abonnement ───
    # Reseau simule : le test ne depend pas d'Internet et n'envoie aucune
    # cle nulle part. « bonne » = le fournisseur accepte, « horsligne » =
    # personne ne repond, le reste = refus (401).
    appels = []
    tests_fournisseurs = {c["test"] for c in installeur.CERVEAUX}

    def faux_http(url, entetes=None, delai=8):
        appels.append((url, " ".join((entetes or {}).values())))
        if url == installeur.OLLAMA:
            return 200, b'{"models": [{"name": "gemma4:26b"}]}'
        if url in tests_fournisseurs:
            cle = appels[-1][1]
            return (0 if "horsligne" in cle else 200 if "bonne" in cle else 401), b""
        return 0, b""

    variables = [c["variable"] for c in installeur.CERVEAUX]
    env_avant = {v: os.environ.pop(v) for v in variables if v in os.environ}
    vrai_http, installeur._http = installeur._http, faux_http
    racine_avant, installeur.RACINE = installeur.RACINE, tempfile.mkdtemp(prefix="jarvis_cerveaux_")
    try:
        c = api.cerveaux()
        assert not any(k["presente"] for k in c["cles"]), "cle annoncee presente dans un .env vide"
        assert c["ollama"] == {"actif": True, "modeles": ["gemma4:26b"]}, c["ollama"]
        assert "claude_cli" not in {k["id"] for k in c["cles"]}, "l'abonnement Claude est propose"

        # Un modele de fichier de reglages (« votre_cle ») n'est pas une cle.
        os.environ["GROQ_API_KEY"] = "votre_cle"
        try:
            assert not next(k for k in api.cerveaux()["cles"] if k["id"] == "groq")["presente"], \
                "une valeur de 9 caracteres compte comme une cle"
        finally:
            del os.environ["GROQ_API_KEY"]

        # Vingt ajouts en meme temps (la page appelle Python depuis plusieurs fils) : aucun ne se perd.
        import threading
        fils = [threading.Thread(target=installeur._ecrire_env, args=({"CLE_ESSAI_%d" % i: "valeur_%d" % i},))
                for i in range(20)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        ecrit = installeur._lire_env()
        perdus = [i for i in range(20) if ecrit.get("CLE_ESSAI_%d" % i) != "valeur_%d" % i]
        assert not perdus, "ajouts perdus par des ecritures simultanees : %s" % perdus

        for nom in ("PATH", "JARVIS_ACCESS_TOKEN", "HA_TOKEN"):
            assert not api.ajouter_cle(nom, "valeur_assez_longue_0123")["ok"], \
                "%s accepte comme cle de cerveau" % nom
        r = api.ajouter_cle("GROQ_API_KEY", "mauvaise_cle_0123456789")
        assert not r["ok"] and "GROQ_API_KEY" not in installeur._lire_env(), \
            "une cle refusee par le fournisseur a ete enregistree"
        r = api.ajouter_cle("GROQ_API_KEY", "bonne_cle_0123456789")
        assert r["ok"] and installeur._lire_env()["GROQ_API_KEY"] == "bonne_cle_0123456789"
        assert all("bonne_cle" not in url for url, _ in appels), "la cle est partie dans l'adresse"
        brut = json.dumps([r, api.cerveaux(), api.tester_cle("GROQ_API_KEY")], ensure_ascii=False)
        assert "bonne_cle" not in brut, "la valeur de la cle revient vers la page"
        assert '"presente": true' in brut, "la cle ajoutee n'est pas detectee"
        r = api.ajouter_cle("MISTRAL_API_KEY", "horsligne_cle_0123456789")
        assert r["ok"] and "sans" in r["message"], "hors ligne, la cle doit etre gardee : %s" % r
        print("  OK  cerveaux : presence seule, cle testee en en-tete, refus du fournisseur respecte")

        # preferred_brain : seul champ touche, abonnement refuse, fichier
        # illisible jamais ecrase (main2 y range aussi l'age, la musique...).
        cfg = installeur._fichier_config()
        io.open(cfg, "w", encoding="utf-8").write('{"user_age": 13, "musique_lien": "x"}')
        assert api.choisir_cerveau("groq")["ok"]
        assert json.load(io.open(cfg, encoding="utf-8")) == {
            "user_age": 13, "musique_lien": "x", "preferred_brain": "groq"}, "reglages perdus"
        assert not api.choisir_cerveau("claude_cli")["ok"], "abonnement Claude accepte"
        io.open(cfg, "w", encoding="utf-8").write('{"user_age": 13,')
        assert not api.choisir_cerveau("gemini")["ok"], "fichier illisible ecrase"
        assert io.open(cfg, encoding="utf-8").read() == '{"user_age": 13,'
        print("  OK  preferred_brain ecrit seul, claude_cli refuse, fichier illisible intact")
    finally:
        shutil.rmtree(installeur.RACINE, ignore_errors=True)
        installeur.RACINE = racine_avant
        installeur._http = vrai_http
        os.environ.update(env_avant)

    # ── La page existe et ne charge rien d'externe ──────────────────────
    # Elle doit s'ouvrir sur une machine ou rien n'est installe.
    assert os.path.exists(installeur.PAGE), "page.html introuvable"
    # Le style vit dans style.css, a cote : local, il ne demande pas Internet.
    style = os.path.join(os.path.dirname(installeur.PAGE), "style.css")
    assert os.path.exists(style), "style.css introuvable a cote de page.html"
    page = io.open(installeur.PAGE, encoding="utf-8").read()
    feuilles = re.findall(r'<link rel="stylesheet" href="([^"]+)"', page)
    assert feuilles == ["style.css"], "feuille de style inattendue : %s" % feuilles
    page += io.open(style, encoding="utf-8").read()
    for interdit in ("http://", "https://cdn", "<script src", "@import", "url(http"):
        assert interdit not in page, \
            "la page charge une ressource externe (%s) : elle doit tenir seule" % interdit
    # Le HUD est devenu l'Orbe de verre (1.5) : l'installeur reprend ses couleurs.
    assert "#7FB8F5" in page and "#1F6FC4" in page, \
        "la page ne reprend pas les couleurs de l'Orbe de verre"
    print("  OK  page autonome, sans ressource externe, couleurs de l'Orbe de verre")

    # ── Le jeton du WebSocket est genere, jamais renvoye ────────────────
    # Sans jeton, le WebSocket se limite a la machine : l'assistant doit le
    # creer pour que le telephone puisse se connecter.
    import catalogue
    racine_avant, installeur.RACINE = installeur.RACINE, tempfile.mkdtemp(prefix="jarvis_env_")
    # Fichier de choix temporaire, pas le vrai : voir _test_catalogue (08/10/2026).
    choix = os.path.join(tempfile.mkdtemp(prefix="jarvis_choix_"), "capacites.json")
    vrai_chemin, catalogue._chemin_choix = catalogue._chemin_choix, lambda: choix
    try:
        r = api.enregistrer("simple", [], {})
        jeton = installeur._lire_env().get("JARVIS_ACCESS_TOKEN", "")
        assert r["jeton_genere"] and len(jeton) >= 32, "jeton non genere dans un .env vide"
        assert jeton not in json.dumps(r), "le jeton genere est renvoye a la page"
        assert not api.enregistrer("simple", [], {})["jeton_genere"], "jeton regenere"
        assert installeur._lire_env()["JARVIS_ACCESS_TOKEN"] == jeton, "jeton existant ecrase"
    finally:
        shutil.rmtree(installeur.RACINE, ignore_errors=True)
        installeur.RACINE = racine_avant
        catalogue._chemin_choix = vrai_chemin
        shutil.rmtree(os.path.dirname(choix), ignore_errors=True)
    print("  OK  jeton d'acces genere dans un .env vide, jamais renvoye ni ecrase")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Assistant de configuration : conforme.")
