# -*- coding: utf-8 -*-
"""Tests de micro_etat.choisir (sans matériel) + une lecture réelle : venv\\Scripts\\python.exe _test_micro_etat.py"""
import micro_etat as m

MICROS = [("id-real", "Microphone (Realtek(R) Audio)", False),
          ("id-cam", "Microphone (USB 2.0 Camera)", True),
          ("id-steam", "Microphone (Steam Streaming Microphone)", False)]
assert m.choisir(MICROS, "Microphone (USB 2.0 Camera)", "id-real") == ("Microphone (USB 2.0 Camera)", True), \
    "le micro réglé dans JARVIS, pas celui par défaut"
assert m.choisir(MICROS, "Microphone (Steam Streaming Micro", "id-real")[0] == "Microphone (Steam Streaming Microphone)", \
    "nom tronqué par PyAudio"
assert m.choisir(MICROS, "", "id-cam") == ("Microphone (USB 2.0 Camera)", True), "sans réglage : le micro par défaut"
assert m.choisir(MICROS, "Casque Bluetooth", "id-real") == ("Microphone (Realtek(R) Audio)", False), "introuvable : défaut"
assert m.choisir([], "", "x") == (None, None)
coupe, nom = m.etat()  # vraie lecture : ne doit jamais lever
assert coupe in (True, False, None) and isinstance(nom, str)
print("OK : micro coupé reconnu ; micro par défaut ici :", nom, "(coupé)" if coupe else "(actif)" if coupe is False else "(illisible)")
