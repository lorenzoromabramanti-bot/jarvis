# -*- coding: utf-8 -*-
"""
Verifie les messages WebSocket de la delegation de code (delegation_projets,
delegation_code) avec un FAUX client : aucun vrai outil, aucun envoi reseau.

Le protocole en deux temps : sans "confirme": true le serveur ne fait que dire
ce qu'il LANCERAIT ; seul un `confirme` strictement True lance. Et le garde
central de ws_handler (catalogue.action_autorisee sur le type du message) doit
refuser tout le bloc quand la capacite est desactivee.

    venv\\Scripts\\python.exe _test_delegation_ws.py
"""

import asyncio
import io
import json
import os
import subprocess
import sys
import tempfile
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


import main2
import catalogue
import confiance
import delegation_code as dc
import notifications
import notifications_slack

_chemin_reg = dc._chemin_registre()
_sauv_reg = io.open(_chemin_reg, encoding="utf-8").read() if os.path.exists(_chemin_reg) else None
_vrais = {
    "auth": main2._authentifier_ws, "parler": main2.parler,
    "action": catalogue.action_autorisee, "executer": dc.executer_delegation,
    "resume": dc.resume_changements, "conf": confiance.enregistrer,
    "n_disc": notifications.envoyer_tache_terminee,
    "n_slack": notifications_slack.envoyer_tache_terminee,
    "briefing": main2._BRIEFING_FAIT,
    "natif": main2._agent_natif_disponible,
}
natif = {"v": False}
executions, decisions = [], []
porte = {"ouverte": True}


class FauxWS:
    """Un client : messages entrants via une file, sortants captures."""

    def __init__(self):
        self.entrant = asyncio.Queue()
        self.sortant = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        m = await self.entrant.get()
        if m is None:
            raise StopAsyncIteration
        return m

    async def send(self, texte):
        self.sortant.append(json.loads(texte))

    async def envoyer(self, **msg):
        await self.entrant.put(json.dumps(msg))

    async def recevoir(self, type_, delai=5.0, depuis=0):
        fin = time.time() + delai
        while time.time() < fin:
            for m in self.sortant[depuis:]:
                if m.get("type") == type_:
                    return m
            await asyncio.sleep(0.03)
        return None


async def _auth(ws):
    return True


async def _parler(texte):
    pass


def _executer(chemin, tache, modele=None, journal=None):
    executions.append((chemin, tache))
    return {"outil": "claude", "succes": True, "diff": "diff --git a/x", "sortie": "ok",
            "erreur": None, "baseline": "depot existant"}


def _action(a):
    if a in ("delegation_code", "delegation_projets"):
        return porte["ouverte"]
    return _vrais["action"](a)


