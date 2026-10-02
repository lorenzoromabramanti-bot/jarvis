# JARVIS sur macOS — état et marche à suivre

**Rien de ce document n'a été vérifié sur un vrai Mac.** C'est ce que le code
prévoit, pas ce qui a été constaté. Les points marqués « à vérifier » sont
ceux qui décideront si ça marche.

---

## Ce qui devrait fonctionner

L'amorceur ne dépend que de la bibliothèque standard et connaît macOS : il
installe dans `~/Applications/JARVIS`, cherche `python3`, et bascule en mode
texte si tkinter manque.

Le cœur de JARVIS démarre : depuis la passe de portabilité, plus aucun import
Windows n'est inconditionnel. `winreg` et les API `user32` sont remplacés par
un substitut qui explique son absence au premier usage au lieu de faire
échouer le chargement.

## Ce qui ne fonctionnera pas, et pourquoi

| Fonction | Cause |
|---|---|
| Analyse antivirus, désinstalleur | lisent le registre Windows |
| Mises à jour logicielles | `winget` |
| VPN | commandes PowerShell |
| Lancement d'applications | `pywin32` |
| Raccourci global Ctrl+Alt+J | `RegisterHotKey`, API Windows |

`config.py` les liste avec leur raison :

```bash
venv/bin/python config.py
```

Ces fonctions ne planteront pas : elles diront qu'elles ne sont pas
disponibles ici. C'est la différence entre un produit dégradé et un produit
mort.

## Le point qui décidera : la reconnaissance vocale

JARVIS transcrit avec **Nemotron**, qui passe par `torch`. Sur PC, ça tourne
sur une carte NVIDIA via CUDA. **Un Mac n'a pas de GPU NVIDIA.**

`torch` existe pour Apple Silicon et sait utiliser Metal (backend `mps`),
mais Nemotron n'a jamais été essayé dessus. Deux issues possibles :

- il tourne sur `mps`, plus lentement qu'avec CUDA mais utilisable ;
- il retombe sur le processeur, et la transcription devient trop lente pour
  un usage vocal.

**À vérifier sur le Mac.** En attendant, `requirements-voix.txt` reste
facultatif : sans lui, JARVIS fonctionne au clavier et par l'assistant, et
seule la dictée manque.

## Marche à suivre

```bash
# 1. Vérifier la version de Python (3.10 à 3.13 ; 3.14 est trop récent)
python3 --version

# 2. Lancer l'amorceur
python3 amorceur/amorceur.py --console

# 3. Voir ce qui est disponible sur cette machine
cd ~/Applications/JARVIS && venv/bin/python config.py

# 4. Configurer
venv/bin/python installeur.py
```

### Si l'interface graphique ne s'ouvre pas

tkinter manque. Avec Homebrew :

```bash
brew install python-tk
```

### Si un paquet refuse de s'installer

L'amorceur reprend paquet par paquet et nomme ceux qui échouent — il
n'abandonne pas tout pour un seul. Les candidats probables sur Mac :

- `pywin32`, `comtypes`, `pycaw` : ils portent déjà un marqueur
  `sys_platform == "win32"` et seront ignorés ;
- `PyAudio` : demande PortAudio, `brew install portaudio` ;
- `pygame` : demande SDL, `brew install sdl2`.

## Ce qu'il faudra me rapporter

Pour que je corrige ce qui ne va pas, ces quatre réponses suffisent :

1. la sortie complète de `python3 amorceur/amorceur.py --console` ;
2. la sortie de `venv/bin/python config.py` ;
3. si l'assistant de configuration s'ouvre et à quoi il ressemble ;
4. si `venv/bin/python main2.py` démarre, et ce qu'il affiche.

Les erreurs entières, pas résumées : c'est la dernière ligne qui dit
d'habitude la vraie cause.
