import builtins
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_model_config.json")

# Dictionnaire des modeles disponibles par agent
AVAILABLE_MODELS = {
    "Gemini": [
        "gemini-3.5-flash",
        "gemini-3.1-pro",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash-exp"
    ],
    "Grok": [
        "grok-beta",
        "grok-2-1212",
        "grok-4.5",
        "grok-4.3",
        "grok-4.20-0309-non-reasoning",
        "grok-4.20-0309-reasoning"
    ],
    "Claude": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-latest",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307"
    ],
    "Mistral": [
        "mistral-large-latest",
        "mistral-small-latest",
        "open-mixtral-8x22b"
    ],
    "Groq": [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma-7b-it"
    ],
    # Ollama : liste lue en vrai sur le serveur (ollama_installes), pas codee
    # en dur — l'ancienne liste (llama3, mistral, gemma) ne correspondait plus
    # a rien d'installe, et un modele choisi hors liste etait ecarte en silence.
    "Ollama": [],
    "ChatGPT": [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.6",
        "o4-mini",
        "o3",
        "o3-pro"
    ]
}

# Modeles par defaut
DEFAULT_MODELS = {
    "Gemini": "gemini-3.1-flash-lite",
    "Grok": "grok-beta",
    "Claude": "claude-3-5-sonnet-20241022",
    "Mistral": "mistral-large-latest",
    "Groq": "llama-3.3-70b-versatile",
    "Ollama": "gemma4:26b",
    "ChatGPT": "gpt-5.6-sol"
}

OLLAMA_URL = "http://127.0.0.1:11434"


def ollama_installes():
    """Modeles reellement installes (API /api/tags). None si Ollama ne repond pas."""
    try:
        import requests
        r = requests.get(OLLAMA_URL + "/api/tags", timeout=2)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return None


def _modeles_dispo(agent, installes):
    if agent == "Ollama":
        return installes or []
    return AVAILABLE_MODELS.get(agent, [])


def load_chosen_models():
    """Charge les modeles preferes depuis le JSON ou retourne les defauts."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                loaded_models = config.get("chosen_models", {})

                # Fusionner avec les valeurs par defaut pour eviter des cles manquantes
                result = DEFAULT_MODELS.copy()
                installes = ollama_installes()
                for agent, model in loaded_models.items():
                    if agent not in result:
                        continue
                    # Ollama eteint (demarrage de Windows) : impossible de
                    # verifier, on garde le choix de la config.
                    if agent == "Ollama" and installes is None:
                        result[agent] = model
                    elif model in _modeles_dispo(agent, installes):
                        result[agent] = model
                    else:
                        print(f"[AGENT MODELE] {agent} : '{model}' indisponible, "
                              f"'{result[agent]}' utilise a la place")
                return result
    except Exception as e:
        print(f"[AGENT MODELE] Erreur lors du chargement des modeles : {e}")
    return DEFAULT_MODELS.copy()

def save_chosen_models(models_dict):
    """Sauvegarde le dictionnaire de modeles choisis dans le JSON."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"chosen_models": models_dict}, f)
        print(f"[AGENT MODELE] Modeles sauvegardes dans la configuration.")
    except Exception as e:
        print(f"[AGENT MODELE] Erreur lors de la sauvegarde des modeles : {e}")

def get_agent_models_info(current_models):
    """Retourne la structure complete pour construire l'interface web."""
    return {
        "available_models": {**AVAILABLE_MODELS, "Ollama": ollama_installes() or []},
        "current_models": current_models
    }

def set_agent_models(new_models_dict):
    """Mets a jour et sauvegarde les modeles."""
    # Validation
    valid_models = DEFAULT_MODELS.copy()
    installes = ollama_installes()
    for agent, model in new_models_dict.items():
        if agent in AVAILABLE_MODELS and model in _modeles_dispo(agent, installes):
            valid_models[agent] = model
            
    builtins.CHOSEN_MODELS = valid_models
    save_chosen_models(valid_models)
    return valid_models

