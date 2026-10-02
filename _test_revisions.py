# -*- coding: utf-8 -*-
r"""
Vérifie revisions.py sans réseau : lecteur Home Assistant et modèle injectés.

CE QU'IL GARDE VRAIMENT
1. Les contrôles de DEMAIN sont trouvés là où Pronote les met vraiment (un
   devoir « Evaluation prevue en classe »), pas les devoirs ordinaires ni les
   évaluations déjà notées.
2. Un JSON de modèle bancal ne produit jamais un quiz faux : QCM dont la
   réponse n'est pas un choix écarté, « B » ramené au texte du choix B.
3. La préparation du soir ne régénère pas un quiz existant (pas de double
   notification).
4. Le mode quiz corrige lui-même (lettre, « moins 8 », ouverte jugée par le modèle
   local), compte le score et s'éteint après la dernière question.

    venv\Scripts\python.exe _test_revisions.py
"""

import json
import sys
import tempfile
from datetime import date

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import revisions as r

AUJ = date(2030, 1, 14)
DEVOIRS = [
    {"date": "2030-01-15", "subject": "MATHEMATIQUES", "short_description": "Evaluation prevue en classe",
     "description": "Evaluation prevue en classe", "done": False},
    {"date": "2030-01-15", "subject": "FRANCAIS", "short_description": "Relire la leçon",
     "description": "Relire la leçon", "done": True},
    {"date": "2030-01-17", "subject": "HISTOIRE-GEOGRAPHIE", "short_description": "Évaluation sur le chapitre exemple",
     "description": "Évaluation sur le chapitre exemple", "done": False},
]
EVALS = [  # déjà notées (passées) : servent de chapitres, pas de cibles
    {"date": "2030-01-09", "subject": "MATHEMATIQUES", "name": "Chapitre exemple A", "description": ""},
    {"date": "2030-01-15", "subject": "SCIENCES VIE & TERRE", "name": "Chapitre exemple B", "description": ""},
]


def lecteur(capteur, attribut=None):
    return {"homework": DEVOIRS, "evaluations": EVALS}.get(attribut, "inconnu")


def qcm(i, reponse="Paris", choix=("Paris", "Lyon", "Nice", "Lille")):
    return {"q": "Question %d ?" % i, "choix": list(choix), "reponse": reponse, "explication": "Parce que."}


BON = json.dumps({"qcm": [qcm(i) for i in range(6)],        # format demandé au modèle
                  "ouvertes": [{"q": "Ouverte %d ?" % i, "reponse": "42", "explication": "Calcul."}
                               for i in range(4)]})

echecs = []


def verifier(libelle, condition):
    print("  %s  %s" % ("OK " if condition else "ECHEC", libelle))
    if not condition:
        echecs.append(libelle)


# 1. Sélection des évaluations
import agenda_scolaire
donnees, _ = agenda_scolaire.devoirs_evaluations_notes(lecteur)
demain = r.evaluations_du(donnees, "2030-01-15")
matieres = sorted(e["matiere"] for e in demain)
verifier("demain : le devoir « Evaluation » de maths et l'évaluation SVT datée",
         matieres == ["MATHEMATIQUES", "SCIENCES VIE & TERRE"])
verifier("le devoir ordinaire de français n'est pas une évaluation", "FRANCAIS" not in matieres)
verifier("les évaluations notées de la matière deviennent des chapitres",
         "Chapitre exemple A" in r.contexte(demain[0] if demain[0]["matiere"] == "MATHEMATIQUES"
                                                  else demain[1], donnees))

# 2. Validation du JSON du modèle
qs = r.valider(BON)
verifier("10 questions valides gardées", len(qs) == 10)
verifier("question ouverte : pas de clé choix", "choix" not in qs[-1] and qs[0]["choix"])
verifier("format du fichier {questions: [...]} relu aussi",
         len(r.valider({"questions": qs})) == 10 and qs[-1]["q"] == "Ouverte 3 ?")
lettre = json.loads(BON)
lettre["qcm"][0]["reponse"] = "C"
lettre["qcm"][1]["reponse"] = "Marseille"          # pas un choix -> écartée
qs = r.valider(lettre)
verifier("« C » ramené au texte du choix C", qs[0]["reponse"] == "Nice")
verifier("QCM dont la réponse n'est pas un choix : écarté", len(qs) == 9)
for brut in ("pas du json", json.dumps({"questions": [qcm(1)]}), json.dumps({"autre": 1})):
    try:
        r.valider(brut)
        verifier("JSON inexploitable refusé : %s" % brut[:25], False)
    except ValueError:
        verifier("JSON inexploitable refusé : %s" % brut[:25], True)

# 3. Génération (2e essai) et préparation du soir
reponses = iter(["{cassé", BON])
quiz = r.generer(demain[0], donnees, appel_modele=lambda m: next(reponses))
verifier("un premier JSON cassé déclenche un second essai",
         len(quiz["questions"]) == 10 and set(quiz) == {"date", "matiere", "evaluation", "questions"})

r.DOSSIER = tempfile.mkdtemp()
appels = []


def modele(messages):
    appels.append(messages)
    return BON


