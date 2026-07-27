import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any


def runtime_dir() -> Path:
    scripts_dir = os.getenv("CORPS_PYTHON_SCRIPTS_DIR")
    if scripts_dir:
        return Path(scripts_dir).resolve() / "_runtime"
    return Path(__file__).resolve().parent / "_runtime"


def add_runtime_path() -> None:
    sys.path.insert(0, str(runtime_dir()))


add_runtime_path()

from _runtime.tool_runtime import emit_result, failure, load_json, normalize_optional, parse_bool, parse_int, success, strip_fence  # noqa: E402
from _runtime.llm_runtime import generate_llm_text  # noqa: E402
from _runtime.engine.parser import SkillParser  # noqa: E402
from _runtime.engine.workflow_engine import WorkflowEngine  # noqa: E402

from skills import (
    resolve_skills_dir,
    builtin_skills_dir,
    load_skill_definition,
    load_skill_markdown,
    load_skill_bundle,
    list_skill_definitions,
    list_skill_bundles,
    build_skill_card,
    execute_skill
)


def resolve_tools_dir(explicit_tools_dir: str | None = None) -> Path:
    if explicit_tools_dir and explicit_tools_dir.strip():
        return Path(explicit_tools_dir).expanduser().resolve()
    env_tools_dir = os.getenv("CORPS_TOOLS_DIR")
    if env_tools_dir and env_tools_dir.strip():
        return Path(env_tools_dir).expanduser().resolve()
    # default to ~/.config/corps/tools for user tools
    return Path.home() / ".config" / "corps" / "tools"


def builtin_tools_dir() -> Path:
    return Path(__file__).resolve().parents[0] / "builtin" / "tools"


def load_tool_definition(tool_home: Path) -> dict[str, object]:
    yaml_path = None
    for candidate in ("tool.yaml", "tool.yml", "tool.json"):
        maybe = tool_home / candidate
        if maybe.is_file():
            yaml_path = maybe
            break
    if yaml_path is None:
        raise FileNotFoundError(f"Missing tool definition in {tool_home}")
    if yaml_path.suffix == ".json":
        return load_json(yaml_path.read_text(encoding="utf-8"))
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("tool definition must be a mapping")
        return loaded
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyYAML is required to load tool.yaml files for the Python dispatcher."
        ) from exc


def normalize_args(args_obj: object) -> dict[str, object]:
    if isinstance(args_obj, dict):
        return dict(args_obj)
    return {}


