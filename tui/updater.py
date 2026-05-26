"""
tui/updater.py
──────────────
Lightweight update checker for Biju.

How it works
────────────
On startup, a background thread silently queries the GitHub Releases API
to get the latest published version tag. It compares that against the
locally installed version from setup.py / the VERSION constant here.

If a newer version is found the result is cached in ~/.biju_update_cache.json
(TTL: 6 hours) so we only hit the network once per session at most.

The check is fire-and-forget — it never blocks startup.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

# ── Version constants ─────────────────────────────────────────────────────────
CURRENT_VERSION = "2.0.0"
GITHUB_REPO     = "Prithish-22/open-source-cli"
GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CACHE_FILE      = Path.home() / ".biju_update_cache.json"
CACHE_TTL_HOURS = 6   # only check GitHub once every 6 hours


# ── Public result holder ──────────────────────────────────────────────────────

class UpdateResult:
    """Holds the result of the update check (populated from the background thread)."""

    def __init__(self) -> None:
        self.checked   = False
        self.has_update = False
        self.latest    = CURRENT_VERSION
        self.url       = f"https://github.com/{GITHUB_REPO}/releases"

    def __bool__(self) -> bool:
        return self.has_update


# ── Core logic ────────────────────────────────────────────────────────────────

def _parse_version(tag: str) -> tuple[int, ...]:
    """Convert a version string like 'v2.1.0' or '2.1.0' into a comparable tuple."""
    clean = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in clean.split("."))
    except ValueError:
        return (0,)


def _load_cache() -> dict | None:
    """Return cached result if it exists and hasn't expired."""
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


def _fetch_latest() -> tuple[str, str]:
    """
    Query GitHub API for the latest release tag.
    Returns (tag_name, html_url).
    Raises on any network/parse error.
    """
    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"biju-cli/{CURRENT_VERSION}",
        },
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
    return data["tag_name"], data["html_url"]


def _do_check(result: UpdateResult) -> None:
    """Run inside a daemon thread. Populates *result* in-place."""
    try:
        # Try cache first
        cached = _load_cache()
        if cached:
            latest_tag = cached["latest"]
            url        = cached["url"]
        else:
            latest_tag, url = _fetch_latest()
            _save_cache(latest_tag, url)

        current_tuple = _parse_version(CURRENT_VERSION)
        latest_tuple  = _parse_version(latest_tag)

        result.latest    = latest_tag.lstrip("v")
        result.url       = url
        result.has_update = latest_tuple > current_tuple
        result.checked   = True

    except Exception:
        # Network errors, rate limits, etc. — silently ignore
        result.checked = True  # mark done even on failure


def check_for_updates() -> UpdateResult:
    """
    Kick off a non-blocking background update check.

    Returns an UpdateResult object immediately.
    The object's attributes will be populated once the background
    thread completes (usually within 2–3 seconds).

    Usage
    ─────
    result = check_for_updates()
    # ... do startup work ...
    if result.has_update:
        show_update_banner(result)
    """
    result = UpdateResult()
    thread = threading.Thread(target=_do_check, args=(result,), daemon=True)
    thread.start()
    return result, thread


# ── Rich banner (used by Classic CLI) ────────────────────────────────────────

def print_update_banner(result: UpdateResult) -> None:
    """
    Print a Rich-formatted update notification to stdout.
    Call this after the startup screen if result.has_update is True.
    """
    try:
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        console.print(Panel(
            f"[bold yellow]⬆  New version available: [cyan]v{result.latest}[/cyan][/bold yellow]\n"
            f"[dim]You're on v{CURRENT_VERSION}. Update to get the latest features and bug fixes.[/dim]\n\n"
            f"[bold]Update commands:[/bold]\n"
            f"  [cyan]npm update -g biju-cli[/cyan]          (if installed via npm)\n"
            f"  [cyan]pip install --upgrade biju-cli[/cyan]  (if installed via pip)\n"
            f"  [cyan]git pull origin main[/cyan]            (if cloned from GitHub)\n\n"
            f"[dim]Release notes → {result.url}[/dim]",
            title="[bold yellow]🆕 Biju Update Available[/bold yellow]",
            border_style="yellow",
            expand=False,
        ))
    except Exception:
        # Fallback plain-text banner
        print(f"\n  ⬆  New Biju version: v{result.latest}  (you have v{CURRENT_VERSION})")
        print(f"     Run: pip install --upgrade biju-cli   OR   git pull origin main\n")


# ── Textual notification (used by TUI) ───────────────────────────────────────

def make_update_markup(result: UpdateResult) -> str:
    """
    Return a Rich markup string suitable for display inside the TUI's
    OutputPanel as a tool event notification.
    """
    return (
        f"🆕 **Update available: v{result.latest}** *(you have v{CURRENT_VERSION})*\n\n"
        f"Run one of these to update:\n"
        f"```\n"
        f"npm update -g biju-cli\n"
        f"pip install --upgrade biju-cli\n"
        f"git pull origin main && pip install -e .\n"
        f"```\n"
        f"[Release notes]({result.url})"
    )
