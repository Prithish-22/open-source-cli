"""
tui/ui/status_bar.py
Status Bar — persistent bottom row matching the mockup layout.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from textual.reactive import reactive


class StatusBar(Widget):
    """
    Persistent bottom status row in simple plain text.
    """

    DEFAULT_CSS = """
    StatusBar {
        width: 1fr;
        height: 1;
        background: #08080f;
        layout: horizontal;
        padding: 0 1;
    }

    StatusBar .sb-left {
        width: 1fr;
        color: #ffffff;
        height: 1;
        text-style: bold;
    }

    StatusBar .sb-model {
        width: auto;
        color: #ffffff;
        height: 1;
        text-style: bold;
    }
    """

    model_label: reactive[str] = reactive("Llama 3.3 70B")
    status_text: reactive[str] = reactive("")
    autopilot: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static(
            "Commands /   ?Help",
            classes="sb-left",
            id="sb-left",
        )
        yield Static("", classes="sb-model", id="sb-model")

    def on_mount(self) -> None:
        self._refresh_model()

    # ── Reactive watchers ─────────────────────────────────────────────────────

    def watch_model_label(self, value: str) -> None:
        self._refresh_model()

    def watch_status_text(self, value: str) -> None:
        pass

    def watch_autopilot(self, value: bool) -> None:
        pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _refresh_model(self) -> None:
        try:
            label = self.query_one("#sb-model", Static)
            label.update(f"{self.model_label}  ")
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def set_model(self, label: str) -> None:
        self.model_label = label

    def set_status(self, text: str) -> None:
        pass

    def set_autopilot(self, on: bool) -> None:
        pass
