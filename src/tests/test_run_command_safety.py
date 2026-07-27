import sys
import os
from pathlib import Path
import unittest

# Add src and run-command tool dir to path for imports
ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "builtin" / "tools" / "run-command"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOL_DIR))

# Mock emit_result before importing run.py
import tool_runtime
tool_runtime.emit_result = lambda x: None

from run import is_completely_safe

class TestRunCommandSafety(unittest.TestCase):
    def test_completely_safe_commands(self):
        safe_commands = [
            "ls",
            "dir",
            "git status",
            "git diff",
            "git log -n 5",
            "pytest",
            "ruff check .",
            "mypy src",
            "echo hello",
            "cat README.md",
            "grep pattern file.txt",
            "uv list",
            "pip show requests"
        ]
        for cmd in safe_commands:
            with self.subTest(cmd=cmd):
                self.assertTrue(is_completely_safe(cmd), f"'{cmd}' should be considered safe")

    def test_unsafe_modifying_commands(self):
        unsafe_commands = [
            "git commit -m 'feat'",
            "git push origin main",
            "git checkout main",
            "git reset --hard",
            "git clean -fd",
            "pip install requests",
            "uv add requests",
            "mkdir new_dir",
            "touch new_file.txt",
            "rm -rf tmp",
            "ls > files.txt",
            "cat file.txt >> log.txt",
            "pytest --force", # hypothetical unsafe flag
            "git status && rm -rf /",
            "ls; rm -rf /"
        ]
        for cmd in unsafe_commands:
            with self.subTest(cmd=cmd):
                self.assertFalse(is_completely_safe(cmd), f"'{cmd}' should be considered unsafe")

if __name__ == "__main__":
    unittest.main()
