import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YT_DIR = ROOT / "builtin" / "tools" / "youtube-transcript"
os.environ.setdefault("CORPS_PYTHON_SCRIPTS_DIR", str(ROOT))
sys.path.insert(0, str(YT_DIR))

import run as youtube_transcript_run  # noqa: E402

from youtube_transcript_lib import build_plan, normalize_optional, parse_output_mode, process_video  # noqa: E402


def test_normalize_optional_treats_unresolved_placeholders_as_missing():
    assert normalize_optional("${inputs_file}") is None
    assert normalize_optional("${input.inputs_file}") is None
    assert normalize_optional("   ${output_mode}   ") is None


def test_parse_output_mode_accepts_text_alias():
    assert parse_output_mode("text") == "plain-text"
    assert parse_output_mode("plain-text") == "plain-text"
    assert parse_output_mode("json") == "json"


def test_build_plan_ignores_unresolved_optional_inputs_file(tmp_path):
    plan = build_plan(
        single_input="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        batch_inputs=None,
        inputs_file="${inputs_file}",
        languages="zh-Hans,zh,en,ja",
        output_dir=None,
        cache_file=None,
        error_log=None,
        workers="1",
        retries="1",
        use_cache="false",
        output_mode="text",
        include_transcript_text="true",
        max_chars_per_transcript="12000",
        dry_run="true",
        script_dir=tmp_path,
    )

    assert plan["outputMode"] == "plain-text"
    assert plan["rawInputs"] == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]


def test_process_video_returns_cached_transcript_text(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    transcript_path = output_dir / "HQGUed-e2wM.txt"
    transcript_path.write_text("[0.00] cached transcript line\n", encoding="utf-8")
    cache = {"HQGUed-e2wM"}

    result = process_video(
        video_id="HQGUed-e2wM",
        languages=["zh-Hans", "zh", "en", "ja"],
        retries=1,
        cache=cache,
        use_cache=True,
        output_dir=output_dir,
        error_log=str(tmp_path / "error.log"),
        include_transcript_text=True,
        max_chars_per_transcript=12000,
    )

    assert result["status"] == "success"
    assert result["source"] == "cache"
    assert result["transcriptFile"] == str(transcript_path.resolve())
    assert result["transcriptText"] == "[0.00] cached transcript line\n"
    assert result["transcript"] == "[0.00] cached transcript line\n"


def test_run_main_prints_plain_text_without_json_wrapping(monkeypatch, capsys):
    monkeypatch.setattr(
        youtube_transcript_run,
        "build_plan",
        lambda **kwargs: {"outputMode": "plain-text"},
    )
    monkeypatch.setattr(
        youtube_transcript_run,
        "execute_plan",
        lambda plan: "### HQGUed-e2wM\ncached transcript",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run.py",
            "--input",
            "HQGUed-e2wM",
        ],
    )

    youtube_transcript_run.main()

    captured = capsys.readouterr()
    assert captured.out.strip() == "### HQGUed-e2wM\ncached transcript"
