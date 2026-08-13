# -*- coding: utf-8 -*-
"""
Verifie que JARVIS repond sur la machine ou il tourne, et vite.

Ces sept questions partaient au modele, qui mettait de 3 a 15 SECONDES a
repondre qu'il n'avait pas acces a l'information — alors que psutil etait
installe et deja utilise par le HUD pour afficher le CPU en direct.

Le test mesure deux choses : que la reponse existe, et qu'elle soit LOCALE.
Un delai qui remonte au-dessus du seuil signifie que la question est
repartie au modele, meme si la reponse a l'air correcte.

    venv\\Scripts\\python.exe _test_machine.py
"""

import asyncio
import builtins
import sys
import time

builtins.get_user_name = lambda: "Lorenzo"
builtins.get_user_age = lambda: None

import tools

# Genereux : sur une machine chargee, un outil local reste tres loin des
# secondes que coutait le modele.
SEUIL_MS = 900

QUESTIONS = [
    "quelle est mon adresse ip",
    "combien de place libre sur le disque",
    "quel est mon nom d ordinateur",
    "quelle est ma version de windows",
    "combien de memoire vive utilisee",
    "combien de mémoire vive utilisée",       # meme question, accentuee
    "quel est mon processeur",
    "suis-je connecte a internet",
    "quel est mon wifi",
]


def verifier():
    noms, echecs = tools.charger_outils()
    assert not echecs, "modules en echec : %s" % echecs
    assert "machine" in noms, "l'outil machine n'est pas charge"

    lents, muets = [], []
    for q in QUESTIONS:
        t = time.perf_counter()
        r = asyncio.run(tools.resoudre_async(q))
        ms = (time.perf_counter() - t) * 1000
        if not r:
            muets.append(q)
        elif ms > SEUIL_MS:
            lents.append("%s (%.0f ms)" % (q, ms))

    assert not muets, "aucune reponse locale : %s" % "; ".join(muets)
    assert not lents, "reparti au modele : %s" % "; ".join(lents)
    print("  OK  %d questions sur la machine, toutes locales" % len(QUESTIONS))

    # Accents : la MEME question doit donner la MEME reponse.
    a = asyncio.run(tools.resoudre_async("combien de memoire vive utilisee"))
    b = asyncio.run(tools.resoudre_async("combien de mémoire vive utilisée"))
    assert a and b, "une des deux formes reste sans reponse"
    assert a.split("—")[0] == b.split("—")[0], \
        "accentuee et non accentuee divergent :\n    %r\n    %r" % (a, b)
    print("  OK  accents indifferents (c'etait la cause des 6 secondes)")

    # Le MODELE du processeur n'est pas sa CHARGE.
    modele = asyncio.run(tools.resoudre_async("quel est mon processeur"))
    charge = asyncio.run(tools.resoudre_async("utilisation du processeur"))
    assert "utilisation" not in modele.lower(), \
        "« quel est mon processeur » repond la charge : %r" % modele
    assert "%" in charge or "utilisation" in charge.lower(), \
        "la question de charge ne repond plus la charge : %r" % charge
    print("  OK  modele de processeur et charge sont distingues")

    # La connexion doit etre TESTEE, pas deduite. JARVIS repondait
    # « puisque nous conversons en temps reel, la reponse est oui » — un
    # sophisme : lui et le navigateur sont sur la meme machine.
    import tools.machine as m
    assert isinstance(m._internet(delai=2.0), bool)
    reponse = asyncio.run(tools.resoudre_async("suis-je connecte a internet"))
    assert "conversons" not in reponse.lower(), "la deduction fautive est revenue"
    print("  OK  la connexion est testee, pas deduite")

    # Une information indisponible doit dire POURQUOI.
    ssid, raison = m._ssid()
    assert ssid or raison, "le Wi-Fi echoue sans expliquer pourquoi"
    print("  OK  le Wi-Fi indisponible donne sa raison (%s)"
          % (("connecte a %s" % ssid) if ssid else raison))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Informations machine : conforme.")
