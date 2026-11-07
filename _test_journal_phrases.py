"""Tests de journal_phrases.py : venv\\Scripts\\python.exe _test_journal_phrases.py"""
import json
import os
import tempfile

import journal_phrases as jp

with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "phrases.jsonl")
    assert jp.noter("  allume   la lumière\n du salon ", "voix", fichier=f)
    assert jp.noter("c'est quoi ma moyenne ?", "texte", fichier=f)
    assert not jp.noter("   ", "voix", fichier=f), "rien à garder"
    assert not jp.noter("tout bas", "voix", actif=False, fichier=f), "réglage garder_phrases à false"
    lignes = [json.loads(l) for l in open(f, encoding="utf-8")]
    assert [l["texte"] for l in lignes] == ["allume la lumière du salon", "c'est quoi ma moyenne ?"]
    assert [l["canal"] for l in lignes] == ["voix", "texte"] and all(len(l["t"]) == 19 for l in lignes)
    assert not jp.noter("x", "voix", fichier=os.path.join(d, "dossier-absent", "p.jsonl")), "erreur affichée, pas levée"
print("OK : journal des phrases")
