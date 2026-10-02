import os
import base64
import time
import uuid
try:
    import pyautogui
except BaseException:
    pyautogui = None
try:
    import cv2
except ImportError:
    cv2 = None
import asyncio
import json
try:
    import requests
except ImportError:
    requests = None
from dotenv import load_dotenv
from config import nom_utilisateur

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def jarvis_vision_cliquer(instruction):
    try:
        # On attend un peu que l'UI soit stable
        time.sleep(0.5)
        path_ss = "jarvis_vision_temp.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(path_ss)
        img_w, img_h = screenshot.size  # Dimensions réelles de la capture d'écran
        img = Image.open(path_ss)
        prompt_vision = (
            f"Tu es l'oeil de JARVIS. Voici une capture de l'écran de {nom_utilisateur()} ({img_w}x{img_h} pixels).\n"
            f"Instruction : {instruction}\n"
            "Trouve l'élément demandé (bouton, texte, icône ou numéro dans une liste) sur l'écran.\n"
            "Si l'instruction mentionne un chiffre (ex: 'musique numéro 4'), cherche ce chiffre ou le morceau correspondant dans la liste.\n"
            "Réponds UNIQUEMENT en JSON avec ce format :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description courte de l'élément\"}\n"
            "Les coordonnées sont normalisées de 0 à 1000 (0=coin haut-gauche, 1000=coin bas-droit)."
        )
        response = client.models.generate_content(model=CHOSEN_MODEL, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        print(f"[VISION] Gemini a renvoyé : {rep_text}")
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        # Centre de la bounding box, converti en pixels réels via les dimensions de la capture
        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)
        
        print(f"[VISION] Cible identifiée : {data.get('description', 'inconnu')} à ({target_x}, {target_y})")

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.2)
        
        # DOUBLE-CLIC si c'est une musique ou un chiffre pour être sûr de lancer la lecture
        t_inst = instruction.lower()
        if any(keyword in t_inst for keyword in ["musique", "chanson", "piste", "numéro", "numero", "titre"]):
            print(f"[VISION] Double-clic sur l'élément de liste : {target_x}, {target_y}")
            pyautogui.doubleClick()
        else:
            pyautogui.click()

        if os.path.exists(path_ss):
            os.remove(path_ss)
        desc = data.get("description", instruction)
        return f"C'est fait {nom_utilisateur()}, j'ai cliqué sur : {desc}."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return f"Je vois l'interface, mais je n'ai pas réussi à identifier l'élément précis, {nom_utilisateur()}."

async def jarvis_vision_ecrire(instruction, texte_a_taper):
    try:
        import pyperclip
        path_ss = "jarvis_vision_temp.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(path_ss)
        img_w, img_h = screenshot.size
        img = Image.open(path_ss)
        prompt_vision = (
            f"Tu es la vision de JARVIS. {nom_utilisateur()} veut écrire dans le champ : {instruction}.\n"
            f"Résolution de la capture : {img_w}x{img_h} pixels.\n"
            "Trouve EXACTEMENT la position de ce champ de saisie de texte.\n"
            "Les coordonnées sont normalisées de 0 à 1000.\n"
            "Réponds UNIQUEMENT en JSON :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description du champ\"}\n"
            "Exemple : {\"box\": [250, 480, 290, 520], \"description\": \"champ de recherche Google\"}"
        )
        response = client.models.generate_content(model=CHOSEN_MODEL, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.15)
        pyautogui.click()
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')  # Effacer le contenu existant
        time.sleep(0.1)
        # Coller via presse-papiers pour supporter les accents et caractères spéciaux
        pyperclip.copy(texte_a_taper)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        pyautogui.press('enter')

        if os.path.exists(path_ss):
            os.remove(path_ss)
        return f"C'est fait {nom_utilisateur()}. J'ai saisi '{texte_a_taper}' dans {instruction}."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return f"J'ai eu un petit souci technique pour taper le texte, {nom_utilisateur()}."

async def jarvis_vision_rechercher_sur_site(texte_recherche):
    """Trouve la barre de recherche sur la page actuelle et tape la requête."""
    try:
        import pyperclip
        path_ss = "jarvis_vision_temp.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(path_ss)
        img_w, img_h = screenshot.size
        img = Image.open(path_ss)
        prompt_vision = (
            f"Tu es la vision de JARVIS. {nom_utilisateur()} veut faire une recherche sur le site affiché à l'écran.\n"
            f"Résolution de la capture : {img_w}x{img_h} pixels.\n"
            "Localise la BARRE DE RECHERCHE principale du site (champ search, zone avec icône loupe, "
            "placeholder 'Rechercher', 'Search', 'Chercher'...).\n"
            "Si tu vois une barre d'adresse de navigateur ET une barre de recherche du site, "
            "préfère la barre de recherche du site.\n"
            "Les coordonnées sont normalisées de 0 à 1000 (0=haut-gauche, 1000=bas-droite).\n"
            "Réponds UNIQUEMENT en JSON :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description de la barre trouvée\"}\n"
            "Exemple : {\"box\": [48, 220, 78, 820], \"description\": \"barre de recherche YouTube\"}"
        )
        response = client.models.generate_content(model=CHOSEN_MODEL, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.15)
        pyautogui.click()
        time.sleep(0.35)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyperclip.copy(texte_recherche)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.15)
        pyautogui.press('enter')

        if os.path.exists(path_ss):
            os.remove(path_ss)
        desc = data.get("description", "barre de recherche")
        return f"C'est fait {nom_utilisateur()} ! J'ai tapé '{texte_recherche}' dans la {desc} et j'ai validé."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return f"Je n'ai pas réussi à trouver la barre de recherche sur ce site, {nom_utilisateur()}."

