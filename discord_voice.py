# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Vocal natif Discord (rejoindre un salon, écouter, répondre)
=============================================================================
Différent du bot texte (discord_bot.py) : ici JARVIS rejoint un salon
VOCAL Discord et parle/écoute en direct, comme le micro du PC mais sur
Discord — gratuit (voix native Discord, pas de téléphonie payante comme
le plugin voice-call d'OpenClaw qui passe par Twilio/Telnyx/Plivo).

Pipeline par segment de parole :
  PCM Discord (opus décodé, discord-ext-voice-recv)
    -> segmentation par silence (même seuil RMS que le micro PC, main2.py)
    -> reconnaissance vocale (speech_recognition, Google gratuit — même
       moteur que le micro PC)
    -> traiter_reponse_ia (même pipeline que le bot texte, DISCORD_SINK)
    -> synthèse (edge_tts, même moteur que la voix locale)
    -> lecture dans le salon vocal (discord.FFmpegPCMAudio)

PLAFOND CONNU (ponytail) : un seul utilisateur écouté à la fois (celui
autorisé, DISCORD_USER_ID) — pas de vraie diarisation multi-locuteurs.
Écoute suspendue pendant que JARVIS parle (pas d'écho, pas de vraie
duplex simultanée). Segmentation par silence simple (seuil RMS fixe),
pas de VAD ML — un bruit de fond fort peut couper une phrase trop tôt.
"""

import asyncio
import os
import queue
import time
import uuid

import speech_recognition as sr

try:
    import numpy as np
except ImportError:
    np = None

try:
    import discord
    from discord.ext import voice_recv
except ImportError:
    discord = None
    voice_recv = None


def _patcher_resilience_voice_recv():
    """
    discord-ext-voice-recv (marquée EXPERIMENTAL, encore en alpha) tue TOUTE
    l'écoute dès la première erreur de décodage Opus -- confirmé en test
    réel ce soir : "OpusError: corrupted stream" sur le tout premier paquet
    d'un SSRC inconnu, et plus rien n'arrivait ensuite (write() jamais
    rappelé). Bug connu et non résolu côté lib (issues #27 et #35 du dépôt
    imayhaveborkedit/discord-ext-voice-recv -- "packet loss", "bot stops
    listening").

    PacketRouter._do_run() n'a aucun try/except autour de
    decoder.pop_data() : une seule erreur remonte jusqu'à run(), qui logue
    et appelle stop_listening() -- arrête tout, silencieusement pour
    l'utilisateur. Ce patch reproduit la structure originale à l'identique
    (même verrou, même boucle sur waiter.items) et ajoute uniquement un
    try/except par décodeur : un paquet corrompu est ignoré, pas fatal.
    """
    if voice_recv is None:
        return
    from discord.ext.voice_recv import router as _router_mod

    def _do_run_resilient(self):
        while not self._end_thread.is_set():
            self.waiter.wait()
            with self._lock:
                for decoder in self.waiter.items:
                    try:
                        data = decoder.pop_data()
                    except Exception as e:
                        print(f"[VOCAL DISCORD] Paquet audio ignoré (décodage) : {e}")
                        continue
                    if data is not None:
                        self.sink.write(data.source, data)

    _router_mod.PacketRouter._do_run = _do_run_resilient


_patcher_resilience_voice_recv()

SEUIL_RMS_SILENCE = 250          # même seuil que le micro PC (main2.py)
SILENCE_FIN_SEGMENT_MS = 700     # silence continu avant de considérer la phrase finie
DUREE_MIN_SEGMENT_MS = 300       # segments plus courts = bruit, ignorés
VOIX_TTS = "fr-FR-HenriNeural"   # même défaut que le fallback Edge TTS de parler()

_recognizer = sr.Recognizer()


def _rms(pcm_bytes):
    if np is None or not pcm_bytes:
        return 0
    echantillons = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    if len(echantillons) == 0:
        return 0
    return int(np.sqrt(np.mean(echantillons ** 2)))


class EcouteurUtilisateur(voice_recv.AudioSink):
    """
    Bufferise l'audio PCM d'UN SEUL utilisateur autorisé, segmente par
    silence, pousse chaque segment terminé dans une queue thread-safe.

    write() est appelé par la lib d'extraction audio (thread dédié) --
    jamais de code asyncio directement ici, juste un put() sur une Queue
    standard, consommée depuis la boucle asyncio ailleurs.
    """

    def __init__(self, user_id_autorise, segments_queue):
        super().__init__()
        self._uid = int(user_id_autorise)
        self._queue = segments_queue
        self._buffer = bytearray()
        self._ms_silence_consecutif = 0
        self._suspendu = False
        self._diag_premier_write = False
        self._diag_premier_match = False

    def suspendre(self, suspendu):
        """Coupe l'écoute pendant que JARVIS parle (anti-écho)."""
        self._suspendu = suspendu
        if suspendu:
            self._buffer.clear()
            self._ms_silence_consecutif = 0

    def wants_opus(self):
        return False

    def write(self, user, data):
        # Diagnostic temporaire (une seule fois par cas) -- premiere mise
        # en service de l'ecoute Discord, aucune visibilite sur ce que la
        # lib recoit reellement sans ca.
        if not self._diag_premier_write:
            self._diag_premier_write = True
            print(f"[VOCAL DISCORD][DIAG] Premier write() : "
                  f"user={user.id if user else None} (autorise={self._uid}), "
                  f"pcm={len(data.pcm) if data.pcm else 0} octets")

        if self._suspendu or user is None or user.id != self._uid:
            return

        if not self._diag_premier_match:
            self._diag_premier_match = True
            print(f"[VOCAL DISCORD][DIAG] Premier paquet de l'utilisateur autorise recu.")

        pcm = data.pcm
        if not pcm:
            return

        est_silence = _rms(pcm) < SEUIL_RMS_SILENCE
        # Ne pas demarrer un nouveau tampon sur du silence : sinon, apres
        # avoir pousse une phrase, le silence qui suit continue de
        # s'accumuler indefiniment au lieu de rester vide -- un bruit de
        # fond faible et constant finirait par etre transcrit pour rien.
        if est_silence and not self._buffer:
            return

        self._buffer.extend(pcm)
        # 48kHz stereo 16-bit : 1 ms = 48*2*2 = 192 octets.
        duree_ms = len(pcm) / 192.0

        if est_silence:
            self._ms_silence_consecutif += duree_ms
        else:
            self._ms_silence_consecutif = 0

        buffer_duree_ms = len(self._buffer) / 192.0
        if (self._ms_silence_consecutif >= SILENCE_FIN_SEGMENT_MS
                and buffer_duree_ms >= DUREE_MIN_SEGMENT_MS):
            self._queue.put(bytes(self._buffer))
            self._buffer.clear()
            self._ms_silence_consecutif = 0

    def cleanup(self):
        self._buffer.clear()


def _stereo_vers_mono(pcm_bytes):
    """Discord fournit du PCM stereo 16 bits -- la reconnaissance vocale
    (conçue pour un micro mono) marche bien mieux sur un signal mono."""
    if np is None:
        return pcm_bytes
    echantillons = np.frombuffer(pcm_bytes, dtype=np.int16).reshape(-1, 2)
    mono = echantillons.mean(axis=1).astype(np.int16)
    return mono.tobytes()


def transcrire_pcm(pcm_bytes, sample_rate=48000, sample_width=2):
    """
    PCM brut (stereo, comme fourni par Discord) -> texte, via le même
    moteur (Google, gratuit) que le micro PC dans main2.py. Renvoie None
    si rien de compréhensible.
    """
    try:
        pcm_mono = _stereo_vers_mono(pcm_bytes)
        audio = sr.AudioData(pcm_mono, sample_rate, sample_width)
        texte = _recognizer.recognize_google(audio, language="fr-FR").strip()
        return texte or None
    except sr.UnknownValueError:
        return None
    except Exception as e:
        print(f"[VOCAL DISCORD] Erreur reconnaissance : {e}")
        return None


async def synthetiser(texte, voix=VOIX_TTS):
    """Texte -> fichier audio (Edge TTS, gratuit, même moteur que la voix locale)."""
    import edge_tts
    chemin = f"jarvis_voice_discord_{uuid.uuid4().hex[:8]}.mp3"
    communicate = edge_tts.Communicate(texte, voice=voix)
    await communicate.save(chemin)
    return chemin
