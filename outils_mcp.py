# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Serveur MCP « outils »
====================================
Expose le registre tools/ (décorateur @outil) à n'importe quel client MCP.

Idée reprise de sosoj92/jarvis-assistant-vocal (jarvis/mcp_server.py) :
réutiliser le registre existant plutôt que de redéclarer les outils une
seconde fois. Ajouter un fichier dans tools/ suffit à le publier ici — rien
à recâbler. Même parti pris que `mail_mcp.py`, qui expose la messagerie.

DIFFÉRENCE AVEC LEUR IMPLÉMENTATION
Chez eux, un outil est une fonction typée dont le schéma de paramètres se
déduit de la signature. Ici le contrat est autre : `fonction(texte) -> str`,
un metteur en correspondance sur du langage naturel. On expose donc la forme
réelle de JARVIS plutôt que d'imiter la leur :

    lister_outils()            inventaire du registre
    resoudre(texte)            passe la phrase dans la chaîne complète
    appeler_outil(nom, texte)  cible un outil précis

CONFIRMATION
Reprise de leur garde-fou : un outil sensible n'agit pas sans `confirme=True`,
il renvoie une demande. Les niveaux sont ceux de la passerelle du HUD
(gateway.js), pour que les deux surfaces d'accès à JARVIS aient la même
échelle et pas deux politiques divergentes.

Lancement : venv\\Scripts\\python.exe outils_mcp.py    (transport stdio)

