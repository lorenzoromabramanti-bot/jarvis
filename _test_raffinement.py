# -*- coding: utf-8 -*-
"""Vérifie raffinement.py — échéance et boucle de critique. Modèle simulé, aucun appel réel."""

import asyncio
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import raffinement as rf

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


def _a(h, m, s=0):
    """struct_time factice, aujourd'hui à h:m:s — pour des tests reproductibles."""
    n = time.localtime()
    return time.localtime(time.mktime((n.tm_year, n.tm_mon, n.tm_mday, h, m, s, 0, 0, -1)))


# ── temps_restant_secondes ──────────────────────────────────────────────
verifier("échéance dans 1h -> ~3600s",
          3595 <= rf.temps_restant_secondes("15:00", maintenant=_a(14, 0)) <= 3600)
verifier("échéance déjà passée aujourd'hui -> comprise comme demain (12h pile, 20h -> 8h)",
          rf.temps_restant_secondes("08:00", maintenant=_a(20, 0)) == 12 * 3600)
verifier("échéance dans 5 minutes -> ~300s",
          295 <= rf.temps_restant_secondes("14:05", maintenant=_a(14, 0)) <= 300)


# ── raffiner_jusqu_a — modèle simulé ────────────────────────────────────
async def _tests_raffinement():
    appels = []

    async def _modele_qui_ameliore_puis_se_satisfait(prompt):
        appels.append(prompt)
        if "Trouve UN défaut" in prompt:
            return "Manque un exemple concret" if len(appels) < 5 else rf.SIGNAL_SATISFACTION
        if "Produis une version améliorée" in prompt:
            return "réponse améliorée v%d" % len(appels)
        return "première réponse"

    echeance_lointaine = time.strftime("%H:%M", time.localtime(time.time() + 3600))
    r = await rf.raffiner_jusqu_a("explique les listes en Python",
                                  echeance_lointaine,
                                  _modele_qui_ameliore_puis_se_satisfait,
                                  max_iterations=10)
    verifier("s'arrête sur satisfaction, pas sur le plafond", r["arret"] == "satisfait")
    verifier("plusieurs itérations réellement faites", r["iterations"] > 1)
    verifier("réponse finale est la version améliorée, pas la première",
              "améliorée" in r["reponse"])

    # ── Plafond d'itérations : le modèle ne se satisfait jamais ─────────
    async def _modele_jamais_satisfait(prompt):
        if "Trouve UN défaut" in prompt:
            return "encore un défaut"
        if "Produis une version" in prompt:
            return "version améliorée"
        return "réponse initiale"

    r2 = await rf.raffiner_jusqu_a("tâche sans fin", echeance_lointaine,
                                   _modele_jamais_satisfait, max_iterations=3)
    verifier("plafond d'itérations respecté même si le modèle ne se satisfait jamais",
              r2["iterations"] == 3 and r2["arret"] == "plafond_iterations")

    # ── Échéance imminente (15s) : une seule passe, pas de boucle ────────
    r3 = await rf.raffiner_jusqu_a("tâche urgente", "14:00",
                                   _modele_jamais_satisfait, max_iterations=10,
                                   maintenant=_a(13, 59, 45))
    verifier("échéance imminente -> une seule passe, arrêt propre",
              r3["iterations"] == 1 and r3["arret"] == "echeance_proche")


asyncio.run(_tests_raffinement())

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Raffinement jusqu'à échéance (mission E) : conforme.")
