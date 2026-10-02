# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Orchestration multi-sous-tâches (mission A)
===========================================================
Deux étages, volontairement séparés :

1. detecter_sous_taches() — décide SEULEMENT si une demande justifie une
   orchestration. Déterministe, sans appel modèle : le garde-fou de
   proportionnalité doit rester testable vite et ne peut pas se laisser
   convaincre par un raisonnement du modèle lui-même.
2. executer_sous_taches() — exécute, une fois la décision prise. Prend
   l'appel modèle en paramètre (injecté) : ce fichier ne connaît aucun
   détail de fournisseur IA, main2.py fournit l'appel réel.

POURQUOI UN GARDE-FOU DÉTERMINISTE ET PAS UN JUGEMENT DU MODÈLE
Un modèle qu'on interroge « est-ce que ça mérite plusieurs agents ? » peut
se convaincre que oui sur a peu près n'importe quoi — c'est exactement le
risque nommé dans le brief (l'incident du gym australien avec OpenClaw : un
agent qui poursuit un objectif sans jugement sur la méthode). Un filtre
regex n'a pas ce problème : il refuse ou accepte selon une règle écrite,
lisible, et qui ne peut pas se laisser convaincre.

CE QUE CE FICHIER NE FAIT PAS
Il ne résout pas les références. « Compare le prix de ces 3 produits » ne
nomme aucun produit dans la phrase — impossible à extraire ici, et ce
n'est pas le rôle de ce filtre. Il renvoie le compte annoncé (3), une liste
vide d'éléments nommés, et laisse l'appelant (A2, qui a le contexte de la
conversation) résoudre ce que sont ces 3 produits.

