"""
tui/updater.py
──────────────
Update checker + one-click /update command for Biju.

How it works
────────────
On startup, a background thread silently queries the GitHub Releases API.
If a newer version is found it's cached in ~/.biju_update_cache.json
(TTL: 6 hours) so GitHub is only hit once per session.

/update command
───────────────
Auto-detects how Biju was installed:
  1. Git clone  → git pull origin main  +  pip install -e .
  2. Pip package → pip install --upgrade biju-cli
  3. NPM package → npm update -g biju-cli

After updating, os.execv() restarts the current process cleanly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ── Version constants ─────────────────────────────────────────────────────────
CURRENT_VERSION = "2.0.8"
GITHUB_REPO     = "Prithish-22/open-source-cli"
GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CACHE_FILE      = Path.home() / ".biju_update_cache.json"
CACHE_TTL_HOURS = 6


# ── Public result holder ──────────────────────────────────────────────────────

class UpdateResult:
    """Holds the result of the update check."""

    def __init__(self) -> None:
        self.checked    = False
        self.has_update = False
        self.latest     = CURRENT_VERSION
        self.url        = f"https://github.com/{GITHUB_REPO}/releases"

    def __bool__(self) -> bool:
        return self.has_update


# ── Version helpers ───────────────────────────────────────────────────────────

def _parse_version(tag: str) -> tuple[int, ...]:
    clean = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in clean.split("."))
    except ValueError:
        return (0,)


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS):
            return data
    except Exception:
        pass
    return None


def _save_cache(latest: str, url: str) -> None:
    try:
        CACHE_FILE.write_text(
            json.dumps({
                "latest":    latest,
                "url":       url,
                "cached_at": datetime.now().isoformat(),
            }),
            encoding="utf-8",
        )
    except Exception:
        pass


# ── GitHub API ────────────────────────────────────────────────────────────────

def _fetch_latest() -> tuple[str, str]:
    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={
            "Accept":     "application/vnd.github+json",
            "User-Agent": f"biju-cli/{CURRENT_VERSION}",
        },
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
    return data["tag_name"], data["html_url"]


def _do_check(result: UpdateResult) -> None:
    try:
        cached = _load_cache()
        if cached:
            latest_tag, url = cached["latest"], cached["url"]
        else:
            latest_tag, url = _fetch_latest()
            _save_cache(latest_tag, url)

        result.latest     = latest_tag.lstrip("v")
        result.url        = url
        result.has_update = _parse_version(latest_tag) > _parse_version(CURRENT_VERSION)
        result.checked    = True
    except Exception:
        result.checked = True


def check_for_updates() -> tuple[UpdateResult, threading.Thread]:
    """
    Kick off a non-blocking background update check.
    Returns (UpdateResult, thread) immediately.
    """
    result = UpdateResult()
    thread = threading.Thread(target=_do_check, args=(result,), daemon=True)
    thread.start()
    return result, thread


# ── Install method detector ───────────────────────────────────────────────────

def _detect_install_method() -> str:
    """
    Auto-detect how Biju was installed.
    Returns: 'git' | 'pip' | 'npm'
    """
    # Walk up from this file looking for a .git folder
    here = Path(__file__).resolve()
    for parent in (here.parent, here.parent.parent, here.parent.parent.parent):
        if (parent / ".git").exists():
            return "git"

    # Check npm global installs
    try:
        r = subprocess.run(
            ["npm", "list", "-g", "biju-cli", "--depth=0"],
            capture_output=True, text=True, timeout=5,
        )
        if "biju-cli" in r.stdout:
            return "npm"
    except Exception:
        pass

    return "pip"


def _get_git_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in (here.parent, here.parent.parent, here.parent.parent.parent):
        if (parent / ".git").exists():
            return parent
    return None


# ── Step dataclass ────────────────────────────────────────────────────────────

class UpdateStep:
    def __init__(self, label: str) -> None:
        self.label  = label
        self.status = "pending"   # pending | running | done | error
        self.output = ""


# ── Core update runner ────────────────────────────────────────────────────────

def do_update(progress_cb=None) -> tuple[bool, str]:
    """
    Run the correct update commands for the detected install method.

    progress_cb(step: UpdateStep) is called after each step changes state.
    Returns (success: bool, error_message_or_method: str).
    """
    method = _detect_install_method()

    if method == "git":
        repo_root = _get_git_root()
        if repo_root is None:
            return False, "Could not locate the git repository root."
        steps = [
            UpdateStep("git pull origin main"),
        ]
        cmds = [
            # Editable installs (-e) read source directly, so git pull is all that's needed.
            # pip install -e . is NOT repeated — it would fail if pyproject.toml is missing
            # and is unnecessary since the live source is already linked.
            (["git", "pull", "origin", "main"], str(repo_root)),
        ]
    elif method == "npm":
        steps = [UpdateStep("npm update -g biju-cli")]
        cmds  = [(["npm", "update", "-g", "biju-cli"], None)]
    else:  # pip
        steps = [UpdateStep("pip install --upgrade biju-cli")]
        cmds  = [([sys.executable, "-m", "pip", "install", "--upgrade", "biju-cli"], None)]

    for step, (cmd, cwd) in zip(steps, cmds):
        step.status = "running"
        if progress_cb:
            progress_cb(step)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=cwd,
            )
            step.output = (proc.stdout + proc.stderr).strip()
            if proc.returncode == 0:
                step.status = "done"
            else:
                step.status = "error"
                if progress_cb:
                    progress_cb(step)
                return False, (
                    f"Step failed: `{' '.join(cmd)}`\n\n"
                    f"{step.output[:500]}"
                )
        except subprocess.TimeoutExpired:
            step.status = "error"
            return False, f"Timed out: `{' '.join(cmd)}`"
        except FileNotFoundError:
            step.status = "error"
            return False, f"Command not found: `{cmd[0]}` — make sure it's on PATH."
        except Exception as exc:
            step.status = "error"
            return False, f"Unexpected error: {exc}"

        if progress_cb:
            progress_cb(step)

    # Bust the update cache so startup re-checks next time
    try:
        CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    return True, method


def restart_process() -> None:
    """Replace the current process with a fresh identical one (cross-platform)."""
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ── Classic CLI /update handler ───────────────────────────────────────────────

def run_update_classic(console) -> None:
    """
    Full /update flow for the classic (prompt_toolkit) CLI.
    Blocking — runs in-process. Restarts on success.
    """
    import time
    from rich.panel import Panel

    method = _detect_install_method()
    labels = {
        "git": "git pull origin main",
        "pip": "pip install --upgrade biju-cli",
        "npm": "npm update -g biju-cli",
    }

    console.print(Panel(
        f"[dim]Install method:[/dim] [bold cyan]{labels[method]}[/bold cyan]",
        title="[bold cyan]⬆  Updating Biju[/bold cyan]",
        border_style="cyan",
        expand=False,
    ))

    def progress_cb(step: UpdateStep) -> None:
        icons  = {"running": "[cyan]⠋[/cyan]", "done": "[green]✓[/green]", "error": "[red]✗[/red]"}
        icon   = icons.get(step.status, "○")
        console.print(f"  {icon} {step.label}")
        if step.status == "error" and step.output:
            console.print(f"    [dim red]{step.output[:300]}[/dim red]")

    success, result = do_update(progress_cb=progress_cb)

    if success:
        console.print()
        console.print(Panel(
            "[bold green]✓ Update complete![/bold green]\n"
            "[dim]Restarting Biju in 2 seconds…[/dim]",
            border_style="green", expand=False,
        ))
        time.sleep(2)
        restart_process()
    else:
        console.print()
        console.print(Panel(
            f"[bold red]✗ Update failed[/bold red]\n\n{result}",
            border_style="red", expand=False,
        ))


# ── TUI /update handler ───────────────────────────────────────────────────────

async def run_update_async(output_panel, status_bar=None) -> None:
    """
    Full /update flow for the Textual TUI.
    Runs the blocking subprocess in an executor so the UI stays responsive.
    Restarts on success.
    """
    import asyncio

    method = _detect_install_method()
    labels = {
        "git": "git pull origin main",
        "pip": "pip install --upgrade biju-cli",
        "npm": "npm update -g biju-cli",
    }

    output_panel.add_tool_event(
        f"⬆ **Updating Biju…**\n"
        f"Method: `{labels[method]}`"
    )
    if status_bar:
        status_bar.set_status("⬆ Updating…")

    def progress_cb(step: UpdateStep) -> None:
        icons = {"running": "⏳", "done": "✅", "error": "❌"}
        icon  = icons.get(step.status, "○")
        msg   = f"{icon} `{step.label}`"
        if step.status == "error" and step.output:
            msg += f"\n```\n{step.output[:300]}\n```"
        output_panel.add_tool_event(msg)

    loop = asyncio.get_event_loop()
    success, result = await loop.run_in_executor(
        None, lambda: do_update(progress_cb=progress_cb)
    )

    if status_bar:
        status_bar.set_status("")

    if success:
        output_panel.add_tool_event(
            "✅ **Update complete! Restarting in 3 seconds…**"
        )
        await asyncio.sleep(3)
        restart_process()
    else:
        output_panel.add_tool_event(
            f"❌ **Update failed**\n\n```\n{result}\n```\n\n"
            f"Try manually:\n```\ngit pull origin main\npip install -e .\n```"
        )


# ── Startup banners ───────────────────────────────────────────────────────────

def print_update_banner(result: UpdateResult) -> None:
    """Rich banner for the classic CLI startup."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console()
        console.print(Panel(
            f"[bold yellow]⬆  New version available: [cyan]v{result.latest}[/cyan][/bold yellow]\n"
            f"[dim]You're on v{CURRENT_VERSION}.[/dim]\n\n"
            f"Type [bold cyan]/update[/bold cyan] to update and restart automatically!\n"
            f"[dim]Release notes → {result.url}[/dim]",
            title="[bold yellow]🆕 Biju Update Available[/bold yellow]",
            border_style="yellow",
            expand=False,
        ))
    except Exception:
        print(f"\n  ⬆  New Biju version: v{result.latest}  (you have v{CURRENT_VERSION})")
        print(f"     Type /update to update automatically!\n")


def make_update_markup(result: UpdateResult) -> str:
    """Markdown for the TUI startup notification."""
    return (
        f"🆕 **Update available: v{result.latest}** *(you have v{CURRENT_VERSION})*\n\n"
        f"Type `/update` to update and restart automatically!"
    )
