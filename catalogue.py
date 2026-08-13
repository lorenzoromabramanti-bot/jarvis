# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Catalogue des capacités
=====================================
Ce que JARVIS sait faire, ce que chaque chose exige, et ce qui est activé.

Source unique pour les deux modes d'installation : ils affichent la même
liste, ils la présentent différemment.

POURQUOI CE N'EST PAS UNE LISTE FIGÉE
Une liste écrite à la main diverge dès la première fonction ajoutée, et
personne ne s'en aperçoit — la nouvelle capacité n'apparaît simplement jamais
dans l'installeur. Ici chaque capacité déclare les points d'entrée qu'elle
couvre, et `verifier_coherence()` compare cette déclaration au CODE RÉEL :
142 points d'entrée existent aujourd'hui dans main2.py, et le test échoue si
l'un d'eux n'appartient à personne. Ajouter une action sans l'inscrire au
catalogue casse la suite de tests.

CE QUE « DISPONIBLE » VEUT DIRE
Une capacité peut être connue et indisponible : il manque une clé, un module
Python, ou le service ne répond pas. `catalogue()` le dit et donne la raison,
plutôt que de proposer à quelqu'un d'activer une chose qui ne marchera pas.

    venv\\Scripts\\python.exe catalogue.py
"""

import io
import json
import os
import re
import sys

import config

RACINE = config.RACINE

# ── Les capacités ────────────────────────────────────────────────────────
#
#   titre / description : ce que voit l'utilisateur. Sans jargon : le mode
#       simple les affiche tels quels.
#   reglages   : variables de .env exigées (voir config.REGLAGES)
#   capacites  : modules Python ou services exigés (voir config.capacites())
#   actions    : points d'entrée couverts — sert au contrôle de cohérence
#   niveau     : autorisation la plus élevée que la capacité peut demander,
#                sur l'échelle 1-10 de la passerelle
#   avance     : n'apparaît pas du tout en mode simple
#   defaut     : cochée d'office à l'installation

CAPACITES = {
    "essentiel": dict(
        titre="Conversation et réglages",
        description="Parler à JARVIS, le configurer, l'entendre répondre.",
        reglages=["GEMINI_API_KEY", "JARVIS_ACCESS_TOKEN"],
        capacites=[], niveau=3, avance=False, defaut=True, obligatoire=True,
        actions=["user_input", "get_settings", "update_settings", "stop_audio",
                 "toggle_mic", "toggle_fullscreen", "location_update",
                 "mobile_command", "set_primary_model", "get_available_models",
                 "get_auto_diagnostic", "get_propositions", "envoyer_proposition",
                 "toggle_startup", "clear_cache", "dictee", "allow",
                 "mode_iron_man", "memoriser", "oublier", "lister_memoire",
                 "install_nemotron_deps", "uninstall_nemotron_deps",
                 "toggle_nemotron_asr", "av_speak"],
    ),
    "courrier": dict(
        titre="Courrier",
        description="Relève vos boîtes, trie ce qui compte, et prépare des "
                    "réponses que vous relisez avant envoi.",
        reglages=[], capacites=[], niveau=9, avance=False, defaut=False,
        comptes="Une adresse et un mot de passe d'application par boîte.",
        actions=["read_emails", "get_courrier", "lire_mail",
                 "proposer_reponse_mail", "envoyer_mail", "etat_envoi_mail"],
    ),
    "domotique": dict(
        titre="Maison connectée",
        description="Lumières, prises, chauffage, alarme et capteurs, "
                    "via Home Assistant.",
        reglages=["HA_URL", "HA_TOKEN"], capacites=[], niveau=5,
        avance=False, defaut=False,
        actions=["ha_alarme", "ha_anniversaires", "ha_aspirateur", "ha_batterie",
                 "ha_consommation", "ha_energie", "ha_humidite", "ha_lumiere",
                 "ha_oeufs", "ha_prise", "ha_scene", "ha_simulation",
                 "ha_temperature", "ha_thermostat", "ha_tiktok", "ha_verrou",
                 "alerte_meteo", "meteo", "get_meteo"],
    ),
    "media": dict(
        titre="Musique et vidéo",
        description="Contrôler Spotify, Deezer et YouTube à la voix.",
        reglages=[], capacites=["automation_clavier"], niveau=3,
        avance=False, defaut=False,
        actions=["spotify_lecture_pause", "spotify_ouvrir", "spotify_precedent",
                 "spotify_rechercher", "spotify_stop", "spotify_suivant",
                 "spotify_volume", "deezer_lecture_pause", "deezer_ouvrir",
                 "deezer_precedent", "deezer_rechercher", "deezer_stop",
                 "deezer_suivant", "deezer_volume"],
    ),
    "fichiers": dict(
        titre="Fichiers et dossiers",
        description="Chercher, ranger, renommer et ouvrir vos fichiers.",
        reglages=[], capacites=[], niveau=7, avance=False, defaut=False,
        actions=["chercher_fichier", "creer_dossier", "lister_dossier",
                 "deplacer_fichier", "renommer_fichier", "ouvrir_dossier",
                 "trier_complet", "trier_par_date", "trier_par_type",
                 "open_file_location", "delete"],
    ),
    "maintenance": dict(
        titre="Entretien de l'ordinateur",
        description="Mises à jour des logiciels, désinstallation, "
                    "nettoyage des restes.",
        reglages=[], capacites=["winget", "registre_windows"], niveau=8,
        avance=False, defaut=False,
        actions=["get_winget_upgrades", "run_winget_upgrade",
                 "get_installed_programs", "uninstall_program",
                 "clean_leftovers", "clean"],
    ),
    "securite": dict(
        titre="Analyse antivirus",
        description="Examiner les fichiers et les programmes qui démarrent "
                    "avec Windows.",
        reglages=[], capacites=["registre_windows"], niveau=8,
        avance=False, defaut=False,
        actions=["antivirus_scan", "av_scan_start", "av_scan_cancel",
                 "av_threat_action", "quarantine"],
    ),
    "vision": dict(
        titre="Voir l'écran et la webcam",
        description="JARVIS regarde votre écran ou votre caméra pour "
                    "répondre à ce qu'il y voit.",
        reglages=[], capacites=["capture_ecran"], niveau=6,
        avance=False, defaut=False,
        actions=["voir_ecran", "lance_camera", "screen_frame", "webcam_state",
                 "camera_capture_response", "vision_chercher_sur_site",
                 "vision_ecrire", "vision_navigateur", "recherche_images"],
    ),
    "navigateur": dict(
        titre="Navigation web",
        description="Ouvrir des pages, chercher, remplir des formulaires.",
        reglages=[], capacites=[], niveau=6, avance=False, defaut=False,
        actions=["open_browser", "close_browser", "dock_browser",
                 "undock_browser", "recherche_web", "restaurant_search"],
    ),
    "vpn": dict(
        titre="VPN",
        description="Se connecter à un réseau privé et changer de pays.",
        reglages=[], capacites=["powershell"], niveau=6,
        avance=False, defaut=False,
        actions=["vpn_connect", "vpn_disconnect", "vpn_get_countries",
                 "vpn_get_status", "vpn_cancel"],
    ),
    "notes": dict(
        titre="Notes",
        description="Créer et retrouver des notes dans un carnet Obsidian.",
        reglages=[], capacites=[], niveau=4, avance=False, defaut=False,
        actions=["obsidian_creer_note", "obsidian_lire_note", "obsidian_lister",
                 "obsidian_rechercher", "get_obsidian_notes",
                 "read_obsidian_note", "save_obsidian_note",
                 "delete_obsidian_note", "get_shopping_list",
                 "update_shopping_list"],
    ),
    "quotidien": dict(
        titre="Vie quotidienne",
        description="Météo, résultats sportifs, recettes, agenda.",
        reglages=[], capacites=[], niveau=3, avance=False, defaut=True,
        actions=["sport_classement", "sport_live", "sport_resultats",
                 "afficher_recette", "read_calendar", "create_doc",
                 "create_sheet", "write_doc", "whatsapp_appel"],
    ),
    "creation": dict(
        titre="Images et vidéos",
        description="Produire une image ou une courte vidéo à la demande.",
        reglages=[], capacites=[], niveau=5, avance=False, defaut=False,
        actions=["generer_image", "generer_video", "generate_image_selected"],
    ),
    "memoire_partagee": dict(
        titre="Mémoire partagée entre agents",
        description="Un vault que JARVIS et les agents de code (Claude Code, "
                    "OpenCode) lisent et écrivent en commun.",
        reglages=[], capacites=[], niveau=4, avance=False, defaut=False,
        actions=["get_memoire_resume", "memoire_ecrire", "memoire_lire",
                 "memoire_lister", "memoire_chercher", "memoire_supprimer"],
    ),
    # ── Réservé au mode avancé ───────────────────────────────────────────
    "agents": dict(
        titre="Suivi des agents de développement",
        description="Repère Claude Code, Codex et OpenCode sur la machine, "
                    "et suit leur activité.",
        reglages=[], capacites=[], niveau=4, avance=True, defaut=False,
        actions=["get_agents", "get_agent_models", "set_agent_models",
                 "detect_apps"],
    ),
    "jarvis_os": dict(
        titre="JARVIS OS",
        description="Environnement d'exécution isolé pour les applications.",
        reglages=[], capacites=[], niveau=8, avance=True, defaut=False,
        actions=["jarvis_os_install", "jarvis_os_install_app",
                 "jarvis_os_open_shared", "jarvis_os_pick_folder",
                 "jarvis_os_restart", "jarvis_os_start", "jarvis_os_stop",
                 "jarvis_os_uninstall", "check_jarvis_os_status"],
    ),
    "shadowbroker": dict(
        titre="Shadow Broker",
        description="Passerelle expérimentale. Peu utilisée.",
        reglages=[], capacites=[], niveau=7, avance=True, defaut=False,
        actions=["open_shadowbroker"],
    ),
}

FICHIER_CHOIX = "capacites.json"


# ── Ce que le code contient RÉELLEMENT ───────────────────────────────────

def actions_du_code():
    """Tous les points d'entrée présents dans main2.py, lus dans le fichier."""
    source = io.open(os.path.join(RACINE, "main2.py"), encoding="utf-8").read()
    actions = set(re.findall(r'action == "([a-z_0-9]+)"', source))
    handlers = set(re.findall(r'data\.get\("type"\) == "([a-z_0-9]+)"', source))
    return actions | handlers


