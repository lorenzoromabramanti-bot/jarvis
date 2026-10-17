<div align="center">

# J.A.R.V.I.S

[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **中文** · [हिन्दी](README.hi.md) · [Português](README.pt-BR.md)

桌面语音助手。它会倾听、回答，并直接操作你的电脑：Home Assistant 智能家居、邮件、软件更新、VPN、
启动应用、读取屏幕内容。

[**官网**](https://lorenzoromabramanti-bot.github.io/jarvis/) · [**下载**](../../releases/latest)

![JARVIS 界面](docs/images/hud-desktop.jpg)

</div>

它在后台运行，没有窗口，可以在任何应用中用键盘唤出。

---

## 它能做什么

**回答。** 一组本地工具会先处理它们会做的事——时间、计算、单位换算、本机信息——只需
**两到六毫秒**，不调用任何模型。其余的交给模型。

**执行。** Home Assistant 的灯和插座、整理邮件并起草回复、`winget` 更新、VPN、卸载软件、控制
Spotify 和 Deezer。标签页、视频、窗口、锁屏和已打开的应用都直接控制，不经过模型。

**不知道就不说。** 这是设计选择，不是客套：一个什么都没做却说"已完成"的助手，比拒绝的助手更糟。
在智能家居中，被 Home Assistant 拒绝的操作会被报告为失败。

**没有 Gemini 也能继续。** 如果 Gemini 没有响应，它会切换到本地 Ollama 模型。模型列表从实际运行的
Ollama 服务器读取。

**远程与后台工作。**

| | | |
|---|---|---|
| **Discord** | 与 JARVIS 聊天并下达指令；敏感操作前会请求确认。它还可以加入语音频道 | `.env` 中的令牌和 ID |
| **通知** | 后台任务完成时发送 Discord 或 Slack 消息，安静时段除外 | `.env` 中的 webhook |
| **今晚** | "今晚做这件事"：任务会等待，报告随早间简报送达 | |
| **子任务** | 需要比较多项内容的请求会被拆分并行处理；超过 5 个子任务时会先询问 | |
| **直到截止** | 只要还有时间，它就会重读并改进自己的工作 | |

**写代码。** 它会把编程任务交给 Claude Code、Codex、OpenCode、Cursor Agent 或 OpenClaw，在你声明过的
项目中执行。没有它们时，它自己的文件代理会读取、搜索和修改项目，并被限制在项目文件夹内。

**可追溯。** 每次调用模型的费用和令牌数都清晰可见。按操作类型记录的信任日志：自主权是一次次操作
赢得的，而不是预先给予的。

**跟踪。** 可选功能，在安装时或设置中勾选——默认全部关闭：

| | | |
|---|---|---|
| **新增技能** | 查看 JARVIS 为自己编写的技能，停用某个技能而不删除，知道哪个坏了 | "技能列表"、"停用技能 *名称*" |
| **剪贴板** | 翻译、总结、解释或纠正刚复制的内容——纠正后的文本会放回剪贴板 | "翻译剪贴板"、"纠正剪贴板" |
| **话题关注** | 每天检查一次所选话题；新内容会在早间简报中告诉你，从不打断你 | "关注 AMD 的公告"、"你在关注什么？" |
| **系统提醒** | 交给任务计划程序：即使 JARVIS 关闭、甚至重启后也会触发 | 操作 `rappel_os_creer`（HUD、iOS 应用） |
| **Notion 笔记** | 创建、阅读、修改、删除和搜索笔记 | `.env` 中的 Notion 令牌 |

### 默认关闭的选项

有些功能依赖特定环境：一个家、一所学校、一项第三方服务。它们以**关闭**状态发布，没有任何默认值。
在你配置之前，它们什么都不做，并会明确说明。

| | | |
|---|---|---|
| **课程表** | Pronote 课程复制到单独的 Google 日历，取消的课程会被标记并空出时间段 | 安装了 Pronote 集成的 Home Assistant、Google 账号 |
| **复习** | 考试前一天准备好的小测验，以及"帮我复习" | 上面的课程表、Ollama |
| **摄像头在场检测** | 有人经过办公桌时把照片发到 Discord | 摄像头、Discord 机器人 |
| **3D OSINT 地图** | 从 JARVIS 打开 God's Eye View 和 ShadowBroker | 这两个程序，需单独安装 |
| **代码委托** | 见上面的*写代码* | 你选择的编程代理 |

**启用方法：** 重新运行安装程序（`installeur.py`），进入*能力*（Capacités）部分，勾选后填写它要求的
设置。标为"高级"的选项只在高级模式下显示。每项设置都在 `.env.example` 中有说明。

## 界面

<p align="center"><img src="docs/images/orbe.webp" alt="JARVIS 的球体动画" width="340"></p>

![Agents 标签页列出本机找到的 AI 工具](docs/images/hud-agents.jpg)

<img src="docs/images/hud-mobile.jpg" alt="手机上的界面" width="260" align="right">

一个随 JARVIS 声音变化的 3D 球体、聊天窗口、本机状态，以及带标签页的*数据中心*：任务、技能、记忆、
日程、媒体、日常、家居、安全、设置、控制、代理和系统。**Agents** 标签页会列出本机找到的 AI 工具
（编程助手、MCP 服务器、模型引擎）以及哪些正在运行。

在手机浏览器中同样可用。

界面基于 **JincocoDev** 的 [openclaw-jarvis-ui](https://github.com/jincocodev/openclaw-jarvis-ui)
（ISC 许可证，见 [`frontend/LICENSE`](frontend/LICENSE)），而它又基于 **Filip Zrnzevic** 的
[Three.js Orb Visualizer](https://codepen.io/filipz/pen/yyyRgry)。它已被重新接线，直接与 JARVIS 通信。

需要 **Node.js**（推荐 22 LTS，最低 20.19）。首次启动时，JARVIS 会自动安装界面所需的软件包
（`npm install`，一到两分钟）。没有 Node.js 时，JARVIS 仍可通过语音和快捷栏使用。

<br clear="right">

## 如何与它交流

| | |
|---|---|
| **语音** | 说"Jarvis"，然后说出请求 |
| **Ctrl+Alt+J** | 在任何应用中，屏幕中央都会出现一个输入栏 |
| **HUD** | 完整界面——家居、邮件、日历、安全、设置 |

关闭窗口不会让它停止：它会继续在后台运行，时钟旁有一个图标。要停止它：说"退出 jarvis"，或使用
该图标的菜单。

---

## 安装

**从[版本发布](../../releases)页面下载安装程序并运行。** 它会找到可用的 Python，获取最新版本，
准备好一切，然后打开配置向导。

| 系统 | 文件 | 状态 |
|---|---|---|
| Windows 10 / 11 | `Installer-JARVIS.exe` | 已验证 |
| Linux | `python3 amorceur/amorceur.py` | 已在 Ubuntu 26.04 上验证 |
| macOS | `python3 amorceur/amorceur.py` | **从未在真实的 Mac 上试过**——见 [docs/macos.md](docs/macos.md) |

安装程序只有 11 MB：它会下载 JARVIS，而不是把它打包在内。因此你可以在安装前阅读代码——对于一个
能控制你电脑的程序来说，这很重要。

需要 **Python 3.10 到 3.13**。3.14 太新：有几个依赖项还没有为它提供编译版本。

### 手动安装

```bash
git clone <仓库地址> jarvis
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

随时查看缺少什么（Windows 用 `venv\Scripts\python.exe`，Linux/macOS 用 `venv/bin/python3`）：

```bash
config.py
```

该命令会列出你机器上可用的内容，以及**哪些功能处于降级状态、原因是什么**。

`requirements.txt` 还包含 `discord.py`、`discord-ext-voice-recv` 和 `PyNaCl`，用于 Discord 机器人和语音。
只有设置了 Discord 令牌时才会用到。

### 语音识别是单独的

`requirements-voix.txt` 有好几 GB（torch、Nemotron）。没有它，JARVIS 仍可通过键盘、快捷栏和 HUD 使用；
只是缺少听写功能，它也会明确告诉你。

## 设置

两项是必需的，其余可选。`.env.example` 说明了每一项的用途和获取方式。

| | |
|---|---|
| `GEMINI_API_KEY` | 主模型。没有它，只有本地工具会回答 |
| `JARVIS_ACCESS_TOKEN` | 保护 WebSocket，**它会执行系统命令** |

第二项实际上并非可选：没有它，身份验证会被关闭，本机上的任何程序都能控制 JARVIS。安装程序会生成
一个很长的随机令牌。

---

## 系统

**Windows 10 和 11**——在这里开发和验证。

**Linux、macOS**——JARVIS 可以启动，但部分功能不可用：依赖 PowerShell、`winget`、注册表或 Windows API
的功能。它们会**明确说明**，而不是运行中途失败，`config.py` 会把它们列出来。

> macOS 从未在真实机器上试过。这里写的是代码的设计意图，而不是实际观察的结果。

## 隐私

除了你配置的对模型、天气和 Home Assistant 的调用之外——以及如果你启用的话，对 Discord、Slack、Notion
和 Google 日历的调用——没有任何数据会离开你的电脑。

对话、配置和邮件都保存在本地。密钥保存在 `.env` 中，`git` 会忽略它。HUD 在显示时会隐藏密钥：它从不
接收密钥的值，只知道密钥是否存在。

不可撤销的操作——发送邮件、卸载软件——需要明确同意，并在执行前**准确显示将要发出的内容**。

## 安全

- **受保护的 WebSocket。** 安装时会生成一个令牌。没有令牌时，JARVIS 只在本机上监听。
- **选项保持关闭。** 未勾选的选项会一直保持关闭，即使不经过安装程序也是如此。
- **高风险操作前需确认。** 警报、门锁和远程控制电脑都需要明确同意。
- **代码委托和提醒。** 任务或提醒的文本永远不会被当作命令执行。

## 更新

当前版本：**1.3.0**。更新内容见 [NOTES-1.3.0.md](NOTES-1.3.0.md)。

启动时，JARVIS 会询问 GitHub 是否有更新的版本并提示你。它从不自动安装任何东西。在 `.env` 中填写
`JARVIS_DEPOT` 以启用此检查；留空即可禁用。

---

## 参与贡献

本项目坚持两条规则，它们解释了代码的样子：

**不可用的功能会明确说明。** 它不会返回空列表，不会回答"已完成"，也不会编造默认值。本仓库的大多数
修复，都源于某处违反了这条规则。

**声称的内容都要验证。** `_test_*.py` 文件可直接运行，无需测试框架：

```bash
venv\Scripts\python.exe _test_machine.py
```

它们不是检查代码在做它正在做的事，而是检查它不会重犯已经犯过的错误——一句让程序卡死的话、写死在
代码里的名字、按字母顺序比较版本号。

## 许可证

待定。`frontend/` 文件夹中的界面采用 ISC 许可证（JincocoDev）。
