#!/usr/bin/env python3
"""
MagicCode — 从零构建的终端 AI 编程助手。
特性：Tool Use | Markdown 渲染 | Agentic Loop
"""
import os
import json
import glob
import subprocess
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# ========== 配置 ==========
MODEL = os.getenv("MAGIC_MODEL", "gpt-4o")
client = OpenAI()  # 从环境变量读取 OPENAI_API_KEY

SYSTEM_PROMPT = """You are MagicCode, a powerful terminal AI coding assistant.

## Your Tools
- read_file: Read file contents (with line numbers)
- write_file: Write to files (auto-creates directories)
- edit_file: Replace specific text in a file
- run_command: Execute shell commands (30s timeout)
- list_files: List directory structure
- search_code: Search for patterns in code

## Working Principles
1. Always read a file before modifying it
2. Break complex tasks into steps; verify each step
3. Never execute destructive commands (rm -rf, format, etc.)
4. Respond in Markdown format"""

# ========== 工具定义 ==========
def _fn(name, desc, params, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": params, "required": required},
    }}

TOOLS = [
    _fn("read_file", "Read file contents. Returns text with line numbers.",
        {"path": {"type": "string", "description": "File path"}}, ["path"]),
    _fn("write_file", "Write content to a file. Creates directories if needed.",
        {"path": {"type": "string", "description": "File path"},
         "content": {"type": "string", "description": "Complete file content"}}, ["path", "content"]),
    _fn("edit_file", "Replace old_text with new_text in a file (first occurrence).",
        {"path": {"type": "string", "description": "File path"},
         "old_text": {"type": "string", "description": "Text to find"},
         "new_text": {"type": "string", "description": "Replacement text"}}, ["path", "old_text", "new_text"]),
    _fn("run_command", "Execute a shell command with 30-second timeout.",
        {"command": {"type": "string", "description": "Shell command"}}, ["command"]),
    _fn("list_files", "Recursively list directory structure (max 3 levels, ignores .git etc.).",
        {"path": {"type": "string", "description": "Directory path"}}, []),
    _fn("search_code", "Search for a pattern across all files in a directory.",
        {"pattern": {"type": "string", "description": "Search pattern"},
         "path": {"type": "string", "description": "Search directory"}}, ["pattern"]),
]

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

# ========== 工具执行 ==========
def execute_tool(name: str, params: dict) -> str:
    try:
        if name == "read_file":
            with open(params["path"], "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            lines = content.split("\n")
            numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
            return f"📄 {params['path']} ({len(lines)} lines)\n{numbered}"

        elif name == "write_file":
            path = params["path"]
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(params["content"])
            return f"✅ Written to {path} ({len(params['content'])} chars)"

        elif name == "edit_file":
            path = params["path"]
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if params["old_text"] not in content:
                return "❌ Target text not found in file"
            new_content = content.replace(params["old_text"], params["new_text"], 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"✅ Edited {path}"

        elif name == "run_command":
            cmd = params["command"]
            dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd"]
            if any(d in cmd for d in dangerous):
                return "❌ Refused to execute dangerous command"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += "\n--- stderr ---\n" + result.stderr
            return output.strip() or "(No output)"

        elif name == "list_files":
            path = params.get("path", ".")
            lines = []
            def walk(d, prefix="", depth=0):
                if depth >= 3: return
                try: entries = sorted(os.listdir(d))
                except PermissionError: return
                for e in entries:
                    full = os.path.join(d, e)
                    if e in IGNORED_DIRS or e.startswith("."): continue
                    if os.path.isdir(full):
                        lines.append(f"{prefix}📁 {e}/")
                        walk(full, prefix + "  ", depth + 1)
                    else:
                        lines.append(f"{prefix}📄 {e}")
            walk(path)
            return "\n".join(lines[:200]) or "Empty directory"

        elif name == "search_code":
            pattern = params["pattern"]
            path = params.get("path", ".")
            matches = []
            for fp in glob.glob(os.path.join(path, "**", "*"), recursive=True):
                if any(d in fp for d in IGNORED_DIRS) or not os.path.isfile(fp):
                    continue
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if pattern.lower() in line.lower():
                                matches.append(f"{fp}:{i}: {line.rstrip()}")
                                if len(matches) >= 50: break
                except OSError: continue
                if len(matches) >= 50: break
            return "\n".join(matches) or f"No matches for '{pattern}'"

    except Exception as e:
        return f"❌ {type(e).__name__}: {e}"

# ========== Agentic Loop ==========
class MagicCode:
    def __init__(self):
        self.console = Console()
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat(self, user_input: str):
        self.history.append({"role": "user", "content": user_input})
        tool_count = 0

        while True:
            response = client.chat.completions.create(
                model=MODEL, messages=self.history, tools=TOOLS,
            )
            message = response.choices[0].message
            self.history.append(message)

            # 显示文本回复
            if message.content:
                self.console.print(Panel(
                    Markdown(message.content),
                    title="🤖 MagicCode", border_style="blue", padding=(1, 2),
                ))

            # 没有工具调用 → 任务完成
            if not message.tool_calls:
                break

            # 执行每个工具调用
            for tc in message.tool_calls:
                tool_count += 1
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                info = json.dumps(args, ensure_ascii=False)
                if len(info) > 120: info = info[:120] + "..."
                self.console.print(f"  [yellow]🔧 [{tool_count}] {name}[/] [dim]{info}[/]")

                result = execute_tool(name, args)
                preview = result[:100].replace("\n", " ")
                self.console.print(f"  [green]  ✓[/] [dim]{preview}[/]")

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

            # 安全阀：防止无限循环
            if tool_count > 20:
                self.console.print("[red]⚠️ Tool call limit reached (20)[/]")
                break

    def run(self):
        self.console.print(Panel(
            "[bold cyan]🪄 MagicCode[/] — 你的终端 AI 编程助手\n\n"
            "  [green]工具[/]: 读写文件 | 执行命令 | 搜索代码 | 编辑文件\n"
            "  [green]命令[/]: exit 退出 | clear 清空历史",
            border_style="cyan", padding=(1, 2),
        ))
        self.console.print(f"  [dim]📂 {os.getcwd()}[/]")
        self.console.print(f"  [dim]🧠 {MODEL}[/]\n")

        while True:
            try:
                user_input = self.console.input("[bold green]✦ You >[/] ")
                cmd = user_input.strip().lower()
                if cmd in ("exit", "quit"): break
                elif cmd == "clear":
                    self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
                    self.console.print("[dim]🗑️ History cleared[/]")
                    continue
                elif not cmd: continue
                self.chat(user_input)
                self.console.print()
            except KeyboardInterrupt:
                self.console.print("\n[cyan]👋 Goodbye![/]")
                break

if __name__ == "__main__":
    MagicCode().run()