def verifier_coherence():
    """
    Compare le catalogue au code. Renvoie (orphelines, fantomes).

    orphelines : présentes dans main2.py, réclamées par aucune capacité.
                 C'est le cas qui compte : une fonction ajoutée sans être
                 inscrite ici n'apparaîtrait jamais à l'installation.
    fantomes   : déclarées ici, absentes du code.
    """
    reelles = actions_du_code()
    declarees = set()
    for c in CAPACITES.values():
        declarees.update(c["actions"])
    return sorted(reelles - declarees), sorted(declarees - reelles)


# ── Disponibilité ────────────────────────────────────────────────────────

def _manques(capacite):
    """Ce qui empêche cette capacité de fonctionner ici. Vide = elle marche."""
    manques = []
    presents = {v for variables, p, _, _, _ in config.configuration()
                if p for v in variables}
    for reglage in capacite["reglages"]:
        if reglage not in presents:
            manques.append("le réglage %s n'est pas renseigné" % reglage)
    dispo = config.capacites()
    for besoin in capacite["capacites"]:
        if not dispo.get(besoin):
            manques.append("%s n'est pas disponible sur ce système" % besoin)
    return manques


def catalogue(mode="avance"):
    """
    La liste à présenter. `mode` vaut "simple" ou "avance".

    En mode simple, les capacités marquées `avance` sont ABSENTES — pas
    grisées, pas désactivées : absentes. Le brief est explicite là-dessus.
    """
    sortie = []
    for cle, c in CAPACITES.items():
        if mode == "simple" and c.get("avance"):
            continue
        manques = _manques(c)
        sortie.append({
            "cle": cle,
            "titre": c["titre"],
            "description": c["description"],
            "disponible": not manques,
            "manques": manques,
            "niveau": c["niveau"],
            "defaut": c.get("defaut", False),
            "obligatoire": c.get("obligatoire", False),
            "comptes": c.get("comptes", ""),
            "reglages": c["reglages"],
        })
    return sortie


