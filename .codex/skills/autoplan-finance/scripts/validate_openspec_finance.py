#!/usr/bin/env python3
"""Validate minimum OpenSpec Finance Profile section coverage.

Usage:
  python scripts/validate_openspec_finance.py /path/to/specs

This is a lightweight structural validator. It checks that required finance
profile files exist and contain the minimum section headings needed for manual
review gates. It does not validate business correctness.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REQUIRED = {
    "requirements.md": ["# requirements", "decision flow"],
    "design.md": ["# design"],
    "tasks.md": ["# tasks"],
    "metrics.md": ["# metrics", "metric registry", "source mapping", "financial correctness", "consistency review"],
    "permissions.md": ["# permissions", "roles", "permission matrix", "field-level restrictions", "data scope rules"],
    "audit.md": ["# audit", "audited actions", "retention policy", "audit query requirements"],
    "release.md": ["# release", "decision", "release checklist", "rollback plan", "open release risks"],
}


def normalize(text: str) -> str:
    return text.lower().replace("_", "-")


def validate(specs_dir: Path) -> list[str]:
    errors: list[str] = []
    if not specs_dir.exists() or not specs_dir.is_dir():
        return [f"specs directory not found: {specs_dir}"]

    for filename, required_terms in REQUIRED.items():
        path = specs_dir / filename
        if not path.exists():
            errors.append(f"missing required file: {filename}")
            continue
        content = normalize(path.read_text(encoding="utf-8"))
        for term in required_terms:
            if term not in content:
                errors.append(f"{filename}: missing required section or term: {term}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("specs_dir", help="path to specs directory")
    args = parser.parse_args()

    errors = validate(Path(args.specs_dir))
    if errors:
        print("OpenSpec Finance Profile validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("OpenSpec Finance Profile validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
