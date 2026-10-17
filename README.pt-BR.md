<div align="center">

# J.A.R.V.I.S

[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [中文](README.zh-CN.md) · [हिन्दी](README.hi.md) · **Português**

Um assistente de voz para o computador. Ele escuta, responde e age na sua máquina: Home
Assistant, e-mail, atualizações de software, VPN, abrir aplicativos, ler a tela.

[**Site**](https://lorenzoromabramanti-bot.github.io/jarvis/) · [**Baixar**](../../releases/latest)

![A interface do JARVIS](docs/images/hud-desktop.jpg)

</div>

Ele roda em segundo plano, sem janela, e pode ser chamado pelo teclado em qualquer aplicativo.

---

## O que ele faz

**Responder.** Uma cadeia de ferramentas locais resolve primeiro o que sabe fazer — hora,
cálculos, conversões, informações sobre a máquina — em **dois a seis milissegundos**, sem
chamar nenhum modelo. O resto vai para o modelo.

**Agir.** Luzes e tomadas do Home Assistant, organizar o e-mail e redigir respostas,
atualizações com `winget`, VPN, desinstalar programas, controlar Spotify e Deezer. Abas,
vídeos, janelas, bloqueio e aplicativos abertos são controlados diretamente, sem passar pelo
modelo.

**Ficar quieto quando não sabe.** É uma escolha de design, não de educação: um assistente que
diz "feito" sem ter feito nada é pior do que um que se recusa. Na automação residencial, uma
ação recusada pelo Home Assistant é anunciada como uma falha.

**Continuar sem o Gemini.** Se o Gemini não responder, ele passa para um modelo local do
Ollama. A lista de modelos é lida no servidor Ollama real.

**Trabalhar a distância e em segundo plano.**

| | | |
|---|---|---|
| **Discord** | conversar com o JARVIS e dar ordens; ele pede confirmação antes de uma ação sensível. Também pode entrar em um canal de voz | token e identificador no `.env` |
| **Notificações** | uma mensagem no Discord ou no Slack quando uma tarefa em segundo plano termina, exceto nos horários de silêncio | webhook no `.env` |
| **Esta noite** | "faça isso esta noite": a tarefa espera e o relatório chega no resumo da manhã | |
| **Subtarefas** | um pedido que compara várias coisas é dividido e processado em paralelo; acima de 5 subtarefas, ele pergunta | |
| **Até o prazo** | ele relê e melhora o trabalho enquanto houver tempo | |

**Programar.** Ele entrega uma tarefa de código ao Claude Code, Codex, OpenCode, Cursor Agent
ou OpenClaw, em um projeto que você declarou. Sem eles, o próprio agente de arquivos lê, busca
e altera o projeto, preso dentro da pasta do projeto.

**Prestar contas.** O custo e os tokens de cada chamada aos modelos ficam visíveis. Um registro
de confiança por tipo de ação: a autonomia é conquistada ação por ação, não concedida de
antemão.

**Acompanhar.** Recursos opcionais, para marcar na instalação ou nas configurações — todos
desativados por padrão:

| | | |
|---|---|---|
| **Habilidades adicionadas** | ver as que o JARVIS escreveu para si, desligar uma sem apagá-la, saber qual está quebrada | "lista de habilidades", "desative a habilidade *nome*" |
| **Área de transferência** | traduzir, resumir, explicar ou corrigir o que acabou de ser copiado — o texto corrigido volta para a área de transferência | "traduza a área de transferência", "corrija a área de transferência" |
| **Monitoramento de temas** | uma verificação por dia dos temas escolhidos; o que for novo é dito no resumo da manhã, nunca interrompendo você | "monitore os anúncios da AMD", "o que você está monitorando?" |
| **Lembretes do sistema** | entregues ao Agendador de Tarefas: disparam mesmo com o JARVIS fechado, mesmo depois de reiniciar | ação `rappel_os_creer` (HUD, app iOS) |
| **Notas do Notion** | criar, ler, editar, apagar e buscar notas | token do Notion no `.env` |

### Opções desativadas por padrão

Algumas funções dependem de uma instalação específica: uma casa, uma escola, um serviço de
terceiros. Elas vêm **desligadas**, sem nenhum valor padrão. Enquanto você não as configurar,
não fazem nada e avisam.

| | | |
|---|---|---|
| **Horário escolar** | as aulas do Pronote copiadas para uma agenda Google separada, aulas canceladas marcadas e o horário liberado | Home Assistant com a integração Pronote, conta Google |
| **Revisão** | um quiz preparado na véspera de uma prova, e "me ajude a revisar" | o horário acima, Ollama |
| **Presença pela webcam** | uma foto enviada ao Discord quando alguém passa em frente à mesa | webcam, bot do Discord |
| **Mapa OSINT 3D** | abre o God's Eye View e o ShadowBroker a partir do JARVIS | esses dois programas, instalados à parte |
| **Delegação de código** | veja *Programar* acima | o agente de código que você preferir |

**Para ativar uma:** rode o instalador de novo (`installeur.py`), seção *Capacidades*
(Capacités), marque-a e preencha as configurações pedidas. As opções marcadas como "avançadas"
só aparecem no modo avançado. Cada configuração está descrita no `.env.example`.

## A interface

![A aba Agents lista as ferramentas de IA encontradas na máquina](docs/images/hud-agents.jpg)

<img src="docs/images/hud-mobile.jpg" alt="A interface em um celular" width="260" align="right">

Uma esfera 3D que reage à voz do JARVIS, o chat, o estado da máquina e um *Data center* com
abas: tarefas, habilidades, memória, agenda, mídia, dia a dia, casa, segurança,
configurações, controles, agentes e sistema. A aba **Agents** lista as ferramentas de IA
encontradas na máquina (assistentes de código, servidores MCP, motores de modelos) e quais
estão rodando.

Também funciona no celular, pelo navegador.

A interface é construída sobre o [openclaw-jarvis-ui](https://github.com/jincocodev/openclaw-jarvis-ui)
de **JincocoDev** (licença ISC, veja [`frontend/LICENSE`](frontend/LICENSE)), que por sua vez se
baseia no [Three.js Orb Visualizer](https://codepen.io/filipz/pen/yyyRgry) de **Filip Zrnzevic**.
Ela foi religada para falar diretamente com o JARVIS.

Ela precisa do **Node.js** (22 LTS recomendado, 20.19 no mínimo). Na primeira execução, o JARVIS
instala os pacotes sozinho (`npm install`, um ou dois minutos). Sem o Node.js, o JARVIS continua
funcionando por voz e pela barra rápida.

<br clear="right">

## Como falar com ele

| | |
|---|---|
| **Voz** | diga "Jarvis" e depois o pedido |
| **Ctrl+Alt+J** | uma barra aparece no centro da tela, a partir de qualquer aplicativo |
| **O HUD** | a interface completa — casa, e-mail, agenda, segurança, configurações |

Fechar a janela não o encerra: ele continua em segundo plano, com um ícone perto do relógio.
Para encerrá-lo: "quitter jarvis" (sair do jarvis), ou o menu desse ícone.

---

## Instalação

**Baixe o instalador na página de [versões](../../releases) e execute-o.** Ele encontra um
Python utilizável, baixa a versão mais recente, prepara tudo e abre o assistente de
configuração.

| Sistema | Arquivo | Estado |
|---|---|---|
| Windows 10 / 11 | `Installer-JARVIS.exe` | testado |
| Linux | `python3 amorceur/amorceur.py` | testado no Ubuntu 26.04 |
| macOS | `python3 amorceur/amorceur.py` | **nunca testado em um Mac de verdade** — veja [docs/macos.md](docs/macos.md) |

O instalador tem 11 MB: ele baixa o JARVIS em vez de embuti-lo. Assim você pode ler o código
antes de instalar — o que importa em um programa que controla o seu computador.

É preciso **Python 3.10 a 3.13**. O 3.14 é recente demais: várias dependências ainda não têm
versão compilada para ele.

### Manualmente, se preferir

```bash
git clone <url-do-repositorio> jarvis
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

Para saber a qualquer momento o que está faltando (`venv\Scripts\python.exe` no Windows,
`venv/bin/python3` no Linux/macOS):

```bash
config.py
```

Esse comando lista o que está disponível na sua máquina e **quais funções estão degradadas, e
por quê**.

O `requirements.txt` também inclui `discord.py`, `discord-ext-voice-recv` e `PyNaCl`, para o bot e
a voz do Discord. Eles só são usados se houver um token do Discord configurado.

### O reconhecimento de voz é separado

O `requirements-voix.txt` tem vários gigabytes (torch, Nemotron). Sem ele, o JARVIS funciona pelo
teclado, pela barra rápida e pelo HUD; só falta o ditado, e ele avisa.

## Configurações

Duas são necessárias, o resto é opcional. O `.env.example` explica para que serve cada uma e
onde obtê-la.

| | |
|---|---|
| `GEMINI_API_KEY` | o modelo principal. Sem ele, só as ferramentas locais respondem |
| `JARVIS_ACCESS_TOKEN` | protege o WebSocket, **que executa comandos do sistema** |

O segundo não é opcional na prática: sem ele, a autenticação fica desativada e qualquer
programa da máquina pode controlar o JARVIS. O instalador gera um longo e aleatório.

---

## Sistemas

**Windows 10 e 11** — desenvolvido e testado ali.

**Linux, macOS** — o JARVIS inicia, mas parte das funções não está disponível: as que dependem
do PowerShell, do `winget`, do registro ou da API do Windows. Elas **avisam** em vez de falhar no
meio, e o `config.py` as lista.

> O macOS nunca foi testado em uma máquina de verdade. O que está escrito aqui é o que o código
> prevê, não o que foi verificado.

## Privacidade

Nada sai da máquina além das chamadas que você configurar para os modelos, a previsão do tempo e
o Home Assistant — e, se você ativar, para o Discord, Slack, Notion e Google Agenda.

Conversas, configuração e e-mail ficam no computador. As chaves ficam no `.env`, que o `git`
ignora. O HUD esconde as chaves na tela: ele nunca recebe o valor delas, só se elas existem.

Ações irreversíveis — enviar um e-mail, desinstalar um programa — pedem autorização explícita e
**mostram exatamente o que vai sair** antes de agir.

## Segurança

- **WebSocket protegido.** Um token é gerado na instalação. Sem token, o JARVIS só escuta na
  máquina local.
- **Opções continuam desligadas.** Uma opção não marcada continua desativada, mesmo sem passar
  pelo instalador.
- **Confirmação antes das ações de risco.** Alarme, fechadura e controle remoto do PC pedem
  autorização explícita.
- **Delegação de código e lembretes.** O texto de uma tarefa ou de um lembrete nunca é executado
  como comando.

## Atualizações

Versão atual: **1.3.0**. As mudanças estão descritas em [NOTES-1.3.0.md](NOTES-1.3.0.md).

Ao iniciar, o JARVIS pergunta ao GitHub se existe uma versão mais recente e avisa. Ele nunca
instala nada sozinho. Preencha `JARVIS_DEPOT` no `.env` para ativar essa verificação; deixe vazio
para desativá-la.

---

## Contribuir

O projeto segue duas regras, que explicam a forma do código:

**Uma função indisponível avisa.** Ela não devolve uma lista vazia, não responde "feito", não
inventa um valor padrão. A maioria das correções deste repositório veio de ter quebrado essa
regra em algum lugar.

**O que é afirmado é verificado.** Os arquivos `_test_*.py` rodam diretamente, sem framework de
testes:

```bash
venv\Scripts\python.exe _test_machine.py
```

Eles não verificam que o código faz o que faz, e sim que ele não repete erros já cometidos — uma
frase que travava o programa, um nome escrito direto no código, uma comparação de versões em
ordem alfabética.

## Licença

A definir. A interface da pasta `frontend/` está sob a licença ISC (JincocoDev).
