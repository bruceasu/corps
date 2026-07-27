# youtube-transcript

Fetch YouTube transcripts for one or more videos, playlists, or channel video pages.

This workspace tool follows the same external-tool conventions as the other distributed tools in this repository:

- `tool.yaml` and `run.py` live in the same directory
- local resources stay in the same directory by default
- transcript output, cache, and error log default to local paths
- Python is the orchestration layer for better Windows/Linux portability

## Files

- `tool.yaml`: corps tool definition
- `run.py`: CLI-friendly wrapper used by `tool run`
- `youtube_transcript_lib.py`: reusable core logic module
- `get-transcript.py`: compatibility wrapper for the historical script name
- `requirements.txt`: Python dependencies
- `output/`: default transcript output directory at runtime
- `cache.json`: default cache file at runtime
- `error.log`: default error log at runtime

## Dependencies

Install:

```bash
pip install -r requirements.txt
```

Dependencies:

- `youtube-transcript-api`
- `yt-dlp`

## Behavior

- Accepts a single YouTube URL / video ID, multiple URLs / IDs, or an input file
- Supports playlists and channel video pages through `yt-dlp`
- Prefers transcript languages in order, defaulting to `zh-Hans,zh,en,ja`
- Saves one transcript text file per video ID
- Stores processed IDs in a local cache file
- Writes fetch failures to a local error log
- Can inline transcript text into the JSON result for downstream summarization skills
- Supports `outputMode=plain-text` to return merged transcript text only
- Accepts `text` as a compatibility alias for `plain-text`
- Prints a JSON summary to stdout for downstream skills or wrappers

## Examples

Dry-run without external dependencies:

```bash
python run.py --input https://www.youtube.com/watch?v=dQw4w9WgXcQ --output-mode plain-text --dry-run true
```

Single video:

```bash
python run.py --input https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Multiple inputs:

```bash
python run.py --inputs "https://www.youtube.com/watch?v=AAAAAAA1111,https://youtu.be/BBBBBBB2222"
```

Input file:

```bash
python run.py --inputs-file ./videos.txt --output-dir ./output
```

Plain text mode:

```bash
python run.py --input https://www.youtube.com/watch?v=dQw4w9WgXcQ --output-mode plain-text
```
