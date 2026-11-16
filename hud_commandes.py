"""Commandes qui pilotent le HUD lui-même : thème (clair / sombre / automatique) et ouverture des réglages.

Fonction pure, appelée par resoudre_commandes_locales (main2.py) avant le filet « ouvre X inconnu » :
sans elle, le modèle répondait des explications inventées (« c'est l'application qui doit l'appliquer »)."""
import re
import unicodedata

PHRASES_THEME = {
    "sombre": "Mode sombre.",
    "clair": "Mode clair.",
    "auto": "Thème automatique : clair le jour, sombre la nuit.",
}
_VERBES = r"mets?|mettre|remets?|passe|passer|active|activer|desactive|desactiver|bascule|basculer|change|changer|enleve|enlever|retire|retirer|arrete|arreter|quitte|quitter"
_NEGATIF = r"\b(?:desactive|desactiver|enleve|enlever|retire|retirer|arrete|arreter|quitte|quitter)\b"
_AUTRE_CIBLE = r"\b(?:youtube|windows|chrome|opera|edge|discord|spotify|telephone|iphone|ecran|pc|ordinateur|site|clim|lumiere|lampe)\b"
_QUESTION = r"\b(?:c est quoi|qu est|pourquoi|comment|est ce que)\b"


def _normaliser(texte):
    t = "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9?]+", " ", t).strip()


def analyser(texte):
    """('theme', 'sombre'|'clair'|'auto'), ('reglages', None), ou None si la phrase ne parle pas du HUD."""
    t = _normaliser(texte)
    mots = t.split()
    if "?" in t or re.search(_QUESTION, t) or re.search(_AUTRE_CIBLE, t):
        return None
    # Thème : « mode/thème sombre|clair », « thème auto(matique) » (pas « mode auto » : c'est celui de la clim).
    m = re.search(r"\b(?:mode|theme)\s+(sombre|clair)\b", t) or re.search(r"\btheme\s+(auto|automatique)\b", t)
    if m and (re.search(rf"\b(?:{_VERBES})\b", t) or len(mots) <= 4):
        theme = "auto" if m.group(1).startswith("auto") else m.group(1)
        if theme != "auto" and re.search(_NEGATIF, t):
            theme = "clair" if theme == "sombre" else "sombre"
        return "theme", theme
    # Réglages du HUD : il faut « tes / ses / Jarvis » pour ne pas prendre les paramètres de Windows.
    if (re.search(r"\b(?:reglages|parametres|settings)\b", t)
            and re.search(r"\b(?:ouvre|ouvrir|affiche|afficher|montre|montrer|va|vas|aller)\b", t)
            and re.search(r"\b(?:tes|ses|jarvis)\b", t)):
        return "reglages", None
    return None
