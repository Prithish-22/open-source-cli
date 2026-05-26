"""
tui/ui/input_panel.py
User Input Area (~10 % height).

Features
────────
• Single-line text area that grows up to ~5 lines.
• Enter → send message.
• Shift+Enter → insert newline.
• Slash-command autocomplete popup.
• Placeholder text "Ask Biju anything…".
• Emits InputPanel.MessageSubmitted when the user confirms.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import TextArea, Static, Label
from textual import on

from tui.commands.registry import get_completions


class InputPanel(Widget):
    """
    Bottom input section.

    Events emitted
    ──────────────
    InputPanel.MessageSubmitted — carries the raw text the user typed
    """

    DEFAULT_CSS = """
    InputPanel {
        width: 1fr;
        height: auto;
        min-height: 5;
        max-height: 10;
        background: #0a0a1a;
        border: tall #1a2a4a;
        padding: 0 1;
    }

    InputPanel .input-label {
        color: #3a3a6c;
        height: 1;
        margin: 0 0 0 1;
    }

    InputPanel TextArea {
        background: #0a0a1a;
        color: #e8e8ff;
        border: none;
        height: auto;
        min-height: 2;
        max-height: 8;
        scrollbar-color: #1a2a4a;
    }

    InputPanel TextArea:focus {
        border: none;
    }

    InputPanel .completions-bar {
        height: 1;
        color: #2a4a6a;
        overflow: hidden;
        margin: 0 0 0 1;
    }

    InputPanel .hint-bar {
        height: 1;
        color: #2a2a4a;
        margin: 0 0 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_input", "Clear input", show=False),
    ]

    # ── Inner message ─────────────────────────────────────────────────────────

    class MessageSubmitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    # ── Compose ───────────────────────────────────────────────────────────────

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._completions: list[str] = []

    def compose(self) -> ComposeResult:
        yield Label("╭─ Message", classes="input-label")
        yield TextArea(
            "",
            id="chat-input",
            show_line_numbers=False,
            soft_wrap=True,
        )
        yield Static("", id="completions-bar", classes="completions-bar")
        yield Static(
            "Enter [dim]↵ Send[/dim]   Shift+Enter [dim]↵ Newline[/dim]   Ctrl+K [dim]Palette[/dim]   Ctrl+L [dim]Clear[/dim]",
            id="hint-bar",
            classes="hint-bar",
        )

    def on_mount(self) -> None:
        self.query_one("#chat-input", TextArea).focus()

    # ── Key handling ──────────────────────────────────────────────────────────

    def on_key(self, event) -> None:
        ta = self.query_one("#chat-input", TextArea)

        # Enter (no shift) → submit
        if event.key == "enter":
            event.stop()
            text = ta.text.strip()
            if text:
                ta.clear()
                self._update_completions("")
                self.post_message(self.MessageSubmitted(text))
            return

        # Shift+Enter → insert newline
        if event.key == "shift+enter":
            event.stop()
            ta.insert("\n")
            return

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        text = event.text_area.text
        self._update_completions(text)

    def _update_completions(self, text: str) -> None:
        bar = self.query_one("#completions-bar", Static)
        stripped = text.strip()
        if stripped.startswith("/"):
            matches = get_completions(stripped)
            if matches:
                parts = []
                for cmd in matches[:6]:
                    parts.append(f"[bold cyan]{cmd.name}[/bold cyan] [dim]{cmd.description}[/dim]")
                bar.update("  ".join(parts))
            else:
                bar.update("")
        else:
            bar.update("")

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_clear_input(self) -> None:
        self.query_one("#chat-input", TextArea).clear()
        self._update_completions("")

    def focus_input(self) -> None:
        self.query_one("#chat-input", TextArea).focus()

    def set_text(self, text: str) -> None:
        """Pre-fill the input box (e.g. from command palette)."""
        ta = self.query_one("#chat-input", TextArea)
        ta.clear()
        ta.insert(text)
