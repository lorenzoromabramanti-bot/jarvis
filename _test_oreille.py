# -*- coding: utf-8 -*-
"""L'oreille (oreille.py) : découpage des phrases (Silero), écho de JARVIS, coupure, et client côté JARVIS.
Sans micro ni modèle.

    venv\\Scripts\\python.exe _test_oreille.py
"""
import json
import os
import tempfile
import urllib.error

import oreille

# --- Découpeur : début dès que Silero entend de la parole (avec 0,3 s d'avant), fin après 0,5 s de silence
T = 0.032
d = oreille.Decoupeur()
trames = [(b"s", 0.05)] * 40 + [(b"p", 0.9)] * 25 + [(b"s", 0.1)] * 16   # 1,28 s de bruit, 0,8 s de parole, 0,5 s de silence
fins = [r for i, (pcm, prob) in enumerate(trames) if (r := d.pousser(pcm, prob, i * T))]
assert len(fins) == 1, fins
pcm, t_debut, t_fin = fins[0]
n_avant = d.avant.maxlen - 1  # trames de bruit gardées avant le 1er « p » (1 s, la 1re trame de parole comprise)
assert pcm.count(b"p") == 25 and pcm.startswith(b"s" * n_avant), "la seconde d'avant garde le « Jarvis » faible"
assert abs(t_debut - (40 - n_avant) * T) < 1e-9 and abs(t_fin - 80 * T) < 1e-9, (t_debut, t_fin)
# un claquement de 0,1 s n'est pas une phrase ; une hésitation de 0,3 s ne coupe pas la phrase
d = oreille.Decoupeur()
assert not [r for i, (p, q) in enumerate([(b"p", 0.9)] * 3 + [(b"s", 0.1)] * 20) if (r := d.pousser(p, q, i * T))]
d = oreille.Decoupeur()
suite = [(b"p", 0.9)] * 15 + [(b"s", 0.1)] * 9 + [(b"p", 0.9)] * 15 + [(b"s", 0.1)] * 16
fins = [r for i, (p, q) in enumerate(suite) if (r := d.pousser(p, q, i * T))]
assert len(fins) == 1 and fins[0][0].count(b"p") == 30, "une pause de 0,29 s reste dans la même phrase"
# plus de 15 s d'affilée : coupée quand même
d = oreille.Decoupeur()
assert [r for i in range(500) if (r := d.pousser(b"p", 0.9, i * T))], "max 15 s"

# --- Écho, coupure, tri
DIT = "La tour Eiffel a été construite pour l'exposition universelle de 1889."
assert oreille.est_echo("la tour eiffel a été construite", DIT) and not oreille.est_echo("stop arrête toi", DIT)
assert oreille.trier("quelle heure est-il", parlait=False, dit=DIT) == "garder"
assert oreille.trier("construite pour l'exposition universelle", parlait=True, dit=DIT) == "jeter", "sa propre voix"
assert oreille.trier("Stop !", parlait=True, dit=DIT) == "couper"
assert oreille.trier("Jarvis, attends, plutôt la météo", parlait=True, dit=DIT) == "couper"
assert oreille.trier("il fait beau dehors", parlait=True, dit=DIT) == "jeter", "pendant qu'il parle, seul un ordre de coupure passe"
assert oreille.trier("universelle de 1889 à Paris stop", parlait=True, dit=DIT + " à Paris.") == "couper", "« stop » mêlé à son écho"
assert oreille.trier("stop", parlait=True, dit="Appuie sur stop pour arrêter.") == "jeter", "il dit « stop » lui-même"
assert oreille.trier("Je suis Jarvis", parlait=True, dit="Bonjour, je suis Jarvis, ton assistant.") == "jeter", "il dit son nom : écho"
for seule in ("stop", "Stop !", "Jarvis, stop.", "attends", "arrête-toi", "c'est bon", "Jarvis attends !"):
    assert oreille.est_coupure_seule(seule), seule
for pas in ("jarvis, attends, plutôt la météo", "stop la musique", "tais-toi", "silence", "quelle heure est-il"):
    assert not oreille.est_coupure_seule(pas), pas

