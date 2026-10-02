# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Boîte à outils locale (2e vague de fonctionnalités)
=================================================================
Nouvelles commandes 100 % hors-ligne (stdlib uniquement), complémentaires
à jarvis_extras.py. Chaînées APRÈS jarvis_extras dans main2.py, donc tout
résolveur existant a la priorité ; ce module ne répond que sur des tournures
spécifiques et renvoie ``None`` sinon.

Point d'entrée : ``resoudre_outils(texte)``.
Testable seul : ``python jarvis_outils.py``
"""

import os
import re
import json
import math
import uuid
import random
import unicodedata
from datetime import datetime, date, timedelta


# ─────────────────────────────────────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def _nom():
    """Le prenom configure. Delegue a config : une seule source."""
    # Ce module relisait jarvis_config.json de son cote, avec son propre
    # repli. Quatre copies de la meme lecture existaient (main2, ha_config,
    # jarvis_extras, ici) : quatre occasions de diverger, et c'est ce qui
    # est arrive.
    from config import nom_utilisateur
    return nom_utilisateur()


def _sa(s: str) -> str:
    """minuscule sans accents."""
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def _nums(texte: str):
    return [float(x.replace(",", ".")) for x in re.findall(r"-?\d+(?:[.,]\d+)?", texte)]


def _fmt(x) -> str:
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    if isinstance(x, float):
        return (f"{x:.4f}".rstrip("0").rstrip(".")).replace(".", ",")
    return str(x)


# ─────────────────────────────────────────────────────────────────────────────
#  Nombre entier → toutes lettres (français, 0 à 999 999)
# ─────────────────────────────────────────────────────────────────────────────

_U = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit",
      "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize"]
_D = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"}


def _fr99(n: int) -> str:
    if n < 17:
        return _U[n]
    if n < 20:
        return "dix-" + _U[n - 10]
    if n < 70:
        t, u = (n // 10) * 10, n % 10
        if u == 0:
            return _D[t]
        if u == 1:
            return _D[t] + " et un"
        return _D[t] + "-" + _U[u]
    if n < 80:
        if n == 71:
            return "soixante et onze"
        return "soixante-" + _fr99(n - 60)
    u = n - 80
    if u == 0:
        return "quatre-vingts"
    return "quatre-vingt-" + _fr99(u)


def _fr999(n: int) -> str:
    if n < 100:
        return _fr99(n)
    c, r = n // 100, n % 100
    cent = "cent" if c == 1 else _U[c] + " cent"
    if r == 0:
        return cent + ("s" if c > 1 else "")
    return cent + " " + _fr99(r)


def _fr_lettres(n: int):
    if n == 0:
        return "zéro"
    if n < 0:
        return "moins " + _fr_lettres(-n)
    if n < 1000:
        return _fr999(n)
    if n < 1_000_000:
        m, r = n // 1000, n % 1000
        if m == 1:
            mille = "mille"
        else:
            mw = _fr999(m)
            if mw.endswith("cents"):
                mw = mw[:-1]           # deux cents mille → deux cent mille
            elif mw.endswith("quatre-vingts"):
                mw = mw[:-1]           # quatre-vingts mille → quatre-vingt mille
            mille = mw + " mille"
        return mille if r == 0 else mille + " " + _fr999(r)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Données statiques
# ─────────────────────────────────────────────────────────────────────────────

_ASTRO = [
    (1, 20, "Capricorne"), (2, 19, "Verseau"), (3, 21, "Poissons"),
    (4, 20, "Bélier"), (5, 21, "Taureau"), (6, 21, "Gémeaux"),
    (7, 23, "Cancer"), (8, 23, "Lion"), (9, 23, "Vierge"),
    (10, 23, "Balance"), (11, 22, "Scorpion"), (12, 22, "Sagittaire"),
    (12, 31, "Capricorne"),
]
_CHINOIS = ["Rat", "Buffle", "Tigre", "Lapin", "Dragon", "Serpent",
            "Cheval", "Chèvre", "Singe", "Coq", "Chien", "Cochon"]
_EMOJIS = ["🚀", "🧠", "⚡", "🛰️", "🤖", "🔮", "🎯", "💡", "🌌", "🛡️", "🎲", "🔥", "❄️", "🧩", "📡"]
_MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre"]
_MAGIC = ["Oui, sans aucun doute.", "C'est certain.", "Très probablement.",
          "Mes circuits penchent pour oui.", "Peut-être, l'avenir est flou.",
          "Rien n'est moins sûr.", "Ne comptez pas dessus.", "Ma réponse est non.",
          "Il vaut mieux ne pas vous le dire maintenant.", "Concentrez-vous et redemandez."]
_ADJ = ["Cosmic", "Neon", "Cyber", "Quantum", "Shadow", "Iron", "Turbo", "Nova", "Hyper", "Ghost"]
_NOM = ["Falcon", "Wolf", "Reactor", "Phoenix", "Circuit", "Raven", "Titan", "Vortex", "Blade", "Pixel"]
_LEET = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7", "l": "1", "b": "8"}


# ─────────────────────────────────────────────────────────────────────────────
#  Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def resoudre_outils(texte: str):
    if not texte or not texte.strip():
        return None
    orig = texte.strip()
    t = _sa(orig)
    nom = _nom()

    # ══════════════════ CONVERSIONS D'UNITÉS ══════════════════════════════════

    # — Vitesse (km/h ↔ m/s ↔ mph)
    if any(u in t for u in ["km/h", "km h", "m/s", "m s", "mph"]):
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(km/?h|km h|m/?s|m s|mph)\s+en\s+(km/?h|km h|m/?s|m s|mph)", t)
        if m:
            val = float(m.group(1).replace(",", "."))
            fac = {"kmh": 0.277778, "ms": 1.0, "mph": 0.44704}
            lbl = {"kmh": "km/h", "ms": "m/s", "mph": "mph"}
            src = m.group(2).replace("/", "").replace(" ", "")
            dst = m.group(3).replace("/", "").replace(" ", "")
            if src in fac and dst in fac:
                return f"{_fmt(val)} {lbl[src]} font {_fmt(round(val * fac[src] / fac[dst], 4))} {lbl[dst]}, {nom}."

    # — Poids kg ↔ livres
    if ("livre" in t or " lb" in t or "pound" in t) and ("kg" in t or "kilo" in t):
        v = _nums(t)
        if v:
            x = v[0]
            if re.search(r"\d+(?:[.,]\d+)?\s*(?:kg|kilo)", t):
                return f"{_fmt(x)} kg font {_fmt(round(x * 2.20462, 2))} livres, {nom}."
            return f"{_fmt(x)} livres font {_fmt(round(x / 2.20462, 2))} kg, {nom}."

    # — Longueur cm ↔ pouces
    if ("pouce" in t or "inch" in t) and ("cm" in t or "centim" in t):
        v = _nums(t)
        if v:
            x = v[0]
            if re.search(r"\d+(?:[.,]\d+)?\s*(?:cm|centim)", t):
                return f"{_fmt(x)} cm font {_fmt(round(x / 2.54, 2))} pouces, {nom}."
            return f"{_fmt(x)} pouces font {_fmt(round(x * 2.54, 2))} cm, {nom}."

    # — Longueur m ↔ pieds
    if ("pied" in t or "feet" in t or " ft" in t) and ("metre" in t or " m " in f" {t} "):
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(pieds?|feet|ft|metres?|m)\s+en\s+(pieds?|feet|ft|metres?|m)", t)
        if m:
            val = float(m.group(1).replace(",", "."))
            src, dst = m.group(2), m.group(3)
            src_pied = src.startswith(("pied", "feet", "ft"))
            vm = val * 0.3048 if src_pied else val
            if dst.startswith(("pied", "feet", "ft")):
                res, dlbl = vm / 0.3048, "pieds"
            else:
                res, dlbl = vm, "mètres"
            slbl = "pieds" if src_pied else "mètres"
            return f"{_fmt(val)} {slbl} font {_fmt(round(res, 2))} {dlbl}, {nom}."

    # — Volume litres ↔ gallons
    if "gallon" in t or "litre" in t:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(litres?|gallons?)\s+en\s+(litres?|gallons?)", t)
        if m:
            val = float(m.group(1).replace(",", "."))
            fac = {"litre": 1.0, "gallon": 3.78541}
            lbl = {"litre": "litres", "gallon": "gallons"}
            src, dst = m.group(2).rstrip("s"), m.group(3).rstrip("s")
            if src in fac and dst in fac:
                return f"{_fmt(val)} {lbl[src]} font {_fmt(round(val * fac[src] / fac[dst], 4))} {lbl[dst]}, {nom}."

    # — Température Kelvin
    if "kelvin" in t and ("celsius" in t or "degre" in t):
        v = _nums(t)
        if v:
            x = v[0]
            if re.search(r"\d+(?:[.,]\d+)?\s*kelvin", t):
                return f"{_fmt(x)} kelvin font {_fmt(round(x - 273.15, 2))} °C, {nom}."
            return f"{_fmt(x)} °C font {_fmt(round(x + 273.15, 2))} kelvin, {nom}."

    # — Angle degrés ↔ radians
    if "radian" in t and ("degre" in t or "°" in orig):
        v = _nums(t)
        if v:
            x = v[0]
            if re.search(r"\d+(?:[.,]\d+)?\s*radian", t):
                return f"{_fmt(x)} radians font {_fmt(round(math.degrees(x), 2))} degrés, {nom}."
            return f"{_fmt(x)} degrés font {_fmt(round(math.radians(x), 4))} radians, {nom}."

    # — Données informatiques (octets/Ko/Mo/Go/To, bits)
    if "en mo" in t or "en go" in t or "en ko" in t or "en octet" in t or "en bit" in t or "en to" in t:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(to|go|mo|ko|octets?|bits?)\s+en\s+(to|go|mo|ko|octets?|bits?)", t)
        if m:
            val = float(m.group(1).replace(",", "."))
            src, dst = m.group(2).rstrip("s"), m.group(3).rstrip("s")
            fac = {"bit": 1 / 8, "octet": 1, "ko": 1024, "mo": 1024**2, "go": 1024**3, "to": 1024**4}
            lbl = {"bit": "bits", "octet": "octets", "ko": "Ko", "mo": "Mo", "go": "Go", "to": "To"}
            octets = val * fac[src]
            res = octets / fac[dst]
            return f"{_fmt(val)} {lbl[src]} font {_fmt(round(res, 4))} {lbl[dst]}, {nom}."

    # ══════════════════ TEMPS & DATES ═════════════════════════════════════════

    # — Durée en secondes → format lisible
    if "seconde" in t and ("en heure" in t or "en minute" in t or "convertis" in t or "format" in t):
        v = _nums(t)
        if v:
            s = int(v[0])
            h, r = divmod(s, 3600)
            mn, sec = divmod(r, 60)
            parts = []
            if h:
                parts.append(f"{h} heure{'s' if h > 1 else ''}")
            if mn:
                parts.append(f"{mn} minute{'s' if mn > 1 else ''}")
            if sec or not parts:
                parts.append(f"{sec} seconde{'s' if sec > 1 else ''}")
            return f"{s} secondes font {', '.join(parts)}, {nom}."

    # — Signe astrologique
    if "signe" in t and ("astro" in t or "zodiaque" in t or "ne le" in t or "né le" in _sa("né le") and ("signe" in t)):
        dm = re.search(r"(\d{1,2})[/\- ]+(\d{1,2}|janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)", t)
        jour, mois = None, None
        if dm:
            jour = int(dm.group(1))
            g2 = dm.group(2)
            if g2.isdigit():
                mois = int(g2)
            else:
                noms = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
                        "aout", "septembre", "octobre", "novembre", "decembre"]
                mois = noms.index(g2) + 1
        if jour and mois:
            signe = None
            for mo, lim, s in _ASTRO:
                if mois == mo and jour <= lim:
                    signe = s
                    break
            if signe is None:
                # après la limite du mois → signe suivant dans la table
                nxt = {1: "Verseau", 2: "Poissons", 3: "Bélier", 4: "Taureau", 5: "Gémeaux",
                       6: "Cancer", 7: "Lion", 8: "Vierge", 9: "Balance", 10: "Scorpion",
                       11: "Sagittaire", 12: "Capricorne"}
                signe = nxt[mois]
            return f"Une personne née le {jour} {_MOIS[mois]} est du signe {signe}, {nom}."

    # — Signe chinois
    if "signe chinois" in t or "astrologie chinoise" in t or "zodiaque chinois" in t:
        v = [int(n) for n in _nums(t) if 1900 <= n <= 2100]
        if v:
            an = v[0]
            return f"L'année {an} est placée sous le signe du {_CHINOIS[(an - 2020) % 12]}, {nom}."
        return f"Précisez une année, {nom}. Exemple : « signe chinois de 1990 »."

    # — Quantième (jour de l'année)
    if "quantieme" in t or "jour de l'annee" in t or "combien de jours depuis le debut de l'annee" in t or "quel jour de l'annee" in t:
        n = datetime.now()
        jour_an = n.timetuple().tm_yday
        return f"Nous sommes le {jour_an}e jour de l'année {n.year}, {nom}."

    # — Saison actuelle
    if "quelle saison" in t or "on est en quelle saison" in t or "saison actuelle" in t:
        n = datetime.now()
        md = (n.month, n.day)
        if (3, 20) <= md < (6, 21):
            sais = "au printemps"
        elif (6, 21) <= md < (9, 23):
            sais = "en été"
        elif (9, 23) <= md < (12, 21):
            sais = "en automne"
        else:
            sais = "en hiver"
        return f"Nous sommes actuellement {sais}, {nom}."

    # — Heure dans X heures/minutes
    m = re.search(r"quelle heure.*dans\s+(\d+)\s*(heure|minute|h|min)", t)
    if m:
        q = int(m.group(1))
        delta = timedelta(hours=q) if m.group(2).startswith("h") else timedelta(minutes=q)
        cible = datetime.now() + delta
        return f"Dans {q} {m.group(2)}{'s' if q > 1 and not m.group(2).endswith('s') else ''}, il sera {cible.strftime('%H:%M')}, {nom}."

    # — 24h → 12h AM/PM
    m = re.search(r"(\d{1,2})\s*h\s*(\d{2})?\s*(?:en|au format)\s*(?:12|am|pm|americain)", t)
    if m and ("12" in t or "am" in t or "pm" in t or "americain" in t):
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        suff = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h:02d}h{mn:02d} correspond à {h12}:{mn:02d} {suff}, {nom}."

    # ══════════════════ MATHS & NOMBRES ═══════════════════════════════════════

    # — Nombre en toutes lettres
    if ("en lettres" in t or "en toutes lettres" in t) and re.search(r"\d", t):
        v = [int(n) for n in _nums(t) if n == int(n)]
        if v:
            mots = _fr_lettres(v[0])
            if mots:
                return f"{v[0]} s'écrit « {mots} », {nom}."
            return f"Ce nombre dépasse ma table (max 999 999), {nom}."

    # — Somme des chiffres
    if "somme des chiffres" in t:
        m = re.search(r"\d+", t)
        if m:
            s = sum(int(c) for c in m.group())
            return f"La somme des chiffres de {m.group()} est {s}, {nom}."

    # — Suite de Fibonacci
    if "fibonacci" in t:
        v = [int(n) for n in _nums(t) if n == int(n)]
        n = min(v[0], 30) if v else 10
        seq = [0, 1]
        while len(seq) < n:
            seq.append(seq[-1] + seq[-2])
        return f"Les {n} premiers nombres de Fibonacci : {', '.join(map(str, seq[:n]))}."

    # — Augmentation / réduction en pourcentage
    m = re.search(r"(augmente|majore|reduis|reduit|diminue|baisse)\s+(\d+(?:[.,]\d+)?)\s+de\s+(\d+(?:[.,]\d+)?)\s*%", t)
    if m:
        base = float(m.group(2).replace(",", "."))
        pct = float(m.group(3).replace(",", "."))
        if m.group(1) in ("augmente", "majore"):
            return f"{_fmt(base)} augmenté de {_fmt(pct)} % donne {_fmt(base * (1 + pct / 100))}, {nom}."
        return f"{_fmt(base)} réduit de {_fmt(pct)} % donne {_fmt(base * (1 - pct / 100))}, {nom}."

    # — Conversion en base N (2 à 36)
    m = re.search(r"(\d+)\s+en\s+base\s+(\d+)", t)
    if m:
        n, b = int(m.group(1)), int(m.group(2))
        if 2 <= b <= 36:
            digits = "0123456789abcdefghijklmnopqrstuvwxyz"
            x, out = n, ""
            if x == 0:
                out = "0"
            while x:
                out = digits[x % b] + out
                x //= b
            return f"{n} en base {b} s'écrit {out.upper()}, {nom}."

    # — Racine cubique / n-ième
    m = re.search(r"racine\s+(cubique|troisieme|quatrieme|cinquieme|(\d+)\s*(?:ieme|eme|e))\s+de\s+(\d+(?:[.,]\d+)?)", t)
    if m:
        rang_txt = m.group(1)
        rangs = {"cubique": 3, "troisieme": 3, "quatrieme": 4, "cinquieme": 5}
        rang = rangs.get(rang_txt) or (int(m.group(2)) if m.group(2) else 3)
        val = float(m.group(3).replace(",", "."))
        res = val ** (1 / rang)
        return f"La racine {rang}-ième de {_fmt(val)} vaut environ {_fmt(round(res, 4))}, {nom}."

    # — Nombre parfait
    if "nombre parfait" in t or "est parfait" in t:
        v = [int(n) for n in _nums(t) if n == int(n)]
        if v:
            n = v[0]
            div = [i for i in range(1, n) if n % i == 0]
            if sum(div) == n and n > 0:
                return f"Oui, {n} est un nombre parfait (somme de ses diviseurs {'+'.join(map(str, div))} = {n}), {nom}."
            return f"Non, {n} n'est pas un nombre parfait, {nom}."

    # ══════════════════ TEXTE ═════════════════════════════════════════════════

    # — Palindrome (extraction d'un seul mot)
    if "palindrome" in t:
        m = re.search(r"([A-Za-zÀ-ÿ0-9'’-]+)\s+est(?:-il|-elle| il| elle)?\s+(?:un|une)\s+palindrome", orig, re.I)
        if not m:
            m = re.search(r"palindrome\s*(?:du mot|de|:|\-)?\s*([A-Za-zÀ-ÿ0-9'’-]+)", orig, re.I)
        cible = m.group(1).strip(" ?.:!\"'") if m else ""
        if cible:
            norm = re.sub(r"[^a-z0-9]", "", _sa(cible))
            if norm:
                verdict = "est" if norm == norm[::-1] else "n'est pas"
                return f"« {cible} » {verdict} un palindrome, {nom}."

    # — Anagramme
    if "anagramme" in t:
        mots = re.findall(r"[a-zà-ÿ]{2,}", _sa(orig))
        mots = [w for w in mots if w not in ("anagramme", "anagrammes", "est", "sont", "les", "des", "une", "un", "de", "et", "que", "ce")]
        if len(mots) >= 2:
            a = sorted(re.sub(r"[^a-z]", "", mots[0]))
            b = sorted(re.sub(r"[^a-z]", "", mots[1]))
            ok = a == b
            return f"« {mots[0]} » et « {mots[1]} » {'sont' if ok else 'ne sont pas'} des anagrammes, {nom}."

    # — Compter voyelles / consonnes
    if ("combien de voyelles" in t or "combien de consonnes" in t or "compte les voyelles" in t or "compte les consonnes" in t):
        m = re.search(r"(?:voyelles?|consonnes?)\s+(?:dans|de|:)?\s*(.+)", orig, re.I)
        cible = m.group(1).strip(" :\"'") if m else ""
        if cible:
            lettres = [c for c in _sa(cible) if c.isalpha()]
            voy = sum(1 for c in lettres if c in "aeiouy")
            if "voyelle" in t:
                return f"« {cible} » contient {voy} voyelles, {nom}."
            return f"« {cible} » contient {len(lettres) - voy} consonnes, {nom}."

    # — ROT13
    if "rot13" in t or "rot 13" in t:
        m = re.search(r"rot\s*13\s*(?:de|:|\-)?\s*(.+)", orig, re.I)
        cible = m.group(1).strip(" :\"'") if m else ""
        if cible:
            import codecs
            return f"En ROT13 : {codecs.encode(cible, 'rot_13')}"

    # — Leet speak (« leet de X » ou « écris X en leet »)
    if "leet" in t or "1337" in t:
        low = orig.lower()
        if " en leet" in low or " en 1337" in low:
            cible = re.split(r"\ben\s+(?:leet|1337)", orig, flags=re.I)[0]
            cible = re.sub(r"^\s*(écris|ecris|mets?|met|convertis|passe|traduis)\s+", "", cible, flags=re.I).strip(" :\"'")
        else:
            m = re.search(r"(?:leet|1337)\s*(?:speak)?\s*(?:de|:|\-)?\s*(.+)", orig, re.I)
            cible = m.group(1).strip(" :\"'") if m else ""
        if cible:
            return "En leet : " + "".join(_LEET.get(c, c) for c in cible.lower())

    # — Slug
    if "slug" in t or "slugify" in t:
        m = re.search(r"(?:slugify|slug)\s*(?:de|:|\-)?\s*(.+)", orig, re.I)
        cible = m.group(1).strip(" :\"'") if m else ""
        if cible:
            s = re.sub(r"[^a-z0-9]+", "-", _sa(cible)).strip("-")
            return f"Slug : {s}"

    # ══════════════════ ALÉATOIRE & FUN ═══════════════════════════════════════

    # — Loto
    if "loto" in t or ("tire" in t and "numero" in t):
        grille = sorted(random.sample(range(1, 50), 5))
        chance = random.randint(1, 10)
        return f"Votre grille de Loto : {', '.join(map(str, grille))} — numéro chance : {chance}. Bonne chance, {nom} !"

    # — UUID / identifiant unique
    if "identifiant unique" in t or "uuid" in t or "genere un id" in t:
        return f"Identifiant unique : {uuid.uuid4()}"

    # — Code PIN
    if "code pin" in t or "genere un pin" in t or "un pin" in t:
        m = re.search(r"(\d+)\s*chiffres", t)
        lg = min(max(int(m.group(1)), 3), 12) if m else 4
        pin = "".join(str(random.randint(0, 9)) for _ in range(lg))
        return f"Votre code PIN à {lg} chiffres : {pin}"

    # — Pseudo aléatoire
    if "pseudo" in t or "surnom" in t or "nom d'utilisateur" in t:
        return f"Suggestion de pseudo : {random.choice(_ADJ)}{random.choice(_NOM)}{random.randint(1, 99)}"

    # — Boule magique / oracle oui-non
    if "boule magique" in t or "oracle" in t or ("reponds par oui ou non" in t):
        return f"🔮 {random.choice(_MAGIC)}"

    # — Emoji aléatoire
    if "emoji" in t and ("hasard" in t or "aleatoire" in t or "donne" in t or "un emoji" in t):
        return f"Voici votre emoji : {random.choice(_EMOJIS)}"

    # — Dés notation NdM+K (ex: 2d20+3)
    m = re.search(r"(\d*)d(\d+)([+-]\d+)?", t)
    if m and any(k in t for k in ["lance", "jette", "roll", "tire", "d20", "d6", "d100"]):
        nb = int(m.group(1)) if m.group(1) else 1
        faces = int(m.group(2))
        bonus = int(m.group(3)) if m.group(3) else 0
        if 1 <= nb <= 50 and 2 <= faces <= 1000:
            tirages = [random.randint(1, faces) for _ in range(nb)]
            total = sum(tirages) + bonus
            détail = f"{' + '.join(map(str, tirages))}" + (f" {'+' if bonus >= 0 else '-'} {abs(bonus)}" if bonus else "")
            return f"🎲 {nb}d{faces}{m.group(3) or ''} → [{détail}] = {total}, {nom}."

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Auto-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        "convertis 100 km/h en m/s",
        "10 m/s en km/h",
        "60 mph en km/h",
        "70 kg en livres",
        "150 livres en kg",
        "180 cm en pouces",
        "2 mètres en pieds",
        "10 litres en gallons",
        "2 Go en Mo",
        "500 octets en bits",
        "100 celsius en kelvin",
        "180 degrés en radians",
        "convertis 3661 secondes en heures",
        "quel est mon signe astrologique si je suis né le 14 mars",
        "signe chinois de 1990",
        "quel jour de l'année sommes-nous",
        "on est en quelle saison",
        "quelle heure sera-t-il dans 3 heures",
        "14h30 au format américain",
        "écris 342 en lettres",
        "écris 1342 en lettres",
        "écris 80 en lettres",
        "écris 71 en lettres",
        "écris 999999 en lettres",
        "somme des chiffres de 12345",
        "suite de fibonacci jusqu'à 10",
        "augmente 200 de 15%",
        "réduis 80 de 10%",
        "convertis 42 en base 5",
        "racine cubique de 27",
        "est-ce que 28 est un nombre parfait",
        "est-ce que kayak est un palindrome",
        "est-ce que chien et niche sont des anagrammes",
        "combien de voyelles dans anticonstitutionnellement",
        "rot13 de bonjour",
        "écris bonjour en leet",
        "slugify Mon Super Titre",
        "tire les numéros du loto",
        "génère un identifiant unique",
        "génère un code pin à 6 chiffres",
        "génère un pseudo",
        "boule magique dois-je sortir ce soir",
        "donne-moi un emoji au hasard",
        "lance 2d20+3",
    ]
    for q in tests:
        print(f"Q: {q}\n→ {resoudre_outils(q)}\n")
