"""
biju/tools.py
Shared tool implementations used by both the classic CLI and the TUI.

Every function here is a pure tool implementation — no UI rendering,
no approval prompts, no API calls.  The caller (CLI or TUI) is responsible
for gating, display, and permission handling.
"""

from __future__ import annotations

import difflib
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

# ── File backups (shared state for /undo) ─────────────────────────────────────
_file_backups: dict[str, str] = {}


def get_file_backups() -> dict[str, str]:
    """Return the global backup dict so callers can inspect / pop."""
    return _file_backups


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1 — edit_file (patch-based editing with diff preview)
# ─────────────────────────────────────────────────────────────────────────────

def edit_file(filepath: str, old_text: str, new_text: str) -> str:
    """
    Replace *old_text* with *new_text* in *filepath*.

    Returns a human-readable diff preview followed by a confirmation message.
    Raises on errors (file not found, old_text not found, ambiguous match).
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
    except FileNotFoundError:
        return f"Error: File not found: {filepath}"
    except Exception as e:
        return f"Error reading file: {e}"

    # Exact-match search
    count = original.count(old_text)
    if count == 0:
        return (
            f"Error: Could not find the specified text in {filepath}.\n"
            "Make sure old_text matches exactly, including whitespace and indentation."
        )
    if count > 1:
        return (
            f"Error: Found {count} occurrences of old_text in {filepath}. "
            "Please provide a more unique/larger snippet so the match is unambiguous."
        )

    # Build diff preview
    diff_preview = _build_diff_preview(original, old_text, new_text, filepath)

    # Back up original
    _file_backups[filepath] = original

    # Apply edit
    new_content = original.replace(old_text, new_text, 1)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return f"Error writing file: {e}"

    old_lines = len(old_text.splitlines())
    new_lines = len(new_text.splitlines())
    return (
        f"{diff_preview}\n\n"
        f"✅ Applied edit to {filepath} — replaced {old_lines} line(s) with {new_lines} line(s)."
    )


def _build_diff_preview(
    original: str, old_text: str, new_text: str, filepath: str
) -> str:
    """Generate a simple diff preview showing the change in context."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    # Find the starting line number of old_text in the original file
    before = original[: original.index(old_text)]
    start_line = before.count("\n") + 1

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{os.path.basename(filepath)}",
        tofile=f"b/{os.path.basename(filepath)}",
        lineterm="",
    )
    diff_str = "\n".join(diff)
    if not diff_str:
        return "No changes detected."
    return f"--- Diff Preview (starting at line {start_line}) ---\n{diff_str}"


# ─────────────────────────────────────────────────────────────────────────────
# Feature 2 — repo discovery tools
# ─────────────────────────────────────────────────────────────────────────────

def list_dir(path: str | None = None, depth: int = 2) -> str:
    """
    Tree-formatted directory listing with file sizes.
    Respects *depth* to avoid overwhelming output.
    """
    root = Path(path) if path else Path.cwd()
    if not root.exists():
        return f"Error: Path does not exist: {root}"
    if not root.is_dir():
        return f"Error: Not a directory: {root}"

    lines: list[str] = [str(root) + "/"]
    _tree_walk(root, "", depth, 0, lines)

    if len(lines) == 1:
        lines.append("  (empty directory)")

    return "\n".join(lines)


