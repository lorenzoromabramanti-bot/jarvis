# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Réflexion jusqu'à une échéance (mission E)
===========================================================
« Fais cette tâche et termine-la à telle heure » — pas un simple aller-
retour comme demander_ia_isolee(), mais des passes de critique/amélioration
répétées, tant qu'il reste du temps avant l'échéance.

POURQUOI PAS UNE BOUCLE INFINIE
Une échéance lointaine ne doit pas devenir un gouffre à appels modèle.
MAX_ITERATIONS borne le coût même si l'échéance est dans 8 heures — et le
modèle peut s'arrêter lui-même plus tôt en signalant qu'il n'a plus rien
à améliorer (RIEN_A_AMELIORER). Les deux limites sont indépendantes,
la première qui tombe l'emporte.

CE QUE CE FICHIER NE FAIT PAS
Ne connaît aucun détail de fournisseur IA — `appel_modele` est injecté,
comme dans orchestrateur.py. Ne décide pas non plus SI une tâche mérite
ce traitement (mise en file, capacité, garde) — ça reste dans
taches_nocturnes.py et main2.py.
"""

import time

MAX_ITERATIONS = 5
MARGE_MINIMALE_SECONDES = 30  # sous ce seuil, pas de nouvelle passe : le
                              # temps restant ne suffit pas à un aller-retour
SIGNAL_SATISFACTION = "RIEN A AMELIORER"


def temps_restant_secondes(echeance, maintenant=None):
    """
    Secondes avant `echeance` ("HH:MM", heure locale).

    Si l'heure est déjà passée aujourd'hui, l'échéance est comprise comme
    demain — cohérent avec taches_nocturnes.heure (« pas avant »), qui
    suppose la même chose. Une échéance non postée reste testable : passer
    `maintenant` (struct_time) pour ne pas dépendre de l'horloge réelle.
    """
    maintenant = maintenant or time.localtime()
    h, m = (int(x) for x in echeance.split(":"))
    cible_aujourdhui = time.mktime((maintenant.tm_year, maintenant.tm_mon, maintenant.tm_mday,
                                    h, m, 0, 0, 0, -1))
    maintenant_ts = time.mktime(maintenant)
    if cible_aujourdhui <= maintenant_ts:
        cible_aujourdhui += 86400
    return int(cible_aujourdhui - maintenant_ts)


async def raffiner_jusqu_a(description, echeance, appel_modele, max_iterations=MAX_ITERATIONS,
                           maintenant=None):
    """
    Répond à `description`, puis se critique et s'améliore tant qu'il
    reste du temps avant `echeance` et que `max_iterations` n'est pas
    atteint. `appel_modele` : callable async (prompt:str) -> str.
    `maintenant` : struct_time injectable pour les tests, comme
    temps_restant_secondes() — None = l'heure réelle.

    Renvoie {"reponse": str, "iterations": int, "arret": str}
    où "arret" ∈ {"satisfait", "plafond_iterations", "echeance_proche", "erreur"}
    — toujours dit POURQUOI ça s'est arrêté, jamais un simple résultat nu.
    """
    reponse = await appel_modele(description)
    iterations = 1

    while iterations < max_iterations:
        if temps_restant_secondes(echeance, maintenant=maintenant) < MARGE_MINIMALE_SECONDES:
            return {"reponse": reponse, "iterations": iterations, "arret": "echeance_proche"}

        prompt_critique = (
            "Voici la tâche : %s\n\nVoici la réponse actuelle :\n%s\n\n"
            "Trouve UN défaut concret à améliorer (précision, complétude, clarté). "
            "Si tu n'en trouves vraiment aucun, réponds EXACTEMENT : %s"
            % (description, reponse, SIGNAL_SATISFACTION)
        )
        critique = (await appel_modele(prompt_critique)).strip()

        if critique.upper().startswith(SIGNAL_SATISFACTION):
            return {"reponse": reponse, "iterations": iterations, "arret": "satisfait"}

        if temps_restant_secondes(echeance, maintenant=maintenant) < MARGE_MINIMALE_SECONDES:
            return {"reponse": reponse, "iterations": iterations, "arret": "echeance_proche"}

        prompt_amelioration = (
            "Tâche d'origine : %s\n\nRéponse actuelle :\n%s\n\n"
            "Défaut relevé : %s\n\nProduis une version améliorée de la réponse "
            "qui corrige précisément ce défaut. Ne réponds qu'avec la réponse "
            "améliorée, rien d'autre."
            % (description, reponse, critique)
        )
        reponse = await appel_modele(prompt_amelioration)
        iterations += 1

    return {"reponse": reponse, "iterations": iterations, "arret": "plafond_iterations"}
