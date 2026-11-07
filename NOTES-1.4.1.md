# JARVIS 1.4.1

*Français plus bas.*

A fix for 1.4.0. Please update.

**JARVIS could close on its own.** Every five minutes, 1.4.0 checks whether your microphone is muted
in Windows. That check read the audio devices inside JARVIS itself, and opening then closing PyAudio
there shut down Windows' COM while some audio objects were still alive: when one of them was released
later, JARVIS crashed (access violation `0xc0000005` in `_ctypes`), sometimes after twenty minutes,
sometimes after hours. The check now runs in a separate process, reads PyAudio before any COM object
exists, and never closes COM by hand. Even if a sound driver misbehaves, only that small process can
fail; JARVIS stays up.

---

# JARVIS 1.4.1 (français)

Une correction de la 1.4.0. Mettez à jour.

**JARVIS pouvait se fermer tout seul.** Toutes les cinq minutes, la 1.4.0 vérifie si votre micro est
coupé dans Windows. Ce contrôle lisait les périphériques audio dans JARVIS lui-même, et ouvrir puis
fermer PyAudio à cet endroit refermait le COM de Windows pendant que des objets audio vivaient
encore : quand l'un d'eux était libéré plus tard, JARVIS plantait (violation d'accès `0xc0000005`
dans `_ctypes`), parfois au bout de vingt minutes, parfois au bout de plusieurs heures. Le contrôle
tourne maintenant dans un processus à part, lit PyAudio avant tout objet COM et ne referme jamais COM
à la main. Même si un pilote audio se comporte mal, seul ce petit processus peut échouer : JARVIS
reste debout.
