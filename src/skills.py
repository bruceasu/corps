import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# Import runtime utilities
try:
    from _runtime.tool_runtime import emit_result, failure, load_json, normalize_optional, success
    from _runtime.llm_runtime import generate_llm_text
    from _runtime.engine.parser import SkillParser
    from _runtime.engine.workflow_engine import WorkflowEngine
except ImportError:
    # Fallback for different execution contexts
    from tool_runtime import emit_result, failure, load_json, normalize_optional, success
    from llm_runtime import generate_llm_text
    from engine.parser import SkillParser
    from engine.workflow_engine import WorkflowEngine

def resolve_skills_dir() -> Path:
    env_skills_dir = os.getenv("CORPS_SKILLS_DIR")
    if env_skills_dir and env_skills_dir.strip():
        return Path(env_skills_dir).expanduser().resolve()
    # default to ~/.config/corps/skills for user skills
    return Path.home() / ".config" / "corps" / "skills"

def builtin_skills_dir() -> Path:
    return Path(__file__).resolve().parent / "builtin" / "skills"

def load_skill_definition(skill_home: Path) -> dict[str, object]:
    yaml_path = None
    for candidate in ("skill.yaml", "skill.yml", "skill.json"):
        maybe = skill_home / candidate
        if maybe.is_file():
            yaml_path = maybe
            break
    if yaml_path is None:
        # Return a minimal definition if YAML is missing to allow Markdown-only skills
        return {"name": skill_home.name, "description": "", "steps": []}
    if yaml_path.suffix == ".json":
        return load_json(yaml_path.read_text(encoding="utf-8"))
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("skill definition must be a mapping")
        return loaded
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "PyYAML is required to load skill.yaml files."
        ) from exc

def build_skill_markdown_fallback(definition: dict[str, object], skill_name: str) -> str:
    title = str(definition.get("name") or skill_name).strip() or skill_name
    description = str(definition.get("description") or "").strip()
    detail = definition.get("detail")
    example = definition.get("example")
    lines = [f"# {title}", ""]
    if description:
        lines.append(description)
        lines.append("")
    if isinstance(detail, str) and detail.strip():
        lines.append(detail.strip())
        lines.append("")
    elif isinstance(detail, list):
        for item in detail:
            text = str(item).strip()
            if text:
                lines.append(f"- {text}")
        lines.append("")
    if example:
        lines.append("## Example")
        lines.append("")
        lines.append(str(example).strip())
        lines.append("")
    lines.append("This skill does not yet have a dedicated SKILL.md file.")
    return "\n".join(line for line in lines if line is not None).strip()

def load_skill_markdown(skill_home: Path, definition: dict[str, object] | None = None) -> str:
    for candidate in ("SKILL.md", "skill.md", "README.md"):
        maybe = skill_home / candidate
        if maybe.is_file():
            return maybe.read_text(encoding="utf-8")
    skill_def = definition if definition is not None else load_skill_definition(skill_home)
    return build_skill_markdown_fallback(skill_def, skill_home.name)

def load_skill_bundle(skill_home: Path) -> dict[str, object]:
    definition = load_skill_definition(skill_home)
    return {
        "name": str(definition.get("name") or skill_home.name),
        "markdown": load_skill_markdown(skill_home, definition),
        "yaml": definition,
    }

def list_skill_definitions(skills_dir: Path) -> list[dict[str, object]]:
    skills: list[dict[str, object]] = []
    seen: set[str] = set()

    # builtin skills first
    bdir = builtin_skills_dir()
    if bdir.is_dir():
        for child in sorted(bdir.iterdir()):
            if not child.is_dir():
                continue
            try:
                definition = load_skill_definition(child)
                name = str(definition.get("name") or child.name)
                skills.append(definition)
                seen.add(name)
            except Exception:
                continue

    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if name in seen:
                continue
            try:
                definition = load_skill_definition(child)
                skills.append(definition)
                seen.add(name)
            except Exception:
                continue

    return skills

