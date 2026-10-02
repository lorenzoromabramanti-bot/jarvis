# -*- coding: utf-8 -*-
"""
Verifie le flux VOCAL de la delegation de code, de bout en bout, sans jamais
lancer un vrai outil ni rien envoyer sur le reseau :

    « code-moi X dans le projet Y »  ->  question  ->  « oui »  ->  lancement
    en arriere-plan  ->  compte-rendu parle

Les faux : parler() (capture), demander_ia() (echoue si le message n'a PAS ete
intercepte par la delegation), executer_delegation() (aucun outil), les push
Discord/Slack (aucun envoi), confiance.enregistrer() (n'ecrit pas le vrai
journal).

    venv\\Scripts\\python.exe _test_delegation_voix.py
"""

import asyncio
import io
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

# ── Etat reel a restaurer ────────────────────────────────────────────────
_chemin_reg = dc._chemin_registre()
_sauv_reg = io.open(_chemin_reg, encoding="utf-8").read() if os.path.exists(_chemin_reg) else None
_vrais = {
    "parler": main2.parler, "demander_ia": main2.demander_ia,
    "action_autorisee": catalogue.action_autorisee,
    "executer": dc.executer_delegation, "resume": dc.resume_changements,
    "conf": confiance.enregistrer,
    "n_disc": notifications.envoyer_tache_terminee,
    "n_slack": notifications_slack.envoyer_tache_terminee,
    "natif": main2._agent_natif_disponible,
}

dits, appels_ia, executions, decisions, pushs, modeles = [], [], [], [], [], []
natif = {"v": False}
porte_ouverte = {"delegation_code": True}


async def _parler(texte):
    dits.append(texte)


async def _demander_ia(texte):
    appels_ia.append(texte)
    return "reponse du modele"


def _executer(chemin, tache, modele=None, journal=None):
    executions.append((chemin, tache))
    modeles.append(modele)
    _executer.attente.wait(5)
    return {"outil": "claude", "succes": True, "diff": "diff --git", "sortie": "ok",
            "erreur": None, "baseline": "depot existant"}


_executer.attente = threading.Event()
_executer.attente.set()


def _action_autorisee(action):
    if action == "delegation_code":
        return porte_ouverte["delegation_code"]
    return _vrais["action_autorisee"](action)


async def dire(texte):
    dits.clear()
    appels_ia.clear()
    await main2.traiter_reponse_ia(texte, canal="voix")
    return " | ".join(dits)


async def attendre_fin(delai=5.0):
    fin = time.time() + delai
    while main2._DELEGATION_EN_COURS and time.time() < fin:
        await asyncio.sleep(0.05)
    return main2._DELEGATION_EN_COURS is None


