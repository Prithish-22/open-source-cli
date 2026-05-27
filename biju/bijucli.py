import os
import sys
import json
import subprocess
import datetime
import re
import shutil
import platform
import threading
import time
import html
from collections import deque

# Shared tool modules — single source of truth for both CLI and TUI
from biju.tool_defs import TOOL_SCHEMAS, ALL_TOOL_NAMES, PERMISSION_REQUIRED, READ_ONLY_TOOLS
from biju.tools import (
    dispatch_tool, run_command_impl, read_file, write_file, edit_file,
    check_trusted_dir, is_destructive_command,
    build_repo_context, summarize_conversation, get_file_backups,
)
from openai import OpenAI, APITimeoutError
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML

# Update checker — add project root to sys.path so tui package is always findable
# regardless of how biju was launched (source / pip install -e . / global install)
try:
    _biju_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _biju_root not in sys.path:
        sys.path.insert(0, _biju_root)
    from tui.updater import check_for_updates, print_update_banner, run_update_classic
    _HAS_UPDATER = True
except Exception:
    _HAS_UPDATER = False

console = Console()
CONFIG_FILE = os.path.expanduser("~/.biju_config.json")
BACKUP_DIR  = os.path.expanduser("~/.biju_backups")

# --- GLOBAL STATES ---
DEFAULT_MODEL      = "meta/llama-3.3-70b-instruct"
MODEL              = DEFAULT_MODEL
FAST_FALLBACK_MODEL = "meta/llama-3.1-8b-instruct"
AUTOPILOT          = False
ALLOW_ALL          = False   # /allow-all — skip all approval prompts
MAX_TOOL_CALLS     = 10          # safety limiter per turn
_file_backups = get_file_backups()  # shared with biju.tools for /undo
cancel_flag   = threading.Event()   # set to cancel an in-flight AI request
prompt_queue: deque[str] = deque()  # queued prompts to auto-process
RUNNING_AGENTS: dict[str, object] = {}  # name -> Agent object

# --- CATEGORIZED MODEL LIST (verified working on NVIDIA free API) ---
AGENT_MODELS_CATEGORIZED = {
    "Flagship": [
        ("meta/llama-3.3-70b-instruct",                "Llama 3.3 70B — Best overall for coding and logic."),
        ("mistralai/mistral-large-3-675b-instruct-2512", "Mistral Large 3 675B — Top-tier from Mistral."),
        ("nvidia/llama-3.3-nemotron-super-49b-v1.5",    "Nemotron Super 49B v1.5 — Great balance of speed and smarts."),
        ("nvidia/nemotron-3-super-120b-a12b",           "Nemotron 3 Super 120B — NVIDIA's large MoE model."),
        ("mistralai/mistral-nemotron",                  "Mistral Nemotron — NVIDIA-tuned Mistral."),
        ("meta/llama-4-maverick-17b-128e-instruct",     "Llama 4 Maverick 17B MoE — Latest Meta model."),
        ("openai/gpt-oss-120b",                         "GPT-OSS 120B — OpenAI's open-source on NVIDIA."),
    ],
    "Code and Reasoning": [
        ("abacusai/dracarys-llama-3.1-70b-instruct",    "Dracarys Llama 3.1 — Exceptional at coding."),
        ("openai/gpt-oss-20b",                          "GPT-OSS 20B — Compact OpenAI, good for code."),
        ("stepfun-ai/step-3.5-flash",                   "Step 3.5 Flash — StepFun's fast reasoning model."),
    ],
    "Fast and Lightweight": [
        ("meta/llama-3.1-8b-instruct",                  "Llama 3.1 8B — Super fast for quick tasks."),
        ("meta/llama-3.2-3b-instruct",                  "Llama 3.2 3B — Ultra-lightweight, instant responses."),
        ("meta/llama-3.2-1b-instruct",                  "Llama 3.2 1B — Smallest Llama, fastest possible."),
        ("mistralai/mistral-7b-instruct-v0.3",          "Mistral 7B v0.3 — Fast and reliable."),
        ("mistralai/ministral-14b-instruct-2512",       "Ministral 14B — Mistral's compact model."),
        ("mistralai/mistral-small-4-119b-2603",         "Mistral Small 4 119B — Compact but powerful."),
        ("nvidia/nemotron-mini-4b-instruct",            "Nemotron Mini 4B — NVIDIA's tiniest model."),
        ("nvidia/nemotron-3-nano-30b-a3b",              "Nemotron 3 Nano 30B — Small NVIDIA MoE."),
        ("nvidia/nvidia-nemotron-nano-9b-v2",           "Nemotron Nano 9B v2 — Latest compact NVIDIA."),
        ("google/gemma-3n-e4b-it",                      "Gemma 3N E4B — Google's nano model."),
        ("google/gemma-3n-e2b-it",                      "Gemma 3N E2B — Tiniest Google model."),
        ("google/gemma-2-2b-it",                        "Gemma 2 2B — Ultra-light Google model."),
        ("upstage/solar-10.7b-instruct",                "Solar 10.7B — Korean-made, strong for size."),
        ("stockmark/stockmark-2-100b-instruct",         "Stockmark 2 100B — Japanese enterprise model."),
    ],
    "Third-Party APIs": [
        ("deepseek-chat",    "DeepSeek V3 (DeepSeek API). Brilliant at coding and math."),
        ("moonshot-v1-8k",   "Kimi AI (Moonshot API). Great context window."),
    ],
    "Vision and Multimodal": [
        ("meta/llama-3.2-90b-vision-instruct",          "Llama 3.2 90B Vision — Large vision model."),
        ("meta/llama-3.2-11b-vision-instruct",          "Llama 3.2 11B Vision — Compact vision model."),
    ],
}

# --- MODEL DISPLAY LABELS (short human-readable names) ---
MODEL_LABELS: dict[str, str] = {
    # Flagship
    "meta/llama-3.3-70b-instruct":                 "Llama 3.3 70B",
    "mistralai/mistral-large-3-675b-instruct-2512": "Mistral Large 3",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5":     "Nemotron Super 49B",
    "nvidia/nemotron-3-super-120b-a12b":            "Nemotron 3 Super 120B",
    "mistralai/mistral-nemotron":                   "Mistral Nemotron",
    "meta/llama-4-maverick-17b-128e-instruct":      "Llama 4 Maverick",
    "openai/gpt-oss-120b":                          "GPT-OSS 120B",
    # Code & Reasoning
    "abacusai/dracarys-llama-3.1-70b-instruct":     "Dracarys 70B",
    "openai/gpt-oss-20b":                           "GPT-OSS 20B",
    "stepfun-ai/step-3.5-flash":                    "Step 3.5 Flash",
    # Fast & Lightweight
    "meta/llama-3.1-8b-instruct":                   "Llama 3.1 8B",
    "meta/llama-3.2-3b-instruct":                   "Llama 3.2 3B",
    "meta/llama-3.2-1b-instruct":                   "Llama 3.2 1B",
    "mistralai/mistral-7b-instruct-v0.3":           "Mistral 7B",
    "mistralai/ministral-14b-instruct-2512":        "Ministral 14B",
    "mistralai/mistral-small-4-119b-2603":          "Mistral Small 4",
    "nvidia/nemotron-mini-4b-instruct":             "Nemotron Mini 4B",
    "nvidia/nemotron-3-nano-30b-a3b":               "Nemotron Nano 30B",
    "nvidia/nvidia-nemotron-nano-9b-v2":            "Nemotron Nano 9B",
    "google/gemma-3n-e4b-it":                       "Gemma 3N E4B",
    "google/gemma-3n-e2b-it":                       "Gemma 3N E2B",
    "google/gemma-2-2b-it":                         "Gemma 2 2B",
    "upstage/solar-10.7b-instruct":                 "Solar 10.7B",
    "stockmark/stockmark-2-100b-instruct":          "Stockmark 2 100B",
    # Third-party
    "deepseek-chat":                                "DeepSeek V3",
    "moonshot-v1-8k":                               "Kimi (8K)",
    # Vision
    "meta/llama-3.2-90b-vision-instruct":           "Llama 3.2 90B Vision",
    "meta/llama-3.2-11b-vision-instruct":           "Llama 3.2 11B Vision",
}

def get_model_label(model_id: str) -> str:
    """Return short human-readable label for a model ID."""
    return MODEL_LABELS.get(model_id, model_id.split("/")[-1])

# ── Best NVIDIA models for web searching (ordered by capability/recency) ───────
# Auto-selected for the Web Search sub-agent — always picks the most up-to-date
# available model from the list. Never uses third-party APIs.
_WEB_SEARCH_MODEL_PRIORITY = [
    "meta/llama-4-maverick-17b-128e-instruct",    # Latest Meta architecture
    "openai/gpt-oss-120b",                         # Largest OSS model on NVIDIA
    "nvidia/nemotron-3-super-120b-a12b",           # Large NVIDIA MoE
    "mistralai/mistral-large-3-675b-instruct-2512",# Top Mistral
    "meta/llama-3.3-70b-instruct",                 # Reliable flagship fallback
]

def get_web_search_model() -> str:
    """
    Auto-select the best available NVIDIA model for the Web Search sub-agent.
    Picks the highest-priority model present in the current model list.
    This ensures the web agent always uses the most up-to-date model
    regardless of what year or version is added to the list.
    """
    all_ids = []
    for models in AGENT_MODELS_CATEGORIZED.values():
        all_ids.extend(m for m, _ in models)
    for model_id in _WEB_SEARCH_MODEL_PRIORITY:
        if model_id in all_ids:
            return model_id
    # Ultimate fallback: first flagship model
    flagship = AGENT_MODELS_CATEGORIZED.get("Flagship", [])
    return flagship[0][0] if flagship else DEFAULT_MODEL

# --- ALL SLASH COMMANDS ---
COMMANDS = {
    "/add-dir":    "Add a trusted directory Biju can freely read/write",
    "/agent":      "Spawn a background agent (Researcher/Coder/Git/File/Test/Shell/Repo-Scout/Patch-Editor/Reviewer/Security)",
    "/allow-all":  "Enable full autonomy — autopilot ON + skip all approvals",
    "/ask":        "Ask a quick side question without adding to conversation history",
    "/autopilot":  "Toggle autopilot mode for terminal commands",
    "/changelog":  "Display changelog for CLI versions",
    "/clear":      "Clear the terminal screen",
    "/config":     "Reset and delete your saved API keys",
    "/help":       "Show the help menu with all commands and available tools",
    "/history":    "Show current session message count and token estimate",
    "/init":       "Initialize Biju instructions for this repository",
    "/model":      "Interactive menu to choose a different AI model",
    "/setkey":     "Add or change your API keys directly in the chat",
    "/undo":       "Restore the last file that Biju modified",
    "/update":     "Update Biju to the latest version and restart automatically",
    "/queue":      "Manage prompt queue — add, list, clear, or run next",
    "/exit":       "Quit the CLI",
    "/quit":       "Quit the CLI",
}

