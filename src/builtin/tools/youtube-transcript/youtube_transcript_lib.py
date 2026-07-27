import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


VIDEO_ID_PATTERNS = [
    r"(?:v=)([0-9A-Za-z_-]{11})",
    r"(?:youtu\.be/)([0-9A-Za-z_-]{11})",
    r"(?:shorts/)([0-9A-Za-z_-]{11})",
    r"(?:embed/)([0-9A-Za-z_-]{11})",
]


def normalize_optional(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "undefined"}:
        return None
    if re.fullmatch(r"\$\{[^}]+\}", text):
        return None
    return text


def parse_bool(value, default=False):
    text = normalize_optional(value)
    if text is None:
        return default
    return text.lower() in {"1", "true", "yes", "y", "on"}


def parse_int(value, default):
    text = normalize_optional(value)
    if text is None:
        return default
    return int(text)


def parse_languages(value):
    text = normalize_optional(value) or "zh-Hans,zh,en,ja"
    return [item.strip() for item in re.split(r"[,\n]", text) if item.strip()]


def parse_output_mode(value):
    text = (normalize_optional(value) or "json").lower()
    if text == "text":
        text = "plain-text"
    if text not in {"json", "plain-text", "file-path"}:
        raise ValueError("Unsupported output mode: %s. Use json, plain-text, or file-path." % text)
    return text


def load_inputs(single_input, batch_inputs, inputs_file):
    items = []
    for value in (single_input, batch_inputs):
        text = normalize_optional(value)
        if text:
            items.extend(part.strip() for part in re.split(r"[\r\n,]+", text) if part.strip())
    file_path = normalize_optional(inputs_file)
    if file_path:
        path = Path(file_path).expanduser()
        items.extend(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    unique = []
    seen = set()
    for item in items:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def extract_video_id(input_str):
    for pattern in VIDEO_ID_PATTERNS:
        match = re.search(pattern, input_str)
        if match:
            return match.group(1)
    if re.match(r"^[0-9A-Za-z_-]{11}$", input_str):
        return input_str
    raise ValueError(f"Invalid input: {input_str}")


def import_transcript_api():
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: youtube-transcript-api. Install from requirements.txt before running this tool."
        ) from exc
    return YouTubeTranscriptApi


def import_yt_dlp():
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("Missing dependency: yt-dlp. Install from requirements.txt before running this tool.") from exc
    return yt_dlp


def fetch_video_ids_from_url(url):
    yt_dlp = import_yt_dlp()
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }
    video_ids = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if "entries" in info:
            for entry in info["entries"]:
                if entry and "id" in entry:
                    video_ids.append(entry["id"])
        elif "id" in info:
            video_ids.append(info["id"])
    return video_ids


def load_cache(cache_file):
    path = Path(cache_file)
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def save_cache(cache_file, cache):
    Path(cache_file).write_text(json.dumps(sorted(cache), ensure_ascii=False, indent=2), encoding="utf-8")


def get_transcript_with_retry(video_id, languages, retries):
    YouTubeTranscriptApi = import_transcript_api()
    for attempt in range(retries):
        try:
            api = YouTubeTranscriptApi() if callable(YouTubeTranscriptApi) else YouTubeTranscriptApi
            if hasattr(api, "list"):
                transcripts = api.list(video_id)
            else:
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            for lang in languages:
                try:
                    return transcripts.find_transcript([lang]).fetch()
                except Exception:
                    pass
            for lang in languages:
                try:
                    return transcripts.find_generated_transcript([lang]).fetch()
                except Exception:
                    pass
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise
    return None


