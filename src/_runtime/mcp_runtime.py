from __future__ import annotations

import os
import json
import asyncio
import threading
from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

class MCPManager:
    """Manages multiple MCP server connections and handles sync-to-async bridging."""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.server_params: Dict[str, StdioServerParameters] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._initialized = False

    def _start_event_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def ensure_loop(self):
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._start_event_loop, daemon=True)
            self._thread.start()
            # Wait for loop to be ready
            while self._loop is None or not self._loop.is_running():
                pass

    def initialize_from_env(self):
        """Scans environment variables for MCP_SERVER_<NAME>=<COMMAND>"""
        if not _MCP_AVAILABLE:
            return

        for key, value in os.environ.items():
            if key.startswith("MCP_SERVER_"):
                server_name = key[len("MCP_SERVER_"):].lower()
                # Value can be a simple command or a JSON string with more config
                try:
                    if value.strip().startswith("{"):
                        config = json.loads(value)
                        command = config.get("command")
                        args = config.get("args", [])
                        env = config.get("env")
                    else:
                        parts = value.split()
                        command = parts[0]
                        args = parts[1:]
                        env = None
                    
                    if command:
                        self.server_params[server_name] = StdioServerParameters(
                            command=command,
                            args=args,
                            env=env
                        )
                except Exception as e:
                    print(f"Error parsing MCP server config for {server_name}: {e}")

    async def _connect_server(self, name: str, params: StdioServerParameters):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.sessions[name] = session
                # Keep the session alive - this is tricky in a generic manager
                # For now, we'll need to maintain the context manager scope
                # A better implementation might use a task for each server
                while name in self.sessions:
                    await asyncio.sleep(1)

    def connect_all(self):
        """Attempts to connect to all configured servers."""
        if not _MCP_AVAILABLE:
            return

        self.ensure_loop()
        for name, params in self.server_params.items():
            if name not in self.sessions:
                # We need to run the context manager in a way that stays open
                # This is a simplified version; real production needs more robust lifecycle mgmt
                asyncio.run_coroutine_threadsafe(self._run_session(name, params), self._loop)

    async def _run_session(self, name: str, params: StdioServerParameters):
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.sessions[name] = session
                    # Keep alive until removed from dict
                    try:
                        while name in self.sessions:
                            await asyncio.sleep(0.5)
                    finally:
                        self.sessions.pop(name, None)
        except Exception as e:
            print(f"MCP Server '{name}' connection error: {e}")

    def list_tools(self) -> List[Dict[str, Any]]:
        """Sync wrapper to list all tools from all active sessions."""
        if not self.sessions:
            return []

        all_tools = []
        for name, session in self.sessions.items():
            future = asyncio.run_coroutine_threadsafe(session.list_tools(), self._loop)
            try:
                result = future.result(timeout=10)
                for tool in result.tools:
                    # Prefix tool name to avoid collisions
                    tool_dict = {
                        "name": f"mcp_{name}_{tool.name}",
                        "description": f"[MCP:{name}] {tool.description}",
                        "input_schema": tool.inputSchema,
                        "mcp_server": name,
                        "original_name": tool.name
                    }
                    all_tools.append(tool_dict)
            except Exception as e:
                print(f"Error listing tools for MCP server '{name}': {e}")
        
        return all_tools

    def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Sync wrapper to call an MCP tool."""
        session = self.sessions.get(server_name)
        if not session:
            return {"ok": False, "error": f"MCP server '{server_name}' not connected"}

        future = asyncio.run_coroutine_threadsafe(
            session.call_tool(tool_name, arguments), 
            self._loop
        )
        try:
            result = future.result(timeout=60)
            # Result is usually a List of content parts
            output = ""
            for part in result.content:
                if hasattr(part, 'text'):
                    output += part.text
                else:
                    output += str(part)
            
            return {
                "ok": not result.isError,
                "output": output,
                "data": {}
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def shutdown(self):
        self.sessions.clear()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

# Global instance for runtime use
mcp_manager = MCPManager()
