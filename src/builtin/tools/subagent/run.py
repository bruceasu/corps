import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Force UTF-8 for stdout and stderr on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def add_runtime_path() -> None:
    # Path(__file__).resolve() is src/builtin/tools/subagent/run.py
    # parents[3] is the 'src' directory
    src_dir = Path(__file__).resolve().parents[3]
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))

add_runtime_path()

from _runtime.llm_runtime import generate_llm_text
from _runtime.tool_runtime import emit_result, failure, success, normalize_optional
from _runtime.engine.executor import AgentNodeExecutor
from _runtime.engine.model import WorkflowNode

def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous sub-agent tool.")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--system-prompt", default="")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--allowed-tools", default="")
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    goal = args.goal
    system_prompt = args.system_prompt
    max_steps = args.max_steps
    allowed_tools_str = args.allowed_tools
    
    provider = normalize_optional(args.provider) or os.getenv("CORPS_PROVIDER", "openai")
    model = normalize_optional(args.model) or os.getenv("CORPS_MODEL", "gpt-4o")

    # Setup tool execution for the sub-agent
    # In a standalone tool, we need to import dispatch logic
    from tools import execute_tool_dispatch, resolve_tools_dir
    from skills import execute_skill, resolve_skills_dir, builtin_skills_dir
    
    tools_dir = resolve_tools_dir()
    skills_dir = resolve_skills_dir()
    bskills_dir = builtin_skills_dir()
    
    def execute_tool_func(tool_name: str, tool_args: Dict[str, Any]) -> Any:
        # Check if it's a skill or tool
        is_skill = False
        if (skills_dir / tool_name).is_dir():
            is_skill = True
        elif bskills_dir and (bskills_dir / tool_name).is_dir():
            is_skill = True
            
        if is_skill:
            # execute_skill(skill_name, args, confirmed, provider, model, tools_dir)
            result = execute_skill(tool_name, tool_args, True, provider, model, tools_dir)
        else:
            result = execute_tool_dispatch(tool_name, tool_args, True, provider, model, tools_dir)
            
        if result.get("ok"):
            return result.get("output")
        else:
            return f"Error: {result.get('error')}"

    # Create a dummy WorkflowNode to satisfy AgentNodeExecutor
    node = WorkflowNode(
        id="subagent_root",
        type="agent",
        arguments={
            "userPrompt": goal,
            "systemPrompt": system_prompt,
            "maxSteps": max_steps,
            "allowedTools": allowed_tools_str
        }
    )

    executor = AgentNodeExecutor(execute_tool_func, generate_llm_text)
    
    context = {
        "provider": provider,
        "model": model
    }

    try:
        # AgentNodeExecutor.execute returns a dict containing its outputKey or the raw result
        result = executor.execute(node, context)
        
        # Extract output and trace
        output = result.get("output", "No output from sub-agent.")
        trace = result.get("trace", [])
        
        data = {
            "goal": goal,
            "maxSteps": max_steps,
            "trace": trace
        }
        
        emit_result(success("subagent", output, data))
    except Exception as e:
        emit_result(failure("subagent", str(e)))
        sys.exit(1)

if __name__ == "__main__":
    main()
