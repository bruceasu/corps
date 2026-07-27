import sys
import os
from pathlib import Path

# Add engine to path
sys.path.append(str(Path(__file__).resolve().parent))

from engine.model import WorkflowNode, WorkflowEdge, WorkflowConfig
from engine.parser import SkillParser
from engine.workflow_engine import WorkflowEngine

def mock_execute_tool(tool_name, args):
    print(f"Mock executing tool: {tool_name} with args: {args}")
    if tool_name == "youtube-transcript":
        return "Transcript for " + args.get("input", "unknown")
    if tool_name == "llm":
        return "Summary of: " + args.get("prompt", "")
    return {"result": f"Executed {tool_name}"}

def test_skill_execution():
    skill_def = {
        "name": "test-skill",
        "steps": [
            {
                "id": "fetch",
                "type": "tool",
                "toolName": "youtube-transcript",
                "outputKey": "transcript",
                "arguments": {
                    "input": "${input.url}"
                }
            },
            {
                "id": "summarize",
                "type": "tool",
                "toolName": "llm",
                "outputKey": "summary",
                "arguments": {
                    "prompt": "Summarize this: ${transcript}"
                }
            }
        ]
    }
    
    parser = SkillParser()
    config = parser.parse_skill(skill_def)
    
    engine = WorkflowEngine(mock_execute_tool)
    result = engine.execute(config, {"url": "https://youtu.be/abc"})
    
    print("Final context:", result)
    assert "transcript" in result
    assert "summary" in result
    assert result["summary"] == "Summary of: Summarize this: Transcript for https://youtu.be/abc"

if __name__ == "__main__":
    test_skill_execution()
    print("Test passed!")
