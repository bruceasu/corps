import json
import os
import shlex
from dataclasses import dataclass
from typing import Any, Dict, Sequence

from _runtime.mcp_runtime import mcp_manager


@dataclass(frozen=True)
class GithubWorkflowTask:
    key: str
    label: str
    keywords: Sequence[str]
    positional_args: Sequence[str] = ()
    required_args: Sequence[str] = ()


GITHUB_WORKFLOW_TASKS: tuple[GithubWorkflowTask, ...] = (
    GithubWorkflowTask("list_repos", "列出仓库", ("list repositories", "repositories", "repo"), ("owner",), ("owner",)),
    GithubWorkflowTask("list_issues", "列出 Issue", ("list issues", "issues"), ("owner", "repo"), ("owner", "repo")),
    GithubWorkflowTask("create_issue", "创建 Issue", ("create issue", "new issue", "issue create"), ("owner", "repo", "title", "body"), ("owner", "repo", "title")),
    GithubWorkflowTask("list_pull_requests", "列出 PR", ("list pull requests", "pull requests", "prs", "pr"), ("owner", "repo"), ("owner", "repo")),
    GithubWorkflowTask("create_pull_request", "创建 PR", ("create pull request", "open pull request", "pull request create"), ("owner", "repo", "title", "head", "base", "body"), ("owner", "repo", "title", "head", "base")),
    GithubWorkflowTask("comment", "评论", ("add comment", "comment issue", "comment pull request", "comment"), ("owner", "repo", "number", "body"), ("owner", "repo", "number", "body")),
    GithubWorkflowTask("merge_pull_request", "合并 PR", ("merge pull request", "merge pr", "merge"), ("owner", "repo", "number"), ("owner", "repo", "number")),
    GithubWorkflowTask("workflow_dispatch", "触发工作流", ("dispatch workflow", "run workflow", "workflow dispatch", "workflow"), ("owner", "repo", "workflow"), ("owner", "repo", "workflow")),
)


class GithubMCPClient:
    def __init__(self, server_name: str = "github"):
        self.server_name = server_name

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool for tool in mcp_manager.list_tools() if tool.get("mcp_server") == self.server_name]

    def describe_tasks(self) -> list[dict[str, Any]]:
        tools = self.list_tools()
        return [self._match_task(task, tools) for task in GITHUB_WORKFLOW_TASKS]

    def task_help(self) -> list[dict[str, Any]]:
        return [
            {
                "key": task.key,
                "label": task.label,
                "positional_args": list(task.positional_args),
                "required_args": list(task.required_args),
            }
            for task in GITHUB_WORKFLOW_TASKS
        ]

    def auth_status(self) -> dict[str, Any]:
        token_vars = ["GITHUB_TOKEN", "GH_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GITHUB_MCP_TOKEN"]
        active_token_vars = [name for name in token_vars if os.getenv(name)]
        identity_vars = ["GITHUB_OWNER", "GITHUB_USERNAME", "GITHUB_USER", "GITHUB_ACCOUNT"]
        active_identity_vars = {name: os.getenv(name) for name in identity_vars if os.getenv(name)}
        return {
            "server_name": self.server_name,
            "token_vars": active_token_vars,
            "identity_vars": active_identity_vars,
            "has_token": bool(active_token_vars),
            "multiple_tokens": len(active_token_vars) > 1,
        }

    def call(self, task_key: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        task = next((item for item in GITHUB_WORKFLOW_TASKS if item.key == task_key), None)
        if task is None:
            return {"ok": False, "error": f"Unknown GitHub workflow task: {task_key}", "data": {}}

        tools = self.list_tools()
        if not tools:
            return {"ok": False, "error": f"No MCP tools found for server '{self.server_name}'", "data": {}}

        tool = self._match_task(task, tools).get("tool")
        if not tool:
            return {
                "ok": False,
                "error": f"Unable to match GitHub workflow task '{task.label}' to an MCP tool",
                "data": {"available_tools": [item.get("name") for item in tools]},
            }

        original_name = tool.get("original_name") or tool.get("name", "")
        return mcp_manager.call_tool(self.server_name, original_name, arguments)

    def _match_task(self, task: GithubWorkflowTask, tools: Sequence[dict[str, Any]]) -> dict[str, Any]:
        best_tool = None
        best_score = -1
        for tool in tools:
            score = self._score_tool(task, tool)
            if score > best_score:
                best_score = score
                best_tool = tool

        return {
            "key": task.key,
            "label": task.label,
            "tool": best_tool,
            "available": best_tool is not None and best_score > 0,
        }

    def _score_tool(self, task: GithubWorkflowTask, tool: dict[str, Any]) -> int:
        text = " ".join(str(tool.get(field, "")).lower() for field in ("name", "description", "original_name"))
        score = 0
        for keyword in task.keywords:
            if keyword in text:
                score += 3
        return score

    @staticmethod
    def parse_arguments(task_key: str, raw: str) -> Dict[str, Any]:
        text = raw.strip()
        if not text:
            return {}
        if text.startswith("{"):
            return json.loads(text)

        task = next((item for item in GITHUB_WORKFLOW_TASKS if item.key == task_key), None)
        tokens = shlex.split(text)
        payload = GithubMCPClient._parse_key_value_args(tokens)
        if task is not None:
            payload.update(GithubMCPClient._parse_positional_args(task, tokens))
        return payload

    @staticmethod
    def _parse_positional_args(task: GithubWorkflowTask, tokens: Sequence[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        positional_names = list(task.positional_args)
        positional_values: list[str] = []

        for token in tokens:
            if "=" in token:
                continue
            positional_values.append(token)

        for index, name in enumerate(positional_names):
            if index >= len(positional_values):
                break
            payload[name] = positional_values[index]

        return payload

    @staticmethod
    def _parse_key_value_args(tokens: Sequence[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for token in tokens:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            payload[key.strip()] = value.strip()
        return payload