async def scenario(projet):
    ws = FauxWS()
    tache_ws = asyncio.ensure_future(main2.ws_handler(ws))
    await asyncio.sleep(0.2)

    # ── Lister les projets ───────────────────────────────────────────────
    await ws.envoyer(type="delegation_projets")
    r = await ws.recevoir("delegation_projets")
    verifier("delegation_projets renvoie le registre", r and r["projets"] == {"demo": projet}, r)

    # ── Apercu : rien ne part sans confirme ──────────────────────────────
    n = len(ws.sortant)
    await ws.envoyer(type="delegation_code", projet="demo", tache="ajoute une page")
    r = await ws.recevoir("delegation_apercu", depuis=n)
    verifier("sans confirme : apercu, confirmation requise, outil nomme, RIEN lance",
              r and r["ok"] and r["confirmation_requise"] and r["outil"] and not executions, r)

    natif["v"] = True
    n = len(ws.sortant)
    await ws.envoyer(type="delegation_code", projet="demo", tache="ajoute une page")
    r = await ws.recevoir("delegation_apercu", depuis=n)
    verifier("agent integre disponible : l'apercu nomme « mon agent intégré » comme premier outil",
              r and r["ok"] and r["outil"] == "mon agent intégré", r)
    natif["v"] = False

    for faux in ("true", 1, "oui", None, False):
        n = len(ws.sortant)
        await ws.envoyer(type="delegation_code", projet="demo", tache="ajoute une page", confirme=faux)
        r = await ws.recevoir("delegation_apercu", depuis=n)
        verifier("confirme=%r n'est PAS un vrai True : toujours un simple apercu" % (faux,),
                  r and r.get("confirmation_requise") and not executions, r)

    # ── Projet inconnu / tache vide ──────────────────────────────────────
    n = len(ws.sortant)
    await ws.envoyer(type="delegation_code", projet="fantome", tache="x", confirme=True)
    r = await ws.recevoir("delegation_apercu", depuis=n)
    verifier("projet inconnu : refuse meme avec confirme", r and not r["ok"] and not executions, r)
    n = len(ws.sortant)
    await ws.envoyer(type="delegation_code", projet="demo", tache="   ", confirme=True)
    r = await ws.recevoir("delegation_apercu", depuis=n)
    verifier("tache vide : refuse meme avec confirme", r and not r["ok"] and not executions, r)

    # ── Confirme : lancement, puis resultat diffuse au HUD ───────────────
    decisions.clear()
    n = len(ws.sortant)
    await ws.envoyer(type="delegation_code", projet="demo", tache="ajoute une page", confirme=True)
    r = await ws.recevoir("delegation_apercu", depuis=n)
    verifier("confirme=True : lance", r and r["ok"] and r["lance"], r)
    res = await ws.recevoir("delegation_resultat", depuis=n)
    verifier("le HUD recoit le resultat (outil, succes, fichiers, diff, phrase)",
              res and res["outil"] == "claude" and res["succes"] and res["changements"]
              and res["diff"] and "testé" in res["phrase"], res)
    verifier("l'outil est appele une fois avec la tache exacte du message",
              executions == [(projet, "ajoute une page")], executions)
    verifier("l'approbation HUD est journalisee dans confiance",
              decisions and decisions[-1][:2] == ("delegation_code", True), decisions)
    await asyncio.sleep(0.2)
    verifier("verrou libere apres la fin", main2._DELEGATION_EN_COURS is None)

    # ── Dossier sale : bloquant, meme confirme ───────────────────────────
    io.open(os.path.join(projet, "a.txt"), "a").write("sale\n")
    executions.clear()
    n = len(ws.sortant)
    await ws.envoyer(type="delegation_code", projet="demo", tache="ajoute une page", confirme=True)
    r = await ws.recevoir("delegation_apercu", depuis=n)
    verifier("modifications non commitees : refuse meme avec confirme",
              r and not r["ok"] and "non commitées" in r["erreur"] and not executions, r)

    # ── Garde central : capacite desactivee -> tout le bloc est refuse ───
    porte["ouverte"] = False
    n = len(ws.sortant)
    await ws.envoyer(type="delegation_code", projet="demo", tache="x", confirme=True)
    r = await ws.recevoir("capacite_desactivee", depuis=n)
    verifier("capacite desactivee : le garde central de ws_handler refuse (delegation_code)",
              r and r["demande"] == "delegation_code" and not executions, r)
    n = len(ws.sortant)
    await ws.envoyer(type="delegation_projets")
    r = await ws.recevoir("capacite_desactivee", depuis=n)
    verifier("... et delegation_projets aussi", r and r["demande"] == "delegation_projets", r)
    porte["ouverte"] = True

    await ws.entrant.put(None)
    await asyncio.wait_for(tache_ws, 5)


projet = tempfile.mkdtemp(prefix="jarvis_test_ws_")
try:
    _git = ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", projet]
    subprocess.run(["git", "init", "-q", projet], capture_output=True)
    io.open(os.path.join(projet, "a.txt"), "w").write("un\n")
    subprocess.run(_git + ["add", "-A"], capture_output=True)
    subprocess.run(_git + ["commit", "-q", "-m", "base"], capture_output=True)
    dc._ecrire_registre({"demo": projet})

    main2._authentifier_ws = _auth
    main2.parler = _parler
    main2._BRIEFING_FAIT = True          # ne PAS lancer le vrai briefing du matin
    main2._agent_natif_disponible = lambda: natif["v"]
    catalogue.action_autorisee = _action
    dc.executer_delegation = _executer
    dc.resume_changements = lambda c: [("M", "index.html"), ("??", "style.css")]
    confiance.enregistrer = lambda t, a, d="": decisions.append((t, a, d))
    notifications.envoyer_tache_terminee = lambda *a, **k: (False, "test")
    notifications_slack.envoyer_tache_terminee = lambda *a, **k: (False, "test")

    asyncio.run(scenario(projet))
finally:
    main2._authentifier_ws = _vrais["auth"]
    main2.parler = _vrais["parler"]
    main2._BRIEFING_FAIT = _vrais["briefing"]
    main2._agent_natif_disponible = _vrais["natif"]
    catalogue.action_autorisee = _vrais["action"]
    dc.executer_delegation = _vrais["executer"]
    dc.resume_changements = _vrais["resume"]
    confiance.enregistrer = _vrais["conf"]
    notifications.envoyer_tache_terminee = _vrais["n_disc"]
    notifications_slack.envoyer_tache_terminee = _vrais["n_slack"]
    main2._DELEGATION_EN_COURS = None
    main2.CONNECTED_CLIENTS.clear()
    if _sauv_reg is not None:
        io.open(_chemin_reg, "w", encoding="utf-8").write(_sauv_reg)
    elif os.path.exists(_chemin_reg):
        os.remove(_chemin_reg)
    import shutil
    shutil.rmtree(projet, ignore_errors=True)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Delegation de code (WebSocket) : conforme.")
