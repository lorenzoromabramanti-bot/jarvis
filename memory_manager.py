import os
import json
import time
import threading
from google.genai import types

# MEMOIRE PERSISTANTE
# ==========================================
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMOIRE_FILE = os.path.join(_BASE_DIR, "jarvis_memoire.json")

def charger_memoire():
    if os.path.exists(MEMOIRE_FILE):
        try:
            with open(MEMOIRE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def sauvegarder_memoire(memoire):
    try:
        with open(MEMOIRE_FILE, "w", encoding="utf-8") as f:
            json.dump(memoire, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur sauvegarde memoire : {e}")

def ajouter_memoire(cle, valeur):
    memoire      = charger_memoire()
    memoire[cle] = {"valeur": valeur, "timestamp": time.strftime("%d/%m/%Y %H:%M")}
    sauvegarder_memoire(memoire)

def supprimer_memoire(cle):
    memoire = charger_memoire()
    if cle in memoire:
        del memoire[cle]
        sauvegarder_memoire(memoire)
        return True
    return False

def construire_contexte_memoire():
    memoire = charger_memoire()
    if not memoire:
        return ""
    lignes = ["MEMOIRE PERSISTANTE :"]
    for cle, data in memoire.items():
        lignes.append(f"  - {cle} : {data['valeur']} (note le {data['timestamp']})")
    return "\n".join(lignes)

# ==========================================
# HISTORIQUE CONVERSATIONS PERSISTANT
# ==========================================
HISTORIQUE_CONV_FILE = os.path.join(_BASE_DIR, "jarvis_conversations.json")
MAX_ECHANGES_FICHIER = 200   # max échanges stockés sur disque
MAX_ECHANGES_CHARGE  = 30    # échanges rechargés au démarrage (contexte IA)

def _sauvegarder_echange_conv_sync(user_text: str, model_text: str):
    """Effectue la sauvegarde réelle sur le disque."""
    # Attendre quelques secondes pour s'assurer que Jarvis a commencé à parler
    # Cela permet à la notification [OBSIDIAN] d'apparaître à la fin, comme souhaité par l'utilisateur
    time.sleep(3)
    
    # 1. Sauvegarde locale dans le fichier JSON
    try:
        echanges = []
        if os.path.exists(HISTORIQUE_CONV_FILE):
            with open(HISTORIQUE_CONV_FILE, "r", encoding="utf-8") as f:
                echanges = json.load(f)
        echanges.append({
            "date":  time.strftime("%d/%m/%Y"),
            "heure": time.strftime("%H:%M"),
            "user":  user_text[:2000],
            "model": model_text[:3000],
        })
        if len(echanges) > MAX_ECHANGES_FICHIER:
            echanges = echanges[-MAX_ECHANGES_FICHIER:]
        with open(HISTORIQUE_CONV_FILE, "w", encoding="utf-8") as f:
            json.dump(echanges, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CONV] Erreur sauvegarde historique: {e}")

    # 2. Sauvegarde dans la note 'Journal_Discussions.md' du coffre Obsidian configuré
    try:
        import obsidian_helper
        success, content = obsidian_helper.lire_note("Journal_Discussions")
        if not success:
            content = "# Journal des Discussions JARVIS\n\nCe journal enregistre l'historique complet de vos échanges avec JARVIS.\n\n"
            
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        nouvel_echange = f"### Échange du {timestamp}\n- **Utilisateur** : {user_text}\n- **JARVIS** : {model_text}\n\n"
        
        # Concaténer le nouvel échange au tout début (sous le titre)
        lines = content.split("\n")
        header = []
        rest_lines = []
        
        for line in lines:
            if line.startswith("# ") or (line.strip() and not line.startswith("##") and not line.startswith("###") and not line.startswith("- ") and len(header) < 3):
                header.append(line)
            else:
                rest_lines.append(line)
                
        header_content = "\n".join(header).strip()
        past_content = "\n".join(rest_lines).strip()
        
        nouveau_contenu = f"{header_content}\n\n{nouvel_echange}{past_content}"
        obsidian_helper.creer_ou_modifier_note("Journal_Discussions", nouveau_contenu)
    except Exception as e:
        print(f"[OBSIDIAN] Erreur lors de la sauvegarde de l'historique dans Obsidian : {e}")

def _sauvegarder_echange_conv(user_text: str, model_text: str):
    """Lance la sauvegarde de l'échange en arrière-plan pour ne pas ralentir Jarvis."""
    threading.Thread(target=_sauvegarder_echange_conv_sync, args=(user_text, model_text), daemon=True).start()

def _charger_historique_recent():
    """Charge les derniers échanges et retourne une liste types.Content."""
    if not os.path.exists(HISTORIQUE_CONV_FILE):
        return []
    try:
        with open(HISTORIQUE_CONV_FILE, "r", encoding="utf-8") as f:
            echanges = json.load(f)
        recents = echanges[-MAX_ECHANGES_CHARGE:]
        hist = []
        for e in recents:
            date_str = f"[{e.get('date','?')} {e.get('heure','?')}] "
            hist.append(types.Content(role="user",  parts=[types.Part(text=date_str + e["user"])]))
            hist.append(types.Content(role="model", parts=[types.Part(text=e["model"])]))
        print(f"[CONV] {len(recents)} echanges passes rechargees en memoire.")
        return hist
    except Exception as e:
        print(f"[CONV] Erreur chargement historique: {e}")
        return []