def list_skill_bundles(skills_dir: Path) -> list[dict[str, object]]:
    skills: list[dict[str, object]] = []
    seen: set[str] = set()

    bdir = builtin_skills_dir()
    if bdir.is_dir():
        for child in sorted(bdir.iterdir()):
            if not child.is_dir():
                continue
            try:
                bundle = load_skill_bundle(child)
                name = str(bundle.get("name") or child.name)
                skills.append(bundle)
                seen.add(name)
            except Exception:
                continue

    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if name in seen:
                continue
            try:
                bundle = load_skill_bundle(child)
                skills.append(bundle)
                seen.add(name)
            except Exception:
                continue

    return skills

def extract_arg_names(definition: dict[str, object], required_only: bool | None = None) -> list[str]:
    names: list[str] = []
    for arg_def in definition.get("arguments") or []:
        if not isinstance(arg_def, dict):
            continue
        if required_only is True and not arg_def.get("required"):
            continue
        if required_only is False and arg_def.get("required"):
            continue
        name = str(arg_def.get("name") or "").strip()
        if name:
            names.append(name)
    return names

def build_skill_card(skill: dict[str, object]) -> dict[str, object]:
    yaml_data = skill.get("yaml") if isinstance(skill.get("yaml"), dict) else {}
    markdown = str(skill.get("markdown") or "").strip()
    steps = yaml_data.get("steps") if isinstance(yaml_data, dict) else []
    step_summaries: list[dict[dict[str, object]]] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        step_summaries.append({
            "id": str(step.get("id") or "").strip(),
            "type": str(step.get("type") or "tool").strip(),
            "toolName": str(step.get("toolName") or "").strip(),
            "outputKey": str(step.get("outputKey") or "").strip(),
        })
    return {
        "kind": "skill",
        "name": str(yaml_data.get("name") or skill.get("name") or "").strip(),
        "summary": str(yaml_data.get("description") or "").strip(),
        "steps": step_summaries,
        "markdown": markdown,
    }

def execute_skill(skill_name: str, args: dict[str, object], confirmed: bool, provider: str, model: str, tools_dir: Path) -> dict[str, object]:
    # Circular dependency mitigation
    from tools import execute_external, load_tool_definition, builtin_tools_dir
    
    skills_dir = resolve_skills_dir()
    skill_home = skills_dir / skill_name
    if not skill_home.is_dir():
        # Try builtin skills
        bdir = builtin_skills_dir()
        alt = bdir / skill_name
        if alt.is_dir():
            skill_home = alt
        else:
            raise ValueError(f"Unknown skill: {skill_name}")

    definition = load_skill_definition(skill_home)

    parser = SkillParser()
    config = parser.parse_skill(definition)

    def engine_execute_tool(tool_name: str, tool_args: dict[str, Any]) -> Any:
        tool_home = tools_dir / tool_name
        if not tool_home.is_dir():
            # Try builtin tools
            alt = builtin_tools_dir() / tool_name
            if alt.is_dir():
                tool_home = alt
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
        
        tool_def = load_tool_definition(tool_home)
        envelope = execute_external(tool_name, tool_home, tool_def, json.dumps(tool_args, ensure_ascii=False), confirmed, provider, model)
        if not envelope.get("ok"):
            raise RuntimeError(f"Tool {tool_name} failed: {envelope.get('error')}")

        # Try to return structured data if possible, else output string
        output = envelope.get("output")
        if output and isinstance(output, str) and (output.strip().startswith("{") or output.strip().startswith("[")):
            try:
                return json.loads(output)
            except Exception:
                pass
        return output

    engine = WorkflowEngine(engine_execute_tool, generate_llm_text)
    # Add provider/model to context so executors can use them
    args["provider"] = provider
    args["model"] = model
    final_context = engine.execute(config, args)

    # Determine the "main" output. If the last step has an outputKey, use it.
    output_text = ""
    if definition.get("steps"):
        last_step = definition["steps"][-1]
        last_key = last_step.get("outputKey")
        if last_key and last_key in final_context:
            output_text = str(final_context[last_key])

    if not output_text:
        output_text = str(final_context.get("summary") or final_context.get("output") or "")

    return {
        "ok": True,
        "toolName": skill_name,
        "output": output_text,
        "data": final_context,
        "error": "",
    }

