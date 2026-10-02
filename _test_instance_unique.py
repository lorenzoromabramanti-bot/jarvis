# -*- coding: utf-8 -*-
r"""
Vérifie le verrou d'instance unique — SANS tuer quoi que ce soit.

CE QU'IL GARDE VRAIMENT
1. La reconnaissance d'un « vrai » JARVIS. Une recherche naïve de « main2.py »
   dans la ligne de commande attrape aussi `python -c "...main2.py..."` : un
   script de diagnostic. Mesuré pendant l'écriture de ce module — quatre
   instances comptées, dont deux étaient les sondes qui comptaient. Tuer ça
   reviendrait à tirer sur l'observateur.
2. On ne tue jamais un ancêtre. Le lanceur (`DEMARRER_JARVIS.bat` puis le
   python du venv) est le parent du processus courant : le fermer tuerait
   le JARVIS qu'on est en train de démarrer.
3. Un dossier différent n'est pas notre affaire : une autre copie de JARVIS
   ailleurs sur le disque ne doit pas être fermée.

    venv\Scripts\python.exe _test_instance_unique.py
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import instance_unique as iu

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


RACINE = os.path.dirname(os.path.abspath(__file__))
AILLEURS = os.path.join(RACINE, "..", "autre-jarvis")

# ── Reconnaissance d'un lancement reel ───────────────────────────────────
verifier("le lanceur du venv est reconnu",
         iu.est_jarvis([r".\venv\Scripts\python.exe", "main2.py"], RACINE))
verifier("le processus enfant est reconnu",
         iu.est_jarvis([r"C:\Python312\python.exe", "main2.py"], RACINE))
verifier("un chemin absolu vers main2.py est reconnu",
         iu.est_jarvis(["python.exe", os.path.join(RACINE, "main2.py")], RACINE))
verifier("les guillemets autour de l'argument ne genent pas",
         iu.est_jarvis(["python.exe", '"main2.py"'], RACINE))

# Le piege qui a REELLEMENT fausse le comptage.
SONDE = ["python.exe", "-c", "import psutil\nfor p in ...: 'main2.py' in cmd"]
verifier("une sonde qui MENTIONNE main2.py n'est PAS prise pour JARVIS",
         not iu.est_jarvis(SONDE, RACINE))
verifier("un module autre que main2.py n'est pas pris pour JARVIS",
         not iu.est_jarvis(["python.exe", "agenda_scolaire.py"], RACINE))
verifier("une ligne de commande trop courte est rejetee",
         not iu.est_jarvis(["python.exe"], RACINE) and not iu.est_jarvis([], RACINE))

# ── Le dossier compte ────────────────────────────────────────────────────
verifier("un JARVIS lance depuis un AUTRE dossier n'est pas notre affaire",
         not iu.est_jarvis(["python.exe", "main2.py"], AILLEURS))
verifier("sans repertoire de travail connu, on s'abstient",
         not iu.est_jarvis(["python.exe", "main2.py"], None))
verifier("la casse du chemin ne change rien (Windows)",
         iu.est_jarvis(["python.exe", "main2.py"], RACINE.upper()))

# ── Ancetres : jamais touches ────────────────────────────────────────────
if iu.psutil is not None:
    ancetres = iu._ancetres(os.getpid())
    verifier("la chaine des parents est bien retrouvee", len(ancetres) >= 1)
    verifier("le processus courant n'est pas dans ses propres ancetres",
             os.getpid() not in ancetres)

    instances, raison = iu.autres_instances()
    verifier("l'inventaire repond sans exception", isinstance(instances, list))
    verifier("le processus courant ne s'y trouve jamais",
             all(i["pid"] != os.getpid() for i in instances))
    verifier("aucun ancetre ne s'y trouve",
             all(i["pid"] not in ancetres for i in instances))
    print("      (%d autre(s) instance(s) vue(s) a l'instant)" % len(instances))
else:
    verifier("sans psutil, l'inventaire DIT pourquoi au lieu de renvoyer vide",
             iu.autres_instances()[1] != "")

# ── Journal de vie ───────────────────────────────────────────────────────
ligne = iu.journaliser("test : ligne de verification")
verifier("la ligne journalisee porte l'horodatage et le pid",
         "pid=" in ligne and str(os.getpid()) in ligne)
verifier("le fichier de journal est bien dans le dossier JARVIS",
         os.path.dirname(iu.chemin_journal()) == RACINE)
verifier("le journal existe apres ecriture", os.path.exists(iu.chemin_journal()))

contenu = open(iu.chemin_journal(), encoding="utf-8", errors="replace").read()
verifier("la ligne est bien retrouvee dans le fichier",
         "test : ligne de verification" in contenu)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Instance unique : reconnaissance sure, ancetres epargnes, journal ecrit.")