# --- CUSTOM KEY BINDINGS ---
kb = KeyBindings()

@kb.add("escape")
def _(event):
    event.app.current_buffer.text = ""

# --- CUSTOM AUTOCOMPLETE ---
class SlashCommandCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd, desc in COMMANDS.items():
                if cmd.startswith(text.lower()):
                    yield Completion(
                        cmd, start_position=-len(text),
                        display=cmd, display_meta=desc,
                    )

# --- UI LAYOUT FUNCTIONS ---
def get_prompt_message():
    from prompt_toolkit.formatted_text import FormattedText
    cwd  = os.getcwd()
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        cwd = cwd.replace(home, "~", 1)
    width = shutil.get_terminal_size().columns
    line  = "─" * width
    return FormattedText([
        ("ansicyan",    cwd),
        ("",           "\n"),
        ("ansigray",    line),
        ("",           "\n"),
        ("bold ansimagenta", "❯"),
        ("",           " "),
    ])

def get_bottom_toolbar():
    from prompt_toolkit.formatted_text import FormattedText
    width    = shutil.get_terminal_size().columns
    ap_badge = " ⚡AUTOPILOT" if AUTOPILOT else ""
    q_badge  = f" [{len(prompt_queue)} queued]" if prompt_queue else ""
    ag_badge = f" [{len(RUNNING_AGENTS)} agent(s)]" if RUNNING_AGENTS else ""
    left     = f"/ commands · Esc cancel{ap_badge}{q_badge}{ag_badge}"
    right    = get_model_label(MODEL)
    spaces   = max(1, width - len(left) - len(right))
    line     = "─" * width
    return FormattedText([
        ("ansigray",  line),
        ("",          "\n"),
        ("ansigray",  left),
        ("",          " " * spaces),
        ("ansicyan",  right),
    ])

ui_style = Style.from_dict({
    "completion-menu.completion":         "bg:#1a1a2e #e0e0e0",
    "completion-menu.completion.current": "bg:#16213e #ffffff bold",
    "completion-menu.meta.completion":    "bg:#1a1a2e #888888",
    "completion-menu.meta.completion.current": "bg:#16213e #aaaaaa",
    "bottom-toolbar": "bg:#0f0f23 #666666",
    "prompt":         "bold",
})

# --- CONFIGURATION & ROUTING ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def ensure_keys():
    config = load_config()
    if not any(k in config for k in ["NVIDIA_API_KEY", "DEEPSEEK_API_KEY", "KIMI_API_KEY"]):
        console.print(Panel(
            "[bold cyan]Welcome to Biju CLI![/bold cyan]\n[dim]Developed by Prithish — your autonomous terminal engineer[/dim]",
            border_style="cyan", expand=False, padding=(1, 2),
        ))
        console.print("[bold yellow]Please enter at least one API Key to continue.[/bold yellow]\n")

        nv = input("  NVIDIA API Key   (Enter to skip): ").strip()
        if nv: config["NVIDIA_API_KEY"] = nv

        ds = input("  DeepSeek API Key (Enter to skip): ").strip()
        if ds: config["DEEPSEEK_API_KEY"] = ds

        km = input("  Kimi API Key     (Enter to skip): ").strip()
        if km: config["KIMI_API_KEY"] = km

        if not any(config.values()):
            console.print("\n[bold red]✗ You must provide at least one key to use Biju![/bold red]")
            sys.exit(1)

        save_config(config)
        console.print("\n[bold green]✓ API Keys saved successfully![/bold green]\n")

def get_api_client():
    config = load_config()
    # Third-party APIs: only exact model IDs (not NVIDIA-hosted variants)
    if MODEL in ("moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"):
        api_key  = config.get("KIMI_API_KEY")
        base_url = "https://api.moonshot.cn/v1"
        provider = "Kimi (Moonshot)"
    elif MODEL in ("deepseek-chat", "deepseek-reasoner"):
        api_key  = config.get("DEEPSEEK_API_KEY")
        base_url = "https://api.deepseek.com/v1"
        provider = "DeepSeek"
    else:
        # All other models (including deepseek-ai/*, moonshotai/*) are NVIDIA-hosted
        api_key  = config.get("NVIDIA_API_KEY")
        base_url = "https://integrate.api.nvidia.com/v1"
        provider = "NVIDIA"

    if not api_key:
        raise ValueError(f"No API key found for {provider}. Run /setkey to add it.")
    return OpenAI(base_url=base_url, api_key=api_key)

# --- INTERACTIVE MODEL SELECTOR TUI ---
def interactive_model_selector(current_model):
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout, Window, FormattedTextControl

    categories = list(AGENT_MODELS_CATEGORIZED.keys())
    cat_idx, mod_idx = 0, 0
    for i, cat in enumerate(categories):
        for j, (m, _) in enumerate(AGENT_MODELS_CATEGORIZED[cat]):
            if m == current_model:
                cat_idx, mod_idx = i, j

    state     = {"cat_idx": cat_idx, "mod_idx": mod_idx}
    kb_menu   = KeyBindings()

    @kb_menu.add("up")
    def _(event):
        state["mod_idx"] = max(0, state["mod_idx"] - 1)

    @kb_menu.add("down")
    def _(event):
        cat = categories[state["cat_idx"]]
        state["mod_idx"] = min(len(AGENT_MODELS_CATEGORIZED[cat]) - 1, state["mod_idx"] + 1)

    @kb_menu.add("tab")
    @kb_menu.add("right")
    def _(event):
        state["cat_idx"] = (state["cat_idx"] + 1) % len(categories)
        state["mod_idx"] = 0

    @kb_menu.add("s-tab")
    @kb_menu.add("left")
    def _(event):
        state["cat_idx"] = (state["cat_idx"] - 1) % len(categories)
        state["mod_idx"] = 0

    @kb_menu.add("enter")
    def _(event):
        cat      = categories[state["cat_idx"]]
        selected = AGENT_MODELS_CATEGORIZED[cat][state["mod_idx"]][0]
        event.app.exit(result=selected)

    @kb_menu.add("escape")
    @kb_menu.add("c-c")
    def _(event):
        event.app.exit(result=None)

    def get_text():
        lines = []
        lines.append("\n<ansicyan><b>╔══ SELECT AI MODEL ══╗</b></ansicyan>")
        lines.append("<ansigray>  [Tab/←/→] Switch category   [↑/↓] Select   [Enter] Confirm   [Esc] Cancel</ansigray>\n")

        # Tabs
        tabs = []
        for i, cat in enumerate(categories):
            safe_cat = html.escape(cat)
            if i == state["cat_idx"]:
                tabs.append(f"<ansibgblue><ansiwhite><b> {safe_cat} </b></ansiwhite></ansibgblue>")
            else:
                tabs.append(f"<ansigray> {safe_cat} </ansigray>")
        lines.append("  " + "  │  ".join(tabs) + "\n")

        # Models
        cat    = categories[state["cat_idx"]]
        models = AGENT_MODELS_CATEGORIZED[cat]
        for i, (m, desc) in enumerate(models):
            is_selected = i == state["mod_idx"]
            is_active   = m == current_model
            safe_desc   = html.escape(desc)
            label       = html.escape(get_model_label(m))
            safe_id     = html.escape(m)
            cursor      = "<ansigreen><b>❯</b></ansigreen>" if is_selected else " "
            label_tag   = f"<ansigreen><b>{label}</b></ansigreen>" if is_selected else f"<ansiwhite><b>{label}</b></ansiwhite>"
            id_tag      = f"<ansigray>{safe_id}</ansigray>"
            active_tag  = "  <ansiyellow>(active)</ansiyellow>" if is_active else ""
            lines.append(f"  {cursor} {label_tag}{active_tag}")
            lines.append(f"       {id_tag}")
            lines.append(f"       <ansigray>↳ {safe_desc}</ansigray>")

        lines.append("")
        return HTML("\n".join(lines))

    app = Application(
        layout=Layout(Window(content=FormattedTextControl(get_text))),
        key_bindings=kb_menu,
        full_screen=False,
    )
    return app.run()

# --- TOOLS SCHEMA (imported from shared module) ---
tools = TOOL_SCHEMAS

# --- TOOL IMPLEMENTATIONS (imported from biju.tools) ---
# run_command wrapper — adds CLI-specific approval UI on top of shared impl
def run_command(cmd: str) -> str:
    """Execute a shell command with approval, trusted-dir, and destructive-cmd checks."""
    global AUTOPILOT, ALLOW_ALL

    # ── Destructive command safety (Feature 8) ────────────────────────────
    is_destr, destr_desc = is_destructive_command(cmd)
    if is_destr and not ALLOW_ALL:
        console.print(Panel(
            f"[bold red]⚠ DESTRUCTIVE COMMAND DETECTED[/bold red]\n\n"
            f"  [bold white]{cmd}[/bold white]\n\n"
            f"  [yellow]Risk: {destr_desc}[/yellow]",
            border_style="red", title="[red]🛑 Dangerous Operation[/red]", padding=(0, 1),
        ))
        approval = input("  This is destructive. Are you sure? [y/N]: ").strip().lower()
        if approval != "y":
            return "Destructive command denied by user."
    elif not AUTOPILOT and not ALLOW_ALL:
        console.print(Panel(
            f"[bold yellow]Biju wants to run:[/bold yellow]\n\n  [bold white]{cmd}[/bold white]",
            border_style="yellow", title="[yellow]⚠ Command Approval[/yellow]", padding=(0, 1),
        ))
        approval = input("  Allow? [y/N]: ").strip().lower()
        if approval != "y":
            return "Command denied by user."
    else:
        console.print(Panel(
            f"[bold white]{cmd}[/bold white]",
            border_style="magenta", title="[magenta]⚡ Autopilot[/magenta]", padding=(0, 1),
        ))

    return run_command_impl(cmd)

# write_file wrapper — adds trusted-dir check
def cli_write_file(filepath: str, content: str) -> str:
    """Write file with trusted-dir enforcement."""
    if not ALLOW_ALL:
        config = load_config()
        trusted = config.get("trusted_dirs", [])
        allowed, reason = check_trusted_dir(filepath, trusted, os.getcwd(), ALLOW_ALL)
        if not allowed:
            console.print(Panel(
                f"[bold red]🚫 Write blocked:[/bold red] {reason}",
                border_style="red", expand=False,
            ))
            return f"Write denied: {reason}"
    return write_file(filepath, content)

