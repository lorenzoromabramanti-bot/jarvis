<div align="center">

# J.A.R.V.I.S

**English** · [Français](README.fr.md) · [Español](README.es.md) · [中文](README.zh-CN.md) · [हिन्दी](README.hi.md) · [Português](README.pt-BR.md)

A desktop voice assistant. It listens, answers, and acts on your computer: Home Assistant,
email, software updates, VPN, launching apps, reading the screen.

[**Website**](https://lorenzoromabramanti-bot.github.io/jarvis/) · [**Download**](../../releases/latest)

![The JARVIS interface](docs/images/hud-desktop.jpg)

</div>

It runs in the background, without a window, and can be summoned from the keyboard in any
application.

---

## What it does

**Answer.** A chain of local tools first handles what it knows how to do — time,
calculations, conversions, information about the machine — in **two to six milliseconds**,
without calling a model. Everything else goes to the model.

**Act.** Home Assistant lights and plugs, sorting email and drafting replies, `winget`
updates, VPN, uninstalling software, Spotify and Deezer control. Tabs, videos, windows,
locking and open applications are driven directly, without going through the model.

**Stay quiet when it doesn't know.** This is a design choice, not politeness: an assistant
that says "done" without doing anything is worse than one that refuses. In home automation,
an action refused by Home Assistant is now reported as a failure.

**Keep going without Gemini.** If Gemini does not answer, it falls back to a local Ollama
model. The list of models is read from the actual Ollama server.

**Work remotely and in the background.**

| | | |
|---|---|---|
| **Discord** | chat with JARVIS and give it orders; it asks for confirmation before a sensitive action. It can also join a voice channel | token and ID in `.env` |
| **Notifications** | a Discord or Slack message when a background task finishes, except during quiet hours | webhook in `.env` |
| **Tonight** | "do this tonight": the task waits, the report arrives with the morning briefing | |
| **Subtasks** | a request that compares several things is split up and handled in parallel; beyond 5 subtasks, it asks | |
| **Until the deadline** | it rereads and improves its work while time remains | |

**Code.** It hands a coding task to Claude Code, Codex, OpenCode, Cursor Agent or
OpenClaw, in a project you have declared. Without them, its own file agent reads, searches
and edits the project, locked inside the project folder.

**Be accountable.** The cost and tokens of every model call are visible. A trust log per
type of action: autonomy is earned action by action, not granted in advance.

**Keep track.** Optional capabilities, to tick during installation or in the settings — all
disabled by default:

| | | |
|---|---|---|
| **Added skills** | see the ones JARVIS wrote for itself, turn one off without deleting it, know which one is broken | "list skills", "disable skill *name*" |
| **Clipboard** | translate, summarise, explain or correct what was just copied — the corrected text goes back to the clipboard | "translate the clipboard", "fix the clipboard" |
| **Topic watch** | one check a day on chosen topics; anything new is mentioned in the morning briefing, never by interrupting you | "watch AMD announcements", "what are you watching?" |
| **System reminders** | handed to the Task Scheduler: they fire even with JARVIS closed, even after a restart | action `rappel_os_creer` (HUD, iOS app) |
| **Notion notes** | create, read, edit, delete and search notes | Notion token in `.env` |

### Options disabled by default

Some features depend on a specific setup: a home, a school, a third-party service. They ship
**switched off**, with no default value. Until you configure them, they do nothing and say
so.

| | | |
|---|---|---|
| **Timetable** | Pronote lessons copied into a separate Google calendar, cancelled lessons marked and the slot freed | Home Assistant with the Pronote integration, Google account |
| **Revision** | a quiz prepared the day before a test, and "help me revise" | the timetable above, Ollama |
| **Webcam presence** | a photo sent to Discord when someone walks past the desk | webcam, Discord bot |
| **3D OSINT map** | opens God's Eye View and ShadowBroker from JARVIS | those two programs, installed separately |
| **Code delegation** | see *Code* above | the coding agent of your choice |

**To enable one:** run the installer again (`installeur.py`), *Capabilities* section, tick
it, then fill in the settings it asks for. Options marked "advanced" only appear in advanced
mode. Every setting is described in `.env.example`.

## The interface

<p align="center"><img src="docs/images/orbe.webp" alt="The JARVIS orb, live" width="340"></p>

![The Agents tab lists the AI tools found on the machine](docs/images/hud-agents.jpg)

<img src="docs/images/hud-mobile.jpg" alt="The interface on a phone" width="260" align="right">

A 3D orb that reacts to JARVIS's voice, the chat, the machine's status, and a *Data center*
with tabs: tasks, skills, memory, schedule, media, daily life, home, security, settings,
controls, agents and system. The **Agents** tab lists the AI tools found on the machine
(coding assistants, MCP servers, model engines) and which ones are running.

It also works on a phone, from the browser.

The interface is built on [openclaw-jarvis-ui](https://github.com/jincocodev/openclaw-jarvis-ui)
by **JincocoDev** (ISC License, see [`frontend/LICENSE`](frontend/LICENSE)), itself based on the
[Three.js Orb Visualizer](https://codepen.io/filipz/pen/yyyRgry) by **Filip Zrnzevic**. It has
been rewired to talk directly to JARVIS.

It needs **Node.js** (22 LTS recommended, 20.19 minimum). On first launch, JARVIS installs its
packages by itself (`npm install`, one or two minutes). Without Node.js, JARVIS still works by
voice and with the quick bar.

<br clear="right">

## How to talk to it

| | |
|---|---|
| **Voice** | say "Jarvis", then the request |
| **Ctrl+Alt+J** | a bar appears in the middle of the screen, from any application |
| **The HUD** | the full interface — home, email, calendar, security, settings |

Closing the window does not stop it: it keeps running in the background, with an icon near
the clock. To stop it: "quit jarvis", or the menu of that icon.

---

## Installation

**Download the installer from the [releases](../../releases) page and run it.** It finds a
usable Python, fetches the latest version, prepares everything, then opens the setup
assistant.

| System | File | Status |
|---|---|---|
| Windows 10 / 11 | `Installer-JARVIS.exe` | tested |
| Linux | `python3 amorceur/amorceur.py` | tested on Ubuntu 26.04 |
| macOS | `python3 amorceur/amorceur.py` | **never tried on a real Mac** — see [docs/macos.md](docs/macos.md) |

The installer weighs 11 MB: it downloads JARVIS rather than bundling it. So you can read the
code before it installs — which matters for a program that controls your computer.

You need **Python 3.10 to 3.13**. 3.14 is too recent: several dependencies do not have a
compiled version for it yet.

### By hand, if you prefer

```bash
git clone <repository-url> jarvis
cd jarvis
python -m venv venv
```

**Windows**
```bash
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
venv\Scripts\python.exe installeur.py
```

**Linux / macOS**
```bash
venv/bin/python3 -m pip install -r requirements.txt
cp .env.example .env
venv/bin/python3 installeur.py
```

To see what is missing at any time (`venv\Scripts\python.exe` on Windows, `venv/bin/python3`
on Linux/macOS):

```bash
config.py
```

This command lists what is available on your machine and **which features are degraded,
with the reason**.

`requirements.txt` also contains `discord.py`, `discord-ext-voice-recv` and `PyNaCl`, for the
Discord bot and voice. They are only used if a Discord token is set.

### Speech recognition is separate

`requirements-voix.txt` weighs several gigabytes (torch, Nemotron). Without it, JARVIS works
from the keyboard, the quick bar and the HUD; only dictation is missing, and it says so.

## Settings

Two are required, the rest is optional. `.env.example` explains what each one is for and
where to get it.

| | |
|---|---|
| `GEMINI_API_KEY` | the main model. Without it, only the local tools answer |
| `JARVIS_ACCESS_TOKEN` | protects the WebSocket, **which runs system commands** |

The second is not optional in practice: without it, authentication is disabled and any
program on the machine can drive JARVIS. The installer generates a long random one.

---

## Systems

**Windows 10 and 11** — developed and tested there.

**Linux, macOS** — JARVIS starts, but some features are unavailable: those that rely on
PowerShell, `winget`, the registry or the Windows API. They **say so** instead of failing
mid-flight, and `config.py` lists them.

> macOS has never been tried on a real machine. What is written here is what the code
> intends, not what has been observed.

## Privacy

Nothing leaves the machine except the calls you configure to models, the weather and Home
Assistant — and, if you enable them, Discord, Slack, Notion and Google Calendar.

Conversations, configuration and email stay local. Keys live in `.env`, which `git` ignores.
The HUD masks keys on screen: it never receives their value, only whether they are present.

Irreversible actions — sending an email, uninstalling software — require explicit consent and
**show exactly what is going to be sent** before doing it.

## Security

- **Protected WebSocket.** A token is generated at installation. Without a token, JARVIS only
  listens on the local machine.
- **Options stay off.** An unticked option stays disabled, even without going through the
  installer.
- **Confirmation before risky actions.** Alarm, lock and remote control of the PC require
  explicit consent.
- **Code delegation and reminders.** The text of a task or a reminder is never executed as a
  command.

## Updates

Current version: **1.3.0**. What changed is described in [NOTES-1.3.0.md](NOTES-1.3.0.md).

On launch, JARVIS asks GitHub whether a newer version exists and reports it. It never
installs anything by itself. Set `JARVIS_DEPOT` in `.env` to enable this check; leave it
empty to disable it.

---

## Contributing

The project keeps two rules, which explain the shape of the code:

**An unavailable feature says so.** It does not return an empty list, does not answer "done",
does not invent a default value. Most fixes in this repository come from breaking this rule
somewhere.

**What is claimed is verified.** The `_test_*.py` files run directly, without a test
framework:

```bash
venv\Scripts\python.exe _test_machine.py
```

They do not check that the code does what it does, but that it does not repeat mistakes
already made — a sentence that froze the program, a first name hard-coded, a version
comparison done in alphabetical order.

## License

To be defined. The interface in `frontend/` is under the ISC License (JincocoDev).