# Caméras VIRTUELLES connues -- elles s'ouvrent sans erreur et renvoient de
# vraies frames (donc indétectables par un simple "cap.isOpened()"), mais
# sans flux réel derrière, elles renvoient leur propre logo/placeholder.
# Cas constaté : sur un PC sans webcam physique mais avec "NVIDIA Broadcast",
# capturer dessus renvoie une image "valide" (bon format, bonnes dimensions)
# qui n'est que le logo NVIDIA. Jamais annoncer une capture comme
# réussie sur une caméra dont on sait qu'elle n'est que virtuelle.
_CAMERAS_VIRTUELLES = ("nvidia broadcast", "obs virtual camera", "snap camera",
                        "manycam", "xsplit vcam", "droidcam")


def camera_physique_disponible():
    """
    Une caméra qui n'est PAS sur la liste des caméras virtuelles connues
    est-elle déclarée à Windows ? Best-effort : si la détection elle-même
    échoue (WMI indisponible, etc.), on ne bloque pas la capture -- on
    laisse cap.isOpened() trancher, comme avant. Cette fonction sert
    seulement à éviter une "réussite" trompeuse sur une caméra 100%
    virtuelle connue, pas à garantir la détection de tout matériel.
    """
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_PnPEntity | "
             "Where-Object { $_.Name -match 'camera|webcam|broadcast|video' } | "
             "Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=10)
        noms = [l.strip().lower() for l in r.stdout.splitlines() if l.strip()]
        if not noms:
            return False
        return any(n not in _CAMERAS_VIRTUELLES for n in noms)
    except Exception as e:
        print(f"[CAMERA] Détection matériel impossible ({e}) — capture tentée quand même.")
        return True


async def capturer_frame_camera():
    """
    Ouvre la caméra configurée (index/label dans jarvis_config.json, même
    résolution que jarvis_vision_camera) et renvoie une frame OpenCV brute.

    Renvoie (frame, None) en cas de succès, (None, message_erreur) sinon.
    Extrait de jarvis_vision_camera pour être réutilisable par un appelant
    qui n'a besoin QUE de l'image (pas de l'analyse Gemini Vision qui suit),
    comme la détection de présence -- lui éviter le coût d'un appel modèle
    à chaque frame.
    """
    if cv2 is None:
        return None, "OpenCV (cv2) n'est pas installé."
    if not camera_physique_disponible():
        return None, ("aucune webcam physique détectée sur cette machine "
                       "(seule une caméra virtuelle type NVIDIA Broadcast est déclarée).")

    cap = None
    try:
        config_path = "jarvis_config.json"
        camera_idx = None
        camera_label = None
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    camera_idx = config.get("camera_device_index")
                    camera_label = config.get("camera_device_label")
            except Exception as e:
                print(f"[VISION] Erreur lors du chargement de la config de caméra : {e}")

        if camera_label:
            try:
                from pygrabber.dshow_graph import FilterGraph
                graph = FilterGraph()
                devices = graph.get_input_devices()

                def match_names(lbl, dev_name):
                    def get_clean_words(s):
                        clean = "".join(c if c.isalnum() or c.isspace() else " " for c in s.lower())
                        return {w for w in clean.split() if len(w) > 2}
                    return len(get_clean_words(lbl).intersection(get_clean_words(dev_name))) >= 2

                for idx, name in enumerate(devices):
                    if match_names(camera_label, name):
                        camera_idx = idx
                        print(f"[CAMERA] Correspondance par label : '{camera_label}' -> Index {camera_idx} ({name})")
                        break
            except Exception as e:
                print(f"[CAMERA] Échec énumération pygrabber : {e}")

        if camera_idx is not None:
            try:
                camera_idx = int(camera_idx)
                cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap.release()
                    cap = cv2.VideoCapture(camera_idx)
            except Exception as e:
                print(f"[CAMERA] Échec d'ouverture index {camera_idx} : {e}")
                cap = None

        if not cap or not cap.isOpened():
            for idx in [0, 1, 2]:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if cap.isOpened():
                    break
                cap.release()
            if not cap or not cap.isOpened():
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    return None, "impossible d'accéder à la caméra (utilisée ailleurs ?)."

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        start_time = time.time()
        while time.time() - start_time < 2.0:
            cap.read()
            await asyncio.sleep(0.1)

        ret, frame = cap.read()
        if not ret or frame is None:
            return None, "la capture a échoué."
        return frame, None
    except Exception as e:
        return None, f"erreur technique : {e}"
    finally:
        if cap:
            cap.release()


