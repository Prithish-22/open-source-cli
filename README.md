# 🤖 Biju CLI (v2.0)
> **An Autonomous AI Software Engineer in Your Terminal**

Biju CLI is a **100% Free, Fully Open Source**, and premium Command Line Interface that transforms your terminal into an interactive AI workspace. Powered by NVIDIA’s high-performance NIM APIs and featuring dedicated background-running AI agents, Biju CLI handles web research, code generation, testing, and git operations autonomously while you work.

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

## 🔑 How to Get a Free NVIDIA NIM API Key (Step-by-Step)

Biju CLI utilizes the high-speed **NVIDIA NIM API** which provides access to state-of-the-art models (like Llama 3.3, Mistral Large, Qwen Coder, etc.) completely free of charge! Follow these steps to get your key in 2 minutes:

1. **Visit the NVIDIA Build Portal:**  
   Go to [NVIDIA Build](https://build.nvidia.com/).
2. **Sign Up/Log In:**  
   Click on the login icon in the top-right. Sign in with your existing NVIDIA account, or create a new one (it's entirely free and takes 1 minute).
3. **Select a Model:**  
   Click on any model (for example, `Llama 3.3 70B Instruct` or `Mistral Large 3`).
4. **Generate Your API Key:**  
   Under the selected model's interface, look for the **"Get API Key"** button. Click it, then click **"Generate Key"**.
5. **Copy Your Key:**  
   Copy the generated API key (it starts with `nvapi-`). Store it safely!

*Note: New accounts receive 1,000 free credits, which is more than enough for thousands of code generations and agent executions!*

---

## 🚀 Installation & Setup

### 1. Install Biju CLI Globally
Since Biju is built on Python, you can install it globally using `pip`. 

#### Direct Local Installation (for development/use)
1. Clone this repository or navigate to your downloaded project directory.
2. Install it in editable/global mode:
   ```bash
   pip install -e .
   ```
3. Launch the CLI from anywhere in your terminal:
   ```bash
   biju
   ```

#### Installing from PyPI (Once published)
```bash
pip install biju-cli
```

### 2. Configure Your API Key (One-time Setup)
Once the CLI starts, you can set your key directly inside the interactive console. It will be stored securely on your local machine so you don't have to enter it again!

1. Open your terminal and run:
   ```bash
   biju
   ```
2. In the interactive console, type `/setkey` followed by your key:
   ```text
   ❯ /setkey nvapi-YOUR_COPIED_NVIDIA_KEY_HERE
   ```
3. Press **Enter**. You are all set! Biju CLI is ready to work.

---

## 🛠️ Usage & Commands

Launch the interactive console by typing `biju`. Inside the console, you can use the following commands:

| Command | Description |
| :--- | :--- |
| `/setkey <key>` | Save your NVIDIA NIM API Key securely |
| `/model` | Open the interactive model selector |
| `/agent <task>` | Spawn a dedicated, autonomous background agent to perform a task |
| `/agent status` | Check the current status of all running background agents |
| `/agent stop` | Safely terminate all active background agents |
| `/exit` or `/quit` | Exit the Biju console |

### 💡 Example Agent Commands
* `❯ /agent write a comprehensive python unit test for setup.py`
* `❯ /agent search the web and summarize the latest updates in Python 3.12`
* `❯ /agent clean up duplicate methods in main.py`

---

## 📦 How to Publish Biju CLI to PyPI

To publish your package to PyPI so anyone in the world can run `pip install biju-cli`, run:

### Step 1: Install Publishing Tools
```bash
pip install --upgrade setuptools wheel twine
```

### Step 2: Build the Package Distribution
```bash
python setup.py sdist bdist_wheel
```

### Step 3: Upload to PyPI
1. Create a developer account on [PyPI](https://pypi.org/).
2. Create an API Token on your account settings page.
3. Upload the package:
   ```bash
   python -m twine upload dist/*
   ```
   *(Enter `__token__` as the username, and paste your PyPI API token as the password).*

---

## 📄 License
This project is licensed under the MIT License.
