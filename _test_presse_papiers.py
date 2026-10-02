# -*- coding: utf-8 -*-
r"""
Vérifie le presse-papiers intelligent sans appeler le modèle et sans
dépendre de ce qui est copié en ce moment.

CE QU'IL GARDE VRAIMENT
1. Un mode mal orthographié LÈVE, il ne produit pas une consigne vide qui
   partirait au modèle sans instruction.
2. Un texte démesuré est tronqué ET la troncature est dite — sinon le
   résumé porterait sur la moitié du texte sans que personne le sache.
3. « traduis ça » ne vise pas le presse-papiers : les deux mots comptent,
   sinon toute demande de traduction serait détournée.

    venv\Scripts\python.exe _test_presse_papiers.py
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import presse_papiers as pp

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


# ── Consignes ────────────────────────────────────────────────────────────
verifier("les quatre modes annoncés existent",
         set(pp.MODES) == {"traduire", "resumer", "expliquer", "corriger"})

for mode in pp.MODES:
    p = pp.prompt_pour(mode, "Bonjour le monde.")
    verifier("mode %s : la consigne contient le texte source" % mode,
             "Bonjour le monde." in p)
    verifier("mode %s : la consigne porte une instruction" % mode,
             len(p) > len("Bonjour le monde.") + 20)

verifier("« corriger » exige le texte seul, sans commentaire",
         "UNIQUEMENT" in pp.MODES["corriger"])

for mauvais in ("resume", "TRADUIRE", "", None, "fix"):
    try:
        pp.prompt_pour(mauvais, "x")
        verifier("mode inconnu %r refusé" % (mauvais,), False)
    except ValueError:
        verifier("mode inconnu %r refusé" % (mauvais,), True)

# ── Troncature ───────────────────────────────────────────────────────────
long_texte = "mot " * (pp.LIMITE // 2)
p = pp.prompt_pour("resumer", long_texte)
verifier("un texte au-delà de la limite est tronqué",
         len(p) < len(long_texte))
verifier("la troncature est ANNONCÉE dans la consigne", "tronqué" in p)
verifier("un texte court n'est pas annoncé comme tronqué",
         "tronqué" not in pp.prompt_pour("resumer", "court"))

# ── Reconnaissance vocale de la demande ──────────────────────────────────
verifier("« traduis le presse-papiers » -> traduire",
         pp.reconnaitre_mode("Jarvis, traduis le presse-papiers") == "traduire")
verifier("accents et casse ignorés",
         pp.reconnaitre_mode("RESUME LE PRESSE-PAPIER") == "resumer")
verifier("« corrige les fautes du presse-papiers » -> corriger",
         pp.reconnaitre_mode("corrige les fautes du presse papier") == "corriger")
verifier("« explique ce que j'ai copié » -> expliquer",
         pp.reconnaitre_mode("explique ce que j'ai copié") == "expliquer")
verifier("« traduis ça » NE vise PAS le presse-papiers",
         pp.reconnaitre_mode("traduis ça en anglais") is None)
verifier("parler du presse-papiers sans verbe connu ne déclenche rien",
         pp.reconnaitre_mode("qu'y a-t-il dans le presse-papiers ?") is None)

# ── Refus propres ────────────────────────────────────────────────────────
prompt, source, raison = pp.preparer("inconnu")
verifier("preparer() avec un mode inconnu -> raison, pas d'exception",
         not prompt and "mode inconnu" in raison)

ok, raison = pp.ecrire("")
verifier("écrire du vide est refusé, avec la raison", not ok and bool(raison))

# ── Lecture réelle, sans rien exiger de son contenu ──────────────────────
texte, raison = pp.lire()
verifier("lire() renvoie TOUJOURS soit un texte, soit une raison — jamais "
         "un vide muet", bool(texte) != bool(raison))
print("  --  presse-papiers actuel : %s"
      % ("%d caractères" % len(texte) if texte else raison))

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Presse-papiers intelligent : conforme.")