async def jarvis_vision_camera(question_utilisateur=None, garder_fichier=False):
    """Capture une image depuis la caméra (via le frontend ou OpenCV) et l'analyse avec Gemini Vision.

    `garder_fichier=True` : renvoie (description, chemin_du_jpg) au lieu de
    juste la description, et ne supprime pas le fichier -- pour un appelant
    qui a besoin de l'image elle-même (ex. l'envoyer sur Discord), pas
    seulement de sa description parlée. Comportement par défaut inchangé.
    """
    import builtins
    USER_NAME = builtins.get_user_name() if hasattr(builtins, "get_user_name") else f"{nom_utilisateur()}"
    parler = builtins.parler
    demander_ia_vision = builtins.demander_ia_vision
    
    img_b64 = None
    
    # ── 1. Tenter d'obtenir l'image directement depuis le frontend (Caméra active ou getUserMedia) ──
    try:
        if hasattr(builtins, "request_camera_capture"):
            print("[CAMERA] Tentative d'obtention de la frame depuis le frontend...")
            img_b64 = await builtins.request_camera_capture()
            if img_b64:
                print("[CAMERA] Frame obtenue avec succès depuis le frontend.")
    except Exception as e:
        print(f"[CAMERA] Échec de la capture via le frontend : {e}")

    # ── 2. Fallback OpenCV si le frontend n'a pas renvoyé d'image ──
    path_cam = None
    if not img_b64:
        print("[CAMERA] Fallback : Utilisation d'OpenCV (cv2.VideoCapture)...")
        frame, erreur = await capturer_frame_camera()
        if frame is None:
            message_erreur = f"Désolé {USER_NAME}, {erreur}"
            return (message_erreur, None) if garder_fichier else message_erreur

        # Nom unique : un appel voix et un appel Discord concurrents ne
        # doivent pas se marcher dessus sur le même fichier partagé.
        path_cam = f"jarvis_camera_temp_{uuid.uuid4().hex[:8]}.jpg"
        cv2.imwrite(path_cam, frame)
        with open(path_cam, "rb") as f:
            img_bytes = f.read()
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        if not garder_fichier and os.path.exists(path_cam):
            os.remove(path_cam)

    if garder_fichier and not (path_cam and os.path.exists(path_cam)):
        # Image obtenue via le frontend (pas de fichier local) : écrire le
        # base64 reçu pour donner quand même un chemin exploitable à l'appelant.
        path_cam = f"jarvis_camera_temp_{uuid.uuid4().hex[:8]}.jpg"
        with open(path_cam, "wb") as f:
            f.write(base64.b64decode(img_b64))

    # ── 3. Analyse avec Gemini Vision ──
    prompt_cam = f"{USER_NAME} te montre une image via sa caméra. Sa demande : '{question_utilisateur or 'Décris ce que tu vois'}'. Analyse l'image et réponds précisément."
    await parler(f"C'est fait {USER_NAME}, je regarde ce que votre caméra voit...")
    description = await demander_ia_vision(prompt_cam, img_b64)
    if garder_fichier:
        return description, path_cam
    return description

async def jarvis_vision_navigateur(question_utilisateur=None):
    """Capture une image depuis le navigateur via WebSocket et l'analyse avec Gemini Vision."""
    import builtins
    USER_NAME = builtins.get_user_name() if hasattr(builtins, "get_user_name") else f"{nom_utilisateur()}"
    parler = builtins.parler
    demander_ia_vision = builtins.demander_ia_vision
    CONNECTED_CLIENTS = getattr(builtins, "CONNECTED_CLIENTS", set())
    
    # Rediriger automatiquement vers la caméra si celle-ci est active à l'écran
    if getattr(builtins, "WEBCAM_ACTIVE", False):
        print("[VISION] La webcam est active. Redirection de la vision navigateur vers la caméra.")
        return await jarvis_vision_camera(question_utilisateur)
        
    try:
        if not CONNECTED_CLIENTS:
            return f"Désolé {USER_NAME}, l'interface web (navigateur) n'est pas connectée actuellement."
            
        await parler(f"J'active la vision du navigateur, un instant {USER_NAME}...")
        img_b64 = await request_screen_capture()
        
        if not img_b64:
            return f"Désolé {USER_NAME}, le flux vidéo est inactif. Pensez bien à cliquer sur le bouton 'Activer la vision' en haut à droite de l'interface web."
            
        if question_utilisateur:
            prompt_vision = f"{USER_NAME} te montre son navigateur/écran. Sa demande : '{question_utilisateur}'. Analyse l'image et réponds précisément."
        else:
            prompt_vision = f"Analyse cette capture du navigateur/écran de {USER_NAME} et décris-lui ce que tu vois en détail."
            
        reponse = await demander_ia_vision(prompt_vision, img_b64)
        return reponse
        
    except Exception as e:
        print(f"[VISION NAVIGATEUR ERROR] {e}")
        return f"Désolé {USER_NAME}, une erreur est survenue lors de l'accès à la vision du navigateur : {e}"

