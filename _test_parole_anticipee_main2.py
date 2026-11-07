"""La parole anticipée branchée dans main2 (faux OmniRoute, aucune voix, aucun réseau) :
demander_omniroute lit en flux, confie la 1re phrase à la voix, saute la route dédiée en panne,
et la mémoire ne retient la réponse qu'une fois.

    venv\\Scripts\\python.exe _test_parole_anticipee_main2.py
"""
import asyncio
from types import SimpleNamespace

import main2
import parole_anticipee


def morceau(texte):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=texte))])


class FauxOmniroute:
    def __init__(self, morceaux, panne_route=False):
        self.appels, self.morceaux, self.panne_route = [], morceaux, panne_route
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.appels.append((kw["model"], kw.get("stream", False)))
        if self.panne_route and kw["model"] == main2.OMNIROUTE_MODEL:
            raise RuntimeError("502 Bad Gateway")
        if kw.get("stream"):
            return iter([morceau(t) for t in self.morceaux])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="".join(self.morceaux)))])


async def scenario():
    dits = []

    async def faux_parler(texte, memoire=True):
        dits.append((texte, memoire))
        return False

    sauve = (main2.omniroute_client, main2._sauvegarder_echange_conv, list(main2.historique),
             main2._ROUTE_OMNI_EN_PANNE_JUSQUA, main2.OMNIROUTE_MODEL)
    main2._sauvegarder_echange_conv = lambda *a, **k: None  # rien dans la vraie mémoire de JARVIS
    main2.OMNIROUTE_MODEL = "route-dediee-de-test"
    main2._ROUTE_OMNI_EN_PANNE_JUSQUA = 0.0
    try:
        # 1. En flux, route dédiée en panne : secours, 1re phrase dite dès qu'elle est écrite.
        faux = FauxOmniroute(["Salut Alex ! ", "Il fait ", "beau."], panne_route=True)
        main2.omniroute_client = faux
        a = parole_anticipee.Anticipation(faux_parler)
        jeton = main2.PAROLE_ANTICIPEE.set(a)
        try:
            rep = await main2.demander_omniroute("Quel temps ?")
        finally:
            main2.PAROLE_ANTICIPEE.reset(jeton)
        assert rep == "Salut Alex ! Il fait beau.", rep
        assert dits == [("Salut Alex !", False)], dits
        assert await a.reste(rep) == "Il fait beau."
        assert faux.appels == [("route-dediee-de-test", True), (main2.OMNIROUTE_FALLBACK, True)], faux.appels

        # 2. Ensuite la route en panne est sautée (10 min) ; hors voix, appel classique.
        faux.appels.clear()
        assert await main2.demander_omniroute("Et demain ?") == "Salut Alex ! Il fait beau."
        assert faux.appels == [(main2.OMNIROUTE_FALLBACK, False)], faux.appels

        # 3. Mémoire : la réponse n'entre qu'une fois.
        n = len(main2.historique)
        main2._retenir_parole("Salut Alex ! Il fait beau.")  # déjà la dernière réplique
        assert len(main2.historique) == n
        main2._retenir_parole("Autre chose.")
        assert len(main2.historique) == n + 1
    finally:
        (main2.omniroute_client, main2._sauvegarder_echange_conv, hist,
         main2._ROUTE_OMNI_EN_PANNE_JUSQUA, main2.OMNIROUTE_MODEL) = sauve
        main2.historique[:] = hist


