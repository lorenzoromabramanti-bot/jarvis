# -*- coding: utf-8 -*-
r"""
J.A.R.V.I.S — Rappels confiés au système (Planificateur de tâches)
===================================================================
`boucle_rappels()` dans main2.py réveille l'utilisateur tant que JARVIS
tourne. Fermez JARVIS, redémarrez la machine : le rappel de 18h n'existe
plus. Personne n'est prévenu — c'est exactement le genre de silence que ce
dépôt refuse.

Ce module confie le rappel au SYSTÈME. Une fois posé, il se déclenche même
si JARVIS est éteint, même après un redémarrage. Les deux mécanismes
coexistent : le rappel en mémoire pour « dans dix minutes », celui-ci pour
« demain matin » et tout ce qui traverse une extinction.

POURQUOI UN XML ET PAS `schtasks /SC ONCE /ST /SD`
L'option /SD attend la date au format LOCAL (jj/mm/aaaa ici, mm/jj/aaaa sur
un Windows anglais). La même commande poserait donc le rappel du 3 avril au
4 mars selon la machine, sans erreur visible. Le XML de tâche utilise
l'ISO 8601, qui ne dépend d'aucune locale.

CE MODULE NE MARCHE QUE SOUS WINDOWS
Ailleurs, `disponible()` dit pourquoi, et `programmer()` refuse au lieu de
prétendre avoir posé un rappel qui n'existera jamais.

    venv\Scripts\python.exe rappels_os.py
"""

import base64
import io
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from xml.sax.saxutils import escape as _xml_echap

PREFIXE = "JARVIS_rappel_"

# Fenêtre affichée à l'échéance. PresentationFramework est livré avec
# Windows : aucune dépendance à installer, contrairement à BurntToast.
#
# Le texte n'entre JAMAIS dans le code PowerShell : il y arrive en base64
# (alphabet A-Z a-z 0-9 + / =, incapable de fermer une chaîne) et n'est
# décodé qu'à l'exécution. Doubler l'apostrophe droite ne suffisait pas :
# PowerShell traite aussi ‘ ’ ‚ ‛ comme des apostrophes, et « d’appeler’);
# calc; (’ » lançait calc — or c'est la ponctuation par défaut d'un iPhone.
_MODELE_COMMANDE = (
    "-NoProfile -WindowStyle Hidden -Command "
    "\"Add-Type -AssemblyName PresentationFramework; "
    "[System.Windows.MessageBox]::Show([Text.Encoding]::UTF8.GetString("
    "[Convert]::FromBase64String('%s')),'J.A.R.V.I.S')\""
)

_GABARIT_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>%(description)s</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>%(debut)s</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>%(arguments)s</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def disponible():
    """(ok, raison). Windows + schtasks présents, ou la raison de l'absence."""
    if os.name != "nt":
        return False, "les rappels système ne sont disponibles que sous Windows"
    if not os.path.exists(_schtasks()):
        return False, "schtasks.exe est introuvable sur cette machine"
    return True, ""


def _schtasks():
    r"""
    Chemin ABSOLU vers schtasks.exe.

    Un Python 32 bits sur un Windows 64 bits ne voit pas le vrai System32 :
    la redirection WOW64 l'envoie dans SysWOW64, où schtasks.exe n'est pas.
    « schtasks » tout court y échouerait avec « fichier introuvable » sans
    dire pourquoi. C:\Windows\Sysnative traverse la redirection.
    """
    racine = os.environ.get("SystemRoot", r"C:\Windows")
    direct = os.path.join(racine, "System32", "schtasks.exe")
    if os.path.exists(direct):
        return direct
    return os.path.join(racine, "Sysnative", "schtasks.exe")


def _horodatage(heure, date=None, maintenant=None):
    """
    L'instant ISO 8601 du déclenchement, à partir de « HH:MM » (+ date).

    Sans date, la PROCHAINE occurrence : si l'heure est déjà passée
    aujourd'hui, c'est demain. Même règle que taches_nocturnes._heure_arrivee,
    et pour la même raison — « rappelle-moi à 8h » dit à 22h ne veut pas dire
    « il y a quatorze heures ».
    """
    if not re.match(r"^\d{2}:\d{2}$", str(heure or "")):
        raise ValueError("heure invalide : %r (attendu HH:MM)" % (heure,))
    h, m = (int(x) for x in heure.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("heure hors plage : %r" % (heure,))

    base = time.localtime(maintenant if maintenant is not None else time.time())
    if date:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date)):
            raise ValueError("date invalide : %r (attendu AAAA-MM-JJ)" % (date,))
        a, mo, j = (int(x) for x in date.split("-"))
        cible = time.mktime((a, mo, j, h, m, 0, 0, 0, -1))
    else:
        cible = time.mktime((base.tm_year, base.tm_mon, base.tm_mday, h, m, 0, 0, 0, -1))
        if cible <= time.mktime(base):
            cible += 86400
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(cible))


