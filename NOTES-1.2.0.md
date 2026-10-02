# JARVIS 1.2.0

Cette version fait deux choses. Elle ajoute ce qui permet de piloter JARVIS
à distance et de lui confier du travail de fond. Et elle livre **éteint** tout
ce qui dépend d'une installation particulière.

## Ce qui change

**Discord.** On discute avec JARVIS et on lui donne des ordres depuis Discord.
Avant une action sensible, il demande confirmation. Il peut aussi rejoindre un
salon vocal, écouter et répondre, sans service de téléphonie payant. Il reste
inactif tant qu'aucun jeton n'est renseigné dans `.env`.

**Notifications.** Quand une tâche de fond se termine, un message part sur
Discord ou Slack. Rien ne part pendant les heures calmes, la nuit.

**« Fais ça cette nuit ».** La tâche est mise en file. Le compte rendu arrive
au briefing du matin.

**Sous-tâches en parallèle.** Une demande qui compare ou analyse plusieurs
choses est découpée et traitée en parallèle. Au-delà de 5 sous-tâches, JARVIS
demande avant de lancer.

**Travail jusqu'à une échéance.** Tant qu'il reste du temps, JARVIS relit et
améliore ce qu'il a produit.

**Délégation de code.** JARVIS confie une tâche de code à Claude Code, Codex,
OpenCode, Cursor Agent ou OpenClaw. La tâche se fait dans un projet que vous
avez déclaré, avec des contrôles de sécurité. Sans ces outils, son propre agent
de fichiers lit, cherche et modifie le projet via Gemini. Il ne peut pas sortir
du dossier du projet.

**Confiance et coûts.** Un journal de confiance est tenu par type d'action :
l'autonomie se gagne action par action. Pour chaque appel à un modèle, les
jetons utilisés et le coût sont visibles.

**Autres ajouts.**
- Notes Notion : créer, lire, modifier, supprimer, chercher.
- Veille de sujets : un contrôle par jour, et les nouveautés dites au briefing.
- Des rappels qui survivent à l'extinction, confiés au Planificateur de tâches
  Windows.
- Le presse-papiers : traduire, résumer, expliquer ou corriger le texte copié.
- Les compétences que JARVIS s'est écrites : les lister, en éteindre une,
  repérer celle qui est cassée.
- Le PC et le navigateur se pilotent sans passer par le modèle : onglets,
  vidéos, sites, fenêtres, verrouillage, applications ouvertes, gros
  consommateurs, carte graphique.
- App iOS : un client natif qui se connecte au WebSocket de JARVIS.

## Corrections qui comptent

**Le démarrage avec Windows ne tuait plus JARVIS en silence.** Au démarrage de
session, JARVIS est lancé par `pythonw`, qui n'a pas de sortie standard. La
première écriture dans la console arrêtait le processus, sans message ni trace.
Ce cas est maintenant géré.

**Repli sur Ollama.** Si Gemini est indisponible, JARVIS bascule sur un modèle
Ollama local au lieu de se taire. La liste des modèles proposés est lue sur le
serveur Ollama réel. Elle n'est plus écrite à l'avance dans le code.

**Domotique.** Quand Home Assistant refuse une action, JARVIS le dit au lieu
d'annoncer « c'est fait ».

**Une seule instance.** Un second lancement ne crée plus un deuxième JARVIS.
Chaque démarrage et chaque arrêt sont notés dans un journal local.

**Écrans à forte mise à l'échelle.** Les fenêtres sont correctement placées,
jusqu'à 225 %.

## Sécurité

**Accès au WebSocket.** L'installeur génère un jeton propre à votre machine.
Sans jeton, JARVIS n'écoute que sur la machine elle-même : un autre appareil du
réseau ne peut pas s'y connecter.

**Options vraiment éteintes.** Une option non cochée reste désactivée même si
JARVIS est installé sans passer par l'installeur.

**Confirmations.** Désarmer une alarme, ouvrir une serrure ou piloter le PC à
distance demande désormais une confirmation explicite.

**Délégation de code et rappels.** Un texte malveillant glissé dans une tâche
déléguée ou dans un rappel ne peut plus être exécuté comme une commande.

## Options livrées désactivées

Ces fonctions dépendent d'une maison, d'un établissement scolaire ou d'un
programme tiers. Elles sont **éteintes par défaut** et n'ont aucune valeur
préremplie :

| Option | Ce qu'il faut |
|---|---|
| Emploi du temps recopié dans un agenda Google à part, cours annulés marqués | Home Assistant avec l'intégration Pronote, un compte Google |
| Quiz de révision la veille d'une évaluation, mode « fais-moi réviser » | l'option précédente, Ollama |
| Détection de présence par webcam, avec une photo envoyée sur Discord | une webcam, le bot Discord |
| Carte OSINT 3D (God's Eye View et ShadowBroker) | ces deux programmes, installés à part |
| Délégation de code | l'agent de code de votre choix |

Pour en activer une, relancez `installeur.py`, allez dans *Capacités*, cochez
l'option, puis remplissez les réglages demandés. `.env.example` décrit chaque
réglage.

## Mettre à jour depuis la 1.1.0

**Avec l'installeur.** Relancez `Installer-JARVIS.exe`. Il récupère la dernière
version.

**À la main.**

```bash
git pull
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe installeur.py
```

Sous Linux et macOS, remplacez `venv\Scripts\python.exe` par
`venv/bin/python3`.

Il faut relancer `pip`, car quatre dépendances sont nouvelles : `discord.py`,
`discord-ext-voice-recv` et `PyNaCl`, qui ne servent que si un jeton Discord est
renseigné, et `tzdata` (fuseaux horaires, absents de Windows).

Votre `.env` est conservé. Comparez-le à `.env.example` : les nouveaux réglages
(Discord, Slack, heures calmes, Notion…) y sont décrits, et ils sont vides par
défaut.

Les capacités déjà choisies restent cochées. Les nouvelles sont décochées : à
vous de les ajouter dans l'installeur.

Si vous n'aviez jamais lancé l'installeur (installation par `install.bat`),
JARVIS 1.1.0 laissait tout ouvert. La 1.2.0 n'active plus que les capacités par
défaut : lancez `installeur.py` une fois pour cocher celles dont vous vous
serviez (domotique, courrier…) et pour générer le jeton d'accès du téléphone.