# ── Ce qui est activé ────────────────────────────────────────────────────

def _chemin_choix():
    return config.chemin_donnees(FICHIER_CHOIX, creer_dossier=True)


def activees():
    """Les clés activées. Au premier lancement : celles marquées par défaut."""
    chemin = _chemin_choix()
    try:
        with io.open(chemin, encoding="utf-8") as f:
            donnees = json.load(f)
        return set(donnees.get("activees", []))
    except Exception:
        return {c for c, v in CAPACITES.items() if v.get("defaut")}


def definir_activees(cles, mode="avance"):
    """
    Enregistre la sélection. Renvoie (retenues, refusees).

    Les capacités obligatoires sont ajoutées d'office : les retirer laisserait
    JARVIS incapable de répondre. Les capacités avancées sont refusées si le
    mode est simple — sinon l'interdiction ne tiendrait qu'à l'affichage.
    """
    retenues, refusees = set(), []
    for cle in cles:
        c = CAPACITES.get(cle)
        if c is None:
            refusees.append("%s : capacité inconnue" % cle)
            continue
        if mode == "simple" and c.get("avance"):
            refusees.append("%s : réservée au mode avancé" % cle)
            continue
        retenues.add(cle)
    retenues |= {c for c, v in CAPACITES.items() if v.get("obligatoire")}

    chemin = _chemin_choix()
    tmp = str(chemin) + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps({"mode": mode, "activees": sorted(retenues)},
                   ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)
    return sorted(retenues), refusees