def list_tool_definitions(tools_dir: Path) -> list[dict[str, object]]:
    tools: list[dict[str, object]] = []
    seen: set[str] = set()

    # Load builtin tools first (cannot be overridden)
    bdir = builtin_tools_dir()
    if bdir.is_dir():
        for child in sorted(bdir.iterdir()):
            if not child.is_dir():
                continue
            try:
                definition = load_tool_definition(child)
                name = str(definition.get("name") or child.name)
                tools.append(definition)
                seen.add(name)
            except Exception:
                continue

    # Then load external tools if they don't override builtin ones
    if tools_dir.is_dir():
        for child in sorted(tools_dir.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if name in seen:
                continue
            try:
                definition = load_tool_definition(child)
                tools.append(definition)
                seen.add(name)
            except Exception:
                continue

    return tools


def apply_defaults(definition: dict[str, object], args: dict[str, object]) -> dict[str, object]:
    result = dict(args)
    for arg_def in definition.get("arguments") or []:
        if not isinstance(arg_def, dict):
            continue
        name = str(arg_def.get("name") or "").strip()
        if not name or name in result:
            continue
        default_value = arg_def.get("defaultValue")
        if default_value is not None:
            result[name] = default_value
    return result


def missing_required_args(definition: dict[str, object], args: dict[str, object]) -> list[str]:
    missing: list[str] = []
    for arg_def in definition.get("arguments") or []:
        if not isinstance(arg_def, dict):
            continue
        if not arg_def.get("required"):
            continue
        name = str(arg_def.get("name") or "").strip()
        if not name:
            continue
        value = args.get(name)
        if value is None or str(value).strip() == "":
            missing.append(name)
    return missing


def build_fill_args_prompt(definition: dict[str, object], missing: list[str], existing_args: dict[str, object]) -> str:
    lines = [
        "You are an assistant that helps fill missing tool invocation parameters.",
        f"Tool: {definition.get('name') or ''}",
        f"Required missing parameters: {', '.join(missing)}",
        "",
        "Parameter details:",
    ]
    for arg_def in definition.get("arguments") or []:
        if not isinstance(arg_def, dict):
            continue
        name = str(arg_def.get("name") or "").strip()
        if not name or name not in missing:
            continue
        line = f"- {name}: "
        description = str(arg_def.get("description") or "").strip()
        if description:
            line += description + " "
        arg_type = str(arg_def.get("type") or "").strip()
        if arg_type:
            line += f"(type: {arg_type})"
        lines.append(line)
    lines.extend([
        "",
        "Existing args (do not change unless needed):",
        json.dumps(existing_args or {}, ensure_ascii=False),
        "",
        "Please provide a JSON object that supplies values for the missing parameters only.",
        "Return ONLY valid JSON (no surrounding text). Use best effort based on the parameter descriptions.",
    ])
    return "\n".join(lines)


def try_fill_missing_args(definition: dict[str, object], missing: list[str], args: dict[str, object], provider: str, model: str) -> dict[str, object]:
    if not missing:
        return args
    if not provider or not model:
        return args
    prompt = build_fill_args_prompt(definition, missing, args)
    filled_raw = generate_llm_text(provider, model, prompt)
    filled = load_json(filled_raw)
    if isinstance(filled, dict) and filled:
        merged = dict(args)
        merged.update(filled)
        return merged
    return args


def render_token(token: str, args: dict[str, object], tool_home: Path, scripts_dir: Path) -> str:
    rendered = token.replace("${toolHome}", str(tool_home).replace("\\", "/"))
    rendered = rendered.replace("${pythonScriptsDir}", str(scripts_dir).replace("\\", "/"))
    rendered = rendered.replace("${pythonHome}", str(scripts_dir).replace("\\", "/"))
    for key, value in args.items():
        placeholder = "${" + key + "}"
        if placeholder in rendered:
            rendered = rendered.replace(placeholder, "" if value is None else str(value))
    return rendered


def compact_text(text: str, max_lines: int = 10, max_chars: int = 1200) -> str:
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not normalized:
        return ""
    lines = [line for line in normalized.splitlines() if line.strip()]
    clipped = lines[:max_lines]
    result = "\n".join(clipped)
    if len(result) > max_chars:
        result = result[: max_chars - 3].rstrip() + "..."
    return result


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


def build_tool_card(tool: dict[str, object]) -> dict[str, object]:
    tool_spec = tool.get("tool") if isinstance(tool.get("tool"), dict) else {}
    return {
        "kind": "tool",
        "name": str(tool.get("name") or "").strip(),
        "summary": str(tool.get("description") or "").strip(),
        "triggers": tool.get("triggers") if isinstance(tool.get("triggers"), list) else [],
        "requiredArgs": extract_arg_names(tool, required_only=True),
        "optionalArgs": extract_arg_names(tool, required_only=False),
        "autoExecuteAllowed": bool(tool_spec.get("autoExecuteAllowed", False)) if isinstance(tool_spec, dict) else False,
        "toolType": str(tool_spec.get("type") or "").strip(),
        "execution": {
            "program": str(tool_spec.get("program") or "").strip() if isinstance(tool_spec, dict) else "",
            "workingDirectory": str(tool_spec.get("workingDirectory") or ".").strip() if isinstance(tool_spec, dict) else ".",
        },
    }


def candidate_complexity(candidate: dict[str, object]) -> int:
    kind = str(candidate.get("kind") or "").strip()
    required = candidate.get("requiredArgs") if isinstance(candidate.get("requiredArgs"), list) else []
    optional = candidate.get("optionalArgs") if isinstance(candidate.get("optionalArgs"), list) else []
    arg_count = len(required) + len(optional)
    if kind == "skill":
        plan = candidate.get("executionPlan") if isinstance(candidate.get("executionPlan"), dict) else {}
        step_count = int(plan.get("stepCount") or 0)
        return step_count * 10 + arg_count
    return arg_count


def build_candidate_card(candidate: dict[str, object]) -> dict[str, object]:
    kind = str(candidate.get("kind") or "").strip()
    required = candidate.get("requiredArgs") if isinstance(candidate.get("requiredArgs"), list) else []
    optional = candidate.get("optionalArgs") if isinstance(candidate.get("optionalArgs"), list) else []
    card: dict[str, object] = {
        "kind": kind,
        "name": str(candidate.get("name") or "").strip(),
        "summary": str(candidate.get("summary") or "").strip(),
        "requiredArgs": required,
        "optionalArgs": optional,
        "complexity": candidate_complexity(candidate),
    }
    if kind == "tool":
        card["why"] = "atomic tool"
        card["autoExecuteAllowed"] = bool(candidate.get("autoExecuteAllowed", False))
    elif kind == "skill":
        plan = candidate.get("executionPlan") if isinstance(candidate.get("executionPlan"), dict) else {}
        human_docs = str(candidate.get("humanDocs") or "").strip()
        if human_docs:
            card["summary"] = human_docs
        card["why"] = "multi-step skill"
        card["steps"] = int(plan.get("stepCount") or 0)
        card["autoExecuteAllowed"] = bool(plan.get("autoExecuteAllowed", False))
        card["humanDocs"] = human_docs
        step_tools = [
            str(step.get("toolName") or "").strip()
            for step in (plan.get("steps") or [])
            if isinstance(step, dict) and str(step.get("toolName") or "").strip()
        ]
        if step_tools:
            card["planSummary"] = {"stepTools": step_tools[:5]}
    return card


def build_dispatch_index(tools: list[dict[str, object]], skills: list[dict[str, object]]) -> dict[str, object]:
    raw_candidates = [build_tool_card(tool) for tool in tools] + [build_skill_card(skill) for skill in skills]
    ordered = sorted(
        raw_candidates,
        key=lambda candidate: (
            candidate_complexity(candidate),
            0 if str(candidate.get("kind") or "") == "tool" else 1,
            str(candidate.get("name") or ""),
        ),
    )
    return {
        "selectionRules": [
            "Choose exactly one capability.",
            "Use the smallest capability that fully satisfies the user instruction.",
            "Prefer a skill when the request matches a named multi-step workflow or combines multiple tools.",
            "Prefer a tool when the request is a single atomic action or direct primitive operation.",
            "Do not invent capability names or arguments.",
            "Return the first candidate that fully satisfies the instruction.",
        ],
        "candidates": [
            {
                **build_candidate_card(candidate),
                "priority": index + 1,
            }
            for index, candidate in enumerate(ordered)
        ],
    }


def build_dispatch_prompt(user_instruction: str, tools: list[dict[str, object]], skills: list[dict[str, object]]) -> str:
    index = build_dispatch_index(tools, skills)
    lines = [
        "You are a strict dispatcher.",
        "Output ONLY valid JSON with this schema:",
        '{ "actionType": "tool" | "skill", "name": "capability-name", "args": { ... }, "confirm": true|false }',
        "",
        "Candidate priority rules:",
    ]
    for rule in index.get("selectionRules") or []:
        lines.append(f"- {rule}")
    lines.extend([
        "",
        "Candidate priority JSON:",
        json.dumps(
            {
                "selectionRules": index.get("selectionRules") or [],
                "candidates": index.get("candidates") or [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "User instruction:",
        user_instruction or "",
    ])
    return "\n".join(lines)


def parse_dispatch_intent(raw: str) -> dict[str, object]:
    intent = load_json(strip_fence(raw))
    if not isinstance(intent, dict):
        raise ValueError("Dispatcher LLM did not return a JSON object")
    action_type = str(intent.get("actionType") or intent.get("action") or "tool").strip().lower()
    name = str(intent.get("name") or intent.get("tool") or "").strip()
    if not name:
        raise ValueError("Dispatcher LLM did not return a name")
    args = intent.get("args")
    if not isinstance(args, dict):
        args = {}
    confirm = bool(intent.get("confirm") or intent.get("confirmed") or False)
    return {
        "actionType": action_type if action_type in {"tool", "skill"} else "tool",
        "name": name,
        "args": args,
        "confirm": confirm,
    }


def resolve_launcher(program: str) -> list[str]:
    if program.lower() in {"python", "python3", "py"}:
        return [sys.executable]
    return [program]


def dispatch_capability(user_instruction: str, tools_dir: Path, provider: str, model: str, require_confirm: bool) -> dict[str, object]:
    tools = list_tool_definitions(tools_dir)
    skills = list_skill_bundles(resolve_skills_dir())
    prompt = build_dispatch_prompt(user_instruction, tools, skills)
    raw = generate_llm_text(provider, model, prompt)
    intent = parse_dispatch_intent(raw)
    action_type = str(intent.get("actionType") or "tool").lower()
    name = str(intent.get("name") or "").strip()
    args = intent.get("args") if isinstance(intent.get("args"), dict) else {}
    confirm = bool(intent.get("confirm") or False)
    if require_confirm and action_type == "tool":
        confirm = True

    if action_type == "skill":
        return {
            "ok": True,
            "toolName": name,
            "output": "",
            "data": {
                "actionType": "skill",
                "name": name,
                "args": args,
                "confirm": confirm,
            },
            "error": "",
        }

    if action_type != "tool":
        raise ValueError(f"Unsupported action type: {action_type}")

    definition = next((tool for tool in tools if str(tool.get("name") or "") == name), None)
    if definition is None:
        raise ValueError(f"Unknown tool: {name}")
    tool_home = tools_dir / name
    return execute_external(name, tool_home, definition, json.dumps(args, ensure_ascii=False), confirm, provider, model)


def execute_external(tool_name: str, tool_home: Path, definition: dict[str, object], args_json: str, confirmed: bool, provider: str, model: str) -> dict[str, object]:
    tool_spec = definition.get("tool")
    if not isinstance(tool_spec, dict):
        raise ValueError("tool definition is missing tool spec")
    if str(tool_spec.get("type") or "").lower() != "external-command":
        raise ValueError(f"Unsupported tool type: {tool_spec.get('type')}")

    try:
        raw_args = normalize_args(load_json(args_json))
    except Exception as exc:
        raise ValueError(f"Failed to parse --args-json={args_json!r}: {exc}") from exc
    args = apply_defaults(definition, raw_args)
    missing = missing_required_args(definition, args)
    if missing:
        filled = try_fill_missing_args(definition, missing, args, provider, model)
        args = apply_defaults(definition, filled)
        missing = missing_required_args(definition, args)
        if missing:
            return {
                "ok": False,
                "toolName": tool_name,
                "output": "",
                "data": {"missingArgs": missing},
                "error": "Missing required arguments: " + ", ".join(missing),
            }

    auto_execute = bool(definition.get("autoExecuteAllowed", False))
    if not auto_execute and isinstance(tool_spec, dict):
        auto_execute = bool(tool_spec.get("autoExecuteAllowed", False))

    if not auto_execute and not confirmed:
        return {
            "ok": False,
            "toolName": tool_name,
            "output": "",
            "data": {},
            "error": "Tool requires confirmation. Re-run with --confirm to execute.",
        }

    scripts_dir = runtime_dir().parent
    command: list[str] = []
    program = str(tool_spec.get("program") or "")
    if not program:
        raise ValueError("Missing external command program")
    command.extend(resolve_launcher(program))
    for token in tool_spec.get("args") or []:
        rendered = render_token(str(token), args, tool_home, scripts_dir)
        command.append(rendered)

    # Inject PYTHONPATH to include _runtime and scripts_dir for external tools
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    r_dir = str(runtime_dir())
    s_dir = str(scripts_dir)
    
    # We want both s_dir (for from _runtime.xxx) and r_dir (for from xxx)
    paths_to_add = [r_dir, s_dir]
    new_pythonpath = os.pathsep.join(paths_to_add)
    
    if current_pythonpath:
        env["PYTHONPATH"] = f"{new_pythonpath}{os.pathsep}{current_pythonpath}"
    else:
        env["PYTHONPATH"] = new_pythonpath

    completed = subprocess.run(command, cwd=str(tool_home), capture_output=True, text=True, env=env)
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0:
        return {
            "ok": False,
            "toolName": tool_name,
            "output": "",
            "data": {"command": command, "exitCode": completed.returncode},
            "error": stderr or f"tool failed with exit code {completed.returncode}",
        }

    if stdout.startswith("{") and stdout.endswith("}"):
        try:
            envelope = load_json(stdout)
            if isinstance(envelope, dict) and "ok" in envelope and "toolName" in envelope:
                return envelope
        except Exception:
            pass

    return {
        "ok": True,
        "toolName": tool_name,
        "output": stdout,
        "data": {"command": command, "exitCode": completed.returncode},
        "error": "",
    }


def execute_tool_dispatch(tool_name: str, tool_args: dict[str, Any], confirmed: bool, provider: str, model: str, tools_dir: Path) -> dict[str, Any]:
    tool_home = tools_dir / tool_name
    if not tool_home.is_dir():
        # try builtin tools
        bdir = builtin_tools_dir()
        alt = bdir / tool_name
        if alt.is_dir():
            tool_home = alt
        else:
            return failure(tool_name, f"Unknown tool: {tool_name}")
    
    try:
        tool_def = load_tool_definition(tool_home)
        args_with_defaults = apply_defaults(tool_def, tool_args)
        
        missing = missing_required_args(tool_def, args_with_defaults)
        if missing:
            args_with_defaults = try_fill_missing_args(tool_def, missing, args_with_defaults, provider, model)
            missing = missing_required_args(tool_def, args_with_defaults)
            if missing:
                return failure(tool_name, f"Missing required arguments: {', '.join(missing)}")

        if not tool_def.get("autoExecuteAllowed") and not confirmed:
            return failure(tool_name, "Tool requires confirmation.")

        envelope = execute_external(tool_name, tool_home, tool_def, json.dumps(args_with_defaults, ensure_ascii=False), confirmed, provider, model)
        return envelope
    except Exception as exc:
        return failure(tool_name, str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(description="Python tool dispatcher.")
    parser.add_argument("--mode", default="execute")
    parser.add_argument("--tool", required=True)
    parser.add_argument("--args-json", default="")
    parser.add_argument("--instruction", default="")
    parser.add_argument("--tools-dir", default="")
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    tools_dir = resolve_tools_dir(args.tools_dir)
    try:
        provider = normalize_optional(args.provider) or os.getenv("CORPS_PROVIDER") or ""
        model = normalize_optional(args.model) or os.getenv("CORPS_MODEL") or ""

        if args.mode == "dispatch":
            envelope = dispatch_capability(
                normalize_optional(args.instruction) or "",
                tools_dir,
                provider,
                model,
                args.confirm,
            )
            if envelope.get("ok"):
                data = envelope.get("data")
                if isinstance(data, dict) and data.get("actionType") == "skill":
                    # If it's a skill, execute it now!
                    skill_envelope = execute_skill(
                        str(data["name"]),
                        data.get("args") or {},
                        bool(data.get("confirm")),
                        provider,
                        model,
                        tools_dir
                    )
                    emit_result(success(
                        skill_envelope["toolName"],
                        skill_envelope["output"],
                        skill_envelope["data"]
                    ))
                    return

                emit_result(success(
                    str(envelope.get("toolName") or args.tool),
                    str(envelope.get("output") or ""),
                    envelope.get("data") if isinstance(envelope.get("data"), dict) else {},
                ))
                return
            emit_result(failure(str(envelope.get("toolName") or args.tool), str(envelope.get("error") or "Execution failed")))
            raise SystemExit(1)

        if args.mode == "skill":
            args_json = normalize_optional(args.args_json) or "{}"
            args_dict = load_json(args_json)
            envelope = execute_skill(args.tool, args_dict, args.confirm, provider, model, tools_dir)
            emit_result(success(envelope["toolName"], envelope["output"], envelope["data"]))
            return

        args_json = normalize_optional(args.args_json)
        if not args_json:
            if sys.stdin.isatty():
                args_dict = {}
            else:
                stdin_payload = sys.stdin.read()
                args_dict = load_json(stdin_payload.strip() if stdin_payload and stdin_payload.strip() else "{}")
        else:
            args_dict = load_json(args_json)

        envelope = execute_tool_dispatch(args.tool, args_dict, args.confirm, provider, model, tools_dir)
        if envelope.get("ok"):
            emit_result(success(
                str(envelope.get("toolName") or args.tool),
                str(envelope.get("output") or ""),
                envelope.get("data") if isinstance(envelope.get("data"), dict) else {},
            ))
            return
        emit_result(failure(str(envelope.get("toolName") or args.tool), str(envelope.get("error") or "Execution failed")))
        raise SystemExit(1)
    except Exception as exc:
        emit_result(failure(args.tool, str(exc)))
        raise SystemExit(1)


if __name__ == "__main__":
    main()