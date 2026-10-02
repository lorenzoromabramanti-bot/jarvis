import os
try:
    import winreg
except ImportError:                    # macOS, Linux : pas de registre
    from config import ModuleAbsent
    winreg = ModuleAbsent("winreg", "le registre est propre a Windows")
import re
import shutil
import subprocess

def clean_name_for_search(name):
    """Nettoie le nom de l'application pour la recherche heuristique de traces."""
    # Retirer les parenthèses et les mentions de version
    name = re.sub(r'\(.*?\)|v\d+(\.\d+)*|\d+\.\d+(\.\d+)*', '', name)
    # Retirer les caractères spéciaux
    name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    return name.strip()

def list_installed_programs():
    """Énumère toutes les applications installées sur la machine à partir du Registre."""
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    
    programs = []
    seen = set()
    
    for hive, path in paths:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            info = winreg.QueryInfoKey(key)
            num_subkeys = info[0]
            
            for i in range(num_subkeys):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ)
                    
                    try:
                        name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                        uninstall_string, _ = winreg.QueryValueEx(subkey, "UninstallString")
                        
                        name = name.strip()
                        if not name or name in seen:
                            winreg.CloseKey(subkey)
                            continue
                            
                        seen.add(name)
                        
                        # Fallbacks facultatifs
                        publisher = ""
                        try: publisher, _ = winreg.QueryValueEx(subkey, "Publisher")
                        except OSError: pass
                        
                        version = ""
                        try: version, _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                        except OSError: pass
                        
                        install_location = ""
                        try: install_location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                        except OSError: pass
                        
                        icon_path = ""
                        try: icon_path, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                        except OSError: pass
                        
                        programs.append({
                            "name": name,
                            "subkey": subkey_name,
                            "publisher": publisher.strip(),
                            "version": version.strip(),
                            "uninstall_string": uninstall_string.strip(),
                            "install_location": install_location.strip(),
                            "icon_path": icon_path.strip(),
                            "hive": "HKLM" if hive == winreg.HKEY_LOCAL_MACHINE else "HKCU"
                        })
                    except OSError:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                except OSError:
                    continue
            winreg.CloseKey(key)
        except OSError:
            continue
            
    programs.sort(key=lambda x: x["name"].lower())
    return programs

def scan_file_leftovers(app_name, publisher="", install_location=""):
    """Recherche heuristique des traces de dossiers sur le disque dur."""
    app_name_clean = clean_name_for_search(app_name).lower()
    app_name_no_space = app_name_clean.replace(" ", "")
    
    publisher_clean = clean_name_for_search(publisher).lower() if publisher else ""
    
    leftovers = []
    seen_paths = set()
    
    # 1. Traiter le dossier d'installation officiel du registre s'il existe
    if install_location and os.path.exists(install_location):
        abs_path = os.path.abspath(install_location)
        # Éviter de cibler la racine d'un disque dur par erreur !
        if len(abs_path) > 4:
            seen_paths.add(abs_path)
            leftovers.append({
                "type": "folder",
                "path": abs_path,
                "desc": "Dossier d'installation officiel configuré dans le Registre Windows."
            })
            
    # Dossiers sensibles par défaut
    search_dirs = [
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        os.environ.get("ProgramData", "C:\\ProgramData"),
        os.path.expanduser("~/AppData/Local"),
        os.path.expanduser("~/AppData/Roaming"),
        os.path.expanduser("~/AppData/LocalLow")
    ]
    
    for base_dir in search_dirs:
        if not base_dir or not os.path.exists(base_dir):
            continue
        try:
            # Niveau 1
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if not os.path.isdir(item_path):
                    continue
                    
                item_lower = item.lower()
                item_no_space = item_lower.replace(" ", "")
                
                match = False
                if app_name_clean and len(app_name_clean) > 3 and app_name_clean in item_lower:
                    match = True
                elif app_name_no_space and len(app_name_no_space) > 3 and app_name_no_space in item_no_space:
                    match = True
                    
                if match:
                    abs_path = os.path.abspath(item_path)
                    if abs_path not in seen_paths and len(abs_path) > 4:
                        seen_paths.add(abs_path)
                        leftovers.append({
                            "type": "folder",
                            "path": abs_path,
                            "desc": f"Dossier associé à l'application dans {os.path.basename(base_dir)}."
                        })
                    continue  # Ne pas descendre au niveau 2 si le dossier parent correspond déjà
                    
                # Niveau 2 (ex: base_dir\Google\Android Studio)
                try:
                    for subitem in os.listdir(item_path):
                        subitem_path = os.path.join(item_path, subitem)
                        if not os.path.isdir(subitem_path):
                            continue
                            
                        subitem_lower = subitem.lower()
                        subitem_no_space = subitem_lower.replace(" ", "")
                        
                        sub_match = False
                        if app_name_clean and len(app_name_clean) > 3 and app_name_clean in subitem_lower:
                            sub_match = True
                        elif app_name_no_space and len(app_name_no_space) > 3 and app_name_no_space in subitem_no_space:
                            sub_match = True
                            
                        if sub_match:
                            abs_path = os.path.abspath(subitem_path)
                            if abs_path not in seen_paths and len(abs_path) > 4:
                                seen_paths.add(abs_path)
                                leftovers.append({
                                    "type": "folder",
                                    "path": abs_path,
                                    "desc": f"Dossier associé à l'application sous l'éditeur/catégorie '{item}'."
                                })
                except OSError:
                    pass
        except OSError:
            continue
            
    return leftovers

