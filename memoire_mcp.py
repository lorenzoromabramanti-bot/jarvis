# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Serveur MCP « mémoire » (mémoire partagée SEULE)
=============================================================
Le point d'entrée des agents de code (Claude Code, Codex, OpenCode) dans le vault
`memoire_partagee` : lister, chercher, lire, écrire. Rien d'autre.

Pourquoi un serveur à part plutôt que `outils_mcp.py` : celui-là expose aussi tout
le registre tools/ (courrier, pilotage du PC), et sa confirmation n'est qu'un
paramètre que l'agent peut remplir lui-même. Un agent qui code en autonomie n'a
besoin que de la mémoire (08/10/2026). `outils_mcp.py` réutilise ces fonctions.

Lancement : venv\\Scripts\\python.exe memoire_mcp.py    (transport stdio)
"""

from mcp.server.fastmcp import FastMCP

import memoire_partagee as mp

mcp = FastMCP("jarvis-memoire")

# La source est imposée par l'appelant et non devinée : un agent doit signer
# ses notes de son nom, pour qu'on sache toujours qui a écrit quoi.


@mcp.tool()
def memoire_lister(dossier: str = "") -> list:
    """Liste les notes de la mémoire partagée, avec leur source et leur date.
    `dossier` filtre parmi : decisions, pannes, conventions, etat, brouillons."""
    return mp.lister(dossier or None)


@mcp.tool()
def memoire_chercher(motif: str) -> dict:
    """Cherche un mot ou une expression régulière dans toutes les notes.
    Renvoie un extrait autour de chaque correspondance."""
    return mp.chercher(motif)


@mcp.tool()
def memoire_lire(dossier: str, id_note: str, source: str) -> dict:
    """Lit une note précise. `source` fait partie de son identité : deux
    auteurs peuvent avoir écrit sur le même sujet, ce sont deux notes."""
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
    try:
        chemin = mp.ecrire(dossier, id_note, corps, source=source,
                           titre=titre or None,
                           sujet=[s.strip() for s in sujet.split(",") if s.strip()] or None)
        mp.regenerer_index()
        return {"ok": True, "chemin": str(chemin)}
    except ValueError as e:
        return {"ok": False, "erreur": str(e)}


OUTILS = (memoire_lister, memoire_chercher, memoire_lire, memoire_ecrire)

if __name__ == "__main__":
    mcp.run()
