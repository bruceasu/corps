import subprocess
import sys
from pathlib import Path


def main():
    script_dir = Path(__file__).resolve().parent
    target = (script_dir.parent / "import-tool" / "generate_control_file.py").resolve()
    command = [sys.executable, str(target), *sys.argv[1:]]
    completed = subprocess.run(command, capture_output=True, text=True, cwd=script_dir)
    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr.rstrip(), file=sys.stderr)
        elif completed.stdout:
            print(completed.stdout.rstrip(), file=sys.stderr)
        raise SystemExit(completed.returncode)

    stdout = completed.stdout.strip()
    prefix = "Generated control file:"
    if stdout.startswith(prefix):
        print(stdout[len(prefix):].strip())
    else:
        print(stdout)


if __name__ == "__main__":
    main()