def _tree_walk(
    directory: Path,
    prefix: str,
    max_depth: int,
    current_depth: int,
    lines: list[str],
) -> None:
    """Recursive helper for list_dir."""
    if current_depth >= max_depth:
        return

    # Skip hidden / __pycache__ / node_modules / .git
    skip = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".mypy_cache"}
    try:
        entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        lines.append(f"{prefix}(permission denied)")
        return

    entries = [e for e in entries if e.name not in skip]

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")

        if entry.is_dir():
            lines.append(f"{prefix}{connector}{entry.name}/")
            _tree_walk(entry, child_prefix, max_depth, current_depth + 1, lines)
        else:
            size = _human_size(entry.stat().st_size)
            lines.append(f"{prefix}{connector}{entry.name} ({size})")


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}" if unit == "B" else f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def search_in_files(
    query: str,
    paths: str | None = None,
    glob_pattern: str | None = None,
) -> str:
    """
    Search for *query* across files.

    Tries ripgrep (rg) first, falls back to grep (Unix) or findstr (Windows).
    Returns up to 50 matches in file:line:content format.
    """
    search_path = paths or "."
    is_windows = platform.system() == "Windows"
    max_matches = 50

    # Try ripgrep first
    rg = shutil.which("rg")
    if rg:
        cmd = [rg, "--no-heading", "--line-number", "--max-count", str(max_matches)]
        if glob_pattern:
            cmd.extend(["--glob", glob_pattern])
        cmd.extend([query, search_path])
    elif is_windows:
        # Fallback: findstr
        cmd_str = f'findstr /S /N /I /C:"{query}"'
        if glob_pattern:
            cmd_str += f" {os.path.join(search_path, glob_pattern)}"
        else:
            cmd_str += f" {os.path.join(search_path, '*')}"
        try:
            result = subprocess.run(
                cmd_str, shell=True, capture_output=True, text=True, timeout=30,
            )
            output = result.stdout.strip()
            if not output:
                return f"No matches found for '{query}'."
            lines = output.splitlines()[:max_matches]
            return f"Found {len(lines)} match(es):\n" + "\n".join(lines)
        except subprocess.TimeoutExpired:
            return "Error: Search timed out after 30 seconds."
        except Exception as e:
            return f"Error: {e}"
    else:
        # Fallback: grep
        cmd = ["grep", "-rnI", "--max-count", str(max_matches)]
        if glob_pattern:
            cmd.extend(["--include", glob_pattern])
        cmd.extend([query, search_path])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip()
        if not output:
            return f"No matches found for '{query}'."
        lines = output.splitlines()[:max_matches]
        return f"Found {len(lines)} match(es):\n" + "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "Error: Search timed out after 30 seconds."
    except FileNotFoundError:
        return "Error: Search tools (rg, grep) not available."
    except Exception as e:
        return f"Error: {e}"


def read_file_range(filepath: str, start_line: int, end_line: int) -> str:
    """
    Read lines *start_line* through *end_line* (1-indexed, inclusive).
    Returns numbered lines.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except FileNotFoundError:
        return f"Error: File not found: {filepath}"
    except Exception as e:
        return f"Error reading file: {e}"

    total = len(all_lines)
    if start_line < 1:
        start_line = 1
    if end_line > total:
        end_line = total
    if start_line > total:
        return f"Error: start_line ({start_line}) exceeds file length ({total} lines)."
    if start_line > end_line:
        return f"Error: start_line ({start_line}) > end_line ({end_line})."

    selected = all_lines[start_line - 1 : end_line]
    numbered = "".join(
        f"{start_line + i:>4}: {line}" for i, line in enumerate(selected)
    )
    return f"Lines {start_line}-{end_line} of {filepath} ({total} total lines):\n{numbered}"


# ─────────────────────────────────────────────────────────────────────────────
# Core tools — read_file, write_file, run_command
# ─────────────────────────────────────────────────────────────────────────────

def read_file(filepath: str) -> str:
    """Read the full contents of a file with line numbers."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(f"{i+1:>4}: {line}" for i, line in enumerate(lines))
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(filepath: str, content: str) -> str:
    """Write content to a file, backing up the original."""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                _file_backups[filepath] = f.read()

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content.splitlines())} lines to {filepath}"
    except Exception as e:
        return f"Error writing file: {e}"


def run_command_impl(cmd: str, timeout: int = 60) -> str:
    """
    Execute a shell command and return its output.

    This is the raw implementation — the caller handles approval prompts,
    autopilot checks, destructive-command gating, and trusted-dir enforcement.
    """
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        parts = [f"Exit Code: {result.returncode}"]
        if result.stdout.strip():
            parts.append(f"Stdout:\n{result.stdout.strip()}")
        if result.stderr.strip():
            parts.append(f"Stderr:\n{result.stderr.strip()}")
        return "\n".join(parts) if parts else "Command completed with no output."
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing command: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Feature 3 — trusted-dir enforcement
# ─────────────────────────────────────────────────────────────────────────────

def check_trusted_dir(
    filepath: str,
    trusted_dirs: list[str],
    cwd: str,
    allow_all: bool = False,
) -> Tuple[bool, str]:
    """
    Check whether *filepath* falls within CWD or a trusted directory.

    Returns (is_allowed, reason).
    """
    if allow_all:
        return True, ""

    abs_path = os.path.abspath(filepath)
    abs_cwd = os.path.abspath(cwd)

    # Allow if under CWD
    if abs_path.startswith(abs_cwd + os.sep) or abs_path == abs_cwd:
        return True, ""

    # Allow if under any trusted dir
    for td in trusted_dirs:
        abs_td = os.path.abspath(td)
        if abs_path.startswith(abs_td + os.sep) or abs_path == abs_td:
            return True, ""

    return (
        False,
        f"Path '{filepath}' is outside the current working directory and trusted directories.\n"
        f"CWD: {abs_cwd}\n"
        f"Trusted dirs: {trusted_dirs or '(none)'}\n"
        "Use /add-dir to add a trusted directory, or /allow-all to bypass restrictions.",
    )


