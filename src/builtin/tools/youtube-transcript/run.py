import os
import sys
import argparse
import logging
from pathlib import Path
from youtube_transcript_lib import build_plan, execute_plan, print_json

def main():
    script_dir = Path(__file__).parent.resolve()
    
    parser = argparse.ArgumentParser(description="YouTube Transcript Tool")
    parser.add_argument("--input", help="Single YouTube URL or ID")
    parser.add_argument("--inputs", help="Comma-separated URLs or IDs")
    parser.add_argument("--inputs_file", help="Path to file containing URLs/IDs")
    parser.add_argument("--languages", default="zh-Hans,zh,en,ja", help="Preferred languages")
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--cache_file", help="Cache file path")
    parser.add_argument("--error_log", help="Error log path")
    parser.add_argument("--workers", default="8", help="Worker count")
    parser.add_argument("--retries", default="3", help="Retry count")
    parser.add_argument("--use_cache", default="true", help="Use cache (true/false)")
    parser.add_argument("--output_mode", default="json", help="Output mode (json/plain-text)")
    parser.add_argument("--include_transcript_text", default="true", help="Include text in JSON")
    parser.add_argument("--max_chars_per_transcript", default="12000", help="Max chars")
    parser.add_argument("--dry_run", default="false", help="Dry run (true/false)")

    args = parser.parse_args()

    # Self-healing: Handle 'null', 'None', or empty strings from orchestration
    def clean_param(v, default=None):
        if v is None: return default
        s = str(v).strip().lower()
        if s in ["null", "none", "", "undefined"]: return default
        return str(v).strip()

    single_input = clean_param(args.input)
    batch_inputs = clean_param(args.inputs)
    inputs_file = clean_param(args.inputs_file)
    
    if not any([single_input, batch_inputs, inputs_file]):
        print("Error: No valid input provided (input, inputs, or inputs_file).", file=sys.stderr)
        sys.exit(1)

    try:
        # Use keyword arguments to avoid positional mismatch
        plan = build_plan(
            single_input=single_input,
            batch_inputs=batch_inputs,
            inputs_file=inputs_file,
            languages=clean_param(args.languages, "zh-Hans,zh,en,ja"),
            output_dir=clean_param(args.output_dir),
            cache_file=clean_param(args.cache_file),
            error_log=clean_param(args.error_log),
            workers=clean_param(args.workers, "8"),
            retries=clean_param(args.retries, "3"),
            use_cache=clean_param(args.use_cache, "true"),
            output_mode=clean_param(args.output_mode, "json"),
            include_transcript_text=clean_param(args.include_transcript_text, "true"),
            max_chars_per_transcript=clean_param(args.max_chars_per_transcript, "12000"),
            dry_run=clean_param(args.dry_run, "false"),
            script_dir=script_dir
        )

        results = execute_plan(plan)
        
        output_mode = clean_param(args.output_mode, "json")
        
        if output_mode == "json":
            print_json(results)
        elif output_mode == "file-path":
            paths = [r["transcriptFile"] for r in results["results"] if r.get("transcriptFile")]
            if not paths:
                print("")
            elif len(paths) == 1:
                print(paths[0])
            else:
                # Merge multiple transcripts into one for the LLM
                merged_path = Path(plan["outputDir"]) / "merged_transcripts.txt"
                with merged_path.open("w", encoding="utf-8") as f:
                    for p_str in paths:
                        p = Path(p_str)
                        if p.exists():
                            f.write(f"### {p.stem}\n")
                            f.write(p.read_text(encoding="utf-8"))
                            f.write("\n\n")
                print(str(merged_path.resolve()))
        else:
            # plain-text
            for r in results["results"]:
                if r["status"] == "success":
                    print(f"### {r['videoId']}")
                    print(r["transcriptText"])
                elif r["status"] == "no_sub":
                    print(f"### {r['videoId']} (No transcript found)")
                else:
                    print(f"### {r['videoId']} (Failed: {r.get('error')})")

    except Exception as e:
        logging.error(f"Execution failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
