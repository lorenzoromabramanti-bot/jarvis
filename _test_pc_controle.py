# -*- coding: utf-8 -*-
"""
Verifie tools/pc_controle.interpreter() : lecture seule, rien n'est execute.

Deux moities, aussi importantes l'une que l'autre :
- chaque demande PC / navigateur trouve la bonne action ;
- tout le reste renvoie None. pc_controle passe AVANT les commandes
  locales : un motif trop large volerait les volets, la musique, la meteo...

    venv\\Scripts\\python.exe _test_pc_controle.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.pc_controle import interpreter, trouver_dans_menu_demarrer  # noqa: E402

ATTENDU = {
    # onglets
    "ouvre un nouvel onglet": "onglet_nouveau", "nouvel onglet": "onglet_nouveau",
    "ouvre un nouvel onglet sur youtube": "onglet_nouveau", "ferme l'onglet": "onglet_fermer",
    "ferme cet onglet": "onglet_fermer", "onglet suivant": "onglet_suivant", "change d'onglet": "onglet_suivant",
    "onglet précédent": "onglet_precedent", "rouvre l'onglet que j'ai fermé": "onglet_rouvrir",
    # page
    "recharge la page": "page_recharger", "actualise": "page_recharger", "rafraîchis la page": "page_recharger",
    "reviens en arrière sur la page": "page_retour", "page précédente": "page_retour",
    "retourne à la page d'avant": "page_retour", "page suivante": "page_avant",
    "fais défiler la page vers le bas": "defiler", "descends en bas de la page": "defiler",
    "remonte en haut de la page": "defiler", "scroll vers le bas": "defiler",
    # video / zoom
    "mets la vidéo en plein écran": "plein_ecran", "mets youtube en plein écran": "plein_ecran",
    "plein écran": "plein_ecran", "quitte le plein écran": "plein_ecran",
    "pause la vidéo": "video_pause", "mets la vidéo en pause": "video_pause", "reprends la vidéo": "video_pause",
    "zoome": "zoom", "dézoome": "zoom",
    # recherches
    "cherche recette de crêpes sur google": "recherche", "cherche sur google meteo marseille": "recherche",
    "google comment faire des pates": "recherche", "cherche une ps5 sur amazon": "recherche",
    "recherche tour eiffel sur wikipedia": "recherche",
    # sites
    "ouvre youtube": "site", "va sur amazon": "site", "ouvre gmail": "site", "ouvre netflix": "site",
    "ouvre le site de netflix": "site", "va sur leboncoin.fr": "site", "ouvre chatgpt": "site",
    "ouvre home assistant": "site", "mets youtube": "site", "ouvre google maps": "site",
    "ouvre l'oeil de dieu": "site", "ouvre l'œil de dieu": "site", "ouvre god's eye": "site",
    "affiche la carte osint": "site", "lance shadowbroker": "site",
    # fenetres
    "montre le bureau": "bureau", "réduis toutes les fenêtres": "bureau", "affiche le bureau": "bureau",
    "change de fenêtre": "fenetre_suivante", "ferme cette fenêtre": "fenetre_fermer",
    "ferme la fenêtre": "fenetre_fermer", "agrandis la fenêtre": "fenetre_agrandir",
    "mets la fenêtre en plein écran": "fenetre_agrandir", "réduis cette fenêtre": "fenetre_reduire",
    # systeme
    "verrouille le pc": "verrouiller", "verrouille l'ordi": "verrouiller", "verrouille ma session": "verrouiller",
    "annule l'extinction": "annuler_extinction", "annule l'arrêt": "annuler_extinction",
    "quelles applis sont ouvertes": "apps_ouvertes", "quels programmes sont ouverts": "apps_ouvertes",
    "qu'est ce qui consomme le plus sur mon pc": "gros_consommateurs",
    "pourquoi mon pc rame": "gros_consommateurs", "qu'est-ce qui bouffe toute la ram": "gros_consommateurs",
    "ma carte graphique chauffe ?": "gpu", "température du gpu": "gpu", "c'est quoi ma carte graphique": "gpu",
    "qu'est ce que j'ai copié": "presse_papier_lire", "lis le presse-papier": "presse_papier_lire",
    # discord
    "rejoins le vocal discord": "discord_rejoindre", "rejoin le salon vocal": "discord_rejoindre",
    "Rejoin l’appelle": "discord_rejoindre", "viens en vocal": "discord_rejoindre",
    "quitte le vocal": "discord_quitter", "déconnecte-toi du vocal": "discord_quitter",
    # clavier
    "tape bonjour tout le monde": "taper", "écris au clavier Salut Alex": "taper", "tape entrée": "touche",
    "appuie sur échap": "touche", "appuie sur la touche espace": "touche", "valide": "touche",
    # politesse / majuscules / ponctuation
    "JARVIS, ouvre youtube stp !": "site", "RECHARGE LA PAGE": "page_recharger",
}

RIEN = [
    # maison / Home Assistant
    "ferme les volets du salon", "ouvre le volet de ma chambre", "descends les volets", "monte le store",
    "allume la lumière", "quelles fenêtres sont ouvertes", "ferme la fenêtre du salon",
    "qu'est-ce qui consomme le plus d'électricité", "verrouille la porte d'entrée", "monte le chauffage",
    # musique
    "mets en pause", "mets de la musique", "chanson suivante", "reviens en arrière", "monte le son",
    "baisse le volume", "mets du daft punk", "lance ma playlist", "joue la dernière de ninho",
    # applis (restent a app_launcher / commandes locales)
    "ouvre discord", "ouvre spotify", "lance steam", "ouvre vs code", "ouvre la calculatrice",
    "ouvre le dossier téléchargements", "ouvre mes documents", "ferme spotify", "ferme chrome",
    # camera, vision
    "mets la caméra en plein écran", "regarde mon écran", "fais une capture d'écran",
    # questions / agenda / meteo / divers
    "il va pleuvoir demain", "j'ai quoi comme cours demain", "quelle est mon adresse ip",
    "combien de ram j'utilise", "c'est quoi la capitale de l'australie", "raconte moi une blague",
    "rappelle moi d'acheter du pain", "recharge la batterie de la manette", "actualise la météo",
    "traduis le presse-papiers", "corrige les fautes du presse-papiers", "copie ça dans le presse papier",
    "ouvre le site de la mairie", "mets le pc en veille", "éteins le pc dans 10 minutes",
    "cherche un billet d'avion paris rome", "yo", "ça va",
]

ok = ko = 0
for phrase, attendu in ATTENDU.items():
    r = interpreter(phrase)
    obtenu = r[0] if r else None
    if obtenu == attendu:
        ok += 1
    else:
        ko += 1
        print("  X   %-45s attendu %-20s obtenu %s" % (phrase, attendu, r))
for phrase in RIEN:
    r = interpreter(phrase)
    if r is None:
        ok += 1
    else:
        ko += 1
        print("  X   %-45s aurait du rester None, obtenu %s" % (phrase, r))

# details d'arguments
assert interpreter("cherche recette de crêpes sur google") == ("recherche", ("google", "recette de crepes"))
assert interpreter("cherche sur google meteo marseille") == ("recherche", ("google", "meteo marseille"))
assert interpreter("va sur leboncoin.fr") == ("site", ("https://leboncoin.fr", "leboncoin.fr"))
assert interpreter("ouvre un nouvel onglet sur youtube") == ("onglet_nouveau", "https://www.youtube.com")
assert interpreter("JARVIS, ouvre l'Œil de Dieu stp")[1][0].startswith("http://localhost:4173")
assert interpreter("montre-moi god's eye view")[1][0].startswith("http://localhost:4173")
assert interpreter("quitte le plein écran") == ("plein_ecran", "quitter")
assert interpreter("écris au clavier Salut Alex stp") == ("taper", "Salut Alex")
assert interpreter("JARVIS, tape Rendez-vous à 18h") == ("taper", "Rendez-vous à 18h")
assert interpreter("écris une fonction python qui trie une liste") is None
assert interpreter("remonte en haut de la page")[1] == "debut"
assert interpreter("fais défiler la page vers le bas")[1] == "bas"

# a distance (Discord, telephone), frappe et presse-papiers attendent un « oui »
from tools.pc_controle import A_CONFIRMER_A_DISTANCE  # noqa: E402
for phrase in ("tape rm -rf tout", "valide", "lis le presse-papier", "appuie sur entrée"):
    assert interpreter(phrase)[0] in A_CONFIRMER_A_DISTANCE, phrase
assert interpreter("ouvre youtube")[0] not in A_CONFIRMER_A_DISTANCE

# menu Demarrer : lecture seule (rien n'est lance)
assert trouver_dans_menu_demarrer("zzz application qui n'existe pas") is None
assert trouver_dans_menu_demarrer("x") is None

print("\n  %d / %d justes" % (ok, ok + ko))
if ko:
    sys.exit(1)
print("  pc_controle : chaque demande a sa place, rien de vole aux autres modules.")
