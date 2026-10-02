# -*- coding: utf-8 -*-
"""
Verifie la commande qui eteint JARVIS.

Depuis que fermer le HUD masque au lieu d'eteindre, cette commande est un
des deux seuls moyens de sortir. Elle doit donc declencher quand on le
demande, et SURTOUT jamais quand on demande autre chose : eteindre
l'assistant parce qu'on voulait couper la musique serait pire que l'inverse.

Un premier jet cherchait « jarvis » plus un verbe d'arret n'importe ou dans
la phrase, avec une liste noire d'exceptions. « Jarvis, arrete la musique »
eteignait l'assistant. Les cas ci-dessous sont ecrits d'apres ce qui DOIT se
passer, pas d'apres ce que le code fait.

    venv\\Scripts\\python.exe _test_ordre_arret.py
"""

import re
import sys
import unicodedata


def est_ordre_arret(texte):
    """Copie exacte de la regle de main2.py. Doit rester synchronisee."""
    t = "".join(c for c in unicodedata.normalize("NFD", texte.lower())
                if unicodedata.category(c) != "Mn")
    # Ponctuation d'abord : « s'il te plait » garderait sinon son apostrophe
    # et echapperait au filtre de politesse.
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\b(s ?il te plait|stp|merci|maintenant|completement|"
               r"totalement|tout de suite)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    ordre = re.match(
        r"^(jarvis )?(quitte|quitter|ferme|fermer|arrete|arreter|eteins|eteindre|"
        r"eteins toi|coupe)( toi)?( jarvis)?$", t)
    return bool(ordre and "jarvis" in t)


DOIT_ETEINDRE = [
    "quitter jarvis", "quitte jarvis", "ferme jarvis", "fermer jarvis",
    "arrete jarvis", "arrête jarvis", "arrêter jarvis", "eteins jarvis",
    "éteins jarvis", "Jarvis, quitte.", "jarvis arrete toi",
    "quitte jarvis stp", "ferme jarvis s'il te plait",
    "arrête jarvis maintenant", "QUITTER JARVIS",
]

# Chacune de ces phrases a deja son propre traitement ailleurs. Les capturer
# eteindrait l'assistant au lieu de faire ce qui est demande.
NE_DOIT_PAS = [
    "jarvis arrete la musique",      # le piege du premier jet
    "jarvis arrête la musique",
    "jarvis ferme le navigateur",
    "jarvis ferme cet onglet",
    "jarvis eteins le pc",
    "jarvis coupe le son",
    "jarvis arrete le minuteur",
    "jarvis ferme spotify",
    "jarvis quitte cette page",
    "jarvis arrete de parler",
    "eteins le pc", "arrete", "stop", "tais toi", "au revoir",
    "jarvis quelle heure est-il",
    "jarvis comment fermer une fenetre",
    "ferme la porte du garage",
    "jarvis ferme les volets",
    "",
]


def verifier():
    rates = []
    for phrase in DOIT_ETEINDRE:
        if not est_ordre_arret(phrase):
            rates.append("NON DECLENCHE alors qu'il devait : %r" % phrase)
    for phrase in NE_DOIT_PAS:
        if est_ordre_arret(phrase):
            rates.append("DECLENCHE a tort : %r" % phrase)

    for r in rates:
        print("  RATE  %s" % r)
    assert not rates, "%d cas incorrects" % len(rates)

    print("  OK  %d formulations eteignent JARVIS" % len(DOIT_ETEINDRE))
    print("  OK  %d phrases voisines ne l'eteignent PAS" % len(NE_DOIT_PAS))
    print("  OK  « jarvis arrete la musique » ne tue plus l'assistant")

    # La regle de ce fichier doit rester identique a celle de main2.
    import io, os
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "main2.py"), encoding="utf-8").read()
    assert "quitte|quitter|ferme|fermer|arrete|arreter|eteins|eteindre" in src, \
        "la regle de main2.py a change sans que ce test suive"
    print("  OK  la regle testee est bien celle de main2.py")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Ordre d'arret : conforme.")
