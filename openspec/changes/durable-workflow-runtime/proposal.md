## Problem Statement

Workflow execution keeps a flat context only in memory. It has no run identity, node lifecycle, checkpoint, timeout, cancellation, retry policy, or durable trace. A process interruption loses progress and re-running may repeat unsafe or expensive tools.

## Solution

Evolve the workflow harness into a durable run runtime with validated workflow definitions, node-level state, append-only execution events, checkpoints, retry/timeout policy, and explicit resume semantics.

## User Stories

1. As a workflow user, I want to resume an interrupted workflow from completed nodes, so that work is not repeated unnecessarily.
2. As an operator, I want to inspect a run's node states and failure causes, so that I can diagnose a failed skill.
3. As a workflow author, I want invalid references and duplicate node IDs rejected before execution, so that configuration errors are actionable.
4. As a user, I want timed-out or cancelled work clearly reported, so that I know whether an external action completed.
5. As an operator, I want retries to be explicit and bounded, so that failures do not loop indefinitely.
6. As an existing user, I want existing sequential skills to execute compatibly, so that migration is incremental.

## Implementation Decisions

- Introduce a run model with stable run id, node state, attempt count, input/output references, and event trace.
- Persist checkpoints locally using append-only events plus compact snapshots; resume derives state from persisted records.
- Validate the DAG and variable references before starting a run.
- Separate execution policy from lifecycle management: authorization remains in `agent-execution-policy`.
- Use per-node retry and timeout settings with conservative defaults; do not infer idempotency.

## Testing Decisions

- Test public `WorkflowEngine.execute`/resume behaviour with controllable fake executors and a temporary run store.
- Cover interruption after a completed node, retry exhaustion, timeout/cancellation outcome, invalid DAG definitions, and output-key collision handling.
- Existing engine tests are prior art for workflow construction.

## Out of Scope

- Distributed workers, parallel scheduling, transactional rollback of external tools, remote run storage, and a visual workflow UI.

## Further Notes

%% Automatic replay of non-idempotent external tools must remain disabled unless workflow metadata explicitly declares safe replay behaviour.
