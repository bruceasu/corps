# Implementation Plan - MCP Integration

Integrate Model Context Protocol (MCP) into the Corps CLI to support external tools and data sources.

## Objectives
- Add `mcp` SDK as a dependency.
- Create `src/_runtime/mcp_runtime.py` to manage MCP server connections via stdio.
- Support MCP server configuration via environment variables (`MCP_SERVER_<NAME>`).
- Integrate MCP tools into the `DPEFOrchestrator` and `ChatCli`.

## Phased Implementation

### Phase 1: Foundation & Dependencies
- Update `requirements.txt` and `pyproject.toml` to include `mcp`.
- Create `src/_runtime/mcp_runtime.py` with an `MCPManager` that handles the sync-to-async bridge.

### Phase 2: Configuration & Connection
- Implement logic in `MCPManager` to scan environment variables for `MCP_SERVER_` prefix.
- Example: `MCP_SERVER_WEATHER="npx @modelcontextprotocol/server-weather"`.
- Support `stdio` transport for connecting to these servers.

### Phase 3: Orchestrator Integration
- Modify `DPEFOrchestrator` to include MCP tools in its internal registry or dynamically fetch them for the LLM prompt.
- Update `_execute_action` to route `mcp` tool calls through `MCPManager`.

### Phase 4: CLI Features
- Add `/mcp` command to `ChatCli` to list connected servers and their tools.
- Add `/mcp-reload` to refresh connections from environment variables.

## Verification
- Verify that MCP servers start correctly.
- Ensure the Agent can successfully call a tool provided by an MCP server.
- Test with standard MCP servers (e.g., weather, filesystem).
