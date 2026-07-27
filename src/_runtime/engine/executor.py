import json
import re
from typing import Any, Dict, Optional, Callable
from .model import WorkflowNode

class NodeExecutor:
    def execute(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()

class AgentNodeExecutor(NodeExecutor):
    def __init__(self, execute_tool_func: Callable[[str, Dict[str, Any]], Any], generate_llm_text_func: Callable[[str, str, str], str]):
        self.execute_tool_func = execute_tool_func
        self.generate_llm_text_func = generate_llm_text_func

    def execute(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        # Extract config
        args = node.arguments
        user_prompt_tpl = args.get("userPrompt", "")
        system_prompt_tpl = args.get("systemPrompt", "You are a helpful assistant.")
        max_steps = int(args.get("maxSteps", 5))
        allowed_tools = args.get("allowedTools", "")
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.split(",") if t.strip()]

        # Initial context
        goal = self._substitute_value(user_prompt_tpl, context)
        
        # Build tool descriptions for the system prompt
        tool_desc = ""
        # Note: We might need tool definitions here, but for now we list names
        if allowed_tools:
            tool_desc = "\nAvailable tools:\n" + "\n".join([f"- {t}" for t in allowed_tools])

        system_prompt = system_prompt_tpl + tool_desc + """
Output ONLY a JSON object in each step:
{"action": "tool_call", "reasoningSummary": "...", "toolName": "...", "toolInput": {}}
OR
{"action": "final_answer", "reasoningSummary": "...", "finalAnswer": "..."}
"""

        trace = []
        provider = context.get("provider", os.getenv("CORPS_PROVIDER", "openai"))
        model = context.get("model", os.getenv("CORPS_MODEL", "gpt-4o"))

        for step in range(max_steps):
            # Build current prompt
            current_prompt = f"Goal: {goal}\n\nTrace:\n"
            for t in trace:
                current_prompt += f"Step {t['step']}:\nAction: {t['action']}\nReasoning: {t['reasoningSummary']}\n"
                if "observation" in t:
                    current_prompt += f"Observation: {t['observation']}\n"
            
            current_prompt += f"\nNow at step {step + 1}. What is your next action?"

            try:
                raw_response = self.generate_llm_text_func(provider, model, f"{system_prompt}\n\n{current_prompt}")
                # Strip code fences
                cleaned = self._strip_fence(raw_response)
                decision = json.loads(cleaned)
                
                action = decision.get("action")
                reasoning = decision.get("reasoningSummary", "")
                
                trace_item = {
                    "step": step + 1,
                    "action": action,
                    "reasoningSummary": reasoning
                }

                if action == "final_answer":
                    final_answer = decision.get("finalAnswer", "")
                    trace_item["finalAnswer"] = final_answer
                    trace.append(trace_item)
                    
                    result = {"output": final_answer, "trace": trace}
                    if node.outputKey:
                        return {node.outputKey: result}
                    return result

                if action == "tool_call":
                    tool_name = decision.get("toolName")
                    tool_input = decision.get("toolInput", {})
                    
                    if tool_name not in allowed_tools:
                        observation = f"Error: Tool '{tool_name}' is not in the allowed list."
                    else:
                        try:
                            observation = self.execute_tool_func(tool_name, tool_input)
                        except Exception as e:
                            observation = f"Error executing tool {tool_name}: {str(e)}"
                    
                    trace_item["toolName"] = tool_name
                    trace_item["toolInput"] = tool_input
                    trace_item["observation"] = observation
                    trace.append(trace_item)
                else:
                    # Unknown action
                    observation = "Error: Unknown action type. Please use 'tool_call' or 'final_answer'."
                    trace_item["observation"] = observation
                    trace.append(trace_item)

            except Exception as e:
                return {"error": f"Agent loop failed at step {step + 1}: {str(e)}", "trace": trace}

        return {"output": "Max steps reached", "trace": trace}

    def _substitute_value(self, value: Any, context: Dict[str, Any]) -> Any:
        # Re-use logic from ToolNodeExecutor or move to base class
        if isinstance(value, str):
            def replace_match(match):
                var_path = match.group(1)
                parts = var_path.split('.')
                curr = context
                for part in parts:
                    if isinstance(curr, dict) and part in curr:
                        curr = curr[part]
                    else:
                        return match.group(0)
                return str(curr) if curr is not None else ""
            return re.sub(r'\$\{([^}]+)\}', replace_match, value)
        return value

    def _strip_fence(self, text: str) -> str:
        trimmed = text.strip()
        if trimmed.startswith("```"):
            trimmed = re.sub(r"^```(?:json)?\s*", "", trimmed)
            trimmed = re.sub(r"\s*```$", "", trimmed)
        return trimmed.strip()


class ToolNodeExecutor(NodeExecutor):
    def __init__(self, execute_tool_func: Callable[[str, Dict[str, Any]], Any]):
        self.execute_tool_func = execute_tool_func

    def execute(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        # Substitute variables in arguments
        substituted_args = self._substitute_variables(node.arguments, context)
        
        # Execute the tool
        result = self.execute_tool_func(node.toolName, substituted_args)
        
        # If outputKey is defined, wrap the result
        if node.outputKey:
            return {node.outputKey: result}
        return result if isinstance(result, dict) else {"output": result}

    def _substitute_variables(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key, value in arguments.items():
            result[key] = self._substitute_value(value, context)
        return result

    def _substitute_value(self, value: Any, context: Dict[str, Any]) -> Any:
        if isinstance(value, str):
            # Simple ${var} substitution
            # Supports ${input.key} and ${previousStepOutputKey}
            def replace_match(match):
                var_path = match.group(1)
                parts = var_path.split('.')
                
                curr = context
                for part in parts:
                    if isinstance(curr, dict) and part in curr:
                        curr = curr[part]
                    else:
                        return match.group(0) # Keep as is if not found
                return str(curr) if curr is not None else ""

            return re.sub(r'\$\{([^}]+)\}', replace_match, value)
        elif isinstance(value, dict):
            return {k: self._substitute_value(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._substitute_value(v, context) for v in value]
        return value
