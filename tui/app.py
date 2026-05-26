"""
tui/app.py
Biju TUI — main Textual application.

Architecture overview
─────────────────────

  ┌─────────────────────────────────────────────┐  ← OutputPanel  (~65 %)
  │  AI Output Area (scrollable markdown)        │
  ├─────────────────────────────────────────────┤  ← PermissionPanel (~15 %, hidden by default)
  │  Permission Panel (tool approval)            │
  ├─────────────────────────────────────────────┤  ← InputPanel (~10 %)
  │  User Input (Enter=send, Shift+Enter=newline)│
  ├─────────────────────────────────────────────┤  ← StatusBar (~5 %)
  │  /commands  /help  /clear  /model  /save     │
  │                          Current Model: …    │
  └─────────────────────────────────────────────┘

Keyboard shortcuts
──────────────────
  Ctrl+L  → Clear chat display
  Ctrl+K  → Command palette
  Ctrl+C  → Cancel in-flight AI generation
  Ctrl+M  → Open model selector
  Ctrl+S  → Save session
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import AsyncGenerator

from openai import AsyncOpenAI, APITimeoutError
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer

from tui.models.config import (
    DEFAULT_MODEL,
    FAST_FALLBACK_MODEL,
    NVIDIA_BASE_URL,
    THIRD_PARTY_MODELS,
    get_model_label,
)
from tui.storage.session import load_session, save_session
from tui.ui.input_panel import InputPanel
from tui.ui.output_panel import OutputPanel
from tui.ui.permission_panel import PermissionPanel, PermissionRequest
from tui.ui.popups import CommandPaletteModal, ModelSelectorModal, SessionBrowserModal
from tui.ui.status_bar import StatusBar
from tui.updater import check_for_updates, make_update_markup, CURRENT_VERSION

# ── Configuration file (shared with the classic CLI) ─────────────────────────
CONFIG_FILE = Path.home() / ".biju_config.json"

# ── Tool definitions sent to the API ─────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Execute a shell/terminal command on the user's OS and return its "
                "full output including exit code, stdout, and stderr."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The exact shell command to execute."}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a file with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Absolute or relative path."}
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file with new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["filepath", "content"],
            },
        },
    },
]

# ── Tools that require permission ─────────────────────────────────────────────
PERMISSION_REQUIRED = {"run_command", "write_file"}


class BijuTUI(App):
    """
    Main Biju Terminal UI Application.
    """

    CSS = """
    Screen {
        background: #08080f;
        layout: vertical;
    }

    OutputPanel {
        height: 6fr;
    }

    PermissionPanel {
        height: auto;
        min-height: 0;
    }

    InputPanel {
        height: 2fr;
        max-height: 12;
        min-height: 5;
    }

    StatusBar {
        height: 1;
        dock: bottom;
    }
    """

    TITLE = "Biju — AI Terminal Engineer"
    SUB_TITLE = "Powered by NVIDIA Free APIs"

    BINDINGS = [
        Binding("ctrl+l", "clear_chat",     "Clear Chat",    show=False),
        Binding("ctrl+k", "command_palette", "Commands",     show=False),
        Binding("ctrl+c", "cancel_gen",     "Cancel",        show=False),
        Binding("ctrl+m", "model_selector", "Switch Model",  show=False),
        Binding("ctrl+s", "save_session",   "Save Session",  show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        # ── State ──────────────────────────────────────────────────────────
        self._model: str = DEFAULT_MODEL
        self._messages: list[dict] = []
        self._autopilot: bool = False
        self._allow_all: bool = False
        self._file_backups: dict[str, str] = {}
        self._generating: bool = False
        self._cancel_event = asyncio.Event()

        # ── Permission gate ────────────────────────────────────────────────
        # When a tool needs approval we pause generation, show the panel,
        # and wait for a Future to be resolved by the user's button click.
        self._permission_future: asyncio.Future | None = None

        # ── Update checker ─────────────────────────────────────────────────
        self._update_result, self._update_thread = check_for_updates()

        # ── System prompt ──────────────────────────────────────────────────
        self._system_prompt = self._build_system_prompt()

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield OutputPanel(id="output")
        yield PermissionPanel(id="permission")
        yield InputPanel(id="input")
        yield StatusBar(id="statusbar")

    def on_mount(self) -> None:
        self._refresh_status_bar()
        # Schedule an update notification check 4 seconds after startup
        # (gives the background thread time to finish the network request)
        self.set_timer(4, self._show_update_notification)

    # ── Input handler ─────────────────────────────────────────────────────────

    async def on_input_panel_message_submitted(self, event: InputPanel.MessageSubmitted) -> None:
        text = event.text.strip()
        if not text:
            return

        # Check for slash commands
        if text.startswith("/"):
            await self._handle_command(text)
            return

        # Regular chat message
        await self._send_message(text)

    # ── Permission response ───────────────────────────────────────────────────

    def on_permission_panel_permission_response(
        self, event: PermissionPanel.PermissionResponse
    ) -> None:
        if self._permission_future and not self._permission_future.done():
            self._permission_future.set_result(event.choice)

    # ── Command dispatcher ────────────────────────────────────────────────────

    async def _handle_command(self, text: str) -> None:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        out = self.query_one("#output", OutputPanel)

        if cmd in ("/exit", "/quit"):
            self.exit()

        elif cmd in ("/clear", "/cls"):
            out.clear_messages()

        elif cmd == "/new":
            self._messages.clear()
            out.clear_messages()
            out.add_tool_event("✦ New conversation started.")

        elif cmd == "/help":
            help_text = self._build_help_text()
            out.add_assistant_message(help_text)

        elif cmd == "/commands":
            cmds_text = self._build_commands_text()
            out.add_assistant_message(cmds_text)

        elif cmd == "/model":
            await self.action_model_selector()

        elif cmd == "/save":
            await self.action_save_session()

        elif cmd == "/load":
            await self._action_load_session()

        elif cmd == "/history":
            count = len([m for m in self._messages if m.get("role") in ("user", "assistant")])
            tokens_est = sum(len(m.get("content", "") or "") for m in self._messages) // 4
            out.add_tool_event(
                f"Messages: {count}  ·  Estimated tokens: ~{tokens_est:,}"
            )

        elif cmd == "/autopilot":
            self._autopilot = not self._autopilot
            sb = self.query_one("#statusbar", StatusBar)
            sb.set_autopilot(self._autopilot)
            state = "ON ⚡" if self._autopilot else "OFF"
            out.add_tool_event(f"Autopilot {state}")

        elif cmd == "/allow-all":
            self._allow_all = True
            self._autopilot = True
            sb = self.query_one("#statusbar", StatusBar)
            sb.set_autopilot(True)
            out.add_tool_event("⚡ Full autonomy enabled — all tool calls will execute without approval.")

        elif cmd == "/init":
            await self._cmd_init()

        elif cmd == "/undo":
            await self._cmd_undo()

        elif cmd == "/setkey":
            out.add_tool_event(
                "To update API keys, edit: **~/.biju_config.json**\n\n"
                "Keys: `NVIDIA_API_KEY`, `DEEPSEEK_API_KEY`, `KIMI_API_KEY`"
            )

        elif cmd == "/config":
            out.add_tool_event(
                "To reset config, delete: **~/.biju_config.json**\n\n"
                "Then restart Biju TUI to be prompted for new keys."
            )

        else:
            out.add_tool_event(f"Unknown command: `{cmd}`. Type `/help` for all commands.")

    # ── AI generation ─────────────────────────────────────────────────────────

    async def _send_message(self, text: str) -> None:
        if self._generating:
            self.query_one("#output", OutputPanel).add_tool_event(
                "⏳ Generation in progress — press Ctrl+C to cancel."
            )
            return

        out = self.query_one("#output", OutputPanel)
        sb = self.query_one("#statusbar", StatusBar)

        out.add_user_message(text)
        self._messages.append({"role": "user", "content": text})

        self._generating = True
        self._cancel_event.clear()
        sb.set_status(f"⠋ {get_model_label(self._model)} is thinking…")

        try:
            await self._agent_loop(out, sb)
        finally:
            self._generating = False
            sb.set_status("")

    async def _agent_loop(self, out: OutputPanel, sb: StatusBar) -> None:
        """Run the full tool-calling agent loop until a final text reply."""
        MAX_TOOL_CALLS = 10
        tool_call_count = 0

        while True:
            if self._cancel_event.is_set():
                out.add_tool_event("🚫 Generation cancelled.")
                return

            if tool_call_count >= MAX_TOOL_CALLS:
                out.add_tool_event(
                    f"⚠ Reached the maximum of {MAX_TOOL_CALLS} tool calls. "
                    "Stopping to check in."
                )
                return

            # Build messages with system prompt prepended
            msgs = [{"role": "system", "content": self._system_prompt}] + self._messages

            # ── Stream from API ───────────────────────────────────────────
            try:
                client = self._get_async_client()
            except ValueError as e:
                out.add_tool_event(f"❌ {e}")
                return

            out.start_streaming()

            full_content = ""
            tool_calls_acc: dict[int, dict] = {}
            has_tool_calls = False

            try:
                stream = await client.chat.completions.create(
                    model=self._model,
                    messages=msgs,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.1,
                    stream=True,
                )

                async for chunk in stream:
                    if self._cancel_event.is_set():
                        out.finish_streaming("")
                        out.add_tool_event("🚫 Generation cancelled.")
                        return

                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if delta.content:
                        full_content += delta.content
                        # Strip thinking tags before showing to user
                        visible = self._strip_thinking(full_content)
                        out.append_stream_token("")  # trigger scroll
                        # Update the streaming widget directly
                        sw = out._streaming_widget
                        if sw is not None:
                            sw.text = visible

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

            except APITimeoutError:
                out.finish_streaming("")
                out.add_tool_event(f"⏱ Timeout — switching to fallback model ({FAST_FALLBACK_MODEL}).")
                self._model = FAST_FALLBACK_MODEL
                self._refresh_status_bar()
                continue

            except Exception as e:
                out.finish_streaming("")
                err = str(e).lower()
                if "404" in err or "not found" in err:
                    out.add_tool_event(f"❌ Model '{self._model}' not found. Reverting to default.")
                    self._model = DEFAULT_MODEL
                    self._refresh_status_bar()
                else:
                    out.add_tool_event(f"❌ API Error: {e}")
                return

            # ── Finalize text ─────────────────────────────────────────────
            clean = self._strip_thinking(full_content)

            # Check for text-embedded tool calls (Llama quirk)
            if not has_tool_calls and clean:
                text_tool = self._try_parse_text_tool_call(clean)
                if text_tool:
                    has_tool_calls = True
                    tool_calls_acc[0] = {
                        "id": f"text_call_{tool_call_count}",
                        "type": "function",
                        "function": {
                            "name": text_tool["name"],
                            "arguments": json.dumps(text_tool["arguments"]),
                        },
                    }
                    clean = ""

            if not has_tool_calls:
                out.finish_streaming(clean)
                self._messages.append({"role": "assistant", "content": full_content or ""})
                return

            # ── Handle tool calls ─────────────────────────────────────────
            out.finish_streaming(clean)

            tool_calls_list = [
                {
                    "id": tool_calls_acc[i]["id"],
                    "type": "function",
                    "function": {
                        "name": tool_calls_acc[i]["function"]["name"],
                        "arguments": tool_calls_acc[i]["function"]["arguments"],
                    },
                }
                for i in sorted(tool_calls_acc)
            ]
            self._messages.append({
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": tool_calls_list,
            })

            for tc in tool_calls_list:
                tool_call_count += 1
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                result = await self._execute_tool(func_name, args, out, sb)
                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            sb.set_status(f"⠋ {get_model_label(self._model)} is thinking…")

    # ── Tool execution ────────────────────────────────────────────────────────

    async def _execute_tool(
        self,
        func_name: str,
        args: dict,
        out: OutputPanel,
        sb: StatusBar,
    ) -> str:
        """Execute a tool, requesting permission if needed."""
        icons = {"run_command": "⚙", "read_file": "📄", "write_file": "✏"}
        icon = icons.get(func_name, "🔧")

        # ── Show what we're about to do ───────────────────────────────────
        if func_name == "run_command":
            detail = args.get("command", "")
            event_text = f"{icon} **Run Command**: `{detail}`"
        elif func_name == "read_file":
            detail = args.get("filepath", "")
            event_text = f"{icon} **Read File**: `{detail}`"
        elif func_name == "write_file":
            detail = args.get("filepath", "")
            event_text = f"{icon} **Write File**: `{detail}`"
        else:
            detail = ""
            event_text = f"{icon} **{func_name}**"

        # ── Permission gate ───────────────────────────────────────────────
        if func_name in PERMISSION_REQUIRED and not self._autopilot and not self._allow_all:
            tool_labels = {
                "run_command": "Shell Executor",
                "write_file":  "File Editor",
            }
            req = PermissionRequest(
                tool=tool_labels.get(func_name, func_name),
                action=event_text.replace("**", "").replace("`", ""),
                command=detail,
                risk="high" if func_name == "run_command" else "medium",
            )
            perm = self.query_one("#permission", PermissionPanel)
            loop = asyncio.get_event_loop()
            self._permission_future = loop.create_future()
            sb.set_status("⚠ Waiting for permission…")
            perm.request_permission(req)

            # Wait for user to respond
            try:
                choice = await asyncio.wait_for(self._permission_future, timeout=120)
            except asyncio.TimeoutError:
                choice = "deny"

            if choice == "always":
                self._autopilot = True
                self.query_one("#statusbar", StatusBar).set_autopilot(True)

            if choice == "deny":
                out.add_tool_event(f"🚫 Permission denied: `{func_name}`")
                return "Permission denied by user."

            sb.set_status(f"⠋ {get_model_label(self._model)} is thinking…")

        # ── Execute ───────────────────────────────────────────────────────
        out.add_tool_event(event_text)

        if func_name == "run_command":
            return await self._tool_run_command(args.get("command", ""))
        elif func_name == "read_file":
            return self._tool_read_file(args.get("filepath", ""))
        elif func_name == "write_file":
            return self._tool_write_file(args.get("filepath", ""), args.get("content", ""))
        else:
            return f"Unknown tool: {func_name}"

    # ── Tool implementations ──────────────────────────────────────────────────

    async def _tool_run_command(self, cmd: str) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            parts = [f"Exit Code: {proc.returncode}"]
            if stdout.strip():
                parts.append(f"Stdout:\n{stdout.decode(errors='replace').strip()}")
            if stderr.strip():
                parts.append(f"Stderr:\n{stderr.decode(errors='replace').strip()}")
            return "\n".join(parts) or "Command completed with no output."
        except asyncio.TimeoutError:
            return "Error: Command timed out after 60 seconds."
        except Exception as e:
            return f"Error executing command: {e}"

    def _tool_read_file(self, filepath: str) -> str:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            return "".join(f"{i+1:>4}: {line}" for i, line in enumerate(lines))
        except Exception as e:
            return f"Error reading file: {e}"

    def _tool_write_file(self, filepath: str, content: str) -> str:
        try:
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    self._file_backups[filepath] = f.read()
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content.splitlines())} lines to {filepath}"
        except Exception as e:
            return f"Error writing file: {e}"

    # ── Helper: build async OpenAI client ────────────────────────────────────

    def _get_async_client(self) -> AsyncOpenAI:
        config = self._load_config()
        if self._model in THIRD_PARTY_MODELS:
            info = THIRD_PARTY_MODELS[self._model]
            api_key = config.get(info["key"])
            base_url = info["base_url"]
            provider = info["provider"]
        else:
            api_key = config.get("NVIDIA_API_KEY")
            base_url = NVIDIA_BASE_URL
            provider = "NVIDIA"

        if not api_key:
            raise ValueError(f"No API key for {provider}. Edit ~/.biju_config.json or run the classic CLI to set keys.")

        return AsyncOpenAI(api_key=api_key, base_url=base_url)

    # ── Helper: config ─────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    # ── Helper: system prompt ─────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        import platform
        os_name = platform.system()
        cwd = os.getcwd()
        # Check for biju-instructions.md
        instructions = ""
        instr_path = Path(cwd) / "biju-instructions.md"
        if instr_path.exists():
            try:
                instructions = "\n\nProject Instructions:\n" + instr_path.read_text(encoding="utf-8")
            except Exception:
                pass

        return (
            f"You are Biju, an autonomous AI terminal engineer. "
            f"You run on {os_name}. Current working directory: {cwd}.\n"
            "You have access to tools: run_command (shell), read_file, write_file.\n"
            "Always be precise, professional, and efficient. "
            "Prefer targeted edits over full rewrites. "
            "Always explain what you're about to do before using a tool."
            + instructions
        )

    # ── Helper: text cleanup ──────────────────────────────────────────────

    @staticmethod
    def _strip_thinking(text: str) -> str:
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
        text = re.sub(
            r"^(?:Thinking|Let me think|I need to think)[\s.…:–—-]*.*?(?=\n\n|\Z)",
            "", text, flags=re.DOTALL | re.IGNORECASE,
        )
        return text.strip()

    KNOWN_TOOLS = {"run_command", "read_file", "write_file"}

    def _try_parse_text_tool_call(self, text: str) -> dict | None:
        stripped = text.strip()
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped).strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            obj = json.loads(stripped[start:end + 1])
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        if obj.get("name") in self.KNOWN_TOOLS:
            args = obj.get("parameters") or obj.get("arguments") or {}
            return {"name": obj["name"], "arguments": args}
        if "function" in obj and isinstance(obj["function"], dict):
            fn = obj["function"]
            if fn.get("name") in self.KNOWN_TOOLS:
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                return {"name": fn["name"], "arguments": args}
        return None

    # ── Status bar sync ───────────────────────────────────────────────────

    def _refresh_status_bar(self) -> None:
        try:
            sb = self.query_one("#statusbar", StatusBar)
            sb.set_model(get_model_label(self._model))
            sb.set_autopilot(self._autopilot)
        except Exception:
            pass

    def _show_update_notification(self) -> None:
        """Called ~4 s after startup; shows an update banner if one is available."""
        if self._update_thread.is_alive():
            # Thread not done yet — check again in 2 more seconds
            self.set_timer(2, self._show_update_notification)
            return
        if self._update_result.has_update:
            try:
                out = self.query_one("#output", OutputPanel)
                out.add_tool_event(make_update_markup(self._update_result))
            except Exception:
                pass

    # ── Slash command helpers ─────────────────────────────────────────────

    def _build_help_text(self) -> str:
        return (
            "## Biju TUI — Help\n\n"
            "### Keyboard Shortcuts\n"
            "| Shortcut | Action |\n"
            "|----------|--------|\n"
            "| `Enter` | Send message |\n"
            "| `Shift+Enter` | New line in input |\n"
            "| `Ctrl+K` | Open command palette |\n"
            "| `Ctrl+L` | Clear chat |\n"
            "| `Ctrl+M` | Switch model |\n"
            "| `Ctrl+S` | Save session |\n"
            "| `Ctrl+C` | Cancel generation |\n\n"
            "### Slash Commands\n"
            "Type `/commands` to see the full list of slash commands."
        )

    def _build_commands_text(self) -> str:
        from tui.commands.registry import COMMANDS
        rows = "\n".join(
            f"| `{cmd.name}` | {cmd.description} |"
            for cmd in COMMANDS
        )
        return f"## Available Commands\n\n| Command | Description |\n|---------|-------------|\n{rows}"

    async def _cmd_init(self) -> None:
        out = self.query_one("#output", OutputPanel)
        path = Path(os.getcwd()) / "biju-instructions.md"
        if path.exists():
            out.add_tool_event(f"⚠ `biju-instructions.md` already exists at `{path}`")
            return
        template = (
            "# Biju Instructions\n\n"
            "This file customises Biju behaviour for **this repository**.\n\n"
            "## Project Overview\n<!-- Briefly describe what this project does -->\n\n"
            "## Tech Stack\n<!-- e.g. Python 3.11, FastAPI, PostgreSQL -->\n\n"
            "## Code Style\n<!-- e.g. use Black, 4-space indent, snake_case -->\n\n"
            "## Common Commands\n- Run tests: `pytest`\n\n"
            "## Notes\n<!-- Things Biju should always keep in mind -->\n"
        )
        path.write_text(template, encoding="utf-8")
        out.add_tool_event(f"✅ Created `biju-instructions.md` — fill it in to customize Biju's behavior!")

    async def _cmd_undo(self) -> None:
        out = self.query_one("#output", OutputPanel)
        if not self._file_backups:
            out.add_tool_event("Nothing to undo.")
            return
        filepath, original = self._file_backups.popitem()
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(original)
            out.add_tool_event(f"↩ Restored `{filepath}`")
        except Exception as e:
            out.add_tool_event(f"❌ Undo failed: {e}")

    # ── Keyboard actions ──────────────────────────────────────────────────

    async def action_clear_chat(self) -> None:
        self.query_one("#output", OutputPanel).clear_messages()

    async def action_command_palette(self) -> None:
        result = await self.push_screen_wait(CommandPaletteModal())
        if result:
            inp = self.query_one("#input", InputPanel)
            inp.set_text(result + " ")
            inp.focus_input()

    async def action_cancel_gen(self) -> None:
        if self._generating:
            self._cancel_event.set()

    async def action_model_selector(self) -> None:
        result = await self.push_screen_wait(ModelSelectorModal(current_model=self._model))
        if result:
            self._model = result
            self._refresh_status_bar()
            self.query_one("#output", OutputPanel).add_tool_event(
                f"✦ Model switched to **{get_model_label(result)}** (`{result}`)"
            )

    async def action_save_session(self) -> None:
        path = save_session(self._messages, self._model)
        self.query_one("#output", OutputPanel).add_tool_event(
            f"💾 Session saved → `{path}`"
        )

    async def _action_load_session(self) -> None:
        path = await self.push_screen_wait(SessionBrowserModal())
        if path:
            messages, model = load_session(path)
            self._messages = messages
            self._model = model
            self._refresh_status_bar()
            out = self.query_one("#output", OutputPanel)
            out.clear_messages()
            # Re-render existing messages
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content") or ""
                if role == "user" and content:
                    out.add_user_message(content)
                elif role == "assistant" and content:
                    out.add_assistant_message(content)
            out.add_tool_event(f"📂 Loaded session · {len(messages)} messages · Model: {get_model_label(model)}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = BijuTUI()
    app.run()


if __name__ == "__main__":
    main()
