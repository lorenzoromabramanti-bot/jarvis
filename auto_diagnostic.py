# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Auto-diagnostic
=============================
JARVIS rend compte de son PROPRE état, pas de celui de la machine.

Le HUD surveille déjà le processeur, la mémoire et l'uptime. Personne ne
surveille JARVIS : un modèle écarté sans message, un outil qui lève à chaque
appel, un module optionnel absent — tout ça ne se voit aujourd'hui que dans
une console que personne ne lit.

Chaque constat renvoyé ici s'appuie sur une observation, jamais sur une
supposition. Un constat porte :
    cle        identifiant stable (sert à ne pas reproposer deux fois)
    gravite    'critique' | 'attention' | 'info'
    titre      une phrase
    preuve     CE QUI A ÉTÉ OBSERVÉ, avec les valeurs réelles
    fichier    où ça se passe, quand c'est localisable

Utilisable sans JARVIS lancé :
    venv\\Scripts\\python.exe auto_diagnostic.py
"""

import io
import json
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.abspath(__file__))

# Outils ayant levé pendant l'exécution. Rempli par main2.py via l'observateur
# du socle tools/ ; vide quand on tourne hors JARVIS.
ECHECS_EXECUTION = {}


def noter_echec_outil(nom, detail):
    """Appelé par l'observateur de tools/ à chaque outil qui lève."""
    e = ECHECS_EXECUTION.setdefault(nom, {"nombre": 0, "dernier": ""})
    e["nombre"] += 1
    e["dernier"] = str(detail)[:200]


def _constat(cle, gravite, titre, preuve, fichier=""):
    return {"cle": cle, "gravite": gravite, "titre": titre,
            "preuve": preuve, "fichier": fichier}


# ── Contrôles ────────────────────────────────────────────────────────────

def _modeles_ecartes():
    """
    Modèles choisis dans la config mais silencieusement remplacés.

    agent_model_manager.load_chosen_models() ne garde un modèle que s'il
    figure dans AVAILABLE_MODELS, une liste codée en dur. Sinon il retombe
    sur le défaut SANS RIEN DIRE : on croit parler à un modèle, on parle à
    un autre.
    """
    constats = []
    try:
        import agent_model_manager as amm
    except Exception as e:
        return [_constat("modeles-module", "attention",
                         "agent_model_manager illisible", repr(e))]

    chemin = getattr(amm, "CONFIG_PATH", "")
    if not chemin or not os.path.exists(chemin):
        return constats
    try:
        demandes = json.load(io.open(chemin, encoding="utf-8")).get("chosen_models", {})
    except Exception as e:
        return [_constat("modeles-config", "attention",
                         "config des modèles illisible", repr(e), chemin)]

    effectifs = amm.load_chosen_models()
    dispo = getattr(amm, "AVAILABLE_MODELS", {})
    for agent, voulu in demandes.items():
        obtenu = effectifs.get(agent)
        if obtenu != voulu:
            constats.append(_constat(
                "modele-ecarte-%s" % agent, "critique",
                "Le modèle choisi pour '%s' est ignoré en silence" % agent,
                "config demande %r, JARVIS utilise %r. Motif : %r ne figure pas "
                "dans AVAILABLE_MODELS[%r] (%d entrées codées en dur). Aucun "
                "message n'est émis."
                % (voulu, obtenu, voulu, agent, len(dispo.get(agent, []))),
                "agent_model_manager.py:81"))
    return constats


def _outils():
    """Outils absents du registre, et outils qui lèvent à l'exécution."""
    constats = []
    try:
        import tools
    except Exception as e:
        return [_constat("tools-socle", "critique",
                         "socle tools/ indisponible", repr(e), "tools/__init__.py")]

    if not tools.lister_outils():          # pas encore chargé (hors JARVIS)
        _, echecs = tools.charger_outils()
    else:
        echecs = []
    for module, erreur in echecs:
        constats.append(_constat(
            "outil-import-%s" % module, "critique",
            "L'outil '%s' ne se charge pas" % module,
            "import refusé : %s. L'outil est absent du registre, ses "
            "déclencheurs ne répondront jamais." % erreur,
            "tools/%s.py" % module))

    for nom, e in ECHECS_EXECUTION.items():
        constats.append(_constat(
            "outil-execution-%s" % nom, "critique",
            "L'outil '%s' lève à l'exécution" % nom,
            "%d échec(s) depuis le démarrage. Dernière erreur : %s. "
            "Le socle le saute et passe au suivant — l'utilisateur ne voit "
            "qu'une réponse générique." % (e["nombre"], e["dernier"]),
            "tools/%s.py" % nom))
    return constats


