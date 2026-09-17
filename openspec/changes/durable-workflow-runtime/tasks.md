## 1. Validation and run model

- [ ] 1.1 Add pre-execution validation for node ids, edges, node types, output keys, and variable references.
- [ ] 1.2 Define WorkflowRun, node lifecycle, event, checkpoint, retry, timeout, and idempotency contracts.
- [ ] 1.3 Replace flat output merges with namespaced context and compatibility reads for existing sequential skills.

## 2. Durable execution

- [ ] 2.1 Implement a local append-only run store with snapshots and inspect/resume APIs.
- [ ] 2.2 Persist lifecycle transitions around every node execution and resume without replaying completed nodes.
- [ ] 2.3 Add bounded retry, timeout, and cancellation adapters for tool and agent nodes.

## 3. Integration and verification

- [ ] 3.1 Integrate durable runs into skill execution while preserving the existing execute API.
- [ ] 3.2 Add tests for definition validation, checkpoints/resume, context collision, retry exhaustion, timeout, and cancellation.
- [ ] 3.3 Add a compatibility test for an existing sequential skill definition.

## TODO

- [ ] Keep scheduling sequential and local; do not add distributed workers or automatic replay of non-idempotent tools.

## Verification

- [ ] Run focused workflow-engine and skill-runtime tests after implementation approval.

## Notes

- %% Decide the default local run-store retention limit before enabling durable storage by default.
