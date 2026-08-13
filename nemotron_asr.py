# ══════════════════════════════════════════════════════════════
#  NVIDIA Nemotron / Canary ASR — Module local pour J.A.R.V.I.S
#  Site : www.techenclair.fr
# ══════════════════════════════════════════════════════════════
#  Ce module est 100% optionnel. Il n'est activé que si
#  l'utilisateur bascule le toggle "NEMOTRON ASR" dans l'UI.
#
#  Prérequis (optionnels) :
#    pip install nemo_toolkit[asr] torch
#
#  Modèle utilisé : nvidia/canary-1b  (multilingue — français)
#  Taille : ~4 Go (téléchargé automatiquement au 1er lancement)
# ══════════════════════════════════════════════════════════════

import os
import tempfile
import wave
import struct
import time

# Indicateur global de disponibilité
_NEMO_AVAILABLE = False
_TORCH_AVAILABLE = False

# IMPORT CONTRAINTES DE CHARGEMENT DE DLL & CONFLITS BINAIRES (WINDOWS)
import sys
import warnings

# Mettre en sourdine les avertissements et journaux verbeux de NeMo/Megatron/PyTorch
warnings.filterwarnings("ignore")
os.environ["NEMO_LOG_LEVEL"] = "ERROR"
os.environ["HYDRA_FULL_ERROR"] = "0"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

# Redirection robuste au niveau OS (descripteurs de fichiers 1 et 2)
# pour intercepter les sorties C/C++ de Pygame, PyTorch et OneLogger.
sys.stdout.flush()
sys.stderr.flush()
_os_redirected = False

try:
    _devnull_fd = os.open(os.devnull, os.O_WRONLY)
    _old_stdout_fd = os.dup(1)
    _old_stderr_fd = os.dup(2)
    os.dup2(_devnull_fd, 1)
    os.dup2(_devnull_fd, 2)
    _os_redirected = True
except Exception:
    pass

# Redirection au niveau Python
_old_sys_stdout = sys.stdout
_old_sys_stderr = sys.stderr
sys.stdout = open(os.devnull, 'w', encoding='utf-8')
sys.stderr = open(os.devnull, 'w', encoding='utf-8')

try:
    # 1. Charger pyarrow.dataset avant torch pour éviter un conflit binaire (OpenMP/MKL) sur Windows
    try:
        import pyarrow.dataset
    except Exception:
        pass

    # 2. Charger torch et ajouter son répertoire lib aux DLLs Windows pour torchaudio/NeMo
    try:
        import torch
        _TORCH_AVAILABLE = True
        try:
            torch_lib_dir = os.path.join(os.path.dirname(torch.__file__), "lib")
            if os.path.exists(torch_lib_dir) and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(torch_lib_dir)
        except Exception:
            pass
    except Exception:
        torch = None
        _TORCH_AVAILABLE = False

    # 3. Charger nemo.collections.asr
    try:
        import nemo.collections.asr as nemo_asr
        _NEMO_AVAILABLE = True
    except Exception:
        nemo_asr = None
        _NEMO_AVAILABLE = False
finally:
    # Restaurer la redirection Python
    try:
        sys.stdout.close()
    except Exception:
        pass
    try:
        sys.stderr.close()
    except Exception:
        pass
    sys.stdout = _old_sys_stdout
    sys.stderr = _old_sys_stderr

    # Restaurer la redirection au niveau OS
    if _os_redirected:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(_old_stdout_fd, 1)
            os.dup2(_old_stderr_fd, 2)
            os.close(_devnull_fd)
            os.close(_old_stdout_fd)
            os.close(_old_stderr_fd)
        except Exception:
            pass


