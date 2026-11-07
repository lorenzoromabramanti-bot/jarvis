# -*- coding: utf-8 -*-
"""Tests de demontage.py, sans lancer Claude Code ni ouvrir de navigateur."""
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demontage as d
import memoire_partagee


def test_detection():
    cas = {
        "démonte ce site igloo.inc": "https://igloo.inc",
        "Jarvis, démonte igloo point inc": "https://igloo.inc",
        "démonte-moi le site https://www.apple.com/fr/": "https://www.apple.com/fr/",
        "rétro-ingénierie du site linear.app.": "https://linear.app",
        "reverse engineer stripe.com": "https://stripe.com",
    }
    for texte, url in cas.items():
        r = d.detecter(texte)
        assert r and r["url"] == url, (texte, r)
    assert d.detecter("démonte ce site igloo inc") == {"url": None, "domaine": None}
    for rien in ("démonte la roue du vélo", "quelle heure est-il", "démonte le meuble",
                 "démonte ce site file:///C:/x", "démonte javascript:alert(1)"):
        assert not (d.detecter(rien) or {}).get("url"), rien
    print("  OK  détection")


def test_resume_et_phrase():
    rapport = "RÉSUMÉ : Un site WebGL en Three.js. Les textures pèsent le plus.\n\n## Ce que c'est\n..."
    assert d.extraire_resume(rapport) == "Un site WebGL en Three.js. Les textures pèsent le plus."
    assert d.extraire_resume("**Résumé :** court.") == "court."
    p = d.phrase({"succes": True, "domaine": "igloo.inc", "resume": "Deux phrases."}, "Alex")
    assert p == "Démontage de igloo.inc terminé, Alex. Deux phrases. Le rapport complet est dans la mémoire partagée.", p
    assert "échoué" in d.phrase({"succes": False, "domaine": "x.fr", "erreur": "timeout"})
    print("  OK  résumé et phrase")


def test_demonter_ecrit_le_rapport():
    """Claude simulé : le rapport atterrit dans etat/, la consigne limite les outils à REA."""
    vus = {}

    def faux_lancer(outil, args, **kw):
        vus["args"], vus["env"], vus["input"] = args, kw["env"], kw["input"]
        return subprocess.CompletedProcess(args, 0, "RÉSUMÉ : Ok.\n\n## Ce que c'est\nUn test.\n", "")

    racine = memoire_partagee.RACINE
    d.delegation_code._lancer, ancien = faux_lancer, d.delegation_code._lancer
    d.delegation_code._claude_authentique, ancien_auth = (lambda c: True), d.delegation_code._claude_authentique
    d.delegation_code._resoudre, ancien_res = (lambda c: sys.executable), d.delegation_code._resoudre
    try:
        memoire_partagee.RACINE = Path(tempfile.mkdtemp())
        res = d.demonter("https://igloo.inc", journal=lambda *_: None)
        assert res["succes"] and res["resume"] == "Ok.", res
        assert res["chemin"].endswith(os.path.join("etat", "demontage-igloo-inc.claude-code.md")), res
        texte = io.open(res["chemin"], encoding="utf-8").read()
        assert "Source : https://igloo.inc" in texte and "sujet: [demontage, igloo.inc]" in texte
        a = vus["args"]
        assert a[a.index("--allowedTools") + 1] == "mcp__rea", a
        assert vus["env"]["FIN_CLAUDE_SEUIL"] == "999999"
        assert "igloo.inc" in vus["input"] and "igloo.inc" not in " ".join(a)
    finally:
        memoire_partagee.RACINE = racine
        d.delegation_code._lancer, d.delegation_code._claude_authentique = ancien, ancien_auth
        d.delegation_code._resoudre = ancien_res
    print("  OK  rapport écrit dans la mémoire partagée")


if __name__ == "__main__":
    test_detection()
    test_resume_et_phrase()
    test_demonter_ecrit_le_rapport()
    print("Tous les tests demontage passent")
