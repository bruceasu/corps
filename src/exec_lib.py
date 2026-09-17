import os
from typing import Optional
from pathlib import Path
from _runtime.llm_runtime import LlmRequest, invoke_llm

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

class ExecManager:
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None

    def execute_prompt(self, prompt: str, provider: Optional[str] = None, model: Optional[str] = None, system: Optional[str] = None):
        provider = provider or os.getenv("CORPS_PROVIDER", "openai")
        model = model or os.getenv("CORPS_MODEL", "gpt-4o-mini")
        
        if self.console:
            self.console.print("\n[italic dim]Thinking...[/]")
        else:
            print("\nThinking...")

        result = invoke_llm(LlmRequest.from_prompt(provider, model, prompt, system_prompt=system or ""))
        response = result.text

        if self.console:
            self.console.print(
                Panel(
                    Markdown(response),
                    title="[bold blue]Assistant[/]",
                    border_style="blue",
                    padding=(1, 2),
                )
            )
        else:
            print(response)
        
        return response
