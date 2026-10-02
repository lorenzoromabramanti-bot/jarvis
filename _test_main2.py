# -*- coding: utf-8 -*-
"""
Verifie les gardes de main2.py ajoutees en revue de securite (v1.2.0), sans
reseau, sans Home Assistant, sans toucher au clavier :

  - le WebSocket refuse les pages web etrangeres (en-tete Origin) ;
  - main2 lance en script s'enregistre sous son nom (pas de seconde copie) ;
  - desarmer l'alarme, deverrouiller une porte attendent un « oui » ;
  - depuis le telephone ou Discord, taper au clavier attend un « oui ».

    venv\\Scripts\\python.exe _test_main2.py
"""

import asyncio
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

echecs = []


def verifier(libelle, condition, detail=None):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        if detail is not None:
            print("      ->", detail)
        echecs.append(libelle)


# ── #8 : l'alias est pose AVANT tout import qui ferait `import main2` ──
source = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "main2.py"),
                 encoding="utf-8").read()
alias = source.find('sys.modules.setdefault("main2", sys.modules[__name__])')
verifier("main2 lance en script s'enregistre sous le nom main2, en tete de fichier",
          0 < alias < source.find("import google.genai"))

import main2  # noqa: E402
import catalogue  # noqa: E402
from tools import pc_controle  # noqa: E402

# ── #4 : Origin ─────────────────────────────────────────────────────────
for origine in (None, "", "http://localhost:5173", "http://127.0.0.1:8001",
                "http://[::1]:5173", "http://192.168.1.20:5173", "http://100.101.102.103"):
    verifier("origine acceptee : %r" % origine, main2._origine_autorisee(origine))
for origine in ("https://evil.example", "null", "http://localhost.evil.example",
                "http://8.8.8.8", "https://127.0.0.1.nip.io"):
    verifier("origine refusee : %r" % origine, not main2._origine_autorisee(origine))

# ── #11 et #9 : confirmations ──────────────────────────────────────────
dits, services, frappes, reponse_modele = [], [], [], {"v": ""}
vrais = (main2.parler, main2.demander_ia, main2.ha_appeler_service,
         catalogue.action_autorisee, pc_controle.executer)


async def _parler(texte, *a, **k):
    dits.append(texte)


async def _demander_ia(*a, **k):
    return reponse_modele["v"]


main2.parler = _parler
main2.demander_ia = _demander_ia
main2.ha_appeler_service = lambda *a, **k: services.append(a)
catalogue.action_autorisee = lambda action: True
pc_controle.executer = lambda action, arg: frappes.append((action, arg)) or "fait"
os.environ["HA_ALARME_ENTITY"] = "alarm_control_panel.test"


async def dire(texte, **k):
    dits.clear()
    await main2.traiter_reponse_ia(texte, **k)
    await asyncio.sleep(0.05)
    return " | ".join(dits)


async def scenario():
    reponse_modele["v"] = '{"action": "ha_alarme", "etat": "off"}'
    await dire("fais le necessaire pour la maison")
    verifier("alarme : rien n'est desarme sur la demande seule",
              not services and main2.ATTENTE_CONFIRMATION_ACTION is not None, dits)
    await dire("oui")
    verifier("alarme : desarmee apres « oui »",
              services and services[0][1] == "alarm_disarm", (services, dits))

    services.clear()
    await dire("fais le necessaire pour la maison")
    reponse_modele["v"] = "rien"
    await dire("oui mais plus tard")
    verifier("alarme : une phrase qui contient « oui » sans le dire ne desarme rien",
              not services and main2.ATTENTE_CONFIRMATION_ACTION is None, dits)
    reponse_modele["v"] = '{"action": "ha_alarme", "etat": "off"}'
    await dire("fais le necessaire pour la maison")
    await dire("non")
    verifier("alarme : « non » ne desarme rien",
              not services and main2.ATTENTE_CONFIRMATION_ACTION is None, dits)

    await dire("tape bonjour", mobile_ws=object(), target_pc=True)
    verifier("telephone : « tape » attend un « oui », rien n'est frappe",
              not frappes and main2.ATTENTE_CONFIRMATION_ACTION is not None, dits)
    await dire("oui", mobile_ws=object(), target_pc=True)
    verifier("telephone : frappe apres « oui »", frappes == [("taper", "bonjour")], frappes)


try:
    asyncio.run(scenario())
finally:
    (main2.parler, main2.demander_ia, main2.ha_appeler_service,
     catalogue.action_autorisee, pc_controle.executer) = vrais

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    sys.stdout.flush()
    os._exit(1)
print("Gardes de main2 : conformes.")
sys.stdout.flush()
os._exit(0)
