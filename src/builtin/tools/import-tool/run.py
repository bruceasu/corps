import argparse
import copy
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Missing dependency: pyyaml", file=sys.stderr)
    print("Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Wrapper for the bundled import_tool.py")
    parser.add_argument("--command", default="scan", choices=["scan", "run-one"])
    parser.add_argument("--file", default="")
    parser.add_argument("--dir", default="")
    parser.add_argument("--workers", default="")
    parser.add_argument("--dry-run", dest="dry_run", default="false")
    parser.add_argument("--config", default="")
    return parser.parse_args()


def choose_client(name, script_dir):
    native = shutil.which(name)
    if native:
        return native
    suffix = ".exe" if os.name == "nt" else ""
    local_name = {
        "mysql": "mysql-go" + suffix,
        "psql": "psql-go" + suffix,
    }[name]
    local_path = script_dir / "bin" / local_name
    if local_path.is_file():
        return str(local_path)
    raise SystemExit(f"Neither native {name} nor local bundled fallback was found.")


def patched_config_path(script_dir, config_path):
    with open(config_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    config = copy.deepcopy(config or {})
    databases = config.get("databases", {})
    for db in databases.values():
        db_type = str(db.get("type", "")).strip().lower()
        if db_type == "postgres":
            db["psql_path"] = choose_client("psql", script_dir)
            if not db.get("pgpass_file"):
                db["pgpass_file"] = str((script_dir / "config" / "pgpass.conf").resolve())
        elif db_type == "mysql":
            db["mysql_path"] = choose_client("mysql", script_dir)
            if not db.get("defaults_extra_file"):
                db["defaults_extra_file"] = str((script_dir / "config" / "mysql.cnf").resolve())

    fd, temp_name = tempfile.mkstemp(prefix="import-tool-", suffix=".yaml")
    os.close(fd)
    temp_path = Path(temp_name)
    with open(temp_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)
    return temp_path


def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    config_path = Path(args.config).resolve() if args.config.strip() else (script_dir / "config.yaml").resolve()
    import_tool_path = (script_dir / "import_tool.py").resolve()

    patched_config = patched_config_path(script_dir, config_path)
    try:
        command = [sys.executable, str(import_tool_path), "--config", str(patched_config)]
        if args.dry_run.strip().lower() == "true":
            command.append("--dry-run")
        command.append(args.command)
        if args.command == "run-one" and args.file.strip():
            command.extend(["--file", args.file])
        if args.command == "scan" and args.dir.strip():
            command.extend(["--dir", args.dir])
        if args.command == "scan" and args.workers.strip():
            command.extend(["--workers", args.workers])

        completed = subprocess.run(command, cwd=script_dir)
        raise SystemExit(completed.returncode)
    finally:
        patched_config.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
