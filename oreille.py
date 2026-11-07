# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — L'oreille : micro + Silero VAD + Parakeet TDT 0.6B v3, dans un processus à part
=============================================================================================
Charger NeMo dans main2.py déjà lancé le tuait net (conflit de DLL pyarrow/torch, constaté le 31/08/2026) :
ici tout est importé au démarrage d'un processus neuf, et si l'oreille manque, JARVIS repasse sur son écoute
d'avant (speech_recognition + Google).

L'oreille écoute le micro EN CONTINU, même pendant que JARVIS parle :
  - Silero VAD découpe les phrases : fin de phrase après 0,5 s de silence (au lieu de 0,8 s fixes) ;
  - Google les transcrit et les met en file ; JARVIS les prend avec prochaine_phrase(). Mesuré le 23/10 sur
    le vrai micro (webcam) : Google reconnaît « Jarvis » 5 fois sur 5, Parakeet 1 sur 5 (« Jardis »,
    « Charvis »), et Parakeet a pris « Stop ! » pour « Спасибо » : il ne sert donc que sans Internet ;
  - JARVIS lui dit quand il parle (signaler_parole) : ce qu'elle entend pendant ce temps est sa propre voix
    dans les haut-parleurs, jeté ; sauf un ordre de coupure (« stop », « attends », « Jarvis »…) qui n'est
    pas un écho de ce qu'il dit : alors interruption() renvoie vrai et JARVIS se tait.
Au quotidien : torch + Silero seulement. Parakeet (NeMo, ≈ 4 Go de mémoire validée + 1,4 Go de carte
graphique) n'est chargé que si Google ne répond plus (Internet coupé). Pendant une partie (~/mode-jeu/actif.json), l'oreille s'arrête
d'elle-même ; JARVIS la relance après.

    venv\\Scripts\\python.exe oreille.py   -> http://127.0.0.1:8770
    GET  /phrase?attente=2  -> 200 {"texte"} ou 204 (rien)     POST /parle {"actif", "texte"}
    GET  /interruption      -> {"couper": bool}                POST /transcrire (PCM 16 bits mono 16 kHz)
    GET  /etat              -> {"pret", "ecoute", "appareil", "niveau", "phrases"}

