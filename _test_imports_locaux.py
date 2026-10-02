# -*- coding: utf-8 -*-
r"""
Un import local ne doit pas piéger les lignes situées au-dessus de lui.

LE PIÈGE, ET CE QU'IL A COÛTÉ
`resoudre_commandes_locales()` importe `re` en tête de fichier. Six cents
lignes plus bas, dans la branche YouTube, quelqu'un a réécrit `import re`.
Python décide de la portée d'un nom pour la FONCTION ENTIÈRE : à partir de
cet import, `re` est une variable locale partout dans la fonction — y
compris six cents lignes plus haut, où elle n'est pas encore assignée.

Résultat mesuré sur l'installation qui tourne : « supprime la compétence X »
et « exécute la compétence X » levaient UnboundLocalError avant d'atteindre
quoi que ce soit. JARVIS passait de « thinking » à « idle » sans un mot, et
sans rien faire — le fichier n'était pas supprimé, la compétence pas lancée.
Aucun message d'erreur côté utilisateur : exactement le silence que ce dépôt
refuse, mais causé par une règle du langage, pas par une omission.

UNE fonction était réellement touchée : `resoudre_commandes_locales`, pour
`re`. La première version de ce contrôle en avait signalé deux autres
(`generer_image_xai`, `main`) — à tort : leur `import os` vivait dans une
fonction imbriquée, où il ne piège rien. `_propre_a_la_fonction` corrige
cette erreur, et le témoin « imbriqué » plus bas empêche qu'elle revienne.
Ce test interdit le retour du motif dans tout le dépôt.

    venv\Scripts\python.exe _test_imports_locaux.py
"""

import ast
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RACINE = os.path.dirname(os.path.abspath(__file__))
IGNORES = ("venv", ".venv", "__pycache__", "_backups", "_pre_freellm_snapshot",
           "node_modules", "frontend", "webmail", "webmail-desktop", "ios",
           "amorceur", "installeur", "models", "video_gen", "_setup", "mobile")


def fichiers_python():
    for dossier, sous, noms in os.walk(RACINE):
        sous[:] = [d for d in sous if d not in IGNORES and not d.startswith(".")]
        for nom in noms:
            if nom.endswith(".py") and not nom.endswith((".bak", ".bak_asrfix")):
                yield os.path.join(dossier, nom)


def noms_importes_au_module(arbre):
    """Les noms qu'un `import x` en colonne 0 met à disposition de tout le fichier."""
    noms = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Import, ast.ImportFrom)) and n.col_offset == 0:
            for a in n.names:
                noms.add(a.asname or a.name.split(".")[0])
    return noms


def _propre_a_la_fonction(fn):
    """
    Les noeuds du corps de `fn` SEULEMENT, sans descendre dans les fonctions
    imbriquees.

    ast.walk() y descend, lui — et c'est faux ici : un `import os` ecrit dans
    une fonction imbriquee ne rend `os` local qu'a ELLE, pas a la fonction qui
    la contient. Sans cette limite, le controle a signale trois fonctions
    saines de main2.py (leur `import os` etait dans un gestionnaire de
    fermeture imbrique). Un test qui crie au loup fait desapprendre a l'ecouter.
    """
    frontiere = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
    a_visiter = list(ast.iter_child_nodes(fn))
    while a_visiter:
        noeud = a_visiter.pop()
        yield noeud
        if not isinstance(noeud, frontiere):
            a_visiter.extend(ast.iter_child_nodes(noeud))


def pieges(chemin):
    """[(fonction, nom, ligne_usage, ligne_import)] pour un fichier."""
    try:
        arbre = ast.parse(io.open(chemin, encoding="utf-8", errors="replace").read())
    except SyntaxError:
        return []      # un fichier illisible est le problème d'un autre test
    globaux = noms_importes_au_module(arbre)
    trouves = []
    for fn in ast.walk(arbre):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Premier import LOCAL de chaque nom déjà connu au niveau module.
        propres = list(_propre_a_la_fonction(fn))
        locaux = {}
        for n in propres:
            if isinstance(n, ast.Import):
                for a in n.names:
                    nom = a.asname or a.name.split(".")[0]
                    if nom in globaux:
                        locaux[nom] = min(locaux.get(nom, n.lineno), n.lineno)
        for nom, ligne_import in locaux.items():
            usages = [u.lineno for u in propres
                      if isinstance(u, ast.Name) and u.id == nom
                      and u.lineno < ligne_import]
            if usages:
                trouves.append((fn.name, nom, min(usages), ligne_import))
    return trouves


echecs = []
fichiers = 0
for chemin in fichiers_python():
    fichiers += 1
    for fonction, nom, usage, imp in pieges(chemin):
        relatif = os.path.relpath(chemin, RACINE)
        echecs.append("%s : %s() utilise '%s' ligne %d, mais l'importe "
                      "localement ligne %d — UnboundLocalError garanti"
                      % (relatif, fonction, nom, usage, imp))

# Le contrôle doit ATTRAPER le motif, sinon il ne prouve rien.
TEMOIN = "import os\n\ndef f():\n    p = os.sep\n    import os\n    return p, os\n"
temoin = os.path.join(RACINE, "_temoin_import_local.py")
io.open(temoin, "w", encoding="utf-8", newline="\n").write(TEMOIN)
try:
    detecte = pieges(temoin)
finally:
    os.remove(temoin)

# Le meme motif, mais l'import est dans une fonction IMBRIQUEE : `os` n'est
# alors local qu'a elle, la fonction englobante n'a aucun probleme. Le
# controle doit rester MUET dessus, sinon il signale du code sain.
TEMOIN_SAIN = ("import os\n\ndef f():\n    p = os.sep\n"
               "    def g():\n        import os\n        return os.sep\n"
               "    return p, g\n")
sain = os.path.join(RACINE, "_temoin_import_imbrique.py")
io.open(sain, "w", encoding="utf-8", newline="\n").write(TEMOIN_SAIN)
try:
    faux_positif = pieges(sain)
finally:
    os.remove(sain)

print()
print("  %d fichiers analyses" % fichiers)
if detecte and detecte[0][1] == "os":
    print("  OK  le controle detecte reellement le motif (temoin)")
else:
    echecs.append("le controle ne detecte PAS le motif : il ne prouve rien")
if faux_positif:
    echecs.append("le controle signale a tort un import dans une fonction IMBRIQUEE")
else:
    print("  OK  un import dans une fonction imbriquee n'est PAS signale")

for e in echecs:
    print("  X   %s" % e)
print()
if echecs:
    print("ECHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Imports locaux : aucun nom de module piege par un import place plus bas.")
