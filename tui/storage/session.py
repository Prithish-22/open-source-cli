"""
tui/storage/session.py
Session persistence — saves and loads conversation history to/from JSON files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# ── Session directory ─────────────────────────────────────────────────────────
SESSION_DIR = Path.home() / ".biju_sessions"


def ensure_session_dir() -> Path:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_DIR


def list_sessions() -> list[dict]:
    """Return a list of available sessions sorted newest-first."""
    ensure_session_dir()
    sessions = []
    for f in SESSION_DIR.glob("*.json"):
        try:
            stat = f.stat()
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "filename": f.name,
                "path": str(f),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "message_count": len(data.get("messages", [])),
                "model": data.get("model", "unknown"),
                "title": data.get("title", f.stem),
            })
        except Exception:
            pass
    return sorted(sessions, key=lambda s: s["modified"], reverse=True)


def save_session(messages: list[dict], model: str, title: str = "") -> str:
    """Save the current session to a JSON file. Returns the saved file path."""
    ensure_session_dir()
    if not title:
        # Auto-generate title from first user message
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    title = content[:50].replace("\n", " ").strip()
                    break
        title = title or "Untitled Session"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{timestamp}.json"
    path = SESSION_DIR / filename

    data = {
        "title": title,
        "model": model,
        "created": datetime.now().isoformat(),
        "messages": messages,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def load_session(path: str) -> tuple[list[dict], str]:
    """Load a session from JSON. Returns (messages, model)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("messages", []), data.get("model", "meta/llama-3.3-70b-instruct")


def delete_session(path: str) -> None:
    """Delete a session file."""
    Path(path).unlink(missing_ok=True)
