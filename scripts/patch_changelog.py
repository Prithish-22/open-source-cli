"""Patch the changelog in bijucli.py to include v3.1 changes."""

path = "biju/bijucli.py"
content = open(path, "r", encoding="utf-8").read()

# Find the changelog section by line number
lines = content.splitlines(keepends=True)
for i, line in enumerate(lines):
    if "v3.0" in line and "Markdown rendered" in line:
        # Found the v3.0 line — insert v3.1 before it
        v31_line = (
            '                        "[bold]v3.1[/bold]  10 tools (edit_file, list_dir, search_in_files, read_file_range, git tools)\\n"\n'
            '                        "        4 new agents: Repo Scout, Patch Editor, Reviewer, Security Guard\\n"\n'
            '                        "        Trusted-dir enforcement, destructive-cmd safety, live streaming, repo context\\n"\n'
        )
        lines.insert(i, v31_line)
        break

content = "".join(lines)
open(path, "w", encoding="utf-8").write(content)
print("OK: v3.1 changelog added")
