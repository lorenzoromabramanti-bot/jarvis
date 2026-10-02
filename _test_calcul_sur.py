# -*- coding: utf-8 -*-
"""
Verifie l'evaluateur arithmetique qui remplace eval().

Ce qui est teste n'est pas « ca calcule juste » — c'est facile — mais que
l'expression qui FIGEAIT JARVIS soit refusee, et qu'aucun eval() ne revienne.

    « 9 puissance 9 puissance 9 puissance 9 »  ->  9**9**9**9

Python calcule cela sans jamais rendre la main : mesure, toujours bloque
apres 15 secondes, processus tue. La voix, la barre rapide et le WebSocket y
menaient tous.

    venv\\Scripts\\python.exe _test_calcul_sur.py
"""

import io
import math
import os
import sys
import time

from calcul_sur import CHIFFRES_MAX, Refus, calculer

ICI = os.path.dirname(os.path.abspath(__file__))


def verifier():
    # ── Ce qui doit marcher ─────────────────────────────────────────────
    justes = [
        ("2+2", 4), ("47*12", 564), ("100/8", 12.5), ("(3+4)*5", 35),
        ("2**10", 1024), ("-5+3", -2), ("7%3", 1), ("7//2", 3),
        ("sqrt(144)", 12.0), ("2**0.5", math.sqrt(2)), ("3.5*2", 7.0),
        ("0**0", 1), ("-2**2", -4),
    ]
    for expr, attendu in justes:
        obtenu = calculer(expr)
        assert abs(obtenu - attendu) < 1e-9, "%s = %r, attendu %r" % (expr, obtenu, attendu)
    print("  OK  %d expressions correctes" % len(justes))

    # ── La bombe, et ses variantes ──────────────────────────────────────
    bombes = ["9**9**9**9", "9**9**9", "10**999999999", "2**(10**10)",
              "99999**99999"]
    for expr in bombes:
        debut = time.perf_counter()
        try:
            calculer(expr)
            raise AssertionError("%s n'a PAS ete refusee" % expr)
        except Refus:
            pass
        ms = (time.perf_counter() - debut) * 1000
        assert ms < 200, "%s a pris %.0f ms — le refus doit etre immediat" % (expr, ms)
    print("  OK  %d bombes exponentielles refusees, sans calcul" % len(bombes))

    # Une puissance honnete reste possible : la borne ne doit pas gener.
    assert calculer("2**10000") > 0, "une puissance legitime a ete refusee"
    print("  OK  2**10000 (3011 chiffres) toujours accepte")

    # ── Ce qui doit etre refuse ─────────────────────────────────────────
    interdits = [
        "__import__('os')", "open('x')", "exec('1')", "pow(2,3)",
        "[1,2,3]", "{'a':1}", "1 if 2 else 3", "lambda: 1",
        "x", "sqrt", "sqrt(1,2)", "1;2", "", "   ",
        "True", "None", "'texte'", "1 and 2", "not 1",
    ]
    for expr in interdits:
        try:
            calculer(expr)
            raise AssertionError("%r a ete accepte" % expr)
        except Refus:
            pass
    print("  OK  %d expressions interdites refusees" % len(interdits))

    # Une expression demesurement longue : refus avant analyse.
    try:
        calculer("1+" * 500 + "1")
        raise AssertionError("une expression de 1500 caracteres est passee")
    except Refus:
        pass
    print("  OK  expression trop longue refusee")

    # ── Le refus explique ───────────────────────────────────────────────
    try:
        calculer("9**9**9**9")
    except Refus as e:
        assert "chiffres" in str(e), "le refus n'explique pas : %s" % e
    print("  OK  le refus dit pourquoi")

    # ── eval() ne doit pas revenir ──────────────────────────────────────
    src = io.open(os.path.join(ICI, "main2.py"), encoding="utf-8").read()
    fautifs = [(i, l.strip()) for i, l in enumerate(src.splitlines(), 1)
               if "eval(" in l and "evaluate_js" not in l
               and not l.strip().startswith("#")]
    assert not fautifs, "eval() est revenu dans main2.py : %s" % fautifs[:3]
    print("  OK  aucun eval() dans main2.py")

    assert CHIFFRES_MAX >= 1000, "la borne est devenue trop stricte"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Calcul sans eval : conforme.")
