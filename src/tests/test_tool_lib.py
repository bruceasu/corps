import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("CORPS_PYTHON_SCRIPTS_DIR", str(ROOT))
sys.path.insert(0, str(ROOT))

from tools import build_dispatch_index, build_dispatch_prompt, load_skill_bundle  # noqa: E402


def test_skill_markdown_takes_precedence_over_yaml_detail(tmp_path):
    skill_home = tmp_path / "demo-skill"
    skill_home.mkdir()
    (skill_home / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Human instruction\n---\n# Demo Skill\nUse this only for humans.\n",
        encoding="utf-8",
    )
    (skill_home / "skill.json").write_text(
        '{"name": "demo-skill", "description": "Machine detail", "autoExecuteAllowed": true, "steps": []}',
        encoding="utf-8",
    )

    bundle = load_skill_bundle(skill_home)
    prompt = build_dispatch_prompt("demo", [], [bundle])

    assert bundle["markdown"]
    assert "Candidate priority JSON:" in prompt
    assert '"kind": "skill"' in prompt
    assert '"name": "demo-skill"' in prompt
    assert "Demo Skill" in prompt
    assert "Use this only for humans." in prompt
    assert "Machine detail" not in prompt


def test_skill_bundle_falls_back_to_definition_as_readable_markdown(tmp_path):
    skill_home = tmp_path / "fallback-skill"
    skill_home.mkdir()
    (skill_home / "skill.json").write_text(
        '{"name": "fallback-skill", "description": "Fallback description", "example": "example-input", "detail": ["first detail", "second detail"]}',
        encoding="utf-8",
    )

    bundle = load_skill_bundle(skill_home)

    assert bundle["name"] == "fallback-skill"
    assert "Fallback description" in str(bundle["markdown"])
    assert "first detail" in str(bundle["markdown"])
    assert "This skill does not yet have a dedicated SKILL.md file." in str(bundle["markdown"])


def test_dispatch_prompt_labels_skill_docs_and_plan_sections(tmp_path):
    skill_home = tmp_path / "plan-skill"
    skill_home.mkdir()
    (skill_home / "SKILL.md").write_text(
        "---\nname: plan-skill\ndescription: Human instruction\n---\n# Plan Skill\nHuman instructions here.\n",
        encoding="utf-8",
    )
    (skill_home / "skill.json").write_text(
        '{"name": "plan-skill", "autoExecuteAllowed": true, "steps": [{"id": "step1", "type": "tool", "toolName": "echo-tool"}]}',
        encoding="utf-8",
    )

    bundle = load_skill_bundle(skill_home)
    prompt = build_dispatch_prompt("generate import workflow", [], [bundle])

    assert "Candidate priority JSON:" in prompt
    assert "Plan Skill" in prompt
    assert "step1" in prompt


def test_dispatch_index_is_structured_and_stable(tmp_path):
    skill_home = tmp_path / "plan-skill"
    skill_home.mkdir()
    (skill_home / "SKILL.md").write_text(
        "---\nname: plan-skill\ndescription: Human instruction\n---\n# Plan Skill\nHuman instructions here.\n",
        encoding="utf-8",
    )
    (skill_home / "skill.json").write_text(
        '{"name": "plan-skill", "autoExecuteAllowed": true, "arguments": [{"name": "csvPath", "required": true}, {"name": "dryRun", "required": false}], "steps": [{"id": "step1", "type": "tool", "toolName": "echo-tool", "outputKey": "step1"}]}',
        encoding="utf-8",
    )

    bundle = load_skill_bundle(skill_home)
    index = build_dispatch_index(
        [
            {
                "name": "echo-tool",
                "description": "Echo input text",
                "arguments": [{"name": "message", "required": True}],
                "tool": {"type": "external-command", "program": "python", "autoExecuteAllowed": True},
            }
        ],
        [bundle],
    )

    assert index["selectionRules"][0] == "Choose exactly one capability."
    assert index["candidates"][0]["kind"] == "tool"
    assert index["candidates"][0]["requiredArgs"] == []
    assert index["candidates"][1]["kind"] == "tool"
    assert index["candidates"][1]["requiredArgs"] == ["message"]
    assert index["candidates"][2]["kind"] == "skill"
    assert index["candidates"][2]["steps"] == 1
    assert index["candidates"][2]["requiredArgs"] == ["csvPath"]
    assert index["candidates"][2]["optionalArgs"] == ["dryRun"]


def test_dispatch_index_orders_smallest_candidates_first(tmp_path):
    skill_home = tmp_path / "workflow-skill"
    skill_home.mkdir()
    (skill_home / "SKILL.md").write_text(
        "---\nname: workflow-skill\ndescription: Human instruction\n---\n# Workflow Skill\nMulti-step workflow.\n",
        encoding="utf-8",
    )
    (skill_home / "skill.json").write_text(
        '{"name": "workflow-skill", "autoExecuteAllowed": true, "arguments": [{"name": "source", "required": true}], "steps": [{"id": "step1", "type": "tool", "toolName": "first-tool"}, {"id": "step2", "type": "tool", "toolName": "second-tool"}]}',
        encoding="utf-8",
    )

    bundle = load_skill_bundle(skill_home)
    index = build_dispatch_index(
        [
            {
                "name": "tiny-tool",
                "description": "Single atomic action",
                "arguments": [],
                "tool": {"type": "external-command", "program": "python", "autoExecuteAllowed": True},
            },
            {
                "name": "larger-tool",
                "description": "More arguments",
                "arguments": [{"name": "input", "required": True}, {"name": "mode", "required": False}],
                "tool": {"type": "external-command", "program": "python", "autoExecuteAllowed": True},
            },
        ],
        [bundle],
    )

    candidate_names = [candidate["name"] for candidate in index["candidates"]]

    assert candidate_names[0] == "tiny-tool"
    assert candidate_names[1] == "larger-tool"
    assert candidate_names[2] == "workflow-skill"
    assert index["candidates"][0]["priority"] == 1
    assert index["candidates"][1]["priority"] == 2
    assert index["candidates"][2]["priority"] == 3
    assert index["selectionRules"][-1] == "Return the first candidate that fully satisfies the instruction."
