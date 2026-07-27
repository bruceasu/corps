import os
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Find the nearest parent directory containing a project .env file."""
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / ".env").is_file():
            return candidate

    return current


def load_env_file(path: Path) -> None:
    """Load key=value pairs from a .env-like file into os.environ.

    Supports lines like `KEY=VALUE`, optional `export ` prefix, and quoted values.
    Expands ~ and environment variables inside values.
    """
    try:
        if not path or not Path(path).is_file():
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if not key:
                    continue
                val = val.strip()
                if (val.startswith("\"") and  val.endswith("\"")):
                    val = val[1:-1]
                    val = os.path.expanduser(os.path.expandvars(val))
                elif (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                else:
                    val = os.path.expanduser(os.path.expandvars(val))
                os.environ[key] = val
    except Exception:
        # Do not fail startup if .env can't be read; caller can log if desired
        return


def load_project_envs(project_root: Path) -> None:
    """Convenience to load common env files in project root and python folder."""
    if not project_root:
        return
    load_env_file(Path(project_root) / ".env")
    # common per-module env file used by notification wrapper
    load_env_file(Path(project_root) / "src" / "python" / "notify_wrapper.env")
