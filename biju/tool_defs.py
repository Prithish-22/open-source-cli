"""
biju/tool_defs.py
Single source of truth for all tool schemas (OpenAI function-calling format).
Both the classic CLI and TUI import from here to stay in sync.
"""

from __future__ import annotations

# ── Tool schema definitions ───────────────────────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    # ── Core tools ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Execute a shell/terminal command on the user's OS and return its full output "
                "including exit code, stdout, and stderr. Use to navigate directories, run scripts, "
                "install packages, run tests, or perform any system operation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the full contents of a file, returned with line numbers prepended to every line "
                "(e.g. '  12: def foo():') so you can reference exact line numbers for targeted edits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Absolute or relative path to the file.",
                    }
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write or completely overwrite a file with new content. "
                "Use this only when creating a brand-new file. "
                "For editing existing files prefer edit_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Absolute or relative path to the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete new content of the file.",
                    },
                },
                "required": ["filepath", "content"],
            },
        },
    },

    # ── Feature 1: edit_file (patch-based) ────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Edit an existing file by replacing an exact text match with new content. "
                "A diff preview is generated and returned before applying the change. "
                "Use this instead of write_file when you only need to change part of a file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path to the file to edit.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": (
                            "The exact text to find and replace. Must match verbatim "
                            "(including whitespace and indentation)."
                        ),
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The replacement text.",
                    },
                },
                "required": ["filepath", "old_text", "new_text"],
            },
        },
    },

    # ── Feature 2: repo discovery tools ───────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": (
                "List the contents of a directory as a tree with file sizes. "
                "Defaults to depth=2. Use this instead of running ls/dir commands."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (absolute or relative). Defaults to CWD.",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum depth to traverse. Default is 2.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": (
                "Search for a text pattern across files in a directory. "
                "Uses ripgrep (rg) if available, falls back to grep/findstr. "
                "Returns matching lines with file:line:content format."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The text or regex pattern to search for.",
                    },
                    "paths": {
                        "type": "string",
                        "description": "Directory or file path to search in. Defaults to CWD.",
                    },
                    "glob": {
                        "type": "string",
                        "description": "Glob pattern to filter files, e.g. '*.py', '*.js'. Optional.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file_range",
            "description": (
                "Read a specific range of lines from a file. "
                "More efficient than read_file when you only need part of a large file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path to the file.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-indexed, inclusive).",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (1-indexed, inclusive).",
                    },
                },
                "required": ["filepath", "start_line", "end_line"],
            },
        },
    },

    # ── Feature 4: git-native tools ───────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": (
                "Show the current git status: branch name, staged/unstaged/untracked files. "
                "Safe, read-only — no side effects."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": (
                "Show the git diff of current changes. "
                "Pass staged=true to see staged changes. Safe, read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "If true, show only staged changes. Default is false (working tree).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for real-time information, news, or technical documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_repo_map",
            "description": "Generate a high-level map of the repository, including key files and symbols.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": (
                "Show recent git commit history. Safe, read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Number of commits to show. Default is 10.",
                    },
                },
                "required": [],
            },
        },
    },
]


# ── Convenience lookups ───────────────────────────────────────────────────────

ALL_TOOL_NAMES: set[str] = {
    t["function"]["name"] for t in TOOL_SCHEMAS
}

# Tools that require explicit user permission (when not in autopilot/allow-all)
PERMISSION_REQUIRED: set[str] = {"run_command", "write_file", "edit_file"}

# Tools that are safe / read-only (never need permission)
READ_ONLY_TOOLS: set[str] = {
    "read_file", "read_file_range", "list_dir", "search_in_files",
    "git_status", "git_diff", "git_log", "search_web", "get_repo_map",
}
