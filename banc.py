"""Banc d'essai de JARVIS : lance tous les _test_*.py et dit ce qui a change depuis le passage precedent.

    venv/Scripts/python.exe banc.py            -> tous les tests, resume, comparaison avec banc-dernier.json
    venv/Scripts/python.exe banc.py calcul     -> seulement les tests dont le nom contient « calcul »

A lancer apres chaque modification : un test qui passait et qui casse est en tete du resume.
Rien en direct : les tests simulent leurs appels (pas de WebSocket, pas de voix, pas de Discord).
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
PYTHON = ICI / "venv" / "Scripts" / "python.exe"
DERNIER = ICI / "banc-dernier.json"


def env_test():
    """Env des tests enfants : PYTHONUTF8 + identité git de secours.

    Un harnais (Paperclip) peut VIDer GIT_AUTHOR_NAME / GIT_COMMITTER_* sans
    qu'aucune config git globale n'existe : les commits des dépôts témoins des
    tests tombent alors avec « empty ident name (for <>) not allowed ». On
    comble chaque variable manquante, sans écraser une identité déjà fournie.
    """
    env = {**os.environ, "PYTHONUTF8": "1"}
    for var, valeur in (("GIT_AUTHOR_NAME", "jarvis-baseline"),
                        ("GIT_AUTHOR_EMAIL", "jarvis@local"),
                        ("GIT_COMMITTER_NAME", "jarvis-baseline"),
                        ("GIT_COMMITTER_EMAIL", "jarvis@local")):
        if not (env.get(var) or "").strip():
            env[var] = valeur
    return env


def lancer(test):
    t0 = time.time()
    try:
        r = subprocess.run([str(PYTHON), test.name], cwd=ICI, capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace", env=env_test(),
                           stdin=subprocess.DEVNULL)
        ok, sortie = r.returncode == 0, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        ok, sortie = False, "plus de 180 s : bloqué ?"
    derniere = sortie.splitlines()[-1] if sortie else ""
    return test.name, {"ok": ok, "s": round(time.time() - t0, 1), "fin": derniere[:160]}


def comparer(avant, apres):
    """(casses depuis la derniere fois, repares, toujours en echec) — listes de noms de tests."""
    casses = [t for t, r in apres.items() if not r["ok"] and avant.get(t, {}).get("ok") is True]
    repares = [t for t, r in apres.items() if r["ok"] and t in avant and not avant[t]["ok"]]
    toujours = [t for t, r in apres.items() if not r["ok"] and t not in casses]
    return casses, repares, toujours


def main():
    filtre = sys.argv[1] if len(sys.argv) > 1 else ""
    tests = sorted(p for p in ICI.glob("_test_*.py") if filtre in p.name)
    t0 = time.time()
    # Un test a la fois : en parallele, les tests de delegation (voix, WebSocket) se genent (08/10/2026).
    apres = dict(map(lancer, tests))
    try:
        avant = json.loads(DERNIER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        avant = {}
    casses, repares, toujours = comparer(avant, apres)
    print(f"{sum(r['ok'] for r in apres.values())}/{len(apres)} tests OK en {time.time() - t0:.0f} s")
    for titre, liste in (("CASSÉ depuis la dernière fois", casses), ("Réparé", repares), ("Toujours en échec", toujours)):
        for t in liste:
            print(f"  {titre} : {t} -> {apres[t]['fin']}")
    if not filtre:  # un passage partiel ne remplace pas la reference
        DERNIER.write_text(json.dumps(apres, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if casses or toujours else 0


def _verifier():
    avant = {"a": {"ok": True}, "b": {"ok": False}, "c": {"ok": False}}
    apres = {"a": {"ok": False}, "b": {"ok": True}, "c": {"ok": False}, "d": {"ok": False}}
    assert comparer(avant, apres) == (["a"], ["b"], ["c", "d"])


if __name__ == "__main__":
    _verifier()
    sys.exit(main())
