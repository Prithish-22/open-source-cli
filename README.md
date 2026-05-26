# 🤖 Biju CLI (v2.0)
> **An Autonomous AI Software Engineer in Your Terminal**

Biju CLI is a premium, state-of-the-art Command Line Interface that transforms your terminal into an interactive AI workspace. Powered by NVIDIA’s high-performance NIM APIs and featuring dedicated, background-running AI agents, Biju CLI handles web research, code generation, testing, and git operations autonomously while you work.

---

## ✨ Features

* **🤖 Real Background Agents:** Spawn specialized, autonomous agents that run in the background. They have access to local file tools, web search, shell execution, and test suites.
  * 🔎 **Researcher:** Gathers web findings, summarizes topics, and provides direct sources.
  * 💻 **Coder:** Surgical code editor that writes and refines logic.
  * 🌿 **Git Agent:** Manages commits, reviews diffs, and pushes cleanly.
  * 📁 **File Agent:** Batch moves, renames, and manages directories.
  * 🧪 **Test Runner:** Runs your test suites, reads stack traces, fixes bugs, and loops until everything is green.
  * ⚡ **Shell Agent:** Autonomous shell execution and task runner.
* **🧠 Smart Task-Specific Models:** Biju automatically assigns the best-fitting, free NVIDIA-hosted models (e.g., *Dracarys 70B*, *Mistral Large 3*, *Llama 3.3 70B*) to each background agent, keeping you free of token limits and rate issues.
* **🏷️ Dynamic Model Selector:** Interactive `/model` command featuring human-readable descriptions of model strengths and purpose badges.
* **🎨 Premium Interactive UI:** Built using `rich` and `prompt_toolkit` to offer live token streaming, modern syntax highlighting, a beautiful status toolbar showing active background agents, and custom colors.

---

## 🚀 Installation

### 1. Prerequisites
To use Biju CLI, you need an NVIDIA API key (which is completely free).
* Get your key from [NVIDIA Build](https://build.nvidia.com/).

### 2. Install Globally (Like npm)
Since Biju is built on Python, you can install it globally using `pip`. 

#### Direct Local Installation (for development)
1. Clone the repository or navigate to your project directory.
2. Install it in editable/global mode:
   ```bash
   pip install -e .
   ```
3. You can now launch the CLI from anywhere in your terminal by simply typing:
   ```bash
   biju
   ```

#### Installing from PyPI (Once published)
Once published to PyPI, anyone in the world can install Biju CLI like a normal CLI:
```bash
pip install biju-cli
```

---

## 🛠️ Usage & Commands

Launch the interactive console by typing `biju`. Inside the console, you can use the following commands:

| Command | Description |
| :--- | :--- |
| `/setkey` | Save your NVIDIA NIM API Key securely |
| `/model` | Open the interactive model selector |
| `/agent <task>` | Spawn a dedicated, autonomous background agent to perform a task |
| `/agent status` | Check the current status of all running background agents |
| `/agent stop` | Safely terminate all active background agents |
| `/exit` or `/quit` | Exit the Biju console |

---

## 📦 How to Publish Biju CLI to PyPI

To make Biju installable globally via `pip install biju-cli` for anyone, follow these simple steps to publish your package:

### Step 1: Install Publishing Tools
Install `setuptools`, `wheel`, and `twine`:
```bash
pip install --upgrade setuptools wheel twine
```

### Step 2: Build the Package Distribution
From the root directory (where `setup.py` is), run:
```bash
python setup.py sdist bdist_wheel
```
This will create a `dist/` folder containing the package files (`.tar.gz` and `.whl`).

### Step 3: Register and Upload to PyPI
1. Create a free developer account on [PyPI (Python Package Index)](https://pypi.org/).
2. Create an API Token on your account settings page.
3. Upload your built package:
   ```bash
   python -m twine upload dist/*
   ```
4. Enter `__token__` as the username, and paste your PyPI API token as the password.

Once completed, anyone can install your CLI using `pip install biju-cli`!

---

## 📄 License
This project is licensed under the MIT License.