# ── Destructive command detection (Feature 8) ────────────────────────────────

_DESTRUCTIVE_PATTERNS: list[Tuple[str, str]] = [
    (r"\brm\s+(-[a-zA-Z]*\s+)*",        "Permanently deletes files"),
    (r"\bdel\s+",                         "Permanently deletes files (Windows)"),
    (r"\brmdir\s+",                       "Removes directories"),
    (r"\brd\s+",                          "Removes directories (Windows)"),
    (r"\bgit\s+reset\s+--hard",           "Discards all uncommitted changes"),
    (r"\bgit\s+checkout\s+--\s",          "Discards uncommitted file changes"),
    (r"\bgit\s+clean\s+(-[a-zA-Z]*\s+)*", "Removes untracked files from repo"),
    (r"\bformat\s+[a-zA-Z]:",            "Formats a disk drive (Windows)"),
    (r"\bmkfs\b",                         "Creates a filesystem (destructive)"),
    (r"\bdrop\s+(table|database)\b",      "Drops a database table/database"),
    (r"\bgit\s+push\s+.*--force",         "Force-pushes (rewrites remote history)"),
]

_DESTRUCTIVE_RE = [
    (re.compile(pattern, re.IGNORECASE), desc)
    for pattern, desc in _DESTRUCTIVE_PATTERNS
]


def is_destructive_command(cmd: str) -> Tuple[bool, str]:
    """
    Check if *cmd* matches a known destructive pattern.

    Returns (is_destructive, description).
    """
    for regex, desc in _DESTRUCTIVE_RE:
        if regex.search(cmd):
            return True, desc
    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# Feature 4 — git-native tools (safe, read-only)
# ─────────────────────────────────────────────────────────────────────────────

def git_status() -> str:
    """Return current git branch and status."""
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=10,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        branch_name = branch.stdout.strip() or "(detached HEAD)"
        status_out = status.stdout.strip()

        result = f"Branch: {branch_name}\n"
        if not status_out:
            result += "Working tree clean — no changes."
        else:
            result += f"Changes:\n{status_out}"
        return result
    except FileNotFoundError:
        return "Error: git is not installed or not in PATH."
    except subprocess.TimeoutExpired:
        return "Error: git status timed out."
    except Exception as e:
        return f"Error: {e}"


def git_diff(staged: bool = False) -> str:
    """Return git diff output."""
    try:
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--staged")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
        )
        output = result.stdout.strip()
        if not output:
            label = "staged" if staged else "working tree"
            return f"No {label} changes."
        return output
    except FileNotFoundError:
        return "Error: git is not installed or not in PATH."
    except subprocess.TimeoutExpired:
        return "Error: git diff timed out."
    except Exception as e:
        return f"Error: {e}"


def git_log(n: int = 10) -> str:
    """Return recent git log entries."""
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{n}"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout.strip()
        if not output:
            return "No commits yet."
        return output
    except FileNotFoundError:
        return "Error: git is not installed or not in PATH."
    except subprocess.TimeoutExpired:
        return "Error: git log timed out."
    except Exception as e:
        return f"Error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5 — repo context priming
# ─────────────────────────────────────────────────────────────────────────────

# Files that indicate project type / structure
_PROJECT_FILES = [
    "package.json", "pyproject.toml", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "requirements.txt", "Pipfile", "Gemfile", "composer.json",
    "Makefile", "CMakeLists.txt", "Dockerfile", ".env.example",
]


def build_repo_context(cwd: str, depth: int = 2) -> str:
    """
    Build a lightweight repository summary for injection into the system prompt.

    Includes:
    - Top-level tree (up to *depth*)
    - Detected project files with key metadata
    """
    root = Path(cwd)
    parts: list[str] = []

    parts.append("# Repository Context")
    parts.append(f"Root: {root}")

    # Directory tree
    tree = list_dir(str(root), depth=depth)
    parts.append(f"\n## Directory Structure\n```\n{tree}\n```")

    # Detected project files
    detected: list[str] = []
    for pf in _PROJECT_FILES:
        pf_path = root / pf
        if pf_path.exists():
            detected.append(pf)

    if detected:
        parts.append("\n## Detected Project Files")
        for pf in detected:
            pf_path = root / pf
            try:
                content = pf_path.read_text(encoding="utf-8", errors="replace")
                # Truncate large files
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                parts.append(f"\n### {pf}\n```\n{content}\n```")
            except Exception:
                parts.append(f"\n### {pf}\n(could not read)")

    # Git info
    try:
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        branch = branch_result.stdout.strip()
        if branch:
            parts.append(f"\n## Git\nCurrent branch: `{branch}`")
    except Exception:
        pass

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Feature 6 — conversation summarization
# ─────────────────────────────────────────────────────────────────────────────

