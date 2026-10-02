# -*- coding: utf-8 -*-
"""Vérifie orchestrateur.detecter_sous_taches — surtout le refus par défaut."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio

from orchestrateur import (
    detecter_sous_taches, executer_sous_taches, synthese,
    LIMITE_SANS_CONFIRMATION,
)

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


# ── Le garde-fou : phrases vagues ou courtes ne déclenchent RIEN ──────────
for phrase in [
    "salut",
    "ça va ?",
    "merci",
    "quelle heure il est",
    "explique-moi ce qu'est une variable",
    "raconte-moi ta journée",
    "et donc",
]:
    verifier("phrase courte/vague refusée : %r" % phrase,
              detecter_sous_taches(phrase) is None)

# ── Décomposition réelle, comptage annoncé sans les nommer ────────────────
r = detecter_sous_taches("compare les prix de ces 3 produits")
verifier("compte détecté = 3", r is not None and r["nombre"] == 3)
verifier("éléments non nommés restent vides", r is not None and r["elements"] == [])
verifier("pas de confirmation requise sous la limite", r is not None and not r["confirmation_requise"])

r = detecter_sous_taches("regarde ce qui s'est passé sur ces quatre sujets")
verifier("nombre en toutes lettres compris (quatre=4)", r is not None and r["nombre"] == 4)

# ── Liste littérale : les éléments sont extraits ───────────────────────────
r = detecter_sous_taches("compare le prix de la baguette, du lait et du beurre")
verifier("3 éléments extraits d'une liste littérale", r is not None and len(r["elements"]) == 3)

# ── Plafond et confirmation ────────────────────────────────────────────────
r = detecter_sous_taches("compare ces 12 villes pour un déménagement")
verifier("nombre réel conservé (12) même au-delà du plafond", r is not None and r["nombre"] == 12)
verifier("confirmation exigée au-delà de %d" % LIMITE_SANS_CONFIRMATION,
          r is not None and r["confirmation_requise"] is True)
verifier("plafonné à %d dans plafonne_a" % LIMITE_SANS_CONFIRMATION,
          r is not None and r["plafonne_a"] == LIMITE_SANS_CONFIRMATION)

r = detecter_sous_taches("compare ces 5 offres d'abonnement internet")
verifier("exactement à la limite : pas de confirmation requise",
          r is not None and r["nombre"] == 5 and not r["confirmation_requise"])

r = detecter_sous_taches("compare ces 6 offres d'abonnement internet")
verifier("un cran au-dessus de la limite : confirmation requise",
          r is not None and r["confirmation_requise"] is True)

# ── Une conjonction "et" isolée dans une phrase normale n'est pas une liste ─
r = detecter_sous_taches("compare le prix et dis-moi si c'est raisonnable")
verifier("'et' sans énumération réelle ne déclenche rien", r is None)

# ── Un seul élément ne justifie jamais l'orchestration ─────────────────────
r = detecter_sous_taches("compare le prix de ce produit avec la semaine dernière")
verifier("un seul élément comparé -> pas d'orchestration", r is None)


# ═══ executer_sous_taches / synthese — appel modèle simulé, sans réseau ═══

async def _tests_execution():
    async def _faux_modele(prompt):
        # Un stub déterministe : la "réponse" reprend l'élément questionné,
        # ce qui permet de vérifier que CHAQUE sous-tâche reçoit bien sa
        # propre question et que rien ne se mélange entre elles.
        return "réponse pour %s" % prompt.split("« ")[1].split(" »")[0]

    async def _faux_modele_echec_sur_lait(prompt):
        # Cibler l'élément désigné par « ... », pas une recherche de sous-chaîne
        # dans le prompt entier — texte_original (qui mentionne les 3 éléments)
        # est intégré dans CHAQUE question, donc "lait" y apparaît toujours.
        cible = prompt.split("« ")[1].split(" »")[0]
        if cible == "du lait":
            raise RuntimeError("panne simulée")
        return await _faux_modele(prompt)

    d = detecter_sous_taches("compare le prix de la baguette, du lait et du beurre")
    resultats = await executer_sous_taches(d, "compare le prix de la baguette, du lait et du beurre", _faux_modele)
    verifier("3 sous-tâches exécutées, une par élément", len(resultats) == 3)
    verifier("chaque sous-tâche a reçu SA question (pas de fuite entre elles)",
              all(r["element"] in r["reponse"] for r in resultats))
    verifier("aucune erreur quand le modèle répond toujours", all("erreur" not in r for r in resultats))

    resultats_echec = await executer_sous_taches(d, "compare le prix de la baguette, du lait et du beurre", _faux_modele_echec_sur_lait)
    en_echec = [r for r in resultats_echec if "erreur" in r]
    en_succes = [r for r in resultats_echec if "erreur" not in r]
    verifier("un échec sur 3 n'empêche PAS les 2 autres de répondre", len(en_succes) == 2)
    verifier("l'échec reste visible, pas silencieux", len(en_echec) == 1 and "lait" in en_echec[0]["element"])

    # Compte annoncé sans éléments nommés, aucune résolution fournie -> échec propre
    d_sans_noms = detecter_sous_taches("compare les prix de ces 3 produits")
    resultats_sans_noms = await executer_sous_taches(d_sans_noms, "compare les prix de ces 3 produits", _faux_modele)
    verifier("sans éléments nommés et sans résolveur -> échec propre, pas d'invention",
              len(resultats_sans_noms) == 1 and "erreur" in resultats_sans_noms[0])

    # Résolution par contexte fournie
    async def _faux_resolveur(texte, n):
        return ["produit A", "produit B", "produit C"][:n]

    resultats_resolus = await executer_sous_taches(
        d_sans_noms, "compare les prix de ces 3 produits", _faux_modele,
        resoudre_elements=_faux_resolveur)
    verifier("résolution par contexte -> 3 sous-tâches malgré l'absence de noms dans la phrase",
              len(resultats_resolus) == 3 and all("erreur" not in r for r in resultats_resolus))

    texte_synthese = synthese(resultats)
    verifier("la synthèse mentionne les 3 éléments",
              all(r["element"] in texte_synthese for r in resultats))
    texte_echec_seul = synthese(resultats_sans_noms)
    verifier("synthèse d'un échec global reste lisible (pas de traceback brut)",
              "erreur" not in texte_echec_seul.lower() or "Je n'ai pas pu" in texte_echec_seul)


asyncio.run(_tests_execution())

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Orchestrateur (détection A1) : conforme.")
