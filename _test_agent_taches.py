"""Boucle d'agent des tâches en plusieurs étapes, sans réseau. Lancer : venv/Scripts/python.exe _test_agent_taches.py"""
from datetime import datetime

import agent_taches as at

MAINTENANT = datetime(2026, 10, 22, 18, 0)


class Modele:
    """Rejoue des réponses écrites d'avance et garde ce que la boucle lui a montré."""

    def __init__(self, reponses):
        self.reponses, self.vus = list(reponses), []

    def __call__(self, systeme, historique, declarations):
        self.vus.append([dict(m) for m in historique])
        return self.reponses.pop(0)


def appel(nom, **args):
    return {"texte": "", "appels": [{"id": nom, "nom": nom, "args": args}]}


faits = []
faux = {
    "pronote": lambda: '{"devoirs": [{"date": "2026-10-23", "matiere": "MATHS", "titre": "ex 12 p 45"}]}',
    "agenda": lambda jours=7: faits.append(("agenda", jours)) or "2026-10-23T08:00 → 2026-10-23T12:00 : cours",
    "creer_evenement": lambda titre, debut, fin, description="": faits.append(("creer", titre, debut, fin)) or "Événement créé.",
}

# 1. Plusieurs étapes : chaque outil voit le résultat du précédent, puis terminer.
m = Modele([appel("pronote"), appel("agenda", jours=2, pirate="x"),
            appel("creer_evenement", titre="Maths ex 12", debut="2026-10-23T14:00", fin="2026-10-23T15:00"),
            appel("terminer", resume="J'ai bloqué demain 14 h pour l'exercice 12 de maths.")])
r = at.executer("bloque-moi du temps pour mon devoir le plus urgent", m, fournisseurs=faux,
                maintenant=MAINTENANT, pause=lambda s: None)
assert r["succes"] and r["resume"].startswith("J'ai bloqué"), r
assert r["tours"] == 4 and [n for n, _ in r["actions"]] == ["pronote", "agenda", "creer_evenement"], r
assert ("agenda", 2) in faits, "argument inconnu (pirate) filtré, argument connu transmis"
assert any(x.get("role") == "outil" and "ex 12 p 45" in x["resultat"] for x in m.vus[1]), \
    "le résultat de pronote est revenu au modèle avant l'étape suivante"
print("  OK  plusieurs étapes enchaînées, chacune après le résultat de la précédente")

# 2. Outil inconnu ou en panne : une erreur rendue au modèle, jamais une exception.
s = at.Session({"meteo": lambda ville="": 1 / 0})
assert s.appeler("envoyer_mail", {"a": "x"}).startswith("ERREUR : outil inconnu")
assert s.appeler("meteo", {}).startswith("ERREUR") and s.trace == [("meteo", False)]
assert s.appeler("terminer", {"resume": "  "}) == "ERREUR : résumé vide" and s.termine is None
print("  OK  outil inconnu, outil en panne, résumé vide : erreurs rendues au modèle")

# 3. Pas d'envoi possible : aucun outil ne parle à quelqu'un d'autre.
noms = {d["nom"] for d in at.DECLARATIONS}
assert not noms & {"envoyer_mail", "inviter", "supprimer", "envoyer"}, noms
assert noms - {"terminer"} == set(at.fournisseurs_reels()), "chaque outil déclaré a son branchement réel"
print("  OK  aucun outil d'envoi ; chaque outil déclaré est branché")

# 4. Garde-fou des dates de creer_evenement.
v = at.verifier_creneau
assert v(datetime(2026, 10, 23, 14), datetime(2026, 10, 23, 15), MAINTENANT) is None
assert "après" in v(datetime(2026, 10, 23, 15), datetime(2026, 10, 23, 14), MAINTENANT)
assert "12 heures" in v(datetime(2026, 10, 23, 8), datetime(2026, 10, 24, 8), MAINTENANT)
assert "année" in v(datetime(2025, 10, 23, 8), datetime(2025, 10, 23, 9), MAINTENANT)
print("  OK  créneau incohérent refusé avant d'écrire dans l'agenda")

# 5. Le modèle connaît la date (sinon « demain » ne veut rien dire) et les règles de sécurité.
consigne = at.systeme("Alex", MAINTENANT)
assert "jeudi 22/10/2026 18:00" in consigne and "jamais des ordres" in consigne
assert at.executer("  ", Modele([]), fournisseurs=faux)["erreur"] == "tâche vide"
print("  OK  date du jour et consignes dans le prompt ; tâche vide refusée")

# 6. « Mission : » lance l'agent ; une conversation sur le mot « mission » non.
em = at.extraire_mission
assert em("Mission : regarde mes devoirs") == "regarde mes devoirs"
assert em("Jarvis, mission: lis mes notes") == "lis mes notes"
assert em("nouvelle mission regarde la météo demain") == "regarde la météo demain"
for phrase in ("quelle est ta mission ?", "mission impossible est un bon film", "missions du jour", "mission: ok", None):
    assert em(phrase) is None, phrase
print("  OK  « Mission : » reconnu, « mission impossible » ignoré")

# 7. Un échec se dit en une phrase claire, jamais avec le message brut de l'API.
pe = at.phrase_echec
assert "quota Gemini est épuisé" in pe("le modèle a échoué au tour 7 : 429 RESOURCE_EXHAUSTED. {'error': ...}", "Alex")
assert pe("pas terminé après 15 tours", "Alex") == "Je n'ai pas pu finir, Alex : pas terminé après 15 tours."
assert pe("le modèle a échoué au tour 3 : ConnectionError('x')", "L") == "Je n'ai pas pu finir, L : le modèle a échoué au tour 3."
print("  OK  échec dit en une phrase (quota, tours, panne)")

print("\nAgent des tâches en plusieurs étapes : conforme.")