class NemotronASR:
    """
    Encapsule le modèle NVIDIA Canary-1B (NeMo) pour la transcription
    vocale 100% locale.

    Caractéristiques :
      - Chargement paresseux (le modèle n'est chargé qu'au 1er appel)
      - Libération explicite de la mémoire GPU/CPU
      - Détection automatique GPU vs CPU avec avertissements
      - Nettoyage VRAM après chaque transcription
    """

    DEFAULT_MODEL = "nvidia/canary-1b"

    def __init__(self, model_name: str | None = None):
        self._model = None
        self._model_name = model_name or self.DEFAULT_MODEL
        self._device = None  # "cuda" ou "cpu"
        self._chargement_en_cours = False
        self._charge = False

    # ── Détection matérielle ──────────────────────────────────────

    @staticmethod
    def is_nemo_installed() -> bool:
        """Retourne True si nemo_toolkit[asr] est installé."""
        return _NEMO_AVAILABLE and _TORCH_AVAILABLE

    @staticmethod
    def is_gpu_available() -> bool:
        """Retourne True si un GPU NVIDIA CUDA est disponible."""
        if not _TORCH_AVAILABLE:
            return False
        return torch.cuda.is_available()

    def get_device_info(self) -> dict:
        """Retourne les infos sur le device utilisé."""
        info = {
            "nemo_installed": _NEMO_AVAILABLE,
            "torch_installed": _TORCH_AVAILABLE,
            "gpu_available": self.is_gpu_available(),
            "device": self._device or ("cuda" if self.is_gpu_available() else "cpu"),
            "model": self._model_name,
            "loaded": self._charge,
        }
        if self.is_gpu_available() and _TORCH_AVAILABLE:
            try:
                info["gpu_name"] = torch.cuda.get_device_name(0)
                info["gpu_vram_mb"] = round(
                    torch.cuda.get_device_properties(0).total_mem / 1024 / 1024
                )
            except Exception:
                pass
        return info

    # ── Chargement / déchargement du modèle ───────────────────────

    def charger_modele(self) -> dict:
        """
        Charge le modèle NeMo en mémoire.

        Retourne un dict avec les infos de chargement :
          {"success": bool, "device": str, "warnings": [str], "error": str|None}
        """
        if self._charge:
            return {
                "success": True,
                "device": self._device,
                "warnings": [],
                "error": None,
            }

        if self._chargement_en_cours:
            return {
                "success": False,
                "device": None,
                "warnings": [],
                "error": "Chargement déjà en cours…",
            }

        if not _NEMO_AVAILABLE or not _TORCH_AVAILABLE:
            msg = []
            if not _TORCH_AVAILABLE:
                msg.append("PyTorch non installé (pip install torch)")
            if not _NEMO_AVAILABLE:
                msg.append("NeMo non installé (pip install nemo_toolkit[asr])")
            return {
                "success": False,
                "device": None,
                "warnings": [],
                "error": " | ".join(msg),
            }

        self._chargement_en_cours = True
        warnings = []

        try:
            # Choix du device
            if self.is_gpu_available():
                self._device = "cuda"
                print(f"[ASR] 🟢 GPU NVIDIA détecté : {torch.cuda.get_device_name(0)}")
            else:
                self._device = "cpu"
                warnings.append(
                    "Aucun GPU NVIDIA détecté. Le mode CPU sera utilisé — "
                    "la transcription sera LENTE (10-30s par phrase)."
                )
                print("[ASR] ⚠ Aucun GPU NVIDIA — mode CPU (lent)")

            print(f"[ASR] Chargement du modèle {self._model_name}…")
            print(f"[ASR] ⚠ Premier lancement : téléchargement ~4 Go si nécessaire")

            t0 = time.time()

            # Chargement du modèle NeMo ASR
            local_model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "canary-1b.nemo")
            if self._model_name == "nvidia/canary-1b" and os.path.exists(local_model_path):
                print(f"[ASR] Chargement du modèle local depuis {local_model_path}…")
                self._model = nemo_asr.models.ASRModel.restore_from(
                    restore_path=local_model_path
                )
            else:
                self._model = nemo_asr.models.ASRModel.from_pretrained(
                    model_name=self._model_name
                )

            # Déplacer sur le bon device
            if self._device == "cuda":
                self._model = self._model.cuda()
            else:
                self._model = self._model.cpu()

            # Mode évaluation (pas de gradient — économise la mémoire)
            self._model.eval()

            dt = round(time.time() - t0, 1)
            print(f"[ASR] ✔ Modèle chargé en {dt}s sur {self._device.upper()}")

            self._charge = True
            self._chargement_en_cours = False

            return {
                "success": True,
                "device": self._device,
                "warnings": warnings,
                "error": None,
            }

        except Exception as e:
            self._chargement_en_cours = False
            self._model = None
            print(f"[ASR] ✖ Erreur chargement modèle : {e}")
            return {
                "success": False,
                "device": None,
                "warnings": warnings,
                "error": str(e),
            }

    def liberer(self):
        """Libère le modèle et nettoie la mémoire GPU/CPU."""
        if self._model is not None:
            del self._model
            self._model = None

        self._charge = False
        self._device = None

        if _TORCH_AVAILABLE and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            except Exception:
                pass

        # Garbage collector Python
        import gc
        gc.collect()

        print("[ASR] ✔ Modèle Nemotron déchargé — mémoire libérée")

    # ── Transcription ─────────────────────────────────────────────

    def transcrire(self, raw_audio_data: bytes, sample_rate: int = 16000) -> str:
        """
        Transcrit un segment audio brut (PCM 16-bit mono).

        Args:
            raw_audio_data : bytes PCM 16-bit little-endian mono
            sample_rate    : taux d'échantillonnage (défaut 16000 Hz)

        Returns:
            Texte transcrit (str), ou chaîne vide si erreur.
        """
        if not self._charge or self._model is None:
            # Auto-chargement si pas encore fait
            result = self.charger_modele()
            if not result["success"]:
                print(f"[ASR] Impossible de transcrire : {result['error']}")
                return ""

        # Sauvegarder l'audio dans un fichier WAV temporaire
        # (NeMo attend un fichier audio en entrée)
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="jarvis_asr_")
            os.close(tmp_fd)

            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)        # mono
                wf.setsampwidth(2)        # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(raw_audio_data)

            # Transcription NeMo
            t0 = time.time()

            with _no_grad_context():
                transcriptions = self._model.transcribe(
                    [tmp_path],
                    batch_size=1,
                    source_lang="fr",
                    target_lang="fr",
                )

            dt = round(time.time() - t0, 2)

            # NeMo retourne une liste de résultats
            if isinstance(transcriptions, list) and len(transcriptions) > 0:
                # Selon la version de NeMo, c'est soit une str soit un objet
                texte = transcriptions[0]
                if hasattr(texte, "text"):
                    texte = texte.text
                texte = str(texte).strip()
            else:
                texte = ""

            print(f"[ASR] Transcription ({dt}s) : \"{texte}\"")

            # Nettoyage mémoire GPU après chaque transcription
            self._cleanup_gpu_cache()

            return texte

        except Exception as e:
            print(f"[ASR] ✖ Erreur transcription : {e}")
            return ""

        finally:
            # Supprimer le fichier WAV temporaire
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    # ── Utilitaires internes ──────────────────────────────────────

    def _cleanup_gpu_cache(self):
        """Libère la mémoire GPU temporaire sans décharger le modèle."""
        if _TORCH_AVAILABLE and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass


def _no_grad_context():
    """Retourne le context manager torch.no_grad() si disponible."""
    if _TORCH_AVAILABLE:
        return torch.no_grad()
    # Fallback : context manager neutre
    from contextlib import nullcontext
    return nullcontext()
