import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from _runtime.engine.executor import AgentNodeExecutor
from _runtime.engine.model import WorkflowNode


def test_agent_does_not_execute_invalid_tool_input():
    calls = []
    node = WorkflowNode(id="agent", type="agent", arguments={"userPrompt": "do work", "allowedTools": "read-file"})
    executor = AgentNodeExecutor(lambda name, args: calls.append((name, args)), lambda *_args: '{"action":"tool_call","reasoningSummary":"x","toolName":"read-file","toolInput":"bad"}')

    result = executor.execute(node, {"provider": "openai", "model": "test"})

    assert calls == []
    assert "toolInput" in result["error"]
