import os
import shutil
import subprocess
import sys
from pathlib import Path


def add_if_value(args, flag, value):
    if value and value.strip():
        args.extend([flag, value])


def parse_options(argv):
    options = {
        "query": "",
        "file": "",
        "host": "",
        "port": "",
        "database": "",
        "user": "",
        "password": "",
        "ssl_mode": "",
        "pass_file": "",
        "tuples_only": "false",
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "-Query" and i + 1 < len(argv):
            options["query"] = argv[i + 1]
            i += 2
        elif arg == "-FilePath" and i + 1 < len(argv):
            options["file"] = argv[i + 1]
            i += 2
        elif arg == "-Host" and i + 1 < len(argv):
            options["host"] = argv[i + 1]
            i += 2
        elif arg == "-Port" and i + 1 < len(argv):
            options["port"] = argv[i + 1]
            i += 2
        elif arg == "-Database" and i + 1 < len(argv):
            options["database"] = argv[i + 1]
            i += 2
        elif arg == "-User" and i + 1 < len(argv):
            options["user"] = argv[i + 1]
            i += 2
        elif arg == "-Password" and i + 1 < len(argv):
            options["password"] = argv[i + 1]
            i += 2
        elif arg == "-SslMode" and i + 1 < len(argv):
            options["ssl_mode"] = argv[i + 1]
            i += 2
        elif arg == "-PassFile" and i + 1 < len(argv):
            options["pass_file"] = argv[i + 1]
            i += 2
        elif arg == "-TuplesOnly" and i + 1 < len(argv):
            options["tuples_only"] = argv[i + 1]
            i += 2
        else:
            raise SystemExit(f"Unknown option: {arg}")
    return options


def main():
    options = parse_options(sys.argv[1:])
    script_dir = Path(__file__).resolve().parent
    native = shutil.which("psql")
    fallback = script_dir / "bin" / ("psql-go.exe" if os.name == "nt" else "psql-go")
    local_pass_file = script_dir / "pgpass.conf"
    if native:
        program = native
    elif fallback.is_file():
        program = str(fallback)
    else:
        raise SystemExit("Neither native psql nor local psql-go fallback was found.")

    cmd = []
    if options["query"].strip():
        cmd.extend(["-c", options["query"]])
    if options["file"].strip():
        cmd.extend(["-f", options["file"]])
    if options["tuples_only"].strip().lower() == "true":
        cmd.append("-t")

    add_if_value(cmd, "-h", options["host"])
    add_if_value(cmd, "-p", options["port"])
    add_if_value(cmd, "-d", options["database"])
    add_if_value(cmd, "-U", options["user"])

    env = os.environ.copy()
    if options["password"].strip():
        env["PGPASSWORD"] = options["password"]
    if options["ssl_mode"].strip():
        env["PGSSLMODE"] = options["ssl_mode"]
    if options["pass_file"].strip():
        env["PGPASSFILE"] = options["pass_file"]
    elif local_pass_file.is_file():
        env["PGPASSFILE"] = str(local_pass_file)

    completed = subprocess.run([program, *cmd], cwd=script_dir, env=env)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
