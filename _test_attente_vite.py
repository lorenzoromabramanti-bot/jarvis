"""attendre_vite : la fenetre attend un vite lent au lieu de servir le vieux dist/. Lancer : venv/Scripts/python.exe _test_attente_vite.py

Lit la fonction dans main2.py sans l'importer (l'import lance tout JARVIS).
"""
import ast
import time
from pathlib import Path

src = Path(__file__).with_name("main2.py").read_text(encoding="utf-8")
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "attendre_vite")
ns = {"time": time}
exec(compile(ast.Module([fn], []), "main2.py", "exec"), ns)
attendre_vite = ns["attendre_vite"]


class Npm:
    def __init__(self, code=None):
        self.code = code

    def poll(self):
        return self.code


rien = lambda _pas: None
reponses = iter([False, False, True])

assert attendre_vite(Npm(), lambda: True, 0) == "ok"
assert attendre_vite(Npm(1), lambda: False, 60, dormir=rien) == "mort", "npm arrete : pas la peine d'attendre"
assert attendre_vite(Npm(), lambda: False, 0) == "delai", "npm tourne encore : on n'abandonne pas, on le dit"
assert attendre_vite(Npm(), lambda: next(reponses), 60, dormir=rien) == "ok", "vite finit par ouvrir le port"
print("OK : attendre_vite attend vite tant que npm tourne")
