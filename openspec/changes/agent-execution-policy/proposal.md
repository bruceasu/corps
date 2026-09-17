## Problem Statement

The subagent entry point executes every selected tool or skill as confirmed. This lets an LLM-driven subagent bypass the same approval boundary used by interactive orchestration. Agent decision prompts also consume raw tool observations without a consistent trust boundary.

## Solution

Introduce one explicit execution-policy contract shared by the orchestrator, workflow agent nodes, and subagent tool. The policy decides whether an action may run automatically, must be confirmed, or is denied; it preserves existing safe tool behaviour and makes every decision traceable.

## User Stories

1. As a CLI user, I want sensitive subagent actions to require my approval, so that delegation cannot silently broaden authority.
2. As a workflow author, I want an allowlist and confirmation policy for agent nodes, so that a workflow has predictable authority.
3. As an operator, I want each blocked, confirmed, and executed action recorded, so that I can audit an agent run.
4. As a tool author, I want untrusted tool output clearly isolated from agent instructions, so that tool text cannot change the execution policy.
5. As an existing user, I want unchanged behaviour for tools already declared safe to auto-execute, so that compatible workflows keep working.

## Implementation Decisions

- Define a reusable execution-policy abstraction rather than keeping confirmation decisions in individual callers.
- Default delegated actions to the least authority: denied unless allowlisted, and confirmation is required unless the capability explicitly permits automatic execution.
- Keep interactive confirmation as the authority for approval; the subagent must not manufacture confirmation.
- Return structured policy outcomes that distinguish denied, approval-required, cancelled, failed, and completed actions.
- Use the existing subagent CLI and agent executor seams; do not add a second agent runtime.

## Testing Decisions

- Test externally observable execution outcomes through the subagent and agent-node seams, using fake LLM decisions and fake tools.
- Cover auto-allowed, approval-required, denied, cancelled, and untrusted-observation cases.
- Preserve existing structured-agent contract tests as prior art.

## Out of Scope

- OS sandboxing, new user authentication, remote authorization services, and redesigning individual tool definitions.

## Further Notes

%% MCP actions need the same policy adapter even though their execution path differs from built-in tools.
