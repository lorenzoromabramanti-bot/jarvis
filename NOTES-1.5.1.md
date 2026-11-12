# JARVIS 1.5.1

*Français plus bas.*

**JARVIS no longer reads out fake tool calls.** Some models answered a question like "which music is
playing?" with an unusable text, `<dots_function_call> invoke name="voir_ecran"…`, instead of an
answer. JARVIS read it aloud, showed it on screen, and kept it in its conversation memory, where it
became an example the model then copied. Now that text is never spoken, never shown, never executed
(it asked JARVIS to "look at the screen", which JARVIS uses to click) and never kept in memory. If it
was the whole reply, JARVIS asks the model again for a real answer. Old entries are cleaned when the
history is reloaded.

**The Glass Orb gets its halo and its voice line.** A soft glow around the orb, stronger when JARVIS
listens or speaks, and a line of dots under it that moves with its voice. The Devices card now shows
only what is on, one line per device (a real Home Assistant counted about thirty players, many off or
duplicated).

**The website and the README show the Glass Orb.** New screenshots (light and dark), the animated
orb, the glass orb in place of the old 3D scene on the website, and the interface text updated in the
six languages.

---

# JARVIS 1.5.1 (français)

**JARVIS ne lit plus les faux appels d'outil.** Certains modèles répondaient à une question comme
« quelle musique joue ? » par un texte inutilisable, `<dots_function_call> invoke name="voir_ecran"…`,
au lieu d'une réponse. JARVIS le lisait à voix haute, l'affichait, et le gardait dans sa mémoire de
conversation, où il devenait un exemple que le modèle recopiait. Maintenant ce texte n'est jamais dit,
jamais affiché, jamais exécuté (il demandait à JARVIS de « regarder l'écran », une action que JARVIS
utilise pour cliquer) et jamais gardé en mémoire. S'il formait toute la réponse, JARVIS redemande une
vraie réponse au modèle. Les anciennes entrées sont nettoyées au rechargement de l'historique.

**L'Orbe de verre a son halo et sa ligne de voix.** Une lueur douce autour de l'orbe, plus forte quand
JARVIS écoute ou parle, et une ligne de points dessous qui bouge avec sa voix. La carte Appareils
n'affiche plus que ce qui est allumé, une ligne par appareil (un vrai Home Assistant comptait une
trentaine de lecteurs, beaucoup éteints ou en double).

**Le site et le README montrent l'Orbe de verre.** De nouvelles captures (claires et sombres), l'orbe
animée, l'orbe de verre à la place de l'ancienne scène 3D sur le site, et le texte de l'interface mis à
jour dans les six langues.
