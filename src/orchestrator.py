import json
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable
from pathlib import Path

from _runtime.llm_runtime import generate_llm_text
from _runtime.tool_runtime import strip_fence
from _runtime.mcp_runtime import mcp_manager
from knowledge import ProblemKnowledgeStore
from skills import execute_skill, resolve_skills_dir, list_skill_bundles
from tools import execute_tool_dispatch, build_dispatch_index, resolve_tools_dir, list_tool_definitions


from session import ChatSession, ChatMessage

class State(Enum):
    PLANNING = "PLANNING"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    COMPLETE = "COMPLETE"

class DPEFOrchestrator:
    def __init__(
        self,
        knowledge_store: ProblemKnowledgeStore,
        max_steps: int = 5
    ):
        self.tools_dir = resolve_tools_dir()
        self.skills_dir = resolve_skills_dir()
        self.knowledge_store = knowledge_store
        self.execute_skill_func = execute_skill
        self.execute_tool_func = execute_tool_dispatch
        self.max_steps = max_steps
        self.checklist: List[str] = []
        self.action_history: Set[str] = set()

    def list_tools(self):
        return self.tools_dir.iterdir()
   
    def list_skills(self):
        return self.skills_dir.iterdir()
    
    def run_task(
        self, 
        session: ChatSession, 
        provider: str, 
        model: str, 
        observer: Optional[Any] = None,
        confirm_func: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> str:
        state = State.PLANNING
        latest_feedback = ""
        self.checklist = []
        self.action_history = set()

        for step in range(1, self.max_steps + 1):
            prompt = self._build_prompt_for_state(state, session, latest_feedback, step)
            response = generate_llm_text(provider, model, prompt)
            
            if state == State.PLANNING:
                self._update_checklist(response)
                if self.checklist:
                    if observer and hasattr(observer, 'on_plan_updated'):
                        observer.on_plan_updated(self.checklist)
                    state = State.EXECUTE
                    continue
                else:
                    return strip_fence(response)

            action = self._try_parse_action(response)
            if not action:
                return strip_fence(response)

            action_key = f"{action['name']}:{json.dumps(action.get('args', {}), sort_keys=True)}"
            if action_key in self.action_history:
                latest_feedback = "REPETITION ERROR: You are repeating an action. Try a different approach."
                continue
            self.action_history.add(action_key)

            if observer and hasattr(observer, 'on_action_started'):
                observer.on_action_started(action)
            
            result = self._execute_action(action, provider, model, confirm_func)
            
            if observer and hasattr(observer, 'on_action_finished'):
                observer.on_action_finished(action, result)

            session.add_message("assistant", f"[action] {action['action']} {action['name']}")
            feedback = result['output'] if result['ok'] else f"Error: {result['error']}"
            session.add_message("assistant", f"[action-result]\n{feedback}")
            
            latest_feedback = feedback
            state = State.EXECUTE

        final_prompt = self._build_prompt_for_state(State.VERIFY, session, latest_feedback, self.max_steps)
        return strip_fence(generate_llm_text(provider, model, final_prompt))

    def _update_checklist(self, response: str):
        self.checklist = []
        for line in response.splitlines():
            line = line.strip()
            if line.startswith("- [") or line.startswith("- ") or line.startswith("* ") or (len(line) > 2 and line[0].isdigit() and line[1] == '.'):
                self.checklist.append(line)

    def _execute_action(
        self, 
        action: Dict[str, Any], 
        provider: str, 
        model: str,
        confirm_func: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> Dict[str, Any]:
        action_name = action['name']
        action_type = action['action']
        args = action.get('args', {})

        # Handle MCP Actions (prefixed with mcp_)
        if action_name.startswith("mcp_"):
            # Check confirmation for MCP
            confirmed = False
            if confirm_func:
                confirmed = confirm_func(action)
            
            if not confirmed:
                return {"ok": False, "error": "Action cancelled by user."}

            # Parse server and original tool name
            # Format was mcp_{server}_{tool}
            parts = action_name.split("_", 2)
            if len(parts) < 3:
                return {"ok": False, "error": f"Invalid MCP action name: {action_name}"}
            
            server_name = parts[1]
            original_tool_name = parts[2]
            return mcp_manager.call_tool(server_name, original_tool_name, args)

        # Default to safe (unconfirmed)
        confirmed = False
        if confirm_func:
            confirmed = confirm_func(action)

        try:
            if action_type == "skill":
                result = self.execute_skill_func(action_name, args, confirmed, provider, model, self.skills_dir, self.tools_dir)
            else:
                result = self.execute_tool_func(action_name, args, confirmed, provider, model, self.tools_dir)
            return result
        except Exception as e:
            return {"ok": False, "error": str(e), "data": {}}

    def _try_parse_action(self, text: str) -> Optional[Dict[str, Any]]:
        cleaned = strip_fence(text)
        # Try JSON
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and ("action" in data or "tool" in data or "name" in data):
                return {
                    "action": data.get("action", data.get("actionType", "tool")),
                    "name": data.get("name", data.get("tool", "")),
                    "args": data.get("args", data.get("params", {}))
                }
        except:
            pass
            
        # Try heuristic parsing [action] name [args] ...
        # (Simplified version of Java logic)
        match = re.search(r'\[action\]\s*(\w+).*\[name\]\s*([\w-]+).*\[args\]\s*(\{.*\})', cleaned, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return {
                    "action": match.group(1),
                    "name": match.group(2),
                    "args": json.loads(match.group(3))
                }
            except:
                pass
        return None

    def _build_prompt_for_state(self, state: State, session: ChatSession, feedback: str, step: int) -> str:
        if state == State.PLANNING:
            return self._build_planning_prompt(session)
        elif state == State.EXECUTE:
            return self._build_execute_prompt(session, feedback, step)
        else:
            return self._build_verify_prompt(session, feedback)

    def _build_planning_prompt(self, session: ChatSession) -> str:
        return f"""
# Phase: PLANNING
Analyze the goal and output a Checklist. Output ONLY the checklist if you are ready to act.

# Rules:
1. USE SKILLS FIRST if they match the goal.
2. If you are unsure about a skill's details, add a step to use `skill-detail-loader`.
3. Format: `- [ ] step description`.

# History
{session.to_transcript()}
"""

    def _build_execute_prompt(self, session: ChatSession, feedback: str, step: int) -> str:
        plan_str = "\n".join(self.checklist)
        capability_index = self._build_capability_index()
        return f"""
# Phase: EXECUTE
Step: {step}/{self.max_steps}

# Current Plan
{plan_str}

# Capability index (Summarized)
{json.dumps(capability_index, ensure_ascii=False, indent=2)}

# Latest Feedback
{feedback}

# Task
Choose one candidate from the capability index above.
If you need more details about a skill (e.g. its internal steps or full parameter list), use `skill-detail-loader`.
Do not invent tool or skill names.
Output ONLY a JSON block for the next action:
{{ "action": "tool|skill", "name": "...", "args": {{ ... }} }}

# History
{session.to_transcript()}
"""

    def _build_capability_index(self) -> dict[str, Any]:
        tools = list_tool_definitions(self.tools_dir)
        skills = list_skill_bundles(self.skills_dir)
        full_index = build_dispatch_index(tools, skills)
        
        # Implementation of "Progressive Disclosure":
        # We strip detailed docs but keep argument names and descriptions.
        # This helps the LLM provide correct arguments on the first try.
        summarized_candidates = []
        for c in full_index.get("candidates", []):
            summarized = {
                "kind": c.get("kind"),
                "name": c.get("name"),
                "summary": c.get("summary"),
                "triggers": c.get("triggers") if c.get("triggers") else [],
                "requiredArgs": c.get("requiredArgs"),
                "optionalArgs": c.get("optionalArgs"),
                "arguments": c.get("arguments") if "arguments" in c else [],
                "priority": c.get("priority")
            }
            summarized_candidates.append(summarized)

        # 3. Add MCP Tools dynamically
        mcp_tools = mcp_manager.list_tools()
        for mt in mcp_tools:
            summarized_candidates.append({
                "kind": "tool", # Map MCP tools as standard tools to LLM
                "name": mt["name"],
                "summary": mt["description"],
                "triggers": [],
                "requiredArgs": mt.get("input_schema", {}).get("required", []),
                "optionalArgs": [], # MCP schema combines all in properties usually
                "arguments": mt.get("input_schema", {}).get("properties", {}),
                "priority": 10 # MCP tools are generally high utility
            })
        
        return {
            "selectionRules": full_index.get("selectionRules"),
            "candidates": summarized_candidates
        }

    def _build_verify_prompt(self, session: ChatSession, feedback: str) -> str:
        return f"""
# Phase: VERIFY
Provide a final summary in Chinese.

Latest Feedback:
{feedback}

# History
{session.to_transcript()}
"""
