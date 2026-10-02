"""Choix du modele Ollama : verifie contre les modeles reellement installes."""
import json
import os
import tempfile

import agent_model_manager as amm


def _charger(choix, installes):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"chosen_models": choix}, f)
    amm.CONFIG_PATH, amm.ollama_installes = f.name, lambda: installes
    try:
        return amm.load_chosen_models()
    finally:
        os.remove(f.name)


# installe -> garde
assert _charger({"Ollama": "qwen-rapide:latest"}, ["mistral:latest", "qwen-rapide:latest"])["Ollama"] == "qwen-rapide:latest"
# absent -> defaut (avec message), plus jamais un llama3 fantome garde en silence
assert _charger({"Ollama": "llama3"}, ["mistral:latest"])["Ollama"] == amm.DEFAULT_MODELS["Ollama"]
# Ollama eteint au demarrage -> on ne peut pas verifier, on garde la config
assert _charger({"Ollama": "qwen-rapide:latest"}, None)["Ollama"] == "qwen-rapide:latest"
# les autres agents restent valides contre leur liste
assert _charger({"Gemini": "inexistant"}, [])["Gemini"] == amm.DEFAULT_MODELS["Gemini"]
print("OK")
