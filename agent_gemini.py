# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Adaptateur Gemini de l'agent de fichiers
=======================================================
agent_fichiers.py ne connaît aucun fournisseur : il reçoit un appelable
`modele(systeme, historique, declarations)`. Ce fichier fabrique celui de
Gemini (SDK google-genai) — le seul endroit qui en connaisse les types.

LES TROIS PIÈGES DU PROTOCOLE, RÉGLÉS ICI
1. Appels d'outils en PARALLÈLE : Gemini exige autant de réponses d'outil que
   d'appels, dans UN SEUL message. L'historique neutre les stocke séparément ;
   on regroupe ici.
2. Contenu « brut » du modèle : les modèles récents attachent des signatures de
   pensée (thought_signature) aux appels d'outils et REFUSENT le tour suivant
   si elles manquent. On renvoie donc tel quel le Content reçu, au lieu de le
   reconstruire.
3. Réponse sans contenu (bloquée, ou MALFORMED_FUNCTION_CALL) : on lève une
   erreur qui NOMME la raison, plutôt que de renvoyer un tour vide que la
   boucle prendrait pour une réponse finale.

Le SDK est passé en paramètre (`types`) : ce module s'importe sans lui, et les
tests l'exercent avec les vraies classes sans réseau.
"""


def contenus_gemini(types, historique):
    """Historique neutre -> liste de Content Gemini."""
    sortie, i = [], 0
    while i < len(historique):
        m = historique[i]
        role = m.get("role")
        if role == "user":
            sortie.append(types.Content(role="user", parts=[types.Part(text=m["texte"])]))
            i += 1
        elif role == "assistant":
            if m.get("brut") is not None:
                sortie.append(m["brut"])
            else:
                parts = []
                if m.get("texte"):
                    parts.append(types.Part(text=m["texte"]))
                for a in m.get("appels") or []:
                    parts.append(types.Part(function_call=types.FunctionCall(
                        id=a.get("id"), name=a["nom"], args=a.get("args") or {})))
                sortie.append(types.Content(role="model", parts=parts))
            i += 1
        elif role == "outil":
            parts = []
            while i < len(historique) and historique[i].get("role") == "outil":
                o = historique[i]
                parts.append(types.Part(function_response=types.FunctionResponse(
                    id=o.get("id"), name=o["nom"], response={"resultat": o["resultat"]})))
                i += 1
            sortie.append(types.Content(role="user", parts=parts))
        else:
            i += 1
    return sortie


def lire_reponse(rep):
    """Réponse Gemini -> {"texte", "appels", "brut"}. Lève si elle est vide ou bloquée."""
    candidats = getattr(rep, "candidates", None) or []
    cand = candidats[0] if candidats else None
    contenu = getattr(cand, "content", None) if cand is not None else None
    parts = list(getattr(contenu, "parts", None) or [])
    if contenu is None or not parts:
        raison = getattr(cand, "finish_reason", None) if cand is not None else None
        if raison is None:
            raison = getattr(getattr(rep, "prompt_feedback", None), "block_reason", None)
        raise RuntimeError("réponse Gemini sans contenu (%s)" % (raison or "raison inconnue"))
    texte = "".join(p.text for p in parts
                    if getattr(p, "text", None) and not getattr(p, "thought", False))
    appels = []
    for p in parts:
        fc = getattr(p, "function_call", None)
        if fc is not None and getattr(fc, "name", None):
            appels.append({"id": getattr(fc, "id", None), "nom": fc.name, "args": dict(fc.args or {})})
    return {"texte": texte, "appels": appels, "brut": contenu}


def creer_modele(client, types, nom_modele, *, suivi=None, sur_erreur=None, delai_ms=90_000):
    """
    Fabrique le `modele` de agent_fichiers.executer_agent.

    suivi(reponse)   : appelé après chaque réponse (coût/tokens) ; ses erreurs sont ignorées.
    sur_erreur(exc)  : appelé avant de relever une erreur du SDK (ex. marquer un quota atteint).
    delai_ms         : délai HTTP par appel — sans lui, un appel bloqué figerait le thread.
    """
    def modele(systeme, historique, declarations):
        config = types.GenerateContentConfig(
            system_instruction=systeme,
            temperature=0.2,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name=d["nom"], description=d["description"],
                                          parameters_json_schema=d["parametres"])
                for d in declarations])],
            # Boucle manuelle : c'est agent_fichiers qui exécute les outils, dans son bac à sable.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            http_options=types.HttpOptions(timeout=delai_ms),
        )
        try:
            rep = client.models.generate_content(
                model=nom_modele, contents=contenus_gemini(types, historique), config=config)
        except Exception as e:
            if sur_erreur:
                try:
                    sur_erreur(e)
                except Exception:
                    pass
            raise
        if suivi:
            try:
                suivi(rep)
            except Exception:
                pass
        return lire_reponse(rep)

    return modele
