# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Propositions d'amélioration
=========================================
JARVIS regarde son propre état, dit ce qu'il voudrait voir corrigé, et rédige
le prompt qui permettra à un agent de code de le faire. **Il n'écrit jamais le
code lui-même.**

POURQUOI CE DÉCOUPAGE
Laisser un assistant réécrire son propre code sur un main2.py de 10 000 lignes
sans tests, c'est le moyen le plus court de casser une installation qui marche.
En séparant « constater » de « modifier », le pire cas devient un mauvais
prompt — qu'un humain lit avant qu'il ne parte.

LE PASSAGE PAR L'HUMAIN N'EST PAS DÉCORATIF
Ce module produit du TEXTE QUI DEVIENDRA DES INSTRUCTIONS pour un agent
disposant d'un accès en écriture au disque. Trois verrous, dans cet ordre :

  1. `envoyer()` refuse sans confirme=True. Pas de valeur par défaut permissive.
  2. Le dépôt doit être propre, et l'agent travaille sur une branche dédiée
     créée pour l'occasion. Une modification ratée s'annule d'un checkout.
  3. Le prompt complet est lisible avant envoi — c'est tout l'intérêt du
     découpage. Le relire est le geste qui compte.

Rien ici ne se déclenche tout seul : aucun minuteur, aucune boucle de fond.

Utilisation :
    venv\\Scripts\\python.exe auto_amelioration.py            # liste
    venv\\Scripts\\python.exe auto_amelioration.py --prompt 1 # affiche
"""

import json
import os
import subprocess
import sys

import auto_diagnostic

RACINE = os.path.dirname(os.path.abspath(__file__))

# Agents de code disponibles. La commande reçoit le prompt en argument.
# `claude` est le défaut voulu : c'est celui qui connaît déjà ce projet.
AGENTS = {
    "claude":   ["claude", "-p"],
    "opencode": ["opencode", "run"],
    "codex":    ["codex", "exec"],
}
AGENT_DEFAUT = "claude"

# Contraintes rappelées dans CHAQUE prompt. Un agent démarre sans mémoire de
# ce projet : ce qui n'est pas écrit ici n'existe pas pour lui.
CONTRAINTES = """CONTRAINTES ABSOLUES DE CE PROJET
- Aucune fonctionnalité qui marche ne doit être supprimée, remplacée sans
  équivalent, ni cassée en silence. C'est la règle numéro un.
- Ne pas reformater, réorganiser ni « nettoyer » du code hors sujet.
  Diff minimal, strictement limité au problème décrit.
- Écrire les commentaires en français, comme le reste du fichier.
- main2.py fait plus de 10 000 lignes et n'a pas de tests : toute
  modification doit rester locale et vérifiable à l'oeil.
- Si le correctif exige de toucher plus de trois fichiers, s'arrêter et
  expliquer pourquoi plutôt que de se lancer.
- Terminer en indiquant comment vérifier que le correctif marche."""


def _proposition(constat):
    """Un constat -> une proposition avec son prompt prêt à l'emploi."""
    titre = constat["titre"]
    prompt = """Tu interviens sur J.A.R.V.I.S., un assistant vocal Python situé
dans "C:\\Program Files\\JARVIS" (dépôt git, branche de travail dédiée).

PROBLÈME CONSTATÉ PAR JARVIS LUI-MÊME
%s

CE QUI A ÉTÉ OBSERVÉ
%s
%s

CE QUI EST DEMANDÉ
Corriger la cause de ce constat. Ne pas masquer le symptôme : si une valeur
est écartée en silence, le correctif doit soit l'accepter, soit le DIRE
clairement à l'utilisateur — jamais retomber sur un défaut sans un mot.

%s""" % (
        titre,
        constat["preuve"],
        ("\nFICHIER CONCERNÉ\n%s" % constat["fichier"]) if constat["fichier"] else "",
        CONTRAINTES,
    )
    return {
        "cle": constat["cle"],
        "gravite": constat["gravite"],
        "titre": titre,
        "preuve": constat["preuve"],
        "fichier": constat["fichier"],
        "prompt": prompt,
        "branche": "auto/%s" % constat["cle"],
    }


def proposer():
    """
    Propositions issues du diagnostic, les plus graves d'abord.

    Seuls les constats actionnables donnent lieu à une proposition : un dépôt
    propre ou un module simplement absent n'appelle pas de correctif.
    """
    ignores = {"git-propre", "git-sale", "git-absent"}
    return [_proposition(c) for c in auto_diagnostic.diagnostiquer()
            if c["gravite"] != "info" and c["cle"] not in ignores]