Côté JARVIS, seul le client ci-dessous est importé (urllib seulement, aucune DLL).
"""
import collections
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
PORT = 8770
URL = f"http://127.0.0.1:{PORT}"
DEPOT, FICHIER = "nvidia/parakeet-tdt-0.6b-v3", "parakeet-tdt-0.6b-v3.nemo"
ACTIF_JEU = os.path.expanduser(r"~\mode-jeu\actif.json")
CONFIG = os.path.join(ICI, "jarvis_config.json")
MAX_OCTETS = 16000 * 2 * 30   # 30 s d'audio au plus
RELANCE = 120                 # s entre deux tentatives de démarrage du serveur
TRAME = 512                   # échantillons à 16 kHz (32 ms) : la taille que Silero attend
QUEUE_ECHO = 0.8              # s après la fin de sa parole où ce qu'on entend est encore son écho
MORCEAU_PARLANT = 2.5          # s : pendant qu'il parle, on écoute par morceaux (pas de pause dans sa voix)
GAIN_VAD = 16                 # le micro de la webcam capte à ~-50 dB : Silero, fait pour une voix plus forte, la ratait
# « Jarvis » entendu sur le PC (openWakeWord), SI un modèle est posé ici : complète Google quand il rate le mot, et
# marche sans Internet, où Parakeet ne l'entend qu'1 fois sur 5. Aucun modèle livré : le 1er essai d'entraînement
# (07/11, voix de synthèse françaises) faisait ~300 fausses alertes par heure. Sans modèle, rien ne change.
MODELE_EVEIL = os.path.join(ICI, "modeles", "jarvis_fr.onnx")
SEUIL_EVEIL = 0.5
COUPURE = re.compile(r"\b(jarvis|charvis|jardis|stop|arrete|attends?|tais[- ]toi|chut|silence|c est bon|ca suffit)\b")
# Sans « silence » ni « tais-toi » : ceux-là gardent leur sens d'avant dans JARVIS (il se met en veille).
COUPURE_SEULE = re.compile(r"(jarvis\W*)?(stop|arrete(\W*toi)?|attends?|chut|c est bon|ca suffit)\W*")
_etat = {"lancement": 0.0}


def _plat(texte):
    t = unicodedata.normalize("NFD", (texte or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 -]+", " ", t.replace("'", " ")).strip()


def jeu_en_cours():
    """Vrai pendant une partie (~/mode-jeu/actif.json) : l'oreille s'arrête pour libérer la mémoire.

    « oreille_en_jeu »: true dans jarvis_config.json -> faux : elle reste allumée et JARVIS t'entend aussi en jeu
    (environ 1 Go de mémoire en plus pendant la partie). Sans elle, JARVIS retombe
    en jeu sur l'écoute d'avant, dont les seuils (250 / 300) sont bien trop hauts pour le micro de la webcam.
    """
    try:
        with open(CONFIG, encoding="utf-8") as f:
            if json.load(f).get("oreille_en_jeu"):
                return False
    except (OSError, ValueError, AttributeError):
        pass
    try:
        with open(ACTIF_JEU, encoding="utf-8") as f:
            return bool(json.load(f).get("jeu"))
    except (OSError, ValueError, AttributeError):
        return False


def est_coupure_seule(texte):
    """« stop », « Jarvis, attends ! » : un ordre de se taire, rien à répondre."""
    return bool(COUPURE_SEULE.fullmatch(" ".join(_plat(texte).split())))


def est_echo(texte, dit):
    """Ce qu'on entend est-il JARVIS lui-même (ses mots, dans les haut-parleurs) ?"""
    mots = [m for m in _plat(texte).split() if len(m) > 2]
    if not mots:
        return True
    siens = set(_plat(dit).split())
    return sum(m in siens for m in mots) / len(mots) >= 0.6


def trier(texte, parlait, dit):
    """« garder » (une phrase pour JARVIS), « couper » (il doit se taire), « jeter » (son écho, du bruit).
    Pendant qu'il parle, un mot de coupure qu'il n'est pas lui-même en train de dire suffit, même mêlé à son écho."""
    if not parlait:
        return "garder"
    siens = set(_plat(dit).split())
    if any(m.group(0) not in siens for m in COUPURE.finditer(_plat(texte))):
        return "couper"
    return "jeter"


class Eveil:
    """Les « Jarvis » du détecteur local, rattachés aux phrases de Silero.

    La phrase qui contient l'éveil le garde même si Google l'a raté ; un « Jarvis » seul que Silero n'a pas découpé
    (trop faible sur le micro de la webcam) devient une phrase à lui tout seul, après `attente` s de calme.
    """

    def __init__(self, seuil=SEUIL_EVEIL, pause=1.6, attente=0.8):
        self.seuil, self.pause, self.attente = seuil, pause, attente
        self.t, self.dernier, self.fin_phrase = 0.0, -1e9, -1e9

    def score(self, s, t, parle):
        """Score du détecteur à l'instant t ; vrai pour un nouvel éveil (jamais pendant que JARVIS parle :
        « Jarvis » dans sa propre voix)."""
        if s < self.seuil or parle or t - self.dernier < self.pause:
            return False
        self.t = self.dernier = t
        return True

    def phrase(self, t_debut, t_fin):
        """Une phrase finit : contenait-elle l'éveil ?"""
        self.fin_phrase = t_fin
        if self.t and t_debut - 1.0 <= self.t <= t_fin:
            self.t = 0.0
            return True
        return False

    def seul(self, t, en_parole):
        """Vrai une fois pour un « Jarvis » sans phrase autour ; faux si une phrase vient de finir (elle le portait)."""
        if not self.t or en_parole or t - self.t <= self.attente:
            return False
        seul, self.t = self.fin_phrase < self.t - 1.5, 0.0
        return seul


