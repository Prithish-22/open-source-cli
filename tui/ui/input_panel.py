"""
tui/ui/input_panel.py
User Input Area — borderless line with bright magenta prompt, direct text input, and autocomplete.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import TextArea, Static
from textual.containers import Container

from tui.commands.registry import get_completions


class ChatInput(TextArea):
    """
    Subclassed TextArea to cleanly handle Enter and Shift+Enter key events
    natively, bypassing default multiline action bindings.
    """

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            text = self.text.strip()
            if text:
                self.clear()
                # Post the submitted message up to parent InputPanel
                self.screen.query_one("InputPanel").submit_message(text)
            return

        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            self.insert("\n")
            return


class InputPanel(Widget):
    """
    Bottom input section styled exactly like the user's mockup.
    """

    DEFAULT_CSS = """
    InputPanel {
        width: 1fr;
        height: auto;
        min-height: 2;
        max-height: 10;
        background: #08080f;
        layout: vertical;
        padding: 0 1;
    }

    InputPanel .input-row {
        layout: horizontal;
        height: auto;
        min-height: 1;
        max-height: 6;
        background: transparent;
    }

    InputPanel #prompt-label {
        width: auto;
        color: #ff00ff;
        text-style: bold;
        height: 1;
        margin-right: 1;
    }

    InputPanel ChatInput {
        background: #08080f;
        color: #ffffff;
        border: none;
        height: auto;
        min-height: 1;
        max-height: 6;
        padding: 0;
        margin: 0;
    }

    InputPanel ChatInput:focus {
        border: none;
    }

    InputPanel #completions-bar {
        height: 1;
        color: #888888;
        overflow: hidden;
        margin-left: 7; /* Align exactly under input text (after 'biju › ') */
        background: transparent;
    }
    """

    class MessageSubmitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def compose(self) -> ComposeResult:
        with Container(classes="input-row"):
            yield Static("biju ›", id="prompt-label")
            yield ChatInput(
                "",
                id="chat-input",
                show_line_numbers=False,
                soft_wrap=True,
            )
        yield Static("", id="completions-bar")

    def on_mount(self) -> None:
        self.focus_input()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "chat-input":
            self._update_completions(event.text_area.text)

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

    def submit_message(self, text: str) -> None:
        """Called by ChatInput child when Enter is pressed."""
        self._update_completions("")
        self.post_message(self.MessageSubmitted(text))

    def focus_input(self) -> None:
        self.query_one("#chat-input", ChatInput).focus()

    def set_text(self, text: str) -> None:
        ta = self.query_one("#chat-input", ChatInput)
        ta.clear()
        ta.insert(text)
        self._update_completions(text)
