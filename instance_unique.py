# -*- coding: utf-8 -*-
r"""
J.A.R.V.I.S — Une seule instance, et une trace quand elle s'arrête
===================================================================
Deux problèmes distincts, une seule cause commune : on ne sait jamais quel
JARVIS tourne.

1. LANCER SANS FERMER L'ANCIEN. On relance après une modification, l'ancien
   processus tient toujours le port 8765 ET le microphone. Le nouveau
   démarre, ne peut pas prendre le micro, et l'utilisateur parle à un JARVIS
   qui n'écoute pas — en croyant utiliser la version qu'il vient de modifier.
   `terminer_anciennes()` ferme les autres AVANT que le nouveau s'installe.

2. S'ARRÊTER SANS RIEN DIRE. Constaté deux fois : plus aucun processus, plus
   rien sur 8765, aucune erreur applicative dans le journal Windows, et la
   fenêtre console refermée — donc aucune trace à lire. `armer_traces()`
   écrit le démarrage, l'arrêt et sa cause dans un fichier qui SURVIT à la
   fermeture de la console.

CE QUI N'EST JAMAIS TUÉ
Soi-même, et toute la chaîne des processus parents. Le lanceur
(`DEMARRER_JARVIS.bat` -> venv\Scripts\python.exe -> python.exe) fait partie
de cette chaîne : le tuer tuerait le processus qu'on est en train de démarrer.
Et rien en dehors du dossier d'installation — la comparaison porte sur le
répertoire de travail, pas sur un bout de ligne de commande.

    venv\Scripts\python.exe instance_unique.py
"""

import os
import sys
import time

FICHIER_JOURNAL = "jarvis_vie.log"
DELAI_ARRET_DOUX = 6.0        # secondes laissées à un ancien pour finir proprement

try:
    import psutil
except ImportError:           # sans psutil on ne devine pas : on le DIT
    psutil = None


def _racine():
    return os.path.dirname(os.path.abspath(__file__))


def chemin_journal():
    return os.path.join(_racine(), FICHIER_JOURNAL)


def journaliser(message):
    """
    Ajoute une ligne horodatée au journal de vie. Ne lève jamais.

    Volontairement un simple fichier texte en append : il doit rester
    lisible après un arrêt brutal, sans dépendre d'un module qui pourrait
    être justement celui qui a échoué.
    """
    ligne = "%s  pid=%-6d  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                    os.getpid(), message)
    try:
        with open(chemin_journal(), "a", encoding="utf-8", errors="replace") as f:
            f.write(ligne)
            f.flush()
    except Exception:
        pass
    return ligne


def est_jarvis(cmdline, cwd, racine=None):
    """
    Cette ligne de commande est-elle un vrai lancement de JARVIS ?

    Le contrôle porte sur le DERNIER argument (`... main2.py`) et sur le
    répertoire de travail. Chercher « main2.py » n'importe où dans la ligne
    attraperait un `python -c "...main2.py..."` — un script de diagnostic,
    par exemple — et on tuerait l'outil qui observe au lieu de l'observé.
    C'est arrivé pendant la mise au point de ce module : quatre « instances »
    comptées, dont deux étaient les sondes elles-mêmes.
    """
    racine = os.path.normcase(racine or _racine())
    if not cmdline or len(cmdline) < 2:
        return False
    if os.path.basename(str(cmdline[-1]).strip().strip('"')).lower() != "main2.py":
        return False
    if not cwd:
        return False
    return os.path.normcase(os.path.abspath(cwd)) == racine


def _ancetres(pid):
    """Toute la chaîne des parents, jusqu'à la racine. Jamais à tuer."""
    vus = set()
    try:
        p = psutil.Process(pid)
        while True:
            p = p.parent()
            if p is None or p.pid in vus:
                return vus
            vus.add(p.pid)
    except Exception:
        return vus


