import os
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("CORPS_PYTHON_SCRIPTS_DIR", str(ROOT))
sys.path.insert(0, str(ROOT))

import _runtime.github_mcp as github_mcp  # noqa: E402


class GithubMcpClientTests(unittest.TestCase):
    def test_github_mcp_matches_workflow_tools(self):
        tools = [
            {
                "name": "mcp_github_create_issue",
                "description": "[MCP:github] Create issue",
                "original_name": "create_issue",
                "mcp_server": "github",
            }
        ]
        original_list_tools = github_mcp.mcp_manager.list_tools
        original_call_tool = github_mcp.mcp_manager.call_tool
        called = {}

        def fake_call_tool(server_name, tool_name, arguments):
            called["server_name"] = server_name
            called["tool_name"] = tool_name
            called["arguments"] = arguments
            return {"ok": True, "output": "created", "data": {}}

        try:
            github_mcp.mcp_manager.list_tools = lambda: tools
            github_mcp.mcp_manager.call_tool = fake_call_tool

            client = github_mcp.GithubMCPClient()
            result = client.call("create_issue", {"title": "Fix bug"})

            self.assertTrue(result["ok"])
            self.assertEqual(
                called,
                {
                    "server_name": "github",
                    "tool_name": "create_issue",
                    "arguments": {"title": "Fix bug"},
                },
            )
        finally:
            github_mcp.mcp_manager.list_tools = original_list_tools
            github_mcp.mcp_manager.call_tool = original_call_tool

    def test_parse_arguments_returns_empty_dict_for_blank_input(self):
        self.assertEqual(github_mcp.GithubMCPClient.parse_arguments("create_issue", "   "), {})

    def test_parse_arguments_supports_positional_and_key_value_inputs(self):
        payload = github_mcp.GithubMCPClient.parse_arguments(
            "create_issue",
            'octo-org octo-repo "Fix bug" body="details here"',
        )

        self.assertEqual(
            payload,
            {
                "owner": "octo-org",
                "repo": "octo-repo",
                "title": "Fix bug",
                "body": "details here",
            },
        )

    def test_task_help_includes_positional_args(self):
        client = github_mcp.GithubMCPClient()
        help_rows = client.task_help()

        create_issue = next(item for item in help_rows if item["key"] == "create_issue")
        self.assertIn("owner", create_issue["positional_args"])
        self.assertIn("title", create_issue["positional_args"])

    def test_auth_status_detects_token_vars(self):
        original_token = os.environ.get("GITHUB_TOKEN")
        original_owner = os.environ.get("GITHUB_OWNER")
        try:
            os.environ["GITHUB_TOKEN"] = "ghp_demo"
            os.environ["GITHUB_OWNER"] = "octo-org"

            client = github_mcp.GithubMCPClient()
            status = client.auth_status()

            self.assertTrue(status["has_token"])
            self.assertIn("GITHUB_TOKEN", status["token_vars"])
            self.assertEqual(status["identity_vars"]["GITHUB_OWNER"], "octo-org")
        finally:
            if original_token is None:
                os.environ.pop("GITHUB_TOKEN", None)
            else:
                os.environ["GITHUB_TOKEN"] = original_token
            if original_owner is None:
                os.environ.pop("GITHUB_OWNER", None)
            else:
                os.environ["GITHUB_OWNER"] = original_owner