def summarize_conversation(
    messages: list[dict],
    max_user_turns: int = 10,
) -> list[dict]:
    """
    If the conversation has more than *max_user_turns* user messages,
    compress older messages into a summary block prepended to the list.

    Returns the (possibly compressed) messages list.
    Does NOT modify the input list — returns a new one.

    Strategy:
    - Keep the system message intact
    - Count user messages; if <= threshold, return as-is
    - Otherwise, summarize the oldest 60% of non-system messages into
      a compact block and keep the most recent 40% verbatim
    """
    # Count user turns
    user_turn_count = sum(1 for m in messages if m.get("role") == "user")
    if user_turn_count <= max_user_turns:
        return messages  # no compression needed

    # Separate system message
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    # Figure out how many to compress (oldest 60%)
    cut_point = int(len(non_system) * 0.6)
    to_compress = non_system[:cut_point]
    to_keep = non_system[cut_point:]

    # Build summary
    summary_parts: list[str] = []
    summary_parts.append("=== CONVERSATION SUMMARY (older messages compressed) ===")

    for msg in to_compress:
        role = msg.get("role", "?")
        content = msg.get("content") or ""

        if role == "user":
            # Keep user messages short
            preview = content[:200] + ("..." if len(content) > 200 else "")
            summary_parts.append(f"User: {preview}")
        elif role == "assistant":
            # Keep assistant summaries short
            preview = content[:300] + ("..." if len(content) > 300 else "")
            summary_parts.append(f"Assistant: {preview}")
        elif role == "tool":
            # Keep tool results very short
            preview = content[:150] + ("..." if len(content) > 150 else "")
            summary_parts.append(f"Tool result: {preview}")
        # Skip tool_call entries in the summary

    summary_parts.append("=== END SUMMARY ===")

    summary_message = {
        "role": "user",
        "content": "\n".join(summary_parts),
    }

    return system_msgs + [summary_message] + to_keep


# ─────────────────────────────────────────────────────────────────────────────
# Tool dispatcher — maps tool names to implementations
# ─────────────────────────────────────────────────────────────────────────────

def dispatch_tool(func_name: str, args: dict) -> str:
    """
    Execute a tool by name. Returns the tool result as a string.

    This does NOT handle permissions, approval, or trusted-dir checks —
    those must be done by the caller before calling dispatch_tool.
    """
    if func_name == "run_command":
        cmd = args.get("command")
        return run_command_impl(str(cmd) if cmd is not None else "")
    elif func_name == "read_file":
        filepath = args.get("filepath")
        return read_file(str(filepath) if filepath is not None else "")
    elif func_name == "write_file":
        filepath = args.get("filepath")
        content = args.get("content")
        return write_file(str(filepath) if filepath is not None else "", str(content) if content is not None else "")
    elif func_name == "edit_file":
        filepath = args.get("filepath")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        return edit_file(
            str(filepath) if filepath is not None else "",
            str(old_text) if old_text is not None else "",
            str(new_text) if new_text is not None else "",
        )
    elif func_name == "list_dir":
        path = args.get("path")
        depth = args.get("depth")
        return list_dir(str(path) if path is not None else ".", int(depth) if depth is not None else 2)
    elif func_name == "search_in_files":
        query = args.get("query")
        paths = args.get("paths")
        glob_p = args.get("glob")
        return search_in_files(
            str(query) if query is not None else "",
            str(paths) if paths is not None else None,
            str(glob_p) if glob_p is not None else None,
        )
    elif func_name == "read_file_range":
        filepath = args.get("filepath")
        start_line = args.get("start_line")
        end_line = args.get("end_line")
        return read_file_range(
            str(filepath) if filepath is not None else "",
            int(start_line) if start_line is not None else 1,
            int(end_line) if end_line is not None else 1,
        )
    elif func_name == "git_status":
        return git_status()
    elif func_name == "git_diff":
        staged_val = args.get("staged", False)
        is_staged = staged_val if isinstance(staged_val, bool) else str(staged_val).lower() == "true"
        return git_diff(staged=is_staged)
    elif func_name == "git_log":
        n_val = args.get("n")
        return git_log(n=int(n_val) if n_val is not None else 10)
    else:
        return f"Unknown tool: {func_name}"
