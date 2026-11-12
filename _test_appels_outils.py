# -*- coding: utf-8 -*-
"""Faux appels d'outil du modèle (pseudo-XML) : retirés du texte dit et affiché, jamais exécutés.
Les deux premiers exemples sont ceux relevés dans jarvis_conversations.json (07/11 et 12/11/2026)."""
import appels_outils as a

ECHECS = []


def verifier(nom, ok):
    print(("  OK  " if ok else "  ÉCHEC  ") + nom)
    if not ok:
        ECHECS.append(nom)


REEL_DOUBLE = ("\n\n\n<dots_function_call>\n<dots_function_call>\ninvoke name=\"voir_ecran\">\n"
               "<parameter name=\"instruction\">regarde l'écran et scroller vers la droite\n</parameter>\n</invoke>\n"
               "</dots_function_call>")
REEL_SIMPLE = ("<dots_function_call>\ninvoke name=\"voir_ecran\">\n<parameter name=\"instruction\">regarde l'écran pour "
               "voir quelle musique est en train de jouer (sur Spotify, Deezer, YouTube)\n</parameter>\n</invoke>\n"
               "</dots_function_call>")
COMPLET = ("<function_calls>\n<invoke name=\"ha_lumiere\">\n<parameter name=\"piece\">salon</parameter>\n"
           "</invoke>\n</function_calls>")

for nom, texte in (("réel, ouverture doublée", REEL_DOUBLE), ("réel, simple", REEL_SIMPLE), ("balises complètes", COMPLET)):
    reste, noms = a.extraire(texte)
    verifier(f"{nom} : plus rien à dire, outil repéré", reste == "" and len(noms) == 1)
    verifier(f"{nom} : réponse « seulement un faux appel »", a.est_seul(texte))

verifier("nom de l'outil lu", a.extraire(REEL_SIMPLE)[1] == ["voir_ecran"] and a.extraire(COMPLET)[1] == ["ha_lumiere"])
verifier("texte avant gardé", a.sans_appels("Un instant. " + REEL_SIMPLE) == "Un instant.")
verifier("texte après gardé", a.sans_appels(REEL_SIMPLE + " Voilà.") == "Voilà.")
verifier("texte avant et après gardés", a.sans_appels("Un instant. " + REEL_SIMPLE + " Voilà.") == "Un instant. Voilà.")
verifier("faux appel + texte : pas « seul »", not a.est_seul("Un instant. " + REEL_SIMPLE))
verifier("faux appel jamais terminé : retiré jusqu'au bout",
         a.sans_appels("<dots_function_call>\ninvoke name=\"voir_ecran\">\n<parameter name=\"instruction\">regarde l'écr") == "")

normal = "Il fait 9 degrés et le ciel est couvert. C'est tout."
action = 'Je m\'en occupe. {"action": "ha_lumiere", "etat": "on"}'
verifier("phrase normale inchangée", a.extraire(normal) == (normal, []) and not a.est_seul(normal))
verifier("bloc JSON d'action inchangé (main2 le traite)", a.sans_appels(action) == action)
verifier("texte vide ou absent", a.extraire("") == ("", []) and a.extraire(None) == (None, []) and not a.est_seul("   "))
verifier("avant_appel : début du texte seulement", a.avant_appel("Salut. " + REEL_SIMPLE) == "Salut. ")
verifier("avant_appel : rien avant un faux appel", a.avant_appel(REEL_SIMPLE) == "")
verifier("avant_appel : phrase normale entière", a.avant_appel(normal) == normal)
verifier("la note de reprise interdit de regarder l'écran", "voir_ecran" in a.NOTE_REPRISE and "jamais" in a.NOTE_REPRISE)

# Mémoire de conversation : au rechargement, un ancien faux appel d'outil ne sert plus d'exemple au modèle.
import json
import os
import tempfile

import memory_manager as mm

with tempfile.TemporaryDirectory() as dossier:
    mm.HISTORIQUE_CONV_FILE = os.path.join(dossier, "conversations.json")
    with open(mm.HISTORIQUE_CONV_FILE, "w", encoding="utf-8") as f:
        json.dump([{"date": "07/11/2026", "heure": "21:32", "user": "regarde l'écran", "model": REEL_DOUBLE},
                   {"date": "07/11/2026", "heure": "21:40", "user": "salut", "model": "Bonjour."}], f)
    historique = mm._charger_historique_recent()
verifier("historique rechargé : l'ancien faux appel est écarté, la vraie réponse reste",
         len(historique) == 2 and historique[1].parts[0].text == "Bonjour.")

print("\nFaux appels d'outil : " + ("conforme." if not ECHECS else f"{len(ECHECS)} échec(s)."))
raise SystemExit(1 if ECHECS else 0)
