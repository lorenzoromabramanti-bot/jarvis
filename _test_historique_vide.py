"""_retenir_echange : une reponse vide n'entre jamais dans l'historique. Lancer : venv/Scripts/python.exe _test_historique_vide.py

Lit la fonction dans main2.py sans l'importer (l'import lance tout JARVIS). Une reponse None d'OmniRoute
empoisonnait l'historique : Gemini refusait ensuite toutes les requetes en 400 (22/10/2026).
"""
import ast
from pathlib import Path

from google.genai import types

src = Path(__file__).with_name("main2.py").read_text(encoding="utf-8")
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "_retenir_echange")
ns = {"historique": [], "types": types}
exec(compile(ast.Module([fn], []), "main2.py", "exec"), ns)
retenir, historique = ns["_retenir_echange"], ns["historique"]

for vide in (None, "", "   \n"):
    assert retenir("question", vide) is False, f"{vide!r} ne doit pas etre retenu"
assert historique == [], "rien d'ajoute pour une reponse vide"
assert retenir("question", "reponse") is True
assert [(c.role, c.parts[0].text) for c in historique] == [("user", "question"), ("model", "reponse")]
# Le seul autre ajout (parler(), ligne prefixee « [Information retournee... ») n'est jamais vide.
assert "parts=[types.Part(text=rep)]" not in src.replace(ast.get_source_segment(src, fn), ""), \
    "une reponse de modele ajoutee sans passer par _retenir_echange"
print("OK : une reponse vide n'entre jamais dans l'historique")