Branchement dans un client MCP, à ajouter aux serveurs déclarés :
{
  "mcpServers": {
    "jarvis-outils": {
      "command": "C:\\\\Program Files\\\\JARVIS\\\\venv\\\\Scripts\\\\python.exe",
      "args": ["C:\\\\Program Files\\\\JARVIS\\\\outils_mcp.py"]
    }
  }
}
"""

import asyncio
import builtins

from mcp.server.fastmcp import FastMCP

import tools

mcp = FastMCP("jarvis-outils")

# Outils qui ne doivent pas agir sans accord explicite. Même échelle que le
# champ `niveau` de gateway.js : au-delà de 6, on demande.
#   mail_manager (115) rédige et envoie du courrier -> 9
#   web_change   (110) sort sur le réseau            -> 5, passe seul
NIVEAUX_OUTILS = {
    "mail_manager": 9,
}
NIVEAU_PAR_DEFAUT = 3
PLAFOND_AUTONOMIE = 6


def _niveau(nom):
    return NIVEAUX_OUTILS.get(nom, NIVEAU_PAR_DEFAUT)


# ── Capacités runtime attendues par certains outils ──────────────────────
# main2.py publie normalement ces fonctions dans builtins. Le serveur MCP
# tourne dans son propre processus, sans main2 : sans ces bouchons,
# infos_systeme lève NameError('get_user_name') au premier appel. On fournit
# le minimum plutôt que de laisser l'outil échouer en silence.
def _installer_bouchons():
    valeurs = {
        "get_user_name": lambda: "Monsieur",
        "get_user_age": lambda: None,
    }
    for nom, fonction in valeurs.items():
        if not hasattr(builtins, nom):
            setattr(builtins, nom, fonction)


_installer_bouchons()
_NOMS, _ECHECS = tools.charger_outils()


@mcp.tool()
def lister_outils() -> list:
    """Inventaire des outils JARVIS disponibles : nom, priorité dans la chaîne
    de résolution, mode d'exécution, description, et niveau d'autorisation
    requis (au-dessus de 6, l'appel exige confirme=True)."""
    return [
        {**o, "niveau": _niveau(o["nom"]),
         "confirmation_requise": _niveau(o["nom"]) > PLAFOND_AUTONOMIE}
        for o in tools.lister_outils()
    ]


@mcp.tool()
def outils_en_echec() -> list:
    """Modules de tools/ qui n'ont pas pu être chargés, avec leur erreur.
    Vide si tout va bien. Un outil absent de lister_outils() sans figurer ici
    n'existe tout simplement pas."""
    return [{"module": m, "erreur": e} for m, e in _ECHECS]


@mcp.tool()
def resoudre(texte: str) -> dict:
    """Passe une phrase dans la chaîne complète des outils JARVIS et renvoie la
    réponse du premier qui sait la traiter, avec le nom de cet outil.

    C'est le point d'entrée normal : il reproduit exactement ce que fait JARVIS
    en interne quand on lui parle. Renvoie repondu=False si aucun outil ne
    correspond — dans ce cas, JARVIS confierait la phrase à son modèle."""
    declenches = []
    tools.definir_observateur(
        lambda nom, prio, mode, ok, ms, detail: declenches.append(
            {"outil": nom, "ok": ok, "ms": ms, "erreur": detail}))
    try:
        reponse = asyncio.run(tools.resoudre_async(texte))
    finally:
        tools.definir_observateur(None)

    gagnant = next((d["outil"] for d in declenches if d["ok"]), None)
    return {
        "repondu": bool(reponse),
        "reponse": reponse or "",
        "outil": gagnant,
        "tentatives": declenches,
    }


@mcp.tool()
def appeler_outil(nom: str, texte: str, confirme: bool = False) -> dict:
    """Appelle un outil JARVIS précis, en court-circuitant la chaîne.

    `nom` doit figurer dans lister_outils(). Les outils de niveau supérieur à 6
    (mail_manager, qui rédige et envoie du courrier) refusent d'agir tant que
    confirme=True n'est pas passé : ils renvoient alors une demande, sans effet
    de bord. Aucune action irréversible ne part en silence."""
    correspondances = [(p, n, f) for p, n, f in tools._REGISTRE if n == nom]
    if not correspondances:
        return {"ok": False,
                "erreur": "outil inconnu : %s" % nom,
                "disponibles": [o["nom"] for o in tools.lister_outils()]}

    niveau = _niveau(nom)
    if niveau > PLAFOND_AUTONOMIE and not confirme:
        return {
            "ok": False,
            "confirmation_requise": True,
            "niveau": niveau,
            "message": ("L'outil '%s' est de niveau %d (plafond %d). "
                        "Rappeler avec confirme=True pour l'exécuter."
                        % (nom, niveau, PLAFOND_AUTONOMIE)),
        }

    priorite, _, _ = correspondances[0]
    try:
        # On repasse par resoudre_async sur la seule priorité de cet outil :
        # les trois modes (sync/async/bloquant) sont ainsi gérés par le socle,
        # au lieu d'être réimplémentés ici et de diverger au premier ajout.
        reponse = asyncio.run(tools.resoudre_async(texte, depuis=priorite, jusqua=priorite))
    except Exception as e:
        return {"ok": False, "erreur": repr(e)}
    return {"ok": bool(reponse), "outil": nom, "reponse": reponse or "",
            "repondu": bool(reponse)}


# ── Mémoire partagée ─────────────────────────────────────────────────────
# C'est CE point d'entrée qui rend la mémoire partagée plutôt qu'un carnet à
# sens unique : sans lui, un agent de code ne peut ni lire ce que JARVIS a
# constaté, ni y laisser ce qu'il a compris.
#
# La source est imposée par l'appelant et non devinée : un agent doit signer
# ses notes de son nom, pour qu'on sache toujours qui a écrit quoi.

@mcp.tool()
def memoire_lister(dossier: str = "") -> list:
    """Liste les notes de la mémoire partagée, avec leur source et leur date.
    `dossier` filtre parmi : decisions, pannes, conventions, etat, brouillons."""
    import memoire_partagee as mp
    return mp.lister(dossier or None)


@mcp.tool()
def memoire_chercher(motif: str) -> dict:
    """Cherche un mot ou une expression régulière dans toutes les notes.
    Renvoie un extrait autour de chaque correspondance."""
    import memoire_partagee as mp
    return mp.chercher(motif)


@mcp.tool()
def memoire_lire(dossier: str, id_note: str, source: str) -> dict:
    """Lit une note précise. `source` fait partie de son identité : deux
    auteurs peuvent avoir écrit sur le même sujet, ce sont deux notes."""
    import memoire_partagee as mp
    n = mp.lire(dossier, id_note, source)
    return n or {"erreur": "note introuvable"}


@mcp.tool()
def memoire_ecrire(dossier: str, id_note: str, corps: str,
                   source: str, titre: str = "", sujet: str = "") -> dict:
    """Écrit une note dans la mémoire partagée.

    `source` DOIT être ton propre nom (claude-code, opencode, codex...), pas
    'jarvis' : chaque auteur n'écrit que ses propres fichiers, ce qui évite
    tout conflit sans verrou. Écrire sous le nom d'un autre écraserait son
    travail.

    `dossier` : decisions | pannes | conventions | etat | brouillons"""
    import memoire_partagee as mp
    try:
        chemin = mp.ecrire(dossier, id_note, corps, source=source,
                           titre=titre or None,
                           sujet=[s.strip() for s in sujet.split(",") if s.strip()] or None)
        mp.regenerer_index()
        return {"ok": True, "chemin": str(chemin)}
    except ValueError as e:
        return {"ok": False, "erreur": str(e)}


if __name__ == "__main__":
    mcp.run()
