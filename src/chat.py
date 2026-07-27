import os
import re
import sys
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

# Optional rich multiline input using prompt_toolkit
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.completion import Completer, Completion, FuzzyCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.shortcuts import CompleteStyle
    from prompt_toolkit.filters import has_completions

    _PROMPT_TOOLKIT_AVAILABLE = True
except Exception:
    _PROMPT_TOOLKIT_AVAILABLE = False

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.live import Live
    from rich.table import Table
    from rich.status import Status
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

from pathlib import Path as _Path_for_env
from datetime import datetime

import chat_helper_lib
from chat_cmds import ChatCliCommandsMixin
from _runtime.llm_runtime import generate_llm_text
from _runtime.mcp_runtime import mcp_manager
from orchestrator import DPEFOrchestrator
from session import ChatSession, SessionManager
from knowledge import ProblemKnowledgeStore

class CommandCompleter(Completer):
    def __init__(self, commands: Dict[str, str], session_manager: SessionManager):
        self.commands = commands
        self.session_manager = session_manager

    def get_completions(self, document, complete_event):
        try:
            text = document.text_before_cursor
            
            # 1. Complete @ files
            if "@" in text:
                # Find the partial path after @
                last_at = text.rfind("@")
                partial_path = text[last_at+1:]
                
                path_obj = Path(partial_path)
                if partial_path.endswith(("/", "\\")):
                    search_dir = path_obj
                    prefix = ""
                else:
                    search_dir = path_obj.parent if partial_path else Path(".")
                    prefix = path_obj.name
                
                if search_dir.exists() and search_dir.is_dir():
                    try:
                        for entry in search_dir.iterdir():
                            if entry.name.startswith(prefix):
                                display_name = entry.name + ("/" if entry.is_dir() else "")
                                yield Completion(
                                    entry.name + ("/" if entry.is_dir() else ""),
                                    start_position=-len(prefix),
                                    display=display_name
                                )
                    except Exception:
                        pass
                return

            if not text.startswith("/"):
                return

            # If it's just "/", show all commands
            if text == "/":
                for cmd, help_text in self.commands.items():
                    yield Completion(
                        f"/{cmd}",
                        start_position=-1,
                        display_meta=help_text
                    )
                return

            parts = text[1:].split(None, 1)
            cmd_part = parts[0].lower()

            # 2. Complete commands (if we are still typing the command name)
            if " " not in text:
                for cmd, help_text in self.commands.items():
                    if cmd.startswith(cmd_part):
                        yield Completion(
                            f"/{cmd}",
                            start_position=-len(text),
                            display_meta=help_text
                        )
                return

            # 3. Complete arguments for specific commands
            if len(parts) >= 1:
                cmd = parts[0].lower()
                arg_part = parts[1] if len(parts) > 1 else ""
                
                # Commands that use active sessions
                if cmd in ["resume", "load", "rm", "archive", "store"]:
                    if self.session_manager.session_dir.exists():
                        for f in self.session_manager.list_sessions():
                            name = f.stem
                            if name.startswith(arg_part):
                                yield Completion(
                                    name,
                                    start_position=-len(arg_part),
                                    display_meta="Active Session"
                                )
                
                # Commands that use archived sessions
                if cmd in ["unarchive", "rm-archive"]:
                    if self.session_manager.archive_dir.exists():
                        for f in self.session_manager.list_archives():
                            name = f.stem
                            if name.startswith(arg_part):
                                yield Completion(
                                    name,
                                    start_position=-len(arg_part),
                                    display_meta="Archived Session"
                                )

                # Commands that use model names
                if cmd in ["model", "next-model"]:
                    rotator = get_rotator()
                    for item in rotator.rotation_list:
                        m_name = item["model"]
                        if m_name.startswith(arg_part):
                            yield Completion(
                                m_name,
                                start_position=-len(arg_part),
                                display_meta=f"Provider: {item['provider']}"
                            )
        except Exception:
            return