def _texte_sur(texte):
    """
    Le texte du rappel, aplati sur une ligne et borné. Il ne sert plus que
    de donnée (base64 dans la commande, échappement XML dans la description) :
    aucun caractère n'a à y être neutralisé.
    """
    return re.sub(r"\s+", " ", str(texte or "")).strip()[:400]


def construire_xml(texte, debut):
    """Le XML de la tâche. Séparé de l'appel système pour être vérifiable."""
    arguments = _MODELE_COMMANDE % base64.b64encode(
        _texte_sur(texte).encode("utf-8")).decode("ascii")
    return _GABARIT_XML % {
        "description": _xml_echap("Rappel J.A.R.V.I.S : %s" % _texte_sur(texte)),
        "debut": debut,
        "arguments": _xml_echap(arguments, {'"': "&quot;"}),
    }


def programmer(texte, heure, date=None):
    """
    Pose un rappel dans le Planificateur de tâches. Renvoie (ok, id | raison).

    Le rappel survit à la fermeture de JARVIS et au redémarrage. Il ne se
    répète pas : une tâche, un déclenchement.
    """
    ok, raison = disponible()
    if not ok:
        return False, raison
    if not str(texte or "").strip():
        return False, "un rappel sans texte ne rappellerait rien"
    try:
        debut = _horodatage(heure, date)
    except ValueError as e:
        return False, str(e)

    nom = PREFIXE + uuid.uuid4().hex[:8]
    fichier = os.path.join(tempfile.gettempdir(), nom + ".xml")
    try:
        io.open(fichier, "w", encoding="utf-16", newline="\r\n").write(
            construire_xml(texte, debut))
        r = subprocess.run([_schtasks(), "/Create", "/TN", nom, "/XML", fichier, "/F"],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "schtasks a échoué").strip()
        return True, nom
    except (OSError, subprocess.SubprocessError) as e:
        return False, "création impossible : %s" % e
    finally:
        try:
            os.remove(fichier)
        except OSError:
            pass


def lister():
    """Les rappels système posés par JARVIS. Liste vide si aucun, jamais None."""
    ok, _ = disponible()
    if not ok:
        return []
    try:
        r = subprocess.run([_schtasks(), "/Query", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return analyser_query(r.stdout)


def analyser_query(sortie_csv):
    """
    Les rappels JARVIS dans une sortie `schtasks /Query /FO CSV /NH`.

    Séparé de l'appel système : c'est la partie qui peut se tromper, donc
    celle qui doit être vérifiable sans créer de vraie tâche.
    """
    rappels = []
    for ligne in (sortie_csv or "").splitlines():
        champs = [c.strip().strip('"') for c in ligne.split('","')]
        if len(champs) < 2:
            continue
        nom = champs[0].strip('"').lstrip("\\")
        if nom.startswith(PREFIXE):
            rappels.append({"id": nom, "prochaine": champs[1],
                            "statut": champs[2] if len(champs) > 2 else ""})
    return rappels


def supprimer(id_rappel):
    """Retire un rappel système. Renvoie (ok, raison)."""
    ok, raison = disponible()
    if not ok:
        return False, raison
    if not str(id_rappel or "").startswith(PREFIXE):
        return False, "identifiant inattendu : %r" % (id_rappel,)
    try:
        r = subprocess.run([_schtasks(), "/Delete", "/TN", str(id_rappel), "/F"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        return False, "suppression impossible : %s" % e
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "schtasks a échoué").strip()
    return True, "supprimé"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok, raison = disponible()
    print()
    print("=" * 70)
    print("RAPPELS SYSTÈME")
    print("=" * 70)
    if not ok:
        print("  indisponible : %s" % raison)
    else:
        rappels = lister()
        if not rappels:
            print("  aucun rappel système posé par JARVIS")
        for r in rappels:
            print("  %-24s %s  %s" % (r["id"], r["prochaine"], r["statut"]))
    print("=" * 70)
