# J.A.R.V.I.S

Assistant vocal de bureau. Il écoute, répond, et agit sur la machine : domotique
Home Assistant, courrier, mises à jour logicielles, VPN, lancement
d'applications, lecture de l'écran.

Il tourne en fond, sans fenêtre, et s'invoque au clavier depuis n'importe quelle
application.

---

## Ce qu'il fait

**Répondre.** Une chaîne d'outils locaux traite d'abord ce qu'elle sait faire —
heure, calculs, conversions, informations sur la machine — en **deux à six
millisecondes**, sans appeler de modèle. Le reste part au modèle.

**Agir.** Lumières et prises Home Assistant, tri du courrier et brouillons de
réponse, mises à jour `winget`, VPN, désinstallation de logiciels, contrôle de
Spotify et Deezer.

**Se taire quand il ne sait pas.** C'est un choix de conception, pas une
politesse : un assistant qui répond « c'est fait » sans avoir rien fait est pire
qu'un assistant qui refuse.

## Comment on lui parle

| | |
|---|---|
| **Voix** | dire « Jarvis », puis la demande |
| **Ctrl+Alt+J** | une barre apparaît au centre de l'écran, depuis n'importe quelle application |
| **Le HUD** | interface complète — domotique, courrier, agenda, sécurité, réglages |

Fermer la fenêtre ne l'arrête pas : il continue en fond, avec une icône près de
l'horloge. Pour l'arrêter : « quitter jarvis », ou le menu de cette icône.

---

## Installation

**Téléchargez l'installeur depuis la page des [versions](../../releases), et
lancez-le.** Il trouve un Python utilisable, récupère la dernière version,
prépare tout, puis ouvre l'assistant de configuration.

| Système | Fichier | État |
|---|---|---|
| Windows 10 / 11 | `Installer-JARVIS.exe` | éprouvé |
| Linux | `python3 amorceur/amorceur.py` | éprouvé sur Ubuntu 26.04 |
| macOS | `python3 amorceur/amorceur.py` | **jamais essayé sur un vrai Mac** — voir [docs/macos.md](docs/macos.md) |

L'installeur pèse 11 Mo : il télécharge JARVIS plutôt que de l'embarquer.
Vous pouvez donc lire le code avant qu'il ne s'installe — ce qui compte pour
un programme qui pilote votre machine.

Il faut **Python 3.10 à 3.13**. La 3.14 est trop récente : plusieurs
dépendances n'ont pas encore de version compilée pour elle.

### À la main, si vous préférez

```bash
git clone <url-du-depot> jarvis
cd jarvis
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
venv\Scripts\python.exe installeur.py
```

Pour savoir ce qui manque à tout moment :

```bash
venv\Scripts\python.exe config.py
```

Cette commande liste ce qui est disponible sur votre machine et **quelles
fonctions sont dégradées, avec la raison**.

### La reconnaissance vocale est séparée

`requirements-voix.txt` pèse plusieurs gigaoctets (torch, Nemotron). Sans
elle, JARVIS fonctionne au clavier, par la barre rapide et par le HUD ; seule
la dictée manque, et elle le dit.

## Réglages

Deux sont nécessaires, le reste est facultatif. `.env.example` dit à quoi chacun
sert et où l'obtenir.

| | |
|---|---|
| `GEMINI_API_KEY` | le modèle principal. Sans lui, seuls les outils locaux répondent |
| `JARVIS_ACCESS_TOKEN` | protège le WebSocket, **qui exécute les commandes système** |

Le second n'est pas optionnel en pratique : sans lui, l'authentification est
désactivée et n'importe quel programme de la machine peut piloter JARVIS.
Inventez une longue chaîne aléatoire.

---

## Systèmes

**Windows 10 et 11** — développé et éprouvé là.

**Linux, macOS** — JARVIS démarre, mais une partie des fonctions est
indisponible : celles qui reposent sur PowerShell, `winget`, le registre ou
l'API Windows. Elles le **disent** au lieu d'échouer en vol, et `config.py` les
énumère.

> macOS n'a jamais été essayé sur une vraie machine. Ce qui est écrit ici est
> ce que le code prévoit, pas ce qui a été constaté.

## Vie privée

Rien ne quitte la machine sauf les appels aux modèles que vous configurez, à la
météo et à Home Assistant.

Les conversations, la configuration et le courrier restent en local. Les clés
vivent dans `.env`, que `git` ignore. Le HUD masque les clés à l'affichage : il
ne reçoit jamais leur valeur, seulement leur présence.

Les actions irréversibles — envoyer un e-mail, désinstaller un logiciel —
demandent un accord explicite et **montrent exactement ce qui va partir** avant
de le faire.

## Mises à jour

Au lancement, JARVIS demande à GitHub s'il existe une version plus récente et le
signale. Il n'installe rien tout seul. Renseignez `JARVIS_DEPOT` dans `.env`
pour activer cette vérification ; laissez-la vide pour la désactiver.

---

## Contribuer

Le projet garde deux règles, qui expliquent la forme du code :

**Une fonction indisponible le dit.** Elle ne renvoie pas une liste vide, ne
répond pas « c'est fait », n'invente pas de valeur par défaut. La plupart des
corrections de ce dépôt viennent d'avoir enfreint cette règle quelque part.

**Ce qui est affirmé est vérifié.** Les fichiers `_test_*.py` s'exécutent
directement, sans cadre de test :

```bash
venv\Scripts\python.exe _test_machine.py
```

Ils ne vérifient pas que le code fait ce qu'il fait, mais qu'il ne refait pas
les erreurs déjà commises — une phrase qui figeait le programme, un prénom
codé en dur, une comparaison de versions par ordre alphabétique.

## Licence

À définir.
