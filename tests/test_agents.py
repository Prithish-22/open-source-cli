"""
tests/test_agents.py
Tests for agent definitions and agent dispatch logic.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAgentDefinitions:
    """Validate AGENT_DEFINITIONS structure and content."""

    @pytest.fixture
    def agent_defs(self):
        from biju.bijucli import AGENT_DEFINITIONS
        return AGENT_DEFINITIONS

    def test_required_fields_present(self, agent_defs):
        required = {"name", "icon", "color", "desc", "model", "model_label", "system"}
        for agent in agent_defs:
            missing = required - set(agent.keys())
            assert not missing, f"Agent '{agent.get('name', '?')}' missing fields: {missing}"

    def test_no_duplicate_names(self, agent_defs):
        names = [a["name"] for a in agent_defs]
        assert len(names) == len(set(names)), f"Duplicate agent names: {names}"

    def test_all_descriptions_non_empty(self, agent_defs):
        for agent in agent_defs:
            assert len(agent["desc"].strip()) > 5, (
                f"Agent '{agent['name']}' has too short description: '{agent['desc']}'"
            )

    def test_all_systems_non_empty(self, agent_defs):
        for agent in agent_defs:
            assert len(agent["system"].strip()) > 20, (
                f"Agent '{agent['name']}' has too short system prompt"
            )

    def test_new_agents_present(self, agent_defs):
        """Feature 8: verify all 4 new agents exist."""
        names = {a["name"] for a in agent_defs}
        required_new = {"Repo Scout", "Patch Editor", "Reviewer", "Security Guard"}
        missing = required_new - names
        assert not missing, f"Missing new agents: {missing}"

    def test_all_original_agents_present(self, agent_defs):
        """Original agents still exist."""
        names = {a["name"] for a in agent_defs}
        original = {"Researcher", "Coder", "Git Agent", "File Agent", "Test Runner", "Shell Agent"}
        missing = original - names
        assert not missing, f"Missing original agents: {missing}"

    def test_total_agent_count(self, agent_defs):
        """Should have 10 agents total (6 original + 4 new)."""
        assert len(agent_defs) == 10, f"Expected 10 agents, got {len(agent_defs)}"

    def test_repo_scout_uses_discovery_tools(self, agent_defs):
        """Repo Scout system prompt mentions discovery tools."""
        scout = next(a for a in agent_defs if a["name"] == "Repo Scout")
        system = scout["system"]
        assert "list_dir" in system, "Repo Scout should mention list_dir"
        assert "search_in_files" in system, "Repo Scout should mention search_in_files"
        assert "git_log" in system, "Repo Scout should mention git_log"

    def test_patch_editor_uses_edit_file(self, agent_defs):
        """Patch Editor system prompt enforces edit_file usage."""
        editor = next(a for a in agent_defs if a["name"] == "Patch Editor")
        system = editor["system"]
        assert "edit_file" in system, "Patch Editor should mandate edit_file"
        assert "write_file" in system, "Patch Editor should warn against write_file for edits"

    def test_reviewer_uses_git_tools(self, agent_defs):
        """Reviewer system prompt uses git tools."""
        reviewer = next(a for a in agent_defs if a["name"] == "Reviewer")
        system = reviewer["system"]
        assert "git_diff" in system, "Reviewer should use git_diff"
        assert "git_status" in system, "Reviewer should use git_status"

    def test_security_guard_uses_search(self, agent_defs):
        """Security Guard uses search_in_files for scanning."""
        guard = next(a for a in agent_defs if a["name"] == "Security Guard")
        system = guard["system"]
        assert "search_in_files" in system, "Security Guard should use search_in_files"
        assert "CRITICAL" in system, "Security Guard should have CRITICAL severity level"


class TestCommandsDict:
    """Validate COMMANDS dict is updated."""

    @pytest.fixture
    def commands(self):
        from biju.bijucli import COMMANDS
        return COMMANDS

    def test_help_mentions_tools(self, commands):
        assert "tools" in commands["/help"].lower() or "commands" in commands["/help"].lower()

    def test_agent_command_lists_new_agents(self, commands):
        desc = commands["/agent"]
        # Should mention at least some of the new agents
        assert any(name in desc for name in ["Repo", "Patch", "Reviewer", "Security", "Scout"]), (
            f"/agent description should mention new agents, got: {desc}"
        )

    def test_all_expected_commands_present(self, commands):
        expected = {
            "/add-dir", "/agent", "/allow-all", "/ask", "/autopilot",
            "/clear", "/config", "/help", "/history", "/init", "/model",
            "/setkey", "/undo", "/update", "/queue", "/exit",
        }
        missing = expected - set(commands.keys())
        assert not missing, f"Missing commands: {missing}"
