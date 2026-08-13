# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Module en ligne (taux de change réels)
====================================================
Remplace les taux de change codés en dur par des taux RÉELS.

Priorité des sources :
  1. exchangerate-api.com si la clé EXCHANGERATE_API_KEY est configurée
     (panneau « CONFIGURATION API » ou fichier .env) ;
  2. sinon api.frankfurter.app (taux BCE, gratuit, sans clé).

La météo est déjà en temps réel via Open-Meteo (voir ha_config.get_meteo_actuelle),
ce module ne gère donc que le change.

Point d'entrée : ``resoudre_web(texte)`` — renvoie une phrase FR ou ``None``.
Fonction bas niveau réutilisable : ``taux_change(montant, src, dst)``.
Ce module fait des appels réseau : à exécuter hors de la boucle asyncio
(main2.py l'appelle via run_in_executor).
"""

import os
import re
import json
import urllib.request

_TIMEOUT = 8
_UA = {"User-Agent": "JARVIS/1.0"}

# Mots FR (sans accents) → code ISO 4217. Les entrées multi-mots doivent
# être testées AVANT les simples (« dollar canadien » avant « dollar »).
_DEVISES = [
    ("dollar canadien", "CAD"), ("dollar australien", "AUD"),
    ("dollar americain", "USD"), ("dollar us", "USD"),
    ("franc suisse", "CHF"), ("livre sterling", "GBP"),
    ("couronne suedoise", "SEK"), ("couronne norvegienne", "NOK"),
    ("couronne danoise", "DKK"), ("dollar", "USD"), ("euro", "EUR"),
    ("livre", "GBP"), ("sterling", "GBP"), ("yen", "JPY"),
    ("franc", "CHF"), ("yuan", "CNY"), ("renminbi", "CNY"),
    ("roupie", "INR"), ("real", "BRL"), ("rouble", "RUB"),
    ("won", "KRW"), ("peso", "MXN"), ("rand", "ZAR"),
    ("dirham", "AED"), ("zloty", "PLN"), ("lire turque", "TRY"),
    ("couronne", "SEK"), ("eur", "EUR"), ("usd", "USD"),
    ("gbp", "GBP"), ("jpy", "JPY"), ("chf", "CHF"), ("cad", "CAD"),
    ("aud", "AUD"), ("cny", "CNY"),
]
_NOM_DEVISE = {
    "EUR": "euros", "USD": "dollars américains", "GBP": "livres sterling",
    "JPY": "yens", "CHF": "francs suisses", "CAD": "dollars canadiens",
    "AUD": "dollars australiens", "CNY": "yuans", "INR": "roupies",
    "BRL": "reals", "RUB": "roubles", "KRW": "wons", "MXN": "pesos",
    "ZAR": "rands", "AED": "dirhams", "PLN": "zlotys", "TRY": "lires turques",
    "SEK": "couronnes suédoises", "NOK": "couronnes norvégiennes",
    "DKK": "couronnes danoises",
}


def _sa(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def _http_json(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def taux_change(montant: float, src: str, dst: str):
    """Renvoie (montant_converti, taux_unitaire) réels, ou None si indisponible."""
    src, dst = src.upper(), dst.upper()
    if src == dst:
        return montant, 1.0

    cle = os.getenv("EXCHANGERATE_API_KEY", "").strip()
    # 1) Fournisseur avec clé (exchangerate-api.com v6)
    if cle:
        try:
            data = _http_json(f"https://v6.exchangerate-api.com/v6/{cle}/pair/{src}/{dst}/{montant}")
            if data.get("result") == "success":
                return float(data["conversion_result"]), float(data["conversion_rate"])
        except Exception as e:
            print(f"[JARVIS_WEB] exchangerate-api KO ({e}), bascule sur frankfurter.")

    # 2) Frankfurter (BCE, sans clé)
    try:
        data = _http_json(f"https://api.frankfurter.app/latest?amount={montant}&from={src}&to={dst}")
        rates = data.get("rates", {})
        if dst in rates:
            converti = float(rates[dst])
            taux = converti / montant if montant else float(rates[dst])
            return converti, taux
    except Exception as e:
        print(f"[JARVIS_WEB] frankfurter KO ({e}).")
    return None


def _detecter_devises(t: str):
    """Renvoie la liste des codes ISO trouvés, dans l'ordre d'apparition."""
    trouves = []
    for mot, code in _DEVISES:
        # Chaque mot peut être au pluriel : « euros », « francs suisses »…
        pat = r"\b" + r"s?\s+".join(re.escape(w) for w in mot.split()) + r"s?"
        for m in re.finditer(pat, t):
            trouves.append((m.start(), code))
    trouves.sort()
    # Retire les doublons de position qui se chevauchent (garde la 1re, la plus longue)
    ordered, vus_pos = [], []
    for pos, code in trouves:
        if any(abs(pos - p) < 3 for p in vus_pos):
            continue
        if not ordered or ordered[-1] != code:
            ordered.append(code)
            vus_pos.append(pos)
        else:
            vus_pos.append(pos)
    return ordered


def resoudre_web(texte: str):
    """Résout une demande de change en taux réel. Renvoie str ou None."""
    if not texte or not texte.strip():
        return None
    t = _sa(texte.strip())

    intent = any(k in t for k in [
        "taux de change", "taux du change", "convertis", "converti", "conversion",
        "combien vaut", "combien font", "en dollar", "en euro", "en livre",
        "en yen", "en franc", "en yuan", "change", "vaut combien",
    ])
    devises = _detecter_devises(t)
    if not intent or len(devises) < 2:
        # « taux de change » sans 2e devise explicite → EUR/USD par défaut
        if intent and len(devises) == 1:
            devises = [devises[0], "USD" if devises[0] != "USD" else "EUR"]
        else:
            return None

    src, dst = devises[0], devises[1]
    montants = re.findall(r"\d+(?:[.,]\d+)?", t)
    montant = float(montants[0].replace(",", ".")) if montants else 1.0

    res = taux_change(montant, src, dst)
    if res is None:
        return "Je n'arrive pas à récupérer les taux de change en ce moment, réessayez dans un instant."
    converti, taux = res

    def _f(x):
        x = round(x, 2)
        return str(int(x)) if x == int(x) else f"{x:.2f}".replace(".", ",")

    def _ft(x):  # taux : jusqu'à 4 décimales significatives
        return f"{x:.4f}".rstrip("0").rstrip(".").replace(".", ",")

    nom_src = _NOM_DEVISE.get(src, src)
    nom_dst = _NOM_DEVISE.get(dst, dst)
    if montant == 1:
        return f"Taux actuel du marché : 1 {src} = {_ft(taux)} {dst} ({nom_dst})."
    return f"{_f(montant)} {nom_src} valent actuellement {_f(converti)} {nom_dst} (taux : 1 {src} = {_ft(taux)} {dst})."


if __name__ == "__main__":
    tests = [
        "convertis 100 euros en dollars",
        "combien font 50 dollars en euros",
        "taux de change euro dollar",
        "convertis 200 livres sterling en euros",
        "combien vaut 1000 yens en euros",
        "100 francs suisses en dollars canadiens",
        "quel temps fait-il",  # doit renvoyer None (pas du change)
        "convertis 10 en base 2",  # doit renvoyer None
    ]
    for q in tests:
        print(f"Q: {q}\n→ {resoudre_web(q)}\n")
