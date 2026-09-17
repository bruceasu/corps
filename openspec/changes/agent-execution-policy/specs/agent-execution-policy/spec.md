## ADDED Requirements

### Requirement: Delegated actions SHALL be policy-gated

Before an agent node or subagent invokes a tool, skill, or MCP action, the runtime SHALL evaluate a shared execution policy. The policy SHALL receive the invocation origin, requested capability, capability metadata, allowlist status, and actual human-confirmation state.

#### Scenario: Unconfirmed sensitive subagent action

- **WHEN** a subagent requests a capability that is not auto-executable and no confirmation was supplied
- **THEN** the capability SHALL not execute
- **AND** the result SHALL state that confirmation is required.

#### Scenario: Explicitly safe delegated action

- **WHEN** an allowlisted capability is marked auto-executable
- **THEN** the policy MAY permit execution without a confirmation prompt
- **AND** the trace SHALL record the policy decision.

### Requirement: The runtime SHALL preserve approval provenance

The subagent SHALL NOT represent an action as confirmed unless an enclosing caller actually supplied confirmation through the approved interface.

#### Scenario: Subagent invoked without approval

- **WHEN** the subagent CLI is invoked without a confirmation grant
- **THEN** its tool dispatch SHALL receive an unconfirmed execution state.

### Requirement: Agent observations SHALL remain untrusted data

The runtime SHALL bound and label tool observations before supplying them to an LLM for a later decision. Observations SHALL NOT modify policy or tool allowlists.

#### Scenario: Tool output contains instructions

- **WHEN** a tool observation contains text requesting another action
- **THEN** the next agent prompt SHALL present it as untrusted data
- **AND** only the execution policy and declared capability list may authorize the later action.
