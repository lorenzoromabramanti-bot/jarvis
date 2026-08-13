# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Serveur MCP « messagerie »
========================================
Expose la boîte mail unifiée de JARVIS (Gmail + iCloud + Outlook via email_hub)
comme des OUTILS MCP. Permet à un client MCP (Claude Desktop, ou tout agent
compatible MCP) de lire/résumer/chercher tes e-mails.

Lancement : python mail_mcp.py   (transport stdio)

Branchement dans Claude Desktop — ajouter à
%APPDATA%\\Claude\\claude_desktop_config.json :
{
  "mcpServers": {
    "jarvis-mail": {
      "command": "C:\\\\Program Files\\\\JARVIS\\\\venv\\\\Scripts\\\\python.exe",
      "args": ["C:\\\\Program Files\\\\JARVIS\\\\mail_mcp.py"]
    }
  }
}
Puis redémarrer Claude Desktop : les outils jarvis-mail apparaissent.
"""

from mcp.server.fastmcp import FastMCP
import email_hub

mcp = FastMCP("jarvis-mail")


@mcp.tool()
def boite_unifiee(limit_par_compte: int = 8) -> dict:
    """Relève les e-mails récents de TOUTES les boîtes configurées (Gmail, iCloud, Outlook).
    Renvoie l'état de chaque compte et la liste unifiée des messages (expéditeur, sujet, date, compte)."""
    return email_hub.boite_unifiee(limit_par_compte)


@mcp.tool()
def resume_mail() -> str:
    """Résumé en français des e-mails les plus récents, toutes boîtes confondues."""
    return email_hub.resume_vocal()


@mcp.tool()
def chercher_mail(mot_cle: str, limit_par_compte: int = 25) -> list:
    """Cherche un mot-clé dans l'expéditeur ou le sujet des e-mails récents (toutes boîtes)."""
    data = email_hub.boite_unifiee(limit_par_compte)
    k = (mot_cle or "").lower()
    return [m for m in data.get("messages", [])
            if k in (str(m.get("sujet", "")) + " " + str(m.get("de", ""))).lower()]


@mcp.tool()
def lister_comptes() -> list:
    """Liste les boîtes mail configurées (nom, fournisseur, adresse) — sans les mots de passe."""
    return [{"name": c.get("name"), "provider": c.get("provider"), "user": c.get("user")}
            for c in email_hub.charger_comptes()]


if __name__ == "__main__":
    mcp.run()
