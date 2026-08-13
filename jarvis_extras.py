# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Module de fonctionnalités locales avancées
=========================================================
Ensemble de commandes 100 % hors-ligne (bibliothèque standard uniquement).
Chaque fonction renvoie une chaîne de réponse prête à être lue par JARVIS,
ou ``None`` si la demande ne correspond pas (afin que la chaîne de résolveurs
de main2.py continue vers l'IA).

Point d'entrée unique : ``resoudre_extras_avancees(texte)``.

Ce module est autonome et testable seul :  ``python jarvis_extras.py``
"""

import os
import re
import json
import math
import base64
import random
import unicodedata
from datetime import datetime, date
from config import nom_utilisateur

# ─────────────────────────────────────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def _nom_utilisateur() -> str:
    """Le prenom configure. Delegue a config : une seule source."""
    # Ce module relisait jarvis_config.json de son cote, avec son propre
    # repli. Trois copies de la meme lecture, c'etait trois occasions de
    # diverger — et c'est ce qui est arrive.
    return nom_utilisateur()


def _sans_accents(s: str) -> str:
    """Version sans accents et minuscule d'une chaîne (pour matcher les mots-clés)."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


def _nombres(texte: str):
    """Extrait tous les nombres (décimaux avec , ou .) d'un texte."""
    return [float(x.replace(",", ".")) for x in re.findall(r"-?\d+(?:[.,]\d+)?", texte)]


def _fmt(x: float) -> str:
    """Formatage humain d'un nombre (entier si possible, sinon 2 décimales)."""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return f"{x:.2f}".replace(".", ",")


# ─────────────────────────────────────────────────────────────────────────────
#  Données statiques
# ─────────────────────────────────────────────────────────────────────────────

_MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.",
    "g": "--.", "h": "....", "i": "..", "j": ".---", "k": "-.-", "l": ".-..",
    "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-",
    "y": "-.--", "z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..",
    "!": "-.-.--", "/": "-..-.", " ": "/",
}
_MORSE_INV = {v: k for k, v in _MORSE.items()}

_FAITS = [
    "Le saviez-vous ? Le miel ne périme jamais : on a retrouvé du miel comestible dans des tombes égyptiennes de plus de 3000 ans.",
    "Le saviez-vous ? Un éclair est environ cinq fois plus chaud que la surface du Soleil.",
    "Le saviez-vous ? Les poulpes possèdent trois cœurs et un sang bleu.",
    "Le saviez-vous ? La Tour Eiffel peut mesurer 15 cm de plus en été à cause de la dilatation du métal.",
    "Le saviez-vous ? Il y a plus d'étoiles dans l'univers observable que de grains de sable sur toutes les plages de la Terre.",
    "Le saviez-vous ? Le cœur humain bat environ 100 000 fois par jour.",
    "Le saviez-vous ? Les bananes sont légèrement radioactives à cause du potassium 40 qu'elles contiennent.",
    "Le saviez-vous ? Un jour sur Vénus dure plus longtemps qu'une année vénusienne.",
    "Le saviez-vous ? Le mot « robot » vient du tchèque « robota » qui signifie « travail forcé ».",
    f"Le saviez-vous ? Les octets de ce programme voyagent à près de 300 000 km/s dans vos circuits. Presque aussi vite que mon esprit, {nom_utilisateur()}.",
]

_JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]


# ─────────────────────────────────────────────────────────────────────────────
#  Conversions numériques
# ─────────────────────────────────────────────────────────────────────────────

