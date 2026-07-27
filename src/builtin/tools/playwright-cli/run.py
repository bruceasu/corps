import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


SUPPORTED_ACTIONS = {
    "open",
    "goto",
    "snapshot",
    "click",
    "fill",
    "type",
    "press",
    "screenshot",
    "close",
    "list",
    "show",
    "close-all",
    "kill-all",
    "check",
    "uncheck",
    "text-content",
}


def normalize_optional(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_bool(value, default=False):
    text = normalize_optional(value)
    if text is None:
        return default
    return text.lower() in {"1", "true", "yes", "y", "on"}


def resolve_launcher():
    native = shutil.which("playwright-cli")
    if native:
        return [native]
    raise RuntimeError(
        "playwright-cli was not found in PATH. "
        "Install it with 'npm install -g @playwright/cli@latest' and ensure the playwright-cli command is available."
    )


def default_screenshot_path(script_dir, session):
    output_dir = script_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = session or "default"
    return output_dir / f"{suffix}.png"


def build_command(args, script_dir):
    action = normalize_optional(args.action)
    if action is None:
        raise ValueError("Missing required argument: action")
    if action not in SUPPORTED_ACTIONS:
        raise ValueError(f"Unsupported action: {action}")
    session = normalize_optional(args.session)

    url = normalize_optional(args.url)
    target = normalize_optional(args.target)
    value = normalize_optional(args.value)
    path = normalize_optional(args.path)
    headed = parse_bool(args.headed, False)
    persistent = parse_bool(args.persistent, False)
    config = normalize_optional(args.config)
    extra_args = normalize_optional(args.extra_args)

    action_args = []
    if session:
        action_args.append(f"-s={session}")
    if config:
        action_args.extend(["--config", config])
    action_args.append(action)

    if action in {"open", "goto"} and url:
        action_args.append(url)
    elif action in {"click", "check", "uncheck", "text-content"} and target:
        action_args.append(target)
    elif action == "fill":
        if target:
            action_args.append(target)
        if value:
            action_args.append(value)
    elif action in {"type", "press"} and value:
        action_args.append(value)
    elif action == "screenshot":
        screenshot_path = Path(path) if path else default_screenshot_path(script_dir, session)
        action_args.append(str(screenshot_path))

    if headed:
        action_args.append("--headed")
    if persistent:
        action_args.append("--persistent")
    if extra_args:
        action_args.extend(shlex.split(extra_args, posix=os.name != "nt"))

    return action_args


def run(args):
    script_dir = Path(__file__).resolve().parent
    action_args = build_command(args, script_dir)
    plan = {
        "tool": "playwright-cli",
        "launcher": "playwright-cli",
        "command": ["playwright-cli", *action_args],
        "action": args.action,
        "session": normalize_optional(args.session),
        "dryRun": parse_bool(args.dry_run, False),
    }

    if plan["dryRun"]:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    command = [*resolve_launcher(), *action_args]
    completed = subprocess.run(command, cwd=str(script_dir), capture_output=True, text=True)
    summary = {
        "tool": "playwright-cli",
        "ok": completed.returncode == 0,
        "action": args.action,
        "session": normalize_optional(args.session),
        "command": command,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
        "exitCode": completed.returncode,
    }
    if completed.returncode != 0:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(completed.returncode)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description="Run Playwright CLI browser automation commands.")
    parser.add_argument("--action")
    parser.add_argument("--url")
    parser.add_argument("--target")
    parser.add_argument("--value")
    parser.add_argument("--path")
    parser.add_argument("--session")
    parser.add_argument("--config")
    parser.add_argument("--headed")
    parser.add_argument("--persistent")
    parser.add_argument("--extra-args")
    parser.add_argument("--dry-run")
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())
