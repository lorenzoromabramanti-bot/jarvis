# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — « Démonte ce site » : rétro-ingénierie d'un site avec REA
=======================================================================
Idée tirée d'une vidéo de Zubair Trabzada (16/10/2026) : JARVIS confie
l'analyse à Claude Code, qui pilote REA (serveur MCP « rea », skill
reverse-engineer-anything). Chrome s'ouvre avec un profil temporaire, la page
défile, REA relève le code chargé et les requêtes ; Claude en fait un rapport.
JARVIS range ce rapport dans la mémoire partagée :
etat/demontage-<domaine>.claude-code.md

LECTURE SEULE : Claude Code n'a droit qu'aux outils REA (--allowedTools) ; en
mode -p, l'écriture de fichiers et le shell sont refusés au lieu d'attendre
une confirmation. C'est JARVIS qui écrit le rapport, pas l'agent.
"""

import os
import re
import subprocess
import tempfile
from urllib.parse import urlparse

import delegation_code
import memoire_partagee

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MODELE = "sonnet"          # assez pour un rapport ; Opus brûlerait la limite hebdo
MAX_TOURS = 40
TIMEOUT = 900              # secondes : un site lourd peut demander plusieurs captures

# « démonte ce site igloo.inc », « démonte igloo point inc », « rétro-ingénierie
# du site X », « reverse engineer X ». La cible s'arrête à la ponctuation finale.
_MOTIF = re.compile(
    r"\b(?:d[ée]monte(?:[- ]moi)?|r[ée]tro[- ]?ing[ée]nierie|reverse[- ]engineer)\s+"
    r"(?:(?:de|du|des|le|la|les|ce|cet|cette|l')\s*)*"
    r"(?P<site>site\s+(?:web\s+|internet\s+)?)?"
    r"(?:(?:de|du)\s+)?"
    r"(?P<cible>[^\s,;!?]+(?:\s+point\s+[^\s,;!?]+)*)",
    re.IGNORECASE)
_DOMAINE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")


def normaliser_url(cible):
    """« igloo point inc », « igloo.inc », « https://igloo.inc/x » -> URL https, ou None."""
    t = re.sub(r"\s+point\s+", ".", (cible or "").strip().lower()).rstrip(".")
    if not re.match(r"^https?://", t):
        t = "https://" + t
    u = urlparse(t)
    if u.scheme not in ("http", "https") or not _DOMAINE.match(u.hostname or ""):
        return None
    return t


def detecter(texte):
    """
    None : ce n'est pas une demande de démontage.
    Sinon {"url": str|None, "domaine": str|None} ; url None = le mot « site »
    est là mais l'adresse n'est pas lisible (« igloo inc » dicté sans « point »).
    « démonte la roue du vélo » ne dit pas « site » et n'a pas de domaine : None.
    """
    m = _MOTIF.search(texte or "")
    if not m:
        return None
    url = normaliser_url(m.group("cible"))
    if url:
        return {"url": url, "domaine": urlparse(url).hostname}
    return {"url": None, "domaine": None} if m.group("site") else None


def consigne(url):
    return (
        f"Démonte le site {url} avec REA (skill reverse-engineer-anything, outils MCP rea).\n"
        f"Navigateur : capture_browser_scenario en mode launch, executable_path \"{CHROME}\" "
        "(profil temporaire). Ouvre la page, attends qu'elle soit chargée, fais-la défiler "
        "jusqu'en bas en plusieurs étapes, et relève le réseau et les scripts utiles. "
        "Analyse ensuite le code chargé (bibliothèques et versions, animations, 3D, poids des ressources).\n"
        "Ne modifie aucun fichier. Réponds en français, uniquement avec ce rapport en Markdown :\n"
        "RÉSUMÉ : <deux phrases simples, à dire à voix haute, sans Markdown>\n"
        "## Ce que c'est\n## Technologies (avec versions)\n## Comment marchent les effets\n"
        "## Ce qui pèse le plus\n## Pour refaire pareil\n"
        "## Preuves (ce que REA a observé, et ce qui reste une supposition)\n")


def extraire_resume(rapport):
    m = re.search(r"^\s*\**R[ÉE]SUM[ÉE]\**\s*:\s*(.+)$", rapport or "", re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip().strip("*").strip() if m else ""


def demonter(url, journal=print):
    """
    Lance l'analyse (bloquant, plusieurs minutes). Renvoie
    {"succes", "domaine", "resume", "chemin", "erreur"} ; chaque échec est nommé.
    """
    domaine = urlparse(url).hostname
    res = {"succes": False, "domaine": domaine, "resume": "", "chemin": None, "erreur": None}
    chemin_claude = delegation_code._resoudre("claude")
    if not os.path.isabs(chemin_claude):
        res["erreur"] = "Claude Code est introuvable sur le PATH"
        return res
    if not delegation_code._claude_authentique(chemin_claude):
        res["erreur"] = "le binaire claude ne répond pas comme Claude Code"
        return res
    if not os.path.isfile(CHROME):
        res["erreur"] = "Chrome est introuvable (%s)" % CHROME
        return res
    env = dict(os.environ,
               FIN_CLAUDE_SEUIL="999999",   # pas de notif « Claude a fini » : JARVIS prévient lui-même
               MCP_TIMEOUT="60000")         # REA met parfois plus de 30 s à démarrer
    journal("[DEMONTAGE] %s : Claude Code + REA (%s)" % (url, MODELE))
    try:
        r = delegation_code._lancer(
            # La consigne passe par stdin : --allowedTools prend TOUS les mots qui le
            # suivent, une consigne placée après devenait un nom d'outil.
            "claude", ["-p", "--model", MODELE, "--max-turns", str(MAX_TOURS),
                       "--allowedTools", "mcp__rea"],
            input=consigne(url), capture_output=True, encoding="utf-8", errors="replace", timeout=TIMEOUT,
            cwd=tempfile.gettempdir(), env=env)
    except subprocess.TimeoutExpired:
        res["erreur"] = "Claude Code n'a pas fini en %d minutes" % (TIMEOUT // 60)
        return res
    except OSError as e:
        res["erreur"] = "Claude Code ne se lance pas (%s)" % e
        return res
    rapport = (r.stdout or "").strip()
    if r.returncode != 0 or "##" not in rapport:
        detail = rapport or (r.stderr or "").strip()
        res["erreur"] = ("Claude Code n'est plus connecté au compte, il faut lancer « claude auth login »"
                         if "authenticate" in detail.lower() else
                         "Claude Code : %s" % (detail[-300:] or "code %d" % r.returncode))
        return res
    res["resume"] = extraire_resume(rapport)
    res["chemin"] = str(memoire_partagee.ecrire(
        "etat", "demontage-" + domaine, "Source : %s\n\n%s" % (url, rapport), source="claude-code",
        sujet=["demontage", domaine], titre="Démontage de %s" % domaine))
    res["succes"] = True
    return res


def phrase(res, nom="Monsieur"):
    if not res.get("succes"):
        return "Le démontage de %s a échoué, %s : %s." % (res.get("domaine"), nom, res.get("erreur"))
    milieu = (res.get("resume") or "").rstrip(".") + ". " if res.get("resume") else ""
    return ("Démontage de %s terminé, %s. %sLe rapport complet est dans la mémoire partagée."
            % (res["domaine"], nom, milieu))
