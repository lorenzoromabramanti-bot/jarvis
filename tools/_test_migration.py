# -*- coding: utf-8 -*-
"""
Test de non-regression de la passe 1 (prefixe _ => ignore par l'auto-decouverte).

Compare la sortie des outils migres a celle des fonctions ORIGINALES,
extraites du main2.py tel qu'il est dans git. Toute divergence = regression.

Lancer :  python tools/_test_migration.py
"""

import io
import os
import re
import subprocess
import sys

# Commit figé : dernier etat de main2.py contenant encore les fonctions d'origine.
# Ne pas remplacer par HEAD — apres le commit de la passe 1, HEAD ne les a plus.
REF_AVANT_MIGRATION = "b4905d1d430b38794cfc7aac65ce7436ac09c456"

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

PAIRES = [
    ("resoudre_francais_localement", "francais"),
    ("resoudre_conversion_localement", "conversion"),
    ("resoudre_traduction_localement", "traduction"),
]

# Entrees qui DOIVENT declencher chaque outil (sinon le test ne prouve rien),
# plus des entrees hors-sujet qui doivent renvoyer None dans les deux versions.
CAS = [
    "definition de jarvis", "definition de maison", "que veut dire intelligence artificielle",
    "definition de mathematiques", "c'est quoi une maison",
    "convertis 10 km en miles", "combien font 100 km en miles",
    "convertis 20 celsius en fahrenheit", "convertis 50 euros en dollars",
    "convertis 30 dollars en euros", "5 km en miles",
    "traduis bonjour en anglais", "traduis merci en espagnol",
    "traduis au revoir en allemand", "comment dit-on maison en anglais",
    "traduis ordinateur en espagnol", "traduis ami en allemand",
    "traduis oui en anglais", "traduis non en allemand",
    "quelle heure est-il", "allume la lumiere du salon", "", "   ",
    "raconte moi une blague", "quel temps fait-il demain",
]


def _charger_originaux():
    """Extrait les fonctions d'origine du main2.py versionne dans git."""
    src = subprocess.run(
        ["git", "-C", RACINE, "show", REF_AVANT_MIGRATION + ":main2.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.split("\n")
    espace = {"re": re}
    for nom, _ in PAIRES:
        debut = next((i for i, l in enumerate(src) if l.startswith("def %s(" % nom)), None)
        if debut is None:
            raise RuntimeError(
                "%s introuvable dans %s:main2.py" % (nom, REF_AVANT_MIGRATION)
            )
        fin = debut + 1
        while fin < len(src) and (src[fin].strip() == "" or src[fin][:1] in (" ", "\t")):
            fin += 1
        exec(compile("\n".join(src[debut:fin]), "<origine:%s>" % nom, "exec"), espace)
    return espace


def main():
    import tools
    tools.charger_outils()
    originaux = _charger_originaux()
    par_nom = {o["nom"]: f for o, f in
               zip(tools.lister_outils(), [t[2] for t in sorted(tools._REGISTRE)])}

    divergences, declenches = [], 0
    for nom_origine, nom_outil in PAIRES:
        avant = originaux[nom_origine]
        apres = par_nom[nom_outil]
        for texte in CAS:
            a, b = avant(texte), apres(texte)
            if a != b:
                divergences.append((nom_outil, texte, repr(a)[:80], repr(b)[:80]))
            elif a:
                declenches += 1

    print("cas testes      : %d (%d entrees x %d outils)" % (len(CAS) * len(PAIRES), len(CAS), len(PAIRES)))
    print("reponses reelles: %d  (un test qui ne declenche rien ne prouve rien)" % declenches)
    if divergences:
        print("REGRESSIONS     : %d" % len(divergences))
        for d in divergences[:10]:
            print("   outil=%s texte=%r\n     avant=%s\n     apres=%s" % d)
        sys.exit(1)
    assert declenches > 0, "aucun outil n'a repondu : cas de test inadaptes"
    print("RESULTAT        : sortie identique a l'originale, aucune regression")


if __name__ == "__main__":
    main()