def completer(texte, entendu):
    """Remet « Jarvis » que le détecteur a entendu et que la transcription a raté (JARVIS l'enlève de la commande)."""
    if not entendu or re.search(r"\bjarvis\b", _plat(texte)):
        return texte
    return f"Jarvis, {texte}" if texte else "Jarvis"


def _detecteur():
    """(openWakeWord avec le modèle « Jarvis » français, "") ou (None, raison) : Google seul, comme avant."""
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    if not cfg.get("eveil_local", True) or str(cfg.get("wake_word", "jarvis")).strip().lower() != "jarvis":
        return None, "désactivé (eveil_local, ou un autre mot que « jarvis »)"
    if not os.path.exists(MODELE_EVEIL):
        return None, "modèle absent : " + MODELE_EVEIL
    try:
        import openwakeword.utils
        from openwakeword.model import Model
        openwakeword.utils.download_models(model_names=["aucun"])  # ses 2 modèles de base, au 1er lancement seulement
        return Model(wakeword_models=[MODELE_EVEIL], inference_framework="onnx"), ""
    except Exception as e:  # openwakeword absent, pas d'Internet au 1er lancement
        return None, repr(e)


class Decoupeur:
    """Le flux du micro en phrases, d'après la probabilité de parole de Silero à chaque trame de 32 ms."""

    # Seuils bas et 0,6 s d'avant : le micro de la webcam rend « Jarvis » faible (énergie ~15 contre ~50 ensuite), et
    # Silero ne se déclenche souvent qu'après la virgule (« Jarvis, | quelle heure… »).
    def __init__(self, debut=0.4, fin=0.3, pause=0.5, avant=0.6, min_parole=0.3, max_parole=15.0, trame=0.032):
        self.debut, self.fin, self.pause, self.trame = debut, fin, pause, trame
        self.min_parole, self.max_parole = min_parole, max_parole
        self.avant = collections.deque(maxlen=max(1, int(avant / trame)))  # pour ne pas couper la 1re syllabe
        self.en_parole, self.morceaux, self.silence, self.t_debut = False, [], 0.0, 0.0

    def pousser(self, trame_pcm, prob, t):
        """(pcm, t_debut, t_fin) quand une phrase se termine, sinon None."""
        if not self.en_parole:
            self.avant.append(trame_pcm)
            if prob >= self.debut:
                self.en_parole, self.morceaux, self.silence = True, list(self.avant), 0.0
                self.t_debut = t - (len(self.avant) - 1) * self.trame
            return None
        self.morceaux.append(trame_pcm)
        self.silence = self.silence + self.trame if prob < self.fin else 0.0
        duree = len(self.morceaux) * self.trame
        if self.silence < self.pause and duree < self.max_parole:
            return None
        self.en_parole = False
        self.avant.clear()
        if duree - self.silence < self.min_parole:
            return None
        return b"".join(self.morceaux), self.t_debut, t


# ── Client (dans JARVIS) ─────────────────────────────────────────────────

def demarrer(lancer=subprocess.Popen):
    """Lance le serveur en arrière-plan, au plus une fois toutes les RELANCE secondes."""
    if time.time() - _etat["lancement"] < RELANCE:
        return
    _etat["lancement"] = time.time()
    python = os.path.join(ICI, "venv", "Scripts", "pythonw.exe")
    try:
        lancer([python if os.path.exists(python) else sys.executable, os.path.join(ICI, "oreille.py")],
               cwd=ICI, creationflags=0x08000000)
    except OSError as e:
        print(f"[OREILLE] Démarrage impossible : {e}")


def _requete(chemin, corps=None, delai=1.0):
    donnees = None if corps is None else (corps if isinstance(corps, bytes) else json.dumps(corps).encode())
    req = urllib.request.Request(URL + chemin, donnees, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=delai) as r:
        return r.status, (json.load(r) if r.status == 200 else None)


