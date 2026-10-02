# -*- coding: utf-8 -*-
"""Vérifie discord_voice.py : RMS, conversion stéréo->mono. Aucune connexion Discord."""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import discord_voice as dv

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


# ── RMS ───────────────────────────────────────────────────────────────────
silence = np.zeros(480, dtype=np.int16).tobytes()
verifier("RMS du silence pur = 0", dv._rms(silence) == 0)

fort = np.full(480, 20000, dtype=np.int16).tobytes()
verifier("RMS d'un signal constant = sa valeur", dv._rms(fort) == 20000)

verifier("RMS sur bytes vides = 0, pas d'exception", dv._rms(b"") == 0)

verifier("silence sous le seuil de detection", dv._rms(silence) < dv.SEUIL_RMS_SILENCE)
verifier("signal fort au-dessus du seuil", dv._rms(fort) >= dv.SEUIL_RMS_SILENCE)

# ── Stéréo -> mono ────────────────────────────────────────────────────────
stereo = np.array([100, 200, 300, 400], dtype=np.int16).tobytes()
mono = np.frombuffer(dv._stereo_vers_mono(stereo), dtype=np.int16)
verifier("stereo->mono : moyenne des 2 canaux", list(mono) == [150, 350])
verifier("stereo->mono : taille divisee par 2", len(dv._stereo_vers_mono(stereo)) == len(stereo) // 2)

# ── Sink : segmentation par silence ──────────────────────────────────────
import queue


class _FakeUser:
    def __init__(self, uid):
        self.id = uid


class _FakeVoiceData:
    def __init__(self, pcm):
        self.pcm = pcm


q = queue.Queue()
sink = dv.EcouteurUtilisateur(user_id_autorise=42, segments_queue=q)

_moi = _FakeUser(42)
_autre = _FakeUser(999)

# 100ms de parole forte (RMS eleve)
paquet_fort = np.full(int(192 * 20), 20000, dtype=np.int16).tobytes()  # ~20ms a 192 octets/ms
for _ in range(5):
    sink.write(_moi, _FakeVoiceData(paquet_fort))
verifier("rien dans la queue tant qu'on parle (pas de silence)", q.empty())

# Un utilisateur NON autorise ne doit jamais alimenter le buffer.
sink.write(_autre, _FakeVoiceData(paquet_fort))
verifier("utilisateur non autorise ignore", len(sink._buffer) == 5 * len(paquet_fort))

# Silence suffisant -> le segment doit etre pousse dans la queue.
paquet_silence = np.zeros(int(192 * 20), dtype=np.int16).tobytes()
for _ in range(40):  # 40 * 20ms = 800ms > SILENCE_FIN_SEGMENT_MS (700ms)
    sink.write(_moi, _FakeVoiceData(paquet_silence))
verifier("segment pousse dans la queue apres silence suffisant", not q.empty())

if not q.empty():
    segment = q.get()
    verifier("le segment contient la parole (pas juste le silence)", len(segment) > 0)

verifier("buffer vide apres avoir pousse le segment", len(sink._buffer) == 0)

# suspendre() doit vider le buffer et ignorer tout write() pendant la pause.
sink.write(_moi, _FakeVoiceData(paquet_fort))
sink.suspendre(True)
verifier("suspendre() vide le buffer", len(sink._buffer) == 0)
sink.write(_moi, _FakeVoiceData(paquet_fort))
verifier("write() ignore pendant la suspension", len(sink._buffer) == 0)
sink.suspendre(False)
sink.write(_moi, _FakeVoiceData(paquet_fort))
verifier("write() reprend apres suspendre(False)", len(sink._buffer) > 0)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Vocal Discord (RMS + segmentation) : conforme.")
