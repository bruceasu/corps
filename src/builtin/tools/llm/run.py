import argparse
import json
import os
import sys
from pathlib import Path

# Force UTF-8 for stdout and stderr on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def add_runtime_path() -> None:
    # Path(__file__).resolve() is src/builtin/tools/llm/run.py
    # parents[3] is the 'src' directory
    src_dir = Path(__file__).resolve().parents[3]

    if src_dir.exists():
        sys.path.insert(0, str(src_dir))

add_runtime_path()
from _runtime.llm_runtime import generate_llm_text
from _runtime.tool_runtime import emit_result, failure, load_json, normalize_optional, required_keys_missing, strip_fence, success


def parse_structured(output: str, output_format: str, required_keys: str) -> dict[str, object]:
    cleaned = strip_fence(output)
    if output_format == "json":
        structured = load_json(cleaned)
    elif output_format == "yaml":
        try:
            import yaml  # type: ignore

            structured_obj = yaml.safe_load(cleaned)
            if not isinstance(structured_obj, dict):
                raise ValueError("Expected YAML object")
            structured = structured_obj
        except ModuleNotFoundError:
            structured = load_json(cleaned)
    else:
        raise ValueError(f"Unsupported format: {output_format}. Use text, yaml, or json.")

    missing = required_keys_missing(required_keys, structured)
    if missing:
        raise ValueError("Missing required keys: " + ", ".join(missing))
    return structured


def validate_against_schema(structured: dict, schema: dict) -> list[str]:
    errors: list[str] = []
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft7Validator(schema)
        for err in sorted(validator.iter_errors(structured), key=lambda e: e.path):
            path = ".".join([str(p) for p in err.path]) or "<root>"
            errors.append(f"{path}: {err.message}")
        return errors
    except ModuleNotFoundError:
        req = schema.get("required") or []
        for key in req:
            if key not in structured:
                errors.append(f"required property missing: {key}")

        props = schema.get("properties") or {}
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        for name, spec in props.items():
            if name not in structured:
                continue
            expected = spec.get("type")
            if expected:
                pytype = type_map.get(expected)
                if pytype and not isinstance(structured[name], pytype):
                    errors.append(f"{name}: expected {expected}")
        return errors
    except Exception as exc:
        return [f"schema validator error: {exc}"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Call the configured AI provider explicitly.")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--system-prompt", default="")
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--format", default="text")
    parser.add_argument("--required-keys", default="")
    parser.add_argument("--schema-file", default="")
    parser.add_argument("--schema", default="")
    parser.add_argument("--require-schema", action="store_true")
    args = parser.parse_args()

    prompt = normalize_optional(args.prompt) or ""
    prompt_file = normalize_optional(args.prompt_file)
    if prompt_file:
        path = Path(prompt_file).resolve()
        if path.exists():
            prompt = path.read_text(encoding="utf-8", errors="replace").strip()

    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()

    if not prompt:
        emit_result(failure("llm", "Missing required argument: prompt"))
        raise SystemExit(1)

    # Use 'rotation' by default if no provider/model specified
    provider = normalize_optional(args.provider) or "rotation"
    model = normalize_optional(args.model) or "rotation"

    system_prompt = normalize_optional(args.system_prompt) or ""
    output_format = (normalize_optional(args.format) or "text").lower()
    required_keys = normalize_optional(args.required_keys) or ""
    schema_file = normalize_optional(args.schema_file) or ""
    schema_inline = normalize_optional(args.schema) or ""
    require_schema = bool(args.require_schema)

    # Enhance system prompt for structured output
    if output_format in ["json", "yaml"]:
        format_instruction = f"Output ONLY valid {output_format.upper()}. No preamble, no postamble, no explanations."
        if required_keys:
            format_instruction += f" Ensure the following keys are present: {required_keys}."

        if system_prompt:
            system_prompt = f"{system_prompt}\n\n{format_instruction}"
        else:
            system_prompt = format_instruction

    try:
        # Use unified runtime with rotation support
        output = generate_llm_text(provider, model, prompt, system_prompt=system_prompt)

        data = {
            "provider": provider,
            "model": model,
            "format": output_format,
        }

        if output_format != "text":
            structured = parse_structured(output, output_format, required_keys)
            data["structured"] = structured

            # Schema validation
            schema_obj = None
            if schema_inline:
                schema_obj = json.loads(schema_inline)
            elif schema_file:
                with open(schema_file, "r", encoding="utf-8") as f:
                    schema_obj = json.load(f)

            if schema_obj:
                errors = validate_against_schema(structured, schema_obj)
                if errors:
                    data["schemaErrors"] = errors
                    if require_schema:
                        raise ValueError("Schema validation failed: " + "; ".join(errors))
                else:
                    data["schemaValid"] = True

        emit_result(success("llm", output, data))
    except Exception as exc:
        emit_result(failure("llm", str(exc)))
        raise SystemExit(1)

if __name__ == "__main__":
    main()
