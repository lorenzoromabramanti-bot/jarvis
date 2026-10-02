import os
try:
    import winreg
except ImportError:                    # macOS, Linux : pas de registre
    from config import ModuleAbsent
    winreg = ModuleAbsent("winreg", "le registre est propre a Windows")
import psutil
import json
import asyncio
from config import nom_utilisateur

def get_exclusions():
    """Charge les exclusions antivirus depuis jarvis_config.json."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("av_exclusions", [])
    except Exception as e:
        print(f"[AV] Erreur lors du chargement des exclusions : {e}")
    return []

def is_excluded(target, exclusions):
    """Vérifie si une cible de menace est dans la liste des exclusions."""
    if not target or not exclusions:
        return False
    t_norm = target.replace("\\", "/").lower()
    for exc in exclusions:
        exc_norm = exc.replace("\\", "/").lower()
        if exc_norm == t_norm or exc_norm in t_norm:
            return True
    return False

# Chaîne EICAR standard pour le test de détection antivirus
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

def check_registry_startup():
    """Analyse les clés de démarrage du registre Windows pour détecter des anomalies."""
    entries = []
    
    # HKCU Run
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        for i in range(256):
            try:
                name, val, typ = winreg.EnumValue(key, i)
                entries.append({"name": name, "path": val, "hive": "HKCU\\Run"})
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[AV] Erreur lecture registre HKCU : {e}")

    # HKLM Run
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        for i in range(256):
            try:
                name, val, typ = winreg.EnumValue(key, i)
                entries.append({"name": name, "path": val, "hive": "HKLM\\Run"})
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[AV] Erreur lecture registre HKLM : {e}")
        
    return entries

def check_running_processes():
    """Analyse tous les processus en cours d'exécution."""
    proc_list = []
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            info = proc.info
            proc_list.append({
                "pid": info.get('pid') or 0,
                "name": info.get('name') or '',
                "path": info.get('exe') or ''
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return proc_list

def collect_files_to_scan():
    """Collecte les fichiers les plus récents des dossiers sensibles pour l'analyse."""
    paths = []
    folders = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        os.environ.get("TEMP"),
        os.environ.get("TMP"),
        os.path.dirname(os.path.abspath(__file__))
    ]
    
    # Supprimer les doublons et les dossiers inexistants
    folders = list(set([os.path.abspath(f) for f in folders if f and os.path.exists(f)]))
    
    for folder in folders:
        try:
            for root, dirs, files in os.walk(folder):
                # Ignorer les dossiers lourds ou non significatifs
                for d in ["node_modules", "venv", ".git", "__pycache__", ".gemini", ".claude", "dist"]:
                    if d in dirs:
                        dirs.remove(d)
                
                # Limiter la profondeur à 2 sous-dossiers pour rester rapide
                rel_path = os.path.relpath(root, folder)
                depth = 0 if rel_path == "." else len(rel_path.split(os.sep))
                if depth > 2:
                    dirs.clear()
                    
                for file in files:
                    filepath = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(filepath)
                        paths.append((filepath, mtime))
                    except OSError:
                        pass
        except Exception as e:
            print(f"[AV] Erreur parcours dossier {folder} : {e}")
            
    # Trier par date de modification décroissante (les fichiers les plus récents en premier)
    paths.sort(key=lambda x: x[1], reverse=True)
    return [p[0] for p in paths[:200]]  # Caper à 200 fichiers pour l'animation HUD

def is_file_suspicious(filepath):
    """Analyse un fichier physique à la recherche de virus connus, EICAR ou signatures."""
    filename = os.path.basename(filepath).lower()
    
    # ── 1. Vérification EICAR (Chaîne de test antivirus universelle) ───────
    try:
        if os.path.isfile(filepath) and os.path.getsize(filepath) < 1024 * 500: # < 500 KB
            with open(filepath, 'rb') as f:
                content = f.read(2048)
                if EICAR_SIGNATURE in content:
                    return "Threat.EICAR.TestFile", "Chaîne de test antivirus standard détectée (EICAR)"
    except Exception:
        pass

    # ── 2. Vérification des doubles extensions (ex: facture.pdf.exe) ────────
    parts = filename.split('.')
    if len(parts) >= 3:
        dangerous_exts = ["exe", "bat", "cmd", "vbs", "js", "scr", "msi", "lnk", "pif", "com"]
        if parts[-1] in dangerous_exts:
            benign_exts = ["pdf", "jpg", "jpeg", "png", "txt", "doc", "docx", "xls", "xlsx", "zip", "rar", "mp4"]
            if parts[-2] in benign_exts:
                return "Suspicious.DoubleExtension", f"Double extension détectée : .{parts[-2]}.{parts[-1]}"

    # ── 3. Recherche de mots-clés suspects dans le nom ─────────────────────
    suspicious_keywords = ["mimikatz", "keylogger", "ransomware", "miner.exe", "backdoor", "trojan", "virus.exe"]
    for kw in suspicious_keywords:
        if kw in filename:
            return "Suspicious.Keywords", f"Nom de fichier suspect contenant : {kw}"

    # ── 4. Fichier exécutable dans le répertoire Temp ──────────────────────
    if "temp" in filepath.lower() or "tmp" in filepath.lower():
        if filename.endswith((".exe", ".scr", ".pif", ".vbs", ".bat")):
            return "Suspicious.TempExecutable", "Fichier exécutable détecté dans les répertoires temporaires"

    return None, None

# Tâche active de scan pour permettre l'annulation
ACTIVE_SCAN_TASK = None

async def executer_scan_antivirus(ws_broadcast_callback, parler_callback):
    """Exécute l'analyse antivirus complète étape par étape et diffuse la progression."""
    global ACTIVE_SCAN_TASK
    threats_detected = []
    exclusions = get_exclusions()
    
    try:
        # Étape 1 : Initialisation
        await ws_broadcast_callback({
            "type": "av_start",
            "message": "Initialisation du moteur antivirus de J.A.R.V.I.S..."
        })
        await asyncio.sleep(1.0)
        
        # Étape 2 : Analyse du Registre de démarrage
        await ws_broadcast_callback({
            "type": "av_progress",
            "step": "registry",
            "message": "Analyse de la base de registre de démarrage Windows...",
            "scanned": 0,
            "total": 100,
            "percent": 5,
            "threats_found": len(threats_detected)
        })
        await asyncio.sleep(0.8)
        
        reg_entries = check_registry_startup()
        for reg in reg_entries:
            # Vérifier si l'entrée est suspecte
            path_lower = reg["path"].lower()
            for kw in ["temp", "tmp", "mimikatz", "miner", "keylogger", "exploit"]:
                if kw in path_lower or kw in reg["name"].lower():
                    threat = {
                        "type": "registry",
                        "name": reg["name"],
                        "target": reg["path"],
                        "class": "Suspicious.RegistryStartup",
                        "desc": f"Entrée de démarrage suspecte ({reg['hive']})"
                    }
                    if is_excluded(threat["target"], exclusions):
                        continue
                    threats_detected.append(threat)
                    await ws_broadcast_callback({
                        "type": "av_threat_detected",
                        "threat": threat
                    })
        
        # Étape 3 : Analyse des Processus Actifs
        await ws_broadcast_callback({
            "type": "av_progress",
            "step": "processes",
            "message": "Analyse des processus en cours d'exécution...",
            "scanned": 0,
            "total": 100,
            "percent": 15,
            "threats_found": len(threats_detected)
        })
        await asyncio.sleep(0.8)
        
        processes = check_running_processes()
        for i, proc in enumerate(processes):
            name_lower = proc["name"].lower()
            path_lower = proc["path"].lower()
            
            # Détection heuristique sur le processus
            detected = False
            desc = ""
            if "mimikatz" in name_lower or "miner.exe" in name_lower or "keylogger" in name_lower:
                detected = True
                desc = "Processus lié à un outil malveillant connu"
            elif ("temp" in path_lower or "tmp" in path_lower) and name_lower.endswith((".exe", ".bat")):
                detected = True
                desc = "Processus actif lancé depuis le dossier temporaire"
                
            if detected:
                threat = {
                    "type": "process",
                    "name": proc["name"],
                    "target": f"PID {proc['pid']} ({proc['path']})",
                    "class": "Suspicious.ActiveProcess",
                    "desc": desc
                }
                if is_excluded(threat["target"], exclusions) or is_excluded(proc["path"], exclusions):
                    continue
                threats_detected.append(threat)
                await ws_broadcast_callback({
                    "type": "av_threat_detected",
                    "threat": threat
                })
            
            # Transmettre périodiquement pour faire vivre l'UI
            if i % 15 == 0:
                await ws_broadcast_callback({
                    "type": "av_progress",
                    "step": "processes",
                    "message": f"Vérification des processus actifs : {proc['name']} (PID {proc['pid']})",
                    "scanned": i,
                    "total": len(processes),
                    "percent": int(15 + (i / len(processes)) * 15),
                    "threats_found": len(threats_detected)
                })
                await asyncio.sleep(0.02)
                
        # Étape 4 : Analyse des fichiers physiques
        await ws_broadcast_callback({
            "type": "av_progress",
            "step": "files",
            "message": "Indexation et collecte des fichiers récents...",
            "scanned": 0,
            "total": 100,
            "percent": 30,
            "threats_found": len(threats_detected)
        })
        await asyncio.sleep(0.8)
        
        files_to_scan = collect_files_to_scan()
        total_files = len(files_to_scan)
        
        for idx, filepath in enumerate(files_to_scan):
            t_class, t_desc = is_file_suspicious(filepath)
            if t_class:
                threat = {
                    "type": "file",
                    "name": os.path.basename(filepath),
                    "target": filepath,
                    "class": t_class,
                    "desc": t_desc
                }
                if is_excluded(threat["target"], exclusions):
                    continue
                threats_detected.append(threat)
                await ws_broadcast_callback({
                    "type": "av_threat_detected",
                    "threat": threat
                })
                
            # Envoyer la progression pour chaque fichier (pour que les logs défilent joliment sur l'écran !)
            pct = int(30 + ((idx + 1) / total_files) * 69) if total_files > 0 else 99
            await ws_broadcast_callback({
                "type": "av_progress",
                "step": "files",
                "message": filepath,
                "scanned": idx + 1,
                "total": total_files,
                "percent": pct,
                "threats_found": len(threats_detected)
            })
            # Sommeil de 50ms pour donner un effet défilement agréable de 20 fichiers/seconde
            await asyncio.sleep(0.05)
            
        # Étape 5 : Finalisation
        status = "infected" if threats_detected else "clean"
        await ws_broadcast_callback({
            "type": "av_complete",
            "status": status,
            "percent": 100,
            "threats": threats_detected
        })
        
        if status == "infected":
            await parler_callback(f"Analyse terminée, {nom_utilisateur()}. Attention, j'ai détecté {len(threats_detected)} menace(s) de sécurité sur votre système. Consultez la console pour plus de détails.")
        else:
            await parler_callback("Analyse de sécurité terminée. Votre système est entièrement sécurisé. Aucun virus n'a été détecté.")
            
    except asyncio.CancelledError:
        print("[AV] Analyse antivirus annulée par l'utilisateur.")
        await ws_broadcast_callback({
            "type": "av_cancel",
            "message": "Analyse interrompue par l'utilisateur."
        })
    except Exception as e:
        print(f"[AV] Erreur pendant l'analyse antivirus : {e}")
        await ws_broadcast_callback({
            "type": "av_complete",
            "status": "error",
            "message": f"Erreur système durant le scan : {e}"
        })
        await parler_callback("Une erreur s'est produite lors de l'analyse antivirus de votre ordinateur.")
    finally:
        ACTIVE_SCAN_TASK = None
