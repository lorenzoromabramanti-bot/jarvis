# -*- coding: utf-8 -*-
"""
Non-regression du lot B. Prefixe _ => ignore par l'auto-decouverte.

Couvre :
  - globe(70)          : coroutine migree, comparee a l'originale avec les
                         memes doubles pour parler / send_globe_command /
                         geocode_lieu (sinon effets de bord non reproductibles)
  - les 3 adaptateurs  : extras_avancees(90), outils_boite(100), web_change(110)
                         doivent rendre exactement ce que rend le module sous-jacent
  - les modes          : web_change est "bloquant" et doit passer par un
                         executor, pas bloquer la boucle (main2 le faisait deja)
  - les tranches       : les bornes de priorite restent etanches

Lancer :  python tools/_test_migration_lotB.py
"""

import asyncio
import io
import os
import subprocess
import sys

REF_AVANT_MIGRATION = "e30cd00"  # commit du lot A : contient encore globe dans main2

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

CAS_GLOBE = [
    "montre moi paris sur le globe", "affiche new york sur le globe",
    "trajet de paris a londres", "distance entre paris et tokyo",
    "montre le globe", "cache le globe", "zoom sur berlin",
    "quelle heure est-il", "traduis bonjour en anglais", "",
]

# Entrees verifiees comme declenchant reellement chaque module (sinon le test
# comparerait None a None et ne prouverait rien - piege evite en passe 1).
CAS_ADAPTATEURS = [
    # jarvis_extras : aide, IMC, pourboire
    "que sais tu faire", "a quoi tu sers", "liste de tes commandes",
    "quelles sont tes fonctions", "calcule mon imc pour 80 kg et 1m80",
    "calcule le pourboire de 15% sur 40 euros",
    # jarvis_outils : conversions d'unites
    "convertis 10 pouces en metres", "combien fait 6 pieds en metres",
    "convertis 5 livres en kilos", "convertis 100 km h en miles",
    # hors sujet : doivent rendre None des deux cotes
    "allume la lumiere du salon", "",
]

_APPELS = []


async def _faux_parler(texte):
    _APPELS.append(("parler", texte))


async def _faux_send_globe_command(**kwargs):
    _APPELS.append(("globe", tuple(sorted(kwargs.items()))))


async def _faux_geocode_lieu(nom):
    _APPELS.append(("geocode", nom))
    return (48.85, 2.35, nom.title())


