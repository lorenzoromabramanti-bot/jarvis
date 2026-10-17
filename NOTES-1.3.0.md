# JARVIS 1.3.0

*Français plus bas.*

This version changes what you see. JARVIS now ships with a new interface, and the project
speaks six languages.

## What changes

**A new interface.** The `frontend/` folder now holds the HUD JARVIS's author uses every day:
a 3D orb that reacts to its voice, the chat, the machine's vitals, and a tabbed data center —
tasks, skills, memory, schedule, media, daily life, home, security, settings, controls, agents
and system. The **Agents** tab lists the AI tools found on the machine and which ones are
running. It works on a phone too, from the browser.

It is built on [openclaw-jarvis-ui](https://github.com/jincocodev/openclaw-jarvis-ui) by
JincocoDev (ISC License, kept in `frontend/LICENSE`), itself based on the Three.js Orb
Visualizer by Filip Zrnzevic, and rewired to talk directly to JARVIS. It reads the access token
from JARVIS's own `.env`: nothing to copy by hand.

**The interface installs itself.** The `.exe` installer only installs the Python packages, so
until now the interface never started for people who had not run `install.bat`. On first
launch, JARVIS now runs `npm install` in `frontend/` by itself (one or two minutes) when
Node.js is present. Node.js 22 LTS is recommended, 20.19 minimum. Without Node.js, JARVIS keeps
working by voice and with the quick bar, and says the interface is unavailable.

**Six languages.** The README exists in English, French, Spanish, Chinese, Hindi and
Portuguese, with screenshots of the interface.

**A new website.** The project page is now a 3D page that tells what JARVIS does as you
scroll, in the same six languages. The previous page, the project history, is still there.

## What you need to know

- The old interface (green orb with the clock) is replaced. A custom interface still plugs in
  with `JARVIS_INTERFACE_DIR` and `JARVIS_INTERFACE_PORT` in `.env`.
- The interface uses two local ports: 5173 (the page) and 9999 (its link to JARVIS).

---

# JARVIS 1.3.0 (français)

Cette version change ce qu'on voit. JARVIS est livré avec une nouvelle interface, et le projet
parle six langues.

## Ce qui change

**Une nouvelle interface.** Le dossier `frontend/` contient désormais le HUD que l'auteur de
JARVIS utilise tous les jours : une orbe 3D qui réagit à sa voix, le chat, l'état de la machine
et un data center à onglets — tâches, compétences, mémoire, planning, médias, quotidien, maison,
sécurité, réglages, contrôles, agents et système. L'onglet **Agents** liste les outils d'IA
trouvés sur la machine et lesquels tournent. Elle marche aussi sur téléphone, depuis le
navigateur.

Elle est construite sur [openclaw-jarvis-ui](https://github.com/jincocodev/openclaw-jarvis-ui)
de JincocoDev (licence ISC, conservée dans `frontend/LICENSE`), lui-même basé sur le Three.js
Orb Visualizer de Filip Zrnzevic, et rebranchée pour parler directement à JARVIS. Elle lit le
jeton d'accès dans le `.env` de JARVIS : rien à recopier à la main.

**L'interface s'installe seule.** L'installeur `.exe` n'installe que les paquets Python : jusqu'ici,
l'interface ne démarrait jamais chez qui n'avait pas lancé `install.bat`. Au premier lancement,
JARVIS lance maintenant `npm install` dans `frontend/` tout seul (une à deux minutes) si Node.js
est présent. Node.js 22 LTS conseillé, 20.19 minimum. Sans Node.js, JARVIS marche toujours à la
voix et avec la barre rapide, et dit que l'interface est indisponible.

**Six langues.** Le README existe en anglais, français, espagnol, chinois, hindi et portugais,
avec des captures de l'interface.

**Un nouveau site.** La page du projet est maintenant une page 3D qui raconte ce que fait JARVIS
au fil du défilement, dans les mêmes six langues. L'ancienne page, l'historique du projet, est
toujours là.

## À savoir

- L'ancienne interface (orbe verte avec l'horloge) est remplacée. Une interface personnalisée
  se branche toujours avec `JARVIS_INTERFACE_DIR` et `JARVIS_INTERFACE_PORT` dans `.env`.
- L'interface utilise deux ports locaux : 5173 (la page) et 9999 (son lien avec JARVIS).