def _modules_optionnels():
    """Modules que JARVIS sait utiliser mais qui ne s'importent pas."""
    attendus = [
        ("email_hub", "messagerie unifiée"),
        ("jarvis_web", "recherche web"),
        ("jarvis_outils", "boîte à outils locale"),
        ("jarvis_extras", "extras"),
        ("vision_module", "vision écran et webcam"),
        ("memory_manager", "mémoire persistante"),
        ("obsidian_helper", "notes Obsidian"),
        ("vpn", "VPN"),
        ("antivirus_scanner", "antivirus"),
        ("webview", "fenêtre native (pywebview)"),
    ]
    constats = []
    for module, role in attendus:
        try:
            __import__(module)
        except Exception as e:
            constats.append(_constat(
                "module-%s" % module, "attention",
                "Module '%s' indisponible (%s)" % (module, role),
                "import échoué : %r. La fonctionnalité est désactivée en "
                "silence, JARVIS démarre quand même." % (e,),
                "%s.py" % module))
    return constats


def _depot_git():
    """État du dépôt — préalable à toute modification par un agent."""
    def git(*args):
        return subprocess.run(["git"] + list(args), cwd=RACINE,
                              capture_output=True, text=True, timeout=20)
    try:
        if git("rev-parse", "--is-inside-work-tree").returncode != 0:
            return [_constat("git-absent", "critique",
                             "Le dossier JARVIS n'est pas un dépôt git",
                             "Aucun moyen d'annuler une modification. "
                             "Indispensable avant de laisser un agent écrire.")]
        branche = git("branch", "--show-current").stdout.strip()
        sales = [l for l in git("status", "--porcelain").stdout.splitlines()
                 if l.strip() and ".claude-flow" not in l]
        if sales:
            return [_constat(
                "git-sale", "attention",
                "%d fichier(s) modifié(s) non commités" % len(sales),
                "branche '%s'. Exemples : %s. Un agent lancé maintenant "
                "mélangerait ses modifications aux tiennes."
                % (branche, ", ".join(s[3:] for s in sales[:4])))]
        return [_constat("git-propre", "info",
                         "Dépôt propre sur '%s'" % branche,
                         "Un agent peut travailler sans risque de mélange.")]
    except Exception as e:
        return [_constat("git-erreur", "attention", "état git indéterminable", repr(e))]


def _entites_domotiques():
    """
    Entités déclarées dans ha_config.py mais absentes de Home Assistant.

    Home Assistant répond 200 à un appel de service sur une entité
    inexistante : il n'a rien à faire, mais il ne proteste pas. JARVIS
    concluait donc au succès et annonçait « c'est fait » pour une lampe
    qui n'existe pas. C'est le mensonge le plus grave du lot, puisqu'il
    porte sur une action physique que l'utilisateur croit avoir déclenchée.
    """
    try:
        import ha_config
        absentes = ha_config.entites_declarees_absentes()
    except Exception as e:
        return [_constat("ha-injoignable", "attention",
                         "Impossible de vérifier les entités domotiques",
                         repr(e), "ha_config.py")]
    if not absentes:
        return []

    par_table = {}
    for table, cle, eid in absentes:
        par_table.setdefault(table, []).append("%s -> %s" % (cle, eid))
    detail = " | ".join("%s : %d absente(s) (%s)"
                        % (t, len(v), ", ".join(v[:2]) + ("..." if len(v) > 2 else ""))
                        for t, v in sorted(par_table.items()))
    return [_constat(
        "ha-entites-absentes", "critique",
        "%d entité(s) domotique(s) déclarée(s) n'existent pas" % len(absentes),
        "%s. Home Assistant répond 200 à un appel de service sur une entité "
        "inconnue : les commandes partaient sans effet et étaient annoncées "
        "comme réussies. Elles sont désormais refusées et signalées, mais les "
        "tables de ha_config.py restent à refaire sur la vraie installation."
        % detail,
        "ha_config.py")]


CONTROLES = (_modeles_ecartes, _outils, _modules_optionnels,
             _entites_domotiques, _depot_git)


def diagnostiquer():
    """Passe tous les contrôles. Renvoie la liste des constats."""
    constats = []
    for controle in CONTROLES:
        try:
            constats.extend(controle() or [])
        except Exception as e:
            constats.append(_constat(
                "controle-%s" % controle.__name__, "attention",
                "Le contrôle %s a échoué" % controle.__name__, repr(e)))
    ordre = {"critique": 0, "attention": 1, "info": 2}
    constats.sort(key=lambda c: ordre.get(c["gravite"], 3))
    return constats


def resume():
    """Compte par gravité — pour une pastille d'état dans le HUD."""
    c = diagnostiquer()
    return {g: sum(1 for x in c if x["gravite"] == g)
            for g in ("critique", "attention", "info")}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    constats = diagnostiquer()
    print()
    print("=" * 74)
    print("AUTO-DIAGNOSTIC JARVIS — %d constat(s)" % len(constats))
    print("=" * 74)
    for c in constats:
        print("  [%s] %s" % (c["gravite"].upper()[:4], c["titre"]))
        print("         %s" % c["preuve"])
        if c["fichier"]:
            print("         -> %s" % c["fichier"])
        print()
    print("=" * 74)
