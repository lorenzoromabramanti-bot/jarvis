import os
import shutil
import glob
import subprocess
from datetime import datetime
from pathlib import Path
try:
    import pyautogui
except BaseException:
    pyautogui = None
import ctypes
import time
from config import nom_utilisateur

from config import api_windows
user32 = api_windows("user32")   # substitut explicite hors Windows
def resoudre_chemin(chemin):
    if not chemin:
        return None
    chemin = chemin.strip().strip('"').strip("'")
    raccourcis = {
        "bureau": os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        "desktop": os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        "document": os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
        "documents": os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
        "téléchargement": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "téléchargements": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "telechargement": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "telechargements": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "downloads": os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        "image": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "images": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "photo": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "photos": os.path.join(os.environ.get("USERPROFILE", ""), "Pictures"),
        "vidéo": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "vidéos": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "video": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "videos": os.path.join(os.environ.get("USERPROFILE", ""), "Videos"),
        "musique": os.path.join(os.environ.get("USERPROFILE", ""), "Music"),
        "music": os.path.join(os.environ.get("USERPROFILE", ""), "Music"),
        "corbeille": "shell:RecycleBinFolder"
    }
    
    chemin_resolu = raccourcis.get(chemin.lower(), chemin)
    
    # Test des variantes françaises si le dossier anglais n'existe pas
    if not os.path.exists(chemin_resolu):
        variantes = {
            "Downloads": "Téléchargements",
            "Pictures": "Images",
            "Music": "Musique"
        }
        for eng, fra in variantes.items():
            if eng in chemin_resolu:
                test_fra = chemin_resolu.replace(eng, fra)
                if os.path.exists(test_fra):
                    chemin_resolu = test_fra
                    break
    return chemin_resolu

def trouver_extension(ext):
    for categorie, extensions in EXTENSIONS.items():
        if ext.lower() in extensions:
            return categorie
    return "Autres"

def ouvrir_dossier(chemin):
    global dossier_courant
    chemin_resolu = resoudre_chemin(chemin)
    if not chemin_resolu or (not os.path.exists(chemin_resolu) and not chemin_resolu.startswith("shell:")):
        return False, f"Dossier introuvable : {chemin_resolu}"
    dossier_courant = chemin_resolu
    # Utilisation de Popen pour ne pas bloquer
    if chemin_resolu.startswith("shell:"):
        subprocess.Popen(f'explorer "{chemin_resolu}"', shell=True)
    else:
        subprocess.Popen(['explorer', chemin_resolu])
    return True, chemin_resolu

def arranger_fenetres_dossiers():
    """Ouvre et dispose les dossiers Documents, Téléchargements, Images et Vidéos en mosaïque."""
    dossiers = [
        ("document", 0, 0),             # Haut Gauche
        ("téléchargement", 1, 0),       # Haut Droite
        ("image", 0, 1),               # Bas Gauche
        ("vidéo", 1, 1)                # Bas Droite
    ]
    
    sw, sh = pyautogui.size()
    w, h = sw // 2, (sh - 40) // 2  # -40 pour la barre des tâches approximative
    
    for nom, qx, qy in dossiers:
        ouvrir_dossier(nom)
        time.sleep(0.8) # Laisser le temps à Explorer de s'ouvrir
        
        # On tente de trouver la fenêtre active qui vient d'être ouverte
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            x = qx * w
            y = qy * h
            # SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0040)
    
    return f"J'ai ouvert et disposé vos dossiers principaux en mosaïque, {nom_utilisateur()}."

def lister_dossier(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return None, "Aucun dossier ouvert ou chemin invalide."
    fichiers  = []
    dossiers  = []
    for item in os.scandir(cible):
        if item.is_file():
            fichiers.append(item.name)
        elif item.is_dir():
            dossiers.append(item.name)
    return {"chemin": cible, "fichiers": fichiers, "dossiers": dossiers}, None

def trier_par_type(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert ou invalide."
    deplacements = 0
    erreurs      = 0
    categories   = {}
    for item in os.scandir(cible):
        if not item.is_file():
            continue
        ext       = Path(item.name).suffix
        categorie = trouver_extension(ext)
        dest_dir  = os.path.join(cible, categorie)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.name)
            if os.path.exists(dest_path):
                base  = Path(item.name).stem
                ext2  = Path(item.name).suffix
                dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, dest_path)
            deplacements += 1
            categories[categorie] = categories.get(categorie, 0) + 1
        except Exception as e:
            print(f"[FICHIER] Erreur deplacement {item.name} : {e}")
            erreurs += 1
    resume = ", ".join([f"{v} {k}" for k, v in categories.items()])
    return True, f"{deplacements} fichiers tries : {resume}. {erreurs} erreurs."

def trier_par_date(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert ou invalide."
    deplacements = 0
    erreurs      = 0
    for item in os.scandir(cible):
        if not item.is_file():
            continue
        try:
            mtime     = item.stat().st_mtime
            date      = datetime.fromtimestamp(mtime)
            annee     = str(date.year)
            mois      = date.strftime("%m - %B")
            dest_dir  = os.path.join(cible, annee, mois)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.name)
            if os.path.exists(dest_path):
                base      = Path(item.name).stem
                ext2      = Path(item.name).suffix
                dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, dest_path)
            deplacements += 1
        except Exception as e:
            print(f"[FICHIER] Erreur deplacement {item.name} : {e}")
            erreurs += 1
    return True, f"{deplacements} fichiers tries par date. {erreurs} erreurs."

def trier_par_type_puis_date(chemin=None):
    cible = chemin or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert."
    ok1, msg1 = trier_par_type(cible)
    if not ok1:
        return False, msg1
    for item in os.scandir(cible):
        if item.is_dir() and item.name in EXTENSIONS.keys():
            trier_par_date(item.path)
    return True, "Dossier trie par type puis par date dans chaque categorie."

def creer_sous_dossier(nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    nouveau = os.path.join(cible, nom)
    try:
        os.makedirs(nouveau, exist_ok=True)
        return True, f"Dossier {nom} cree."
    except Exception as e:
        return False, f"Erreur creation dossier : {e}"

def renommer_fichier(ancien_nom, nouveau_nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    ancien = os.path.join(cible, ancien_nom)
    nouveau = os.path.join(cible, nouveau_nom)
    try:
        os.rename(ancien, nouveau)
        return True, f"Fichier renomme en {nouveau_nom}."
    except Exception as e:
        return False, f"Erreur renommage : {e}"

def deplacer_fichier(nom_fichier, dossier_dest, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    source = os.path.join(cible, nom_fichier)
    dest   = os.path.join(cible, dossier_dest, nom_fichier)
    try:
        os.makedirs(os.path.join(cible, dossier_dest), exist_ok=True)
        shutil.move(source, dest)
        return True, f"{nom_fichier} deplace dans {dossier_dest}."
    except Exception as e:
        return False, f"Erreur deplacement : {e}"

def chercher_fichier(nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return [], "Aucun dossier ouvert."
    resultats = []
    for root, dirs, files in os.walk(cible):
        for f in files:
            if nom.lower() in f.lower():
                resultats.append(os.path.join(root, f))
    return resultats, None

