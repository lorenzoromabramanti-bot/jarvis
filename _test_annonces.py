# -*- coding: utf-8 -*-
"""Tests de annonces.py : venv\\Scripts\\python.exe _test_annonces.py"""
import annonces as a

AVION = "Alex, un avion jet privé passe à 47 kilomètres de chez toi."
assert a.filtrer("Question 2 sur 10 : …", en_reponse=True, urgent=False, quiz_actif=True) == "Question 2 sur 10 : …", \
    "une réponse à Alex passe pendant le quiz"
assert a.filtrer(AVION, en_reponse=False, urgent=False, quiz_actif=True) is None, "annonce de fond gardée"
assert a.filtrer("Fin du décompte.", en_reponse=False, urgent=True, quiz_actif=True) == "Fin du décompte.", \
    "le minuteur ne se fait pas attendre"
assert a.en_attente() == [AVION]
fin = a.filtrer("Révision terminée : 8 sur 10.", en_reponse=True, urgent=False, quiz_actif=False)
assert fin == "Révision terminée : 8 sur 10.\n" + AVION and a.en_attente() == [], "dite juste après le bilan"
for i in range(8):
    a.filtrer(f"avion {i}", en_reponse=False, urgent=False, quiz_actif=True)
assert a.en_attente() == [f"avion {i}" for i in range(3, 8)], "les plus anciennes tombent"
assert a.filtrer("Bonjour.", en_reponse=False, urgent=False, quiz_actif=False).startswith("Bonjour.\navion 3")
assert a.filtrer("Rien en attente.", en_reponse=False, urgent=False, quiz_actif=False) == "Rien en attente."
print("OK : annonces gardées pendant un quiz")
