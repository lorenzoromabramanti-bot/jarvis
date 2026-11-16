"""Test de hud_commandes.analyser : les ordres du HUD passent, les pièges (questions, clim, Windows) restent None."""
from hud_commandes import analyser

OUI = {
    "mets le mode sombre": ("theme", "sombre"),
    "Jarvis, passe en mode clair": ("theme", "clair"),
    "active le thème sombre s'il te plaît": ("theme", "sombre"),
    "mode sombre": ("theme", "sombre"),
    "désactive le mode sombre": ("theme", "clair"),
    "enlève le thème clair": ("theme", "sombre"),
    "mets le thème automatique": ("theme", "auto"),
    "thème auto": ("theme", "auto"),
    "ouvre tes réglages": ("reglages", None),
    "ouvre les paramètres de Jarvis": ("reglages", None),
    "montre-moi tes paramètres": ("reglages", None),
    "va dans tes réglages": ("reglages", None),
}
NON = [
    "c'est quoi le mode sombre ?",
    "pourquoi le mode sombre est mieux",
    "mets la clim en mode auto",
    "ouvre les paramètres Windows",
    "ouvre mes réglages",
    "mets la lumière claire",
    "le mode sombre de youtube est moche",
    "mets le mode sombre sur youtube",
    "mets le mode sombre sur le pc",
    "quel temps fait-il",
    "ouvre le dossier documents",
]

for phrase, attendu in OUI.items():
    assert analyser(phrase) == attendu, (phrase, analyser(phrase), attendu)
for phrase in NON:
    assert analyser(phrase) is None, (phrase, analyser(phrase))
print(f"_test_hud_commandes : {len(OUI)} ordres reconnus, {len(NON)} pièges ignorés — OK")