# edit_file wrapper — adds trusted-dir check
def cli_edit_file(filepath: str, old_text: str, new_text: str) -> str:
    """Edit file with trusted-dir enforcement."""
    if not ALLOW_ALL:
        config = load_config()
        trusted = config.get("trusted_dirs", [])
        allowed, reason = check_trusted_dir(filepath, trusted, os.getcwd(), ALLOW_ALL)
        if not allowed:
            console.print(Panel(
                f"[bold red]🚫 Edit blocked:[/bold red] {reason}",
                border_style="red", expand=False,
            ))
            return f"Edit denied: {reason}"
    return edit_file(filepath, old_text, new_text)

# --- THINKING BLOCK RENDERER ---
def render_thinking(thoughts: str):
    console.print(Panel(
        f"[dim italic]{thoughts.strip()}[/dim italic]",
        title="[dim]🧠 Thinking[/dim]",
        border_style="dim",
        padding=(0, 1),
        expand=False,
    ))

# --- TOOL CALL DISPLAY ---
def render_tool_call(func_name: str, args: dict):
    icons = {
        "run_command":     "⚙",
        "read_file":       "📄",
        "write_file":      "✏",
        "edit_file":       "🔧",
        "list_dir":        "📂",
        "search_in_files": "🔍",
        "read_file_range": "📄",
        "git_status":      "🌿",
        "git_diff":        "🌿",
        "git_log":         "🌿",
    }
    colors = {
        "run_command":     "yellow",
        "read_file":       "blue",
        "write_file":      "green",
        "edit_file":       "green",
        "list_dir":        "cyan",
        "search_in_files": "cyan",
        "read_file_range": "blue",
        "git_status":      "bright_green",
        "git_diff":        "bright_green",
        "git_log":         "bright_green",
    }
    icon  = icons.get(func_name, "🔧")
    color = colors.get(func_name, "white")
    label = func_name.replace("_", " ").title()

    detail = ""
    if func_name == "run_command":
        detail = args.get("command", "")
    elif func_name in ("read_file", "write_file", "edit_file", "read_file_range"):
        detail = args.get("filepath", "")
    elif func_name == "list_dir":
        detail = args.get("path", ".")
    elif func_name == "search_in_files":
        detail = args.get("query", "")

    console.print(
        f"  [{color}]{icon} {label}[/{color}] [dim]{detail}[/dim]"
    )

# --- HELPER: strip all thinking patterns ---
def _strip_thinking(text: str) -> str:
    """Remove thinking content in all formats models might use."""
    # 1. Strip proper <thinking>...</thinking> tags
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
    # 2. Strip "Thinking..." / "Thinking –" / "Thinking:" preambles (plain text, no tags)
    #    These are full paragraphs that start with "Thinking" and end at a double-newline
    text = re.sub(
        r"^(?:Thinking|Let me think|I need to think)[\s.…:–—-]*.*?(?=\n\n|\Z)",
        "", text, flags=re.DOTALL | re.IGNORECASE
    )
    # 3. Strip inline "Thinking... <sentence>" lines anywhere in the text
    text = re.sub(
        r"\n(?:Thinking|Let me think)[\s.…:–—-]+[^\n]+",
        "", text, flags=re.IGNORECASE
    )
    return text.strip()


# --- HELPER: detect tool calls embedded as text ---
KNOWN_TOOLS = ALL_TOOL_NAMES

def _try_parse_text_tool_call(text: str) -> dict | None:
    """
    Detect when the model outputs a tool call as raw JSON text.
    Returns {"name": str, "arguments": dict} if detected, else None.
    """
    # Strip markdown code fences if present
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    stripped = stripped.strip()

    # Try to find a JSON object in the text
    # Look for the outermost { ... }
    start = stripped.find("{")
    end   = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    json_str = stripped[start:end + 1]
    try:
        obj = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    if not isinstance(obj, dict):
        return None

    # Format 1: {"name": "run_command", "parameters": {"command": "..."}}
    if obj.get("name") in KNOWN_TOOLS:
        args = obj.get("parameters") or obj.get("arguments") or {}
        return {"name": obj["name"], "arguments": args}

    # Format 2: {"function": {"name": "...", "arguments": {...}}}
    if "function" in obj and isinstance(obj["function"], dict):
        fn = obj["function"]
        if fn.get("name") in KNOWN_TOOLS:
            args = fn.get("arguments") or fn.get("parameters") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            return {"name": fn["name"], "arguments": args}

    # Format 3: {"tool_calls": [{"function": {"name": "...", ...}}]}
    if "tool_calls" in obj and isinstance(obj["tool_calls"], list):
        for tc in obj["tool_calls"]:
            fn = tc.get("function", {})
            if fn.get("name") in KNOWN_TOOLS:
                args = fn.get("arguments") or fn.get("parameters") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                return {"name": fn["name"], "arguments": args}

    return None


