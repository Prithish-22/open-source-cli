"""
tui/ui/output_panel.py
AI Output Area — scrollable clean stream with syntax highlighted markdown.
"""

from __future__ import annotations

from datetime import datetime
from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static
from textual.widget import Widget
from textual.reactive import reactive


class MessageBubble(Widget):
    """Renders one message inline with clean, borderless layouts matching the mockup."""

    DEFAULT_CSS = """
    MessageBubble {
        width: 1fr;
        height: auto;
        margin: 1 1;
    }
    """

    def __init__(self, role: str, content: str) -> None:
        super().__init__()
        self.role = role
        self.content = content

    def render(self):
        if self.role == "user":
            # biju › hi
            return Text.assemble(
                ("biju › ", "bright_magenta bold"),
                (self.content, "white bold")
            )
        elif self.role == "assistant":
            # markdown response directly
            return Markdown(self.content, code_theme="monokai")
        else:
            # tool execution or system event
            return Text(f"⚙ {self.content}", style="dim yellow")


class StreamingMessage(Widget):
    """Shown while the AI is streaming a response."""

    DEFAULT_CSS = """
    StreamingMessage {
        width: 1fr;
        height: auto;
        margin: 1 1;
    }
    """

    text: reactive[str] = reactive("", layout=True)

    def render(self):
        cursor = "[blink bold cyan]█[/]"
        return Markdown(self.text + cursor if self.text else "", code_theme="monokai") \
               if self.text else Text("...", style="dim")

    def append(self, token: str) -> None:
        self.text += token


class OutputPanel(Widget):
    """
    Main AI Output Area (~65 % height).
    """

    DEFAULT_CSS = """
    OutputPanel {
        width: 1fr;
        height: 1fr;
        background: #08080f;
        overflow-y: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._streaming_widget: StreamingMessage | None = None

    def compose(self) -> ComposeResult:
        import os
        from tui.updater import CURRENT_VERSION
        from tui.models.config import get_model_label, DEFAULT_MODEL
        
        has_instructions = os.path.exists(os.path.join(os.getcwd(), "biju-instructions.md"))
        instr_status = (
            "[bold green]●[/bold green] [dim]biju-instructions.md loaded[/dim]"
            if has_instructions
            else "[bold yellow]●[/bold yellow] [dim]No instructions — run [bold]/init[/bold] to generate one[/dim]"
        )
        logo = (
            "\n"
            "  [bold cyan]██████╗ ██╗     ██╗██╗   ██╗[/bold cyan]\n"
            "  [bold cyan]██╔══██╗██║     ██║██║   ██║[/bold cyan]\n"
            "  [bold cyan]██████╔╝██║     ██║██║   ██║[/bold cyan]  [bold white]Biju CLI[/bold white]  [dim]v" + CURRENT_VERSION + "[/dim]\n"
            "  [bold magenta]██╔══██╗██║██   ██║██║   ██║[/bold magenta]  [dim]Autonomous AI Engineer[/dim]\n"
            "  [bold magenta]██████╔╝██║╚█████╔╝╚██████╔╝[/bold magenta]  [dim]by Prithish[/dim]\n"
            "  [dim]╚═════╝ ╚═╝ ╚════╝  ╚═════╝[/dim]\n\n"
            f"  {instr_status}\n"
            f"  [bold blue]●[/bold blue] [dim]Model: Llama 3.3 70B  ·  Type [bold]/help[/bold] to see all commands[/dim]\n"
        )
        yield Static(logo, id="startup-logo")

    def add_user_message(self, text: str) -> None:
        bubble = MessageBubble("user", text)
        self.mount(bubble)
        self.scroll_end(animate=True)

    def add_assistant_message(self, text: str) -> None:
        bubble = MessageBubble("assistant", text)
        self.mount(bubble)
        self.scroll_end(animate=True)

    def add_tool_event(self, text: str) -> None:
        bubble = MessageBubble("system", text)
        self.mount(bubble)
        self.scroll_end(animate=True)

    def start_streaming(self) -> None:
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
        for child in list(self.children):
            if child.id != "startup-logo":
                child.remove()
        self._streaming_widget = None