def save_transcript(video_id, transcript, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{video_id}.txt"
    with path.open("w", encoding="utf-8") as handle:
        for item in transcript:
            if isinstance(item, dict):
                start = item.get("start", 0.0)
                text = item.get("text", "")
            else:
                start = getattr(item, "start", 0.0)
                text = getattr(item, "text", str(item))
            handle.write(f"[{float(start):.2f}] {text}\n")
    return path


def log_failure(error_log, video_id, error):
    with Path(error_log).open("a", encoding="utf-8") as handle:
        handle.write(f"{video_id}\t{error}\n")


def resolve_video_ids(raw_inputs):
    resolved = []
    parse_errors = []
    for item in raw_inputs:
        try:
            if "youtube.com" in item or "youtu.be" in item:
                resolved.extend(fetch_video_ids_from_url(item))
            else:
                resolved.append(extract_video_id(item))
        except Exception as exc:
            parse_errors.append({"input": item, "error": str(exc)})
    unique = []
    seen = set()
    for item in resolved:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique, parse_errors


def process_video(video_id, languages, retries, cache, use_cache, output_dir, error_log, include_transcript_text, max_chars_per_transcript):
    if use_cache and video_id in cache:
        transcript_file = output_dir / f"{video_id}.txt"
        if transcript_file.exists():
            transcript_text = None
            if include_transcript_text:
                transcript_text = transcript_file.read_text(encoding="utf-8")
                if len(transcript_text) > max_chars_per_transcript:
                    transcript_text = transcript_text[:max_chars_per_transcript]
            return {
                "videoId": video_id,
                "status": "success",
                "source": "cache",
                "transcriptFile": str(transcript_file.resolve()),
                "transcriptText": transcript_text,
                "transcript": transcript_text,
            }

    try:
        transcript = get_transcript_with_retry(video_id, languages, retries)
        if transcript:
            saved = save_transcript(video_id, transcript, output_dir)
            cache.add(video_id)
            transcript_text = None
            if include_transcript_text:
                transcript_text = saved.read_text(encoding="utf-8")
                if len(transcript_text) > max_chars_per_transcript:
                    transcript_text = transcript_text[:max_chars_per_transcript]
            return {
                "videoId": video_id,
                "status": "success",
                "transcriptFile": str(saved.resolve()),
                "transcriptText": transcript_text,
                "transcript": transcript_text,
            }
        return {
            "videoId": video_id,
            "status": "no_sub",
            "transcriptFile": None,
        }
    except Exception as exc:
        log_failure(error_log, video_id, str(exc))
        return {
            "videoId": video_id,
            "status": "fail",
            "transcriptFile": None,
            "error": str(exc),
        }


def build_plan(
    single_input,
    batch_inputs,
    inputs_file,
    languages,
    output_dir,
    cache_file,
    error_log,
    workers,
    retries,
    use_cache,
    output_mode,
    include_transcript_text,
    max_chars_per_transcript,
    dry_run,
    script_dir,
):
    resolved_output_dir = Path(normalize_optional(output_dir) or script_dir / "output").resolve()
    resolved_cache_file = Path(normalize_optional(cache_file) or script_dir / "cache.json").resolve()
    resolved_error_log = Path(normalize_optional(error_log) or script_dir / "error.log").resolve()
    parsed_languages = parse_languages(languages)
    parsed_workers = parse_int(workers, 8)
    parsed_retries = parse_int(retries, 3)
    parsed_use_cache = parse_bool(use_cache, True)
    parsed_output_mode = parse_output_mode(output_mode)
    parsed_include_transcript_text = parse_bool(include_transcript_text, True)
    parsed_max_chars_per_transcript = parse_int(max_chars_per_transcript, 12000)
    parsed_dry_run = parse_bool(dry_run, False)
    raw_inputs = load_inputs(single_input, batch_inputs, inputs_file)
    return {
        "tool": "youtube-transcript",
        "scriptDir": str(script_dir.resolve()),
        "rawInputs": raw_inputs,
        "languages": parsed_languages,
        "outputDir": str(resolved_output_dir),
        "cacheFile": str(resolved_cache_file),
        "errorLog": str(resolved_error_log),
        "workers": parsed_workers,
        "retries": parsed_retries,
        "useCache": parsed_use_cache,
        "outputMode": parsed_output_mode,
        "includeTranscriptText": parsed_include_transcript_text,
        "maxCharsPerTranscript": parsed_max_chars_per_transcript,
        "dryRun": parsed_dry_run,
    }


def execute_plan(plan):
    if not plan["rawInputs"]:
        raise SystemExit("At least one input must be provided.")

    if plan["dryRun"]:
        return plan

    video_ids, parse_errors = resolve_video_ids(plan["rawInputs"])
    cache = load_cache(plan["cacheFile"]) if plan["useCache"] else set()
    output_dir = Path(plan["outputDir"])
    error_log = plan["errorLog"]

    results = []
    counts = {"success": 0, "fail": 0, "skipped": 0, "no_sub": 0}
    with ThreadPoolExecutor(max_workers=plan["workers"]) as executor:
        futures = {
            executor.submit(
                process_video,
                video_id,
                plan["languages"],
                plan["retries"],
                cache,
                plan["useCache"],
                output_dir,
                error_log,
                plan["includeTranscriptText"],
                plan["maxCharsPerTranscript"],
            ): video_id
            for video_id in video_ids
        }
        for future in as_completed(futures):
            item = future.result()
            results.append(item)
            counts[item["status"]] += 1

    if plan["useCache"]:
        save_cache(plan["cacheFile"], cache)

    return {
        "tool": "youtube-transcript",
        "videoIds": video_ids,
        "parseErrors": parse_errors,
        "counts": counts,
        "results": sorted(results, key=lambda item: item["videoId"]),
        "outputDir": plan["outputDir"],
        "cacheFile": plan["cacheFile"],
        "errorLog": plan["errorLog"],
    }


def merge_transcript_text(results):
    sections = []
    for item in results:
        if item.get("status") != "success":
            continue
        text = item.get("transcriptText")
        if not text:
            continue
        sections.append("### " + item["videoId"])
        sections.append(text.strip())
        sections.append("")
    return "\n".join(sections).strip()


def print_json(data):
    if isinstance(data, str):
        print(data)
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))