async def scenario(projet_a, projet_b):
    # ── Porte fermee : rien ne change, la phrase va au modele ────────────
    porte_ouverte["delegation_code"] = False
    dit = await dire("code-moi une page d'accueil dans le projet demo")
    verifier("capacite desactivee : la phrase reste une conversation (va au modele)",
              appels_ia and main2.ATTENTE_CONFIRMATION_DELEGATION is None and not executions)
    porte_ouverte["delegation_code"] = True

    # ── Pas de projet nomme : conversation ordinaire ─────────────────────
    dit = await dire("développe ton idée un peu plus")
    verifier("« developpe ton idee » sans projet nomme ne declenche RIEN",
              appels_ia and main2.ATTENTE_CONFIRMATION_DELEGATION is None and "projet" not in dit)

    # ── Projet inconnu ───────────────────────────────────────────────────
    dit = await dire("code-moi un script dans le projet fantome")
    verifier("projet inconnu : le dit, liste les projets connus, rien en attente",
              "Je ne connais pas de projet" in dit and "demo" in dit
              and main2.ATTENTE_CONFIRMATION_DELEGATION is None and not appels_ia)

    # ── Declarer un projet par une phrase ────────────────────────────────
    dit = await dire("enregistre le projet autre : %s" % projet_b)
    verifier("« enregistre le projet ... » declare le projet", "déclaré" in dit
              and "autre" in dc.projets_connus())
    dit = await dire("enregistre le projet piege : %s" % os.path.dirname(os.path.abspath(main2.__file__)))
    verifier("declarer l'installation de JARVIS elle-meme est refuse", "interdite" in dit
              and "piege" not in dc.projets_connus(), (dit, list(dc.projets_connus())))

    # ── La demande : question, rien de lance ─────────────────────────────
    dit = await dire("code-moi une page d'accueil dans le projet demo")
    verifier("la demande pose UNE question avec « oui »/« non » et ne lance rien",
              "Dites « oui »" in dit and "Claude Code" in dit and "demo" in dit
              and main2.ATTENTE_CONFIRMATION_DELEGATION is not None
              and not executions and not appels_ia)
    verifier("la question dit que rien n'est enregistre dans git",
              "sans rien enregistrer dans git" in dit)

    # ── « non » : rien ne part, refus journalise ─────────────────────────
    decisions.clear()
    dit = await dire("non merci")
    verifier("« non » : rien lance, attente videe",
              "ne lance rien" in dit and main2.ATTENTE_CONFIRMATION_DELEGATION is None
              and not executions)
    verifier("le refus est journalise dans confiance",
              decisions and decisions[-1][0] == "delegation_code" and decisions[-1][1] is False)

    # ── Une reponse qui n'est ni oui ni non : abandon SANS avaler le message
    await dire("code-moi une page d'accueil dans le projet demo")
    # Une phrase que les outils locaux ne traitent pas (« quelle heure » est
    # repondu sans modele) : il faut qu'elle atteigne demander_ia.
    dit = await dire("explique-moi la photosynthèse en deux phrases")
    verifier("ni oui ni non : la demande est abandonnee et le message va au modele",
              main2.ATTENTE_CONFIRMATION_DELEGATION is None and not executions and appels_ia,
              (dit, appels_ia))

    # ── Demande perimee ──────────────────────────────────────────────────
    await dire("code-moi une page d'accueil dans le projet demo")
    main2.ATTENTE_CONFIRMATION_DELEGATION["ts"] -= main2.DELEGATION_VALIDITE_CONFIRMATION + 5
    await dire("oui")
    verifier("un « oui » apres expiration ne lance RIEN", not executions
              and main2.ATTENTE_CONFIRMATION_DELEGATION is None)

    # ── « look » / « cookie » ne valident pas (mots entiers) ─────────────
    await dire("code-moi une page d'accueil dans le projet demo")
    await dire("regarde le cookie")
    verifier("un mot qui CONTIENT « ok » n'est pas un « oui »", not executions)

    # ── « oui » : lancement en arriere-plan puis compte-rendu ───────────
    decisions.clear()
    pushs.clear()
    await dire("code-moi une page d'accueil dans le projet demo")
    dit = await dire("oui vas-y")
    verifier("« oui » : annonce le lancement, promet de prevenir", "C'est parti" in dit)
    verifier("l'approbation est journalisee", decisions and decisions[-1][1] is True)
    fini = await attendre_fin()
    verifier("la delegation se termine en arriere-plan", fini)
    verifier("l'outil est appele UNE fois, sur le bon dossier avec la phrase d'origine",
              len(executions) == 1 and executions[0][0] == projet_a
              and "page d'accueil" in executions[0][1])
    final = dits[-1] if dits else ""
    verifier("compte-rendu parle : outil, projet, et « personne n'a teste »",
              "Claude Code a terminé" in final and "demo" in final and "testé" in final)
    verifier("push Discord ET Slack du resultat (heures calmes gerees par le module)",
              len(pushs) == 2)

    # ── Un seul lancement a la fois ──────────────────────────────────────
    executions.clear()
    _executer.attente.clear()               # l'outil « tourne » encore
    await dire("code-moi une page d'accueil dans le projet demo")
    await dire("oui")
    await asyncio.sleep(0.2)
    verifier("pendant qu'une delegation tourne, la suivante est refusee",
              main2._DELEGATION_EN_COURS == "demo")
    dit = await dire("code-moi autre chose dans le projet demo")
    verifier("... et JARVIS le dit au lieu d'empiler",
              "tourne déjà" in dit and main2.ATTENTE_CONFIRMATION_DELEGATION is None)
    _executer.attente.set()
    await attendre_fin()
    verifier("apres la fin, le verrou est libere", main2._DELEGATION_EN_COURS is None)

    # ── Agent integre disponible : JARVIS s'en occupe LUI-MEME ───────────
    natif["v"] = True
    executions.clear(); modeles.clear()
    dit = await dire("code-moi une page d'accueil dans le projet demo")
    verifier("agent integre : la question dit que JARVIS s'en occupe et que le contenu part vers Gemini",
              "moi-même" in dit and "Gemini" in dit and "Dites « oui »" in dit and "Claude Code" not in dit
              and "sans rien enregistrer dans git" in dit, dit)
    await dire("oui")
    await attendre_fin()
    verifier("... et le MODELE de l'agent est bien passe a la chaine (appelable)",
              len(modeles) == 1 and callable(modeles[0]), modeles)
    natif["v"] = False
    executions.clear(); modeles.clear()
    await dire("code-moi une page d'accueil dans le projet demo")
    await dire("oui")
    await attendre_fin()
    verifier("sans agent integre : aucun modele n'est passe (la chaine externe prend le relais)",
              len(modeles) == 1 and modeles[0] is None, modeles)
    await dire("explique-moi le fichier a.txt dans le projet demo")
    verifier("un verbe de LECTURE avec projet nomme declenche aussi la question",
              main2.ATTENTE_CONFIRMATION_DELEGATION is not None)
    await dire("non")

    # ── Dossier avec modifications non commitees : BLOQUANT ──────────────
    io.open(os.path.join(projet_a, "a.txt"), "a").write("sale\n")
    dit = await dire("code-moi une page d'accueil dans le projet demo")
    verifier("modifications non commitees : refuse, dit pourquoi, ne demande meme pas oui",
              "non commitées" in dit and main2.ATTENTE_CONFIRMATION_DELEGATION is None)