async def scenario_gemini():
    """Le chemin Gemini de demander_ia (cerveau préféré ou secours) en flux, avec un faux client."""
    import cout_suivi

    dits, appels = [], []

    async def faux_parler(texte, memoire=True):
        dits.append(texte)
        return False

    def flux(**kw):
        appels.append(("flux", kw["model"]))
        usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=5)
        return iter([SimpleNamespace(text=t, usage_metadata=usage) for t in ("Les étoiles ", "brillent ! ", "Voilà.")])

    sauve = (main2.client, main2.gemini_actif, main2._charger_config, main2._sauvegarder_echange_conv,
             list(main2.historique), cout_suivi.enregistrer)
    main2.client = SimpleNamespace(models=SimpleNamespace(
        generate_content_stream=flux, generate_content=lambda **kw: appels.append(("entier", kw["model"]))))
    main2.gemini_actif = True
    main2._charger_config = lambda: {"preferred_brain": "gemini"}
    main2._sauvegarder_echange_conv = lambda *a, **k: None
    cout_suivi.enregistrer = lambda *a, **k: None  # rien dans le vrai suivi des coûts
    try:
        a = parole_anticipee.Anticipation(faux_parler)
        jeton = main2.PAROLE_ANTICIPEE.set(a)
        try:
            rep = await main2.demander_ia("Parle-moi des étoiles en deux phrases.")
        finally:
            main2.PAROLE_ANTICIPEE.reset(jeton)
        assert rep == "Les étoiles brillent ! Voilà.", rep
        assert dits == ["Les étoiles brillent !"], dits
        assert [quoi for quoi, _ in appels] == ["flux"], appels  # jamais l'appel entier en voix
    finally:
        (main2.client, main2.gemini_actif, main2._charger_config, main2._sauvegarder_echange_conv,
         hist, cout_suivi.enregistrer) = sauve
        main2.historique[:] = hist


async def scenario_traiter():
    """traiter_reponse_ia en entier : le début part tôt, la suite après, une action JSON s'exécute en plus,
    et si on lui coupe la parole pendant le début, la suite n'est pas dite."""
    import confiance

    dits, appels = [], []
    coupe = {"oui": False}

    async def faux_parler(texte, memoire=True, apres=None):
        if apres is not None and await apres:
            return True
        debut = memoire is False and apres is None  # la 1re phrase anticipée
        dits.append((texte, memoire))
        await asyncio.sleep(0)
        return coupe["oui"] and debut  # « coupé » pendant la 1re phrase

    async def faux_demander_ia(texte):
        appels.append(texte)
        a = main2.PAROLE_ANTICIPEE.get()
        assert a is not None, "voix sur le PC : l'anticipation doit être posée"
        a.morceau("La mer est salée, depuis toujours ou presque, à cause des roches. ")
        await asyncio.sleep(0)
        return ('La mer est salée, depuis toujours ou presque, à cause des roches. Les rivières y portent des sels. '
                '{"action": "mode_iron_man", "etat": "off"}')

    sauve = (main2.parler, main2.demander_ia, confiance.enregistrer, list(main2.historique),
             getattr(main2, "_BRIEFING_FAIT", None))
    main2.parler, main2.demander_ia = faux_parler, faux_demander_ia
    confiance.enregistrer = lambda *a, **k: None
    if hasattr(main2, "_BRIEFING_FAIT"):
        main2._BRIEFING_FAIT = True
    # Une conversation commencée : _retenir_parole n'écrit rien dans un historique vide (Gemini veut que
    # l'utilisateur parle en premier). Sans cette ligne, le test dépendait de l'historique gardé sur la machine.
    main2.historique[:] = [main2.types.Content(role="user", parts=[main2.types.Part(text="bonjour")])]
    try:
        await main2.traiter_reponse_ia("parle-moi de la mer en deux phrases", canal="voix")
        assert appels, "la phrase devait aller au modèle"
        assert dits[0] == ("La mer est salée, depuis toujours ou presque, à cause des roches.", False), dits
        assert ("Les rivières y portent des sels.", False) in dits, dits
        assert any("Iron Man" in t for t, _ in dits), dits  # l'action du modèle s'exécute toujours
        assert len(dits) == 3, dits  # rien de dit deux fois
        assert main2.historique[-1].parts[0].text.endswith("Les rivières y portent des sels."), \
            main2.historique[-1].parts[0].text  # la réponse entière, une fois, dans la mémoire

        dits.clear()
        coupe["oui"] = True
        await main2.traiter_reponse_ia("parle-moi de la mer en deux phrases", canal="voix")
        assert ("Les rivières y portent des sels.", False) not in dits, dits  # coupé : pas de suite
    finally:
        (main2.parler, main2.demander_ia, confiance.enregistrer, hist, briefing) = sauve
        main2.historique[:] = hist
        if briefing is not None:
            main2._BRIEFING_FAIT = briefing


if __name__ == "__main__":
    asyncio.run(scenario())
    asyncio.run(scenario_gemini())
    asyncio.run(scenario_traiter())
    print("OK : parole anticipée dans main2")
