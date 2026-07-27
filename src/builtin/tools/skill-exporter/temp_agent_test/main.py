
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKFLOW = json.loads((ROOT / "workflow.json").read_text(encoding="utf-8"))

def resolve_template(value, context):
    text = "" if value is None else str(value)
    input_map = context.get("input", {})
    for key, data in input_map.items():
        text = text.replace("${input." + key + "}", str(data))
    for key, data in context.items():
        if key == "input":
            continue
        text = text.replace("${" + key + "}", str(data))
    return text

def select_program(program):
    if str(program).lower() == "python":
        if os.name == "nt":
            for candidate in (["python"], ["py", "-3"]):
                try:
                    result = subprocess.run(candidate + ["--version"], capture_output=True, text=True)
                    if result.returncode in (0, 1):
                        return candidate
                except OSError:
                    pass
        else:
            for candidate in (["python3"], ["python"]):
                try:
                    result = subprocess.run(candidate + ["--version"], capture_output=True, text=True)
                    if result.returncode in (0, 1):
                        return candidate
                except OSError:
                    pass
        raise SystemExit("No Python launcher found")
    return [program]

def resolve_program(program, tool_dir):
    if str(program).lower() == "python":
        return select_program(program)
    candidate = Path(program)
    if candidate.is_absolute():
        return [str(candidate)]
    if "/" in str(program) or "\\" in str(program) or str(program).startswith("."):
        return [str((tool_dir / candidate).resolve())]
    return [program]

def get_override(step, overrides):
    output_key = step.get("outputKey") or step.get("id")
    if output_key in overrides:
        return overrides[output_key]
    step_id = step.get("id")
    if step_id in overrides:
        return overrides[step_id]
    return None

def handle_manual_step(step, context, overrides):
    override = get_override(step, overrides)
    if override is None:
        reason = step.get("manualReason", "manual override required")
        key = step.get("outputKey") or step.get("id")
        raise SystemExit(
            "Missing manual override for step '%s' (outputKey=%s). Reason: %s. "
            "Pass --step-overrides-json with a value for '%s' or '%s'."
            % (step.get("id"), key, reason, key, step.get("id"))
        )
    context[step["outputKey"]] = override

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", default="{}")
    parser.add_argument("--step-overrides-json", default="{}")
    args = parser.parse_args()
    context = {"input": json.loads(args.input_json or "{}")}
    overrides = json.loads(args.step_overrides_json or "{}")

    for step in WORKFLOW["skill"]["steps"]:
        mode = step.get("executionMode", "")
        if mode.startswith("manual"):
            handle_manual_step(step, context, overrides)
            continue

        tool = WORKFLOW["tools"][step["toolName"]]
        tool_dir = ROOT / tool["toolDir"]
        command = resolve_program(tool["program"], tool_dir)
        for token in tool.get("args", []):
            rendered = resolve_template(token, context)
            if "/" in rendered or "\\" in rendered or rendered.startswith("."):
                rendered = str((tool_dir / rendered).resolve()) if not Path(rendered).is_absolute() else str(Path(rendered))
            command.append(rendered)
        completed = subprocess.run(command, cwd=str((tool_dir / tool.get("workingDirectory", ".")).resolve()), capture_output=True, text=True)
        if completed.returncode != 0:
            if step.get("optional"):
                context[step["outputKey"]] = ""
                continue
            sys.stderr.write(completed.stderr or completed.stdout)
            raise SystemExit(completed.returncode)
        context[step["outputKey"]] = (completed.stdout or "").strip()

    output_key = WORKFLOW["skill"]["steps"][-1]["outputKey"] if WORKFLOW["skill"]["steps"] else ""
    result = {
        "skill": WORKFLOW["skill"]["name"],
        "outputKey": output_key,
        "output": context.get(output_key, ""),
        "context": {k: v for k, v in context.items() if k != "input"}
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
