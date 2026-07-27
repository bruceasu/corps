import os
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

try:
    from rich.table import Table
    from rich.panel import Panel
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

import chat_helper_lib
from _runtime.llm_runtime import get_last_used_model_info, get_rotator, skip_current_model
from _runtime.github_mcp import GithubMCPClient

class ChatCliCommandsMixin:
    """
    Mixin class containing slash command handlers (_cmd_*) for ChatCli.
    Dynamically resolved at runtime on ChatCli instances.
    """

    def _cmd_exit(self, args: str) -> bool:
        return True

    def _cmd_help(self, args: str) -> bool:
        if self.console:
            table = Table(title="[bold cyan]Corps CLI Command Help[/]", show_header=True, header_style="bold magenta")
            table.add_column("Command", style="cyan", no_wrap=True)
            table.add_column("Description", style="white")
            
            # Sort commands for better readability
            for c in sorted(self.command_meta.keys()):
                table.add_row(f"/{c}", self.command_meta[c])
            
            self.console.print(table)
        else:
            print("\nCorps CLI Command Help:")
            for c in sorted(self.command_meta.keys()):
                print(f"  /{c:15} {self.command_meta[c]}")
            print()
        return False

    def _cmd_danger(self, args: str) -> bool:
        mode = args.strip().lower()
        if mode == "on":
            self.danger_mode = True
            print("Danger mode ON: Shell commands will auto-confirm.")
        elif mode == "off":
            self.danger_mode = False
            print("Danger mode OFF: Shell commands require manual confirmation.")
        else:
            status = "ON" if self.danger_mode else "OFF"
            print(f"Danger mode is currently {status}. Use /danger [on|off] to toggle.")
        return False

    def _cmd_translate(self, args: str) -> bool:
        words = args.split()
        target_lang = self.last_target_lang or "en"
        is_polite = False
        content_start_idx = 0
        
        lang_map = {
            "zh": "zh", "chinese": "zh", "中文": "zh",
            "en": "en", "english": "en", "英文": "en", "英语": "en",
            "ja": "ja", "japanese": "ja", "日文": "ja", "日语": "ja"
        }
        polite_words = ["polite", "formal", "honorific", "礼貌", "正式", "敬语", "礼貌翻译", "正式翻译", "敬语翻译"]
        
        for _ in range(min(2, len(words))):
            word = words[content_start_idx].lower().strip("[]")
            if word in lang_map:
                target_lang = lang_map[word]
                self.last_target_lang = target_lang
                content_start_idx += 1
            elif any(pw in word for pw in polite_words):
                is_polite = True
                content_start_idx += 1
            else:
                break
        
        content = " ".join(words[content_start_idx:])
        if not content:
            print("Error: Provide content to translate.")
            return False
        
        content = self._process_file_references(content)
        
        if self.console:
            with self.console.status(f"[bold green]Translating to {target_lang}...[/]", spinner="arc"):
                translation = chat_helper_lib.translate_text(
                    self.provider, self.model, content, target_lang, is_polite
                )
            self.console.print(Panel(translation, title=f"Translation ({target_lang})", border_style="green"))
        else:
            print(f"Translating to {target_lang}...")
            translation = chat_helper_lib.translate_text(
                self.provider, self.model, content, target_lang, is_polite
            )
            print(f"\n{translation}\n")
        return False

    def _cmd_fix(self, args: str) -> bool:
        content = self._process_file_references(args.strip())
        if not content:
            print("Error: Provide content to fix.")
            return False
        
        if self.console:
            with self.console.status("[bold yellow]Fixing text...[/]", spinner="bouncingBar"):
                fixed = chat_helper_lib.fix_text(self.provider, self.model, content)
            self.console.print(Panel(fixed, title="Corrected Text", border_style="yellow"))
        else:
            print("Fixing text...")
            fixed = chat_helper_lib.fix_text(self.provider, self.model, content)
            print(f"\n{fixed}\n")
        return False

    def _cmd_summarize(self, args: str) -> bool:
        content = self._process_file_references(args.strip())
        if not content:
            print("Error: Provide content to summarize.")
            return False
        
        if self.console:
            with self.console.status("[bold cyan]Summarizing...[/]", spinner="point"):
                summary = chat_helper_lib.summarize_text(self.provider, self.model, content)
            self.console.print(Panel(summary, title="3-Sentence Summary", border_style="cyan"))
        else:
            print("Summarizing...")
            summary = chat_helper_lib.summarize_text(self.provider, self.model, content)
            print(f"\n{summary}\n")
        return False

    def _cmd_snarky(self, args: str) -> bool:
        content = self._process_file_references(args.strip())
        if not content:
            print("Error: Provide a topic for the snarky paragraph.")
            return False
        
        if self.console:
            with self.console.status("[bold magenta]Generating snark...[/]", spinner="aesthetic"):
                snark = chat_helper_lib.generate_snarky(self.provider, self.model, content)
            self.console.print(Panel(snark, title="Snarky Remark", border_style="magenta"))
        else:
            print("Generating snark...")
            snark = chat_helper_lib.generate_snarky(self.provider, self.model, content)
            print(f"\n{snark}\n")
        return False

    def _cmd_status(self, args: str) -> bool:
        last_info = get_last_used_model_info()
        if self.console:
            table = Table(title="[bold blue]Current CLI Status[/]", show_header=False, border_style="blue")
            table.add_row("Configured Provider", f"[cyan]{self.provider}[/]")
            table.add_row("Configured Model", f"[cyan]{self.model}[/]")
            table.add_row("Last Used Provider", f"[bold green]{last_info['provider']}[/]")
            table.add_row("Last Used Model", f"[bold green]{last_info['model']}[/]")
            table.add_row("Session", f"[green]{self.session.name}[/]")
            table.add_row("Messages", str(len(self.session.messages)))
            table.add_row("Danger Mode", "[red]ON (Auto-confirm)[/]" if self.danger_mode else "[green]OFF (Safe)[/]")
            table.add_row("Last Lang", f"[magenta]{self.last_target_lang or 'None (Default: en)'}[/]")
            table.add_row("Work Dir", f"[yellow]{os.getcwd()}[/]")
            self.console.print(table)
        else:
            print("\nCurrent CLI Status:")
            print(f"  Configured Provider: {self.provider}")
            print(f"  Configured Model:    {self.model}")
            print(f"  Last Used Provider:  {last_info['provider']}")
            print(f"  Last Used Model:     {last_info['model']}")
            print(f"  Session:             {self.session.name}")
            print(f"  Messages:            {len(self.session.messages)}")
            print(f"  Danger Mode:         {'ON' if self.danger_mode else 'OFF'}")
            print(f"  Last Lang:           {self.last_target_lang or 'en'}")
            print(f"  Work Dir:            {os.getcwd()}\n")
        return False

    def _cmd_model(self, args: str) -> bool:
        new_model = args.strip()
        if new_model:
            rotator = get_rotator()
            found_provider = None
            for item in rotator.rotation_list:
                if item["model"] == new_model:
                    found_provider = item["provider"]
                    break
            
            if found_provider:
                self.provider = found_provider
            self.model = new_model
            print(f"Model switched to: {self.model} (Provider: {self.provider or 'default'})")
        else:
            print(f"Current model: {self.model}. Usage: /model <name>")
        return False

    def _cmd_provider(self, args: str) -> bool:
        new_provider = args.strip().lower()
        if new_provider:
            self.provider = new_provider
            print(f"Provider switched to: {self.provider}")
        else:
            print(f"Current provider: {self.provider}. Usage: /provider <name>")
        return False

    def _cmd_set(self, args: str) -> bool:
        if "=" in args:
            key, val = args.split("=", 1)
            key = key.strip()
            val = val.strip()
            os.environ[key] = val
            print(f"Environment variable set: {key}={val}")
        else:
            print("Usage: /set KEY=VALUE")
        return False

    def _cmd_next_model(self, args: str) -> bool:
        target_model = args.strip()
        if target_model:
            rotator = get_rotator()
            found_item = None
            for item in rotator.rotation_list:
                if item["model"] == target_model:
                    found_item = item
                    break
            
            if found_item:
                self.provider = found_item["provider"]
                self.model = found_item["model"]
                print(f"Directly switched to model: {self.model} (Provider: {self.provider})")
            else:
                print(f"Error: Model '{target_model}' not found in rotation list.")
        else:
            skipped = skip_current_model()
            if skipped:
                print(f"Skipping current model {skipped['provider']}:{skipped['model']} and switching to next in rotation...")
                if self.model != "rotation":
                    self.provider = "rotation"
                    self.model = "rotation"
            else:
                print("No active model to skip. Make sure you have made at least one request.")
        return False

    def _cmd_rename(self, args: str) -> bool:
        new_name = args.strip()
        if new_name:
            old_path = self.session_manager.get_session_path(self.session.name)
            self.session.rename(new_name)
            self._save_session(quiet=False)
            if old_path.is_file() and old_path.stem != new_name:
                old_path.unlink()
                print(f"Old session file '{old_path.name}' removed.")
        else:
            print(f"Current session name: {self.session.name}. Usage: /rename <new_name>")
        return False

    def _cmd_cls(self, args: str) -> bool:
        self.session.messages = []
        if self.console:
            self.console.print("[yellow]Current session cleared.[/]")
        else:
            print("Current session cleared.")
        return False

    def _cmd_rm(self, args: str) -> bool:
        name = args.strip()
        if not name:
            print("Error: Provide session name.")
            return False
        try:
            self.session_manager.delete_session(name)
            print(f"Session '{name}' deleted.")
        except Exception as e:
            print(f"Error: {e}")
        return False

    def _cmd_archive(self, args: str) -> bool:
        name = args.strip()
        if not name:
            print("Error: Provide session name.")
            return False
        try:
            self.session_manager.archive_session(name)
            print(f"Session '{name}' archived.")
        except Exception as e:
            print(f"Error: {e}")
        return False

    def _cmd_unarchive(self, args: str) -> bool:
        name = args.strip()
        if not name:
            print("Error: Provide session name.")
            return False
        try:
            self.session_manager.unarchive_session(name)
            print(f"Session '{name}' restored from archive.")
        except Exception as e:
            print(f"Error: {e}")
        return False

    def _cmd_list_archive(self, args: str) -> bool:
        files = self.session_manager.list_archives()
        if self.console:
            self.console.print("[bold]Archived sessions:[/]")
            for f in files:
                mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                self.console.print(f"  [dim]- {f.stem} ({mtime})[/]")
        else:
            print("Archived sessions:")
            for f in files:
                print(f"- {f.stem}")
        return False

    def _cmd_rm_archive(self, args: str) -> bool:
        name = args.strip()
        if not name:
            print("Error: Provide session name.")
            return False
        try:
            self.session_manager.delete_archive(name)
            print(f"Archived session '{name}' deleted.")
        except Exception as e:
            print(f"Error: {e}")
        return False

    def _cmd_store(self, args: str) -> bool:
        name = args.strip() or self.session.name
        self.session.name = name
        path = self.session_manager.save_session(self.session)
        if self.console:
            self.console.print(f"[green]Session stored to {path}[/]")
        else:
            print(f"Session stored to {path}")
        return False

    def _cmd_load(self, args: str) -> bool:
        name = args.strip()
        try:
            self.session = self.session_manager.load_session(name)
            if self.console:
                self.console.print(f"[green]Session '{name}' loaded.[/]")
            else:
                print(f"Session '{name}' loaded.")
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Error: {e}[/]")
            else:
                print(f"Error: {e}")
        return False

    def _cmd_list_session(self, args: str) -> bool:
        files = self.session_manager.list_sessions()
        if self.console:
            self.console.print("[bold]Available sessions:[/]")
            for f in files:
                mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                self.console.print(f"  [green]- {f.stem}[/] [dim]({mtime})[/]")
        else:
            print("Available sessions:")
            for f in files:
                print(f"- {f.stem}")
        return False

    def _cmd_resume(self, args: str) -> bool:
        files = self.session_manager.list_sessions()
        if not args:
            if not files:
                print("No sessions to resume.")
            else:
                self._cmd_list_session("")
        else:
            self._cmd_load(args)
        return False

    def _cmd_continue(self, args: str) -> bool:
        files = self.session_manager.list_sessions()
        if files:
            self._cmd_load(files[0].stem)
        else:
            print("No sessions found to continue.")
        return False

    def _cmd_summary(self, args: str) -> bool:
        if self.console:
            self.console.print("\n[italic dim]Generating concise summary and title...[/]")
        else:
            print("\nGenerating concise summary and title...")
        
        ai_title, summary = chat_helper_lib.generate_session_summary_and_title(
            self.provider, self.model, self.session.to_transcript()
        )
        
        self.knowledge_store.record_chat_session(ai_title, self.session.to_transcript(), summary)
        
        if self.console:
            self.console.print(Panel(
                f"[bold]AI Title:[/] {ai_title}\n\n[bold]Summary:[/]\n{summary}", 
                title="Knowledge Record Saved", 
                border_style="green"
            ))
        else:
            print(f"\nKnowledge Record Saved:")
            print(f"AI Title: {ai_title}")
            print(f"Summary: {summary}\n")
        return False

    def _cmd_knowledge(self, args: str) -> bool:
        if self.console:
            self.console.print("\n[italic dim]Analyzing session for knowledge base...[/]")
        else:
            print("\nAnalyzing session for knowledge base...")
            
        ai_title = chat_helper_lib.generate_session_title(
            self.provider, self.model, self.session.to_transcript()
        )
        
        self.knowledge_store.record_chat_session(ai_title, self.session.to_transcript(), summary="")
        
        if self.console:
            self.console.print(f"[bold green]Session explicitly archived to knowledge base as:[/] {ai_title}")
        else:
            print(f"Session explicitly archived to knowledge base as: {ai_title}")
        return False

    def _cmd_skill(self, args: str) -> bool:
        skill_name = args.strip()
        if not skill_name:
            print("Error: Please provide a skill name. Usage: /skill <name>")
            return False
        
        from skills import create_skill_from_session
        
        if self.console:
            self.console.print(f"\n[italic dim]Generating skill '{skill_name}' from session...[/]")
        else:
            print(f"Generating skill '{skill_name}' from session...")

        try:
            target_dir = create_skill_from_session(
                skill_name,
                self.session.to_transcript(),
                self.session.name,
                self.provider,
                self.model,
                self.orchestrator.skills_dir
            )
            
            msg = f"Skill '{skill_name}' created at {target_dir}"
            if self.console:
                self.console.print(f"[bold green]{msg}[/]")
            else:
                print(msg)
        except Exception as e:
            print(f"Error creating skill: {e}")
        return False

    def _cmd_list_skills(self, args: str) -> bool:
        try:
            skills = list(self.orchestrator.list_skills())
            if not skills:
                print("No skills available.")
                return False
            if self.console:
                self.console.print("[bold]Available Skills:[/]")
                for s in sorted(skills, key=lambda x: x.name):
                    if s.is_dir() and not s.name.startswith("__"):
                        self.console.print(f"  [green]- {s.name}[/]")
            else:
                print("Available Skills:")
                for s in sorted(skills, key=lambda x: x.name):
                    if s.is_dir() and not s.name.startswith("__"):
                        print(f"  - {s.name}")
        except Exception as e:
            print(f"Error listing skills: {e}")
        return False

    def _cmd_list_tools(self, args: str) -> bool:
        try:
            from tools import list_tool_definitions, resolve_tools_dir, builtin_tools_dir
            user_tools = list_tool_definitions(resolve_tools_dir())
            builtin_tools = list_tool_definitions(builtin_tools_dir())
            
            all_tools = user_tools + builtin_tools
            if not all_tools:
                print("No tools available.")
                return False
                
            if self.console:
                self.console.print("[bold]Available Tools:[/]")
                for t in sorted(all_tools, key=lambda x: str(x.get("name") or "")):
                    name = t.get("name")
                    desc = t.get("description", "No description")
                    self.console.print(f"  [cyan]- {name}[/]: [dim]{desc}[/]")
            else:
                print("Available Tools:")
                for t in sorted(all_tools, key=lambda x: str(x.get("name") or "")):
                    name = t.get("name")
                    desc = t.get("description", "No description")
                    print(f"  - {name}: {desc}")
        except Exception as e:
            print(f"Error listing tools: {e}")
        return False

    def _cmd_mcp(self, args: str) -> bool:
        subcmd = args.strip()
        if not subcmd or subcmd.lower() in {"list", "status"}:
            self._print_mcp_status()
            return False

        if subcmd.lower().startswith("github"):
            self._handle_github_mcp(subcmd[6:].strip())
            return False

        print("Usage: /mcp [status|list|github ...]")
        return False

    def _cmd_gh(self, args: str) -> bool:
        subcmd = args.strip()
        if not subcmd or subcmd.lower() in {"help", "list", "--help", "-h"}:
            self._print_github_mcp_help(GithubMCPClient())
            return False

        if subcmd.lower() in {"status", "auth", "whoami"}:
            self._print_github_auth_status(GithubMCPClient())
            return False

        self._handle_github_shortcut(subcmd)
        return False

    def _print_mcp_status(self) -> None:
        client = GithubMCPClient()
        tools = client.list_tools()
        if self.console:
            self.console.print("[bold]MCP Status:[/]")
            if not tools:
                self.console.print("  [yellow]- No GitHub MCP tools available[/]")
                return
            self.console.print("  [green]- GitHub MCP tools:[/]")
            for tool in tools:
                self.console.print(f"    - {tool.get('name')}: {tool.get('description', '')}")
        else:
            print("MCP Status:")
            if not tools:
                print("  - No GitHub MCP tools available")
                return
            print("  GitHub MCP tools:")
            for tool in tools:
                print(f"    - {tool.get('name')}: {tool.get('description', '')}")

    def _handle_github_mcp(self, args: str) -> None:
        client = GithubMCPClient()
        if not args or args.lower() in {"help", "list"}:
            self._print_github_mcp_help(client)
            return

        parts = args.split(None, 1)
        task_key = parts[0].strip().lower()
        if task_key in {"help", "--help", "-h"}:
            self._print_github_mcp_help(client)
            return

        raw_args = parts[1] if len(parts) > 1 else ""
        try:
            payload = GithubMCPClient.parse_arguments(task_key, raw_args)
        except json.JSONDecodeError as exc:
            print(f"Error: GitHub MCP 参数格式错误: {exc}")
            return

        result = client.call(task_key, payload)
        if result.get("ok"):
            output = result.get("output", "")
            if self.console:
                self.console.print(f"[green]{output}[/]" if output else "[green]Done.[/]")
            else:
                print(output or "Done.")
        else:
            print(f"Error: {result.get('error')}")

    def _handle_github_shortcut(self, args: str) -> None:
        parts = args.split(None, 2)
        if not parts:
            self._print_github_mcp_help(GithubMCPClient())
            return

        group = parts[0].lower()
        if group in {"help", "list"}:
            self._print_github_mcp_help(GithubMCPClient())
            return

        if group == "pr":
            if len(parts) == 1 or parts[1].lower() in {"help", "list"}:
                print("用法: /gh pr create <owner> <repo> <title> <head> <base> [body=...] | /gh pr merge <owner> <repo> <number>")
                return
            action = parts[1].lower()
            rest = parts[2] if len(parts) > 2 else ""
            if action in {"create", "new"}:
                self._handle_github_mcp(f"create_pull_request {rest}".strip())
                return
            if action in {"merge", "close"}:
                self._handle_github_mcp(f"merge_pull_request {rest}".strip())
                return

        if group == "issue":
            if len(parts) == 1 or parts[1].lower() in {"help", "list"}:
                print("用法: /gh issue create <owner> <repo> <title> [body=...] | /gh issue list <owner> <repo>")
                return
            action = parts[1].lower()
            rest = parts[2] if len(parts) > 2 else ""
            if action in {"create", "new"}:
                self._handle_github_mcp(f"create_issue {rest}".strip())
                return
            if action in {"list", "ls"}:
                self._handle_github_mcp(f"list_issues {rest}".strip())
                return

        if group in {"wf", "workflow"}:
            if len(parts) == 1 or parts[1].lower() in {"help", "list"}:
                print("用法: /gh wf run <owner> <repo> <workflow> [key=value...]")
                return
            action = parts[1].lower()
            rest = parts[2] if len(parts) > 2 else ""
            if action in {"run", "dispatch"}:
                self._handle_github_mcp(f"workflow_dispatch {rest}".strip())
                return

        legacy_map = {
            "pr-create": "create_pull_request",
            "pr-merge": "merge_pull_request",
            "issue-create": "create_issue",
            "issue-list": "list_issues",
            "wf-run": "workflow_dispatch",
        }
        if group in legacy_map:
            rest = args[len(parts[0]):].strip()
            self._handle_github_mcp(f"{legacy_map[group]} {rest}".strip())
            return

        self._handle_github_mcp(args)

    def _print_github_mcp_help(self, client: GithubMCPClient) -> None:
        tasks = client.describe_tasks()
        if self.console:
            self.console.print("[bold]GitHub MCP 快捷任务:[/]")
            for task in tasks:
                status = "可用" if task.get("available") else "未匹配"
                tool = task.get("tool") or {}
                suffix = f" -> {tool.get('name')}" if tool else ""
                args = " ".join(task.get("positional_args") or [])
                self.console.print(f"  - {task['key']}: {task['label']} [{status}]{suffix}")
                if args:
                    self.console.print(f"    位置参数: {args}")
            self.console.print("  用法: /gh <task> [位置参数...] [key=value...]")
        else:
            print("GitHub MCP 快捷任务:")
            for task in tasks:
                status = "可用" if task.get("available") else "未匹配"
                tool = task.get("tool") or {}
                suffix = f" -> {tool.get('name')}" if tool else ""
                args = " ".join(task.get("positional_args") or [])
                print(f"  - {task['key']}: {task['label']} [{status}]{suffix}")
                if args:
                    print(f"    位置参数: {args}")
            print("  用法: /gh <task> [位置参数...] [key=value...]")

    def _print_github_auth_status(self, client: GithubMCPClient) -> None:
        status = client.auth_status()
        token_vars = status.get("token_vars", [])
        identity_vars = status.get("identity_vars", {})
        if self.console:
            self.console.print("[bold]GitHub 认证状态:[/]")
            self.console.print(f"  server: {status.get('server_name')}")
            self.console.print(f"  has_token: {'yes' if status.get('has_token') else 'no'}")
            self.console.print(f"  token_vars: {', '.join(token_vars) if token_vars else '(none)'}")
            if identity_vars:
                for key, value in identity_vars.items():
                    self.console.print(f"  {key}: {value}")
            else:
                self.console.print("  identity_vars: (none)")
            if status.get("multiple_tokens"):
                self.console.print("  [yellow]注意: 检测到多个 token 来源，实际生效取决于 MCP server 读取顺序[/]")
            self.console.print("  说明: 本地只能看到环境变量状态，精确 GitHub 账号通常要由 MCP server 或 GitHub API 返回")
        else:
            print("GitHub 认证状态:")
            print(f"  server: {status.get('server_name')}")
            print(f"  has_token: {'yes' if status.get('has_token') else 'no'}")
            print(f"  token_vars: {', '.join(token_vars) if token_vars else '(none)'}")
            if identity_vars:
                for key, value in identity_vars.items():
                    print(f"  {key}: {value}")
            else:
                print("  identity_vars: (none)")
            if status.get("multiple_tokens"):
                print("  注意: 检测到多个 token 来源，实际生效取决于 MCP server 读取顺序")
            print("  说明: 本地只能看到环境变量状态，精确 GitHub 账号通常要由 MCP server 或 GitHub API 返回")
