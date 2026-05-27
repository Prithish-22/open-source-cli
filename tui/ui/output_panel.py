"""
tui/ui/output_panel.py
AI Output Area — scrollable rich-markdown display with syntax-highlighted
code blocks. Occupies ~65 % of the vertical space.

Design principles
─────────────────
• Each message is rendered as a Rich Markdown string inside a Textual
  RichLog widget so scrollback is unlimited.
• A thin cyan left-border separates consecutive messages.
• The panel auto-scrolls to the latest response.
• A "typing" animation is shown while the AI is generating.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from textual.app import ComposeResult
from textual.widgets import Static
from textual.widget import Widget
from textual.reactive import reactive

if TYPE_CHECKING:
    pass


# ── Single message bubble ─────────────────────────────────────────────────────

class MessageBubble(Widget):
    """Renders one complete message (user or assistant) as a Rich Panel."""

    DEFAULT_CSS = """
    MessageBubble {
        width: 1fr;
        height: auto;
        margin: 0 1 1 1;
    }
    """

    def __init__(self, role: str, content: str, timestamp: str = "") -> None:
        super().__init__()
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now().strftime("%H:%M")

    def render(self) -> Panel:
        if self.role == "user":
            title = f"[bold cyan]You[/bold cyan]  [dim]{self.timestamp}[/dim]"
            border = "cyan"
            body: Markdown | Text = Text(self.content, style="white")
        elif self.role == "assistant":
            title = f"[bold magenta]✦ Biju[/bold magenta]  [dim]{self.timestamp}[/dim]"
            border = "magenta"
            body = Markdown(self.content, code_theme="monokai")
        else:
            # System / tool result
            title = f"[bold yellow]⚙ System[/bold yellow]  [dim]{self.timestamp}[/dim]"
            border = "yellow"
            body = Text(self.content, style="dim yellow")

        return Panel(body, title=title, border_style=border, padding=(0, 1))


# ── Streaming token display ───────────────────────────────────────────────────

class StreamingMessage(Widget):
    """
    Shown while the AI is streaming a response.
    Accumulates tokens and re-renders on each update.
    """

    DEFAULT_CSS = """
    StreamingMessage {
        width: 1fr;
        height: auto;
        margin: 0 1 1 1;
    }
    """

    text: reactive[str] = reactive("", layout=True)

    def render(self) -> Panel:
        cursor = "[blink bold cyan]█[/]"
        body = Markdown(self.text + cursor if self.text else "", code_theme="monokai") \
               if self.text else Text("  ", style="dim")
        return Panel(
            body,
            title="[bold magenta]✦ Biju[/bold magenta]  [dim cyan]●[/dim cyan] [dim]streaming…[/dim]",
            border_style="magenta",
            padding=(0, 1),
        )

    def append(self, token: str) -> None:
        self.text += token


# ── Output panel container ────────────────────────────────────────────────────

class OutputPanel(Widget):
    """
    Main AI Output Area (~65 % height).

    Public API
    ──────────
    add_user_message(text)          — append a user bubble
    add_assistant_message(text)     — append a finished AI response bubble
    start_streaming()               — show streaming bubble
    append_stream_token(token)      — add token to streaming bubble
    finish_streaming(final_text)    — replace streaming bubble with final
    add_tool_event(text)            — show a tool-call notification
    clear()                         — wipe all messages
    """

    DEFAULT_CSS = """
    OutputPanel {
        width: 1fr;
        height: 1fr;
        background: #0d0d1a;
        border: tall #1a1a3e;
        overflow-y: auto;
        padding: 0 0;
    }

    OutputPanel > .empty-hint {
        color: #3a3a5c;
        text-align: center;
        margin-top: 4;
        padding: 2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._streaming_widget: StreamingMessage | None = None
        self._has_messages = False

    def compose(self) -> ComposeResult:
        yield Static(
            "[dim]╭──────────────────────────────────────────╮\n"
            "│  Ask Biju anything to start the session   │\n"
            "│  Type [bold cyan]/help[/bold cyan] to see all available commands │\n"
            "╰──────────────────────────────────────────╯[/dim]",
            classes="empty-hint",
            id="empty-hint",
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def add_user_message(self, text: str) -> None:
        self._remove_empty_hint()
        bubble = MessageBubble("user", text)
        self.mount(bubble)
        self.scroll_end(animate=True)

    def add_assistant_message(self, text: str) -> None:
        self._remove_empty_hint()
        bubble = MessageBubble("assistant", text)
        self.mount(bubble)
        self.scroll_end(animate=True)

    def add_tool_event(self, text: str) -> None:
        self._remove_empty_hint()
        bubble = MessageBubble("system", text)
        self.mount(bubble)
        self.scroll_end(animate=True)

    def start_streaming(self) -> None:
        self._remove_empty_hint()
        self._streaming_widget = StreamingMessage()
        self.mount(self._streaming_widget)
        self.scroll_end(animate=False)

    def append_stream_token(self, token: str) -> None:
        if self._streaming_widget:
            self._streaming_widget.append(token)
            self.scroll_end(animate=False)

    def finish_streaming(self, final_text: str) -> None:
        if self._streaming_widget:
            self._streaming_widget.remove()
            self._streaming_widget = None
        if final_text.strip():
            self.add_assistant_message(final_text)

    def clear_messages(self) -> None:
        """Remove all message widgets and restore the empty hint."""
        for child in list(self.children):
            child.remove()
        self._has_messages = False
        self._streaming_widget = None
        hint = Static(
            "[dim]╭──────────────────────────────────────────╮\n"
            "│  Ask Biju anything to start the session   │\n"
            "│  Type [bold cyan]/help[/bold cyan] to see all available commands │\n"
            "╰──────────────────────────────────────────╯[/dim]",
            classes="empty-hint",
            id="empty-hint",
        )
        self.mount(hint)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _remove_empty_hint(self) -> None:
        if not self._has_messages:
            hint = self.query_one("#empty-hint", expect_type=Static)
            hint.remove()
            self._has_messages = True
