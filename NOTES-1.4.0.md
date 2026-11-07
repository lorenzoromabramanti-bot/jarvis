# JARVIS 1.4.0

*Français plus bas.*

This version is about the voice and school: JARVIS hears you better, answers faster, and can
be your teacher.

## What changes

**Teacher Mode.** "Quiz me on Pythagoras", "give me a lesson on realism", "review my mistakes":
JARVIS writes a quiz or a short lesson on any subject, asks the questions one by one, gives a
hint, repeats, explains the lesson again. Missed questions become flashcards that come back
two days later, then five. A paused quiz resumes where you left it ("reprends la révision").
With Pronote, "fais-moi réviser" now prepares the quiz for your next test in about twenty
seconds with the online model, instead of two to four minutes with the local one, which stays
the fallback. Inspired by the Teacher Mode of TechEnClair's JARVIS 10.6. Needs the "Révisions"
capability.

**A new ear.** Listening runs in its own process (`oreille.py`): Silero cuts your sentences
after half a second of silence, Google transcribes them, and Parakeet takes over on the
computer when the Internet is down. You can interrupt JARVIS ("stop", "attends", "Jarvis")
while it talks, and keep talking for a few seconds after an answer without saying "Jarvis"
again. Optional: `requirements-voix.txt`.

**Faster answers.** The first sentence of a spoken answer starts while the rest is still being
written.

**More natural.** JARVIS says "tu", drops robot phrasing, and an empty answer from a failing
model no longer enters the conversation.

**Tasks in several steps.** "Mission : …" lets an agent chain the steps alone (Pronote,
calendar, reading mail, web, notes) and report back. It never sends anything to anyone.

**The judge.** Say "juge-moi": every three minutes, JARVIS looks at your webcam and screen with
a local model (nothing is saved) and teases you if you are doing nothing. Off by default.

**Floating orb.** A small orb stays above the other windows and follows what JARVIS is doing.
Click: the quick bar. Double-click: hidden until the next start. It hides during games and
videos.

**Homework by voice.** "J'ai quoi comme devoirs ?" and "c'est quoi ma moyenne ?" read Pronote
(through Home Assistant) instead of letting the model guess.

**Creation tab.** In the interface, image, video and website requests show which model to use,
the progress, and the result with the prompt that produced it.

**Quieter during a quiz.** Background announcements (planes nearby, mail summary) wait until
the quiz is over. Timers and alerts still speak.

**Restarts cleanly.** A restart closes the previous listening process and interface instead of
launching copies, and a second ear can no longer listen on the same port.

**Muted microphone.** If your microphone is muted in Windows, JARVIS tells you, once.

Also: lighter while a game runs (when a game-mode tool writes `~/mode-jeu/actif.json`),
WebSocket errors logged instead of swallowed, the list of connections locked between threads,
dead background tasks purged, startup waits for the interface, and freeing a port targets that
exact port.

## What you need to know

- JARVIS started from J.A.R.V.I.S. v9 by TechEnClair: see the credits in the README and `NOTICE`.
- Integrations made for the author's own setup (Paperclip, Prisme RGB lights, REA site
  dismantling, shared memory) are included but off by default.
- Nothing you say is written to disk: the sentence journal (`garder_phrases`) is off by default.

---

# JARVIS 1.4.0 (français)

Cette version parle de voix et d'école : JARVIS t'entend mieux, répond plus vite, et peut être
ton professeur.

## Ce qui change

**Le Mode Professeur.** « Interroge-moi sur Pythagore », « fais-moi un cours sur le réalisme »,
« révise mes erreurs » : JARVIS écrit un quiz ou un petit cours sur n'importe quel sujet, pose
les questions une par une, donne un indice, répète, redit le cours. Les questions ratées
deviennent des cartes mémoire qui reviennent deux jours plus tard, puis cinq. Un quiz en pause
reprend où il s'était arrêté (« reprends la révision »). Avec Pronote, « fais-moi réviser »
prépare maintenant le quiz de ta prochaine évaluation en une vingtaine de secondes avec le
modèle en ligne, au lieu de deux à quatre minutes avec le modèle local, qui reste le secours.
Inspiré du Mode Professeur du JARVIS 10.6 de TechEnClair. Demande la capacité « Révisions ».

**Une nouvelle oreille.** L'écoute tourne dans son propre processus (`oreille.py`) : Silero
découpe tes phrases après une demi-seconde de silence, Google les transcrit, et Parakeet prend
le relais sur l'ordinateur quand Internet est coupé. Tu peux couper la parole à JARVIS
(« stop », « attends », « Jarvis ») pendant qu'il parle, et continuer quelques secondes après
une réponse sans redire « Jarvis ». Facultatif : `requirements-voix.txt`.

**Des réponses plus rapides.** La première phrase d'une réponse parlée part pendant que la
suite s'écrit encore.

**Plus naturel.** JARVIS tutoie, abandonne les formules de robot, et une réponse vide d'un
modèle en panne n'entre plus dans la conversation.

**Des tâches en plusieurs étapes.** « Mission : … » : un agent enchaîne seul les étapes
(Pronote, agenda, lecture des mails, web, notes) et rend compte. Il n'envoie jamais rien à
personne.

**Le juge.** Dis « juge-moi » : toutes les trois minutes, JARVIS regarde ta webcam et ton écran
avec un modèle local (rien n'est enregistré) et te taquine si tu ne fais rien. Désactivé par
défaut.

**L'orbe flottante.** Une petite orbe reste au-dessus des autres fenêtres et suit ce que fait
JARVIS. Clic : la barre rapide. Double-clic : cachée jusqu'au prochain démarrage. Elle se cache
pendant les jeux et les vidéos.

**Les devoirs à la voix.** « J'ai quoi comme devoirs ? » et « c'est quoi ma moyenne ? » lisent
Pronote (via Home Assistant) au lieu de laisser le modèle deviner.

**L'onglet Création.** Dans l'interface, une demande d'image, de vidéo ou de site montre quel
modèle utiliser, l'avancement, et le résultat avec le prompt qui l'a produit.

**Plus calme pendant un quiz.** Les annonces de fond (avions proches, résumé des mails)
attendent la fin du quiz. Les minuteurs et les alertes parlent toujours.

**Des redémarrages propres.** Un redémarrage ferme l'ancienne écoute et l'ancienne interface au
lieu d'en lancer des copies, et une deuxième oreille ne peut plus écouter le même port.

**Micro coupé.** Si ton micro est coupé dans Windows, JARVIS te le dit, une fois.

Aussi : plus léger pendant une partie (quand un outil de mode jeu écrit
`~/mode-jeu/actif.json`), les erreurs du WebSocket notées au lieu d'être avalées, la liste des
connexions verrouillée entre fils, les tâches de fond mortes purgées, le démarrage qui attend
l'interface, et la libération d'un port qui vise ce port exact.

## À savoir

- JARVIS est parti du J.A.R.V.I.S. v9 de TechEnClair : voir les crédits dans le README et `NOTICE`.
- Des intégrations faites pour l'installation de l'auteur (Paperclip, éclairage RGB Prisme,
  démontage de site REA, mémoire partagée) sont incluses mais désactivées par défaut.
- Rien de ce que tu dis n'est écrit sur le disque : le journal des phrases (`garder_phrases`) est
  désactivé par défaut.