def _int_vers_romain(n: int) -> str:
    if not (0 < n < 4000):
        return None
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
            (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
            (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, sym in vals:
        while n >= v:
            out += sym
            n -= v
    return out


def _romain_vers_int(s: str):
    s = s.upper()
    if not re.fullmatch(r"[IVXLCDM]+", s):
        return None
    table = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total, prev = 0, 0
    for c in reversed(s):
        val = table[c]
        total += -val if val < prev else val
        prev = max(prev, val)
    # Vérification aller-retour pour rejeter les écritures invalides
    return total if _int_vers_romain(total) == s else None


# ─────────────────────────────────────────────────────────────────────────────
#  Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────

def resoudre_extras_avancees(texte: str):
    """Résout une large gamme de commandes locales. Renvoie str ou None."""
    if not texte or not texte.strip():
        return None

    orig = texte.strip()
    t = _sans_accents(orig)
    nom = _nom_utilisateur()

    # ── AIDE / LISTE DES FONCTIONNALITÉS ────────────────────────────────────
    if any(k in t for k in ["que sais-tu faire", "que sais tu faire", "a quoi tu sers",
                            "liste de tes commandes", "tes fonctionnalites",
                            "quelles sont tes fonctions", "liste des fonctionnalites",
                            "que peux-tu faire de plus", "montre-moi tes nouveautes"]):
        return (
            f"Voici un aperçu de mes nouvelles capacités locales, {nom} :\n"
            "• Calculs : IMC, pourboire, TVA, pourcentage, moyenne, PGCD/PPCM, factorielle.\n"
            "• Nombres : premier ou non, chiffres romains, binaire, hexadécimal, octal, table de multiplication.\n"
            "• Texte : compter les mots, inverser, majuscules/minuscules, code Morse, Base64.\n"
            "• Dates : jour d'une date, numéro de semaine, décompte jusqu'à une date.\n"
            "• Divers : décision au hasard, couleur aléatoire, lancer de dés multiples, anecdotes.\n"
            "Dites par exemple : « calcule mon IMC, 72 kg pour 1m78 » ou « convertis 2026 en chiffres romains »."
        )

    # ── IMC ─────────────────────────────────────────────────────────────────
    if "imc" in t or "indice de masse corporelle" in t:
        poids = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kg|kilo)", t)
        # taille : "1m78", "1,78 m", "178 cm", "1.78"
        taille_m = None
        m = re.search(r"(\d)\s*m(?:etre)?s?\s*(\d{1,2})", t)
        if m:
            taille_m = float(m.group(1)) + float(m.group(2)) / (10 ** len(m.group(2)))
        if taille_m is None:
            m = re.search(r"(\d{3})\s*cm", t)
            if m:
                taille_m = float(m.group(1)) / 100
        if taille_m is None:
            m = re.search(r"(\d)[.,](\d{1,2})\s*m\b", t)
            if m:
                taille_m = float(f"{m.group(1)}.{m.group(2)}")
        if poids and taille_m and taille_m > 0:
            imc = float(poids.group(1).replace(",", ".")) / (taille_m ** 2)
            if imc < 18.5:
                cat = "insuffisance pondérale"
            elif imc < 25:
                cat = "corpulence normale"
            elif imc < 30:
                cat = "surpoids"
            else:
                cat = "obésité"
            return f"Votre IMC est de {imc:.1f}, ce qui correspond à une {cat}, {nom}."
        return f"Précisez votre poids et votre taille, {nom}. Exemple : « IMC pour 72 kg et 1m78 »."

    # ── POURBOIRE ───────────────────────────────────────────────────────────
    if "pourboire" in t or re.search(r"\btip\b", t):
        base_m = re.search(r"sur\s+(\d+(?:[.,]\d+)?)", t) or re.search(r"(\d+(?:[.,]\d+)?)\s*(?:euro|eur|€)", t)
        pct_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|pour ?cent)", t)
        nums = _nombres(t)
        base = float(base_m.group(1).replace(",", ".")) if base_m else (nums[-1] if nums else None)
        pct = float(pct_m.group(1).replace(",", ".")) if pct_m else 10.0
        if base:
            tip = base * pct / 100
            return (f"Pour une addition de {_fmt(base)} €, un pourboire de {_fmt(pct)} % représente "
                    f"{_fmt(tip)} €, soit un total de {_fmt(base + tip)} €, {nom}.")
        return f"Indiquez le montant, {nom}. Exemple : « pourboire de 15 % sur 40 euros »."

    # ── TVA ─────────────────────────────────────────────────────────────────
    if "tva" in t or "ttc" in t or re.search(r"\bht\b", t):
        taux_m = re.search(r"(?:a|de)\s+(\d+(?:[.,]\d+)?)\s*%", t) or re.search(r"(\d+(?:[.,]\d+)?)\s*%", t)
        taux = float(taux_m.group(1).replace(",", ".")) if taux_m else 20.0
        # Le montant est le nombre qui n'est pas le taux
        montants = [n for n in _nombres(t) if n != taux]
        if montants:
            base = montants[-1]
            if any(k in t for k in ["enleve", "retire", "sans tva", "prix ht", "hors taxe", "ht de", "vers ht"]):
                ht = base / (1 + taux / 100)
                return f"Un montant TTC de {_fmt(base)} € correspond à {_fmt(ht)} € HT (TVA {_fmt(taux)} %), {nom}."
            ttc = base * (1 + taux / 100)
            return f"Un montant HT de {_fmt(base)} € correspond à {_fmt(ttc)} € TTC (TVA {_fmt(taux)} %), {nom}."
        return f"Précisez le montant, {nom}. Exemple : « ajoute la TVA à 100 euros »."

    # ── POURCENTAGE ─────────────────────────────────────────────────────────
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%\s*de\s+(\d+(?:[.,]\d+)?)", t)
    if m:
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", "."))
        return f"{_fmt(a)} % de {_fmt(b)} égale {_fmt(a * b / 100)}, {nom}."
    m = re.search(r"(\d+(?:[.,]\d+)?)\s+est\s+quel\s+pourcentage\s+de\s+(\d+(?:[.,]\d+)?)", t)
    if m:
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", "."))
        if b:
            return f"{_fmt(a)} représente {_fmt(a / b * 100)} % de {_fmt(b)}, {nom}."

    # ── MOYENNE / SOMME / MIN / MAX ─────────────────────────────────────────
    if any(k in t for k in ["moyenne de", "fais la moyenne", "somme de", "additionne",
                            "maximum de", "minimum de", "le plus grand de", "le plus petit de"]):
        nums = _nombres(t)
        if len(nums) >= 2:
            if "moyenne" in t:
                return f"La moyenne de {', '.join(_fmt(n) for n in nums)} est {_fmt(sum(nums) / len(nums))}, {nom}."
            if "somme" in t or "additionne" in t:
                return f"La somme de {', '.join(_fmt(n) for n in nums)} est {_fmt(sum(nums))}, {nom}."
            if "maximum" in t or "plus grand" in t:
                return f"Le plus grand est {_fmt(max(nums))}, {nom}."
            if "minimum" in t or "plus petit" in t:
                return f"Le plus petit est {_fmt(min(nums))}, {nom}."

    # ── PGCD / PPCM ─────────────────────────────────────────────────────────
    if "pgcd" in t or "ppcm" in t:
        nums = [int(n) for n in _nombres(t) if n == int(n)]
        if len(nums) >= 2:
            a, b = nums[0], nums[1]
            if "pgcd" in t:
                return f"Le PGCD de {a} et {b} est {math.gcd(a, b)}, {nom}."
            ppcm = abs(a * b) // math.gcd(a, b) if a and b else 0
            return f"Le PPCM de {a} et {b} est {ppcm}, {nom}."

    # ── FACTORIELLE ─────────────────────────────────────────────────────────
    fact_m = re.search(r"factorielle\s+(?:de\s+)?(\d+)", t) or re.search(r"(\d+)\s*!", t)
    if fact_m:
        n = int(fact_m.group(1))
        if n <= 170:
            return f"La factorielle de {n} est {math.factorial(n)}, {nom}."
        return f"{n} est trop grand pour un calcul de factorielle raisonnable, {nom}."

    # ── NOMBRE PREMIER ──────────────────────────────────────────────────────
    if "premier" in t and any(k in t for k in ["nombre", "est-il", "est il", "est-ce que", "est ce que"]):
        nums = [int(n) for n in _nombres(t) if n == int(n)]
        if nums:
            n = int(nums[0])
            if n < 2:
                return f"{n} n'est pas un nombre premier, {nom}."
            est_premier = all(n % i for i in range(2, int(math.isqrt(n)) + 1))
            if est_premier:
                return f"Oui, {n} est bien un nombre premier, {nom}."
            diviseur = next(i for i in range(2, n) if n % i == 0)
            return f"Non, {n} n'est pas premier : il est divisible par {diviseur}, {nom}."

    # ── CHIFFRES ROMAINS ────────────────────────────────────────────────────
    if "romain" in t:
        rom_m = re.search(r"\b([ivxlcdm]{1,15})\b", t)
        num_m = re.search(r"\d+", t)
        if num_m and ("en chiffre romain" in t or "en romain" in t or "en chiffres romains" in t):
            r = _int_vers_romain(int(num_m.group()))
            if r:
                return f"{num_m.group()} s'écrit {r} en chiffres romains, {nom}."
            return f"Je ne peux convertir que les nombres de 1 à 3999, {nom}."
        if rom_m:
            val = _romain_vers_int(rom_m.group(1))
            if val:
                return f"Le chiffre romain {rom_m.group(1).upper()} vaut {val}, {nom}."

    # ── BASES : BINAIRE / HEXA / OCTAL ──────────────────────────────────────
    if any(k in t for k in ["en binaire", "en hexadecimal", "en hexa", "en octal", "en decimal"]):
        # Conversion depuis un préfixe explicite vers décimal
        pre = re.search(r"0b([01]+)|0x([0-9a-f]+)|0o([0-7]+)", t)
        if "en decimal" in t and pre:
            if pre.group(1):
                return f"0b{pre.group(1)} vaut {int(pre.group(1), 2)} en décimal, {nom}."
            if pre.group(2):
                return f"0x{pre.group(2)} vaut {int(pre.group(2), 16)} en décimal, {nom}."
            if pre.group(3):
                return f"0o{pre.group(3)} vaut {int(pre.group(3), 8)} en décimal, {nom}."
        num_m = re.search(r"\b(\d+)\b", t)
        if num_m:
            n = int(num_m.group(1))
            if "binaire" in t:
                return f"{n} en binaire s'écrit {bin(n)[2:]}, {nom}."
            if "hexa" in t:
                return f"{n} en hexadécimal s'écrit {hex(n)[2:].upper()}, {nom}."
            if "octal" in t:
                return f"{n} en octal s'écrit {oct(n)[2:]}, {nom}."

    # ── TABLE DE MULTIPLICATION ─────────────────────────────────────────────
    tab_m = re.search(r"table (?:de multiplication )?(?:de |du )?(\d{1,2})", t)
    if tab_m and "table" in t:
        n = int(tab_m.group(1))
        lignes = "  ".join(f"{n}×{i}={n * i}" for i in range(1, 11))
        return f"Table de {n} : {lignes}"

    # ── COMPTER LES MOTS / CARACTÈRES ───────────────────────────────────────
    if any(k in t for k in ["combien de mots", "compte les mots", "nombre de mots",
                            "combien de caracteres", "compte les caracteres"]):
        m = re.search(r"(?:mots?|caracteres?)\s*(?:dans|de|:)?\s*[:\-]?\s*(.+)", orig, re.I)
        cible = m.group(1).strip(" :\"'") if m else ""
        if cible:
            if "caractere" in t:
                return f"Ce texte contient {len(cible)} caractères, {nom}."
            return f"Ce texte contient {len(cible.split())} mots, {nom}."
        return f"Indiquez le texte à analyser, {nom}."

    # ── INVERSER UN TEXTE ───────────────────────────────────────────────────
    m = re.search(r"(?:inverse(?:r)?(?: le texte)?|(?:ecris|met[s]?)(?: ca)? a l'?envers)\s*[:\-]?\s*(.+)", orig, re.I)
    if m and any(k in t for k in ["inverse", "a l'envers", "a l envers"]):
        cible = m.group(1).strip(" :\"'")
        if cible:
            return f"À l'envers : {cible[::-1]}"

    # ── MAJUSCULES / MINUSCULES ─────────────────────────────────────────────
    m = re.search(r"(?:mets?|met|passe|convertis)?\s*(?:en\s+)?(majuscules?|minuscules?)\s*[:\-]?\s*(.+)", orig, re.I)
    if m and ("majuscule" in t or "minuscule" in t):
        mode, cible = m.group(1).lower(), m.group(2).strip(" :\"'")
        if cible:
            return cible.upper() if "maj" in mode else cible.lower()

    # ── CODE MORSE ──────────────────────────────────────────────────────────
    if "morse" in t:
        m = re.search(r"morse\s*(?:de|:|\-)?\s*(.+)", orig, re.I)
        cible = m.group(1).strip(" :\"'") if m else ""
        if "decode" in t or "traduis" in t and set(cible) <= set(".-/ "):
            mots = cible.strip().split(" / ") if " / " in cible else cible.split("  ")
            try:
                out = " ".join("".join(_MORSE_INV.get(c, "") for c in mot.split()) for mot in mots)
                if out.strip():
                    return f"En clair : {out.strip()}"
            except Exception:
                pass
        if cible and set(cible) <= set(".-/ "):
            # C'est déjà du morse → on décode
            out = "".join(_MORSE_INV.get(c, "") if c != "/" else " " for c in cible.split())
            if out.strip():
                return f"En clair : {out.strip()}"
        if cible:
            code = " ".join(_MORSE.get(c, "") for c in cible.lower())
            return f"En morse : {code.strip()}"

    # ── BASE64 ──────────────────────────────────────────────────────────────
    if "base64" in t:
        m = re.search(r"base64\s*(?:de|:|\-)?\s*(.+)", orig, re.I)
        cible = m.group(1).strip(" :\"'") if m else ""
        if cible:
            if "decode" in t or "decrypte" in t:
                try:
                    return f"Décodé : {base64.b64decode(cible).decode('utf-8', 'replace')}"
                except Exception:
                    return f"Ce texte n'est pas un Base64 valide, {nom}."
            return f"Encodé en Base64 : {base64.b64encode(cible.encode('utf-8')).decode()}"

    # ── JOUR D'UNE DATE ─────────────────────────────────────────────────────
    if "quel jour" in t and re.search(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}", t):
        dm = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", t)
        try:
            j, mois, an = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
            if an < 100:
                an += 2000
            d = date(an, mois, j)
            return f"Le {j} {_MOIS_FR[mois]} {an} est un {_JOURS_FR[d.weekday()]}, {nom}."
        except Exception:
            return f"Cette date me semble invalide, {nom}."

    # ── NUMÉRO DE SEMAINE ───────────────────────────────────────────────────
    if any(k in t for k in ["numero de semaine", "quelle semaine", "quel numero de semaine",
                            "on est en quelle semaine", "semaine actuelle"]):
        semaine = datetime.now().isocalendar()[1]
        return f"Nous sommes actuellement en semaine {semaine} de l'année, {nom}."

    # ── DÉCOMPTE JUSQU'À UNE DATE ───────────────────────────────────────────
    if any(k in t for k in ["combien de jours jusqu", "combien de jours avant le",
                            "dans combien de jours", "nombre de jours jusqu"]):
        dm = re.search(r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?", t)
        if dm:
            try:
                j, mois = int(dm.group(1)), int(dm.group(2))
                an = int(dm.group(3)) + (2000 if dm.group(3) and int(dm.group(3)) < 100 else 0) if dm.group(3) else datetime.now().year
                cible = date(an, mois, j)
                if not dm.group(3) and cible < date.today():
                    cible = date(an + 1, mois, j)
                jours = (cible - date.today()).days
                return f"Il reste {jours} jour{'s' if abs(jours) > 1 else ''} jusqu'au {j} {_MOIS_FR[mois]} {cible.year}, {nom}."
            except Exception:
                return f"Cette date me semble invalide, {nom}."

    # ── DÉCISION AU HASARD ──────────────────────────────────────────────────
    if any(k in t for k in ["choisis entre", "aide-moi a choisir", "aide moi a choisir",
                            "dois-je", "dois je", "je prends quoi", "au hasard entre"]) and " ou " in t:
        segment = orig
        for pref in ["choisis entre", "au hasard entre", "aide-moi à choisir entre",
                     "aide moi a choisir entre", "dois-je", "dois je"]:
            idx = _sans_accents(segment).find(_sans_accents(pref))
            if idx != -1:
                segment = segment[idx + len(pref):]
                break
        options = [o.strip(" ?.!") for o in re.split(r"\bou\b", segment, flags=re.I) if o.strip(" ?.!")]
        if len(options) >= 2:
            choix = random.choice(options)
            return f"À votre place, je choisirais : {choix}, {nom}."

    # ── COULEUR ALÉATOIRE ───────────────────────────────────────────────────
    if any(k in t for k in ["couleur aleatoire", "genere une couleur", "une couleur au hasard",
                            "donne-moi une couleur", "donne moi une couleur", "couleur random"]):
        hexa = "#{:06X}".format(random.randint(0, 0xFFFFFF))
        return f"Voici une couleur au hasard : {hexa}, {nom}."

    # ── LANCER DE DÉS MULTIPLES ─────────────────────────────────────────────
    dm = re.search(r"lance\s+(\d+)\s+d[eé]s", t)
    if dm:
        n = min(int(dm.group(1)), 20)
        faces_m = re.search(r"[aà]\s+(\d+)\s+faces", t)
        faces = int(faces_m.group(1)) if faces_m else 6
        tirages = [random.randint(1, faces) for _ in range(n)]
        return f"J'ai lancé {n} dés à {faces} faces : {', '.join(map(str, tirages))} — total {sum(tirages)}, {nom}."

    # ── ANECDOTE / FAIT ─────────────────────────────────────────────────────
    if any(k in t for k in ["le saviez-vous", "le saviez vous", "dis-moi un fait",
                            "dis moi un fait", "une anecdote", "un fait au hasard",
                            "fait aleatoire", "raconte un fait", "info insolite"]):
        return random.choice(_FAITS)

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Auto-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        "calcule mon IMC, 72 kg pour 1m78",
        "pourboire de 15% sur 40 euros",
        "ajoute la TVA à 100 euros",
        "prix HT de 120 euros TTC",
        "combien font 15% de 200",
        "moyenne de 12, 15 et 18",
        "pgcd de 12 et 18",
        "ppcm de 4 et 6",
        "factorielle de 6",
        "est-ce que 17 est un nombre premier",
        "est-ce que 21 est un nombre premier",
        "convertis 2026 en chiffres romains",
        "que vaut le chiffre romain MMXXVI",
        "convertis 42 en binaire",
        "convertis 255 en hexadécimal",
        "table de multiplication de 7",
        "combien de mots dans : bonjour tout le monde ça va",
        "inverse le texte bonjour",
        "mets en majuscules bonjour monsieur",
        "code morse de SOS",
        "encode en base64 bonjour",
        "décode base64 Ym9uam91cg==",
        "quel jour était le 14/07/1789",
        "on est en quelle semaine",
        "combien de jours jusqu'au 25/12",
        "dois-je prendre le thé ou le café",
        "génère une couleur aléatoire",
        "lance 3 dés",
        "dis-moi un fait au hasard",
        "que sais-tu faire",
    ]
    for q in tests:
        rep = resoudre_extras_avancees(q)
        print(f"Q: {q}\n→ {rep}\n")