def mode_installe():
    """"simple" ou "avance", tel qu'enregistré. "avance" si rien n'est écrit."""
    try:
        with io.open(_chemin_choix(), encoding="utf-8") as f:
            return json.load(f).get("mode", "avance")
    except Exception:
        return "avance"


def un_choix_a_ete_fait():
    """
    L'utilisateur a-t-il déjà choisi ses capacités ?

    Tant que non, RIEN n'est bloqué. Une installation antérieure au catalogue
    n'a pas de fichier de choix : appliquer les valeurs par défaut lui
    couperait d'un coup la domotique, le courrier et le reste, sans qu'elle
    ait rien demandé. Le filtrage ne commence qu'après un choix explicite.
    """
    return os.path.exists(str(_chemin_choix()))


def action_autorisee(action):
    """
    L'action fait-elle partie d'une capacité activée ?

    Garde d'exécution : décocher une capacité doit la rendre INOPÉRANTE, pas
    seulement la cacher de l'interface. Sans ce contrôle, l'installeur ne
    ferait que masquer des boutons — le modèle, lui, continuerait à émettre
    les actions correspondantes.
    """
    if not un_choix_a_ete_fait():
        return True
    permises = activees()
    for cle, c in CAPACITES.items():
        if action in c["actions"]:
            return cle in permises
    return True     # action non cataloguée : on ne bloque pas sur un oubli


def refus(action):
    """Le message à donner quand une action est bloquée. Nomme la capacité."""
    for cle, c in CAPACITES.items():
        if action in c["actions"]:
            return ("« %s » n'est pas activé sur cette installation. "
                    "Vous pouvez l'activer dans les réglages." % c["titre"])
    return "Cette fonction n'est pas activée sur cette installation."


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    orphelines, fantomes = verifier_coherence()
    print()
    print("=" * 78)
    print("CATALOGUE DES CAPACITÉS")
    print("=" * 78)
    print("  %d capacités, %d points d'entrée dans le code"
          % (len(CAPACITES), len(actions_du_code())))
    print("  mode installé : %s" % mode_installe())
    print()
    for c in catalogue():
        marque = "x" if c["cle"] in activees() else " "
        etat = "" if c["disponible"] else "   <-- %s" % c["manques"][0]
        avance = " [avancé]" if CAPACITES[c["cle"]].get("avance") else ""
        print("  [%s] %-34s niveau %-2d%s%s"
              % (marque, c["titre"] + avance, c["niveau"], etat, ""))
    print()
    if orphelines:
        print("  %d ACTION(S) ORPHELINE(S) — présentes dans le code, "
              "réclamées par personne :" % len(orphelines))
        for a in orphelines:
            print("    %s" % a)
    else:
        print("  Toutes les actions du code appartiennent à une capacité.")
    if fantomes:
        print("  %d déclarée(s) ici mais absente(s) du code : %s"
              % (len(fantomes), ", ".join(fantomes)))
    print("=" * 78)
