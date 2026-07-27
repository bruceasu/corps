import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

def add_runtime_path() -> None:
    scripts_dir = os.getenv("CORPS_PYTHON_SCRIPTS_DIR")
    if scripts_dir:
        runtime_dir = Path(scripts_dir).resolve() / "_runtime"
    else:
        # Fallback for local development
        runtime_dir = Path(__file__).resolve().parents[3] / "_runtime"
    sys.path.insert(0, str(runtime_dir))

add_runtime_path()
from tool_runtime import emit_result, success, failure, load_json

PYTHON_TEMPLATE = r'''
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
'''

GO_TEMPLATE = r'''
package main

import (
  "encoding/json"
  "flag"
  "fmt"
  "os"
  "os/exec"
  "path/filepath"
  "runtime"
  "strings"
)

type workflow struct {
  Skill struct {
    Name string `json:"name"`
    Steps []step `json:"steps"`
  } `json:"skill"`
  Tools map[string]tool `json:"tools"`
}

type step struct {
  Id string `json:"id"`
  Type string `json:"type"`
  Optional bool `json:"optional"`
  ToolName string `json:"toolName"`
  OutputKey string `json:"outputKey"`
  Arguments map[string]string `json:"arguments"`
  ExecutionMode string `json:"executionMode"`
  ManualReason string `json:"manualReason"`
}

type tool struct {
  Program string `json:"program"`
  Args []string `json:"args"`
  WorkingDirectory string `json:"workingDirectory"`
  ToolDir string `json:"toolDir"`
}

func resolveTemplate(text string, context map[string]string, input map[string]string) string {
  resolved := text
  for k, v := range input {
    resolved = strings.ReplaceAll(resolved, "${input."+k+"}", v)
  }
  for k, v := range context {
    resolved = strings.ReplaceAll(resolved, "${"+k+"}", v)
  }
  return resolved
}

func selectPython() ([]string, error) {
  candidates := [][]string{{"python3"}, {"python"}}
  if runtime.GOOS == "windows" {
    candidates = [][]string{{"python"}, {"py", "-3"}}
  }
  for _, candidate := range candidates {
    cmd := exec.Command(candidate[0], append(candidate[1:], "--version")...)
    if err := cmd.Run(); err == nil {
      return candidate, nil
    }
  }
  return nil, fmt.Errorf("no Python launcher found")
}

func resolveProgram(program string, toolDir string) ([]string, error) {
  if strings.EqualFold(program, "python") {
    return selectPython()
  }
  if filepath.IsAbs(program) {
    return []string{program}, nil
  }
  if strings.Contains(program, "/") || strings.Contains(program, "\\") || strings.HasPrefix(program, ".") {
    return []string{filepath.Clean(filepath.Join(toolDir, program))}, nil
  }
  return []string{program}, nil
}

func getOverride(step step, overrides map[string]string) (string, bool) {
  if value, ok := overrides[step.OutputKey]; ok {
    return value, true
  }
  if value, ok := overrides[step.Id]; ok {
    return value, true
  }
  return "", false
}

func main() {
  inputJSON := flag.String("input-json", "{}", "input json")
  overrideJSON := flag.String("step-overrides-json", "{}", "manual step overrides json")
  flag.Parse()
  root, _ := os.Getwd()
  workflowBytes, err := os.ReadFile(filepath.Join(root, "workflow.json"))
  if err != nil {
    panic(err)
  }
  var wf workflow
  if err := json.Unmarshal(workflowBytes, &wf); err != nil {
    panic(err)
  }
  input := map[string]string{}
  if err := json.Unmarshal([]byte(*inputJSON), &input); err != nil {
    panic(err)
  }
  overrides := map[string]string{}
  if err := json.Unmarshal([]byte(*overrideJSON), &overrides); err != nil {
    panic(err)
  }
  context := map[string]string{}
  for _, step := range wf.Skill.Steps {
    if strings.HasPrefix(step.ExecutionMode, "manual") {
      override, ok := getOverride(step, overrides)
      if !ok {
        fmt.Fprintf(os.Stderr, "missing manual override for step '%s' (outputKey=%s): %s\n", step.Id, step.OutputKey, step.ManualReason)
        os.Exit(1)
      }
      context[step.OutputKey] = override
      continue
    }

    tool := wf.Tools[step.ToolName]
    toolDir := filepath.Join(root, filepath.FromSlash(tool.ToolDir))
    command, err := resolveProgram(tool.Program, toolDir)
    if err != nil {
      panic(err)
    }
    for _, token := range tool.Args {
      rendered := resolveTemplate(token, context, input)
      if filepath.IsAbs(rendered) {
        command = append(command, rendered)
      } else if strings.Contains(rendered, "/") || strings.Contains(rendered, "\\") || strings.HasPrefix(rendered, ".") {
        command = append(command, filepath.Clean(filepath.Join(toolDir, rendered)))
      } else {
        command = append(command, rendered)
      }
    }
    workingDir := filepath.Join(toolDir, filepath.FromSlash(tool.WorkingDirectory))
    cmd := exec.Command(command[0], command[1:]...)
    cmd.Dir = workingDir
    output, err := cmd.CombinedOutput()
    if err != nil {
      if step.Optional {
        context[step.OutputKey] = ""
        continue
      }
      fmt.Fprint(os.Stderr, string(output))
      os.Exit(1)
    }
    context[step.OutputKey] = strings.TrimSpace(string(output))
  }

  outputKey := ""
  output := ""
  if len(wf.Skill.Steps) > 0 {
    outputKey = wf.Skill.Steps[len(wf.Skill.Steps)-1].OutputKey
    output = context[outputKey]
  }
  result := map[string]any{
    "skill": wf.Skill.Name,
    "outputKey": outputKey,
    "output": output,
    "context": context,
  }
  bytes, err := json.MarshalIndent(result, "", "  ")
  if err != nil {
    panic(err)
  }
  fmt.Println(string(bytes))
}
'''

