# -*- coding: utf-8 -*-
r"""
Vérifie « où en est Paperclip » sans toucher au réseau : la lecture de l'API
est remplacée, comme veille_sujets injecte son récupérateur.

CE QU'IL GARDE VRAIMENT
1. Une simple mention de Paperclip ne déclenche rien : seule une QUESTION sur
   son avancement le fait (« paper clip » compris, la reconnaissance vocale
   l'écrit ainsi).
2. La phrase est faite pour être DITE : pas de « [P1] », pas d'identifiant,
   accords justes au singulier comme au pluriel.
3. Paperclip éteint donne une phrase claire, jamais une exception.

    venv\Scripts\python.exe _test_paperclip_suivi.py
"""

import sys
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paperclip_suivi as p

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


REPONSES = {
    "/companies": [{"id": "c1", "name": "Alex"}],
    "/companies/c1/agents": [{"id": "a1", "name": "Dev MiMo", "status": "running"},
                             {"id": "a2", "name": "Chef JARVIS", "status": "idle"}],
    "/companies/c1/issues": [
        {"title": "[P1] Memory leak in BACKGROUND_TASKS set", "status": "in_progress", "assigneeAgentId": "a1"},
        {"title": "[P0] Race conditions on global CONNECTED_CLIENTS set", "status": "todo", "assigneeAgentId": "a1"},
        {"title": "Tests sans identité git", "status": "in_review", "assigneeAgentId": "a1"},
        {"title": "Inventaire", "status": "done", "assigneeAgentId": None},
        {"title": "Mémoire persistante", "status": "done", "assigneeAgentId": "a1"},
    ],
}

_vrai_lire = p._lire
try:
    print("Reconnaissance de la demande")
    verifier("« où en est Paperclip ? »", p.reconnait_demande("Jarvis, où en est Paperclip ?"))
    verifier("« paper clip » de la reconnaissance vocale", p.reconnait_demande("ça avance paper clip"))
    verifier("« qu'est-ce que fait Paperclip »", p.reconnait_demande("qu'est-ce que Paperclip fait quoi en ce moment"))
    verifier("une simple mention ne déclenche rien", not p.reconnait_demande("ouvre Paperclip"))
    verifier("une phrase sans Paperclip ne déclenche rien", not p.reconnait_demande("où en est la météo"))
    verifier("un texte vide ne déclenche rien", not p.reconnait_demande(""))

    print("Phrase à dire")
    p._lire = lambda chemin: REPONSES[chemin]
    e = p.etat()
    phrase = p.phrase(e, "Alex")
    print("      « %s »" % phrase)
    verifier("la tâche en cours est nommée sans son préfixe [P1]",
             "Une tâche en cours : Memory leak in BACKGROUND_TASKS set, par Dev MiMo." in phrase)
    verifier("aucun préfixe entre crochets n'est lu", "[" not in phrase)
    verifier("les comptes forment leur propre phrase", "Une tâche en attente, une tâche attend votre relecture" in phrase)
    verifier("singulier : « une tâche attend votre relecture »", "une tâche attend votre relecture" in phrase)
    verifier("pluriel accordé : « deux tâches terminées »", "deux tâches terminées" in phrase)
    verifier("l'agent qui travaille est nommé", phrase.endswith("Dev MiMo travaille en ce moment."))
    verifier("un titre long est coupé à 60 caractères", len(p._titre("x" * 200)) == 60)

    print("Paperclip éteint")

    def eteint(chemin):
        raise urllib.error.URLError("connexion refusée")

    p._lire = eteint
    verifier("etat() renvoie None au lieu de lever", p.etat() is None)
    verifier("la phrase le dit clairement", p.phrase(None, "Alex") == "Paperclip ne répond pas, Alex : il est éteint.")
    verifier("rien en cours ni d'agent actif : phrase complète",
             p.phrase({"taches": [], "agents": []}, "Alex")
             == "Paperclip, Alex. Aucune tâche en cours. Aucune tâche terminée. Aucun agent ne travaille en ce moment.")
finally:
    p._lire = _vrai_lire

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Suivi de Paperclip : conforme.")
