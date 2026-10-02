# -*- coding: utf-8 -*-
r"""
Vérifie les rappels confiés au Planificateur de tâches, sans en créer un
seul : tout ce qui peut se tromper ici (l'heure visée, l'échappement de la
commande, la lecture de la liste) est calculé avant l'appel système, donc
vérifiable sans lui.

CE QU'IL GARDE VRAIMENT
1. « rappelle-moi à 8h » dit à 22h vise DEMAIN 8h, pas ce matin.
2. Le texte de l'utilisateur ne peut pas casser la commande PowerShell ni
   le XML — une apostrophe dans « j'arrive » suffirait sinon.
3. La date part en ISO, jamais au format local : la même commande ne doit
   pas viser deux jours différents selon la langue de Windows.

    venv\Scripts\python.exe _test_rappels_os.py
"""

import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import rappels_os as r

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


# 15 juin 2026, 22h00 — heure locale, fabriquée sans dépendre de l'horloge.
SOIR = time.mktime((2026, 6, 15, 22, 0, 0, 0, 0, -1))

verifier("heure déjà passée aujourd'hui -> le lendemain",
         r._horodatage("08:00", maintenant=SOIR).startswith("2026-06-16T08:00"))
verifier("heure encore à venir -> aujourd'hui",
         r._horodatage("23:30", maintenant=SOIR).startswith("2026-06-15T23:30"))
verifier("date explicite respectée",
         r._horodatage("07:15", date="2026-12-25", maintenant=SOIR)
         == "2026-12-25T07:15:00")

# Le format ISO est le point de tout le module : pas de jj/mm ni mm/jj.
verifier("l'horodatage est en ISO 8601, insensible à la locale",
         r._horodatage("07:15", date="2026-03-04", maintenant=SOIR)[:10] == "2026-03-04")

for mauvaise in ("8h", "25:00", "08:99", "", None, "0800"):
    try:
        r._horodatage(mauvaise, maintenant=SOIR)
        verifier("heure invalide %r refusée" % (mauvaise,), False)
    except ValueError:
        verifier("heure invalide %r refusée" % (mauvaise,), True)

try:
    r._horodatage("08:00", date="25/12/2026", maintenant=SOIR)
    verifier("date au format local refusée", False)
except ValueError:
    verifier("date au format local refusée", True)

# ── Échappement ──────────────────────────────────────────────────────────
verifier("retours à la ligne aplatis (sinon <Arguments> est cassé)",
         "\n" not in r._texte_sur("deux\nlignes"))

xml = r.construire_xml("réunion & bilan \"annuel\" chez l'agence", "2026-06-16T08:00:00")
verifier("le XML porte l'horodatage voulu", "<StartBoundary>2026-06-16T08:00:00</StartBoundary>" in xml)
verifier("& est échappé dans le XML", "&amp;" in xml and " & " not in xml)
verifier("les guillemets sont échappés dans les arguments", "&quot;" in xml and '"' not in xml.split("<Arguments>")[1].split("</Arguments>")[0])
verifier("l'apostrophe survit intacte dans la description", "chez l'agence" in xml)
verifier("le XML est annoncé en UTF-16, comme schtasks l'attend",
         xml.startswith('<?xml version="1.0" encoding="UTF-16"?>'))
verifier("une seule action, un seul déclenchement",
         xml.count("<TimeTrigger>") == 1 and xml.count("<Exec>") == 1)

# ── #5 : le texte n'entre jamais dans le code PowerShell ─────────────────
# PowerShell traite ‘ ’ ‚ ‛ comme des apostrophes : doubler la seule « ' »
# laissait « appeler’); calc; (’ » lancer calc. Le texte part désormais en
# base64 et n'est décodé qu'à l'exécution.
import base64, html, os, re, subprocess, tempfile
HOSTILES = ("appeler’); calc; (’", "d’appeler l’agence", "a‘b‚c‛d",
            "x'); calc; ('", '"; calc; "', "“”„ $(calc) `n")
for hostile in HOSTILES:
    args = html.unescape(re.search(r"<Arguments>(.*?)</Arguments>",
                                   r.construire_xml(hostile, "2030-01-01T08:00:00"), re.S).group(1))
    b64 = re.search(r"FromBase64String\('([A-Za-z0-9+/=]*)'\)", args)
    verifier("#5 texte en base64 seulement, restitué à l'identique : %r" % hostile[:20],
             b64 and base64.b64decode(b64.group(1)).decode("utf-8") == hostile
             and args.replace(b64.group(1), "") == r._MODELE_COMMANDE % "")

# Rejeu réel, sans fenêtre : la ligne exacte du Planificateur, MessageBox
# remplacée par Write-Output. Le témoin ne doit jamais être créé.
_ps = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
if os.name == "nt" and os.path.exists(_ps):
    temoin = os.path.join(tempfile.mkdtemp(prefix="jarvis_test_rappel_"), "temoin.txt")
    for charge in ("appeler’); Set-Content -LiteralPath %s -Value x; (’" % temoin,
                   "d’appeler’); Set-Content -LiteralPath %s -Value x; (’" % temoin):
        args = html.unescape(re.search(r"<Arguments>(.*?)</Arguments>",
                                       r.construire_xml(charge, "2030-01-01T08:00:00"), re.S).group(1))
        sortie = subprocess.run('"%s" %s' % (_ps, args.replace("[System.Windows.MessageBox]::Show(", "Write-Output (")),
                                capture_output=True, timeout=60)
        verifier("#5 PowerShell réel : l'apostrophe typographique n'exécute rien (%r)" % charge[:12],
                 sortie.returncode == 0 and not os.path.exists(temoin))
    __import__("shutil").rmtree(os.path.dirname(temoin), ignore_errors=True)

texte_long = "a" * 900
verifier("un texte démesuré est tronqué avant la commande",
         len(r._texte_sur(texte_long)) <= 400)

# ── Lecture de la liste ──────────────────────────────────────────────────
SORTIE = (
    '"\\JARVIS_rappel_abcd1234","16/06/2026 08:00:00","Prêt"\n'
    '"\\Microsoft\\Windows\\UpdateOrchestrator\\Reboot","N\\A","Désactivé"\n'
    '"\\JARVIS_rappel_ef567890","17/06/2026 09:30:00","Prêt"\n'
)
lus = r.analyser_query(SORTIE)
verifier("seules les tâches JARVIS sont retenues", len(lus) == 2)
verifier("l'identifiant est nettoyé de son antislash",
         lus[0]["id"] == "JARVIS_rappel_abcd1234")
verifier("la prochaine échéance est lue", lus[0]["prochaine"].startswith("16/06/2026"))
verifier("une sortie vide ne casse rien", r.analyser_query("") == [])

# ── Refus propres ────────────────────────────────────────────────────────
ok, raison = r.programmer("", "08:00")
verifier("un rappel sans texte est refusé, avec la raison",
         not ok and "sans texte" in raison)
ok, raison = r.programmer("acheter du pain", "8h")
verifier("une heure invalide est refusée avant tout appel système",
         not ok and "heure invalide" in raison)
ok, raison = r.supprimer("une_tache_a_moi")
verifier("supprimer une tâche hors préfixe JARVIS est refusé",
         not ok and "identifiant" in raison)

dispo, raison_dispo = r.disponible()
print("  --  disponibilité sur cette machine : %s"
      % ("oui" if dispo else "non — %s" % raison_dispo))

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Rappels système : conforme.")
