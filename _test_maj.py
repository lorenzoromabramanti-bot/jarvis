# -*- coding: utf-8 -*-
"""
Verifie la comparaison de versions et le comportement en cas d'echec.

Ce qui compte n'est pas « ca trouve la mise a jour » — ca depend de GitHub —
mais les deux proprietes qui cassent en silence :

  1. La comparaison doit etre NUMERIQUE. En texte, « 1.10.0 » passe avant
     « 1.9.0 » : la mise a jour cesserait d'etre proposee a partir de la
     version 10, sans erreur nulle part.
  2. Un echec de verification ne doit JAMAIS empecher le demarrage. Pas de
     reseau, depot absent, quota depasse : on renvoie une raison, on ne leve
     pas.

    venv\\Scripts\\python.exe _test_maj.py
"""

import sys
import time

import maj


def verifier():
    # ── Comparaison ─────────────────────────────────────────────────────
    cas = [
        ("1.0.0", "1.0.0",  0),
        ("1.0.0", "1.0.1", -1),
        ("1.0.1", "1.0.0",  1),
        ("1.9.0", "1.10.0", -1),   # le piege du tri alphabetique
        ("1.10.0", "1.9.0",  1),
        ("0.9.9", "1.0.0", -1),
        ("2.0.0", "1.99.99", 1),
        ("1.0.0", "v1.0.0", 0),    # le « v » de GitHub ne compte pas
        ("1.0", "1.0.0",    0),    # composants manquants = zeros
        ("1.0.0", "1.0.0-beta", 0),
    ]
    for locale, distante, attendu in cas:
        obtenu = maj.comparer(locale, distante)
        assert obtenu == attendu, \
            "comparer(%r, %r) = %s, attendu %s" % (locale, distante, obtenu, attendu)
    print("  OK  %d comparaisons, dont 1.9.0 < 1.10.0" % len(cas))

    # Entrees absurdes : ne pas lever.
    for mauvais in (None, "", "abc", "...", 42):
        maj.comparer("1.0.0", mauvais)
        maj.comparer(mauvais, "1.0.0")
    print("  OK  versions illisibles sans plantage")

    # ── Echecs ──────────────────────────────────────────────────────────
    # « Aucun depot configure » ne peut plus se dire en passant depot="" :
    # une chaine vide signifie desormais « prends celui du .env », et il y en
    # a un. On neutralise la source le temps du controle, sinon ce test
    # verifierait le contraire de ce qu'il annonce.
    vrai = maj.depot_configure
    maj.depot_configure = lambda: ""
    try:
        r = maj.verifier()
        assert r["ok"] is False and "dépôt" in r["raison"], r
    finally:
        maj.depot_configure = vrai
    print("  OK  sans depot configure : refus explique, pas d'exception")

    # Et avec le depot reel, la chaine complete repond.
    r = maj.verifier()
    assert r.get("ok"), "le depot configure ne repond pas : %r" % r
    assert r["locale"] == maj.VERSION
    print("  OK  depot reel interroge : locale %s, distante %s, a jour %s"
          % (r["locale"], r["distante"], r["a_jour"]))

    debut = time.perf_counter()
    r = maj.verifier(depot="ce-depot/n-existe-pas-du-tout-12345", delai=8)
    duree = time.perf_counter() - debut
    assert r["ok"] is False, "un depot inexistant a repondu ok : %r" % r
    assert r.get("raison"), "echec sans raison"
    assert duree < 20, "la verification a pris %.0f s — trop long au demarrage" % duree
    print("  OK  depot inexistant : %s (%.1f s)" % (r["raison"], duree))

    # ── La phrase ───────────────────────────────────────────────────────
    assert maj.phrase({"ok": False, "raison": "reseau"}) == "", \
        "un echec reseau ne doit rien annoncer a l'utilisateur"
    assert maj.phrase({"ok": True, "a_jour": True}) == "", \
        "etre a jour ne merite pas une annonce"
    p = maj.phrase({"ok": True, "a_jour": False, "distante": "1.2.0", "locale": "1.0.0"})
    assert "1.2.0" in p and "1.0.0" in p, p
    print("  OK  n'annonce que ce qui merite de l'etre")

    # ── Le module ne met rien a jour ────────────────────────────────────
    # Garde volontaire : telecharger et remplacer du code demande un accord
    # explicite. Si quelqu'un ajoute ca ici un jour, ce test le signalera.
    import io, os
    src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "maj.py"), encoding="utf-8").read()
    for interdit in ("shutil.move", "os.replace", "zipfile", "subprocess"):
        assert interdit not in src, \
            "maj.py s'est mis a installer (%s) : ca demande un accord explicite" % interdit
    print("  OK  le module verifie et n'installe rien")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier()
    print("\n  Verification de mise a jour : conforme.")
