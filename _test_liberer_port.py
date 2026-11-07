"""liberer_port ne doit viser que le port exact sur toutes les interfaces. Lancer : venv/Scripts/python.exe _test_liberer_port.py

Lit la fonction dans main2.py sans l'importer (l'import lance tout JARVIS).
"""
import ast
from pathlib import Path

src = Path(__file__).with_name("main2.py").read_text(encoding="utf-8")
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "pid_ecoute_toutes_interfaces")
ns = {}
exec(compile(ast.Module([fn], []), "main2.py", "exec"), ns)
pid_ecoute = ns["pid_ecoute_toutes_interfaces"]

NETSTAT = """
  TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING       2868
  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       4410
  TCP    0.0.0.0:8001           0.0.0.0:0              LISTENING       5120
  TCP    0.0.0.0:8443           0.0.0.0:0              LISTENING       6230
  TCP    127.0.0.1:8765         127.0.0.1:54461        ESTABLISHED     2868
  TCP    [::]:8765              [::]:0                 LISTENING       7000
"""

assert pid_ecoute(NETSTAT, 8000) == 2868, "l'instance JARVIS sur 0.0.0.0:8000, pas ShadowBroker (127.0.0.1)"
assert pid_ecoute(NETSTAT, 80) is None, "« :80 » ne doit plus attraper 8000, 8001 ou 8443"
assert pid_ecoute(NETSTAT, 8765) == 7000, "IPv6 toutes interfaces, pas une connexion etablie"
assert pid_ecoute(NETSTAT.replace("0.0.0.0:8000 ", "0.0.0.0:9999 "), 8000) is None, "seul ShadowBroker reste : on n'y touche pas"
print("OK : liberer_port vise le bon processus")
