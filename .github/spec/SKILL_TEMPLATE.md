---
name: your-skill-name
description: Briefly describe what this skill does and when it should be used. Mention the triggering task, the expected workflow, and the main boundaries.
---

# Your Skill Title

Use this skill when the task is:

- condition 1
- condition 2
- condition 3

Do not use this skill when:

- a simpler direct tool call is enough
- a stable top-level command already covers the task better
- the workflow is outside this skill's intended boundary

## Goal

State the concrete outcome this skill is meant to produce.

Examples:

- analyze an error and suggest next actions
- read a page and summarize the main ideas
- generate an import control file and then run the import

## Workflow

Describe the intended execution flow in plain language.

Typical pattern:

1. collect or read required input
2. call one or more tools
3. use `toolName: llm` when explicit AI reasoning is needed
4. return a concise final result or artifact path

## Expected Inputs

List the most important user inputs in human terms.

Examples:

- `path`: file path or directory path
- `url`: page to fetch
- `symbol`: code symbol to inspect
- `task`: repair or analysis request
- `dryRun`: plan-only mode

## Suggested Tooling

Mention the likely tools or commands this skill should compose.

Examples:

- `read-file`
- `list-files`
- `web-fetch`
- `web-search`
- `llm`
- `command-analyze`
- `command-fix-suggest`

## Good Use Cases

Write 3 to 5 natural-language examples that should trigger this skill.

- "Example request 1"
- "Example request 2"
- "Example request 3"

## Boundaries

Be explicit about what this skill should not try to do.

- keep the workflow narrow and deterministic when possible
- avoid inventing missing inputs
- prefer asking for clarification over guessing
- do not overload one skill with unrelated responsibilities

## Author Notes

Optional notes for future maintainers:

- preferred workflow shape
- fallback behavior
- important safety constraints
- assumptions about external tools

## YAML Mapping Hint

When converting this Markdown into `skill.yaml`, keep these rules in mind:

- execution should prefer `type: tool`
- explicit AI reasoning should use `toolName: llm`
- avoid legacy `type: ai`
- keep arguments small and concrete
- prefer multiple narrow tool steps over one vague step
