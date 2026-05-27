"""
tests/test_tools.py
Unit tests for biju/tools.py — all shared tool implementations.
"""

import os
import pytest

# Make sure the project root is importable
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from biju.tools import (
    edit_file,
    list_dir,
    search_in_files,
    read_file_range,
    read_file,
    write_file,
    run_command_impl,
    check_trusted_dir,
    is_destructive_command,
    build_repo_context,
    summarize_conversation,
    dispatch_tool,
    get_file_backups,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_file(tmp_path):
    """Create a temporary Python file for testing."""
    f = tmp_path / "sample.py"
    f.write_text(
        "def hello():\n"
        "    print('Hello, World!')\n"
        "\n"
        "def goodbye():\n"
        "    print('Goodbye!')\n",
        encoding="utf-8",
    )
    return str(f)


@pytest.fixture
def tmp_dir(tmp_path):
    """Create a temporary directory structure for testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('main')\n")
    (tmp_path / "src" / "utils.py").write_text("# utils\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("# tests\n")
    (tmp_path / "README.md").write_text("# Project\n")
    (tmp_path / "package.json").write_text('{"name": "test"}\n')
    return str(tmp_path)


# ── Feature 1: edit_file ─────────────────────────────────────────────────────

class TestEditFile:
    def test_basic_edit(self, tmp_file):
        result = edit_file(tmp_file, "print('Hello, World!')", "print('Hi!')")
        assert "✅ Applied edit" in result
        assert "Diff Preview" in result
        # Verify file contents changed
        with open(tmp_file) as f:
            content = f.read()
        assert "print('Hi!')" in content
        assert "print('Hello, World!')" not in content

    def test_edit_creates_backup(self, tmp_file):
        backups = get_file_backups()
        edit_file(tmp_file, "print('Hello, World!')", "print('Hi!')")
        assert tmp_file in backups
        assert "print('Hello, World!')" in backups[tmp_file]

    def test_edit_not_found(self, tmp_file):
        result = edit_file(tmp_file, "THIS DOES NOT EXIST", "replacement")
        assert "Error" in result
        assert "Could not find" in result

    def test_edit_ambiguous_match(self, tmp_file):
        # "print" appears twice in the file
        result = edit_file(tmp_file, "print", "log")
        assert "Error" in result
        assert "occurrences" in result

    def test_edit_file_not_found(self):
        result = edit_file("/nonexistent/path.py", "old", "new")
        assert "Error" in result
        assert "not found" in result

    def test_edit_multiline(self, tmp_file):
        old = "def hello():\n    print('Hello, World!')"
        new = "def hello(name):\n    print(f'Hello, {name}!')"
        result = edit_file(tmp_file, old, new)
        assert "✅ Applied edit" in result
        with open(tmp_file) as f:
            content = f.read()
        assert "def hello(name):" in content


# ── Feature 2: repo discovery tools ──────────────────────────────────────────

class TestListDir:
    def test_basic_listing(self, tmp_dir):
        result = list_dir(tmp_dir, depth=1)
        assert "README.md" in result
        assert "src/" in result
        assert "tests/" in result

    def test_depth_limiting(self, tmp_dir):
        # depth=1 should NOT show files inside src/
        result = list_dir(tmp_dir, depth=1)
        assert "main.py" not in result

        # depth=2 SHOULD show files inside src/
        result = list_dir(tmp_dir, depth=2)
        assert "main.py" in result

    def test_nonexistent_path(self):
        result = list_dir("/nonexistent/path")
        assert "Error" in result

    def test_file_not_directory(self, tmp_file):
        result = list_dir(tmp_file)
        assert "Error" in result
        assert "Not a directory" in result


class TestSearchInFiles:
    def test_basic_search(self, tmp_dir):
        result = search_in_files("print", tmp_dir)
        # Should find "print('main')" in main.py
        assert "main.py" in result or "match" in result.lower()

    def test_no_matches(self, tmp_dir):
        result = search_in_files("XYZNONEXISTENT999", tmp_dir)
        assert "No matches" in result


class TestReadFileRange:
    def test_basic_range(self, tmp_file):
        result = read_file_range(tmp_file, 1, 2)
        assert "def hello():" in result
        assert "print('Hello, World!')" in result
        assert "def goodbye" not in result

    def test_single_line(self, tmp_file):
        result = read_file_range(tmp_file, 1, 1)
        assert "def hello():" in result

    def test_out_of_bounds_end(self, tmp_file):
        result = read_file_range(tmp_file, 1, 999)
        # Should clamp to file end, not error
        assert "def hello():" in result
        assert "def goodbye():" in result

    def test_invalid_range(self, tmp_file):
        result = read_file_range(tmp_file, 5, 2)
        assert "Error" in result

    def test_start_past_end(self, tmp_file):
        result = read_file_range(tmp_file, 999, 1000)
        assert "Error" in result

    def test_file_not_found(self):
        result = read_file_range("/nonexistent/file.py", 1, 10)
        assert "Error" in result


# ── Core tools ────────────────────────────────────────────────────────────────

class TestReadFile:
    def test_basic_read(self, tmp_file):
        result = read_file(tmp_file)
        assert "1:" in result
        assert "def hello():" in result

    def test_file_not_found(self):
        result = read_file("/nonexistent/file.py")
        assert "Error" in result


class TestWriteFile:
    def test_basic_write(self, tmp_path):
        filepath = str(tmp_path / "new_file.txt")
        result = write_file(filepath, "Hello\nWorld\n")
        assert "Successfully wrote" in result
        assert "2 lines" in result
        with open(filepath) as f:
            assert f.read() == "Hello\nWorld\n"

    def test_creates_directories(self, tmp_path):
        filepath = str(tmp_path / "deep" / "nested" / "file.txt")
        result = write_file(filepath, "content\n")
        assert "Successfully wrote" in result
        assert os.path.exists(filepath)

    def test_overwrites_with_backup(self, tmp_file):
        write_file(tmp_file, "new content\n")
        backups = get_file_backups()
        assert tmp_file in backups
        assert "def hello():" in backups[tmp_file]


class TestRunCommand:
    def test_echo(self):
        if os.name == "nt":
            result = run_command_impl('echo hello')
        else:
            result = run_command_impl('echo hello')
        assert "Exit Code: 0" in result
        assert "hello" in result

    def test_nonexistent_command(self):
        result = run_command_impl("nonexistent_command_12345")
        # Should have non-zero exit code or error
        assert "Exit Code:" in result or "Error" in result


# ── Feature 3: trusted-dir enforcement ────────────────────────────────────────

class TestTrustedDir:
    def test_cwd_allowed(self, tmp_path):
        filepath = str(tmp_path / "test.txt")
        allowed, reason = check_trusted_dir(filepath, [], str(tmp_path))
        assert allowed is True
        assert reason == ""

    def test_trusted_dir_allowed(self, tmp_path):
        other_dir = str(tmp_path / "other")
        os.makedirs(other_dir, exist_ok=True)
        filepath = os.path.join(other_dir, "test.txt")
        allowed, reason = check_trusted_dir(filepath, [other_dir], "/some/other/cwd")
        assert allowed is True

    def test_outside_denied(self, tmp_path):
        filepath = "/some/random/path/file.txt"
        allowed, reason = check_trusted_dir(filepath, [], str(tmp_path))
        assert allowed is False
        assert "outside" in reason.lower()

    def test_allow_all_overrides(self):
        allowed, reason = check_trusted_dir("/any/path.txt", [], "/cwd", allow_all=True)
        assert allowed is True


# ── Feature 8: destructive command detection ──────────────────────────────────

class TestDestructiveCommand:
    @pytest.mark.parametrize("cmd", [
        "rm -rf /tmp/test",
        "rm file.txt",
        "del file.txt",
        "rmdir /s test",
        "rd /s /q test",
        "git reset --hard",
        "git checkout -- .",
        "git clean -fd",
        "git push origin main --force",
    ])
    def test_detects_destructive(self, cmd):
        is_destr, desc = is_destructive_command(cmd)
        assert is_destr is True, f"Expected '{cmd}' to be destructive"
        assert desc != ""

    @pytest.mark.parametrize("cmd", [
        "ls -la",
        "echo hello",
        "cat file.txt",
        "git status",
        "git log",
        "git diff",
        "python test.py",
        "npm install",
    ])
    def test_allows_safe(self, cmd):
        is_destr, desc = is_destructive_command(cmd)
        assert is_destr is False, f"Expected '{cmd}' to be safe"


# ── Feature 5: repo context priming ──────────────────────────────────────────

class TestRepoContext:
    def test_basic_context(self, tmp_dir):
        result = build_repo_context(tmp_dir)
        assert "Repository Context" in result
        assert "Directory Structure" in result
        assert "README.md" in result

    def test_detects_project_files(self, tmp_dir):
        result = build_repo_context(tmp_dir)
        assert "package.json" in result
        assert "Detected Project Files" in result


# ── Feature 6: conversation summarization ─────────────────────────────────────

class TestSummarizeConversation:
    def test_no_compression_under_threshold(self):
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = summarize_conversation(messages, max_user_turns=10)
        assert result is messages  # unchanged (same object)

    def test_compression_over_threshold(self):
        messages = [{"role": "system", "content": "system prompt"}]
        for i in range(15):
            messages.append({"role": "user", "content": f"question {i}"})
            messages.append({"role": "assistant", "content": f"answer {i}"})

        result = summarize_conversation(messages, max_user_turns=10)
        # Should be shorter than original
        assert len(result) < len(messages)
        # Should still have system message
        assert result[0]["role"] == "system"
        # Should contain summary marker
        has_summary = any("CONVERSATION SUMMARY" in (m.get("content") or "") for m in result)
        assert has_summary

    def test_preserves_recent_messages(self):
        messages = [{"role": "system", "content": "system prompt"}]
        for i in range(15):
            messages.append({"role": "user", "content": f"question {i}"})
            messages.append({"role": "assistant", "content": f"answer {i}"})

        result = summarize_conversation(messages, max_user_turns=10)
        # The most recent messages should be preserved verbatim
        last_msg = result[-1]
        assert last_msg["content"] == "answer 14"


# ── Tool dispatcher ──────────────────────────────────────────────────────────

class TestDispatchTool:
    def test_read_file(self, tmp_file):
        result = dispatch_tool("read_file", {"filepath": tmp_file})
        assert "def hello():" in result

    def test_unknown_tool(self):
        result = dispatch_tool("nonexistent_tool", {})
        assert "Unknown tool" in result

    def test_list_dir(self, tmp_dir):
        result = dispatch_tool("list_dir", {"path": tmp_dir, "depth": 1})
        assert "README.md" in result

    def test_read_file_range(self, tmp_file):
        result = dispatch_tool("read_file_range", {
            "filepath": tmp_file, "start_line": 1, "end_line": 2
        })
        assert "def hello():" in result
