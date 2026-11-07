# -*- coding: utf-8 -*-
"""
Fluidité de la conversation (23/10) : un cerveau en panne ne coûte plus ~4 s à chaque question, et son
appel ne fige plus la boucle (HUD, WebSocket) pendant l'attente.

    venv\\Scripts\\python.exe _test_fluidite.py
"""
import asyncio
import time


def verifier():
    import main2

    # 1. mark_failed existait dans les appels mais pas dans la classe : AttributeError avalée, jamais d'écart.
    q = main2.APIQuotaManager()
    assert q.is_available("omniroute")
    q.mark_failed("omniroute")
    assert not q.is_available("omniroute") and 590 <= q.remaining_cooldown("omniroute") <= 600

    # 2. Un 502 d'OmniRoute : None (on passe au cerveau suivant), OmniRoute écarté, et la boucle tourne pendant l'appel.
    class Panne(Exception):
        pass

    appels = []

    class FauxComplet:
        def create(self, **k):
            appels.append(k["model"])
            time.sleep(0.4)  # un vrai appel réseau, synchrone
            raise Panne("Error code: 502 - Combo target 1 failed")

    class FauxClient:
        class chat:
            completions = FauxComplet()

    vrai_client, vrai_mgr = main2.omniroute_client, main2._quota_mgr
    main2.omniroute_client, main2._quota_mgr = FauxClient(), main2.APIQuotaManager()
    try:
        tics = []

        async def horloge():
            while True:
                tics.append(time.perf_counter())
                await asyncio.sleep(0.05)

        async def scenario():
            t = asyncio.create_task(horloge())
            rep = await main2.demander_omniroute("Capitale de l'Espagne ?")
            t.cancel()
            return rep

        assert asyncio.run(scenario()) is None
        assert len(tics) >= 8, "la boucle était figée pendant l'appel à OmniRoute (%d tics)" % len(tics)
        assert appels and not main2._quota_mgr.is_available("omniroute"), "OmniRoute en panne doit être écarté"
    finally:
        main2.omniroute_client, main2._quota_mgr = vrai_client, vrai_mgr

    # 3. Suite de conversation : la fenêtre sans « Jarvis » est courte et tient dans la session.
    assert 0 < main2.SUITE_CONVERSATION < main2.SESSION_TIMEOUT
    print("  Fluidité : conforme.")


if __name__ == "__main__":
    verifier()
