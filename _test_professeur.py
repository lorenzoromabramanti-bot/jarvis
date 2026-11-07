# -*- coding: utf-8 -*-
r"""
Vérifie professeur.py (Mode Professeur) et ce qu'il ajoute au quiz de revisions.py, sans réseau :
le cerveau est une fausse coroutine, les fichiers vont dans un dossier temporaire.

CE QU'IL GARDE VRAIMENT
1. « Interroge-moi sur X » part au professeur, mais « interroge-moi en maths » et « fais-moi réviser
   pour demain » restent au quiz Pronote, et « explique-moi… » reste au cerveau.
2. Le JSON du cerveau, même entouré de ```json, donne un quiz ; un cerveau en panne donne une raison.
3. « Répète », « indice » et « redis le cours » ne comptent pas comme une réponse.
4. Une question ratée revient en carte mémoire, monte de boîte quand elle est juste, sort à la 3e.
5. Un quiz arrêté reprend à sa question ; fini, il n'y a plus rien à reprendre.

    venv\Scripts\python.exe _test_professeur.py
"""
import asyncio
import json
import os
import sys
import tempfile
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import professeur as p
import revisions as r

r.DOSSIER = tempfile.mkdtemp()
AUJ = date.today()  # revisions.repondre note les cartes à la date du jour : une date figée rendait le test faux dès le lendemain
echecs = []


def verifier(libelle, condition):
    print("  %s  %s" % ("OK " if condition else "ECHEC", libelle))
    if not condition:
        echecs.append(libelle)


def qcm(i):
    return {"q": "QCM %d ?" % i, "choix": ["1789", "1815", "1492", "1914"], "reponse": "1789", "explication": "Date."}


def ouverte(i):
    return {"q": "Ouverte %d ?" % i, "reponse": "la prise de la Bastille", "explication": "Le 14 juillet."}


QUIZ = json.dumps({"qcm": [qcm(i) for i in range(6)], "ouvertes": [ouverte(i) for i in range(4)]})
COURS = json.dumps({"cours": "Une **fraction** partage une unité en parts égales. Exemple : 3/4.",
                    "qcm": [qcm(0), qcm(1)], "ouvertes": [ouverte(0), ouverte(1)]})


def cerveau(*reponses):
    suite = iter(reponses)

    async def appel(consigne):
        cerveau.consignes.append(consigne)
        rep = next(suite)
        if isinstance(rep, Exception):
            raise rep
        return rep
    cerveau.consignes = []
    return appel


def lancer(demande, appel):
    return asyncio.run(p.lancer(demande, appel, aujourdhui=AUJ))


# 1. Reconnaître la demande
for phrase, attendu in [
        ("Jarvis, interroge-moi sur la Révolution française s'il te plaît", ("quiz", "la Révolution française")),
        ("fais-moi un quiz sur les volcans", ("quiz", "les volcans")),
        ("fais-moi réviser les fractions", ("quiz", "les fractions")),
        ("fais-moi un cours sur la photosynthèse", ("cours", "la photosynthèse")),
        ("fais-moi un cours des volcans", ("cours", "volcans")),
        ("fais-moi un cours d'histoire", ("cours", "histoire")),
        ("apprends-moi les fractions", ("cours", "les fractions")),
        ("fais-moi un cours", ("cours", None)),
        ("mode professeur", ("menu", None)),
        ("révise mes erreurs", ("erreurs", None)),
        ("Jarvis, refais mes erreurs", ("erreurs", None)),
        ("reprends la révision", ("reprise", None)),
        ("on reprend le quiz", ("reprise", None)),
        ("interroge-moi en maths", None),
        ("fais-moi réviser", None),
        ("fais-moi réviser pour demain", None),
        ("fais-moi réviser mes maths", None),
        ("interroge-moi sur mon contrôle de jeudi", None),
        ("explique-moi pourquoi le ciel est bleu", None),
        ("quel temps fait-il", None)]:
    verifier("%-62s -> %s" % (phrase, attendu), p.reconnait(phrase) == attendu)

# 2. Quiz sur un sujet libre
t, raison = lancer(("quiz", "la Révolution française"), cerveau("Voici :\n```json\n" + QUIZ + "\n```"))
verifier("quiz : annonce + question 1 sur 10", not raison and "10 questions sur la Révolution française" in t
         and "Question 1 sur 10" in t and r.quiz_actif())
verifier("le sujet et le niveau sont dans la consigne",
         "la Révolution française" in cerveau.consignes[0] and r.NIVEAU in cerveau.consignes[0])
