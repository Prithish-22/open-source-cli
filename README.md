# 🤖 Biju CLI + TUI (v2.0)
> **An Autonomous AI Software Engineer in Your Terminal**

Developed by **[Prithish Raj T](https://github.com/Prithish-22)** 🚀

[![GitHub stars](https://img.shields.io/github/stars/Prithish-22/open-source-cli?style=flat-square)](https://github.com/Prithish-22/open-source-cli/stargazers)
[![GitHub release](https://img.shields.io/github/v/release/Prithish-22/open-source-cli?style=flat-square)](https://github.com/Prithish-22/open-source-cli/releases)
[![npm version](https://img.shields.io/npm/v/biju-cli.svg?style=flat-square)](https://www.npmjs.com/package/biju-cli)
[![license](https://img.shields.io/github/license/Prithish-22/open-source-cli.svg?style=flat-square)](LICENSE)

---

Biju is a **100% free, open-source** autonomous AI terminal engineer. Plug in your own NVIDIA NIM API key (free tier) and get a full AI coding assistant right inside your terminal — no subscriptions, no paywalls.

---

## ✨ Two Interfaces, One CLI

### 1. 🖥️ Classic CLI — `biju`
The original `prompt_toolkit` + `rich` powered interface. Lightweight, fast, works in any terminal.

### 2. 🎨 TUI (Terminal UI) — `bijutui` *(New in v2.0!)*
A modern, full-screen **Textual**-powered terminal UI — inspired by Claude Code, Warp Terminal, and Gemini CLI.

```
┌─────────────────────────────────────────────┐
│  🟣 Biju           AI Output Area  (~65%)   │  ← Streaming markdown + syntax highlighting
│  Scrollable, rich markdown responses         │
├─────────────────────────────────────────────┤
│  ⚠ Permission Required                       │  ← Tool approval panel (~15%, hidden by default)
│  Tool: Shell Executor  Action: run pytest    │
│  [Y] Allow  [N] Deny  [A] Always Allow       │
├─────────────────────────────────────────────┤
│  Ask Biju anything...           Input (~10%) │  ← Enter=send, Shift+Enter=newline
├─────────────────────────────────────────────┤
│  /commands /help /clear /model   Llama 3.3  │  ← Always-visible status bar (~5%)
└─────────────────────────────────────────────┘
```

---

## 🚀 Quick Install (5 seconds)

### Via NPM *(easiest — works on any OS)*
```bash
npm install -g biju-cli
```

### Via Pip
```bash
pip install biju-cli
```

### From Source *(latest features)*
```bash
git clone https://github.com/Prithish-22/open-source-cli.git
cd open-source-cli
pip install -e .
```

Then launch:
```bash
biju       # Classic CLI
bijutui    # Full TUI (Textual)
```

---

## 🔄 How to Update

Biju checks for updates automatically on every startup and shows a notification if a newer version is available.

### Update via NPM
```bash
npm update -g biju-cli
```

### Update via Pip
```bash
pip install --upgrade biju-cli
```

### Update from Source *(recommended — gets the very latest)*
```bash
cd open-source-cli   # navigate to your cloned folder
git pull origin main
pip install -e .
```

> **💡 Tip:** Biju will tell you exactly which command to run when an update is detected at startup.

---

## 🔑 Get a Free NVIDIA NIM API Key

Biju runs on **NVIDIA NIM** — the free tier gives you **1,000 credits** (enough for thousands of AI interactions).

1. Go to **[build.nvidia.com](https://build.nvidia.com/)**
2. Sign up / Log in (free account)
3. Click any model → **"Get API Key"** → **"Generate Key"**
4. Copy your key (starts with `nvapi-`)
5. Set it in Biju:
   ```bash
   biju        # then type: /setkey
   ```
   Or edit `~/.biju_config.json` directly.

---

## 🎨 TUI Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in input |
| `Ctrl+K` | Open command palette |
| `Ctrl+L` | Clear chat |
| `Ctrl+M` | Switch AI model |
| `Ctrl+S` | Save session |
| `Ctrl+C` | Cancel AI generation |

---

## 🛠️ Slash Commands

Works in both `biju` (classic) and `bijutui` (TUI):

| Command | Description |
|---------|-------------|
| `/help` | Show help menu |
| `/model` | Interactive model selector (30+ models) |
| `/clear` | Clear the screen / chat |
| `/new` | Start a fresh conversation |
| `/save` | Save current session to disk |
| `/load` | Load a previous session |
| `/history` | Show message count and token estimate |
| `/autopilot` | Toggle autopilot (skip all approval prompts) |
| `/allow-all` | Enable full autonomy mode |
| `/init` | Create `biju-instructions.md` for this repo |
| `/setkey` | Add or update API keys |
| `/undo` | Restore the last file Biju modified |
| `/agent <task>` | Spawn a background AI agent *(Classic CLI only)* |
| `/exit` | Quit |

---

## 🤖 Background Agents *(Classic CLI)*

Spawn specialized agents that run in the background while you keep chatting:

```
❯ /agent write unit tests for setup.py
❯ /agent search the web and summarize Python 3.13 changes
❯ /agent clean up duplicate methods in main.py
```

| Agent | Best For |
|-------|----------|
| 🔎 Researcher | Web search, summarization |
| 💻 Coder | Code writing and refactoring |
| 🌿 Git Agent | Commits, diffs, PRs |
| 📁 File Agent | Batch file operations |
| 🧪 Test Runner | Run tests, fix failures in a loop |
| ⚡ Shell Agent | Autonomous shell task execution |

---

## 📦 Supported Models (30+ free on NVIDIA NIM)

| Category | Models |
|----------|--------|
| **Flagship** | Llama 3.3 70B, Mistral Large 3 675B, Llama 4 Maverick, DeepSeek V4 Flash |
| **Code & Reasoning** | Dracarys 70B, GPT-OSS 20B, Nemotron Omni Reasoning |
| **Fast & Lightweight** | Llama 3.1 8B, Llama 3.2 3B, Mistral 7B, Gemma 3N |
| **Vision** | Llama 3.2 90B Vision, Phi-4 Multimodal |
| **Third-party** | DeepSeek V3, Kimi (Moonshot) |

---

## 🗂️ Project Structure

```
open-source-cli/
├── biju/
│   └── bijucli.py          # Classic CLI (prompt_toolkit + rich)
├── tui/
│   ├── app.py              # Main Textual TUI application
│   ├── models/config.py    # Model catalog
│   ├── commands/registry.py # Slash command registry
│   ├── storage/session.py  # Session save/load
│   └── ui/
│       ├── output_panel.py    # AI output (streaming markdown)
│       ├── input_panel.py     # User input box
│       ├── permission_panel.py # Tool approval panel
│       ├── status_bar.py      # Always-visible status bar
│       └── popups.py          # Command palette, model selector
├── setup.py                # Package config (biju + bijutui entry points)
└── biju_tui.py             # Standalone TUI launcher
```

---

## 🗑️ Uninstall

```bash
# NPM
npm uninstall -g biju-cli

# Pip
pip uninstall biju-cli
```

---

## 📄 License

MIT — free to use, modify, and distribute.

---

<div align="center">
  <sub>Built with ❤️ by <a href="https://github.com/Prithish-22">Prithish Raj T</a> — contributions welcome!</sub>
</div>