def _charger_globe_origine():
    src = subprocess.run(
        ["git", "-C", RACINE, "show", REF_AVANT_MIGRATION + ":main2.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.split("\n")
    nom = "resoudre_globe_localement"
    debut = next((i for i, l in enumerate(src) if l.startswith("async def %s(" % nom)), None)
    if debut is None:
        raise RuntimeError("%s introuvable dans %s:main2.py" % (nom, REF_AVANT_MIGRATION))
    fin = debut + 1
    while fin < len(src) and (src[fin].strip() == "" or src[fin][:1] in (" ", "\t")):
        fin += 1
    import re as _re
    espace = {"re": _re, "parler": _faux_parler,
              "send_globe_command": _faux_send_globe_command,
              "geocode_lieu": _faux_geocode_lieu}
    exec(compile("\n".join(src[debut:fin]), "<origine:globe>", "exec"), espace)
    return espace[nom]


async def _run():
    import builtins
    builtins.parler = _faux_parler
    builtins.send_globe_command = _faux_send_globe_command
    builtins.geocode_lieu = _faux_geocode_lieu
    builtins.get_user_name = lambda: "Lorenzo"
    builtins.get_user_age = lambda: "34"

    import tools
    noms, echecs = tools.charger_outils()
    assert not echecs, "outils non charges : %r" % (echecs,)
    print("outils charges  : %s" % [(o["priorite"], o["nom"], o["mode"]) for o in tools.lister_outils()])

    import tools.globe as tg
    tg.parler = _faux_parler
    tg.send_globe_command = _faux_send_globe_command
    tg.geocode_lieu = _faux_geocode_lieu

    echecs_test = []

    # --- globe : sortie ET effets de bord identiques
    avant = _charger_globe_origine()
    apres = tg.resoudre_globe_localement
    declenches = 0
    for texte in CAS_GLOBE:
        del _APPELS[:]
        a = await avant(texte)
        eff_a = list(_APPELS)
        del _APPELS[:]
        b = await apres(texte)
        eff_b = list(_APPELS)
        if a != b:
            echecs_test.append(("globe/sortie", texte, repr(a)[:70], repr(b)[:70]))
        elif eff_a != eff_b:
            echecs_test.append(("globe/effets", texte, repr(eff_a)[:70], repr(eff_b)[:70]))
        elif a or eff_a:
            declenches += 1
    print("globe           : %d cas, %d avec effet reel" % (len(CAS_GLOBE), declenches))

    # --- adaptateurs : rendu identique au module sous-jacent
    import jarvis_extras, jarvis_outils, jarvis_web
    import tools.extras_avancees, tools.outils_boite, tools.web_change
    paires = [
        (jarvis_extras.resoudre_extras_avancees, tools.extras_avancees.extras_avancees, "extras_avancees"),
        (jarvis_outils.resoudre_outils, tools.outils_boite.outils_boite, "outils_boite"),
    ]
    adapt_declenches = 0
    for direct, via_outil, nom in paires:
        for texte in CAS_ADAPTATEURS:
            a, b = direct(texte), via_outil(texte)
            if a != b:
                echecs_test.append((nom, texte, repr(a)[:70], repr(b)[:70]))
            elif a:
                adapt_declenches += 1
    print("adaptateurs     : %d reponses reelles (hors web : appels reseau)" % adapt_declenches)

    # --- mode bloquant : declare, et effectivement deporte hors de la boucle
    assert tools.web_change.web_change._outil_mode == "bloquant", \
        "web_change doit etre bloquant (jarvis_web fait du reseau)"
    marqueur = {}

    def _sonde(texte):
        marqueur["thread"] = __import__("threading").current_thread().name
        return None
    _sonde._outil_mode = "bloquant"
    tools._REGISTRE.append((999, "_sonde", _sonde))
    await tools.resoudre_async("test", depuis=999)
    tools._REGISTRE.pop()
    assert marqueur.get("thread", "MainThread") != "MainThread", \
        "un outil 'bloquant' doit tourner dans un executor, pas sur la boucle"
    print("mode bloquant   : execute hors du thread principal (%s)" % marqueur["thread"])

    # --- etancheite des tranches
    assert await tools.resoudre_async("quelle heure est-il", depuis=31) is None, \
        "depuis=31 laisse passer infos_systeme(20)"
    assert await tools.resoudre_async("traduis bonjour en anglais", jusqua=29) is None, \
        "jusqua=29 laisse passer un outil > 29"
    print("tranches        : bornes etanches")

    # --- resoudre() sync doit refuser une tranche non-sync plutot que la sauter
    try:
        tools.resoudre("montre paris sur le globe", depuis=70, jusqua=70)
        echecs_test.append(("resoudre-sync", "globe", "aucune erreur", "RuntimeError attendue"))
    except RuntimeError:
        print("resoudre() sync : refuse bien une tranche async")

    if echecs_test:
        print("REGRESSIONS     : %d" % len(echecs_test))
        for e in echecs_test[:10]:
            print("   %s texte=%r\n     avant=%s\n     apres=%s" % e)
        return 1
    assert declenches > 0, "globe n'a jamais reagi : cas de test inadaptes"
    assert adapt_declenches > 0, "les adaptateurs n'ont jamais repondu : la comparaison ne prouve rien"
    print("RESULTAT        : sortie et effets identiques, aucune regression")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_run()))