# ── Envoi à un agent de code ─────────────────────────────────────────────

def _git(*args, **kw):
    return subprocess.run(["git"] + list(args), cwd=RACINE,
                          capture_output=True, text=True, timeout=30, **kw)


def _depot_pret():
    """(pret, motif). Un dépôt sale rendrait toute annulation ambiguë."""
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return False, "le dossier JARVIS n'est pas un dépôt git"
    sales = [l for l in _git("status", "--porcelain").stdout.splitlines()
             if l.strip() and ".claude-flow" not in l]
    if sales:
        return False, ("%d fichier(s) non commité(s) : %s"
                       % (len(sales), ", ".join(s[3:] for s in sales[:5])))
    return True, ""


def envoyer(proposition, agent=AGENT_DEFAUT, confirme=False, timeout=1800):
    """
    Transmet le prompt à un agent de code, sur une branche dédiée.

    Refuse tant que confirme n'est pas True : c'est ici que l'humain entre
    dans la boucle, et ce défaut ne doit jamais devenir True.
    """
    if not confirme:
        return {"ok": False, "confirmation_requise": True,
                "message": ("Rien n'a été envoyé. Relis le prompt, puis rappelle "
                            "avec confirme=True. L'agent modifiera de vrais "
                            "fichiers sur la branche '%s'." % proposition["branche"]),
                "agent": agent, "prompt": proposition["prompt"]}

    if agent not in AGENTS:
        return {"ok": False, "erreur": "agent inconnu : %s (connus : %s)"
                                       % (agent, ", ".join(AGENTS))}

    pret, motif = _depot_pret()
    if not pret:
        return {"ok": False, "erreur":
                "dépôt non prêt — %s. Commiter ou remiser d'abord : une "
                "modification d'agent doit pouvoir s'annuler proprement." % motif}

    branche = proposition["branche"]
    depart = _git("branch", "--show-current").stdout.strip()
    r = _git("checkout", "-b", branche)
    if r.returncode != 0 and "already exists" not in (r.stderr or ""):
        return {"ok": False, "erreur": "création de branche impossible : %s" % r.stderr.strip()}
    if r.returncode != 0:
        _git("checkout", branche)

    commande = AGENTS[agent] + [proposition["prompt"]]
    try:
        p = subprocess.run(commande, cwd=RACINE, capture_output=True,
                           text=True, timeout=timeout)
        sortie, erreur, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        sortie, erreur, code = "", "délai dépassé (%ds)" % timeout, -1
    except FileNotFoundError:
        sortie, erreur, code = "", "commande '%s' introuvable" % commande[0], -1

    modifies = [l[3:] for l in _git("status", "--porcelain").stdout.splitlines()
                if l.strip() and ".claude-flow" not in l]
    return {
        "ok": code == 0,
        "agent": agent, "branche": branche, "branche_depart": depart,
        "code_retour": code,
        "fichiers_modifies": modifies,
        "sortie": (sortie or "")[-4000:],
        "erreur": (erreur or "")[-1500:],
        "annuler": "git checkout %s && git branch -D %s" % (depart or "main", branche),
    }


# ── Ligne de commande ────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    props = proposer()

    if "--prompt" in sys.argv:
        i = int(sys.argv[sys.argv.index("--prompt") + 1]) - 1
        if not 0 <= i < len(props):
            print("index hors limites (1..%d)" % len(props)); sys.exit(1)
        print(props[i]["prompt"])
        sys.exit(0)

    if "--json" in sys.argv:
        print(json.dumps(props, ensure_ascii=False, indent=2)); sys.exit(0)

    print()
    print("=" * 74)
    print("JARVIS PROPOSE %d AMÉLIORATION(S)" % len(props))
    print("=" * 74)
    for i, p in enumerate(props, 1):
        print("  %d. [%s] %s" % (i, p["gravite"].upper()[:4], p["titre"]))
        print("     constat  : %s" % p["preuve"][:150])
        if p["fichier"]:
            print("     fichier  : %s" % p["fichier"])
        print("     branche  : %s" % p["branche"])
        print()
    pret, motif = _depot_pret()
    print("  dépôt : %s" % ("prêt" if pret else "PAS PRÊT — " + motif))
    print()
    print("  Voir un prompt   : auto_amelioration.py --prompt N")
    print("  Rien n'est envoyé sans confirme=True.")
    print("=" * 74)
