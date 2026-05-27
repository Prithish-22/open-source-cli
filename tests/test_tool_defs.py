"""
tests/test_tool_defs.py
Validate tool schema definitions — no duplicates, required fields present.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from biju.tool_defs import TOOL_SCHEMAS, ALL_TOOL_NAMES, PERMISSION_REQUIRED, READ_ONLY_TOOLS


class TestToolSchemas:
    def test_all_schemas_have_required_fields(self):
        for schema in TOOL_SCHEMAS:
            assert schema["type"] == "function", f"Schema missing type=function: {schema}"
            func = schema["function"]
            assert "name" in func, f"Schema missing function.name: {schema}"
            assert "description" in func, f"Schema missing function.description: {func['name']}"
            assert "parameters" in func, f"Schema missing function.parameters: {func['name']}"
            params = func["parameters"]
            assert params["type"] == "object", f"Parameters not type=object: {func['name']}"
            assert "properties" in params, f"Parameters missing properties: {func['name']}"

    def test_no_duplicate_names(self):
        names = [s["function"]["name"] for s in TOOL_SCHEMAS]
        assert len(names) == len(set(names)), f"Duplicate tool names found: {names}"

    def test_all_tool_names_matches_schemas(self):
        schema_names = {s["function"]["name"] for s in TOOL_SCHEMAS}
        assert ALL_TOOL_NAMES == schema_names

    def test_permission_required_is_subset(self):
        assert PERMISSION_REQUIRED.issubset(ALL_TOOL_NAMES), (
            f"PERMISSION_REQUIRED contains unknown tools: {PERMISSION_REQUIRED - ALL_TOOL_NAMES}"
        )

    def test_read_only_is_subset(self):
        assert READ_ONLY_TOOLS.issubset(ALL_TOOL_NAMES), (
            f"READ_ONLY_TOOLS contains unknown tools: {READ_ONLY_TOOLS - ALL_TOOL_NAMES}"
        )

    def test_no_overlap_permission_and_readonly(self):
        overlap = PERMISSION_REQUIRED & READ_ONLY_TOOLS
        assert not overlap, f"Tools in both PERMISSION_REQUIRED and READ_ONLY_TOOLS: {overlap}"

    def test_expected_tools_present(self):
        expected = {
            "run_command", "read_file", "write_file", "edit_file",
            "list_dir", "search_in_files", "read_file_range",
            "git_status", "git_diff", "git_log",
        }
        assert expected.issubset(ALL_TOOL_NAMES), (
            f"Missing expected tools: {expected - ALL_TOOL_NAMES}"
        )

    def test_descriptions_non_empty(self):
        for schema in TOOL_SCHEMAS:
            desc = schema["function"]["description"]
            assert len(desc.strip()) > 10, (
                f"Description too short for {schema['function']['name']}: '{desc}'"
            )
