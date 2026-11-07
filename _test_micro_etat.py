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
# Vraie lecture, comme main2 : dans un processus à part. Le 07/11, la lecture dans le processus de
# JARVIS l'a fait planter deux fois (0xc0000005), et la 1re version isolée plantait dès le 1er appel.
coupe, nom = m.etat_isole()
assert coupe in (True, False, None) and isinstance(nom, str), (coupe, nom)  # None : pas de micro sur ce PC
for _ in range(5):  # plusieurs contrôles à la suite donnent la même réponse
    assert m.etat_isole() == (coupe, nom)
# Avec un indice de micro (comme main2 : « mic_device_index ») : PyAudio s'en mêle. C'est ce cas qui
# plantait (0xc0000005), et l'enfant doit maintenant sortir proprement, code 0.
import subprocess, sys  # noqa: E401
for _ in range(5):
    r = subprocess.run([sys.executable, m.__file__, "1"], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip().startswith("{"), (r.returncode, r.stdout, r.stderr[-300:])
print("OK : micro coupé reconnu ; micro par défaut ici :", nom, "(coupé)" if coupe else "(actif)" if coupe is False else "(illisible)")
