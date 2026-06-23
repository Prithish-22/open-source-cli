"""
tui/ui/popups.py
Modal popups for the Biju TUI:
  • CommandPaletteModal  — Ctrl+K searchable command list
  • ModelSelectorModal   — Ctrl+M / /model category-tabbed model picker
  • SessionBrowserModal  — /load session selector
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable, Input, Label,
    ListItem, ListView, Static, TabbedContent, TabPane,
)
from textual import on

from tui.commands.registry import COMMANDS, CommandDef
from tui.models.config import AGENT_MODELS_CATEGORIZED, get_model_label
from tui.storage.session import list_sessions


# ─────────────────────────────────────────────────────────────────────────────
# Command Palette
# ─────────────────────────────────────────────────────────────────────────────

class CommandPaletteModal(ModalScreen[str | None]):
    """
    Full-screen command palette (Ctrl+K).
    Type to filter commands; Enter to select; Escape to dismiss.
    """

    DEFAULT_CSS = """
    CommandPaletteModal {
        align: center middle;
    }

    CommandPaletteModal > .cp-container {
        width: 70;
        max-height: 30;
        background: #0e0e22;
        border: double #00ccff;
        padding: 1 2;
    }

    CommandPaletteModal .cp-title {
        color: #00ccff;
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }

    CommandPaletteModal Input {
        background: #0a0a1a;
        color: #e0e0ff;
        border: tall #1a2a4a;
        margin-bottom: 1;
    }

    CommandPaletteModal ListView {
        background: #0e0e22;
        height: auto;
        max-height: 20;
    }

    CommandPaletteModal ListItem {
        color: #c0c0e0;
        padding: 0 1;
    }

    CommandPaletteModal ListItem:hover, CommandPaletteModal ListItem.-highlighted {
        background: #1a2a4a;
        color: #00ccff;
    }
    """

    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]

    def compose(self) -> ComposeResult:
        with Static(classes="cp-container"):
            yield Label("⌨  Command Palette", classes="cp-title")
            yield Input(placeholder="Search commands…", id="cp-search")
            yield ListView(id="cp-list")

    def on_mount(self) -> None:
        self._all_cmds = COMMANDS
        self._populate(COMMANDS)
        self.query_one("#cp-search", Input).focus()

    def _populate(self, cmds: list[CommandDef]) -> None:
        lv = self.query_one("#cp-list", ListView)
        lv.clear()
        for cmd in cmds:
            item = ListItem(
                Label(f"[bold cyan]{cmd.name}[/bold cyan]  [dim]{cmd.description}[/dim]")
            )
            item.data = cmd.name  # type: ignore[attr-defined]
            lv.append(item)
        if cmds:
            lv.index = 0

    @on(Input.Changed, "#cp-search")
    def _filter(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if not query:
            self._populate(self._all_cmds)
        else:
            filtered = [
                c for c in self._all_cmds
                if query in c.name or query in c.description.lower()
            ]
            self._populate(filtered)


    @on(Input.Changed, "#ms-search")
    def _filter_models(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        # This is a bit tricky with TabbedContent, so we'll just highlight the first match
        # or we could filter the lists inside. For simplicity, let's filter the lists.
        for category, models in AGENT_MODELS_CATEGORIZED.items():
            safe_cat = category[:8].replace(' ', '-').replace('&','n')
            try:
                lv = self.query_one(f"#lv-{safe_cat}", ListView)
                lv.clear()
                for model_id, desc in models:
                    if query in model_id.lower() or query in desc.lower() or query in get_model_label(model_id).lower():
                        label_text = get_model_label(model_id)
                        active = "  [bold yellow](active)[/bold yellow]" if model_id == self._current else ""
                        item = ListItem(
                            Static(
                                f"[bold white] {label_text}[/bold white]{active}\n"
                                f"  [dim] ID: {model_id}[/dim]\n"
                                f"  [italic #5a5a8a] ❯ {desc}[/italic #5a5a8a]"
                            )
                        )
                        item.data = model_id
                        lv.append(item)
            except:
                pass

    def on_key(self, event) -> None:
        if event.key == "enter":
            lv = self.query_one("#cp-list", ListView)
            if lv.highlighted_child is not None:
                name = getattr(lv.highlighted_child, "data", None)
                self.dismiss(name)

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        name = getattr(event.item, "data", None)
        self.dismiss(name)


# ─────────────────────────────────────────────────────────────────────────────
# Model Selector
# ─────────────────────────────────────────────────────────────────────────────

class ModelSelectorModal(ModalScreen[str | None]):
    """
    Tabbed model selector (Ctrl+M / /model).
    Returns the selected model ID or None if cancelled.
    """

    DEFAULT_CSS = """
    ModelSelectorModal {
        align: center middle;
    }

    ModelSelectorModal > .ms-container {
        width: 80;
        max-height: 35;
        background: #0e0e22;
        border: double #9944ff;
        padding: 1 2;
    }

    ModelSelectorModal .ms-title {
        color: #9944ff;
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }

    ModelSelectorModal .ms-hint {
        color: #3a3a6a;
        text-align: center;
        margin-bottom: 1;
    }

    ModelSelectorModal TabbedContent {
        height: auto;
        max-height: 28;
    }

    ModelSelectorModal ListView {
        background: #0e0e22;
        height: auto;
        max-height: 22;
    }

    ModelSelectorModal ListItem {
        color: #c0c0e0;
        padding: 0 2;
        height: 4;
        border-bottom: solid #1a1a3e;
    }

    ModelSelectorModal ListItem.-highlighted {
        background: #1a1a3e;
        color: #00ccff;
        text-style: bold;
    }

    ModelSelectorModal TabbedContent {
        margin-top: 1;
    }

    ModelSelectorModal TabPane {
        padding: 0;
    }
    """

    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]

    def __init__(self, current_model: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._current = current_model

    def compose(self) -> ComposeResult:
        with Static(classes="ms-container"):
            yield Label("✦  Select AI Model", classes="ms-title")
            yield Input(placeholder="Search models...", id="ms-search")
            yield Label(
                "[dim]Tab to switch categories · Enter to select · Esc to cancel[/dim]",
                classes="ms-hint",
            )
            with TabbedContent(id="ms-tabs"):
                for category, models in AGENT_MODELS_CATEGORIZED.items():
                    with TabPane(category, id=f"tab-{category[:8].replace(' ', '-').replace('&','n')}"):
                        lv = ListView(id=f"lv-{category[:8].replace(' ', '-').replace('&','n')}")
                        for model_id, desc in models:
                            label_text = get_model_label(model_id)
                            active = "  [bold yellow](active)[/bold yellow]" if model_id == self._current else ""
                            item = ListItem(
                                Static(
                                    f"[bold white] {label_text}[/bold white]{active}\n"
                                    f"  [dim] ID: {model_id}[/dim]\n"
                                    f"  [italic #5a5a8a] ❯ {desc}[/italic #5a5a8a]"
                                )
                            )
                            item.data = model_id  # type: ignore[attr-defined]
                            lv.append(item)
                        yield lv


    @on(Input.Changed, "#ms-search")
    def _filter_models(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        # This is a bit tricky with TabbedContent, so we'll just highlight the first match
        # or we could filter the lists inside. For simplicity, let's filter the lists.
        for category, models in AGENT_MODELS_CATEGORIZED.items():
            safe_cat = category[:8].replace(' ', '-').replace('&','n')
            try:
                lv = self.query_one(f"#lv-{safe_cat}", ListView)
                lv.clear()
                for model_id, desc in models:
                    if query in model_id.lower() or query in desc.lower() or query in get_model_label(model_id).lower():
                        label_text = get_model_label(model_id)
                        active = "  [bold yellow](active)[/bold yellow]" if model_id == self._current else ""
                        item = ListItem(
                            Static(
                                f"[bold white] {label_text}[/bold white]{active}\n"
                                f"  [dim] ID: {model_id}[/dim]\n"
                                f"  [italic #5a5a8a] ❯ {desc}[/italic #5a5a8a]"
                            )
                        )
                        item.data = model_id
                        lv.append(item)
            except:
                pass

    def on_key(self, event) -> None:
        if event.key == "enter":
            # Find the active list view
            for lv in self.query(ListView):
                if lv.display and lv.highlighted_child is not None:
                    model_id = getattr(lv.highlighted_child, "data", None)
                    self.dismiss(model_id)
                    return

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        model_id = getattr(event.item, "data", None)
        self.dismiss(model_id)


# ─────────────────────────────────────────────────────────────────────────────
# Session Browser
# ─────────────────────────────────────────────────────────────────────────────

class SessionBrowserModal(ModalScreen[str | None]):
    """Session loader. Returns the path of the chosen session or None."""

    DEFAULT_CSS = """
    SessionBrowserModal {
        align: center middle;
    }

    SessionBrowserModal > .sb-container {
        width: 75;
        max-height: 30;
        background: #0e0e22;
        border: double #00aa66;
        padding: 1 2;
    }

    SessionBrowserModal .sb-title {
        color: #00aa66;
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }

    SessionBrowserModal DataTable {
        height: auto;
        max-height: 22;
        background: #0e0e22;
    }
    """

    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]

    def compose(self) -> ComposeResult:
        with Static(classes="sb-container"):
            yield Label("💾  Load Session", classes="sb-title")
            yield DataTable(id="session-table", cursor_type="row")
            yield Label("[dim]Enter to load · Esc to cancel[/dim]", id="sb-hint")

    def on_mount(self) -> None:
        table = self.query_one("#session-table", DataTable)
        table.add_columns("Title", "Date", "Messages", "Model")
        sessions = list_sessions()
        if not sessions:
            table.add_row("No saved sessions found", "", "", "")
            self._sessions = []
        else:
            self._sessions = sessions
            for s in sessions:
                table.add_row(
                    s["title"][:35],
                    s["modified"],
                    str(s["message_count"]),
                    s["model"].split("/")[-1],
                )
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = event.cursor_row
        if self._sessions and 0 <= idx < len(self._sessions):
            self.dismiss(self._sessions[idx]["path"])
        else:
            self.dismiss(None)