class ChatCli(ChatCliCommandsMixin):
    def __init__(self, provider: str, model: str,knowledge_dir: Path, system:str = None):
        self.provider = provider
        self.model = model
        self.knowledge_store = ProblemKnowledgeStore(knowledge_dir)
        self.session_manager = SessionManager()
        self.session = ChatSession(f"session-{datetime_now_str()}")
        self.console = Console() if _RICH_AVAILABLE else None
        self.orchestrator = DPEFOrchestrator(
            knowledge_store=self.knowledge_store,
        )
        self.danger_mode = False  # Default to safe mode
        self._current_status = None # Track rich status object
        self.last_target_lang = None # For /translate memory
        
        # Setup history file
        history_dir = Path.home() / ".config" / "corps"
        history_dir.mkdir(parents=True, exist_ok=True)
        self.history = FileHistory(str(history_dir / "history.txt"))

        self.command_meta = {
            "help": "Show detailed help for all commands",
            "exit": "Exit the chat CLI",
            "cls": "Clear current session messages",
            "list-skills": "List all available skills",
            "list-tools": "List all available tools",
            "mcp": "Show MCP status or GitHub MCP shortcuts: /mcp github <task> ...",
            "gh": "GitHub MCP shortcuts: /gh <task> [params]",
            "store": "Save session: /store [name]",
            "load": "Load session: /load <name>",
            "list-session": "List all saved sessions",
            "resume": "Resume a session: /resume [name]",
            "continue": "Resume the most recent session",
            "summary": "Summarize session and save to knowledge",
            "knowledge": "Explicitly save current session to knowledge base with AI title",
            "skill": "Convert session to skill: /skill <name>",
            "rm": "Delete a session: /rm <name>",
            "archive": "Archive a session: /archive <name>",
            "unarchive": "Restore from archive: /unarchive <name>",
            "list-archive": "List archived sessions",
            "rm-archive": "Delete an archived session",
            "danger": "Toggle danger mode (auto-confirm): /danger [on|off]",
            "translate": "Translate content: /translate [LANG] [polite] <Content>",
            "fix": "Fix typos, casing, and punctuation: /fix <Content>",
            "summarize": "Summarize text in 3 sentences: /summarize <Content>",
            "snarky": "Generate a snarky 3-sentence paragraph: /snarky <Topic>",
            "status": "Show current session and environment status",
            "model": "Change current model: /model <name>",
            "provider": "Change current provider: /provider <name>",
            "set": "Set environment variable: /set KEY=VALUE",
            "rename": "Rename current session: /rename <new_name>",
            "next-model": "Switch to the next available model in rotation"
        }
        if system:
            self.session.add_message("system", system)

    def run(self):
        tips=self._build_prompt_hint()
        builtin_cmds = self._get_builtin_cmds()
        if self.console:
            banner = "\n".join(self._build_startup_banner())
            self.console.print(Panel(
                f"[bold cyan]Corps Chat CLI[/]\n\n{banner}\n"
                f"[dim]Commands:{builtin_cmds}[/]\n"
                f"[dim]Tips: {tips} [/]\n"
                "[dim]Special: use @filename to include file content.",
                border_style="cyan", padding=(1, 2)
            ))
        else:
            for line in self._build_startup_banner():
                print(line)
            print(f"Commands: {builtin_cmds}")
            print(f"Tips: {tips}\n")
            print("Special: use @filename to include file content.")

        while True:
            try:
                user_input = self._read_input()
                if not user_input:
                    continue

                if user_input.startswith("/") or user_input.startswith("!"):
                    if self._handle_command(user_input):
                        break
                    continue

                processed_input = self._process_file_references(user_input)
                self.session.add_message("user", processed_input)
                self._save_session(quiet=True) # Save immediately after user input

                answer = ""
                if self.console:
                    self._current_status = self.console.status("[bold blue]Thinking...[/]", spinner="dots")
                    self._current_status.start()
                    try:
                        answer = self.orchestrator.run_task(
                            self.session, 
                            self.provider, 
                            self.model, 
                            observer=self,
                            confirm_func=self.confirm_action
                        )
                    finally:
                        self._current_status.stop()
                        self._current_status = None
                else:
                    print("\nThinking...")
                    answer = self.orchestrator.run_task(
                        self.session, 
                        self.provider, 
                        self.model, 
                        observer=self,
                        confirm_func=self.confirm_action
                    )
                
                self.session.add_message("assistant", answer)
                self._save_session(quiet=True) # Save again after assistant response

                if self.console:
                    self.console.print(Panel(
                        Markdown(answer),
                        title="[bold blue]Assistant[/]",
                        border_style="blue",
                        padding=(1, 2)
                    ))
                else:
                    print(f"\n{answer}\n")

            except KeyboardInterrupt:
                if self.console:
                    self.console.print("\n[yellow]Interrupted. Type /exit or press Alt+Q to quit.[/]")
                else:
                    print("\nInterrupted. Type /exit or press Alt+Q to quit.")
            except EOFError:
                break
            except Exception as e:
                if self.console:
                    self.console.print(f"\n[red]Error: {e}[/]")
                else:
                    print(f"\nError: {e}")

    def _build_startup_banner(self) -> list[str]:
        return [
            f"Chat session started: {self.session.name}",
            f"Provider: {self.provider}",
            f"Model: {self.model}",
        ]

    def _read_input(self) -> str:
        prompt = self._build_prompt_label()
        
        if _PROMPT_TOOLKIT_AVAILABLE:
            completer = CommandCompleter(self.command_meta, self.session_manager)
            # Wrap with FuzzyCompleter for better matching
            fuzzy_completer = FuzzyCompleter(completer)
            session = PromptSession(
                multiline=True, 
                key_bindings=self._build_prompt_key_bindings(),
                completer=fuzzy_completer,
                complete_while_typing=True,
                history=self.history,
                complete_style=CompleteStyle.MULTI_COLUMN,
                reserve_space_for_menu=6
            )
            try:
                return session.prompt(prompt)
            except KeyboardInterrupt:
                raise
            except EOFError:
                raise

        return self._read_multiline_prompt(input, prompt)

    def _build_prompt_label(self) -> str:
        return f"{self.session.name} > [{self._build_prompt_hint()}] \n"

    def _build_prompt_hint(self) -> str:
        return "Enter 换行, Alt+S 发送, Alt+Q退出"

    def _build_prompt_key_bindings(self):
        key_bindings = KeyBindings()


        @key_bindings.add("enter")
        def _(event):
            buffer = event.app.current_buffer
            
            # If completion menu is visible, select the current completion
            if buffer.complete_state:
                buffer.apply_completion(buffer.complete_state.current_completion)
                return

            text = buffer.text.lstrip()

            if text.endswith("\\"):
                buffer.insert_text("\n")
            elif text.startswith("/") or text.startswith("!"):
                buffer.validate_and_handle()
            else:
                buffer.insert_text("\n")

        @key_bindings.add("escape", "escape")
        def _(event):
            """Double Esc clears the buffer."""
            event.app.current_buffer.reset()

        @key_bindings.add("c-g")
        def _(event):
            """Ctrl+G opens in external editor."""
            event.app.current_buffer.open_in_editor()

        @key_bindings.add("escape", "s")
        def _(event):
            """Alt+S (Escape then s) submits the current multiline buffer."""
            event.app.current_buffer.validate_and_handle()

        @key_bindings.add("escape", "q") # "c-q" 容易冲突，改为 "escape q"
        def _(event):
            """Alt+Qexits immediately from the chat prompt."""
            event.app.exit(result="/exit")

        # Completion navigation with arrow keys
        @key_bindings.add("down", filter=has_completions)
        def _(event):
            event.current_buffer.complete_next()

        @key_bindings.add("up", filter=has_completions)
        def _(event):
            event.current_buffer.complete_previous()

        @key_bindings.add("left", filter=has_completions)
        def _(event):
            event.current_buffer.complete_previous()

        @key_bindings.add("right", filter=has_completions)
        def _(event):
            event.current_buffer.complete_next()

        return key_bindings

    def _read_multiline_prompt(self, read_line, prompt: str) -> str:
        lines: List[str] = []
        line = read_line(prompt)
        if line.startswith("/"):
            return line.strip()

        lines.append(line)
        while self._should_continue("\n".join(lines)):
            line = read_line("... ")
            lines.append(line)

        return "\n".join(lines).strip()

    def _should_continue(self, text: str) -> bool:
        if text.strip().endswith("\\"):
            return True
        if text.count("```") % 2 != 0:
            return True
        return False
    
    def _get_builtin_cmds(self):
        return "/help, /exit, /list-skills, /list-tools, /store <name>, /resume, /continue, /summary, /cls";

    def _handle_command(self, cmd_line: str) -> bool:
        if cmd_line.startswith("!"):
            shell_cmd = cmd_line[1:].strip()
            if not shell_cmd:
                print("Error: Provide shell command after !")
                return False
            
            # Special handling for 'cd' to change current process directory
            if shell_cmd.startswith("cd "):
                target_dir = shell_cmd[3:].strip().strip('"').strip("'")
                try:
                    os.chdir(Path(target_dir).expanduser())
                    print(f"Changed directory to: {os.getcwd()}")
                except Exception as e:
                    print(f"Error changing directory: {e}")
                return False

            print(f"Executing shell command: {shell_cmd}")
            try:
                subprocess.run(shell_cmd, shell=True, check=False)
            except Exception as e:
                print(f"Error executing shell command: {e}")
            return False

        parts = cmd_line[1:].split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler_name = f"_cmd_{cmd.replace('-', '_')}"
        handler = getattr(self, handler_name, None)
        if handler:
            return bool(handler(args))

        print(f"Unknown command: /{cmd}. Type /help for assistance.")
        return False

    def _process_file_references(self, text: str) -> str:
        def log_fn(file_path: str, msg: str):
            if self.console:
                if msg.startswith("Failed"):
                    self.console.print(f"[red]{msg}[/]")
                else:
                    self.console.print(f"[dim]{msg}[/]")
            else:
                print(msg)
        return chat_helper_lib.resolve_file_references(text, log_fn=log_fn)



    def on_plan_updated(self, checklist: List[str]):
        if self.console:
            self.console.print("\n[bold yellow]Plan updated:[/]")
            for item in checklist:
                self.console.print(f"  [yellow][/] {item}")
        else:
            print("\nPlan updated:")
            for item in checklist:
                print(f"  {item}")

    def on_action_started(self, action: Dict[str, Any]):
        if self.console:
            self.console.print(f"\n[bold green]>> Executing:[/] [cyan]{action['action']}:{action['name']}[/]")
        else:
            print(f"\n>> Executing: {action['action']}:{action['name']}")

    def on_action_finished(self, action: Dict[str, Any], result: Dict[str, Any]):
        if result.get("ok"):
            output = result.get('output', '')
            if isinstance(output, str):
                preview = output[:200]
            else:
                preview = str(output)[:200]
            if self.console:
                self.console.print(f"  [bold green]SUCCESS:[/] [dim]{preview}...[/]")
            else:
                print(f"SUCCESS: {preview}")
        else:
            if self.console:
                self.console.print(f"  [bold red]FAILED:[/] {result.get('error')}")
            else:
                print(f"FAILED: {result.get('error')}")

    def _save_session(self, quiet: bool = False):
        try:
            path = self.session_manager.save_session(self.session)
            if not quiet:
                msg = f"Session stored to {path}"
                if self.console:
                    self.console.print(f"[green]{msg}[/]")
                else:
                    print(msg)
        except Exception as e:
            if not quiet:
                print(f"Error auto-saving session: {e}")

    def confirm_action(self, action: Dict[str, Any]) -> bool:
        action_type = action.get("action", "tool")
        
        # 1. Trusted built-in tools do not need confirmation
        if action_type == "tool":
            return True
            
        # 2. If danger mode is ON, auto-confirm everything else
        if self.danger_mode:
            return True
            
        # 3. Otherwise, manual confirmation for skills/external commands
        action_name = action.get("name", "unknown")
        args = action.get("args", {})
        
        # STOP the spinner to ensure the prompt is visible
        was_running = False
        if self._current_status:
            self._current_status.stop()
            was_running = True

        msg = f"\n[bold yellow]SENSITIVE ACTION REQUIRED[/]\nType: {action_type} '{action_name}'\nArgs: {json.dumps(args, ensure_ascii=False)}\nProceed? (y/n): "
        
        if self.console:
            self.console.print(msg, end="")
        else:
            print(msg, end="")
            
        try:
            choice = input().lower().strip()
            result = (choice == 'y')
        except EOFError:
            result = False
        
        # RESTART the spinner if it was running
        if was_running and self._current_status:
            self._current_status.start()
            
        return result


def datetime_now_str() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d-%H%M%S")

