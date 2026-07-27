---
name: generate-import-control-and-run
description: Generate an import control file for a CSV and then execute the bundled import workflow. Use when a user already has a CSV file and wants a two-step flow: create the control YAML first, then run the import tool with that generated control file.
detail:
  - This skill is designed for the common case where a user has a CSV and wants to generate the corresponding control YAML and immediately run the import workflow with it.
  - It combines the functionality of `import-control-file-generator` and `import-tool` into one seamless workflow.
  - The skill captures the generated control file path from the first step and feeds it into the second step, optionally supporting a dry-run mode for validation before execution.
  - This skill is intentionally narrow in scope to keep it simple and focused on the specific use case of generating a control file for one CSV and running it, without adding extra logic or interpretation.
example: |
  ```json
  {
    "job": "userImportJob",
    "csvPath": "/data/users.csv",
    "importDate": "2024-01-01",
    "dryRun": "false"
  }
  ```
---

# Generate Import Control And Run

Use this skill when the task is:

- a CSV file already exists
- a control YAML still needs to be generated
- the control file should immediately feed into `import-tool`
- the user wants one combined workflow instead of manually calling two tools

This skill is intentionally narrow. It is designed for the common flow:

1. generate a control file for one CSV
2. pass that generated file into `import-tool`

## Workflow

The execution flow is:

1. call `import-control-file-generator`
2. capture the generated control file path
3. call `import-tool` with `command=run-one`
4. optionally run in dry-run mode for plan-only verification

## Expected Inputs

Typical inputs:

- `csvPath`: source CSV path
- `importDate`: import date in `yyyy-MM-dd`
- `job`: optional job name from `import-tool` configuration
- `dbRef`: optional database reference from `import-tool` configuration
- `output`: optional explicit path for the generated control file
- `dryRun`: set to `true` when the user only wants validation or execution planning

## Good Use Cases

Use this skill for requests like:

- "I already have a CSV, generate the control file and run the import"
- "Prepare and execute a single import for this CSV"
- "Validate the import flow in dry-run mode before running it"

## Boundaries

Do not use this skill when:

- the user only wants the control file and does not want to run the import
  Use `import-control-file-generator` directly.
- the user already has a finished control YAML
  Use `import-tool` directly.
- the task is a batch or multi-file orchestration problem
  Prefer a dedicated higher-level workflow.

## Notes

- Keep this skill simple and deterministic.
- Prefer passing through explicit user inputs instead of inventing defaults.
- If the import behavior needs interpretation, explanation, or repair advice, compose that as a separate skill layer instead of overloading this one.
