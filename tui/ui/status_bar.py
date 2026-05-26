"""
tui/ui/status_bar.py
Status Bar — always-visible bottom row (~5 % height).

Left side : clickable command shortcuts
Right side: current model name + connection status indicator
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static
from textual.reactive import reactive


class StatusBar(Widget):
    """
    Persistent bottom status row.

    Public API
    ──────────
    set_model(label)          — update the model display
    set_status(text, style)   — show a temporary status (e.g. "Generating…")
    set_autopilot(on)         — show/hide the AUTOPILOT badge
    """

    DEFAULT_CSS = """
    StatusBar {
        width: 1fr;
        height: 1;
        background: #080818;
        border-top: solid #1a1a3e;
        layout: horizontal;
        padding: 0 1;
    }

    StatusBar .sb-left {
        width: 1fr;
        color: #3a4a6a;
        height: 1;
    }

    StatusBar .sb-sep {
        width: 1;
        color: #1a1a3e;
        height: 1;
    }

    StatusBar .sb-status {
        width: auto;
        color: #00ccaa;
        height: 1;
        margin: 0 2;
    }

    StatusBar .sb-autopilot {
        width: auto;
        color: #ffaa00;
        height: 1;
        margin: 0 1;
        display: none;
    }

    StatusBar .sb-autopilot.on {
        display: block;
    }

    StatusBar .sb-model {
        width: auto;
        color: #00ccff;
        text-style: bold;
        height: 1;
    }
    """

    model_label: reactive[str] = reactive("Llama 3.3 70B")
    status_text: reactive[str] = reactive("")
    autopilot: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static(
            " [dim cyan]/commands[/dim cyan]"
            "  [dim cyan]/help[/dim cyan]"
            "  [dim cyan]/clear[/dim cyan]"
            "  [dim cyan]/model[/dim cyan]"
            "  [dim cyan]/save[/dim cyan]"
            "  [dim cyan]/load[/dim cyan]",
            classes="sb-left",
            id="sb-left",
        )
        yield Static("⚡ AUTOPILOT", classes="sb-autopilot", id="sb-autopilot")
        yield Static("", classes="sb-status", id="sb-status")
        yield Static("", classes="sb-model", id="sb-model")

    def on_mount(self) -> None:
        self._refresh_model()
        self._refresh_status()

    # ── Reactive watchers ─────────────────────────────────────────────────────

    def watch_model_label(self, value: str) -> None:
        self._refresh_model()

    def watch_status_text(self, value: str) -> None:
        self._refresh_status()

    def watch_autopilot(self, value: bool) -> None:
        ap = self.query_one("#sb-autopilot", Static)
        if value:
            ap.add_class("on")
        else:
            ap.remove_class("on")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _refresh_model(self) -> None:
        try:
            label = self.query_one("#sb-model", Static)
            label.update(f"Current Model: [bold]{self.model_label}[/bold]  ")
        except Exception:
            pass

    def _refresh_status(self) -> None:
        try:
            status = self.query_one("#sb-status", Static)
            if self.status_text:
                status.update(f"[dim]{self.status_text}[/dim]  ")
            else:
                status.update("")
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def set_model(self, label: str) -> None:
        self.model_label = label

    def set_status(self, text: str) -> None:
        self.status_text = text

    def set_autopilot(self, on: bool) -> None:
        self.autopilot = on