LA LIMITE DE 5
Les deux exemples du brief portent sur 3 éléments. 5 laisse une marge
raisonnable sans ouvrir la porte à un « compare ces 20 villes » silencieux.
Au-delà, confirmation explicite requise — jamais un plafond plus haut
appliqué sans le dire.
"""

import asyncio
import re

LIMITE_SANS_CONFIRMATION = 5

SEUIL_MOTS_MINIMUM = 6
# En dessous, aucune phrase ne justifie une orchestration : « en cas de
# doute, traitement simple par défaut » s'applique dès le comptage de mots,
# avant même de chercher un motif.

_NOMBRES_LETTRES = {
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
}

_VERBES_MULTI_CIBLES = (
    r"compare[rz]?|comparaison|diff[ée]rences? entre|"
    r"regarde ce qui s'est pass[ée] sur|cherche(?:z)? (?:des )?informations? sur chacun|"
    r"r[ée]sume(?:z)? chacun|analyse(?:z)? chacun|fais (?:le point|un point) sur chacun"
)

# Motif A — compte explicite : « compare ces 3 produits », « analyse chacun
# de ces quatre sujets ». Capture le nombre (chiffre ou mot), pas les noms —
# ils ne sont, par construction de cet exemple, pas dans la phrase.
_MOTIF_COMPTE = re.compile(
    r"(?:%s)\b[^.!?]{0,40}?\b(\d{1,2}|%s)\b"
    % (_VERBES_MULTI_CIBLES, "|".join(_NOMBRES_LETTRES)),
    re.IGNORECASE,
)

# Motif B — liste littérale : « compare le prix de X, Y et Z ». Capture les
# éléments nommés eux-mêmes, séparés par virgule et/ou « et »/« ou ».
_MOTIF_LISTE = re.compile(
    r"(?:%s)\b[^.!?:]{0,60}?[:\s]\s*(.+)$" % _VERBES_MULTI_CIBLES,
    re.IGNORECASE,
)


def _elements_de_liste(reste):
    """
    Découpe 'X, Y et Z' -> ['X', 'Y', 'Z']. Vide si ça ne ressemble pas à une liste.

    Une virgule est OBLIGATOIRE. Sans elle, scinder sur « et »/« ou » seul
    confond une énumération avec une phrase ordinaire — « compare le prix
    et dis-moi si c'est raisonnable » n'est pas une liste de deux éléments,
    c'est une instruction et une clause de suivi. Une vraie énumération de
    2+ éléments s'écrit avec au moins une virgule en français, y compris
    pour deux éléments avec « et »/« ou » final ("X, et Y" reste rare mais
    "X et Y" seul, sans aucune virgule, est trop ambigu pour être accepté).
    """
    reste = reste.strip().rstrip(".!?")
    if "," not in reste:
        return []
    morceaux = re.split(r"\s*,\s*|\s+et\s+|\s+ou\s+", reste, flags=re.IGNORECASE)
    morceaux = [m.strip() for m in morceaux if m.strip()]
    # Une liste a au moins 2 morceaux courts (pas une clause complète glissée
    # à la fin après la virgule).
    if len(morceaux) < 2 or any(len(m.split()) > 6 for m in morceaux):
        return []
    return morceaux


def detecter_sous_taches(texte):
    """
    None : traitement simple, pas d'orchestration.
    Sinon : dict avec
        - "nombre" : combien de sous-tâches (annoncé ou compté)
        - "elements" : noms extraits de la phrase, [] si non nommés
        - "confirmation_requise" : True si nombre > LIMITE_SANS_CONFIRMATION
        - "plafonne_a" : nombre réellement retenu (min(nombre, LIMITE)+confirmation sinon)

    Le refus est le comportement par défaut. Une correspondance doit être
    explicite pour faire basculer vers l'orchestration.
    """
    if not texte or len(texte.split()) < SEUIL_MOTS_MINIMUM:
        return None

    m_liste = _MOTIF_LISTE.search(texte)
    elements = _elements_de_liste(m_liste.group(1)) if m_liste else []
    if elements:
        nombre = len(elements)
    else:
        m_compte = _MOTIF_COMPTE.search(texte)
        if not m_compte:
            return None
        brut = m_compte.group(1).lower()
        nombre = int(brut) if brut.isdigit() else _NOMBRES_LETTRES[brut]

    if nombre < 2:
        return None

    confirmation_requise = nombre > LIMITE_SANS_CONFIRMATION
    plafonne_a = min(nombre, LIMITE_SANS_CONFIRMATION)

    return {
        "nombre": nombre,
        "elements": elements[:plafonne_a],
        "confirmation_requise": confirmation_requise,
        "plafonne_a": plafonne_a,
    }


async def executer_sous_taches(decomposition, texte_original, appel_modele, resoudre_elements=None):
    """
    Exécute une sous-tâche par élément, en parallèle, chacune traçable.

    `appel_modele` : callable async (prompt:str) -> str, injecté — ce
    module ne connaît aucun détail de fournisseur (Gemini, etc.). En
    production, `main2.py` y passe un appel ISOLÉ qui ne touche pas
    l'historique de conversation partagé : deux sous-tâches concurrentes
    qui écriraient dans le même historique se marcheraient dessus, et un
    fan-out interne n'a pas à polluer la mémoire de la conversation
    principale.

    `resoudre_elements` : callable async (texte, n) -> list[str], optionnel.
    Utilisé seulement si `decomposition["elements"]` est vide (compte
    annoncé sans les nommer, ex. "ces 3 produits") — un SEUL appel modèle
    pour identifier les éléments depuis le contexte, avant le fan-out.
    Sans ce paramètre, un compte sans éléments nommés est un échec propre,
    pas une invention de noms.

    Renvoie une liste de dicts, un par sous-tâche, TOUJOURS dans le même
    ordre que les éléments : {"element", "question", "reponse" ou "erreur"}.
    Une sous-tâche en échec n'empêche pas les autres de répondre — mais son
    échec reste visible, jamais silencieux.
    """
    elements = decomposition["elements"]
    if not elements:
        if resoudre_elements is None:
            return [{"element": None, "question": None,
                     "erreur": "les %d éléments ne sont pas nommés dans la demande, "
                               "et aucune résolution par contexte n'est disponible"
                               % decomposition["nombre"]}]
        elements = await resoudre_elements(texte_original, decomposition["plafonne_a"])
        if not elements:
            return [{"element": None, "question": None,
                     "erreur": "impossible d'identifier les éléments depuis le contexte"}]

    async def _une_sous_tache(element):
        question = "%s\n\nContexte : concentre-toi UNIQUEMENT sur « %s » parmi les éléments de la demande d'origine." % (texte_original, element)
        try:
            reponse = await appel_modele(question)
            return {"element": element, "question": question, "reponse": reponse}
        except Exception as e:
            return {"element": element, "question": question, "erreur": str(e)}

    return list(await asyncio.gather(*[_une_sous_tache(e) for e in elements]))


def synthese(resultats):
    """Assemble les résultats de executer_sous_taches en un texte parlable, traçable."""
    if len(resultats) == 1 and resultats[0].get("erreur") and resultats[0].get("element") is None:
        return "Je n'ai pas pu lancer cette comparaison : %s." % resultats[0]["erreur"]

    morceaux = []
    for r in resultats:
        if "erreur" in r:
            morceaux.append("Pour %s : échec (%s)." % (r["element"], r["erreur"]))
        else:
            morceaux.append("Pour %s : %s" % (r["element"], r["reponse"]))
    return "\n\n".join(morceaux)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for exemple in [
        "compare les prix de ces 3 produits",
        "regarde ce qui s'est passé sur ces 3 sujets",
        "compare le prix de la baguette, du lait et du beurre",
        "salut ça va",
        "explique-moi ce qu'est une variable",
        "compare ces 12 villes pour un déménagement",
    ]:
        print("%-58s -> %s" % (exemple, detecter_sous_taches(exemple)))
