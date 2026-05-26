"""
tui/commands/registry.py
All slash-command definitions and their handler dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any

# ── Command metadata ──────────────────────────────────────────────────────────

@dataclass
class CommandDef:
    name: str          # e.g. "/help"
    description: str
    usage: str = ""    # e.g. "/model [id]"
    aliases: list[str] = field(default_factory=list)


# ── Master command registry ───────────────────────────────────────────────────
COMMANDS: list[CommandDef] = [
    CommandDef("/help",      "Show this help menu",                         "/help"),
    CommandDef("/clear",     "Clear the chat history display",              "/clear",     ["/cls"]),
    CommandDef("/model",     "Open the interactive model selector",         "/model"),
    CommandDef("/update",    "Update Biju to the latest version and restart", "/update"),
    CommandDef("/commands",  "List all available commands",                 "/commands"),
    CommandDef("/new",       "Start a fresh conversation",                  "/new"),
    CommandDef("/save",      "Save current session to disk",                "/save [title]"),
    CommandDef("/load",      "Load a previously saved session",             "/load"),
    CommandDef("/history",   "Show message count and token estimate",       "/history"),
    CommandDef("/autopilot", "Toggle autopilot (skip all approvals)",       "/autopilot"),
    CommandDef("/allow-all", "Enable full autonomy mode",                   "/allow-all"),
    CommandDef("/init",      "Initialize biju-instructions.md here",        "/init"),
    CommandDef("/setkey",    "Add or update API keys",                      "/setkey"),
    CommandDef("/config",    "Reset / delete saved configuration",          "/config"),
    CommandDef("/undo",      "Restore last file Biju modified",             "/undo"),
    CommandDef("/add-dir",   "Add a trusted directory for Biju",            "/add-dir"),
    CommandDef("/exit",      "Quit the TUI",                               "/exit",      ["/quit"]),
]

# Build a quick lookup dict: "/cmd" → CommandDef
COMMAND_MAP: dict[str, CommandDef] = {}
for _cmd in COMMANDS:
    COMMAND_MAP[_cmd.name] = _cmd
    for _alias in _cmd.aliases:
        COMMAND_MAP[_alias] = _cmd


def get_completions(prefix: str) -> list[CommandDef]:
    """Return commands whose name starts with *prefix*."""
    prefix = prefix.lower()
    seen = set()
    results = []
    for cmd in COMMANDS:
        if cmd.name.startswith(prefix) and cmd.name not in seen:
            results.append(cmd)
            seen.add(cmd.name)
    return results