def scan_registry_leftovers(app_name, publisher=""):
    """Recherche heuristique des traces de clés de registre obsolètes."""
    app_name_clean = clean_name_for_search(app_name).lower()
    app_name_no_space = app_name_clean.replace(" ", "")
    
    publisher_clean = clean_name_for_search(publisher).lower() if publisher else ""
    
    leftovers = []
    
    hives = [
        (winreg.HKEY_CURRENT_USER, "Software"),
        (winreg.HKEY_LOCAL_MACHINE, "Software"),
        (winreg.HKEY_LOCAL_MACHINE, "Software\\Wow6432Node")
    ]
    
    for hive, base_path in hives:
        hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
        try:
            key = winreg.OpenKey(hive, base_path, 0, winreg.KEY_READ)
            info = winreg.QueryInfoKey(key)
            num_subkeys = info[0]
            
            for i in range(num_subkeys):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_name_lower = subkey_name.lower()
                    subkey_name_no_space = subkey_name_lower.replace(" ", "")
                    full_path = f"{hive_name}\\{base_path}\\{subkey_name}"
                    
                    match = False
                    if app_name_clean and len(app_name_clean) > 3 and app_name_clean in subkey_name_lower:
                        match = True
                    elif app_name_no_space and len(app_name_no_space) > 3 and app_name_no_space in subkey_name_no_space:
                        match = True
                        
                    if match:
                        leftovers.append({
                            "type": "registry",
                            "hive": hive_name,
                            "path": full_path,
                            "desc": "Clé de registre associée au nom de l'application."
                        })
                        continue  # Pas besoin d'entrer si la racine correspond
                        
                    # Niveau 2 (ex: HKLM\Software\Publisher\AppName)
                    if publisher_clean and len(publisher_clean) > 3 and publisher_clean in subkey_name_lower:
                        try:
                            pub_key = winreg.OpenKey(hive, f"{base_path}\\{subkey_name}", 0, winreg.KEY_READ)
                            pub_info = winreg.QueryInfoKey(pub_key)
                            for j in range(pub_info[0]):
                                subkey_subname = winreg.EnumKey(pub_key, j)
                                subkey_subname_lower = subkey_subname.lower()
                                subkey_subname_no_space = subkey_subname_lower.replace(" ", "")
                                
                                sub_match = False
                                if app_name_clean and len(app_name_clean) > 3 and app_name_clean in subkey_subname_lower:
                                    sub_match = True
                                elif app_name_no_space and len(app_name_no_space) > 3 and app_name_no_space in subkey_subname_no_space:
                                    sub_match = True
                                    
                                if sub_match:
                                    leftovers.append({
                                        "type": "registry",
                                        "hive": hive_name,
                                        "path": f"{full_path}\\{subkey_subname}",
                                        "desc": f"Clé de registre associée sous l'éditeur '{subkey_name}'."
                                    })
                            winreg.CloseKey(pub_key)
                        except OSError:
                            pass
                except OSError:
                    continue
            winreg.CloseKey(key)
        except OSError:
            continue
            
    return leftovers

def run_uninstall_process(uninstall_string):
    """Lance le processus de désinstallation officielle de l'application."""
    try:
        print(f"[UNINSTALLER] Lancement du désinstallateur officiel : {uninstall_string}")
        # Lancer le désinstallateur et attendre qu'il finisse
        p = subprocess.Popen(uninstall_string, shell=True)
        p.wait()
        return True, "Désinstallation officielle terminée."
    except Exception as e:
        print(f"[UNINSTALLER] Erreur lors du lancement de la désinstallation : {e}")
        return False, str(e)

def delete_registry_key_recursive(hive, path):
    """Supprime une clé de registre et toutes ses sous-clés récursivement."""
    # Convertir le nom de la ruche en objet winreg HKEY
    hkey_hive = winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    
    try:
        # 1. Ouvrir la clé pour lister les sous-clés
        key = winreg.OpenKey(hkey_hive, path, 0, winreg.KEY_ALL_ACCESS)
        info = winreg.QueryInfoKey(key)
        num_subkeys = info[0]
        
        subkeys = []
        for i in range(num_subkeys):
            subkeys.append(winreg.EnumKey(key, i))
        winreg.CloseKey(key)
        
        # 2. Supprimer les sous-clés d'abord récursivement
        for subkey in subkeys:
            delete_registry_key_recursive(hive, f"{path}\\{subkey}")
            
        # 3. Supprimer la clé elle-même
        parent_path, key_name = path.rsplit("\\", 1)
        parent_key = winreg.OpenKey(hkey_hive, parent_path, 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteKey(parent_key, key_name)
        winreg.CloseKey(parent_key)
        return True
    except Exception as e:
        print(f"[UNINSTALLER] Échec de la suppression de la clé de registre {hive}\\{path} : {e}")
        return False

def clean_leftover_item(item):
    """Supprime un élément résiduel (dossier ou clé de registre)."""
    item_type = item.get("type")
    path = item.get("path")
    
    if item_type == "folder":
        if not path or len(path) <= 4:
            return False, "Chemin invalide ou trop court pour suppression sécurisée."
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
                return True, "Dossier supprimé avec succès."
            return True, "Dossier déjà inexistant."
        except Exception as e:
            return False, f"Impossible de supprimer le dossier : {e}"
            
    elif item_type == "registry":
        hive = item.get("hive")
        # Le chemin contient la ruche au début (HKCU\ ou HKLM\), on doit le découper
        parts = path.split("\\", 1)
        if len(parts) < 2:
            return False, "Chemin de registre invalide."
        reg_path = parts[1]
        
        success = delete_registry_key_recursive(hive, reg_path)
        if success:
            return True, "Clé de registre supprimée avec succès."
        return False, "Échec de la suppression de la clé."
        
    return False, "Type de résidu inconnu."
