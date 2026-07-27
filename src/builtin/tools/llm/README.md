Tool/LLM — Schema and usage
=============================

Purpose
-------
This document explains the canonical JSON Schema for machine-readable tool/skill responses, how to validate LLM outputs with `workspace/tools/llm/run.py`, and quick CLI examples.

Schema
------
- File: [workspace/tools/llm/schema/tool_response.schema.json](workspace/tools/llm/schema/tool_response.schema.json#L1-L200)
- Example response: [workspace/tools/llm/schema/example_response.json](workspace/tools/llm/schema/example_response.json#L1-L200)

Usage
-----
The `run.py` tool supports validating structured outputs (JSON/YAML) against a JSON Schema.

Auto-discovery: if you don't pass `--schema-file` or `--schema`, `run.py` will look for `workspace/tools/llm/schema/tool_response.schema.json` next to the script.

Examples
--------
1) Validate using the repository schema (auto-discovered):

```bash
python workspace/tools/llm/run.py \
  --prompt '请返回符合 schema 的 JSON' \
  --format json \
  --require-schema
```

2) Validate with an explicit schema file:

```bash
python workspace/tools/llm/run.py \
  --prompt '返回工具响应' \
  --format json \
  --schema-file workspace/tools/llm/schema/tool_response.schema.json \
  --require-schema
```

Notes
-----
- The validator uses `jsonschema` if installed; otherwise a minimal fallback validator performs basic `required` and top-level type checks.
- In strict mode (`--require-schema`) the tool will fail if validation errors are present; otherwise errors are included in the returned metadata under `schemaErrors`.

Testing
-------
Unit tests for the validator are in `workspace/tools/llm/tests/test_schema_validation.py` and use `pytest`.

To run the tests locally:

```bash
pip install pytest
pytest -q workspace/tools/llm/tests
```

Next steps
----------
- Optionally add a CI job to run these tests and ensure `jsonschema` is installed in the test environment.