def create_skill_from_session(skill_name: str, session_transcript: str, session_name: str, provider: str, model: str, skills_dir: Path) -> Path:
    target_dir = skills_dir / skill_name
    if target_dir.exists():
        # Auto-rename if exists
        counter = 1
        new_name = f"{skill_name}_{counter}"
        while (skills_dir / new_name).exists():
            counter += 1
            new_name = f"{skill_name}_{counter}"
        skill_name = new_name
        target_dir = skills_dir / skill_name

    prompt = (
        f"Convert the following chat session into a reusable 'SKILL.md' document. "
        f"The document should describe the task, the steps taken, and how to repeat it. "
        f"Use the standard SKILL.md format with Understanding, Steps, and Examples.\n\n"
        f"Session Transcript:\n{session_transcript}"
    )
    skill_md_content = generate_llm_text(provider, model, prompt)
    
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
    
    # Also generate a basic skill.yaml
    skill_yaml = {
        "name": skill_name,
        "description": f"Generated from session {session_name}",
        "steps": [] # To be filled or left for manual adjustment
    }
    try:
        import yaml
        (target_dir / "skill.yaml").write_text(yaml.dump(skill_yaml, allow_unicode=True), encoding="utf-8")
    except ImportError:
        pass
    
    return target_dir

def main() -> None:
    parser = argparse.ArgumentParser(description="Corps Skill Management CLI")
    parser.add_argument("command", choices=["list", "show", "run", "discover"], help="Command to execute")
    parser.add_argument("--name", help="Skill name")
    parser.add_argument("--args", help="JSON arguments for running a skill")
    parser.add_argument("--provider", help="LLM provider")
    parser.add_argument("--model", help="LLM model")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution for tools")

    args = parser.parse_args()
    
    skills_dir = resolve_skills_dir()
    
    if args.command == "list" or args.command == "discover":
        bundles = list_skill_bundles(skills_dir)
        print(f"Found {len(bundles)} skills:")
        for b in bundles:
            desc = b["yaml"].get("description", "No description")
            print(f"  - {b['name']}: {desc}")
            
    elif args.command == "show":
        if not args.name:
            print("Error: --name is required for 'show'")
            sys.exit(1)
            
        skill_home = skills_dir / args.name
        if not skill_home.is_dir():
            skill_home = builtin_skills_dir() / args.name
            
        if not skill_home.is_dir():
            print(f"Error: Skill '{args.name}' not found.")
            sys.exit(1)
            
        bundle = load_skill_bundle(skill_home)
        print(bundle["markdown"])
        
    elif args.command == "run":
        if not args.name:
            print("Error: --name is required for 'run'")
            sys.exit(1)
            
        provider = args.provider or os.getenv("CORPS_PROVIDER")
        model = args.model or os.getenv("CORPS_MODEL")
        
        if not provider or not model:
            print("Error: Provider and model must be specified via --provider/--model or env.")
            sys.exit(1)
            
        try:
            skill_args = json.loads(args.args) if args.args else {}
        except Exception as e:
            print(f"Error parsing --args: {e}")
            sys.exit(1)
            
        from tools import resolve_tools_dir
        tools_dir = resolve_tools_dir()
        
        try:
            result = execute_skill(args.name, skill_args, args.confirm, provider, model, tools_dir)
            if result.get("ok"):
                print(result.get("output"))
                if result.get("data"):
                    # Optionally print data if needed, or just output
                    pass
            else:
                print(f"Error: {result.get('error')}")
                sys.exit(1)
        except Exception as e:
            print(f"Execution failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
