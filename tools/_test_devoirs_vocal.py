# -*- coding: utf-8 -*-
"""Tests de tools/devoirs_vocal.py, sans Home Assistant : venv\\Scripts\\python.exe tools\\_test_devoirs_vocal.py"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import devoirs_vocal as dv  # noqa: E402

VENDREDI = dt.date(2026, 11, 6)
DEVOIRS = [
    {"date": "2026-11-09", "matiere": "EMI", "titre": "Apprendre la définition de Moyen de communication", "fait": False},
    {"date": "2026-11-12", "matiere": "MATHEMATIQUES", "titre": "Évaluation sur le théorème de Pythagore", "fait": False},
    {"date": "2026-11-10", "matiere": "SCIENCES VIE & TERRE", "titre": "revoir les hormones", "fait": False},
    {"date": "2026-11-10", "matiere": "ANGLAIS", "titre": "", "description": "Contrôle   vocabulaire", "fait": False},
    {"date": "2026-11-09", "matiere": "FRANCAIS", "titre": "déjà fait", "fait": True},
    {"date": "2026-11-06", "matiere": "ARTS", "titre": "rapporter des feuilles", "fait": False},
    {"date": "2026-11-20", "matiere": "SVT", "titre": "trop loin", "fait": False},
    {"date": "", "matiere": "?", "titre": "sans date", "fait": False},
]


def test_resume():
    phrase = dv.resume_devoirs(DEVOIRS, VENDREDI)
    assert phrase == ("Tu as lundi, Emi : Apprendre la définition de Moyen de communication ; "
                      "mardi, contrôle d'Anglais : Contrôle vocabulaire ; mardi, Sciences vie & terre : revoir les hormones ; "
                      "jeudi, contrôle de Mathematiques : Évaluation sur le théorème de Pythagore."), phrase
    assert dv.resume_devoirs(DEVOIRS, VENDREDI, seulement_aujourdhui=True) == "Tu as aujourd'hui, Arts : rapporter des feuilles."
    deux = dv.resume_devoirs(DEVOIRS, VENDREDI, maxi=2)
    assert deux == ("Tu as mardi, contrôle d'Anglais : Contrôle vocabulaire ; "
                    "jeudi, contrôle de Mathematiques : Évaluation sur le théorème de Pythagore. Et 2 autres après."), deux
    doublon = [{"date": "2026-11-10", "matiere": "MATHS", "titre": "Voir agenda", "fait": False}] * 2
    assert dv.resume_devoirs(doublon, VENDREDI) == "Tu as mardi, Maths : Voir agenda."  # dit une seule fois
    assert dv.resume_devoirs([], VENDREDI) == "Rien à rendre d'ici vendredi prochain, tout est coché."
    assert dv.resume_devoirs(DEVOIRS, VENDREDI, seulement_evals=True) == (
        "Tu as mardi, contrôle d'Anglais : Contrôle vocabulaire ; "
        "jeudi, contrôle de Mathematiques : Évaluation sur le théorème de Pythagore.")
    assert dv.resume_devoirs(DEVOIRS[:1], VENDREDI, seulement_evals=True) == \
        "Aucun contrôle annoncé dans Pronote d'ici vendredi prochain."
    long = [{"date": "2026-11-09", "matiere": "maths", "titre": "mot " * 40, "fait": False}]
    assert dv.resume_devoirs(long, VENDREDI).endswith("mot mot.") and len(dv.resume_devoirs(long, VENDREDI)) < 120
    colle = [{"date": "2026-11-09", "matiere": "maths", "titre": "Connaître la méthode de rédactionSavoir refaire sur iPhone", "fait": False}]
    assert dv.resume_devoirs(colle, VENDREDI) == "Tu as lundi, Maths : Connaître la méthode de rédaction. Savoir refaire sur iPhone."
    jeudi = dt.date(2026, 11, 5)
    assert dv.resume_devoirs([{"date": "2026-11-06", "matiere": "maths", "titre": "ex 3", "fait": False}], jeudi) == \
        "Tu as demain, Maths : ex 3."


def test_motifs():
    oui = ["J'ai quoi comme devoirs pour demain ?", "Jarvis, mes devoirs", "c'est quand mon prochain contrôle",
           "Quels devoirs pour lundi ?", "j'ai une éval cette semaine ?"]
    non = ["tu vas devoir attendre", "ouvre youtube", "quelle heure il est", "évalue mon code"]
    assert all(dv.contient(t, dv.MOTIFS) for t in oui), [t for t in oui if not dv.contient(t, dv.MOTIFS)]
    assert not any(dv.contient(t, dv.MOTIFS) for t in non), [t for t in non if dv.contient(t, dv.MOTIFS)]
    assert dv.devoirs_vocal("ouvre youtube") is None
    assert dv.contient("j’ai une éval demain".replace("’", "'"), dv.MOTIFS)  # apostrophe de la dictée


def test_notes():
    donnees = {"moyenne": "16,74", "moyennes": [
        {"matiere": "MATHEMATIQUES", "eleve": "17,5", "classe": "12,3"},
        {"matiere": "SCIENCES VIE & TERRE", "eleve": "15", "classe": ""},
        {"matiere": "ANGLAIS LV1", "eleve": "", "classe": "13"}],
        "notes": [{"date": "2026-11-03", "matiere": "ANGLAIS LV1", "note": "18", "bareme": "20"},
                  {"date": "2026-11-05", "matiere": "MATHEMATIQUES", "note": "8", "bareme": "10"},
                  {"date": "2026-10-20", "matiere": "SVT", "note": "Absent", "bareme": "20"},
                  {"date": "2026-09-01", "matiere": "EPS", "note": "12", "bareme": "20"}]}
    assert dv.resume_notes("c'est quoi ma moyenne en maths ?", donnees) == \
        "En Mathematiques, tu as 17,5 de moyenne. La classe est à 12,3."
    assert dv.resume_notes("ma moyenne en svt", donnees) == "En Sciences vie & terre, tu as 15 de moyenne."
    assert dv.resume_notes("ma moyenne en anglais", donnees).startswith("Ta moyenne générale")  # pas de moyenne d'anglais
    assert dv.resume_notes("c'est quoi ma moyenne ?", donnees) == (
        "Ta moyenne générale est de 16,74. Tes dernières notes : 8/10 en Mathematiques, "
        "18 sur 20 en Anglais lv1, Absent sur 20 en Svt.")
    assert dv.resume_notes("ma moyenne", {"moyenne": None, "moyennes": [], "notes": []}) == \
        "Pronote n'a encore aucune note ce trimestre."
    assert dv.contient("c'est quoi ma moyenne", dv.MOTIFS_NOTES) and not dv.contient("ouvre mes notes", dv.MOTIFS_NOTES)
    assert dv.notes_vocal("ouvre mes notes") is None  # « mes notes » reste à Obsidian
    assert dv._matiere("ANGLAIS LV1 > ORAL") == "Anglais lv1 oral"
    assert dv._matiere("HISTOIRE-GEOGRAPHIE > histoire-geographie") == "Histoire-geographie"


if __name__ == "__main__":
    test_resume()
    test_motifs()
    test_notes()
    print("OK : devoirs à la voix")