t, raison = lancer(("quiz", "les volcans"), cerveau("{cassé", "toujours pas du json"))
verifier("deux réponses inutilisables -> raison, pas de plantage", t is None and "inutilisable" in raison)
t, raison = lancer(("quiz", "les volcans"), cerveau(RuntimeError("Gemini ET Ollama indisponibles")))
verifier("cerveau en panne -> raison", t is None and "ne répond pas" in raison)
t, raison = lancer(("cours", None), cerveau())
verifier("cours sans sujet -> on demande lequel", "Sur quel sujet" in t and not cerveau.consignes)

# 3. Cours puis questions ; « répète », « indice », « redis le cours »
t, raison = lancer(("cours", "les fractions"), cerveau(COURS))
verifier("cours : le cours, sans Markdown, puis 4 questions", t.startswith("Une fraction partage")
         and "**" not in t and "4 questions pour vérifier" in t and "Question 1 sur 4" in t)
verifier("« répète » redonne la question sans la compter",
         "Question 1 sur 4" in r.repondre("Tu peux répéter s'il te plaît ?") and r._ETAT["repondues"] == 0)
verifier("« indice » sur un QCM écarte deux choix", r.repondre("un indice") == "Indice : ce n'est ni B, ni D.")
verifier("« redis le cours »", r.repondre("Jarvis redis le cours").startswith("Une fraction"))
verifier("indice d'une question ouverte : le début d'un mot", r.indice(ouverte(0)) == "Indice : un mot de la réponse commence par « pri… ».")
verifier("indice d'un nombre : ne le donne pas", r.indice({"q": "?", "reponse": "-8"}) == "Indice : c'est un nombre négatif à 1 chiffre.")

# 4. Cartes mémoire
verifier("réponse fausse : corrigé montré", r.repondre("1492").startswith("Faux. La réponse était : 1789"))
cartes = p._lire_cartes()
verifier("la question ratée devient une carte en boîte 1", len(cartes) == 1 and cartes[0]["boite"] == 1
         and cartes[0]["sujet"] == "les fractions")
r.repondre("C")
verifier("une 2e erreur sur une autre question : 2 cartes", len(p._lire_cartes()) == 2)
r.repondre("la prise de la Bastille")
t = r.repondre("la prise de la bastille")
verifier("fin du cours : bilan + rappel des erreurs", "Révision terminée : 2 sur 4" in t and "révise mes erreurs" in t)
verifier("le menu annonce les 2 erreurs à revoir", "2 erreurs à revoir" in p.menu(AUJ))

t, raison = lancer(("erreurs", None), cerveau())
verifier("« révise mes erreurs » : quiz des 2 cartes", "On revoit 2 erreurs" in t and "Question 1 sur 2" in t)
r.repondre("A")
r.repondre("1789")
verifier("justes : boîte 2, à revoir dans 2 jours",
         all(c["boite"] == 2 and c["revoir"] == (date.today() + timedelta(days=2)).isoformat() for c in p._lire_cartes()))
verifier("plus rien à revoir aujourd'hui", p.cartes_dues(date.today()) == [] and len(p.cartes_dues(date.today() + timedelta(days=2))) == 2)
q0 = p._lire_cartes()[0]
p.noter(q0, True, {}, aujourdhui=AUJ)
p.noter(q0, True, {}, aujourdhui=AUJ)
verifier("juste en boîte 3 : carte apprise, retirée", len(p._lire_cartes()) == 1)
p.noter(p._lire_cartes()[0], False, {}, aujourdhui=AUJ)
verifier("de nouveau ratée : retour en boîte 1", p._lire_cartes()[0]["boite"] == 1)

# 5. Reprise
t, raison = lancer(("quiz", "la Révolution française"), cerveau(QUIZ))
r.repondre("A")
r.arreter()
verifier("après « stop révision », le menu propose la reprise", not r.quiz_actif() and "en pause" in p.menu(AUJ))
t, raison = lancer(("reprise", None), cerveau())
verifier("« reprends la révision » : question 2, score gardé", "Question 2 sur 10" in t and "score 1 sur 1" in t
         and r.quiz_actif())
for _ in range(9):
    t = r.repondre("1789")
verifier("quiz fini : plus rien à reprendre", "Révision terminée" in t and not os.path.exists(r._chemin_en_cours()))
t, raison = lancer(("reprise", None), cerveau())
verifier("reprise sans quiz en pause -> raison", t is None and "aucun quiz en pause" in raison)

print("\n  %s" % ("Mode Professeur : conforme." if not echecs else "%d ECHEC(S)" % len(echecs)))
sys.exit(1 if echecs else 0)
