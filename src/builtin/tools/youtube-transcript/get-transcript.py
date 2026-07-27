"""
Compatibility wrapper for the historical script name.

This file is no longer the main implementation entrypoint.
Use `run.py` for the packaged tool runner, or import `youtube_transcript_lib.py`
for reusable logic.
"""

import argparse
from pathlib import Path

from youtube_transcript_lib import build_plan, execute_plan, print_json


def build_parser():
    parser = argparse.ArgumentParser(description="Compatibility wrapper for youtube transcript fetching.")
    parser.add_argument("--input")
    parser.add_argument("--inputs")
    parser.add_argument("--inputs-file")
    parser.add_argument("--languages")
    parser.add_argument("--output-dir")
    parser.add_argument("--cache-file")
    parser.add_argument("--error-log")
    parser.add_argument("--workers")
    parser.add_argument("--retries")
    parser.add_argument("--use-cache")
    parser.add_argument("--output-mode")
    parser.add_argument("--include-transcript-text")
    parser.add_argument("--max-chars-per-transcript")
    parser.add_argument("--dry-run")
    return parser


def main():
    args = build_parser().parse_args()
    script_dir = Path(__file__).resolve().parent
    plan = build_plan(
        args.input,
        args.inputs,
        args.inputs_file,
        args.languages,
        args.output_dir,
        args.cache_file,
        args.error_log,
        args.workers,
        args.retries,
        args.use_cache,
        args.output_mode,
        args.include_transcript_text,
        args.max_chars_per_transcript,
        args.dry_run,
        script_dir,
    )
    print_json(execute_plan(plan))


if __name__ == "__main__":
    main()