projet_a = tempfile.mkdtemp(prefix="jarvis_test_voix_a_")
projet_b = tempfile.mkdtemp(prefix="jarvis_test_voix_b_")
try:
    _git = ["git", "-c", "user.name=t", "-c", "user.email=t@t.t", "-C", projet_a]
    subprocess.run(["git", "init", "-q", projet_a], capture_output=True)
    io.open(os.path.join(projet_a, "a.txt"), "w").write("un\n")
    subprocess.run(_git + ["add", "-A"], capture_output=True)
    subprocess.run(_git + ["commit", "-q", "-m", "base"], capture_output=True)

    dc._ecrire_registre({"demo": projet_a})

    main2.parler = _parler
    main2._agent_natif_disponible = lambda: natif["v"]
    main2.demander_ia = _demander_ia
    catalogue.action_autorisee = _action_autorisee
    dc.executer_delegation = _executer
    dc.resume_changements = lambda chemin: [("M", "index.html"), ("??", "style.css")]
    confiance.enregistrer = lambda type_action, approuve, detail="": decisions.append((type_action, approuve, detail))
    notifications.envoyer_tache_terminee = lambda msg, *a, **k: pushs.append(("discord", msg)) or (False, "test")
    notifications_slack.envoyer_tache_terminee = lambda msg, *a, **k: pushs.append(("slack", msg)) or (False, "test")

    asyncio.run(scenario(projet_a, projet_b))
finally:
    main2.parler = _vrais["parler"]
    main2._agent_natif_disponible = _vrais["natif"]
    main2.demander_ia = _vrais["demander_ia"]
    catalogue.action_autorisee = _vrais["action_autorisee"]
    dc.executer_delegation = _vrais["executer"]
    dc.resume_changements = _vrais["resume"]
    confiance.enregistrer = _vrais["conf"]
    notifications.envoyer_tache_terminee = _vrais["n_disc"]
    notifications_slack.envoyer_tache_terminee = _vrais["n_slack"]
    main2.ATTENTE_CONFIRMATION_DELEGATION = None
    main2._DELEGATION_EN_COURS = None
    if _sauv_reg is not None:
        io.open(_chemin_reg, "w", encoding="utf-8").write(_sauv_reg)
    elif os.path.exists(_chemin_reg):
        os.remove(_chemin_reg)
    import shutil
    shutil.rmtree(projet_a, ignore_errors=True)
    shutil.rmtree(projet_b, ignore_errors=True)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Delegation de code (flux vocal) : conforme.")
