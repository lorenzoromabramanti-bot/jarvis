# -*- coding: utf-8 -*-
"""
LOR-9 : fuite de BACKGROUND_TASKS (main2.lancer_tache_arriere_plan).

Trois chemins verifies, sans reseau et sans lancer JARVIS :

  1. WEB_LOOP inactif + boucle qui reste vivante : add_done_callback retire
     la tache du set a la fin, qu'elle reussisse ou echoue -> pas de fuite.
  2. WEB_LOOP inactif + boucle ephemere fermee AVANT la fin des taches
     (motif exact de la boucle vocale, main2.py:11946-11962 : new_event_loop
     -> run_until_complete -> loop.close()) : le done_callback ne s'execute
     jamais et l'entree reste dans le set pour toujours. La purge en tete de
     lancer_tache_arriere_plan borne le set a la tache en cours.
  3. WEB_LOOP actif : la branche run_coroutine_threadsafe ne touche jamais
     au set (l'analyse initiale du ticket deplacait la fuite sur ce chemin).

Les messages « Task was destroyed but it is pending! » en fin de scenario 2
sont attendus : ils sont le symptome visible des taches orphelines.

    venv\\Scripts\\python.exe _test_taches_arriere_plan.py
"""

import asyncio
import os
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

echecs = []


def verifier(libelle, condition, detail=None):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        if detail is not None:
            print("      ->", detail)
        echecs.append(libelle)


import main2  # noqa: E402


async def _tache_echec():
    raise RuntimeError("echec simule")


def _recuperer_exceptions(taches):
    for tache in taches:
        if tache.done() and not tache.cancelled():
            tache.exception()  # evite le bruit « exception never retrieved »


# ── 1 : boucle vivante, WEB_LOOP inactif ─────────────────────────────────
async def scenario_boucle_vivante():
    main2.WEB_LOOP = None
    main2.BACKGROUND_TASKS.clear()
    taches = [main2.lancer_tache_arriere_plan(asyncio.sleep(0.01))
              for _ in range(10)]
    taches.append(main2.lancer_tache_arriere_plan(_tache_echec()))
    await asyncio.sleep(0.3)
    _recuperer_exceptions(taches)
    verifier("boucle vivante : le set se vide apres succes comme apres echec",
             len(main2.BACKGROUND_TASKS) == 0,
             "%d entrees restantes" % len(main2.BACKGROUND_TASKS))
    verifier("boucle vivante : les 11 taches ont bien ete creees",
             len(taches) == 11 and all(t is not None for t in taches))


# ── 2 : boucle ephemere fermee avec taches pendantes (motif voix) ────────
def scenario_boucle_fermee():
    main2.WEB_LOOP = None
    main2.BACKGROUND_TASKS.clear()
    for _ in range(5):  # 5 « commandes voix » consecutives
        boucle = asyncio.new_event_loop()
        asyncio.set_event_loop(boucle)

        async def commande():
            # tache longue : elle est encore en cours quand la boucle se ferme
            main2.lancer_tache_arriere_plan(asyncio.sleep(30))

        try:
            boucle.run_until_complete(commande())
        finally:
            boucle.close()
    taille = len(main2.BACKGROUND_TASKS)
    verifier("boucle fermee : le set reste borne apres 5 commandes (purge LOR-9)",
             taille <= 1, "%d entrees pour 5 commandes fermees" % taille)
    main2.BACKGROUND_TASKS.clear()


# ── 3 : WEB_LOOP actif, branche run_coroutine_threadsafe ─────────────────
def scenario_web_loop_actif():
    main2.BACKGROUND_TASKS.clear()
    boucle = asyncio.new_event_loop()

    def tourner():
        asyncio.set_event_loop(boucle)
        boucle.run_forever()

    fil = threading.Thread(target=tourner, daemon=True)
    fil.start()
    for _ in range(100):
        if boucle.is_running():
            break
        time.sleep(0.01)
    main2.WEB_LOOP = boucle
    try:
        futur = main2.lancer_tache_arriere_plan(asyncio.sleep(0.01))
        resultat_ok = futur is not None and futur.result(timeout=5) is None
        time.sleep(0.1)
        verifier("WEB_LOOP actif : la branche threadsafe rend une future valide",
                 resultat_ok, futur)
        verifier("WEB_LOOP actif : le set n'est jamais touche",
                 len(main2.BACKGROUND_TASKS) == 0,
                 len(main2.BACKGROUND_TASKS))
    finally:
        main2.WEB_LOOP = None
        boucle.call_soon_threadsafe(boucle.stop)
        fil.join(timeout=5)
        boucle.close()


try:
    asyncio.run(scenario_boucle_vivante())
    scenario_boucle_fermee()
    scenario_web_loop_actif()
finally:
    main2.WEB_LOOP = None

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    sys.stdout.flush()
    os._exit(1)
print("BACKGROUND_TASKS : pas de fuite (LOR-9).")
sys.stdout.flush()
os._exit(0)