# --- Client côté JARVIS
with tempfile.TemporaryDirectory() as t:
    vrai_jeu, vrai_url, vraie_config = oreille.ACTIF_JEU, oreille.URL, oreille.CONFIG
    oreille.ACTIF_JEU, oreille.URL = os.path.join(t, "actif.json"), "http://127.0.0.1:9"  # port fermé
    oreille.CONFIG = os.path.join(t, "jarvis_config.json")  # pas la vraie : « oreille_en_jeu » y est peut-être
    try:
        lances = []
        lancer = lambda argv, **k: lances.append(argv)  # noqa: E731
        PCM = b"\x00\x01" * 1600
        assert oreille.transcrire(PCM, envoyer=lambda p: "quelle heure est-il") == "quelle heure est-il"
        assert oreille.transcrire(b"", envoyer=lambda p: "x") is None
        with open(oreille.ACTIF_JEU, "w", encoding="utf-8") as f:
            json.dump({"jeu": "Geometry Dash"}, f)
        assert oreille.transcrire(PCM, envoyer=lambda p: "x", lancer=lancer) is None and lances == []
        assert oreille.prochaine_phrase(requete=lambda *a, **k: (200, {"texte": "x"})) is None, "partie : écoute d'avant"
        with open(oreille.CONFIG, "w", encoding="utf-8") as f:
            json.dump({"oreille_en_jeu": True}, f)
        assert not oreille.jeu_en_cours(), "oreille_en_jeu : elle reste allumée pendant la partie"
        assert oreille.prochaine_phrase(requete=lambda *a, **k: (200, {"texte": "x"})) == "x"
        os.remove(oreille.CONFIG)
        os.remove(oreille.ACTIF_JEU)
        oreille._etat["lancement"] = 0.0
        assert oreille.transcrire(PCM, lancer=lancer) is None and len(lances) == 1
        assert oreille.transcrire(PCM, lancer=lancer) is None and len(lances) == 1, "au plus 1 démarrage / 2 min"

        def pas_prete(*a, **k):
            raise urllib.error.HTTPError(oreille.URL, 503, "chargement", {}, None)
        assert oreille.prochaine_phrase(requete=lambda *a, **k: (200, {"texte": "Jarvis, ça va ?"})) == "Jarvis, ça va ?"
        assert oreille.prochaine_phrase(requete=lambda *a, **k: (204, None)) == "", "rien entendu"
        assert oreille.prochaine_phrase(requete=pas_prete) is None, "en chargement : écoute d'avant"
        assert oreille.interruption(requete=lambda *a, **k: (200, {"couper": True})) is True
        assert oreille.interruption() is False, "oreille absente : jamais d'interruption"
        envoye = []
        oreille.signaler_parole(True, "bonjour", requete=lambda c, b=None, **k: envoye.append((c, b)))
        assert envoye == [("/parle", {"actif": True, "texte": "bonjour"})]
        oreille.signaler_parole(False)  # oreille absente : sans erreur
    finally:
        oreille.ACTIF_JEU, oreille.URL, oreille.CONFIG = vrai_jeu, vrai_url, vraie_config
        oreille._etat["lancement"] = 0.0

# --- Éveil local : le « Jarvis » du détecteur rattaché aux phrases de Silero
e = oreille.Eveil(seuil=0.5)
assert not e.score(0.3, 10.0, False), "sous le seuil"
assert not e.score(0.9, 10.0, True), "jamais pendant que JARVIS parle : « Jarvis » dans sa propre voix"
assert e.score(0.9, 10.0, False) and not e.score(0.95, 10.5, False), "un éveil, puis 1,6 s sans doublon"
assert e.phrase(9.4, 11.0) and not e.seul(13.0, False), "la phrase le porte : pas de « Jarvis » seul en plus"
e = oreille.Eveil(seuil=0.5)
assert e.score(0.9, 20.0, False)
assert not e.seul(20.5, False), "0,8 s d'attente : une phrase peut suivre"
assert not e.seul(21.0, True), "une phrase est en cours : elle le portera"
assert e.seul(21.0, False) and not e.seul(22.0, False), "« Jarvis » seul, livré une seule fois"
e = oreille.Eveil(seuil=0.5)
assert not e.phrase(28.0, 29.5) and e.score(0.9, 30.0, False)
assert not e.seul(31.0, False), "une phrase vient de finir : c'est elle qui portait « Jarvis »"
assert oreille.completer("quelle heure est-il", True) == "Jarvis, quelle heure est-il"
assert oreille.completer("", True) == "Jarvis", "Google n'a rien compris, le détecteur a entendu « Jarvis »"
assert oreille.completer("Jarvis, ça va ?", True) == "Jarvis, ça va ?", "déjà dans la phrase"
assert oreille.completer("quelle heure est-il", False) == "quelle heure est-il"
vraie_config = oreille.CONFIG
try:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"eveil_local": False}, f)
    oreille.CONFIG = f.name
    assert oreille._detecteur()[0] is None, "désactivé dans la config"
    with open(f.name, "w", encoding="utf-8") as g:
        json.dump({"wake_word": "friday"}, g)
    assert oreille._detecteur()[0] is None, "le modèle ne connaît que « Jarvis »"
finally:
    oreille.CONFIG = vraie_config
    os.remove(f.name)

# --- Une 2e oreille ne peut pas écouter le port de la 1re (sous Windows, SO_REUSEADDR le permettait)
from http.server import BaseHTTPRequestHandler

premiere = oreille.ouvrir_port(0, BaseHTTPRequestHandler)
try:
    try:
        oreille.ouvrir_port(premiere.server_address[1], BaseHTTPRequestHandler).server_close()
        raise AssertionError("une 2e oreille a pris le même port")
    except OSError:
        pass
finally:
    premiere.server_close()

print("OK : l'oreille est vérifiée")
