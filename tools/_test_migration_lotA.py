# -*- coding: utf-8 -*-
"""
Non-regression du lot A (infos_systeme). Prefixe _ => ignore par l'auto-decouverte.

Cette fonction depend de l'heure et de psutil : comparer deux appels reels
donnerait des faux positifs (le CPU et l'horloge bougent entre les deux).
On injecte donc des doubles DETERMINISTES identiques des deux cotes, pour que
toute difference soit imputable a la migration et a rien d'autre.

Lancer :  python tools/_test_migration_lotA.py
"""

import io
import os
import subprocess
import sys
import types

REF_AVANT_MIGRATION = "e933cc1"  # dernier commit contenant encore la fonction d'origine

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

NOM = "resoudre_infos_systeme_localement"

CAS = [
    "quelle heure est-il", "il est quelle heure", "on est quel jour",
    "quelle est la date", "quel jour sommes-nous", "en quelle annee sommes-nous",
    "quel mois sommes-nous", "quel age j'ai", "quel age ai-je",
    "niveau de batterie", "combien de batterie", "utilisation du processeur",
    "combien de cpu", "combien de ram", "memoire utilisee",
    "depuis combien de temps l'ordinateur est allume", "uptime",
    "allume la lumiere", "traduis bonjour en anglais", "", "raconte une blague",
]


class _FauxBatterie(object):
    percent = 87
    power_plugged = False


def _faux_psutil():
    m = types.SimpleNamespace()
    m.sensors_battery = lambda: _FauxBatterie()
    m.cpu_percent = lambda interval=None: 42.0
    m.virtual_memory = lambda: types.SimpleNamespace(
        used=8 * 1024**3, total=16 * 1024**3, percent=50.0)
    m.boot_time = lambda: 1754800000.0
    return m


class _FauxDatetime(object):
    """datetime fige : meme instant des deux cotes."""
    _FIXE = None

    @classmethod
    def now(cls):
        return cls._FIXE

    @staticmethod
    def fromtimestamp(ts):
        import datetime as _d
        return _d.datetime.fromtimestamp(ts)


def _charger_origine():
    src = subprocess.run(
        ["git", "-C", RACINE, "show", REF_AVANT_MIGRATION + ":main2.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.split("\n")
    debut = next((i for i, l in enumerate(src) if l.startswith("def %s(" % NOM)), None)
    if debut is None:
        raise RuntimeError("%s introuvable dans %s:main2.py" % (NOM, REF_AVANT_MIGRATION))
    fin = debut + 1
    while fin < len(src) and (src[fin].strip() == "" or src[fin][:1] in (" ", "\t")):
        fin += 1
    espace = {"psutil": _faux_psutil(), "datetime": _FauxDatetime,
              "USER_NAME": "Lorenzo", "USER_AGE": "34"}
    exec(compile("\n".join(src[debut:fin]), "<origine>", "exec"), espace)
    return espace[NOM]


def main():
    import builtins
    import datetime as _dt
    _FauxDatetime._FIXE = _dt.datetime(2026, 8, 10, 14, 37, 5)

    builtins.get_user_name = lambda: "Lorenzo"
    builtins.get_user_age = lambda: "34"

    import tools
    tools.charger_outils()
    import tools.infos_systeme as ti
    ti.psutil = _faux_psutil()
    ti.datetime = _FauxDatetime

    avant = _charger_origine()
    apres = ti.resoudre_infos_systeme_localement

    divergences, declenches = [], 0
    for texte in CAS:
        a, b = avant(texte), apres(texte)
        if a != b:
            divergences.append((texte, repr(a)[:90], repr(b)[:90]))
        elif a:
            declenches += 1

    print("cas testes      : %d" % len(CAS))
    print("reponses reelles: %d" % declenches)
    if divergences:
        print("REGRESSIONS     : %d" % len(divergences))
        for t, a, b in divergences[:10]:
            print("   texte=%r\n     avant=%s\n     apres=%s" % (t, a, b))
        sys.exit(1)
    assert declenches > 0, "aucune reponse : cas de test inadaptes"

    # la tranche de priorite doit isoler infos_systeme(20) de francais(40)+
    assert tools.resoudre("traduis bonjour en anglais", jusqua=29) is None, \
        "la borne jusqua=29 laisse passer un outil de priorite > 29"
    # jusqua=69 : au-dela commence globe(70), async -> resoudre() sync refuserait
    assert tools.resoudre("quelle heure est-il", depuis=31, jusqua=69) is None, \
        "la borne depuis=31 laisse passer infos_systeme(20)"
    print("bornes de priorite : jusqua=29 / depuis=31 correctement etanches")
    print("RESULTAT        : sortie identique a l'originale, aucune regression")


if __name__ == "__main__":
    main()
