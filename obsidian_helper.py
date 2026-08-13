import os
import glob
import json
from config import nom_utilisateur

def obtenir_chemin_vault():
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                vault_path = data.get("obsidian_vault_path")
                if vault_path and os.path.isdir(vault_path):
                    return vault_path
    except Exception:
        pass
    
    # Par défaut
    default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ObsidianVault")
    if not os.path.exists(default_path):
        os.makedirs(default_path, exist_ok=True)
    return default_path

def creer_ou_modifier_note(titre, contenu):
    """Crée ou modifie une note markdown dans le coffre."""
    vault = obtenir_chemin_vault()
    # Nettoyer le titre pour éviter les injections de chemin
    filename = os.path.basename(titre)
    if not filename.endswith(".md"):
        filename += ".md"
    
    filepath = os.path.join(vault, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(contenu)
        print(f"[OBSIDIAN] Note créée/modifiée : {filepath}")
        return True, f"Note '{titre}' créée dans votre coffre Obsidian, {nom_utilisateur()}."
    except Exception as e:
        print(f"[OBSIDIAN] Erreur création note : {e}")
        return False, f"Impossible de créer la note : {e}"

def lire_note(titre):
    """Lit le contenu d'une note markdown."""
    vault = obtenir_chemin_vault()
    filename = os.path.basename(titre)
    if not filename.endswith(".md"):
        filename += ".md"
    
    filepath = os.path.join(vault, filename)
    if not os.path.exists(filepath):
        return False, f"La note '{titre}' n'existe pas dans le coffre, {nom_utilisateur()}."
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return True, content
    except Exception as e:
        return False, f"Erreur lors de la lecture de la note : {e}"

def supprimer_note(titre):
    """Supprime une note markdown du coffre."""
    vault = obtenir_chemin_vault()
    filename = os.path.basename(titre)
    if not filename.endswith(".md"):
        filename += ".md"
    
    filepath = os.path.join(vault, filename)
    if not os.path.exists(filepath):
        return False, f"La note '{titre}' n'existe pas dans le coffre, {nom_utilisateur()}."
    
    try:
        os.remove(filepath)
        print(f"[OBSIDIAN] Note supprimée : {filepath}")
        return True, f"La note '{titre}' a été supprimée de votre coffre Obsidian, {nom_utilisateur()}."
    except Exception as e:
        return False, f"Erreur lors de la suppression de la note : {e}"

def lister_notes():
    """Liste toutes les notes markdown du coffre avec métadonnées de base."""
    vault = obtenir_chemin_vault()
    files = glob.glob(os.path.join(vault, "*.md"))
    notes = []
    for f in files:
        try:
            stat = os.stat(f)
            notes.append({
                "titre": os.path.basename(f)[:-3], # enlever le .md
                "taille": stat.st_size,
                "mtime": stat.st_mtime # date de modification
            })
        except Exception:
            pass
    # Trier par date de modification décroissante
    notes.sort(key=lambda x: x["mtime"], reverse=True)
    return notes

def rechercher_notes(query):
    """Recherche des fichiers markdown contenant le mot-clé dans le coffre."""
    vault = obtenir_chemin_vault()
    files = glob.glob(os.path.join(vault, "*.md"))
    results = []
    query = query.lower()
    for f in files:
        titre = os.path.basename(f)[:-3]
        matched = False
        snippet = ""
        
        # Match dans le titre
        if query in titre.lower():
            matched = True
        
        # Match dans le contenu
        try:
            with open(f, "r", encoding="utf-8") as file_obj:
                content = file_obj.read()
                if query in content.lower():
                    matched = True
                    # Extraire un court extrait
                    idx = content.lower().find(query)
                    start = max(0, idx - 40)
                    end = min(len(content), idx + 80)
                    snippet = "..." + content[start:end].replace("\n", " ") + "..."
        except Exception:
            pass
            
        if matched:
            results.append({
                "titre": titre,
                "snippet": snippet
            })
    return results
