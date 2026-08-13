# -*- coding: utf-8 -*-
"""Outil JARVIS : Traduction rapide de mots courants.

Migre depuis main2.py (passe 1). Corps repris a l'identique,
seul le decorateur @outil a ete ajoute.
"""

from . import outil


@outil(nom="traduction", priorite=60, description="Traduction rapide de mots courants")
def resoudre_traduction_localement(texte):
    """Traduction ultra-rapide de mots courants localement."""
    t = texte.lower().strip()
    
    dict_trad = {
        "bonjour": {"en": "hello", "es": "hola", "de": "hallo"},
        "merci": {"en": "thank you", "es": "gracias", "de": "danke"},
        "au revoir": {"en": "goodbye", "es": "adiós", "de": "auf wiedersehen"},
        "s'il vous plaît": {"en": "please", "es": "por favor", "de": "bitte"},
        "oui": {"en": "yes", "es": "sí", "de": "ja"},
        "non": {"en": "no", "es": "no", "de": "nein"},
        "ami": {"en": "friend", "es": "amigo", "de": "freund"},
        "maison": {"en": "house", "es": "casa", "de": "haus"},
        "ordinateur": {"en": "computer", "es": "ordenador", "de": "computer"},
        "assistant": {"en": "assistant", "es": "asistente", "de": "assistent"},
    }

    if any(p in t for p in ["comment dit-on", "traduis", "en anglais", "en espagnol", "en allemand"]):
        cible = "en"
        if "espagnol" in t: cible = "es"
        elif "allemand" in t: cible = "de"
        
        # Extraction du mot
        # On nettoie les expressions courantes
        mot = t
        for p in ["comment dit-on", "traduis", "en anglais", "en espagnol", "en allemand", "?"]:
            mot = mot.replace(p, "")
        mot = mot.replace('"', '').replace("'", "").strip()
        
        if mot in dict_trad:
            res = dict_trad[mot][cible]
            lang = "anglais" if cible == "en" else ("espagnol" if cible == "es" else "allemand")
            return f"En {lang}, '{mot}' se dit '{res}'."
            
    return None
