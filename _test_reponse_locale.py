"""Test des réponses toutes faites (reponse_locale de main2.py) : elles ne répondent qu'à un message COURT et NU.
La fonction est extraite de main2.py sans l'importer (importer main2 démarre tout JARVIS).
    python _test_reponse_locale.py"""
import ast
import re
import time
from pathlib import Path

source = (Path(__file__).resolve().parent / "main2.py").read_text(encoding="utf-8")
fonction = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "reponse_locale")
espace = {"re": re, "time": time, "nom_utilisateur": lambda: "Alex", "ajouter_memoire": lambda *a: None, "charger_memoire": lambda: {}}
exec(compile(ast.Module(body=[fonction], type_ignores=[]), "main2.py", "exec"), espace)
reponse_locale = espace["reponse_locale"]

TOUTE_FAITE = ["bonjour", "Salut Jarvis", "hey jarvis", "bonsoir", "coucou", "bien le bonjour", "good morning",
               "merci", "merci beaucoup jarvis", "raconte-moi une blague", "fais-moi rire", "dis une blague",
               "au revoir", "bonne nuit", "comment tu vas", "qui es-tu"]
for phrase in TOUTE_FAITE:
    assert reponse_locale(phrase), f"réponse toute faite attendue : {phrase!r}"

# une consigne ou une question n'est PAS une salutation : au modèle (None), jamais une réponse toute faite
AU_MODELE = ["bonjour, quel temps fait-il demain à Paris", "bonjour quel temps fait-il", "merci de me rappeler demain à 8 heures",
             "dis au revoir à ma mère", "ouvre Firefox", "Jarvis ou pas", "non Jarvis", "salut, tu peux ouvrir Firefox",
             "Jarvis dis coucou à ma mère puis explique-moi pourquoi le ciel est bleu", "dis coucou à ma mère et à mon père",
             "dis bonjour à ma mère et demande-lui si elle veut du café"]
for phrase in AU_MODELE:
    assert reponse_locale(phrase) is None, f"devait aller au modèle : {phrase!r} -> {reponse_locale(phrase)!r}"

# « dis coucou à X » : une vraie réponse, jamais « Je suis opérationnel » (essai du 14/11)
for phrase, attendu in (("Jarvis dis coucou à ma mère", "Coucou ! Ici Jarvis"), ("Jarvis dis coucou Camille", "Coucou Camille ! Ici Jarvis"),
                        ("dis bonjour à tout le monde", "Bonjour Tout le monde ! Ici Jarvis"), ("dis salut à mon père", "Salut ! Ici Jarvis")):
    rep = reponse_locale(phrase)
    assert rep and rep.startswith(attendu) and "opérationnel" not in rep and "Alex" in rep, (phrase, rep)
# l'outil « heure » : « quelle heure est-il » oui, « à quelle heure se pose Starship » non (essai du 14/11 : il répondait l'heure qu'il était)
import builtins
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
builtins.get_user_name, builtins.get_user_age = (lambda: "Alex"), (lambda: "34")     # main2 les publie dans builtins
from tools.infos_systeme import resoudre_infos_systeme_localement as infos  # noqa: E402
for phrase in ("quelle heure est-il", "il est quelle heure", "Jarvis quelle heure il est ?"):
    assert infos(phrase) and re.search(r"\d+h\d\d", infos(phrase)), f"l'heure qu'il est était attendue : {phrase!r}"
for phrase in ("Jarvis à quelle heure se pose Starship", "a quelle heure commence le film", "vers quelle heure tu penses qu'il arrive"):
    assert infos(phrase) is None, f"heure d'un événement : au modèle, pas l'heure qu'il est : {phrase!r} -> {infos(phrase)!r}"

# l'aide : le garde de main2.py n'est pas importable sans démarrer JARVIS, on vérifie qu'il est bien là
assert "len(t.split()) <= 7 and DISCORD_SINK.get() is None and any(q in t for q in _aide_questions)" in source, "garde de l'aide absent"
print(f"_test_reponse_locale : {len(TOUTE_FAITE)} réponses toutes faites, {len(AU_MODELE)} messages laissés au modèle, 4 « dis bonjour à… », "
      f"heure d'événement au modèle, aide réservée aux demandes courtes du PC — OK")
