import argparse
import os
import subprocess
import sys
from pathlib import Path

def add_runtime_path() -> None:
    scripts_dir = os.getenv("CORPS_PYTHON_SCRIPTS_DIR")
    if scripts_dir:
        runtime_dir = Path(scripts_dir).resolve() / "_runtime"
    else:
        runtime_dir = Path(__file__).resolve().parents[3] / "_runtime"
        if not runtime_dir.is_dir():
             runtime_dir = Path(__file__).resolve().parents[2] / "_runtime"
    sys.path.insert(0, str(runtime_dir))

add_runtime_path()

from tool_runtime import emit_result, failure, success

def is_completely_safe(cmd: str) -> bool:
    """Check if a command is a known safe read-only or inspection command."""
    cmd_lower = cmd.lower()
    
    # 1. Broad unsafe tokens (side effects or destructive)
    unsafe_tokens = [
        "-f", "--force", "--hard", "clean", "reset", "checkout", "commit", 
        "push", "install", "uninstall", "update", "mkdir", "touch", 
        "rm ", "del ", ">", ">>", "|", "&&", ";"
    ]
    if any(token in cmd_lower for token in unsafe_tokens):
        return False
    
    # 2. Base command classification
    parts = cmd.split()
    if not parts:
        return False
    base = parts[0].lower()
    if base.endswith(".exe"):
        base = base[:-4]
        
    safe_base_commands = {
        "git", "pytest", "ruff", "black", "isort", "mypy", "ls", "dir", "echo", "cat", "grep", "find", "uv", "pip"
    }
    
    if base in safe_base_commands:
        # Extra granularity for git: only allow read-only subcommands as 'auto-safe'
        if base == "git":
            if len(parts) > 1:
                subcmd = parts[1].lower()
                safe_git_subcmds = {"status", "diff", "log", "show", "branch", "remote", "tag", "rev-parse"}
                return subcmd in safe_git_subcmds
            return True # 'git' alone is safe (shows help)
        
        # 'uv' and 'pip' are only safe if they are 'list' or 'show' (no install/uninstall)
        if base in ["uv", "pip"]:
            if len(parts) > 1:
                subcmd = parts[1].lower()
                return subcmd in ["list", "show", "--version", "help"]
            return True
            
        return True
    
    return False

def prompt_confirmation(cmd: str) -> bool:
    """Prompt the user for confirmation via direct terminal interaction."""
    print(f"\n\x1b[33m⚠️  [SECURITY WARNING] A tool is requesting execution of a modifying or unknown command:\x1b[0m", file=sys.stderr)
    print(f"   Command: \x1b[36m{cmd}\x1b[0m", file=sys.stderr)
    print(f"Proceed with execution? (y/n): ", end="", file=sys.stderr, flush=True)
    
    try:
        # Windows-specific: read from console directly to bypass redirection
        if sys.platform == "win32":
            import msvcrt
            # Flush existing buffer
            while msvcrt.kbhit():
                msvcrt.getch()
            while True:
                ch = msvcrt.getch()
                try:
                    ch_str = ch.decode('utf-8').lower()
                except UnicodeDecodeError:
                    continue
                if ch_str == 'y':
                    print("y", file=sys.stderr)
                    return True
                if ch_str in ['n', '\r', '\n', '\x1b']:
                    print("n", file=sys.stderr)
                    return False
        else:
            # Unix-like: try /dev/tty
            try:
                with open("/dev/tty", "r") as tty:
                    choice = tty.readline().strip().lower()
                    return choice == 'y'
            except Exception:
                # Fallback to stdin
                choice = input().strip().lower()
                return choice == 'y'
    except Exception as e:
        print(f"\n❌ Confirmation failed: {e}", file=sys.stderr)
        return False

def main() -> None:
    parser = argparse.ArgumentParser(description="Execute a shell command.")
    parser.add_argument("--command", required=True)
    args = parser.parse_args()

    cmd = args.command.strip()
    if not cmd:
        emit_result(failure("run-command", "Empty command"))
        sys.exit(1)
    
    # 1. Critical Blacklist (Always Refuse)
    critical_dangerous = ["rm -rf /", "mkfs", "dd if=", "format ", "shutdown", "reboot", "> /dev/"]
    if any(d in cmd.lower() for d in critical_dangerous):
        emit_result(failure("run-command", "❌ Refused: command is on the critical disaster blacklist."))
        sys.exit(1)

    # 2. Safety Classification
    is_safe = is_completely_safe(cmd)
    
    # 3. Whitelist check (base command match)
    whitelist = {
        "python", "python3", "py", "uv", "pip", "git",
        "ls", "dir", "echo", "cat", "mkdir", "touch", "rm", "del",
        "grep", "find", "npm", "node", "npx", "cargo",
        "go", "make", "cmake", "pytest", "ruff", "black", "isort", "mypy"
    }
    
    base_cmd = cmd.split()[0].lower()
    if base_cmd.endswith(".exe"):
        base_cmd = base_cmd[:-4]

    if base_cmd not in whitelist:
        # If not in whitelist, we MUST confirm even if it 'looks' safe
        if not prompt_confirmation(cmd):
            emit_result(failure("run-command", "❌ Execution cancelled by user."))
            sys.exit(1)
    elif not is_safe:
        # Whitelisted but NOT read-only (e.g., git commit, pip install) -> MUST confirm
        if not prompt_confirmation(cmd):
            emit_result(failure("run-command", "❌ Execution cancelled by user (modifying command)."))
            sys.exit(1)

    # 4. Execution
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += "\n--- stderr ---\n" + result.stderr
        
        output = output.strip() or "(No output)"
        
        if result.returncode == 0:
            emit_result(success("run-command", output, {
                "command": cmd,
                "exitCode": result.returncode
            }))
        else:
            emit_result(failure("run-command", f"Command failed with exit code {result.returncode}\n{output}"))
            sys.exit(result.returncode)
            
    except subprocess.TimeoutExpired:
        emit_result(failure("run-command", "❌ Command timed out (30s)"))
        sys.exit(1)
    except Exception as e:
        emit_result(failure("run-command", f"❌ Error executing command: {e}"))
        sys.exit(1)

if __name__ == "__main__":
    main()
