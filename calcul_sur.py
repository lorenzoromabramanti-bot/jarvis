# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Évaluation d'expressions arithmétiques, sans eval()
=================================================================

CE QUI EXISTAIT
    resultat = eval(expr, {"__builtins__": None}, safe_dict)

Le filtre en amont ne laissait passer que `0-9 + - * / . ( ) , s q r t`.
C'était plus solide qu'il n'y paraît : `pow`, `pi` et `e` sont inatteignables
faute de leurs lettres, et « ouvre __import__(1) » devient « r rt(1) ». Il n'y
avait donc pas d'exécution de code arbitraire.

MAIS IL RESTAIT UNE VRAIE PANNE
    « 9 puissance 9 puissance 9 puissance 9 »  ->  9**9**9**9

Python calcule cela indéfiniment. Mesuré : toujours bloqué après 15 secondes,
processus tué. N'importe qui pouvant envoyer du texte à JARVIS — la voix, la
barre rapide, le WebSocket — pouvait donc le figer pour de bon. Ce n'est pas
une faille théorique dans un fichier, c'est un déni de service à une phrase.

CE QUI LE REMPLACE
On analyse l'expression avec `ast`, et on n'exécute QUE les nœuds autorisés :
nombres, quatre opérations, puissance, parenthèses, signe, et sqrt. Tout le
reste est refusé par construction, pas par filtrage de caractères — une
liste blanche de nœuds ne se contourne pas en trouvant un caractère oublié.

La puissance est bornée AVANT d'être calculée : on estime le nombre de
chiffres du résultat et on refuse au-delà. Vérifier après coup n'aurait servi
à rien, puisque c'est le calcul lui-même qui ne rend jamais la main.

    venv\\Scripts\\python.exe calcul_sur.py
"""

import ast
import math

# Assez pour tout usage honnête : 2**10000 a 3011 chiffres et se calcule
# instantanément. 9**9**9 en aurait 369 millions.
CHIFFRES_MAX = 5000
LONGUEUR_MAX = 300          # une expression dictée n'est jamais si longue

FONCTIONS = {
    "sqrt": math.sqrt,
}

_BINAIRES = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
}


class Refus(ValueError):
    """Expression rejetée. Le message dit pourquoi."""


def _puissance(base, exposant):
    """
    base ** exposant, refusée si le résultat serait démesuré.

    Le contrôle est fait AVANT le calcul : une fois `9**9**9` lancé, Python ne
    rend plus la main et aucun garde-fou postérieur ne s'exécute.
    """
    if isinstance(exposant, float) and not exposant.is_integer():
        # Exposant fractionnaire : pas d'explosion de taille possible.
        return base ** exposant
    if base == 0:
        # Surtout pas « return 0 » : 0**0 vaut 1, et 0**-1 doit lever plutôt
        # que de renvoyer un résultat inventé. Python tranche correctement les
        # trois cas, on le laisse faire.
        return base ** exposant
    chiffres = math.log10(abs(base)) * abs(exposant) if abs(base) != 1 else 0
    if chiffres > CHIFFRES_MAX:
        raise Refus("le résultat aurait environ %d chiffres" % int(chiffres))
    return base ** exposant


def _evaluer(noeud):
    if isinstance(noeud, ast.Expression):
        return _evaluer(noeud.body)

    if isinstance(noeud, ast.Constant):
        if isinstance(noeud.value, bool) or not isinstance(noeud.value, (int, float)):
            raise Refus("seuls les nombres sont acceptés")
        return noeud.value

    if isinstance(noeud, ast.UnaryOp):
        if isinstance(noeud.op, ast.USub):
            return -_evaluer(noeud.operand)
        if isinstance(noeud.op, ast.UAdd):
            return +_evaluer(noeud.operand)
        raise Refus("opérateur unaire non autorisé")

    if isinstance(noeud, ast.BinOp):
        gauche, droite = _evaluer(noeud.left), _evaluer(noeud.right)
        if isinstance(noeud.op, ast.Pow):
            return _puissance(gauche, droite)
        operation = _BINAIRES.get(type(noeud.op))
        if operation is None:
            raise Refus("opérateur non autorisé")
        return operation(gauche, droite)

    if isinstance(noeud, ast.Call):
        if not isinstance(noeud.func, ast.Name) or noeud.func.id not in FONCTIONS:
            raise Refus("fonction non autorisée")
        if noeud.keywords or len(noeud.args) != 1:
            raise Refus("cette fonction prend un seul argument")
        return FONCTIONS[noeud.func.id](_evaluer(noeud.args[0]))

    raise Refus("élément non autorisé : %s" % type(noeud).__name__)


def calculer(expression):
    """
    Évalue une expression arithmétique. Lève Refus si elle n'est pas conforme.

    Ne renvoie jamais None silencieusement : l'appelant doit pouvoir
    distinguer « 0 » d'un refus.
    """
    texte = (expression or "").strip()
    if not texte:
        raise Refus("expression vide")
    if len(texte) > LONGUEUR_MAX:
        raise Refus("expression trop longue (%d caractères)" % len(texte))
    try:
        arbre = ast.parse(texte, mode="eval")
    except SyntaxError as e:
        raise Refus("expression mal formée (%s)" % e.msg)
    try:
        return _evaluer(arbre)
    except (ZeroDivisionError, OverflowError, ValueError) as e:
        # Division par zéro, racine d'un négatif, dépassement : ce sont des
        # refus, pas des pannes. L'appelant n'a qu'un type d'erreur à traiter.
        if isinstance(e, Refus):
            raise
        raise Refus("calcul impossible (%s)" % type(e).__name__)


if __name__ == "__main__":
    import sys
    import time
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    essais = ["2+2", "47*12", "sqrt(144)", "2**10", "(3+4)*5", "10/4",
              "9**9**9**9", "-5+3", "2**0.5", "__import__('os')"]
    print()
    for e in essais:
        debut = time.perf_counter()
        try:
            r = calculer(e)
            etat = str(r)
        except Refus as x:
            etat = "REFUS : %s" % x
        print("  %8.2f ms  %-22s %s" % ((time.perf_counter() - debut) * 1000, e, etat))
