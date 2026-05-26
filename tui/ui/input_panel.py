"""
tui/ui/input_panel.py
User Input Area — borderless line with bright magenta prompt and direct text input.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import TextArea, Static


class InputPanel(Widget):
    """
    Bottom input section styled exactly like the user's mockup.
    """

    DEFAULT_CSS = """
    InputPanel {
        width: 1fr;
        height: auto;
        min-height: 2;
        max-height: 8;
        background: #08080f;
        layout: horizontal;
        padding: 0 1;
    }

    InputPanel #prompt-label {
        width: auto;
        color: #ff00ff;
        text-style: bold;
        height: 1;
        margin-right: 1;
    }

    InputPanel TextArea {
        background: #08080f;
        color: #ffffff;
        border: none;
        height: auto;
        min-height: 1;
        max-height: 6;
        padding: 0;
        margin: 0;
    }

    InputPanel TextArea:focus {
        border: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_input", "Clear input", show=False),
    ]

    class MessageSubmitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def compose(self) -> ComposeResult:
        yield Static("biju ›", id="prompt-label")
        yield TextArea(
            "",
            id="chat-input",
            show_line_numbers=False,
            soft_wrap=True,
        )

    def on_mount(self) -> None:
        self.query_one("#chat-input", TextArea).focus()

    def on_key(self, event) -> None:
        ta = self.query_one("#chat-input", TextArea)

        if event.key == "enter":
            event.stop()
            text = ta.text.strip()
            if text:
                ta.clear()
                self.post_message(self.MessageSubmitted(text))
            return

        if event.key == "shift+enter":
            event.stop()
            ta.insert("\n")
            return

    def action_clear_input(self) -> None:
        self.query_one("#chat-input", TextArea).clear()

    def focus_input(self) -> None:
        self.query_one("#chat-input", TextArea).focus()

    def set_text(self, text: str) -> None:
        ta = self.query_one("#chat-input", TextArea)
        ta.clear()
        ta.insert(text)