def load_yaml(path: Path) -> dict:
    try:
        import yaml # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def is_exportable_external_tool(tool_def: dict, tool_home: Optional[Path]) -> bool:
    tool_spec = tool_def.get("tool", {})
    return (
        tool_spec.get("type") == "external-command"
        and tool_home is not None
        and tool_home.is_dir()
    )

def manual_reason_for_tool(tool_def: dict, tool_home: Optional[Path]) -> str:
    tool_spec = tool_def.get("tool", {})
    if not tool_spec:
        return "Tool runtime is missing, so this step must be supplied manually."
    if tool_spec.get("type") != "external-command":
         return "Only filesystem external-command tools can run directly in exported workflows."
    return "Unknown reason for manual override."

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target", default="python")
    args = parser.parse_args()

    skills_dir = Path(os.getenv("CORPS_SKILLS_DIR", "/skills")).resolve()
    tools_dir = Path(os.getenv("CORPS_TOOLS_DIR", "/tools")).resolve()
    
    skill_home = skills_dir / args.skill
    if not skill_home.is_dir():
        emit_result(failure("skill-exporter", f"Skill not found: {args.skill}"))
        return

    skill_def_path = skill_home / "skill.yaml"
    if not skill_def_path.is_file():
        emit_result(failure("skill-exporter", f"skill.yaml not found in {skill_home}"))
        return
    
    skill_def = load_yaml(skill_def_path)
    
    output_path = Path(args.output).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "tools").mkdir(exist_ok=True)

    workflow = {
        "skill": {
            "name": skill_def.get("name"),
            "description": skill_def.get("description"),
            "arguments": skill_def.get("arguments", []),
            "steps": []
        },
        "tools": {},
        "manualSteps": []
    }

    for step in skill_def.get("steps", []):
        step_id = step.get("id")
        output_key = step.get("outputKey") or step_id
        step_node = {
            "id": step_id,
            "type": step.get("type", "tool"),
            "optional": step.get("optional", False),
            "outputKey": output_key,
            "arguments": step.get("arguments", {})
        }

        if step_node["type"] == "tool" and step.get("toolName"):
            tool_name = step["toolName"]
            tool_home = tools_dir / tool_name
            tool_def_path = tool_home / "tool.yaml"
            
            if tool_def_path.is_file():
                tool_def = load_yaml(tool_def_path)
                if is_exportable_external_tool(tool_def, tool_home):
                    dest_tool_dir = output_path / "tools" / tool_name
                    if not dest_tool_dir.exists():
                        shutil.copytree(tool_home, dest_tool_dir)
                    
                    step_node["executionMode"] = "external-tool"
                    step_node["toolName"] = tool_name
                    
                    tool_spec = tool_def.get("tool", {})
                    workflow["tools"][tool_name] = {
                        "name": tool_name,
                        "description": tool_def.get("description"),
                        "program": tool_spec.get("program"),
                        "args": tool_spec.get("args"),
                        "workingDirectory": tool_spec.get("workingDirectory", "."),
                        "toolDir": f"tools/{tool_name}"
                    }
                    workflow["skill"]["steps"].append(step_node)
                    continue

            # Fallback to manual
            reason = manual_reason_for_tool(load_yaml(tool_def_path) if tool_def_path.is_file() else {}, tool_home if tool_home.is_dir() else None)
            step_node["executionMode"] = "manual-tool"
            step_node["toolName"] = tool_name
            step_node["manualReason"] = reason
            workflow["manualSteps"].append(step_node)
        else:
            step_node["executionMode"] = "manual-unsupported"
            step_node["manualReason"] = "Unsupported step type for automatic export."
            workflow["manualSteps"].append(step_node)
        
        workflow["skill"]["steps"].append(step_node)

    (output_path / "workflow.json").write_text(json.dumps(workflow, indent=2, ensure_ascii=False), encoding="utf-8")

    targets = [args.target] if args.target != "both" else ["python", "go"]
    if "python" in targets:
        (output_path / "main.py").write_text(PYTHON_TEMPLATE, encoding="utf-8")
    if "go" in targets:
        (output_path / "main.go").write_text(GO_TEMPLATE, encoding="utf-8")
    
    readme = f"# Exported Workflow: {args.skill}\n\nGenerated with skill-exporter."
    (output_path / "README.md").write_text(readme, encoding="utf-8")

    emit_result(success("skill-exporter", f"Exported {args.skill} to {output_path}", {
        "outputDir": str(output_path),
        "targets": targets,
        "manualStepsCount": len(workflow["manualSteps"])
    }))

if __name__ == "__main__":
    main()
