## 1. Shared policy contract

- [ ] 1.1 Define policy input, decision codes, and structured action outcome with backward-compatible envelope mapping.
- [ ] 1.2 Adapt tool, skill, and MCP dispatch paths to evaluate the contract before execution.
- [ ] 1.3 Add bounded, untrusted observation rendering for agent follow-up prompts.

## 2. Entry-point integration

- [ ] 2.1 Replace the subagent's hard-coded approval with actual caller confirmation and policy evaluation.
- [ ] 2.2 Integrate the policy into DPEF orchestration and workflow agent nodes without duplicating authorization logic.
- [ ] 2.3 Add trace fields for policy decision and safe diagnostics.

## 3. Verification

- [ ] 3.1 Add contract tests for allowed, denied, approval-required, and cancelled delegated actions.
- [ ] 3.2 Add a subagent regression test proving unconfirmed sensitive tools do not execute.
- [ ] 3.3 Add an agent-loop test proving instruction-like tool output is treated as untrusted data.

## TODO

- [ ] Implement only this execution-policy boundary; defer durable workflow state and memory retrieval to their dedicated changes.

## Verification

- [ ] Run the focused agent/subagent contract tests after implementation approval.

## Notes

- %% Confirm how MCP capability metadata exposes auto-execution eligibility before enabling automatic MCP actions.
