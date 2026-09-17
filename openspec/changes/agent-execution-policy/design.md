## Context

Confirmation is currently decided by several callers. In particular, the standalone subagent passes `True` into both tool and skill dispatch. That makes safety depend on the entry point instead of the requested capability.

## Decision

Create an immutable `ExecutionPolicy` evaluated before any dispatch:

```
requested action -> policy evaluation -> deny | require confirmation | execute
                                      -> structured action outcome -> trace
```

The policy input contains the action identity, action kind, capability metadata, invocation origin, and whether a human confirmation has actually been supplied. It returns a reason code and never executes tools itself.

`DPEFOrchestrator`, `AgentNodeExecutor`, and the subagent wrapper adapt their existing parameters into this policy. The wrapper passes the real confirmation state, not a hard-coded value. Tool output is bounded and labelled as untrusted before it is included in a subsequent LLM prompt.

## Compatibility

- Existing tools marked `autoExecuteAllowed` remain eligible for automatic execution.
- Existing callers that pass an explicit confirmation remain supported.
- Action envelopes retain `ok`, `output`, `data`, and `error`; policy information is additive under `data`.

## Observability

Each trace entry records policy decision, reason code, action identity, and confirmation state. Sensitive argument values must not be copied into policy diagnostics.

## Alternatives Considered

- Keeping a boolean `confirmed` parameter: rejected because it cannot convey origin, denial, or policy reason.
- Making every subagent invocation interactive: rejected because explicitly safe tools should remain automatable.
