# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Éclairage RGB du PC par Prisme (application locale, API 127.0.0.1:8472)
=========================================================================================
Prisme pilote OpenRGB ; JARVIS ne fait que traduire une phrase en appel d'API.
La phrase doit dire « RGB » ou « Prisme » : « éteins la lumière » reste à Home
Assistant, qui pilote les vraies lampes de la maison.

    « éteins le RGB », « allume le RGB », « mets le RGB en rouge »,
    « RGB arc-en-ciel », « RGB à 40 % », « RGB suivant »
"""
import json
import re
import unicodedata
import urllib.request

API = "http://127.0.0.1:8472"

COULEURS = {
    "rouge": "#ff0000", "vert": "#00ff40", "bleu": "#0050ff", "jaune": "#ffd000", "orange": "#ff6a00",
    "violet": "#8f3bff", "rose": "#ff3fa8", "blanc": "#ffffff", "cyan": "#00e5ff", "turquoise": "#00e5c0",
}
# mot dit -> effet de Prisme (premier trouvé dans la phrase)
EFFETS = [("arc en ciel", "vague_arc_en_ciel"), ("respiration", "respiration"), ("respire", "respiration"),
          ("feu", "feu"), ("flamme", "feu"), ("etoile", "etoiles"), ("degrade", "degrade"),
          ("gyrophare", "police"), ("police", "police"), ("cycle", "cycle_couleurs")]


def _plat(texte):
    t = unicodedata.normalize("NFD", (texte or "").lower())
    return re.sub(r"[-']", " ", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def detecter(texte):
    """None si la phrase ne parle pas du RGB, sinon (chemin d'API, corps JSON, phrase de réussite)."""
    t = _plat(texte)
    # « prisme » seul est un mot courant (cours de physique) : il ne compte qu'avec un ordre.
    if not (re.search(r"\brgb\b", t) or (re.search(r"\bprisme\b", t) and
            re.search(r"\b(mets|met|passe|allume|rallume|eteins|eteint|coupe|lance)\b", t))):
        return None
    if re.search(r"\b(eteins|eteint|coupe|stop|arrete|desactive)\b", t):
        return "/api/allume", {"on": False}, "RGB éteint"
    m = re.search(r"(\d{1,3})\s*(%|pour ?cent)", t)
    if m and 0 <= int(m.group(1)) <= 100:
        return "/api/luminosite", {"valeur": int(m.group(1))}, "RGB à %s %%" % m.group(1)
    if re.search(r"\b(suivant|prochain)\b", t):
        return "/api/suivant", {}, "effet suivant"
    if re.search(r"\b(precedent|d avant)\b", t):
        return "/api/precedent", {}, "effet précédent"
    for mot, hexa in COULEURS.items():
        if re.search(r"\b%ss?e?s?\b" % mot, t):
            return "/api/effet", {"id": "couleur_unie", "params": {"couleur": hexa}}, "RGB en %s" % mot
    for mot, effet in EFFETS:
        if mot in t:
            return "/api/effet", {"id": effet}, "RGB en mode %s" % mot.replace("arc en ciel", "arc-en-ciel")
    if re.search(r"\b(allume|rallume|active|lance)\b", t):
        return "/api/allume", {"on": True}, "RGB allumé"
    return None


def executer(action, appel=None):
    """Envoie l'action à Prisme. Renvoie (ok, phrase). `appel` remplaçable pour les tests."""
    chemin, corps, reussite = action
    try:
        rep = (appel or _http)(chemin, corps)
    except Exception:
        return False, "Prisme ne répond pas : il démarre avec le PC, ou se relance depuis son raccourci"
    etat = rep.get("etat") or {}
    # Une couleur ou un effet sur un RGB éteint ne se verrait pas : on rallume aussi.
    if chemin in ("/api/effet", "/api/luminosite", "/api/suivant", "/api/precedent") and not etat.get("allume", True):
        try:
            (appel or _http)("/api/allume", {"on": True})
        except Exception:
            pass
    return True, reussite


def _http(chemin, corps=None):
    """GET si corps est None, sinon POST JSON ; renvoie la réponse décodée."""
    donnees = None if corps is None else json.dumps(corps).encode()
    req = urllib.request.Request(API + chemin, donnees, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def passer_rouge(appel=None):
    """Le juge fait une remarque : RGB en rouge. Renvoie l'état d'avant (pour restaurer()), ou None si Prisme est absent."""
    appel = appel or _http
    try:
        avant = appel("/api/etat").get("etat") or {}
        appel("/api/effet", {"id": "couleur_unie", "params": {"couleur": COULEURS["rouge"]}})
        if not avant.get("allume", True):
            appel("/api/allume", {"on": True})
        return {"effet": avant.get("effet"), "params": avant.get("params") or {}, "allume": avant.get("allume", True)}
    except Exception:
        return None


def restaurer(avant, appel=None):
    """Remet l'effet (et l'extinction) d'avant passer_rouge()."""
    if not avant or not avant.get("effet"):
        return
    appel = appel or _http
    try:
        appel("/api/effet", {"id": avant["effet"], "params": avant["params"]})
        if not avant["allume"]:
            appel("/api/allume", {"on": False})
    except Exception:
        pass


if __name__ == "__main__":
    cas = {
        "éteins le RGB": ("/api/allume", {"on": False}),
        "Jarvis mets le RGB en rouge": ("/api/effet", {"id": "couleur_unie", "params": {"couleur": "#ff0000"}}),
        "RGB arc-en-ciel": ("/api/effet", {"id": "vague_arc_en_ciel"}),
        "mets le prisme en mode feu": ("/api/effet", {"id": "feu"}),
        "RGB à 40 %": ("/api/luminosite", {"valeur": 40}),
        "rgb suivant": ("/api/suivant", {}),
        "allume le RGB": ("/api/allume", {"on": True}),
    }
    for phrase, attendu in cas.items():
        r = detecter(phrase)
        assert r and r[:2] == attendu, (phrase, r)
    for rien in ("éteins la lumière du salon", "mets de la musique", "allume le PC", "un prismes de verre",
                 "explique comment un prisme fait un arc-en-ciel"):
        assert detecter(rien) is None, rien
    vus = []
    ok, phrase = executer(detecter("RGB en bleu"),
                          appel=lambda c, b: vus.append(c) or {"etat": {"allume": False}})
    assert ok and phrase == "RGB en bleu" and vus == ["/api/effet", "/api/allume"], vus

    def panne(c, b):
        raise OSError("refusé")
    assert executer(detecter("éteins le RGB"), appel=panne)[0] is False

    # Le juge : rouge pendant la remarque, puis l'effet d'avant (et l'extinction s'il était éteint)
    vus = []

    def prisme(c, b=None):
        vus.append((c, b))
        return {"etat": {"effet": "feu", "params": {"vitesse": 2}, "allume": False}} if c == "/api/etat" else {}
    avant = passer_rouge(appel=prisme)
    assert avant == {"effet": "feu", "params": {"vitesse": 2}, "allume": False}
    assert vus[1] == ("/api/effet", {"id": "couleur_unie", "params": {"couleur": "#ff0000"}}) and vus[2] == ("/api/allume", {"on": True})
    vus.clear()
    restaurer(avant, appel=prisme)
    assert vus == [("/api/effet", {"id": "feu", "params": {"vitesse": 2}}), ("/api/allume", {"on": False})]
    assert passer_rouge(appel=panne) is None and restaurer(None) is None
    print("OK rgb_prisme")
