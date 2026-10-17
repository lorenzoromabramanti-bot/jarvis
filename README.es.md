<div align="center">

# J.A.R.V.I.S

[English](README.md) · [Français](README.fr.md) · **Español** · [中文](README.zh-CN.md) · [हिन्दी](README.hi.md) · [Português](README.pt-BR.md)

Un asistente de voz para el escritorio. Escucha, responde y actúa sobre tu ordenador: Home
Assistant, correo, actualizaciones de software, VPN, abrir aplicaciones, leer la pantalla.

[**Sitio web**](https://lorenzoromabramanti-bot.github.io/jarvis/) · [**Descargar**](../../releases/latest)

![La interfaz de JARVIS](docs/images/hud-desktop.jpg)

</div>

Funciona en segundo plano, sin ventana, y se invoca con el teclado desde cualquier
aplicación.

---

## Qué hace

**Responder.** Una cadena de herramientas locales resuelve primero lo que sabe hacer — hora,
cálculos, conversiones, información sobre el equipo — en **dos a seis milisegundos**, sin
llamar a ningún modelo. El resto va al modelo.

**Actuar.** Luces y enchufes de Home Assistant, ordenar el correo y redactar respuestas,
actualizaciones con `winget`, VPN, desinstalar programas, controlar Spotify y Deezer.
Pestañas, vídeos, ventanas, bloqueo y aplicaciones abiertas se manejan directamente, sin pasar
por el modelo.

**Callarse cuando no sabe.** Es una decisión de diseño, no de cortesía: un asistente que dice
"hecho" sin haber hecho nada es peor que uno que se niega. En domótica, una acción rechazada
por Home Assistant se anuncia como un fallo.

**Seguir sin Gemini.** Si Gemini no responde, cambia a un modelo local de Ollama. La lista de
modelos se lee del servidor Ollama real.

**Trabajar a distancia y en segundo plano.**

| | | |
|---|---|---|
| **Discord** | hablar con JARVIS y darle órdenes; pide confirmación antes de una acción sensible. También puede entrar en un canal de voz | token e identificador en `.env` |
| **Notificaciones** | un mensaje de Discord o Slack cuando termina una tarea en segundo plano, salvo en las horas de silencio | webhook en `.env` |
| **Esta noche** | "haz esto esta noche": la tarea espera y el informe llega con el resumen de la mañana | |
| **Subtareas** | una petición que compara varias cosas se divide y se procesa en paralelo; a partir de 5 subtareas, pregunta | |
| **Hasta el plazo** | relee y mejora su trabajo mientras quede tiempo | |

**Programar.** Encarga una tarea de código a Claude Code, Codex, OpenCode, Cursor Agent u
OpenClaw, en un proyecto que hayas declarado. Sin ellos, su propio agente de archivos lee,
busca y modifica el proyecto, encerrado en la carpeta del proyecto.

**Rendir cuentas.** El coste y los tokens de cada llamada a los modelos están a la vista. Un
registro de confianza por tipo de acción: la autonomía se gana acción por acción, no se
concede de antemano.

**Seguimiento.** Capacidades opcionales, para marcar en la instalación o en los ajustes —
todas desactivadas por defecto:

| | | |
|---|---|---|
| **Habilidades añadidas** | ver las que JARVIS se ha escrito, apagar una sin borrarla, saber cuál está rota | "lista de habilidades", "desactiva la habilidad *nombre*" |
| **Portapapeles** | traducir, resumir, explicar o corregir lo que se acaba de copiar — el texto corregido vuelve al portapapeles | "traduce el portapapeles", "corrige el portapapeles" |
| **Vigilancia de temas** | una comprobación al día de los temas elegidos; lo nuevo se cuenta en el resumen de la mañana, nunca interrumpiéndote | "vigila los anuncios de AMD", "¿qué estás vigilando?" |
| **Recordatorios del sistema** | confiados al Programador de tareas: saltan aunque JARVIS esté cerrado, incluso tras reiniciar | acción `rappel_os_creer` (HUD, app iOS) |
| **Notas de Notion** | crear, leer, editar, borrar y buscar notas | token de Notion en `.env` |

### Opciones desactivadas por defecto

Algunas funciones dependen de una instalación concreta: una casa, un centro escolar, un
servicio externo. Vienen **apagadas**, sin ningún valor por defecto. Mientras no las
configures, no hacen nada y lo dicen.

| | | |
|---|---|---|
| **Horario** | las clases de Pronote copiadas en un calendario de Google aparte, las clases canceladas marcadas y la franja liberada | Home Assistant con la integración Pronote, cuenta de Google |
| **Repaso** | un cuestionario preparado la víspera de un examen, y "ayúdame a repasar" | el horario de arriba, Ollama |
| **Presencia por webcam** | una foto enviada a Discord cuando alguien pasa por delante del escritorio | webcam, bot de Discord |
| **Mapa OSINT 3D** | abre God's Eye View y ShadowBroker desde JARVIS | esos dos programas, instalados aparte |
| **Delegación de código** | ver *Programar* arriba | el agente de código que elijas |

**Para activar una:** vuelve a ejecutar el instalador (`installeur.py`), sección
*Capacidades*, márcala y rellena los ajustes que pida. Las opciones marcadas como "avanzadas"
solo aparecen en modo avanzado. Cada ajuste se describe en `.env.example`.

## La interfaz

<p align="center"><img src="docs/images/orbe.webp" alt="La esfera de JARVIS, en movimiento" width="340"></p>

![La pestaña Agents lista las herramientas de IA encontradas en el equipo](docs/images/hud-agents.jpg)

<img src="docs/images/hud-mobile.jpg" alt="La interfaz en un teléfono" width="260" align="right">

Una esfera 3D que reacciona a la voz de JARVIS, el chat, el estado del equipo y un *Data
center* con pestañas: tareas, habilidades, memoria, agenda, multimedia, día a día, casa,
seguridad, ajustes, controles, agentes y sistema. La pestaña **Agents** lista las
herramientas de IA encontradas en el equipo (asistentes de código, servidores MCP, motores de
modelos) y cuáles están en marcha.

También funciona en el teléfono, desde el navegador.

La interfaz está construida sobre [openclaw-jarvis-ui](https://github.com/jincocodev/openclaw-jarvis-ui)
de **JincocoDev** (licencia ISC, ver [`frontend/LICENSE`](frontend/LICENSE)), basado a su vez en
el [Three.js Orb Visualizer](https://codepen.io/filipz/pen/yyyRgry) de **Filip Zrnzevic**. Se ha
reconectado para hablar directamente con JARVIS.

Necesita **Node.js** (22 LTS recomendado, 20.19 como mínimo). En el primer arranque, JARVIS
instala sus paquetes por sí mismo (`npm install`, uno o dos minutos). Sin Node.js, JARVIS
sigue funcionando por voz y con la barra rápida.

<br clear="right">

## Cómo hablarle

| | |
|---|---|
| **Voz** | decir "Jarvis" y luego la petición |
| **Ctrl+Alt+J** | aparece una barra en el centro de la pantalla, desde cualquier aplicación |
| **El HUD** | la interfaz completa — casa, correo, agenda, seguridad, ajustes |

Cerrar la ventana no lo detiene: sigue en segundo plano, con un icono junto al reloj. Para
detenerlo: "salir de jarvis", o el menú de ese icono.

---

## Instalación

**Descarga el instalador desde la página de [versiones](../../releases) y ejecútalo.** Busca
un Python utilizable, descarga la última versión, lo prepara todo y abre el asistente de
configuración.

| Sistema | Archivo | Estado |
|---|---|---|
| Windows 10 / 11 | `Installer-JARVIS.exe` | probado |
| Linux | `python3 amorceur/amorceur.py` | probado en Ubuntu 26.04 |
| macOS | `python3 amorceur/amorceur.py` | **nunca probado en un Mac real** — ver [docs/macos.md](docs/macos.md) |

El instalador pesa 11 MB: descarga JARVIS en lugar de incluirlo. Así puedes leer el código
antes de que se instale — algo importante en un programa que controla tu ordenador.

Hace falta **Python 3.10 a 3.13**. La 3.14 es demasiado reciente: varias dependencias aún no
tienen versión compilada para ella.

### A mano, si lo prefieres

```bash
git clone <url-del-repositorio> jarvis
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

Para saber en cualquier momento qué falta (`venv\Scripts\python.exe` en Windows,
`venv/bin/python3` en Linux/macOS):

```bash
config.py
```

Este comando lista lo que está disponible en tu equipo y **qué funciones están degradadas, y
por qué**.

`requirements.txt` también incluye `discord.py`, `discord-ext-voice-recv` y `PyNaCl`, para el
bot y la voz de Discord. Solo se usan si hay un token de Discord configurado.

### El reconocimiento de voz va aparte

`requirements-voix.txt` pesa varios gigabytes (torch, Nemotron). Sin él, JARVIS funciona con
el teclado, la barra rápida y el HUD; solo falta el dictado, y lo dice.

## Ajustes

Dos son necesarios, el resto es opcional. `.env.example` explica para qué sirve cada uno y
dónde conseguirlo.

| | |
|---|---|
| `GEMINI_API_KEY` | el modelo principal. Sin él, solo responden las herramientas locales |
| `JARVIS_ACCESS_TOKEN` | protege el WebSocket, **que ejecuta comandos del sistema** |

El segundo no es opcional en la práctica: sin él, la autenticación queda desactivada y
cualquier programa del equipo puede controlar JARVIS. El instalador genera uno largo y
aleatorio.

---

## Sistemas

**Windows 10 y 11** — desarrollado y probado ahí.

**Linux, macOS** — JARVIS arranca, pero parte de las funciones no está disponible: las que
dependen de PowerShell, `winget`, el registro o la API de Windows. Lo **dicen** en lugar de
fallar a mitad, y `config.py` las enumera.

> macOS nunca se ha probado en una máquina real. Lo escrito aquí es lo que el código prevé, no
> lo que se ha comprobado.

## Privacidad

Nada sale del equipo salvo las llamadas que configures a los modelos, al tiempo y a Home
Assistant — y, si los activas, a Discord, Slack, Notion y Google Calendar.

Las conversaciones, la configuración y el correo se quedan en local. Las claves viven en
`.env`, que `git` ignora. El HUD oculta las claves en pantalla: nunca recibe su valor, solo si
existen.

Las acciones irreversibles — enviar un correo, desinstalar un programa — piden un acuerdo
explícito y **muestran exactamente lo que va a salir** antes de hacerlo.

## Seguridad

- **WebSocket protegido.** Se genera un token en la instalación. Sin token, JARVIS solo
  escucha en el equipo local.
- **Las opciones siguen apagadas.** Una opción sin marcar sigue desactivada, incluso sin pasar
  por el instalador.
- **Confirmación antes de las acciones de riesgo.** Alarma, cerradura y control remoto del PC
  piden un acuerdo explícito.
- **Delegación de código y recordatorios.** El texto de una tarea o de un recordatorio nunca
  se ejecuta como un comando.

## Actualizaciones

Versión actual: **1.3.0**. Los cambios se describen en [NOTES-1.3.0.md](NOTES-1.3.0.md).

Al arrancar, JARVIS pregunta a GitHub si hay una versión más reciente y lo avisa. Nunca
instala nada por su cuenta. Rellena `JARVIS_DEPOT` en `.env` para activar esta comprobación;
déjalo vacío para desactivarla.

---

## Contribuir

El proyecto mantiene dos reglas, que explican la forma del código:

**Una función no disponible lo dice.** No devuelve una lista vacía, no responde "hecho", no se
inventa un valor por defecto. La mayoría de las correcciones de este repositorio vienen de
haber roto esta regla en algún sitio.

**Lo que se afirma se comprueba.** Los archivos `_test_*.py` se ejecutan directamente, sin
marco de pruebas:

```bash
venv\Scripts\python.exe _test_machine.py
```

No comprueban que el código hace lo que hace, sino que no repite errores ya cometidos — una
frase que congelaba el programa, un nombre escrito a mano en el código, una comparación de
versiones por orden alfabético.

## Licencia

Por definir. La interfaz de la carpeta `frontend/` está bajo licencia ISC (JincocoDev).
