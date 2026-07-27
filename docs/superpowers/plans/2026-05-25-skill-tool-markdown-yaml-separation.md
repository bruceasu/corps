# Skill/Tool Markdown-YAML Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `SKILL.md` the human-authored source of truth for skill intent and boundaries, while treating `skill.yaml` and `tool.yaml` as machine-oriented execution plans and cached metadata.

**Architecture:** The dispatcher will load Markdown and YAML separately, then compose a structured capability prompt where Markdown explains intent, YAML describes executable steps, and tool definitions describe invocation contracts. This keeps the LLM-facing narrative readable while preserving deterministic execution data for the runtime.

**Tech Stack:** Python 3.10+, PyYAML, pytest, existing `tool_dispatcher.py` and `src/_runtime/engine/*` workflow parser/executor.

---

### Task 1: Add Markdown-first skill loading to the dispatcher

**Files:**
- Modify: `src/tool_dispatcher.py`
- Test: `src/tests/test_tool_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from tool_dispatcher import load_skill_bundle, build_dispatch_prompt


def test_skill_markdown_takes_precedence_over_yaml_detail(tmp_path):
    skill_home = tmp_path / "demo-skill"
    skill_home.mkdir()
    (skill_home / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Human instruction\n---\n# Demo Skill\nUse this only for humans.\n",
        encoding="utf-8",
    )
    (skill_home / "skill.yaml").write_text(
        "name: demo-skill\ndescription: Machine detail\nautoExecuteAllowed: true\nsteps: []\n",
        encoding="utf-8",
    )

    bundle = load_skill_bundle(skill_home)
    prompt = build_dispatch_prompt("demo", [], [bundle])

    assert "Demo Skill" in prompt
    assert "Use this only for humans." in prompt
    assert "Machine detail" not in prompt
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
python -m pytest src/tests/test_tool_dispatcher.py::test_skill_markdown_takes_precedence_over_yaml_detail -q
```

Expected: fail because `load_skill_bundle()` does not exist yet and `build_dispatch_prompt()` still treats skills as YAML-only records.

- [ ] **Step 3: Implement the Markdown-first loader**

```python
def load_skill_markdown(skill_home: Path) -> str:
    for candidate in ("SKILL.md", "skill.md", "README.md"):
        maybe = skill_home / candidate
        if maybe.is_file():
            return maybe.read_text(encoding="utf-8")
    return ""


def load_skill_bundle(skill_home: Path) -> dict[str, object]:
    skill_def = load_skill_definition(skill_home)
    skill_md = load_skill_markdown(skill_home)
    return {
        "name": str(skill_def.get("name") or skill_home.name),
        "markdown": skill_md,
        "yaml": skill_def,
    }
```

Then update `build_dispatch_prompt()` so skill entries are rendered in two sections:

```python
skill_markdown = str(skill.get("markdown") or "").strip()
skill_yaml = skill.get("yaml") if isinstance(skill.get("yaml"), dict) else {}
```

Use Markdown text as the primary description and YAML only as the executable plan summary.

- [ ] **Step 4: Run the test and verify it passes**

Run:

```powershell
python -m pytest src/tests/test_tool_dispatcher.py::test_skill_markdown_takes_precedence_over_yaml_detail -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/tool_dispatcher.py src/tests/test_tool_dispatcher.py
git commit -m "feat: load skills from markdown-first metadata"
```

### Task 2: Make dispatcher prompts explicit about Markdown vs YAML roles

**Files:**
- Modify: `src/tool_dispatcher.py`
- Test: `src/tests/test_tool_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
from tool_dispatcher import build_dispatch_prompt


def test_dispatch_prompt_labels_markdown_as_human_docs_and_yaml_as_plan():
    prompt = build_dispatch_prompt(
        "generate import workflow",
        [],
        [
            {
                "name": "generate-import-control-and-run",
                "markdown": "# Generate Import Control And Run\nHuman instructions here.",
                "yaml": {"name": "generate-import-control-and-run", "steps": [{"id": "a", "type": "tool"}]},
            }
        ],
    )

    assert "Human instructions here." in prompt
    assert "Execution plan" in prompt
    assert "steps" in prompt
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
python -m pytest src/tests/test_tool_dispatcher.py::test_dispatch_prompt_labels_markdown_as_human_docs_and_yaml_as_plan -q
```

Expected: fail because the prompt does not yet separate human docs from machine plan text.

- [ ] **Step 3: Update the prompt formatter**

```python
lines.append("Skill human docs (Markdown):")
lines.append(skill_markdown or "(no SKILL.md found)")
lines.append("")
lines.append("Skill execution plan (YAML):")
lines.append(json.dumps(skill_yaml, ensure_ascii=False, indent=2))
```

Keep tool rendering unchanged except for making the contract language explicit:

```python
lines.append("Tool contract (YAML):")
```

- [ ] **Step 4: Run the test and verify it passes**

Run:

```powershell
python -m pytest src/tests/test_tool_dispatcher.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/tool_dispatcher.py src/tests/test_tool_dispatcher.py
git commit -m "feat: separate skill docs from execution plans"
```

### Task 3: Document the authoring contract for humans

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing check by inspection**

Add a short authoring section to `README.md` that explicitly says:

```markdown
- `SKILL.md` is the human-written explanation, usage guide, and boundary contract.
- `skill.yaml` is the machine-oriented execution plan and should be treated as generated or cacheable metadata.
- Human edits to YAML should be limited to small adjustments after generation.
```

- [ ] **Step 2: Update the documentation**

Insert the new section near the existing developer-extension docs and update the examples that currently imply `skill.yaml` is the primary hand-authored artifact.

- [ ] **Step 3: Validate the wording**

Run:

```powershell
python -m pytest src/tests/test_tool_dispatcher.py -q
```

Expected: PASS, and manual review of `README.md` confirms the new contract is clear and consistent with the code.

- [ ] **Step 4: Commit**

```powershell
git add README.md
git commit -m "docs: clarify markdown-first skill authoring"
```

### Task 4: Self-review the new split against existing builtin skills

**Files:**
- Inspect: `src/builtin/skills/*/SKILL.md`
- Inspect: `src/builtin/skills/*/skill.yaml`

- [ ] **Step 1: Check built-in skills for Markdown coverage**

```powershell
Get-ChildItem src\builtin\skills -Directory | ForEach-Object {
  $skill = $_.FullName
  [pscustomobject]@{
    Name = $_.Name
    HasMarkdown = Test-Path (Join-Path $skill 'SKILL.md')
    HasYaml = Test-Path (Join-Path $skill 'skill.yaml')
  }
}
```

- [ ] **Step 2: Decide whether any missing SKILL.md files need to be added**

If a builtin skill is YAML-only but intended for human use, add a companion `SKILL.md` instead of overloading the YAML with prose.

- [ ] **Step 3: Verify the split is consistent**

Confirm that Markdown contains the human narrative and YAML contains the executable structure only.

---

### Coverage Check

- Markdown-first loading and prompt rendering: Task 1, Task 2
- Documentation and authoring rules: Task 3
- Existing builtin skill consistency: Task 4

### Risks

- Prompt changes may slightly alter dispatch behavior and need re-tuning.
- Some existing skills may not yet have `SKILL.md`; those will fall back to YAML text until they are migrated.
- Tool/skill discovery code must remain backward compatible with existing `skill.yaml` and `tool.yaml` layouts.

### Validation

- `python -m pytest src/tests/test_tool_dispatcher.py -q`
- Manual review of `README.md`
- Spot-check one builtin skill end-to-end through the dispatcher