phrases = r.preparer(lecteur=lecteur, appel_modele=modele, aujourdhui=AUJ)
verifier("deux quiz préparés pour demain, deux phrases", len(phrases) == 2 and "demain" in phrases[0])
verifier("fichier AAAA-MM-JJ_matiere.json écrit",
         any(q["fichier"] == "2030-01-15_mathematiques.json" for q in r.quiz_prepares()))
verifier("le prompt contient la matière et le niveau",
         "MATHEMATIQUES" in json.dumps(appels, ensure_ascii=False) and r.NIVEAU in appels[0][0]["content"])
verifier("seconde préparation : rien à refaire", r.preparer(lecteur=lecteur, appel_modele=modele,
                                                           aujourdhui=AUJ) == [] and len(appels) == 2)

# 4. Conversation
verifier("« fais-moi réviser » reconnu", r.reconnait_demande("Jarvis, fais-moi réviser"))
verifier("« interroge-moi en maths » reconnu", r.reconnait_demande("interroge-moi en maths"))
verifier("« quel temps fait-il » ignoré", not r.reconnait_demande("quel temps fait-il"))
verifier("« stop révision » reconnu", r.reconnait_arret("Stop révision"))
verifier("une réponse « -5 » n'arrête pas", not r.reconnait_arret("-5"))
mats = ["HISTOIRE-GEOGRAPHIE", "MATHEMATIQUES", "SCIENCES VIE & TERRE"]
verifier("maths -> MATHEMATIQUES", r.matiere_demandee("interroge-moi en maths", mats) == "MATHEMATIQUES")
verifier("svt -> SCIENCES VIE & TERRE", r.matiere_demandee("quiz de revision svt", mats) == "SCIENCES VIE & TERRE")
verifier("géo -> HISTOIRE-GEOGRAPHIE", r.matiere_demandee("interroge-moi en géo", mats) == "HISTOIRE-GEOGRAPHIE")
verifier("sans matière -> None", r.matiere_demandee("fais-moi réviser", mats) is None)

q, raison = r.quiz_pour("interroge-moi en histoire", lecteur=lecteur, appel_modele=modele, aujourdhui=AUJ)
verifier("histoire -> l'évaluation du 01/10 générée à la volée",
         not raison and q["matiere"] == "HISTOIRE-GEOGRAPHIE" and q["date"] == "2030-01-17")
q, raison = r.quiz_pour("fais-moi réviser", lecteur=lecteur, appel_modele=modele, aujourdhui=AUJ)
verifier("sans matière -> la plus proche (demain)", not raison and q["date"] == "2030-01-15")

# 5. Mode quiz : déroulé tenu par le code (le modèle de chat se trompait, test WS du 28/09)
QCM = {"q": "(-5) - (+3) ?", "choix": ["-2", "-8", "+2", "+8"], "reponse": "-8", "explication": "E1."}
OUV = {"q": "Définir un nombre relatif.", "reponse": "un nombre avec un signe", "explication": "E2."}
quiz = {"date": "2030-01-15", "matiere": "MATHEMATIQUES", "evaluation": "Evaluation prevue en classe",
        "questions": [QCM, OUV, QCM]}
verifier("QCM : « B, moins 8 » juste", r.est_juste(QCM, "B, moins 8"))
verifier("QCM : « la b » juste", r.est_juste(QCM, "la b"))
verifier("QCM : « moins 8 » (voix) juste", r.est_juste(QCM, "moins 8"))
verifier("QCM : « A » faux", not r.est_juste(QCM, "A"))
verifier("QCM : « je sais pas » faux", not r.est_juste(QCM, "je sais pas"))
verifier("ouverte : texte attendu contenu -> juste sans modèle",
         r.est_juste(OUV, "c'est un nombre avec un signe", juge=lambda q, a: 1 / 0))
verifier("ouverte : sinon le juge décide", r.est_juste(OUV, "positif ou négatif", juge=lambda q, a: True))
verifier("ouverte : juge en panne -> faux, pas de plantage",
         not r.est_juste(OUV, "positif ou négatif", juge=lambda q, a: 1 / 0))
t = r.demarrer(quiz)
verifier("démarrage : annonce + question 1 avec lettres", r.quiz_actif() and "Question 1 sur 3" in t
         and "B) -8" in t and "stop révision" in t)
t = r.repondre("B")
verifier("réponse 1 juste : score 1 sur 1, question 2", t.startswith("Juste") and "Score : 1 sur 1" in t
         and "Question 2 sur 3" in t)
t = r.repondre("je ne sais pas", juge=lambda q, a: True)
verifier("réponse 2 faux : corrigé montré, score 1 sur 2", "Faux. La réponse était : un nombre avec un signe" in t
         and "Score : 1 sur 2" in t and "Question 3 sur 3" in t)
t = r.repondre("-8")
verifier("dernière réponse : bilan, mode éteint", "Révision terminée : 2 sur 3" in t and not r.quiz_actif())

print("\n  %s" % ("Révisions : conforme." if not echecs else "%d ECHEC(S)" % len(echecs)))
sys.exit(1 if echecs else 0)
