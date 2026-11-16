# JARVIS 1.6.0

*Français plus bas.*

**The setup assistant lets you choose JARVIS's brain.** A new "Brains" step looks at what you already
have: API keys saved in your settings, models running in Ollama, an OmniRoute gateway. You can test a
key, add one (Gemini, Groq, Claude, OpenAI, Mistral or Grok) and pick the brain JARVIS prefers, without
editing a file. A key never reaches the page of the assistant, and it is only ever sent to its own
provider, in a header, never in an address. Claude and Gemini subscriptions (the chat plans) are not
offered: they are not meant to be plugged into other software. API keys only.

**A new look for the setup assistant and the starter.** The setup assistant now has seven short steps in
the glass style of the Glass Orb, light by day and dark at night, and the starter that downloads JARVIS
wears the same look. The setup assistant also no longer freezes: with recent
versions of pywebview its window could stay on a page where no button worked, because the window itself
was handed to the page. A test now guards it. Writes to the settings file are taken in turn, so two
simultaneous saves cannot lose a line, and a placeholder such as `votre_cle` is no longer counted as a
key.

**The quick bar (Ctrl+Alt+J) is complete.** Rebuilt in the Glass Orb style: suggestion chips (time,
weather, schedule, "quiz me on…", timer, music), up and down arrows to bring back what you asked before,
answers with bold, italics, code and lists, a Copy button, and a microphone button that makes JARVIS
listen right away, without "Jarvis". The window follows the length of the answer, has rounded corners,
and closes with Esc. A request that needs your agreement asks for it, as in the HUD. It also no longer
opens as an empty panel: if its page does not answer, or after two minutes closed, the page is reloaded
first, and a short message replaces the blank panel if the interface is down.

**Dark mode and settings by voice.** "Mode sombre", "mode clair" or "thème automatique" switches the
interface; "ouvre tes réglages" opens the settings tab. Before, the model invented explanations.

**JARVIS no longer goes silent on a JSON answer.** One route sometimes sent the question to a model
made to extract JSON, which replied `{"message": …}`. JARVIS removes everything between braces from
what it says, so it said nothing. Such an answer is now skipped (the next model is tried, or JARVIS asks
again) and never kept in memory.

**Ready-made answers only for short, bare messages.** "Say hi to my mother" is an instruction, not a
greeting: it now gets a real hello. "Hello" or "thanks" still get an instant answer. Also fixed: "at
what time does Starship land?" is no longer answered with the current time, the system note pasted
next to your message is no longer kept as something you said, the web is searched only for questions,
and by voice, when the models are down, JARVIS says so in one sentence.

**JARVIS has a logo.** It sits at the top of the README, on the website and its journal, in the browser
tab of the Glass Orb, on the home-screen icon of the phone app, and as the Windows icon.

---

# JARVIS 1.6.0 (français)

**L'assistant d'installation laisse choisir le cerveau de JARVIS.** Une nouvelle étape « Cerveaux »
regarde ce que vous avez déjà : des clés d'API enregistrées dans vos réglages, des modèles qui tournent
dans Ollama, une passerelle OmniRoute. On peut tester une clé, en ajouter une (Gemini, Groq, Claude,
OpenAI, Mistral ou Grok) et choisir le cerveau préféré de JARVIS, sans éditer de fichier. Une clé
n'arrive jamais jusqu'à la page de l'assistant, et elle n'est envoyée qu'à son propre fournisseur, dans
un en-tête, jamais dans une adresse. Les abonnements Claude et Gemini (les formules de chat) ne sont pas
proposés : ils ne sont pas faits pour être branchés dans un autre logiciel. Des clés d'API seulement.

**Un nouvel habillage pour l'assistant d'installation et l'amorceur.** L'assistant compte maintenant sept
étapes courtes, dans le style verre de l'Orbe de verre, clair le jour et sombre la nuit, et l'amorceur qui
télécharge JARVIS prend le même habillage. L'assistant ne se fige plus non plus :
avec les versions récentes de pywebview, sa fenêtre pouvait rester sur une page où aucun bouton ne
répondait, parce que la fenêtre elle-même était confiée à la page. Un test le surveille. Les écritures du
fichier de réglages se font à tour de rôle, donc deux enregistrements simultanés ne peuvent plus perdre
une ligne, et un modèle comme `votre_cle` n'est plus compté comme une clé.

**La barre rapide (Ctrl+Alt+J) est complète.** Refaite dans le style de l'Orbe de verre : des puces de
suggestion (heure, météo, emploi du temps, « interroge-moi sur… », minuteur, musique), les flèches haut et
bas pour rappeler ce qu'on a demandé avant, des réponses avec gras, italique, code et listes, un bouton
Copier, et un bouton micro qui fait écouter JARVIS tout de suite, sans « Jarvis ». La fenêtre suit la
longueur de la réponse, a les coins arrondis et se ferme avec Échap. Une demande qui exige votre accord le
demande, comme dans le HUD. Elle ne s'ouvre plus non plus en panneau vide : si sa page ne répond pas, ou
après deux minutes fermée, la page est rechargée d'abord, et une phrase remplace le panneau vide si
l'interface est arrêtée.

**Mode sombre et réglages à la voix.** « Mode sombre », « mode clair » ou « thème automatique » change
l'interface ; « ouvre tes réglages » ouvre l'onglet des réglages. Avant, le modèle inventait des
explications.

**JARVIS ne reste plus muet sur une réponse JSON.** Une route envoyait parfois la question à un modèle
fait pour extraire du JSON, qui répondait `{"message": …}`. JARVIS retire tout ce qui est entre
accolades de ce qu'il dit, donc il ne disait rien. Une telle réponse est maintenant ignorée (on essaie le
modèle suivant, ou JARVIS redemande) et jamais gardée en mémoire.

**Les réponses toutes faites ne valent que pour un message court et nu.** « Dis coucou à ma mère » est
une consigne, pas un bonjour : elle reçoit maintenant un vrai bonjour. « Bonjour » ou « merci » reçoivent
toujours une réponse instantanée. Corrigé aussi : « à quelle heure se pose Starship ? » n'est plus
répondu par l'heure qu'il est, la note système collée à côté de votre message n'est plus gardée comme
ce que vous avez dit, le web n'est cherché que pour une question, et à la voix, quand les modèles sont
en panne, JARVIS le dit en une phrase.

**JARVIS a un logo.** Il est en tête du README, sur le site et son journal, dans l'onglet du navigateur
de l'Orbe de verre, sur l'icône d'écran d'accueil de l'application du téléphone, et comme icône Windows.
