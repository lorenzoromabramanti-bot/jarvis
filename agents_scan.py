# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Mode agent : recensement des IA de la machine
===========================================================
Balaie la machine et rend compte de TOUS les agents IA présents : ceux qui
tournent, ceux qui sont installés mais éteints, les serveurs MCP, les
runtimes de modèles locaux, et JARVIS lui-même avec ses sous-systèmes.

PRINCIPE : ne rapporter que du constaté.
Un agent est « actif » parce qu'un processus porte son nom ou qu'un port
répond — jamais parce qu'il est installé. Un port qui refuse la connexion
est signalé comme éteint, pas passé sous silence. C'est toute la différence
avec un tableau de bord décoratif.

REGROUPEMENT
Une application Electron ouvre une quinzaine de processus (Claude en ouvre
15 sur cette machine). Les compter comme 15 agents n'aurait aucun sens : on
regroupe par agent, en gardant le nombre de processus, la mémoire cumulée
et l'ancienneté du plus vieux.

Utilisable sans JARVIS lancé :
    venv\\Scripts\\python.exe agents_scan.py
"""

import os
import socket
import subprocess
import sys
import time

try:
    import psutil
except ImportError:
    psutil = None

RACINE = os.path.dirname(os.path.abspath(__file__))

# Catalogue. `motifs` est cherché dans la ligne de commande en minuscules.
# `categorie` sert au regroupement dans l'interface.
CATALOGUE = [
    # -- assistants de code --
    {"nom": "Claude Desktop", "categorie": "assistant",
     "motifs": ["windowsapps\\claude", "\\claude\\claude.exe"]},
    {"nom": "Claude Code (CLI)", "categorie": "assistant",
     "motifs": ["\\.local\\bin\\claude", "cli.js --", "claude-code"]},
    {"nom": "OpenCode", "categorie": "assistant", "motifs": ["opencode"]},
    {"nom": "Codex", "categorie": "assistant", "motifs": ["codex"]},
    {"nom": "Gemini CLI", "categorie": "assistant", "motifs": ["gemini"]},
    {"nom": "Cursor", "categorie": "assistant", "motifs": ["cursor"]},
    {"nom": "Antigravity", "categorie": "assistant", "motifs": ["antigravity"]},
    {"nom": "Hermes", "categorie": "assistant", "motifs": ["hermes"]},
    # -- serveurs MCP --
    {"nom": "MCP Windows", "categorie": "mcp", "motifs": ["windows-mcp"]},
    {"nom": "MCP Home Assistant", "categorie": "mcp", "motifs": ["ha-mcp"]},
    {"nom": "MCP messagerie JARVIS", "categorie": "mcp", "motifs": ["mail_mcp.py"]},
    {"nom": "MCP outils JARVIS", "categorie": "mcp", "motifs": ["outils_mcp.py"]},
    {"nom": "MCP (autre)", "categorie": "mcp", "motifs": ["mcp-server", "mcp_server"]},
    # -- moteurs de modeles --
    {"nom": "Ollama", "categorie": "modele", "motifs": ["ollama"]},
    {"nom": "LM Studio", "categorie": "modele", "motifs": ["lm studio", "lmstudio"]},
    {"nom": "ComfyUI", "categorie": "modele", "motifs": ["comfy"]},
]

# Services interrogeables par leur port. Un port muet = service eteint.
SERVICES = [
    {"nom": "Ollama (API)", "categorie": "modele", "port": 11434,
     "role": "modeles de langage locaux"},
    {"nom": "JARVIS — WebSocket", "categorie": "jarvis", "port": 8765,
     "role": "canal principal, interfaces et outils"},
    {"nom": "JARVIS — interface PC", "categorie": "jarvis", "port": 8001,
     "role": "HUD servi par Vite"},
    {"nom": "JARVIS — adaptateur HUD", "categorie": "jarvis", "port": 9999,
     "role": "passerelle REST/SSE du HUD"},
    {"nom": "JARVIS — interface mobile", "categorie": "jarvis", "port": 8000,
     "role": "acces telephone"},
    {"nom": "LM Studio (API)", "categorie": "modele", "port": 1234,
     "role": "serveur compatible OpenAI"},
]


def _port_ouvert(port, hote="127.0.0.1", delai=0.35):
    s = socket.socket()
    s.settimeout(delai)
    try:
        return s.connect_ex((hote, port)) == 0
    finally:
        s.close()


def _processus():
    """Tous les processus, avec ligne de commande. Liste vide si psutil manque."""
    if psutil is None:
        return []
    sortie = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or []) or (p.info.get("name") or "")
            sortie.append((p, cmd.lower()))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sortie


def _agreger(procs):
    """Mémoire cumulée, plus ancien démarrage, PID principal."""
    total_mo, plus_vieux, principal = 0, None, None
    for p in procs:
        try:
            total_mo += p.memory_info().rss / 1048576.0
            t = p.create_time()
            if plus_vieux is None or t < plus_vieux:
                plus_vieux, principal = t, p.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return round(total_mo), plus_vieux, principal


def _duree(depuis):
    if not depuis:
        return ""
    s = int(time.time() - depuis)
    if s < 60:
        return "%ds" % s
    if s < 3600:
        return "%dmin" % (s // 60)
    if s < 86400:
        return "%dh%02d" % (s // 3600, (s % 3600) // 60)
    return "%dj %dh" % (s // 86400, (s % 86400) // 3600)


def scanner():
    """Recensement complet. Renvoie une liste d'agents, actifs d'abord."""
    procs = _processus()
    agents = []
    deja = set()

    # ── Agents identifiés par leurs processus ────────────────────────────
    for entree in CATALOGUE:
        trouves = []
        for p, cmd in procs:
            if p.pid in deja:
                continue
            if any(m in cmd for m in entree["motifs"]):
                trouves.append(p)
        if not trouves:
            continue
        for p in trouves:
            deja.add(p.pid)
        memoire, depuis, principal = _agreger(trouves)
        agents.append({
            "nom": entree["nom"], "categorie": entree["categorie"],
            "actif": True, "processus": len(trouves), "pid": principal,
            "memoire_mo": memoire, "depuis": _duree(depuis),
            "detail": "%d processus" % len(trouves) if len(trouves) > 1 else "",
        })

    # ── Services identifiés par leur port ────────────────────────────────
    for s in SERVICES:
        ouvert = _port_ouvert(s["port"])
        agents.append({
            "nom": s["nom"], "categorie": s["categorie"],
            "actif": ouvert, "port": s["port"],
            "detail": s["role"] if ouvert else "port %d muet — service eteint" % s["port"],
            "processus": 0, "memoire_mo": 0, "depuis": "",
        })

    # ── Modèles réellement chargés dans Ollama ───────────────────────────
    if _port_ouvert(11434):
        try:
            r = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=12)
            lignes = [l for l in r.stdout.splitlines()[1:] if l.strip()]
            for l in lignes:
                agents.append({
                    "nom": "Modele charge : %s" % l.split()[0], "categorie": "modele",
                    "actif": True, "detail": l.strip()[:90],
                    "processus": 0, "memoire_mo": 0, "depuis": "",
                })
            if not lignes:
                agents.append({
                    "nom": "Ollama : aucun modele charge", "categorie": "modele",
                    "actif": False, "detail": "le serveur repond mais ne tient aucun modele en memoire",
                    "processus": 0, "memoire_mo": 0, "depuis": "",
                })
        except Exception:
            pass

    actifs = {"actif": 0, "inactif": 1}
    agents.sort(key=lambda a: (actifs[("actif" if a["actif"] else "inactif")],
                               a["categorie"], a["nom"]))
    return agents


def resume():
    a = scanner()
    return {"total": len(a),
            "actifs": sum(1 for x in a if x["actif"]),
            "categories": sorted({x["categorie"] for x in a})}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    agents = scanner()
    print()
    print("=" * 78)
    print("MODE AGENT — %d entree(s), %d active(s)"
          % (len(agents), sum(1 for a in agents if a["actif"])))
    print("=" * 78)
    categorie = None
    for a in agents:
        if a["categorie"] != categorie:
            categorie = a["categorie"]
            print("\n  -- %s --" % categorie.upper())
        etat = "ACTIF  " if a["actif"] else "eteint "
        extra = []
        if a.get("processus"):
            extra.append("%d proc" % a["processus"])
        if a.get("memoire_mo"):
            extra.append("%d Mo" % a["memoire_mo"])
        if a.get("depuis"):
            extra.append("depuis %s" % a["depuis"])
        print("  %s %-26s %s" % (etat, a["nom"], " · ".join(extra)))
        if a.get("detail"):
            print("          %s" % a["detail"])
    print("=" * 78)
