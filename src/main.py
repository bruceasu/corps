import argparse
import sys
from pathlib import Path
import os

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

# Centralized environment initialization
try:
    from env_loader import find_project_root, load_project_envs
    proj_root = find_project_root(SRC_DIR)
    load_project_envs(proj_root)
    
    # Initialize MCP
    from _runtime.mcp_runtime import mcp_manager
    mcp_manager.initialize_from_env()
    mcp_manager.connect_all()
except Exception:
    pass

def main():
    parser = argparse.ArgumentParser(description="corps: Pure Python AI Toolkit")
    parser.add_argument("--version", action="version", version="corps 2.0 (Pure Python)")
    
    subparsers = parser.add_subparsers(dest="mode", help="Commands")

    # Chat mode
    chat_parser = subparsers.add_parser("chat", help="Start interactive chat session")
    chat_parser.add_argument("--provider", default=os.getenv("CORPS_PROVIDER", "openai"))
    chat_parser.add_argument("--model", default=os.getenv("CORPS_MODEL", "gpt-4o-mini"))
    chat_parser.add_argument("--knowledge-dir", help="Path to knowledge directory")
    chat_parser.add_argument("--system")

    # Knowledge mode
    subparsers.add_parser("knowledge", help="Manage knowledge base")

    # Skill mode
    subparsers.add_parser("skill", help="Manage and run skills")

    # Exec mode
    exec_parser = subparsers.add_parser("exec", help="Execute specific tasks")
    exec_parser.add_argument("--provider", help="LLM provider")
    exec_parser.add_argument("--model", help="LLM model")
    exec_parser.add_argument("--system", help="System prompt")
    exec_parser.add_argument("prompt", nargs="*", help="Prompt text")

    # Tool/Dispatch mode
    subparsers.add_parser("tool", help="Run a specific tool")
    subparsers.add_parser("dispatch", help="Auto-dispatch an instruction to tools/skills")

    # Parse args
    args, unknown = parser.parse_known_args()

    if not args.mode:
        parser.print_help()
        return

    if args.mode == "chat":
        from chat import ChatCli
        knowledge_dir = Path(args.knowledge_dir) if args.knowledge_dir else Path.home() / ".config" / "corps" / "knowledge"
        cli = ChatCli(args.provider, args.model, knowledge_dir, args.system)
        cli.run()
    elif args.mode == "exec":
        from exec_lib import ExecManager
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            # Fallback to interactive chat if no prompt provided
            from chat import ChatCli
            knowledge_dir_val = getattr(args, "knowledge_dir", None)
            knowledge_dir = Path(knowledge_dir_val) if knowledge_dir_val else Path.home() / ".config" / "corps" / "knowledge"
            cli = ChatCli(args.provider, args.model, knowledge_dir, args.system)
            cli.run()
        else:
            manager = ExecManager()
            manager.execute_prompt(prompt, args.provider, args.model, args.system)
    elif args.mode == "knowledge":
        from knowledge import main as knowledge_main
        sys.argv = [sys.argv[0]] + unknown
        knowledge_main()
    elif args.mode == "skill":
        from skills import main as skill_main
        sys.argv = [sys.argv[0]] + unknown
        skill_main()
    elif args.mode == "dispatch" or args.mode == "tool":
        from tools import main as dispatcher_main
        if args.mode == "dispatch":
            sys.argv = [sys.argv[0], "--mode", "dispatch"] + unknown
        else:
            sys.argv = [sys.argv[0]] + unknown
        dispatcher_main()


if __name__ == "__main__":
    main()