def autres_instances(racine=None):
    """
    (instances, raison). Les autres JARVIS lancés depuis ce dossier.

    Sans psutil, renvoie une raison au lieu d'une liste vide : « aucune autre
    instance » et « je ne sais pas regarder » ne sont pas la même chose, et
    l'appelant doit pouvoir le dire à l'utilisateur.
    """
    if psutil is None:
        return [], "psutil n'est pas installé : impossible de voir les autres instances"
    moi = os.getpid()
    interdits = {moi} | _ancetres(moi)
    trouves = []
    for p in psutil.process_iter(["pid", "name"]):
        if p.pid in interdits:
            continue
        try:
            if est_jarvis(p.cmdline(), p.cwd(), racine):
                trouves.append({"pid": p.pid, "age": int(time.time() - p.create_time())})
        except Exception:
            continue          # process disparu ou hors de portée : pas notre affaire
    return trouves, ""


def terminer_anciennes(racine=None, delai=DELAI_ARRET_DOUX):
    """
    Ferme les autres instances. Renvoie un compte rendu.

    D'abord `terminate()` — l'ancien peut relâcher le micro et le port
    proprement — puis `kill()` pour ceux qui n'ont pas obéi dans le délai.
    Chaque décision est journalisée : si un JARVIS disparaît, on doit
    pouvoir lire QUI l'a fermé.
    """
    instances, raison = autres_instances(racine)
    if raison:
        journaliser("demarrage : %s" % raison)
        return {"ok": False, "raison": raison, "tuees": [], "recalcitrantes": []}
    if not instances:
        journaliser("demarrage : aucune autre instance, port et micro libres")
        return {"ok": True, "raison": "", "tuees": [], "recalcitrantes": []}

    objets = []
    for inst in instances:
        try:
            p = psutil.Process(inst["pid"])
            journaliser("demarrage : fermeture de l'instance pid=%d (age %ds)"
                        % (inst["pid"], inst["age"]))
            p.terminate()
            objets.append(p)
        except Exception as e:
            journaliser("demarrage : fermeture impossible pid=%d (%r)" % (inst["pid"], e))

    partis, restants = psutil.wait_procs(objets, timeout=delai)
    for p in restants:
        try:
            journaliser("demarrage : pid=%d n'a pas repondu, arret force" % p.pid)
            p.kill()
        except Exception:
            pass
    if restants:
        psutil.wait_procs(restants, timeout=3)

    return {"ok": True, "raison": "",
            "tuees": [p.pid for p in partis],
            "recalcitrantes": [p.pid for p in restants]}


def armer_traces():
    """
    Fait en sorte qu'un arrêt laisse une trace, quelle qu'en soit la cause.

    Trois filets, parce qu'ils n'attrapent pas les mêmes morts :
      - `faulthandler` écrit la pile sur un plantage natif (segfault dans
        une bibliothèque audio, par exemple), là où Python n'a plus la main ;
      - `atexit` couvre l'arrêt normal et `sys.exit()` ;
      - les signaux couvrent une fermeture demandée de l'extérieur
        (fermeture de la console, `taskkill`, arrêt de session).

    Aucun ne couvre `os._exit()` ni un `kill -9` : c'est justement ce que
    l'absence de ligne « arret » dans le journal permettra de conclure.
    """
    journaliser("demarrage : JARVIS demarre (python %s)" % sys.version.split()[0])

    try:
        import faulthandler
        _f = open(chemin_journal(), "a", encoding="utf-8", errors="replace")
        faulthandler.enable(file=_f, all_threads=True)
    except Exception as e:
        journaliser("demarrage : faulthandler indisponible (%r)" % (e,))

    try:
        import atexit
        atexit.register(lambda: journaliser("arret : sortie normale de l'interpreteur"))
    except Exception:
        pass

    try:
        import signal
        def _sur_signal(numero, _cadre):
            journaliser("arret : signal %s recu" % numero)
            raise SystemExit(128 + int(numero))
        for nom in ("SIGTERM", "SIGINT", "SIGBREAK"):
            numero = getattr(signal, nom, None)
            if numero is not None:
                try:
                    signal.signal(numero, _sur_signal)
                except (ValueError, OSError):
                    pass          # hors du thread principal : sans importance
    except Exception:
        pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    instances, raison = autres_instances()
    print()
    print("=" * 70)
    print("INSTANCES JARVIS")
    print("=" * 70)
    if raison:
        print("  %s" % raison)
    elif not instances:
        print("  aucune autre instance en cours")
    else:
        for i in instances:
            print("  pid %-6d  demarre il y a %d s" % (i["pid"], i["age"]))
    print("  journal de vie : %s" % chemin_journal())
    print("=" * 70)