# --- AGENT LOOP ---
def chat_with_agent(user_input: str, messages: list) -> str | None:
    global MODEL
    messages.append({"role": "user", "content": user_input})

    try:
        client = get_api_client()
    except ValueError as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {e}\n")
        messages.pop()
        return None

    tool_call_count = 0

    while True:
        if cancel_flag.is_set():
            return None

        if tool_call_count >= MAX_TOOL_CALLS:
            console.print(Panel(
                f"[bold yellow]Biju reached the maximum of {MAX_TOOL_CALLS} tool calls in one turn.\n"
                "Stopping to check in with you.[/bold yellow]",
                border_style="yellow", title="[yellow]⚠ Tool Call Limit Reached[/yellow]",
            ))
            return None

        model_label = MODEL.split("/")[-1]

        # ── Conversation summarization (Feature 6) ────────────────────────
        summarized = summarize_conversation(messages)
        api_messages = summarized

        # ── Open streaming request ────────────────────────────────────────
        try:
            stream_iter = client.chat.completions.create(
                model=MODEL,
                messages=api_messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.1,
                timeout=30.0,
                stream=True,
            )
        except APITimeoutError:
            console.print(f"\n[bold yellow]⚠ {model_label} timed out. Switching to fallback...[/bold yellow]")
            MODEL = FAST_FALLBACK_MODEL
            return chat_with_agent(user_input, messages[:-1])
        except KeyboardInterrupt:
            console.print("\n[bold red]🚫 Request cancelled.[/bold red]")
            return None
        except Exception as e:
            err = str(e).lower()
            if "404" in err or "not found" in err:
                console.print(f"\n[bold red]✗ Model '{MODEL}' not found.[/bold red]")
                console.print(f"[bold yellow]↩ Recovering to default...[/bold yellow]")
                MODEL = DEFAULT_MODEL
            else:
                console.print(f"\n[bold red]✗ API Error:[/bold red] {e}")
            return None

        # ── Stream tokens live using Rich Live ─────────────────────────────
        full_content: str = ""
        tool_calls_acc: dict[int, dict] = {}
        has_tool_calls = False
        first_token = True

        try:
            with Live("", console=console, refresh_per_second=10, transient=True) as live:
                for chunk in stream_iter:
                    if cancel_flag.is_set():
                        return None
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if delta.content:
                        full_content += delta.content
                        # Show live-updating markdown (only visible text)
                        visible = _strip_thinking(full_content)
                        if visible:
                            live.update(Markdown(visible))

                    if delta.tool_calls:
                        has_tool_calls = True
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": "", "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.id:
                                tool_calls_acc[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_acc[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments
        except Exception:
            pass  # stream ended or network error

        # ── Extract and optionally display thinking ───────────────────────
        thinking_content = ""
        if "<thinking>" in full_content:
            m = re.search(r"<thinking>(.*?)</thinking>", full_content, re.DOTALL)
            if m:
                thinking_content = m.group(1).strip()
        if thinking_content:
            render_thinking(thinking_content)

        # ── Clean all thinking patterns from visible content ──────────────
        clean_content = _strip_thinking(full_content)

        # ── Detect tool calls embedded as raw JSON text ───────────────────
        # Llama models sometimes output tool calls as text instead of using
        # the structured tool_calls field.  Detect and convert them.
        if not has_tool_calls and clean_content:
            text_tool = _try_parse_text_tool_call(clean_content)
            if text_tool:
                has_tool_calls = True
                tc_id = f"text_call_{tool_call_count}"
                tool_calls_acc[0] = {
                    "id": tc_id, "type": "function",
                    "function": {
                        "name": text_tool["name"],
                        "arguments": json.dumps(text_tool["arguments"]),
                    },
                }
                clean_content = ""   # don't display the JSON as text

        # ── Render response as Rich Markdown ──────────────────────────────
        if not has_tool_calls and clean_content:
            console.print()
            console.print(Rule(characters="─", style="dim"))
            console.print("[bold purple]🟣 Biju[/bold purple]")
            console.print(Markdown(clean_content))
            console.print(Rule(characters="─", style="dim"))

        # ── Save to message history & handle tool calls ───────────────────
        if has_tool_calls:
            tool_calls_list = [
                {
                    "id": tool_calls_acc[i]["id"],
                    "type": "function",
                    "function": {
                        "name":      tool_calls_acc[i]["function"]["name"],
                        "arguments": tool_calls_acc[i]["function"]["arguments"],
                    },
                }
                for i in sorted(tool_calls_acc)
            ]
            messages.append({
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": tool_calls_list,
            })
            console.print()
            for tc in tool_calls_list:
                tool_call_count += 1
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                render_tool_call(func_name, args)
                # Dispatch tool — use CLI wrappers for gated tools
                if func_name == "run_command":
                    result = run_command(args.get("command", ""))
                elif func_name == "write_file":
                    result = cli_write_file(args.get("filepath", ""), args.get("content", ""))
                elif func_name == "edit_file":
                    result = cli_edit_file(
                        args.get("filepath", ""),
                        args.get("old_text", ""),
                        args.get("new_text", ""),
                    )
                else:
                    # All other tools (read_file, list_dir, search_in_files,
                    # read_file_range, git_status, git_diff, git_log) use shared dispatch
                    result = dispatch_tool(func_name, args)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            console.print()
            # loop for next AI turn
        else:
            messages.append({"role": "assistant", "content": full_content or ""})
            return clean_content

# --- ESC-CANCELLABLE RUNNER ---
def run_with_esc_cancel(user_input: str, messages: list) -> str | None:
    """
    Runs chat_with_agent in a background thread.
    Polls for ESC key (Windows: msvcrt) in the main thread to cancel.
    """
    cancel_flag.clear()
    result_holder: dict = {}

    def _worker():
        result_holder["reply"] = chat_with_agent(user_input, messages)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    # Use platform-appropriate non-blocking key polling
    try:
        import msvcrt  # Windows only
        _use_msvcrt = True
    except ImportError:
        _use_msvcrt = False

    while thread.is_alive():
        if _use_msvcrt:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ord(ch) == 27:  # ESC
                    cancel_flag.set()
                    console.print("\n[bold red]🚫 Request cancelled — press Enter to continue.[/bold red]\n")
                    thread.join(timeout=3)  # give thread a moment to clean up
                    return None
        time.sleep(0.05)

    thread.join()
    return result_holder.get("reply")

# --- STARTUP SCREEN ---
def print_startup_screen():
    os.system("cls" if os.name == "nt" else "clear")
    width = shutil.get_terminal_size().columns

    console.print()
    console.print(Rule(style="cyan dim"))
    console.print(
        "  [bold cyan]██████╗ ██╗     ██╗██╗   ██╗[/bold cyan]",
        justify="left",
    )
    console.print(
        "  [bold cyan]██╔══██╗██║     ██║██║   ██║[/bold cyan]",
        justify="left",
    )
    console.print(
        "  [bold cyan]██████╔╝██║     ██║██║   ██║[/bold cyan]  [bold white]Biju CLI[/bold white]  [dim]v2.0[/dim]",
        justify="left",
    )
    console.print(
        "  [bold magenta]██╔══██╗██║██   ██║██║   ██║[/bold magenta]  [dim]Autonomous AI Engineer[/dim]",
        justify="left",
    )
    console.print(
        "  [bold magenta]██████╔╝██║╚█████╔╝╚██████╔╝[/bold magenta]  [dim]by Prithish[/dim]",
        justify="left",
    )
    console.print(
        "  [dim]╚═════╝ ╚═╝ ╚════╝  ╚═════╝[/dim]",
        justify="left",
    )
    console.print(Rule(style="cyan dim"))

    # Status dots
    has_instructions = os.path.exists(os.path.join(os.getcwd(), "biju-instructions.md"))
    instr_status = (
        "[bold green]●[/bold green] [dim]biju-instructions.md loaded[/dim]"
        if has_instructions
        else "[bold yellow]●[/bold yellow] [dim]No biju-instructions.md — run [bold]/init[/bold] to generate one[/dim]"
    )
    console.print(f"  {instr_status}")
    console.print(f"  [bold blue]●[/bold blue] [dim]Model: [cyan]{get_model_label(MODEL)}[/cyan]  ·  Type [bold]/help[/bold] to see all commands[/dim]")
    console.print()

# --- SLASH COMMAND HANDLERS ---
def cmd_help():
    # ── Commands table
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, header_style="bold cyan", title="[bold cyan]Slash Commands[/bold cyan]")
    table.add_column("Command",     style="bold white",  no_wrap=True)
    table.add_column("Description", style="dim white")
    for cmd, desc in COMMANDS.items():
        table.add_row(cmd, desc)
    console.print(table)

    # ── Tools table
    tool_rows = [
        ("run_command",     "⚙",  "yellow",       "Execute a shell command (approval required)"),
        ("read_file",       "📄",  "blue",         "Read a file with line numbers"),
        ("write_file",      "✏",   "green",        "Create a new file (use edit_file for changes)"),
        ("edit_file",       "🔧",  "green",        "Patch exact text in an existing file (diff preview)"),
        ("list_dir",        "📂",  "cyan",         "Tree-formatted directory listing"),
        ("search_in_files", "🔍",  "cyan",         "Search text/regex across files"),
        ("read_file_range", "📄",  "blue",         "Read specific line range from a file"),
        ("git_status",      "🌿",  "bright_green", "Show git status and branch"),
        ("git_diff",        "🌿",  "bright_green", "Show git diff (working or staged)"),
        ("git_log",         "🌿",  "bright_green", "Show recent git commit log"),
    ]
    ttable = Table(box=box.ROUNDED, border_style="dim", show_header=True, header_style="bold", title="[bold]Available AI Tools[/bold]")
    ttable.add_column("Tool",        style="bold white", no_wrap=True)
    ttable.add_column("Icon",        style="dim",        no_wrap=True, width=3)
    ttable.add_column("Description", style="dim white")
    for name, icon, _color, desc in tool_rows:
        ttable.add_row(name, icon, desc)
    console.print(ttable)

    # ── Agents table
    atable = Table(box=box.ROUNDED, border_style="dim", show_header=True, header_style="bold", title="[bold]Background Agents  (/agent)[/bold]")
    atable.add_column("Agent",       style="bold white", no_wrap=True)
    atable.add_column("Icon",        no_wrap=True, width=3)
    atable.add_column("Description", style="dim white")
    for a in AGENT_DEFINITIONS:
        atable.add_row(a["name"], a["icon"], a["desc"])
    console.print(atable)

def cmd_setkey():
    console.print(Panel(
        "[0] NVIDIA\n[1] DeepSeek\n[2] Kimi (Moonshot)",
        title="[bold cyan]Which API Key to update?[/bold cyan]",
        border_style="cyan", expand=False,
    ))
    choice = input("\n  Enter number (Enter to cancel): ").strip()
    config = load_config()
    key_map = {"0": "NVIDIA_API_KEY", "1": "DEEPSEEK_API_KEY", "2": "KIMI_API_KEY"}
    label_map = {"0": "NVIDIA", "1": "DeepSeek", "2": "Kimi"}
    if choice in key_map:
        new_key = input(f"  Enter new {label_map[choice]} API Key: ").strip()
        if new_key:
            config[key_map[choice]] = new_key
            save_config(config)
            console.print(f"[bold green]✓ {label_map[choice]} API Key updated![/bold green]")
        else:
            console.print("[dim]No key entered — cancelled.[/dim]")
    else:
        console.print("[dim]Cancelled.[/dim]")

def cmd_config_reset():
    confirm = input("  ⚠  This will delete all saved API keys. Are you sure? [y/N]: ").strip().lower()
    if confirm == "y":
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        console.print("[bold green]✓ Config deleted. Restart Biju to set new keys.[/bold green]")
    else:
        console.print("[dim]Cancelled.[/dim]")

def cmd_init():
    path = os.path.join(os.getcwd(), "biju-instructions.md")
    if os.path.exists(path):
        console.print(f"[bold yellow]⚠ biju-instructions.md already exists.[/bold yellow]")
        return
    template = f"""# Biju Instructions

This file customises Biju CLI behaviour for **this repository**.
Biju will read this file on startup and follow these rules throughout the session.

## Project Overview
<!-- Briefly describe what this project does -->

## Tech Stack
<!-- e.g. Python 3.11, FastAPI, PostgreSQL -->

## Code Style & Conventions
<!-- e.g. use Black formatter, 4-space indent, snake_case -->

## Common Commands
<!-- e.g. -->
- Run tests: `pytest`
- Start server: `uvicorn main:app --reload`

## Important Notes
<!-- Things Biju should always keep in mind -->
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(template)
    console.print(f"[bold green]✓ Created biju-instructions.md[/bold green] — open it and fill in your project details!")

def cmd_queue(rest: str, messages: list):
    """Manage the prompt queue."""
    sub = rest.strip()

    # /queue with no args → show queue
    if not sub or sub == "list":
        if not prompt_queue:
            console.print(Panel(
                "[dim]The queue is empty.[/dim]\n\n"
                "Add prompts with: [bold]/queue add <your prompt>[/bold]\n"
                "They will run automatically one by one after each response.",
                title="[bold cyan]📋 Prompt Queue[/bold cyan]",
                border_style="cyan", expand=False,
            ))
        else:
            table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, header_style="bold cyan")
            table.add_column("#",      style="dim",        width=4)
            table.add_column("Prompt", style="bold white")
            for i, p in enumerate(prompt_queue, 1):
                preview = p if len(p) <= 80 else p[:77] + "..."
                table.add_row(str(i), preview)
            console.print(Panel(
                table,
                title=f"[bold cyan]📋 Prompt Queue ({len(prompt_queue)} item{'s' if len(prompt_queue) != 1 else ''})[/bold cyan]",
                border_style="cyan", expand=False,
            ))
        return

    # /queue clear
    if sub == "clear":
        count = len(prompt_queue)
        prompt_queue.clear()
        console.print(f"[bold green]✓ Cleared {count} prompt(s) from the queue.[/bold green]")
        return

    # /queue next  — manually trigger next queued prompt
    if sub == "next":
        if not prompt_queue:
            console.print("[yellow]⚠ Queue is empty.[/yellow]")
        else:
            next_prompt = prompt_queue.popleft()
            console.print(f"[bold cyan]▶ Running queued prompt:[/bold cyan] {next_prompt}\n")
            reply = run_with_esc_cancel(next_prompt, messages)
            if reply and reply.strip():
                console.print(Rule(characters="─", style="dim"))
                console.print("[bold purple]🟣 Biju[/bold purple]")
                console.print(Markdown(reply.strip()))
                console.print(Rule(characters="─", style="dim"))
        return

    # /queue add <text>  (or just /queue <text> with no subcommand keyword)
    if sub.startswith("add "):
        prompt_text = sub[4:].strip()
    else:
        prompt_text = sub  # treat entire rest as the prompt

    if not prompt_text:
        console.print("[yellow]Usage:[/yellow] /queue add <your prompt>")
        return

    prompt_queue.append(prompt_text)
    pos = len(prompt_queue)
    console.print(Panel(
        f"[bold white]{prompt_text}[/bold white]",
        title=f"[bold green]✓ Added to queue (position {pos})[/bold green]",
        border_style="green", expand=False,
    ))
    if pos == 1:
        console.print("[dim]  It will run automatically after your next AI response.[/dim]")
    else:
        console.print(f"[dim]  It will run after the {pos-1} prompt(s) ahead of it.[/dim]")


def cmd_add_dir():
    """Add a trusted directory that Biju is allowed to read/write freely."""
    config = load_config()
    trusted = config.get("trusted_dirs", [])

    # Show current list first
    if trusted:
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("#",    style="dim", width=4)
        table.add_column("Path", style="bold white")
        for i, d in enumerate(trusted, 1):
            exists = os.path.isdir(d)
            marker = "[green]✓[/green]" if exists else "[red]✗ missing[/red]"
            table.add_row(str(i), f"{d}  {marker}")
        console.print(Panel(table, title="[bold cyan]Trusted Directories[/bold cyan]", border_style="cyan", expand=False))
    else:
        console.print("[dim]No trusted directories added yet.[/dim]\n")

    console.print(
        "[dim]Options:[/dim]\n"
        "  [bold]Enter a path[/bold]  — add it\n"
        "  [bold]r \u003cnumber\u003e[/bold]    — remove that entry\n"
        "  [bold]Enter[/bold]        — cancel\n"
    )
    raw = input("  > ").strip()
    if not raw:
        console.print("[dim]Cancelled.[/dim]")
        return

    # Remove entry
    if raw.lower().startswith("r "):
        try:
            idx = int(raw.split()[1]) - 1
            removed = trusted.pop(idx)
            config["trusted_dirs"] = trusted
            save_config(config)
            console.print(f"[bold green]✓ Removed:[/bold green] {removed}")
        except (IndexError, ValueError):
            console.print("[red]Invalid index.[/red]")
        return

    # Add path
    path = os.path.expanduser(raw)
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        console.print(f"[bold yellow]⚠ Directory not found:[/bold yellow] {path}")
        yn = input("  Add it anyway? [y/N]: ").strip().lower()
        if yn != "y":
            console.print("[dim]Cancelled.[/dim]")
            return

    if path in trusted:
        console.print(f"[yellow]Already in trusted list:[/yellow] {path}")
        return

    trusted.append(path)
    config["trusted_dirs"] = trusted
    save_config(config)
    console.print(Panel(
        f"[bold white]{path}[/bold white]\n[dim]Biju now knows it can freely read and write files in this directory.[/dim]",
        title="[bold green]✓ Directory Added[/bold green]",
        border_style="green", expand=False,
    ))


# ─────────────────────────────────────────────────────────────────────────────
# REAL AGENT SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

# Agent definitions — each spawnable as its own background AI loop
# 'model' is the best NVIDIA-hosted model for that agent's job.
# Agents NEVER use the user's current model or any third-party API.
AGENT_DEFINITIONS = [
    {
        "name": "Researcher",
        "icon": "🔎",
        "color": "cyan",
        "desc": "Searches the web, reads URLs, summarises findings",
        "model": "mistralai/mistral-large-3-675b-instruct-2512",  # large context, great comprehension
        "model_label": "Mistral Large 3",
        "system": (
            "You are the Researcher agent inside Biju CLI. Your job is to gather information.\n"
            "Given a task, use run_command to fetch pages with curl/wget, search with web tools, "
            "read local files, and produce a clear, structured summary.\n"
            "Always cite your sources. Be concise. End with a clear FINDINGS section."
        ),
    },
    {
        "name": "Coder",
        "icon": "💻",
        "color": "green",
        "desc": "Writes & edits code, runs tests, fixes bugs",
        "model": "abacusai/dracarys-llama-3.1-70b-instruct",  # purpose-built for coding
        "model_label": "Dracarys 70B",
        "system": (
            "You are the Coder agent inside Biju CLI. Your job is to write and fix code.\n"
            "Read files before editing. Make surgical targeted changes. "
            "Always run the relevant build or test command after changing code. "
            "If tests fail, read the error and fix it. Do not stop until the code works."
        ),
    },
    {
        "name": "Git Agent",
        "icon": "🌿",
        "color": "bright_green",
        "desc": "Handles git operations: status, diff, commit, push",
        "model": "meta/llama-3.3-70b-instruct",  # best at context + writing commit messages
        "model_label": "Llama 3.3 70B",
        "system": (
            "You are the Git agent inside Biju CLI. Your job is to manage git.\n"
            "Start by running git status and git log --oneline -10 to understand state. "
            "Perform the requested git operations carefully. "
            "Always show a diff before committing. Write descriptive commit messages."
        ),
    },
    {
        "name": "File Agent",
        "icon": "📁",
        "color": "yellow",
        "desc": "Explores directories, bulk rename/move/delete",
        "model": "mistralai/mistral-small-4-119b-2603",  # fast enough, file tasks are simple
        "model_label": "Mistral Small 4",
        "system": (
            "You are the File Agent inside Biju CLI. Your job is to manage files and directories.\n"
            "Start by listing the relevant directory. Read files when needed. "
            "Be careful with destructive operations — always confirm what will be deleted or moved. "
            "Report clearly what you changed."
        ),
    },
    {
        "name": "Test Runner",
        "icon": "🧪",
        "color": "magenta",
        "desc": "Runs test suites, reads failures, proposes & applies fixes",
        "model": "abacusai/dracarys-llama-3.1-70b-instruct",  # needs strong code understanding
        "model_label": "Dracarys 70B",
        "system": (
            "You are the Test Runner agent inside Biju CLI. Your job is to run and fix tests.\n"
            "Run the test suite, read the failure output carefully, locate the failing code, "
            "fix it with minimal changes, and re-run. Repeat until all tests pass. "
            "Report a final summary of what you fixed."
        ),
    },
    {
        "name": "Shell Agent",
        "icon": "⚡",
        "color": "bright_yellow",
        "desc": "Executes long-running shell tasks autonomously",
        "model": "meta/llama-3.1-8b-instruct",  # fast; shell commands are simple
        "model_label": "Llama 3.1 8B",
        "system": (
            "You are the Shell Agent inside Biju CLI. Your job is to run shell commands.\n"
            "Execute the requested task using terminal commands. "
            "Handle errors by reading output and adapting. "
            "Report exit codes and important output clearly."
        ),
    },
    # ── New specialized agents (Feature 8) ─────────────────────────────
    {
        "name": "Repo Scout",
        "icon": "🧐",
        "color": "bright_cyan",
        "desc": "Maps repo structure, reads key files, builds a project briefing",
        "model": "meta/llama-3.3-70b-instruct",
        "model_label": "Llama 3.3 70B",
        "system": (
            "You are the Repo Scout agent inside Biju CLI. Your job is to understand and map a codebase.\n"
            "Start with list_dir('.', depth=3) to get the full project tree. "
            "Then read key files: README, setup.py/pyproject.toml/package.json, main entry points, and any config files. "
            "Use search_in_files to locate important patterns (e.g. class definitions, exports, routes, models). "
            "Use git_log to understand recent activity. "
            "Produce a structured CODEBASE BRIEFING with sections:\n"
            "  1. Project Overview (what it does, stack, entry points)\n"
            "  2. Directory Map (key directories and their purpose)\n"
            "  3. Key Files (what each important file contains)\n"
            "  4. Dependencies (external libs, APIs, databases)\n"
            "  5. Recent Activity (last 10 commits summary)\n"
            "  6. Suggested Entry Points (best files to start reading)\n"
            "Be thorough but concise. Do not guess — read the actual files."
        ),
    },
    {
        "name": "Patch Editor",
        "icon": "🩹",
        "color": "green",
        "desc": "Applies precise targeted edits using edit_file with diff preview",
        "model": "abacusai/dracarys-llama-3.1-70b-instruct",
        "model_label": "Dracarys 70B",
        "system": (
            "You are the Patch Editor agent inside Biju CLI. Your job is to apply precise, surgical code edits.\n"
            "RULES:\n"
            "1. ALWAYS read the file first with read_file or read_file_range before editing.\n"
            "2. ALWAYS use edit_file (never write_file) for changes to existing files. "
               "edit_file shows a diff preview before applying.\n"
            "3. Match the exact whitespace, indentation, and style of the surrounding code.\n"
            "4. After each edit, use read_file_range to verify the change looks correct.\n"
            "5. After all edits, run the relevant test/lint command to confirm nothing broke.\n"
            "6. If multiple files need editing, handle them one at a time in dependency order.\n"
            "7. Report each edit made: filename, what changed, and why."
        ),
    },
    {
        "name": "Reviewer",
        "icon": "📈",
        "color": "blue",
        "desc": "Reviews code changes, checks for bugs, style, and best practices",
        "model": "meta/llama-3.3-70b-instruct",
        "model_label": "Llama 3.3 70B",
        "system": (
            "You are the Reviewer agent inside Biju CLI. Your job is to review code for quality and correctness.\n"
            "Start by running git_status and git_diff to see all current changes. "
            "Then read the changed files in full using read_file. "
            "Also read tests related to changed code using search_in_files. "
            "Produce a structured CODE REVIEW with sections:\n"
            "  🐛 BUGS: Any correctness issues, logic errors, or crashes\n"
            "  ⚠ RISKS: Security issues, data loss, race conditions, edge cases\n"
            "  📝 STYLE: Naming, complexity, missing docstrings, inconsistent formatting\n"
            "  ✅ GOOD: What was done well (always acknowledge positives)\n"
            "  💡 SUGGESTIONS: Non-blocking improvement ideas\n"
            "Rate severity: CRITICAL / HIGH / MEDIUM / LOW.\n"
            "End with: VERDICT: [Approve / Needs Changes / Reject] and a one-line summary."
        ),
    },
    {
        "name": "Security Guard",
        "icon": "🔐",
        "color": "red",
        "desc": "Scans for security vulnerabilities, secrets, and risky patterns",
        "model": "meta/llama-3.3-70b-instruct",
        "model_label": "Llama 3.3 70B",
        "system": (
            "You are the Security Guard agent inside Biju CLI. Your job is to find security vulnerabilities.\n"
            "Use search_in_files to scan for known vulnerability patterns such as:\n"
            "  - Hardcoded secrets: passwords, API keys, tokens, private keys\n"
            "  - SQL injection: string-formatted queries, f-strings in SQL\n"
            "  - Command injection: shell=True with user input, os.system() with variables\n"
            "  - Path traversal: unsanitized file paths from user input\n"
            "  - Insecure deserialization: pickle.loads, yaml.load without Loader\n"
            "  - XSS: unescaped HTML output, innerHTML with user data\n"
            "  - Weak crypto: MD5, SHA1 for passwords, ECB mode, hardcoded IVs\n"
            "  - Debug/development flags left on: DEBUG=True, verbose error output\n"
            "Read suspicious files fully with read_file. "
            "Check .env files, config files, and any file handling user input. "
            "Produce a SECURITY REPORT with:\n"
            "  CRITICAL: Findings that could lead to data breach / RCE\n"
            "  HIGH: Serious vulnerabilities needing immediate fix\n"
            "  MEDIUM: Issues that should be fixed before production\n"
            "  LOW: Minor issues and best-practice violations\n"
            "  CLEAN: Areas that looked clean\n"
            "For each finding: file, line range, description, severity, and recommended fix."
        ),
    },
]


def _agent_worker(agent_def: dict, task: str, agent_obj: dict) -> None:
    """Background thread function — runs a full AI loop for one agent."""
    global RUNNING_AGENTS
    name        = agent_def["name"]
    icon        = agent_def["icon"]
    color       = agent_def["color"]
    # Use the user's currently selected model, not a hardcoded agent model.
    # The 'model' field in AGENT_DEFINITIONS is kept as metadata only.
    agent_model = MODEL
    model_label = get_model_label(MODEL)
    header = f"[bold {color}]{name}[/bold {color}]"

    # Connect using the appropriate API for the user's chosen model.
    # Third-party models (DeepSeek, Kimi) use their own APIs;
    # NVIDIA-hosted models use the NVIDIA API.
    THIRD_PARTY_ROUTING = {
        "deepseek-chat":     {"key": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1"},
        "deepseek-reasoner": {"key": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1"},
        "moonshot-v1-8k":    {"key": "KIMI_API_KEY",     "base_url": "https://api.moonshot.cn/v1"},
        "moonshot-v1-32k":   {"key": "KIMI_API_KEY",     "base_url": "https://api.moonshot.cn/v1"},
        "moonshot-v1-128k":  {"key": "KIMI_API_KEY",     "base_url": "https://api.moonshot.cn/v1"},
    }
    try:
        config  = load_config()
        if agent_model in THIRD_PARTY_ROUTING:
            routing = THIRD_PARTY_ROUTING[agent_model]
            api_key  = config.get(routing["key"])
            base_url = routing["base_url"]
            provider = routing["key"].replace("_API_KEY", "")
        else:
            api_key  = config.get("NVIDIA_API_KEY")
            base_url = "https://integrate.api.nvidia.com/v1"
            provider = "NVIDIA"
        if not api_key:
            raise ValueError(f"No API key found for {provider}. Run /setkey to add it.")
        from openai import OpenAI as _OAI
        client = _OAI(base_url=base_url, api_key=api_key)
    except Exception as e:
        agent_obj["status"] = "error"
        agent_obj["last_output"] = f"API error: {e}"
        console.print(f"{header} [red]Failed to connect: {e}[/red]")
        return

    sys_msg = agent_def["system"]
    messages = [
        {"role": "system",  "content": sys_msg},
        {"role": "user",    "content": task},
    ]
    agent_obj["status"] = "running"
    console.print(f"\n{header} [dim]Starting task using [cyan]{model_label}[/cyan]:[/dim] {task}\n")

    tool_calls_made = 0
    max_tool_calls = 20

    while not agent_obj.get("stop_flag", False):
        try:
            stream_iter = client.chat.completions.create(
                model=agent_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=4096,
                stream=True,
                timeout=60.0,
            )
        except Exception as e:
            console.print(f"{header} [red]API error: {e}[/red]")
            agent_obj["status"] = "error"
            agent_obj["last_output"] = str(e)
            break

        full_content  = ""
        tool_calls_acc: dict = {}
        for chunk in stream_iter:
            if agent_obj.get("stop_flag", False):
                break
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            if delta.content:
                full_content += delta.content
                print(delta.content, end="", flush=True)

            # Accumulate tool calls
            if delta.tool_calls:
                has_tool_calls = True
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "name": "", "args": ""}
                    if tc.id:
                        tool_calls_acc[idx]["id"] += tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_acc[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_acc[idx]["args"] += tc.function.arguments

        # Detect text-based tool calls
        has_tool_calls = bool(tool_calls_acc)
        if not has_tool_calls and full_content.strip():
            parsed = _try_parse_text_tool_call(full_content)
            if parsed:
                has_tool_calls = True
                tool_calls_acc = {0: {"id": "text_tc_0", "name": parsed["name"], "args": json.dumps(parsed["args"])}}

        # Render text response
        clean = _strip_thinking(full_content)
        if not has_tool_calls and clean:
            console.print(f"{header}")
            console.print(Markdown(clean))
            agent_obj["last_output"] = clean[:200]

            # ── Auto-detect web search requests ──────────────────────────────
            # If the agent's response mentions searching online, automatically
            # spawn a parallel Web Search sub-agent to handle it.
            web_task = _detect_web_search_need(clean)
            if web_task and not agent_obj.get("_web_search_launched"):
                agent_obj["_web_search_launched"] = True
                ws_result = spawn_web_search_subagent(web_task)
                # Wait for the web search to complete (max 120s)
                ws_thread = ws_result.get("_thread")
                if ws_thread:
                    ws_thread.join(timeout=120)
                findings = ws_result.get("findings")
                if findings:
                    # Inject web search findings as a system-level message
                    # so the main agent can incorporate them
                    messages.append({
                        "role": "user",
                        "content": (
                            f"[Web Search Sub-Agent Results]\n\n"
                            f"The parallel Web Search sub-agent has completed and found the following:\n\n"
                            f"{findings}\n\n"
                            f"Please use these findings to continue your task."
                        ),
                    })
                    continue  # loop back so main agent can use the findings

        # Execute tool calls
        if has_tool_calls and tool_calls_acc:
            if tool_calls_made >= max_tool_calls:
                console.print(f"{header} [yellow]Tool call limit reached ({max_tool_calls}).[/yellow]")
                break

            # Add assistant message
            tc_list = []
            for idx in sorted(tool_calls_acc):
                tc = tool_calls_acc[idx]
                tc_list.append({
                    "id": tc["id"] or f"tc_{idx}",
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["args"]},
                })
            messages.append({"role": "assistant", "content": full_content or None, "tool_calls": tc_list})

            for tc in tc_list:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    fn_args = {}

                console.print(f"{header} [dim]→ {fn_name}({', '.join(f'{k}={repr(v)[:40]}' for k,v in fn_args.items())})[/dim]")

                if fn_name == "run_command":
                    # Agents always run in full autopilot — no approval prompt
                    cmd_to_run = fn_args.get("command", "")
                    # Still warn on destructive commands in the output
                    is_destr, destr_desc = is_destructive_command(cmd_to_run)
                    if is_destr:
                        console.print(f"{header} [yellow]Destructive command: {destr_desc}[/yellow]")
                    tool_result = run_command_impl(cmd_to_run)
                else:
                    # All other tools: use the shared dispatcher
                    tool_result = dispatch_tool(fn_name, fn_args)

                agent_obj["last_output"] = f"{fn_name}: {tool_result[:100]}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })
                tool_calls_made += 1

            continue  # loop back for next AI response

        # No more tool calls — agent is done
        break

    agent_obj["status"] = "done" if not agent_obj.get("stop_flag") else "stopped"
    console.print(f"\n{header} [dim]{'Finished' if agent_obj['status'] == 'done' else 'Stopped'}.[/dim]\n")
    # Remove from running after a delay so status can be checked
    import time as _time
    _time.sleep(3)
    RUNNING_AGENTS.pop(name, None)


# ─────────────────────────────────────────────────────────────────────────────
# WEB SEARCH SUB-AGENT
# ─────────────────────────────────────────────────────────────────────────────
# Automatically spawned in parallel when a main agent needs to search online.
# Uses the best available up-to-date NVIDIA model (auto-selected, never
# third-party APIs). Reports findings back via a shared result dict.

_WEB_SEARCH_KEYWORDS = [
    "search online", "search the web", "search for best", "find template",
    "find the best", "look up online", "find animation", "find colour",
    "find color", "best template", "search internet", "look up on web",
    "find on the web", "best library", "find plugin", "search for",
    "look for online", "find examples online",
]

_WEB_SEARCH_SYSTEM = (
    "You are the Web Search sub-agent inside Biju CLI. Your job is to search the web "
    "and find the best resources, templates, animations, color palettes, and libraries "
    "as requested.\n"
    "Use run_command with curl to fetch web pages (e.g. `curl -s 'https://...'`).\n"
    "Search for GitHub repos, CDN links, CodePen examples, and documentation pages.\n"
    "Always try multiple search approaches:\n"
    "  1. Fetch search engine results via curl (e.g. DuckDuckGo lite)\n"
    "  2. Fetch the top result pages directly\n"
    "  3. Look for CDN/npm links for any libraries you find\n"
    "Produce a clear FINDINGS section at the end with:\n"
    "  - Name and URL of each resource found\n"
    "  - Why it is recommended (features, popularity, recency)\n"
    "  - A ready-to-use code snippet or CDN link where applicable\n"
    "Be specific and actionable. Do not guess — only report what you actually found."
)


def _web_search_worker(task: str, result_store: dict) -> None:
    """
    Background thread: runs a web search using the best available NVIDIA model.
    Stores results in result_store['findings'] when done.
    """
    ws_model = get_web_search_model()
    ws_label = get_model_label(ws_model)
    header   = "[bold bright_cyan]Web Search[/bold bright_cyan]"

    console.print(
        f"\n{header} [dim]Starting parallel web search using "
        f"[cyan]{ws_label}[/cyan] (auto-selected)…[/dim]\n"
    )

    try:
        config  = load_config()
        api_key = config.get("NVIDIA_API_KEY")
        if not api_key:
            result_store["findings"] = "Error: No NVIDIA_API_KEY for web search sub-agent."
            return
        from openai import OpenAI as _OAI
        client = _OAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
    except Exception as e:
        result_store["findings"] = f"Error connecting for web search: {e}"
        return

    messages = [
        {"role": "system", "content": _WEB_SEARCH_SYSTEM},
        {"role": "user",   "content": task},
    ]

    tool_calls_made = 0
    max_tool_calls  = 10

    while True:
        try:
            stream_iter = client.chat.completions.create(
                model=ws_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=4096,
                stream=True,
                timeout=60.0,
            )
        except Exception as e:
            result_store["findings"] = f"Web search API error: {e}"
            return

        full_content   = ""
        tool_calls_acc: dict = {}

        for chunk in stream_iter:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            if delta.content:
                full_content += delta.content
                print(delta.content, end="", flush=True)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "name": "", "args": ""}
                    if tc.id:
                        tool_calls_acc[idx]["id"] += tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_acc[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_acc[idx]["args"] += tc.function.arguments

        has_tool_calls = bool(tool_calls_acc)
        clean = _strip_thinking(full_content)

        if not has_tool_calls:
            # Final text response — this is the search findings
            if clean:
                console.print(f"\n{header}")
                console.print(Markdown(clean))
                result_store["findings"] = clean
            break

        if tool_calls_made >= max_tool_calls:
            result_store["findings"] = clean or "Web search reached tool call limit."
            break

        # Execute tool calls
        tc_list = []
        for idx in sorted(tool_calls_acc):
            tc = tool_calls_acc[idx]
            tc_list.append({
                "id": tc["id"] or f"ws_tc_{idx}",
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["args"]},
            })
        messages.append({"role": "assistant", "content": full_content or None, "tool_calls": tc_list})

        for tc in tc_list:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                fn_args = {}
            console.print(f"{header} [dim]→ {fn_name}[/dim]")
            tool_result = run_command_impl(fn_args.get("command", "")) if fn_name == "run_command" \
                          else dispatch_tool(fn_name, fn_args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
            tool_calls_made += 1

    result_store.setdefault("findings", clean or "No findings returned.")
    console.print(f"\n{header} [dim]Web search complete.[/dim]\n")


def spawn_web_search_subagent(task: str) -> dict:
    """
    Spawn a parallel Web Search sub-agent in a background thread.
    Returns a shared dict; check result['findings'] when the thread completes.
    The caller can inject result['findings'] into the main agent's messages.
    """
    result_store: dict = {"findings": None}
    t = threading.Thread(
        target=_web_search_worker,
        args=(task, result_store),
        daemon=True,
    )
    t.start()
    result_store["_thread"] = t
    console.print(Panel(
        f"[bold bright_cyan]Web Search sub-agent[/bold bright_cyan] spawned in parallel\n"
        f"[dim]Task: {task}\n"
        f"Model: [cyan]{get_model_label(get_web_search_model())}[/cyan] (auto-selected)[/dim]",
        border_style="bright_cyan", expand=False,
    ))
    return result_store


def _detect_web_search_need(text: str) -> str | None:
    """
    Detect if the agent's response text contains a request to search online.
    Returns a task string if detected, or None otherwise.
    """
    text_lower = text.lower()
    for kw in _WEB_SEARCH_KEYWORDS:
        if kw in text_lower:
            # Extract the relevant sentence containing the keyword as the task
            for sentence in text.split("."):
                if kw in sentence.lower():
                    return sentence.strip()
            return f"Search online for: {kw} (from agent request)"
    return None


def _spawn_agent(agent_def: dict, task: str) -> None:
    """Spawn a background agent thread."""
    global RUNNING_AGENTS
    name = agent_def["name"]

    if name in RUNNING_AGENTS:
        console.print(f"[yellow]⚠ Agent '{name}' is already running. Use /agent stop {name} first.[/yellow]")
        return

    agent_obj = {
        "def": agent_def,
        "task": task,
        "status": "starting",
        "last_output": "",
        "stop_flag": False,
        "thread": None,
    }
    t = threading.Thread(target=_agent_worker, args=(agent_def, task, agent_obj), daemon=True)
    agent_obj["thread"] = t
    RUNNING_AGENTS[name] = agent_obj
    t.start()
    console.print(Panel(
        f"[bold white]{agent_def['icon']} {name}[/bold white]  →  {task}\n"
        f"[dim]Running in background. Use [bold]/agent status[/bold] to check progress.[/dim]",
        title=f"[bold {agent_def['color']}]Agent Spawned[/bold {agent_def['color']}]",
        border_style=agent_def["color"], expand=False,
    ))


def cmd_agent(rest: str) -> None:
    """
    /agent              — show launcher + status of running agents
    /agent status       — list all running agents
    /agent stop <name>  — kill a named agent
    """
    global RUNNING_AGENTS
    sub = rest.strip()

    # ── /agent status ────────────────────────────────────────────────────────
    if sub in ("status", ""):
        # Show running agents panel
        if RUNNING_AGENTS:
            table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, header_style="bold cyan")
            table.add_column("Agent",       style="bold white", no_wrap=True)
            table.add_column("Status",      style="bold")
            table.add_column("Last Output", style="dim white")
            for aname, aobj in list(RUNNING_AGENTS.items()):
                st = aobj["status"]
                color = {"running": "green", "starting": "yellow", "done": "cyan",
                         "error": "red", "stopped": "dim"}.get(st, "white")
                table.add_row(
                    f"{aobj['def']['icon']} {aname}",
                    f"[{color}]{st}[/{color}]",
                    aobj["last_output"][:60] or "—",
                )
            console.print(Panel(table, title="[bold cyan]🤖 Running Agents[/bold cyan]",
                                border_style="cyan", expand=False))
        else:
            console.print("[dim]No agents currently running.[/dim]\n")

        if sub == "status":
            return

        # ── Launcher TUI ──────────────────────────────────────────────────────
        from prompt_toolkit.application import Application
        from prompt_toolkit.layout import Layout, Window, FormattedTextControl

        state = {"idx": 0}
        kb_menu = KeyBindings()

        @kb_menu.add("up")
        def _(event): state["idx"] = max(0, state["idx"] - 1)

        @kb_menu.add("down")
        def _(event): state["idx"] = min(len(AGENT_DEFINITIONS) - 1, state["idx"] + 1)

        @kb_menu.add("enter")
        def _(event): event.app.exit(result=state["idx"])

        @kb_menu.add("escape")
        @kb_menu.add("c-c")
        def _(event): event.app.exit(result=None)

        def get_text():
            lines = ["\n<ansicyan><b>╔══ SPAWN AN AGENT ══╗</b></ansicyan>"]
            lines.append("<ansigray>  [↑/↓] Navigate   [Enter] Spawn   [Esc] Cancel</ansigray>\n")
            for i, a in enumerate(AGENT_DEFINITIONS):
                sel     = i == state["idx"]
                running = a["name"] in RUNNING_AGENTS
                name    = html.escape(a["name"])
                desc    = html.escape(a["desc"])
                cursor  = "<ansigreen><b>❯</b></ansigreen>" if sel else " "
                badge   = " <ansiyellow>(running)</ansiyellow>" if running else ""
                ntag    = (f"<ansigreen><b>{name}</b></ansigreen>"
                           if sel else f"<ansiwhite>{name}</ansiwhite>")
                lines.append(f"  {cursor} {ntag}{badge}")
                lines.append(f"       <ansigray>↳ {desc}</ansigray>")
            lines.append("")
            return HTML("\n".join(lines))

        app = Application(
            layout=Layout(Window(content=FormattedTextControl(get_text))),
            key_bindings=kb_menu,
            full_screen=False,
        )
        chosen_idx = app.run()
        if chosen_idx is None:
            console.print("[dim]Cancelled.[/dim]")
            return

        chosen = AGENT_DEFINITIONS[chosen_idx]
        console.print(f"\n[bold {chosen['color']}]{chosen['name']}[/bold {chosen['color']}] selected.")
        console.print("[dim]  Describe the task (Esc or empty to cancel):[/dim]")
        # Use PromptSession so Esc returns an empty string instead of crashing
        try:
            from prompt_toolkit import PromptSession as _PS
            _task_session = _PS()
            task = _task_session.prompt("  ➤ ").strip()
        except (KeyboardInterrupt, EOFError):
            task = ""
        if not task:
            console.print("[dim]Cancelled — back to chat.[/dim]")
            return
        _spawn_agent(chosen, task)
        return

    # ── /agent stop <name> ────────────────────────────────────────────────────
    if sub.lower().startswith("stop"):
        parts = sub.split(None, 1)
        if len(parts) < 2:
            console.print("[yellow]Usage:[/yellow] /agent stop <AgentName>")
            return
        target = parts[1].strip()
        # Case-insensitive match
        matched = next((k for k in RUNNING_AGENTS if k.lower() == target.lower()), None)
        if not matched:
            console.print(f"[yellow]No running agent named '{target}'.[/yellow]")
            return
        RUNNING_AGENTS[matched]["stop_flag"] = True
        console.print(f"[bold red]🛑 Stop signal sent to {matched}.[/bold red]")
        return

    console.print(f"[red]Unknown /agent subcommand.[/red] Use [bold]/agent[/bold], [bold]/agent status[/bold], or [bold]/agent stop <name>[/bold].")


def cmd_allow_all():
    """Enable full autonomy — autopilot ON + unrestricted tool use."""
    global AUTOPILOT, ALLOW_ALL
    AUTOPILOT = True
    ALLOW_ALL = True
    console.print(Panel(
        "[bold green]🔓 ALLOW ALL — Full Autonomy Enabled[/bold green]\n"
        "[dim]✓ Autopilot ON — commands run without approval\n"
        "✓ All tools unrestricted — Biju can read/write any file and run any command\n\n"
        "[yellow]Use with caution — Biju will not ask for permission for anything.[/yellow][/dim]",
        border_style="green", expand=False,
    ))

def cmd_undo():
    backups = get_file_backups()
    if not backups:
        console.print("[bold yellow]⚠ No file backups found for this session.[/bold yellow]")
        return
    # Restore the most recently backed-up file
    filepath, original = list(backups.items())[-1]
    confirm = input(f"  Restore '{filepath}' to its state before Biju edited it? [y/N]: ").strip().lower()
    if confirm == "y":
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(original)
        del backups[filepath]
        console.print(f"[bold green]✓ Restored {filepath}[/bold green]")
    else:
        console.print("[dim]Undo cancelled.[/dim]")

def cmd_history(messages: list):
    non_system = [m for m in messages if m["role"] != "system"]
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    estimated_tokens = total_chars // 4

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column(style="dim")
    table.add_column(style="bold white")
    table.add_row("Messages in session",  str(len(non_system)))
    table.add_row("Estimated tokens",     f"~{estimated_tokens:,}")
    table.add_row("Token limit warning",  "[yellow]⚠ Consider /clear if > 8,000[/yellow]" if estimated_tokens > 5000 else "[green]✓ OK[/green]")
    console.print(Panel(table, title="[bold cyan]Session Info[/bold cyan]", border_style="cyan", expand=False))

def cmd_ask(messages: list):
    """Ask a side question that doesn't affect conversation history."""
    console.print("[dim]Side-question mode — this won't be added to your conversation history.[/dim]")
    side_q = input("  Ask: ").strip()
    if not side_q:
        console.print("[dim]Cancelled.[/dim]")
        return
    temp_messages = [messages[0], {"role": "user", "content": side_q}]
    try:
        client = get_api_client()
        stream_iter = client.chat.completions.create(
            model=MODEL, messages=temp_messages, temperature=0.2, timeout=30.0, stream=True,
        )
        full = ""
        for chunk in stream_iter:
            if chunk.choices and chunk.choices[0].delta.content:
                full += chunk.choices[0].delta.content
        clean = re.sub(r"<thinking>.*?</thinking>", "", full, flags=re.DOTALL).strip()
        console.print()
        console.print(Rule(characters="─", style="dim"))
        console.print("[bold purple]🟣 Biju[/bold purple]")
        if clean:
            console.print(Markdown(clean))
        console.print(Rule(characters="─", style="dim"))
    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")


# --- MAIN APPLICATION ---
def main():
    global AUTOPILOT, MODEL, ALLOW_ALL
    ensure_keys()

    # ── Start background update check before anything blocks the terminal ──
    _update_result = _update_thread = None
    if _HAS_UPDATER:
        try:
            _update_result, _update_thread = check_for_updates()
        except Exception:
            pass

    session = PromptSession(
        style=ui_style,
        completer=SlashCommandCompleter(),
        key_bindings=kb,
        bottom_toolbar=get_bottom_toolbar,
    )

    print_startup_screen()

    # ── Show update banner if a newer version was found ──────────────────
    if _update_result is not None and _update_thread is not None:
        _update_thread.join(timeout=3)   # wait at most 3 s for network check
        if _update_result.has_update:
            print_update_banner(_update_result)

    current_date      = datetime.datetime.now().strftime("%B %d, %Y")
    home_directory    = os.path.expanduser("~")
    current_directory = os.getcwd()
    os_name           = platform.system()

    # Load per-project instructions if present
    instructions_path = os.path.join(current_directory, "biju-instructions.md")
    project_instructions = ""
    if os.path.exists(instructions_path):
        with open(instructions_path, "r", encoding="utf-8") as f:
            project_instructions = f"\n\n# PROJECT-SPECIFIC INSTRUCTIONS\n{f.read()}"

    # Build repo context summary (Feature 5)
    repo_context = ""
    try:
        repo_context = "\n\n" + build_repo_context(current_directory)
    except Exception:
        pass  # non-critical — skip if it fails

    system_prompt = f"""You are Biju, an elite, autonomous AI software engineer operating directly in the user's terminal.
Developed by Prithish, you are designed to act as a relentless, highly capable agentic assistant.

CURRENT ENVIRONMENT:
- Operating System: {os_name}
- User's Home Directory: {home_directory}
- Current Working Directory (CWD): {current_directory}
- Date: {current_date}

# MISSION & AUTONOMY
You are not a passive chatbot. You are an active agent.
When given a task, you do not ask for permission to investigate. You immediately use your tools to explore the codebase, read files, find the problem, and execute the solution.
You work recursively: if a command fails, you read the error, adjust your approach, and try again until you succeed.

# CORE RULES OF ENGAGEMENT
1. THINK BEFORE YOU ACT: Before making any tool call, you MUST use <thinking>...</thinking> tags to explain your logic, what you are looking for, and what your next step is.
2. BE SURGICAL: Never rewrite an entire file if you only need to change a few lines. Use edit_file to patch specific sections.
3. VERIFY YOUR WORK: After writing or editing code, ALWAYS run the relevant build, lint, or test command to ensure your changes didn't break anything. Do not stop until the tests pass.
4. NATIVE COMMANDS: You are running on {os_name}. Only propose terminal commands that are native and guaranteed to work on this OS.
5. NO HALLUCINATION: Never assume the contents of a file or the structure of the project. Always use list_dir or search_in_files to verify paths and variable names first.
6. CONVERSATION VS TOOLS: Do not use `run_command` (like `echo` or `print`) just to speak to the user. Just output regular text for conversation.
7. EXIT CODES MATTER: When you run a command and get a non-zero exit code, treat it as a failure. Read the stderr, understand the error, and fix it before continuing.

# AVAILABLE TOOLS
- run_command: Execute shell commands
- read_file: Read a file with line numbers
- write_file: Create new files (use edit_file for changes)
- edit_file: Replace exact text matches in existing files (shows diff preview)
- list_dir: Tree-formatted directory listing (prefer over ls/dir)
- search_in_files: Search for text across files (prefer over grep/findstr)
- read_file_range: Read specific line range from a file
- git_status: Show current git status and branch
- git_diff: Show git diff (working tree or staged)
- git_log: Show recent git commit history

# TOOL USAGE GUIDELINES
- Use list_dir and search_in_files instead of run_command with ls/dir/grep/findstr.
- Use read_file_range for large files instead of reading the whole thing.
- Use edit_file for targeted edits. Only use write_file for brand-new files.
- Use git_status, git_diff, git_log instead of running raw git commands for inspection.
- Command Errors: If a terminal command returns a non-zero exit code, analyze the error in your <thinking> block and run a corrective command.

# GREETING PROTOCOL
If the user simply says "hi", "hello", "hey", or "help", DO NOT use tools. Respond EXACTLY with this friendly formatted list:

Hi! 👋 I'm Biju, your autonomous terminal engineer. I can help you with:
- **Codebase Exploration** (finding bugs, tracing logic)
- **Surgical Refactoring** (editing code safely with diff previews)
- **Automated Debugging** (running tests and fixing errors)
- **Project Setup & Git Workflows**

What are we building or breaking today?
{project_instructions}{repo_context}
"""

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            user_input = session.prompt(get_prompt_message)

            # Clear the prompt_toolkit input lines from terminal
            sys.stdout.write("\033[F\033[K" * 3)
            sys.stdout.flush()

            if not user_input.strip():
                continue

            # Echo user input
            console.print(f"[bold magenta]❯[/bold magenta] [bold]{user_input}[/bold]\n")

            # --- SLASH COMMAND ROUTING ---
            if user_input.strip().startswith("/"):
                cmd_input = user_input.strip().lower()

                # /queue has free-form text — handle before lower-casing
                if user_input.strip().lower().startswith("/queue"):
                    rest = user_input.strip()[6:]
                    cmd_queue(rest, messages)
                    console.print()
                    continue

                matches = [c for c in COMMANDS if c.startswith(cmd_input)]
                if len(matches) == 1:
                    cmd = matches[0]
                elif len(matches) > 1 and cmd_input in COMMANDS:
                    cmd = cmd_input
                elif len(matches) > 1:
                    console.print(f"[yellow]Ambiguous command. Did you mean: {', '.join(matches)}?[/yellow]\n")
                    continue
                else:
                    cmd = cmd_input

                if cmd in ("/exit", "/quit"):
                    console.print(Rule(style="purple"))
                    console.print("[bold purple]  Goodbye! 👋  See you next time.[/bold purple]")
                    console.print(Rule(style="purple"))
                    break

                elif cmd == "/clear":
                    print_startup_screen()

                elif cmd == "/autopilot":
                    AUTOPILOT = not AUTOPILOT
                    if AUTOPILOT:
                        console.print(Panel(
                            "[bold green]⚡ Autopilot ON[/bold green]\n[dim]Commands will run automatically without asking for approval.[/dim]",
                            border_style="green", expand=False,
                        ))
                    else:
                        console.print(Panel(
                            "[bold red]⚡ Autopilot OFF[/bold red]\n[dim]You will be asked to approve each command.[/dim]",
                            border_style="red", expand=False,
                        ))

                elif cmd == "/setkey":
                    cmd_setkey()

                elif cmd == "/config":
                    cmd_config_reset()

                elif cmd == "/model":
                    selected = interactive_model_selector(MODEL)
                    # Clear the menu residue without jumping to the top
                    sys.stdout.write("\033[1A\033[2K" * 2)
                    sys.stdout.flush()
                    if selected:
                        MODEL = selected
                        label = MODEL.split("/")[-1]
                        console.print(f"[bold green]✓ Model → [cyan]{label}[/cyan][/bold green]")
                    else:
                        console.print("[dim]Model switch cancelled.[/dim]")

                elif cmd == "/init":
                    cmd_init()

                elif cmd == "/undo":
                    cmd_undo()

                elif cmd == "/update":
                    if _HAS_UPDATER:
                        run_update_classic(console)
                    else:
                        console.print("[yellow]Updater not available. Run: git pull origin main[/yellow]")

                elif cmd == "/history":
                    cmd_history(messages)

                elif cmd == "/ask":
                    cmd_ask(messages)

                elif cmd == "/help":
                    cmd_help()

                elif cmd == "/changelog":
                    console.print(Panel(
                        "[bold]v3.1[/bold]  10 tools (edit_file, list_dir, search_in_files, read_file_range, git tools)\n"
                        "        4 new agents: Repo Scout, Patch Editor, Reviewer, Security Guard\n"
                        "        Trusted-dir enforcement, destructive-cmd safety, live streaming, repo context\n"
                        "[bold]v3.0[/bold]  Markdown rendered responses, ESC cancel, prompt queue\n"
                        "[bold]v2.0[/bold]  Complete rewrite — new UI, /undo, /history, /ask, safety limiter\n"
                        "[bold]v1.0[/bold]  Initial release — model selector TUI, autopilot, tool calling",
                        title="[bold cyan]Changelog[/bold cyan]",
                        border_style="cyan", expand=False,
                    ))

                elif cmd == "/add-dir":
                    cmd_add_dir()

                elif user_input.strip().lower().startswith("/agent"):
                    rest = user_input.strip()[6:]   # everything after "/agent"
                    cmd_agent(rest)


                elif cmd == "/allow-all":
                    cmd_allow_all()

                else:
                    console.print(f"[red]Unknown command: {cmd}[/red]  Type [bold]/help[/bold] to see all commands.\n")

                console.print()
                continue

            # --- AI CHAT ---
            console.print("[dim]  Press [bold]Esc[/bold] to cancel...[/dim]")
            reply = run_with_esc_cancel(user_input, messages)
            # Output already rendered by chat_with_agent
            console.print()

            # --- AUTO-PROCESS QUEUE ---
            while prompt_queue and reply is not None:
                next_prompt = prompt_queue.popleft()
                console.print(Panel(
                    f"[bold white]{next_prompt}[/bold white]",
                    title=f"[bold cyan]▶ Auto-running queued prompt ({len(prompt_queue)} remaining)[/bold cyan]",
                    border_style="cyan", expand=False,
                ))
                console.print("[dim]  Press [bold]Esc[/bold] to cancel...[/dim]")
                reply = run_with_esc_cancel(next_prompt, messages)
                console.print()

        except KeyboardInterrupt:
            sys.stdout.write("\033[F\033[K" * 3)
            sys.stdout.flush()
            console.print("\n[bold red]Cancelled.[/bold red]  Type [bold]/exit[/bold] to quit.\n")
            continue
        except EOFError:
            console.print("\n[bold purple]  Goodbye! 👋[/bold purple]")
            break
        except Exception as e:
            console.print(f"[bold red]✗ Unexpected error:[/bold red] {e}\n")
            continue

if __name__ == "__main__":
    main()

