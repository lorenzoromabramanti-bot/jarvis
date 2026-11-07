# -*- coding: utf-8 -*-
"""
Verifie le verrou pose sur CONNECTED_CLIENTS (LOR-6), sans reseau.

Le set est partage entre la boucle WebSocket (thread dedie, qui ajoute et
retire) et les diffusions partant de la boucle principale, de boucles
temporaires et des threads d'arriere-plan. Sans verrou, une iteration en
comprehension lancee pendant une connexion/deconnexion echoue avec
« RuntimeError: Set changed size during iteration » — d'ou des envois
manquants.

Quatre controles :
  1. structure — le set est bien une instance verrouillee (mutations et
     __iter__ surcharges, pas ceux de set) ;
  2. copie — list() renvoie bien une copie figee, pas une vue vivante ;
  3. conducteur de course — un thread mute pendant que l'autre itere en
     comprehension : 0 erreur sur les clients proteges, alors qu'un set nu
     en produit ( controle negatif : le test sait voir le bug ) ;
  4. envois — send_web_broadcast_sync appele depuis un thread pendant des
     connexions/deconnexions : le client stable recoit tout, sans manque.

    venv\\Scripts\\python.exe _test_clients_web.py
"""

import builtins
import sys
import threading
import time

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


import main2


# ---------------------------------------------------------------- 1. structure
C = main2.CONNECTED_CLIENTS
verifier("CONNECTED_CLIENTS reste un set (isinstance)",
         isinstance(C, set), type(C))
verifier("CONNECTED_CLIENTS est bien l'objet expose sur builtins",
         C is getattr(builtins, "CONNECTED_CLIENTS", None))
verifier("le verrou existe et est un verrou threading "
         "(pas asyncio.Lock : les envois partent d'autres threads)",
         isinstance(getattr(type(C), "_verrou", None), type(threading.Lock())),
         getattr(type(C), "_verrou", None))
verifier("add() surcharge (et non set.add)",
         type(C).add is not set.add)
verifier("discard() surcharge (et non set.discard)",
         type(C).discard is not set.discard)
verifier("__iter__ surcharge (et non set.__iter__)",
         type(C).__iter__ is not set.__iter__)


# -------------------------------------------------------------------- 2. copie
FAUX = object()
try:
    C.add(FAUX)
    vue = list(C)
    C.discard(FAUX)
    vue_apres = list(C)
    verifier("list() renvoie une copie contenant le client ajoute",
             FAUX in vue, vue)
    verifier("... et cette copie ne change plus apres un retrait "
             "(pas de vue vivante)", FAUX in vue and FAUX not in vue_apres,
             (vue, vue_apres))
finally:
    C.discard(FAUX)


# ------------------------------------------------------- 3. conducteur de course
def conducteur(cible, duree=0.5, taille=100):
    """Un thread itere en comprehension, un autre ajoute/retrait."""
    erreurs = [0]
    arret = threading.Event()
    for i in range(taille):
        cible.add("tmp%d" % i)

    def boucle_iteration():
        while not arret.is_set():
            try:
                [ws for ws in cible]
            except RuntimeError:
                erreurs[0] += 1

    def boucle_mutation():
        while not arret.is_set():
            for i in range(5):
                cible.add("vivant%d" % i)
            for i in range(5):
                cible.discard("vivant%d" % i)

    fils = [threading.Thread(target=boucle_iteration),
            threading.Thread(target=boucle_mutation)]
    for f in fils:
        f.start()
    time.sleep(duree)
    arret.set()
    for f in fils:
        f.join()
    for i in range(taille):
        cible.discard("tmp%d" % i)
    return erreurs[0]


erreurs_nu = conducteur(set())
verifier("controle negatif : un set nu produit bien « Set changed size "
         "during iteration » (le test sait voir le bug)",
         erreurs_nu >= 1, "%d RuntimeError observe(s)" % erreurs_nu)

erreurs_clients = conducteur(C)
verifier("aucune erreur d'iteration sur CONNECTED_CLIENTS verrouille",
         erreurs_clients == 0, "%d RuntimeError" % erreurs_clients)
verifier("... et le set est propre apres le conducteur "
         "(pas d'entrees fantome)",
         len(C) == 0, sorted(map(str, C)))


# ------------------------------------------------------------------- 4. envois
class FauxClient:
    """Client WebSocket factice : compte les messages recus."""

    def __init__(self, nom):
        self.nom = nom
        self.recus = 0

    async def send(self, message):
        self.recus += 1


stabilisateur = {"loop": None}


def envoi_sous_charge():
    """25 diffusions depuis ce thread pendant que l'autre connecte/deconnecte."""
    stabilisateur["loop"] = main2.WEB_LOOP
    main2.WEB_LOOP = None          # chemin de repli : boucle creee sur place
    stable = FauxClient("stable")
    main2.CONNECTED_CLIENTS.add(stable)
    arret = threading.Event()
    erreurs_mutateur = []

    def mutateur():
        try:
            while not arret.is_set():
                ephemere = FauxClient("ephemere")
                main2.CONNECTED_CLIENTS.add(ephemere)
                main2.CONNECTED_CLIENTS.discard(ephemere)
        except Exception as e:                      # pragma: no cover
            erreurs_mutateur.append(repr(e))

    f = threading.Thread(target=mutateur)
    f.start()
    try:
        nb = 25
        for i in range(nb):
            main2.send_web_broadcast_sync({"action": "test_lor6", "n": i})
    finally:
        arret.set()
        f.join()
        main2.CONNECTED_CLIENTS.discard(stable)
        main2.WEB_LOOP = stabilisateur["loop"]
    return stable.recus, nb, erreurs_mutateur


recus, voulus, erreurs_mut = envoi_sous_charge()
verifier("aucune erreur du cote mutation pendant les envois",
         not erreurs_mut, erreurs_mut)
verifier("le client stable recoit toutes les diffusions (pas d'envoi "
         "manquant pendant connexions/deconnexions)",
         recus == voulus, "%d/%d recus" % (recus, voulus))


print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("CONNECTED_CLIENTS verrouille (LOR-6) : conforme.")