def prochaine_phrase(attente=2.0, requete=None):
    """La phrase suivante ; "" si rien n'a été dit ; None si l'oreille n'écoute pas (JARVIS écoute à l'ancienne)."""
    if jeu_en_cours():
        return None
    try:
        statut, donnees = (requete or _requete)(f"/phrase?attente={attente}", delai=attente + 3)
        return donnees.get("texte", "") if statut == 200 else ""
    except urllib.error.HTTPError:   # 503 : modèle en chargement ou micro indisponible
        return None
    except OSError:                  # pas lancée
        demarrer()
        return None


def signaler_parole(actif, texte="", requete=None):
    """JARVIS commence ou finit de parler : l'oreille sait alors que c'est sa voix qu'elle entend."""
    try:
        (requete or _requete)("/parle", {"actif": bool(actif), "texte": texte or ""}, delai=0.3)
    except OSError:
        pass


def interruption(requete=None):
    """Vrai si on vient de lui dire « stop », « attends »… pendant qu'il parle (lu une seule fois)."""
    try:
        statut, donnees = (requete or _requete)("/interruption", delai=0.3)
        return bool(donnees and donnees.get("couper"))
    except OSError:
        return False


def transcrire(pcm, envoyer=None, lancer=subprocess.Popen):
    """Pour l'écoute à l'ancienne : texte, ou None (serveur absent, en route, partie en cours) -> Google."""
    if jeu_en_cours() or not pcm:
        return None
    try:
        if envoyer:
            return envoyer(pcm)
        req = urllib.request.Request(URL + "/transcrire", pcm, {"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.load(r).get("texte", "")
    except urllib.error.HTTPError:
        return None
    except OSError:
        demarrer(lancer)
        return None


# ── Serveur (processus à part) ───────────────────────────────────────────

def _chemin_modele():
    from huggingface_hub import hf_hub_download
    return hf_hub_download(DEPOT, FICHIER)  # déjà dans le cache (F:\hf-cache) : ne télécharge rien


def _index_micro():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f).get("mic_device_index")
    except (OSError, ValueError):
        return None


def ouvrir_port(port, gestionnaire):
    """Le serveur HTTP de l'oreille, seul sur son port. http.server active SO_REUSEADDR, qui sous Windows laisse une
    2e oreille écouter le MÊME port (quatre ensemble le 06/11) ; sans lui, la 2e lève OSError et s'arrête."""
    from http.server import ThreadingHTTPServer

    class Serveur(ThreadingHTTPServer):
        allow_reuse_address = os.name != "nt"
    return Serveur(("127.0.0.1", port), gestionnaire)


def servir():
    import queue
    import threading
    import urllib.parse
    from http.server import BaseHTTPRequestHandler

    etat = {"pret": False, "modele": None, "chargement": False, "appareil": None, "ecoute": False, "niveau": 0, "phrases": 0,
            "eveil": "pas encore chargé", "journal": collections.deque(maxlen=10)}  # dernières phrases (diagnostic, /etat)
    parole = {"actif": False, "texte": "", "depuis": 0.0, "jusqua": 0.0}
    couper = threading.Event()
    file_phrases = queue.Queue()     # (t_fin, texte) pour JARVIS
    a_transcrire = queue.Queue()     # (pcm, t_debut, t_fin) du découpeur

    class Requete(BaseHTTPRequestHandler):
        def do_GET(self):
            chemin = urllib.parse.urlparse(self.path)
            if chemin.path == "/etat":
                return self.repondre(200, {"pret": etat["pret"], "parakeet": etat["modele"] is not None, "ecoute": etat["ecoute"],
                                           "appareil": etat["appareil"], "niveau": etat["niveau"],
                                           "phrases": etat["phrases"], "modele": DEPOT, "eveil": etat["eveil"],
                                           "journal": list(etat["journal"]), "parle": parole["actif"]})
            if chemin.path == "/interruption":
                vu = couper.is_set()
                couper.clear()
                return self.repondre(200, {"couper": vu})
            if chemin.path == "/phrase":
                if not (etat["pret"] and etat["ecoute"]):
                    return self.repondre(503, {"erreur": "pas prête"})
                attente = min(10.0, float(urllib.parse.parse_qs(chemin.query).get("attente", ["2"])[0]))
                limite = time.time() + attente
                while True:
                    try:
                        t_fin, texte = file_phrases.get(timeout=max(0.01, limite - time.time()))
                    except queue.Empty:
                        return self.repondre(204, None)
                    if time.time() - t_fin < 10:  # une phrase de plus de 10 s n'attend plus personne
                        return self.repondre(200, {"texte": texte})
            self.repondre(404, {"erreur": "introuvable"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            if self.path == "/parle":
                d = json.loads(self.rfile.read(n) or b"{}") if 0 < n <= 20000 else {}
                maintenant = time.time()
                if d.get("actif"):
                    parole.update(actif=True, texte=str(d.get("texte", ""))[:4000], depuis=maintenant)
                else:
                    parole.update(actif=False, jusqua=maintenant)
                return self.repondre(200, {"ok": True})
            if self.path != "/transcrire":
                return self.repondre(404, {"erreur": "introuvable"})
            if etat["modele"] is None:
                charger_parakeet()
                return self.repondre(503, {"erreur": "Parakeet en chargement"})
            if not 0 < n <= MAX_OCTETS:
                return self.repondre(400, {"erreur": "audio vide ou trop long"})
            t = time.time()
            texte = transcrire_local(self.rfile.read(n))
            self.repondre(200, {"texte": texte, "secondes": round(time.time() - t, 3)})

        def repondre(self, code, donnees):
            self.send_response(code)
            if donnees is None:
                return self.end_headers()
            corps = json.dumps(donnees, ensure_ascii=False).encode()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, *a):
            pass

    serveur = ouvrir_port(PORT, Requete)  # d'abord le port : une 2e oreille s'arrête ici
    threading.Thread(target=serveur.serve_forever, daemon=True).start()

    # Même ordre que nemotron_asr.py : pyarrow avant torch, sinon conflit OpenMP sous Windows.
    try:
        import pyarrow.dataset  # noqa: F401
    except Exception:
        pass
    import numpy as np
    import torch
    from silero_vad import load_silero_vad

    etat["appareil"] = "cuda" if torch.cuda.is_available() else "cpu"
    verrou = threading.Lock()

    def charger_parakeet():
        """Parakeet ne sert que sans Internet : chargé à ce moment-là seulement (NeMo + modèle ≈ 4 Go de mémoire
        validée et 1,4 Go de carte graphique, mesuré le 23/10 : chargé en permanence, il frôlait la limite)."""
        if etat["modele"] is not None or etat["chargement"]:
            return
        etat["chargement"] = True

        def charger():
            try:
                import nemo.collections.asr as nemo_asr
                m = nemo_asr.models.ASRModel.restore_from(_chemin_modele(), map_location=etat["appareil"])
                m.eval()
                with torch.inference_mode():  # échauffement : la 1re transcription prenait 23 s
                    m.transcribe([np.zeros(16000, dtype=np.float32)], batch_size=1, verbose=False)
                etat["modele"] = m
                etat["journal"].append(f"{time.strftime('%H:%M:%S')} Parakeet chargé (Internet coupé)")
            finally:
                etat["chargement"] = False
        threading.Thread(target=charger, daemon=True).start()

    def transcrire_local(pcm):
        """Parakeet, ou "" tant qu'il se charge (la phrase est perdue, pas JARVIS)."""
        if etat["modele"] is None:
            charger_parakeet()
            return ""
        son = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        son = son / max(1e-4, float(np.abs(son).max())) * 0.9  # micro faible : on ramène le volume
        with verrou, torch.inference_mode():
            sortie = etat["modele"].transcribe([son], batch_size=1, verbose=False)
        return (sortie[0].text if hasattr(sortie[0], "text") else str(sortie[0])).strip()

    vad = load_silero_vad()
    etat["pret"] = True

    import speech_recognition as sr

    def google(pcm):
        """Google comme l'écoute d'avant ; "" s'il n'a rien compris ; None sans Internet (-> Parakeet)."""
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        x = (x / max(1.0, float(np.abs(x).max())) * 0.9 * 32767).astype(np.int16).tobytes()
        try:
            return sr.Recognizer().recognize_google(sr.AudioData(x, 16000, 2), language="fr-FR")
        except sr.UnknownValueError:
            return ""
        except Exception:
            return None

    def traducteur():
        """Les phrases découpées -> texte -> trié selon que JARVIS parlait ou non."""
        while True:
            pcm, t_debut, t_fin, entendu = a_transcrire.get()
            parlait = parole["actif"] or t_debut < parole["jusqua"] + QUEUE_ECHO
            texte = google(pcm)  # même pendant qu'il parle : Parakeet a pris « Stop ! » pour « Спасибо » (23/10)
            if texte is None:
                texte = transcrire_local(pcm)  # sans Internet
            texte = completer(texte, entendu)
            if not texte:
                etat["journal"].append(f"{time.strftime('%H:%M:%S')} vide : {len(pcm) / 32000:.1f} s d'audio")
                continue
            verdict = trier(texte, parlait, parole["texte"])
            etat["journal"].append(f"{time.strftime('%H:%M:%S')} {verdict} : {texte}")
            if verdict == "couper":
                couper.set()
            if verdict != "jeter":
                etat["phrases"] += 1
                file_phrases.put((t_fin, texte))

    def micro():
        import pyaudio
        p = pyaudio.PyAudio()
        for taux in (16000, 48000):  # 48 kHz ramené à 16 kHz (1 échantillon sur 3, moyenné) si le micro refuse 16 kHz
            try:
                flux = p.open(format=pyaudio.paInt16, channels=1, rate=taux, input=True,
                              input_device_index=_index_micro(), frames_per_buffer=TRAME * taux // 16000)
                break
            except OSError as e:
                print(f"[OREILLE] Micro à {taux} Hz refusé : {e}", flush=True)
        else:
            return
        detecteur, raison = _detecteur()
        etat["eveil"] = "actif" if detecteur else raison
        nom_eveil, eveil = os.path.splitext(os.path.basename(MODELE_EVEIL))[0], Eveil()
        etat["ecoute"] = True
        decoupeur = Decoupeur()
        try:
            while True:
                brut = np.frombuffer(flux.read(TRAME * taux // 16000, exception_on_overflow=False), dtype=np.int16)
                if taux != 16000:
                    brut = brut[: len(brut) // 3 * 3].reshape(-1, 3).mean(axis=1).astype(np.int16)
                etat["niveau"] = int(np.sqrt(np.mean(brut.astype(np.float32) ** 2)))
                with torch.no_grad():
                    entree = np.clip(brut.astype(np.float32) * GAIN_VAD / 32768.0, -1.0, 1.0)
                    prob = float(vad(torch.from_numpy(entree), 16000))
                decoupeur.max_parole = MORCEAU_PARLANT if parole["actif"] else 15.0  # « attends » par-dessus sa voix
                t = time.time()
                if detecteur is not None:
                    s = float(detecteur.predict(brut)[nom_eveil])
                    if eveil.score(s, t, parole["actif"] or t < parole["jusqua"] + QUEUE_ECHO):
                        etat["journal"].append(f"{time.strftime('%H:%M:%S')} « Jarvis » entendu sur le PC ({s:.2f})")
                    if eveil.seul(t, decoupeur.en_parole):
                        etat["phrases"] += 1
                        file_phrases.put((t, "Jarvis"))
                fini = decoupeur.pousser(brut.tobytes(), prob, t)
                if fini:
                    a_transcrire.put(fini + (eveil.phrase(fini[1], fini[2]),))
                    vad.reset_states()
        finally:
            etat["ecoute"] = False

    threading.Thread(target=traducteur, daemon=True).start()
    threading.Thread(target=micro, daemon=True).start()

    while True:
        time.sleep(10)
        if jeu_en_cours():
            print("[OREILLE] Partie en cours : je m'arrête pour libérer la mémoire", flush=True)
            os._exit(0)


if __name__ == "__main__":
    if jeu_en_cours():
        sys.exit(0)
    try:
        servir()
    except OSError:  # port déjà pris : une oreille tourne déjà
        sys.exit(0)
