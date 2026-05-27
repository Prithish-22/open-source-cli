"""
tui/ui/permission_panel.py
Permission Panel — middle section (~15 % height).

Displays a structured permission request when the AI wants to use a tool
that modifies the system (run_command, write_file, delete, internet, etc.).

The panel is HIDDEN by default and only shown when a permission is pending.

Events emitted
──────────────
PermissionPanel.PermissionResponse  — posted when user presses Y / N / A
"""

from __future__ import annotations

from dataclasses import dataclass
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Label, Static


# ── Permission request data ───────────────────────────────────────────────────

@dataclass
class PermissionRequest:
    tool: str          # e.g. "File Editor"
    action: str        # e.g. "Modify main.py"
    command: str = ""  # raw command / path if applicable
    risk: str = "medium"  # "low" | "medium" | "high"


# ── Permission panel widget ───────────────────────────────────────────────────

class PermissionPanel(Widget):
    """
    Collapsible permission panel. Hidden when no permission is pending.

    Usage
    ─────
    panel.request_permission(PermissionRequest(...))
        → shows the panel; emits PermissionResponse on user action
    """

    DEFAULT_CSS = """
    PermissionPanel {
        width: 1fr;
        height: auto;
        background: #120a00;
        border: tall #c47a00;
        display: none;
        padding: 0 2;
    }

    PermissionPanel.visible {
        display: block;
    }

    PermissionPanel .perm-header {
        color: #ffaa00;
        text-style: bold;
        margin: 1 0 0 0;
    }

    PermissionPanel .perm-tool {
        color: #ffd080;
        margin: 0 0 0 2;
    }

    PermissionPanel .perm-action {
        color: #ffe0a0;
        margin: 0 0 0 2;
    }

    PermissionPanel .perm-command {
        color: #888;
        margin: 0 0 1 4;
    }

    PermissionPanel .perm-buttons {
        layout: horizontal;
        height: auto;
        margin: 0 0 1 0;
    }

    PermissionPanel Button {
        min-width: 12;
        margin: 0 1 0 0;
    }

    PermissionPanel #btn-allow {
        background: #006633;
        color: #00ff88;
        border: tall #00ff88;
    }

    PermissionPanel #btn-allow:hover {
        background: #00884a;
    }

    PermissionPanel #btn-deny {
        background: #660000;
        color: #ff4444;
        border: tall #ff4444;
    }

    PermissionPanel #btn-deny:hover {
        background: #880000;
    }

    PermissionPanel #btn-always {
        background: #003366;
        color: #44aaff;
        border: tall #44aaff;
    }

    PermissionPanel #btn-always:hover {
        background: #004488;
    }
    """

    # ── Inner message class ───────────────────────────────────────────────────

    class PermissionResponse(Message):
        """Posted when the user responds to a permission request."""

        def __init__(self, choice: str, request: PermissionRequest) -> None:
            super().__init__()
            self.choice = choice      # "allow" | "deny" | "always"
            self.request = request

    # ── Widget lifecycle ──────────────────────────────────────────────────────

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_request: PermissionRequest | None = None

    def compose(self) -> ComposeResult:
        yield Label("", id="perm-header", classes="perm-header")
        yield Label("", id="perm-tool",   classes="perm-tool")
        yield Label("", id="perm-action", classes="perm-action")
        yield Label("", id="perm-cmd",    classes="perm-command")
        with Static(classes="perm-buttons"):
            yield Button("⏎ [Y] Allow",        id="btn-allow",  variant="success")
            yield Button("✗ [N] Deny",          id="btn-deny",   variant="error")
            yield Button("★ [A] Always Allow",  id="btn-always", variant="primary")

    # ── Public API ────────────────────────────────────────────────────────────

    def request_permission(self, req: PermissionRequest) -> None:
        """Show the panel and populate it with the given request."""
        self._current_request = req

        risk_emoji = {"low": "🟡", "medium": "⚠", "high": "🔴"}.get(req.risk, "⚠")
        self.query_one("#perm-header", Label).update(
            f"[bold yellow]{risk_emoji}  Permission Required[/bold yellow]"
        )
        self.query_one("#perm-tool",   Label).update(f"[dim]Tool:[/dim]   [bold white]{req.tool}[/bold white]")
        self.query_one("#perm-action", Label).update(f"[dim]Action:[/dim] [bold white]{req.action}[/bold white]")
        cmd_label = self.query_one("#perm-cmd", Label)
        if req.command:
            cmd_label.update(f"[dim]  $ {req.command}[/dim]")
            cmd_label.display = True
        else:
            cmd_label.display = False

        self.add_class("visible")
        self.display = True

    def hide_panel(self) -> None:
        """Dismiss the panel after user responds."""
        self._current_request = None
        self.remove_class("visible")
        self.display = False

    # ── Button handlers ───────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._current_request is None:
            return
        choice_map = {
            "btn-allow":  "allow",
            "btn-deny":   "deny",
            "btn-always": "always",
        }
        choice = choice_map.get(event.button.id or "", "deny")
        self.post_message(self.PermissionResponse(choice, self._current_request))
        self.hide_panel()
